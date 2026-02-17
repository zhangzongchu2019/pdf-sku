"""
锁管理 (SKIP LOCKED)。对齐: Collaboration 详设 §5.1

- DB 为唯一权威来源: locked_by + locked_at
- SKIP LOCKED 确保多实例并发安全
- 心跳 30s, 超时 5min 释放
- [P1-C8] 重入上限 MAX_REWORK_COUNT=5
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text, update, select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import HumanTask, StateTransition
import structlog

logger = structlog.get_logger()

HEARTBEAT_INTERVAL = 30
LOCK_TIMEOUT = 300  # 5 min
MAX_REWORK_COUNT = 5


class LockManager:
    """SKIP LOCKED 锁管理器。"""

    async def acquire_next(
        self, db: AsyncSession, annotator_id: str,
    ) -> HumanTask | None:
        """
        原子领取优先级最高的待处理任务。
        使用 FOR UPDATE SKIP LOCKED 确保并发安全。
        """
        result = await db.execute(text("""
            UPDATE human_tasks
            SET locked_by = :ann,
                locked_at = now(),
                status = 'PROCESSING',
                assigned_to = :ann,
                assigned_at = now()
            WHERE task_id = (
                SELECT task_id FROM human_tasks
                WHERE status IN ('CREATED', 'ESCALATED')
                ORDER BY
                    CASE priority
                        WHEN 'AUTO_RESOLVE' THEN 0
                        WHEN 'URGENT' THEN 1
                        WHEN 'HIGH' THEN 2
                        WHEN 'NORMAL' THEN 3
                    END,
                    created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING task_id
        """), {"ann": annotator_id})
        row = result.fetchone()
        if not row:
            return None

        task_id = row[0]
        await self._record_transition(
            db, str(task_id), "CREATED", "PROCESSING", "lock", annotator_id)

        task_result = await db.execute(
            select(HumanTask).where(HumanTask.task_id == task_id))
        return task_result.scalar_one_or_none()

    async def heartbeat(
        self, db: AsyncSession, task_id: str, annotator_id: str,
    ) -> bool:
        """心跳续期。返回 True 表示续期成功。"""
        result = await db.execute(text("""
            UPDATE human_tasks SET locked_at = now()
            WHERE task_id = :tid AND locked_by = :ann AND status = 'PROCESSING'
        """), {"tid": task_id, "ann": annotator_id})
        if result.rowcount == 0:
            logger.warning("heartbeat_failed", task_id=task_id, annotator=annotator_id)
            return False
        return True

    async def scan_expired_locks(self, db: AsyncSession) -> int:
        """
        定时扫描: 超时锁 → 释放回队列。
        [P1-C8] 重入上限检查。
        """
        result = await db.execute(text("""
            SELECT task_id, locked_by, rework_count FROM human_tasks
            WHERE status = 'PROCESSING'
              AND locked_at < now() - interval ':timeout seconds'
        """.replace(":timeout", str(LOCK_TIMEOUT))))
        expired = result.fetchall()
        released = 0

        for row in expired:
            task_id, locked_by, rework_count = row
            if (rework_count or 0) >= MAX_REWORK_COUNT:
                # 超过重入上限 → SKIPPED
                await db.execute(text("""
                    UPDATE human_tasks
                    SET status = 'SKIPPED', locked_by = NULL, locked_at = NULL
                    WHERE task_id = :tid AND status = 'PROCESSING'
                """), {"tid": str(task_id)})
                await self._record_transition(
                    db, str(task_id), "PROCESSING", "SKIPPED",
                    "max_rework_exceeded", "system")
                logger.warning("task_max_rework", task_id=str(task_id))
            else:
                await db.execute(text("""
                    UPDATE human_tasks
                    SET status = 'CREATED', locked_by = NULL, locked_at = NULL
                    WHERE task_id = :tid AND status = 'PROCESSING'
                """), {"tid": str(task_id)})
                await self._record_transition(
                    db, str(task_id), "PROCESSING", "CREATED",
                    "lock_timeout", "system")
            released += 1

        if released:
            logger.info("expired_locks_released", count=released)
        return released

    @staticmethod
    async def _record_transition(
        db: AsyncSession, entity_id: str,
        from_status: str, to_status: str,
        trigger: str, operator: str,
    ) -> None:
        db.add(StateTransition(
            entity_type="task",
            entity_id=entity_id,
            from_status=from_status,
            to_status=to_status,
            trigger=trigger,
            operator=operator,
        ))
