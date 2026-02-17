"""
Token 预算守卫 (三阶段)。对齐: LLM Adapter 详设 §6.3

阶段:
- NORMAL: budget > 20% → 正常
- WARNING: 5% < budget ≤ 20% → 降级: 仅 eval 类调用允许
- EXHAUSTED: budget ≤ 5% → 全部拒绝
"""
from __future__ import annotations
from enum import StrEnum
from redis.asyncio import Redis
from pdf_sku.common.exceptions import LLMBudgetExhaustedError
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

BUDGET_KEY = "llm:daily_budget"
USAGE_KEY_PREFIX = "llm:daily_usage"


class BudgetPhase(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    EXHAUSTED = "EXHAUSTED"


class BudgetGuard:
    def __init__(self, redis: Redis, daily_budget_usd: float | None = None) -> None:
        self._redis = redis
        self._daily_budget = daily_budget_usd or settings.llm_daily_budget_usd

    async def check(self, operation: str, estimated_cost: float = 0.0) -> BudgetPhase:
        """
        检查预算状态。

        Args:
            operation: 操作类型 (eval/classify/extract 等)
            estimated_cost: 预估本次调用成本 (USD)
        Returns:
            BudgetPhase
        Raises:
            LLMBudgetExhaustedError: 预算耗尽
        """
        import datetime
        today = datetime.date.today().isoformat()
        key = f"{USAGE_KEY_PREFIX}:{today}"

        used = float(await self._redis.get(key) or "0")
        remaining_pct = max(0, (self._daily_budget - used) / self._daily_budget)

        if remaining_pct <= 0.05:
            logger.error("budget_exhausted",
                          used=round(used, 4), budget=self._daily_budget)
            raise LLMBudgetExhaustedError(
                f"Daily LLM budget exhausted ({remaining_pct*100:.1f}% remaining)")

        if remaining_pct <= 0.20:
            # WARNING: 仅允许 eval 类操作
            if operation not in ("evaluate_document", "evaluate_page"):
                raise LLMBudgetExhaustedError(
                    f"Budget warning ({remaining_pct*100:.1f}%): only eval ops allowed")
            logger.warning("budget_warning", remaining_pct=round(remaining_pct, 3))
            return BudgetPhase.WARNING

        return BudgetPhase.NORMAL

    async def record_usage(self, cost_usd: float) -> float:
        """记录消耗。返回当日累计。"""
        import datetime
        today = datetime.date.today().isoformat()
        key = f"{USAGE_KEY_PREFIX}:{today}"

        new_total = await self._redis.incrbyfloat(key, cost_usd)
        # 设置过期 (次日凌晨后自动清理)
        await self._redis.expire(key, 86400 * 2)
        return float(new_total)

    async def get_status(self) -> dict:
        """获取当日预算状态。"""
        import datetime
        today = datetime.date.today().isoformat()
        key = f"{USAGE_KEY_PREFIX}:{today}"
        used = float(await self._redis.get(key) or "0")
        return {
            "daily_budget_usd": self._daily_budget,
            "used_usd": round(used, 4),
            "remaining_usd": round(max(0, self._daily_budget - used), 4),
            "remaining_pct": round(max(0, (self._daily_budget - used) / self._daily_budget), 4),
        }
