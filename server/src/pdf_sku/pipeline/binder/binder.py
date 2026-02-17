"""
SKU-图片绑定。对齐: Pipeline 详设 §5.4

策略:
- 按版面类型选距离阈值 (L1~L4)
- 歧义: top1-top2 < 0.2 → 不落绑定, 携带 topK=3 候选
- 宁可不绑也别错绑
- [C15] binding_method 推断
"""
from __future__ import annotations
import math
from pdf_sku.pipeline.ir import (
    SKUResult, ImageInfo, BindingResult, BindingCandidate, ClassifyResult,
)
import structlog

logger = structlog.get_logger()

DISTANCE_THRESHOLDS = {
    "grid": 100,
    "table": 150,
    "list": 200,
    "freeform": 150,
    "single_product": 300,
}
AMBIGUITY_GAP = 0.2
TOP_K = 3
DELIVERABLE_ROLES = {"product_main", "product_detail"}


class SKUImageBinder:
    def bind(
        self,
        skus: list[SKUResult],
        images: list[ImageInfo],
        layout: ClassifyResult | None = None,
        profile: dict | None = None,
    ) -> list[BindingResult]:
        """将 SKU 绑定到最近的可交付图片。"""
        layout_type = layout.layout_type if layout else "freeform"
        threshold = DISTANCE_THRESHOLDS.get(layout_type, 150)
        results = []

        # 筛选可交付图片
        deliverable = [
            img for img in images
            if (not img.role or img.role in DELIVERABLE_ROLES)
            and not img.is_duplicate
        ]

        for sku in skus:
            candidates = []
            for img in deliverable:
                dist = self._bbox_distance(sku.source_bbox, img.bbox)
                if dist <= threshold:
                    conf = max(0.01, 1.0 - (dist / threshold))
                    method = self._infer_method(sku, img, layout_type)
                    candidates.append(BindingCandidate(
                        image_id=img.image_id,
                        confidence=round(conf, 3),
                        method=method,
                    ))

            candidates.sort(key=lambda c: c.confidence, reverse=True)

            if not candidates:
                results.append(BindingResult(
                    sku_id=sku.sku_id, image_id=None,
                    confidence=0.0, is_ambiguous=False))
            elif (len(candidates) == 1 or
                  candidates[0].confidence - candidates[1].confidence >= AMBIGUITY_GAP):
                results.append(BindingResult(
                    sku_id=sku.sku_id,
                    image_id=candidates[0].image_id,
                    confidence=candidates[0].confidence,
                    method=candidates[0].method,
                    is_ambiguous=False,
                ))
            else:
                results.append(BindingResult(
                    sku_id=sku.sku_id, image_id=None,
                    confidence=candidates[0].confidence,
                    is_ambiguous=True,
                    candidates=candidates[:TOP_K],
                ))
                logger.debug("binding_ambiguous",
                             sku_id=sku.sku_id, top_k=len(candidates[:TOP_K]))
        return results

    @staticmethod
    def _bbox_distance(
        bbox1: tuple[float, ...], bbox2: tuple[float, ...]
    ) -> float:
        """两个 bbox 的中心距离。"""
        if len(bbox1) < 4 or len(bbox2) < 4:
            return float("inf")
        cx1 = (bbox1[0] + bbox1[2]) / 2
        cy1 = (bbox1[1] + bbox1[3]) / 2
        cx2 = (bbox2[0] + bbox2[2]) / 2
        cy2 = (bbox2[1] + bbox2[3]) / 2
        return math.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)

    @staticmethod
    def _infer_method(sku: SKUResult, img: ImageInfo, layout_type: str) -> str:
        """[C15] 推断绑定方法。"""
        if layout_type == "grid":
            return "grid_alignment"
        sx = (sku.source_bbox[0] + sku.source_bbox[2]) / 2 if len(sku.source_bbox) >= 4 else 0
        sy = (sku.source_bbox[1] + sku.source_bbox[3]) / 2 if len(sku.source_bbox) >= 4 else 0
        ix = (img.bbox[0] + img.bbox[2]) / 2 if len(img.bbox) >= 4 else 0
        iy = (img.bbox[1] + img.bbox[3]) / 2 if len(img.bbox) >= 4 else 0
        dx, dy = abs(sx - ix), abs(sy - iy)
        if dx < 50 and dy > 100:
            return "vertical_stack"
        if dy < 50 and dx > 100:
            return "reading_order"
        return "spatial_proximity"
