"""
单阶段 SKU 提取 (Fallback)。对齐: Pipeline 详设 §5.2

两阶段失败/无效率高时回退到单阶段。
单 LLM 调用: 一次性提取所有 SKU + 属性。
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import ParsedPageIR, SKUResult
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
import structlog

logger = structlog.get_logger()
_parser = ResponseParser()

SINGLE_STAGE_PROMPT = """Extract ALL products and their SKU variants from this PDF page.
Each product may have multiple SKU variants.

IMPORTANT rules for variant splitting:
- ONLY split into multiple SKUs when the text explicitly lists multiple sizes/dimensions (e.g. "规格-1500/1800/2000mm" → 3 SKUs).
- Material and color lines (e.g. "材质-进口橡木 颜色-板栗色/宝马灰") describe the ENTIRE product series, NOT individual variants. Put them in "common_attrs".
- Do NOT create separate SKUs for different colors or materials.

For each product extract: product_name, model_number, price, material, color, size, weight, description.
Put series-shared attributes (material, color) in "common_attrs". Put variant-specific attributes (size) in each SKU entry.

Page text content for reference:
{page_text}

Respond with ONLY a JSON array:
[{{
  "product_name": "858B# Sofa",
  "model_number": "858B",
  "common_attrs": {{"material": "imported oak", "color": "chestnut/grey"}},
  "skus": [
    {{"variant_label": "single seat", "size": "850*900*950mm"}},
    {{"variant_label": "double seat", "size": "1400*900*950mm"}}
  ]
}}]"""


class SingleStageExtractor:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def extract(
        self,
        raw: ParsedPageIR,
        text_roles: list[str] | None = None,
        profile: dict | None = None,
        screenshot: bytes | None = None,
    ) -> list[SKUResult]:
        """单阶段提取: 一次 LLM 调用获取所有 SKU。"""
        if not self._llm:
            return self._rule_extract(raw)

        try:
            page_text = raw.raw_text[:2000] if raw.raw_text else ""
            prompt = SINGLE_STAGE_PROMPT.format(page_text=page_text)
            resp = await self._llm._call_llm(
                operation="extract_sku_single",
                prompt=prompt,
                images=[screenshot] if screenshot else None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for p_idx, item in enumerate(parsed.data):
                    if not isinstance(item, dict):
                        continue
                    results.extend(self._parse_product_item(item, p_idx))
                return results
        except Exception as e:
            logger.warning("single_stage_failed", error=str(e))

        return self._rule_extract(raw)

    @staticmethod
    def _parse_product_item(item: dict, p_idx: int) -> list[SKUResult]:
        """解析单个产品项，支持新格式（products/skus）和旧格式（扁平）。"""
        results = []

        if "skus" in item:
            # 新格式: 带变体
            product_name = item.get("product_name", "")
            model_number = item.get("model_number", "")
            common_attrs = item.get("common_attrs", {})
            temp_product_id = f"S_P{p_idx + 1}"

            for sku_data in item["skus"]:
                if not isinstance(sku_data, dict):
                    continue
                attrs = {}
                if product_name:
                    attrs["product_name"] = product_name
                if model_number:
                    attrs["model_number"] = model_number
                attrs.update(common_attrs)
                variant_label = sku_data.pop("variant_label", "")
                attrs.update(sku_data)

                results.append(SKUResult(
                    attributes=attrs,
                    validity="valid" if attrs.get("product_name") else "invalid",
                    confidence=0.6,
                    extraction_method="single_stage",
                    product_id=temp_product_id,
                    variant_label=variant_label,
                ))
        else:
            # 旧格式: 扁平
            attrs = {k: v for k, v in item.items()
                     if k not in ("confidence",)}
            results.append(SKUResult(
                attributes=attrs,
                validity="valid" if attrs.get("product_name") else "invalid",
                confidence=float(item.get("confidence", 0.6)),
                extraction_method="single_stage",
            ))

        return results

    def _rule_extract(self, raw: ParsedPageIR) -> list[SKUResult]:
        """最后规则兜底 (从表格提取)。"""
        results = []
        for table in raw.tables:
            if not table.rows or len(table.rows) < 2:
                continue
            headers = [h.lower().strip() for h in table.rows[0]]
            for row in table.rows[1:]:
                attrs = {}
                for i, cell in enumerate(row):
                    if i < len(headers) and cell:
                        attrs[headers[i]] = cell
                if attrs:
                    results.append(SKUResult(
                        attributes=attrs,
                        validity="valid" if any(attrs.values()) else "invalid",
                        confidence=0.4,
                        extraction_method="single_stage_rule",
                    ))
        return results
