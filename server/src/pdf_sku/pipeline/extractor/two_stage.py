"""
两阶段 SKU 提取。对齐: Pipeline 详设 §5.2 Phase 6

阶段1: SKU 边界识别 (identify_boundaries)
阶段2: SKU 属性提取 (extract_batch)
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import (
    ParsedPageIR, SKUBoundary, SKUResult, TextBlock,
)
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
import structlog

logger = structlog.get_logger()
_parser = ResponseParser()

BOUNDARY_PROMPT_TEMPLATE = """Identify ALL product boundaries in this PDF catalog page image.
The image dimensions are {img_w} x {img_h} pixels.

IMPORTANT: Scene/room photos often contain MULTIPLE products (e.g. a bedroom photo may show a bed, bedside tables, wardrobe, and dresser). Each distinct product must have its own boundary, even if it appears small or in the background.

For each product, return its bounding box coordinates in pixel units (0 to {img_w} for x, 0 to {img_h} for y).
The bbox uses the top-left origin: [x0, y0, x1, y1] where (x0,y0) is the top-left and (x1,y1) is the bottom-right of the product region.

Respond with ONLY a JSON array:
[{{"boundary_id": 1, "bbox": [x0, y0, x1, y1], "text_content": "product name...", "confidence": 0.9}}]"""

ATTR_PROMPT = """Extract products and their SKU variants for each boundary region.
Each boundary may contain one or more products. Each product may have multiple SKU variants.

IMPORTANT rules for variant splitting:
- ONLY split into multiple SKUs when the text explicitly lists multiple sizes/dimensions (e.g. "规格-1500/1800/2000mm" → 3 SKUs).
- Material and color lines (e.g. "材质-进口橡木 颜色-板栗色/宝马灰") describe the ENTIRE product series, NOT individual variants. Put them in "common_attrs".
- Do NOT create separate SKUs for different colors or materials.
- IMPORTANT: When the page lists N size variants (e.g. "1人位/2人位/3人位" with different dimensions), you MUST create exactly N SKUs — do NOT skip any variant.

Extract these attributes where visible: product_name, model_number, price, material, color, size, weight, description.
Put series-shared attributes (material, color) in "common_attrs". Put variant-specific attributes (size) in each SKU entry.

Raw OCR text from the page (authoritative — use this to ensure ALL size variants are captured):
{raw_text}

Boundaries: {boundaries}

Respond with ONLY a JSON array:
[{{
  "boundary_id": 1,
  "products": [
    {{
      "product_name": "858B# Sofa",
      "model_number": "858B",
      "common_attrs": {{"material": "imported oak", "color": "chestnut/grey"}},
      "skus": [
        {{"variant_label": "single seat", "size": "850*900*950mm"}},
        {{"variant_label": "double seat", "size": "1400*900*950mm"}}
      ]
    }}
  ]
}}]"""


def _compute_iou(bbox1: tuple, bbox2: tuple) -> float:
    """计算两个 bbox 的 IoU。"""
    x0 = max(bbox1[0], bbox2[0])
    y0 = max(bbox1[1], bbox2[1])
    x1 = min(bbox1[2], bbox2[2])
    y1 = min(bbox1[3], bbox2[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area1 = max(0, bbox1[2] - bbox1[0]) * max(0, bbox1[3] - bbox1[1])
    area2 = max(0, bbox2[2] - bbox2[0]) * max(0, bbox2[3] - bbox2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


class TwoStageExtractor:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def identify_boundaries(
        self,
        text_blocks: list[TextBlock],
        text_roles: list[str] | None,
        screenshot: bytes | None,
        profile: dict | None = None,
        image_size: tuple[int, int] | None = None,
        images: list | None = None,
    ) -> list[SKUBoundary]:
        """阶段1: SKU 边界识别。"""
        if not self._llm:
            return self._rule_boundaries(text_blocks, text_roles, images=images)

        # 获取截图实际尺寸
        img_w, img_h = image_size or (0, 0)
        if (not img_w or not img_h) and screenshot:
            img_w, img_h = self._get_image_size(screenshot)

        try:
            prompt = BOUNDARY_PROMPT_TEMPLATE.format(
                img_w=img_w or "unknown",
                img_h=img_h or "unknown",
            )
            resp = await self._llm.call_llm(
                operation="identify_boundaries",
                prompt=prompt,
                images=[screenshot] if screenshot else None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                boundaries = []
                for item in parsed.data:
                    bbox = item.get("bbox", [0, 0, 0, 0])
                    if len(bbox) == 4:
                        bbox = self._normalize_bbox(
                            bbox, img_w, img_h)
                    boundaries.append(SKUBoundary(
                        boundary_id=item.get("boundary_id", len(boundaries) + 1),
                        bbox=tuple(bbox) if len(bbox) == 4 else (0, 0, 0, 0),
                        text_content=item.get("text_content", ""),
                        confidence=float(item.get("confidence", 0.5)),
                    ))
                boundaries = self._nms_boundaries(boundaries)
                boundaries = self._penalize_fullpage_boundaries(
                    boundaries, img_w, img_h)
                return boundaries
        except Exception as e:
            logger.warning("boundary_identify_failed", error=str(e))

        return self._rule_boundaries(text_blocks, text_roles, images=images)

    async def extract_batch(
        self,
        boundaries: list[SKUBoundary],
        raw: ParsedPageIR,
        profile: dict | None = None,
        screenshot: bytes | None = None,
    ) -> list[SKUResult]:
        """阶段2: 批量属性提取。"""
        if not boundaries:
            return []

        if not self._llm:
            return self._rule_extract(boundaries, raw)

        boundary_desc = [
            {"boundary_id": b.boundary_id, "text": b.text_content[:1000]}
            for b in boundaries
        ]

        # 从 pdfplumber 提取的原始文本块（比 LLM 生成的 text_content 更完整准确）
        raw_text_lines = []
        for tb in (raw.text_blocks or []):
            t = getattr(tb, "text", "") or ""
            if t.strip():
                raw_text_lines.append(t.strip())
        raw_text = "\n".join(raw_text_lines)[:2000] if raw_text_lines else "(none)"

        try:
            prompt = ATTR_PROMPT.format(
                boundaries=str(boundary_desc),
                raw_text=raw_text,
            )
            resp = await self._llm.call_llm(
                operation="extract_sku_attrs",
                prompt=prompt,
                images=[screenshot] if screenshot else None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for item in parsed.data:
                    bid = item.get("boundary_id", 0)
                    boundary = next((b for b in boundaries if b.boundary_id == bid), None)
                    bbox = boundary.bbox if boundary else (0, 0, 0, 0)

                    if "products" in item:
                        # 新格式: 产品分组
                        results.extend(self._parse_products(
                            item["products"], bid, bbox))
                    else:
                        # 旧格式: 向后兼容
                        attrs = item.get("attributes", {})
                        validity = "valid" if attrs.get("product_name") else "invalid"
                        results.append(SKUResult(
                            attributes=attrs,
                            source_bbox=bbox,
                            validity=validity,
                            confidence=float(item.get("confidence", 0.7)),
                            extraction_method="two_stage",
                        ))
                return results
        except Exception as e:
            logger.warning("attr_extract_failed", error=str(e))

        return self._rule_extract(boundaries, raw)

    @staticmethod
    def _parse_products(
        products: list[dict],
        boundary_id: int,
        bbox: tuple,
    ) -> list[SKUResult]:
        """解析产品分组格式，每个 SKU 变体生成一个 SKUResult。"""
        results = []
        for p_idx, product in enumerate(products):
            product_name = product.get("product_name", "")
            model_number = product.get("model_number", "")
            common_attrs = product.get("common_attrs", {})
            temp_product_id = f"B{boundary_id}_P{p_idx + 1}"

            skus_data = product.get("skus", [])
            if not skus_data:
                # 无变体时整个产品作为一个 SKU
                skus_data = [{}]

            for sku_data in skus_data:
                attrs = {}
                if product_name:
                    attrs["product_name"] = product_name
                if model_number:
                    attrs["model_number"] = model_number
                # 合并 common_attrs
                attrs.update(common_attrs)
                # 合并变体特有属性（覆盖 common）
                variant_label = sku_data.pop("variant_label", "") if isinstance(sku_data, dict) else ""
                if isinstance(sku_data, dict):
                    attrs.update(sku_data)

                validity = "valid" if attrs.get("product_name") else "invalid"
                results.append(SKUResult(
                    attributes=attrs,
                    source_bbox=bbox,
                    validity=validity,
                    confidence=0.7,
                    extraction_method="two_stage",
                    product_id=temp_product_id,
                    variant_label=variant_label,
                ))
        return results

    @staticmethod
    def _nms_boundaries(
        boundaries: list[SKUBoundary], iou_threshold: float = 0.5,
    ) -> list[SKUBoundary]:
        """IoU > threshold 的 boundary 保留 confidence 更高的。"""
        sorted_b = sorted(boundaries, key=lambda b: b.confidence, reverse=True)
        keep: list[SKUBoundary] = []
        for b in sorted_b:
            if not any(_compute_iou(b.bbox, k.bbox) > iou_threshold for k in keep):
                keep.append(b)
        for i, b in enumerate(keep):
            b.boundary_id = i + 1
        return keep

    @staticmethod
    def _penalize_fullpage_boundaries(
        boundaries: list[SKUBoundary],
        img_w: int, img_h: int,
    ) -> list[SKUBoundary]:
        """覆盖 >80% 页面的 boundary 降低 confidence。"""
        page_area = img_w * img_h
        if page_area <= 0:
            return boundaries
        for b in boundaries:
            b_area = (b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1])
            if b_area > page_area * 0.8:
                b.confidence = min(b.confidence, 0.3)
        return boundaries

    @staticmethod
    def _get_image_size(data: bytes) -> tuple[int, int]:
        """从 PNG 头部读取图片尺寸（不依赖 PIL）。"""
        # PNG: bytes 16-23 contain width (4 bytes) and height (4 bytes) in IHDR
        if data[:4] == b'\x89PNG' and len(data) >= 24:
            import struct
            w, h = struct.unpack('>II', data[16:24])
            return w, h
        return 0, 0

    @staticmethod
    def _normalize_bbox(
        bbox: list, img_w: int, img_h: int,
    ) -> list:
        """
        将 VLM 返回的 bbox 归一化到实际图片像素坐标。
        VLM 可能在内部缩放了图片，导致返回的坐标比实际像素偏小。
        通过检测 bbox 范围 vs 图片尺寸的比例来推断并修正。
        """
        if not img_w or not img_h:
            return bbox

        x0, y0, x1, y1 = bbox
        max_coord = max(x1, y1)

        # 如果坐标已经接近或超过图片尺寸，说明已在正确空间
        if max_coord >= min(img_w, img_h) * 0.8:
            return bbox

        # VLM 可能将长边缩放到某个固定值，推断缩放因子
        # 使用较大的维度比来估算（更保守）
        if x1 > 0 and y1 > 0:
            # 假设 VLM 等比缩放，用长边比来推断
            # 检测 VLM 的等效长边 = max(所有 bbox 坐标的理论最大值)
            # 由于单次调用无法看到全局 max，用当前 bbox 估算
            scale_x = img_w / max(x1, 1)
            scale_y = img_h / max(y1, 1)
            # 等比缩放时 scale_x ≈ scale_y，取较小值保守估计
            s = min(scale_x, scale_y)
            if s > 1.1:  # 只在明显缩放时修正
                return [x0 * s, y0 * s, x1 * s, y1 * s]

        return bbox

    def _rule_boundaries(
        self,
        text_blocks: list[TextBlock],
        text_roles: list[str] | None,
        images: list | None = None,
    ) -> list[SKUBoundary]:
        """规则兜底: 优先用图片锚点聚类，否则 Y-gap 分组。"""
        if not text_blocks:
            return []

        # 筛选锚点图片: search_eligible 且非重复
        anchors = [
            img for img in (images or [])
            if getattr(img, "search_eligible", False)
            and not getattr(img, "is_duplicate", False)
        ]

        if len(anchors) >= 2:
            result = self._image_anchor_boundaries(text_blocks, anchors)
            if result:
                return result

        # 退回 Y-gap 法
        return self._ygap_boundaries(text_blocks)

    def _ygap_boundaries(self, text_blocks: list[TextBlock]) -> list[SKUBoundary]:
        """Y 轴间距分组（原始 fallback）。

        当结果只有 1 个 boundary 且文本较长时，尝试按型号模式二次切分。
        """
        boundaries: list[SKUBoundary] = []
        current_group: list[TextBlock] = [text_blocks[0]]
        for i in range(1, len(text_blocks)):
            prev = text_blocks[i - 1]
            curr = text_blocks[i]
            gap = curr.bbox[1] - prev.bbox[3] if curr.bbox[1] > prev.bbox[3] else 0
            if gap > 30:
                boundaries.append(self._group_to_boundary(current_group, len(boundaries) + 1))
                current_group = [curr]
            else:
                current_group.append(curr)
        if current_group:
            boundaries.append(self._group_to_boundary(current_group, len(boundaries) + 1))

        # 若仅 1 个 boundary 且文本较长，尝试按型号模式切分
        if len(boundaries) == 1 and len(boundaries[0].text_content) > 100:
            split = self._split_by_model_pattern(boundaries[0])
            if len(split) > 1:
                return split

        return boundaries

    @staticmethod
    def _split_by_model_pattern(boundary: SKUBoundary) -> list[SKUBoundary]:
        """按型号模式（如 886#、858B#）切分单个 boundary 为多个产品区域。"""
        import re
        text = boundary.text_content
        # 匹配型号+# 模式: 886#, 858B#, 09# 等（字母数字混合+#）
        # 在行首或换行后、或前有空白/换行时切分
        pattern = re.compile(r'(?:^|(?<=\n)|(?<=\s))(?=[A-Za-z0-9]*\d[A-Za-z0-9]*[#＃])')
        splits = list(pattern.finditer(text))
        if len(splits) < 2:
            return [boundary]

        results = []
        for idx, match in enumerate(splits):
            start = match.end()  # skip the newline itself
            end = splits[idx + 1].start() if idx + 1 < len(splits) else len(text)
            segment = text[start:end].strip()
            if segment:
                results.append(SKUBoundary(
                    boundary_id=len(results) + 1,
                    bbox=boundary.bbox,
                    text_content=segment[:2000],
                ))
        return results if results else [boundary]

    @staticmethod
    def _image_anchor_boundaries(
        text_blocks: list[TextBlock],
        anchors: list,
    ) -> list[SKUBoundary]:
        """
        图片锚点聚类: 将文字块归属到最近的图片区域。

        亲和度规则:
        - 图片正下方的文字优先（X 轴重叠 + Y 在图片下方）
        - 其次按中心距离
        距离所有图片过远的孤儿文字单独 Y-gap 分组。
        """
        import math

        ORPHAN_THRESHOLD = 300  # pt

        # 图片中心和 bbox
        anchor_cx = [(a.bbox[0] + a.bbox[2]) / 2 for a in anchors]
        anchor_cy = [(a.bbox[1] + a.bbox[3]) / 2 for a in anchors]

        # 按锚点分组: index → list of TextBlock
        groups: dict[int, list[TextBlock]] = {i: [] for i in range(len(anchors))}
        orphans: list[TextBlock] = []

        for tb in text_blocks:
            tb_cx = (tb.bbox[0] + tb.bbox[2]) / 2
            tb_cy = (tb.bbox[1] + tb.bbox[3]) / 2

            best_idx = -1
            best_score = float("inf")

            for i, anchor in enumerate(anchors):
                ax0, ay0, ax1, ay1 = anchor.bbox
                # 计算亲和度（越小越好）
                dist = math.sqrt((tb_cx - anchor_cx[i]) ** 2 + (tb_cy - anchor_cy[i]) ** 2)

                # 正下方加分: 文字顶部在图片底部附近/以下 且 X 轴有重叠
                x_overlap = max(0, min(tb.bbox[2], ax1) - max(tb.bbox[0], ax0))
                x_span = max(1, tb.bbox[2] - tb.bbox[0])
                overlap_ratio = x_overlap / x_span

                score = dist
                if overlap_ratio > 0.3 and tb.bbox[1] >= ay0:
                    # 正下方: 大幅降低分值（优先归属）
                    score = dist * 0.3

                if score < best_score:
                    best_score = score
                    best_idx = i

            if best_score > ORPHAN_THRESHOLD:
                orphans.append(tb)
            else:
                groups[best_idx].append(tb)

        # 构建 boundaries
        boundaries: list[SKUBoundary] = []
        for i, anchor in enumerate(anchors):
            blocks = groups[i]
            if not blocks:
                continue
            # 合并图片 bbox 与文字 bbox
            all_x0 = min(anchor.bbox[0], min(b.bbox[0] for b in blocks))
            all_y0 = min(anchor.bbox[1], min(b.bbox[1] for b in blocks))
            all_x1 = max(anchor.bbox[2], max(b.bbox[2] for b in blocks))
            all_y1 = max(anchor.bbox[3], max(b.bbox[3] for b in blocks))
            text = " ".join(b.content for b in blocks)
            boundaries.append(SKUBoundary(
                boundary_id=len(boundaries) + 1,
                bbox=(all_x0, all_y0, all_x1, all_y1),
                text_content=text[:2000],
            ))

        # 孤儿文字用 Y-gap 法
        if orphans:
            orphans.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
            current_group: list[TextBlock] = [orphans[0]]
            for j in range(1, len(orphans)):
                prev = orphans[j - 1]
                curr = orphans[j]
                gap = curr.bbox[1] - prev.bbox[3] if curr.bbox[1] > prev.bbox[3] else 0
                if gap > 30:
                    boundaries.append(TwoStageExtractor._group_to_boundary(
                        current_group, len(boundaries) + 1))
                    current_group = [curr]
                else:
                    current_group.append(curr)
            if current_group:
                boundaries.append(TwoStageExtractor._group_to_boundary(
                    current_group, len(boundaries) + 1))

        return boundaries

    @staticmethod
    def _group_to_boundary(blocks: list[TextBlock], bid: int) -> SKUBoundary:
        x0 = min(b.bbox[0] for b in blocks)
        y0 = min(b.bbox[1] for b in blocks)
        x1 = max(b.bbox[2] for b in blocks)
        y1 = max(b.bbox[3] for b in blocks)
        text = " ".join(b.content for b in blocks)
        return SKUBoundary(boundary_id=bid, bbox=(x0, y0, x1, y1), text_content=text[:2000])

    def _rule_extract(self, boundaries: list[SKUBoundary], raw: ParsedPageIR) -> list[SKUResult]:
        """规则兜底: 从文本内容提取基本属性。"""
        import re
        results = []
        for b in boundaries:
            attrs: dict = {}
            text = b.text_content
            if text:
                attrs["product_name"] = text[:100]
            price_match = re.search(r'[\$¥€£]\s*([\d,.]+)', text)
            if price_match:
                attrs["price"] = price_match.group(0)
            model_match = re.search(r'[A-Z]{1,5}[-\s]?\d{2,10}', text)
            if model_match:
                attrs["model_number"] = model_match.group(0)
            results.append(SKUResult(
                attributes=attrs,
                source_bbox=b.bbox,
                validity="valid" if attrs.get("product_name") else "invalid",
                confidence=0.5,
                extraction_method="two_stage_rule",
            ))
        return results
