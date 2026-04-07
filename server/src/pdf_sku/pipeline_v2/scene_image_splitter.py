"""Split multi-panel scene pages, otherwise trim outer PDF background only."""
from __future__ import annotations

from collections import deque
import hashlib
import io
import math
from typing import Iterable

import numpy as np
from PIL import Image as PILImage

from pdf_sku.common.image_utils import flatten_for_jpeg
from pdf_sku.pipeline.ir import ImageInfo


def _trim_near_white_bbox(
    pil_img: PILImage.Image,
    *,
    threshold: int = 245,
) -> tuple[int, int, int, int] | None:
    arr = np.array(pil_img.convert("RGB"))
    mask = np.any(arr < threshold, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _mask_from_image(
    pil_img: PILImage.Image,
    *,
    threshold: int = 245,
    max_edge: int = 1024,
) -> tuple[np.ndarray, float]:
    rgb = pil_img.convert("RGB")
    width, height = rgb.size
    scale = min(1.0, max_edge / max(width, height))
    if scale < 1.0:
        sample = rgb.resize(
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            PILImage.Resampling.NEAREST,
        )
    else:
        sample = rgb
    arr = np.array(sample)
    mask = np.any(arr < threshold, axis=2)
    return mask, scale


def _split_bbox_by_whitespace(
    mask: np.ndarray,
    *,
    min_band_ratio: float = 0.015,
    max_dark_ratio: float = 0.01,
) -> tuple[str, int, int] | None:
    sample_h, sample_w = mask.shape
    best: tuple[int, str, int, int] | None = None
    for axis in ("x", "y"):
        values = mask.mean(axis=0 if axis == "x" else 1)
        min_band = max(8, int(round(len(values) * min_band_ratio)))
        start = None
        runs: list[tuple[int, int]] = []
        for index, value in enumerate(values):
            if value <= max_dark_ratio:
                if start is None:
                    start = index
            else:
                if start is not None and index - start >= min_band:
                    runs.append((start, index))
                start = None
        if start is not None and len(values) - start >= min_band:
            runs.append((start, len(values)))

        for band_start, band_end in runs:
            center = (band_start + band_end) // 2
            if center < len(values) * 0.08 or center > len(values) * 0.92:
                continue
            lhs = mask[:, :band_start] if axis == "x" else mask[:band_start, :]
            rhs = mask[:, band_end:] if axis == "x" else mask[band_end:, :]
            if lhs.size == 0 or rhs.size == 0:
                continue
            if lhs.mean() < 0.03 or rhs.mean() < 0.03:
                continue
            candidate = (band_end - band_start, axis, band_start, band_end)
            if best is None or candidate > best:
                best = candidate
    if best is None:
        return None
    return best[1], best[2], best[3]


def _xy_cut_panel_bboxes(
    pil_img: PILImage.Image,
    *,
    threshold: int = 245,
    max_edge: int = 1024,
    max_depth: int = 3,
) -> list[tuple[int, int, int, int]]:
    width, height = pil_img.size
    mask, scale = _mask_from_image(
        pil_img,
        threshold=threshold,
        max_edge=max_edge,
    )
    scale = max(scale, 1e-6)

    def recurse(
        submask: np.ndarray,
        *,
        offset_x: int,
        offset_y: int,
        depth: int,
    ) -> list[tuple[int, int, int, int]]:
        sample_h, sample_w = submask.shape
        if depth >= max_depth or sample_w < 120 or sample_h < 120:
            return [(offset_x, offset_y, offset_x + sample_w, offset_y + sample_h)]
        band = _split_bbox_by_whitespace(submask)
        if band is None:
            return [(offset_x, offset_y, offset_x + sample_w, offset_y + sample_h)]
        axis, band_start, band_end = band
        if axis == "x":
            return recurse(
                submask[:, :band_start],
                offset_x=offset_x,
                offset_y=offset_y,
                depth=depth + 1,
            ) + recurse(
                submask[:, band_end:],
                offset_x=offset_x + band_end,
                offset_y=offset_y,
                depth=depth + 1,
            )
        return recurse(
            submask[:band_start, :],
            offset_x=offset_x,
            offset_y=offset_y,
            depth=depth + 1,
        ) + recurse(
            submask[band_end:, :],
            offset_x=offset_x,
            offset_y=offset_y + band_end,
            depth=depth + 1,
        )

    sample_boxes = recurse(mask, offset_x=0, offset_y=0, depth=0)
    boxes: list[tuple[int, int, int, int]] = []
    for x0, y0, x1, y1 in sample_boxes:
        ox0 = max(0, int(math.floor(x0 / scale)))
        oy0 = max(0, int(math.floor(y0 / scale)))
        ox1 = min(width, int(math.ceil(x1 / scale)))
        oy1 = min(height, int(math.ceil(y1 / scale)))
        boxes.append((ox0, oy0, ox1, oy1))
    return boxes


def _detect_panel_bboxes(
    pil_img: PILImage.Image,
    *,
    threshold: int = 245,
    max_edge: int = 256,
) -> list[tuple[int, int, int, int]]:
    rgb = pil_img.convert("RGB")
    width, height = rgb.size
    scale = min(1.0, max_edge / max(width, height))
    if scale < 1.0:
        sample = rgb.resize(
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            PILImage.BILINEAR,
        )
    else:
        sample = rgb

    arr = np.array(sample)
    mask = np.any(arr < threshold, axis=2)
    sample_h, sample_w = mask.shape
    total_pixels = max(1, sample_h * sample_w)
    visited = np.zeros_like(mask, dtype=bool)
    components: list[tuple[int, int, int, int, int]] = []

    for y in range(sample_h):
        for x in range(sample_w):
            if not mask[y, x] or visited[y, x]:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited[y, x] = True
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while queue:
                cx, cy = queue.pop()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for ny in range(max(0, cy - 1), min(sample_h, cy + 2)):
                    for nx in range(max(0, cx - 1), min(sample_w, cx + 2)):
                        if visited[ny, nx] or not mask[ny, nx]:
                            continue
                        visited[ny, nx] = True
                        queue.append((nx, ny))
            components.append((min_x, min_y, max_x + 1, max_y + 1, area))

    filtered: list[tuple[int, int, int, int, float]] = []
    for x0, y0, x1, y1, area in components:
        box_w = x1 - x0
        box_h = y1 - y0
        box_area = max(1, box_w * box_h)
        area_ratio = area / total_pixels
        density = area / box_area
        if area_ratio < 0.015:
            continue
        if box_w < sample_w * 0.12 or box_h < sample_h * 0.12:
            continue
        if density < 0.35:
            continue
        filtered.append((x0, y0, x1, y1, area_ratio))

    filtered.sort(key=lambda item: (-item[4], item[1], item[0]))
    bboxes: list[tuple[int, int, int, int]] = []
    for x0, y0, x1, y1, _ratio in filtered:
        ox0 = max(0, int(math.floor(x0 / max(scale, 1e-6))))
        oy0 = max(0, int(math.floor(y0 / max(scale, 1e-6))))
        ox1 = min(width, int(math.ceil(x1 / max(scale, 1e-6))))
        oy1 = min(height, int(math.ceil(y1 / max(scale, 1e-6))))
        bboxes.append((ox0, oy0, ox1, oy1))
    return bboxes


class SceneImageSplitter:
    """Split into multiple scene panels when clearly present, else keep one trimmed image."""

    @staticmethod
    def _expand_bbox(
        bbox: tuple[int, int, int, int],
        *,
        pad: int,
        img_width: int,
        img_height: int,
    ) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = bbox
        return (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(img_width, x1 + pad),
            min(img_height, y1 + pad),
        )

    @staticmethod
    def _build_image_info(
        crop: PILImage.Image,
        *,
        crop_bbox: tuple[int, int, int, int],
        page_box: tuple[float, float, float, float],
        img_width: int,
        img_height: int,
        page_no: int,
        index: int,
    ) -> ImageInfo:
        scale_x = (page_box[2] - page_box[0]) / max(img_width, 1)
        scale_y = (page_box[3] - page_box[1]) / max(img_height, 1)
        x0, y0, x1, y1 = crop_bbox
        out = io.BytesIO()
        crop.save(out, format="JPEG", quality=90)
        crop_data = out.getvalue()
        pdf_bbox = (
            page_box[0] + x0 * scale_x,
            page_box[1] + y0 * scale_y,
            page_box[0] + x1 * scale_x,
            page_box[1] + y1 * scale_y,
        )
        short_edge = min(crop.width, crop.height)
        return ImageInfo(
            image_id=f"p{page_no}_scene_{index}",
            bbox=pdf_bbox,
            data=crop_data,
            width=crop.width,
            height=crop.height,
            short_edge=short_edge,
            search_eligible=short_edge >= 80,
            role="unknown",
            image_hash=hashlib.md5(crop_data[:2048]).hexdigest()[:12],
        )

    @staticmethod
    def _refine_crop_bbox(
        pil_img: PILImage.Image,
        bbox: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = bbox
        crop = pil_img.crop((x0, y0, x1, y1))
        trimmed = _trim_near_white_bbox(crop)
        if trimmed is None:
            return bbox
        tx0, ty0, tx1, ty1 = trimmed
        return (x0 + tx0, y0 + ty0, x0 + tx1, y0 + ty1)

    @classmethod
    def _build_images_from_bboxes(
        cls,
        *,
        base_img: PILImage.Image,
        panel_bboxes: Iterable[tuple[int, int, int, int]],
        pad: int,
        page_box: tuple[float, float, float, float],
        img_width: int,
        img_height: int,
        page_no: int,
    ) -> list[ImageInfo]:
        images: list[ImageInfo] = []
        for index, (x0, y0, x1, y1) in enumerate(panel_bboxes):
            crop_bbox = cls._expand_bbox(
                (x0, y0, x1, y1),
                pad=pad,
                img_width=img_width,
                img_height=img_height,
            )
            crop_bbox = cls._refine_crop_bbox(base_img, crop_bbox)
            crop = base_img.crop(crop_bbox)
            if crop.width < img_width * 0.12 or crop.height < img_height * 0.12:
                continue
            images.append(
                cls._build_image_info(
                    crop,
                    crop_bbox=crop_bbox,
                    page_box=page_box,
                    img_width=img_width,
                    img_height=img_height,
                    page_no=page_no,
                    index=index,
                )
            )
        return images

    @staticmethod
    def _mask_text_regions(
        pil_img: PILImage.Image,
        *,
        page_box: tuple[float, float, float, float],
        text_boxes: list[tuple[float, float, float, float]] | None = None,
    ) -> PILImage.Image:
        if not text_boxes:
            return pil_img

        img_width, img_height = pil_img.size
        masked = pil_img.copy()
        arr = np.array(masked.convert("RGB"))
        x_scale = img_width / max(page_box[2] - page_box[0], 1.0)
        y_scale = img_height / max(page_box[3] - page_box[1], 1.0)
        pad_x = max(2, int(round(img_width * 0.006)))
        pad_y = max(2, int(round(img_height * 0.008)))

        for bbox in text_boxes:
            if len(bbox) < 4:
                continue
            x0 = max(0, int(math.floor((bbox[0] - page_box[0]) * x_scale)) - pad_x)
            y0 = max(0, int(math.floor((bbox[1] - page_box[1]) * y_scale)) - pad_y)
            x1 = min(img_width, int(math.ceil((bbox[2] - page_box[0]) * x_scale)) + pad_x)
            y1 = min(img_height, int(math.ceil((bbox[3] - page_box[1]) * y_scale)) + pad_y)
            if x1 <= x0 or y1 <= y0:
                continue
            arr[y0:y1, x0:x1] = 255
        return PILImage.fromarray(arr)

    def extract(
        self,
        image: ImageInfo,
        *,
        page_no: int,
        page_width: float,
        page_height: float,
        raw_text: str = "",
        text_boxes: list[tuple[float, float, float, float]] | None = None,
    ) -> list[ImageInfo]:
        if not image.data or not image.image_id:
            return []

        with PILImage.open(io.BytesIO(image.data)) as raw_img:
            base_img = flatten_for_jpeg(raw_img)
            img_width, img_height = base_img.size
            page_box = image.bbox if image.bbox and len(image.bbox) >= 4 else (0.0, 0.0, page_width, page_height)
            panel_source = self._mask_text_regions(
                base_img,
                page_box=page_box,
                text_boxes=text_boxes,
            )
            pad = max(4, int(round(min(img_width, img_height) * 0.008)))

            whitespace_panels = _xy_cut_panel_bboxes(panel_source)
            if len(whitespace_panels) >= 2:
                images = self._build_images_from_bboxes(
                    base_img=base_img,
                    panel_bboxes=whitespace_panels,
                    pad=pad,
                    page_box=page_box,
                    img_width=img_width,
                    img_height=img_height,
                    page_no=page_no,
                )
                if len(images) >= 2:
                    return images

            panel_bboxes = _detect_panel_bboxes(panel_source)
            if len(panel_bboxes) >= 2:
                images = self._build_images_from_bboxes(
                    base_img=base_img,
                    panel_bboxes=panel_bboxes,
                    pad=pad,
                    page_box=page_box,
                    img_width=img_width,
                    img_height=img_height,
                    page_no=page_no,
                )
                if len(images) >= 2:
                    return images

            if len(panel_bboxes) == 1:
                panel_bbox = self._expand_bbox(panel_bboxes[0], pad=pad, img_width=img_width, img_height=img_height)
                panel_bbox = self._refine_crop_bbox(base_img, panel_bbox)
                x0, y0, x1, y1 = panel_bbox
                panel_area = max(1, (x1 - x0) * (y1 - y0))
                img_area = max(1, img_width * img_height)
                if panel_area / img_area >= 0.18:
                    crop = base_img.crop(panel_bbox)
                    if crop.width >= img_width * 0.12 and crop.height >= img_height * 0.12:
                        return [
                            self._build_image_info(
                                crop,
                                crop_bbox=panel_bbox,
                                page_box=page_box,
                                img_width=img_width,
                                img_height=img_height,
                                page_no=page_no,
                                index=0,
                            )
                        ]

            trimmed = _trim_near_white_bbox(panel_source)
            if trimmed is None:
                return []
            x0, y0, x1, y1 = trimmed
            if x1 - x0 >= img_width * 0.985 and y1 - y0 >= img_height * 0.985:
                return []

            crop = base_img.crop((x0, y0, x1, y1))
            if crop.width < img_width * 0.12 or crop.height < img_height * 0.12:
                return []
            return [
                self._build_image_info(
                    crop,
                    crop_bbox=(x0, y0, x1, y1),
                    page_box=page_box,
                    img_width=img_width,
                    img_height=img_height,
                    page_no=page_no,
                    index=0,
                )
            ]
