"""pipeline_v2 页面处理器。"""
from __future__ import annotations

import asyncio
import hashlib
import io
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import structlog
from PIL import Image as PILImage

from pdf_sku.common.image_utils import flatten_for_jpeg
from pdf_sku.pipeline.exporter.exporter import SKUIdGenerator
from pdf_sku.pipeline.layout_detector import LayoutRegion, detect_all_regions
from pdf_sku.pipeline.ir import BindingResult, ImageInfo, PageResult, ParsedPageIR, SKUResult, TextBlock
from pdf_sku.pipeline.parser.adapter import PDFExtractor
from pdf_sku.pipeline.parser.ocr_engine import OcrBlock, OcrEngine
from pdf_sku.settings import settings

from .models import TableDocumentContext
from .attribute_extractor import RegionAttributeExtractor
from .document_hints import build_document_hints, merge_document_hints
from .model_anchor_extractor import ModelAnchorExtractor
from .page_verifier import PageVerifier
from .region_proposer import RegionProposer
from .region_refiner import RegionRefiner
from .scene_image_splitter import SceneImageSplitter
from .table_preprocessor import TablePreprocessor

logger = structlog.get_logger()

_MIN_VISUAL_ONLY_AREA_RATIO = 0.003


def _extract_page_sync(file_path: str, page_no: int) -> ParsedPageIR:
    extractor = PDFExtractor()
    return extractor.extract(file_path, page_no)


def _count_pages_sync(file_path: str) -> int:
    import fitz

    doc = fitz.open(file_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def _render_page_screenshot_sync(
    file_path: str,
    page_no: int,
    dpi: int = 160,
    max_long_edge: int = 1800,
) -> bytes:
    import fitz

    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        zoom = dpi / 72
        width = page.rect.width * zoom
        height = page.rect.height * zoom
        long_edge = max(width, height)
        if long_edge > max_long_edge:
            zoom = zoom * max_long_edge / long_edge
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = PILImage.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=82)
        return buf.getvalue()
    finally:
        doc.close()


def _extract_precise_pdf_text_sync(
    file_path: str,
    page_no: int,
) -> list[dict]:
    import fitz

    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        blocks = page.get_text("dict").get("blocks", [])
        lines: list[dict] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span.get("text", "") for span in spans).strip()
                if not text:
                    continue
                font_size = max((float(span.get("size", 0.0)) for span in spans), default=0.0)
                lines.append(
                    {
                        "text": text,
                        "bbox": tuple(float(value) for value in line.get("bbox", (0, 0, 0, 0))),
                        "font_size": font_size,
                    }
                )
        return lines
    finally:
        doc.close()


class PageProcessor:
    """新 pipeline 的兼容入口。"""

    def __init__(
        self,
        llm_service=None,
        process_pool: ProcessPoolExecutor | None = None,
        config_provider=None,
        fallback_processor=None,
        allow_legacy_fallback: bool | None = None,
        legacy_processor=None,
    ) -> None:
        self._llm = llm_service
        self._pool = process_pool
        self._config = config_provider
        self._table = TablePreprocessor(llm_service=llm_service)
        self._region_proposer = RegionProposer(
            min_visual_only_area_ratio=_MIN_VISUAL_ONLY_AREA_RATIO,
        )
        self._model_extractor = ModelAnchorExtractor()
        self._region_refiner = RegionRefiner(llm_service=llm_service)
        self._region_extractor = RegionAttributeExtractor()
        self._page_verifier = PageVerifier(llm_service=llm_service)
        self._scene_splitter = SceneImageSplitter()
        self._id_gen = SKUIdGenerator()
        self._ocr_engine = OcrEngine()
        self._job_contexts: dict[str, TableDocumentContext] = {}
        self._job_locks: dict[str, asyncio.Lock] = {}
        if fallback_processor is None and legacy_processor is not None:
            fallback_processor = legacy_processor
        self._fallback = fallback_processor
        self._allow_legacy_fallback = (
            settings.pipeline_v2_allow_legacy_fallback
            if allow_legacy_fallback is None else allow_legacy_fallback
        )

    def _get_lock(self, job_id: str) -> asyncio.Lock:
        if job_id not in self._job_locks:
            self._job_locks[job_id] = asyncio.Lock()
        return self._job_locks[job_id]

    async def _extract_page(self, file_path: str, page_no: int) -> ParsedPageIR:
        loop = asyncio.get_running_loop()
        if self._pool:
            return await loop.run_in_executor(self._pool, _extract_page_sync, file_path, page_no)
        return _extract_page_sync(file_path, page_no)

    async def _count_pages(self, file_path: str) -> int:
        loop = asyncio.get_running_loop()
        if self._pool:
            return await loop.run_in_executor(self._pool, _count_pages_sync, file_path)
        return _count_pages_sync(file_path)

    async def _build_sampled_document_hints(
        self,
        file_path: str,
        *,
        first_page_raw: ParsedPageIR,
    ):
        sampled_pages = [first_page_raw]
        try:
            page_count = await self._count_pages(file_path)
        except Exception:
            page_count = 1

        if page_count > 1:
            last_page = await self._extract_page(file_path, page_count)
            sampled_pages.append(last_page)
        return build_document_hints(sampled_pages=sampled_pages)

    async def _ensure_job_context(self, job_id: str, file_path: str) -> TableDocumentContext:
        cached = self._job_contexts.get(job_id)
        if cached is not None:
            return cached

        async with self._get_lock(job_id):
            cached = self._job_contexts.get(job_id)
            if cached is not None:
                return cached

            first_page_raw = await self._extract_page(file_path, 1)
            schema = self._table.build_schema(first_page_raw, source_page=1)
            document_hints = await self._build_sampled_document_hints(
                file_path,
                first_page_raw=first_page_raw,
            )
            context = TableDocumentContext(
                job_id=job_id,
                table_pdf_mode=schema is not None,
                schema=schema,
                first_page_raw=first_page_raw,
                document_hints=document_hints,
            )
            self._job_contexts[job_id] = context
            logger.info(
                "pipeline_v2_context_initialized",
                job_id=job_id,
                table_pdf_mode=context.table_pdf_mode,
                schema_id=schema.table_schema_id if schema else None,
            )
            return context

    @staticmethod
    def _row_confidence(source: str, filled_fields: int) -> float:
        base = 0.9 if source == "table_rows" else 0.75
        return min(0.98, base + min(0.08, filled_fields * 0.01))

    async def _process_table_page(
        self,
        context: TableDocumentContext,
        *,
        file_path: str,
        page_no: int,
        file_hash: str,
    ) -> PageResult:
        raw = context.first_page_raw if page_no == 1 and context.first_page_raw else await self._extract_page(file_path, page_no)
        self._prepare_images(raw, page_no=page_no)
        schema = context.schema
        if schema is None:
            return PageResult(
                status="AI_FAILED",
                error="table schema missing",
                needs_review=True,
            )

        precise_text_lines: list[TextBlock] = []
        if not raw.tables:
            try:
                precise_objects = await self._extract_precise_pdf_text_objects(file_path, page_no)
                precise_text_lines = [
                    TextBlock(content=obj.text, bbox=obj.bbox, font_size=obj.font_size)
                    for obj in precise_objects
                    if (obj.text or "").strip()
                ]
            except Exception:
                precise_text_lines = []

        rows = self._table.extract_rows(
            raw,
            schema,
            precise_text_lines=precise_text_lines,
        )
        if not rows and self._llm:
            screenshot = None
            try:
                screenshot = await self._render_page_screenshot(file_path, page_no)
            except Exception:
                screenshot = None
            rows = await self._table.fallback_rows_with_llm(
                raw,
                schema,
                screenshot=screenshot,
            )
        skus: list[SKUResult] = []
        for row in rows:
            attributes = self._table.row_to_attributes(row)
            if not attributes:
                continue
            skus.append(
                SKUResult(
                    sku_id="",
                    attributes=attributes,
                    source_bbox=row.bbox,
                    validity="valid",
                    confidence=self._row_confidence(row.source, len(row.values)),
                    extraction_method="table_schema_v2",
                )
            )

        hash_prefix = (file_hash or hashlib.md5(file_path.encode("utf-8")).hexdigest())[:8]
        skus = self._id_gen.assign_ids(
            skus,
            hash_prefix=hash_prefix,
            page_no=page_no,
            page_height=raw.metadata.page_height or 1.0,
        )
        bindings = self._build_table_bindings(raw, rows, skus)

        extraction_method = "table_schema_v2"
        row_sources = {row.source for row in rows}
        if "precise_text_lines" in row_sources:
            extraction_method = "table_image_rows_v2"
        elif "llm_table_fallback" in row_sources:
            extraction_method = "table_fallback_v2"

        logger.info(
            "pipeline_v2_table_page_processed",
            page_no=page_no,
            rows=len(rows),
            skus=len(skus),
            schema_id=schema.table_schema_id,
        )
        return PageResult(
            status="AI_COMPLETED",
            page_type="A",
            needs_review=not bool(skus),
            skus=skus,
            images=raw.images,
            bindings=bindings,
            classification_confidence=1.0,
            extraction_method=extraction_method,
            fitz_page_class="TABLE",
        )

    async def process_page(
        self,
        job_id: str,
        file_path: str,
        page_no: int,
        file_hash: str = "",
        category: str | None = None,
        frozen_config_version: str | None = None,
        catalog_profile=None,
    ) -> PageResult:
        context = await self._ensure_job_context(job_id, file_path)
        document_hints = merge_document_hints(
            context.document_hints,
            build_document_hints(
                category=category,
                catalog_profile=catalog_profile,
            ),
        )
        if context.table_pdf_mode:
            return await self._process_table_page(
                context,
                file_path=file_path,
                page_no=page_no,
                file_hash=file_hash,
            )

        raw = context.first_page_raw if page_no == 1 and context.first_page_raw else await self._extract_page(file_path, page_no)
        result = await self._process_regular_page(
            raw,
            file_path=file_path,
            file_hash=file_hash,
            page_no=page_no,
            document_hints=document_hints,
        )
        if result.status == "SKIPPED":
            return result
        if result.status == "AI_COMPLETED" and result.skus:
            return result

        if not self._allow_legacy_fallback:
            return result

        fallback = self._get_legacy_fallback()
        logger.info("pipeline_v2_fallback_legacy", job_id=job_id, page_no=page_no)
        return await fallback.process_page(
            job_id=job_id,
            file_path=file_path,
            page_no=page_no,
            file_hash=file_hash,
            category=category,
            frozen_config_version=frozen_config_version,
            catalog_profile=catalog_profile,
        )

    def clear_job_cache(self, job_id: str) -> None:
        self._job_contexts.pop(job_id, None)
        self._job_locks.pop(job_id, None)
        if self._fallback is not None and hasattr(self._fallback, "clear_job_cache"):
            self._fallback.clear_job_cache(job_id)

    def _get_legacy_fallback(self):
        if self._fallback is None:
            from pdf_sku.pipeline.page_processor import PageProcessor as LegacyPageProcessor

            self._fallback = LegacyPageProcessor(
                llm_service=self._llm,
                process_pool=self._pool,
                config_provider=self._config,
            )
        return self._fallback

    @staticmethod
    def _page_type(raw: ParsedPageIR) -> str:
        if raw.tables:
            return "A"
        if raw.images and raw.text_blocks:
            return "B"
        if raw.images:
            return "C"
        return "B"

    @staticmethod
    def _is_blank(raw: ParsedPageIR) -> bool:
        return not raw.tables and not raw.images and not any((block.content or "").strip() for block in raw.text_blocks)

    @staticmethod
    def _looks_like_tile_page(images: list[ImageInfo]) -> bool:
        candidates = [
            image
            for image in images
            if image.width > 0 and image.height > 0 and image.bbox != (0, 0, 0, 0)
        ]
        if len(candidates) < 30:
            return False
        small_count = sum(1 for image in candidates if min(image.width, image.height) < 200)
        return small_count >= len(candidates) * 0.7

    @staticmethod
    def _compose_tile_cluster_image(
        screenshot_img: PILImage.Image,
        *,
        bbox: tuple[float, float, float, float],
        page_width: float,
        page_height: float,
        page_no: int,
        index: int,
    ) -> ImageInfo | None:
        screen_width, screen_height = screenshot_img.size
        if screen_width <= 0 or screen_height <= 0 or page_width <= 0 or page_height <= 0:
            return None

        x0 = max(0, int((bbox[0] / page_width) * screen_width))
        y0 = max(0, int((bbox[1] / page_height) * screen_height))
        x1 = min(screen_width, int((bbox[2] / page_width) * screen_width))
        y1 = min(screen_height, int((bbox[3] / page_height) * screen_height))
        if x1 <= x0 or y1 <= y0:
            return None

        crop = screenshot_img.crop((x0, y0, x1, y1))
        if crop.width <= 1 or crop.height <= 1:
            return None

        out = io.BytesIO()
        crop.save(out, format="JPEG", quality=88)
        crop_data = out.getvalue()
        short_edge = min(crop.width, crop.height)
        return ImageInfo(
            image_id=f"p{page_no}_composite_{index}",
            bbox=bbox,
            data=crop_data,
            width=crop.width,
            height=crop.height,
            short_edge=short_edge,
            role="unknown",
            search_eligible=short_edge >= 80,
            image_hash=hashlib.md5(crop_data[:2048]).hexdigest()[:12],
        )

    @classmethod
    def _merge_tile_fragments(
        cls,
        raw: ParsedPageIR,
        *,
        screenshot: bytes | None,
        page_no: int,
    ) -> None:
        if not cls._looks_like_tile_page(raw.images) or not screenshot:
            return

        valid_indices = [
            index
            for index, image in enumerate(raw.images)
            if image.bbox != (0, 0, 0, 0)
        ]
        if len(valid_indices) < 30:
            return

        parent = {index: index for index in valid_indices}
        rank = {index: 0 for index in valid_indices}

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left == root_right:
                return
            if rank[root_left] < rank[root_right]:
                root_left, root_right = root_right, root_left
            parent[root_right] = root_left
            if rank[root_left] == rank[root_right]:
                rank[root_left] += 1

        gap = 5.0
        for pos, left in enumerate(valid_indices):
            left_box = raw.images[left].bbox
            for right in valid_indices[pos + 1:]:
                right_box = raw.images[right].bbox
                horizontally_adjacent = left_box[0] < right_box[2] + gap and right_box[0] < left_box[2] + gap
                vertically_adjacent = left_box[1] < right_box[3] + gap and right_box[1] < left_box[3] + gap
                if horizontally_adjacent and vertically_adjacent:
                    union(left, right)

        clusters: dict[int, list[int]] = defaultdict(list)
        for index in valid_indices:
            clusters[find(index)].append(index)

        try:
            with PILImage.open(io.BytesIO(screenshot)) as screenshot_img:
                normalized_screenshot = flatten_for_jpeg(screenshot_img)
        except Exception:
            return

        merged: list[ImageInfo] = []
        composite_count = 0
        for members in clusters.values():
            if len(members) == 1:
                image = raw.images[members[0]]
                native_short = min(image.width, image.height) if image.width and image.height else 0
                if native_short < 200:
                    image.is_fragmented = True
                    image.search_eligible = False
                merged.append(image)
                continue

            union_bbox = (
                min(raw.images[index].bbox[0] for index in members),
                min(raw.images[index].bbox[1] for index in members),
                max(raw.images[index].bbox[2] for index in members),
                max(raw.images[index].bbox[3] for index in members),
            )
            composite = cls._compose_tile_cluster_image(
                normalized_screenshot,
                bbox=union_bbox,
                page_width=raw.metadata.page_width,
                page_height=raw.metadata.page_height,
                page_no=page_no,
                index=composite_count,
            )
            if composite is not None:
                merged.append(composite)
                composite_count += 1

            for index in members:
                image = raw.images[index]
                image.is_fragmented = True
                image.search_eligible = False
                merged.append(image)

        if composite_count == 0:
            return

        raw.images = merged
        logger.info(
            "pipeline_v2_tile_fragments_merged",
            page_no=page_no,
            original_count=len(valid_indices),
            composite_count=composite_count,
            total_images=len(raw.images),
        )

    @staticmethod
    def _trim_image_background(image: ImageInfo, raw: ParsedPageIR) -> None:
        if not image.data or image.bbox == (0, 0, 0, 0):
            return
        try:
            with PILImage.open(io.BytesIO(image.data)) as pil_img:
                normalized = flatten_for_jpeg(pil_img)
                arr = np.array(normalized.convert("RGB"))
        except Exception:
            return

        mask = np.any(arr < 245, axis=2)
        ys, xs = np.where(mask)
        if len(xs) == 0 or len(ys) == 0:
            return
        x0 = int(xs.min())
        y0 = int(ys.min())
        x1 = int(xs.max()) + 1
        y1 = int(ys.max()) + 1
        original_width, original_height = normalized.size
        if (
            x0 <= max(2, int(original_width * 0.01))
            and y0 <= max(2, int(original_height * 0.01))
            and x1 >= original_width - max(2, int(original_width * 0.01))
            and y1 >= original_height - max(2, int(original_height * 0.01))
        ):
            return
        if x1 - x0 < original_width * 0.25 or y1 - y0 < original_height * 0.25:
            return

        cropped = normalized.crop((x0, y0, x1, y1))
        out = io.BytesIO()
        cropped.save(out, format="JPEG", quality=88)
        image.data = out.getvalue()
        image.width = cropped.width
        image.height = cropped.height
        image.short_edge = min(cropped.width, cropped.height)

        scale_x = (image.bbox[2] - image.bbox[0]) / max(original_width, 1)
        scale_y = (image.bbox[3] - image.bbox[1]) / max(original_height, 1)
        image.bbox = (
            image.bbox[0] + x0 * scale_x,
            image.bbox[1] + y0 * scale_y,
            image.bbox[0] + x1 * scale_x,
            image.bbox[1] + y1 * scale_y,
        )

    def _prepare_images(
        self,
        raw: ParsedPageIR,
        *,
        screenshot: bytes | None = None,
        page_no: int,
    ) -> None:
        seen_image_ids: set[str] = set()
        for index, image in enumerate(raw.images):
            candidate_id = (image.image_id or "").strip() or f"image_{index}"
            if candidate_id in seen_image_ids:
                candidate_id = f"{candidate_id}_{index}"
            image.image_id = candidate_id
            seen_image_ids.add(candidate_id)
        self._merge_tile_fragments(raw, screenshot=screenshot, page_no=page_no)

        seen_image_ids.clear()
        for index, image in enumerate(raw.images):
            candidate_id = (image.image_id or "").strip() or f"image_{index}"
            if candidate_id in seen_image_ids:
                candidate_id = f"{candidate_id}_{index}"
            image.image_id = candidate_id
            seen_image_ids.add(candidate_id)
            if image.is_fragmented:
                image.search_eligible = False
                continue
            self._trim_image_background(image, raw)
            if image.short_edge <= 0 and image.width and image.height:
                image.short_edge = min(image.width, image.height)
            if not image.search_eligible:
                if image.short_edge >= 80:
                    image.search_eligible = True
                elif image.bbox != (0, 0, 0, 0):
                    width = max(0.0, image.bbox[2] - image.bbox[0])
                    height = max(0.0, image.bbox[3] - image.bbox[1])
                    if min(width, height) >= 60:
                        image.search_eligible = True

    @staticmethod
    def _primary_image_id(region_image_ids: list[str], image_map: dict[str, ImageInfo]) -> str | None:
        if not region_image_ids:
            return None
        ranked = sorted(
            region_image_ids,
            key=lambda image_id: (
                max(0.0, image_map[image_id].bbox[2] - image_map[image_id].bbox[0]) *
                max(0.0, image_map[image_id].bbox[3] - image_map[image_id].bbox[1]),
                image_map[image_id].short_edge,
            ),
            reverse=True,
        )
        return ranked[0] if ranked else None

    @staticmethod
    def _build_table_bindings(
        raw: ParsedPageIR,
        rows,
        skus: list[SKUResult],
    ) -> list[BindingResult]:
        eligible_images = [
            image
            for image in raw.images
            if image.search_eligible and image.image_id and image.bbox != (0, 0, 0, 0)
        ]
        if not eligible_images:
            return [
                BindingResult(
                    sku_id=sku.sku_id,
                    image_id=None,
                    confidence=0.0,
                    method="table_row_image",
                    is_ambiguous=False,
                    rank=1,
                )
                for sku in skus
            ]

        bindings: list[BindingResult] = []
        for row, sku in zip(rows, skus, strict=False):
            row_center_y = (row.bbox[1] + row.bbox[3]) / 2 if row.bbox != (0, 0, 0, 0) else 0.0
            row_center_x = (row.bbox[0] + row.bbox[2]) / 2 if row.bbox != (0, 0, 0, 0) else 0.0
            best = min(
                eligible_images,
                key=lambda image: (
                    abs(((image.bbox[1] + image.bbox[3]) / 2) - row_center_y),
                    abs(((image.bbox[0] + image.bbox[2]) / 2) - row_center_x),
                ),
            )
            best.role = "product_main"
            bindings.append(
                BindingResult(
                    sku_id=sku.sku_id,
                    image_id=best.image_id,
                    confidence=0.86,
                    method="table_row_image",
                    is_ambiguous=False,
                    rank=1,
                )
            )
        return bindings

    @staticmethod
    def _is_full_page_image(image: ImageInfo, raw: ParsedPageIR) -> bool:
        if image.bbox == (0, 0, 0, 0):
            return False
        page_area = max(1.0, raw.metadata.page_width * raw.metadata.page_height)
        image_area = max(0.0, image.bbox[2] - image.bbox[0]) * max(0.0, image.bbox[3] - image.bbox[1])
        return image_area / page_area >= 0.55

    def _scene_image_group_for_single_sku(
        self,
        raw: ParsedPageIR,
        skus: list[SKUResult],
        *,
        page_no: int,
        text_boxes: list[tuple[float, float, float, float]] | None = None,
    ) -> list[list[str]] | None:
        if not skus:
            return None
        bindable_images = [
            image for image in raw.images
            if image.search_eligible and image.bbox != (0, 0, 0, 0)
        ]
        if len(bindable_images) != 1:
            return None
        eligible = [
            image for image in raw.images
            if image.search_eligible and image.data and self._is_full_page_image(image, raw)
        ]
        if len(eligible) != 1:
            return None

        original = eligible[0]
        split_images = self._scene_splitter.extract(
            original,
            page_no=page_no,
            page_width=raw.metadata.page_width,
            page_height=raw.metadata.page_height,
            raw_text=raw.raw_text,
            text_boxes=text_boxes or [
                block.bbox
                for block in raw.text_blocks
                if (block.content or "").strip()
            ],
        )
        if not split_images:
            return None

        original.role = "scene_full"
        original.search_eligible = False
        raw.images.extend(split_images)
        if len(skus) == 1:
            return [[image.image_id for image in split_images if image.image_id]]
        return self._assign_scene_images_to_skus(
            skus=skus,
            split_images=split_images,
            page_width=raw.metadata.page_width,
            page_height=raw.metadata.page_height,
        )

    @staticmethod
    def _scene_image_score(
        sku_bbox: tuple[float, float, float, float],
        image_bbox: tuple[float, float, float, float],
        *,
        page_width: float,
        page_height: float,
    ) -> float:
        sku_cx = (sku_bbox[0] + sku_bbox[2]) / 2
        sku_cy = (sku_bbox[1] + sku_bbox[3]) / 2
        img_cx = (image_bbox[0] + image_bbox[2]) / 2
        img_cy = (image_bbox[1] + image_bbox[3]) / 2
        diag = max(1.0, (page_width ** 2 + page_height ** 2) ** 0.5)
        center_distance = ((sku_cx - img_cx) ** 2 + (sku_cy - img_cy) ** 2) ** 0.5 / diag
        horizontal_distance = abs(sku_cx - img_cx) / max(1.0, page_width)
        image_below_text_penalty = max(0.0, image_bbox[1] - sku_bbox[3]) / max(1.0, page_height)
        image_above_text_gap = max(0.0, sku_bbox[1] - image_bbox[3]) / max(1.0, page_height)
        x_overlap = max(0.0, min(sku_bbox[2], image_bbox[2]) - max(sku_bbox[0], image_bbox[0]))
        x_overlap_ratio = x_overlap / max(
            1.0,
            min(max(1.0, sku_bbox[2] - sku_bbox[0]), max(1.0, image_bbox[2] - image_bbox[0])),
        )
        return (
            center_distance
            + horizontal_distance * 0.65
            + image_below_text_penalty * 1.5
            + image_above_text_gap * 0.35
            - x_overlap_ratio * 0.25
        )

    @staticmethod
    def _normalize_spu_key(value: str | None) -> str | None:
        if not value:
            return None
        normalized = " ".join(str(value).strip().split())
        if not normalized:
            return None
        return normalized.lower()

    @classmethod
    def _shared_scene_primary_image_id(
        cls,
        *,
        sku: SKUResult,
        split_images: list[ImageInfo],
        page_width: float,
        page_height: float,
    ) -> str | None:
        best_image: ImageInfo | None = None
        best_score: tuple[float, float] | None = None
        for image in split_images:
            if not image.image_id:
                continue
            area_ratio = (
                max(0.0, image.bbox[2] - image.bbox[0]) *
                max(0.0, image.bbox[3] - image.bbox[1])
            ) / max(1.0, page_width * page_height)
            score = cls._scene_image_score(
                sku.source_bbox,
                image.bbox,
                page_width=page_width,
                page_height=page_height,
            ) - min(area_ratio, 0.35) * 0.65
            key = (score, -image.short_edge)
            if best_score is None or key < best_score:
                best_score = key
                best_image = image
        return best_image.image_id if best_image and best_image.image_id else None

    @classmethod
    def _share_scene_images_across_spu_groups(
        cls,
        *,
        skus: list[SKUResult],
        split_images: list[ImageInfo],
        groups: list[list[str]],
        page_width: float,
        page_height: float,
    ) -> list[list[str]]:
        updated = [list(dict.fromkeys(group)) for group in groups]
        image_lookup = {
            image.image_id: image
            for image in split_images
            if image.image_id
        }
        cluster_map: dict[tuple[str, str], list[int]] = {}
        for index, sku in enumerate(skus):
            spu_key = cls._normalize_spu_key(sku.attributes.get("product_name"))
            if not spu_key:
                continue
            primary_image_id = cls._shared_scene_primary_image_id(
                sku=sku,
                split_images=split_images,
                page_width=page_width,
                page_height=page_height,
            )
            if not primary_image_id:
                continue
            cluster_map.setdefault((spu_key, primary_image_id), []).append(index)

        for (_spu_key, primary_image_id), indices in cluster_map.items():
            if len(indices) <= 1:
                continue
            centers = [cls._bbox_center(skus[index].source_bbox) for index in indices]
            if centers:
                x_span = max(point[0] for point in centers) - min(point[0] for point in centers)
                y_span = max(point[1] for point in centers) - min(point[1] for point in centers)
                if x_span > max(360.0, page_width * 0.24) or y_span > max(240.0, page_height * 0.22):
                    continue
            shared = [primary_image_id]
            for index in indices:
                shared.extend(updated[index])
            shared = [image_id for image_id in dict.fromkeys(shared) if image_id in image_lookup]
            for index in indices:
                shared_rest = sorted(
                    [image_id for image_id in shared if image_id != primary_image_id],
                    key=lambda image_id: cls._scene_image_score(
                        skus[index].source_bbox,
                        image_lookup[image_id].bbox,
                        page_width=page_width,
                        page_height=page_height,
                    ),
                )
                shared_sorted = [primary_image_id, *shared_rest]
                updated[index] = shared_sorted
        return updated

    @classmethod
    def _assign_scene_images_to_skus(
        cls,
        *,
        skus: list[SKUResult],
        split_images: list[ImageInfo],
        page_width: float,
        page_height: float,
    ) -> list[list[str]] | None:
        if not skus or not split_images:
            return None
        groups: list[list[str]] = [[] for _ in skus]

        pair_scores: list[tuple[float, int, int]] = []
        for sku_index, sku in enumerate(skus):
            for image_index, image in enumerate(split_images):
                pair_scores.append(
                    (
                        cls._scene_image_score(
                            sku.source_bbox,
                            image.bbox,
                            page_width=page_width,
                            page_height=page_height,
                        ),
                        sku_index,
                        image_index,
                    )
                )
        pair_scores.sort(key=lambda item: item[0])

        assigned_skus: set[int] = set()
        assigned_images: set[int] = set()
        for _score, sku_index, image_index in pair_scores:
            if sku_index in assigned_skus or image_index in assigned_images:
                continue
            groups[sku_index].append(split_images[image_index].image_id)
            assigned_skus.add(sku_index)
            assigned_images.add(image_index)
            if len(assigned_images) == min(len(skus), len(split_images)):
                break

        for image_index, image in enumerate(split_images):
            if image_index in assigned_images:
                continue
            best_sku_index = min(
                range(len(skus)),
                key=lambda sku_index: cls._scene_image_score(
                    skus[sku_index].source_bbox,
                    image.bbox,
                    page_width=page_width,
                    page_height=page_height,
                ),
            )
            groups[best_sku_index].append(image.image_id)

        if not any(groups):
            return None
        return cls._share_scene_images_across_spu_groups(
            skus=skus,
            split_images=split_images,
            groups=groups,
            page_width=page_width,
            page_height=page_height,
        )

    @staticmethod
    def _bboxes_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

    @staticmethod
    def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

    @staticmethod
    def _screenshot_size(screenshot: bytes | None) -> tuple[int, int] | None:
        if not screenshot:
            return None
        try:
            with PILImage.open(io.BytesIO(screenshot)) as image:
                return image.size
        except Exception:
            return None

    async def _render_page_screenshot(
        self,
        file_path: str,
        page_no: int,
        *,
        dpi: int = 160,
        max_long_edge: int = 1800,
    ) -> bytes | None:
        loop = asyncio.get_running_loop()
        if self._pool:
            return await loop.run_in_executor(
                self._pool,
                _render_page_screenshot_sync,
                file_path,
                page_no,
                dpi,
                max_long_edge,
            )
        return _render_page_screenshot_sync(file_path, page_no, dpi=dpi, max_long_edge=max_long_edge)

    async def _run_ocr(self, screenshot: bytes | None) -> list[OcrBlock]:
        if not screenshot or not settings.ocr_enabled:
            return []
        loop = asyncio.get_event_loop()
        if self._pool:
            return await loop.run_in_executor(self._pool, self._ocr_engine.run, screenshot)
        return self._ocr_engine.run(screenshot)

    async def _run_layout_detection(self, screenshot: bytes | None) -> list[LayoutRegion]:
        if not screenshot or not settings.layout_detect_enabled:
            return []
        try:
            loop = asyncio.get_event_loop()
            if self._pool:
                return await loop.run_in_executor(self._pool, detect_all_regions, screenshot)
            return detect_all_regions(screenshot)
        except Exception:
            return []

    @staticmethod
    def _needs_precise_pdf_text(raw: ParsedPageIR) -> bool:
        if not raw.text_blocks:
            return False
        page_area = max(1.0, raw.metadata.page_width * raw.metadata.page_height)
        for block in raw.text_blocks:
            width = max(0.0, block.bbox[2] - block.bbox[0])
            height = max(0.0, block.bbox[3] - block.bbox[1])
            block_area = width * height
            if block_area / page_area >= 0.55 and (block.content or "").count("\n") >= 4:
                return True
        return len(raw.text_blocks) == 1 and bool((raw.text_blocks[0].content or "").strip())

    async def _extract_precise_pdf_text_objects(self, file_path: str, page_no: int):
        from .models import EvidenceObject

        loop = asyncio.get_running_loop()
        if self._pool:
            rows = await loop.run_in_executor(self._pool, _extract_precise_pdf_text_sync, file_path, page_no)
        else:
            rows = _extract_precise_pdf_text_sync(file_path, page_no)
        objects = []
        for index, row in enumerate(rows):
            objects.append(
                EvidenceObject(
                    object_id=f"pdfline_{index}",
                    object_type="text_block",
                    bbox=row["bbox"],
                    text=row["text"],
                    source="pdf_text_precise",
                    confidence=1.0,
                    font_size=row["font_size"],
                )
            )
        return objects

    def _build_regular_page_result(
        self,
        raw: ParsedPageIR,
        evidence,
        proposals,
        skus: list[SKUResult] | None = None,
        *,
        file_hash: str,
        page_no: int,
        preferred_image_ids: list[str | None] | None = None,
        preferred_image_groups: list[list[str]] | None = None,
        page_extraction_method: str = "region_rule_v2",
    ) -> PageResult:
        if not proposals and not skus:
            return PageResult(
                status="AI_FAILED",
                page_type=self._page_type(raw),
                error="no_region_proposals",
                needs_review=True,
            )

        image_lookup = {
            image.image_id: image
            for image in raw.images
        }
        skus = list(skus or [])
        bindings: list[BindingResult] = []
        if not skus:
            for proposal in proposals:
                attrs = self._region_extractor.extract(proposal, evidence)
                if attrs.get("evidence_mode") == "visual_only":
                    confidence = max(0.35, proposal.score)
                else:
                    confidence = max(0.55, proposal.score)

                sku = SKUResult(
                    sku_id="",
                    attributes=attrs,
                    source_bbox=proposal.bbox,
                    validity="valid",
                    confidence=confidence,
                    extraction_method="region_rule_v2",
                )
                skus.append(sku)

        if preferred_image_groups is None and preferred_image_ids is not None:
            preferred_image_groups = [[image_id] if image_id else [] for image_id in preferred_image_ids]
        if preferred_image_groups and len(preferred_image_groups) != len(skus):
            preferred_image_groups = None

        if preferred_image_groups:
            page_h = max(1.0, raw.metadata.page_height or 1.0)

            def sort_key(item: tuple[SKUResult, list[str]]):
                sku, _group = item
                y = sku.source_bbox[1] / page_h if len(sku.source_bbox) >= 4 else 0
                x = sku.source_bbox[0] / page_h if len(sku.source_bbox) >= 4 else 0
                return (round(y, 2), round(x, 2))

            paired = sorted(zip(skus, preferred_image_groups, strict=False), key=sort_key)
            skus = [sku for sku, _ in paired]
            preferred_image_groups = [group for _, group in paired]

        hash_prefix = (file_hash or hashlib.md5(str(page_no).encode("utf-8")).hexdigest())[:8]
        skus = self._id_gen.assign_ids(
            skus,
            hash_prefix=hash_prefix,
            page_no=page_no,
            page_height=raw.metadata.page_height or 1.0,
        )

        for sku_index, sku in enumerate(skus):
            preferred_image_id = None
            preferred_group = preferred_image_groups[sku_index] if preferred_image_groups else None
            region_image_ids = [
                object_id for object_id, image in image_lookup.items()
                if image.bbox != (0, 0, 0, 0) and self._bboxes_intersect(sku.source_bbox, image.bbox)
            ]
            if preferred_group:
                region_image_ids = [
                    image_id
                    for image_id in dict.fromkeys(preferred_group)
                    if image_id in image_lookup
                ]
                primary_image_id = region_image_ids[0] if region_image_ids else None
            else:
                if preferred_image_ids:
                    preferred_image_id = preferred_image_ids[sku_index]
                if preferred_image_id and preferred_image_id in image_lookup:
                    primary_image_id = preferred_image_id
                    if preferred_image_id not in region_image_ids:
                        region_image_ids = [preferred_image_id, *region_image_ids]
                else:
                    primary_image_id = self._primary_image_id(region_image_ids, image_lookup)
            if not preferred_group and not region_image_ids and preferred_image_id and preferred_image_id in image_lookup:
                region_image_ids = [preferred_image_id]
            if not primary_image_id and region_image_ids:
                primary_image_id = self._primary_image_id(region_image_ids, image_lookup)
            for rank, image_id in enumerate(region_image_ids, start=1):
                image_lookup[image_id].role = "product_main" if image_id == primary_image_id else "product_detail"
                bindings.append(
                    BindingResult(
                        sku_id=sku.sku_id,
                        image_id=image_id,
                        confidence=max(0.55, 0.78 - (rank - 1) * 0.08) if image_id else 0.0,
                        method="region_membership" if not preferred_group else "model_anchor_image_group",
                        is_ambiguous=False,
                        rank=rank,
                    )
                )
            if not region_image_ids:
                bindings.append(
                    BindingResult(
                        sku_id=sku.sku_id,
                        image_id=None,
                        confidence=0.0,
                        method="region_membership" if not preferred_group else "model_anchor_image_group",
                        is_ambiguous=False,
                        rank=1,
                    )
                )

        return PageResult(
            status="AI_COMPLETED",
            page_type=self._page_type(raw),
            needs_review=not bool(skus),
            skus=skus,
            images=raw.images,
            bindings=bindings,
            classification_confidence=0.8,
            extraction_method=page_extraction_method,
            fitz_page_class="REGION_V2",
        )

    async def _process_regular_page(
        self,
        raw: ParsedPageIR,
        *,
        file_path: str,
        file_hash: str,
        page_no: int,
        document_hints,
    ) -> PageResult:
        screenshot = None
        tile_merge_needed = self._looks_like_tile_page(raw.images)
        screenshot_needed = (
            tile_merge_needed
            or bool(self._llm)
            or settings.ocr_enabled
            or settings.layout_detect_enabled
        )
        ocr_blocks: list[OcrBlock] = []
        layout_regions: list[LayoutRegion] = []
        if screenshot_needed:
            try:
                screenshot = await self._render_page_screenshot(file_path, page_no)
            except Exception:
                screenshot = None
            if screenshot:
                ocr_blocks, layout_regions = await asyncio.gather(
                    self._run_ocr(screenshot),
                    self._run_layout_detection(screenshot),
                )
        self._prepare_images(raw, screenshot=screenshot, page_no=page_no)

        pdf_text_objects = None
        if self._needs_precise_pdf_text(raw):
            try:
                pdf_text_objects = await self._extract_precise_pdf_text_objects(file_path, page_no)
            except Exception:
                pdf_text_objects = None

        evidence = self._region_proposer.build_page_evidence(
            raw,
            pdf_text_objects=pdf_text_objects,
            ocr_blocks=ocr_blocks,
            layout_regions=layout_regions,
            screenshot_size=self._screenshot_size(screenshot),
        )
        if self._is_blank(raw) and not evidence.objects:
            return PageResult(
                status="SKIPPED",
                page_type="D",
                fitz_page_class="BLANK",
                classification_confidence=0.99,
            )

        model_skus, model_bindings = self._model_extractor.extract(evidence)
        if model_skus:
            preferred_image_groups: list[list[str]] = []
            current_group: list[str] | None = None
            for binding in model_bindings:
                if binding.rank == 1:
                    if current_group is not None:
                        preferred_image_groups.append(current_group)
                    current_group = []
                if current_group is None:
                    current_group = []
                if binding.image_id:
                    current_group.append(binding.image_id)
            if current_group is not None:
                preferred_image_groups.append(current_group)
            while len(preferred_image_groups) < len(model_skus):
                preferred_image_groups.append([])
            scene_groups = self._scene_image_group_for_single_sku(
                raw,
                model_skus,
                page_no=page_no,
                text_boxes=[
                    obj.bbox
                    for obj in evidence.objects
                    if obj.object_type in {"text_block", "ocr_block"} and (obj.text or "").strip()
                ],
            )
            if scene_groups:
                preferred_image_groups = scene_groups
            return self._build_regular_page_result(
                raw,
                evidence=evidence,
                proposals=[],
                skus=model_skus,
                file_hash=file_hash,
                page_no=page_no,
                preferred_image_groups=preferred_image_groups,
                page_extraction_method="model_anchor_v2",
            )

        proposals = self._region_proposer.propose(evidence)
        if proposals and self._llm and settings.pipeline_v2_region_refine_enabled:
            proposals = await self._region_refiner.refine(
                evidence,
                proposals,
                screenshot=screenshot,
                document_hints=document_hints,
            )

        skus: list[SKUResult] = []
        for proposal in proposals:
            attrs = self._region_extractor.extract(proposal, evidence)
            if attrs.get("evidence_mode") == "visual_only":
                confidence = max(0.35, proposal.score)
            else:
                confidence = max(0.55, proposal.score)
            skus.append(
                SKUResult(
                    sku_id="",
                    attributes=attrs,
                    source_bbox=proposal.bbox,
                    validity="valid",
                    confidence=confidence,
                    extraction_method="region_rule_v2",
                )
            )
        if settings.pipeline_v2_page_verify_enabled:
            skus = await self._page_verifier.verify(
                skus,
                screenshot=screenshot,
                document_hints=document_hints,
            )

        preferred_image_groups = self._scene_image_group_for_single_sku(
            raw,
            skus,
            page_no=page_no,
            text_boxes=[
                obj.bbox
                for obj in evidence.objects
                if obj.object_type in {"text_block", "ocr_block"} and (obj.text or "").strip()
            ],
        )

        return self._build_regular_page_result(
            raw,
            evidence=evidence,
            proposals=proposals,
            skus=skus,
            file_hash=file_hash,
            page_no=page_no,
            preferred_image_groups=preferred_image_groups,
        )
