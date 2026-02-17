"""
智能派单。对齐: Collaboration 详设 §5.2

- 难任务 (confidence < 0.5) → 仅高准确率标注员
- 评分 = quality × 0.6 + load_balance × 0.4
- 无合适人选 → None (进公共队列)
- [P1-C10] 冷启动: 前 10 个任务随机分配
"""
from __future__ import annotations
import random
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import HumanTask, AnnotatorProfile
import structlog

logger = structlog.get_logger()

COLD_START_THRESHOLD = 10
MIN_ACCURACY_FOR_HARD = 0.85
MAX_TASKS_PER_ANNOTATOR = 10


class SmartDispatcher:

    async def assign(
        self, db: AsyncSession, task: HumanTask,
    ) -> str | None:
        """
        为任务分配标注员。

        Returns:
            annotator_id 或 None (进公共队列)
        """
        difficulty = (task.context or {}).get("page_confidence", 0.5)
        available = await self._get_available(db)

        if not available:
            return None

        scored = []
        for ann in available:
            profile = ann[0]  # AnnotatorProfile
            current_tasks = ann[1]  # count

            # 冷启动: 随机分配
            if profile.total_tasks < COLD_START_THRESHOLD:
                scored.append((profile.annotator_id, random.random()))
                continue

            # 难任务过滤
            if difficulty < 0.5 and profile.accuracy_rate < MIN_ACCURACY_FOR_HARD:
                continue

            load = 1.0 - min(current_tasks / MAX_TASKS_PER_ANNOTATOR, 1.0)
            score = profile.accuracy_rate * 0.6 + load * 0.4
            scored.append((profile.annotator_id, score))

        if not scored:
            return None

        scored.sort(key=lambda x: x[1], reverse=True)
        winner = scored[0][0]
        logger.debug("task_assigned", task_id=str(task.task_id), annotator=winner)
        return winner

    async def _get_available(self, db: AsyncSession):
        """获取可用标注员 + 当前任务数。"""
        result = await db.execute(
            select(
                AnnotatorProfile,
                func.count(HumanTask.task_id).label("active_tasks"),
            )
            .outerjoin(
                HumanTask,
                (HumanTask.assigned_to == AnnotatorProfile.annotator_id) &
                (HumanTask.status == "PROCESSING"),
            )
            .group_by(AnnotatorProfile.annotator_id)
            .having(func.count(HumanTask.task_id) < MAX_TASKS_PER_ANNOTATOR)
        )
        return result.all()
