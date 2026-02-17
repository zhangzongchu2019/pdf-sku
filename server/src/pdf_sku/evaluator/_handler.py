"""
评估事件处理器。

监听 JobCreated 事件 → 启动异步评估任务。
评估完成后发布 EvaluationCompleted 事件。
"""
from __future__ import annotations
import asyncio
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob
from pdf_sku.common.enums import JobInternalStatus
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.gateway.user_status import update_job_status
import structlog

logger = structlog.get_logger()

# 全局引用 (由 main.py lifespan 注入)
_evaluator_service = None
_db_session_factory = None


def init_handler(evaluator_service, session_factory) -> None:
    """初始化并注册事件监听。"""
    global _evaluator_service, _db_session_factory
    _evaluator_service = evaluator_service
    _db_session_factory = session_factory
    event_bus.subscribe("JobCreated", _on_job_created)
    logger.info("evaluator_handler_registered")


async def _on_job_created(data: dict) -> None:
    """
    处理 JobCreated 事件。

    如果 Job 状态为 UPLOADED (非 DEGRADED_HUMAN)，
    启动后台评估任务。
    """
    job_id = data.get("job_id", "")
    status = data.get("status", "")

    if status == JobInternalStatus.DEGRADED_HUMAN.value:
        logger.info("eval_skipped_degraded", job_id=job_id)
        return

    # 启动异步评估 (不阻塞事件总线)
    asyncio.create_task(_run_evaluation(job_id, data.get("prescan", {})))


async def _run_evaluation(job_id: str, prescan_data: dict) -> None:
    """后台评估任务。"""
    if not _evaluator_service or not _db_session_factory:
        logger.error("evaluator_not_initialized")
        return

    try:
        async with _db_session_factory() as db:
            async with db.begin():
                # 更新状态: UPLOADED → EVALUATING
                await update_job_status(
                    db, job_id, JobInternalStatus.EVALUATING.value,
                    trigger="eval_start")

                # 获取 Job
                result = await db.execute(
                    select(PDFJob).where(PDFJob.job_id == UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if not job:
                    logger.error("eval_job_not_found", job_id=job_id)
                    return

                # 执行评估
                eval_result = await _evaluator_service.evaluate(
                    db=db, job=job, prescan_data=prescan_data)

                logger.info("eval_task_complete",
                            job_id=job_id,
                            route=eval_result.get("route"),
                            c_doc=eval_result.get("doc_confidence"))

    except Exception:
        logger.exception("eval_task_error", job_id=job_id)
        # 降级处理: EVAL_FAILED
        try:
            async with _db_session_factory() as db:
                async with db.begin():
                    await update_job_status(
                        db, job_id, JobInternalStatus.EVAL_FAILED.value,
                        trigger="eval_error",
                        error_message="Evaluation failed due to unexpected error")
        except Exception:
            logger.exception("eval_fallback_status_error", job_id=job_id)
