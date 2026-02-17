"""
页面分类器 (LLM)。对齐: Pipeline 详设 §5.2 Phase 5

分类:
- A: 结构化表格页 (规则引擎可处理)
- B: 混合页 (文字+图片, 需 LLM 提取)
- C: 图片为主 (需图片分类)
- D: 空白/目录/封面 (跳过)
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import ClassifyResult, FeatureVector
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
import structlog

logger = structlog.get_logger()
_parser = ResponseParser()


class PageClassifier:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def classify(
        self,
        screenshot: bytes,
        features: FeatureVector,
        raw_text: str = "",
    ) -> ClassifyResult:
        """页面分类: 优先规则判断, 低信心时 LLM 补充。"""
        # 规则快速路径
        rule_result = self._rule_classify(features, raw_text)
        if rule_result and rule_result.confidence >= 0.85:
            return rule_result

        # LLM 分类
        if self._llm:
            try:
                resp = await self._llm._call_llm(
                    operation="classify_page",
                    prompt=f"Classify this PDF page. Features: {features.to_prompt_context()}",
                    images=[screenshot] if screenshot else None,
                    timeout=30.0,
                )
                parsed = _parser.parse(resp.text, expected_type="object")
                if parsed.success and isinstance(parsed.data, dict):
                    return ClassifyResult(
                        page_type=parsed.data.get("page_type", "B"),
                        layout_type=parsed.data.get("layout_type", "freeform"),
                        confidence=float(parsed.data.get("confidence", 0.7)),
                        raw_response=resp.text,
                    )
            except Exception as e:
                logger.warning("llm_classify_failed", error=str(e))

        # Fallback: 使用规则结果或默认
        return rule_result or ClassifyResult(page_type="B", confidence=0.5)

    def _rule_classify(self, features: FeatureVector, raw_text: str) -> ClassifyResult | None:
        """基于特征的规则分类。"""
        # A: 表格主导 (优先于空白页检测，有表格就不算空白)
        if features.table_count > 0 and features.table_area_ratio > 0.3:
            return ClassifyResult(page_type="A", layout_type="table", confidence=0.88)

        # D: 空白页
        if features.text_block_count == 0 and features.image_count == 0 and features.table_count == 0:
            return ClassifyResult(page_type="D", layout_type="freeform", confidence=0.95)

        # D: 目录页
        toc_kw = {"目录", "contents", "table of contents", "index"}
        if features.image_count == 0 and any(kw in raw_text.lower() for kw in toc_kw):
            return ClassifyResult(page_type="D", layout_type="freeform", confidence=0.90)

        # C: 图片为主
        if features.image_count >= 3 and features.text_block_count < 5:
            return ClassifyResult(page_type="C", layout_type="grid", confidence=0.80)

        # B: 混合 (低信心, 需 LLM)
        if features.has_price_pattern or features.has_model_pattern:
            return ClassifyResult(page_type="B", layout_type="freeform", confidence=0.70)

        return None  # 规则无法判断
