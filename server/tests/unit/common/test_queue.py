import json

import pytest
from unittest.mock import AsyncMock, call

from pdf_sku.common.queue import (
    DLQ_EVALUATE,
    GROUP_EVAL,
    STREAM_EVALUATE,
    ack,
    consume,
    ensure_stream_group,
    produce,
    reclaim_pending,
)


@pytest.mark.asyncio
async def test_ensure_stream_group_is_idempotent():
    redis = AsyncMock()
    redis.xgroup_create = AsyncMock(side_effect=[Exception("BUSYGROUP Consumer Group name already exists")])

    await ensure_stream_group(redis, STREAM_EVALUATE, GROUP_EVAL)

    redis.xgroup_create.assert_awaited_once_with(STREAM_EVALUATE, GROUP_EVAL, id="0", mkstream=True)


@pytest.mark.asyncio
async def test_produce_and_consume_use_stage_mapping():
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value="1740000000000-0")
    redis.xreadgroup = AsyncMock(return_value=[
        (STREAM_EVALUATE, [("1740000000000-0", {"job_id": "job-1", "attempt": "1"})]),
    ])

    redis_msg_id = await produce(redis, "evaluate", "job-1", payload={"foo": "bar"})
    messages = await consume(redis, "evaluate", "consumer-1", batch_size=5, block_ms=10)

    assert redis_msg_id == "1740000000000-0"
    redis.xadd.assert_awaited_once()
    stream, msg = redis.xadd.await_args.args
    assert stream == STREAM_EVALUATE
    assert msg["job_id"] == "job-1"
    assert msg["stage"] == "evaluate"
    assert json.loads(msg["payload_json"]) == {"foo": "bar"}
    assert messages == [("1740000000000-0", {"job_id": "job-1", "attempt": "1"})]


@pytest.mark.asyncio
async def test_ack_confirms_message():
    redis = AsyncMock()

    await ack(redis, "evaluate", "1740000000000-0")

    redis.xack.assert_awaited_once_with(STREAM_EVALUATE, GROUP_EVAL, "1740000000000-0")


@pytest.mark.asyncio
async def test_reclaim_pending_requeues_retryable_messages():
    redis = AsyncMock()
    redis.xautoclaim = AsyncMock(return_value=(
        "0-0",
        [("1740-0", {"job_id": "job-2", "attempt": "1", "trace_id": "trace-2"})],
        [],
    ))

    reclaimed = await reclaim_pending(redis, "evaluate", "consumer-2", idle_ms=1000, max_retry=3)

    assert reclaimed == [("1740-0", {"job_id": "job-2", "attempt": "2", "trace_id": "trace-2"})]
    redis.xadd.assert_awaited_once_with(
        STREAM_EVALUATE,
        {"job_id": "job-2", "attempt": "2", "trace_id": "trace-2"},
    )
    redis.xack.assert_awaited_once_with(STREAM_EVALUATE, GROUP_EVAL, "1740-0")


@pytest.mark.asyncio
async def test_reclaim_pending_sends_max_retry_to_dlq():
    redis = AsyncMock()
    redis.xautoclaim = AsyncMock(return_value=(
        "0-0",
        [("1741-0", {"job_id": "job-3", "attempt": "3", "trace_id": "trace-3"})],
        [],
    ))

    reclaimed = await reclaim_pending(redis, "evaluate", "consumer-3", idle_ms=1000, max_retry=3)

    assert reclaimed == []
    assert redis.xadd.await_count == 1
    dlq_stream, dlq_msg = redis.xadd.await_args.args
    assert dlq_stream == DLQ_EVALUATE
    assert dlq_msg["error_type"] == "MAX_RETRY_EXCEEDED"
    assert dlq_msg["trace_id"] == "trace-3"
    redis.xack.assert_awaited_once_with(STREAM_EVALUATE, GROUP_EVAL, "1741-0")
