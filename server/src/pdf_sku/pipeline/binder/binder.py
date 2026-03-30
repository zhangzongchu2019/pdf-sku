"""
SKU-图片绑定。对齐: Pipeline 详设 §5.4

策略路由:
- 单SKU页面上下文 → all_to_one (所有图归同一产品)
- TABLE/表格页面 → table_row_align (按表格行Y坐标对齐)
- 单图多SKU → shared (共享同一张图)
- 多图多SKU → y_coordinate_align (按Y坐标分段归组)
- 默认 → spatial_proximity (距离匹配, 原有逻辑)
"""
from __future__ import annotations
import math
from pdf_sku.pipeline.ir import (
    SKUResult, ImageInfo, BindingResult, BindingCandidate, ClassifyResult,
)
from pdf_sku.pipeline.classifier.fitz_classifier import PagePlan
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
        page_plan: PagePlan | None = None,
    ) -> list[BindingResult]:
        """将 SKU 绑定到最近的可交付图片。

        根据页面布局类型自动选择绑定策略。
        """
        # 筛选可交付图片
        deliverable = [
            img for img in images
            if (not img.role or img.role in DELIVERABLE_ROLES)
            and not img.is_duplicate
        ]

        if not skus or not deliverable:
            return [BindingResult(sku_id=s.sku_id, image_id=None, confidence=0.0)
                    for s in skus]

        # ── 策略路由 ──
        strategy = self._select_strategy(skus, deliverable, layout, page_plan)
        logger.debug("binding_strategy", strategy=strategy,
                     skus=len(skus), images=len(deliverable))

        if strategy == "all_to_one":
            return self._bind_all_to_one(skus, deliverable)
        elif strategy == "table_row_align":
            return self._bind_by_y_align(skus, deliverable)
        elif strategy == "shared":
            return self._bind_shared(skus, deliverable)
        elif strategy == "y_coordinate_align":
            return self._bind_by_y_align(skus, deliverable)
        else:
            return self._bind_spatial_proximity(skus, deliverable, layout)

    def _select_strategy(
        self,
        skus: list[SKUResult],
        images: list[ImageInfo],
        layout: ClassifyResult | None,
        page_plan: PagePlan | None,
    ) -> str:
        """根据页面特征选择绑定策略。"""
        page_class = page_plan.page_class if page_plan else ""

        # TABLE/MIXED_TABLE → 按Y坐标对齐
        if page_class in ("TABLE", "MIXED_TABLE"):
            return "table_row_align"

        # 单 SKU 页面上下文 → 所有图归该产品
        # 没有 page_plan 时保留原有距离匹配语义，避免影响通用调用方。
        if page_plan and len(skus) == 1:
            return "all_to_one"

        # 单图多SKU → 共享
        if page_plan and len(images) == 1 and len(skus) > 1:
            return "shared"

        # MULTI_SPARSE (2-4图+少文字) + SKU数接近图数 → Y坐标对齐
        if page_class == "MULTI_SPARSE":
            if len(skus) <= len(images):
                return "y_coordinate_align"
            return "shared"

        # 多图多SKU → 尝试Y坐标对齐
        if page_plan and len(images) >= len(skus):
            return "y_coordinate_align"

        # 默认: 距离匹配
        return "spatial_proximity"

    def _bind_all_to_one(
        self, skus: list[SKUResult], images: list[ImageInfo],
    ) -> list[BindingResult]:
        """所有图片绑定到唯一的 SKU。"""
        results = []
        for i, img in enumerate(images):
            results.append(BindingResult(
                sku_id=skus[0].sku_id,
                image_id=img.image_id,
                confidence=0.95,
                method="all_to_one",
                is_ambiguous=False,
                rank=i + 1,
            ))
        return results

    def _bind_shared(
        self, skus: list[SKUResult], images: list[ImageInfo],
    ) -> list[BindingResult]:
        """所有图片共享给所有 SKU（配套产品/组合场景）。"""
        results = []
        for sku in skus:
            for i, img in enumerate(images):
                results.append(BindingResult(
                    sku_id=sku.sku_id,
                    image_id=img.image_id,
                    confidence=0.80,
                    method="shared",
                    is_ambiguous=False,
                    rank=i + 1,
                ))
        return results

    def _bind_by_y_align(
        self, skus: list[SKUResult], images: list[ImageInfo],
    ) -> list[BindingResult]:
        """按 Y 坐标对齐: 图片和 SKU 各自按 Y 排序后对应绑定。

        适用于: 表格行对齐、上下分区、网格布局等。
        """
        # 按 Y 坐标排序
        sorted_skus = sorted(skus, key=lambda s: self._bbox_cy(s.source_bbox))
        sorted_imgs = sorted(images, key=lambda i: self._bbox_cy(i.bbox))

        results = []

        if len(sorted_imgs) == len(sorted_skus):
            # 图数 == SKU数 → 一一对应
            for sku, img in zip(sorted_skus, sorted_imgs):
                results.append(BindingResult(
                    sku_id=sku.sku_id,
                    image_id=img.image_id,
                    confidence=0.90,
                    method="y_coordinate_align",
                    is_ambiguous=False,
                ))
        elif len(sorted_imgs) > len(sorted_skus):
            # 图多于 SKU → 每个 SKU 分配最近的图(可能多张)
            per_sku = max(1, len(sorted_imgs) // len(sorted_skus))
            for i, sku in enumerate(sorted_skus):
                start = i * per_sku
                end = start + per_sku if i < len(sorted_skus) - 1 else len(sorted_imgs)
                for rank, img in enumerate(sorted_imgs[start:end], 1):
                    results.append(BindingResult(
                        sku_id=sku.sku_id,
                        image_id=img.image_id,
                        confidence=0.85,
                        method="y_coordinate_align",
                        is_ambiguous=False,
                        rank=rank,
                    ))
        else:
            # SKU 多于图 → 每个 SKU 绑定最近的图
            for sku in sorted_skus:
                sku_cy = self._bbox_cy(sku.source_bbox)
                nearest = min(sorted_imgs, key=lambda i: abs(self._bbox_cy(i.bbox) - sku_cy))
                results.append(BindingResult(
                    sku_id=sku.sku_id,
                    image_id=nearest.image_id,
                    confidence=0.80,
                    method="y_coordinate_align",
                    is_ambiguous=False,
                ))

        return results

    def _bind_spatial_proximity(
        self, skus: list[SKUResult], images: list[ImageInfo],
        layout: ClassifyResult | None,
    ) -> list[BindingResult]:
        """原有距离匹配逻辑（默认兜底）。"""
        layout_type = layout.layout_type if layout else "freeform"
        threshold = DISTANCE_THRESHOLDS.get(layout_type, 150)
        results = []

        for sku in skus:
            candidates = []
            for img in images:
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
    def _bbox_cy(bbox: tuple[float, ...]) -> float:
        """bbox 的 Y 中心坐标。"""
        if len(bbox) >= 4:
            return (bbox[1] + bbox[3]) / 2
        return 0.0

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
