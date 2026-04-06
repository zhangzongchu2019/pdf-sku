"""基于型号锚点的普通页 SKU 提取。"""
from __future__ import annotations

import math
import re

from pdf_sku.pipeline.ir import BindingResult, ImageInfo, SKUResult

from .models import EvidenceObject, PageEvidence

_PAGE_MARKER_RE = re.compile(r"^P\s*\d+\s*$", re.IGNORECASE)
_MODEL_RE = re.compile(
    r"\b(?=[A-Z0-9#/_-]{5,}\b)(?=[A-Z0-9#/_-]*[A-Z])(?=[A-Z0-9#/_-]*\d)"
    r"[A-Z0-9#]+(?:[-_/][A-Z0-9#]+)*\b"
)
_SPEC_RE = re.compile(
    r"(?:\b[HWDL]\s*\d+(?:\.\d+)?\s*(?:cm|mm|in)\b|\b\d+(?:\.\d+)?\s*(?:cm|mm|in)\b)",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return (0, 0, 0, 0)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _bbox_expand(
    bbox: tuple[float, float, float, float],
    *,
    pad_x: float,
    pad_y: float,
) -> tuple[float, float, float, float]:
    return (
        bbox[0] - pad_x,
        bbox[1] - pad_y,
        bbox[2] + pad_x,
        bbox[3] + pad_y,
    )


def _center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _distance(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return math.hypot(ax - bx, ay - by)


def _x_overlap_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    overlap = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    width = max(1.0, min(a[2] - a[0], b[2] - b[0]))
    return overlap / width


def _bboxes_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _bbox_contains_center(
    bbox: tuple[float, float, float, float],
    target: tuple[float, float, float, float],
) -> bool:
    cx, cy = _center(target)
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


def _area_ratio(
    bbox: tuple[float, float, float, float],
    *,
    page_width: float,
    page_height: float,
) -> float:
    page_area = max(1.0, page_width * page_height)
    width = max(0.0, bbox[2] - bbox[0])
    height = max(0.0, bbox[3] - bbox[1])
    return (width * height) / page_area


def _size(
    bbox: tuple[float, float, float, float],
) -> tuple[float, float]:
    return (max(0.0, bbox[2] - bbox[0]), max(0.0, bbox[3] - bbox[1]))


def _is_page_marker(text: str) -> bool:
    return bool(_PAGE_MARKER_RE.fullmatch(_normalize_text(text)))


def _extract_model_token(text: str) -> str | None:
    normalized = _normalize_text(text).upper()
    if not normalized or _is_page_marker(normalized):
        return None
    if _is_spec_line(normalized):
        return None
    tokens = [token for token in _MODEL_RE.findall(normalized) if len(token) >= 5]
    if not tokens:
        return None
    return max(tokens, key=len)


def _is_spec_line(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if _SPEC_RE.search(normalized):
        return True
    compact = normalized.replace(" ", "")
    return bool(re.search(r"[HWDL]\d+(?:\.\d+)?cm", compact, re.IGNORECASE))


def _contains_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text))


def _canonical_product_name(title_text: str, model_number: str) -> str:
    title_text = _normalize_text(title_text)
    model_upper = (model_number or "").upper()
    lower = title_text.lower()
    if "WOOD" in model_upper and lower.startswith("resin "):
        return title_text.split(" ", 1)[1].strip() if " " in title_text else title_text
    if ("PP" in model_upper or "RESIN" in model_upper) and lower.startswith("wood "):
        return title_text.split(" ", 1)[1].strip() if " " in title_text else title_text
    return title_text


def _is_title_line(line: EvidenceObject, baseline_font_size: float) -> bool:
    text = _normalize_text(line.text)
    if not text or _is_page_marker(text) or _extract_model_token(text) or _is_spec_line(text):
        return False
    if not _contains_letters(text):
        return False
    if len(text) > 72:
        return False
    if text.endswith((".", "!", "?")) and line.font_size < baseline_font_size + 2.0:
        return False
    words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?|[\u4e00-\u9fff]+|\d+", text)
    if len(words) > 8:
        return False
    if len(words) > 4 and line.font_size < baseline_font_size + 2.5:
        return False
    if line.font_size >= baseline_font_size + 1.5:
        return True
    return len(text) <= 36 and len(words) <= 6 and not text.endswith((".", "!", "?"))


def _page_half(bbox: tuple[float, float, float, float], page_width: float) -> int:
    return 0 if _center(bbox)[0] < (page_width / 2) else 1


def _is_bindable_image(
    image: ImageInfo,
    *,
    page_width: float,
    page_height: float,
) -> bool:
    if not image.image_id or image.bbox == (0, 0, 0, 0):
        return False
    width = max(0.0, image.bbox[2] - image.bbox[0])
    height = max(0.0, image.bbox[3] - image.bbox[1])
    if width <= 0 or height <= 0:
        return False
    if min(width, height) < 60 and not image.search_eligible:
        return False
    width_ratio = width / max(1.0, page_width)
    height_ratio = height / max(1.0, page_height)
    if (width_ratio <= 0.12 and height_ratio >= 0.85) or (height_ratio <= 0.12 and width_ratio >= 0.85):
        return False
    return True


class ModelAnchorExtractor:
    """页面内存在显式型号时，优先按型号拆分 SKU。"""

    def extract(
        self,
        evidence: PageEvidence,
    ) -> tuple[list[SKUResult], list[BindingResult]]:
        if evidence.raw is None:
            return [], []

        text_objects = [
            obj
            for obj in evidence.objects
            if obj.object_type in {"text_block", "ocr_block"} and _normalize_text(obj.text)
        ]
        if not text_objects:
            return [], []

        if any(obj.source == "pdf_text_precise" for obj in text_objects):
            text_objects = [obj for obj in text_objects if obj.source == "pdf_text_precise"]
        elif any(obj.source.startswith("pdf_text") for obj in text_objects):
            text_objects = [obj for obj in text_objects if obj.source.startswith("pdf_text")]

        ordered = sorted(text_objects, key=lambda obj: (obj.bbox[1], obj.bbox[0]))
        font_sizes = [obj.font_size for obj in ordered if obj.font_size > 0]
        baseline_font_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 0.0
        title_candidates = [obj for obj in ordered if _is_title_line(obj, baseline_font_size)]
        model_anchors: list[tuple[int, EvidenceObject, str]] = []
        seen_models: set[str] = set()
        for index, obj in enumerate(ordered):
            model = _extract_model_token(obj.text)
            if not model or model in seen_models:
                continue
            seen_models.add(model)
            model_anchors.append((index, obj, model))
        if not model_anchors:
            return [], []

        image_candidates = [
            image for image in evidence.raw.images
            if _is_bindable_image(
                image,
                page_width=evidence.page_width,
                page_height=evidence.page_height,
            )
        ]
        records = []
        for index, anchor, model_number in model_anchors:
            title = self._choose_title(
                anchor,
                title_candidates=title_candidates,
                page_width=evidence.page_width,
            )
            spec_lines = self._collect_spec_lines(ordered, index)
            description_lines = self._collect_description_lines(
                ordered,
                anchor=anchor,
                title=title,
                page_width=evidence.page_width,
                baseline_font_size=baseline_font_size,
            )
            records.append(
                {
                    "anchor_index": index,
                    "anchor": anchor,
                    "model_number": model_number,
                    "title": title,
                    "spec_lines": spec_lines,
                    "description_lines": description_lines,
                    "family_key": title.object_id if title else model_number,
                }
            )

        image_groups = self._assign_images_to_records(
            records=records,
            images=image_candidates,
            page_width=evidence.page_width,
            page_height=evidence.page_height,
        )
        skus: list[SKUResult] = []
        bindings: list[BindingResult] = []
        for record_index, record in enumerate(records):
            anchor = record["anchor"]
            model_number = record["model_number"]
            title = record["title"]
            spec_lines = record["spec_lines"]
            description_lines = record["description_lines"]
            assigned_group = image_groups[record_index]
            primary_image_id = assigned_group[0].image_id if assigned_group else None

            component_lines = []
            if title:
                component_lines.append(_normalize_text(title.text))
            component_lines.extend(_normalize_text(line.text) for line in description_lines)
            component_lines.append(_normalize_text(anchor.text))
            component_lines.extend(_normalize_text(line.text) for line in spec_lines)
            unique_lines = [line for line in dict.fromkeys(component_lines) if line]
            if not unique_lines:
                continue

            attributes: dict[str, str] = {
                "evidence_mode": "text_backed",
                "model_number": model_number,
                "raw_attribute_text": " ".join(unique_lines),
                "product_description": " ".join(unique_lines),
            }
            if title:
                attributes["product_name"] = _canonical_product_name(title.text, model_number)
            if spec_lines:
                attributes["specs"] = " ".join(_normalize_text(line.text) for line in spec_lines)

            boxes = [anchor.bbox]
            if title:
                boxes.append(title.bbox)
            boxes.extend(line.bbox for line in description_lines)
            boxes.extend(line.bbox for line in spec_lines)
            if primary_image_id:
                image = next((item for item in assigned_group if item.image_id == primary_image_id), None)
                if image is not None:
                    boxes.append(image.bbox)

            confidence = 0.7
            if title:
                confidence += 0.08
            if spec_lines:
                confidence += 0.07
            if primary_image_id:
                confidence += 0.05

            skus.append(
                SKUResult(
                    sku_id="",
                    attributes=attributes,
                    source_bbox=_bbox_union(boxes),
                    validity="valid",
                    confidence=min(confidence, 0.94),
                    extraction_method="model_anchor_v2",
                )
            )
            if not assigned_group:
                bindings.append(
                    BindingResult(
                        sku_id="",
                        image_id=None,
                        confidence=0.0,
                        method="model_anchor_image_group",
                        is_ambiguous=False,
                        rank=1,
                    )
                )
                continue
            for rank, image in enumerate(assigned_group, start=1):
                bindings.append(
                    BindingResult(
                        sku_id="",
                        image_id=image.image_id,
                        confidence=max(0.55, 0.84 - (rank - 1) * 0.08),
                        method="model_anchor_image_group",
                        is_ambiguous=False,
                        rank=rank,
                    )
                )

        return skus, bindings

    @classmethod
    def _assign_images_to_records(
        cls,
        *,
        records: list[dict],
        images: list[ImageInfo],
        page_width: float,
        page_height: float,
    ) -> list[list[ImageInfo]]:
        if not records:
            return []
        family_counts: dict[str, int] = {}
        family_to_indices: dict[str, list[int]] = {}
        for record in records:
            family_key = str(record.get("family_key") or "")
            family_counts[family_key] = family_counts.get(family_key, 0) + 1
        for index, record in enumerate(records):
            family_key = str(record.get("family_key") or "")
            family_to_indices.setdefault(family_key, []).append(index)
        groups: list[list[tuple[tuple[float, float], ImageInfo]]] = [[] for _ in records]
        for image in images:
            scored: list[tuple[tuple[float, float], int]] = []
            for index, record in enumerate(records):
                scored.append(
                    (
                        cls._rank_image_for_anchor(
                            record["anchor"],
                            image,
                            page_width=page_width,
                            page_height=page_height,
                        ),
                        index,
                    )
                )
            best_score, best_index = min(scored, key=lambda item: item[0])
            groups[best_index].append((best_score, image))

        used_image_ids = {
            image.image_id
            for group in groups
            for _, image in group
            if image.image_id
        }
        for index, record in enumerate(records):
            if groups[index]:
                continue
            fallback = cls._choose_image(
                record["anchor"],
                images=images,
                page_width=page_width,
                page_height=page_height,
                assigned_images=used_image_ids,
            )
            if not fallback:
                continue
            image = next((candidate for candidate in images if candidate.image_id == fallback), None)
            if image is None:
                continue
            groups[index].append(
                (
                    cls._rank_image_for_anchor(
                        record["anchor"],
                        image,
                        page_width=page_width,
                        page_height=page_height,
                    ),
                    image,
                )
            )
            used_image_ids.add(fallback)

        groups = cls._reassign_family_companions(
            records=records,
            grouped_images=groups,
            family_to_indices=family_to_indices,
            page_width=page_width,
            page_height=page_height,
        )

        pruned_groups = [
            cls._prune_image_group(
                anchor=records[index]["anchor"],
                images=[image for _, image in group],
                page_width=page_width,
                page_height=page_height,
                family_model_count=family_counts.get(str(records[index].get("family_key") or ""), 1),
            )
            for index, group in enumerate(groups)
        ]
        return cls._supplement_image_groups(
            records=records,
            groups=pruned_groups,
            images=images,
            family_to_indices=family_to_indices,
            page_width=page_width,
            page_height=page_height,
        )

    @classmethod
    def _reassign_family_companions(
        cls,
        *,
        records: list[dict],
        grouped_images: list[list[tuple[tuple[float, float], ImageInfo]]],
        family_to_indices: dict[str, list[int]],
        page_width: float,
        page_height: float,
    ) -> list[list[tuple[tuple[float, float], ImageInfo]]]:
        updated = [
            list(group)
            for group in grouped_images
        ]
        for family_indices in family_to_indices.values():
            if len(family_indices) <= 1:
                continue
            primary_by_index: dict[int, ImageInfo] = {}
            companion_pool: list[ImageInfo] = []
            for index in family_indices:
                group = sorted(updated[index], key=lambda item: item[0])
                if not group:
                    continue
                primary_by_index[index] = group[0][1]
                companion_pool.extend(image for _, image in group[1:])
                updated[index] = [group[0]]
            if len(primary_by_index) <= 1:
                continue
            for image in companion_pool:
                scored: list[tuple[tuple[float, float, float, float], int]] = []
                for index, primary in primary_by_index.items():
                    score = cls._score_supplement_candidate(
                        anchor=records[index]["anchor"],
                        current_images=[primary],
                        image=image,
                        page_width=page_width,
                        page_height=page_height,
                        family_model_count=len(family_indices),
                    )
                    if score is None:
                        continue
                    scored.append((score, index))
                if not scored:
                    continue
                scored.sort(key=lambda item: item[0])
                best_score, best_index = scored[0]
                if len(scored) > 1:
                    second_score = scored[1][0]
                    if second_score[0] - best_score[0] < max(18.0, page_width * 0.014):
                        continue
                updated[best_index].append((best_score, image))
        return updated

    @staticmethod
    def _prune_image_group(
        *,
        anchor: EvidenceObject,
        images: list[ImageInfo],
        page_width: float,
        page_height: float,
        family_model_count: int,
    ) -> list[ImageInfo]:
        if len(images) <= 1:
            return images
        primary = images[0]
        primary_width, primary_height = _size(primary.bbox)
        primary_diag = math.hypot(primary_width, primary_height)
        primary_center = _center(primary.bbox)
        kept = [primary]
        for image in images[1:]:
            image_center = _center(image.bbox)
            dx = abs(primary_center[0] - image_center[0])
            dy = abs(primary_center[1] - image_center[1])
            near_primary = _distance(primary.bbox, image.bbox) <= max(primary_diag * 0.65, page_width * 0.08)
            horizontal_companion = (
                dy <= max(primary_height * 0.30, 60.0)
                and dx <= max(primary_width * 1.45, 150.0)
            )
            aligned_band = (
                dx <= max(primary_width * 0.55, 72.0)
                and dy <= max(primary_height * 0.55, 72.0)
            )
            vertical_stack = (
                _x_overlap_ratio(primary.bbox, image.bbox) >= 0.22
                and dy <= max(primary_height * 0.95, page_height * 0.13)
            )
            if family_model_count <= 1:
                keep = near_primary or horizontal_companion or aligned_band or vertical_stack
            else:
                keep = horizontal_companion or aligned_band or vertical_stack
            if keep:
                kept.append(image)
        return kept

    @classmethod
    def _supplement_image_groups(
        cls,
        *,
        records: list[dict],
        groups: list[list[ImageInfo]],
        images: list[ImageInfo],
        family_to_indices: dict[str, list[int]],
        page_width: float,
        page_height: float,
    ) -> list[list[ImageInfo]]:
        updated = [list(group) for group in groups]
        used_ids = {
            image.image_id
            for group in updated
            for image in group
            if image.image_id
        }
        family_counts = {
            family_key: len(indices)
            for family_key, indices in family_to_indices.items()
        }
        for image in images:
            if not image.image_id or image.image_id in used_ids:
                continue
            scored: list[tuple[tuple[float, float, float, float], int]] = []
            for index, record in enumerate(records):
                score = cls._score_supplement_candidate(
                    anchor=record["anchor"],
                    current_images=updated[index],
                    image=image,
                    page_width=page_width,
                    page_height=page_height,
                    family_model_count=family_counts.get(str(record.get("family_key") or ""), 1),
                )
                if score is None:
                    continue
                scored.append((score, index))
            if not scored:
                continue
            scored.sort(key=lambda item: item[0])
            best_score, best_index = scored[0]
            if len(scored) > 1:
                second_score = scored[1][0]
                improvement = second_score[0] - best_score[0]
                if improvement < max(16.0, page_width * 0.012):
                    continue
            updated[best_index].append(image)
            used_ids.add(image.image_id)
        return updated

    @classmethod
    def _score_supplement_candidate(
        cls,
        *,
        anchor: EvidenceObject,
        current_images: list[ImageInfo],
        image: ImageInfo,
        page_width: float,
        page_height: float,
        family_model_count: int,
    ) -> tuple[float, float, float, float] | None:
        if _page_half(anchor.bbox, page_width) != _page_half(image.bbox, page_width):
            return None

        seed_boxes = [anchor.bbox]
        if current_images:
            seed_boxes.extend(candidate.bbox for candidate in current_images)
        seed_box = _bbox_union(seed_boxes)
        seed_width, seed_height = _size(seed_box)
        primary = current_images[0] if current_images else None
        primary_bbox = primary.bbox if primary else anchor.bbox
        primary_width, primary_height = _size(primary_bbox)
        dx = abs(_center(primary_bbox)[0] - _center(image.bbox)[0])
        dy = abs(_center(primary_bbox)[1] - _center(image.bbox)[1])
        primary_diag = math.hypot(primary_width, primary_height)

        expanded = _bbox_expand(
            seed_box,
            pad_x=max(42.0, seed_width * (0.40 if family_model_count <= 1 else 0.16)),
            pad_y=max(36.0, seed_height * (0.22 if family_model_count <= 1 else 0.12)),
        )
        inside_seed = _bbox_contains_center(expanded, image.bbox)
        near_primary = _distance(primary_bbox, image.bbox) <= max(primary_diag * 0.85, page_width * 0.085)
        same_row = (
            dy <= max(primary_height * 0.38, 68.0)
            and dx <= max(primary_width * 0.75, 118.0)
        )
        upper_band = (
            image.bbox[3] <= primary_bbox[3] + max(primary_height * 0.16, 24.0)
            and primary_bbox[1] - image.bbox[3] <= max(primary_height * 0.72, 120.0)
            and dx <= max(primary_width * 0.72, 118.0)
        )
        vertical_stack = (
            _x_overlap_ratio(primary_bbox, image.bbox) >= 0.16
            and dy <= max(primary_height * 0.95, page_height * 0.14)
        )
        if family_model_count <= 1:
            accepted = inside_seed or near_primary or same_row or upper_band or vertical_stack
        else:
            accepted = inside_seed or same_row or upper_band or vertical_stack
        if not accepted:
            return None

        anchor_score = cls._rank_image_for_anchor(
            anchor,
            image,
            page_width=page_width,
            page_height=page_height,
        )
        primary_score = cls._rank_image_for_primary(
            primary if primary is not None else ImageInfo(bbox=anchor.bbox, image_id="anchor_proxy"),
            image,
            page_width=page_width,
            page_height=page_height,
        )
        combined = primary_score[0] * 0.7 + anchor_score[0] * 0.3
        return (combined, primary_score[0], anchor_score[0], -image.short_edge)

    @staticmethod
    def _choose_title(
        anchor: EvidenceObject,
        *,
        title_candidates: list[EvidenceObject],
        page_width: float,
    ) -> EvidenceObject | None:
        if not title_candidates:
            return None

        anchor_half = _page_half(anchor.bbox, page_width)
        same_half_candidates = [
            title for title in title_candidates
            if _page_half(title.bbox, page_width) == anchor_half
        ]
        candidates = same_half_candidates or title_candidates
        best: tuple[float, EvidenceObject] | None = None
        for title in candidates:
            dx = abs(_center(anchor.bbox)[0] - _center(title.bbox)[0])
            score = dx * 0.35
            if title.bbox[1] > anchor.bbox[3]:
                gap = title.bbox[1] - anchor.bbox[3]
                score += 120.0 + gap * 0.7
                if gap <= 28 and (_x_overlap_ratio(anchor.bbox, title.bbox) >= 0.15 or dx <= page_width * 0.12):
                    score -= 80.0
            else:
                score += max(0.0, anchor.bbox[1] - title.bbox[3])
            score -= title.font_size * 2.0
            if best is None or score < best[0]:
                best = (score, title)
        return best[1] if best else None

    @staticmethod
    def _collect_spec_lines(ordered: list[EvidenceObject], anchor_index: int) -> list[EvidenceObject]:
        anchor = ordered[anchor_index]
        specs: list[EvidenceObject] = []
        for candidate in ordered[anchor_index + 1:anchor_index + 8]:
            if _extract_model_token(candidate.text):
                same_row = abs(candidate.bbox[1] - anchor.bbox[1]) <= 24
                x_distance = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
                if same_row and x_distance > 140:
                    continue
                break
            if candidate.bbox[1] - anchor.bbox[3] > 120:
                break
            if _is_spec_line(candidate.text):
                x_distance = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
                if x_distance <= 140 or _x_overlap_ratio(anchor.bbox, candidate.bbox) >= 0.2:
                    specs.append(candidate)
                elif specs:
                    break
            elif specs:
                x_distance = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
                if x_distance > 140:
                    continue
                break
        return specs

    @staticmethod
    def _collect_description_lines(
        ordered: list[EvidenceObject],
        *,
        anchor: EvidenceObject,
        title: EvidenceObject | None,
        page_width: float,
        baseline_font_size: float,
    ) -> list[EvidenceObject]:
        if title is None:
            return []

        lower = min(anchor.bbox[1], title.bbox[1]) - 6
        upper = max(anchor.bbox[3], title.bbox[3]) + 120
        anchor_half = _page_half(anchor.bbox, page_width)
        selected: list[EvidenceObject] = []
        for candidate in ordered:
            if candidate is title or candidate is anchor:
                continue
            if _page_half(candidate.bbox, page_width) != anchor_half:
                continue
            if candidate.bbox[1] < lower or candidate.bbox[3] > upper:
                continue
            if _is_page_marker(candidate.text) or _extract_model_token(candidate.text) or _is_spec_line(candidate.text):
                continue
            if _is_title_line(candidate, baseline_font_size):
                continue
            selected.append(candidate)
        return selected[:6]

    @staticmethod
    def _choose_image(
        anchor: EvidenceObject,
        *,
        images: list[ImageInfo],
        page_width: float,
        page_height: float,
        assigned_images: set[str],
    ) -> str | None:
        if not images:
            return None

        fresh = [image for image in images if image.image_id and image.image_id not in assigned_images]
        if fresh:
            best = min(
                fresh,
                key=lambda image: ModelAnchorExtractor._rank_image_for_anchor(
                    anchor,
                    image,
                    page_width=page_width,
                    page_height=page_height,
                ),
            )
            return best.image_id
        best = min(
            [image for image in images if image.image_id],
            key=lambda image: (
                ModelAnchorExtractor._rank_image_for_anchor(
                    anchor,
                    image,
                    page_width=page_width,
                    page_height=page_height,
                )[0] + page_width * 0.05,
                ModelAnchorExtractor._rank_image_for_anchor(
                    anchor,
                    image,
                    page_width=page_width,
                    page_height=page_height,
                )[1],
            ),
            default=None,
        )
        return best.image_id if best else None

    @staticmethod
    def _rank_image_for_anchor(
        anchor: EvidenceObject,
        image: ImageInfo,
        *,
        page_width: float,
        page_height: float,
    ) -> tuple[float, float]:
        anchor_half = _page_half(anchor.bbox, page_width)
        half_penalty = 0.0 if _page_half(image.bbox, page_width) == anchor_half else page_width * 0.25
        dx = abs(_center(anchor.bbox)[0] - _center(image.bbox)[0])
        dy = abs(_center(anchor.bbox)[1] - _center(image.bbox)[1])
        score = dy + dx * 1.4 + half_penalty
        overlap = _x_overlap_ratio(anchor.bbox, image.bbox)
        if overlap >= 0.2:
            score -= 80.0
        elif dx <= page_width * 0.08:
            score -= 25.0
        if image.bbox[1] >= anchor.bbox[3] + 40:
            score += 40.0
        if image.bbox[3] <= anchor.bbox[1]:
            score -= 15.0
        score -= min(_area_ratio(image.bbox, page_width=page_width, page_height=page_height), 0.08) * 120.0
        return (score, -image.short_edge)

    @staticmethod
    def _rank_image_for_primary(
        primary: ImageInfo,
        image: ImageInfo,
        *,
        page_width: float,
        page_height: float,
    ) -> tuple[float, float]:
        dx = abs(_center(primary.bbox)[0] - _center(image.bbox)[0])
        dy = abs(_center(primary.bbox)[1] - _center(image.bbox)[1])
        score = _distance(primary.bbox, image.bbox) + dx * 0.25
        if _x_overlap_ratio(primary.bbox, image.bbox) >= 0.2:
            score -= 40.0
        score -= min(_area_ratio(image.bbox, page_width=page_width, page_height=page_height), 0.08) * 80.0
        return (score, -image.short_edge)
