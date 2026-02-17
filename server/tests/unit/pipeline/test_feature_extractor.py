"""FeatureExtractor 测试。"""
from pdf_sku.pipeline.ir import ParsedPageIR, TextBlock, ImageInfo, PageMetadata
from pdf_sku.pipeline.parser.feature_extractor import FeatureExtractor


def test_basic_features():
    raw = ParsedPageIR(
        page_no=1,
        text_blocks=[TextBlock(content="Product A $29.99", bbox=(10, 10, 200, 30))],
        images=[ImageInfo(image_id="i1"), ImageInfo(image_id="i2")],
        raw_text="Product A $29.99 Model XZ-500",
        metadata=PageMetadata(page_width=612, page_height=792),
    )
    fe = FeatureExtractor()
    fv = fe.extract(raw)
    assert fv.text_block_count == 1
    assert fv.image_count == 2
    assert fv.has_price_pattern is True
    assert fv.has_model_pattern is True


def test_empty_page():
    raw = ParsedPageIR(page_no=1, metadata=PageMetadata(page_width=100, page_height=100))
    fe = FeatureExtractor()
    fv = fe.extract(raw)
    assert fv.text_density == 0.0
    assert fv.image_count == 0
