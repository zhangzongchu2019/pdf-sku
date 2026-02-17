"""IR 数据结构测试。"""
from pdf_sku.pipeline.ir import (
    ParsedPageIR, TextBlock, TableData, ImageInfo, FeatureVector,
    SKUResult, BindingResult, PageResult, PageChunk,
)


def test_parsed_page_defaults():
    ir = ParsedPageIR(page_no=1)
    assert ir.page_no == 1
    assert ir.text_blocks == []
    assert ir.text_coverage == 0.0


def test_feature_vector_prompt():
    fv = FeatureVector(text_density=0.5, image_count=3, table_count=1, has_price_pattern=True)
    ctx = fv.to_prompt_context()
    assert "text_density=0.50" in ctx
    assert "images=3" in ctx
    assert "has_prices" in ctx


def test_page_result_to_dict():
    result = PageResult(
        status="AI_COMPLETED", page_type="B",
        skus=[SKUResult(sku_id="s1"), SKUResult(sku_id="s2")],
        extraction_method="two_stage",
    )
    d = result.to_dict()
    assert d["sku_count"] == 2
    assert d["extraction_method"] == "two_stage"


def test_page_chunk():
    chunk = PageChunk(chunk_id=0, pages=[1, 2, 3, 4, 5])
    assert len(chunk.pages) == 5
