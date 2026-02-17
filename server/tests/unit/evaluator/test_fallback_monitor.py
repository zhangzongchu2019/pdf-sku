"""FallbackMonitor 测试。"""
from pdf_sku.evaluator.fallback_monitor import (
    FallbackMonitor, CONSECUTIVE_THRESHOLD,
)


def test_threshold():
    assert CONSECUTIVE_THRESHOLD == 3


def test_no_fallback_initially():
    fm = FallbackMonitor()
    assert not fm.should_suspend("job-1")


def test_consecutive_fallback_triggers():
    fm = FallbackMonitor(threshold=3)
    fm.on_page_fallback("job-1", 1)
    fm.on_page_fallback("job-1", 2)
    assert not fm.should_suspend("job-1")
    fm.on_page_fallback("job-1", 3)
    assert fm.should_suspend("job-1")


def test_success_resets_counter():
    fm = FallbackMonitor(threshold=3)
    fm.on_page_fallback("job-1", 1)
    fm.on_page_fallback("job-1", 2)
    fm.on_page_success("job-1")
    fm.on_page_fallback("job-1", 3)
    assert not fm.should_suspend("job-1")


def test_job_isolation():
    fm = FallbackMonitor(threshold=2)
    fm.on_page_fallback("job-1", 1)
    fm.on_page_fallback("job-2", 1)
    fm.on_page_fallback("job-1", 2)
    assert fm.should_suspend("job-1")
    assert not fm.should_suspend("job-2")


def test_reset():
    fm = FallbackMonitor(threshold=2)
    fm.on_page_fallback("job-1", 1)
    fm.on_page_fallback("job-1", 2)
    assert fm.should_suspend("job-1")
    fm.reset("job-1")
    assert not fm.should_suspend("job-1")
