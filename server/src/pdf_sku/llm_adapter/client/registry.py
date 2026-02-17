"""
LLM 客户端注册表。对齐: LLM Adapter 详设 §4.2

- 多模型注册 + 能力标签
- 按 task_type 选择最优模型
- fallback 链
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pdf_sku.llm_adapter.client.base import BaseLLMClient
import structlog

logger = structlog.get_logger()


@dataclass
class ModelCapability:
    """模型能力描述。"""
    model_id: str
    provider: str           # "qwen" | "gemini" | "openai"
    supports_vision: bool = False
    supports_json_mode: bool = True
    max_context_tokens: int = 8192
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    priority: int = 0       # 越小越优先
    tags: list[str] = field(default_factory=list)  # "fast", "accurate", "cheap"


class LLMClientRegistry:
    """LLM 客户端注册表 (多模型切换)。"""

    def __init__(self):
        self._clients: dict[str, BaseLLMClient] = {}
        self._capabilities: dict[str, ModelCapability] = {}
        self._task_mapping: dict[str, list[str]] = {
            "classify": [],
            "extract_table": [],
            "extract_mixed": [],
            "extract_image": [],
            "binding": [],
            "evaluate": [],
        }

    def register(
        self,
        model_id: str,
        client: BaseLLMClient,
        capability: ModelCapability,
        tasks: list[str] | None = None,
    ) -> None:
        """注册模型。"""
        self._clients[model_id] = client
        self._capabilities[model_id] = capability
        if tasks:
            for task in tasks:
                if task in self._task_mapping:
                    self._task_mapping[task].append(model_id)
                    # 按 priority 排序
                    self._task_mapping[task].sort(
                        key=lambda m: self._capabilities[m].priority)
        logger.info("llm_registered",
                     model_id=model_id, provider=capability.provider,
                     tasks=tasks)

    def get_client(self, model_id: str) -> BaseLLMClient | None:
        """获取指定模型客户端。"""
        return self._clients.get(model_id)

    def get_for_task(self, task_type: str) -> BaseLLMClient | None:
        """按任务类型获取最优模型。"""
        models = self._task_mapping.get(task_type, [])
        for model_id in models:
            client = self._clients.get(model_id)
            if client:
                return client
        # fallback: 返回任意可用
        for client in self._clients.values():
            return client
        return None

    def get_fallback_chain(self, task_type: str) -> list[BaseLLMClient]:
        """获取任务的 fallback 链 (按 priority 排序)。"""
        models = self._task_mapping.get(task_type, [])
        return [self._clients[m] for m in models if m in self._clients]

    def get_vision_client(self) -> BaseLLMClient | None:
        """获取支持视觉的模型。"""
        for model_id, cap in self._capabilities.items():
            if cap.supports_vision and model_id in self._clients:
                return self._clients[model_id]
        return None

    def list_models(self) -> list[dict]:
        """列出已注册模型。"""
        return [
            {
                "model_id": m,
                "provider": c.provider,
                "supports_vision": c.supports_vision,
                "priority": c.priority,
                "tags": c.tags,
            }
            for m, c in self._capabilities.items()
        ]

    @property
    def model_count(self) -> int:
        return len(self._clients)


# ─── Backwards-compatible singleton ───
_default_registry = LLMClientRegistry()


def get_client(model_id: str | None = None) -> BaseLLMClient | None:
    """获取 LLM 客户端 (向后兼容)。"""
    if model_id:
        return _default_registry.get_client(model_id)
    # 返回第一个可用的
    for client in _default_registry._clients.values():
        return client
    return None


def get_registry() -> LLMClientRegistry:
    """获取全局注册表。"""
    return _default_registry


def register(name: str, client: BaseLLMClient) -> None:
    """注册 LLM 客户端 (简便接口, main.py 使用)。"""
    _default_registry._clients[name] = client
