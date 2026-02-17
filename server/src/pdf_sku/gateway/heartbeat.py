"""
Worker 心跳。对齐: Gateway 详设 §4.2

每 30s 向 Redis SETEX worker:heartbeat:{id} 90 {timestamp}
同时更新 DB worker_heartbeats 表。
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import WorkerHeartbeat
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

HEARTBEAT_INTERVAL = 30  # 秒
HEARTBEAT_TTL = 90  # 秒


async def heartbeat_loop(redis, session_factory) -> None:
    """后台心跳循环。在 lifespan 中启动。"""
    worker_id = settings.worker_id
    import socket
    hostname = socket.gethostname()

    logger.info("heartbeat_started", worker_id=worker_id, hostname=hostname)

    while True:
        try:
            # Redis 心跳
            await redis.setex(
                f"worker:heartbeat:{worker_id}",
                HEARTBEAT_TTL,
                datetime.now(timezone.utc).isoformat(),
            )

            # DB 心跳 (upsert)
            async with session_factory() as db:
                async with db.begin():
                    result = await db.execute(
                        select(WorkerHeartbeat).where(
                            WorkerHeartbeat.worker_id == worker_id
                        )
                    )
                    hb = result.scalar_one_or_none()
                    if hb:
                        hb.last_heartbeat = datetime.now(timezone.utc)
                        hb.hostname = hostname
                        hb.status = "ALIVE"
                    else:
                        db.add(WorkerHeartbeat(
                            worker_id=worker_id,
                            hostname=hostname,
                            status="ALIVE",
                        ))

        except Exception:
            logger.exception("heartbeat_error")

        await asyncio.sleep(HEARTBEAT_INTERVAL)
