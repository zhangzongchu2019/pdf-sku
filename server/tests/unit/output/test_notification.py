"""Notifier 测试。"""
import pytest
from pdf_sku.collaboration.notification import Notifier


@pytest.mark.asyncio
async def test_send_no_webhook():
    """无 webhook → 仅记日志, 返回 True。"""
    n = Notifier()
    result = await n.send("supervisor", "test message")
    assert result is True


@pytest.mark.asyncio
async def test_send_unknown_channel():
    n = Notifier()
    result = await n.send("unknown_channel", "test")
    assert result is True  # fallback to log
