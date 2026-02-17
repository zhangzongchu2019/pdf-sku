"""LockManager 常量测试。"""
from pdf_sku.collaboration.lock_manager import (
    HEARTBEAT_INTERVAL, LOCK_TIMEOUT, MAX_REWORK_COUNT,
)


def test_heartbeat_interval():
    assert HEARTBEAT_INTERVAL == 30


def test_lock_timeout():
    assert LOCK_TIMEOUT == 300  # 5 min


def test_max_rework():
    assert MAX_REWORK_COUNT == 5


def test_heartbeat_fits_in_timeout():
    """心跳间隔应远小于锁超时。"""
    assert HEARTBEAT_INTERVAL * 3 < LOCK_TIMEOUT
