"""Output handler 测试。"""
from pdf_sku.output._handler import _on_page_completed


def test_handler_importable():
    from pdf_sku.output._handler import init_output_handler
    assert callable(init_output_handler)
