"""
Orchestrator — Job 级处理编排。对齐: Pipeline 详设 §5.1

职责:
- 接收 EvaluationCompleted → 启动 Pipeline
- ≤100 页串行, >100 页分片并行 (Semaphore 3)
- 每页完成 → 增量持久化 + 事件发布
- [C2] 终态以 import_status 为准 (INV-04)
- [C4] gather 异常不吞
- [C5] 导入成功后才保存 Checkpoint
"""
from __future__ import annotations
import asyncio
import json
import os
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob, Page
from pdf_sku.common.enums import JobInternalStatus, PageStatus
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.gateway.user_status import update_job_status, refresh_job_page_stats
from pdf_sku.pipeline.ir import PageResult
from pdf_sku.pipeline.page_processor import PageProcessor
from pdf_sku.pipeline.catalog_profiler import scan_catalog, CatalogProfile
import structlog

logger = structlog.get_logger()

PIPELINE_CONCURRENCY = int(os.environ.get("PIPELINE_CONCURRENCY", "5"))


class Orchestrator:
    """Job 级处理编排器。"""

    def __init__(
        self,
        page_processor: PageProcessor,
        db_session_factory=None,
        **_kwargs,
    ) -> None:
        self._pp = page_processor
        self._db_factory = db_session_factory

    @staticmethod
    def _compress_image(data: bytes, max_edge: int = 2000, quality: int = 85) -> bytes:
        """大图压缩: 长边超过 max_edge 时缩放 + 重压缩 JPEG。"""
        from PIL import Image as PILImage
        import io

        buf = io.BytesIO(data)
        with PILImage.open(buf) as im:
            if max(im.size) <= max_edge:
                return data  # 无需压缩
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((max_edge, max_edge), PILImage.LANCZOS)
            out = io.BytesIO()
            im.save(out, "JPEG", quality=quality)
            return out.getvalue()

    async def process_job(
        self,
        db: AsyncSession,
        job: PDFJob,
        evaluation: dict,
    ) -> None:
        """
        Job 处理入口。

        Args:
            db: 数据库会话（仅用于初始状态更新）
            job: PDFJob ORM
            evaluation: 评估结果 dict (route, prescan, ...)
        """
        job_id = str(job.job_id)
        job_uuid = job.job_id
        file_path = self._resolve_file_path(job)
        blank_pages = evaluation.get("prescan", {}).get("blank_pages", [])

        logger.info("pipeline_start",
                     job_id=job_id,
                     total_pages=job.total_pages,
                     route=evaluation.get("route"))

        # 更新路由 & 状态: EVALUATED → PROCESSING
        route = evaluation.get("route")
        if route:
            job.route = route
        await update_job_status(db, job_id, JobInternalStatus.PROCESSING.value,
                                trigger="pipeline_start")
        await db.commit()

        try:
            non_blank = [p for p in range(1, job.total_pages + 1)
                         if p not in blank_pages]

            # 图册级预扫描: 识别主营品类
            catalog_profile = scan_catalog(file_path)

            await self._process_parallel(job, non_blank, file_path,
                                          catalog_profile=catalog_profile)

            # 终态判定 — 用新 session
            async with self._db_factory() as final_db:
                result = await final_db.execute(
                    select(PDFJob).where(PDFJob.job_id == job_uuid))
                fresh_job = result.scalar_one()
                await self._finalize_job(final_db, fresh_job)
                await final_db.commit()

            # 导出 result.json 供前端可视化
            try:
                async with self._db_factory() as export_db:
                    await self._export_result_json(export_db, job_id, file_path)
            except Exception as export_err:
                logger.warning("result_json_export_failed",
                               job_id=job_id, error=str(export_err))

            # 导出 Excel
            try:
                self._export_result_excel(job_id, source_name=job.source_file)
            except Exception as excel_err:
                logger.warning("excel_export_failed",
                               job_id=job_id, error=str(excel_err))

        except Exception as e:
            logger.exception("pipeline_failed", job_id=job_id)
            async with self._db_factory() as err_db:
                await update_job_status(
                    err_db, job_id, JobInternalStatus.PARTIAL_FAILED.value,
                    trigger="pipeline_error", error_message=str(e))
                await err_db.commit()

        self._pp.clear_job_cache(job_id)

    async def _process_parallel(
        self,
        job: PDFJob,
        pages: list[int],
        file_path: str,
        catalog_profile: CatalogProfile | None = None,
    ) -> None:
        """并行处理所有页面（Semaphore 控制并发）。"""
        semaphore = asyncio.Semaphore(PIPELINE_CONCURRENCY)

        async def process_one(page_no: int):
            async with semaphore:
                async with self._db_factory() as page_db:
                    result = await self._process_single_page(
                        page_db, job, page_no, file_path,
                        catalog_profile=catalog_profile)
                    await self._on_page_done(page_db, job, page_no, result)
                    await page_db.commit()

        results = await asyncio.gather(
            *[process_one(p) for p in pages],
            return_exceptions=True,
        )

        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("page_parallel_failed",
                             page_no=pages[i], error=str(r))

    async def _process_single_page(
        self,
        db: AsyncSession,
        job: PDFJob,
        page_no: int,
        file_path: str,
        catalog_profile: CatalogProfile | None = None,
    ) -> PageResult:
        """单页处理 + 异常降级。"""
        try:
            await event_bus.publish("PageStatusChanged", {
                "job_id": str(job.job_id),
                "page_no": page_no,
                "status": "AI_PROCESSING",
            })

            result = await self._pp.process_page(
                job_id=str(job.job_id),
                file_path=file_path,
                page_no=page_no,
                file_hash=job.file_hash or "",
                category=job.category,
                frozen_config_version=job.frozen_config_version,
                catalog_profile=catalog_profile,
            )
            return result

        except Exception as e:
            logger.error("page_processing_error",
                         job_id=str(job.job_id), page_no=page_no, error=str(e))
            return PageResult(
                status="AI_FAILED",
                error=str(e),
                needs_review=True,
            )

    async def _on_page_done(
        self,
        db: AsyncSession,
        job: PDFJob,
        page_no: int,
        result: PageResult,
    ) -> None:
        """
        每页完成: 落库 → 事件 → 人工任务(如需)。
        [C5] 导入成功后才保存 Checkpoint
        """
        # 更新 Page 记录
        status_map = {
            "AI_COMPLETED": PageStatus.AI_COMPLETED.value,
            "SKIPPED": PageStatus.BLANK.value,
            "AI_FAILED": PageStatus.AI_FAILED.value,
            "HUMAN_QUEUED": PageStatus.HUMAN_QUEUED.value,
        }
        new_status = status_map.get(result.status, result.status)

        await db.execute(
            update(Page).where(
                Page.job_id == job.job_id,
                Page.page_number == page_no,
            ).values(
                status=new_status,
                page_type=result.page_type,
                sku_count=len(result.skus),
                needs_review=result.needs_review,
                extraction_method=result.extraction_method,
                classification_confidence=result.classification_confidence,
            )
        )

        # 持久化 SKU + Image + Binding
        if result.skus:
            await self._persist_skus(db, job.job_id, page_no, result)

        # 发布事件
        await event_bus.publish("PageCompleted", {
            "job_id": str(job.job_id),
            "page_no": page_no,
            "status": result.status,
            "sku_count": len(result.skus),
            "needs_review": result.needs_review,
        })

    async def _persist_skus(
        self,
        db: AsyncSession,
        job_id,
        page_no: int,
        result: PageResult,
    ) -> None:
        """持久化 SKU/Image/Binding 到 DB。"""
        from pdf_sku.common.models import SKU, Image, SKUImageBinding

        job_dir = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) / str(job_id)
        img_dir = job_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        for idx, sku in enumerate(result.skus, start=1):
            if sku.validity == "valid":
                bbox = [int(v) for v in sku.source_bbox] if sku.source_bbox else None
                db.add(SKU(
                    sku_id=sku.sku_id or f"SKU-{page_no}-{idx}",
                    job_id=job_id,
                    page_number=page_no,
                    attributes=sku.attributes,
                    validity=sku.validity,
                    source_bbox=bbox,
                    attribute_source="AI_EXTRACTED",
                    status="EXTRACTED",
                ))

        for idx, img in enumerate(result.images, start=1):
            if img.search_eligible:
                image_id = img.image_id or f"{str(job_id)[:8]}-{page_no}-{idx}"
                file_rel = f"images/{image_id}.jpg"
                file_abs = job_dir / file_rel
                if img.data:
                    file_abs.write_bytes(
                        self._compress_image(img.data, max_edge=2000, quality=85)
                    )

                bbox = [int(v) for v in img.bbox] if img.bbox else None
                resolution = [int(img.width), int(img.height)] if img.width and img.height else None
                db.add(Image(
                    image_id=image_id,
                    job_id=job_id,
                    page_number=page_no,
                    role=img.role or "unknown",
                    bbox=bbox,
                    extracted_path=file_rel,
                    format="jpg",
                    resolution=resolution,
                    short_edge=img.short_edge,
                    image_hash=img.image_hash,
                    is_duplicate=img.is_duplicate,
                    search_eligible=img.search_eligible,
                    is_fragmented=img.is_fragmented,
                ))

        for binding in result.bindings:
            if binding.image_id and not binding.is_ambiguous:
                db.add(SKUImageBinding(
                    sku_id=binding.sku_id,
                    image_id=binding.image_id,
                    job_id=job_id,
                    binding_method=binding.method,
                    binding_confidence=binding.confidence,
                    is_ambiguous=binding.is_ambiguous,
                    rank=binding.rank,
                ))

    async def _finalize_job(
        self,
        db: AsyncSession,
        job: PDFJob,
    ) -> None:
        """
        [C2] 终态判定 (以 page status 为准)。
        """
        result = await db.execute(
            select(
                Page.status,
                func.count().label("cnt"),
            ).where(Page.job_id == job.job_id)
            .group_by(Page.status)
        )
        status_counts = {row.status: row.cnt for row in result.all()}

        failed = status_counts.get(PageStatus.AI_FAILED.value, 0)
        human = (status_counts.get(PageStatus.HUMAN_QUEUED.value, 0) +
                 status_counts.get(PageStatus.HUMAN_PROCESSING.value, 0))
        completed = (status_counts.get(PageStatus.AI_COMPLETED.value, 0) +
                     status_counts.get(PageStatus.IMPORTED_CONFIRMED.value, 0) +
                     status_counts.get(PageStatus.IMPORTED_ASSUMED.value, 0))
        blank = status_counts.get(PageStatus.BLANK.value, 0)

        total_valid = sum(status_counts.values()) - blank

        if failed > 0:
            new_status = JobInternalStatus.PARTIAL_FAILED.value
        elif human > 0:
            new_status = JobInternalStatus.PROCESSING.value  # 等 Collaboration
        elif completed >= total_valid and total_valid > 0:
            new_status = JobInternalStatus.FULL_IMPORTED.value
        else:
            new_status = JobInternalStatus.PROCESSING.value
            logger.warning("finalize_incomplete",
                           job_id=str(job.job_id),
                           status_counts=status_counts)

        await refresh_job_page_stats(db, str(job.job_id))
        await update_job_status(db, str(job.job_id), new_status,
                                trigger="pipeline_finalize")

        logger.info("pipeline_finalized",
                     job_id=str(job.job_id),
                     final_status=new_status,
                     completed=completed, failed=failed, human=human)

    @staticmethod
    async def _export_result_json(
        db: AsyncSession, job_id: str, file_path: str,
    ) -> None:
        """将处理结果导出为 result.json，供前端可视化。"""
        from pdf_sku.common.models import SKU, Image, SKUImageBinding

        job_uuid = UUID(job_id)

        # 获取真实文件名
        job_row = (await db.execute(
            select(PDFJob).where(PDFJob.job_id == job_uuid)
        )).scalar_one_or_none()
        real_filename = job_row.source_file if job_row else (file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path)

        # 查询所有页面
        page_rows = (await db.execute(
            select(Page).where(Page.job_id == job_uuid).order_by(Page.page_number)
        )).scalars().all()

        # 查询所有 SKU
        sku_rows = (await db.execute(
            select(SKU).where(SKU.job_id == job_uuid).order_by(SKU.page_number, SKU.sku_id)
        )).scalars().all()

        # 查询所有绑定
        binding_rows = (await db.execute(
            select(SKUImageBinding).where(SKUImageBinding.job_id == job_uuid)
        )).scalars().all()

        # 查询所有图片
        image_rows = (await db.execute(
            select(Image).where(Image.job_id == job_uuid)
        )).scalars().all()

        # 构建 sku_id → image_paths 映射
        img_map = {img.image_id: img.extracted_path for img in image_rows}
        sku_bindings: dict[str, list[str]] = {}
        for b in binding_rows:
            path = img_map.get(b.image_id)
            if path:
                sku_bindings.setdefault(b.sku_id, []).append(f"/images/jobs/{job_id}/{path}")

        # 按页组织 SKU
        skus_by_page: dict[int, list[dict]] = {}
        for sku in sku_rows:
            d = {
                "sku_id": sku.sku_id,
                "attributes": sku.attributes or {},
                "confidence": 0.0,
                "validity": sku.validity or "valid",
                "extraction_method": sku.attribute_source or "",
                "image_paths": sku_bindings.get(sku.sku_id, []),
            }
            skus_by_page.setdefault(sku.page_number, []).append(d)

        pages = []
        total_skus = 0
        for p in page_rows:
            page_skus = skus_by_page.get(p.page_number, [])
            total_skus += len(page_skus)
            pages.append({
                "page_no": p.page_number,
                "status": p.status or "",
                "page_type": p.page_type,
                "fitz_page_class": None,
                "extraction_method": p.extraction_method,
                "slice_count": 0,
                "sku_count": len(page_skus),
                "skus": page_skus,
                "error": None,
            })

        output = {
            "dataset": real_filename,
            "pdf": file_path,
            "total_pages": len(page_rows),
            "total_skus": total_skus,
            "elapsed_seconds": 0,
            "pages": pages,
        }

        job_dir = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) / job_id
        result_path = job_dir / "result.json"
        result_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("result_json_exported", job_id=job_id, path=str(result_path))

    @staticmethod
    def _export_result_excel(job_id: str, source_name: str = "") -> None:
        """从 result.json 生成 Excel 文件。"""
        from pdf_sku.pipeline.exporter.excel_exporter import export_job_excel

        job_dir = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) / job_id
        result_path = job_dir / "result.json"
        if not result_path.exists():
            logger.warning("excel_export_skip_no_json", job_id=job_id)
            return
        result_data = json.loads(result_path.read_text("utf-8"))
        excel_path = job_dir / "result.xlsx"
        export_job_excel(result_data, job_dir, excel_path,
                         source_name=source_name or None)

    @staticmethod
    def _resolve_file_path(job: PDFJob) -> str:
        import os
        base = os.environ.get("JOB_DATA_DIR", "/data/jobs")
        return str(Path(base) / str(job.job_id) / "source.pdf")
