"""
单阶段 SKU 提取 (Fallback)。对齐: Pipeline 详设 §5.2

两阶段失败/无效率高时回退到单阶段。
单 LLM 调用: 一次性提取所有 SKU + 属性。
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import ParsedPageIR, SKUResult
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
import structlog

logger = structlog.get_logger()
_parser = ResponseParser()

SINGLE_STAGE_PROMPT = """从这个 PDF 页面中提取所有商品(SKU)信息。
对每个商品提取: product_name, model_number, price, specs, color, tag, source。

核心原则: 宁可多提、不可遗漏。确保页面上每一个可识别的产品都被提取。

提取规则:
- 仔细扫描页面的每个区域（左上、右上、左下、右下、中间），不要只关注最显眼的产品
- 如果页面是产品图册/画册，每个不同的产品图片区域都要提取为独立 SKU
- 小字体的型号编号（如 Y001, FP-W01, SPJ-001, 302# 等）务必提取到 model_number 字段
- product_name: 使用页面上标注的中文名称。如果没有文字标注但能看到产品图片，用简短中文描述产品类型（如"沙发"、"茶几"、"餐椅"）
- 看到中文商品用中文提取，不要翻译成英文
- 如果页面上有多个产品但文字很少，每个产品图片区域仍需独立提取一条 SKU
- 不要虚构不存在的信息，但对于页面上可见的产品图片，即使只有图片没有文字也要提取
- 如果页面没有任何商品（如目录页、封面页、纯文字说明页），返回空数组 []

重要: 不要提前停止！如果页面有 10 个产品，必须提取 10 条 SKU。逐区域检查确保无遗漏。

自校验:
- 回顾整个页面，是否有被忽略的产品区域？
- 是否有小字体的型号/价格没有被提取？
- 不要把营销文案、广告语、公司介绍、联系方式当作商品
- 不要把表格列标题行、目录标题当作商品

仅返回 JSON 数组:
[{{"product_name": "...", "model_number": "...", "price": "...", "specs": "...", "color": "...", "confidence": 0.8}}]"""


RESCUE_PROMPT = """这个 PDF 页面包含商品但之前提取不完整。请重新仔细检查整个页面，提取所有商品。

系统性扫描方法:
1. 从页面左上角开始，按"Z"形路径扫描到右下角
2. 每个产品图片区域都是一个独立 SKU
3. 注意小字体: 型号编号通常在图片角落或底部（如 Y001, FP-W01, SPJ-001, 302# 等）
4. 产品名称可能在图片旁边、下方、上方、或直接印在图片上

提取要求:
- 对每个可见的产品图片区域，提取一条 SKU
- 即使只有产品图片没有文字，也要用简短中文描述产品类型（如"沙发"、"茶几"）
- 型号编号提取到 model_number 字段
- 配套家具（如床+床头柜）分别提取为独立 SKU
- 不要遗漏任何产品区域

仅返回 JSON 数组:
[{{"product_name": "...", "model_number": "...", "price": "...", "specs": "...", "color": "...", "confidence": 0.7}}]"""


class SingleStageExtractor:
    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def extract(
        self,
        raw: ParsedPageIR,
        text_roles: list[str] | None = None,
        profile: dict | None = None,
        screenshot: bytes | None = None,
        sku_count_hint: tuple[int, int] | None = None,
        region_hint: str | None = None,
        scene_filter: bool = False,
    ) -> list[SKUResult]:
        """单阶段提取: 一次 LLM 调用获取所有 SKU。

        Args:
            sku_count_hint: 预估 SKU 数范围 (min, max)
            region_hint: 区域提示 (切片模式下标注第几片)
            scene_filter: 启用场景过滤 (大图覆盖页面时过滤场景展示图)
        """
        if not self._llm:
            return self._rule_extract(raw)

        try:
            # 构建 prompt，注入 OCR 文本辅助 LLM 交叉验证
            prompt = SINGLE_STAGE_PROMPT
            text_content = (raw.raw_text or "").strip()
            if text_content:
                if len(text_content) > 3000:
                    text_content = text_content[:3000] + "..."
                prompt += f"\n\n## 本页 OCR 文本 (辅助参考，以截图为准)\n{text_content}"

            # 动态 Prompt 增强
            if sku_count_hint:
                lo, hi = sku_count_hint
                if lo > 0 and hi > 0:
                    prompt += f"\n\n## 数量提示\n预计该区域有 {lo}-{hi} 个商品，请确保全部提取，不要遗漏。"
            if region_hint:
                prompt += f"\n\n## 区域上下文\n{region_hint}"
            if scene_filter:
                prompt += ("\n\n## 场景过滤\n"
                           "若图片为场景展示图（如样板间、展厅全景），"
                           "只提取有明确标注（文字/价签/型号）的产品，"
                           "忽略纯装饰背景中无标注的物品。")

            resp = await self._llm._call_llm(
                operation="extract_sku_single",
                prompt=prompt,
                images=[screenshot] if screenshot else None,
            )

            # 响应验证: 空响应或纯空白 → 回退规则提取
            if not resp.text or not resp.text.strip():
                logger.warning("single_stage_empty_response")
                return self._rule_extract(raw)

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
                            confidence=float(item.get("confidence", 0.6)),
                            extraction_method="single_stage",
                        ))

                # 验证: 全部 SKU 的 product_name 为空 → 回退规则提取
                if results and all(
                    not (r.attributes.get("product_name") or "").strip()
                    for r in results
                ):
                    logger.warning("single_stage_all_empty_names", count=len(results))
                    return self._rule_extract(raw)

                return results
        except Exception as e:
            logger.warning("single_stage_failed", error=str(e))

        return self._rule_extract(raw)

    async def extract_rescue(
        self,
        raw: ParsedPageIR,
        screenshot: bytes | None = None,
    ) -> list[SKUResult]:
        """二次提取 (rescue pass): 用更激进的 Prompt 查找遗漏的商品。"""
        if not self._llm or not screenshot:
            return []

        try:
            prompt = RESCUE_PROMPT
            text_content = (raw.raw_text or "").strip()
            if text_content:
                if len(text_content) > 3000:
                    text_content = text_content[:3000] + "..."
                prompt += f"\n\n## 本页 OCR 文本\n{text_content}"

            resp = await self._llm._call_llm(
                operation="extract_sku_rescue",
                prompt=prompt,
                images=[screenshot],
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
                            confidence=float(item.get("confidence", 0.5)),
                            extraction_method="single_stage_rescue",
                        ))
                return results
        except Exception as e:
            logger.warning("rescue_extract_failed", error=str(e))
        return []

    def _rule_extract(self, raw: ParsedPageIR) -> list[SKUResult]:
        """最后规则兜底 (从表格提取)。"""
        results = []
        for table in raw.tables:
            if not table.rows or len(table.rows) < 2:
                continue
            headers = [h.lower().strip() for h in table.rows[0]]
            for row in table.rows[1:]:
                attrs = {}
                for i, cell in enumerate(row):
                    if i < len(headers) and cell:
                        attrs[headers[i]] = cell
                if attrs:
                    results.append(SKUResult(
                        attributes=attrs,
                        validity="valid" if any(attrs.values()) else "invalid",
                        confidence=0.4,
                        extraction_method="single_stage_rule",
                    ))
        return results
