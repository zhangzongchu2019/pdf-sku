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

from collections import defaultdict

from pdf_sku.common.events import JobEvent, publish_job_event
from pdf_sku.common.models import PDFJob, Page
from pdf_sku.common.enums import JobInternalStatus, PageStatus
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.gateway.user_status import update_job_status, refresh_job_page_stats
from pdf_sku.pipeline.ir import PageResult, BindingResult
from pdf_sku.pipeline.page_processor import PageProcessor
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

PIPELINE_CONCURRENCY_FALLBACK = int(
    os.environ.get("PIPELINE_CONCURRENCY", str(settings.pipeline_page_concurrency))
)

_SIZE_KEYS = ["size", "尺寸", "规格", "specification", "spec"]

import re as _re
_CHINESE_RE = _re.compile(r'[\u4e00-\u9fff]')


def _mark_hallucinated_skus_invalid(result: PageResult) -> None:
    """将无型号、无尺寸、且商品名仅含 ASCII 通用词的 SKU 标记为 invalid。

    典型场景：LLM 看到生活场景图，按肉眼臆想出 "armchair"/"sofa" 等英文名称，
    但实际 PDF 上无任何产品规格文字可读。
    判断条件（全部满足才标记为 invalid）：
      1. model_number 为空
      2. product_name 不含中文字符
      3. 无任何尺寸/规格属性
    """
    for sku in result.skus:
        if sku.validity != "valid":
            continue
        model = sku.attributes.get("model_number", "")
        name = sku.attributes.get("product_name", "")
        has_size = any(k in sku.attributes for k in _SIZE_KEYS)
        if not model and not _CHINESE_RE.search(name) and not has_size:
            sku.validity = "invalid"
            logger.info("hallucinated_sku_invalidated", sku_id=sku.sku_id, product_name=name)


def _normalize_product_name(name: str) -> str:
    """规范化商品名称，用于合并判断：去括号内容、小写、去空格。
    例："餐桌(Dining Table)" → "餐桌"，"沙发" → "沙发"
    """
    import re
    # 去掉括号及括号内的英文/内容（中英文括号均处理）
    name = re.sub(r'[\(（][^\)）]*[\)）]', '', name)
    return name.strip().lower()


def _merge_by_model_number(result: PageResult) -> None:
    """合并同一页中 model_number 相同且 product_name 相同 的有效 SKU 为一个。

    适用于：LLM 将同一型号同一商品的不同规格识别为独立产品但 product_id 各异时的兜底合并。
    注意：同型号但不同商品名称（如 201# 茶几 vs 201# 电视柜）不合并，保留为独立 SKU。
    _merge_variant_skus 已按 product_id 合并；本函数进一步按 (model_number, product_name) 合并剩余分散项。
    无效 SKU（validity != "valid"）直接透传，不参与合并。
    """
    # 按 (model_number, normalized_product_name) 分组
    by_model_name: dict[tuple[str, str], list] = defaultdict(list)
    no_model = []
    for sku in result.skus:
        model = sku.attributes.get("model_number", "")
        if sku.validity == "valid" and model:
            name = _normalize_product_name(sku.attributes.get("product_name", ""))
            by_model_name[(model, name)].append(sku)
        else:
            no_model.append(sku)

    by_model = by_model_name  # reuse variable name for rest of function

    merged_skus = list(no_model)

    for (model, _name), group in by_model.items():
        if len(group) <= 1:
            merged_skus.extend(group)
            continue

        group_sorted = sorted(group, key=lambda s: s.sku_id)
        primary = group_sorted[0]
        others = group_sorted[1:]

        # 合并规格（与 _merge_variant_skus 逻辑一致）
        all_sizes: list[str] = []
        for sku in group_sorted:
            sz = next((str(sku.attributes[k]) for k in _SIZE_KEYS
                       if k in sku.attributes and isinstance(sku.attributes[k], str)), None)
            if not sz:
                continue
            label = (sku.variant_label or "").strip()
            entry = f"{label}: {sz}" if label else sz
            if entry not in all_sizes:
                all_sizes.append(entry)

        if all_sizes:
            size_key = next((k for k in _SIZE_KEYS if k in primary.attributes), _SIZE_KEYS[0])
            primary.attributes = {**primary.attributes, size_key: all_sizes}

        # 将 others 的绑定移到 primary
        other_ids = {s.sku_id for s in others}
        primary_images = {b.image_id for b in result.bindings if b.sku_id == primary.sku_id}
        max_rank = max((b.rank for b in result.bindings if b.sku_id == primary.sku_id), default=0)

        extra_bindings: list[BindingResult] = []
        for b in result.bindings:
            if b.sku_id in other_ids and b.image_id and b.image_id not in primary_images:
                primary_images.add(b.image_id)
                max_rank += 1
                extra_bindings.append(BindingResult(
                    sku_id=primary.sku_id,
                    image_id=b.image_id,
                    confidence=b.confidence,
                    method=b.method,
                    is_ambiguous=b.is_ambiguous,
                    rank=max_rank,
                ))

        result.bindings = [b for b in result.bindings if b.sku_id not in other_ids]
        result.bindings.extend(extra_bindings)

        logger.info("model_name_skus_merged",
                    model_number=model,
                    product_name=_name,
                    n_merged=len(others),
                    primary_sku=primary.sku_id,
                    sizes=all_sizes)
        merged_skus.append(primary)

    result.skus = merged_skus


def _merge_variant_skus(result: PageResult) -> None:
    """合并同一页中 product_id 相同的多个规格 SKU 为一个。

    - 规格合并为列表，格式 "variant_label: size"（若无 label 则只保留 size）
    - 其余 SKU 的图片绑定重新指向主 SKU（已绑定的图片不重复添加）
    - 非主 SKU 从 result.skus / result.bindings 中移除
    """
    by_product: dict[str, list] = defaultdict(list)
    no_product = []
    for sku in result.skus:
        if sku.product_id:
            by_product[sku.product_id].append(sku)
        else:
            no_product.append(sku)

    merged_skus = list(no_product)

    for product_id, group in by_product.items():
        if len(group) <= 1:
            merged_skus.extend(group)
            continue

        group_sorted = sorted(group, key=lambda s: s.sku_id)
        primary = group_sorted[0]
        others = group_sorted[1:]

        # 合并规格：拼接 variant_label
        all_sizes: list[str] = []
        for sku in group_sorted:
            sz = next((str(sku.attributes[k]) for k in _SIZE_KEYS
                       if k in sku.attributes and isinstance(sku.attributes[k], str)), None)
            if not sz:
                continue
            label = (sku.variant_label or "").strip()
            entry = f"{label}: {sz}" if label else sz
            if entry not in all_sizes:
                all_sizes.append(entry)

        if all_sizes:
            size_key = next((k for k in _SIZE_KEYS if k in primary.attributes), _SIZE_KEYS[0])
            primary.attributes = {**primary.attributes, size_key: all_sizes}

        # 重新指向绑定
        other_ids = {s.sku_id for s in others}
        primary_images = {b.image_id for b in result.bindings if b.sku_id == primary.sku_id}
        max_rank = max((b.rank for b in result.bindings if b.sku_id == primary.sku_id), default=0)

        extra_bindings: list[BindingResult] = []
        for b in result.bindings:
            if b.sku_id in other_ids and b.image_id and b.image_id not in primary_images:
                primary_images.add(b.image_id)
                max_rank += 1
                extra_bindings.append(BindingResult(
                    sku_id=primary.sku_id,
                    image_id=b.image_id,
                    confidence=b.confidence,
                    method=b.method,
                    is_ambiguous=b.is_ambiguous,
                    rank=max_rank,
                ))

        result.bindings = [b for b in result.bindings if b.sku_id not in other_ids]
        result.bindings.extend(extra_bindings)

        logger.info("variant_skus_merged",
                    product_id=product_id,
                    n_merged=len(others),
                    primary_sku=primary.sku_id,
                    sizes=all_sizes,
                    extra_bindings=len(extra_bindings))
        merged_skus.append(primary)

    result.skus = merged_skus

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
        importer=None,
        **_kwargs,
    ) -> None:
        self._pp = page_processor
        self._db_factory = db_session_factory
        self._redis = redis
        self._importer = importer

    async def process_job(
        self,
        db: AsyncSession,
        job: PDFJob,
        evaluation: dict,
        *,
        trace_id: str = "",
        worker_id: str = "",
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
        requested_pages = evaluation.get("pages") or []

        logger.info("pipeline_start",
                     job_id=job_id,
                     total_pages=job.total_pages,
                     route=evaluation.get("route"))

        # 更新路由 & 状态: EVALUATED → PROCESSING
        route = evaluation.get("route")
        if route:
            job.route = route
        if worker_id:
            job.worker_id = worker_id
        await update_job_status(db, job_id, JobInternalStatus.PROCESSING.value,
                                trigger="pipeline_start")
        await db.commit()
        if self._redis:
            await publish_job_event(
                self._redis,
                JobEvent.JOB_STARTED,
                job_id=job_id,
                stage="pipeline",
                status=JobInternalStatus.PROCESSING.value,
                trace_id=trace_id,
            )

        try:
            if requested_pages:
                non_blank = sorted(
                    p for p in requested_pages
                    if 1 <= p <= job.total_pages and p not in blank_pages
                )
            else:
                non_blank = [p for p in range(1, job.total_pages + 1)
                             if p not in blank_pages]

            if not non_blank:
                logger.warning("all_pages_blank", job_id=job_id, total_pages=job.total_pages)
                async with self._db_factory() as final_db:
                    fresh = (
                        await final_db.execute(select(PDFJob).where(PDFJob.job_id == job_uuid))
                    ).scalar_one()
                    await update_job_status(final_db, job_id, "FULL_IMPORTED", trigger="all_blank")
                    await final_db.commit()
                    await self._publish_final_job_event(
                        str(fresh.job_id),
                        JobInternalStatus.FULL_IMPORTED.value,
                        trace_id=trace_id,
                    )
                return

            await self._process_parallel(job, non_blank, file_path, trace_id=trace_id)

            # 终态判定 — 用新 session
            async with self._db_factory() as final_db:
                result = await final_db.execute(
                    select(PDFJob).where(PDFJob.job_id == job_uuid))
                fresh_job = result.scalar_one()
                final_event = await self._finalize_job(final_db, fresh_job, trace_id=trace_id)
                await final_db.commit()
                if final_event:
                    await self._publish_final_job_event(**final_event)

        except Exception as e:
            logger.exception("pipeline_failed", job_id=job_id)
            async with self._db_factory() as err_db:
                await update_job_status(
                    err_db, job_id, JobInternalStatus.PARTIAL_FAILED.value,
                    trigger="pipeline_error", error_message=str(e))
                await err_db.commit()
            await self._publish_final_job_event(
                job_id,
                JobInternalStatus.PARTIAL_FAILED.value,
                trace_id=trace_id,
                error=str(e),
            )

        self._pp.clear_job_cache(job_id)

    async def _process_parallel(
        self,
        job: PDFJob,
        pages: list[int],
        file_path: str,
        *,
        trace_id: str = "",
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
                    start_event = await self._mark_page_processing(page_db, job, page_no)
                    await page_db.commit()
                    await self._publish_page_started(start_event, trace_id=trace_id)

                    result = await self._process_single_page(
                        page_db, job, page_no, file_path, trace_id=trace_id)
                    page_event = await self._on_page_done(
                        page_db, job, page_no, result, trace_id=trace_id)
                    await page_db.commit()
                    await self._publish_page_event(page_event, trace_id=trace_id)

        results = await asyncio.gather(
            *[process_one(p) for p in pages],
            return_exceptions=True,
        )

        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("page_parallel_failed",
                             page_no=pages[i], error=str(r))

    async def _mark_page_processing(
        self,
        db: AsyncSession,
        job: PDFJob,
        page_no: int,
    ) -> dict:
        await db.execute(
            update(Page).where(
                Page.job_id == job.job_id,
                Page.page_number == page_no,
            ).values(status=PageStatus.AI_PROCESSING.value)
        )
        return {
            "job_id": str(job.job_id),
            "page_no": page_no,
            "status": PageStatus.AI_PROCESSING.value,
        }

    async def _publish_page_started(self, page_event: dict, *, trace_id: str = "") -> None:
        await event_bus.publish("PageStarted", page_event)
        if self._redis:
            await publish_job_event(
                self._redis,
                JobEvent.PAGE_STARTED,
                job_id=page_event["job_id"],
                page_no=page_event["page_no"],
                status=page_event["status"],
                trace_id=trace_id,
            )

    async def _process_single_page(
        self,
        db: AsyncSession,
        job: PDFJob,
        page_no: int,
        file_path: str,
        *,
        trace_id: str = "",
    ) -> PageResult:
        """单页处理 + 异常降级。"""
        try:
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
        *,
        trace_id: str = "",
    ) -> dict:
        """
        每页完成: 落库 → 事件 → 人工任务(如需)。
        [C5] 导入成功后才保存 Checkpoint
        """
        # 1. 幻觉检测：无型号+无中文+无尺寸的 SKU 标记为 invalid
        _mark_hallucinated_skus_invalid(result)
        # 2. 合并同 product_id 的多规格变体
        _merge_variant_skus(result)
        # 3. 合并同型号但 product_id 不同的变体（LLM 错误地分配了不同 product_id）
        _merge_by_model_number(result)
        # 4. 清理无效 SKU 的绑定，避免 FK 异常
        _invalid_ids = {s.sku_id for s in result.skus if s.validity != "valid"}
        if _invalid_ids:
            result.bindings = [b for b in result.bindings if b.sku_id not in _invalid_ids]

        # 只统计有效 SKU 数量（与 _persist_skus 中实际入库的保持一致）
        valid_sku_count = len([s for s in result.skus if s.validity == "valid"])

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
                sku_count=valid_sku_count,
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

        if self._importer:
            await self._importer.import_page_incremental(
                db,
                str(job.job_id),
                page_no,
                result,
            )

        # 将处理时使用的截图缓存到磁盘，保证坐标系与 bbox 一致
        # （密集页面使用 216dpi 渲染，不落盘则 API 会以 150dpi 重新渲染导致 bbox 错位）
        if result.screenshot:
            import os as _os
            _job_dir = Path(_os.environ.get("JOB_DATA_DIR", "/data/jobs")) / str(job.job_id)
            _ss_dir = _job_dir / "screenshots"
            _ss_dir.mkdir(parents=True, exist_ok=True)
            (_ss_dir / f"page-{page_no}.png").write_bytes(result.screenshot)

        # 同步更新 Job 级别的页面统计数组，保持与前端进度条一致
        await refresh_job_page_stats(db, str(job.job_id))

        # 发布事件
        event_name = "PageFailed" if new_status == PageStatus.AI_FAILED.value else "PageCompleted"
        redis_event = JobEvent.PAGE_FAILED if new_status == PageStatus.AI_FAILED.value else JobEvent.PAGE_COMPLETED
        return {
            "event_name": event_name,
            "redis_event": redis_event,
            "job_id": str(job.job_id),
            "page_number": page_no,
            "page_no": page_no,
            "status": result.status,
            "sku_count": valid_sku_count,
            "needs_review": result.needs_review,
            "error": result.error,
            "skus": [
                {
                    "sku_id": sku.sku_id,
                    "attributes": sku.attributes,
                    "confidence": sku.confidence,
                    "validity": sku.validity,
                    "extraction_method": result.extraction_method,
                }
                for sku in result.skus
            ],
            "new_status": new_status,
        }

    async def _publish_page_event(self, page_event: dict, *, trace_id: str = "") -> None:
        event_name = page_event["event_name"]
        event_payload = {k: v for k, v in page_event.items() if k not in {"event_name", "redis_event", "new_status"}}
        await event_bus.publish(event_name, event_payload)

        if self._redis:
            await publish_job_event(
                self._redis,
                page_event["redis_event"],
                job_id=page_event["job_id"],
                page_no=page_event["page_no"],
                status=page_event["new_status"],
                sku_count=page_event["sku_count"],
                trace_id=trace_id,
                extra={
                    "needs_review": page_event["needs_review"],
                    "error": page_event["error"],
                },
            )

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
        *,
        trace_id: str = "",
    ) -> dict | None:
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
        return {
            "job_id": str(job.job_id),
            "status": new_status,
            "total_skus": job.total_skus or 0,
            "total_images": job.total_images or 0,
            "duration_sec": max(
                0.0,
                (datetime.now(timezone.utc) - job.created_at).total_seconds(),
            ) if getattr(job, "created_at", None) else 0.0,
            "trace_id": trace_id,
        }

    @staticmethod
    def _resolve_file_path(job: PDFJob) -> str:
        import os
        base = os.environ.get("JOB_DATA_DIR", "/data/jobs")
        return str(Path(base) / str(job.job_id) / "source.pdf")

    async def _publish_final_job_event(
        self,
        job_id: str,
        status: str,
        *,
        total_skus: int = 0,
        total_images: int = 0,
        duration_sec: float = 0.0,
        trace_id: str = "",
        error: str | None = None,
    ) -> None:
        if not self._redis:
            return

        if status == JobInternalStatus.FULL_IMPORTED.value:
            event = JobEvent.JOB_COMPLETED
        elif status == JobInternalStatus.PARTIAL_FAILED.value:
            event = JobEvent.JOB_FAILED
        elif status == JobInternalStatus.DEGRADED_HUMAN.value:
            event = JobEvent.HUMAN_NEEDED
        else:
            event = JobEvent.JOB_STAGE_CHANGED

        await publish_job_event(
            self._redis,
            event,
            job_id=job_id,
            status=status,
            trace_id=trace_id,
            error=error,
            extra={
                "total_skus": total_skus,
                "total_images": total_images,
                "duration_sec": duration_sec,
            } if event == JobEvent.JOB_COMPLETED else None,
        )
