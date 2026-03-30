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
import io
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
    _FIGURE_LABELS,
)
from pdf_sku.pipeline.classifier.page_classifier import PageClassifier
from pdf_sku.pipeline.classifier.fitz_classifier import (
    FitzClassifier, FitzPageMeta, PagePlan, extract_fitz_meta,
    BLANK, TABLE, SINGLE_STD, SINGLE_LARGE, SINGLE_TALL, IMG_DENSE,
    IMG_LABEL, MIXED_TABLE, MULTI_SPARSE, MIXED_OTHER,
)
from pdf_sku.pipeline.slicer.page_slicer import plan_slices, render_slice, TALL_OVERLAP
from pdf_sku.pipeline.extractor.single_stage import SingleStageExtractor
from pdf_sku.pipeline.extractor.ocr_guided import OcrGuidedExtractor
from pdf_sku.pipeline.extractor.consistency_validator import ConsistencyValidator
from pdf_sku.pipeline.extractor.sku_dedup import (
    run_dedup_chain, dedup_by_model, dedup_by_similarity,
    dedup_by_model_variant, dedup_material_variants,
    _merge_variant_size,
    pre_filter, ocr_cross_validate, split_compound_models,
    normalize_model,
)
from pdf_sku.pipeline.extractor.sku_scorer import score_and_filter
from pdf_sku.pipeline.extractor.sku_reviewer import SKUReviewer
from pdf_sku.pipeline.catalog_profiler import CatalogProfile
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


def _make_refined_slices(
    image_bboxes: list[tuple],
    page_w: float,
    page_h: float,
    max_slices: int = 20,
) -> list[tuple]:
    """用图片 bbox 生成细粒度切片，每 1-2 张图一片。

    算法: 按 Y 坐标聚类图片为行，每行按 X 坐标拆分。
    切片间保留 40pt overlap。
    """
    if not image_bboxes or page_w <= 0 or page_h <= 0:
        return []

    OVERLAP = 40.0
    ROW_GAP = 30.0  # Y 方向间距 > 此值视为不同行

    # 按 Y 中心排序
    sorted_bboxes = sorted(image_bboxes, key=lambda b: (b[1] + b[3]) / 2)

    # 聚类为行
    rows: list[list[tuple]] = []
    current_row: list[tuple] = [sorted_bboxes[0]]
    for bbox in sorted_bboxes[1:]:
        prev_bottom = max(b[3] for b in current_row)
        cur_top = bbox[1]
        if cur_top - prev_bottom > ROW_GAP:
            rows.append(current_row)
            current_row = [bbox]
        else:
            current_row.append(bbox)
    rows.append(current_row)

    # 每行按 X 排序，每 1-2 张图生成一个切片
    slices: list[tuple] = []
    for row in rows:
        row.sort(key=lambda b: b[0])  # 按 X 排序
        row_y0 = min(b[1] for b in row)
        row_y1 = max(b[3] for b in row)

        # 每 2 张图一片
        for i in range(0, len(row), 2):
            chunk = row[i:i + 2]
            x0 = max(0, min(b[0] for b in chunk) - OVERLAP)
            x1 = min(page_w, max(b[2] for b in chunk) + OVERLAP)
            y0 = max(0, row_y0 - OVERLAP)
            y1 = min(page_h, row_y1 + OVERLAP)
            slices.append((x0, y0, x1, y1))

        if len(slices) >= max_slices:
            break

    return slices[:max_slices]


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


import re as _re

# 从 PDF 矢量文本提取型号的正则（匹配 "型号#" 和 "型号(" 格式）
_TEXT_MODEL_HASH_RE = _re.compile(r'^(.{1,20})#', _re.MULTILINE)
_TEXT_MODEL_PAREN_RE = _re.compile(r'^([A-Za-z]+\d+(?:[-]\d+)?)\s*[\(（]', _re.MULTILINE)

# 纯图目录: 页面级 OCR 产品信号检测
_PRODUCT_SIGNAL_MODEL_RE = _re.compile(r'[A-Za-z]{1,5}[-\s]?\d{3,}|[A-Z]{2,}\d+|\d{3,}#')
_PRODUCT_SIGNAL_PRICE_RE = _re.compile(r'[¥￥$€£]\s*[\d,.]+|\d{3,}(?:\.\d{2})?\s*元')


def _has_product_signal(ocr_text: str) -> bool:
    """检测 OCR 文本中是否包含产品信号（型号/价格模式）。"""
    if not ocr_text or len(ocr_text.strip()) < 15:
        return False
    return bool(_PRODUCT_SIGNAL_MODEL_RE.search(ocr_text)
                or _PRODUCT_SIGNAL_PRICE_RE.search(ocr_text))


def _extract_models_from_text(raw_text: str, page_no: int) -> list[SKUResult]:
    """从 PDF 矢量文本中用正则提取型号，生成 SKUResult。

    适用于产品卡片页面（每页 1-N 个产品，型号以 "xxx#" 格式标注）。
    """
    models_hash = [m.strip() for m in _TEXT_MODEL_HASH_RE.findall(raw_text) if m.strip()]
    models_paren = [m.strip() for m in _TEXT_MODEL_PAREN_RE.findall(raw_text)
                    if m.strip() and m.strip() not in models_hash]
    all_models = models_hash + models_paren

    if not all_models:
        return []

    results = []
    for model in all_models:
        sku = SKUResult(
            sku_id="",
            attributes={
                "product_name": model,
                "model_number": model,
            },
            confidence=0.45,
            extraction_method="text_rule_fallback",
        )
        results.append(sku)
    return results


def _render_page_sync(
    file_path: str, page_no: int, dpi: int = 200, max_long_edge: int = 3000
) -> bytes:
    """在进程池中渲染截图，长边不超过 max_long_edge，JPEG 输出。"""
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
        return _pixmap_to_jpeg(pix)
    finally:
        doc.close()


def _pixmap_to_jpeg(pix, quality: int = 80) -> bytes:
    """将 fitz.Pixmap 转为 JPEG bytes，比 PNG 小 5-10 倍。"""
    from PIL import Image
    import io
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()



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
        catalog_profile: CatalogProfile | None = None,
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
            # 纯图产品目录：禁用场景过滤（产品无文字标注是正常的）
            if catalog_profile and catalog_profile.is_pure_image_catalog:
                plan.scene_filter = False
            logger.info("fitz_classify", page=page_no,
                        page_class=plan.page_class,
                        legacy=plan.legacy_type,
                        dpi=plan.render_dpi,
                        sku_range=plan.expected_sku_range,
                        grid=fitz_meta.grid,
                        pure_visual=plan.pure_visual)

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

            # ═══ Phase 2a: 密集网格页布局感知 eligible ═══
            # 如果页面有>=5个大小相似的非eligible图片，视为产品网格页，降低阈值
            _not_eligible = [img for img in raw.images if not img.search_eligible
                             and img.short_edge >= 40]
            if len(_not_eligible) >= 5:
                _sizes = [img.short_edge for img in _not_eligible]
                _avg = sum(_sizes) / len(_sizes)
                _variance = sum((s - _avg) ** 2 for s in _sizes) / len(_sizes)
                # 大小相似(方差/均值² < 0.3) → 网格布局，降低阈值到80
                if _avg > 0 and _variance / (_avg ** 2) < 0.3:
                    for img in _not_eligible:
                        if img.short_edge >= 80:
                            img.search_eligible = True
                    _newly = sum(1 for img in _not_eligible if img.search_eligible)
                    if _newly:
                        logger.info("grid_layout_eligible_relaxed",
                                    page=page_no, relaxed=_newly,
                                    avg_short_edge=int(_avg))

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

            # 纯图目录: 无 OCR 产品信号的页面 → 恢复 scene_filter
            _page_has_product_signal = True
            if catalog_profile and catalog_profile.is_pure_image_catalog:
                _ocr_page_text = OcrEngine.blocks_to_text(ocr_blocks) if ocr_blocks else ""
                _page_has_product_signal = _has_product_signal(_ocr_page_text)
                if not _page_has_product_signal and not plan.pure_visual:
                    plan.scene_filter = True
                    logger.info("pure_img_scene_filter_restored", page=page_no,
                                ocr_len=len(_ocr_page_text))

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
                _ocr_text_for_sliced = OcrEngine.blocks_to_text(ocr_blocks) if ocr_blocks else ""
                skus = await self._extract_sliced(raw, plan, screenshots,
                                                     catalog_profile=catalog_profile,
                                                     ocr_text=_ocr_text_for_sliced)
                extraction_method = "sliced_vision"

                # 切片零结果回退: 回退到整页 single_stage 提取
                if not skus and screenshot:
                    logger.info("slice_zero_fallback", page=page_no,
                                slices=len(plan.slices))
                    skus = await self._single_stage.extract(
                        raw, screenshot=screenshot,
                        sku_count_hint=plan.expected_sku_range,
                        scene_filter=plan.scene_filter,
                        page_class=plan.page_class)
                    extraction_method = "sliced_vision_fallback"

                # 低产出密度检测: 提取数远低于预期 → 加密切片二次提取
                _expect_lo = plan.expected_sku_range[0] if plan.expected_sku_range else 0
                if (skus and _expect_lo >= 8
                        and len(skus) < _expect_lo * 0.3
                        and plan.page_class == IMG_DENSE
                        and plan.pure_visual
                        and screenshot):
                    logger.info("low_density_retry", page=page_no,
                                found=len(skus), expected_lo=_expect_lo,
                                old_slices=len(plan.slices))
                    # 加密: 切片数翻倍，最多 24
                    _pw = fitz_meta.page_width
                    _ph = fitz_meta.page_height
                    _n_retry = min(len(plan.slices) * 2, 24)
                    _row_h = _ph / _n_retry
                    _retry_bboxes = []
                    for _i in range(_n_retry):
                        _y0 = max(0, _i * _row_h - TALL_OVERLAP) if _i > 0 else 0
                        _y1 = min(_ph, (_i + 1) * _row_h + TALL_OVERLAP) if _i < _n_retry - 1 else _ph
                        _retry_bboxes.append((0, _y0, _pw, _y1))
                    # 渲染 + 提取
                    _retry_imgs = await asyncio.gather(*[
                        loop.run_in_executor(None, render_slice, file_path, page_no, bbox, 250)
                        for bbox in _retry_bboxes
                    ], return_exceptions=True)
                    _retry_skus: list[SKUResult] = []
                    _retry_tasks = []
                    for _ri, _rimg in enumerate(_retry_imgs):
                        if isinstance(_rimg, Exception) or not _rimg:
                            continue
                        _hint = (f"区域{_ri+1}/{_n_retry}。"
                                 f"逐一提取每个产品，不同颜色/尺寸各算独立SKU。")
                        _retry_tasks.append(self._single_stage.extract(
                            raw, screenshot=_rimg,
                            sku_count_hint=(1, max(3, _expect_lo // _n_retry + 1)),
                            region_hint=_hint,
                            scene_filter=False,
                            page_class=plan.page_class))
                    if _retry_tasks:
                        _retry_results = await asyncio.gather(*_retry_tasks, return_exceptions=True)
                        for _rr in _retry_results:
                            if isinstance(_rr, list) and _rr:
                                _retry_skus.extend(_rr)
                    if len(_retry_skus) > len(skus):
                        _retry_skus = dedup_by_model(_retry_skus)
                        _retry_skus = dedup_by_similarity(_retry_skus, threshold=0.90)
                        logger.info("low_density_retry_done", page=page_no,
                                    old=len(skus), new=len(_retry_skus))
                        skus = _retry_skus
                        extraction_method = "low_density_retry"

                # 切片 + 整页均零结果，OCR 有内容 → OCR-guided 回退
                if not skus and ocr_text_len > 30:
                    logger.info("slice_ocr_fallback", page=page_no,
                                ocr_chars=ocr_text_len)
                    skus = await self._extract_skus(
                        raw, page_type, screenshot, features,
                        ocr_blocks, layout_regions, ocr_text_len,
                        sku_count_hint=plan.expected_sku_range,
                        scene_filter=plan.scene_filter, plan=plan)
                    if skus:
                        extraction_method = "ocr_guided"
            else:
                # 整页模式: 原有三路策略
                skus = await self._extract_skus(
                    raw, page_type, screenshot, features,
                    ocr_blocks, layout_regions, ocr_text_len,
                    sku_count_hint=plan.expected_sku_range,
                    scene_filter=plan.scene_filter,
                    plan=plan)
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

            # ═══ Phase 6.35: MIXED_OTHER 切片回退 ═══
            if (not skus
                    and plan.page_class == "MIXED_OTHER"
                    and effective_screenshot
                    and fitz_meta.page_height > 0):
                # 高 DPI 重渲 + 三等分 (比二等分更细粒度，有助识别小字型号)
                n_slices = 3
                slice_h = fitz_meta.page_height / n_slices
                page_w = fitz_meta.page_width
                slice_bboxes = [
                    (0, i * slice_h, page_w, (i + 1) * slice_h)
                    for i in range(n_slices)
                ]
                slice_tasks = [
                    loop.run_in_executor(
                        None, render_slice, file_path, page_no, bbox, 300)
                    for bbox in slice_bboxes
                ]
                slice_results = await asyncio.gather(
                    *slice_tasks, return_exceptions=True)
                for sr in slice_results:
                    if isinstance(sr, Exception) or not sr:
                        continue
                    # 直接用 Vision 提取 (不走 OCR-guided, 因为 OCR 数据来自全页)
                    slice_skus = await self._single_stage.extract(
                        raw, screenshot=sr,
                        sku_count_hint=(1, 8),
                        scene_filter=False,
                        page_class=plan.page_class)
                    if slice_skus:
                        skus.extend(slice_skus)
                if skus:
                    skus = dedup_by_model(skus)
                    skus = dedup_by_similarity(skus)
                    extraction_method = "mixed_other_sliced"
                    logger.info("mixed_other_slice_rescue", page=page_no,
                                found=len(skus))

            # ═══ Phase 6.355: Type-A 零 SKU 切片回退 ═══
            # ocr_guided/整页提取均失败的 Type-A 页面，用切片兜底
            if (not skus
                    and page_type == "A"
                    and effective_screenshot
                    and ocr_text_len > 50
                    and fitz_meta.page_height > 0):
                n_slices = 3
                slice_h = fitz_meta.page_height / n_slices
                page_w = fitz_meta.page_width
                slice_bboxes = [
                    (0, i * slice_h, page_w, (i + 1) * slice_h)
                    for i in range(n_slices)
                ]
                slice_tasks = [
                    loop.run_in_executor(
                        None, render_slice, file_path, page_no, bbox, 300)
                    for bbox in slice_bboxes
                ]
                slice_results = await asyncio.gather(
                    *slice_tasks, return_exceptions=True)
                for sr in slice_results:
                    if isinstance(sr, Exception) or not sr:
                        continue
                    slice_skus = await self._single_stage.extract(
                        raw, screenshot=sr,
                        sku_count_hint=(1, 10),
                        scene_filter=False,
                        page_class=plan.page_class)
                    if slice_skus:
                        skus.extend(slice_skus)
                if skus:
                    skus = dedup_by_model(skus)
                    skus = dedup_by_similarity(skus)
                    extraction_method = "type_a_slice_rescue"
                    logger.info("type_a_slice_rescue", page=page_no,
                                found=len(skus))

            # ═══ Phase 6.36: IMG_LABEL 零 SKU 回退 ═══
            if (not skus
                    and plan.page_class == IMG_LABEL
                    and effective_screenshot):
                # 先尝试 OCR 路径
                if ocr_text_len > 50:
                    logger.info("img_label_ocr_fallback", page=page_no,
                                ocr_chars=ocr_text_len)
                    skus = await self._extract_skus(
                        raw, page_type, effective_screenshot, features,
                        ocr_blocks, layout_regions, ocr_text_len,
                        sku_count_hint=plan.expected_sku_range,
                        scene_filter=plan.scene_filter, plan=plan)
                    if skus:
                        extraction_method = "img_label_ocr_fallback"

                # 仍无结果 → 关闭 scene_filter 重试 vision
                if not skus:
                    logger.info("img_label_no_scene_retry", page=page_no)
                    skus = await self._single_stage.extract(
                        raw, screenshot=effective_screenshot,
                        sku_count_hint=plan.expected_sku_range,
                        scene_filter=False,
                        page_class=plan.page_class)
                    if skus:
                        extraction_method = "img_label_no_scene_fallback"

                if skus:
                    logger.info("img_label_fallback_done", page=page_no,
                                method=extraction_method, found=len(skus))

            # ═══ Phase 6.37: pure_visual 切片回退 ═══
            # 纯图产品页 (text≤30, img_coverage>85%) 零 SKU 时，
            # 强制三等分切片重试，不论原始页面分类
            if (not skus
                    and plan.pure_visual
                    and effective_screenshot
                    and fitz_meta.page_height > 0
                    and not plan.slices):  # 已走过切片路径的不重复
                n_slices = 3
                slice_h = fitz_meta.page_height / n_slices
                page_w = fitz_meta.page_width
                pv_bboxes = [
                    (0, i * slice_h, page_w, (i + 1) * slice_h)
                    for i in range(n_slices)
                ]
                pv_tasks = [
                    loop.run_in_executor(
                        None, render_slice, file_path, page_no, bbox, 300)
                    for bbox in pv_bboxes
                ]
                pv_results = await asyncio.gather(
                    *pv_tasks, return_exceptions=True)
                for sr in pv_results:
                    if isinstance(sr, Exception) or not sr:
                        continue
                    pv_skus = await self._single_stage.extract(
                        raw, screenshot=sr,
                        sku_count_hint=(1, 8),
                        scene_filter=False,
                        page_class=plan.page_class)
                    if pv_skus:
                        skus.extend(pv_skus)
                if skus:
                    skus = dedup_by_model(skus)
                    skus = dedup_by_similarity(skus)
                    extraction_method = "pure_visual_sliced"
                    logger.info("pure_visual_slice_rescue", page=page_no,
                                found=len(skus))

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

            # ═══ Phase 6.45: IMG_DENSE 细粒度二次切片 ═══
            # 切片已提取到 SKU 但数量远低于预期 → 用图片 bbox 生成更细粒度切片
            if (plan.page_class == IMG_DENSE
                    and len(skus) >= 2
                    and fitz_meta.image_bboxes
                    and fitz_meta.page_height > 0):
                expected_min = plan.expected_sku_range[0] or 4
                if len(skus) < expected_min * 0.8:
                    refined_bboxes = _make_refined_slices(
                        fitz_meta.image_bboxes,
                        fitz_meta.page_width, fitz_meta.page_height,
                        max_slices=20)
                    if refined_bboxes and len(refined_bboxes) > len(plan.slices or []):
                        logger.info("img_dense_refined_slicing",
                                    page=page_no,
                                    current_skus=len(skus),
                                    expected_min=expected_min,
                                    refined_slices=len(refined_bboxes))
                        ref_tasks = [
                            loop.run_in_executor(
                                None, render_slice, file_path, page_no, bbox, 250)
                            for bbox in refined_bboxes
                        ]
                        ref_results = await asyncio.gather(
                            *ref_tasks, return_exceptions=True)
                        ref_skus: list[SKUResult] = []
                        for sr in ref_results:
                            if isinstance(sr, Exception) or not sr:
                                continue
                            slice_skus = await self._single_stage.extract(
                                raw, screenshot=sr,
                                sku_count_hint=(1, 4),
                                scene_filter=plan.scene_filter,
                                page_class=plan.page_class)
                            if slice_skus:
                                ref_skus.extend(slice_skus)
                        if ref_skus:
                            skus.extend(ref_skus)
                            skus = dedup_by_model(skus)
                            skus = dedup_by_similarity(skus)
                            logger.info("img_dense_refined_done",
                                        page=page_no, total=len(skus))

            # ═══ Phase 6.46: 通用高密度不足检测 ═══
            # 有 SKU 但远低于预期 → rescue 补充
            if (plan.page_class in (SINGLE_LARGE, SINGLE_TALL, MULTI_SPARSE, IMG_LABEL, MIXED_OTHER)
                    and len(skus) >= 1
                    and effective_screenshot):
                expected_min = plan.expected_sku_range[0] or 4
                # 降低触发阈值：当前SKU数 < 预期最小值的 85%（原来是 70%）
                if len(skus) < expected_min * 0.85:
                    logger.info("high_density_undercount_rescue",
                                page=page_no,
                                current_skus=len(skus),
                                expected_min=expected_min)
                    rescue_skus = await self._single_stage.extract_rescue(
                        raw, screenshot=effective_screenshot)
                    if rescue_skus:
                        skus.extend(rescue_skus)
                        skus = dedup_by_model(skus)
                        skus = dedup_by_similarity(skus)
                        logger.info("high_density_rescue_done",
                                    page=page_no, total=len(skus))

            # ═══ Phase 6.5: 综合打分 + 去重链 ═══
            if skus:
                before = len(skus)
                ocr_full_text = OcrEngine.blocks_to_text(ocr_blocks) if ocr_blocks else ""

                # IMG_DENSE/IMG_LABEL + grid → 放宽去重（网格产品名称相似是正常的）
                is_image_catalog = plan.page_class in (IMG_DENSE, IMG_LABEL) and fitz_meta.grid

                # 综合打分替代 pre_filter + ocr_cross_validate
                _page_has_model = any(
                    (s.attributes.get("model_number") or "").strip()
                    for s in skus
                )
                skus = score_and_filter(skus, ocr_text=ocr_full_text,
                                         catalog_profile=catalog_profile,
                                         scene_filter=plan.scene_filter,
                                         page_has_model_bearing=_page_has_model,
                                         pure_visual=plan.pure_visual)
                skus = split_compound_models(skus)
                skus = dedup_by_model(skus)
                skus = _merge_variant_size(skus)
                skus = dedup_by_model_variant(skus)
                skus = dedup_material_variants(skus)
                if not is_image_catalog:
                    skus = dedup_by_similarity(skus)

                if len(skus) < before:
                    logger.info("dedup_chain_applied",
                                page=page_no, before=before, after=len(skus))

                # 过滤后 SKU 全部被清除 → 触发 post-filter rescue
                if not skus and page_type in ("B", "C") and effective_screenshot:
                    logger.info("post_filter_rescue", page=page_no, before_filter=before)
                    rescue_skus = await self._single_stage.extract_rescue(
                        raw, screenshot=effective_screenshot,
                        scene_filter=plan.scene_filter)
                    if rescue_skus:
                        skus = score_and_filter(rescue_skus, ocr_text=ocr_full_text,
                                                 catalog_profile=catalog_profile,
                                                 scene_filter=plan.scene_filter,
                                                 page_has_model_bearing=False,
                                                 pure_visual=plan.pure_visual)
                        skus = dedup_by_model(skus)
                        if not is_image_catalog:
                            skus = dedup_by_similarity(skus)
                        logger.info("post_filter_rescue_done",
                                    page=page_no, rescued=len(skus))

            # ═══ Phase 6.55: Companion Rescue (配套产品补提取) ═══
            # Companion SKU 经过 scorer 过滤后再加入
            if (1 <= len(skus) <= 2
                    and plan.page_class in (SINGLE_LARGE, SINGLE_TALL, IMG_LABEL,
                                            "MULTI_SPARSE", IMG_DENSE)
                    and effective_screenshot):
                main_names = [s.attributes.get("product_name", "") for s in skus]
                companion_skus = await self._single_stage.extract_companion(
                    raw, screenshot=effective_screenshot, main_products=main_names)
                if companion_skus:
                    ocr_full_text_c = OcrEngine.blocks_to_text(ocr_blocks) if ocr_blocks else ""
                    _main_has_model = any(
                        (s.attributes.get("model_number") or "").strip()
                        for s in skus
                    )
                    companion_skus = score_and_filter(
                        companion_skus, ocr_text=ocr_full_text_c,
                        catalog_profile=catalog_profile,
                        scene_filter=plan.scene_filter,
                        page_has_model_bearing=_main_has_model,
                        pure_visual=plan.pure_visual)
                    for cs in companion_skus:
                        cs.extraction_method = "companion_rescue"
                    skus.extend(companion_skus)
                    skus = dedup_by_model(skus)
                    logger.info("companion_rescue_done", page=page_no,
                                found=len(companion_skus))

            # ═══ Phase 6.58: 文本规则提取（回退 + 补充）═══
            # 从 PDF 矢量文本提取型号，补充 LLM 遗漏的 SKU
            if raw.raw_text:
                text_skus = _extract_models_from_text(raw.raw_text, page_no)
                if text_skus:
                    if not skus:
                        # 零 SKU → 直接用文本规则结果
                        skus = text_skus
                        extraction_method = "text_rule_fallback"
                        logger.info("text_rule_final_fallback", page=page_no,
                                    found=len(text_skus))
                    elif len(text_skus) > len(skus) * 1.5:
                        # LLM 提取远少于文本规则 → 合并补充 (用 normalize_model 去重)
                        existing_models = {
                            normalize_model(s.attributes.get("model_number") or "")
                            for s in skus if s.attributes.get("model_number")
                        }
                        added = 0
                        for ts in text_skus:
                            tm = normalize_model(ts.attributes.get("model_number") or "")
                            if tm and tm not in existing_models:
                                skus.append(ts)
                                existing_models.add(tm)
                                added += 1
                        if added:
                            logger.info("text_rule_supplement", page=page_no,
                                        added=added, total=len(skus))

                # 纯图目录 + SINGLE_* + 零 SKU → 用页面首行文字作产品名
                if (not skus
                        and catalog_profile
                        and catalog_profile.is_pure_image_catalog
                        and plan.page_class in ("SINGLE_STD", "SINGLE_LARGE",
                                                "SINGLE_TALL")):
                    page_text = raw.raw_text.strip()
                    first_line = page_text.split('\n')[0].strip() if page_text else ""
                    if 1 <= len(first_line) <= 20:
                        skus = [SKUResult(
                            sku_id="",
                            attributes={
                                "product_name": first_line,
                                "model_number": "",
                            },
                            confidence=0.35,
                            extraction_method="pure_image_text_fallback",
                        )]
                        extraction_method = "pure_image_text_fallback"
                        logger.info("pure_image_text_fallback", page=page_no,
                                    name=first_line)

            # ═══ Phase 6.585: 纯图零 SKU Vision 兜底 ═══
            # 零 SKU + 纯图目录 + 有截图 + 非 BLANK → 300 DPI 重渲 + rescue
            if (not skus
                    and plan.pure_visual
                    and screenshot
                    and plan.page_class != BLANK):
                logger.info("pure_visual_zero_sku_rescue", page=page_no,
                            page_class=plan.page_class)
                try:
                    hi_dpi_img = await loop.run_in_executor(
                        None, render_slice, file_path, page_no,
                        (0, 0, fitz_meta.page_width, fitz_meta.page_height), 300)
                    if hi_dpi_img:
                        rescue_skus = await self._single_stage.extract_rescue(
                            raw, screenshot=hi_dpi_img, scene_filter=False)
                        if rescue_skus:
                            ocr_full_text = OcrEngine.blocks_to_text(ocr_blocks) if ocr_blocks else ""
                            _rescue_has_model = any(
                                (s.attributes.get("model_number") or "").strip()
                                for s in rescue_skus
                            )
                            rescue_skus = score_and_filter(
                                rescue_skus, ocr_text=ocr_full_text,
                                catalog_profile=catalog_profile,
                                scene_filter=False,
                                page_has_model_bearing=_rescue_has_model,
                                pure_visual=True)
                            if rescue_skus:
                                skus = rescue_skus
                                extraction_method = "pure_visual_rescue"
                                logger.info("pure_visual_rescue_done",
                                            page=page_no, found=len(skus))
                except Exception as e:
                    logger.warning("pure_visual_rescue_failed",
                                   page=page_no, error=str(e))

            # ═══ Phase 6.586: 混合型PDF无文字页面兜底 ═══
            # 非纯图目录，但当前页面无文字+有图片+零SKU → 可能是产品展示页
            # 用 pure_visual 模式尝试提取
            if (not skus
                    and not (catalog_profile and catalog_profile.is_pure_image_catalog)
                    and not (raw.raw_text or "").strip()
                    and screenshot
                    and plan.page_class != BLANK):
                logger.info("mixed_pdf_no_text_rescue", page=page_no,
                            page_class=plan.page_class)
                try:
                    rescue_skus = await self._single_stage.extract_rescue(
                        raw, screenshot=screenshot, scene_filter=False)
                    if rescue_skus:
                        rescue_skus = score_and_filter(
                            rescue_skus, ocr_text="",
                            catalog_profile=catalog_profile,
                            scene_filter=False,
                            pure_visual=True)
                        if rescue_skus:
                            skus = rescue_skus
                            extraction_method = "mixed_pdf_no_text_rescue"
                            logger.info("mixed_pdf_no_text_rescue_done",
                                        page=page_no, found=len(skus))
                except Exception as e:
                    logger.warning("mixed_pdf_no_text_rescue_failed",
                                   page=page_no, error=str(e))

            # ═══ Phase 6.59: IMG_DENSE figure rescue ═══
            # IMG_DENSE 零 SKU + YOLO 检测到 figure → 按区域裁剪让 LLM 识别产品
            # 单 figure 覆盖整页时，用整页截图 + 强制枚举 hint
            if (not skus
                    and plan.page_class == IMG_DENSE
                    and layout_regions
                    and screenshot):
                figure_regions = [
                    r for r in layout_regions
                    if r.label in _FIGURE_LABELS
                ]
                if figure_regions:
                    figure_regions.sort(
                        key=lambda r: abs(r.bbox[2] - r.bbox[0]) * abs(r.bbox[3] - r.bbox[1]),
                        reverse=True,
                    )
                    figure_regions = figure_regions[:12]

                    from PIL import Image as PILImage
                    pil_img = PILImage.open(io.BytesIO(screenshot))
                    img_w, img_h = pil_img.size

                    _RESCUE_HINT = (
                        "这是一个产品目录页面，包含多个独立产品图片。"
                        "请仔细观察页面中每一个独立的产品图片区域，"
                        "为每个产品提取名称。不要遗漏任何产品。"
                    )

                    crop_tasks = []
                    if len(figure_regions) == 1:
                        # 单 figure 覆盖整页 → 用整页截图 + 强制枚举
                        sku_lo = plan.expected_sku_range[0] or 2
                        sku_hi = plan.expected_sku_range[1] or 8
                        crop_tasks.append(self._single_stage.extract(
                            raw, screenshot=screenshot,
                            sku_count_hint=(sku_lo, sku_hi),
                            region_hint=_RESCUE_HINT,
                            scene_filter=False,
                            page_class=plan.page_class,
                        ))
                    else:
                        for region in figure_regions:
                            x0, y0, x1, y1 = region.bbox
                            crop = pil_img.crop(
                                (int(x0), int(y0), int(x1), int(y1)))
                            buf = io.BytesIO()
                            crop.save(buf, format="JPEG", quality=85)
                            crop_bytes = buf.getvalue()

                            crop_tasks.append(self._single_stage.extract(
                                raw, screenshot=crop_bytes,
                                sku_count_hint=(1, 3),
                                region_hint=_RESCUE_HINT,
                                scene_filter=False,
                                page_class=plan.page_class,
                            ))

                    if crop_tasks:
                        crop_results = await asyncio.gather(
                            *crop_tasks, return_exceptions=True)
                        for r in crop_results:
                            if isinstance(r, list) and r:
                                for s in r:
                                    s.extraction_method = "img_dense_figure_rescue"
                                skus.extend(r)

                        if skus:
                            skus = dedup_by_model(skus)
                            skus = dedup_by_similarity(skus, threshold=0.90)
                            extraction_method = "img_dense_figure_rescue"
                            logger.info("img_dense_figure_rescue",
                                        page=page_no,
                                        figures=len(figure_regions),
                                        skus=len(skus))

            # ═══ Phase 6.6: SKUReviewer Pass 2 (B/C 类 + 有 SKU) ═══
            # 仅 IMG_LABEL+grid 跳过（有文字标签，幻觉率低）
            # IMG_DENSE 需要 Reviewer 过滤场景装饰物
            review_screenshot = screenshot or effective_screenshot
            skip_review = plan.page_class == IMG_LABEL and fitz_meta.grid
            if page_type in ("B", "C") and skus and review_screenshot and not skip_review:
                before_review = len(skus)
                skus = await self._reviewer.review(
                    skus, screenshot=review_screenshot,
                    scene_filter=plan.scene_filter,
                    pure_visual=plan.pure_visual)
                if len(skus) < before_review:
                    logger.info("reviewer_applied",
                                page=page_no, before=before_review, after=len(skus))

            # ═══ Phase 6.7: IMG_DENSE 幻觉安全阀 ═══
            # 如果页面 SKU 数远超预期，且大部分无型号+低 confidence → 幻觉爆炸
            if (skus
                    and plan.page_class == IMG_DENSE
                    and len(skus) > plan.expected_sku_range[1] * 3):
                no_model = sum(
                    1 for s in skus
                    if not (s.attributes.get("model_number") or "").strip()
                )
                low_conf = sum(1 for s in skus if s.confidence < 0.4)
                if no_model > len(skus) * 0.7 and low_conf > len(skus) * 0.5:
                    # 保留有型号的 + confidence >= 0.5 的
                    before_halluc = len(skus)
                    skus = [
                        s for s in skus
                        if (s.attributes.get("model_number") or "").strip()
                        or s.confidence >= 0.5
                    ]
                    logger.warning("img_dense_hallucination_filter",
                                   page=page_no,
                                   before=before_halluc,
                                   after=len(skus),
                                   no_model_ratio=f"{no_model}/{before_halluc}",
                                   low_conf_ratio=f"{low_conf}/{before_halluc}")

            # ═══ Phase 6.8: 页面级无型号密度过滤 ═══
            # 条件: 页面SKU数>=5 且 无型号占比>80% → 只保留有型号或长名称(>5字)的SKU
            # 目标: 缩略图/目录总览页的泛化名称FP (如30个"沙发")
            if len(skus) >= 5:
                _no_model_count = sum(
                    1 for s in skus
                    if not (s.attributes.get("model_number") or "").strip()
                )
                if _no_model_count > len(skus) * 0.8:
                    before_density = len(skus)
                    skus = [
                        s for s in skus
                        if (s.attributes.get("model_number") or "").strip()
                        or len((s.attributes.get("product_name") or "").strip()) > 5
                    ]
                    if len(skus) < before_density:
                        logger.info("no_model_density_filter",
                                    page=page_no, before=before_density,
                                    after=len(skus))

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
            bindings = self._binder.bind(skus, raw.images, cls_result, page_plan=plan)

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
        catalog_profile: CatalogProfile | None = None,
        ocr_text: str = "",
    ) -> list[SKUResult]:
        """切片模式提取: 每片独立送 LLM，合并去重。"""
        lo, hi = plan.expected_sku_range
        n = len(plan.slices)
        slice_lo = max(2, lo // n)
        slice_hi = max(5, (hi + n - 1) // n)
        # SINGLE_TALL 纯图页面：提高每片上限，鼓励 LLM 更彻底搜索
        if plan.page_class == SINGLE_TALL and slice_hi < 10:
            slice_hi = 10
        slice_range = (slice_lo, slice_hi)

        tasks = []
        slice_indices = []  # 记录每个 task 对应的切片索引
        for i, (ss, bbox) in enumerate(zip(screenshots, plan.slices)):
            if not ss:
                continue
            hint = f"这是页面的第{i+1}/{len(plan.slices)}个区域 (共{len(plan.slices)}片)"
            tasks.append(self._single_stage.extract(
                raw, screenshot=ss,
                sku_count_hint=slice_range,
                region_hint=hint,
                scene_filter=plan.scene_filter,
                page_class=plan.page_class))
            slice_indices.append(i)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_skus: list[SKUResult] = []
        retry_indices = []  # 零 SKU 的切片需要重试
        for idx, r in zip(slice_indices, results):
            if isinstance(r, Exception):
                logger.warning("slice_extract_failed", error=str(r))
                retry_indices.append(idx)
            elif isinstance(r, list):
                if r:
                    all_skus.extend(r)
                elif plan.page_class in (IMG_DENSE, IMG_LABEL) or (slice_lo >= 2 and len(plan.slices) <= 6):
                    # IMG_DENSE/IMG_LABEL: 零结果切片始终重试（纯图页不应有空片）
                    # 其他页面: 预期每片有 ≥2 SKU 但返回 0 → 重试
                    retry_indices.append(idx)

        # 重试零 SKU 切片（每页产品密度高时，空切片通常是 LLM 遗漏）
        # 允许最多 75% 切片失败仍触发重试
        if retry_indices and len(retry_indices) <= len(plan.slices):
            retry_tasks = []
            for idx in retry_indices:
                ss = screenshots[idx]
                if not ss:
                    continue
                hint = (f"这是页面的第{idx+1}/{len(plan.slices)}个区域。"
                        f"请先数一数这个区域有几个不同的产品图片，然后逐一提取。"
                        f"即使没有文字标注，每个产品图片也要提取一条记录。"
                        f"product_name 用简短中文描述(如'餐椅'、'沙发')即可。")
                retry_range = (1, slice_hi)  # 降低下限，放宽预期
                retry_tasks.append(self._single_stage.extract(
                    raw, screenshot=ss,
                    sku_count_hint=retry_range,
                    region_hint=hint,
                    scene_filter=False,
                    page_class=plan.page_class))
            if retry_tasks:
                retry_results = await asyncio.gather(
                    *retry_tasks, return_exceptions=True)
                retry_found = 0
                for r in retry_results:
                    if isinstance(r, list) and r:
                        all_skus.extend(r)
                        retry_found += len(r)
                if retry_found:
                    logger.info("slice_retry_rescued", retried=len(retry_indices),
                                rescued=retry_found)

        if all_skus:
            # 切片合并后: 综合打分 + 去重 (与整页模式对齐)
            before = len(all_skus)
            _slice_has_model = any(
                (s.attributes.get("model_number") or "").strip()
                for s in all_skus
            )
            all_skus = score_and_filter(all_skus, ocr_text=ocr_text,
                                          catalog_profile=catalog_profile,
                                          scene_filter=plan.scene_filter,
                                          page_has_model_bearing=_slice_has_model,
                                          pure_visual=plan.pure_visual)
            all_skus = split_compound_models(all_skus)
            all_skus = dedup_by_model(all_skus)
            # 密集产品页面: IMG_DENSE pure_visual 只按型号去重，跳过名称去重
            # (同类不同产品名称一样是正常的，如"餐椅"x20)
            if plan.page_class == IMG_DENSE and plan.pure_visual:
                pass  # 已做 dedup_by_model，跳过 similarity 去重
            elif plan.page_class in (IMG_DENSE, IMG_LABEL, SINGLE_TALL):
                all_skus = dedup_by_similarity(all_skus, threshold=0.90)
            else:
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
        plan: PagePlan | None = None,
    ) -> list[SKUResult]:
        """Phase 6: 融合策略提取。

        - A 类 (表格页): 规则表格提取
        - B/C 类: OCR-Guided + Vision 并行融合，合并去重
        """

        # A 类: 规则表格提取
        has_screenshot = bool(screenshot)
        if page_type == "A" and raw.tables:
            table_skus = self._table_extract(raw)
            # MIXED_TABLE: 表格面积不够大，补充 Vision 提取非表格区域
            if plan and plan.page_class == MIXED_TABLE and has_screenshot:
                vision_skus = await self._single_stage.extract(
                    raw, screenshot=screenshot,
                    sku_count_hint=sku_count_hint,
                    scene_filter=scene_filter,
                    page_class=plan.page_class if plan else None)
                if vision_skus:
                    table_skus.extend(vision_skus)
                    table_skus = dedup_by_model(table_skus)
            # R1: TABLE/MIXED_TABLE 零结果 → vision 回退
            # 某些 TABLE 页 (如佛山奢品嘉) 实际是图文混排，表格规则提取零结果
            if not table_skus and has_screenshot:
                logger.info("table_zero_vision_fallback", page=raw.page_no,
                            page_class=plan.page_class if plan else None)
                table_skus = await self._single_stage.extract(
                    raw, screenshot=screenshot,
                    sku_count_hint=sku_count_hint,
                    scene_filter=scene_filter,
                    page_class=plan.page_class if plan else None)
                if table_skus:
                    for s in table_skus:
                        s.extraction_method = "table_vision_fallback"
            return table_skus

        # B/C 类: OCR-Guided + Vision 并行融合
        has_ocr = (ocr_text_len >= settings.ocr_min_text_length and ocr_blocks)

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
                    scene_filter=scene_filter,
                    page_class=plan.page_class if plan else None)))
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

    @staticmethod
    def _merge_combo_skus(skus: list[SKUResult], page_no: int) -> list[SKUResult]:
        """组合图册: 将同页多个 SKU 合并为一个组合 SKU。

        选 confidence 最高的作为主产品，其他产品名称用 " + " 追加，
        型号用 " / " 连接。
        """
        if len(skus) < 2:
            return skus

        # 按 confidence 降序
        sorted_skus = sorted(skus, key=lambda s: s.confidence, reverse=True)
        main = sorted_skus[0]
        others = sorted_skus[1:]

        # 合并产品名称
        main_name = main.attributes.get("product_name", "")
        other_names = [
            s.attributes.get("product_name", "") for s in others
            if s.attributes.get("product_name", "")
        ]
        if other_names:
            combined_name = main_name + " + " + " + ".join(other_names)
            main.attributes["product_name"] = combined_name

        # 合并型号
        main_model = main.attributes.get("model_number", "")
        other_models = [
            s.attributes.get("model_number", "") for s in others
            if s.attributes.get("model_number", "")
        ]
        if other_models:
            all_models = [main_model] + other_models if main_model else other_models
            main.attributes["model_number"] = " / ".join(all_models)

        main.extraction_method = "combo_merge"

        logger.info("combo_merge", page=page_no,
                     original=len(skus), merged_name=main.attributes.get("product_name", ""))

        return [main]

    def clear_job_cache(self, job_id: str) -> None:
        self._xpage.clear_job(job_id)
