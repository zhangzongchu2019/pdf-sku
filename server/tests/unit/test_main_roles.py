from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pdf_sku.llm_adapter.provider_config import LLMProviderEntry
from pdf_sku.main import _bootstrap_worker_llm_clients, create_app
from pdf_sku.settings import settings


def test_create_app_worker_role_exposes_health_only():
    with patch("pdf_sku.main.settings.run_role", "worker-eval"), patch("pdf_sku.main.settings.app_env", "test"):
        app = create_app()

    paths = {route.path for route in app.routes}
    assert "/api/v1/health" in paths
    assert "/api/v1/jobs" not in paths
    assert "/openapi.json" not in paths


def test_create_app_api_role_includes_business_routes():
    with patch("pdf_sku.main.settings.run_role", "api"), patch("pdf_sku.main.settings.app_env", "test"):
        app = create_app()

    paths = {route.path for route in app.routes}
    assert "/api/v1/health" in paths
    assert "/api/v1/jobs" in paths


@pytest.mark.asyncio
async def test_bootstrap_worker_llm_clients_registers_named_provider_and_alias(monkeypatch):
    entry = LLMProviderEntry(
        name="gemini-3-pro-preview.llm.ai-nebula.com",
        provider_type="gemini",
        access_mode="proxy",
        model="gemini-3-pro-preview",
        account_name="nebula",
    )
    registered = []

    class DummySessionFactory:
        def __call__(self):
            class _Ctx:
                async def __aenter__(self):
                    return object()

                async def __aexit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    async def fake_get_provider_entries(_redis):
        return [entry]

    async def fake_get_account_api_key(_db, _account_name, _jwt_secret):
        return ("secret-key", "https://llm.ai-nebula.com/v1")

    class FakeOpenAICompatClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(settings, "jwt_secret_key", "test-secret")
    monkeypatch.setattr("pdf_sku.llm_adapter.provider_config.get_provider_entries", fake_get_provider_entries)
    monkeypatch.setattr("pdf_sku.llm_adapter.account_service.get_account_api_key", fake_get_account_api_key)
    monkeypatch.setattr("pdf_sku.llm_adapter.client.openai_compat.OpenAICompatClient", FakeOpenAICompatClient)
    monkeypatch.setattr(
        "pdf_sku.llm_adapter.client.registry.register",
        lambda name, client: registered.append((name, client)),
    )
    monkeypatch.setattr("pdf_sku.llm_adapter.client.registry.get_client", lambda _name: None)

    await _bootstrap_worker_llm_clients(DummySessionFactory(), object())

    assert [name for name, _client in registered] == [
        "gemini-3-pro-preview.llm.ai-nebula.com",
        "gemini",
    ]
    provider_client = registered[0][1]
    assert isinstance(provider_client, FakeOpenAICompatClient)
    assert provider_client.kwargs["model"] == "gemini-3-pro-preview"
    assert provider_client.kwargs["api_base"] == "https://llm.ai-nebula.com/v1"
