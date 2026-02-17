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

SINGLE_STAGE_PROMPT = """Extract ALL product SKUs from this PDF page.
For each product, extract: product_name, model_number, price, description, material, color, size.
Only extract clearly visible attributes.

Respond with ONLY a JSON array:
[{{"product_name": "...", "model_number": "...", "price": "...", "confidence": 0.8}}]"""


class SingleStageExtractor:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def extract(
        self,
        raw: ParsedPageIR,
        text_roles: list[str] | None = None,
        profile: dict | None = None,
    ) -> list[SKUResult]:
        """单阶段提取: 一次 LLM 调用获取所有 SKU。"""
        if not self._llm:
            return self._rule_extract(raw)

        try:
            resp = await self._llm._call_llm(
                operation="extract_sku_single",
                prompt=SINGLE_STAGE_PROMPT,
                images=None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for item in parsed.data:
                    if isinstance(item, dict):
                        attrs = {k: v for k, v in item.items()
                                 if k not in ("confidence",)}
                        results.append(SKUResult(
                            attributes=attrs,
                            validity="valid" if attrs.get("product_name") else "invalid",
                            confidence=float(item.get("confidence", 0.6)),
                            extraction_method="single_stage",
                        ))
                return results
        except Exception as e:
            logger.warning("single_stage_failed", error=str(e))

        return self._rule_extract(raw)

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
