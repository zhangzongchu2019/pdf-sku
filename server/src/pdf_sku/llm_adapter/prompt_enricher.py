"""
Prompt 增强器 — Few-shot 样本注入 + 上下文增强。

- 从 annotation_examples 获取 confirmed 样本
- 构建 few-shot prompt 段
- 页面上下文 (前后页摘要)
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import AnnotationExample
from pdf_sku.pipeline.ir import FeatureVector, ClassifyResult
import structlog

logger = structlog.get_logger()

MAX_FEWSHOT_EXAMPLES = 3
MAX_CONTEXT_CHARS = 500


class PromptEnricher:
    """LLM Prompt 增强器。"""

    async def build_classify_prompt(
        self,
        db: AsyncSession | None,
        features: FeatureVector,
        prev_page_summary: str = "",
        next_page_summary: str = "",
    ) -> str:
        """构建页面分类 prompt。"""
        parts = [
            "# Page Classification\n",
            "Classify this page into one of: A (table-dominant), "
            "B (mixed product), C (image-heavy product), D (non-product).\n",
        ]

        # Few-shot examples
        if db:
            examples = await self._get_examples(db, "PAGE_TYPE_CORRECTION")
            if examples:
                parts.append("\n## Examples\n")
                for i, ex in enumerate(examples, 1):
                    output = ex.output_json or {}
                    parts.append(
                        f"Example {i}: {output.get('input_summary', '...')} "
                        f"→ {output.get('corrected_page_type', '?')}\n")

        # Page context
        parts.append("\n## Current Page Features\n")
        parts.append(features.to_prompt_context())

        if prev_page_summary:
            parts.append(f"\n## Previous Page\n{prev_page_summary[:MAX_CONTEXT_CHARS]}\n")
        if next_page_summary:
            parts.append(f"\n## Next Page\n{next_page_summary[:MAX_CONTEXT_CHARS]}\n")

        parts.append("\nReturn JSON: {\"page_type\": \"A/B/C/D\", \"confidence\": 0.0-1.0}")
        return "".join(parts)

    async def build_extract_prompt(
        self,
        db: AsyncSession | None,
        page_type: str,
        text_content: str,
        category: str | None = None,
    ) -> str:
        """构建 SKU 提取 prompt。"""
        parts = [
            "# SKU Extraction\n",
            f"Page type: {page_type}\n",
            "Extract all product SKUs with attributes: "
            "product_name, model_number, price, specifications.\n",
        ]

        # Few-shot examples
        if db:
            examples = await self._get_examples(
                db, "SKU_ATTRIBUTE_CORRECTION", category)
            if examples:
                parts.append("\n## Examples\n")
                for i, ex in enumerate(examples, 1):
                    output = ex.output_json or {}
                    skus = output.get("corrected_skus", output.get("skus", []))
                    if skus:
                        parts.append(f"Example {i}: {len(skus)} SKUs extracted\n")

        # Page content
        parts.append(f"\n## Page Content\n{text_content[:3000]}\n")
        parts.append(
            "\nReturn JSON array: [{\"product_name\": ..., "
            "\"model_number\": ..., \"price\": ..., \"confidence\": 0.0-1.0}]")
        return "".join(parts)

    async def build_binding_prompt(
        self,
        db: AsyncSession | None,
        skus: list[dict],
        images: list[dict],
    ) -> str:
        """构建 SKU-Image 绑定 prompt (用于歧义消歧)。"""
        parts = [
            "# SKU-Image Binding\n",
            f"Match {len(skus)} SKUs to {len(images)} images.\n",
        ]

        parts.append("\n## SKUs\n")
        for s in skus:
            parts.append(f"- {s.get('sku_id')}: {s.get('product_name', '?')}\n")

        parts.append("\n## Images\n")
        for img in images:
            parts.append(
                f"- {img.get('image_id')}: position=({img.get('x', 0)}, "
                f"{img.get('y', 0)}), role={img.get('role', '?')}\n")

        parts.append(
            "\nReturn JSON: [{\"sku_id\": ..., \"image_id\": ..., \"confidence\": 0.0-1.0}]")
        return "".join(parts)

    async def _get_examples(
        self,
        db: AsyncSession,
        task_type: str,
        category: str | None = None,
    ) -> list[AnnotationExample]:
        """获取 confirmed Few-shot 样本。"""
        try:
            query = (
                select(AnnotationExample).where(
                    AnnotationExample.task_type == task_type,
                    AnnotationExample.is_confirmed == True,  # noqa: E712
                )
                .order_by(AnnotationExample.quality_score.desc())
                .limit(MAX_FEWSHOT_EXAMPLES)
            )
            if category:
                query = query.where(AnnotationExample.category == category)
            result = await db.execute(query)
            return list(result.scalars().all())
        except Exception:
            return []
