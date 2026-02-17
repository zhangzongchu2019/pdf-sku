"""
评估缓存。对齐: Evaluator 详设 §5.1 缓存策略

缓存键: {file_hash}:{config_version}
策略:
1. Redis GET → 命中返回
2. Redis MISS → DB 查询 → 命中则回写 Redis
3. DB MISS → 返回 None (需执行评估)
分布式锁: Redis SET NX + 续约协程
"""
from __future__ import annotations
import asyncio
import contextlib
from datetime import datetime
from typing import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import orjson
import structlog

logger = structlog.get_logger()

CACHE_TTL = 86400 * 7  # 7 天
LOCK_TTL = 300  # 5 分钟
LOCK_RENEW_INTERVAL = 30  # 每 30s 续约


class EvalCache:
    def __init__(self, redis: Redis, db_session_factory) -> None:
        self._redis = redis
        self._db_factory = db_session_factory

    async def get(self, cache_key: str) -> dict | None:
        """查询缓存 (Redis → DB fallback)。"""
        # 1. Redis
        try:
            data = await self._redis.get(f"eval:{cache_key}")
            if data:
                logger.debug("eval_cache_hit", key=cache_key, source="redis")
                return orjson.loads(data)
        except Exception:
            logger.warning("eval_cache_redis_error", key=cache_key)

        # 2. DB fallback
        return await self._get_from_db(cache_key)

    async def _get_from_db(self, cache_key: str) -> dict | None:
        """从 DB evaluations 表查询。"""
        parts = cache_key.split(":", 1)
        if len(parts) != 2:
            return None

        file_hash, config_version = parts
        from pdf_sku.common.models import Evaluation

        async with self._db_factory() as db:
            result = await db.execute(
                select(Evaluation).where(
                    Evaluation.file_hash == file_hash,
                    Evaluation.config_version == config_version,
                ).limit(1)
            )
            eval_row = result.scalar_one_or_none()
            if not eval_row:
                return None

            data = {
                "file_hash": eval_row.file_hash,
                "config_version": eval_row.config_version,
                "doc_confidence": eval_row.doc_confidence,
                "route": eval_row.route,
                "route_reason": eval_row.route_reason,
                "degrade_reason": eval_row.degrade_reason,
                "dimension_scores": eval_row.dimension_scores,
                "prescan": eval_row.prescan,
                "sampling": eval_row.sampling,
                "model_used": eval_row.model_used,
                "page_evaluations": eval_row.page_evaluations,
            }

            # 回写 Redis
            try:
                await self._redis.set(
                    f"eval:{cache_key}",
                    orjson.dumps(data),
                    ex=CACHE_TTL,
                )
            except Exception:
                pass

            logger.debug("eval_cache_hit", key=cache_key, source="db")
            return data

    async def put(self, cache_key: str, data: dict) -> None:
        """写入缓存 (Redis)。"""
        try:
            await self._redis.set(
                f"eval:{cache_key}",
                orjson.dumps(data),
                ex=CACHE_TTL,
            )
        except Exception:
            logger.warning("eval_cache_put_error", key=cache_key)

    @contextlib.asynccontextmanager
    async def lock(self, cache_key: str, timeout: int = LOCK_TTL) -> AsyncGenerator[bool, None]:
        """
        分布式锁 (Redis SET NX + 续约协程)。
        防止相同 file_hash 并发评估穿透。
        """
        lock_key = f"eval_lock:{cache_key}"
        acquired = await self._redis.set(lock_key, "1", nx=True, ex=timeout)
        if not acquired:
            # 等待锁释放 (最多等 timeout 秒)
            for _ in range(timeout // 2):
                await asyncio.sleep(2)
                # 再次尝试从缓存获取 (另一个 worker 可能已完成)
                cached = await self.get(cache_key)
                if cached:
                    yield True
                    return
                if not await self._redis.exists(lock_key):
                    break
            # 锁超时或其他 worker 完成，尝试获取
            acquired = await self._redis.set(lock_key, "1", nx=True, ex=timeout)

        # 启动续约协程
        renew_task = asyncio.create_task(self._renew_lock(lock_key, timeout))

        try:
            yield bool(acquired)
        finally:
            renew_task.cancel()
            try:
                await renew_task
            except asyncio.CancelledError:
                pass
            await self._redis.delete(lock_key)

    async def _renew_lock(self, lock_key: str, timeout: int) -> None:
        """每 30s 续约锁 TTL。"""
        while True:
            await asyncio.sleep(LOCK_RENEW_INTERVAL)
            try:
                await self._redis.expire(lock_key, timeout)
            except Exception:
                break
