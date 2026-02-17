"""Redis 连接管理。"""
import redis.asyncio as aioredis
from pdf_sku.settings import settings

redis_client: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        if settings.redis_sentinel_hosts:
            sentinel = aioredis.Sentinel(
                [(h.split(":")[0], int(h.split(":")[1])) for h in settings.redis_sentinel_hosts.split(",")],
            )
            redis_client = sentinel.master_for(settings.redis_sentinel_master)
        else:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return redis_client

async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
