"""
OpenRouter LLM 客户端。

- OpenAI 兼容 API 格式
- 支持多模型路由 (Gemini, Claude, GPT 等)
- 视觉支持 (图片 base64)
- JSON mode
"""
from __future__ import annotations
import base64
import time
import httpx
import structlog

from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse
from pdf_sku.llm_adapter.client.request_utils import (
    prepare_request,
    raise_for_status_with_context,
    wrap_transport_error,
)

logger = structlog.get_logger()

DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api"


class OpenRouterClient(BaseLLMClient):
    """OpenRouter 客户端 (OpenAI 兼容)。"""

    def __init__(
        self,
        api_key: str = "",
        model: str = "google/gemini-2.5-flash",
        timeout: float = 60.0,
        api_base: str = "",
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        base = (api_base or DEFAULT_OPENROUTER_BASE).rstrip("/")
        self._api_url = f"{base}/v1/chat/completions"
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
        images: list[bytes] | None = None,
    ) -> LLMResponse:
        prepared_images, request_metrics = prepare_request(
            provider=self.provider,
            model=self._model,
            endpoint=self._api_url,
            prompt=prompt,
            images=images,
            json_mode=json_mode,
            max_tokens=max_tokens,
            use_data_url=True,
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # 构建 user message content
        if prepared_images:
            content_parts = []
            for prepared in prepared_images:
                b64 = base64.b64encode(prepared.data).decode()
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{prepared.mime_type};base64,{b64}"},
                })
            content_parts.append({"type": "text", "text": prompt})
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": prompt})

        body: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        try:
            resp = await self._client.post(self._api_url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise wrap_transport_error(
                exc,
                provider=self.provider,
                model=self._model,
                endpoint=self._api_url,
                request_metrics=request_metrics,
            ) from exc
        latency = (time.monotonic() - start) * 1000
        raise_for_status_with_context(
            resp,
            provider=self.provider,
            model=self._model,
            endpoint=self._api_url,
            request_metrics=request_metrics,
        )
        data = resp.json()

        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=self._model,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            finish_reason=choices[0].get("finish_reason", "") if choices else "",
            latency_ms=latency,
            raw_response=data,
        )

    async def complete_with_retry(
        self,
        prompt: str,
        system: str = "",
        max_retries: int = 2,
        **kwargs,
    ) -> LLMResponse:
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.complete(prompt, system, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import asyncio
                    await asyncio.sleep(1.5 * (attempt + 1))
                    logger.warning("openrouter_retry",
                                   attempt=attempt + 1, error=str(e))
        raise last_error  # type: ignore

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "openrouter"
