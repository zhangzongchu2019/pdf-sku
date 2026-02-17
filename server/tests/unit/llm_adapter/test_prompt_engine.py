"""PromptEngine 单元测试。"""
from pdf_sku.llm_adapter.prompt.engine import PromptEngine


def test_eval_document_template():
    pe = PromptEngine()
    prompt = pe.get_prompt("eval_document", {"category": "electronics"})
    assert "electronics" in prompt
    assert "text_clarity" in prompt
    assert "image_quality" in prompt


def test_eval_document_no_category():
    pe = PromptEngine()
    prompt = pe.get_prompt("eval_document")
    assert "text_clarity" in prompt


def test_unknown_template():
    pe = PromptEngine()
    try:
        pe.get_prompt("nonexistent")
        assert False, "Should raise"
    except ValueError:
        pass


def test_version():
    pe = PromptEngine()
    v = pe.get_version("eval_document")
    assert "eval_document" in v
    assert "v1.0" in v


def test_list_templates():
    pe = PromptEngine()
    templates = pe.list_templates()
    assert "eval_document" in templates
    assert "classify_page" in templates
