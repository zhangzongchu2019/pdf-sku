"""
采样得分方差 + 熵值检测。对齐: Evaluator 详设 §5.6

当方差过高时 → variance_forced=True → 强制 HYBRID 路由
防止少量极差页被平均分掩盖。
"""
from __future__ import annotations
import math
import structlog

logger = structlog.get_logger()

DEFAULT_VARIANCE_THRESHOLD = 0.08
DEFAULT_ENTROPY_THRESHOLD = 0.7


class VarianceDetector:
    def check(
        self,
        page_scores: list[float],
        variance_threshold: float | None = None,
        entropy_threshold: float | None = None,
    ) -> tuple[float, bool]:
        """
        检查页间评分一致性。

        Returns:
            (variance, forced): variance 值 + 是否强制 HYBRID
        """
        if len(page_scores) < 3:
            return 0.0, False

        vt = variance_threshold or DEFAULT_VARIANCE_THRESHOLD
        et = entropy_threshold or DEFAULT_ENTROPY_THRESHOLD

        # 方差
        mean = sum(page_scores) / len(page_scores)
        variance = sum((s - mean) ** 2 for s in page_scores) / len(page_scores)

        # 归一化熵 (将分数离散为 10 个 bin)
        entropy = self._compute_entropy(page_scores)

        forced = variance > vt or entropy > et

        if forced:
            logger.warning("variance_forced",
                           variance=round(variance, 4),
                           entropy=round(entropy, 4),
                           threshold_var=vt, threshold_ent=et,
                           scores_sample=page_scores[:5])

        return round(variance, 6), forced

    @staticmethod
    def _compute_entropy(scores: list[float]) -> float:
        """将分数离散化到 10 bin → 计算归一化熵。"""
        if not scores:
            return 0.0

        bins = [0] * 10
        for s in scores:
            idx = min(9, int(s * 10))
            bins[idx] += 1

        n = len(scores)
        entropy = 0.0
        for count in bins:
            if count > 0:
                p = count / n
                entropy -= p * math.log2(p)

        max_entropy = math.log2(10)
        return entropy / max_entropy if max_entropy > 0 else 0.0
