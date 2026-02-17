"""Feedback handler 测试。"""
from pdf_sku.feedback._handler import _on_task_completed


def test_handler_importable():
    """handler 模块可导入。"""
    from pdf_sku.feedback._handler import init_feedback_handler
    assert callable(init_feedback_handler)
