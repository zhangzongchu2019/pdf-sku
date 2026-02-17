"""GoldenSetEvaluator 测试。"""
from pdf_sku.feedback.golden_set_eval import GoldenSetEvaluator


def test_sku_metrics_perfect():
    ev = GoldenSetEvaluator()
    predictions = [{"page": 1, "skus": [{"model_number": "A1"}, {"model_number": "A2"}]}]
    ground_truth = [{"page": 1, "skus": [{"model_number": "A1"}, {"model_number": "A2"}]}]
    m = ev._compute_sku_metrics(predictions, ground_truth)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0
    assert m["tp"] == 2
    assert m["fp"] == 0


def test_sku_metrics_partial():
    ev = GoldenSetEvaluator()
    predictions = [{"page": 1, "skus": [{"model_number": "A1"}, {"model_number": "A3"}]}]
    ground_truth = [{"page": 1, "skus": [{"model_number": "A1"}, {"model_number": "A2"}]}]
    m = ev._compute_sku_metrics(predictions, ground_truth)
    assert m["tp"] == 1
    assert m["fp"] == 1
    assert m["fn"] == 1
    assert m["precision"] == 0.5
    assert m["recall"] == 0.5


def test_sku_metrics_empty():
    ev = GoldenSetEvaluator()
    m = ev._compute_sku_metrics([], [])
    assert m["f1"] == 0.0


def test_binding_accuracy():
    ev = GoldenSetEvaluator()
    preds = [{"page": 1, "bindings": [
        {"sku_id": "s1", "image_id": "i1"},
        {"sku_id": "s2", "image_id": "i2"},
    ]}]
    gt = [{"page": 1, "bindings": [
        {"sku_id": "s1", "image_id": "i1"},
        {"sku_id": "s2", "image_id": "i3"},
    ]}]
    acc = ev._compute_binding_accuracy(preds, gt)
    assert acc == 0.5


def test_human_rate():
    ev = GoldenSetEvaluator()
    preds = [
        {"page": 1, "needs_review": True},
        {"page": 2, "needs_review": False},
        {"page": 3},
    ]
    rate = ev._compute_human_rate(preds)
    assert abs(rate - 0.3333) < 0.01
