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
import structlog

logger = structlog.get_logger()

PIPELINE_CONCURRENCY_FALLBACK = int(os.environ.get("PIPELINE_CONCURRENCY", "5"))

# Redis key for pipeline concurrency rules
CONCURRENCY_RULES_KEY = "pdf_sku:pipeline_concurrency_rules"

# Default rules: page_threshold → concurrency
DEFAULT_CONCURRENCY_RULES = [
    {"min_pages": 1, "concurrency": 1},
    {"min_pages": 10, "concurrency": 2},
]


async def get_concurrency_for_pages(total_pages: int, redis=None, provider_name: str = "") -> int:
    """Determine pipeline concurrency based on page count and (optionally) provider.

    Two-dimensional matching:
    1. First try provider-specific rules (provider_name matches exactly).
    2. If none found, fall back to global rules (provider_name is empty).
    3. Within matched rules, pick the highest min_pages that total_pages >= min_pages.
    """
    rules = DEFAULT_CONCURRENCY_RULES
    if redis:
        try:
            raw = await redis.get(CONCURRENCY_RULES_KEY)
            if raw:
                rules = json.loads(raw)
        except Exception:
            logger.warning("concurrency_rules_read_failed, using defaults")

    # 1. Filter provider-specific rules
    if provider_name:
        provider_rules = [r for r in rules if r.get("provider_name") == provider_name]
    else:
        provider_rules = []

    if not provider_rules:
        # 2. Fall back to global rules (no provider_name or empty)
        provider_rules = [r for r in rules if not r.get("provider_name")]

    # 3. Sort by min_pages desc, pick the first rule where total_pages >= min_pages
    concurrency = PIPELINE_CONCURRENCY_FALLBACK
    for rule in sorted(provider_rules, key=lambda r: r["min_pages"], reverse=True):
        if total_pages >= rule["min_pages"]:
            concurrency = rule["concurrency"]
            break

    return max(1, concurrency)


class Orchestrator:
    """Job 级处理编排器。"""

    def __init__(
        self,
        page_processor: PageProcessor,
        db_session_factory=None,
        redis=None,
        **_kwargs,
    ) -> None:
        self._pp = page_processor
        self._db_factory = db_session_factory
        self._redis = redis

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

            if not non_blank:
                logger.warning("all_pages_blank", job_id=job_id, total_pages=job.total_pages)
                async with self._db_factory() as final_db:
                    await update_job_status(final_db, job_id, "FULL_IMPORTED", trigger="all_blank")
                    await final_db.commit()
                return

            await self._process_parallel(job, non_blank, file_path)

            # 终态判定 — 用新 session
            async with self._db_factory() as final_db:
                result = await final_db.execute(
                    select(PDFJob).where(PDFJob.job_id == job_uuid))
                fresh_job = result.scalar_one()
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
    ) -> None:
        """并行处理所有页面（Semaphore 控制并发，根据页数动态调整）。"""
        concurrency = await get_concurrency_for_pages(len(pages), self._redis)
        logger.info("pipeline_concurrency",
                     job_id=str(job.job_id),
                     total_pages=len(pages),
                     concurrency=concurrency)
        semaphore = asyncio.Semaphore(concurrency)

        async def process_one(page_no: int):
            async with semaphore:
                async with self._db_factory() as page_db:
                    result = await self._process_single_page(
                        page_db, job, page_no, file_path)
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
                llm_model_used=result.llm_model_used,
                classification_confidence=result.classification_confidence,
                page_confidence=result.page_confidence,
            )
        )

        # 持久化 SKU + Image + Binding（即使无 SKU，也保留商品子图）
        if result.skus or result.images:
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
        from sqlalchemy import delete, update as sa_update
        from pdf_sku.common.models import SKU, Image, SKUImageBinding

        job_dir = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) / str(job_id)
        img_dir = job_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        # 重新处理时清理旧数据，避免唯一约束冲突
        old_sku_ids_result = await db.execute(
            select(SKU.sku_id).where(
                SKU.job_id == job_id,
                SKU.page_number == page_no,
                SKU.superseded == False,  # noqa: E712
            )
        )
        old_sku_ids = [row[0] for row in old_sku_ids_result.fetchall()]
        if old_sku_ids:
            await db.execute(
                delete(SKUImageBinding).where(
                    SKUImageBinding.sku_id.in_(old_sku_ids),
                    SKUImageBinding.job_id == job_id,
                )
            )
            await db.execute(
                sa_update(SKU).where(
                    SKU.job_id == job_id,
                    SKU.page_number == page_no,
                    SKU.superseded == False,  # noqa: E712
                ).values(superseded=True)
            )
        await db.execute(
            delete(Image).where(Image.job_id == job_id, Image.page_number == page_no)
        )

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
                    product_id=sku.product_id or None,
                    variant_label=sku.variant_label or None,
                ))

        for idx, img in enumerate(result.images, start=1):
            if img.search_eligible:
                image_id = img.image_id or f"{str(job_id)[:8]}-{page_no}-{idx}"
                file_rel = f"images/{image_id}.jpg"
                file_abs = job_dir / file_rel
                if img.data:
                    file_abs.write_bytes(img.data)

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
            if binding.image_id:
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
    def _resolve_file_path(job: PDFJob) -> str:
        import os
        base = os.environ.get("JOB_DATA_DIR", "/data/jobs")
        return str(Path(base) / str(job.job_id) / "source.pdf")
