"""LLM 客户端基类。"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """LLM 调用响应。"""
    content: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)  # {input_tokens, output_tokens}
    finish_reason: str = ""
    latency_ms: float = 0.0
    raw_response: dict | None = None

    @property
    def total_tokens(self) -> int:
        return self.usage.get("input_tokens", 0) + self.usage.get("output_tokens", 0)

    @property
    def cost(self) -> float:
        """估算成本 (USD)。"""
        input_cost = self.usage.get("input_tokens", 0) / 1000 * 0.001
        output_cost = self.usage.get("output_tokens", 0) / 1000 * 0.002
        return input_cost + output_cost


class BaseLLMClient(ABC):
    """LLM 客户端基类。"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
        images: list[bytes] | None = None,
    ) -> LLMResponse:
        """发送 completion 请求。"""
        ...

    @abstractmethod
    async def complete_with_retry(
        self,
        prompt: str,
        system: str = "",
        max_retries: int = 2,
        **kwargs,
    ) -> LLMResponse:
        """带重试的 completion。"""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        ...

    @property
    @abstractmethod
    def provider(self) -> str:
        ...
