"""TaskManager 状态机测试。"""
from pdf_sku.collaboration.annotation_service import (
    VALID_TRANSITIONS, REVERTABLE_STATUSES, MAX_REWORK_COUNT,
)


def test_valid_transitions_complete():
    """验证关键状态转换路径存在。"""
    assert ("CREATED", "PROCESSING") in VALID_TRANSITIONS
    assert ("PROCESSING", "COMPLETED") in VALID_TRANSITIONS
    assert ("PROCESSING", "SKIPPED") in VALID_TRANSITIONS
    assert ("COMPLETED", "CREATED") in VALID_TRANSITIONS   # revert
    assert ("SKIPPED", "CREATED") in VALID_TRANSITIONS      # revert


def test_invalid_transitions():
    """验证非法转换不存在。"""
    assert ("CREATED", "COMPLETED") not in VALID_TRANSITIONS  # 不能直接完成
    assert ("COMPLETED", "PROCESSING") not in VALID_TRANSITIONS


def test_revertable_statuses():
    assert "COMPLETED" in REVERTABLE_STATUSES
    assert "SKIPPED" in REVERTABLE_STATUSES
    assert "PROCESSING" not in REVERTABLE_STATUSES


def test_max_rework_count():
    assert MAX_REWORK_COUNT == 5
