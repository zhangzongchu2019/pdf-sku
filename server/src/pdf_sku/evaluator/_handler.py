"""
评估事件处理器。

监听 JobCreated 事件 → 启动异步评估任务。
评估完成后发布 EvaluationCompleted 事件。

环境变量 ENABLE_EVALUATION=0 (默认) 跳过评估，直接走 AI 处理。
"""
from __future__ import annotations
import asyncio
import os
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


def _eval_enabled() -> bool:
    """读取环境变量判断是否启用评估，默认关闭。"""
    return os.environ.get("ENABLE_EVALUATION", "0").lower() in ("1", "true", "yes")


def init_handler(evaluator_service, session_factory) -> None:
    """初始化并注册事件监听。"""
    global _evaluator_service, _db_session_factory
    _evaluator_service = evaluator_service
    _db_session_factory = session_factory
    event_bus.subscribe("JobCreated", _on_job_created)
    logger.info("evaluator_handler_registered", eval_enabled=_eval_enabled())


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

    # 评估关闭时跳过 LLM 评估，直接发布 EvaluationCompleted 走 AI 处理
    if not _eval_enabled():
        logger.info("eval_skipped_disabled", job_id=job_id)
        asyncio.create_task(_skip_evaluation(job_id, data))
        return

    # 启动异步评估 (不阻塞事件总线)
    asyncio.create_task(_run_evaluation(job_id, data.get("prescan", {})))


async def _skip_evaluation(job_id: str, data: dict) -> None:
    """跳过评估，直接将 Job 路由到 AI 处理。"""
    if not _db_session_factory:
        logger.error("evaluator_not_initialized")
        return
    try:
        async with _db_session_factory() as db:
            async with db.begin():
                result = await db.execute(
                    select(PDFJob).where(PDFJob.job_id == UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if not job:
                    logger.error("eval_skip_job_not_found", job_id=job_id)
                    return

                await update_job_status(
                    db, job_id, JobInternalStatus.EVALUATED.value,
                    trigger="eval_skipped")

        await event_bus.publish("EvaluationCompleted", {
            "job_id": job_id,
            "route": "AUTO",
            "degrade_reason": None,
            "prescan": data.get("prescan", {}),
        })
        logger.info("eval_skipped_auto_route", job_id=job_id)

    except Exception:
        logger.exception("eval_skip_error", job_id=job_id)
        try:
            async with _db_session_factory() as db:
                async with db.begin():
                    await update_job_status(
                        db, job_id, JobInternalStatus.EVAL_FAILED.value,
                        trigger="eval_skip_error",
                        error_message="Failed to skip evaluation")
        except Exception:
            logger.exception("eval_skip_fallback_error", job_id=job_id)


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
