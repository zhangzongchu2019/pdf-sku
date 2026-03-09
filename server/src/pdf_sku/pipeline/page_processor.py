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
import math
import hashlib
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from pdf_sku.pipeline.ir import (
    ParsedPageIR, FeatureVector, ClassifyResult, PageResult,
    SKUResult, ImageInfo, BindingResult, ValidationResult, TableData,
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


_PRODUCT_REGION_PROMPT = """\
This is a furniture product catalog page image.

The following {n} products have been identified on this page:
{product_list}

For each product, identify ALL its individual photo panels separately:
- "product_photo": the product shown alone on a clean/white background
- "lifestyle_photo": the product shown in a room or scene setting (if visible)

Return a JSON array with one entry per individual photo panel found:
[
  {{"product_index": 0, "photo_type": "product_photo", "bbox": [x0, y0, x1, y1]}},
  {{"product_index": 0, "photo_type": "lifestyle_photo", "bbox": [x0, y0, x1, y1]}},
  {{"product_index": 1, "photo_type": "product_photo", "bbox": [x0, y0, x1, y1]}},
  {{"product_index": 1, "photo_type": "lifestyle_photo", "bbox": [x0, y0, x1, y1]}},
  ...
]

RULES:
1. product_index is 0-indexed, matching the product list above
2. Each bbox should cover the ENTIRE photo panel region — include all product views, angles, and close-ups shown together in that panel area. Be generous: extend to the natural boundary of the photo zone (edge of the image or the dividing line between panels). Do NOT crop into the product.
3. Only include photo panels clearly visible on this page
4. If a product has no lifestyle photo on this page, omit it — do not fabricate one
5. Every product must have at least one "product_photo" entry

Image size: {img_w} × {img_h} pixels. Use integer pixel coordinates.
Respond ONLY with the JSON array, no other text."""


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
            RENDER_DPI = 150
            dpi_scale = RENDER_DPI / 72.0
            for img in raw.images:
                # 原生像素尺寸
                native_short = min(img.width, img.height) if img.width and img.height else 0
                # 显示尺寸 (bbox @150dpi): 处理瓦片 PDF 中低分辨率图片被放大显示的情况
                display_short = 0
                if img.bbox != (0, 0, 0, 0) and len(img.bbox) >= 4:
                    dw = abs(img.bbox[2] - img.bbox[0]) * dpi_scale
                    dh = abs(img.bbox[3] - img.bbox[1]) * dpi_scale
                    display_short = int(min(dw, dh))
                img.short_edge = max(native_short, display_short)
                img.search_eligible = img.short_edge >= 150
                if img.data:
                    img.image_hash = hashlib.md5(img.data[:2048]).hexdigest()[:12]

            # ═══ Phase 2a: 图片去重 ═══
            raw.images = self._dedup_images(raw.images)

            # ═══ Phase 2a2: 过滤跨页溢出图片 ═══
            # bbox[3] (底边) 超出页面高度 + 5pt 容差 → 属于下一页产品，排除当前页绑定
            page_h = raw.metadata.page_height
            for img in raw.images:
                if (len(img.bbox) >= 4
                        and img.bbox[3] > page_h + 5
                        and img.search_eligible):
                    img.search_eligible = False
                    logger.info("image_overflow_excluded",
                                page=page_no,
                                image_id=img.image_id,
                                img_bottom=round(img.bbox[3], 1),
                                page_height=round(page_h, 1))

            # ═══ Phase 2a3: 过滤全页背景图 ═══
            # 覆盖 >80% 页面面积的图片通常是装饰背景，不应绑定给 SKU。
            # 但若该图是页面上的唯一商品图（全页商品展示图），则保留为商品图。
            page_w = raw.metadata.page_width
            page_area = max(1.0, page_w * page_h)
            eligible_imgs = [i for i in raw.images if i.search_eligible and len(i.bbox) >= 4]
            for img in raw.images:
                if not img.search_eligible or len(img.bbox) < 4:
                    continue
                img_area = abs(img.bbox[2] - img.bbox[0]) * abs(img.bbox[3] - img.bbox[1])
                if img_area / page_area > 0.8:
                    # 仅当页面上还有其他合格图片时才视为背景并过滤
                    # 若是唯一合格图片，保留为商品展示图
                    other_eligible = [i for i in eligible_imgs if i.image_id != img.image_id]
                    if other_eligible:
                        img.search_eligible = False
                        img.role = "background"
                        logger.info("image_fullpage_background_excluded",
                                    page=page_no, image_id=img.image_id,
                                    coverage=round(img_area / page_area, 2))
                    else:
                        logger.info("image_fullpage_product_kept",
                                    page=page_no, image_id=img.image_id,
                                    coverage=round(img_area / page_area, 2))

            # ═══ Phase 2b: 瓦片碎片聚类合并 ═══
            raw.images = self._merge_tile_fragments(raw.images, page_no)

            # ═══ Phase 2c: 合成大图布局检测 ═══
            raw.images = self._split_fullpage_composites(
                raw.images, page_no, raw.metadata)

            # ═══ Phase 3: 特征提取 ═══
            features = self._feat.extract(raw)

            # ═══ Phase 4: 跨页表格检测 ═══
            continuation = await self._xpage.find_continuation(
                job_id, page_no, raw, file_path=file_path)
            if continuation:
                raw.tables = self._xpage.merge(continuation.source_tables, raw.tables)

            # ═══ Phase 5: 页面分类 ═══
            screenshot = b""
            if self._pool:
                try:
                    # 纯图片密集目录页（几乎无可提取文字 + 大量图片）→ 提升渲染 DPI
                    # 150 DPI 下每个商品格约 5px 字体，LLM 难以读取，216 DPI 可提升 44%
                    _raw_text_len = len((raw.raw_text or "").strip())
                    _is_image_only = _raw_text_len < 30
                    _is_dense = len(raw.images) >= 20
                    _render_dpi = 216 if (_is_image_only and _is_dense) else 150
                    screenshot = await loop.run_in_executor(
                        self._pool, _render_page_sync, file_path, page_no, _render_dpi)
                    if _render_dpi != 150:
                        logger.info("screenshot_highres",
                                    page=page_no, dpi=_render_dpi,
                                    raw_text_len=_raw_text_len,
                                    image_count=len(raw.images))
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
                    classification_confidence=cls_result.confidence,
                    page_confidence=cls_result.confidence)

            # ═══ Phase 6: SKU 提取 ═══
            skus = await self._extract_skus_with_fallback(
                raw, page_type, screenshot, features, llm_calls_used)
            extraction_method = skus[0].extraction_method if skus else None

            # A 类: 表格每行独立 SKU，无需去重；使用 relaxed 有效性校验（可信结构化数据）
            # B/C 类: LLM 可能重复提取，需去重；使用 strict 校验
            validity_profile = {"sku_validity_mode": "relaxed"} if page_type == "A" else None
            skus = self._validator.enforce_sku_validity(
                skus, validity_profile, text_block_count=features.text_block_count)
            skus = [s for s in skus if s.validity == "valid"]
            if page_type != "A":
                # A 类: 表格行天然不重复，跳过去重以保留同名不同规格/专利号的行
                skus = self._validator.deduplicate_skus(skus)

            # ── retry: validity 全灭 或 SKU 数远少于图片数 ──
            # 包含 extraction_method=None（所有 LLM 调用均失败）的情况：
            # 并发处理时 API 限流可能导致全部失败，重试时往往可以成功
            eligible_count = sum(1 for img in raw.images if img.search_eligible)
            should_retry = (
                page_type not in ("D", "A")
                and (
                    (not skus and eligible_count >= 1)
                    or (0 < len(skus) < eligible_count * 0.7
                        and eligible_count >= 1)
                )
            )
            if should_retry:
                retry_skus = await self._extract_skus_with_fallback(
                    raw, page_type, screenshot, features, llm_calls_used=4)
                retry_skus = self._validator.enforce_sku_validity(
                    retry_skus, None, text_block_count=features.text_block_count)
                retry_skus = [s for s in retry_skus if s.validity == "valid"]
                retry_skus = self._validator.deduplicate_skus(retry_skus)
                if len(retry_skus) > len(skus):
                    skus = retry_skus
                    extraction_method = skus[0].extraction_method if skus else extraction_method
                    fallback_reason = "retry_improved"
                logger.info("sku_extraction_retry",
                            page=page_no,
                            trigger="all_invalid" if not skus else "low_coverage",
                            before_retry=len(skus),
                            after_retry=len(retry_skus),
                            adopted=len(retry_skus) > len(skus),
                            eligible_images=eligible_count)

            # ═══ Phase 6.5: 单大图多商品子图拆分 ═══
            # 当页面只有 1 张全页大图且 SKU boundary bbox 各不相同时，
            # 为每个产品区域创建独立 ImageInfo（_region_），
            # _crop_composites 在 Phase 8 后从截图裁剪实际图片数据。
            await self._maybe_create_product_regions(raw, skus, page_no, screenshot)

            # ═══ Phase 7: ID 分配 ═══
            hash_prefix = (file_hash or "unknown")[:8]
            skus = self._id_gen.assign_ids(
                skus, hash_prefix, page_no, raw.metadata.page_height)

            # ═══ Phase 8: 绑定 ═══
            # 坐标系对齐: image bbox 从 PDF points → 截图像素 (与 SKU source_bbox 同系)
            # 使用实际截图像素宽度推算缩放比，避免密集图片页以 216dpi 渲染时坐标错位
            if screenshot and len(screenshot) >= 24 and screenshot[:4] == b'\x89PNG':
                import struct as _struct
                _ss_w = _struct.unpack('>I', screenshot[16:20])[0]
                scale = _ss_w / max(1, raw.metadata.page_width or 1)
            else:
                scale = 150 / 72.0
            for img in raw.images:
                if img.bbox != (0, 0, 0, 0):
                    img.bbox = (
                        img.bbox[0] * scale,
                        img.bbox[1] * scale,
                        img.bbox[2] * scale,
                        img.bbox[3] * scale,
                    )
            eligible_images = [img for img in raw.images if img.search_eligible]

            # source_bbox 坐标对齐: PDF pts → 截图像素
            # 先无条件缩放，再用文字块覆盖有匹配的 SKU（文字块仅是精确修正，不影响无匹配的 SKU）
            if skus:
                for sku in skus:
                    sb = sku.source_bbox
                    if sb and sb != (0, 0, 0, 0):
                        sku.source_bbox = (sb[0]*scale, sb[1]*scale, sb[2]*scale, sb[3]*scale)
            if raw.text_blocks and skus:
                self._refine_sku_bboxes(skus, raw.text_blocks, scale)

            # A 类表格页: 图片与 SKU 按竖直顺序一一对应，不依赖空间 bbox 匹配
            # （_table_extract 给所有 SKU 相同的 table.bbox，空间绑定无法区分行）
            if page_type == "A" and skus:
                bindings = self._bind_table_by_row_order(
                    skus, eligible_images, raw.tables, scale)
            else:
                bindings = self._binder.bind(skus, eligible_images, cls_result)

            # VLM 辅助绑定: 文字层极少或绑定质量低时用 VLM 视觉匹配
            avg_bind_conf = (sum(b.confidence for b in bindings) / len(bindings)) if bindings else 0
            low_quality_bind = avg_bind_conf < 0.5 and len(skus) >= 2
            few_text = len(raw.text_blocks) <= 3
            # 多图页但所有 SKU 都绑到同一张图 → 空间绑定失效（SKU 共享同一 text-block bbox）
            all_same_single_image = (
                len(eligible_images) > 1
                and len(skus) > 1
                and bool(bindings)
                and len({b.image_id for b in bindings if b.image_id}) == 1
            )
            # 多图页但大量 SKU 集中于少数图片，其余图片无绑定 → 空间绑定失效
            # （LLM boundary 把多个不同产品归入同一大 bbox，binder 全映射到中心最近图片）
            _bound_img_counts = Counter(b.image_id for b in bindings if b.image_id)
            _max_single_img_skus = max(_bound_img_counts.values(), default=0)
            _unbound_img_count = len(eligible_images) - len(_bound_img_counts)
            overcrowded_binding = (
                len(eligible_images) >= 3
                and len(skus) >= 3
                and _max_single_img_skus > len(skus) * 0.4
                and _unbound_img_count > 0
            )
            # 空间绑定已高质且无歧义 → 跳过 VLM rebind（纯图片密集页 source_bbox=image_bbox 精准匹配）
            high_quality_spatial = (
                avg_bind_conf >= 0.85
                and not all_same_single_image
                and not overcrowded_binding
            )
            logger.info("phase8_bind_decision",
                        avg_bind_conf=round(avg_bind_conf, 3),
                        few_text=few_text,
                        low_quality_bind=low_quality_bind,
                        all_same_single_image=all_same_single_image,
                        overcrowded_binding=overcrowded_binding,
                        max_single_img_skus=_max_single_img_skus,
                        unbound_img_count=_unbound_img_count,
                        high_quality_spatial=high_quality_spatial,
                        n_bindings=len(bindings),
                        n_skus=len(skus),
                        n_eligible_imgs=len(eligible_images))
            if (not high_quality_spatial
                    and (few_text or low_quality_bind or all_same_single_image
                         or overcrowded_binding)
                    and len(eligible_images) >= 1
                    and len(skus) >= 2 and screenshot and self._llm):
                vlm_bindings = await self._vlm_rebind_composites(
                    skus, eligible_images, screenshot)
                if vlm_bindings:
                    # 合并模式: VLM 匹配的覆盖空间绑定，未匹配的保留原绑定
                    vlm_sku_ids = {b.sku_id for b in vlm_bindings}
                    kept = [b for b in bindings if b.sku_id not in vlm_sku_ids]
                    bindings = vlm_bindings + kept

            # VLM 后修正: 同列独立产品图按位置顺序匹配人位变体
            bindings = self._correct_column_isolated_bindings(
                bindings, skus, eligible_images)

            # 虚拟图片裁剪: 从截图生成实际图片数据
            if screenshot:
                self._crop_composites(raw.images, screenshot)

            # ═══ Phase 9: 校验 + 导出 ═══
            validation = self._validator.validate(
                page_type, skus, raw.images, bindings)

            exported = await self._exporter.export(
                skus, job_id, page_no)

            page_confidence = self._compute_page_confidence(
                cls_result, skus, bindings, validation,
                extraction_method, fallback_reason,
            )
            needs_review = page_confidence < 0.6

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
                llm_model_used=self._llm.current_model_name if self._llm else None,
                fallback_reason=fallback_reason,
                page_confidence=page_confidence,
                screenshot=screenshot,
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
                # 获取截图实际像素尺寸，传给 VLM 做坐标归一化
                _img_size = self._two_stage._get_image_size(screenshot) if screenshot else (0, 0)
                _page_size = (
                    raw.metadata.page_width or 0.0,
                    raw.metadata.page_height or 0.0,
                )
                boundaries = await self._two_stage.identify_boundaries(
                    raw.text_blocks, None, screenshot, image_size=_img_size,
                    images=raw.images, page_size=_page_size)
                if boundaries:
                    skus = await self._two_stage.extract_batch(
                        boundaries, raw, screenshot=screenshot)
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
            skus = await self._single_stage.extract(raw, screenshot=screenshot)
            if skus:
                return skus
        except Exception as e:
            logger.warning("single_stage_failed", page=raw.page_no, error=str(e))

        # [C7] 最终兜底: 返回空
        return []

    # 常见中文列名 → 系统标准英文键映射（供 bbox 精修 & 前端展示一致性）
    _COLUMN_NORM: dict[str, str] = {
        "产品名称": "product_name", "名称": "product_name", "商品名称": "product_name",
        "品名": "product_name", "产品": "product_name",
        "型号": "model_number", "货号": "model_number", "品号": "model_number",
        "编号": "model_number", "sku": "model_number",
        "规格": "size", "尺寸": "size",
        "单价": "unit_price", "价格": "unit_price", "出厂价": "unit_price",
        "price": "unit_price",  # PDF 中常见的英文价格列头
        "颜色": "color", "材质": "material",
        "备注": "remarks", "说明": "remarks",
        "重量": "weight", "毛重": "weight",
        "包装": "packaging", "最小量": "min_qty", "最小订量": "min_qty",
    }

    def _table_extract(self, raw: ParsedPageIR) -> list[SKUResult]:
        """A 类表格页: 规则引擎提取。

        自动定位实际列标题行（跳过页面标题/说明行），
        将常见中文列名归一化为系统标准英文键，
        并对空白单元格执行前向填充（处理 PDF 竖向合并单元格）。
        """
        results = []
        for table in raw.tables:
            if not table.rows or len(table.rows) < 2:
                continue

            # 定位实际列标题行（第一个多列非空的行）
            header_idx = self._find_table_header_idx(table.rows, table.column_count)
            if header_idx < 0:
                continue

            raw_headers = [h.lower().strip() for h in table.rows[header_idx]]
            # 归一化: 中文列名 → 标准英文键（精确匹配 > 前缀匹配 > 原名兜底）
            headers = [self._normalize_header(h) for h in raw_headers]

            # 获取数据行的图片标志（True=有独立图片单元格, False=合并共享上行图片）
            # row_image_flags 与 table.rows 等长（含标题行）；CrossPageMerger 改写后可能为空
            img_flags = table.row_image_flags[header_idx + 1:] if table.row_image_flags else []

            # 前向填充游标: 记录上一有效行的属性，用于继承竖向合并单元格的值
            prev_attrs: dict[str, str] = {}
            for data_row_idx, row in enumerate(table.rows[header_idx + 1:]):
                attrs: dict[str, str] = {}
                row_has_own_value = False
                for i, cell in enumerate(row):
                    if i < len(headers) and headers[i]:
                        if cell and cell.strip():
                            val = self._clean_table_cell(cell.strip())
                            if not val:
                                continue
                            # 避免同一键重复覆盖（取第一次出现的值）
                            if headers[i] not in attrs:
                                attrs[headers[i]] = val
                            row_has_own_value = True

                # 合并单元格前向填充: 当前行有自身值时，对空白列从上一行继承
                # 这处理 PDF 中竖向 span 的单元格（pdfplumber 只填第一行）
                if row_has_own_value:
                    for key, val in prev_attrs.items():
                        if key not in attrs:
                            attrs[key] = val

                if attrs:
                    # 图片共享标志: 从 row_image_flags 读取；缺失时默认独立图片
                    has_own_image = (
                        img_flags[data_row_idx]
                        if data_row_idx < len(img_flags)
                        else True
                    )
                    results.append(SKUResult(
                        attributes=attrs,
                        source_bbox=table.bbox,
                        validity="valid",
                        confidence=0.85,
                        extraction_method="table_rule",
                        has_own_image=has_own_image,
                    ))
                    prev_attrs = attrs
        return results

    @staticmethod
    def _clean_table_cell(value: str) -> str:
        """清理表格单元格值。

        处理 PDF 中常见的「英文标注\\n实际值」格式：
        若多行值的第一行仅由 ASCII 字母组成（如 'PRICE\\n370'），
        则该行为列内英文副标题，移除后取后续内容。
        """
        if '\n' in value:
            parts = [p.strip() for p in value.split('\n') if p.strip()]
            if parts and re.match(r'^[A-Za-z ]+$', parts[0]):
                value = '\n'.join(parts[1:]).strip()
        return value

    @classmethod
    def _normalize_header(cls, h: str) -> str:
        """将表格列标题归一化为系统标准键。精确匹配 → 前缀匹配 → 原名兜底。"""
        if h in cls._COLUMN_NORM:
            return cls._COLUMN_NORM[h]
        for key, val in cls._COLUMN_NORM.items():
            if h.startswith(key):
                return val
        return h

    @staticmethod
    def _find_table_header_idx(rows: list[list[str]], column_count: int) -> int:
        """定位实际列标题行的索引。

        策略: 从上到下扫描，返回第一个非空格子数 >= max(2, col_count//2) 的行的索引。
        该行之前的行是页面标题/说明文字，通常只有 1 个非空格子。
        """
        min_nonempty = max(2, column_count // 2)
        for i, row in enumerate(rows):
            nonempty = sum(1 for c in row if c and c.strip())
            if nonempty >= min_nonempty:
                return i
        return -1

    @staticmethod
    def _refine_sku_bboxes(
        skus: list[SKUResult],
        text_blocks: list,
        scale: float,
    ) -> None:
        """用 PDF 文本块修正 SKU 的 source_bbox。

        LLM 返回的 source_bbox 可能不准（过大或偏移），
        用 text_blocks 中匹配到的关键属性文本位置来生成更精确的 bbox。
        text_blocks bbox 是 PDF points，乘 scale 转为截图像素坐标。
        """
        for sku in skus:
            # 提取匹配关键词: model_number 最可靠，其次 product_name
            keywords = []
            model = sku.attributes.get("model_number", "").strip()
            if model and len(model) >= 2:
                keywords.append(model)
            name = sku.attributes.get("product_name", "").strip()
            if name and len(name) >= 2:
                keywords.append(name)
            if not keywords:
                continue

            # 找包含关键词的文本块
            matched_blocks = []
            for tb in text_blocks:
                content = tb.content.strip()
                if not content:
                    continue
                for kw in keywords:
                    if kw in content:
                        matched_blocks.append(tb)
                        break

            if not matched_blocks:
                continue

            # 用匹配文本块的外接矩形作为修正 bbox (转为截图像素坐标)
            refined_x0 = min(tb.bbox[0] for tb in matched_blocks) * scale
            refined_y0 = min(tb.bbox[1] for tb in matched_blocks) * scale
            refined_x1 = max(tb.bbox[2] for tb in matched_blocks) * scale
            refined_y1 = max(tb.bbox[3] for tb in matched_blocks) * scale

            old = sku.source_bbox
            sku.source_bbox = (refined_x0, refined_y0, refined_x1, refined_y1)
            logger.info("sku_bbox_refined",
                        sku_id=sku.sku_id,
                        keywords=keywords[:2],
                        matched=len(matched_blocks),
                        old_bbox=[round(v, 1) for v in old[:4]],
                        new_bbox=[round(v, 1) for v in sku.source_bbox[:4]])

    @staticmethod
    def _bind_table_by_row_order(
        skus: list[SKUResult],
        images: list[ImageInfo],
        tables: list[TableData] | None = None,
        scale: float = 150 / 72.0,
    ) -> list[BindingResult]:
        """表格页专用绑定: 按图片 Y 坐标顺序与 SKU 提取顺序对应。

        处理两种特殊情况:
        1. 合并图片单元格 (sku.has_own_image=False): 不前进图片索引，
           共享上一行图片（同一产品的多个规格 SKU 共用一张产品图）。
        2. 表格 bbox 外的图片: 溢出到表格下方的图片按中心点过滤，
           避免把下一产品区域的图片错误绑定给最后一行 SKU。
        """
        deliverable = [
            img for img in images
            if not img.is_duplicate
            and (not img.role or img.role in {"product_main", "product_detail", "unknown"})
        ]
        sorted_imgs = sorted(
            deliverable,
            key=lambda img: (img.bbox[1] + img.bbox[3]) / 2 if len(img.bbox) >= 4 else 0,
        )

        # 过滤表格 bbox 外的图片（用图片中心判断，比用顶边更鲁棒）
        # table.bbox 是 PDF points，图片 bbox 已在 Phase 8 中缩放为像素坐标
        if tables:
            table_bottoms = [tbl.bbox[3] * scale for tbl in tables if len(tbl.bbox) >= 4]
            if table_bottoms:
                tbl_bottom_px = max(table_bottoms)
                sorted_imgs = [
                    img for img in sorted_imgs
                    if len(img.bbox) < 4
                    or (img.bbox[1] + img.bbox[3]) / 2 <= tbl_bottom_px
                ]

        results: list[BindingResult] = []
        img_idx = -1
        current_img_id: str | None = None

        for sku in skus:
            if sku.has_own_image:
                img_idx += 1
                current_img_id = (
                    sorted_imgs[img_idx].image_id
                    if img_idx < len(sorted_imgs)
                    else None
                )
            # has_own_image=False: 保持 current_img_id（共享上一行图片）

            if current_img_id is not None:
                results.append(BindingResult(
                    sku_id=sku.sku_id,
                    image_id=current_img_id,
                    confidence=0.9,
                    method="table_row_order",
                    is_ambiguous=False,
                    rank=1,
                ))

        logger.info("table_row_order_bind",
                    sku_count=len(skus),
                    img_count=len(sorted_imgs),
                    bound=len(results))
        return results

    REBIND_BATCH_SIZE = 15

    async def _vlm_rebind_composites(
        self,
        skus: list[SKUResult],
        composites: list[ImageInfo],
        screenshot: bytes,
    ) -> list[BindingResult] | None:
        """瓦片页 VLM 辅助绑定: 分批调度，避免大量 SKU 时 token 截断。"""
        if len(skus) <= self.REBIND_BATCH_SIZE:
            return await self._vlm_rebind_batch(skus, composites, screenshot)

        all_bindings: list[BindingResult] = []
        for start in range(0, len(skus), self.REBIND_BATCH_SIZE):
            batch = skus[start:start + self.REBIND_BATCH_SIZE]
            result = await self._vlm_rebind_batch(batch, composites, screenshot)
            if result:
                all_bindings.extend(result)

        if len(all_bindings) >= len(skus) * 0.5:
            logger.info("vlm_rebind_batched_success",
                        batches=math.ceil(len(skus) / self.REBIND_BATCH_SIZE),
                        sku_count=len(skus),
                        matched=len(all_bindings))
            return all_bindings

        logger.warning("vlm_rebind_batched_low_coverage",
                       matched=len(all_bindings), total=len(skus))
        return None

    async def _vlm_rebind_batch(
        self,
        skus: list[SKUResult],
        composites: list[ImageInfo],
        screenshot: bytes,
    ) -> list[BindingResult] | None:
        """单批次 VLM 辅助绑定: 在截图上标注图片区域，让 VLM 匹配 SKU→图片。"""
        try:
            from PIL import Image as PILImage, ImageDraw, ImageFont
            import io

            pil_img = PILImage.open(io.BytesIO(screenshot))
            draw = ImageDraw.Draw(pil_img)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            except Exception:
                font = ImageFont.load_default()

            # 按阅读顺序（上→下、左→右）排序，使 IMG 编号与视觉位置一致
            composites = sorted(
                composites,
                key=lambda img: (
                    round((img.bbox[1] + img.bbox[3]) / 2 / 200) * 200,  # 分200px行
                    (img.bbox[0] + img.bbox[2]) / 2,                      # 同行内左→右
                ) if len(img.bbox) >= 4 else (0, 0),
            )

            for idx, comp in enumerate(composites):
                x0, y0, x1, y1 = [int(c) for c in comp.bbox[:4]]
                draw.rectangle([x0, y0, x1, y1], outline="red", width=4)
                label = f"IMG-{idx}"
                draw.rectangle([x0, y0, x0 + 100, y0 + 35], fill="red")
                draw.text((x0 + 5, y0 + 3), label, fill="white", font=font)

            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            annotated = buf.getvalue()

            # 构建 SKU 描述（含 variant_label 帮助 VLM 区分座位数等变体）
            sku_lines = []
            for i, sku in enumerate(skus):
                name = sku.attributes.get("product_name", "?")
                model = sku.attributes.get("model_number", "")
                size = sku.attributes.get("size", "")
                label = sku.variant_label or ""
                parts = [p for p in [model, name, label, size] if p]
                sku_lines.append(f"SKU-{i}: {' '.join(parts)}")

            prompt = f"""This product catalog page has {len(composites)} product images highlighted with red rectangles labeled IMG-0 to IMG-{len(composites) - 1}.

Match each SKU to every image that represents it. Rules:
1. If an image is a "set/scene" photo showing the full product family (room setting with multiple pieces), link it to ALL SKU variants.
2. If an image is an isolated product shot of a specific size (white background, single piece), link it only to the matching SKU.
3. Return one [sku_index, image_index] pair for EACH valid association — a SKU may appear in multiple pairs.

SKUs:
{chr(10).join(sku_lines)}

Respond with ONLY a JSON array of [sku_index, image_index] pairs:
[[0,2],[1,3],...]"""

            resp = await self._llm.call_llm(
                operation="vlm_rebind",
                prompt=prompt,
                images=[annotated],
            )

            import re, json as _json
            text = resp.text.strip()
            items = None

            # 尝试解析紧凑格式 [[0,2],[1,3],...]
            m = re.search(r'\[[\s\S]*\]', text)
            if m:
                try:
                    items = _json.loads(m.group(0))
                except Exception:
                    pass

            if not items:
                # 截断修复: response 以 [ 开头但无 ]（token 限制截断）
                if '[' in text and ']' not in text:
                    arr_start = text.index('[')
                    truncated = text[arr_start:]
                    last_bracket = truncated.rfind(']')
                    if last_bracket > 0:
                        repaired = truncated[:last_bracket + 1] + ']'
                        try:
                            items = _json.loads(repaired)
                            logger.info("vlm_rebind_truncated_repaired",
                                        parsed_count=len(items))
                        except Exception:
                            pass

            if not items or not isinstance(items, list):
                logger.warning("vlm_rebind_parse_failed",
                               text_preview=text[:300])
                return None

            new_bindings = []
            for item in items:
                # 支持紧凑格式 [sku_idx, img_idx] 和旧格式 {"sku_index":..., "image_index":...}
                if isinstance(item, list) and len(item) >= 2:
                    si, ii = item[0], item[1]
                elif isinstance(item, dict):
                    si = item.get("sku_index", -1)
                    ii = item.get("image_index", -1)
                else:
                    continue
                if 0 <= si < len(skus) and 0 <= ii < len(composites):
                    new_bindings.append(BindingResult(
                        sku_id=skus[si].sku_id,
                        image_id=composites[ii].image_id,
                        confidence=0.85,
                        method="vlm_rebind",
                        is_ambiguous=False,
                    ))

            if len(new_bindings) >= len(skus) * 0.5:
                logger.info("vlm_rebind_success",
                            sku_count=len(skus),
                            matched=len(new_bindings))
                return new_bindings

            logger.warning("vlm_rebind_low_coverage",
                           matched=len(new_bindings), total=len(skus))
            return None

        except Exception as e:
            logger.exception("vlm_rebind_failed", error=str(e))
            return None

    @staticmethod
    def _crop_composites(images: list[ImageInfo], screenshot: bytes) -> None:
        """从页面截图裁剪 composite 图片区域，填充 img.data。"""
        composites = [img for img in images
                      if ("_composite_" in img.image_id or "_region_" in img.image_id)
                      and not img.data]
        if not composites:
            return
        try:
            from PIL import Image as PILImage
            import io
            pil_img = PILImage.open(io.BytesIO(screenshot))
            for img in composites:
                if len(img.bbox) < 4:
                    continue
                # bbox 已经在 Phase 8 中转换为像素坐标
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
    def _compute_page_confidence(
        cls_result: ClassifyResult,
        skus: list[SKUResult],
        bindings: list[BindingResult],
        validation: ValidationResult | None,
        extraction_method: str | None,
        fallback_reason: str | None,
    ) -> float:
        """计算页面综合置信度: 几何均值(分类, 提取, 绑定) × 惩罚因子。"""
        # ── C_classify ──
        c_classify = cls_result.confidence

        # ── C_extract ──
        page_type = cls_result.page_type
        if skus:
            confs = [s.confidence for s in skus]
            c_extract = 0.3 * min(confs) + 0.7 * (sum(confs) / len(confs))
        else:
            c_extract = 1.0 if page_type == "D" else 0.0

        # ── C_bind ──
        if bindings and skus:
            bind_confs = [b.confidence for b in bindings]
            c_bind_raw = 0.3 * min(bind_confs) + 0.7 * (sum(bind_confs) / len(bind_confs))
            # 歧义惩罚
            ambiguous_ratio = sum(1 for b in bindings if b.is_ambiguous) / len(bindings)
            c_bind_raw *= (1.0 - 0.3 * ambiguous_ratio)
            # 覆盖惩罚
            bound_sku_ids = set(b.sku_id for b in bindings)
            coverage = len(bound_sku_ids) / len(skus)
            c_bind = c_bind_raw * min(1.0, coverage)
        elif not skus:
            c_bind = 1.0
        else:
            c_bind = 0.0

        # 几何均值
        c_page = (c_classify * c_extract * c_bind) ** (1.0 / 3.0)

        # 方法降级惩罚
        if fallback_reason == "retry_improved":
            c_page *= 0.9
        if extraction_method == "single_stage":
            c_page *= 0.95

        # 校验错误惩罚
        if validation and validation.has_errors:
            c_page *= 0.8

        return round(max(0.0, min(1.0, c_page)), 3)

    @staticmethod
    def _correct_column_isolated_bindings(
        bindings: list,
        skus: list,
        images: list,
    ) -> list:
        """
        VLM 后修正：同列独立产品图（面积 < 60% 最大图）按纵向位置顺序
        映射到有「人位」标签的 SKU（座位数从小到大）。

        触发条件:
        1. SKU 中有 ≥ 2 个带「X人位」标签的变体
        2. 独立产品图 ≥ 2 张，且它们的 x_center 相互间距 < 250px（同列）
        3. 独立图数量 ≤ 人位变体数量
        4. 独立图所在列的 x_center 与最大图 x_center 距离 > 200px（不同区域）
        """
        import re as _re
        from pdf_sku.pipeline.ir import BindingResult

        if not bindings or not skus or not images:
            return bindings

        # 1. 收集有人位标签的 SKU，解析座位数
        ren_wei: list[tuple[int, object]] = []
        for sku in skus:
            label = getattr(sku, "variant_label", "") or ""
            m = _re.match(r"(\d+)人位", label.strip())
            if m:
                ren_wei.append((int(m.group(1)), sku))
        if len(ren_wei) < 2:
            return bindings

        ren_wei.sort(key=lambda x: x[0])

        # 2. 找最大图（面积最大）
        def _area(img):
            if len(img.bbox) < 4:
                return 0
            return (img.bbox[2] - img.bbox[0]) * (img.bbox[3] - img.bbox[1])

        max_area = max((_area(img) for img in images), default=0)
        if max_area <= 0:
            return bindings

        largest = max(images, key=_area)
        largest_xc = (largest.bbox[0] + largest.bbox[2]) / 2 if len(largest.bbox) >= 4 else 0

        # 3. 找独立产品图（面积 < 60% 最大图，且在不同列）
        isolated = [
            img for img in images
            if _area(img) < max_area * 0.60 and len(img.bbox) >= 4
            and abs((img.bbox[0] + img.bbox[2]) / 2 - largest_xc) > 200
        ]
        if len(isolated) < 2 or len(isolated) > len(ren_wei):
            return bindings

        # 4. 独立图必须在同一列（x_center 相互间距 < 250px）
        xcs = [(img.bbox[0] + img.bbox[2]) / 2 for img in isolated]
        if max(xcs) - min(xcs) >= 250:
            return bindings

        # 5. 按 Y 坐标（上→下）排序独立图
        isolated.sort(key=lambda img: (img.bbox[1] + img.bbox[3]) / 2)
        isolated_ids = {img.image_id for img in isolated}

        # 6. 从现有绑定中移除所有独立图的绑定，重新按位置分配
        new_bindings = [b for b in bindings if b.image_id not in isolated_ids]
        for i, img in enumerate(isolated):
            _, sku = ren_wei[i]
            new_bindings.append(BindingResult(
                sku_id=sku.sku_id,
                image_id=img.image_id,
                confidence=0.78,
                method="column_positional",
                is_ambiguous=False,
            ))

        logger.info(
            "isolated_column_corrected",
            isolated_count=len(isolated),
            ren_wei_count=len(ren_wei),
        )
        return new_bindings

    @staticmethod
    def _bbox_overlap_ratio(bbox1: tuple, bbox2: tuple) -> float:
        """计算两个 bbox 的重叠比率: overlap_area / min(area1, area2)。"""
        if len(bbox1) < 4 or len(bbox2) < 4:
            return 0.0
        ox0 = max(bbox1[0], bbox2[0])
        oy0 = max(bbox1[1], bbox2[1])
        ox1 = min(bbox1[2], bbox2[2])
        oy1 = min(bbox1[3], bbox2[3])
        overlap = max(0, ox1 - ox0) * max(0, oy1 - oy0)
        if overlap == 0:
            return 0.0
        a1 = max(1, (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1]))
        a2 = max(1, (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1]))
        # IoU: 避免「大图包含小图→小图被误删」；
        # 真正重叠的副本 IoU 仍接近 1.0，被容器包含的子图 IoU ≈ 小图/大图 << 1
        return overlap / (a1 + a2 - overlap)

    @staticmethod
    def _dedup_images(images: list[ImageInfo]) -> list[ImageInfo]:
        """图片去重: 哈希去重 + 重叠去重 + 小图过滤。"""
        if not images:
            return images

        # 1. 小图过滤: short_edge < 30 → 不参与搜索
        for img in images:
            if img.short_edge < 30:
                img.search_eligible = False

        # 2. 哈希去重: 相同 image_hash → 保留分辨率最高的
        hash_groups: dict[str, list[ImageInfo]] = {}
        for img in images:
            if img.image_hash:
                hash_groups.setdefault(img.image_hash, []).append(img)
        for h, group in hash_groups.items():
            if len(group) <= 1:
                continue
            group.sort(key=lambda i: i.width * i.height, reverse=True)
            for dup in group[1:]:
                dup.is_duplicate = True
                dup.search_eligible = False

        # 3. 重叠去重: bbox 重叠率 > 70% → 保留高分辨率的
        active = [img for img in images if not img.is_duplicate and img.search_eligible]
        for i in range(len(active)):
            if active[i].is_duplicate:
                continue
            for j in range(i + 1, len(active)):
                if active[j].is_duplicate:
                    continue
                ratio = PageProcessor._bbox_overlap_ratio(
                    active[i].bbox, active[j].bbox)
                if ratio > 0.7:
                    area_i = active[i].width * active[i].height
                    area_j = active[j].width * active[j].height
                    loser = active[j] if area_i >= area_j else active[i]
                    loser.is_duplicate = True
                    loser.search_eligible = False

        deduped = sum(1 for img in images if img.is_duplicate)
        if deduped > 0:
            logger.info("image_dedup", total=len(images), deduped=deduped)
        return images

    @staticmethod
    def _merge_tile_fragments(images: list[ImageInfo], page_no: int = 0) -> list[ImageInfo]:
        """检测并合并瓦片碎片为虚拟复合图片。

        判定条件: 页面图片数 > 30 且多数图片 short_edge < 200 (原生)。
        使用 Union-Find 将相邻碎片 (间隔 < 5pt) 聚类,
        每个聚类生成一个虚拟 ImageInfo, 原碎片标记 is_fragmented。
        """
        if len(images) < 30:
            return images

        # 检查是否为瓦片页:
        # 1) 多数原生 short_edge < 200 (经典小瓦片)
        # 2) 图片数 > 50 且尺寸高度一致 (大瓦片, 如 225×215)
        small_count = sum(
            1 for img in images
            if min(img.width, img.height) < 200 and img.width > 0
        )
        is_tile_page = small_count >= len(images) * 0.7
        if not is_tile_page and len(images) > 50:
            # 大瓦片检测: 多数图片尺寸相近
            dims = [(img.width, img.height) for img in images
                    if img.width and img.height]
            if dims:
                from collections import Counter
                dim_counts = Counter(dims)
                most_common_count = dim_counts.most_common(1)[0][1]
                if most_common_count >= len(dims) * 0.5:
                    is_tile_page = True
        if not is_tile_page:
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

        # 按聚类分组
        from collections import defaultdict
        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        # 超大聚类 (> MAX_COMPOSITE_TILES 个碎片) 说明是密集产品网格
        # (如椅子页面每格各一张图), 不应合并成一张大图——保留各自作为独立商品图
        MAX_COMPOSITE_TILES = 10

        # 瓦片页单张图片判定为商品图的最小短边 (150 DPI 像素)。
        # 比普通页门槛 (200px) 低，因为密集网格页每个商品格本身就小。
        TILE_PAGE_MIN_SHORT = 80

        dpi_scale = 150 / 72.0
        merged: list[ImageInfo] = []
        composite_idx = 0
        for members in clusters.values():
            if len(members) == 1:
                img = images[members[0]]
                # 计算该图片在 150 DPI 下的短边
                if len(img.bbox) >= 4:
                    _dw = (img.bbox[2] - img.bbox[0]) * dpi_scale
                    _dh = (img.bbox[3] - img.bbox[1]) * dpi_scale
                    _single_short = int(min(_dw, _dh))
                else:
                    _single_short = img.short_edge or 0
                if _single_short >= TILE_PAGE_MIN_SHORT:
                    # 瓦片页上足够大的独立图片 = 商品图，保留
                    img.is_fragmented = False
                    img.search_eligible = True
                else:
                    # 极小碎片 (图标/水印): 标记为碎片，不参与绑定
                    img.is_fragmented = True
                    img.search_eligible = False
                merged.append(img)
                continue

            if len(members) > MAX_COMPOSITE_TILES:
                # 超大聚类: 密集产品网格，每张图是独立的商品图，直接保留
                for m in members:
                    img = images[m]
                    img.is_fragmented = False
                    img.search_eligible = True
                    merged.append(img)
                logger.info("tile_cluster_too_large_kept_individual",
                            page_no=page_no, members=len(members))
                continue

            # 合并: 计算外接矩形
            x0 = min(images[m].bbox[0] for m in members)
            y0 = min(images[m].bbox[1] for m in members)
            x1 = max(images[m].bbox[2] for m in members)
            y1 = max(images[m].bbox[3] for m in members)
            dw = (x1 - x0) * dpi_scale
            dh = (y1 - y0) * dpi_scale
            short = int(min(dw, dh))

            # 生成虚拟复合图片
            composite = ImageInfo(
                image_id=f"p{page_no}_composite_{composite_idx}",
                bbox=(x0, y0, x1, y1),
                width=int(dw),
                height=int(dh),
                short_edge=short,
                search_eligible=short >= TILE_PAGE_MIN_SHORT,
                is_tile_composite=True,
                role="unknown",
            )
            merged.append(composite)
            composite_idx += 1

            # 原碎片标记并保留（用于图片导出）
            for m in members:
                images[m].is_fragmented = True
                images[m].search_eligible = False
                merged.append(images[m])

        # 若没有任何聚类真正合并（composite_idx==0），说明图片间距较大，
        # 是密集产品目录页（非真正瓦片页）。恢复原始图片，不做碎片标记。
        # 同时对 short_edge >= 80 的图片强制 eligible（密集目录页小图也是商品图）。
        if composite_idx == 0:
            logger.info("tile_merge_skipped_no_clusters",
                        original=len(images),
                        reason="no adjacent fragments found, treating as dense catalog page")
            for img in images:
                img.is_fragmented = False
                if img.short_edge >= 80:
                    img.search_eligible = True
            return images

        logger.info("tile_merge_result",
                     original=len(images),
                     composites=composite_idx,
                     remaining=len([m for m in merged if not m.is_fragmented]))
        return merged

    async def _maybe_create_product_regions(
        self,
        raw: ParsedPageIR,
        skus: list[SKUResult],
        page_no: int,
        screenshot: bytes = b"",
    ) -> None:
        """Phase 6.5: 单大图多商品页 → 用 LLM 检测商品子图区域。

        触发条件:
        - 仅 1 张 search_eligible 图片且覆盖 >= 70% 页面面积
        - 提取到 >= 2 个 SKU
        - 至少 2 个 SKU 有不同的有效 source_bbox

        策略: 调用 Vision LLM，直接询问页面上 n 个商品各自的完整区域坐标，
        返回 PDF pts 坐标系的 bbox 列表。若 LLM 不可用或返回异常结果，
        降级为等比网格（page_w/n_cols × page_h/n_rows 均等切分）。
        """
        eligible = [img for img in raw.images if img.search_eligible]
        if len(eligible) != 1:
            return

        full_img = eligible[0]
        if len(full_img.bbox) < 4:
            return

        page_w = raw.metadata.page_width or 1.0
        page_h = raw.metadata.page_height or 1.0
        img_area = abs(full_img.bbox[2] - full_img.bbox[0]) * abs(full_img.bbox[3] - full_img.bbox[1])
        if img_area / (page_w * page_h) < 0.70:
            return

        if len(skus) < 2:
            return

        # ── 1. 收集唯一 source_bbox（IoU 去重）──
        def _iou(a: tuple, b: tuple) -> float:
            x0, y0 = max(a[0], b[0]), max(a[1], b[1])
            x1, y1 = min(a[2], b[2]), min(a[3], b[3])
            inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
            area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
            area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
            union = area_a + area_b - inter
            return inter / union if union > 0 else 0.0

        # ── 1a. 构建有 model_number 的唯一产品列表（去重），排除 ghost SKU ──
        # Phase 6 可能把生活场景图识别为产品（无 model_number），这里只取真实产品。
        # 按 source_bbox 左上角坐标排序，尽量保持阅读顺序（上→下、左→右）。
        seen_models: set[str] = set()
        unique_products: list[tuple[str, str, "SKUResult"]] = []  # (model, name, sku)
        for sku in sorted(skus, key=lambda s: (
            round((s.source_bbox[1] if s.source_bbox else 0) / 50) * 50,
            s.source_bbox[0] if s.source_bbox else 0,
        )):
            model = sku.attributes.get("model_number", "")
            if not model:
                continue
            if model in seen_models:
                continue
            seen_models.add(model)
            unique_products.append((model, sku.attributes.get("product_name", ""), sku))

        # 如果有 model_number 的产品不足 2 个，退而用所有有位置的 SKU
        if len(unique_products) < 2:
            seen_bboxes: list[tuple] = []
            unique_products = []
            for sku in sorted(skus, key=lambda s: (
                round((s.source_bbox[1] if s.source_bbox else 0) / 50) * 50,
                s.source_bbox[0] if s.source_bbox else 0,
            )):
                sb = sku.source_bbox
                if not sb or sb == (0, 0, 0, 0):
                    continue
                if any(_iou(sb, e) > 0.80 for e in seen_bboxes):
                    continue
                seen_bboxes.append(sb)
                unique_products.append(("", sku.attributes.get("product_name", ""), sku))

        n = len(unique_products)
        if n < 2:
            return

        # ── 2. 检测产品子图区域：优先 YOLO（像素级精确），降级 LLM，再降级等比网格 ──
        product_descs = [(model, name) for model, name, _ in unique_products]

        # 主路：YOLO 图形检测（同步，快速，无 API 成本）
        llm_photos = self._detect_product_regions_yolo(
            screenshot, unique_products, page_w, page_h, page_no)
        _detection_method = "yolo" if llm_photos is not None else "llm"

        # 次路：LLM 降级
        if llm_photos is None:
            llm_photos = await self._detect_product_regions_with_llm(
                screenshot, product_descs, page_w, page_h, page_no)

        dpi_scale = 150 / 72.0
        img_idx = 0

        def _min_dist_to_bbox(cx: float, cy: float, bbox: tuple) -> float:
            bx = max(bbox[0], min(cx, bbox[2]))
            by = max(bbox[1], min(cy, bbox[3]))
            return ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5

        if llm_photos is not None:
            # ── LLM 成功：为每张子图创建独立 ImageInfo ──
            # LLM 返回 list[dict]，每项含 product_index / photo_type / bbox
            # product_photo → role="product_main"（白底产品图，用于搜索）
            # lifestyle_photo → role="product_detail"（生活场景图，作为附图）
            from collections import defaultdict as _defaultdict
            by_product: dict[int, list[dict]] = _defaultdict(list)
            for photo in llm_photos:
                by_product[photo["product_index"]].append(photo)

            new_region_images: list[ImageInfo] = []
            model_to_main_bbox: dict[str, tuple] = {}   # model → product_photo bbox
            for prod_idx, (model, _name, _rep_sku) in enumerate(unique_products):
                for photo in by_product.get(prod_idx, []):
                    bbox = photo["bbox"]
                    dw = abs(bbox[2] - bbox[0]) * dpi_scale
                    dh = abs(bbox[3] - bbox[1]) * dpi_scale
                    short = int(min(dw, dh))
                    role = "product_main" if photo["photo_type"] == "product_photo" else "product_detail"
                    new_region_images.append(ImageInfo(
                        image_id=f"p{page_no}_region_{img_idx}",
                        bbox=bbox,
                        width=int(dw), height=int(dh), short_edge=short,
                        search_eligible=short >= 150,
                        role=role,
                        data=b"",
                    ))
                    if role == "product_main" and model:
                        model_to_main_bbox[model] = bbox
                    img_idx += 1

            # 安全检查: 若 LLM 坐标异常导致产品图片不足（如归一化坐标、bbox太小），
            # 则放弃 LLM 结果，降级为等比网格。
            # 要求每个产品至少有 1 张可搜索的 product_main 图片；
            # 若有产品的主图不可搜索，说明坐标质量不可靠，整体降级。
            eligible_main_count = sum(
                1 for img in new_region_images
                if img.search_eligible and img.role == "product_main"
            )
            has_eligible_llm = eligible_main_count >= n
            if not has_eligible_llm:
                logger.warning(
                    "product_regions_llm_no_eligible",
                    page=page_no,
                    n_created=len(new_region_images),
                    reason="all short_edge < 150, likely bad LLM coords",
                )
                llm_photos = None
                img_idx = 0
            else:
                # ── 3. 标记原大图为不可搜索（仅在成功创建有效区域时）──
                full_img.search_eligible = False
                raw.images.extend(new_region_images)

                # 将每个 SKU 的 source_bbox 指向对应产品的 product_main 照片
                for sku in skus:
                    model = sku.attributes.get("model_number", "")
                    sb = sku.source_bbox
                    if model and model in model_to_main_bbox:
                        sku.source_bbox = model_to_main_bbox[model]
                    elif not model and sb and sb != (0, 0, 0, 0):
                        # fallback：找最近的 product_main 图片
                        main_bboxes = [b for b in model_to_main_bbox.values()]
                        if main_bboxes:
                            cx, cy = (sb[0] + sb[2]) / 2, (sb[1] + sb[3]) / 2
                            sku.source_bbox = min(main_bboxes, key=lambda b: _min_dist_to_bbox(cx, cy, b))

                n_images = img_idx
                used_method = f"{_detection_method}_individual"

        if llm_photos is None:
            # ── 降级：等比网格，每产品一个区域（旧行为）──
            # ── 3. 标记原大图为不可搜索 ──
            full_img.search_eligible = False
            grid_cells = self._make_equal_product_grid(n, page_w, page_h)
            for cell_bbox in grid_cells:
                x0, y0, x1, y1 = cell_bbox
                dw = abs(x1 - x0) * dpi_scale
                dh = abs(y1 - y0) * dpi_scale
                short = int(min(dw, dh))
                raw.images.append(ImageInfo(
                    image_id=f"p{page_no}_region_{img_idx}",
                    bbox=cell_bbox,
                    width=int(dw), height=int(dh), short_edge=short,
                    search_eligible=short >= 150,
                    role="unknown",
                    data=b"",
                ))
                img_idx += 1

            model_to_region: dict[str, tuple] = {
                model: grid_cells[i] for i, (model, _, _) in enumerate(unique_products)
                if model and i < len(grid_cells)
            }
            for sku in skus:
                model = sku.attributes.get("model_number", "")
                sb = sku.source_bbox
                if model and model in model_to_region:
                    sku.source_bbox = model_to_region[model]
                elif not model and sb and sb != (0, 0, 0, 0) and grid_cells:
                    cx, cy = (sb[0] + sb[2]) / 2, (sb[1] + sb[3]) / 2
                    sku.source_bbox = min(grid_cells, key=lambda c: _min_dist_to_bbox(cx, cy, c))

            n_images = img_idx
            used_method = "equal_grid"

        logger.info(
            "product_regions_created",
            page=page_no,
            original_image=full_img.image_id,
            n_products=n,
            n_images=n_images,
            method=used_method,
        )

    def _detect_product_regions_yolo(
        self,
        screenshot: bytes,
        unique_products: list,  # [(model, name, rep_sku), ...]
        page_w: float,
        page_h: float,
        page_no: int,
    ) -> list[dict] | None:
        """使用 DocLayout-YOLO 精确检测产品子图区域（像素级精度）。

        返回与 _detect_product_regions_with_llm 相同格式的 list[dict]，
        每项含 product_index / photo_type / bbox (PDF pts)；
        失败时返回 None（调用方降级为 LLM 或等比网格）。

        流程：
        1. YOLO 检测页面截图中的 Figure 区域（像素坐标）
        2. 白底像素比例区分 product_photo（白底）/ lifestyle_photo（场景）
        3. source_bbox 近邻匹配将每个 figure 分配给对应产品
        """
        try:
            from pdf_sku.pipeline.layout_detector import detect_figures_on_image
            import io as _io
            from PIL import Image as _PILImage

            if not screenshot:
                return None

            pil_img = _PILImage.open(_io.BytesIO(screenshot))
            img_w, img_h = pil_img.size

            # 使用较高置信度以减少噪点检测（0.40 > default 0.25）
            figures_px = detect_figures_on_image(screenshot, conf_override=0.40)
            if not figures_px:
                return None

            n = len(unique_products)

            # 最小面积过滤：figure 需 >= 页面面积 / (n * 6)，排除微小噪点
            min_area_px = (img_w * img_h) / max(n * 6, 1)
            figures_px = [
                f for f in figures_px
                if (f[2] - f[0]) * (f[3] - f[1]) >= min_area_px
            ]

            if len(figures_px) < n:
                logger.info(
                    "product_regions_yolo_insufficient",
                    page=page_no, n_products=n, n_figures=len(figures_px),
                )
                return None

            # 像素坐标 → PDF 点坐标
            def _px_to_pt(fx0: float, fy0: float, fx1: float, fy1: float) -> tuple:
                return (
                    fx0 * page_w / img_w,
                    fy0 * page_h / img_h,
                    fx1 * page_w / img_w,
                    fy1 * page_h / img_h,
                )

            figures_pt = [_px_to_pt(*f) for f in figures_px]

            # 白底检测：R/G/B 均 > 220 的像素占比 > 45% 认为是白底产品图
            def _is_white_bg(fx0: float, fy0: float, fx1: float, fy1: float) -> bool:
                x0 = max(0, int(fx0))
                y0 = max(0, int(fy0))
                x1 = min(img_w, int(fx1))
                y1 = min(img_h, int(fy1))
                if x1 <= x0 or y1 <= y0:
                    return False
                region = pil_img.crop((x0, y0, x1, y1)).convert("RGB")
                pixels = list(region.getdata())
                total = len(pixels)
                if total == 0:
                    return False
                white = sum(1 for r, g, b in pixels if r > 220 and g > 220 and b > 220)
                ratio = white / total
                logger.debug(
                    "product_regions_yolo_white_check",
                    page=page_no, bbox=[x0, y0, x1, y1], white_ratio=round(ratio, 3),
                )
                return ratio > 0.45

            fig_is_white = [_is_white_bg(*f) for f in figures_px]
            fig_photo_type = [
                "product_photo" if w else "lifestyle_photo" for w in fig_is_white
            ]

            # ── 产品 → figure 匹配 ──
            # source_bbox 此时为 PDF pts（Phase 8 尚未执行缩放）
            def _min_dist_to_box(cx: float, cy: float, bbox: tuple) -> float:
                bx = max(bbox[0], min(cx, bbox[2]))
                by = max(bbox[1], min(cy, bbox[3]))
                return ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5

            # 第一轮：为每个产品找最近的 product_photo figure（若有）
            unassigned_product = list(range(len(figures_pt)))  # 所有 figure 编号
            prod_to_figs: dict[int, list[int]] = {i: [] for i in range(n)}

            # 按白底/非白底分组
            white_figs = [i for i, w in enumerate(fig_is_white) if w]
            scene_figs = [i for i, w in enumerate(fig_is_white) if not w]

            used_white: set[int] = set()
            used_scene: set[int] = set()

            for prod_idx, (_, _, rep_sku) in enumerate(unique_products):
                sb = rep_sku.source_bbox
                if sb and sb != (0, 0, 0, 0):
                    cx = (sb[0] + sb[2]) / 2
                    cy = (sb[1] + sb[3]) / 2
                else:
                    # 无 source_bbox：按产品序号估算页面位置
                    cx = page_w * ((prod_idx % max(n // 2, 1)) + 0.5) / max(n // 2, 1)
                    cy = page_h * ((prod_idx // max(n // 2, 1)) + 0.5) / max((n + 1) // 2, 1)

                # 找最近的白底 figure 作为 product_photo
                avail_white = [i for i in white_figs if i not in used_white]
                if avail_white:
                    best_w = min(avail_white,
                                 key=lambda i: _min_dist_to_box(cx, cy, figures_pt[i]))
                    prod_to_figs[prod_idx].append(best_w)
                    used_white.add(best_w)
                else:
                    # 无白底 figure：用任意最近 figure 作为 product_photo
                    avail_any = [i for i in range(len(figures_pt))
                                 if i not in used_white and i not in used_scene]
                    if not avail_any:
                        avail_any = [i for i in range(len(figures_pt))
                                     if not prod_to_figs.get(prod_idx)]
                    if avail_any:
                        best_any = min(avail_any,
                                       key=lambda i: _min_dist_to_box(cx, cy, figures_pt[i]))
                        prod_to_figs[prod_idx].append(best_any)
                        fig_photo_type[best_any] = "product_photo"  # 强制标记
                        used_white.add(best_any)

            # 第二轮：将剩余的场景图分配给最近产品（lifestyle_photo）
            remaining_scene = [i for i in scene_figs if i not in used_white and i not in used_scene]
            for fig_i in remaining_scene:
                fp = figures_pt[fig_i]
                fcx = (fp[0] + fp[2]) / 2
                fcy = (fp[1] + fp[3]) / 2
                # 找 product_photo 中心最近的产品
                best_prod = min(
                    range(n),
                    key=lambda pi: _min_dist_to_box(
                        fcx, fcy,
                        figures_pt[prod_to_figs[pi][0]] if prod_to_figs[pi] else (0, 0, 0, 0),
                    ),
                )
                prod_to_figs[best_prod].append(fig_i)
                used_scene.add(fig_i)

            # 验证：每个产品必须有至少 1 个 figure
            if any(not figs for figs in prod_to_figs.values()):
                logger.warning(
                    "product_regions_yolo_unmatched",
                    page=page_no,
                    unmatched=[i for i, figs in prod_to_figs.items() if not figs],
                )
                return None

            # 构建结果列表（与 LLM 方法格式相同）
            photos: list[dict] = []
            for prod_idx in range(n):
                for fig_i in prod_to_figs[prod_idx]:
                    photos.append({
                        "product_index": prod_idx,
                        "photo_type": fig_photo_type[fig_i],
                        "bbox": figures_pt[fig_i],
                    })

            # 最终保障：每个产品至少一个 product_photo
            covered = {p["product_index"] for p in photos if p["photo_type"] == "product_photo"}
            if not all(i in covered for i in range(n)):
                # 将该产品第一个 figure 强制改为 product_photo
                for prod_idx in range(n):
                    if prod_idx not in covered:
                        for photo in photos:
                            if photo["product_index"] == prod_idx:
                                photo["photo_type"] = "product_photo"
                                covered.add(prod_idx)
                                break

            logger.info(
                "product_regions_yolo_ok",
                page=page_no,
                n_products=n,
                n_figures=len(figures_px),
                n_photos=len(photos),
                white_figures=len(white_figs),
                scene_figures=len(scene_figs),
            )
            return photos

        except Exception as e:
            logger.warning("product_regions_yolo_failed", page=page_no, error=str(e))
            return None

    async def _detect_product_regions_with_llm(
        self,
        screenshot: bytes,
        product_descs: list[tuple[str, str]],  # [(model_number, product_name), ...]
        page_w: float,
        page_h: float,
        page_no: int,
    ) -> list[dict] | None:
        """用 Vision LLM 检测每个产品的独立子图（产品照 + 场景照）。

        返回 list[dict]，每项：{"product_index": int, "photo_type": str, "bbox": tuple(PDF pts)}
        product_index 对应 product_descs 的下标；失败返回 None（调用方降级为等比网格）。
        """
        if not screenshot or not self._llm:
            return None
        n = len(product_descs)
        try:
            import io
            from PIL import Image as PILImage
            pil = PILImage.open(io.BytesIO(screenshot))
            img_w, img_h = pil.size

            product_list_lines = []
            for idx, (model, name) in enumerate(product_descs):
                if model and name:
                    product_list_lines.append(f"{idx}. {model} - {name}")
                elif model:
                    product_list_lines.append(f"{idx}. {model}")
                else:
                    product_list_lines.append(f"{idx}. {name or f'Product {idx}'}")
            product_list = "\n".join(product_list_lines)

            prompt = _PRODUCT_REGION_PROMPT.format(
                n=n, product_list=product_list, img_w=img_w, img_h=img_h)
            resp = await self._llm.call_llm(
                operation="detect_product_regions",
                prompt=prompt,
                images=[screenshot],
            )

            from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
            parsed = ResponseParser().parse(resp.text, expected_type="array")
            if not parsed.success or not isinstance(parsed.data, list):
                logger.warning("product_regions_llm_parse_failed",
                               page=page_no, text=resp.text[:200])
                return None

            photos: list[dict] = []
            for item in parsed.data:
                prod_idx = item.get("product_index")
                photo_type = item.get("photo_type", "")
                bbox = item.get("bbox") or []
                if prod_idx is None or len(bbox) != 4:
                    continue
                prod_idx = int(prod_idx)
                if not (0 <= prod_idx < n):
                    continue

                # 坐标规范化: 确保 x0<x1, y0<y1（防止 LLM 返回坐标顺序颠倒）
                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                if x0 > x1:
                    x0, x1 = x1, x0
                if y0 > y1:
                    y0, y1 = y1, y0

                # bbox 合理性检查: 最大值 < 5 说明是归一化坐标（0-1范围），跳过
                # 在像素坐标系下, 有效产品图的最小维度应 >= 5px
                if x1 - x0 < 5 or y1 - y0 < 5:
                    logger.warning(
                        "product_regions_llm_bbox_too_small",
                        page=page_no,
                        prod_idx=prod_idx,
                        bbox=[x0, y0, x1, y1],
                    )
                    continue

                # bbox 扩展: 按图片尺寸的 3% 向外扩展，补偿 LLM 框选偏紧的问题
                # clamp 到图片边界，防止越界
                pad_x = (x1 - x0) * 0.03
                pad_y = (y1 - y0) * 0.03
                x0 = max(0.0, x0 - pad_x)
                y0 = max(0.0, y0 - pad_y)
                x1 = min(float(img_w), x1 + pad_x)
                y1 = min(float(img_h), y1 + pad_y)

                pt_bbox = (
                    x0 * page_w / img_w,
                    y0 * page_h / img_h,
                    x1 * page_w / img_w,
                    y1 * page_h / img_h,
                )
                photos.append({
                    "product_index": prod_idx,
                    "photo_type": photo_type,
                    "bbox": pt_bbox,
                })

            # 验证：每个产品至少有一张 product_photo
            covered = {p["product_index"] for p in photos if p["photo_type"] == "product_photo"}
            if not all(i in covered for i in range(n)):
                missing = [i for i in range(n) if i not in covered]
                logger.warning("product_regions_llm_missing_product_photos",
                               page=page_no, missing=missing)
                return None

            logger.info("product_regions_llm_ok", page=page_no, n=n, photos=len(photos))
            return photos

        except Exception as e:
            logger.warning("product_regions_llm_failed", page=page_no, error=str(e))
            return None

    @staticmethod
    def _make_equal_product_grid(n: int, page_w: float, page_h: float) -> list[tuple]:
        """生成 n 格等比网格（PDF pts），作为 LLM 检测失败时的降级方案。"""
        # 找最接近正方形的因子对
        best_rows, best_cols = n, 1
        best_ratio_diff = float("inf")
        for nr in range(1, n + 1):
            if n % nr == 0:
                nc = n // nr
                # 期望网格格子接近正方形
                cell_w = page_w / nc
                cell_h = page_h / nr
                ratio_diff = abs(cell_w / cell_h - 1.0)
                if ratio_diff < best_ratio_diff:
                    best_ratio_diff = ratio_diff
                    best_rows, best_cols = nr, nc

        cells: list[tuple] = []
        for row in range(best_rows):
            y0 = row * page_h / best_rows
            y1 = (row + 1) * page_h / best_rows
            for col in range(best_cols):
                x0 = col * page_w / best_cols
                x1 = (col + 1) * page_w / best_cols
                cells.append((x0, y0, x1, y1))
        return cells

    @staticmethod
    def _split_fullpage_composites(
        images: list[ImageInfo],
        page_no: int,
        metadata: "PageMetadata",
    ) -> list[ImageInfo]:
        """Phase 2c: 合成大图布局检测拆分。

        当页面仅 1 张 search_eligible 图片且覆盖 >60% 页面面积时，
        用 DocLayout-YOLO 检测 Figure 区域并拆分为独立子图。
        ultralytics 未安装或模型不存在时 graceful pass。
        """
        try:
            from pdf_sku.pipeline.layout_detector import split_composite_image
            return split_composite_image(
                images, page_no, metadata.page_width, metadata.page_height)
        except Exception as exc:
            logger.debug("phase2c_skip", reason=str(exc))
            return images

    def clear_job_cache(self, job_id: str) -> None:
        self._xpage.clear_job(job_id)
