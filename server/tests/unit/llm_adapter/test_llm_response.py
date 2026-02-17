"""LLMResponse 测试。"""
from pdf_sku.llm_adapter.client.base import LLMResponse


def test_response_defaults():
    r = LLMResponse()
    assert r.content == ""
    assert r.total_tokens == 0
    assert r.cost == 0.0


def test_response_with_usage():
    r = LLMResponse(
        content="hello",
        model="qwen-max",
        usage={"input_tokens": 100, "output_tokens": 50},
        latency_ms=250.0,
    )
    assert r.total_tokens == 150
    assert r.cost > 0


def test_response_finish_reason():
    r = LLMResponse(finish_reason="stop")
    assert r.finish_reason == "stop"
