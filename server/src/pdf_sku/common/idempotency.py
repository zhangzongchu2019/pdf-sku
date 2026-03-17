"""
投递与消费幂等键管理。

对齐: fix.md §9.3 — §9.4 幂等设计

幂等 key 格式:
  enqueue: job:{job_id}:stage:{stage}:enqueued
  done:    job:{job_id}:stage:{stage}:done

使用 Redis SET NX + TTL 保证：
- 同一阶段正常路径只投递一次
- 重试必须走显式 retry 分支（调用方传 force=True）
- 消费侧开始执行前检查阶段是否已完成
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger()

_ENQUEUE_TTL = 86400 * 3   # 3 天 — 涵盖 job 最大生命周期
_DONE_TTL = 86400 * 7      # 7 天 — 历史追踪窗口


def _enqueue_key(job_id: str, stage: str) -> str:
    return f"job:{job_id}:stage:{stage}:enqueued"


def _done_key(job_id: str, stage: str) -> str:
    return f"job:{job_id}:stage:{stage}:done"


async def try_enqueue_lock(
    redis,
    job_id: str,
    stage: str,
    *,
    force: bool = False,
) -> bool:
    """
    尝试获取投递锁。

    - force=False (默认): 同一阶段只允许投递一次，已存在则返回 False。
    - force=True: 允许重复投递（显式重试路径），先删旧 key 再重新锁。

    返回 True 表示已获得锁，可以安全投递；False 表示重复投递，跳过。
    """
    key = _enqueue_key(job_id, stage)
    if force:
        await redis.delete(key)
    result = await redis.set(key, "1", nx=True, ex=_ENQUEUE_TTL)
    if result:
        logger.debug("idempotency_enqueue_locked", job_id=job_id, stage=stage)
        return True
    logger.info("idempotency_enqueue_skip", job_id=job_id, stage=stage,
                reason="already_enqueued")
    return False


async def mark_stage_done(redis, job_id: str, stage: str) -> None:
    """标记某阶段已成功完成（写 done key）。"""
    key = _done_key(job_id, stage)
    await redis.set(key, "1", ex=_DONE_TTL)
    logger.debug("idempotency_stage_done", job_id=job_id, stage=stage)


async def is_stage_done(redis, job_id: str, stage: str) -> bool:
    """检查某阶段是否已成功完成。"""
    key = _done_key(job_id, stage)
    result = await redis.exists(key)
    return bool(result)


async def release_enqueue_lock(redis, job_id: str, stage: str) -> None:
    """手动释放投递锁（用于回滚场景）。"""
    key = _enqueue_key(job_id, stage)
    await redis.delete(key)
    logger.debug("idempotency_enqueue_released", job_id=job_id, stage=stage)


async def reset_stage_state(redis, job_id: str, stage: str) -> None:
    """清理阶段的 enqueue/done 状态，用于显式重跑。"""
    await redis.delete(_enqueue_key(job_id, stage), _done_key(job_id, stage))
    logger.info("idempotency_stage_reset", job_id=job_id, stage=stage)
