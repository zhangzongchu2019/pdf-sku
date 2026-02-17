"""
全局限流器 (滑动窗口)。对齐: LLM Adapter 详设 §6.2

支持 QPM (queries per minute) 和 TPM (tokens per minute)。
Redis ZSET 实现滑动窗口。
"""
from __future__ import annotations
import time
from redis.asyncio import Redis
from pdf_sku.common.exceptions import LLMRateLimitedError
import structlog

logger = structlog.get_logger()


class RateLimiter:
    def __init__(
        self,
        redis: Redis,
        qpm: int = 60,
        tpm: int = 100_000,
    ) -> None:
        self._redis = redis
        self._qpm = qpm
        self._tpm = tpm

    async def check_and_acquire(self, estimated_tokens: int = 0) -> None:
        """
        检查限流 + 获取令牌。超限时抛异常。
        """
        now = time.time()
        window_start = now - 60  # 1 分钟窗口

        # QPM 检查
        qpm_key = "llm:rate:qpm"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(qpm_key, 0, window_start)
        pipe.zcard(qpm_key)
        pipe.zadd(qpm_key, {f"{now}:{id(self)}": now})
        pipe.expire(qpm_key, 120)
        results = await pipe.execute()
        current_qpm = results[1]

        if current_qpm >= self._qpm:
            logger.warning("rate_limited_qpm", current=current_qpm, limit=self._qpm)
            raise LLMRateLimitedError(f"QPM limit ({self._qpm}) exceeded")

        # TPM 检查
        if estimated_tokens > 0:
            tpm_key = "llm:rate:tpm"
            current_tpm = float(await self._redis.get(tpm_key) or "0")
            if current_tpm + estimated_tokens > self._tpm:
                logger.warning("rate_limited_tpm",
                               current=current_tpm, estimated=estimated_tokens, limit=self._tpm)
                raise LLMRateLimitedError(f"TPM limit ({self._tpm}) exceeded")

    async def record_tokens(self, tokens: int) -> None:
        """记录本次消耗的 token 数。"""
        tpm_key = "llm:rate:tpm"
        pipe = self._redis.pipeline()
        pipe.incrbyfloat(tpm_key, tokens)
        pipe.expire(tpm_key, 120)
        await pipe.execute()
