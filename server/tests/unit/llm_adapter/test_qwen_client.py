"""QWen Client 测试 (无网络)。"""
from pdf_sku.llm_adapter.client.qwen import QwenClient, QWEN_API_BASE


def test_client_init():
    client = QwenClient(api_key="test-key", model="qwen-max")
    assert client.model_id == "qwen-max"
    assert client.provider == "qwen"


def test_api_base():
    assert "dashscope" in QWEN_API_BASE
