"""
单页 9 阶段处理链。对齐: Pipeline 详设 §5.2

Phase 1: PDF 解析 (多库兜底, ProcessPool)
Phase 2: 图片预处理 (质量评估)
Phase 3: 特征提取
Phase 4: 跨页表格检测
Phase 5: 页面分类 (规则+LLM)
Phase 6: SKU 提取 (两阶段+单阶段 Fallback)
Phase 7: 一致性校验
Phase 8: ID 分配 + 绑定
Phase 9: 导出
"""
from __future__ import annotations
import asyncio
import hashlib
from concurrent.futures import ProcessPoolExecutor

from pdf_sku.pipeline.ir import (
    ParsedPageIR, FeatureVector, ClassifyResult, PageResult,
    SKUResult, ImageInfo, BindingResult,
)
from pdf_sku.pipeline.parser.adapter import PDFExtractor
from pdf_sku.pipeline.parser.feature_extractor import FeatureExtractor
from pdf_sku.pipeline.classifier.page_classifier import PageClassifier
from pdf_sku.pipeline.extractor.two_stage import TwoStageExtractor
from pdf_sku.pipeline.extractor.single_stage import SingleStageExtractor
from pdf_sku.pipeline.extractor.consistency_validator import ConsistencyValidator
from pdf_sku.pipeline.binder.binder import SKUImageBinder
from pdf_sku.pipeline.exporter.exporter import SKUIdGenerator, SKUExporter
from pdf_sku.pipeline.cross_page_merger import CrossPageMerger
import structlog

logger = structlog.get_logger()

MAX_LLM_CALLS_PER_PAGE = 6  # [C13]


def _extract_page_sync(file_path: str, page_no: int) -> ParsedPageIR:
    """在进程池中执行 PDF 解析。"""
    extractor = PDFExtractor()
    return extractor.extract(file_path, page_no)


def _render_page_sync(file_path: str, page_no: int, dpi: int = 150) -> bytes:
    """在进程池中渲染截图。"""
    import fitz
    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    finally:
        doc.close()


class PageProcessor:
    """单页 9 阶段处理管线。"""

    def __init__(
        self,
        llm_service=None,
        process_pool: ProcessPoolExecutor | None = None,
        config_provider=None,
    ) -> None:
        self._llm = llm_service
        self._pool = process_pool
        self._config = config_provider
        self._extractor = PDFExtractor()
        self._feat = FeatureExtractor()
        self._classifier = PageClassifier(llm_service)
        self._two_stage = TwoStageExtractor(llm_service)
        self._single_stage = SingleStageExtractor(llm_service)
        self._validator = ConsistencyValidator()
        self._binder = SKUImageBinder()
        self._id_gen = SKUIdGenerator()
        self._exporter = SKUExporter()
        self._xpage = CrossPageMerger()

    async def process_page(
        self,
        job_id: str,
        file_path: str,
        page_no: int,
        file_hash: str = "",
        category: str | None = None,
        frozen_config_version: str | None = None,
    ) -> PageResult:
        """
        单页处理入口。

        Returns:
            PageResult: 包含 SKU、图片、绑定、校验结果
        """
        loop = asyncio.get_event_loop()
        llm_calls_used = 0
        extraction_method = None
        fallback_reason = None

        try:
            # ═══ Phase 1: PDF 解析 ═══
            if self._pool:
                raw = await loop.run_in_executor(
                    self._pool, _extract_page_sync, file_path, page_no)
            else:
                raw = self._extractor.extract(file_path, page_no)

            # 缓存到 CrossPageMerger
            await self._xpage.cache_page(job_id, page_no, raw)

            # ═══ Phase 2: 图片预处理 ═══
            for img in raw.images:
                img.short_edge = min(img.width, img.height) if img.width and img.height else 0
                img.search_eligible = img.short_edge >= 200
                if img.data:
                    img.image_hash = hashlib.md5(img.data[:2048]).hexdigest()[:12]

            # ═══ Phase 3: 特征提取 ═══
            features = self._feat.extract(raw)

            # ═══ Phase 4: 跨页表格检测 ═══
            continuation = await self._xpage.find_continuation(job_id, page_no, raw)
            if continuation:
                raw.tables = self._xpage.merge(continuation.source_tables, raw.tables)

            # ═══ Phase 5: 页面分类 ═══
            screenshot = b""
            if self._pool:
                try:
                    screenshot = await loop.run_in_executor(
                        self._pool, _render_page_sync, file_path, page_no)
                except Exception:
                    pass
            cls_result = await self._classifier.classify(
                screenshot=screenshot,
                features=features,
                raw_text=raw.raw_text,
            )
            page_type = cls_result.page_type

            # D 类 → 跳过
            if page_type == "D" and cls_result.confidence >= 0.85:
                return PageResult(
                    status="SKIPPED", page_type="D",
                    classification_confidence=cls_result.confidence)

            # ═══ Phase 6: SKU 提取 ═══
            skus = await self._extract_skus_with_fallback(
                raw, page_type, screenshot, features, llm_calls_used)
            extraction_method = skus[0].extraction_method if skus else None

            # enforce validity
            profile_data = None
            if self._config and frozen_config_version:
                try:
                    from pdf_sku.common.dependencies import get_db
                    # In production, db would be passed. Here use profile dict directly.
                    pass
                except Exception:
                    pass

            skus = self._validator.enforce_sku_validity(skus, profile_data)

            # ═══ Phase 7: ID 分配 ═══
            hash_prefix = (file_hash or "unknown")[:8]
            skus = self._id_gen.assign_ids(
                skus, hash_prefix, page_no, raw.metadata.page_height)

            # ═══ Phase 8: 绑定 ═══
            bindings = self._binder.bind(skus, raw.images, cls_result)

            # ═══ Phase 9: 校验 + 导出 ═══
            validation = self._validator.validate(
                page_type, skus, raw.images, bindings)

            exported = await self._exporter.export(
                skus, job_id, page_no)

            needs_review = (
                validation.has_errors or
                cls_result.confidence < 0.6 or
                (not skus and page_type not in ("D",))
            )

            return PageResult(
                status="AI_COMPLETED",
                page_type=page_type,
                needs_review=needs_review,
                skus=skus,
                images=raw.images,
                bindings=bindings,
                validation=validation,
                classification_confidence=cls_result.confidence,
                extraction_method=extraction_method,
                fallback_reason=fallback_reason,
            )

        except Exception as e:
            logger.exception("page_processing_error",
                             job_id=job_id, page_no=page_no)
            return PageResult(
                status="AI_FAILED",
                error=str(e),
                needs_review=True,
            )

    async def _extract_skus_with_fallback(
        self,
        raw: ParsedPageIR,
        page_type: str,
        screenshot: bytes,
        features: FeatureVector,
        llm_calls_used: int,
    ) -> list[SKUResult]:
        """Phase 6: 两阶段 + 单阶段 Fallback。"""

        # A 类: 规则表格提取
        if page_type == "A" and raw.tables:
            return self._table_extract(raw)

        # B/C 类: 两阶段
        remaining = MAX_LLM_CALLS_PER_PAGE - llm_calls_used
        if remaining >= 2:
            try:
                boundaries = await self._two_stage.identify_boundaries(
                    raw.text_blocks, None, screenshot)
                if boundaries:
                    skus = await self._two_stage.extract_batch(boundaries, raw)
                    if skus:
                        invalid_count = sum(1 for s in skus if s.validity == "invalid")
                        if len(skus) > 0 and invalid_count / len(skus) <= 0.3:
                            return skus
                        logger.info("two_stage_high_invalid",
                                    page=raw.page_no,
                                    invalid_ratio=invalid_count / len(skus))
            except Exception as e:
                logger.warning("two_stage_failed", page=raw.page_no, error=str(e))

        # 单阶段 Fallback
        try:
            skus = await self._single_stage.extract(raw)
            if skus:
                return skus
        except Exception as e:
            logger.warning("single_stage_failed", page=raw.page_no, error=str(e))

        # [C7] 最终兜底: 返回空
        return []

    def _table_extract(self, raw: ParsedPageIR) -> list[SKUResult]:
        """A 类表格页: 规则引擎提取。"""
        results = []
        for table in raw.tables:
            if not table.rows or len(table.rows) < 2:
                continue
            headers = [h.lower().strip() for h in table.rows[0]]
            for row in table.rows[1:]:
                attrs = {}
                for i, cell in enumerate(row):
                    if i < len(headers) and cell and cell.strip():
                        attrs[headers[i]] = cell.strip()
                if attrs:
                    results.append(SKUResult(
                        attributes=attrs,
                        source_bbox=table.bbox,
                        validity="valid" if attrs else "invalid",
                        confidence=0.85,
                        extraction_method="table_rule",
                    ))
        return results

    def clear_job_cache(self, job_id: str) -> None:
        self._xpage.clear_job(job_id)
