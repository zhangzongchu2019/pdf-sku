"""LLM request_utils 单元测试。"""
from __future__ import annotations

import httpx
import pytest
from PIL import Image

from pdf_sku.llm_adapter.client.request_utils import (
    LLMClientRequestError,
    prepare_request,
    raise_for_status_with_context,
)
from pdf_sku.settings import settings


def _make_noisy_png(width: int = 1200, height: int = 1200) -> bytes:
    img = Image.effect_noise((width, height), 100).convert("RGB")
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_prepare_request_compresses_large_png_under_limit(monkeypatch):
    monkeypatch.setattr(settings, "llm_image_max_inline_bytes", 120_000)
    monkeypatch.setattr(settings, "llm_request_max_inline_bytes", 240_000)
    monkeypatch.setattr(settings, "llm_image_max_long_edge", 1600)
    monkeypatch.setattr(settings, "llm_image_jpeg_quality_start", 80)
    monkeypatch.setattr(settings, "llm_image_jpeg_quality_min", 40)
    monkeypatch.setattr(settings, "llm_image_resize_ratio", 0.8)
    monkeypatch.setattr(settings, "llm_image_min_edge", 256)

    prepared, metrics = prepare_request(
        provider="qwen",
        model="qwen-vl-max",
        endpoint="https://example.test/v1/chat/completions",
        prompt="return json",
        images=[_make_noisy_png()],
        json_mode=True,
        max_tokens=128,
        use_data_url=True,
    )

    assert len(prepared) == 1
    assert prepared[0].mime_type == "image/jpeg"
    assert prepared[0].inline_bytes <= settings.llm_image_max_inline_bytes
    assert metrics.total_image_inline_bytes <= settings.llm_request_max_inline_bytes


def test_prepare_request_rejects_prompt_too_long(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_max_chars", 16)

    with pytest.raises(LLMClientRequestError) as exc:
        prepare_request(
            provider="qwen",
            model="qwen-vl-max",
            endpoint="https://example.test/v1/chat/completions",
            prompt="x" * 17,
            images=[],
            json_mode=True,
            max_tokens=64,
            use_data_url=True,
        )

    assert exc.value.error_kind == "prompt_too_long"
    assert not exc.value.retryable


def test_prepare_request_rejects_too_many_images(monkeypatch):
    monkeypatch.setattr(settings, "llm_max_images_per_request", 2)
    png = _make_noisy_png(64, 64)

    with pytest.raises(LLMClientRequestError) as exc:
        prepare_request(
            provider="qwen",
            model="qwen-vl-max",
            endpoint="https://example.test/v1/chat/completions",
            prompt="ok",
            images=[png, png, png],
            json_mode=True,
            max_tokens=64,
            use_data_url=True,
        )

    assert exc.value.error_kind == "too_many_images"
    assert not exc.value.retryable


def test_raise_for_status_with_context_extracts_provider_error():
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
        json={
            "error": {
                "message": "Exceeded limit on max bytes per data-uri item : 10485760",
                "type": "invalid_request_error",
            }
        },
    )

    with pytest.raises(LLMClientRequestError) as exc:
        raise_for_status_with_context(
            response,
            provider="qwen",
            model="qwen-vl-max",
            endpoint="https://example.test/v1/chat/completions",
            request_metrics=None,
        )

    assert exc.value.error_kind == "payload_too_large"
    assert exc.value.status_code == 400
    assert "10485760" in exc.value.response_body
