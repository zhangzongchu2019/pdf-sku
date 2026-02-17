"""BackpressureMonitor 测试。"""
from pdf_sku.output.backpressure import BackpressureMonitor


def test_initial_not_throttled():
    bp = BackpressureMonitor()
    assert not bp.is_throttled("job1")


def test_all_success_not_throttled():
    bp = BackpressureMonitor()
    for _ in range(20):
        bp.on_success("job1")
    assert not bp.is_throttled("job1")


def test_high_failure_throttled():
    bp = BackpressureMonitor()
    for _ in range(5):
        bp.on_success("job1")
    for _ in range(15):
        bp.on_failure("job1")
    assert bp.is_throttled("job1")


def test_job_isolation():
    bp = BackpressureMonitor()
    for _ in range(20):
        bp.on_failure("job1")
    assert bp.is_throttled("job1")
    assert not bp.is_throttled("job2")


def test_failure_rate():
    bp = BackpressureMonitor()
    for _ in range(7):
        bp.on_success("job1")
    for _ in range(3):
        bp.on_failure("job1")
    rate = bp.get_failure_rate("job1")
    assert 0.25 < rate < 0.35


def test_clear():
    bp = BackpressureMonitor()
    for _ in range(20):
        bp.on_failure("job1")
    bp.clear("job1")
    assert not bp.is_throttled("job1")
