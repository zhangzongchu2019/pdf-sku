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
                # 丢弃数 > 保留数 → 回退 (Reviewer 可能误判)
                if discarded_count > len(reviewed):
                    logger.warning("sku_review_too_aggressive_fallback",
                                   original=len(skus), kept=len(reviewed),
                                   discarded=discarded_count,
                                   msg="Reviewer discarded majority, keeping originals")
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
                discarded += 1
                logger.debug("sku_discarded",
                             index=i,
                             name=sku.attributes.get("product_name", ""),
                             reason=review.get("reason", ""))
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
