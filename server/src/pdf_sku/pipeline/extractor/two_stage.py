"""
两阶段 SKU 提取。对齐: Pipeline 详设 §5.2 Phase 6

阶段1: SKU 边界识别 (identify_boundaries)
阶段2: SKU 属性提取 (extract_batch)
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import (
    ParsedPageIR, SKUBoundary, SKUResult, TextBlock,
)
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
import structlog

logger = structlog.get_logger()
_parser = ResponseParser()

DENSE_ANNOTATED_PROMPT = """This cropped catalog image shows {n} product cells labeled CELL-1 to CELL-{n} with red numbered boxes.

Read the label text for each cell EXACTLY as it appears in the image.

CRITICAL — text faithfulness rules:
- Copy ALL text verbatim from the image. Do NOT translate, paraphrase, or simplify.
- Preserve Chinese characters exactly: "餐桌（table）" stays "餐桌（table）", NOT "table".
- Preserve parenthetical content: "B24#硬" stays "B24#硬", "Y11*（圆9分角）" stays as-is.
- model_number: copy exactly including #, *, （）, 硬, and any suffixes shown.
- The label format varies — it may be ONLY a model number (e.g. "241#"), or include product type, size, price.
  Extract whatever fields are actually visible; leave other fields as "".

Return EXACTLY {n} entries in order (CELL-1 first, CELL-{n} last). Do NOT skip any cell.

Respond ONLY with a JSON array:
[
  {{"cell": 1, "product_name": "餐椅", "model_number": "241#", "size": "", "variant_label": ""}},
  {{"cell": 2, "product_name": "沙发", "model_number": "LF302#", "size": "1110*860*900mm", "variant_label": "单人位"}},
  ...
]

Rules:
- Return EXACTLY {n} objects, ordered cell 1 … {n}
- variant_label: seat-count string if visible (单人位/双人位/三人位/四人位/单椅/etc.), else ""
- If a cell label is partly unclear, still return an entry with whatever text you can read"""

SINGLE_CELL_PROMPT = """This cropped catalog image shows a single product cell.
Read the product label text visible (typically below or beside the product image).

CRITICAL — text faithfulness rules:
- Copy ALL text verbatim from the image. Do NOT translate, paraphrase, or simplify.
- Preserve Chinese characters exactly: "餐桌（table）" stays "餐桌（table）", NOT "table".
- model_number: keep exactly as shown including #, *, suffixes like 硬, parentheticals like （圆9分角）.

Return ONLY a single JSON object:
{{"product_name": "餐椅", "model_number": "241#", "size": "", "variant_label": ""}}

Rules:
- variant_label: seat-count if visible (单人位/双人位/三人位/四人位), else ""
- If text is unclear, return your best reading — do NOT return null or an empty object"""

BOUNDARY_PROMPT_TEMPLATE = """Identify ALL product boundaries in this PDF catalog page image.
The image dimensions are {img_w} x {img_h} pixels.

IMPORTANT: Scene/room photos often contain MULTIPLE products (e.g. a bedroom photo may show a bed, bedside tables, wardrobe, and dresser). Each distinct product must have its own boundary, even if it appears small or in the background.

For each product, return its bounding box coordinates in pixel units (0 to {img_w} for x, 0 to {img_h} for y).
The bbox uses the top-left origin: [x0, y0, x1, y1] where (x0,y0) is the top-left and (x1,y1) is the bottom-right of the product region.

Respond with ONLY a JSON array:
[{{"boundary_id": 1, "bbox": [x0, y0, x1, y1], "text_content": "product name...", "confidence": 0.9}}]"""

ATTR_PROMPT = """Extract products and their SKU variants for each boundary region.
Each boundary may contain one or more products. Each product may have multiple SKU variants.

CRITICAL — text faithfulness rules:
- Copy ALL text verbatim from the image/OCR. Do NOT translate, paraphrase, or simplify.
- Preserve Chinese characters exactly: "餐桌（table）" stays "餐桌（table）", NOT "table".
- Preserve parenthetical content and suffixes exactly as written.
- product_name and model_number must match what is visible in the PDF — no translation, no summarization.

CRITICAL rule — how to count products:
- If raw OCR text is available (not "(none)"), count every distinct "型号：" / "型号:" entry.
  Each distinct 型号 entry = one separate product/SKU — even when two entries share the same
  model prefix (e.g. "A105*铁艺茶几" and "A105*功夫茶几" are TWO different products).
  NEVER merge different 型号 entries into a single SKU.
- If raw OCR text is "(none)" or empty (dense image-only page):
  Each boundary has a "bbox_norm" field with normalized [x0, y0, x1, y1] coordinates (0.0-1.0)
  indicating WHERE on the screenshot that product is located. Use this to locate and read the
  product label/text in that specific region of the screenshot. Extract ONE product per boundary.
  ONLY include a boundary in your response if product text (product_name or model_number) is
  clearly visible in the image for that region. If no text is readable, omit that boundary entirely.
  Do NOT invent or guess product names — only extract what is explicitly visible in the PDF.
- Only expand a SINGLE 型号 into multiple variant SKUs when that same 型号 has multiple
  different sizes/dimensions listed (e.g. "型号：WS-100 规格：1500/1800/2000mm" → 3 SKUs).

Additional rules:
- STRICT EXTRACTION: Only extract attributes that are explicitly written in the PDF text or clearly visible in the image. Do NOT infer, guess, or fabricate any attribute value. If an attribute is not present, omit it.
- Material and color lines describe the ENTIRE product series, NOT individual variants → put in "common_attrs".
- Do NOT create separate SKUs for different colors or materials.
- CRITICAL: When a product has N座位/人位/seater variants listed (e.g. "1人位", "2人位", "3人位"),
  count every unique 人位/座位 entry in the raw OCR text and create EXACTLY that many SKUs — one per entry.
  Do NOT skip any entry. Verify your count before responding.
- When a model number contains a parenthetical descriptor (e.g. "Y11*（圆9分角）", "A105*（铁艺款）"),
  KEEP the full model number including the parenthetical part in "model_number".
  ALSO incorporate the descriptor into "product_name": e.g. product_name="圆9分角茶几" (not just "茶几").
  The descriptor is a key characteristic that distinguishes this product from others in the same series.

Extract these attributes where visible: product_name, model_number, price, material, color, size, weight, description.
Put series-shared attributes (material, color) in "common_attrs". Put variant-specific attributes (size) in each SKU entry.

Raw OCR text from the page:
{raw_text}

Boundaries: {boundaries}

Respond with ONLY a JSON array:
[{{
  "boundary_id": 1,
  "products": [
    {{
      "product_name": "858B#布艺沙发",
      "model_number": "858B#",
      "common_attrs": {{"material": "进口橡木", "color": "栗色/灰色"}},
      "skus": [
        {{"variant_label": "单人位", "size": "850*900*950mm"}},
        {{"variant_label": "双人位", "size": "1400*900*950mm"}}
      ]
    }}
  ]
}}]"""


def _compute_iou(bbox1: tuple, bbox2: tuple) -> float:
    """计算两个 bbox 的 IoU。"""
    x0 = max(bbox1[0], bbox2[0])
    y0 = max(bbox1[1], bbox2[1])
    x1 = min(bbox1[2], bbox2[2])
    y1 = min(bbox1[3], bbox2[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area1 = max(0, bbox1[2] - bbox1[0]) * max(0, bbox1[3] - bbox1[1])
    area2 = max(0, bbox2[2] - bbox2[0]) * max(0, bbox2[3] - bbox2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


class TwoStageExtractor:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def identify_boundaries(
        self,
        text_blocks: list[TextBlock],
        text_roles: list[str] | None,
        screenshot: bytes | None,
        profile: dict | None = None,
        image_size: tuple[int, int] | None = None,
        images: list | None = None,
        page_size: tuple[float, float] | None = None,
    ) -> list[SKUBoundary]:
        """阶段1: SKU 边界识别。"""
        if not self._llm:
            return self._rule_boundaries(text_blocks, text_roles, images=images)

        # 密集图片目录页: 大量可交付图片（>=20）→ 跳过 LLM 边界识别，直接用图片 bbox 作边界
        # 两种情形:
        # 1. 大量瓦片合成图 (is_tile_composite=True): 旧代码路径
        # 2. 大量小尺寸独立产品图 (short_edge < 300): 如椅子密集网格页，每格一张独立图
        #    在这种情形下 LLM boundary detection 会返回粗粒度边界（<20），触发 ATTR_PROMPT
        #    而非 dense_by_rows，导致绑定错位。直接用图片 bbox 作锚点更准确。
        eligible_imgs = [img for img in (images or []) if getattr(img, "search_eligible", False)]
        tile_composite_imgs = [img for img in eligible_imgs if getattr(img, "is_tile_composite", False)]
        small_individual_imgs = [
            img for img in eligible_imgs
            if not getattr(img, "is_tile_composite", False)
            and (img.short_edge or 0) < 300
        ]
        is_dense_imageset = len(tile_composite_imgs) >= 20 or len(small_individual_imgs) >= 20
        if is_dense_imageset:
            logger.info("dense_imageset_boundary_skip_llm",
                        tile_composite_count=len(tile_composite_imgs),
                        small_individual_count=len(small_individual_imgs),
                        eligible_count=len(eligible_imgs),
                        text_block_count=len(text_blocks),
                        reason="dense imageset >= 20, using image bboxes as boundaries directly")
            return self._rule_boundaries(text_blocks, text_roles, images=images)

        # 获取截图实际尺寸
        img_w, img_h = image_size or (0, 0)
        if (not img_w or not img_h) and screenshot:
            img_w, img_h = self._get_image_size(screenshot)

        # 计算像素→PDF点坐标的转换系数（用于将 LLM 返回的像素坐标转回 PDF 点坐标）
        # Phase 8 会统一将 source_bbox 从 PDF 点缩放到截图像素，所以这里必须保持 PDF 点空间
        page_w, page_h = page_size or (0.0, 0.0)
        px_to_pt_x = page_w / img_w if (img_w and page_w) else None
        px_to_pt_y = page_h / img_h if (img_h and page_h) else None

        try:
            prompt = BOUNDARY_PROMPT_TEMPLATE.format(
                img_w=img_w or "unknown",
                img_h=img_h or "unknown",
            )
            resp = await self._llm.call_llm(
                operation="identify_boundaries",
                prompt=prompt,
                images=[screenshot] if screenshot else None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                boundaries = []
                for item in parsed.data:
                    bbox = item.get("bbox", [0, 0, 0, 0])
                    if len(bbox) == 4:
                        bbox = self._normalize_bbox(bbox, img_w, img_h)
                    boundaries.append(SKUBoundary(
                        boundary_id=item.get("boundary_id", len(boundaries) + 1),
                        bbox=tuple(bbox) if len(bbox) == 4 else (0, 0, 0, 0),
                        text_content=item.get("text_content", ""),
                        confidence=float(item.get("confidence", 0.5)),
                    ))
                # NMS 和全页 boundary 惩罚在像素坐标下执行
                boundaries = self._nms_boundaries(boundaries)
                boundaries = self._penalize_fullpage_boundaries(
                    boundaries, img_w, img_h)
                # LLM 返回像素坐标，转回 PDF 点坐标（与 _rule_boundaries 一致），
                # 避免 Phase 8 的统一缩放（PDF pts → 截图像素）导致坐标翻倍
                if px_to_pt_x and px_to_pt_y:
                    for b in boundaries:
                        if b.bbox and b.bbox != (0, 0, 0, 0):
                            b.bbox = (
                                b.bbox[0] * px_to_pt_x,
                                b.bbox[1] * px_to_pt_y,
                                b.bbox[2] * px_to_pt_x,
                                b.bbox[3] * px_to_pt_y,
                            )
                return boundaries
        except Exception as e:
            logger.warning("boundary_identify_failed", error=str(e))

        return self._rule_boundaries(text_blocks, text_roles, images=images)

    async def extract_batch(
        self,
        boundaries: list[SKUBoundary],
        raw: ParsedPageIR,
        profile: dict | None = None,
        screenshot: bytes | None = None,
    ) -> list[SKUResult]:
        """阶段2: 批量属性提取。"""
        if not boundaries:
            return []

        if not self._llm:
            return self._rule_extract(boundaries, raw)

        # 密集图片目录页: boundary 数 >= 20 时按行/列分割处理
        # 无论是否有文字，都使用 _extract_dense_by_rows：
        #   - 自动检测列间隙（如双页并排），将页面拆为多个子区域
        #   - 每组 4 格左右，避免 LLM 一次处理 20+ 格导致漏识别或错位
        #   - source_bbox 精确对应各自图片 bbox，保证绑定正确
        _all_empty_text = all(not b.text_content for b in boundaries)
        if len(boundaries) >= 20 and screenshot:
            return await self._extract_dense_by_rows(boundaries, raw, screenshot)

        # 当所有 boundary 都没有文字时（如密集图片目录页），包含归一化 bbox
        # 让 LLM 能在截图中定位每个产品区域
        _all_empty_text = all(not b.text_content for b in boundaries)
        _pw = (raw.metadata.page_width or 1)
        _ph = (raw.metadata.page_height or 1)
        boundary_desc = []
        for b in boundaries:
            item: dict = {"boundary_id": b.boundary_id, "text": b.text_content[:1000]}
            if _all_empty_text and b.bbox and b.bbox != (0, 0, 0, 0):
                # 归一化坐标 [0,1] (x0, y0, x1, y1)
                item["bbox_norm"] = [
                    round(b.bbox[0] / _pw, 3),
                    round(b.bbox[1] / _ph, 3),
                    round(b.bbox[2] / _pw, 3),
                    round(b.bbox[3] / _ph, 3),
                ]
            boundary_desc.append(item)

        # 从 pdfplumber 提取的原始文本块（比 LLM 生成的 text_content 更完整准确）
        raw_text_lines = []
        for tb in (raw.text_blocks or []):
            t = getattr(tb, "text", "") or ""
            if t.strip():
                raw_text_lines.append(t.strip())
        raw_text = "\n".join(raw_text_lines)[:2000] if raw_text_lines else "(none)"

        try:
            prompt = ATTR_PROMPT.format(
                boundaries=str(boundary_desc),
                raw_text=raw_text,
            )
            resp = await self._llm.call_llm(
                operation="extract_sku_attrs",
                prompt=prompt,
                images=[screenshot] if screenshot else None,
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for item in parsed.data:
                    bid = item.get("boundary_id", 0)
                    boundary = next((b for b in boundaries if b.boundary_id == bid), None)
                    bbox = boundary.bbox if boundary else (0, 0, 0, 0)

                    if "products" in item:
                        # 新格式: 产品分组
                        results.extend(self._parse_products(
                            item["products"], bid, bbox))
                    else:
                        # 旧格式: 向后兼容
                        attrs = item.get("attributes", {})
                        validity = "valid" if attrs.get("product_name") else "invalid"
                        results.append(SKUResult(
                            attributes=attrs,
                            source_bbox=bbox,
                            validity=validity,
                            confidence=float(item.get("confidence", 0.7)),
                            extraction_method="two_stage",
                        ))
                # 后处理：从 raw OCR 补充 LLM 遗漏的 N人位 变体
                results = self._supplement_seat_variants(results, raw_text)
                return results
        except Exception as e:
            logger.warning("attr_extract_failed", error=str(e))

        return self._rule_extract(boundaries, raw)

    async def _extract_dense_by_rows(
        self,
        boundaries: list[SKUBoundary],
        raw: ParsedPageIR,
        screenshot: bytes,
    ) -> list[SKUResult]:
        """密集图片目录页按行/列分组提取。

        将 boundary 按 Y 坐标分组为多行，并检测垂直列间隙（如双页并排 PDF）。
        若检测到列分隔则每行再按左/右列分别裁剪，使每次 LLM 只看 ~4 个产品，
        识别率显著优于全行 8 产品处理。
        """
        import io
        try:
            from PIL import Image as PILImage
        except ImportError:
            logger.warning("PIL not available, falling back to full-page extraction")
            return await self._extract_full_page(boundaries, raw, screenshot)

        # 检测垂直列间隙（如双页并排 PDF）
        col_split_x = self._detect_column_split(boundaries)

        # 按行分组: 自适应 gap = 边界框高度中位数 × 0.3（最小 15pt）
        heights = [b.bbox[3] - b.bbox[1] for b in boundaries if b.bbox[3] > b.bbox[1]]
        heights.sort()
        median_h = heights[len(heights) // 2] if heights else 80.0
        adaptive_gap = max(15.0, median_h * 0.3)
        rows = self._group_boundaries_by_row(boundaries, gap=adaptive_gap)
        logger.info("dense_row_split", page=raw.page_no,
                    total_boundaries=len(boundaries), row_count=len(rows),
                    adaptive_gap=round(adaptive_gap, 1),
                    col_split_x=round(col_split_x, 1) if col_split_x is not None else None)

        # 页面/截图尺寸及缩放比
        img = PILImage.open(io.BytesIO(screenshot))
        img_w, img_h = img.size
        pw = raw.metadata.page_width or 1
        ph = raw.metadata.page_height or 1
        scale_x = img_w / pw
        scale_y = img_h / ph

        # 文字标签在图片下方的估算高度（向下扩展以包含型号/尺寸文字）
        TEXT_MARGIN_PT = 70

        all_results: list[SKUResult] = []

        for row_idx, row_bounds in enumerate(rows):
            # 行在 PDF 坐标中的范围
            row_y0 = min(b.bbox[1] for b in row_bounds)
            row_y1 = max(b.bbox[3] for b in row_bounds)
            crop_y0_pt = max(0.0, row_y0 - 5)
            crop_y1_pt = min(ph, row_y1 + TEXT_MARGIN_PT)
            row_h_pt = max(1.0, crop_y1_pt - crop_y0_pt)
            crop_py0 = max(0, int(crop_y0_pt * scale_y))
            crop_py1 = min(img_h, int(crop_y1_pt * scale_y))

            # 按列分组: 有列间隙则左/右各一组，否则整行一组
            if col_split_x is not None:
                col_groups = [
                    [b for b in row_bounds if (b.bbox[0] + b.bbox[2]) / 2 < col_split_x],
                    [b for b in row_bounds if (b.bbox[0] + b.bbox[2]) / 2 >= col_split_x],
                ]
            else:
                col_groups = [row_bounds]

            for col_idx, group_bounds in enumerate(col_groups):
                if not group_bounds:
                    continue

                # 列组 X 范围（略向两侧扩展以包含边框/文字）
                grp_x0_pt = max(0.0, min(b.bbox[0] for b in group_bounds) - 5)
                grp_x1_pt = min(pw, max(b.bbox[2] for b in group_bounds) + 5)
                grp_w_pt = max(1.0, grp_x1_pt - grp_x0_pt)
                crop_px0 = max(0, int(grp_x0_pt * scale_x))
                crop_px1 = min(img_w, int(grp_x1_pt * scale_x))

                row_img = img.crop((crop_px0, crop_py0, crop_px1, crop_py1))

                # 在裁剪图上标注编号红框（提高 LLM 对每个产品格的定位精度）
                annotated_img, cell_map = self._annotate_group_cells(
                    row_img,
                    group_bounds,
                    grp_x0_pt, crop_y0_pt, grp_w_pt, row_h_pt,
                )
                buf = io.BytesIO()
                annotated_img.save(buf, format="PNG")
                row_screenshot = buf.getvalue()

                n = len(cell_map)
                prompt = DENSE_ANNOTATED_PROMPT.format(n=n)

                try:
                    resp = await self._llm.call_llm(
                        operation="extract_sku_dense_annotated",
                        prompt=prompt,
                        images=[row_screenshot],
                    )
                    parsed = _parser.parse(resp.text, expected_type="array")
                    if parsed.success and isinstance(parsed.data, list):
                        # LLM 按顺序返回 CELL-1…CELL-N；按索引对应 cell_map（左→右）
                        for cell_idx, boundary in enumerate(cell_map):
                            if cell_idx >= len(parsed.data):
                                break
                            item = parsed.data[cell_idx]
                            bbox = boundary.bbox
                            bid = boundary.boundary_id
                            if "products" in item:
                                all_results.extend(
                                    self._parse_products(item["products"], bid, bbox))
                            else:
                                attrs: dict = {}
                                for key in ("product_name", "model_number", "size",
                                            "material", "color", "price"):
                                    v = item.get(key, "")
                                    if v:
                                        attrs[key] = str(v)
                                variant_label = item.get("variant_label", "")
                                validity = "valid" if (
                                    attrs.get("model_number") or attrs.get("size")
                                ) else "invalid"
                                all_results.append(SKUResult(
                                    attributes=attrs,
                                    source_bbox=bbox,
                                    validity=validity,
                                    confidence=0.75,
                                    extraction_method="two_stage_dense_annotated",
                                    variant_label=variant_label if isinstance(
                                        variant_label, str) else "",
                                ))
                        logger.info("dense_row_col_extracted",
                                    page=raw.page_no, row=row_idx + 1, col=col_idx + 1,
                                    boundaries=n, returned=len(parsed.data),
                                    total_so_far=len(all_results))
                except Exception as e:
                    logger.warning("dense_row_extract_failed",
                                   page=raw.page_no, row=row_idx + 1,
                                   col=col_idx + 1, error=str(e))

        return all_results

    @staticmethod
    def _annotate_group_cells(
        img: "PILImage",
        group_bounds: list[SKUBoundary],
        grp_x0_pt: float,
        crop_y0_pt: float,
        grp_w_pt: float,
        row_h_pt: float,
    ) -> tuple["PILImage", list[SKUBoundary]]:
        """在裁剪图上按左→右顺序标注编号红框（CELL-1, CELL-2, ...）。

        按 X 坐标从左到右排序 group_bounds，在每个 boundary 对应的像素区域
        绘制红色矩形框和 CELL-N 标签，帮助 LLM 明确识别每个产品格。
        标注框从图片顶部延伸到裁剪图底部（含文字标签区域）。

        Returns:
            (annotated_image, sorted_boundaries_left_to_right)
        """
        try:
            from PIL import ImageDraw, ImageFont
        except ImportError:
            return img, group_bounds

        img_w, img_h = img.size
        scale_x = img_w / max(1.0, grp_w_pt)
        scale_y = img_h / max(1.0, row_h_pt)

        # 按 X 中心从左到右排序
        sorted_bounds = sorted(
            group_bounds,
            key=lambda b: (b.bbox[0] + b.bbox[2]) / 2,
        )

        annotated = img.copy()
        draw = ImageDraw.Draw(annotated)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except Exception:
            font = ImageFont.load_default()

        for idx, b in enumerate(sorted_bounds):
            # PDF pt → 裁剪图像素
            px0 = max(0, int((b.bbox[0] - grp_x0_pt) * scale_x))
            py0 = max(0, int((b.bbox[1] - crop_y0_pt) * scale_y))
            px1 = min(img_w, int((b.bbox[2] - grp_x0_pt) * scale_x))
            # 延伸到裁剪图底部，包含图片下方的文字标签区域
            py1 = img_h
            label = f"CELL-{idx + 1}"
            draw.rectangle([px0, py0, px1, py1], outline="red", width=3)
            lbl_w = max(80, len(label) * 14)
            draw.rectangle([px0, py0, px0 + lbl_w, py0 + 30], fill="red")
            draw.text((px0 + 4, py0 + 4), label, fill="white", font=font)

        return annotated, sorted_bounds

    @staticmethod
    def _detect_column_split(boundaries: list[SKUBoundary]) -> float | None:
        """检测 boundary 集合中是否存在垂直列间隙（如双页并排 PDF）。

        扫描所有 boundary 的 X 范围，找最宽的无覆盖间隔：
        - 间隔宽度 > 50pt
        - 间隔中心位于页面横向 30%~70% 之间
        满足以上条件时返回间隔中点 X 坐标作为列分隔线；否则返回 None。
        """
        if not boundaries:
            return None

        x_intervals = [
            (b.bbox[0], b.bbox[2]) for b in boundaries
            if len(b.bbox) >= 4 and b.bbox[2] > b.bbox[0]
        ]
        if not x_intervals:
            return None

        x_min = min(x for x, _ in x_intervals)
        x_max = max(x for _, x in x_intervals)
        page_width = x_max - x_min
        if page_width < 100:
            return None

        # 以 10pt 分辨率构建 X 轴覆盖位图
        BIN = 10
        n_bins = int(page_width / BIN) + 2
        covered = [False] * n_bins
        for x0, x1 in x_intervals:
            b0 = max(0, int((x0 - x_min) / BIN))
            b1 = min(n_bins - 1, int((x1 - x_min) / BIN))
            for b in range(b0, b1 + 1):
                covered[b] = True

        # 找最宽的连续空白段
        best_gap_start = -1.0
        best_gap_end = -1.0
        best_gap_width = 0.0
        in_gap = False
        gap_start_bin = 0
        for i, is_covered in enumerate(covered):
            if not is_covered:
                if not in_gap:
                    in_gap = True
                    gap_start_bin = i
            else:
                if in_gap:
                    in_gap = False
                    gap_w = (i - gap_start_bin) * BIN
                    if gap_w > best_gap_width:
                        best_gap_width = gap_w
                        best_gap_start = gap_start_bin * BIN + x_min
                        best_gap_end = i * BIN + x_min
        if in_gap:
            gap_w = (n_bins - gap_start_bin) * BIN
            if gap_w > best_gap_width:
                best_gap_width = gap_w
                best_gap_start = gap_start_bin * BIN + x_min
                best_gap_end = n_bins * BIN + x_min

        if best_gap_width < 50:
            return None

        gap_center = (best_gap_start + best_gap_end) / 2
        gap_pos = (gap_center - x_min) / page_width
        if not (0.3 <= gap_pos <= 0.7):
            return None

        return gap_center

    async def _extract_full_page(
        self,
        boundaries: list[SKUBoundary],
        raw: ParsedPageIR,
        screenshot: bytes,
    ) -> list[SKUResult]:
        """全页提取（_extract_dense_by_rows 的 fallback）。"""
        pw = raw.metadata.page_width or 1
        ph = raw.metadata.page_height or 1
        boundary_desc = []
        for b in boundaries:
            item: dict = {"boundary_id": b.boundary_id, "text": ""}
            if b.bbox and b.bbox != (0, 0, 0, 0):
                item["bbox_norm"] = [
                    round(b.bbox[0] / pw, 3),
                    round(b.bbox[1] / ph, 3),
                    round(b.bbox[2] / pw, 3),
                    round(b.bbox[3] / ph, 3),
                ]
            boundary_desc.append(item)
        try:
            prompt = ATTR_PROMPT.format(boundaries=str(boundary_desc), raw_text="(none)")
            resp = await self._llm.call_llm(
                operation="extract_sku_attrs",
                prompt=prompt,
                images=[screenshot],
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for item in parsed.data:
                    bid = item.get("boundary_id", 0)
                    boundary = next((b for b in boundaries if b.boundary_id == bid), None)
                    bbox = boundary.bbox if boundary else (0, 0, 0, 0)
                    if "products" in item:
                        results.extend(self._parse_products(item["products"], bid, bbox))
                    else:
                        attrs = item.get("attributes", {})
                        validity = "valid" if attrs.get("product_name") else "invalid"
                        results.append(SKUResult(
                            attributes=attrs, source_bbox=bbox, validity=validity,
                            extraction_method="two_stage",
                        ))
                return results
        except Exception as e:
            logger.warning("full_page_extract_failed", error=str(e))
        return self._rule_extract(boundaries, raw)

    async def _extract_per_cell(
        self,
        boundaries: list[SKUBoundary],
        raw: ParsedPageIR,
        screenshot: bytes,
    ) -> list[SKUResult]:
        """密集图片目录页逐格提取：每个 boundary 单独裁剪 + 单独 LLM 调用。

        相比分组方式（4格/次），逐格方式消除了 LLM 跳格或错位的风险，
        确保每个 SKU 都有独立的 LLM 调用且 source_bbox 精确对应。
        """
        import io
        try:
            from PIL import Image as PILImage
        except ImportError:
            logger.warning("PIL not available, falling back to full-page extraction")
            return await self._extract_full_page(boundaries, raw, screenshot)

        img = PILImage.open(io.BytesIO(screenshot))
        img_w, img_h = img.size
        pw = raw.metadata.page_width or 1
        ph = raw.metadata.page_height or 1
        scale_x = img_w / pw
        scale_y = img_h / ph

        TEXT_MARGIN_PT = 70  # 向下扩展包含图片下方文字标签

        # 按 Y 后 X 排序（从左上到右下）
        sorted_bounds = sorted(boundaries, key=lambda b: (b.bbox[1], b.bbox[0]))

        all_results: list[SKUResult] = []
        for cell_idx, boundary in enumerate(sorted_bounds):
            x0, y0, x1, y1 = boundary.bbox
            crop_y1_pt = min(ph, y1 + TEXT_MARGIN_PT)

            px0 = max(0, int(x0 * scale_x))
            py0 = max(0, int(y0 * scale_y))
            px1 = min(img_w, int(x1 * scale_x))
            py1 = min(img_h, int(crop_y1_pt * scale_y))

            if px1 <= px0 or py1 <= py0:
                logger.warning("per_cell_zero_size", cell=cell_idx + 1,
                               boundary_id=boundary.boundary_id)
                continue

            cell_img = img.crop((px0, py0, px1, py1))
            buf = io.BytesIO()
            cell_img.save(buf, format="PNG")
            cell_screenshot = buf.getvalue()

            try:
                resp = await self._llm.call_llm(
                    operation="extract_sku_single_cell",
                    prompt=SINGLE_CELL_PROMPT,
                    images=[cell_screenshot],
                )
                parsed = _parser.parse(resp.text, expected_type="object")
                # 兼容 LLM 返回单元素数组的情况
                item = None
                if parsed.success and isinstance(parsed.data, dict):
                    item = parsed.data
                elif parsed.success and isinstance(parsed.data, list) and len(parsed.data) == 1:
                    item = parsed.data[0]

                if item:
                    attrs: dict = {}
                    for key in ("product_name", "model_number", "size",
                                "material", "color", "price"):
                        v = item.get(key, "")
                        if v:
                            attrs[key] = str(v)
                    variant_label = item.get("variant_label", "")
                    validity = "valid" if (
                        attrs.get("model_number") or attrs.get("size")
                    ) else "invalid"
                    all_results.append(SKUResult(
                        attributes=attrs,
                        source_bbox=boundary.bbox,
                        validity=validity,
                        confidence=0.8,
                        extraction_method="two_stage_per_cell",
                        variant_label=variant_label if isinstance(variant_label, str) else "",
                    ))
                    logger.info("per_cell_extracted",
                                page=raw.page_no, cell=cell_idx + 1,
                                total=len(sorted_bounds),
                                boundary_id=boundary.boundary_id,
                                model_number=attrs.get("model_number", ""),
                                variant_label=variant_label)
                else:
                    logger.warning("per_cell_parse_failed",
                                   cell=cell_idx + 1,
                                   boundary_id=boundary.boundary_id,
                                   raw_text=resp.text[:200] if resp.text else "")
            except Exception as e:
                logger.warning("per_cell_extract_failed",
                               cell=cell_idx + 1,
                               boundary_id=boundary.boundary_id,
                               error=str(e))

        logger.info("per_cell_complete",
                    page=raw.page_no,
                    total_boundaries=len(sorted_bounds),
                    total_skus=len(all_results))
        return all_results

    @staticmethod
    def _group_boundaries_by_row(
        boundaries: list[SKUBoundary],
        gap: float = 60,
    ) -> list[list[SKUBoundary]]:
        """按 Y 坐标将 boundary 分组为行（相邻 boundary Y 间距 > gap 则换行）。"""
        if not boundaries:
            return []
        sorted_b = sorted(boundaries, key=lambda b: b.bbox[1])
        rows: list[list[SKUBoundary]] = [[sorted_b[0]]]
        for b in sorted_b[1:]:
            prev_y_bottom = max(bb.bbox[3] for bb in rows[-1])
            if b.bbox[1] - prev_y_bottom > gap:
                rows.append([b])
            else:
                rows[-1].append(b)
        return rows

    @staticmethod
    def _parse_products(
        products: list[dict],
        boundary_id: int,
        bbox: tuple,
    ) -> list[SKUResult]:
        """解析产品分组格式，每个 SKU 变体生成一个 SKUResult。"""
        results = []
        for p_idx, product in enumerate(products):
            product_name = product.get("product_name", "")
            model_number = product.get("model_number", "")
            common_attrs = product.get("common_attrs", {})
            temp_product_id = f"B{boundary_id}_P{p_idx + 1}"

            skus_data = product.get("skus", [])
            if not skus_data:
                # 无变体时整个产品作为一个 SKU
                skus_data = [{}]

            for sku_data in skus_data:
                attrs = {}
                if product_name:
                    attrs["product_name"] = product_name
                if model_number:
                    attrs["model_number"] = model_number
                # 合并 common_attrs
                attrs.update(common_attrs)
                # 合并变体特有属性（覆盖 common）
                variant_label = sku_data.pop("variant_label", "") if isinstance(sku_data, dict) else ""
                if isinstance(sku_data, dict):
                    attrs.update(sku_data)

                # 过滤伪 SKU：product_name == model_number 且无尺寸/变体
                # 这是 LLM 把型号表头（如"WS X-685"）误当成独立产品抽取
                pn = attrs.get("product_name", "")
                mn = attrs.get("model_number", "")
                is_header_artifact = (
                    pn and mn and pn == mn
                    and not attrs.get("size")
                    and not variant_label
                )
                validity = "invalid" if is_header_artifact else (
                    "valid" if pn else "invalid"
                )
                results.append(SKUResult(
                    attributes=attrs,
                    source_bbox=bbox,
                    validity=validity,
                    confidence=0.7,
                    extraction_method="two_stage",
                    product_id=temp_product_id,
                    variant_label=variant_label,
                ))
        return results

    @staticmethod
    def _supplement_seat_variants(
        results: list[SKUResult],
        raw_text: str,
    ) -> list[SKUResult]:
        """
        后处理：从 raw OCR 文本中正则提取所有 'N人位+尺寸' 条目，
        补充 LLM 漏提的变体（常见于多列布局中 2人位 被夹在段落文字里）。
        仅当已有 ≥1 个 variant_label 时才激活，避免干扰非沙发类产品。
        """
        import re

        # 只在已有 人位 变体标签的结果中生效
        existing_variants = {r.variant_label for r in results if r.variant_label}
        if not existing_variants:
            return results

        # 匹配 "N人位" + 可选空白 + "WxDxH" 格式（宽容大小写和分隔符）
        seat_pat = re.compile(
            r'(\d+人位)\s*(\d+[Ww][*×xX×]\d+[Dd][*×xX×]\d+[Hh])',
        )
        found = seat_pat.findall(raw_text)
        if len(found) <= len(existing_variants):
            return results  # 没有遗漏

        # 找出 LLM 未提取到的变体
        missing = [(vl, sz) for vl, sz in found if vl not in existing_variants]
        if not missing:
            return results

        # 以第一个 valid 结果为模板，继承公共属性
        template = next((r for r in results if r.validity == "valid"), None)
        if not template:
            return results

        for variant_label, size in missing:
            new_attrs = {k: v for k, v in template.attributes.items() if k != "size"}
            new_attrs["size"] = size
            results.append(SKUResult(
                attributes=new_attrs,
                source_bbox=template.source_bbox,
                validity="valid",
                confidence=0.65,
                extraction_method="two_stage_supplemented",
                product_id=template.product_id,
                variant_label=variant_label,
            ))

        logger.info(
            "seat_variants_supplemented",
            missing_count=len(missing),
            variants=[m[0] for m in missing],
        )
        return results

    @staticmethod
    def _nms_boundaries(
        boundaries: list[SKUBoundary], iou_threshold: float = 0.5,
    ) -> list[SKUBoundary]:
        """IoU > threshold 的 boundary 保留 confidence 更高的。"""
        sorted_b = sorted(boundaries, key=lambda b: b.confidence, reverse=True)
        keep: list[SKUBoundary] = []
        for b in sorted_b:
            if not any(_compute_iou(b.bbox, k.bbox) > iou_threshold for k in keep):
                keep.append(b)
        for i, b in enumerate(keep):
            b.boundary_id = i + 1
        return keep

    @staticmethod
    def _penalize_fullpage_boundaries(
        boundaries: list[SKUBoundary],
        img_w: int, img_h: int,
    ) -> list[SKUBoundary]:
        """覆盖 >80% 页面的 boundary 降低 confidence。"""
        page_area = img_w * img_h
        if page_area <= 0:
            return boundaries
        for b in boundaries:
            b_area = (b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1])
            if b_area > page_area * 0.8:
                b.confidence = min(b.confidence, 0.3)
        return boundaries

    @staticmethod
    def _get_image_size(data: bytes) -> tuple[int, int]:
        """从 PNG 头部读取图片尺寸（不依赖 PIL）。"""
        # PNG: bytes 16-23 contain width (4 bytes) and height (4 bytes) in IHDR
        if data[:4] == b'\x89PNG' and len(data) >= 24:
            import struct
            w, h = struct.unpack('>II', data[16:24])
            return w, h
        return 0, 0

    @staticmethod
    def _normalize_bbox(
        bbox: list, img_w: int, img_h: int,
    ) -> list:
        """
        将 VLM 返回的 bbox 归一化到实际图片像素坐标。
        VLM 可能在内部缩放了图片，导致返回的坐标比实际像素偏小。
        通过检测 bbox 范围 vs 图片尺寸的比例来推断并修正。
        """
        if not img_w or not img_h:
            return bbox

        x0, y0, x1, y1 = bbox
        max_coord = max(x1, y1)

        # 如果坐标已经接近或超过图片尺寸，说明已在正确空间
        if max_coord >= min(img_w, img_h) * 0.8:
            return bbox

        # VLM 可能将长边缩放到某个固定值，推断缩放因子
        # 使用较大的维度比来估算（更保守）
        if x1 > 0 and y1 > 0:
            # 假设 VLM 等比缩放，用长边比来推断
            # 检测 VLM 的等效长边 = max(所有 bbox 坐标的理论最大值)
            # 由于单次调用无法看到全局 max，用当前 bbox 估算
            scale_x = img_w / max(x1, 1)
            scale_y = img_h / max(y1, 1)
            # 等比缩放时 scale_x ≈ scale_y，取较小值保守估计
            s = min(scale_x, scale_y)
            if s > 1.1:  # 只在明显缩放时修正
                return [x0 * s, y0 * s, x1 * s, y1 * s]

        return bbox

    def _rule_boundaries(
        self,
        text_blocks: list[TextBlock],
        text_roles: list[str] | None,
        images: list | None = None,
    ) -> list[SKUBoundary]:
        """规则兜底: 优先用图片锚点聚类，否则 Y-gap 分组。"""
        # 纯图片页（无文字）: 不过滤 is_duplicate，因为密集目录中相同外观的图
        # 可能对应不同尺寸规格，每张图片位置都代表一个独立 SKU
        is_text_empty = not text_blocks
        anchors = [
            img for img in (images or [])
            if getattr(img, "search_eligible", False)
            and (is_text_empty or not getattr(img, "is_duplicate", False))
        ]

        if len(anchors) >= 2:
            result = self._image_anchor_boundaries(text_blocks or [], anchors)
            if result:
                return result

        if not text_blocks:
            return []

        # 退回 Y-gap 法
        return self._ygap_boundaries(text_blocks)

    def _ygap_boundaries(self, text_blocks: list[TextBlock]) -> list[SKUBoundary]:
        """Y 轴间距分组（原始 fallback）。

        当结果只有 1 个 boundary 且文本较长时，尝试按型号模式二次切分。
        """
        boundaries: list[SKUBoundary] = []
        current_group: list[TextBlock] = [text_blocks[0]]
        for i in range(1, len(text_blocks)):
            prev = text_blocks[i - 1]
            curr = text_blocks[i]
            gap = curr.bbox[1] - prev.bbox[3] if curr.bbox[1] > prev.bbox[3] else 0
            if gap > 30:
                boundaries.append(self._group_to_boundary(current_group, len(boundaries) + 1))
                current_group = [curr]
            else:
                current_group.append(curr)
        if current_group:
            boundaries.append(self._group_to_boundary(current_group, len(boundaries) + 1))

        # 若仅 1 个 boundary 且文本较长，尝试按型号模式切分
        if len(boundaries) == 1 and len(boundaries[0].text_content) > 100:
            split = self._split_by_model_pattern(boundaries[0])
            if len(split) > 1:
                return split

        return boundaries

    @staticmethod
    def _split_by_model_pattern(boundary: SKUBoundary) -> list[SKUBoundary]:
        """按型号模式（如 886#、858B#）切分单个 boundary 为多个产品区域。"""
        import re
        text = boundary.text_content
        # 匹配型号+# 模式: 886#, 858B#, 09# 等（字母数字混合+#）
        # 在行首或换行后、或前有空白/换行时切分
        pattern = re.compile(r'(?:^|(?<=\n)|(?<=\s))(?=[A-Za-z0-9]*\d[A-Za-z0-9]*[#＃])')
        splits = list(pattern.finditer(text))
        if len(splits) < 2:
            return [boundary]

        results = []
        for idx, match in enumerate(splits):
            start = match.end()  # skip the newline itself
            end = splits[idx + 1].start() if idx + 1 < len(splits) else len(text)
            segment = text[start:end].strip()
            if segment:
                results.append(SKUBoundary(
                    boundary_id=len(results) + 1,
                    bbox=boundary.bbox,
                    text_content=segment[:2000],
                ))
        return results if results else [boundary]

    @staticmethod
    def _image_anchor_boundaries(
        text_blocks: list[TextBlock],
        anchors: list,
    ) -> list[SKUBoundary]:
        """
        图片锚点聚类: 将文字块归属到最近的图片区域。

        亲和度规则:
        - 图片正下方的文字优先（X 轴重叠 + Y 在图片下方）
        - 其次按中心距离
        距离所有图片过远的孤儿文字单独 Y-gap 分组。
        """
        import math

        ORPHAN_THRESHOLD = 300  # pt

        # 图片中心和 bbox
        anchor_cx = [(a.bbox[0] + a.bbox[2]) / 2 for a in anchors]
        anchor_cy = [(a.bbox[1] + a.bbox[3]) / 2 for a in anchors]

        # 按锚点分组: index → list of TextBlock
        groups: dict[int, list[TextBlock]] = {i: [] for i in range(len(anchors))}
        orphans: list[TextBlock] = []

        for tb in text_blocks:
            tb_cx = (tb.bbox[0] + tb.bbox[2]) / 2
            tb_cy = (tb.bbox[1] + tb.bbox[3]) / 2

            best_idx = -1
            best_score = float("inf")

            for i, anchor in enumerate(anchors):
                ax0, ay0, ax1, ay1 = anchor.bbox
                # 计算亲和度（越小越好）
                dist = math.sqrt((tb_cx - anchor_cx[i]) ** 2 + (tb_cy - anchor_cy[i]) ** 2)

                # 正下方加分: 文字顶部在图片底部附近/以下 且 X 轴有重叠
                x_overlap = max(0, min(tb.bbox[2], ax1) - max(tb.bbox[0], ax0))
                x_span = max(1, tb.bbox[2] - tb.bbox[0])
                overlap_ratio = x_overlap / x_span

                score = dist
                if overlap_ratio > 0.3 and tb.bbox[1] >= ay0:
                    # 正下方: 大幅降低分值（优先归属）
                    score = dist * 0.3

                if score < best_score:
                    best_score = score
                    best_idx = i

            if best_score > ORPHAN_THRESHOLD:
                orphans.append(tb)
            else:
                groups[best_idx].append(tb)

        # 构建 boundaries
        boundaries: list[SKUBoundary] = []
        for i, anchor in enumerate(anchors):
            blocks = groups[i]
            if not blocks:
                # 无关联文字块时: 直接用图片 bbox 作边界（密集图片目录页）
                boundaries.append(SKUBoundary(
                    boundary_id=len(boundaries) + 1,
                    bbox=anchor.bbox,
                    text_content="",
                ))
                continue
            # 合并图片 bbox 与文字 bbox
            all_x0 = min(anchor.bbox[0], min(b.bbox[0] for b in blocks))
            all_y0 = min(anchor.bbox[1], min(b.bbox[1] for b in blocks))
            all_x1 = max(anchor.bbox[2], max(b.bbox[2] for b in blocks))
            all_y1 = max(anchor.bbox[3], max(b.bbox[3] for b in blocks))
            text = " ".join(b.content for b in blocks)
            boundaries.append(SKUBoundary(
                boundary_id=len(boundaries) + 1,
                bbox=(all_x0, all_y0, all_x1, all_y1),
                text_content=text[:2000],
            ))

        # 孤儿文字用 Y-gap 法
        if orphans:
            orphans.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
            current_group: list[TextBlock] = [orphans[0]]
            for j in range(1, len(orphans)):
                prev = orphans[j - 1]
                curr = orphans[j]
                gap = curr.bbox[1] - prev.bbox[3] if curr.bbox[1] > prev.bbox[3] else 0
                if gap > 30:
                    boundaries.append(TwoStageExtractor._group_to_boundary(
                        current_group, len(boundaries) + 1))
                    current_group = [curr]
                else:
                    current_group.append(curr)
            if current_group:
                boundaries.append(TwoStageExtractor._group_to_boundary(
                    current_group, len(boundaries) + 1))

        return boundaries

    @staticmethod
    def _group_to_boundary(blocks: list[TextBlock], bid: int) -> SKUBoundary:
        x0 = min(b.bbox[0] for b in blocks)
        y0 = min(b.bbox[1] for b in blocks)
        x1 = max(b.bbox[2] for b in blocks)
        y1 = max(b.bbox[3] for b in blocks)
        text = " ".join(b.content for b in blocks)
        return SKUBoundary(boundary_id=bid, bbox=(x0, y0, x1, y1), text_content=text[:2000])

    def _rule_extract(self, boundaries: list[SKUBoundary], raw: ParsedPageIR) -> list[SKUResult]:
        """规则兜底: 从文本内容提取基本属性。"""
        import re
        results = []
        for b in boundaries:
            attrs: dict = {}
            text = b.text_content
            if text:
                attrs["product_name"] = text[:100]
            price_match = re.search(r'[\$¥€£]\s*([\d,.]+)', text)
            if price_match:
                attrs["price"] = price_match.group(0)
            model_match = re.search(r'[A-Z]{1,5}[-\s]?\d{2,10}', text)
            if model_match:
                attrs["model_number"] = model_match.group(0)
            results.append(SKUResult(
                attributes=attrs,
                source_bbox=b.bbox,
                validity="valid" if attrs.get("product_name") else "invalid",
                confidence=0.5,
                extraction_method="two_stage_rule",
            ))
        return results
