"""
通用 OpenAI 兼容 LLM 客户端。

支持任意 OpenAI 兼容的 API 服务，包括：
- laozhang.ai (中转 Gemini/Qwen/Claude 等)
- OpenRouter (google/gemini-2.5-flash 等)
- 任意 OpenAI 兼容端点
"""
from __future__ import annotations
import asyncio
import base64
import time
import httpx
import structlog

from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse

logger = structlog.get_logger()


class OpenAICompatClient(BaseLLMClient):
    """通用 OpenAI 兼容客户端。适用于任何实现了 /v1/chat/completions 的服务。"""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str,
        provider_name: str = "",
        timeout: float = 60.0,
    ):
        """
        Args:
            api_key: API 密钥
            api_base: 服务基础 URL (如 https://api.laozhang.ai 或 https://openrouter.ai/api)
            model: 模型名 (如 gemini-2.5-flash 或 google/gemini-2.5-flash)
            provider_name: 提供商后缀 (如 laozhang.ai, openrouter.ai)，用于日志标识
            timeout: 请求超时 (秒)
        """
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._provider_name = provider_name
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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # 构建用户消息
        user_content: list | str
        if images:
            parts = []
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode()
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            parts.append({"type": "text", "text": prompt})
            user_content = parts
        else:
            user_content = prompt
        messages.append({"role": "user", "content": user_content})

        body: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        url = f"{self._api_base}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        start = time.monotonic()
        effective_timeout = httpx.Timeout(timeout) if timeout else None
        resp = await self._client.post(
            url, json=body, headers=headers, timeout=effective_timeout)
        latency = (time.monotonic() - start) * 1000
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
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
                    await asyncio.sleep(1.5 * (attempt + 1))
                    logger.warning("openai_compat_retry",
                                   provider=self._provider_name,
                                   model=self._model,
                                   attempt=attempt + 1, error=str(e))
        raise last_error  # type: ignore

    @property
    def model_id(self) -> str:
        if self._provider_name:
            return f"{self._model}-{self._provider_name}"
        return self._model

    @property
    def provider(self) -> str:
        # 从模型名推断基础 provider
        model_lower = self._model.lower()
        if "gemini" in model_lower:
            base = "gemini"
        elif "qwen" in model_lower:
            base = "qwen"
        elif "claude" in model_lower:
            base = "claude"
        elif "gpt" in model_lower:
            base = "openai"
        else:
            base = "openai-compat"

        if self._provider_name:
            return f"{base}-{self._provider_name}"
        return base
