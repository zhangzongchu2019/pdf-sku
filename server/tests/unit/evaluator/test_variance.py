"""VarianceDetector 单元测试。"""
from pdf_sku.evaluator.variance_detector import VarianceDetector


def test_low_variance():
    d = VarianceDetector()
    scores = [0.8, 0.82, 0.79, 0.81, 0.80]
    variance, forced = d.check(scores)
    assert not forced
    assert variance < 0.01


def test_high_variance():
    d = VarianceDetector()
    scores = [0.95, 0.1, 0.92, 0.05, 0.88]
    variance, forced = d.check(scores)
    assert forced  # variance > 0.08


def test_too_few_scores():
    d = VarianceDetector()
    variance, forced = d.check([0.5, 0.9])  # <3
    assert not forced
    assert variance == 0.0


def test_custom_threshold():
    d = VarianceDetector()
    scores = [0.7, 0.75, 0.65, 0.72, 0.68]
    _, forced_strict = d.check(scores, variance_threshold=0.001)
    assert forced_strict  # Very strict threshold
