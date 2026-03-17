"""
Pipeline Worker — 从 pdfsku:queue:pipeline 消费任务，执行 PDF 页面处理。

对齐: fix.md §4.4 + §7.4 + §9

消费流程 (fix.md §7.4):
1. XREADGROUP
2. 解析消息
3. 查 Postgres 校验 job 当前状态
4. 若状态不允许 → XACK 跳过
5. 执行 pipeline
6. 分页写结果到 Postgres
7. 成功后 XACK
8. 发轻量事件
9. 失败 → 按策略重试或送 DLQ

角色: RUN_ROLE=worker-pipeline
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
from pdf_sku.common.idempotency import is_stage_done, mark_stage_done
from pdf_sku.common.models import PDFJob
from pdf_sku.common.queue import (
    STAGE_STREAMS, STAGE_GROUPS,
    ack, consume, ensure_stream_group, reclaim_pending, send_to_dlq,
)
from pdf_sku.settings import settings

logger = structlog.get_logger()

# 允许触发 pipeline 的 job 状态集合
_ALLOWED_PIPELINE_STATUSES = {
    JobInternalStatus.EVALUATED.value,
    # 支持重跑场景
    JobInternalStatus.PARTIAL_FAILED.value,
}

PIPELINE_TIMEOUT_SECONDS = 7200  # 2 hours max


class PipelineWorker:
    """
    后台 Pipeline Worker 主循环。

    使用方式:
        worker = PipelineWorker(session_factory, redis, process_pool)
        await worker.run()
    """

    def __init__(
        self,
        session_factory,
        redis,
        process_pool: ProcessPoolExecutor | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._process_pool = process_pool
        self._consumer_name = os.environ.get(
            "WORKER_ID", f"pipeline-{socket.gethostname()}"
        )
        self._running = True
        self._orchestrator = None

    async def _ensure_streams(self) -> None:
        await ensure_stream_group(self._redis, STAGE_STREAMS["pipeline"], STAGE_GROUPS["pipeline"])

    def set_orchestrator(self, orchestrator) -> None:
        self._orchestrator = orchestrator

    async def run(self) -> None:
        """主消费循环。"""
        await self._ensure_streams()
        logger.info("pipeline_worker_started", consumer=self._consumer_name)

        reclaim_counter = 0
        message_concurrency = max(1, min(settings.pipeline_job_concurrency, settings.queue_batch_size))
        while self._running:
            try:
                reclaim_counter += 1
                if reclaim_counter >= 10:
                    reclaim_counter = 0
                    await reclaim_pending(
                        self._redis, "pipeline",
                        self._consumer_name,
                        idle_ms=settings.queue_claim_idle_ms,
                        max_retry=settings.queue_max_retry,
                    )

                messages = await consume(
                    self._redis, "pipeline",
                    self._consumer_name,
                    batch_size=settings.queue_batch_size,
                    block_ms=5000,
                )
                if not messages:
                    continue

                semaphore = asyncio.Semaphore(message_concurrency)

                async def handle_one(msg_id: str, fields: dict) -> None:
                    async with semaphore:
                        await self._handle(msg_id, fields)

                await asyncio.gather(
                    *(handle_one(msg_id, fields) for msg_id, fields in messages)
                )

            except asyncio.CancelledError:
                logger.info("pipeline_worker_cancelled")
                break
            except Exception:
                logger.exception("pipeline_worker_loop_error")
                await asyncio.sleep(2)

        logger.info("pipeline_worker_stopped")

    async def _handle(self, msg_id: str, fields: dict) -> None:
        """处理单条 pipeline 消息。"""
        job_id = fields.get("job_id", "")
        trace_id = fields.get("trace_id", "")
        attempt = int(fields.get("attempt", "1"))

        if not job_id:
            await ack(self._redis, "pipeline", msg_id)
            return

        try:
            payload = json.loads(fields.get("payload_json", "{}"))
            route = payload.get("route", "AI_ALL")
            eval_data = payload.get("eval") or {"route": route}
            eval_data.setdefault("route", route)

            async with self._session_factory() as db:
                result = await db.execute(
                    select(PDFJob).where(PDFJob.job_id == UUID(job_id))
                )
                job = result.scalar_one_or_none()

            # 幂等检查
            if await is_stage_done(self._redis, job_id, "pipeline"):
                logger.info("pipeline_stage_already_done", job_id=job_id)
                await ack(self._redis, "pipeline", msg_id)
                return

            # 状态校验
            if not job or job.status not in _ALLOWED_PIPELINE_STATUSES:
                logger.info("pipeline_status_skip",
                            job_id=job_id,
                            status=job.status if job else "NOT_FOUND")
                await ack(self._redis, "pipeline", msg_id)
                return

            # 执行 pipeline（包含超时保护）
            await _claim_job_for_pipeline(self._session_factory, job_id, settings.worker_id)
            await asyncio.wait_for(
                self._run_pipeline(job, eval_data, trace_id),
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )

            # 成功写 Redis 幂等 key
            await mark_stage_done(self._redis, job_id, "pipeline")
            await ack(self._redis, "pipeline", msg_id)

            logger.info("pipeline_done", job_id=job_id)

        except asyncio.TimeoutError:
            logger.error("pipeline_timeout", job_id=job_id, attempt=attempt)
            await self._handle_failure(msg_id, fields, "PIPELINE_TIMEOUT", "Pipeline timed out")

        except asyncio.CancelledError:
            raise

        except Exception as e:
            logger.exception("pipeline_error", job_id=job_id, attempt=attempt, error=str(e))
            await self._handle_failure(msg_id, fields, type(e).__name__, str(e))

    async def _run_pipeline(self, job: PDFJob, evaluation: dict, trace_id: str) -> None:
        """调用实际 orchestrator 执行 pipeline。"""
        if not self._orchestrator:
            raise RuntimeError("Orchestrator not initialized in PipelineWorker")

        route = evaluation.get("route", "AI_ALL")
        # HUMAN_ALL 路由不走 pipeline，创建人工任务
        if route == "HUMAN_ALL":
            await self._handle_human_all(job, trace_id)
            return

        async with self._session_factory() as db:
            result = await db.execute(
                select(PDFJob).where(PDFJob.job_id == job.job_id)
            )
            fresh_job = result.scalar_one_or_none()
            if not fresh_job:
                raise RuntimeError(f"Job {job.job_id} not found during pipeline")
            await self._orchestrator.process_job(
                db,
                fresh_job,
                evaluation,
                trace_id=trace_id,
                worker_id=settings.worker_id,
            )

    async def _handle_human_all(self, job: PDFJob, trace_id: str) -> None:
        """处理 HUMAN_ALL 路由 — 发布人工任务事件。"""
        from pdf_sku.collaboration.annotation_service import TaskManager
        from pdf_sku.common.enums import HumanTaskType
        from pdf_sku.gateway.user_status import refresh_job_page_stats, update_job_status

        async with self._session_factory() as db:
            result = await db.execute(
                select(PDFJob).where(PDFJob.job_id == job.job_id)
            )
            fresh_job = result.scalar_one_or_none()
            if not fresh_job:
                raise RuntimeError(f"Job {job.job_id} not found during human routing")

            blank_pages = set(fresh_job.blank_pages or [])
            pages = [p for p in range(1, fresh_job.total_pages + 1) if p not in blank_pages]
            task_manager = TaskManager()

            for page_no in pages:
                await task_manager.create_task(
                    db,
                    job_id=str(fresh_job.job_id),
                    page_number=page_no,
                    task_type=HumanTaskType.PAGE_PROCESS.value,
                    context={
                        "route": "HUMAN_ALL",
                        "degrade_reason": fresh_job.degrade_reason,
                    },
                    priority="HIGH",
                )

            await refresh_job_page_stats(db, str(fresh_job.job_id))
            fresh_job.worker_id = settings.worker_id
            await update_job_status(
                db,
                str(fresh_job.job_id),
                JobInternalStatus.DEGRADED_HUMAN.value,
                trigger="pipeline_human_all",
            )
            await db.commit()

        await publish_job_event(
            self._redis, JobEvent.HUMAN_NEEDED,
            job_id=str(job.job_id),
            status=JobInternalStatus.DEGRADED_HUMAN.value,
            trace_id=trace_id,
        )

    async def _handle_failure(
        self,
        msg_id: str,
        fields: dict,
        error_type: str,
        error_message: str,
    ) -> None:
        """失败处理。"""
        attempt = int(fields.get("attempt", "1"))
        job_id = fields.get("job_id", "")
        trace_id = fields.get("trace_id", "")

        if attempt >= settings.queue_max_retry:
            await send_to_dlq(
                self._redis, "pipeline", fields,
                error_type=error_type,
                error_message=error_message,
                trace_id=trace_id,
            )
            await ack(self._redis, "pipeline", msg_id)
            await _mark_job_failed_pipeline(
                self._session_factory, job_id,
                error_message,
            )
            await publish_job_event(
                self._redis, JobEvent.JOB_FAILED,
                job_id=job_id,
                status=JobInternalStatus.PARTIAL_FAILED.value,
                error=error_message,
                trace_id=trace_id,
            )
        # else: 不 ack，让 pending reclaim 超时后重领


async def _mark_job_failed_pipeline(session_factory, job_id: str, reason: str) -> None:
    """将 job 更新为 PARTIAL_FAILED 状态。"""
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
                    JobInternalStatus.PARTIAL_FAILED.value,
                    trigger="worker_failure",
                    error_message=reason,
                )
                await db.commit()
    except Exception as e:
        logger.warning("mark_pipeline_job_failed_error", job_id=job_id, error=str(e))


async def _claim_job_for_pipeline(session_factory, job_id: str, worker_id: str) -> None:
    """记录 pipeline 阶段的 worker 归属。"""
    async with session_factory() as db:
        result = await db.execute(
            select(PDFJob).where(PDFJob.job_id == UUID(job_id))
        )
        job = result.scalar_one_or_none()
        if job:
            job.worker_id = worker_id
            await db.commit()
