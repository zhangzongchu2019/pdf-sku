"""结构化特征提取。对齐: Pipeline 详设 §5.3"""
from __future__ import annotations
import re
from pdf_sku.pipeline.ir import ParsedPageIR, FeatureVector

PRICE_PATTERN = re.compile(r'[\$¥€£]\s*\d+[.,]?\d*|[\d,]+\.\d{2}\s*(?:元|USD|RMB)')
MODEL_PATTERN = re.compile(r'[A-Z]{1,5}[-\s]?\d{2,10}|(?:型号|Model|SKU|Art\.?\s*No)[.:：\s]*\S+', re.IGNORECASE)


class FeatureExtractor:
    def extract(self, raw: ParsedPageIR) -> FeatureVector:
        page_area = max(1.0, raw.metadata.page_width * raw.metadata.page_height)
        text_area = sum(
            (b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1])
            for b in raw.text_blocks if b.bbox != (0, 0, 0, 0)
        )
        table_area = sum(
            (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1])
            for t in raw.tables if t.bbox != (0, 0, 0, 0)
        )
        font_sizes = [b.font_size for b in raw.text_blocks if b.font_size > 0]

        return FeatureVector(
            text_density=text_area / page_area,
            image_density=len(raw.images) / max(1, page_area / 100000),
            table_area_ratio=table_area / page_area,
            avg_font_size=sum(font_sizes) / max(1, len(font_sizes)),
            has_price_pattern=bool(PRICE_PATTERN.search(raw.raw_text)),
            has_model_pattern=bool(MODEL_PATTERN.search(raw.raw_text)),
            text_block_count=len(raw.text_blocks),
            image_count=len(raw.images),
            table_count=len(raw.tables),
            layout_complexity=min(1.0, (len(raw.text_blocks) + len(raw.images) * 2) / 50),
        )
