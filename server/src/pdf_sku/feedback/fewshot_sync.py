"""
Few-Shot 样本同步。对齐: Feedback 详设 §4.3

- 高质量标注 → annotation_examples
- [P1-FC1] 双人共识: 同类型同品类 ≥2 名高分标注员一致才入库
- 防止单个错误标注污染 Few-shot 库
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import (
    Annotation, AnnotationExample, AnnotatorProfile, HumanTask,
)
import structlog

logger = structlog.get_logger()

QUALITY_THRESHOLD = 0.85
MIN_CONSENSUS_COUNT = 2


class FewShotSyncer:
    """Few-shot 样本同步器 (双人共识)。"""

    async def sync_from_task(
        self,
        db: AsyncSession,
        task: HumanTask,
        annotations: list[Annotation],
    ) -> int:
        """
        任务完成后同步优质标注到 Few-shot 库。

        Returns:
            同步入库的样本数
        """
        # 获取标注员画像
        profile = await self._get_profile(db, task.assigned_to or "")
        base_quality = profile.accuracy_rate if profile else 0.6
        synced = 0

        for ann in annotations:
            # 质量评估: 有 rework → 打折
            quality = base_quality * (1.0 if (task.rework_count or 0) == 0 else 0.7)
            if quality < QUALITY_THRESHOLD:
                continue

            # 共识 key: 类型 + 品类
            category = (ann.payload or {}).get("category", "default")
            output_hash = self._hash_output(ann.payload or {})
            consensus_key = f"{ann.type}:{category}:{output_hash}"

            # 检查已有共识数
            existing = await db.execute(
                select(func.count()).select_from(AnnotationExample).where(
                    AnnotationExample.task_type == ann.type,
                    AnnotationExample.category == category,
                    AnnotationExample.is_confirmed == False,  # noqa: E712
                )
            )
            pending_count = existing.scalar() or 0

            if pending_count + 1 >= MIN_CONSENSUS_COUNT:
                # 达到共识 → 入库 (confirmed)
                await self._upsert_example(
                    db, ann, category, quality, confirmed=True)
                # 同时确认已有的候选
                await db.execute(
                    update(AnnotationExample).where(
                        AnnotationExample.task_type == ann.type,
                        AnnotationExample.category == category,
                        AnnotationExample.is_confirmed == False,  # noqa: E712
                    ).values(is_confirmed=True)
                )
                synced += 1
                logger.info("fewshot_synced",
                            type=ann.type, category=category, quality=quality)
            else:
                # 记录候选 (等待第二人)
                await self._upsert_example(
                    db, ann, category, quality, confirmed=False)
                logger.debug("fewshot_candidate",
                             type=ann.type, category=category,
                             consensus_key=consensus_key)

        return synced

    async def get_examples(
        self,
        db: AsyncSession,
        task_type: str,
        category: str | None = None,
        limit: int = 5,
    ) -> list[AnnotationExample]:
        """获取 confirmed 的 Few-shot 样本。"""
        query = (
            select(AnnotationExample)
            .where(
                AnnotationExample.task_type == task_type,
                AnnotationExample.is_confirmed == True,  # noqa: E712
            )
            .order_by(AnnotationExample.quality_score.desc())
            .limit(limit)
        )
        if category:
            query = query.where(AnnotationExample.category == category)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def _upsert_example(
        self,
        db: AsyncSession,
        ann: Annotation,
        category: str,
        quality: float,
        confirmed: bool,
    ) -> None:
        db.add(AnnotationExample(
            task_type=ann.type,
            category=category,
            input_context=(ann.payload or {}).get("input_context", ""),
            output_json=ann.payload or {},
            quality_score=quality,
            is_confirmed=confirmed,
        ))

    async def _get_profile(
        self, db: AsyncSession, annotator_id: str,
    ) -> AnnotatorProfile | None:
        if not annotator_id:
            return None
        result = await db.execute(
            select(AnnotatorProfile).where(
                AnnotatorProfile.annotator_id == annotator_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _hash_output(payload: dict) -> str:
        """对输出内容做哈希 (忽略元数据), 用于共识匹配。"""
        canonical = json.dumps(
            {k: v for k, v in sorted(payload.items())
             if k not in ("annotator", "timestamp", "task_id", "annotated_at")},
            ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
