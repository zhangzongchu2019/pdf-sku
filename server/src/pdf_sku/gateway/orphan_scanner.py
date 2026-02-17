"""
孤儿 Job 检测与自动重提。对齐: Gateway 详设 §4.2

运行方式: APScheduler interval=60s
流程:
1. SCAN Redis worker:heartbeat:* → 存活集合
2. 查 DB: status IN (EVALUATING, PROCESSING) AND worker_id NOT IN alive_set → 孤儿
3. 标记 ORPHANED + state_transition
4. 冷却 5min 后自动 requeue (最多 3 次)
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob, StateTransition
from pdf_sku.common.enums import JobInternalStatus
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

MAX_REQUEUE_COUNT = 3
REQUEUE_COOLDOWN_SECONDS = 300  # 5 min
HEARTBEAT_TTL = 90  # 秒 — 超过此值视为失联


class OrphanScanner:
    def __init__(self, db_session_factory, redis) -> None:
        self._session_factory = db_session_factory
        self._redis = redis

    async def scan(self) -> int:
        """扫描并处理孤儿 Job。返回检测到的孤儿数。"""
        # 1. 获取存活 Worker 集合
        alive_workers = await self._get_alive_workers()
        if not alive_workers:
            logger.debug("orphan_scan_no_workers")
            return 0

        # 2. 查询可能的孤儿 Job
        async with self._session_factory() as db:
            async with db.begin():
                orphans = await self._find_orphans(db, alive_workers)
                if not orphans:
                    return 0

                count = 0
                for job in orphans:
                    await self._mark_orphaned(db, job)
                    count += 1

                    # 3. 检查重提次数 → 调度延迟重提
                    requeue_count = await self._redis.incr(f"orphan:requeue_count:{job.job_id}")
                    if requeue_count <= MAX_REQUEUE_COUNT:
                        asyncio.get_event_loop().call_later(
                            REQUEUE_COOLDOWN_SECONDS,
                            lambda jid=str(job.job_id): asyncio.create_task(
                                self._auto_requeue(jid, alive_workers)
                            ),
                        )
                        logger.info("orphan_requeue_scheduled",
                                    job_id=str(job.job_id),
                                    attempt=requeue_count,
                                    delay_sec=REQUEUE_COOLDOWN_SECONDS)
                    else:
                        logger.error("orphan_max_retries",
                                     job_id=str(job.job_id), retries=requeue_count)

                logger.info("orphan_scan_complete", found=count)
                return count

    async def _get_alive_workers(self) -> set[str]:
        """SCAN Redis heartbeat keys → 存活 worker 集合。"""
        alive = set()
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match="worker:heartbeat:*", count=100
            )
            for key in keys:
                # key = "worker:heartbeat:{worker_id}"
                worker_id = key.split(":", 2)[-1] if isinstance(key, str) else key.decode().split(":", 2)[-1]
                alive.add(worker_id)
            if cursor == 0:
                break
        return alive

    async def _find_orphans(self, db: AsyncSession, alive_workers: set[str]) -> list[PDFJob]:
        """查询 worker 已失联的活跃 Job。"""
        active_statuses = [
            JobInternalStatus.EVALUATING.value,
            JobInternalStatus.PROCESSING.value,
        ]
        result = await db.execute(
            select(PDFJob).where(
                PDFJob.status.in_(active_statuses),
                PDFJob.worker_id.isnot(None),
                PDFJob.worker_id.notin_(alive_workers) if alive_workers else True,
            )
        )
        return list(result.scalars().all())

    async def _mark_orphaned(self, db: AsyncSession, job: PDFJob) -> None:
        """标记 Job 为 ORPHANED。"""
        old_status = job.status
        job.status = JobInternalStatus.ORPHANED.value
        db.add(StateTransition(
            entity_type="job",
            entity_id=str(job.job_id),
            from_status=old_status,
            to_status=JobInternalStatus.ORPHANED.value,
            trigger="heartbeat_scan",
        ))
        await event_bus.publish("JobOrphaned", {
            "job_id": str(job.job_id),
            "old_status": old_status,
            "worker_id": job.worker_id,
        })

    async def _auto_requeue(self, job_id: str, previous_alive: set[str]) -> None:
        """冷却后自动重提: 分配给新的存活 Worker。"""
        try:
            current_alive = await self._get_alive_workers()
            if not current_alive:
                logger.error("requeue_no_workers", job_id=job_id)
                return

            async with self._session_factory() as db:
                async with db.begin():
                    result = await db.execute(
                        select(PDFJob).where(PDFJob.job_id == job_id)
                    )
                    job = result.scalar_one_or_none()
                    if not job or job.status != JobInternalStatus.ORPHANED.value:
                        return

                    # 选择负载最低的 Worker (简化: 随机选)
                    new_worker = next(iter(current_alive))
                    old_status = job.status
                    job.status = JobInternalStatus.PROCESSING.value
                    job.worker_id = new_worker
                    db.add(StateTransition(
                        entity_type="job",
                        entity_id=str(job.job_id),
                        from_status=old_status,
                        to_status=JobInternalStatus.PROCESSING.value,
                        trigger="auto_requeue",
                    ))

                    # 更新 Redis 路由
                    await self._redis.set(
                        f"job_worker:{job.job_id}", new_worker, ex=86400 * 7
                    )

                    await event_bus.publish("JobRequeued", {
                        "job_id": str(job.job_id),
                        "new_worker": new_worker,
                        "checkpoint_page": job.checkpoint_page,
                    })

                    logger.info("orphan_requeued",
                                job_id=job_id, new_worker=new_worker)

        except Exception:
            logger.exception("auto_requeue_failed", job_id=job_id)
