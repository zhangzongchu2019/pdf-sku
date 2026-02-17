"""
影响预估计算。对齐: 接口契约 §2.6 get_impact_preview

基于历史 evaluation 数据, 模拟新阈值下的 auto/human/reject 比例变化。
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob, Page
import structlog

logger = structlog.get_logger()

PREVIEW_WINDOW_DAYS = 30


@dataclass
class ImpactPreviewResult:
    """阈值变更影响预估结果。"""
    current_auto_rate: float = 0.0
    projected_auto_rate: float = 0.0
    current_human_rate: float = 0.0
    projected_human_rate: float = 0.0
    current_reject_rate: float = 0.0
    projected_reject_rate: float = 0.0
    sample_count: int = 0
    confidence_interval: float = 0.0

    def to_dict(self) -> dict:
        return {
            "current_auto_rate": round(self.current_auto_rate, 4),
            "projected_auto_rate": round(self.projected_auto_rate, 4),
            "current_human_rate": round(self.current_human_rate, 4),
            "projected_human_rate": round(self.projected_human_rate, 4),
            "current_reject_rate": round(self.current_reject_rate, 4),
            "projected_reject_rate": round(self.projected_reject_rate, 4),
            "sample_count": self.sample_count,
            "confidence_interval": round(self.confidence_interval, 4),
            "delta_auto": round(self.projected_auto_rate - self.current_auto_rate, 4),
            "delta_human": round(self.projected_human_rate - self.current_human_rate, 4),
        }


class ImpactPreviewCalculator:
    """阈值变更影响预估。"""

    async def preview(
        self,
        db: AsyncSession,
        current_thresholds: dict,
        proposed_thresholds: dict,
    ) -> ImpactPreviewResult:
        """
        基于近 N 天数据, 预估阈值变更影响。

        current_thresholds: {"A": 0.85, "B": 0.45, "PV": 0.65}
        proposed_thresholds: {"A": 0.80, "B": 0.50, "PV": 0.60}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=PREVIEW_WINDOW_DAYS)

        # 获取历史 Job 评估分数
        result = await db.execute(
            select(PDFJob).where(
                PDFJob.created_at >= cutoff,
                PDFJob.eval_score.isnot(None),
            )
        )
        jobs = result.scalars().all()

        if not jobs:
            return ImpactPreviewResult()

        # 当前阈值下的路由分布
        current_dist = self._simulate_routing(jobs, current_thresholds)
        proposed_dist = self._simulate_routing(jobs, proposed_thresholds)

        n = len(jobs)
        # Wilson score interval (95%)
        import math
        z = 1.96
        p = proposed_dist["auto"] / max(1, n)
        ci = z * math.sqrt(p * (1 - p) / max(1, n))

        return ImpactPreviewResult(
            current_auto_rate=current_dist["auto"] / max(1, n),
            projected_auto_rate=proposed_dist["auto"] / max(1, n),
            current_human_rate=current_dist["human"] / max(1, n),
            projected_human_rate=proposed_dist["human"] / max(1, n),
            current_reject_rate=current_dist["reject"] / max(1, n),
            projected_reject_rate=proposed_dist["reject"] / max(1, n),
            sample_count=n,
            confidence_interval=ci,
        )

    @staticmethod
    def _simulate_routing(jobs, thresholds: dict) -> dict:
        """模拟给定阈值下的路由分布。"""
        auto = human = reject = 0
        a_thresh = thresholds.get("A", 0.85)
        b_thresh = thresholds.get("B", 0.45)

        for job in jobs:
            score = job.eval_score or 0
            if score >= a_thresh:
                auto += 1
            elif score >= b_thresh:
                human += 1
            else:
                reject += 1

        return {"auto": auto, "human": human, "reject": reject}
