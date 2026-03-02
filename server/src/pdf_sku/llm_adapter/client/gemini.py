"""
Google Gemini LLM 客户端（原生 API 直连）。

- Gemini 2.0 Flash / 2.5 Flash / Pro
- 视觉支持 (图片 base64)
- JSON mode

注意：如需通过中转服务（laozhang.ai / OpenRouter）调用 Gemini，
请使用 OpenAICompatClient 而非此客户端。
"""
from __future__ import annotations
import asyncio
import base64
import time
import httpx
import structlog

from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse

logger = structlog.get_logger()

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient(BaseLLMClient):
    """Google Gemini 原生 API 客户端（直连 Google）。"""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.0-flash",
        timeout: float = 60.0,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
        images: list[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        parts = []
        if images:
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode()
                parts.append({
                    "inline_data": {"mime_type": "image/jpeg", "data": b64}
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

        url = f"{GEMINI_API_BASE}/{self._model}:generateContent?key={self._api_key}"
        start = time.monotonic()
        effective_timeout = httpx.Timeout(timeout) if timeout else None
        resp = await self._client.post(url, json=body, timeout=effective_timeout)
        latency = (time.monotonic() - start) * 1000
        if resp.is_error:
            body_text = resp.text[:500]
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code} from Gemini ({self._model}): {body_text}",
                request=resp.request,
                response=resp,
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
