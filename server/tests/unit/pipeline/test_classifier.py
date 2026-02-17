"""PageClassifier 测试。"""
import pytest
from pdf_sku.pipeline.ir import FeatureVector
from pdf_sku.pipeline.classifier.page_classifier import PageClassifier


@pytest.fixture
def classifier():
    return PageClassifier(llm_service=None)


def test_classify_blank_page(classifier):
    fv = FeatureVector(text_block_count=0, image_count=0)
    result = classifier._rule_classify(fv, "")
    assert result.page_type == "D"
    assert result.confidence >= 0.9


def test_classify_toc_page(classifier):
    fv = FeatureVector(text_block_count=5, image_count=0)
    result = classifier._rule_classify(fv, "Table of Contents\n1. Introduction")
    assert result.page_type == "D"


def test_classify_table_page(classifier):
    fv = FeatureVector(table_count=2, table_area_ratio=0.5)
    result = classifier._rule_classify(fv, "")
    assert result.page_type == "A"


def test_classify_image_heavy(classifier):
    fv = FeatureVector(image_count=5, text_block_count=2)
    result = classifier._rule_classify(fv, "")
    assert result.page_type == "C"


def test_classify_mixed_with_prices(classifier):
    fv = FeatureVector(text_block_count=10, image_count=2, has_price_pattern=True)
    result = classifier._rule_classify(fv, "Product $29.99")
    assert result.page_type == "B"


def test_classify_unknown(classifier):
    fv = FeatureVector(text_block_count=2, image_count=1)
    result = classifier._rule_classify(fv, "Some text")
    assert result is None
