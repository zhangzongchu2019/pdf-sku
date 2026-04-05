"""页面级 SKU verify。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
from pdf_sku.pipeline.ir import SKUResult

from .models import DocumentHints

_parser = ResponseParser()

_VERIFY_PROMPT = """你是页面级商品候选核验器。

任务：
- 根据页面截图和当前候选商品列表，只做 keep / discard / merge 决策。
- 不允许新增商品，不允许补充页面中不存在的字段。
- 系统目标偏高召回：只有在“明显重复”或“明显不是商品”时才丢弃。

规则：
1. visual_only 候选可以保留，不要因为缺少文字就直接丢弃。
2. 如果两个候选明显是同一商品的重复拆分，可以 merge。
3. 如果候选明显是 logo、装饰、背景宣传块，可以 discard。
4. 不要修改字段值，只返回索引决策。

文档级弱提示：
{document_context}

候选商品：
{sku_json}

返回 ONLY JSON：
{{
  "discard_indexes": [2],
  "merge_groups": [[0, 3]]
}}"""


def _normalized_key(sku: SKUResult) -> tuple[str, str, str, str, str]:
    attrs = sku.attributes or {}
    return (
        str(attrs.get("product_name", "") or "").strip().lower(),
        str(attrs.get("model_number", "") or "").strip().lower(),
        str(attrs.get("price", "") or "").strip().lower(),
        str(attrs.get("specs", "") or "").strip().lower(),
        str(attrs.get("color", "") or "").strip().lower(),
    )


def _bbox_union(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    )


class PageVerifier:
    """页面级候选核验器。"""

    def __init__(self, llm_service=None) -> None:
        self._llm = llm_service

    def _dedupe_exact(self, skus: list[SKUResult]) -> list[SKUResult]:
        best_by_key: dict[tuple[str, str, str, str, str], SKUResult] = {}
        order: list[tuple[str, str, str, str, str]] = []
        for sku in skus:
            key = _normalized_key(sku)
            if key == ("", "", "", "", ""):
                order.append((str(id(sku)), "", "", "", ""))
                best_by_key[(str(id(sku)), "", "", "", "")] = sku
                continue
            if key not in best_by_key:
                best_by_key[key] = sku
                order.append(key)
                continue
            if sku.confidence > best_by_key[key].confidence:
                best_by_key[key] = sku
        return [best_by_key[key] for key in order if key in best_by_key]

    @staticmethod
    def _merge_group(skus: list[SKUResult], group: list[int]) -> SKUResult:
        base = deepcopy(skus[group[0]])
        for index in group[1:]:
            candidate = skus[index]
            for field, value in candidate.attributes.items():
                if value and not base.attributes.get(field):
                    base.attributes[field] = value
            base.source_bbox = _bbox_union(base.source_bbox, candidate.source_bbox)
            base.confidence = max(base.confidence, candidate.confidence)
        return base

    async def verify(
        self,
        skus: list[SKUResult],
        *,
        screenshot: bytes | None = None,
        document_hints: DocumentHints | None = None,
    ) -> list[SKUResult]:
        if not skus:
            return skus

        current = self._dedupe_exact(skus)
        if not self._llm or not screenshot or len(current) < 2:
            return current

        payload = [
            {
                "index": index,
                "attributes": sku.attributes,
                "bbox": [round(value, 1) for value in sku.source_bbox],
                "confidence": round(sku.confidence, 2),
            }
            for index, sku in enumerate(current)
        ]

        try:
            response = await self._llm._call_llm(
                operation="page_verify_v2",
                prompt=_VERIFY_PROMPT.format(
                    document_context=self._document_context(document_hints),
                    sku_json=payload,
                ),
                images=[screenshot],
            )
            parsed = _parser.parse(response.text, expected_type="object")
            if not parsed.success or not isinstance(parsed.data, dict):
                return current
            return self._apply_llm_decisions(current, parsed.data)
        except Exception:
            return current

    def _apply_llm_decisions(self, skus: list[SKUResult], payload: dict[str, Any]) -> list[SKUResult]:
        discard_indexes = {
            index for index in payload.get("discard_indexes", [])
            if isinstance(index, int) and 0 <= index < len(skus)
        }
        merge_groups = [
            [index for index in group if isinstance(index, int) and 0 <= index < len(skus)]
            for group in payload.get("merge_groups", [])
            if isinstance(group, list)
        ]
        merge_groups = [group for group in merge_groups if len(group) >= 2]

        consumed: set[int] = set()
        result: list[SKUResult] = []
        for group in merge_groups:
            if any(index in consumed for index in group):
                continue
            consumed.update(group)
            result.append(self._merge_group(skus, group))

        for index, sku in enumerate(skus):
            if index in consumed or index in discard_indexes:
                continue
            result.append(sku)

        return result or skus

    @staticmethod
    def _document_context(document_hints: DocumentHints | None) -> str:
        if not document_hints or not document_hints.has_hints():
            return "无额外文档级提示。"
        parts = []
        if document_hints.document_theme:
            parts.append(f"- document_theme: {document_hints.document_theme}")
        if document_hints.ignore_hints:
            parts.append(f"- ignore_hints: {', '.join(document_hints.ignore_hints)}")
        return "\n".join(parts)
