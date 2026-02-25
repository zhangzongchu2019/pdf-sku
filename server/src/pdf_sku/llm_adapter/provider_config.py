"""Per-provider LLM runtime configuration (Redis-backed with code defaults)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

REDIS_KEY_PREFIX = "pdf_sku:llm_provider_config:"
REDIS_PROVIDERS_KEY = "pdf_sku:llm_providers"


@dataclass
class LLMProviderConfig:
    timeout_seconds: int = 60
    vlm_timeout_seconds: int = 180
    max_retries: int = 2


@dataclass
class LLMProviderEntry:
    """A registered LLM provider with priority and metadata."""
    name: str              # "gemini", "gemini.laozhang.ai", "qwen.openrouter"
    provider_type: str     # "gemini" | "qwen" | "claude"
    access_mode: str       # "direct" | "proxy"
    proxy_service: str | None = None  # "laozhang.ai" | "openrouter" | None
    model: str = ""        # "gemini-2.5-flash"
    priority: int = 0      # 0 = highest priority
    enabled: bool = True
    timeout_seconds: int = 60
    vlm_timeout_seconds: int = 180
    max_retries: int = 2
    account_name: str = ""    # references LLMAccount.name
    qpm_limit: int = 60      # per-provider QPM
    tpm_limit: int = 100000  # per-provider TPM


DEFAULT_PROVIDER_CONFIGS: dict[str, LLMProviderConfig] = {
    "gemini": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=120, max_retries=2),
    "qwen": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=180, max_retries=2),
}
# Also match by model-name-based keys for new naming convention
_PROVIDER_TYPE_DEFAULTS = {
    "gemini": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=120, max_retries=2),
    "qwen": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=180, max_retries=2),
    "claude": LLMProviderConfig(timeout_seconds=90, vlm_timeout_seconds=180, max_retries=2),
    "deepseek": LLMProviderConfig(timeout_seconds=60, vlm_timeout_seconds=180, max_retries=2),
}


async def get_provider_config(redis, provider: str) -> LLMProviderConfig:
    """Read provider config from Redis, falling back to code defaults."""
    default = DEFAULT_PROVIDER_CONFIGS.get(provider) or _PROVIDER_TYPE_DEFAULTS.get(provider, LLMProviderConfig())
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


# ──────────── LLMProviderEntry CRUD ────────────

async def get_provider_entries(redis) -> list[LLMProviderEntry]:
    """Get all provider entries from Redis, sorted by priority."""
    if redis is None:
        return []
    try:
        raw = await redis.get(REDIS_PROVIDERS_KEY)
        if raw:
            items = json.loads(raw)
            entries = [LLMProviderEntry(**item) for item in items]
            entries.sort(key=lambda e: e.priority)
            return entries
    except Exception:
        pass
    return []


async def set_provider_entries(redis, entries: list[LLMProviderEntry]) -> None:
    """Persist provider entries to Redis."""
    if redis is None:
        return
    data = [asdict(e) for e in entries]
    await redis.set(REDIS_PROVIDERS_KEY, json.dumps(data))


async def merge_provider_entries(
    redis,
    new_entries: list[LLMProviderEntry],
) -> list[LLMProviderEntry]:
    """
    Merge new entries with existing Redis config.
    Preserves user-adjusted priority/enabled from existing entries.
    Adds new entries, removes stale ones.
    """
    existing = await get_provider_entries(redis)
    existing_map = {e.name: e for e in existing}

    merged: list[LLMProviderEntry] = []
    for entry in new_entries:
        if entry.name in existing_map:
            old = existing_map[entry.name]
            # Preserve user-adjusted fields
            entry.priority = old.priority
            entry.enabled = old.enabled
            # Also preserve user-adjusted timeout/retries/limits
            entry.timeout_seconds = old.timeout_seconds
            entry.vlm_timeout_seconds = old.vlm_timeout_seconds
            entry.max_retries = old.max_retries
            entry.qpm_limit = old.qpm_limit
            entry.tpm_limit = old.tpm_limit
            if old.account_name:
                entry.account_name = old.account_name
        merged.append(entry)

    # Re-sort by priority
    merged.sort(key=lambda e: e.priority)
    await set_provider_entries(redis, merged)
    return merged


async def reorder_providers(redis, ordered_names: list[str]) -> list[LLMProviderEntry]:
    """Reorder providers by the given name list."""
    entries = await get_provider_entries(redis)
    entry_map = {e.name: e for e in entries}

    reordered: list[LLMProviderEntry] = []
    for i, name in enumerate(ordered_names):
        if name in entry_map:
            entry = entry_map.pop(name)
            entry.priority = i
            reordered.append(entry)

    # Append any entries not in the ordered list
    for entry in entry_map.values():
        entry.priority = len(reordered)
        reordered.append(entry)

    await set_provider_entries(redis, reordered)
    return reordered


async def toggle_provider(redis, name: str, enabled: bool) -> LLMProviderEntry | None:
    """Enable/disable a specific provider."""
    entries = await get_provider_entries(redis)
    target = None
    for entry in entries:
        if entry.name == name:
            entry.enabled = enabled
            target = entry
            break
    if target:
        await set_provider_entries(redis, entries)
    return target


async def update_provider_entry(
    redis, name: str, updates: dict,
) -> LLMProviderEntry | None:
    """Update timeout/retry parameters for a provider."""
    entries = await get_provider_entries(redis)
    target = None
    for entry in entries:
        if entry.name == name:
            allowed = ("timeout_seconds", "vlm_timeout_seconds", "max_retries", "qpm_limit", "tpm_limit")
            for k, v in updates.items():
                if hasattr(entry, k) and k in allowed:
                    setattr(entry, k, v)
            target = entry
            break
    if target:
        await set_provider_entries(redis, entries)
    return target
