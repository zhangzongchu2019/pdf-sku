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
                img.search_eligible = img.short_edge >= 200
                if img.data:
                    img.image_hash = hashlib.md5(img.data[:2048]).hexdigest()[:12]

            # ═══ Phase 2b: 瓦片碎片聚类合并 ═══
            raw.images = self._merge_tile_fragments(raw.images, page_no)

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

            # deduplicate + enforce validity + filter invalid
            skus = self._validator.deduplicate_skus(skus)
            skus = self._validator.enforce_sku_validity(skus, None)
            skus = [s for s in skus if s.validity == "valid"]

            # ═══ Phase 7: ID 分配 ═══
            hash_prefix = (file_hash or "unknown")[:8]
            skus = self._id_gen.assign_ids(
                skus, hash_prefix, page_no, raw.metadata.page_height)

            # ═══ Phase 8: 绑定 ═══
            # 坐标系对齐: image bbox 从 PDF points → 截图像素 (与 SKU source_bbox 同系)
            RENDER_DPI = 150
            scale = RENDER_DPI / 72.0
            for img in raw.images:
                if img.bbox != (0, 0, 0, 0):
                    img.bbox = (
                        img.bbox[0] * scale,
                        img.bbox[1] * scale,
                        img.bbox[2] * scale,
                        img.bbox[3] * scale,
                    )
            eligible_images = [img for img in raw.images if img.search_eligible]
            bindings = self._binder.bind(skus, eligible_images, cls_result)

            # 瓦片页 VLM 辅助绑定: 文字层为空时空间绑定不可靠，用 VLM 重新匹配
            composites = [img for img in eligible_images
                          if "_composite_" in img.image_id]
            if (not raw.text_blocks and composites and skus
                    and screenshot and self._llm):
                vlm_bindings = await self._vlm_rebind_composites(
                    skus, composites, screenshot)
                if vlm_bindings:
                    bindings = vlm_bindings

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
                llm_model_used=self._llm.current_model_name if self._llm else None,
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
                # 获取截图实际像素尺寸，传给 VLM 做坐标归一化
                _img_size = self._two_stage._get_image_size(screenshot) if screenshot else (0, 0)
                boundaries = await self._two_stage.identify_boundaries(
                    raw.text_blocks, None, screenshot, image_size=_img_size,
                    images=raw.images)
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

    async def _vlm_rebind_composites(
        self,
        skus: list[SKUResult],
        composites: list[ImageInfo],
        screenshot: bytes,
    ) -> list[BindingResult] | None:
        """瓦片页 VLM 辅助绑定: 在截图上标注图片区域，让 VLM 匹配 SKU→图片。"""
        try:
            from PIL import Image as PILImage, ImageDraw, ImageFont
            import io

            pil_img = PILImage.open(io.BytesIO(screenshot))
            draw = ImageDraw.Draw(pil_img)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            except Exception:
                font = ImageFont.load_default()

            for idx, comp in enumerate(composites):
                x0, y0, x1, y1 = [int(c) for c in comp.bbox[:4]]
                draw.rectangle([x0, y0, x1, y1], outline="red", width=4)
                label = f"IMG-{idx}"
                draw.rectangle([x0, y0, x0 + 100, y0 + 35], fill="red")
                draw.text((x0 + 5, y0 + 3), label, fill="white", font=font)

            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            annotated = buf.getvalue()

            # 构建 SKU 描述
            sku_lines = []
            for i, sku in enumerate(skus):
                name = sku.attributes.get("product_name", "?")
                model = sku.attributes.get("model_number", "")
                size = sku.attributes.get("size", "")
                sku_lines.append(f"SKU-{i}: {model} {name} {size}".strip())

            prompt = f"""This product catalog page has {len(composites)} product images highlighted with red rectangles labeled IMG-0 to IMG-{len(composites) - 1}.

Match each SKU to the image that shows that product. Multiple SKUs can share the same image (e.g., size variants of the same product).

SKUs:
{chr(10).join(sku_lines)}

Respond with ONLY a JSON array:
[{{"sku_index": 0, "image_index": 2}}, ...]"""

            resp = await self._llm.call_llm(
                operation="vlm_rebind",
                prompt=prompt,
                images=[annotated],
            )

            from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
            parsed = ResponseParser().parse(resp.text, expected_type="array")
            if not parsed.success or not isinstance(parsed.data, list):
                return None

            new_bindings = []
            for item in parsed.data:
                si = item.get("sku_index", -1)
                ii = item.get("image_index", -1)
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
    def _merge_tile_fragments(images: list[ImageInfo], page_no: int = 0) -> list[ImageInfo]:
        """检测并合并瓦片碎片为虚拟复合图片。

        判定条件: 页面图片数 > 30 且多数图片 short_edge < 200 (原生)。
        使用 Union-Find 将相邻碎片 (间隔 < 5pt) 聚类,
        每个聚类生成一个虚拟 ImageInfo, 原碎片标记 is_fragmented。
        """
        if len(images) < 30:
            return images

        # 检查是否为瓦片页: 多数原生 short_edge < 200
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

        # 按聚类分组
        from collections import defaultdict
        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        merged: list[ImageInfo] = []
        composite_idx = 0
        for members in clusters.values():
            if len(members) == 1:
                # 瓦片页中的独立小图: 标记为碎片，不参与绑定
                img = images[members[0]]
                native_short = min(img.width, img.height) if img.width and img.height else 0
                if native_short < 200:
                    img.is_fragmented = True
                    img.search_eligible = False
                merged.append(img)
                continue

            # 合并: 计算外接矩形
            x0 = min(images[m].bbox[0] for m in members)
            y0 = min(images[m].bbox[1] for m in members)
            x1 = max(images[m].bbox[2] for m in members)
            y1 = max(images[m].bbox[3] for m in members)
            dpi_scale = 150 / 72.0
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
                search_eligible=short >= 200,
                role="unknown",
            )
            merged.append(composite)
            composite_idx += 1

            # 原碎片标记并保留（用于图片导出）
            for m in members:
                images[m].is_fragmented = True
                images[m].search_eligible = False
                merged.append(images[m])

        logger.info("tile_merge_result",
                     original=len(images),
                     composites=composite_idx,
                     remaining=len([m for m in merged if not m.is_fragmented]))
        return merged

    def clear_job_cache(self, job_id: str) -> None:
        self._xpage.clear_job(job_id)
