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

BOUNDARY_PROMPT = """Identify SKU product boundaries in this PDF page.
For each product, return its bounding box coordinates and brief text content.

Respond with ONLY a JSON array:
[{{"boundary_id": 1, "bbox": [x0, y0, x1, y1], "text_content": "product name...", "confidence": 0.9}}]"""

ATTR_PROMPT = """Extract product attributes for each SKU boundary.
Required attributes: product_name, model_number, price, description, material, color, size, weight.
Only extract attributes that are clearly visible. Leave missing attributes as null.

Boundaries: {boundaries}

Respond with ONLY a JSON array:
[{{"boundary_id": 1, "attributes": {{"product_name": "...", "model_number": "...", "price": "..."}}}}]"""


class TwoStageExtractor:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def identify_boundaries(
        self,
        text_blocks: list[TextBlock],
        text_roles: list[str] | None,
        screenshot: bytes | None,
        profile: dict | None = None,
    ) -> list[SKUBoundary]:
        """阶段1: SKU 边界识别。"""
        if not self._llm:
            return self._rule_boundaries(text_blocks, text_roles)

        try:
            resp = await self._llm._call_llm(
                operation="identify_boundaries",
                prompt=BOUNDARY_PROMPT,
                images=[screenshot] if screenshot else None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                boundaries = []
                for item in parsed.data:
                    bbox = item.get("bbox", [0, 0, 0, 0])
                    boundaries.append(SKUBoundary(
                        boundary_id=item.get("boundary_id", len(boundaries) + 1),
                        bbox=tuple(bbox) if len(bbox) == 4 else (0, 0, 0, 0),
                        text_content=item.get("text_content", ""),
                        confidence=float(item.get("confidence", 0.5)),
                    ))
                return boundaries
        except Exception as e:
            logger.warning("boundary_identify_failed", error=str(e))

        return self._rule_boundaries(text_blocks, text_roles)

    async def extract_batch(
        self,
        boundaries: list[SKUBoundary],
        raw: ParsedPageIR,
        profile: dict | None = None,
    ) -> list[SKUResult]:
        """阶段2: 批量属性提取。"""
        if not boundaries:
            return []

        if not self._llm:
            return self._rule_extract(boundaries, raw)

        boundary_desc = [
            {"boundary_id": b.boundary_id, "text": b.text_content[:200]}
            for b in boundaries
        ]

        try:
            prompt = ATTR_PROMPT.format(boundaries=str(boundary_desc))
            resp = await self._llm._call_llm(
                operation="extract_sku_attrs",
                prompt=prompt,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for item in parsed.data:
                    bid = item.get("boundary_id", 0)
                    attrs = item.get("attributes", {})
                    boundary = next((b for b in boundaries if b.boundary_id == bid), None)
                    validity = "valid" if attrs.get("product_name") else "invalid"
                    results.append(SKUResult(
                        attributes=attrs,
                        source_bbox=boundary.bbox if boundary else (0, 0, 0, 0),
                        validity=validity,
                        confidence=float(item.get("confidence", 0.7)),
                        extraction_method="two_stage",
                    ))
                return results
        except Exception as e:
            logger.warning("attr_extract_failed", error=str(e))

        return self._rule_extract(boundaries, raw)

    def _rule_boundaries(
        self, text_blocks: list[TextBlock], text_roles: list[str] | None
    ) -> list[SKUBoundary]:
        """规则兜底: 基于文本块间距分组。"""
        if not text_blocks:
            return []
        boundaries = []
        current_group: list[TextBlock] = [text_blocks[0]]
        for i in range(1, len(text_blocks)):
            prev = text_blocks[i - 1]
            curr = text_blocks[i]
            gap = curr.bbox[1] - prev.bbox[3] if curr.bbox[1] > prev.bbox[3] else 0
            if gap > 30:  # 大于 30pt → 新 SKU 边界
                boundaries.append(self._group_to_boundary(current_group, len(boundaries) + 1))
                current_group = [curr]
            else:
                current_group.append(curr)
        if current_group:
            boundaries.append(self._group_to_boundary(current_group, len(boundaries) + 1))
        return boundaries

    @staticmethod
    def _group_to_boundary(blocks: list[TextBlock], bid: int) -> SKUBoundary:
        x0 = min(b.bbox[0] for b in blocks)
        y0 = min(b.bbox[1] for b in blocks)
        x1 = max(b.bbox[2] for b in blocks)
        y1 = max(b.bbox[3] for b in blocks)
        text = " ".join(b.content for b in blocks)
        return SKUBoundary(boundary_id=bid, bbox=(x0, y0, x1, y1), text_content=text[:300])

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
