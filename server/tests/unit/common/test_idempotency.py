import pytest
from unittest.mock import AsyncMock, call

from pdf_sku.common.idempotency import (
    is_stage_done,
    mark_stage_done,
    release_enqueue_lock,
    reset_stage_state,
    try_enqueue_lock,
)


@pytest.mark.asyncio
async def test_try_enqueue_lock_acquires_once():
    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=[True, None])

    assert await try_enqueue_lock(redis, "job-1", "evaluate") is True
    assert await try_enqueue_lock(redis, "job-1", "evaluate") is False

    redis.set.assert_has_awaits([
        call("job:job-1:stage:evaluate:enqueued", "1", nx=True, ex=259200),
        call("job:job-1:stage:evaluate:enqueued", "1", nx=True, ex=259200),
    ])


@pytest.mark.asyncio
async def test_try_enqueue_lock_force_replaces_previous_lock():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)

    assert await try_enqueue_lock(redis, "job-2", "pipeline", force=True) is True

    redis.delete.assert_awaited_once_with("job:job-2:stage:pipeline:enqueued")
    redis.set.assert_awaited_once_with(
        "job:job-2:stage:pipeline:enqueued",
        "1",
        nx=True,
        ex=259200,
    )


@pytest.mark.asyncio
async def test_stage_done_helpers_manage_done_key():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=1)

    await mark_stage_done(redis, "job-3", "pipeline")
    assert await is_stage_done(redis, "job-3", "pipeline") is True
    await release_enqueue_lock(redis, "job-3", "pipeline")
    await reset_stage_state(redis, "job-3", "pipeline")

    redis.set.assert_awaited_once_with("job:job-3:stage:pipeline:done", "1", ex=604800)
    redis.exists.assert_awaited_once_with("job:job-3:stage:pipeline:done")
    redis.delete.assert_has_awaits([
        call("job:job-3:stage:pipeline:enqueued"),
        call("job:job-3:stage:pipeline:enqueued", "job:job-3:stage:pipeline:done"),
    ])
