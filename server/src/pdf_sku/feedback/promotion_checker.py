"""
属性升级检查器。对齐: Feedback 详设 §4.2

- 同品类同属性确认 ≥20 次 → 升级候选
- 记入 CalibrationRecord (type=ATTR_PROMOTION, PENDING)
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import (
    Annotation, CalibrationRecord, CustomAttrUpgrade,
)
import structlog

logger = structlog.get_logger()

PROMOTION_THRESHOLD = 20


class AttrPromotionChecker:
    """属性升级检查器。"""

    async def check_promotions(self, db: AsyncSession) -> list[dict]:
        """
        扫描标注中频繁出现的非标属性 → 生成升级建议。

        Returns:
            升级候选列表
        """
        # 获取 SKU_ATTRIBUTE_CORRECTION 类型标注
        result = await db.execute(
            select(Annotation).where(
                Annotation.type.in_([
                    "SKU_ATTRIBUTE_CORRECTION",
                    "SKU_ATTRIBUTE_ADDITION",
                ])
            )
        )
        annotations = result.scalars().all()

        # 统计: (category, attr_name) → count
        attr_counter: Counter = Counter()
        for ann in annotations:
            payload = ann.payload or {}
            category = payload.get("category", "default")
            added_attrs = payload.get("added_attributes", {})
            for attr_name in added_attrs:
                attr_counter[(category, attr_name)] += 1

        # 过滤达到阈值的候选
        candidates = []
        for (category, attr_name), count in attr_counter.items():
            if count >= PROMOTION_THRESHOLD:
                # 检查是否已有该升级记录
                existing = await db.execute(
                    select(CustomAttrUpgrade).where(
                        CustomAttrUpgrade.attr_name == attr_name,
                        CustomAttrUpgrade.category == category,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # 创建升级记录
                upgrade = CustomAttrUpgrade(
                    attr_name=attr_name,
                    suggested_type="text",
                    category=category,
                    source_feedback_count=count,
                )
                db.add(upgrade)

                # 创建校准记录
                record = CalibrationRecord(
                    calibration_id=uuid4(),
                    profile_id="default",
                    type="ATTR_PROMOTION",
                    period_start=datetime.now(timezone.utc),
                    period_end=datetime.now(timezone.utc),
                    sample_count=count,
                    suggested_adjustments={
                        "action": f"Add '{attr_name}' to {category}.required_fields",
                        "category": category,
                        "attr_name": attr_name,
                        "confirm_count": count,
                    },
                    status="PENDING",
                )
                db.add(record)

                candidates.append({
                    "category": category,
                    "attr_name": attr_name,
                    "count": count,
                })
                logger.info("attr_promotion_candidate",
                            category=category, attr_name=attr_name, count=count)

        return candidates
