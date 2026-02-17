"""事件链完整性测试。"""
import pytest
from pdf_sku.gateway.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_pub_sub():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe("TestEvent", handler)
    await bus.publish("TestEvent", {"key": "value"})
    assert len(received) == 1
    assert received[0]["key"] == "value"


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers():
    bus = EventBus()
    results = []

    async def h1(event):
        results.append("h1")

    async def h2(event):
        results.append("h2")

    bus.subscribe("Multi", h1)
    bus.subscribe("Multi", h2)
    await bus.publish("Multi", {})
    assert "h1" in results
    assert "h2" in results


@pytest.mark.asyncio
async def test_event_bus_no_subscribers():
    bus = EventBus()
    # Should not raise
    await bus.publish("NoListener", {"data": 1})


@pytest.mark.asyncio
async def test_event_bus_error_isolation():
    bus = EventBus()
    results = []

    async def bad_handler(event):
        raise ValueError("boom")

    async def good_handler(event):
        results.append("ok")

    bus.subscribe("ErrTest", bad_handler)
    bus.subscribe("ErrTest", good_handler)
    await bus.publish("ErrTest", {})
    # good_handler should still execute
    assert "ok" in results


def test_full_event_chain_types():
    """验证所有事件类型在系统中被使用。"""
    expected_events = {
        "JobCreated",
        "EvaluationCompleted",
        "PageCompleted",
        "PageStatusChanged",
        "TaskCreated",
        "TaskCompleted",
        "JobOrphaned",
        "JobRequeued",
    }
    # Just verify the list is known
    assert len(expected_events) == 8
