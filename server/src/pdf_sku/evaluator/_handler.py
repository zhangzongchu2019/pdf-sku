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
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

# 全局引用 (由 main.py lifespan 注入)
_evaluator_service = None
_db_session_factory = None
_eval_queue: asyncio.Queue[tuple[str, dict]] | None = None
_eval_worker_tasks: list[asyncio.Task] = []


def init_handler(evaluator_service, session_factory) -> None:
    """初始化并注册事件监听。"""
    global _evaluator_service, _db_session_factory, _eval_queue, _eval_worker_tasks
    _evaluator_service = evaluator_service
    _db_session_factory = session_factory
    event_bus.subscribe("JobCreated", _on_job_created)
    if _eval_queue is None:
      _eval_queue = asyncio.Queue(maxsize=settings.evaluation_queue_size)
    if not _eval_worker_tasks:
        try:
            loop = asyncio.get_running_loop()
            for idx in range(max(1, settings.evaluation_job_concurrency)):
                _eval_worker_tasks.append(
                    loop.create_task(_evaluation_worker(idx + 1))
                )
        except RuntimeError:
            logger.warning("evaluator_workers_not_started_no_loop")
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

    if not _eval_queue:
        asyncio.create_task(_run_evaluation(job_id, data.get("prescan", {})))
        return

    _enqueue_evaluation(job_id, data.get("prescan", {}))


def _enqueue_evaluation(job_id: str, prescan_data: dict) -> None:
    """优先无阻塞入队；队列满时转后台等待，避免阻塞事件发布链路。"""
    if not _eval_queue:
        asyncio.create_task(_run_evaluation(job_id, prescan_data))
        return

    try:
        _eval_queue.put_nowait((job_id, prescan_data))
        logger.info(
            "evaluation_enqueued",
            job_id=job_id,
            queue_size=_eval_queue.qsize(),
        )
    except asyncio.QueueFull:
        logger.warning("evaluation_queue_full_waiting", job_id=job_id)
        asyncio.create_task(_wait_enqueue_evaluation(job_id, prescan_data))


async def _wait_enqueue_evaluation(job_id: str, prescan_data: dict) -> None:
    if not _eval_queue:
        return
    await _eval_queue.put((job_id, prescan_data))
    logger.info(
        "evaluation_enqueued_delayed",
        job_id=job_id,
        queue_size=_eval_queue.qsize(),
    )


async def _evaluation_worker(worker_no: int) -> None:
    """有界 worker 池，避免同时起过多评估任务。"""
    if not _eval_queue:
        return

    logger.info("evaluation_worker_started", worker_no=worker_no)
    while True:
        job_id, prescan_data = await _eval_queue.get()
        try:
            await _run_evaluation(job_id, prescan_data)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("evaluation_worker_error", worker_no=worker_no, job_id=job_id)
        finally:
            _eval_queue.task_done()


async def _run_evaluation(job_id: str, prescan_data: dict) -> None:
    """后台评估任务。"""
    if not _evaluator_service or not _db_session_factory:
        logger.error("evaluator_not_initialized")
        return

    try:
        async with _db_session_factory() as db:
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

            # 尽早提交，避免在后续截图渲染 / LLM 评估期间持续占用连接。
            await db.commit()

            # 执行评估
            eval_result = await _evaluator_service.evaluate(
                db=db, job=job, prescan_data=prescan_data)
            await db.commit()

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
