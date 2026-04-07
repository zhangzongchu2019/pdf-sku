"""基于型号锚点的普通页 SKU 提取。"""
from __future__ import annotations

import math
import re

from pdf_sku.pipeline.ir import BindingResult, ImageInfo, SKUResult

from .models import EvidenceObject, PageEvidence

_PAGE_MARKER_RE = re.compile(
    r"^(?:P|PG|PAGE|AGE)\s*[/\\-]?\s*0*\d+\s*$",
    re.IGNORECASE,
)
_GENERIC_MODEL_TOKEN_RE = re.compile(r"[A-Z0-9#]+(?:[-_/][A-Z0-9#]+)*")
_LABELED_MODEL_RE = re.compile(
    r"^(?P<label>.+?)(?:[:：]\s*)+(?P<model>[A-Za-z0-9#/_-]{2,})\s*$"
)
_LABELED_PRODUCT_RE = re.compile(
    r"^(?P<label>.+?)(?:[:：]\s*)+(?P<value>.+?)\s*$"
)
_GENERIC_MODEL_VALUE_RE = re.compile(
    r"^(?:型号|货号|编号|model(?:\s*number)?)\s*[:：]?\s*[A-Za-z0-9#/_-]+\s*$",
    re.IGNORECASE,
)
_CHINESE_NON_PRODUCT_LABELS = (
    "售价",
    "价格",
    "批发价",
    "打包价",
    "代发价",
    "拿货价",
    "活动价",
    "库存",
    "重量",
    "自动下架时间",
    "下架时间",
    "颜色",
    "规格编码",
    "规格",
    "尺寸",
    "备注",
    "来源",
    "标签",
    "商品ID",
    "商品简称",
)
_ENGLISH_NON_PRODUCT_LABEL_RE = re.compile(
    r"\b(?:price|wholesale(?:\s+price)?|pack(?:\s+price)?|dropship(?:\s+price)?|purchase(?:\s+price)?|campaign(?:\s+type|\s+price)?|stock|weight|color|colour|spec(?:\s+code)?|size|remark|source|tag|product\s*id|short\s*name)\b",
    re.IGNORECASE,
)
_SPEC_RE = re.compile(
    r"(?:\b[HWDL]\s*\d+(?:\.\d+)?\s*(?:cm|mm|in)\b|\b\d+(?:\.\d+)?\s*(?:cm|mm|in)\b)",
    re.IGNORECASE,
)
_COLOR_RE = re.compile(r"(?:颜色|colou?r)\s*[:：]?\s*([^\n]+)", re.IGNORECASE)
_LEADING_ORDINAL_RE = re.compile(r"^(?:NO\.?\s*)?\d{1,3}\s*", re.IGNORECASE)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _contains_non_product_label(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(label in normalized for label in _CHINESE_NON_PRODUCT_LABELS) or bool(
        _ENGLISH_NON_PRODUCT_LABEL_RE.search(normalized)
    )


def _bbox_union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return (0, 0, 0, 0)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


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


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    overlap_w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    overlap_h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return overlap_w * overlap_h


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
    normalized = _normalize_text(text).upper().replace(" ", "")
    return bool(_PAGE_MARKER_RE.fullmatch(normalized))


def _looks_like_dimension_token(token: str) -> bool:
    compact = _normalize_text(token).upper().replace(" ", "")
    if not compact:
        return False
    if any(unit in compact for unit in ("MM", "CM", "IN")):
        return True
    if re.search(r"\d+(?:\.\d+)?[X×*]\d+", compact):
        return True
    if re.search(r"\d{3,}(?:[-_/])\d{3,}", compact):
        return True
    return False


def _looks_like_model_token(token: str, *, labeled: bool) -> bool:
    compact = _normalize_text(token).upper().replace(" ", "")
    if not compact or not re.search(r"\d", compact):
        return False
    if _is_page_marker(compact):
        return False
    if compact.startswith(("PAGE/", "AGE/", "P/")):
        return False
    if _looks_like_dimension_token(compact):
        return False
    if re.search(r"[A-Z]", compact):
        return len(compact) >= 4
    if labeled:
        return bool(re.fullmatch(r"\d{2,6}#?", compact))
    return bool(re.fullmatch(r"\d{3,6}#", compact))


def _model_group_key(token: str) -> str:
    normalized = _normalize_text(token).upper().replace(" ", "")
    if re.fullmatch(r"\d{2,6}#?", normalized):
        return normalized.rstrip("#")
    return normalized


def _model_family_key(token: str) -> str:
    normalized = _model_group_key(token)
    suffix = ""
    if normalized.endswith("#"):
        normalized, suffix = normalized[:-1], "#"
    if len(normalized) >= 2 and normalized[-1].isalpha() and any(ch.isdigit() for ch in normalized[:-1]):
        normalized = normalized[:-1]
    return normalized + suffix


def _looks_like_product_label(label: str) -> bool:
    normalized = _normalize_text(label)
    if not normalized:
        return False
    if _contains_non_product_label(normalized):
        return False
    if _is_generic_model_label(normalized):
        return False
    if not _contains_letters(normalized):
        return False
    if len(normalized) > 48:
        return False
    if re.search(r"[.!?。；;]$", normalized):
        return False
    word_parts = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?|[\u4e00-\u9fff]+|\d+", normalized)
    if len(word_parts) > 8:
        return False
    if len(word_parts) >= 6 and " " in normalized and normalized.lower() == normalized:
        return False
    return True


def _is_generic_model_label(label: str) -> bool:
    normalized = _normalize_text(label)
    return bool(
        re.fullmatch(r"(?:型号|货号|编号|model(?:\s*number)?)", normalized, re.IGNORECASE)
    )


def _is_generic_product_name_label(label: str) -> bool:
    normalized = _normalize_text(label)
    return bool(
        re.fullmatch(
            r"(?:型号|名称|品名|款式|系列|product(?:\s+name)?|item(?:\s+name)?|name|series|style)",
            normalized,
            re.IGNORECASE,
        )
    )


def _extract_labeled_model_parts(text: str) -> tuple[str, str] | None:
    normalized = _normalize_text(text)
    if not normalized or _is_page_marker(normalized) or _is_spec_line(normalized):
        return None
    match = _LABELED_MODEL_RE.fullmatch(normalized)
    if not match:
        return None
    label = _normalize_text(match.group("label")).rstrip(":：")
    model = _normalize_text(match.group("model")).upper()
    if not label or not _contains_letters(label):
        return None
    if _is_generic_model_label(label):
        return None
    if not _looks_like_product_label(label):
        return None
    if not _looks_like_model_token(model, labeled=True):
        return None
    return label, model


def _extract_labeled_product_name(text: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized or _is_page_marker(normalized) or _is_spec_line(normalized):
        return None
    match = _LABELED_PRODUCT_RE.fullmatch(normalized)
    if not match:
        return None
    label = _normalize_text(match.group("label")).rstrip(":：")
    value = _normalize_text(match.group("value")).strip()
    if not label or not value:
        return None
    if _contains_non_product_label(label):
        return None
    if not _is_generic_product_name_label(label):
        return None
    if _is_page_marker(value) or _is_spec_line(value):
        return None
    if _extract_labeled_model_parts(normalized):
        return None
    if _looks_like_model_token(value, labeled=True):
        return None
    if not _contains_letters(value):
        return None
    return value.strip("：:;；,， ")


def _cleanup_product_name_candidate(
    text: str,
    *,
    model_number: str | None = None,
) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    if model_number:
        normalized = re.sub(re.escape(model_number), " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"^(?:型号|货号|编号|名称|品名|款式|系列|product(?:\s+name)?|item(?:\s+name)?|name|series|style)\s*[:：]?\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    ordinal_stripped = _LEADING_ORDINAL_RE.sub("", normalized)
    if ordinal_stripped != normalized and _contains_letters(ordinal_stripped):
        normalized = ordinal_stripped
    normalized = normalized.strip(" ：:;；,，._-/#")
    if not normalized or not _contains_letters(normalized):
        return None
    if _contains_non_product_label(normalized) or _is_page_marker(normalized) or _is_spec_line(normalized):
        return None
    if _extract_model_token(normalized):
        return None
    return normalized


def _extract_inline_product_name(text: str, model_number: str | None) -> str | None:
    normalized = _normalize_text(text)
    if not normalized or _is_page_marker(normalized) or _is_spec_line(normalized):
        return None
    labeled = _extract_labeled_model_parts(normalized)
    if labeled and model_number and _model_group_key(labeled[1]) == _model_group_key(model_number):
        return _cleanup_product_name_candidate(labeled[0], model_number=model_number)
    if not model_number:
        return _cleanup_product_name_candidate(normalized)
    if re.search(re.escape(model_number), normalized, re.IGNORECASE) is None:
        return None
    candidate = re.sub(re.escape(model_number), " ", normalized, flags=re.IGNORECASE)
    return _cleanup_product_name_candidate(candidate, model_number=model_number)


def _extract_color_value(lines: list[str]) -> str | None:
    for line in lines:
        match = _COLOR_RE.search(line)
        if not match:
            continue
        value = _normalize_text(match.group(1)).strip("：:;；,， ")
        if value:
            return value
    return None


def _is_color_line(text: str) -> bool:
    return bool(_COLOR_RE.search(_normalize_text(text)))


def _extract_model_token(text: str) -> str | None:
    normalized = _normalize_text(text).upper()
    if not normalized or _is_page_marker(normalized):
        return None
    if _is_spec_line(normalized):
        return None
    labeled = _extract_labeled_model_parts(normalized)
    if labeled:
        return labeled[1]
    tokens = [
        token
        for token in _GENERIC_MODEL_TOKEN_RE.findall(normalized)
        if _looks_like_model_token(token, labeled=False)
    ]
    if not tokens:
        return None
    return max(tokens, key=len)


def _is_spec_line(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if re.search(r"(?:规格|尺寸|size)", normalized, re.IGNORECASE):
        return True
    if _SPEC_RE.search(normalized):
        return True
    compact = normalized.replace(" ", "")
    if re.search(r"\d+(?:\.\d+)?[X×*]\d+(?:\.\d+)?", compact, re.IGNORECASE):
        return True
    return bool(re.search(r"[HWDL]\d+(?:\.\d+)?cm", compact, re.IGNORECASE))


def _contains_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text))


def _same_row_model_siblings(
    ordered: list[EvidenceObject],
    anchor_index: int,
) -> list[EvidenceObject]:
    anchor = ordered[anchor_index]
    siblings: list[EvidenceObject] = []
    for index, candidate in enumerate(ordered):
        if index == anchor_index:
            continue
        if not _extract_model_token(candidate.text):
            continue
        if abs(candidate.bbox[1] - anchor.bbox[1]) <= 24:
            siblings.append(candidate)
    return siblings


def _is_text_heavy_image(
    image: ImageInfo,
    *,
    text_objects: list[EvidenceObject],
    page_width: float,
    page_height: float,
) -> bool:
    image_area = _bbox_area(image.bbox)
    if image_area <= 0:
        return True
    overlapped_blocks = []
    overlap_area = 0.0
    for obj in text_objects:
        if obj.object_type not in {"text_block", "ocr_block"}:
            continue
        text = _normalize_text(obj.text)
        if not text or not _bboxes_intersect(image.bbox, obj.bbox):
            continue
        area = _intersection_area(image.bbox, obj.bbox)
        if area <= 0:
            continue
        overlapped_blocks.append(obj)
        overlap_area += area

    if not overlapped_blocks:
        return False

    overlap_ratio = overlap_area / image_area
    width, height = _size(image.bbox)
    width_ratio = width / max(1.0, page_width)
    height_ratio = height / max(1.0, page_height)
    short_edge = min(width, height)
    long_edge = max(width, height)
    aspect_ratio = long_edge / max(1.0, short_edge)
    textish = sum(
        1
        for obj in overlapped_blocks
        if (
            len(_normalize_text(obj.text)) >= 4
            or " " in _normalize_text(obj.text)
            or _contains_letters(_normalize_text(obj.text))
        )
    )
    return (
        overlap_ratio >= 0.38
        or (
            textish >= 1
            and overlap_ratio >= 0.22
            and (height_ratio <= 0.12 or width_ratio <= 0.22)
        )
        or (
            len(overlapped_blocks) >= 2
            and overlap_ratio >= 0.18
            and height_ratio <= 0.16
        )
        or (
            textish >= 1
            and short_edge <= max(page_width, page_height) * 0.12
            and aspect_ratio >= 2.0
            and overlap_ratio >= 0.08
        )
    )


def _looks_like_ocr_title_text(text: str) -> bool:
    normalized = _normalize_text(text)
    if len(normalized) < 2:
        return False
    if re.search(r"[_\"“”'`~!?,，。；;:：]", normalized):
        return False
    chinese_parts = re.findall(r"[\u4e00-\u9fff]+", normalized)
    english_parts = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?", normalized)
    if chinese_parts:
        if len(chinese_parts) != 1:
            return False
        if not 2 <= len(chinese_parts[0]) <= 12:
            return False
    if english_parts:
        joined_english = " ".join(english_parts)
        if len(joined_english) < 4 or len(joined_english) > 32:
            return False
        if len(english_parts) == 1 and english_parts[0].isupper():
            return False
    if not chinese_parts and not english_parts:
        return False
    return True


def _canonical_product_name(title_text: str, model_number: str) -> str:
    return _cleanup_product_name_candidate(title_text, model_number=model_number) or _normalize_text(title_text)


def _is_title_line(line: EvidenceObject, baseline_font_size: float) -> bool:
    text = _normalize_text(line.text)
    if not text or _is_page_marker(text) or _extract_model_token(text) or _is_spec_line(text):
        return False
    if len(text) < 2:
        return False
    if not _contains_letters(text):
        return False
    if line.source == "ocr_text" and not _looks_like_ocr_title_text(text):
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
    if image.is_fragmented:
        return False
    if not image.image_id or image.bbox == (0, 0, 0, 0):
        return False
    width = max(0.0, image.bbox[2] - image.bbox[0])
    height = max(0.0, image.bbox[3] - image.bbox[1])
    if width <= 0 or height <= 0:
        return False
    short_edge = min(width, height)
    long_edge = max(width, height)
    if short_edge < 90 and long_edge / max(1.0, short_edge) >= 2.0:
        return False
    if min(width, height) < 60 and not image.search_eligible:
        return False
    width_ratio = width / max(1.0, page_width)
    height_ratio = height / max(1.0, page_height)
    if (width_ratio <= 0.12 and height_ratio >= 0.85) or (height_ratio <= 0.12 and width_ratio >= 0.85):
        return False
    return True


def _is_page_spanning_image(
    image: ImageInfo,
    *,
    page_width: float,
    page_height: float,
) -> bool:
    width = max(0.0, image.bbox[2] - image.bbox[0])
    height = max(0.0, image.bbox[3] - image.bbox[1])
    page_area = max(1.0, page_width * page_height)
    area_ratio = (width * height) / page_area
    width_ratio = width / max(1.0, page_width)
    height_ratio = height / max(1.0, page_height)
    return area_ratio >= 0.45 and width_ratio >= 0.55 and height_ratio >= 0.45


class ModelAnchorExtractor:
    """页面内存在显式型号时，优先按型号拆分 SKU。"""

    @staticmethod
    def _collect_anchor_candidates(
        text_objects: list[EvidenceObject],
    ) -> tuple[
        list[EvidenceObject],
        float,
        list[EvidenceObject],
        dict[str, int],
        list[tuple[int, EvidenceObject, str]],
        list[tuple[int, EvidenceObject, str]],
    ]:
        ordered = sorted(text_objects, key=lambda obj: (obj.bbox[1], obj.bbox[0]))
        font_sizes = [obj.font_size for obj in ordered if obj.font_size > 0]
        baseline_font_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 0.0
        title_candidates = [obj for obj in ordered if _is_title_line(obj, baseline_font_size)]
        index_by_object_id = {obj.object_id: index for index, obj in enumerate(ordered)}

        model_anchors: list[tuple[int, EvidenceObject, str]] = []
        seen_model_keys: set[str] = set()
        for index, obj in enumerate(ordered):
            model = _extract_model_token(obj.text)
            if not model:
                continue
            model_key = _model_group_key(model)
            if model_key in seen_model_keys:
                continue
            seen_model_keys.add(model_key)
            model_anchors.append((index, obj, model))

        product_name_anchors: list[tuple[int, EvidenceObject, str]] = []
        if not model_anchors:
            seen_names: set[str] = set()
            for index, obj in enumerate(ordered):
                product_name = _extract_labeled_product_name(obj.text)
                if not product_name or product_name in seen_names:
                    continue
                seen_names.add(product_name)
                product_name_anchors.append((index, obj, product_name))

        return (
            ordered,
            baseline_font_size,
            title_candidates,
            index_by_object_id,
            model_anchors,
            product_name_anchors,
        )

    def extract(
        self,
        evidence: PageEvidence,
    ) -> tuple[list[SKUResult], list[BindingResult]]:
        if evidence.raw is None:
            return [], []

        all_text_objects = [
            obj
            for obj in evidence.objects
            if obj.object_type in {"text_block", "ocr_block"} and _normalize_text(obj.text)
        ]
        if not all_text_objects:
            return [], []

        preferred_text_objects = all_text_objects
        if any(obj.source == "pdf_text_precise" for obj in all_text_objects):
            preferred_text_objects = [obj for obj in all_text_objects if obj.source == "pdf_text_precise"]
        elif any(obj.source.startswith("pdf_text") for obj in all_text_objects):
            preferred_text_objects = [obj for obj in all_text_objects if obj.source.startswith("pdf_text")]

        (
            ordered,
            baseline_font_size,
            title_candidates,
            index_by_object_id,
            model_anchors,
            product_name_anchors,
        ) = self._collect_anchor_candidates(preferred_text_objects)

        if not model_anchors and not product_name_anchors and preferred_text_objects is not all_text_objects:
            (
                ordered,
                baseline_font_size,
                title_candidates,
                index_by_object_id,
                model_anchors,
                product_name_anchors,
            ) = self._collect_anchor_candidates(all_text_objects)
        if not model_anchors and not product_name_anchors:
            return [], []

        image_candidates = [
            image for image in evidence.raw.images
            if _is_bindable_image(
                image,
                page_width=evidence.page_width,
                page_height=evidence.page_height,
            )
            and not _is_text_heavy_image(
                image,
                text_objects=all_text_objects,
                page_width=evidence.page_width,
                page_height=evidence.page_height,
            )
        ]
        records = []
        if model_anchors:
            for index, anchor, model_number in model_anchors:
                label_lines = self._collect_label_lines(
                    ordered,
                    model_number=model_number,
                    anchor=anchor,
                    page_width=evidence.page_width,
                )
                label_titles = [
                    parts[0]
                    for line in label_lines
                    if (parts := _extract_labeled_model_parts(line.text))
                ]
                if label_lines:
                    title = None
                    spec_lines = self._collect_spec_lines_for_lines(
                        ordered,
                        line_indices=[index_by_object_id[line.object_id] for line in label_lines if line.object_id in index_by_object_id],
                    )
                    attribute_lines = self._collect_attribute_lines_for_lines(
                        ordered,
                        line_indices=[index_by_object_id[line.object_id] for line in label_lines if line.object_id in index_by_object_id],
                    )
                    description_lines: list[EvidenceObject] = []
                else:
                    title = self._choose_title(
                        anchor,
                        title_candidates=title_candidates,
                        page_width=evidence.page_width,
                    )
                    spec_lines = self._collect_spec_lines(ordered, index)
                    attribute_lines = self._collect_attribute_lines(ordered, index)
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
                        "label_lines": label_lines,
                        "label_titles": list(dict.fromkeys(label_titles)),
                        "spec_lines": spec_lines,
                        "attribute_lines": attribute_lines,
                        "description_lines": description_lines,
                        "family_key": "/".join(dict.fromkeys(label_titles)) if label_titles else _model_family_key(model_number),
                    }
                )
                if not attribute_lines:
                    records[-1]["attribute_lines"] = self._collect_shared_color_lines(
                        ordered,
                        anchor_index=index,
                        anchor=anchor,
                        page_width=evidence.page_width,
                    )
        else:
            for index, anchor, product_name in product_name_anchors:
                records.append(
                    {
                        "anchor_index": index,
                        "anchor": anchor,
                        "model_number": None,
                        "title": None,
                        "label_lines": [],
                        "label_titles": [product_name],
                        "spec_lines": self._collect_spec_lines(ordered, index),
                        "description_lines": [],
                        "family_key": product_name,
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
            label_lines = record["label_lines"]
            label_titles = record["label_titles"]
            spec_lines = record["spec_lines"]
            attribute_lines = record.get("attribute_lines", [])
            description_lines = record["description_lines"]
            assigned_group = image_groups[record_index]
            primary_image_id = assigned_group[0].image_id if assigned_group else None
            inline_product_name = _extract_inline_product_name(anchor.text, model_number)

            component_lines = []
            if title and not label_titles:
                component_lines.append(_normalize_text(title.text))
            component_lines.extend(_normalize_text(line.text) for line in label_lines)
            component_lines.extend(_normalize_text(line.text) for line in description_lines)
            if not label_lines:
                component_lines.append(_normalize_text(anchor.text))
            component_lines.extend(_normalize_text(line.text) for line in spec_lines)
            component_lines.extend(_normalize_text(line.text) for line in attribute_lines)
            unique_lines = [line for line in dict.fromkeys(component_lines) if line]
            if not unique_lines:
                continue

            attributes: dict[str, str] = {
                "evidence_mode": "text_backed",
                "raw_attribute_text": " ".join(unique_lines),
                "product_description": " ".join(unique_lines),
            }
            if model_number:
                attributes["model_number"] = model_number
            if label_titles:
                attributes["product_name"] = " / ".join(label_titles)
            elif inline_product_name:
                attributes["product_name"] = inline_product_name
            elif title:
                attributes["product_name"] = _canonical_product_name(title.text, model_number)
            if spec_lines:
                attributes["specs"] = " ".join(
                    dict.fromkeys(_normalize_text(line.text) for line in spec_lines)
                )
            color_value = _extract_color_value(unique_lines)
            if color_value:
                attributes["color"] = color_value
            product_name = attributes.get("product_name")
            if product_name and _GENERIC_MODEL_VALUE_RE.fullmatch(_normalize_text(product_name)):
                attributes.pop("product_name", None)

            boxes = [anchor.bbox]
            if title:
                boxes.append(title.bbox)
            boxes.extend(line.bbox for line in label_lines)
            boxes.extend(line.bbox for line in description_lines)
            boxes.extend(line.bbox for line in spec_lines)
            boxes.extend(line.bbox for line in attribute_lines)
            if primary_image_id:
                image = next((item for item in assigned_group if item.image_id == primary_image_id), None)
                if image is not None and not _is_page_spanning_image(
                    image,
                    page_width=evidence.page_width,
                    page_height=evidence.page_height,
                ):
                    boxes.append(image.bbox)

            confidence = 0.7
            if title or label_titles:
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
        supplemented_groups = cls._supplement_image_groups(
            records=records,
            groups=pruned_groups,
            images=images,
            family_to_indices=family_to_indices,
            page_width=page_width,
            page_height=page_height,
        )
        return [
            cls._order_image_group(
                anchor=records[index]["anchor"],
                images=group,
                page_width=page_width,
                page_height=page_height,
            )
            for index, group in enumerate(supplemented_groups)
        ]

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
            image.bbox[3] <= primary_bbox[1] + max(primary_height * 0.16, 24.0)
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
            accepted = inside_seed or upper_band or vertical_stack
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

    @classmethod
    def _order_image_group(
        cls,
        *,
        anchor: EvidenceObject,
        images: list[ImageInfo],
        page_width: float,
        page_height: float,
    ) -> list[ImageInfo]:
        if len(images) <= 1:
            return images

        def primary_sort_key(image: ImageInfo) -> tuple[float, float]:
            anchor_score = cls._rank_image_for_anchor(
                anchor,
                image,
                page_width=page_width,
                page_height=page_height,
            )
            area_bonus = min(
                _area_ratio(image.bbox, page_width=page_width, page_height=page_height),
                0.35,
            ) * 620.0
            return (anchor_score[0] - area_bonus, anchor_score[1])

        primary = min(images, key=primary_sort_key)
        rest = [image for image in images if image.image_id != primary.image_id]
        rest.sort(
            key=lambda image: cls._rank_image_for_primary(
                primary,
                image,
                page_width=page_width,
                page_height=page_height,
            )
        )
        return [primary, *rest]

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
            if dx > max(180.0, page_width * 0.16):
                continue
            if (
                title.source == "ocr_text"
                and title.bbox[3] < anchor.bbox[1]
                and (anchor.bbox[1] - title.bbox[3]) > max(180.0, page_width * 0.12)
            ):
                continue
            if title.bbox[1] > anchor.bbox[3] and (title.bbox[1] - anchor.bbox[3]) > max(120.0, page_width * 0.09):
                continue
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
        same_row_siblings = _same_row_model_siblings(ordered, anchor_index)
        specs: list[EvidenceObject] = []
        scanned = 0
        for candidate in ordered[anchor_index + 1:]:
            scanned += 1
            if scanned > 18:
                break
            if _extract_model_token(candidate.text):
                same_row = abs(candidate.bbox[1] - anchor.bbox[1]) <= 24
                if same_row:
                    continue
                break
            if candidate.bbox[1] - anchor.bbox[3] > 150:
                break
            if _is_spec_line(candidate.text):
                x_distance = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
                sibling_distance = min(
                    (abs(_center(candidate.bbox)[0] - _center(sibling.bbox)[0]) for sibling in same_row_siblings),
                    default=float("inf"),
                )
                if sibling_distance + 8 < x_distance:
                    continue
                if x_distance <= 180 or _x_overlap_ratio(anchor.bbox, candidate.bbox) >= 0.2:
                    specs.append(candidate)
                elif specs:
                    break
            elif specs:
                x_distance = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
                if x_distance > 180:
                    continue
                break
        return specs

    @staticmethod
    def _collect_attribute_lines(ordered: list[EvidenceObject], anchor_index: int) -> list[EvidenceObject]:
        anchor = ordered[anchor_index]
        same_row_siblings = _same_row_model_siblings(ordered, anchor_index)
        attributes: list[EvidenceObject] = []
        scanned = 0
        for candidate in ordered[anchor_index + 1:]:
            scanned += 1
            if scanned > 18:
                break
            if _extract_model_token(candidate.text):
                same_row = abs(candidate.bbox[1] - anchor.bbox[1]) <= 24
                if same_row:
                    continue
                break
            if candidate.bbox[1] - anchor.bbox[3] > 150:
                break
            if _is_color_line(candidate.text):
                x_distance = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
                sibling_distance = min(
                    (abs(_center(candidate.bbox)[0] - _center(sibling.bbox)[0]) for sibling in same_row_siblings),
                    default=float("inf"),
                )
                if sibling_distance + 8 < x_distance:
                    continue
                if x_distance <= 220 or _x_overlap_ratio(anchor.bbox, candidate.bbox) >= 0.2:
                    attributes.append(candidate)
        return attributes

    @staticmethod
    def _collect_shared_color_lines(
        ordered: list[EvidenceObject],
        *,
        anchor_index: int,
        anchor: EvidenceObject,
        page_width: float,
    ) -> list[EvidenceObject]:
        shared: list[EvidenceObject] = []
        scanned = 0
        for candidate in ordered[anchor_index + 1:]:
            scanned += 1
            if scanned > 16:
                break
            if _page_half(candidate.bbox, page_width) != _page_half(anchor.bbox, page_width):
                continue
            if candidate.bbox[1] - anchor.bbox[3] > 180:
                break
            if not _is_color_line(candidate.text):
                continue
            dx = abs(_center(candidate.bbox)[0] - _center(anchor.bbox)[0])
            if dx <= max(220.0, page_width * 0.14) or _x_overlap_ratio(anchor.bbox, candidate.bbox) >= 0.12:
                shared.append(candidate)
        return shared

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
    def _collect_label_lines(
        ordered: list[EvidenceObject],
        *,
        model_number: str,
        anchor: EvidenceObject,
        page_width: float,
    ) -> list[EvidenceObject]:
        anchor_half = _page_half(anchor.bbox, page_width)
        selected: list[EvidenceObject] = []
        for candidate in ordered:
            parts = _extract_labeled_model_parts(candidate.text)
            if not parts or _model_group_key(parts[1]) != _model_group_key(model_number):
                continue
            if _page_half(candidate.bbox, page_width) != anchor_half:
                continue
            if abs(candidate.bbox[1] - anchor.bbox[1]) > 180:
                continue
            selected.append(candidate)
        return selected

    @classmethod
    def _collect_spec_lines_for_lines(
        cls,
        ordered: list[EvidenceObject],
        *,
        line_indices: list[int],
    ) -> list[EvidenceObject]:
        collected: list[EvidenceObject] = []
        seen_ids: set[str] = set()
        for line_index in sorted(dict.fromkeys(line_indices)):
            for candidate in cls._collect_spec_lines(ordered, line_index):
                if candidate.object_id in seen_ids:
                    continue
                seen_ids.add(candidate.object_id)
                collected.append(candidate)
        return collected

    @classmethod
    def _collect_attribute_lines_for_lines(
        cls,
        ordered: list[EvidenceObject],
        *,
        line_indices: list[int],
    ) -> list[EvidenceObject]:
        collected: list[EvidenceObject] = []
        seen_ids: set[str] = set()
        for line_index in sorted(dict.fromkeys(line_indices)):
            for candidate in cls._collect_attribute_lines(ordered, line_index):
                if candidate.object_id in seen_ids:
                    continue
                seen_ids.add(candidate.object_id)
                collected.append(candidate)
        return collected

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
        score -= min(_area_ratio(image.bbox, page_width=page_width, page_height=page_height), 0.25) * 420.0
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
        score -= min(_area_ratio(image.bbox, page_width=page_width, page_height=page_height), 0.25) * 180.0
        return (score, -image.short_edge)
