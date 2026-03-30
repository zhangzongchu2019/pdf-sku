"""
Google Gemini LLM 客户端。对齐: LLM Adapter 详设

- Gemini 2.0 Flash / Pro
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

DEFAULT_GEMINI_API_BASE = "https://generativelanguage.googleapis.com"
GEMINI_API_BASE = DEFAULT_GEMINI_API_BASE


class GeminiClient(BaseLLMClient):
    """Google Gemini 客户端。支持官方 API 和兼容中转 (laozhang.ai 等)。"""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.0-flash",
        timeout: float = 60.0,
        api_base: str = "",
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        base = (api_base or DEFAULT_GEMINI_API_BASE).rstrip("/")
        self._api_base = f"{base}/v1beta/models"
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
        endpoint = f"{self._api_base}/{self._model}:generateContent"
        prepared_images, request_metrics = prepare_request(
            provider=self.provider,
            model=self._model,
            endpoint=endpoint,
            prompt=prompt,
            images=images,
            json_mode=json_mode,
            max_tokens=max_tokens,
            use_data_url=False,
        )
        parts = []

        # 图片 (vision)
        if prepared_images:
            for prepared in prepared_images:
                b64 = base64.b64encode(prepared.data).decode()
                parts.append({
                    "inline_data": {
                        "mime_type": prepared.mime_type,
                        "data": b64,
                    }
                })

        parts.append({"text": prompt})

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        url = f"{self._api_base}/{self._model}:generateContent?key={self._api_key}"
        start = time.monotonic()
        try:
            resp = await self._client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise wrap_transport_error(
                exc,
                provider=self.provider,
                model=self._model,
                endpoint=endpoint,
                request_metrics=request_metrics,
            ) from exc
        latency = (time.monotonic() - start) * 1000
        raise_for_status_with_context(
            resp,
            provider=self.provider,
            model=self._model,
            endpoint=endpoint,
            request_metrics=request_metrics,
        )
        data = resp.json()

        candidates = data.get("candidates", [])
        content = ""
        if candidates:
            parts_out = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts_out)

        usage_meta = data.get("usageMetadata", {})

        return LLMResponse(
            content=content,
            model=self._model,
            usage={
                "input_tokens": usage_meta.get("promptTokenCount", 0),
                "output_tokens": usage_meta.get("candidatesTokenCount", 0),
            },
            finish_reason=candidates[0].get("finishReason", "") if candidates else "",
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
                    logger.warning("gemini_retry",
                                   attempt=attempt + 1, error=str(e))
        raise last_error  # type: ignore

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "gemini"
