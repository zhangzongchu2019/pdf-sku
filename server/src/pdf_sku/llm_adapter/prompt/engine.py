"""
Prompt 渲染引擎。对齐: LLM Adapter 详设 §4

职责:
- 模板管理 (eval_document, classify_page, extract_sku_attrs 等)
- 变量注入 (category, industry, few-shot examples)
- 输入安全: 转义 user input, 长度截断
"""
from __future__ import annotations
from typing import Any
import structlog

logger = structlog.get_logger()

# ─── Prompt 模板 (内嵌，后续可改为文件加载) ───

EVAL_DOCUMENT_TEMPLATE = """You are evaluating a product catalog PDF for automated SKU extraction suitability.

Analyze the provided page screenshot(s) and rate on 0.0-1.0 scale for each dimension:
- text_clarity: How clear and readable is the text? (OCR quality, font legibility)
- image_quality: Are product images clear, well-lit, and of sufficient resolution?
- layout_structure: Is the page layout structured and consistent? (grid, table, list)
- table_regularity: If tables exist, are they regular and well-formatted?
- sku_density: How rich is the SKU information? (product names, prices, specs)

{category_context}

Respond with ONLY a JSON array, one object per page:
[
  {{
    "page_no": 1,
    "text_clarity": 0.85,
    "image_quality": 0.72,
    "layout_structure": 0.90,
    "table_regularity": 0.80,
    "sku_density": 0.88,
    "overall": 0.83,
    "notes": "Clear product listing with images"
  }}
]"""

EVAL_PAGE_LIGHTWEIGHT_TEMPLATE = """Rate this single catalog page for automated SKU extraction on 0.0-1.0 scale.
Consider: text clarity, image quality, layout structure, table regularity.
Respond with ONLY JSON: {{"score": 0.XX, "reason": "brief explanation"}}"""

CLASSIFY_PAGE_TEMPLATE = """Classify this PDF page into one of these categories:
- product_listing: Contains product information with SKUs
- table_page: Contains structured tabular data
- image_page: Primarily product images
- text_page: Primarily text/descriptions
- mixed: Combination of above
- cover: Cover page or title page
- toc: Table of contents
- blank: Empty or near-empty page
- other: None of the above

Also identify the layout type:
- grid: Products arranged in grid layout
- table: Structured table with rows/columns
- list: Vertical list of items
- freeform: Unstructured layout
- single_product: Single product per page

Respond with ONLY JSON:
{{"page_type": "product_listing", "layout_type": "grid", "confidence": 0.92}}"""

EXTRACT_SKU_BOUNDARIES_TEMPLATE = """You are extracting product (SKU) boundaries from a catalog page.

Page text content:
{text_content}

{table_context}

Identify each distinct product/SKU on this page. For each product, return its approximate
bounding region and a brief label.

{few_shot_examples}

Respond with ONLY a JSON array:
[
  {{
    "sku_index": 1,
    "label": "Product name or brief identifier",
    "bbox": [x1, y1, x2, y2],
    "confidence": 0.9
  }}
]
If no products found, return an empty array: []"""

EXTRACT_SKU_ATTRS_TEMPLATE = """You are extracting structured product attributes from a catalog page.

{sku_context}

Page text content:
{text_content}

{table_context}

For each product/SKU identified, extract ALL available attributes. Common attributes include:
- product_name, brand, model, sku_code, price, currency
- material, color, size, weight, dimensions
- description, specifications, category

{category_hints}

{few_shot_examples}

Respond with ONLY a JSON array of SKU objects:
[
  {{
    "sku_index": 1,
    "attributes": {{
      "product_name": "...",
      "brand": "...",
      "price": "...",
      "color": "...",
      ...
    }},
    "confidence": 0.88,
    "source_text": "relevant source text snippet"
  }}
]"""

EXTRACT_SKU_SINGLE_STAGE_TEMPLATE = """You are extracting structured product (SKU) data from a catalog page.

This is a single-pass extraction. Identify ALL products on the page and extract their attributes.

Page text:
{text_content}

{table_context}

{few_shot_examples}

For each product found, extract: product_name, brand, model, sku_code, price, currency,
material, color, size, weight, dimensions, description, and any other visible attributes.

Respond with ONLY a JSON array:
[
  {{
    "sku_index": 1,
    "attributes": {{"product_name": "...", "price": "...", ...}},
    "bbox": [x1, y1, x2, y2],
    "confidence": 0.85
  }}
]
If no products found, return: []"""

CROSS_PAGE_TABLE_TEMPLATE = """Analyze whether this page is a continuation of a table from the previous page.

Previous page ending:
{prev_page_ending}

Current page beginning:
{current_page_beginning}

Determine:
1. Is the current page a continuation of the previous page's table?
2. If yes, should the first row be merged with the last row of the previous page?

Respond with ONLY JSON:
{{"is_continuation": true, "merge_first_row": false, "confidence": 0.9, "reason": "..."}}"""

CONSISTENCY_CHECK_TEMPLATE = """Review extracted SKU data for consistency and completeness.

Extracted SKUs:
{sku_data}

Page context (layout type: {layout_type}, expected SKU density: {expected_density}):

Check for:
1. Missing critical fields (product_name is mandatory)
2. Duplicate SKUs (same product listed twice)
3. Price format consistency
4. Attribute value plausibility

Respond with ONLY JSON:
{{
  "valid_skus": [0, 1, 3],
  "invalid_skus": [2],
  "issues": [
    {{"sku_index": 2, "issue": "missing product_name", "severity": "critical"}}
  ],
  "overall_quality": 0.85
}}"""


class PromptEngine:
    """Prompt 模板管理 + 变量渲染。"""

    TEMPLATES: dict[str, str] = {
        "eval_document": EVAL_DOCUMENT_TEMPLATE,
        "eval_page_lightweight": EVAL_PAGE_LIGHTWEIGHT_TEMPLATE,
        "classify_page": CLASSIFY_PAGE_TEMPLATE,
        "extract_sku_boundaries": EXTRACT_SKU_BOUNDARIES_TEMPLATE,
        "extract_sku_attrs": EXTRACT_SKU_ATTRS_TEMPLATE,
        "extract_sku_single_stage": EXTRACT_SKU_SINGLE_STAGE_TEMPLATE,
        "cross_page_table": CROSS_PAGE_TABLE_TEMPLATE,
        "consistency_check": CONSISTENCY_CHECK_TEMPLATE,
    }

    VERSION = "v1.0"

    def get_prompt(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """渲染 prompt 模板。"""
        template = self.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")

        variables = variables or {}

        # 注入 category 上下文
        category = variables.get("category", "")
        category_context = ""
        if category:
            category_context = f"This PDF is from the '{category}' product category. Apply domain-specific evaluation criteria."
        variables["category_context"] = category_context

        # 安全: 截断过长变量
        for k, v in variables.items():
            if isinstance(v, str) and len(v) > 2000:
                variables[k] = v[:2000] + "... [truncated]"

        try:
            return template.format(**variables)
        except KeyError:
            # 模板中有未提供的变量 → 替换为空
            import re
            result = template
            for match in re.finditer(r'\{(\w+)\}', template):
                key = match.group(1)
                if key not in variables:
                    result = result.replace(f'{{{key}}}', '')
            return result

    def get_version(self, template_name: str) -> str:
        return f"{template_name}:{self.VERSION}"

    def list_templates(self) -> list[str]:
        return list(self.TEMPLATES.keys())
