from pdf_sku.evaluator.router_logic import decide_route
from pdf_sku.common.schemas import ThresholdSet
from pdf_sku.common.enums import RouteDecision

def test_auto_route():
    route, _ = decide_route(0.90, ThresholdSet(A=0.85, B=0.45, PV=0.65))
    assert route == RouteDecision.AUTO

def test_hybrid_route():
    route, _ = decide_route(0.60, ThresholdSet(A=0.85, B=0.45, PV=0.65))
    assert route == RouteDecision.HYBRID

def test_human_all_route():
    route, _ = decide_route(0.30, ThresholdSet(A=0.85, B=0.45, PV=0.65))
    assert route == RouteDecision.HUMAN_ALL
