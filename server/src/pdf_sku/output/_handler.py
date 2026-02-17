"""
Output 事件处理器。

事件链:
  PageCompleted → IncrementalImporter.import_page_incremental
  TaskCompleted → IncrementalImporter (人工确认后导入)
"""
from __future__ import annotations
import asyncio

from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.output.importer import IncrementalImporter
from pdf_sku.pipeline.ir import PageResult, SKUResult
import structlog

logger = structlog.get_logger()

_importer: IncrementalImporter | None = None
_session_factory = None


def init_output_handler(
    importer: IncrementalImporter,
    session_factory,
) -> None:
    global _importer, _session_factory
    _importer = importer
    _session_factory = session_factory

    event_bus.subscribe("PageCompleted", _on_page_completed)
    event_bus.subscribe("TaskCompleted", _on_task_completed)
    logger.info("output_handler_registered")


async def _on_page_completed(event: dict) -> None:
    """Pipeline 页面完成 → 增量导入。"""
    if not _importer or not _session_factory:
        return

    job_id = event.get("job_id", "")
    page_number = event.get("page_number", 0)
    status = event.get("status", "")
    skus_data = event.get("skus", [])

    if status not in ("AI_COMPLETED",):
        return

    # 重建 PageResult (轻量)
    result = PageResult(
        status=status,
        skus=[SKUResult(
            sku_id=s.get("sku_id", ""),
            attributes=s.get("attributes", {}),
            confidence=s.get("confidence", 0),
            validity=s.get("validity", "invalid"),
            extraction_method=s.get("extraction_method", ""),
        ) for s in skus_data],
    )

    try:
        async with _session_factory() as db:
            async with db.begin():
                await _importer.import_page_incremental(
                    db, job_id, page_number, result)
        logger.debug("page_import_done",
                     job_id=job_id, page=page_number)
    except Exception as e:
        logger.error("page_import_error",
                     job_id=job_id, page=page_number, error=str(e))


async def _on_task_completed(event: dict) -> None:
    """人工任务完成 → 导入人工确认的 SKU。"""
    if not _importer or not _session_factory:
        return

    job_id = event.get("job_id", "")
    page_number = event.get("page_number", 0)

    # 人工任务完成后, 页面 SKU 已更新, 重新导入
    try:
        from pdf_sku.common.models import SKU as SKUModel
        from sqlalchemy import select
        from uuid import UUID

        async with _session_factory() as db:
            result = await db.execute(
                select(SKUModel).where(
                    SKUModel.job_id == UUID(job_id),
                    SKUModel.page_number == page_number,
                    SKUModel.validity == "valid",
                )
            )
            db_skus = result.scalars().all()

            page_result = PageResult(
                status="AI_COMPLETED",
                skus=[SKUResult(
                    sku_id=s.sku_external_id or str(s.sku_id),
                    attributes=s.attributes or {},
                    confidence=s.confidence or 0,
                    validity=s.validity or "valid",
                    extraction_method=s.extraction_method or "human",
                ) for s in db_skus],
            )

            async with db.begin():
                await _importer.import_page_incremental(
                    db, job_id, page_number, page_result, attempt_no=2)

        logger.info("task_completed_import",
                     job_id=job_id, page=page_number, skus=len(db_skus))
    except Exception as e:
        logger.error("task_completed_import_error",
                     job_id=job_id, error=str(e))
