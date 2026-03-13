"""
单页 9 阶段处理链。对齐: Pipeline 详设 §5.2

Phase 1: PDF 解析 (多库兜底, ProcessPool)
Phase 2: 图片预处理 (质量评估 + 瓦片合并)
Phase 2.5: [OCR] 高清截图渲染 (DPI 300) → OCR 引擎提取文字块
Phase 2.6: [Layout] DocLayout-YOLO 检测布局区域
Phase 3: 特征提取
Phase 4: 跨页表格检测
Phase 5: 页面分类 (规则+LLM)
Phase 6: SKU 提取 (三路策略: 表格规则 / OCR-Guided / Vision LLM)
Phase 6.3: Rescue Pass
Phase 6.5: 规则去重链
Phase 6.6: SKUReviewer
Phase 7: 一致性校验
Phase 8: ID 分配 + 绑定
Phase 9: 导出
"""
from __future__ import annotations
import asyncio
import hashlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

from pdf_sku.pipeline.ir import (
    ParsedPageIR, FeatureVector, ClassifyResult, PageResult,
    SKUResult, ImageInfo, BindingResult,
)
from pdf_sku.pipeline.parser.adapter import PDFExtractor
from pdf_sku.pipeline.parser.feature_extractor import FeatureExtractor
from pdf_sku.pipeline.parser.ocr_engine import OcrEngine, OcrBlock
from pdf_sku.pipeline.layout_detector import (
    detect_all_regions, split_composite_image, LayoutRegion,
)
from pdf_sku.pipeline.classifier.page_classifier import PageClassifier
from pdf_sku.pipeline.classifier.fitz_classifier import (
    FitzClassifier, FitzPageMeta, PagePlan, extract_fitz_meta,
    BLANK, TABLE, SINGLE_LARGE, SINGLE_TALL, IMG_DENSE,
)
from pdf_sku.pipeline.slicer.page_slicer import plan_slices, render_slice
from pdf_sku.pipeline.extractor.single_stage import SingleStageExtractor
from pdf_sku.pipeline.extractor.ocr_guided import OcrGuidedExtractor
from pdf_sku.pipeline.extractor.consistency_validator import ConsistencyValidator
from pdf_sku.pipeline.extractor.sku_dedup import (
    run_dedup_chain, dedup_by_model, dedup_by_similarity,
    pre_filter, ocr_cross_validate,
)
from pdf_sku.pipeline.extractor.sku_reviewer import SKUReviewer
from pdf_sku.pipeline.binder.binder import SKUImageBinder
from pdf_sku.pipeline.exporter.exporter import SKUIdGenerator, SKUExporter
from pdf_sku.pipeline.cross_page_merger import CrossPageMerger
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

MAX_LLM_CALLS_PER_PAGE = 2  # 分类(规则) + 单阶段提取(1 LLM)

# 中文表格 header → 标准字段名映射
HEADER_NORMALIZE = {
    "商品名称": "product_name",
    "*商品名称/描述": "product_name",
    "商品名称/描述": "product_name",
    "品名": "product_name",
    "产品名称": "product_name",
    "售价": "price",
    "价格": "price",
    "单价": "price",
    "货号": "model_number",
    "型号": "model_number",
    "编号": "model_number",
    "商品规格": "specs",
    "规格": "specs",
    "尺寸": "specs",
    "颜色": "color",
    "标签": "tag",
    "来源": "source",
}


def _extract_page_sync(file_path: str, page_no: int) -> ParsedPageIR:
    """在进程池中执行 PDF 解析。"""
    extractor = PDFExtractor()
    return extractor.extract(file_path, page_no)


def _extract_page_with_meta_sync(
    file_path: str, page_no: int,
) -> tuple[ParsedPageIR, FitzPageMeta]:
    """在进程池中执行 PDF 解析 + fitz 特征提取 (零额外 I/O)。"""
    import fitz
    extractor = PDFExtractor()
    raw = extractor.extract(file_path, page_no)

    # 同一个 fitz.open 会话提取特征 (PDF 已在内存中)
    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        meta = extract_fitz_meta(page)
    finally:
        doc.close()

    return raw, meta


def _render_page_sync(
    file_path: str, page_no: int, dpi: int = 200, max_long_edge: int = 2048
) -> bytes:
    """在进程池中渲染截图，长边不超过 max_long_edge。"""
    import fitz
    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        zoom = dpi / 72
        # 先计算目标尺寸，如果超出限制则降低缩放
        w = page.rect.width * zoom
        h = page.rect.height * zoom
        long_edge = max(w, h)
        if long_edge > max_long_edge:
            zoom = zoom * max_long_edge / long_edge
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
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
        self._fitz_classifier = FitzClassifier()
        self._classifier = PageClassifier(llm_service)
        self._single_stage = SingleStageExtractor(llm_service)
        self._ocr_guided = OcrGuidedExtractor(llm_service)
        self._ocr_engine = OcrEngine()
        self._validator = ConsistencyValidator()
        self._reviewer = SKUReviewer(llm_service)
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
            # ═══ Phase 0+1: PDF 解析 + fitz 预分类 (合并, 零额外 I/O) ═══
            if self._pool:
                raw, fitz_meta = await loop.run_in_executor(
                    self._pool, _extract_page_with_meta_sync, file_path, page_no)
            else:
                raw, fitz_meta = _extract_page_with_meta_sync(file_path, page_no)

            plan = self._fitz_classifier.classify(fitz_meta)
            logger.info("fitz_classify", page=page_no,
                        page_class=plan.page_class,
                        legacy=plan.legacy_type,
                        dpi=plan.render_dpi,
                        sku_range=plan.expected_sku_range,
                        grid=fitz_meta.grid)

            # BLANK → 直接跳过
            if plan.page_class == BLANK:
                return PageResult(
                    status="SKIPPED", page_type="D",
                    fitz_page_class=BLANK,
                    classification_confidence=0.99)

            # 缓存到 CrossPageMerger
            await self._xpage.cache_page(job_id, page_no, raw)

            # ═══ Phase 2: 图片预处理 ═══
            dpi_scale = plan.render_dpi / 72.0
            for img in raw.images:
                native_short = min(img.width, img.height) if img.width and img.height else 0
                display_short = 0
                if img.bbox != (0, 0, 0, 0) and len(img.bbox) >= 4:
                    dw = abs(img.bbox[2] - img.bbox[0]) * dpi_scale
                    dh = abs(img.bbox[3] - img.bbox[1]) * dpi_scale
                    display_short = int(min(dw, dh))
                img.short_edge = max(native_short, display_short)
                img.search_eligible = img.short_edge >= 200
                if img.data:
                    img.image_hash = hashlib.md5(img.data[:2048]).hexdigest()[:12]

            # ═══ Phase 2b: 瓦片碎片聚类合并 ═══
            raw.images = self._merge_tile_fragments(raw.images, page_no)

            # ═══ Phase 2.5: 切片计划 + 渲染 ═══
            plan.slices = plan_slices(fitz_meta, plan)
            screenshots: list[bytes] = []
            screenshot = b""  # 整页截图 (用于 OCR/Layout/Review)

            if plan.slices:
                # 切片渲染: 每个切片独立渲染
                logger.info("slice_render", page=page_no,
                            slices=len(plan.slices), dpi=plan.render_dpi)
                slice_tasks = [
                    loop.run_in_executor(
                        None, render_slice, file_path, page_no, bbox, plan.render_dpi)
                    for bbox in plan.slices
                ]
                slice_results = await asyncio.gather(*slice_tasks, return_exceptions=True)
                for i, r in enumerate(slice_results):
                    if isinstance(r, Exception):
                        logger.warning("slice_render_failed", page=page_no,
                                       slice=i, error=str(r))
                        screenshots.append(b"")
                    else:
                        screenshots.append(r)

                # 同时渲染整页低 DPI 截图 (用于 OCR/Layout/Review)
                try:
                    screenshot = await loop.run_in_executor(
                        None, _render_page_sync, file_path, page_no, 150, 2048)
                except Exception:
                    pass
            else:
                # 整页渲染
                try:
                    screenshot = await loop.run_in_executor(
                        None, _render_page_sync, file_path, page_no,
                        plan.render_dpi, 2048)
                except Exception:
                    pass

            # ═══ Phase 2.6: OCR + Layout 检测 (整页截图) ═══
            ocr_blocks: list[OcrBlock] = []
            layout_regions: list[LayoutRegion] = []

            if screenshot:
                ocr_layout_tasks = []
                if settings.ocr_enabled:
                    ocr_layout_tasks.append(
                        loop.run_in_executor(
                            None, self._ocr_engine.run, screenshot))
                if settings.layout_detect_enabled:
                    ocr_layout_tasks.append(
                        loop.run_in_executor(
                            None, detect_all_regions, screenshot))

                if ocr_layout_tasks:
                    results = await asyncio.gather(
                        *ocr_layout_tasks, return_exceptions=True)
                    idx = 0
                    if settings.ocr_enabled:
                        if not isinstance(results[idx], Exception):
                            ocr_blocks = results[idx]
                        else:
                            logger.warning("ocr_failed", page=page_no,
                                           error=str(results[idx]))
                        idx += 1
                    if settings.layout_detect_enabled and idx < len(results):
                        if not isinstance(results[idx], Exception):
                            layout_regions = results[idx]
                        else:
                            logger.warning("layout_detect_failed", page=page_no,
                                           error=str(results[idx]))

            ocr_text_len = OcrEngine.total_text_length(ocr_blocks)
            if ocr_blocks:
                logger.info("ocr_result", page=page_no,
                            blocks=len(ocr_blocks), text_len=ocr_text_len)
            if layout_regions:
                logger.info("layout_result", page=page_no,
                            regions=len(layout_regions),
                            labels=[r.label for r in layout_regions])

            # ═══ Phase 3: 特征提取 ═══
            features = self._feat.extract(raw)

            # ═══ Phase 4: 跨页表格检测 ═══
            continuation = await self._xpage.find_continuation(job_id, page_no, raw)
            if continuation:
                raw.tables = self._xpage.merge(continuation.source_tables, raw.tables)

            # ═══ Phase 5: 页面分类 (用 fitz plan.legacy_type 直接映射) ═══
            page_type = plan.legacy_type
            cls_result = ClassifyResult(
                page_type=page_type,
                layout_type="grid" if fitz_meta.grid else "freeform",
                confidence=0.85,
            )

            # D 类 → 跳过 (已在 BLANK 处理过，这里处理 legacy 分类的 D)
            if page_type == "D":
                return PageResult(
                    status="SKIPPED", page_type="D",
                    fitz_page_class=plan.page_class,
                    classification_confidence=0.90)

            # ═══ Phase 6: SKU 提取 (策略路由) ═══
            if plan.slices and screenshots:
                # 切片模式: 每片独立送 LLM，合并去重
                skus = await self._extract_sliced(raw, plan, screenshots)
                extraction_method = "sliced_vision"
            else:
                # 整页模式: 原有三路策略
                skus = await self._extract_skus(
                    raw, page_type, screenshot, features,
                    ocr_blocks, layout_regions, ocr_text_len,
                    sku_count_hint=plan.expected_sku_range,
                    scene_filter=plan.scene_filter)
                extraction_method = skus[0].extraction_method if skus else None

            # ═══ Phase 6.3: 低提取二次 Pass (rescue) ═══
            effective_screenshot = screenshot or (screenshots[0] if screenshots else b"")
            if (len(skus) <= 1
                    and page_type in ("A", "B", "C")
                    and effective_screenshot):
                retry_screenshot = effective_screenshot
                if len(skus) == 0:
                    try:
                        retry_screenshot = await loop.run_in_executor(
                            None, _render_page_sync, file_path, page_no, 300, 3072)
                        logger.info("high_dpi_retry", page=page_no, dpi=300)
                    except Exception:
                        pass
                rescue_skus = await self._single_stage.extract_rescue(
                    raw, screenshot=retry_screenshot)
                if rescue_skus:
                    skus.extend(rescue_skus)
                    logger.info("rescue_pass_done",
                                page=page_no, rescued=len(rescue_skus))

            # ═══ Phase 6.4: 密集页补充提取 ═══
            if (page_type in ("B", "C") and ocr_text_len >= 500
                    and len(skus) < max(5, ocr_text_len // 200)
                    and effective_screenshot):
                expected_min = ocr_text_len // 150
                logger.info("dense_page_retry", page=page_no,
                            ocr_chars=ocr_text_len, current_skus=len(skus),
                            expected_min=expected_min)
                retry_skus = await self._single_stage.extract_rescue(
                    raw, screenshot=effective_screenshot)
                if retry_skus:
                    skus.extend(retry_skus)
                    skus = dedup_by_model(skus)
                    logger.info("dense_page_retry_done", page=page_no,
                                after=len(skus))

            # ═══ Phase 6.5: 规则去重链 (含 OCR 交叉验证) ═══
            if skus:
                before = len(skus)
                ocr_full_text = OcrEngine.blocks_to_text(ocr_blocks) if ocr_blocks else ""

                # IMG_DENSE + grid → 放宽去重（网格产品名称相似是正常的）
                if plan.page_class == IMG_DENSE and fitz_meta.grid:
                    skus = pre_filter(skus)
                    if ocr_full_text:
                        skus = ocr_cross_validate(skus, ocr_full_text)
                    skus = dedup_by_model(skus)
                else:
                    skus = run_dedup_chain(skus, ocr_text=ocr_full_text)
                if len(skus) < before:
                    logger.info("dedup_chain_applied",
                                page=page_no, before=before, after=len(skus))

                # 过滤后 SKU 全部被清除 → 触发 post-filter rescue
                if not skus and page_type in ("B", "C") and effective_screenshot:
                    logger.info("post_filter_rescue", page=page_no, before_filter=before)
                    rescue_skus = await self._single_stage.extract_rescue(
                        raw, screenshot=effective_screenshot)
                    if rescue_skus:
                        skus = run_dedup_chain(rescue_skus, ocr_text=ocr_full_text)
                        logger.info("post_filter_rescue_done",
                                    page=page_no, rescued=len(skus))

            # ═══ Phase 6.6: SKUReviewer Pass 2 (B/C 类 + 有 SKU) ═══
            review_screenshot = screenshot or effective_screenshot
            if page_type in ("B", "C") and skus and review_screenshot:
                before_review = len(skus)
                skus = await self._reviewer.review(skus, screenshot=review_screenshot)
                if len(skus) < before_review:
                    logger.info("reviewer_applied",
                                page=page_no, before=before_review, after=len(skus))

            # enforce validity
            profile_data = None
            if self._config and frozen_config_version:
                try:
                    from pdf_sku.common.dependencies import get_db
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

            # Composite 图片: 从截图裁剪生成实际图片数据
            if screenshot:
                self._crop_composites(raw.images, screenshot)

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
                fitz_page_class=plan.page_class,
                slice_count=len(plan.slices) if plan.slices else 0,
            )

        except Exception as e:
            logger.exception("page_processing_error",
                             job_id=job_id, page_no=page_no)
            return PageResult(
                status="AI_FAILED",
                error=str(e),
                needs_review=True,
            )

    async def _extract_sliced(
        self,
        raw: ParsedPageIR,
        plan: PagePlan,
        screenshots: list[bytes],
    ) -> list[SKUResult]:
        """切片模式提取: 每片独立送 LLM，合并去重。"""
        tasks = []
        for i, (ss, bbox) in enumerate(zip(screenshots, plan.slices)):
            if not ss:
                continue
            hint = f"这是页面的第{i+1}/{len(plan.slices)}个区域 (共{len(plan.slices)}片)"
            # 每片的预估 SKU 数 = 总预估 / 片数
            lo, hi = plan.expected_sku_range
            n = len(plan.slices)
            slice_range = (max(1, lo // n), max(1, (hi + n - 1) // n))
            tasks.append(self._single_stage.extract(
                raw, screenshot=ss,
                sku_count_hint=slice_range,
                region_hint=hint,
                scene_filter=plan.scene_filter))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_skus: list[SKUResult] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("slice_extract_failed", error=str(r))
            elif isinstance(r, list):
                all_skus.extend(r)

        if all_skus:
            # 跨切片去重 (重叠区域可能产生重复)
            before = len(all_skus)
            all_skus = dedup_by_model(all_skus)
            all_skus = dedup_by_similarity(all_skus, threshold=0.98)
            if len(all_skus) < before:
                logger.info("slice_dedup", before=before, after=len(all_skus))

        return all_skus

    async def _extract_skus(
        self,
        raw: ParsedPageIR,
        page_type: str,
        screenshot: bytes,
        features: FeatureVector,
        ocr_blocks: list[OcrBlock],
        layout_regions: list[LayoutRegion],
        ocr_text_len: int,
        sku_count_hint: tuple[int, int] | None = None,
        scene_filter: bool = False,
    ) -> list[SKUResult]:
        """Phase 6: 融合策略提取。

        - A 类 (表格页): 规则表格提取
        - B/C 类: OCR-Guided + Vision 并行融合，合并去重
        """

        # A 类: 规则表格提取
        if page_type == "A" and raw.tables:
            return self._table_extract(raw)

        # B/C 类: OCR-Guided + Vision 并行融合
        has_ocr = (ocr_text_len >= settings.ocr_min_text_length and ocr_blocks)
        has_screenshot = bool(screenshot)

        tasks: list[asyncio.Task] = []
        task_labels: list[str] = []

        if has_ocr:
            tasks.append(asyncio.create_task(
                self._ocr_guided.extract(ocr_blocks, layout_regions, screenshot=None)))
            task_labels.append("ocr_guided")
        if has_screenshot:
            tasks.append(asyncio.create_task(
                self._single_stage.extract(
                    raw, screenshot=screenshot,
                    sku_count_hint=sku_count_hint,
                    scene_filter=scene_filter)))
            task_labels.append("vision")

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_skus: list[SKUResult] = []
        methods_ok: list[str] = []
        for label, r in zip(task_labels, results):
            if isinstance(r, Exception):
                logger.warning(f"{label}_extract_failed", page=raw.page_no, error=str(r))
            elif isinstance(r, list) and r:
                all_skus.extend(r)
                methods_ok.append(label)

        if all_skus:
            # 融合去重: 只按 model_number 去重 (相似度去重留给 run_dedup_chain 统一处理)
            before = len(all_skus)
            all_skus = dedup_by_model(all_skus)
            logger.info("fusion_extract_done", page=raw.page_no,
                        methods=methods_ok, before=before, after=len(all_skus))

        return all_skus

    def _table_extract(self, raw: ParsedPageIR) -> list[SKUResult]:
        """A 类表格页: 规则引擎提取 + 中文 header 归一化。"""
        results = []
        for table in raw.tables:
            if not table.rows or len(table.rows) < 2:
                continue
            # 归一化 header: 中文 → 标准字段名
            raw_headers = [h.strip() for h in table.rows[0]]
            headers = []
            for h in raw_headers:
                normalized = HEADER_NORMALIZE.get(h) or HEADER_NORMALIZE.get(h.lower())
                headers.append(normalized or h.lower())
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

    @staticmethod
    def _merge_tile_fragments(images: list[ImageInfo], page_no: int = 0) -> list[ImageInfo]:
        """检测并合并瓦片碎片为虚拟复合图片。

        判定: 页面图片数 > 30 且多数图片 short_edge < 200 (原生)。
        Union-Find 将相邻碎片 (间隔 < 5pt) 聚类。
        """
        if len(images) < 30:
            return images

        small_count = sum(
            1 for img in images
            if min(img.width, img.height) < 200 and img.width > 0
        )
        if small_count < len(images) * 0.7:
            return images

        # Union-Find
        n = len(images)
        parent = list(range(n))
        rank = [0] * n

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri == rj:
                return
            if rank[ri] < rank[rj]:
                ri, rj = rj, ri
            parent[rj] = ri
            if rank[ri] == rank[rj]:
                rank[ri] += 1

        GAP = 5  # PDF points
        for i in range(n):
            bi = images[i].bbox
            if len(bi) < 4:
                continue
            for j in range(i + 1, n):
                bj = images[j].bbox
                if len(bj) < 4:
                    continue
                h_adj = bi[0] < bj[2] + GAP and bj[0] < bi[2] + GAP
                v_adj = bi[1] < bj[3] + GAP and bj[1] < bi[3] + GAP
                if h_adj and v_adj:
                    union(i, j)

        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        merged: list[ImageInfo] = []
        composite_idx = 0
        for members in clusters.values():
            if len(members) == 1:
                img = images[members[0]]
                native_short = min(img.width, img.height) if img.width and img.height else 0
                if native_short < 200:
                    img.is_fragmented = True
                    img.search_eligible = False
                merged.append(img)
                continue

            x0 = min(images[m].bbox[0] for m in members)
            y0 = min(images[m].bbox[1] for m in members)
            x1 = max(images[m].bbox[2] for m in members)
            y1 = max(images[m].bbox[3] for m in members)
            dpi_scale = 200 / 72.0
            dw = (x1 - x0) * dpi_scale
            dh = (y1 - y0) * dpi_scale
            short = int(min(dw, dh))

            composite = ImageInfo(
                image_id=f"p{page_no}_composite_{composite_idx}",
                bbox=(x0, y0, x1, y1),
                width=int(dw),
                height=int(dh),
                short_edge=short,
                search_eligible=short >= 200,
                role="unknown",
            )
            merged.append(composite)
            composite_idx += 1

            for m in members:
                images[m].is_fragmented = True
                images[m].search_eligible = False
                merged.append(images[m])

        logger.info("tile_merge_result",
                     page=page_no,
                     original=len(images),
                     composites=composite_idx,
                     remaining=len([m for m in merged if not m.is_fragmented]))
        return merged

    @staticmethod
    def _crop_composites(images: list[ImageInfo], screenshot: bytes) -> None:
        """从页面截图裁剪 composite 图片区域，填充 img.data。"""
        composites = [img for img in images
                      if "_composite_" in img.image_id and not img.data]
        if not composites:
            return
        try:
            from PIL import Image as PILImage
            import io
            pil_img = PILImage.open(io.BytesIO(screenshot))
            for img in composites:
                if len(img.bbox) < 4:
                    continue
                x0 = max(0, int(img.bbox[0]))
                y0 = max(0, int(img.bbox[1]))
                x1 = min(pil_img.width, int(img.bbox[2]))
                y1 = min(pil_img.height, int(img.bbox[3]))
                if x1 <= x0 or y1 <= y0:
                    continue
                cropped = pil_img.crop((x0, y0, x1, y1))
                buf = io.BytesIO()
                cropped.save(buf, format="JPEG", quality=85)
                img.data = buf.getvalue()
        except Exception as e:
            logger.warning("crop_composites_failed", error=str(e))

    def clear_job_cache(self, job_id: str) -> None:
        self._xpage.clear_job(job_id)
