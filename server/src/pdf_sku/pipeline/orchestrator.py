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
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.media_variants import precompute_image_variants, precompute_page_variants
from pdf_sku.common.models import PDFJob, Page
from pdf_sku.common.enums import JobInternalStatus, PageStatus
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.gateway.user_status import update_job_status, refresh_job_page_stats
from pdf_sku.pipeline.ir import PageResult, SKUResult
from pdf_sku.pipeline.page_processor import PageProcessor
from pdf_sku.pipeline.catalog_profiler import scan_catalog, CatalogProfile
from pdf_sku.settings import settings
from pdf_sku.pipeline.extractor.sku_dedup import (
    cross_page_dedup,
    dedup_by_model_variant,
    dedup_material_variants,
)
import structlog

logger = structlog.get_logger()

PIPELINE_CONCURRENCY = int(
    os.environ.get("PIPELINE_CONCURRENCY", str(settings.pipeline_page_concurrency))
)
GLOBAL_PAGE_CONCURRENCY = int(
    os.environ.get("GLOBAL_PAGE_CONCURRENCY", str(settings.global_page_concurrency))
)


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
        self._global_page_slots = asyncio.Semaphore(max(1, GLOBAL_PAGE_CONCURRENCY))

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
                await self._reconcile_persisted_outputs(
                    final_db, fresh_job, catalog_profile=catalog_profile)
                await self._finalize_job(final_db, fresh_job)
                await final_db.commit()

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
            async with semaphore, self._global_page_slots:
                async with self._db_factory() as page_db:
                    result = await self._process_single_page(
                        page_db, job, page_no, file_path,
                        catalog_profile=catalog_profile)
                    page_completed_event = await self._on_page_done(
                        page_db, job, page_no, result
                    )
                    await page_db.commit()
                    await event_bus.publish("PageCompleted", page_completed_event)

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
    ) -> dict:
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

        if result.status != "AI_FAILED":
            job_dir = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) / str(job.job_id)
            source_pdf = Path(self._resolve_file_path(job))
            if source_pdf.exists():
                try:
                    precompute_page_variants(job_dir, source_pdf, page_no)
                except Exception as e:
                    logger.warning(
                        "page_variants_precompute_failed",
                        job_id=str(job.job_id),
                        page_no=page_no,
                        error=str(e),
                    )

        # 持久化 SKU + Image + Binding
        if result.skus:
            await self._persist_skus(db, job.job_id, page_no, result)

        return {
            "job_id": str(job.job_id),
            "page_no": page_no,
            "page_number": page_no,
            "status": result.status,
            "sku_count": len(result.skus),
            "needs_review": result.needs_review,
            "skus": [{
                "sku_id": sku.sku_id,
                "attributes": sku.attributes,
                "confidence": sku.confidence,
                "validity": sku.validity,
                "extraction_method": sku.extraction_method,
            } for sku in result.skus],
        }

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
                    file_abs.write_bytes(img.data)
                    try:
                        precompute_image_variants(job_dir, file_rel, image_id)
                    except Exception as e:
                        logger.warning(
                            "image_variants_precompute_failed",
                            job_id=str(job_id),
                            page_no=page_no,
                            image_id=image_id,
                            error=str(e),
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

    async def _reconcile_persisted_outputs(
        self,
        db: AsyncSession,
        job: PDFJob,
        catalog_profile: CatalogProfile | None = None,
    ) -> None:
        """让数据库中的最终结果尽量与 benchmark JSON 的整理结果一致。"""
        from pdf_sku.common.models import SKU, SKUImageBinding

        sku_rows = list((await db.execute(
            select(SKU)
            .where(
                SKU.job_id == job.job_id,
                SKU.superseded == False,
            )
            .order_by(SKU.page_number, SKU.id)
        )).scalars().all())

        if not sku_rows:
            await self._refresh_page_sku_counts(db, job.job_id)
            return

        survivor_by_removed: dict[str, str] = {}

        if catalog_profile and catalog_profile.is_combo_catalog:
            seen_by_model: dict[str, object] = {}
            for row in sku_rows:
                model = ((row.attributes or {}).get("model_number") or "").strip().upper()
                if model and model in seen_by_model:
                    survivor_by_removed[row.sku_id] = seen_by_model[model].sku_id
                elif model:
                    seen_by_model[model] = row
        else:
            sku_results = [
                SKUResult(
                    sku_id=row.sku_id,
                    attributes=row.attributes or {},
                    source_bbox=tuple(row.source_bbox or (0, 0, 0, 0)),
                    validity=row.validity,
                    confidence=0.0,
                    extraction_method="",
                )
                for row in sku_rows
            ]
            deduped = cross_page_dedup(sku_results, catalog_profile=catalog_profile)
            deduped = dedup_by_model_variant(deduped)
            deduped = dedup_material_variants(deduped)
            kept_ids = {id(s) for s in deduped}

            survivors_by_model: dict[str, str] = {}
            survivors_by_name: dict[str, str] = {}
            for row, sku in zip(sku_rows, sku_results):
                if id(sku) not in kept_ids:
                    continue
                model = ((sku.attributes.get("model_number") or "").strip().upper())
                name = ((sku.attributes.get("product_name") or "").strip())
                if model:
                    survivors_by_model[model] = row.sku_id
                if name:
                    survivors_by_name[name] = row.sku_id

            for row, sku in zip(sku_rows, sku_results):
                if id(sku) in kept_ids:
                    continue
                model = ((sku.attributes.get("model_number") or "").strip().upper())
                name = ((sku.attributes.get("product_name") or "").strip())
                survivor = survivors_by_model.get(model) if model else None
                if not survivor:
                    survivor = survivors_by_name.get(name)
                if survivor and survivor != row.sku_id:
                    survivor_by_removed[row.sku_id] = survivor

        if survivor_by_removed:
            binding_rows = list((await db.execute(
                select(SKUImageBinding).where(SKUImageBinding.job_id == job.job_id)
            )).scalars().all())
            existing_pairs = {(b.sku_id, b.image_id) for b in binding_rows}

            for binding in binding_rows:
                survivor_sku_id = survivor_by_removed.get(binding.sku_id)
                if not survivor_sku_id:
                    continue
                new_pair = (survivor_sku_id, binding.image_id)
                if new_pair in existing_pairs:
                    await db.delete(binding)
                    continue
                existing_pairs.discard((binding.sku_id, binding.image_id))
                binding.sku_id = survivor_sku_id
                existing_pairs.add(new_pair)

            removed_sku_ids = list(survivor_by_removed.keys())
            await db.execute(
                update(SKU)
                .where(SKU.job_id == job.job_id, SKU.sku_id.in_(removed_sku_ids))
                .values(superseded=True)
            )
            logger.info(
                "job_output_reconciled",
                job_id=str(job.job_id),
                removed=len(removed_sku_ids),
                kept=len(sku_rows) - len(removed_sku_ids),
            )

        await self._refresh_page_sku_counts(db, job.job_id)

    async def _refresh_page_sku_counts(self, db: AsyncSession, job_id) -> None:
        from pdf_sku.common.models import SKU

        counts = {
            row.page_number: row.cnt
            for row in (await db.execute(
                select(SKU.page_number, func.count().label("cnt"))
                .where(
                    SKU.job_id == job_id,
                    SKU.superseded == False,
                )
                .group_by(SKU.page_number)
            )).all()
        }

        page_rows = list((await db.execute(
            select(Page).where(Page.job_id == job_id)
        )).scalars().all())
        for page in page_rows:
            page.sku_count = counts.get(page.page_number, 0)

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
    def _resolve_file_path(job: PDFJob) -> str:
        import os
        base = os.environ.get("JOB_DATA_DIR", "/data/jobs")
        return str(Path(base) / str(job.job_id) / "source.pdf")
