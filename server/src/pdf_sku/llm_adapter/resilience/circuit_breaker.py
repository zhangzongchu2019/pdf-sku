"""
熔断器 (3 态状态机)。对齐: LLM Adapter 详设 §6.1

状态: CLOSED → OPEN → HALF_OPEN → CLOSED
触发: 滑动窗口内连续 failure_threshold 次失败 → OPEN
恢复: open_timeout 后 → HALF_OPEN → 探测成功 → CLOSED
"""
from __future__ import annotations
import time
from enum import StrEnum
from collections import deque
from pdf_sku.common.exceptions import LLMCircuitOpenError
import structlog

logger = structlog.get_logger()


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        open_timeout: float = 60.0,
        window_size: int = 20,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._open_timeout = open_timeout
        self._window_size = window_size

        self._state = CircuitState.CLOSED
        self._failures: deque[float] = deque(maxlen=window_size)
        self._half_open_successes = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at > self._open_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_successes = 0
                logger.info("circuit_half_open")
        return self._state

    def check(self) -> None:
        """调用前检查: OPEN 时抛异常。"""
        if self.state == CircuitState.OPEN:
            remaining = self._open_timeout - (time.monotonic() - self._opened_at)
            raise LLMCircuitOpenError(
                f"Circuit breaker OPEN, retry in {remaining:.0f}s")

    def record_success(self) -> None:
        """记录成功。"""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self._success_threshold:
                self._state = CircuitState.CLOSED
                self._failures.clear()
                logger.info("circuit_closed")
        elif self._state == CircuitState.CLOSED:
            # 成功不记入 failures，清除窗口
            pass

    def record_failure(self) -> None:
        """记录失败。"""
        now = time.monotonic()
        self._failures.append(now)

        if self._state == CircuitState.HALF_OPEN:
            self._trip()
            return

        # CLOSED: 检查滑动窗口内失败次数
        recent = [t for t in self._failures if now - t < 60]  # 60s 窗口
        if len(recent) >= self._failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.error("circuit_opened",
                      failures=len(self._failures),
                      threshold=self._failure_threshold)
