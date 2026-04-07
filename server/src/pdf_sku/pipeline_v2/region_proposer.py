"""普通页区域提议。"""
from __future__ import annotations

import math
import re

from pdf_sku.pipeline.ir import ImageInfo, ParsedPageIR
from pdf_sku.pipeline.layout_detector import _FIGURE_LABELS, LayoutRegion
from pdf_sku.pipeline.parser.ocr_engine import OcrBlock

from .models import EvidenceObject, PageEvidence, RegionProposal

_PAGE_MARKER_RE = re.compile(r"^(?:P|PG|PAGE|AGE)\s*[/\\-]?\s*0*\d+\s*$", re.IGNORECASE)


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return (0, 0, 0, 0)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _distance(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return math.hypot(ax - bx, ay - by)


def _is_textual_object(obj: EvidenceObject) -> bool:
    return obj.object_type in {"text_block", "ocr_block"}


def _is_page_marker_text(text: str) -> bool:
    normalized = re.sub(r"\s+", "", (text or "").strip()).upper()
    return bool(_PAGE_MARKER_RE.fullmatch(normalized))


def _is_figure_layout(obj: EvidenceObject) -> bool:
    return obj.object_type == "layout_block" and obj.label in _FIGURE_LABELS


def _is_visual_candidate(
    image: ImageInfo,
    *,
    page_width: float,
    page_height: float,
    min_area_ratio: float,
) -> bool:
    if image.is_fragmented:
        return False
    if image.bbox == (0, 0, 0, 0):
        return bool(image.search_eligible)
    page_area = max(1.0, page_width * page_height)
    area = max(0.0, image.bbox[2] - image.bbox[0]) * max(0.0, image.bbox[3] - image.bbox[1])
    return area / page_area >= min_area_ratio or bool(image.search_eligible)


def _build_text_groups(text_blocks: list[EvidenceObject], page_width: float) -> list[list[EvidenceObject]]:
    if not text_blocks:
        return []

    ordered = sorted(text_blocks, key=lambda obj: (obj.bbox[1], obj.bbox[0]))
    gap_y = 28.0
    max_x_shift = max(60.0, page_width * 0.18)

    groups: list[list[EvidenceObject]] = [[ordered[0]]]
    group_bbox = ordered[0].bbox
    for block in ordered[1:]:
        vertical_gap = block.bbox[1] - group_bbox[3]
        x_shift = abs(block.bbox[0] - group_bbox[0])
        if vertical_gap <= gap_y and x_shift <= max_x_shift:
            groups[-1].append(block)
            group_bbox = _bbox_union([group_bbox, block.bbox])
        else:
            groups.append([block])
            group_bbox = block.bbox
    return groups


class RegionProposer:
    """生成高召回区域提议。"""

    def __init__(self, *, min_visual_only_area_ratio: float = 0.003) -> None:
        self._min_visual_only_area_ratio = min_visual_only_area_ratio

    @staticmethod
    def _pixel_bbox_to_page(
        bbox: tuple[float, float, float, float],
        *,
        page_width: float,
        page_height: float,
        screenshot_size: tuple[int, int] | None,
    ) -> tuple[float, float, float, float]:
        if not screenshot_size or screenshot_size[0] <= 0 or screenshot_size[1] <= 0:
            return bbox
        scale_x = page_width / screenshot_size[0] if page_width > 0 else 1.0
        scale_y = page_height / screenshot_size[1] if page_height > 0 else 1.0
        return (
            bbox[0] * scale_x,
            bbox[1] * scale_y,
            bbox[2] * scale_x,
            bbox[3] * scale_y,
        )

    def build_page_evidence(
        self,
        raw: ParsedPageIR,
        *,
        pdf_text_objects: list[EvidenceObject] | None = None,
        ocr_blocks: list[OcrBlock] | None = None,
        layout_regions: list[LayoutRegion] | None = None,
        screenshot_size: tuple[int, int] | None = None,
    ) -> PageEvidence:
        objects: list[EvidenceObject] = []

        if pdf_text_objects:
            objects.extend(pdf_text_objects)
        else:
            for index, block in enumerate(raw.text_blocks):
                lines = [line.strip() for line in (block.content or "").splitlines() if line.strip()]
                if not lines:
                    continue
                if len(lines) == 1:
                    objects.append(
                        EvidenceObject(
                            object_id=f"text_{index}",
                            object_type="text_block",
                            bbox=block.bbox,
                            text=lines[0],
                            source="pdf_text",
                            confidence=block.confidence,
                        )
                    )
                    continue

                x0, y0, x1, y1 = block.bbox
                total_height = max(1.0, y1 - y0)
                line_height = total_height / len(lines)
                for line_index, line in enumerate(lines):
                    ly0 = y0 + line_index * line_height
                    ly1 = y0 + (line_index + 1) * line_height
                    objects.append(
                        EvidenceObject(
                            object_id=f"text_{index}_{line_index}",
                            object_type="text_block",
                            bbox=(x0, ly0, x1, ly1),
                            text=line,
                            source="pdf_text",
                            confidence=block.confidence,
                        )
                    )

        for index, image in enumerate(raw.images):
            objects.append(
                EvidenceObject(
                    object_id=f"image_{index}",
                    object_type="image_block",
                    bbox=image.bbox,
                    source="pdf_image",
                    confidence=1.0,
                )
            )

        for index, block in enumerate(ocr_blocks or []):
            page_bbox = self._pixel_bbox_to_page(
                block.bbox,
                page_width=raw.metadata.page_width,
                page_height=raw.metadata.page_height,
                screenshot_size=screenshot_size,
            )
            objects.append(
                EvidenceObject(
                    object_id=f"ocr_{index}",
                    object_type="ocr_block",
                    bbox=page_bbox,
                    text=block.text.strip(),
                    source="ocr_text",
                    confidence=block.confidence,
                    font_size=0.0,
                )
            )

        for index, region in enumerate(layout_regions or []):
            page_bbox = self._pixel_bbox_to_page(
                region.bbox,
                page_width=raw.metadata.page_width,
                page_height=raw.metadata.page_height,
                screenshot_size=screenshot_size,
            )
            objects.append(
                EvidenceObject(
                    object_id=f"layout_{index}",
                    object_type="layout_block",
                    bbox=page_bbox,
                    label=region.label,
                    source="layout",
                    confidence=region.confidence,
                    font_size=0.0,
                )
            )

        return PageEvidence(
            page_no=raw.page_no,
            page_width=raw.metadata.page_width,
            page_height=raw.metadata.page_height,
            objects=objects,
            raw=raw,
        )

    def propose(self, evidence: PageEvidence) -> list[RegionProposal]:
        object_map = {obj.object_id: obj for obj in evidence.objects}
        text_objects = [
            obj for obj in evidence.objects
            if _is_textual_object(obj) and not _is_page_marker_text(obj.text)
        ]
        image_objects = [
            obj for obj in evidence.objects
            if obj.object_type == "image_block"
            and evidence.raw is not None
            and _is_visual_candidate(
                evidence.raw.images[int(obj.object_id.split("_")[1])],
                page_width=evidence.page_width,
                page_height=evidence.page_height,
                min_area_ratio=self._min_visual_only_area_ratio,
            )
        ]
        figure_layouts = [obj for obj in evidence.objects if _is_figure_layout(obj)]

        text_groups = _build_text_groups(text_objects, evidence.page_width)
        proposals: list[RegionProposal] = []

        if image_objects and len(text_groups) == 1:
            members = [obj.object_id for obj in image_objects] + [obj.object_id for obj in text_groups[0]]
            proposals.append(
                RegionProposal(
                    region_id="region_1",
                    bbox=_bbox_union([object_map[member].bbox for member in members]),
                    score=0.82,
                    member_object_ids=members,
                    reason="single_text_group_all_images",
                )
            )
            return proposals

        if text_groups:
            for group_index, group in enumerate(text_groups, start=1):
                members = [obj.object_id for obj in group]
                proposals.append(
                    RegionProposal(
                        region_id=f"region_{group_index}",
                        bbox=_bbox_union([obj.bbox for obj in group]),
                        score=0.72,
                        member_object_ids=members,
                        reason="text_group_seed",
                    )
                )

            visual_objects = list(image_objects) + list(figure_layouts)
            for visual_object in visual_objects:
                if not proposals:
                    break
                nearest = min(proposals, key=lambda proposal: _distance(proposal.bbox, visual_object.bbox))
                if visual_object.object_id not in nearest.member_object_ids:
                    nearest.member_object_ids.append(visual_object.object_id)
                nearest.bbox = _bbox_union([nearest.bbox, visual_object.bbox])
                nearest.score = max(nearest.score, 0.78 if visual_object.object_type == "image_block" else 0.74)
                nearest.reason = "text_visual_grouped"
        elif figure_layouts:
            for index, layout in enumerate(figure_layouts, start=1):
                proposals.append(
                    RegionProposal(
                        region_id=f"region_{index}",
                        bbox=layout.bbox,
                        score=0.66,
                        member_object_ids=[layout.object_id],
                        reason="layout_figure_seed",
                    )
                )
        elif image_objects:
            for index, image in enumerate(image_objects, start=1):
                proposals.append(
                    RegionProposal(
                        region_id=f"region_{index}",
                        bbox=image.bbox,
                        score=0.65,
                        member_object_ids=[image.object_id],
                        reason="visual_only_image",
                    )
                )

        has_visual_candidates = bool(image_objects or figure_layouts)
        filtered: list[RegionProposal] = []
        for proposal in proposals:
            if not proposal.member_object_ids:
                continue
            if has_visual_candidates and not any(
                (
                    object_map[member].object_type == "image_block"
                    or _is_figure_layout(object_map[member])
                )
                for member in proposal.member_object_ids
                if member in object_map
            ):
                continue
            filtered.append(proposal)
        return filtered
