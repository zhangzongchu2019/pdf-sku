"""FallbackMonitor 单元测试。"""
from pdf_sku.evaluator.fallback_monitor import FallbackMonitor


def test_no_suspend_initially():
    fm = FallbackMonitor(threshold=3)
    assert not fm.should_suspend("job1")


def test_suspend_after_threshold():
    fm = FallbackMonitor(threshold=3)
    fm.on_page_fallback("job1", 1)
    fm.on_page_fallback("job1", 2)
    assert not fm.should_suspend("job1")
    fm.on_page_fallback("job1", 3)
    assert fm.should_suspend("job1")


def test_success_resets():
    fm = FallbackMonitor(threshold=3)
    fm.on_page_fallback("job1", 1)
    fm.on_page_fallback("job1", 2)
    fm.on_page_success("job1")
    fm.on_page_fallback("job1", 3)
    assert not fm.should_suspend("job1")  # Reset by success


def test_different_jobs_independent():
    fm = FallbackMonitor(threshold=2)
    fm.on_page_fallback("job1", 1)
    fm.on_page_fallback("job2", 1)
    fm.on_page_fallback("job1", 2)
    assert fm.should_suspend("job1")
    assert not fm.should_suspend("job2")


def test_reset():
    fm = FallbackMonitor(threshold=2)
    fm.on_page_fallback("job1", 1)
    fm.on_page_fallback("job1", 2)
    fm.reset("job1")
    assert not fm.should_suspend("job1")
