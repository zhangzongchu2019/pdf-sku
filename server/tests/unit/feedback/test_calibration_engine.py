"""CalibrationEngine 测试。"""
from pdf_sku.feedback.calibration_engine import (
    CalibrationEngine, MAX_THRESHOLD_DRIFT, MIN_ANNOTATORS,
    MIN_SAMPLES_DEFAULT, KL_DIVERGENCE_THRESHOLD, APPROVAL_SLA_HOURS,
)


def test_constants():
    assert MAX_THRESHOLD_DRIFT == 0.10
    assert MIN_ANNOTATORS == 3
    assert MIN_SAMPLES_DEFAULT == 50
    assert KL_DIVERGENCE_THRESHOLD == 0.5
    assert APPROVAL_SLA_HOURS == 48


def test_confusion_matrix():
    engine = CalibrationEngine()
    # Mock annotations
    class MockAnn:
        def __init__(self, ai, human):
            self.payload = {"ai_page_type": ai, "corrected_page_type": human}
    corrections = [
        MockAnn("A", "A"), MockAnn("A", "B"), MockAnn("B", "B"),
        MockAnn("A", "A"), MockAnn("C", "C"),
    ]
    matrix = engine._build_confusion_matrix(corrections)
    assert matrix["A->A"] == 2
    assert matrix["A->B"] == 1
    assert matrix["B->B"] == 1
    assert matrix["C->C"] == 1


def test_calc_accuracy_perfect():
    engine = CalibrationEngine()
    matrix = {"A->A": 5, "B->B": 3, "C->C": 2}
    assert engine._calc_accuracy(matrix) == 1.0


def test_calc_accuracy_partial():
    engine = CalibrationEngine()
    matrix = {"A->A": 3, "A->B": 2, "B->B": 5}
    accuracy = engine._calc_accuracy(matrix)
    assert 0.75 < accuracy < 0.85  # 8/10 = 0.8


def test_calc_accuracy_empty():
    engine = CalibrationEngine()
    assert engine._calc_accuracy({}) == 1.0


def test_confidence_drift():
    engine = CalibrationEngine()
    class MockAnn:
        def __init__(self, conf, correct):
            self.payload = {"ai_confidence": conf, "was_correct": correct}
    # All correct, high confidence → small negative drift
    corrections = [MockAnn(0.95, True)] * 10
    drift = engine._analyze_confidence_drift(corrections)
    assert drift < 0  # slight under-confidence relative to 1.0

    # All wrong, high confidence → large positive drift
    wrong = [MockAnn(0.9, False)] * 10
    drift2 = engine._analyze_confidence_drift(wrong)
    assert drift2 > 0.5  # over-confident


def test_kl_divergence_low():
    engine = CalibrationEngine()
    class MockAnn:
        def __init__(self, conf, correct):
            self.payload = {"ai_confidence": conf, "was_correct": correct}
    # Mixed correct/wrong with varied confidence → moderate KL
    corrections = ([MockAnn(0.9, True)] * 10 +
                   [MockAnn(0.5, False)] * 5 +
                   [MockAnn(0.3, True)] * 5)
    kl = engine._compute_kl_divergence(corrections)
    # Just verify it returns a non-negative number
    assert kl >= 0
