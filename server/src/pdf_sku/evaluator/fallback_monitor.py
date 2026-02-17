"""
Job 级连续 Fallback 熔断。对齐: Evaluator 详设 §5.5

连续 N 页 Fallback → should_suspend() = True → Pipeline 挂起 Job。
"""
from __future__ import annotations
import structlog

logger = structlog.get_logger()

CONSECUTIVE_THRESHOLD = 3


class FallbackMonitor:
    def __init__(self, threshold: int = CONSECUTIVE_THRESHOLD) -> None:
        self._threshold = threshold
        self._counters: dict[str, int] = {}  # job_id → consecutive count

    def on_page_fallback(self, job_id: str, page_no: int) -> None:
        self._counters[job_id] = self._counters.get(job_id, 0) + 1
        if self._counters[job_id] >= self._threshold:
            logger.warning("fallback_threshold",
                           job_id=job_id, consecutive=self._counters[job_id],
                           page_no=page_no)

    def on_page_success(self, job_id: str) -> None:
        self._counters[job_id] = 0

    def should_suspend(self, job_id: str) -> bool:
        return self._counters.get(job_id, 0) >= self._threshold

    def reset(self, job_id: str) -> None:
        self._counters.pop(job_id, None)
