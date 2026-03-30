"""LLMService 重试与批处理测试。"""
from __future__ import annotations

import pytest

from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse
from pdf_sku.llm_adapter.client.request_utils import LLMClientRequestError
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
from pdf_sku.llm_adapter.prompt.engine import PromptEngine
from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker
from pdf_sku.llm_adapter.service import LLMService, _build_eval_batches
from pdf_sku.settings import settings


class _ErrorClient(BaseLLMClient):
    def __init__(self, exc: Exception):
        self._exc = exc
        self.calls = 0

    async def complete(self, prompt, **kwargs):
        self.calls += 1
        raise self._exc

    async def complete_with_retry(self, prompt, **kwargs):
        return await self.complete(prompt, **kwargs)

    @property
    def model_id(self) -> str:
        return "qwen-vl-max"

    @property
    def provider(self) -> str:
        return "qwen"


class _SuccessClient(BaseLLMClient):
    def __init__(self):
        self.calls = 0

    async def complete(self, prompt, **kwargs):
        self.calls += 1
        image_count = len(kwargs.get("images") or [])
        content = str([{"overall": 0.9}] * image_count).replace("'", '"')
        return LLMResponse(content=content, model=self.model_id)

    async def complete_with_retry(self, prompt, **kwargs):
        return await self.complete(prompt, **kwargs)

    @property
    def model_id(self) -> str:
        return "qwen-vl-max"

    @property
    def provider(self) -> str:
        return "qwen"


def _make_service() -> LLMService:
    return LLMService(
        prompt_engine=PromptEngine(),
        parser=ResponseParser(),
        circuit_breaker=CircuitBreaker(),
        default_client_name="qwen",
        fallback_chain=["qwen"],
        provider_weights={"qwen": 1},
    )


@pytest.mark.asyncio
async def test_call_llm_does_not_retry_non_retryable_invalid_request(monkeypatch):
    client = _ErrorClient(
        LLMClientRequestError(
            "payload too large",
            provider="qwen",
            model="qwen-vl-max",
            endpoint="https://example.test/v1/chat/completions",
            error_kind="payload_too_large",
            retryable=False,
            allow_fallback=False,
        )
    )
    monkeypatch.setattr("pdf_sku.llm_adapter.service.get_client", lambda name: client)

    svc = _make_service()
    with pytest.raises(LLMClientRequestError) as exc:
        await svc._call_llm(
            operation="evaluate_document",
            prompt="return json",
            images=[b"x"],
            client_name="qwen",
            timeout=1.0,
        )

    assert exc.value.error_kind == "payload_too_large"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_evaluate_document_splits_batches_by_inline_limit(monkeypatch):
    monkeypatch.setattr(settings, "llm_request_max_inline_bytes", 3_000)
    monkeypatch.setattr(settings, "llm_max_images_per_request", 5)

    client = _SuccessClient()
    monkeypatch.setattr("pdf_sku.llm_adapter.service.get_client", lambda name: client)

    svc = _make_service()
    screenshots = [b"a" * 1000, b"b" * 1000, b"c" * 1000]
    result = await svc.evaluate_document(screenshots=screenshots, sample_pages=[1, 2, 3])

    assert len(result) == 3
    assert client.calls == 2


def test_build_eval_batches_respects_image_cap(monkeypatch):
    monkeypatch.setattr(settings, "llm_request_max_inline_bytes", 100_000)
    monkeypatch.setattr(settings, "llm_max_images_per_request", 2)

    batches = _build_eval_batches(
        screenshots=[b"a", b"b", b"c"],
        pages=[1, 2, 3],
    )

    assert [len(images) for images, _pages in batches] == [2, 1]
