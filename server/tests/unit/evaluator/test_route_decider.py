"""RouteDecider 单元测试。"""
from pdf_sku.evaluator.router_logic import RouteDecider


def test_auto_route():
    d = RouteDecider()
    route, reason = d.decide(0.92, {"A": 0.85, "B": 0.45})
    assert route == "AUTO"
    assert reason is None


def test_hybrid_route():
    d = RouteDecider()
    route, reason = d.decide(0.65, {"A": 0.85, "B": 0.45})
    assert route == "HYBRID"
    assert reason is not None
    assert "HYBRID" in reason


def test_human_all_route():
    d = RouteDecider()
    route, reason = d.decide(0.30, {"A": 0.85, "B": 0.45})
    assert route == "HUMAN_ALL"


def test_variance_forced_downgrades_auto():
    d = RouteDecider()
    # Without variance: AUTO
    route1, _ = d.decide(0.92, {"A": 0.85, "B": 0.45}, variance_forced=False)
    assert route1 == "AUTO"
    # With variance: HYBRID
    route2, reason2 = d.decide(0.92, {"A": 0.85, "B": 0.45}, variance_forced=True)
    assert route2 == "HYBRID"
    assert "variance_forced" in reason2


def test_variance_forced_below_B_still_human():
    d = RouteDecider()
    route, _ = d.decide(0.30, {"A": 0.85, "B": 0.45}, variance_forced=True)
    assert route == "HUMAN_ALL"  # Below B → HUMAN_ALL regardless


def test_boundary_A():
    d = RouteDecider()
    route, _ = d.decide(0.85, {"A": 0.85, "B": 0.45})
    assert route == "AUTO"  # >= A


def test_boundary_B():
    d = RouteDecider()
    route, _ = d.decide(0.45, {"A": 0.85, "B": 0.45})
    assert route == "HYBRID"  # >= B
