"""
Output 事件处理器。

事件链:
  PageCompleted → IncrementalImporter.import_page_incremental
  TaskCompleted → IncrementalImporter (人工确认后导入)
"""
from __future__ import annotations
import asyncio
from uuid import UUID

from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.output.importer import IncrementalImporter
from pdf_sku.pipeline.ir import PageResult, SKUResult
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

_importer: IncrementalImporter | None = None
_session_factory = None
_output_queue: asyncio.Queue[tuple[str, dict]] | None = None
_output_worker_tasks: list[asyncio.Task] = []


def init_output_handler(
    importer: IncrementalImporter,
    session_factory,
) -> None:
    global _importer, _session_factory, _output_queue, _output_worker_tasks
    _importer = importer
    _session_factory = session_factory
    if _output_queue is None:
        _output_queue = asyncio.Queue(maxsize=settings.output_queue_size)
    if not _output_worker_tasks:
        try:
            loop = asyncio.get_running_loop()
            for idx in range(max(1, settings.output_job_concurrency)):
                _output_worker_tasks.append(loop.create_task(_output_worker(idx + 1)))
        except RuntimeError:
            logger.warning("output_workers_not_started_no_loop")

    event_bus.subscribe("PageCompleted", _on_page_completed)
    event_bus.subscribe("TaskCompleted", _on_task_completed)
    logger.info("output_handler_registered")


async def _on_page_completed(event: dict) -> None:
    """Pipeline 页面完成 → 入队增量导入。"""
    await _enqueue_output_event("page", event)


async def _on_task_completed(event: dict) -> None:
    """人工任务完成 → 入队导入人工确认的 SKU。"""
    await _enqueue_output_event("task", event)


async def _enqueue_output_event(kind: str, event: dict) -> None:
    if not _importer or not _session_factory:
        return

    if not _output_queue:
        asyncio.create_task(_process_output_event(kind, event))
        return

    try:
        _output_queue.put_nowait((kind, dict(event)))
        logger.debug("output_event_enqueued", kind=kind, queue_size=_output_queue.qsize())
    except asyncio.QueueFull:
        logger.warning("output_queue_full_waiting", kind=kind)
        asyncio.create_task(_wait_enqueue_output_event(kind, dict(event)))


async def _wait_enqueue_output_event(kind: str, event: dict) -> None:
    if not _output_queue:
        return
    await _output_queue.put((kind, event))
    logger.debug("output_event_enqueued_delayed", kind=kind, queue_size=_output_queue.qsize())


async def _output_worker(worker_no: int) -> None:
    if not _output_queue:
        return

    logger.info("output_worker_started", worker_no=worker_no)
    while True:
        kind, event = await _output_queue.get()
        try:
            await _process_output_event(kind, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("output_worker_error", worker_no=worker_no, kind=kind)
        finally:
            _output_queue.task_done()


async def _process_output_event(kind: str, event: dict) -> None:
    if kind == "page":
        await _process_page_completed(event)
        return
    if kind == "task":
        await _process_task_completed(event)
        return
    logger.warning("output_unknown_event_kind", kind=kind)


async def _process_page_completed(event: dict) -> None:
    """Pipeline 页面完成 → 增量导入。"""
    if not _importer or not _session_factory:
        return

    job_id = event.get("job_id", "")
    page_number = event.get("page_number", 0)
    status = event.get("status", "")
    skus_data = event.get("skus", [])

    if status not in ("AI_COMPLETED",):
        return

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
            await _importer.import_page_incremental(db, job_id, page_number, result)
            await db.commit()
        logger.debug("page_import_done", job_id=job_id, page=page_number)
    except Exception as e:
        logger.error("page_import_error", job_id=job_id, page=page_number, error=str(e))


async def _process_task_completed(event: dict) -> None:
    """人工任务完成 → 导入人工确认的 SKU。"""
    if not _importer or not _session_factory:
        return

    job_id = event.get("job_id", "")
    page_number = event.get("page_number", 0)

    try:
        from sqlalchemy import select
        from pdf_sku.common.models import SKU as SKUModel

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
                    sku_id=s.sku_id,
                    attributes=s.attributes or {},
                    confidence=0.0,
                    validity=s.validity or "valid",
                    extraction_method="human",
                ) for s in db_skus],
            )
            sku_count = len(db_skus)
            await db.rollback()

            await _importer.import_page_incremental(
                db, job_id, page_number, page_result, attempt_no=2)
            await db.commit()

        logger.info("task_completed_import", job_id=job_id, page=page_number, skus=sku_count)
    except Exception as e:
        logger.error("task_completed_import_error", job_id=job_id, error=str(e))
