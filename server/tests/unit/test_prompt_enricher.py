"""PromptEnricher 测试。"""
import pytest
from pdf_sku.llm_adapter.prompt_enricher import (
    PromptEnricher, MAX_FEWSHOT_EXAMPLES, MAX_CONTEXT_CHARS,
)
from pdf_sku.pipeline.ir import FeatureVector


def test_constants():
    assert MAX_FEWSHOT_EXAMPLES == 3
    assert MAX_CONTEXT_CHARS == 500


@pytest.mark.asyncio
async def test_classify_prompt_no_db():
    enricher = PromptEnricher()
    features = FeatureVector(
        text_density=0.5,
        image_density=0.3,
        table_area_ratio=0.0,
        text_block_count=10,
        image_count=3,
        table_count=0,
        has_price_pattern=True,
        has_model_pattern=True,
        layout_complexity=0.6,
    )
    prompt = await enricher.build_classify_prompt(
        db=None,
        features=features,
        prev_page_summary="Previous page had tables",
    )
    assert "Page Classification" in prompt
    assert "text_density" in prompt
    assert "Previous Page" in prompt
    assert "A/B/C/D" in prompt


@pytest.mark.asyncio
async def test_extract_prompt_no_db():
    enricher = PromptEnricher()
    prompt = await enricher.build_extract_prompt(
        db=None,
        page_type="B",
        text_content="Widget Model X100 $29.99",
    )
    assert "SKU Extraction" in prompt
    assert "Widget" in prompt
    assert "Page type: B" in prompt


@pytest.mark.asyncio
async def test_binding_prompt():
    enricher = PromptEnricher()
    prompt = await enricher.build_binding_prompt(
        db=None,
        skus=[{"sku_id": "s1", "product_name": "Widget"}],
        images=[{"image_id": "i1", "x": 100, "y": 200, "role": "product_main"}],
    )
    assert "SKU-Image Binding" in prompt
    assert "s1" in prompt
    assert "i1" in prompt
