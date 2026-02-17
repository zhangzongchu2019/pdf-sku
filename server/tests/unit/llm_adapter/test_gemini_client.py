"""Gemini Client 测试 (无网络)。"""
from pdf_sku.llm_adapter.client.gemini import GeminiClient, GEMINI_API_BASE


def test_client_init():
    client = GeminiClient(api_key="test-key", model="gemini-2.0-flash")
    assert client.model_id == "gemini-2.0-flash"
    assert client.provider == "gemini"


def test_api_base():
    assert "generativelanguage" in GEMINI_API_BASE
