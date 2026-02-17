"""
ConfigProvider 实现。对齐: Config 详设 §5.1 + 接口契约 §2.6

核心职责:
- ThresholdProfile CRUD (乐观锁)
- INV-01 校验: B < PV < A
- INV-02 校验: ΣWi = 1.0
- 配置冻结 (Evaluator/Pipeline 调用)
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import ThresholdProfileModel
from pdf_sku.common.schemas import ThresholdSet
from pdf_sku.common.exceptions import (
    ConfigVersionConflictError, ConfigThresholdInvalidError, ConfigNotFoundError,
)
import structlog

logger = structlog.get_logger()

# 默认配置
DEFAULT_PROFILE = {
    "profile_id": "default",
    "version": "v1.0",
    "thresholds": {"A": 0.85, "B": 0.45, "PV": 0.65},
    "confidence_weights": {
        "text_clarity": 0.25,
        "image_quality": 0.20,
        "layout_structure": 0.25,
        "table_regularity": 0.15,
        "sku_density": 0.15,
    },
    "prescan_rules": {
        "min_text_chars_for_blank": 10,
        "min_ocr_rate": 0.3,
        "min_image_ratio": 0.1,
        "score_variance_threshold": 0.08,
    },
    "classification_thresholds": {
        "product_page_min_confidence": 0.6,
        "table_page_min_confidence": 0.7,
    },
    "sku_validity_mode": "strict",
}


class ConfigProvider:
    """阈值配置管理器。"""

    async def get_active_profile(
        self, db: AsyncSession, profile_id: str = "default"
    ) -> dict:
        """获取活跃配置版本。"""
        result = await db.execute(
            select(ThresholdProfileModel).where(
                ThresholdProfileModel.profile_id == profile_id,
                ThresholdProfileModel.is_active == True,
            ).order_by(desc(ThresholdProfileModel.effective_from)).limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            logger.info("config_default_used", profile_id=profile_id)
            return DEFAULT_PROFILE.copy()

        return self._row_to_dict(row)

    async def get_profile_by_version(
        self, db: AsyncSession, profile_id: str, version: str
    ) -> dict:
        """获取指定版本配置 (冻结用)。"""
        result = await db.execute(
            select(ThresholdProfileModel).where(
                ThresholdProfileModel.profile_id == profile_id,
                ThresholdProfileModel.version == version,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ConfigNotFoundError(f"Profile {profile_id}:{version} not found")
        return self._row_to_dict(row)

    async def get_frozen_config(
        self, db: AsyncSession, frozen_config_version: str
    ) -> dict:
        """
        解析冻结版本字符串 → 配置。
        格式: "{profile_id}:{version}" 或 "{profile_id}" (取活跃版本)
        """
        parts = frozen_config_version.split(":", 1)
        profile_id = parts[0]

        if len(parts) == 2 and parts[1]:
            return await self.get_profile_by_version(db, profile_id, parts[1])
        else:
            return await self.get_active_profile(db, profile_id)

    async def create_or_update_profile(
        self,
        db: AsyncSession,
        profile_id: str,
        data: dict,
        expected_version: str | None = None,
        created_by: str = "",
        change_reason: str = "",
    ) -> dict:
        """
        创建/更新配置 (乐观锁)。

        INV-01: B < PV < A
        INV-02: ΣWi = 1.0
        """
        # 获取当前活跃版本
        current = await db.execute(
            select(ThresholdProfileModel).where(
                ThresholdProfileModel.profile_id == profile_id,
                ThresholdProfileModel.is_active == True,
            ).order_by(desc(ThresholdProfileModel.effective_from)).limit(1)
        )
        current_row = current.scalar_one_or_none()

        # 乐观锁: 版本检查
        if expected_version and current_row:
            if current_row.version != expected_version:
                raise ConfigVersionConflictError(
                    f"Expected version {expected_version}, current is {current_row.version}")

        # 校验 INV-01: B < PV < A
        thresholds = data.get("thresholds", {})
        if thresholds:
            A = thresholds.get("A", 0.85)
            B = thresholds.get("B", 0.45)
            PV = thresholds.get("PV", 0.65)
            if not (B < PV < A):
                raise ConfigThresholdInvalidError(
                    f"INV-01 violated: B({B}) < PV({PV}) < A({A}) must hold")
            if not (0 < B < 1 and 0 < PV < 1 and 0 < A <= 1):
                raise ConfigThresholdInvalidError("Thresholds must be in (0, 1]")

        # 校验 INV-02: ΣWi = 1.0
        weights = data.get("confidence_weights", {})
        if weights:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                raise ConfigThresholdInvalidError(
                    f"INV-02 violated: ΣWi = {total:.4f} ≠ 1.0")

        # 生成新版本号
        if current_row:
            prev_version = current_row.version
            # v1.0 → v2.0
            try:
                v_num = int(prev_version.replace("v", "").split(".")[0])
                new_version = f"v{v_num + 1}.0"
            except (ValueError, IndexError):
                new_version = f"v{prev_version}_next"
        else:
            prev_version = None
            new_version = data.get("version", "v1.0")

        # 标记旧版本非活跃
        if current_row:
            current_row.is_active = False

        # 创建新版本
        merged = DEFAULT_PROFILE.copy()
        merged.update(data)

        new_row = ThresholdProfileModel(
            profile_id=profile_id,
            version=new_version,
            previous_version=prev_version,
            category=merged.get("category"),
            industry=merged.get("industry"),
            thresholds=merged.get("thresholds", DEFAULT_PROFILE["thresholds"]),
            confidence_weights=merged.get("confidence_weights", DEFAULT_PROFILE["confidence_weights"]),
            prescan_rules=merged.get("prescan_rules", DEFAULT_PROFILE["prescan_rules"]),
            classification_thresholds=merged.get("classification_thresholds", {}),
            sku_validity_mode=merged.get("sku_validity_mode", "strict"),
            is_active=True,
            created_by=created_by,
            change_reason=change_reason,
        )
        db.add(new_row)
        await db.flush()

        logger.info("config_updated",
                     profile_id=profile_id, version=new_version,
                     prev=prev_version, by=created_by)

        return self._row_to_dict(new_row)

    async def list_profiles(self, db: AsyncSession) -> list[dict]:
        """列出所有活跃 profile。"""
        result = await db.execute(
            select(ThresholdProfileModel)
            .where(ThresholdProfileModel.is_active == True)
            .order_by(ThresholdProfileModel.profile_id)
        )
        return [self._row_to_dict(r) for r in result.scalars().all()]

    async def get_profile_history(
        self, db: AsyncSession, profile_id: str, limit: int = 20
    ) -> list[dict]:
        """获取 profile 版本历史。"""
        result = await db.execute(
            select(ThresholdProfileModel)
            .where(ThresholdProfileModel.profile_id == profile_id)
            .order_by(desc(ThresholdProfileModel.effective_from))
            .limit(limit)
        )
        return [self._row_to_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _row_to_dict(row: ThresholdProfileModel) -> dict:
        return {
            "profile_id": row.profile_id,
            "version": row.version,
            "previous_version": row.previous_version,
            "category": row.category,
            "industry": row.industry,
            "thresholds": row.thresholds,
            "confidence_weights": row.confidence_weights,
            "prescan_rules": row.prescan_rules,
            "classification_thresholds": row.classification_thresholds,
            "sku_validity_mode": row.sku_validity_mode,
            "is_active": row.is_active,
            "effective_from": row.effective_from.isoformat() if row.effective_from else None,
            "created_by": row.created_by,
            "change_reason": row.change_reason,
        }
