"""Sampler 单元测试。"""
import pytest
from pdf_sku.evaluator.sampler import Sampler


@pytest.fixture
def sampler():
    return Sampler()


def test_full_sample_under_threshold(sampler):
    """≤40 页全量采样。"""
    result = sampler.select_pages(30, blank_pages=[5, 10])
    # 30页排除2个空白 = 28 页
    assert len(result) == 28
    assert 5 not in result
    assert 10 not in result


def test_full_sample_exact_threshold(sampler):
    result = sampler.select_pages(40, blank_pages=[])
    assert len(result) == 40


def test_stratified_over_threshold(sampler):
    """>40 页分层采样。"""
    result = sampler.select_pages(100, blank_pages=[])
    assert len(result) <= 40
    # 首尾页必选
    assert 1 in result
    assert 2 in result
    assert 99 in result or 100 in result


def test_empty_after_blank_removal(sampler):
    """全部空白 → 空列表。"""
    result = sampler.select_pages(3, blank_pages=[1, 2, 3])
    assert result == []


def test_toc_filtering(sampler):
    """目录页被过滤。"""
    features = {
        1: {"image_count": 0, "text_hint": "Table of Contents"},
        2: {"image_count": 3, "text_hint": "Products"},
        3: {"image_count": 5, "text_hint": "Catalog page"},
    }
    result = sampler.select_pages(3, blank_pages=[], page_features=features)
    assert 1 not in result  # TOC filtered
    assert 2 in result
    assert 3 in result


def test_feature_weighted_sample(sampler):
    """特征加权采样: 高复杂度页优先。"""
    features = {}
    for i in range(1, 101):
        if i <= 10:
            features[i] = {"image_count": 8, "ocr_rate": 0.3}  # high
        elif i <= 40:
            features[i] = {"image_count": 3, "ocr_rate": 0.7}  # med
        else:
            features[i] = {"image_count": 1, "ocr_rate": 0.95}  # low
    result = sampler.select_pages(100, blank_pages=[], page_features=features)
    assert len(result) <= 40
    # 高复杂度页占比应高于均匀分布
    high_sampled = [p for p in result if p <= 10]
    assert len(high_sampled) >= 3  # 至少采到 3/10 高复杂度页


def test_single_page(sampler):
    result = sampler.select_pages(1, blank_pages=[])
    assert result == [1]
