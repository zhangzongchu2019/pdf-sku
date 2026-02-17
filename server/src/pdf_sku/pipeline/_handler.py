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
from pdf_sku.common.enums import JobInternalStatus
from pdf_sku.gateway.event_bus import event_bus
import structlog

logger = structlog.get_logger()

_orchestrator = None
_db_session_factory = None


def init_handler(orchestrator, session_factory) -> None:
    """初始化并注册事件监听。"""
    global _orchestrator, _db_session_factory
    _orchestrator = orchestrator
    _db_session_factory = session_factory
    event_bus.subscribe("EvaluationCompleted", _on_evaluation_completed)
    logger.info("pipeline_handler_registered")


async def _on_evaluation_completed(data: dict) -> None:
    """处理 EvaluationCompleted → 启动 Pipeline。"""
    job_id = data.get("job_id", "")
    route = data.get("route", "HUMAN_ALL")

    # HUMAN_ALL → 不走 Pipeline, 直接进人工
    if route == "HUMAN_ALL":
        logger.info("pipeline_skip_human_all", job_id=job_id)
        return

    asyncio.create_task(_run_pipeline(job_id, data))


async def _run_pipeline(job_id: str, eval_data: dict) -> None:
    """后台 Pipeline 任务。"""
    if not _orchestrator or not _db_session_factory:
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
                    logger.error("pipeline_job_not_found", job_id=job_id)
                    return

                await _orchestrator.process_job(db, job, eval_data)
                logger.info("pipeline_task_complete",
                            job_id=job_id, route=eval_data.get("route"))

    except Exception:
        logger.exception("pipeline_task_error", job_id=job_id)
