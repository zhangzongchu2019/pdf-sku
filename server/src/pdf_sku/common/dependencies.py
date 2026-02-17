"""FastAPI 依赖注入。lifespan 中 override 这些 sentinel 函数。"""
from __future__ import annotations
from typing import Annotated, AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """占位 — 由 main.py lifespan 通过 dependency_overrides 替换。"""
    raise RuntimeError("Database session not initialized. Check lifespan setup.")
    yield  # type: ignore[misc]


async def get_redis() -> Redis:
    """占位 — 由 main.py lifespan 通过 dependency_overrides 替换。"""
    raise RuntimeError("Redis not initialized. Check lifespan setup.")


DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
