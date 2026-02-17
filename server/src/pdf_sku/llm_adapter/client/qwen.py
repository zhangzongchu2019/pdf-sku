"""
通义千问 LLM 客户端。对齐: LLM Adapter 详设

- 支持 qwen-max / qwen-vl-max
- JSON mode
- 自动重试
"""
from __future__ import annotations
import time
import httpx
import structlog

from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse

logger = structlog.get_logger()

QWEN_API_BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
QWEN_VL_BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"


class QwenClient(BaseLLMClient):
    """通义千问客户端。"""

    def __init__(
        self,
        api_key: str = "",
        model: str = "qwen-max",
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
        is_vl = images and ("vl" in self._model.lower())
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        if is_vl:
            # Qwen-VL multimodal format
            import base64
            content_parts = []
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode()
                content_parts.append({
                    "image": f"data:image/jpeg;base64,{b64}",
                })
            content_parts.append({"text": prompt})
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": prompt})

        params = {
            "model": self._model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "result_format": "message",
            },
        }
        if json_mode:
            params["parameters"]["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        api_url = QWEN_VL_BASE if is_vl else QWEN_API_BASE
        start = time.monotonic()
        resp = await self._client.post(api_url, json=params, headers=headers)
        latency = (time.monotonic() - start) * 1000
        resp.raise_for_status()
        data = resp.json()

        output = data.get("output", {})
        choices = output.get("choices", [{}])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=self._model,
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
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
                    await asyncio.sleep(1.0 * (attempt + 1))
                    logger.warning("qwen_retry",
                                   attempt=attempt + 1, error=str(e))
        raise last_error  # type: ignore

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "qwen"
