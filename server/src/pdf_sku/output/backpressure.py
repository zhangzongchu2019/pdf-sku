"""
背压监控。对齐: Output 详设 §4.1.1

- 统计最近 N 次导入的失败比例
- 比例 >20% → is_throttled=True → Pipeline 降速
"""
from __future__ import annotations
from collections import deque
import structlog

logger = structlog.get_logger()

WINDOW_SIZE = 50
FAILURE_THRESHOLD = 0.20
THROTTLE_DELAY = 5.0


class BackpressureMonitor:
    def __init__(self):
        self._windows: dict[str, deque] = {}

    def on_success(self, job_id: str) -> None:
        self._record(job_id, True)

    def on_failure(self, job_id: str) -> None:
        self._record(job_id, False)

    def _record(self, job_id: str, success: bool) -> None:
        if job_id not in self._windows:
            self._windows[job_id] = deque(maxlen=WINDOW_SIZE)
        self._windows[job_id].append(success)

    def is_throttled(self, job_id: str) -> bool:
        window = self._windows.get(job_id)
        if not window or len(window) < 10:
            return False
        failure_rate = 1.0 - (sum(window) / len(window))
        return failure_rate > FAILURE_THRESHOLD

    @property
    def delay_seconds(self) -> float:
        return THROTTLE_DELAY

    def get_failure_rate(self, job_id: str) -> float:
        window = self._windows.get(job_id)
        if not window:
            return 0.0
        return 1.0 - (sum(window) / len(window))

    def clear(self, job_id: str) -> None:
        self._windows.pop(job_id, None)
