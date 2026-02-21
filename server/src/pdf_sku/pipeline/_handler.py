"""
Pipeline 事件处理器。

监听 EvaluationCompleted → 启动 Pipeline。
"""
from __future__ import annotations
import asyncio
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob
from pdf_sku.common.enums import JobInternalStatus, HumanTaskType
from pdf_sku.collaboration.annotation_service import TaskManager
from pdf_sku.gateway.user_status import update_job_status, refresh_job_page_stats
from pdf_sku.gateway.event_bus import event_bus
import structlog

logger = structlog.get_logger()

_orchestrator = None
_db_session_factory = None
_task_manager: TaskManager | None = None


def init_handler(orchestrator, session_factory, task_manager: TaskManager | None = None) -> None:
    """初始化并注册事件监听。"""
    global _orchestrator, _db_session_factory, _task_manager
    _orchestrator = orchestrator
    _db_session_factory = session_factory
    _task_manager = task_manager or TaskManager()
    event_bus.subscribe("EvaluationCompleted", _on_evaluation_completed)
    logger.info("pipeline_handler_registered")


async def _on_evaluation_completed(data: dict) -> None:
    """处理 EvaluationCompleted → 启动 Pipeline。"""
    job_id = data.get("job_id", "")
    route = data.get("route", "HUMAN_ALL")

    # HUMAN_ALL → 不走 Pipeline, 直接进人工
    if route == "HUMAN_ALL":
        asyncio.create_task(_run_human_all(job_id, data))
        return

    asyncio.create_task(_run_pipeline(job_id, data))


async def _run_human_all(job_id: str, eval_data: dict) -> None:
    """针对 HUMAN_ALL 路由自动创建人工任务。"""
    if not _db_session_factory or not _task_manager:
        logger.error("pipeline_not_initialized")
        return

    try:
        async with _db_session_factory() as db:
            async with db.begin():
                result = await db.execute(
                    select(PDFJob).where(PDFJob.job_id == UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if not job:
                    logger.error("human_all_job_not_found", job_id=job_id)
                    return

                blank_pages = set(job.blank_pages or [])
                pages = [p for p in range(1, job.total_pages + 1)
                         if p not in blank_pages]

                if not pages:
                    logger.info("human_all_no_pages", job_id=job_id)
                    return

                for page_no in pages:
                    await _task_manager.create_task(
                        db,
                        job_id=job_id,
                        page_number=page_no,
                        task_type=HumanTaskType.PAGE_PROCESS.value,
                        context={
                            "route": "HUMAN_ALL",
                            "degrade_reason": eval_data.get("degrade_reason") or job.degrade_reason,
                        },
                        priority="HIGH",
                    )

                await refresh_job_page_stats(db, job_id)
                await update_job_status(
                    db, job_id, JobInternalStatus.DEGRADED_HUMAN.value,
                    trigger="pipeline_human_all",
                )

                logger.info(
                    "human_all_tasks_created",
                    job_id=job_id,
                    task_count=len(pages),
                )

    except Exception:
        logger.exception("pipeline_human_all_error", job_id=job_id)


async def _run_pipeline(job_id: str, eval_data: dict) -> None:
    """后台 Pipeline 任务。"""
    if not _orchestrator or not _db_session_factory:
        logger.error("pipeline_not_initialized")
        return

    try:
        async with _db_session_factory() as db:
            result = await db.execute(
                select(PDFJob).where(PDFJob.job_id == UUID(job_id))
            )
            job = result.scalar_one_or_none()
            if not job:
                logger.error("pipeline_job_not_found", job_id=job_id)
                return

            await _orchestrator.process_job(db, job, eval_data)
            logger.info("pipeline_task_complete",
                        job_id=job_id, route=eval_data.get("route"))

    except Exception:
        logger.exception("pipeline_task_error", job_id=job_id)
