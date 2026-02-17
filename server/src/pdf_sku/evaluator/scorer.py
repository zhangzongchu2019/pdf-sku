"""
多维评分器。对齐: Evaluator 详设 §5.4 / TA §3.2

维度:
- text_clarity: 文本清晰度 (OCR 可读性)
- image_quality: 图片质量 (分辨率/清晰度)
- layout_structure: 布局结构规整度
- table_regularity: 表格规则性
- sku_density: SKU 信息密度

C_doc = Σ(Wi × Di) - prescan_penalty
"""
from __future__ import annotations
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()

DEFAULT_WEIGHTS = {
    "text_clarity": 0.25,
    "image_quality": 0.20,
    "layout_structure": 0.25,
    "table_regularity": 0.15,
    "sku_density": 0.15,
}

DIMENSION_NAMES = list(DEFAULT_WEIGHTS.keys())


@dataclass
class PageScore:
    """单页 LLM 评分结果。"""
    page_no: int
    overall: float = 0.0
    dimensions: dict[str, float] = field(default_factory=dict)
    raw_response: str | None = None


class Scorer:
    def aggregate(self, page_scores: list[PageScore]) -> dict[str, float]:
        """
        聚合多页评分 → 各维度均值。

        Returns:
            {"text_clarity": 0.82, "image_quality": 0.75, ...}
        """
        if not page_scores:
            return {d: 0.0 for d in DIMENSION_NAMES}

        sums: dict[str, float] = {d: 0.0 for d in DIMENSION_NAMES}
        counts: dict[str, int] = {d: 0 for d in DIMENSION_NAMES}

        for ps in page_scores:
            for dim in DIMENSION_NAMES:
                val = ps.dimensions.get(dim)
                if val is not None:
                    sums[dim] += val
                    counts[dim] += 1

        return {
            d: round(sums[d] / counts[d], 4) if counts[d] > 0 else 0.0
            for d in DIMENSION_NAMES
        }

    def compute_c_doc(
        self,
        dimension_scores: dict[str, float],
        weights: dict[str, float] | None = None,
        prescan_penalty: float = 0.0,
    ) -> float:
        """
        计算文档级置信度 C_doc。

        C_doc = Σ(Wi × Di) - prescan_penalty
        Clamp to [0.0, 1.0]
        """
        w = weights or DEFAULT_WEIGHTS

        # INV-02: ΣWi ≈ 1.0 (容差 0.01)
        total_weight = sum(w.get(d, 0) for d in DIMENSION_NAMES)
        if abs(total_weight - 1.0) > 0.01:
            logger.warning("weight_sum_invalid",
                           total=total_weight, expected=1.0)

        c_doc = 0.0
        for dim in DIMENSION_NAMES:
            score = dimension_scores.get(dim, 0.0)
            weight = w.get(dim, DEFAULT_WEIGHTS.get(dim, 0.0))
            c_doc += weight * score

        c_doc -= prescan_penalty
        c_doc = max(0.0, min(1.0, c_doc))

        logger.info("c_doc_computed",
                     c_doc=round(c_doc, 4),
                     penalty=prescan_penalty,
                     dimensions={d: round(dimension_scores.get(d, 0), 3)
                                 for d in DIMENSION_NAMES})
        return round(c_doc, 4)
