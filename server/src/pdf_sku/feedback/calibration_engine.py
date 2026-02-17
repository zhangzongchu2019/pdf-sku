"""
校准引擎。对齐: Feedback 详设 §4.1

- 7 天窗口内标注偏差分析
- [P0-1] 安全护栏: ±10% 限幅, 最少标注员数, KL 散度异常检测
- [P1-FC2] MIN_SAMPLES 可配置
- [P1-FC3] 建议 → 运营审批队列
- [P1-FC4] PENDING >48h 提醒
"""
from __future__ import annotations
import math
from collections import Counter
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import Annotation, CalibrationRecord
import structlog

logger = structlog.get_logger()

ANALYSIS_WINDOW_DAYS = 7
MAX_THRESHOLD_DRIFT = 0.10
MIN_ANNOTATORS = 3
MIN_SAMPLES_DEFAULT = 50
KL_DIVERGENCE_THRESHOLD = 0.5
APPROVAL_SLA_HOURS = 48


class CalibrationEngine:
    """校准引擎 (偏差分析 + 安全护栏)。"""

    def __init__(self, notifier=None, config_provider=None):
        self._notifier = notifier
        self._config = config_provider

    async def check_and_calibrate(self, db: AsyncSession) -> CalibrationRecord | None:
        """
        执行一轮校准检查。

        Returns:
            CalibrationRecord (PENDING) 或 None
        """
        # 动态 MIN_SAMPLES
        min_samples = MIN_SAMPLES_DEFAULT
        if self._config:
            try:
                min_samples = int(self._config.get_frozen_config(None).get(
                    "calibration_min_samples", MIN_SAMPLES_DEFAULT))
            except Exception:
                pass

        cutoff = datetime.now(timezone.utc) - timedelta(days=ANALYSIS_WINDOW_DAYS)

        # 样本量检查
        count_result = await db.execute(
            select(func.count()).select_from(Annotation).where(
                Annotation.annotated_at >= cutoff))
        sample_count = count_result.scalar() or 0
        if sample_count < min_samples:
            logger.debug("calibration_skip_few_samples",
                         count=sample_count, min=min_samples)
            return None

        # 标注员数检查
        ann_result = await db.execute(
            select(func.count(func.distinct(Annotation.annotator))).where(
                Annotation.annotated_at >= cutoff))
        annotator_count = ann_result.scalar() or 0
        if annotator_count < MIN_ANNOTATORS:
            logger.info("calibration_skip_few_annotators",
                        count=annotator_count, min=MIN_ANNOTATORS)
            return None

        # 获取标注数据
        result = await db.execute(
            select(Annotation).where(Annotation.annotated_at >= cutoff))
        annotations = list(result.scalars().all())

        suggestions = []

        # 1. 页面分类偏差
        page_corrections = [a for a in annotations
                            if a.type == "PAGE_TYPE_CORRECTION"]
        if page_corrections:
            confusion = self._build_confusion_matrix(page_corrections)
            accuracy = self._calc_accuracy(confusion)
            if accuracy < 0.85:
                suggestions.append({
                    "action": "review_classify_prompt",
                    "accuracy": round(accuracy, 4),
                    "confusion": confusion,
                    "sample_count": len(page_corrections),
                })

        # 2. SKU 置信度校准
        sku_corrections = [a for a in annotations
                           if a.type == "SKU_ATTRIBUTE_CORRECTION"]
        if sku_corrections:
            drift = self._analyze_confidence_drift(sku_corrections)

            # 安全护栏: 限幅
            if abs(drift) > MAX_THRESHOLD_DRIFT:
                logger.warning("calibration_drift_clamped",
                               raw_drift=drift, clamped=MAX_THRESHOLD_DRIFT)
                drift = max(-MAX_THRESHOLD_DRIFT,
                            min(MAX_THRESHOLD_DRIFT, drift))

            # KL 散度异常检测
            kl = self._compute_kl_divergence(sku_corrections)
            if kl > KL_DIVERGENCE_THRESHOLD:
                logger.error("calibration_distribution_anomaly",
                             kl_divergence=round(kl, 4),
                             threshold=KL_DIVERGENCE_THRESHOLD)
                return None  # 异常 → 不自动建议

            if abs(drift) > 0.02:
                suggestions.append({
                    "action": "adjust_thresholds",
                    "threshold_drift": round(drift, 4),
                    "drift_clamped": abs(drift) >= MAX_THRESHOLD_DRIFT,
                    "kl_divergence": round(kl, 4),
                    "sample_count": len(sku_corrections),
                })

        # 3. 绑定偏差
        binding_corrections = [a for a in annotations
                               if a.type == "IMAGE_BINDING_CORRECTION"]
        if len(binding_corrections) > 10:
            binding_error_rate = len(binding_corrections) / max(1, sample_count)
            if binding_error_rate > 0.15:
                suggestions.append({
                    "action": "review_binding_thresholds",
                    "binding_error_rate": round(binding_error_rate, 4),
                    "sample_count": len(binding_corrections),
                })

        if not suggestions:
            return None

        # 创建校准记录 (PENDING)
        record = CalibrationRecord(
            calibration_id=uuid4(),
            profile_id="default",
            type="THRESHOLD",
            period_start=cutoff,
            period_end=datetime.now(timezone.utc),
            sample_count=sample_count,
            suggested_adjustments={"suggestions": suggestions},
            status="PENDING",
        )
        db.add(record)

        logger.info("calibration_created",
                     suggestions=len(suggestions),
                     sample_count=sample_count,
                     annotators=annotator_count)

        # 通知运营
        if self._notifier:
            await self._notifier.send(
                channel="ops",
                message=f"📊 新校准建议: {len(suggestions)} 条变更待审批 "
                        f"(样本量={sample_count})",
                level="INFO")

        return record

    async def check_approval_sla(self, db: AsyncSession) -> int:
        """检查 PENDING 超时 → 提醒。"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=APPROVAL_SLA_HOURS)
        result = await db.execute(
            select(CalibrationRecord).where(
                CalibrationRecord.status == "PENDING",
                CalibrationRecord.created_at < cutoff,
            )
        )
        stale = result.scalars().all()
        reminded = 0

        for record in stale:
            if self._notifier:
                await self._notifier.send(
                    channel="ops",
                    message=f"⚠️ 校准建议 #{record.calibration_id} "
                            f"已超 {APPROVAL_SLA_HOURS}h 未审批",
                    level="WARNING")
            reminded += 1

        return reminded

    async def apply_calibration(
        self,
        db: AsyncSession,
        calibration_id: str,
        operator: str,
    ) -> bool:
        """审批通过 → 应用校准。"""
        from sqlalchemy import update as sa_update
        result = await db.execute(
            sa_update(CalibrationRecord).where(
                CalibrationRecord.calibration_id == calibration_id,
                CalibrationRecord.status == "PENDING",
            ).values(
                status="APPROVED",
                applied=True,
                applied_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount == 0:
            return False

        logger.info("calibration_applied",
                     calibration_id=calibration_id, operator=operator)
        return True

    async def reject_calibration(
        self,
        db: AsyncSession,
        calibration_id: str,
        reason: str,
        operator: str,
    ) -> bool:
        """驳回校准建议。"""
        from sqlalchemy import update as sa_update
        result = await db.execute(
            sa_update(CalibrationRecord).where(
                CalibrationRecord.calibration_id == calibration_id,
                CalibrationRecord.status == "PENDING",
            ).values(status="REJECTED")
        )
        if result.rowcount == 0:
            return False

        logger.info("calibration_rejected",
                     calibration_id=calibration_id,
                     operator=operator, reason=reason)
        return True

    # ── Analysis Helpers ──

    @staticmethod
    def _build_confusion_matrix(corrections: list[Annotation]) -> dict:
        matrix: dict[str, int] = {}
        for c in corrections:
            payload = c.payload or {}
            ai = payload.get("ai_page_type", "?")
            human = payload.get("corrected_page_type", "?")
            key = f"{ai}->{human}"
            matrix[key] = matrix.get(key, 0) + 1
        return matrix

    @staticmethod
    def _calc_accuracy(confusion: dict) -> float:
        total = sum(confusion.values())
        if total == 0:
            return 1.0
        correct = sum(v for k, v in confusion.items()
                      if k.split("->")[0] == k.split("->")[1])
        return correct / total

    @staticmethod
    def _analyze_confidence_drift(corrections: list[Annotation]) -> float:
        """计算 AI 置信度偏差 (正=过度自信, 负=过度保守)。"""
        drifts = []
        for c in corrections:
            payload = c.payload or {}
            ai_conf = payload.get("ai_confidence", 0.5)
            was_correct = payload.get("was_correct", True)
            if was_correct:
                drifts.append(ai_conf - 1.0)  # 正确但信心不够
            else:
                drifts.append(ai_conf - 0.0)  # 错误但信心太高
        return sum(drifts) / max(1, len(drifts))

    @staticmethod
    def _compute_kl_divergence(corrections: list[Annotation]) -> float:
        """KL(AI分布 || 人工分布)。"""
        ai_buckets: Counter = Counter()
        human_buckets: Counter = Counter()
        for c in corrections:
            payload = c.payload or {}
            ai_conf = payload.get("ai_confidence", 0.5)
            was_correct = payload.get("was_correct", True)
            ai_bucket = round(ai_conf, 1)
            human_bucket = 1.0 if was_correct else 0.0
            ai_buckets[ai_bucket] += 1
            human_buckets[human_bucket] += 1

        all_keys = set(ai_buckets) | set(human_buckets)
        total_ai = sum(ai_buckets.values()) or 1
        total_human = sum(human_buckets.values()) or 1
        n = len(all_keys) or 1

        kl = 0.0
        for key in all_keys:
            p = (ai_buckets.get(key, 0) + 1) / (total_ai + n)
            q = (human_buckets.get(key, 0) + 1) / (total_human + n)
            if p > 0 and q > 0:
                kl += p * math.log(p / q)
        return abs(kl)
