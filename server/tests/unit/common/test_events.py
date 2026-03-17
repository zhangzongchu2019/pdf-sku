import json

import pytest
from unittest.mock import AsyncMock

from pdf_sku.common.events import JobEvent, publish_job_event


@pytest.mark.asyncio
async def test_publish_job_event_serializes_lightweight_payload():
    redis = AsyncMock()

    await publish_job_event(
        redis,
        JobEvent.JOB_QUEUED,
        "job-123",
        stage="evaluate",
        status="UPLOADED",
        page_no=2,
        sku_count=5,
        progress_percent=40,
        trace_id="trace-1",
        error="x" * 800,
        extra={"route": "AUTO"},
    )

    redis.publish.assert_awaited_once()
    channel, payload_json = redis.publish.await_args.args
    payload = json.loads(payload_json)

    assert channel == "pdfsku:event:job:job-123"
    assert payload["event"] == JobEvent.JOB_QUEUED
    assert payload["job_id"] == "job-123"
    assert payload["stage"] == "evaluate"
    assert payload["status"] == "UPLOADED"
    assert payload["page_no"] == 2
    assert payload["sku_count"] == 5
    assert payload["progress_percent"] == 40
    assert payload["trace_id"] == "trace-1"
    assert payload["route"] == "AUTO"
    assert len(payload["error"]) == 500
    assert "ts" in payload
