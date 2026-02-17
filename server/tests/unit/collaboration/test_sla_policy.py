"""SLA 策略测试。"""
from pdf_sku.collaboration.sla_monitor import SLA_POLICY, AUTO_REVIEW_SAMPLE_RATE


def test_sla_levels():
    assert "NORMAL" in SLA_POLICY
    assert "HIGH" in SLA_POLICY
    assert "CRITICAL" in SLA_POLICY
    assert "AUTO_RESOLVE" in SLA_POLICY


def test_sla_timeout_ascending():
    timeouts = [SLA_POLICY[l]["timeout_min"] for l in
                ["NORMAL", "HIGH", "CRITICAL", "AUTO_RESOLVE"]]
    assert timeouts == sorted(timeouts)


def test_sla_actions():
    assert SLA_POLICY["NORMAL"]["action"] == "PRIORITY_BOOST"
    assert SLA_POLICY["HIGH"]["action"] == "ESCALATE_TO_SUPERVISOR"
    assert SLA_POLICY["CRITICAL"]["action"] == "AUTO_QUALITY_CHECK"
    assert SLA_POLICY["AUTO_RESOLVE"]["action"] == "PARTIAL_ACCEPTANCE"


def test_auto_review_sample_rate():
    assert 0 < AUTO_REVIEW_SAMPLE_RATE < 1
    assert AUTO_REVIEW_SAMPLE_RATE == 0.05
