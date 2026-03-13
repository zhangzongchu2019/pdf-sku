"""
OCR-Guided SKU 提取器。

核心思路: OCR 文字块 + 布局区域 → 空间聚类 → 结构化文本 → LLM 纯文本提取。
消除 LLM "看图识字" 的瓶颈 (小字体看不到 + 幻觉描述)。
"""
from __future__ import annotations

from collections import defaultdict

import structlog

from pdf_sku.pipeline.ir import SKUResult
from pdf_sku.pipeline.parser.ocr_engine import OcrBlock
from pdf_sku.pipeline.layout_detector import LayoutRegion
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser

logger = structlog.get_logger()
_parser = ResponseParser()

# OCR 文字充足阈值 (字符数)
MIN_OCR_TEXT_LENGTH = 20

OCR_GUIDED_PROMPT = """以下是 PDF 页面上 OCR 识别到的全部文字，按空间区域分组。
请从中提取所有商品(SKU)信息。

{grouped_text}

核心原则: 宁可多提、不可遗漏。确保文字中提到的每一个产品/型号都被提取。

提取规则:
- 对每个商品提取: product_name, model_number, price, specs, color, tag, source
- 只提取真实存在于文字中的信息，不要虚构
- 每个区域中的每个产品/型号都要独立提取为一条 SKU
- 如果某区域列出了多个型号或多个产品名称，每个都要单独提取
- 型号编号 (如 Y001, FP-W01, SPJ-001, 302# 等) 提取到 model_number 字段
- product_name 使用原始中文名称，不要翻译成英文
- 同一商品的不同尺寸/颜色变体，如果有不同型号则分别提取
- 忽略页眉页脚、页码、公司信息、联系方式等非商品内容
- 忽略营销文案、广告语、品牌宣传

重要: 逐区域检查，确保不遗漏任何产品。如果一个区域有 5 个产品，必须提取 5 条。

仅返回 JSON 数组:
[{{"product_name": "...", "model_number": "...", "price": "...", "specs": "...", "color": "...", "confidence": 0.85}}]

如果没有商品信息，返回空数组 []"""


class OcrGuidedExtractor:
    """OCR-Guided SKU 提取: 用 OCR 文字代替 VLM 看图。"""

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def extract(
        self,
        ocr_blocks: list[OcrBlock],
        layout_regions: list[LayoutRegion],
        screenshot: bytes | None = None,
    ) -> list[SKUResult]:
        """OCR-Guided 提取流程。

        1. 空间聚类: OCR 文字块按布局区域分组
        2. 组织为结构化文本
        3. LLM 纯文本模式提取 SKU

        Args:
            ocr_blocks: OCR 识别的文字块
            layout_regions: DocLayout-YOLO 检测的布局区域
            screenshot: 页面截图 (OCR-guided 模式下作为辅助参考)
        """
        if not self._llm or not ocr_blocks:
            return []

        # Step 1: 空间聚类
        groups = self._spatial_cluster(ocr_blocks, layout_regions)

        # Step 2: 组织为结构化文本
        grouped_text = self._format_groups(groups)
        if not grouped_text.strip():
            return []

        # Step 3: LLM 纯文本提取
        prompt = OCR_GUIDED_PROMPT.format(grouped_text=grouped_text)

        try:
            # 纯文本模式: 不发截图，减少 token 消耗 ~60%，消除图文冲突
            resp = await self._llm._call_llm(
                operation="extract_sku_ocr_guided",
                prompt=prompt,
                images=None,
            )

            if not resp.text or not resp.text.strip():
                return []

            parsed = _parser.parse(resp.text, expected_type="array")
            if parsed.success and isinstance(parsed.data, list):
                results = []
                for item in parsed.data:
                    if isinstance(item, dict):
                        attrs = {k: v for k, v in item.items()
                                 if k not in ("confidence",)}
                        results.append(SKUResult(
                            attributes=attrs,
                            validity="valid" if attrs.get("product_name") else "invalid",
                            confidence=float(item.get("confidence", 0.8)),
                            extraction_method="ocr_guided",
                        ))
                return results

        except Exception as e:
            logger.warning("ocr_guided_extract_failed", error=str(e))

        return []

    def _spatial_cluster(
        self,
        ocr_blocks: list[OcrBlock],
        layout_regions: list[LayoutRegion],
    ) -> list[list[OcrBlock]]:
        """将 OCR 文字块按空间邻近度分组。

        策略:
        1. 如果有 figure 区域，以 figure 为锚点，将附近文字归入
        2. 否则按 Y 坐标带状分组
        """
        figure_regions = [r for r in layout_regions
                          if r.label in ("figure", "picture", "image", "photo")]

        if figure_regions:
            return self._cluster_by_figures(ocr_blocks, figure_regions)
        else:
            return self._cluster_by_y_bands(ocr_blocks)

    def _cluster_by_figures(
        self,
        ocr_blocks: list[OcrBlock],
        figures: list[LayoutRegion],
    ) -> list[list[OcrBlock]]:
        """以 figure 区域为锚点分组。

        每个 figure 扩展一个 margin 后，将落入范围的文字块归入。
        未归入任何 figure 的文字块单独成组。
        """
        if not figures:
            return [ocr_blocks] if ocr_blocks else []

        # 计算图片平均高度作为 margin 参考
        avg_h = sum(f.bbox[3] - f.bbox[1] for f in figures) / len(figures)
        margin = max(avg_h * 0.5, 50)  # 至少 50px

        assigned: set[int] = set()
        groups: list[list[OcrBlock]] = []

        for fig in figures:
            fx0, fy0, fx1, fy1 = fig.bbox
            # 扩展搜索区域
            ex0, ey0 = fx0 - margin, fy0 - margin
            ex1, ey1 = fx1 + margin, fy1 + margin

            group: list[OcrBlock] = []
            for i, block in enumerate(ocr_blocks):
                if i in assigned:
                    continue
                bx0, by0, bx1, by1 = block.bbox
                # 文字块中心是否在扩展区域内
                cx = (bx0 + bx1) / 2
                cy = (by0 + by1) / 2
                if ex0 <= cx <= ex1 and ey0 <= cy <= ey1:
                    group.append(block)
                    assigned.add(i)

            if group:
                groups.append(group)

        # 未分配的文字块
        remaining = [ocr_blocks[i] for i in range(len(ocr_blocks))
                     if i not in assigned]
        if remaining:
            # 按 Y 坐标子分组
            sub_groups = self._cluster_by_y_bands(remaining)
            groups.extend(sub_groups)

        return groups

    def _cluster_by_y_bands(
        self,
        blocks: list[OcrBlock],
    ) -> list[list[OcrBlock]]:
        """按 Y 坐标带状分组 (无 figure 锚点时的 fallback)。

        相邻文字块 Y 间距 > 阈值时断开为新组。
        """
        if not blocks:
            return []

        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))

        # 估算行高
        heights = [b.bbox[3] - b.bbox[1] for b in sorted_blocks if b.bbox[3] > b.bbox[1]]
        avg_line_h = sum(heights) / len(heights) if heights else 20
        gap_threshold = avg_line_h * 3  # Y 间距超过 3 倍行高则断开

        groups: list[list[OcrBlock]] = []
        current: list[OcrBlock] = [sorted_blocks[0]]

        for block in sorted_blocks[1:]:
            prev_bottom = current[-1].bbox[3]
            curr_top = block.bbox[1]
            if curr_top - prev_bottom > gap_threshold:
                groups.append(current)
                current = [block]
            else:
                current.append(block)

        if current:
            groups.append(current)

        return groups

    def _format_groups(self, groups: list[list[OcrBlock]]) -> str:
        """将分组后的文字块格式化为结构化文本。"""
        parts: list[str] = []

        for idx, group in enumerate(groups):
            if not group:
                continue

            # 区域坐标范围
            x0 = min(b.bbox[0] for b in group)
            y0 = min(b.bbox[1] for b in group)
            x1 = max(b.bbox[2] for b in group)
            y1 = max(b.bbox[3] for b in group)

            # 按位置排序后拼接
            sorted_blocks = sorted(group, key=lambda b: (b.bbox[1], b.bbox[0]))
            text_lines = [b.text for b in sorted_blocks]

            parts.append(
                f"[区域 {idx + 1} — 坐标({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})]\n"
                f"文字: {chr(10).join(text_lines)}"
            )

        return "\n\n".join(parts)
