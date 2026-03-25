"""
Pass 2 审核器: 对照截图审核 Pass 1 提取结果。
过滤幻觉、修正字段格式。
"""
from __future__ import annotations

import json

from pdf_sku.pipeline.ir import SKUResult
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
import structlog

logger = structlog.get_logger()
_parser = ResponseParser()

REVIEW_PROMPT = """你是一个商品数据审核员。请对照 PDF 页面截图，审核以下从该页面提取的商品列表。

提取结果:
{sku_json}

请逐个审核每个商品，判断:
1. 该商品是否在截图中作为一个可售卖的产品/商品存在？
2. product_name 是否来自页面上的实际文字标注（而非对图片的描述）？
3. price、model_number 等字段是否与截图一致？

应该丢弃 (discard) 的情况:
- 商品名称是你对图片内容的描述 (如 "Grey Sofa", "木质餐桌", "装饰画")，而非页面实际标注的产品名称
- 商品在截图中不存在（虚构/幻觉）
- 实际是页面标题、分类标题、品牌介绍等非商品信息
- 同一商品被重复提取（保留信息最完整的那条）
- 实际是产品变体/规格描述（如"床垫尺寸"、"外径尺寸"、"常规款/宽屏款"），而非独立产品
- 颜色/材质描述被误当作产品名称（如"高级灰"、"胡桃色"）
- 品牌来源/参考文字（如"EDRA STANDARD BED"、"MINOTTI LAWRENCE BED"）— 这些是设计参考来源而非在售商品名称
- 如果同一页面已有对应的中文产品名称（如"花瓣床"），英文品牌来源描述应丢弃
- 纯组合代号（如"组合D"、"组合N"、"Combination F"）— 这些是产品布局方案代码，不是独立商品
- 纯材质/面料标签（如"布艺款"、"皮艺款"、"Fabric style"、"Leather style"）— 不是独立商品
- "MODEL XXX" 类文字 — 这是型号标注文本，不是商品名称
- 同一产品的不同座位数/尺寸变体（如"XX单位沙发"和"XX双位沙发"和"XX三位沙发"）— 只保留一条，在 model_number 中标注全部尺寸

应该保留 (keep) 的情况:
- 页面上有文字标注名称/型号/价格的实际商品

审核规则:
- 如果商品名称是英文但截图中对应的是中文，用中文修正
- product_name 应包含完整描述（型号+尺寸+材质等），可多行（用 \\n 分隔）

仅返回 JSON 数组:
[{{"index": 0, "action": "keep|discard", "reason": "简要原因", "corrected": {{"product_name": "修正后名称", "price": "修正后价格"}}}}]

corrected 字段只在需要修正时提供，不需要修正的字段不要包含在 corrected 中。"""


class SKUReviewer:
    """Pass 2: 对照截图审核 SKU 提取结果。"""

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def review(
        self,
        skus: list[SKUResult],
        screenshot: bytes | None = None,
        scene_filter: bool = False,
        pure_visual: bool = False,
    ) -> list[SKUResult]:
        """审核 SKU 列表，过滤幻觉并修正字段。"""
        if not skus or not self._llm or not screenshot:
            return skus

        # 构建待审核的 JSON
        sku_data = []
        for i, sku in enumerate(skus):
            sku_data.append({
                "index": i,
                "product_name": sku.attributes.get("product_name", ""),
                "model_number": sku.attributes.get("model_number", ""),
                "price": sku.attributes.get("price", ""),
                "specs": sku.attributes.get("specs", ""),
                "color": sku.attributes.get("color", ""),
            })

        try:
            prompt = REVIEW_PROMPT.format(sku_json=json.dumps(sku_data, ensure_ascii=False, indent=2))
            if pure_visual:
                prompt += ("\n\n重要提示: 此页面是纯图片产品目录页（几乎没有文字标注）。"
                           "在这种页面中，LLM 根据图片视觉特征推断的产品名称（如\"餐椅\"、\"沙发\"、\"茶几\"）"
                           "是合法的产品名称，不应被视为'图片内容描述'而丢弃。"
                           "仅当商品明显是场景装饰物（如花瓶、窗帘、墙画）且不是家具产品时才丢弃。"
                           "请宽松保留，减少误丢。")
            if scene_filter:
                prompt += ("\n注意: 此页面为场景展示页。"
                           "没有文字标注（名称/型号/价格）的物品应判定为 discard。"
                           "仅保留有明确文字标签的商品。")
            resp = await self._llm._call_llm(
                operation="sku_review",
                prompt=prompt,
                images=[screenshot],
            )
            parsed = _parser.parse(resp.text, expected_type="array")
            if not parsed.success or not isinstance(parsed.data, list):
                logger.warning("sku_review_parse_failed")
                return skus

            reviewed = self._apply_review(skus, parsed.data)

            # 安全阀: 丢弃过多时回退保留原结果
            discarded_count = len(skus) - len(reviewed)
            if discarded_count > 0:
                # 全部丢弃 → 回退
                if not reviewed:
                    logger.warning("sku_review_all_discarded_fallback",
                                   original=len(skus),
                                   msg="Reviewer discarded all SKUs, keeping originals")
                    return skus
                # 场景页允许 Reviewer 丢弃更多（场景图册大多数是装饰品，应该丢弃）
                # 非场景页: 丢弃数 > 保留数 → 回退
                discard_ratio = 5 if scene_filter else 1
                if discarded_count > len(reviewed) * discard_ratio:
                    logger.warning("sku_review_too_aggressive_fallback",
                                   original=len(skus), kept=len(reviewed),
                                   discarded=discarded_count,
                                   scene_filter=scene_filter,
                                   msg="Reviewer discarded too many, keeping originals")
                    return skus

            return reviewed

        except Exception as e:
            logger.warning("sku_review_failed", error=str(e))
            return skus

    def _apply_review(
        self,
        skus: list[SKUResult],
        reviews: list[dict],
    ) -> list[SKUResult]:
        """应用审核结果: 过滤 discard，合并 corrected。"""
        # 建立 index → review 映射
        review_map = {}
        for r in reviews:
            idx = r.get("index")
            if idx is not None:
                review_map[idx] = r

        result = []
        discarded = 0
        corrected = 0
        for i, sku in enumerate(skus):
            review = review_map.get(i)
            if review and review.get("action") == "discard":
                # Companion SKU 不因"重复"丢弃 — 它们是不同产品（如床头柜配套床）
                reason = review.get("reason", "")
                if (sku.extraction_method == "companion_rescue"
                        and ("重复" in reason or "duplicate" in reason.lower()
                             or "已有" in reason)):
                    logger.info("companion_protected",
                                index=i,
                                name=sku.attributes.get("product_name", ""),
                                reason=reason)
                else:
                    discarded += 1
                    logger.debug("sku_discarded",
                                 index=i,
                                 name=sku.attributes.get("product_name", ""),
                                 reason=reason)
                    continue

            # 合并修正
            if review and review.get("corrected"):
                for field, value in review["corrected"].items():
                    if value and field in sku.attributes:
                        sku.attributes[field] = value
                    elif value:
                        sku.attributes[field] = value
                corrected += 1

            result.append(sku)

        if discarded or corrected:
            logger.info("sku_review_applied",
                        total=len(skus),
                        discarded=discarded,
                        corrected=corrected,
                        kept=len(result))
        return result
