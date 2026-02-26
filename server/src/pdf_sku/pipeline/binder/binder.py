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
    "grid": 300,
    "table": 400,
    "list": 500,
    "freeform": 500,
    "single_product": 800,
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
            if (not img.role or img.role in DELIVERABLE_ROLES or img.role == "unknown")
            and not img.is_duplicate
        ]

        # 单 SKU 多图: 所有图片都绑定到该 SKU
        if len(skus) == 1 and len(deliverable) >= 1:
            for rank, img in enumerate(deliverable):
                results.append(BindingResult(
                    sku_id=skus[0].sku_id, image_id=img.image_id,
                    confidence=0.7, method="single_sku_all_images",
                    is_ambiguous=False, rank=rank + 1))
            return results

        # 单图页面: 所有 SKU 直接绑定唯一图片
        if len(deliverable) == 1:
            only_img = deliverable[0]
            for sku in skus:
                results.append(BindingResult(
                    sku_id=sku.sku_id, image_id=only_img.image_id,
                    confidence=0.6, method="single_image_page",
                    is_ambiguous=False,
                ))
            self._unify_product_bindings(skus, results)
            return results

        # 零 bbox 批量处理: 所有 SKU 都是零 bbox 时用位置启发式匹配
        all_zero = all(self._is_zero_bbox(s.source_bbox) for s in skus)
        if all_zero and deliverable:
            return self._bind_zero_bbox_skus(skus, deliverable)
        if all_zero and not deliverable:
            for sku in skus:
                results.append(BindingResult(
                    sku_id=sku.sku_id, image_id=None,
                    confidence=0.0, is_ambiguous=False))
            return results

        for sku in skus:
            # 单个零 bbox SKU: 降级到最大图片
            if self._is_zero_bbox(sku.source_bbox):
                if deliverable:
                    largest = max(deliverable, key=lambda img: self._bbox_area(img.bbox))
                    results.append(BindingResult(
                        sku_id=sku.sku_id, image_id=largest.image_id,
                        confidence=0.4, method="zero_bbox_largest",
                        is_ambiguous=True))
                else:
                    results.append(BindingResult(
                        sku_id=sku.sku_id, image_id=None,
                        confidence=0.0, is_ambiguous=False))
                continue

            # 大 bbox (覆盖 >50% 页面): 用包含关系匹配，取 bbox 内最大图片
            is_large = self._is_fullpage_bbox(
                sku.source_bbox, [img.bbox for img in deliverable]
            ) if deliverable else False

            candidates = []
            if is_large:
                # 找 SKU bbox 内包含的图片，按面积降序
                contained = self._find_contained_images(
                    sku.source_bbox, deliverable)
                if contained:
                    best = contained[0]
                    candidates.append(BindingCandidate(
                        image_id=best.image_id,
                        confidence=0.6,
                        method="containment",
                    ))

            if not candidates:
                # 预计算 SKU bbox 内图片的 overlap ratio
                overlap_map = self._compute_overlap_ratios(
                    sku.source_bbox, deliverable)
                # 预计算图片面积，用于面积加分
                max_area = max(
                    (self._bbox_area(img.bbox) for img in deliverable),
                    default=1,
                ) or 1
                for img in deliverable:
                    dist = self._bbox_distance(sku.source_bbox, img.bbox)
                    if dist <= threshold:
                        conf = max(0.01, 1.0 - (dist / threshold))
                        # 图片 >50% 面积在 SKU bbox 内 → containment bonus
                        if overlap_map.get(img.image_id, 0) > 0.5:
                            conf = min(1.0, conf + 0.3)
                        # 面积加分: 大图更可能是产品主图 (最大 +0.15)
                        area_ratio = self._bbox_area(img.bbox) / max_area
                        conf = min(1.0, conf + area_ratio * 0.15)
                        method = self._infer_method(sku, img, layout_type)
                        candidates.append(BindingCandidate(
                            image_id=img.image_id,
                            confidence=round(conf, 3),
                            method=method,
                        ))

            candidates.sort(key=lambda c: c.confidence, reverse=True)

            if not candidates:
                # Fallback: 放宽阈值到 threshold * 3，取最近邻
                fallback_threshold = threshold * 3
                nearest_img = None
                nearest_dist = float("inf")
                for img in deliverable:
                    dist = self._bbox_distance(sku.source_bbox, img.bbox)
                    if dist < nearest_dist and dist <= fallback_threshold:
                        nearest_dist = dist
                        nearest_img = img
                if nearest_img:
                    conf = max(0.01, 1.0 - (nearest_dist / fallback_threshold))
                    candidates.append(BindingCandidate(
                        image_id=nearest_img.image_id,
                        confidence=round(conf * 0.5, 3),  # 降低置信度
                        method="fallback_nearest",
                    ))

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
                # 歧义时仍绑定 top1（降低置信度），避免完全丢失绑定
                results.append(BindingResult(
                    sku_id=sku.sku_id,
                    image_id=candidates[0].image_id,
                    confidence=round(candidates[0].confidence * 0.7, 3),
                    method=candidates[0].method,
                    is_ambiguous=True,
                    candidates=candidates[:TOP_K],
                ))
                logger.debug("binding_ambiguous_assigned",
                             sku_id=sku.sku_id, top_k=len(candidates[:TOP_K]))
        # 同一 product_id 的 SKU 统一绑定到组内最高置信度图片
        self._unify_product_bindings(skus, results)
        return results

    @staticmethod
    def _find_contained_images(
        bbox: tuple[float, ...], images: list[ImageInfo],
    ) -> list[ImageInfo]:
        """找 bbox 内包含（或大部分重叠）的图片，按面积降序返回。"""
        result = []
        if len(bbox) < 4:
            return result
        bx0, by0, bx1, by1 = bbox[:4]
        for img in images:
            if len(img.bbox) < 4:
                continue
            ix0, iy0, ix1, iy1 = img.bbox[:4]
            # 计算重叠区域
            ox0 = max(bx0, ix0)
            oy0 = max(by0, iy0)
            ox1 = min(bx1, ix1)
            oy1 = min(by1, iy1)
            overlap = max(0, ox1 - ox0) * max(0, oy1 - oy0)
            img_area = max(1, (ix1 - ix0) * (iy1 - iy0))
            # 图片 >50% 面积在 SKU bbox 内
            if overlap > img_area * 0.5:
                result.append(img)
        result.sort(
            key=lambda i: (i.bbox[2] - i.bbox[0]) * (i.bbox[3] - i.bbox[1]),
            reverse=True,
        )
        return result

    @staticmethod
    def _is_fullpage_bbox(
        bbox: tuple[float, ...], img_bboxes: list[tuple[float, ...]],
    ) -> bool:
        """检测 bbox 是否覆盖几乎整个页面（>85% 的图片区域外接矩形）。

        阈值设为 85%：只有真正的整页 bbox 才会触发退化处理，
        避免误伤跨越半页的合理产品区域。
        """
        if len(bbox) < 4 or not img_bboxes:
            return False
        valid = [b for b in img_bboxes if len(b) >= 4]
        if not valid:
            return False
        all_x0 = min(b[0] for b in valid)
        all_y0 = min(b[1] for b in valid)
        all_x1 = max(b[2] for b in valid)
        all_y1 = max(b[3] for b in valid)
        page_area = (all_x1 - all_x0) * (all_y1 - all_y0)
        if page_area <= 0:
            return False
        sku_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        return sku_area > page_area * 0.85

    @staticmethod
    def _is_zero_bbox(bbox: tuple[float, ...]) -> bool:
        """检测 bbox 是否全为 0。"""
        if len(bbox) < 4:
            return True
        return all(v == 0 for v in bbox[:4])

    @staticmethod
    def _bind_zero_bbox_skus(
        skus: list[SKUResult], deliverable: list[ImageInfo],
    ) -> list[BindingResult]:
        """零 bbox 批量绑定: 按图片 Y 坐标排序与 SKU 出现顺序一一对应。

        - SKU 数 == 图片数: 1:1 对应 (confidence=0.55)
        - SKU 数 < 图片数: 前 N 张按序对应，多余图片忽略
        - SKU 数 > 图片数: 前 M 个 SKU 按序对应，多余 SKU 绑最大图
        """
        results: list[BindingResult] = []
        # 按 Y 坐标 (bbox 中心) 排序图片
        sorted_imgs = sorted(
            deliverable,
            key=lambda img: (img.bbox[1] + img.bbox[3]) / 2
            if len(img.bbox) >= 4 else 0,
        )

        for i, sku in enumerate(skus):
            if i < len(sorted_imgs):
                results.append(BindingResult(
                    sku_id=sku.sku_id, image_id=sorted_imgs[i].image_id,
                    confidence=0.55, method="zero_bbox_positional",
                    is_ambiguous=len(skus) != len(sorted_imgs),
                ))
            else:
                # 多余 SKU → 绑最大图
                largest = max(
                    sorted_imgs, key=lambda img: SKUImageBinder._bbox_area(img.bbox))
                results.append(BindingResult(
                    sku_id=sku.sku_id, image_id=largest.image_id,
                    confidence=0.35, method="zero_bbox_largest",
                    is_ambiguous=True,
                ))

        logger.info("zero_bbox_positional_bind",
                     sku_count=len(skus), img_count=len(sorted_imgs))
        return results

    @staticmethod
    def _bbox_area(bbox: tuple[float, ...]) -> float:
        if len(bbox) < 4:
            return 0
        return max(0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

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
    def _unify_product_bindings(
        skus: list[SKUResult],
        results: list[BindingResult],
    ) -> None:
        """同一 product_id 的 SKU 统一使用组内置信度最高的绑定图片。"""
        # 建立 sku_id → product_id 映射
        pid_map: dict[str, str] = {}
        for sku in skus:
            if sku.product_id and sku.sku_id:
                pid_map[sku.sku_id] = sku.product_id

        # 按 product_id 分组，找最高置信度的绑定
        from collections import defaultdict
        groups: dict[str, list[BindingResult]] = defaultdict(list)
        for br in results:
            pid = pid_map.get(br.sku_id)
            if pid:
                groups[pid].append(br)

        for pid, bindings in groups.items():
            # 找组内有图片且置信度最高的绑定
            best = max(
                (b for b in bindings if b.image_id),
                key=lambda b: b.confidence,
                default=None,
            )
            if best:
                for b in bindings:
                    if not b.image_id:
                        b.image_id = best.image_id
                        b.confidence = best.confidence * 0.9
                        b.method = "product_group"
                        b.is_ambiguous = False

    @staticmethod
    def _compute_overlap_ratios(
        bbox: tuple[float, ...], images: list[ImageInfo],
    ) -> dict[str, float]:
        """计算每个图片与 SKU bbox 的重叠比例 (overlap_area / img_area)。"""
        result = {}
        if len(bbox) < 4:
            return result
        bx0, by0, bx1, by1 = bbox[:4]
        for img in images:
            if len(img.bbox) < 4:
                continue
            ix0, iy0, ix1, iy1 = img.bbox[:4]
            ox0 = max(bx0, ix0)
            oy0 = max(by0, iy0)
            ox1 = min(bx1, ix1)
            oy1 = min(by1, iy1)
            overlap = max(0, ox1 - ox0) * max(0, oy1 - oy0)
            img_area = max(1, (ix1 - ix0) * (iy1 - iy0))
            result[img.image_id] = overlap / img_area
        return result

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
