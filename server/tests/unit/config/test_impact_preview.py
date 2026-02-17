"""ImpactPreview 测试。"""
from pdf_sku.config.impact_preview import (
    ImpactPreviewCalculator, ImpactPreviewResult, PREVIEW_WINDOW_DAYS,
)


def test_preview_result_defaults():
    r = ImpactPreviewResult()
    assert r.current_auto_rate == 0.0
    assert r.sample_count == 0


def test_preview_result_to_dict():
    r = ImpactPreviewResult(
        current_auto_rate=0.70,
        projected_auto_rate=0.80,
        current_human_rate=0.20,
        projected_human_rate=0.15,
        current_reject_rate=0.10,
        projected_reject_rate=0.05,
        sample_count=100,
        confidence_interval=0.05,
    )
    d = r.to_dict()
    assert d["current_auto_rate"] == 0.70
    assert d["projected_auto_rate"] == 0.80
    assert d["delta_auto"] == 0.10
    assert d["delta_human"] == -0.05
    assert d["sample_count"] == 100


def test_simulate_routing():
    calc = ImpactPreviewCalculator()

    class MockJob:
        eval_score = None

    jobs = []
    for score in [0.90, 0.85, 0.80, 0.50, 0.40, 0.30]:
        j = MockJob()
        j.eval_score = score
        jobs.append(j)

    # Current: A=0.85, B=0.45
    dist = calc._simulate_routing(jobs, {"A": 0.85, "B": 0.45})
    assert dist["auto"] == 2
    assert dist["human"] == 2
    assert dist["reject"] == 2

    # Proposed: lower thresholds
    dist2 = calc._simulate_routing(jobs, {"A": 0.80, "B": 0.40})
    assert dist2["auto"] == 3
    assert dist2["reject"] == 1


def test_preview_window():
    assert PREVIEW_WINDOW_DAYS == 30
