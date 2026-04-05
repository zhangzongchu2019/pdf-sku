"""区域提议的可选 VLM 修正层。"""
from __future__ import annotations

from typing import Any

from pdf_sku.llm_adapter.parser.response_parser import ResponseParser

from .models import DocumentHints, PageEvidence, RegionProposal

_parser = ResponseParser()

_REGION_REFINE_PROMPT = """你是 PDF 页面中的“商品单元区域修正器”。

任务：
- 根据页面截图、原子对象列表、当前启发式区域提议，修正商品区域分组。
- 你只能做“分组修正”，不能提取属性，不能命名商品，不能补充不存在的对象。

规则：
1. 一个 region 默认对应一个商品单元。
2. 你可以合并多个启发式区域，也可以把一个粗区域拆成多个 region。
3. 明显无关的 logo、banner、背景装饰、非商品宣传物可以忽略。
4. 如果只有一个商品描述，附近多张图很可能属于同一商品。
5. 如果没有文字，也可以只按图片分成多个 visual 区域。
6. 只返回 object_id 分组，不返回坐标，不解释长篇原因。

文档级弱提示：
{document_context}

页面对象：
{objects_json}

当前启发式区域：
{regions_json}

返回 ONLY JSON:
{{
  "regions": [
    {{
      "member_object_ids": ["text_0", "image_1"],
      "score": 0.86,
      "reason": "brief"
    }}
  ],
  "ignored_object_ids": ["text_9"]
}}"""


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return (0, 0, 0, 0)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _serialize_objects(evidence: PageEvidence) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for obj in evidence.objects[:80]:
        item = {
            "object_id": obj.object_id,
            "object_type": obj.object_type,
            "bbox": [round(value, 1) for value in obj.bbox],
        }
        if obj.text:
            item["text"] = obj.text[:120]
        if obj.label:
            item["label"] = obj.label
        items.append(item)
    return items


def _serialize_regions(proposals: list[RegionProposal]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for proposal in proposals[:20]:
        items.append(
            {
                "region_id": proposal.region_id,
                "member_object_ids": proposal.member_object_ids[:20],
                "score": round(proposal.score, 2),
                "reason": proposal.reason,
            }
        )
    return items


class RegionRefiner:
    """基于 VLM 的有限区域修正。"""

    def __init__(self, llm_service=None) -> None:
        self._llm = llm_service

    async def refine(
        self,
        evidence: PageEvidence,
        proposals: list[RegionProposal],
        *,
        screenshot: bytes | None = None,
        document_hints: DocumentHints | None = None,
    ) -> list[RegionProposal]:
        if not self._llm or not screenshot or not proposals:
            return proposals

        try:
            prompt = _REGION_REFINE_PROMPT.format(
                document_context=self._document_context(document_hints),
                objects_json=_serialize_objects(evidence),
                regions_json=_serialize_regions(proposals),
            )
            response = await self._llm._call_llm(
                operation="region_refine_v2",
                prompt=prompt,
                images=[screenshot],
            )
            parsed = _parser.parse(response.text, expected_type="object")
            if not parsed.success or not isinstance(parsed.data, dict):
                return proposals
            return self._apply_response(evidence, proposals, parsed.data)
        except Exception:
            return proposals

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

    def _apply_response(
        self,
        evidence: PageEvidence,
        proposals: list[RegionProposal],
        payload: dict[str, Any],
    ) -> list[RegionProposal]:
        valid_object_ids = {obj.object_id for obj in evidence.objects}
        object_bbox = {obj.object_id: obj.bbox for obj in evidence.objects}
        ignored_object_ids = {
            object_id
            for object_id in payload.get("ignored_object_ids", [])
            if object_id in valid_object_ids
        }

        refined: list[RegionProposal] = []
        assigned_ids: set[str] = set()
        for index, item in enumerate(payload.get("regions", []), start=1):
            if not isinstance(item, dict):
                continue
            members = []
            for object_id in item.get("member_object_ids", []):
                if object_id in valid_object_ids and object_id not in ignored_object_ids and object_id not in assigned_ids:
                    members.append(object_id)
            if not members:
                continue
            assigned_ids.update(members)
            refined.append(
                RegionProposal(
                    region_id=f"vlm_region_{index}",
                    bbox=_bbox_union([object_bbox[member] for member in members]),
                    region_type="product_unit",
                    proposal_source="vlm_refined",
                    score=float(item.get("score", 0.75)),
                    member_object_ids=members,
                    reason=str(item.get("reason", "vlm_refined"))[:120],
                )
            )

        if not refined:
            return proposals

        # 保留 VLM 未覆盖的原始区域，避免无故丢失候选。
        for proposal in proposals:
            leftover = [
                object_id for object_id in proposal.member_object_ids
                if object_id in valid_object_ids
                and object_id not in ignored_object_ids
                and object_id not in assigned_ids
            ]
            if not leftover:
                continue
            refined.append(
                RegionProposal(
                    region_id=f"{proposal.region_id}_leftover",
                    bbox=_bbox_union([object_bbox[member] for member in leftover]),
                    region_type=proposal.region_type,
                    proposal_source=proposal.proposal_source,
                    score=proposal.score,
                    member_object_ids=leftover,
                    reason=f"{proposal.reason}_leftover",
                )
            )

        return refined[:24]
