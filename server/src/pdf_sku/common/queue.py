"""
Redis Streams 任务队列工具。

对齐: fix.md §7 — Redis 队列设计

Stream 命名: pdfsku:queue:{stage}
Consumer Group 命名: {stage}-workers
DLQ 命名: pdfsku:dlq:{stage}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import structlog

logger = structlog.get_logger()

# Stream / DLQ 名称
STREAM_EVALUATE = "pdfsku:queue:evaluate"
STREAM_PIPELINE = "pdfsku:queue:pipeline"
STREAM_OUTPUT = "pdfsku:queue:output"
STREAM_REPROCESS = "pdfsku:queue:reprocess"

DLQ_EVALUATE = "pdfsku:dlq:evaluate"
DLQ_PIPELINE = "pdfsku:dlq:pipeline"
DLQ_OUTPUT = "pdfsku:dlq:output"

GROUP_EVAL = "eval-workers"
GROUP_PIPELINE = "pipeline-workers"
GROUP_OUTPUT = "output-workers"
GROUP_REPROCESS = "reprocess-workers"

STAGE_STREAMS: dict[str, str] = {
    "evaluate": STREAM_EVALUATE,
    "pipeline": STREAM_PIPELINE,
    "output": STREAM_OUTPUT,
    "reprocess": STREAM_REPROCESS,
}

STAGE_GROUPS: dict[str, str] = {
    "evaluate": GROUP_EVAL,
    "pipeline": GROUP_PIPELINE,
    "output": GROUP_OUTPUT,
    "reprocess": GROUP_REPROCESS,
}

STAGE_DLQS: dict[str, str] = {
    "evaluate": DLQ_EVALUATE,
    "pipeline": DLQ_PIPELINE,
    "output": DLQ_OUTPUT,
}


async def ensure_stream_group(redis, stream: str, group: str) -> None:
    """确保 Stream 和 Consumer Group 存在（幂等）。"""
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info("stream_group_created", stream=stream, group=group)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass  # 已存在，忽略
        else:
            logger.warning("stream_group_ensure_error", stream=stream, error=str(e))


async def produce(
    redis,
    stage: str,
    job_id: str,
    attempt: int = 1,
    trigger: str = "job_created",
    trace_id: str | None = None,
    payload: dict | None = None,
) -> str:
    """
    向指定阶段的 Stream 投递消息，返回 Redis stream message id。

    消息结构遵循 fix.md §7.3。
    """
    stream = STAGE_STREAMS[stage]
    message_id = str(uuid.uuid4())
    msg = {
        "message_id": message_id,
        "job_id": job_id,
        "stage": stage,
        "attempt": str(attempt),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "trace_id": trace_id or str(uuid.uuid4()),
        "payload_json": json.dumps(payload or {}),
    }
    redis_msg_id = await redis.xadd(stream, msg)
    logger.info("queue_produced", stream=stream, job_id=job_id,
                stage=stage, attempt=attempt, redis_msg_id=redis_msg_id)
    return redis_msg_id


async def consume(
    redis,
    stage: str,
    consumer_name: str,
    batch_size: int = 10,
    block_ms: int = 5000,
) -> list[tuple[str, dict]]:
    """
    从指定阶段消费消息，返回 [(redis_msg_id, fields), ...]。

    阻塞等待最多 block_ms 毫秒。
    """
    stream = STAGE_STREAMS[stage]
    group = STAGE_GROUPS[stage]
    results = await redis.xreadgroup(
        group,
        consumer_name,
        {stream: ">"},
        count=batch_size,
        block=block_ms,
    )
    if not results:
        return []
    # results: [[stream_name, [(msg_id, fields), ...]]]
    messages = []
    for _stream_name, entries in results:
        for msg_id, fields in entries:
            messages.append((msg_id, fields))
    return messages


async def ack(redis, stage: str, msg_id: str) -> None:
    """确认消息已处理。"""
    stream = STAGE_STREAMS[stage]
    group = STAGE_GROUPS[stage]
    await redis.xack(stream, group, msg_id)
    logger.debug("queue_acked", stream=stream, msg_id=msg_id)


async def send_to_dlq(
    redis,
    stage: str,
    original_fields: dict,
    error_type: str,
    error_message: str,
    trace_id: str = "",
) -> None:
    """将消息送入死信队列。"""
    dlq = STAGE_DLQS.get(stage, f"pdfsku:dlq:{stage}")
    dlq_msg = {
        "original_message": json.dumps(original_fields),
        "error_type": error_type,
        "error_message": error_message,
        "attempt": original_fields.get("attempt", "?"),
        "failure_at": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id or original_fields.get("trace_id", ""),
    }
    await redis.xadd(dlq, dlq_msg)
    logger.warning("queue_dlq_sent", dlq=dlq,
                   job_id=original_fields.get("job_id", ""),
                   error_type=error_type)


async def reclaim_pending(
    redis,
    stage: str,
    consumer_name: str,
    idle_ms: int = 60000,
    max_retry: int = 3,
) -> list[tuple[str, dict]]:
    """
    扫描 pending 超时消息，执行 XAUTOCLAIM，增加 attempt，
    超过 max_retry 则送 DLQ 并 ack。

    返回重领的消息列表 [(msg_id, fields), ...]。
    """
    stream = STAGE_STREAMS[stage]
    group = STAGE_GROUPS[stage]

    reclaimed: list[tuple[str, dict]] = []
    try:
        # XAUTOCLAIM: 将超过 idle_ms 的 pending 消息转移到 consumer_name
        result = await redis.xautoclaim(
            stream, group, consumer_name,
            min_idle_time=idle_ms,
            start_id="0-0",
            count=100,
        )
        # result: (next_start_id, [(msg_id, fields), ...], deleted_ids)
        entries = result[1] if isinstance(result, (list, tuple)) and len(result) >= 2 else []
        for msg_id, fields in entries:
            attempt = int(fields.get("attempt", "1"))
            if attempt >= max_retry:
                # 超限送 DLQ
                await send_to_dlq(
                    redis, stage, fields,
                    error_type="MAX_RETRY_EXCEEDED",
                    error_message=f"Exceeded max retry {max_retry}",
                    trace_id=fields.get("trace_id", ""),
                )
                await ack(redis, stage, msg_id)
                logger.warning("queue_max_retry_dlq", stage=stage,
                               job_id=fields.get("job_id", ""), msg_id=msg_id)
            else:
                # 增加 attempt，继续处理
                updated = dict(fields)
                updated["attempt"] = str(attempt + 1)
                await redis.xadd(stream, updated)
                await ack(redis, stage, msg_id)
                logger.info("queue_reclaimed", stage=stage,
                            job_id=fields.get("job_id", ""),
                            new_attempt=attempt + 1)
                reclaimed.append((msg_id, updated))
    except Exception as e:
        logger.warning("queue_reclaim_error", stage=stage, error=str(e))
    return reclaimed
