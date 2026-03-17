"""
轻量 Redis 事件定义与发布工具。

对齐: fix.md §8 — Redis 轻量事件设计

事件通道: pdfsku:event:job:{job_id}
通过 Redis Pub/Sub 发布，API SSEGateway 订阅后转发给浏览器。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum

import structlog

logger = structlog.get_logger()


def _event_channel(job_id: str) -> str:
    return f"pdfsku:event:job:{job_id}"


class JobEvent(StrEnum):
    """系统事件类型 (fix.md §8.2)。"""
    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    JOB_STAGE_CHANGED = "job_stage_changed"
    PAGE_STARTED = "page_started"
    PAGE_COMPLETED = "page_completed"
    PAGE_FAILED = "page_failed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    HUMAN_NEEDED = "human_needed"
    EXPORT_READY = "export_ready"


async def publish_job_event(
    redis,
    event: str,
    job_id: str,
    *,
    stage: str | None = None,
    page_no: int | None = None,
    status: str | None = None,
    sku_count: int | None = None,
    progress_percent: int | None = None,
    error: str | None = None,
    trace_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """
    向 pdfsku:event:job:{job_id} 频道发布轻量事件。

    负载约束 (fix.md §8.3):
    - 只放轻量信息
    - 不放图片二进制、完整 OCR 文本、完整 page detail
    """
    payload: dict = {
        "event": event,
        "job_id": job_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if stage is not None:
        payload["stage"] = stage
    if page_no is not None:
        payload["page_no"] = page_no
    if status is not None:
        payload["status"] = status
    if sku_count is not None:
        payload["sku_count"] = sku_count
    if progress_percent is not None:
        payload["progress_percent"] = progress_percent
    if error is not None:
        payload["error"] = error[:500]  # 严格截断，避免大对象
    if trace_id is not None:
        payload["trace_id"] = trace_id
    if extra:
        payload.update(extra)

    channel = _event_channel(job_id)
    try:
        await redis.publish(channel, json.dumps(payload))
        logger.debug("event_published", event_type=event, job_id=job_id, channel=channel)
    except Exception as e:
        logger.warning("event_publish_failed", event_type=event, job_id=job_id, error=str(e))
