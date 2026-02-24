"""Per-provider LLM runtime configuration (Redis-backed with code defaults)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

REDIS_KEY_PREFIX = "pdf_sku:llm_provider_config:"


@dataclass
class LLMProviderConfig:
    timeout_seconds: int = 60
    vlm_timeout_seconds: int = 180
    max_retries: int = 2


DEFAULT_PROVIDER_CONFIGS: dict[str, LLMProviderConfig] = {
    "qwen": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=180, max_retries=2),
    "gemini": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=120, max_retries=2),
}


async def get_provider_config(redis, provider: str) -> LLMProviderConfig:
    """Read provider config from Redis, falling back to code defaults."""
    default = DEFAULT_PROVIDER_CONFIGS.get(provider, LLMProviderConfig())
    if redis is None:
        return default
    try:
        raw = await redis.get(f"{REDIS_KEY_PREFIX}{provider}")
        if raw:
            data = json.loads(raw)
            return LLMProviderConfig(
                timeout_seconds=data.get("timeout_seconds", default.timeout_seconds),
                vlm_timeout_seconds=data.get("vlm_timeout_seconds", default.vlm_timeout_seconds),
                max_retries=data.get("max_retries", default.max_retries),
            )
    except Exception:
        pass
    return default


async def set_provider_config(redis, provider: str, config: LLMProviderConfig) -> None:
    """Write provider config to Redis."""
    await redis.set(f"{REDIS_KEY_PREFIX}{provider}", json.dumps(asdict(config)))


async def list_provider_configs(redis) -> dict[str, dict]:
    """Return all provider configs (defaults merged with Redis overrides)."""
    result: dict[str, dict] = {}
    for provider, default in DEFAULT_PROVIDER_CONFIGS.items():
        cfg = await get_provider_config(redis, provider)
        result[provider] = asdict(cfg)
    return result
