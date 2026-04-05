"""区域级文本属性抽取。"""
from __future__ import annotations

import re

from .models import PageEvidence, RegionProposal

_LABEL_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "price": (
        re.compile(r"(?:售价|价格|单价|price)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "model_number": (
        re.compile(r"(?:货号|型号|编号|model(?:\s+number)?)\s*[:：]?\s*([A-Za-z0-9\-_#/]+)", re.IGNORECASE),
    ),
    "product_id": (
        re.compile(r"(?:商品ID|product\s+id)\s*[:：]?\s*([A-Za-z0-9\-_#/]+)", re.IGNORECASE),
    ),
    "tag": (
        re.compile(r"(?:标签|tag)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "source": (
        re.compile(r"(?:来源(?:\(仅自己可见\))?|source)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "short_name": (
        re.compile(r"(?:商品简称|short\s+name)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "specs": (
        re.compile(r"(?:商品规格|规格|尺寸|specs?|size)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "color": (
        re.compile(r"(?:颜色|colou?r)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "spec_code": (
        re.compile(r"(?:规格编码|spec\s+code)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "wholesale_price": (
        re.compile(r"(?:批发价|wholesale\s+price)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "pack_price": (
        re.compile(r"(?:打包价|pack\s+price)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "dropship_price": (
        re.compile(r"(?:代发价|dropship\s+price)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "purchase_price": (
        re.compile(r"(?:拿货价(?:\(仅自己可见\))?|purchase\s+price)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "campaign_type": (
        re.compile(r"(?:活动类型|campaign\s+type)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "campaign_price": (
        re.compile(r"(?:活动价|campaign\s+price)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "stock": (
        re.compile(r"(?:库存|stock)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "weight_kg": (
        re.compile(r"(?:重量(?:\(kg\))?|weight(?:\(kg\))?)\s*[:：]?\s*([^\s,，;；]+)", re.IGNORECASE),
    ),
    "auto_unpublish_time": (
        re.compile(r"(?:自动下架时间|auto\s+unpublish\s+time)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
    "remark": (
        re.compile(r"(?:备注(?:\(公开\))?|remark)\s*[:：]?\s*([^\n]+)", re.IGNORECASE),
    ),
}

_LABEL_KEYWORDS = {
    "售价", "价格", "单价", "price", "货号", "型号", "编号", "model", "商品规格", "规格", "尺寸",
    "spec", "size", "颜色", "color", "colour", "商品ID", "product id", "标签", "tag", "来源",
    "source", "商品简称", "short name", "规格编码", "spec code", "批发价", "wholesale", "打包价",
    "pack", "代发价", "dropship", "拿货价", "purchase", "活动类型", "campaign type", "活动价",
    "campaign", "库存", "stock", "重量", "weight", "自动下架时间", "备注", "remark",
}


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").strip())


def _cleanup_value(value: str) -> str:
    return value.strip().strip("：:;；,，")


def _looks_like_label_line(line: str) -> bool:
    return any(keyword in line for keyword in _LABEL_KEYWORDS)


def _member_texts(region: RegionProposal, evidence: PageEvidence) -> list[str]:
    object_map = {obj.object_id: obj for obj in evidence.objects}
    texts = [
        line
        for object_id in region.member_object_ids
        if object_id in object_map and object_map[object_id].object_type in {"text_block", "ocr_block"}
        for line in (_normalize_line(part) for part in object_map[object_id].text.splitlines())
    ]
    return [text for text in texts if text]


class RegionAttributeExtractor:
    """从区域文本中抽取结构化字段。"""

    def extract(self, region: RegionProposal, evidence: PageEvidence) -> dict[str, str]:
        lines = _member_texts(region, evidence)
        if not lines:
            return {"evidence_mode": "visual_only"}

        merged_text = "\n".join(lines)
        attributes: dict[str, str] = {
            "evidence_mode": "text_backed",
            "raw_attribute_text": " ".join(dict.fromkeys(lines)),
            "product_description": " ".join(dict.fromkeys(lines)),
        }

        for field, patterns in _LABEL_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(merged_text)
                if match:
                    value = _cleanup_value(match.group(1))
                    if value:
                        attributes[field] = value
                        break

        non_label_lines = [
            line for line in lines
            if not _looks_like_label_line(line) and not re.fullmatch(r"[\d\W]+", line)
        ]
        if non_label_lines:
            attributes["product_name"] = non_label_lines[0]
        elif attributes.get("raw_attribute_text"):
            product_name = attributes["raw_attribute_text"]
            for field, patterns in _LABEL_PATTERNS.items():
                if field == "product_name":
                    continue
                for pattern in patterns:
                    product_name = pattern.sub("", product_name)
            product_name = re.sub(r"\s+", " ", product_name).strip(" :：,，;；")
            attributes["product_name"] = product_name or attributes["raw_attribute_text"]

        return attributes
