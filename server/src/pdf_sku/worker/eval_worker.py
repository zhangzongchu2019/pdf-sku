"""
Eval Worker — 从 pdfsku:queue:evaluate 消费任务，执行文档评估。

对齐: fix.md §4.3 + §7.4 + §9

消费流程 (fix.md §7.4):
1. XREADGROUP
2. 解析消息
3. 查 Postgres 校验 job 当前状态
4. 若状态不允许 → XACK 跳过
5. 执行评估
6. 成功写 Postgres
7. 成功后 XACK
8. 推进到 pipeline 队列
9. 失败 → 按策略重试或送 DLQ

角色: RUN_ROLE=worker-eval
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
from concurrent.futures import ProcessPoolExecutor
from uuid import UUID

import structlog
from sqlalchemy import select

from pdf_sku.common.enums import JobInternalStatus
from pdf_sku.common.events import JobEvent, publish_job_event
from pdf_sku.common.idempotency import is_stage_done, mark_stage_done, try_enqueue_lock
from pdf_sku.common.models import PDFJob
from pdf_sku.common.queue import (
    STAGE_STREAMS, STAGE_GROUPS,
    ack, consume, ensure_stream_group, produce, reclaim_pending, send_to_dlq,
)
from pdf_sku.settings import settings

logger = structlog.get_logger()

# 允许触发 evaluate 的 job 状态集合
_ALLOWED_EVAL_STATUSES = {
    JobInternalStatus.UPLOADED.value,
}

# Eval worker 只能写入这些状态
_EVAL_WRITABLE_STATUSES = {
    JobInternalStatus.EVALUATING,
    JobInternalStatus.EVALUATED,
    JobInternalStatus.EVAL_FAILED,
    JobInternalStatus.DEGRADED_HUMAN,
}

EVAL_TIMEOUT_SECONDS = 1200  # 20 min


class EvalWorker:
    """
    后台 Eval Worker 主循环。

    使用方式:
        worker = EvalWorker(session_factory, redis)
        await worker.run()
    """

    def __init__(self, session_factory, redis, process_pool: ProcessPoolExecutor | None = None) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._process_pool = process_pool
        self._consumer_name = os.environ.get(
            "WORKER_ID", f"eval-{socket.gethostname()}"
        )
        self._running = True

        # 延迟初始化（需要连接到 Redis 后才能建组）
        self._evaluator_service = None

    async def _ensure_streams(self) -> None:
        await ensure_stream_group(self._redis, STAGE_STREAMS["evaluate"], STAGE_GROUPS["evaluate"])

    def set_evaluator_service(self, svc) -> None:
        self._evaluator_service = svc

    async def run(self) -> None:
        """主消费循环。"""
        await self._ensure_streams()
        logger.info("eval_worker_started", consumer=self._consumer_name)

        reclaim_counter = 0
        while self._running:
            try:
                # 每 10 轮扫描一次 pending
                reclaim_counter += 1
                if reclaim_counter >= 10:
                    reclaim_counter = 0
                    await reclaim_pending(
                        self._redis, "evaluate",
                        self._consumer_name,
                        idle_ms=settings.queue_claim_idle_ms,
                        max_retry=settings.queue_max_retry,
                    )

                messages = await consume(
                    self._redis, "evaluate",
                    self._consumer_name,
                    batch_size=settings.queue_batch_size,
                    block_ms=5000,
                )
                for msg_id, fields in messages:
                    await self._handle(msg_id, fields)

            except asyncio.CancelledError:
                logger.info("eval_worker_cancelled")
                break
            except Exception:
                logger.exception("eval_worker_loop_error")
                await asyncio.sleep(2)

        logger.info("eval_worker_stopped")

    async def _handle(self, msg_id: str, fields: dict) -> None:
        """处理单条评估消息。"""
        job_id = fields.get("job_id", "")
        trace_id = fields.get("trace_id", "")
        attempt = int(fields.get("attempt", "1"))

        if not job_id:
            await ack(self._redis, "evaluate", msg_id)
            return

        try:
            payload = json.loads(fields.get("payload_json", "{}"))
            prescan_data = payload.get("prescan", {})

            async with self._session_factory() as db:
                result = await db.execute(
                    select(PDFJob).where(PDFJob.job_id == UUID(job_id))
                )
                job = result.scalar_one_or_none()

            # 幂等检查: 阶段已完成则直接 ack
            if await is_stage_done(self._redis, job_id, "evaluate"):
                logger.info("eval_stage_already_done", job_id=job_id)
                await ack(self._redis, "evaluate", msg_id)
                return

            # 状态校验
            if not job or job.status not in _ALLOWED_EVAL_STATUSES:
                logger.info("eval_status_skip",
                            job_id=job_id,
                            status=job.status if job else "NOT_FOUND")
                await ack(self._redis, "evaluate", msg_id)
                return

            await _claim_job_for_eval(self._session_factory, job_id, settings.worker_id)

            # 发布 job_started 事件
            await publish_job_event(
                self._redis, JobEvent.JOB_STARTED,
                job_id=job_id, stage="evaluate",
                status=JobInternalStatus.EVALUATING.value,
                trace_id=trace_id,
            )

            # 执行评估（包含超时保护）
            eval_result = await asyncio.wait_for(
                self._run_evaluation(job, prescan_data),
                timeout=EVAL_TIMEOUT_SECONDS,
            )

            # 成功写 Redis 幂等 key
            await mark_stage_done(self._redis, job_id, "evaluate")

            # XACK
            await ack(self._redis, "evaluate", msg_id)

            # 推进到 pipeline 队列
            route = eval_result.get("route", "AI_ALL")
            if route != "HUMAN_ALL" and await try_enqueue_lock(self._redis, job_id, "pipeline"):
                await produce(
                    self._redis, "pipeline", job_id,
                    attempt=1,
                    trigger="eval_completed",
                    trace_id=trace_id,
                    payload={"route": route, "eval": eval_result},
                )

            await publish_job_event(
                self._redis, JobEvent.JOB_STAGE_CHANGED,
                job_id=job_id, stage="pipeline",
                status=(
                    JobInternalStatus.DEGRADED_HUMAN.value
                    if route == "HUMAN_ALL"
                    else JobInternalStatus.EVALUATED.value
                ),
                trace_id=trace_id,
            )
            if route == "HUMAN_ALL":
                await publish_job_event(
                    self._redis,
                    JobEvent.HUMAN_NEEDED,
                    job_id=job_id,
                    status=JobInternalStatus.DEGRADED_HUMAN.value,
                    trace_id=trace_id,
                    extra={"reason": eval_result.get("degrade_reason")},
                )

            logger.info("eval_done", job_id=job_id, route=route)

        except asyncio.TimeoutError:
            logger.error("eval_timeout", job_id=job_id, attempt=attempt)
            await self._handle_failure(msg_id, fields, "EVAL_TIMEOUT", "Evaluation timed out")

        except asyncio.CancelledError:
            raise

        except Exception as e:
            logger.exception("eval_error", job_id=job_id, attempt=attempt, error=str(e))
            await self._handle_failure(msg_id, fields, type(e).__name__, str(e))

    async def _run_evaluation(self, job: PDFJob, prescan_data: dict) -> dict:
        """调用实际评估服务。"""
        if not self._evaluator_service:
            raise RuntimeError("EvaluatorService not initialized in EvalWorker")
        async with self._session_factory() as db:
            result = await db.execute(
                select(PDFJob).where(PDFJob.job_id == job.job_id)
            )
            fresh_job = result.scalar_one_or_none()
            if not fresh_job:
                raise RuntimeError(f"Job {job.job_id} not found during evaluation")
            eval_result = await self._evaluator_service.evaluate(db, fresh_job, prescan_data)
            await db.commit()
            return eval_result

    async def _handle_failure(
        self,
        msg_id: str,
        fields: dict,
        error_type: str,
        error_message: str,
    ) -> None:
        """失败处理：超限则送 DLQ，否则让 pending reclaim 处理重试。"""
        attempt = int(fields.get("attempt", "1"))
        job_id = fields.get("job_id", "")
        trace_id = fields.get("trace_id", "")

        if attempt >= settings.queue_max_retry:
            await send_to_dlq(
                self._redis, "evaluate", fields,
                error_type=error_type,
                error_message=error_message,
                trace_id=trace_id,
            )
            await ack(self._redis, "evaluate", msg_id)
            # 更新 job 状态为 EVAL_FAILED
            await _mark_job_failed(
                self._session_factory, job_id,
                JobInternalStatus.EVAL_FAILED,
                error_message,
            )
            await publish_job_event(
                self._redis, JobEvent.JOB_FAILED,
                job_id=job_id,
                status=JobInternalStatus.EVAL_FAILED.value,
                error=error_message,
                trace_id=trace_id,
            )
        # else: 不 ack，让 pending reclaim 超时后重领


async def _mark_job_failed(session_factory, job_id: str, status: JobInternalStatus, reason: str) -> None:
    """将 job 更新为失败状态。"""
    if not job_id:
        return
    try:
        from pdf_sku.gateway.user_status import update_job_status
        async with session_factory() as db:
            result = await db.execute(
                select(PDFJob).where(PDFJob.job_id == UUID(job_id))
            )
            job = result.scalar_one_or_none()
            if job:
                job.worker_id = settings.worker_id
                await update_job_status(
                    db,
                    job_id,
                    status.value,
                    trigger="worker_failure",
                    error_message=reason,
                )
                await db.commit()
    except Exception as e:
        logger.warning("mark_job_failed_error", job_id=job_id, error=str(e))


async def _claim_job_for_eval(session_factory, job_id: str, worker_id: str) -> None:
    """记录评估阶段的 worker 归属并推进到 EVALUATING。"""
    from pdf_sku.gateway.user_status import update_job_status

    async with session_factory() as db:
        result = await db.execute(
            select(PDFJob).where(PDFJob.job_id == UUID(job_id))
        )
        job = result.scalar_one_or_none()
        if not job:
            return
        job.worker_id = worker_id
        await update_job_status(
            db,
            job_id,
            JobInternalStatus.EVALUATING.value,
            trigger="queue_claim_evaluate",
        )
        await db.commit()
