"""
路由决策。对齐: Evaluator 详设 §5.2

路由矩阵:
┌─────────────────────────────┬──────────┐
│ 条件                         │ 路由      │
├─────────────────────────────┼──────────┤
│ c_doc ≥ A(0.85)             │ AUTO     │
│ B(0.45) ≤ c_doc < A         │ HYBRID   │
│ c_doc < B(0.45)             │ HUMAN_ALL│
│ variance_forced = true      │ HYBRID ↓ │
└─────────────────────────────┴──────────┘
不变式 INV-01: B < PV < A
"""
from __future__ import annotations
from pdf_sku.common.enums import RouteDecision
from pdf_sku.common.schemas import ThresholdSet
import structlog

logger = structlog.get_logger()


class RouteDecider:
    def decide(
        self,
        c_doc: float,
        thresholds: ThresholdSet | dict,
        variance_forced: bool = False,
    ) -> tuple[str, str | None]:
        """
        根据 C_doc + 阈值 + 方差强制标志 → 路由决策。

        Returns:
            (route, reason): route ∈ {AUTO, HYBRID, HUMAN_ALL}
        """
        if isinstance(thresholds, dict):
            A = thresholds.get("A", 0.85)
            B = thresholds.get("B", 0.45)
        else:
            A = thresholds.A
            B = thresholds.B

        # 方差强制: 本应 AUTO 的降为 HYBRID
        if variance_forced and c_doc >= B:
            route = "HYBRID"
            reason = self._build_reason(c_doc, A, B, route, extra="variance_forced")
            logger.info("route_decided", route=route, c_doc=c_doc, reason="variance_forced")
            return route, reason

        if c_doc >= A:
            logger.info("route_decided", route="AUTO", c_doc=c_doc)
            return "AUTO", None
        elif c_doc >= B:
            reason = self._build_reason(c_doc, A, B, "HYBRID")
            logger.info("route_decided", route="HYBRID", c_doc=c_doc)
            return "HYBRID", reason
        else:
            reason = self._build_reason(c_doc, A, B, "HUMAN_ALL")
            logger.info("route_decided", route="HUMAN_ALL", c_doc=c_doc)
            return "HUMAN_ALL", reason

    @staticmethod
    def _build_reason(c_doc: float, A: float, B: float, route: str, extra: str | None = None) -> str:
        parts = [f"C_doc={c_doc:.3f}", f"A={A}", f"B={B}", f"→ {route}"]
        if extra:
            parts.append(f"({extra})")
        return ", ".join(parts)


# 向后兼容: scaffold 测试使用的函数式接口
def decide_route(doc_confidence: float, thresholds: ThresholdSet) -> tuple[RouteDecision, str]:
    """向后兼容的函数式接口。"""
    decider = RouteDecider()
    route_str, reason = decider.decide(doc_confidence, thresholds)
    route_enum = RouteDecision(route_str)
    return route_enum, reason or f"C_doc({doc_confidence:.3f}) >= A({thresholds.A})"
