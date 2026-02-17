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

logger = structlog.get_logger()

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient(BaseLLMClient):
    """Google Gemini 客户端。"""

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
    ) -> LLMResponse:
        parts = []

        # 图片 (vision)
        if images:
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode()
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
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

        url = f"{GEMINI_API_BASE}/{self._model}:generateContent?key={self._api_key}"
        start = time.monotonic()
        resp = await self._client.post(url, json=body)
        latency = (time.monotonic() - start) * 1000
        resp.raise_for_status()
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
