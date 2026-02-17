"""ScheduledTaskRunner 测试。"""
import asyncio
import pytest
from pdf_sku.feedback.scheduler import ScheduledTaskRunner


def test_init_no_deps():
    runner = ScheduledTaskRunner()
    assert runner._running is False
    assert runner._tasks == []


@pytest.mark.asyncio
async def test_start_stop():
    runner = ScheduledTaskRunner()
    await runner.start()
    assert runner._running is True
    assert len(runner._tasks) == 6
    await runner.stop()
    assert runner._running is False
    assert runner._tasks == []
