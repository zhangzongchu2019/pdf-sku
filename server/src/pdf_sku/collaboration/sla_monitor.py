"""
SLA 四级熔断。对齐: Collaboration 详设 §5.3

L1 NORMAL  (15min): 提升优先级 → HIGH
L2 HIGH    (30min): 升级主管 + 通知
L3 CRITICAL(120min): AI 自动质检
L4 AUTO_RESOLVE(180min): 部分接受
"""
from __future__ import annotations
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import HumanTask
import structlog

logger = structlog.get_logger()

SLA_POLICY = {
    "NORMAL":       {"timeout_min": 15,  "action": "PRIORITY_BOOST",        "next": "HIGH"},
    "HIGH":         {"timeout_min": 30,  "action": "ESCALATE_TO_SUPERVISOR", "next": "CRITICAL"},
    "CRITICAL":     {"timeout_min": 120, "action": "AUTO_QUALITY_CHECK",     "next": "AUTO_RESOLVE"},
    "AUTO_RESOLVE": {"timeout_min": 180, "action": "PARTIAL_ACCEPTANCE",     "next": None},
}

AUTO_REVIEW_SAMPLE_RATE = 0.05
DEFAULT_AUTO_ACCEPT_CONFIDENCE = 0.6


class SLAScanner:
    def __init__(self, notifier=None, task_manager=None, config_provider=None):
        self._notifier = notifier
        self._task_mgr = task_manager
        self._config = config_provider

    async def scan_escalation(self, db: AsyncSession) -> int:
        """扫描全部级别的超时任务。"""
        escalated = 0
        now = datetime.now(timezone.utc)

        for level, policy in SLA_POLICY.items():
            cutoff = now - timedelta(minutes=policy["timeout_min"])
            result = await db.execute(
                select(HumanTask).where(
                    HumanTask.status.in_(["CREATED", "ESCALATED"]),
                    HumanTask.priority == level,
                    HumanTask.created_at < cutoff,
                )
            )
            tasks = result.scalars().all()

            for task in tasks:
                action = policy["action"]
                if action == "PRIORITY_BOOST":
                    await self._boost(db, task, policy["next"])
                elif action == "ESCALATE_TO_SUPERVISOR":
                    await self._escalate(db, task)
                elif action == "AUTO_QUALITY_CHECK":
                    await self._auto_check(db, task)
                elif action == "PARTIAL_ACCEPTANCE":
                    await self._partial_accept(db, task)
                escalated += 1

        if escalated:
            logger.info("sla_scan_complete", escalated=escalated)
        return escalated

    async def _boost(self, db: AsyncSession, task: HumanTask, next_priority: str):
        """L1: 提升优先级。"""
        await db.execute(
            update(HumanTask).where(HumanTask.task_id == task.task_id)
            .values(priority=next_priority)
        )
        logger.info("sla_boost", task_id=str(task.task_id), new_priority=next_priority)

    async def _escalate(self, db: AsyncSession, task: HumanTask):
        """L2: 升级主管 + 通知。"""
        await db.execute(
            update(HumanTask).where(HumanTask.task_id == task.task_id)
            .values(priority="CRITICAL")
        )
        if self._notifier:
            await self._notifier.send(
                channel="supervisor",
                message=f"⚠️ 任务 {task.task_id} 超时 30min, job={task.job_id}",
                level="WARNING",
            )
        logger.warning("sla_escalated", task_id=str(task.task_id))

    async def _auto_check(self, db: AsyncSession, task: HumanTask):
        """L3: AI 自动质检。confidence > 阈值 → 自动接受。"""
        threshold = DEFAULT_AUTO_ACCEPT_CONFIDENCE
        if self._config:
            try:
                profile = self._config.get_frozen_config(
                    (task.context or {}).get("config_version"))
                threshold = (profile or {}).get(
                    "sla_auto_accept_confidence", threshold)
            except Exception:
                pass

        ai_result = (task.context or {}).get("ai_result", {})
        confidence = ai_result.get("confidence", 0)

        if confidence > threshold:
            await db.execute(
                update(HumanTask).where(HumanTask.task_id == task.task_id)
                .values(
                    status="COMPLETED",
                    result=ai_result,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            logger.info("sla_auto_accepted",
                        task_id=str(task.task_id), confidence=confidence)

            # [P1-C6] 5% 抽样复核
            if random.random() < AUTO_REVIEW_SAMPLE_RATE and self._task_mgr:
                await self._task_mgr.create_task(
                    db,
                    job_id=str(task.job_id),
                    page_number=task.page_number,
                    task_type="AUTO_SLA_REVIEW",
                    context={
                        "original_task_id": str(task.task_id),
                        "ai_result": ai_result,
                        "review_reason": "auto_sla_sample_review",
                    },
                    priority="HIGH",
                )
        else:
            await db.execute(
                update(HumanTask).where(HumanTask.task_id == task.task_id)
                .values(priority="AUTO_RESOLVE")
            )

    async def _partial_accept(self, db: AsyncSession, task: HumanTask):
        """L4: 部分接受 (超 3h 无人处理)。"""
        ai_result = (task.context or {}).get("ai_result", {})
        await db.execute(
            update(HumanTask).where(HumanTask.task_id == task.task_id)
            .values(
                status="COMPLETED",
                result={**ai_result, "partial_acceptance": True},
                completed_at=datetime.now(timezone.utc),
            )
        )
        logger.warning("sla_partial_accepted", task_id=str(task.task_id))
