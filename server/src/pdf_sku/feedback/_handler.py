"""
Feedback 事件处理器。

事件链:
  TaskCompleted → FewShotSyncer.sync_from_task
"""
from __future__ import annotations

from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.feedback.fewshot_sync import FewShotSyncer
import structlog

logger = structlog.get_logger()

_syncer: FewShotSyncer | None = None
_session_factory = None


def init_feedback_handler(
    syncer: FewShotSyncer,
    session_factory,
) -> None:
    global _syncer, _session_factory
    _syncer = syncer
    _session_factory = session_factory

    event_bus.subscribe("TaskCompleted", _on_task_completed)
    logger.info("feedback_handler_registered")


async def _on_task_completed(event: dict) -> None:
    """人工任务完成 → 同步 Few-shot 样本。"""
    if not _syncer or not _session_factory:
        return

    task_id = event.get("task_id", "")
    if not task_id:
        return

    try:
        from uuid import UUID
        from sqlalchemy import select
        from pdf_sku.common.models import HumanTask, Annotation

        async with _session_factory() as db:
            task_result = await db.execute(
                select(HumanTask).where(HumanTask.task_id == UUID(task_id)))
            task = task_result.scalar_one_or_none()
            if not task:
                return

            ann_result = await db.execute(
                select(Annotation).where(Annotation.task_id == UUID(task_id)))
            annotations = list(ann_result.scalars().all())

            if annotations:
                async with db.begin():
                    synced = await _syncer.sync_from_task(db, task, annotations)
                if synced > 0:
                    logger.info("fewshot_synced_from_task",
                                task_id=task_id, synced=synced)
    except Exception as e:
        logger.error("fewshot_sync_error", task_id=task_id, error=str(e))
