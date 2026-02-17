"""
TaskManager — 人工任务管理。对齐: Collaboration 详设 §5.4

职责:
- 创建任务 (Pipeline/Evaluator → HumanTask)
- 完成/跳过/回退任务
- 状态机转换 + 审计
- [P1-C8] 重入上限 MAX_REWORK=5
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import (
    HumanTask, Annotation, StateTransition, Page,
)
from pdf_sku.common.enums import PageStatus
from pdf_sku.gateway.event_bus import event_bus
import structlog

logger = structlog.get_logger()

REVERTABLE_STATUSES = {"COMPLETED", "SKIPPED"}
MAX_REWORK_COUNT = 5

# 合法状态转换
VALID_TRANSITIONS = {
    ("CREATED", "PROCESSING"),
    ("CREATED", "ESCALATED"),
    ("PROCESSING", "COMPLETED"),
    ("PROCESSING", "SKIPPED"),
    ("PROCESSING", "CREATED"),     # lock timeout
    ("ESCALATED", "PROCESSING"),
    ("ESCALATED", "COMPLETED"),    # auto SLA
    ("COMPLETED", "CREATED"),      # revert
    ("SKIPPED", "CREATED"),        # revert
}


class TaskManager:
    """人工任务生命周期管理。"""

    async def create_task(
        self,
        db: AsyncSession,
        job_id: str,
        page_number: int,
        task_type: str,
        context: dict | None = None,
        priority: str = "NORMAL",
    ) -> HumanTask:
        """创建人工标注任务。"""
        task = HumanTask(
            task_id=uuid4(),
            job_id=UUID(job_id),
            page_number=page_number,
            task_type=task_type,
            status="CREATED",
            priority=priority,
            context=context or {},
        )
        db.add(task)

        # 更新 Page 状态
        await db.execute(
            update(Page).where(
                Page.job_id == UUID(job_id),
                Page.page_number == page_number,
            ).values(status=PageStatus.HUMAN_QUEUED.value)
        )

        # 审计
        db.add(StateTransition(
            entity_type="task",
            entity_id=str(task.task_id),
            from_status=None,
            to_status="CREATED",
            trigger="create",
            operator="system",
        ))

        logger.info("task_created",
                     task_id=str(task.task_id), job_id=job_id,
                     page=page_number, type=task_type)

        await event_bus.publish("TaskCreated", {
            "task_id": str(task.task_id),
            "job_id": job_id,
            "task_type": task_type,
        })
        return task

    async def complete_task(
        self,
        db: AsyncSession,
        task_id: str,
        result: dict,
        operator: str,
    ) -> HumanTask:
        """完成任务 + 保存标注结果。"""
        task = await self._get_task(db, task_id)
        self._check_transition(task.status, "COMPLETED")

        now = datetime.now(timezone.utc)
        await db.execute(
            update(HumanTask).where(HumanTask.task_id == UUID(task_id))
            .values(
                status="COMPLETED",
                result=result,
                completed_at=now,
                locked_by=None,
                locked_at=None,
            )
        )

        # 保存标注
        annotation = Annotation(
            task_id=UUID(task_id),
            job_id=task.job_id,
            page_number=task.page_number,
            annotator=operator,
            type=task.task_type,
            payload=result,
        )
        db.add(annotation)

        # 审计
        db.add(StateTransition(
            entity_type="task", entity_id=task_id,
            from_status=task.status, to_status="COMPLETED",
            trigger="complete", operator=operator,
        ))

        # 更新 Page 状态
        await db.execute(
            update(Page).where(
                Page.job_id == task.job_id,
                Page.page_number == task.page_number,
            ).values(status=PageStatus.AI_COMPLETED.value)
        )

        logger.info("task_completed", task_id=task_id, operator=operator)

        await event_bus.publish("TaskCompleted", {
            "task_id": task_id,
            "job_id": str(task.job_id),
            "page_number": task.page_number,
            "operator": operator,
        })

        await db.refresh(task)
        return task

    async def skip_task(
        self,
        db: AsyncSession,
        task_id: str,
        reason: str,
        operator: str,
    ) -> HumanTask:
        """跳过任务。"""
        task = await self._get_task(db, task_id)
        self._check_transition(task.status, "SKIPPED")

        await db.execute(
            update(HumanTask).where(HumanTask.task_id == UUID(task_id))
            .values(
                status="SKIPPED",
                result={"skip_reason": reason},
                locked_by=None,
                locked_at=None,
            )
        )

        db.add(StateTransition(
            entity_type="task", entity_id=task_id,
            from_status=task.status, to_status="SKIPPED",
            trigger="skip", operator=operator,
        ))

        logger.info("task_skipped", task_id=task_id, reason=reason)
        await db.refresh(task)
        return task

    async def revert_task(
        self,
        db: AsyncSession,
        task_id: str,
        operator: str,
        reason: str = "",
    ) -> HumanTask:
        """
        回退任务 → CREATED。
        [P1-C8] 重入上限检查。
        """
        task = await self._get_task(db, task_id)

        if task.status not in REVERTABLE_STATUSES:
            raise ValueError(
                f"Cannot revert task in status '{task.status}', "
                f"allowed: {REVERTABLE_STATUSES}")

        if (task.rework_count or 0) >= MAX_REWORK_COUNT:
            raise ValueError(
                f"Max rework count ({MAX_REWORK_COUNT}) exceeded")

        await db.execute(
            update(HumanTask).where(HumanTask.task_id == UUID(task_id))
            .values(
                status="CREATED",
                locked_by=None,
                locked_at=None,
                result=None,
                rework_count=HumanTask.rework_count + 1,
            )
        )

        db.add(StateTransition(
            entity_type="task", entity_id=task_id,
            from_status=task.status, to_status="CREATED",
            trigger="revert", operator=operator,
        ))

        logger.info("task_reverted", task_id=task_id,
                     operator=operator, reason=reason)
        await db.refresh(task)
        return task

    async def assign_task(
        self,
        db: AsyncSession,
        task_id: str,
        operator: str,
    ) -> HumanTask:
        """手动指派任务。"""
        task = await self._get_task(db, task_id)

        now = datetime.now(timezone.utc)
        await db.execute(
            update(HumanTask).where(HumanTask.task_id == UUID(task_id))
            .values(
                status="PROCESSING",
                assigned_to=operator,
                assigned_at=now,
                locked_by=operator,
                locked_at=now,
            )
        )

        db.add(StateTransition(
            entity_type="task", entity_id=task_id,
            from_status=task.status, to_status="PROCESSING",
            trigger="assign", operator=operator,
        ))

        await db.refresh(task)
        return task

    # ── Batch Ops ──

    async def batch_skip(
        self, db: AsyncSession, task_ids: list[str], reason: str, operator: str,
    ) -> dict:
        """批量跳过。"""
        succeeded = failed = 0
        for tid in task_ids:
            try:
                await self.skip_task(db, tid, reason, operator)
                succeeded += 1
            except Exception as e:
                logger.warning("batch_skip_failed", task_id=tid, error=str(e))
                failed += 1
        return {"total": len(task_ids), "succeeded": succeeded, "failed": failed}

    async def batch_reassign(
        self, db: AsyncSession, task_ids: list[str], target: str, operator: str,
    ) -> dict:
        """批量重分配。"""
        succeeded = failed = 0
        for tid in task_ids:
            try:
                await self.assign_task(db, tid, target)
                succeeded += 1
            except Exception as e:
                logger.warning("batch_reassign_failed", task_id=tid, error=str(e))
                failed += 1
        return {"total": len(task_ids), "succeeded": succeeded, "failed": failed}

    # ── Internal ──

    async def _get_task(self, db: AsyncSession, task_id: str) -> HumanTask:
        result = await db.execute(
            select(HumanTask).where(HumanTask.task_id == UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        return task

    @staticmethod
    def _check_transition(from_status: str, to_status: str) -> None:
        if (from_status, to_status) not in VALID_TRANSITIONS:
            raise ValueError(
                f"Invalid transition: {from_status} → {to_status}")
