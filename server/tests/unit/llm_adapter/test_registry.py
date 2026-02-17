"""LLM Client Registry 测试。"""
import pytest
from pdf_sku.llm_adapter.client.registry import (
    LLMClientRegistry, ModelCapability,
)
from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse


class MockClient(BaseLLMClient):
    def __init__(self, mid, prov):
        self._mid = mid
        self._prov = prov

    async def complete(self, prompt, **kw):
        return LLMResponse(content="mock", model=self._mid)

    async def complete_with_retry(self, prompt, **kw):
        return await self.complete(prompt, **kw)

    @property
    def model_id(self):
        return self._mid

    @property
    def provider(self):
        return self._prov


def test_register_and_get():
    reg = LLMClientRegistry()
    client = MockClient("qwen-max", "qwen")
    cap = ModelCapability(model_id="qwen-max", provider="qwen", priority=0)
    reg.register("qwen-max", client, cap, tasks=["classify", "extract_table"])

    assert reg.model_count == 1
    assert reg.get_client("qwen-max") is client
    assert reg.get_client("nonexistent") is None


def test_get_for_task():
    reg = LLMClientRegistry()
    c1 = MockClient("qwen-max", "qwen")
    c2 = MockClient("gemini-flash", "gemini")

    reg.register("qwen-max", c1,
                 ModelCapability("qwen-max", "qwen", priority=1),
                 tasks=["classify"])
    reg.register("gemini-flash", c2,
                 ModelCapability("gemini-flash", "gemini", priority=0),
                 tasks=["classify"])

    # gemini has higher priority (lower number)
    result = reg.get_for_task("classify")
    assert result is c2


def test_fallback_chain():
    reg = LLMClientRegistry()
    c1 = MockClient("m1", "p1")
    c2 = MockClient("m2", "p2")
    reg.register("m1", c1, ModelCapability("m1", "p1", priority=0), tasks=["extract_table"])
    reg.register("m2", c2, ModelCapability("m2", "p2", priority=1), tasks=["extract_table"])

    chain = reg.get_fallback_chain("extract_table")
    assert len(chain) == 2
    assert chain[0] is c1  # priority=0 first


def test_vision_client():
    reg = LLMClientRegistry()
    c1 = MockClient("text-only", "p1")
    c2 = MockClient("vision-model", "p2")
    reg.register("text-only", c1,
                 ModelCapability("text-only", "p1", supports_vision=False))
    reg.register("vision-model", c2,
                 ModelCapability("vision-model", "p2", supports_vision=True))

    vc = reg.get_vision_client()
    assert vc is c2


def test_list_models():
    reg = LLMClientRegistry()
    reg.register("m1", MockClient("m1", "qwen"),
                 ModelCapability("m1", "qwen", priority=0, tags=["fast"]))
    models = reg.list_models()
    assert len(models) == 1
    assert models[0]["tags"] == ["fast"]
