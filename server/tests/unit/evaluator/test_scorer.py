"""Scorer 单元测试。"""
import pytest
from pdf_sku.evaluator.scorer import Scorer, PageScore, DEFAULT_WEIGHTS


@pytest.fixture
def scorer():
    return Scorer()


def test_aggregate_single_page(scorer):
    scores = [PageScore(page_no=1, dimensions={
        "text_clarity": 0.8, "image_quality": 0.7,
        "layout_structure": 0.9, "table_regularity": 0.6,
        "sku_density": 0.85,
    })]
    result = scorer.aggregate(scores)
    assert result["text_clarity"] == 0.8
    assert result["sku_density"] == 0.85


def test_aggregate_multi_page(scorer):
    scores = [
        PageScore(page_no=1, dimensions={"text_clarity": 0.8, "image_quality": 0.6}),
        PageScore(page_no=2, dimensions={"text_clarity": 0.6, "image_quality": 0.8}),
    ]
    result = scorer.aggregate(scores)
    assert result["text_clarity"] == pytest.approx(0.7, abs=0.01)
    assert result["image_quality"] == pytest.approx(0.7, abs=0.01)


def test_aggregate_empty(scorer):
    result = scorer.aggregate([])
    assert all(v == 0.0 for v in result.values())


def test_c_doc_perfect_scores(scorer):
    dims = {d: 1.0 for d in DEFAULT_WEIGHTS}
    c_doc = scorer.compute_c_doc(dims)
    assert c_doc == pytest.approx(1.0, abs=0.01)


def test_c_doc_with_penalty(scorer):
    dims = {d: 0.8 for d in DEFAULT_WEIGHTS}
    c_doc_no_penalty = scorer.compute_c_doc(dims, prescan_penalty=0.0)
    c_doc_with_penalty = scorer.compute_c_doc(dims, prescan_penalty=0.15)
    assert c_doc_with_penalty < c_doc_no_penalty
    assert c_doc_with_penalty == pytest.approx(c_doc_no_penalty - 0.15, abs=0.01)


def test_c_doc_clamped(scorer):
    dims = {d: 0.1 for d in DEFAULT_WEIGHTS}
    c_doc = scorer.compute_c_doc(dims, prescan_penalty=0.5)
    assert c_doc >= 0.0  # Clamped to minimum


def test_c_doc_custom_weights(scorer):
    dims = {"text_clarity": 1.0, "image_quality": 0.0,
            "layout_structure": 0.0, "table_regularity": 0.0, "sku_density": 0.0}
    weights = {"text_clarity": 1.0, "image_quality": 0.0,
               "layout_structure": 0.0, "table_regularity": 0.0, "sku_density": 0.0}
    c_doc = scorer.compute_c_doc(dims, weights)
    assert c_doc == pytest.approx(1.0, abs=0.01)
