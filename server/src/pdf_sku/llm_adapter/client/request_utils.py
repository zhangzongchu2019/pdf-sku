"""LLM 请求预检、图片预处理和错误包装。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from pdf_sku.settings import settings

DATA_URL_PREFIX_TEMPLATE = "data:{mime};base64,"
_SUPPORTED_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass
class PreparedImage:
    data: bytes
    mime_type: str
    original_mime_type: str
    original_bytes: int
    prepared_bytes: int
    inline_bytes: int
    width: int
    height: int
    transformed: bool
    quality: int | None = None


@dataclass
class LLMRequestMetrics:
    prompt_chars: int
    prompt_bytes: int
    image_count: int
    raw_image_bytes: int
    prepared_image_bytes: int
    max_image_inline_bytes: int
    total_image_inline_bytes: int
    estimated_request_bytes: int
    json_mode: bool
    max_tokens: int

    def to_log_dict(self) -> dict[str, int | bool]:
        return {
            "prompt_chars": self.prompt_chars,
            "prompt_bytes": self.prompt_bytes,
            "image_count": self.image_count,
            "raw_image_bytes": self.raw_image_bytes,
            "prepared_image_bytes": self.prepared_image_bytes,
            "max_image_inline_bytes": self.max_image_inline_bytes,
            "total_image_inline_bytes": self.total_image_inline_bytes,
            "estimated_request_bytes": self.estimated_request_bytes,
            "json_mode": self.json_mode,
            "max_tokens": self.max_tokens,
        }


class LLMClientRequestError(Exception):
    """保留 provider 原始错误和请求上下文。"""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str,
        endpoint: str,
        error_kind: str,
        status_code: int | None = None,
        retryable: bool = True,
        allow_fallback: bool = True,
        error_type: str | None = None,
        error_code: str | None = None,
        error_param: str | None = None,
        response_body: str = "",
        request_metrics: LLMRequestMetrics | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.error_kind = error_kind
        self.status_code = status_code
        self.retryable = retryable
        self.allow_fallback = allow_fallback
        self.error_type = error_type
        self.error_code = error_code
        self.error_param = error_param
        self.response_body = response_body
        self.request_metrics = request_metrics
        self.message = message

    @property
    def degrade_reason(self) -> str:
        parts = [self.error_kind]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        parts.append(f"provider={self.provider}")
        parts.append(f"model={self.model}")
        parts.append(f"message={self.message}")
        if self.request_metrics:
            parts.append(
                "image_count="
                f"{self.request_metrics.image_count}"
            )
            parts.append(
                "max_image_inline_bytes="
                f"{self.request_metrics.max_image_inline_bytes}"
            )
            parts.append(
                "total_image_inline_bytes="
                f"{self.request_metrics.total_image_inline_bytes}"
            )
        return _truncate("llm_" + " ".join(parts), 1200)

    def to_log_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.endpoint,
            "error_kind": self.error_kind,
            "status_code": self.status_code,
            "retryable": self.retryable,
            "allow_fallback": self.allow_fallback,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "error_param": self.error_param,
            "provider_error_message": self.message,
            "provider_error_body": self.response_body,
        }
        if self.request_metrics:
            payload.update(self.request_metrics.to_log_dict())
        return payload

    def __str__(self) -> str:
        parts = [
            f"{self.provider}/{self.model}",
            self.error_kind,
        ]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        parts.append(f"message={self.message}")
        parts.append(f"endpoint={self.endpoint}")
        if self.request_metrics:
            parts.append(
                "request_metrics="
                + json.dumps(self.request_metrics.to_log_dict(), ensure_ascii=False)
            )
        if self.response_body:
            parts.append(f"provider_body={self.response_body}")
        return " | ".join(parts)


def estimate_base64_bytes(raw_bytes_len: int) -> int:
    return ((raw_bytes_len + 2) // 3) * 4


def estimate_inline_bytes(raw_bytes_len: int, mime_type: str, *, data_url: bool) -> int:
    total = estimate_base64_bytes(raw_bytes_len)
    if data_url:
        total += len(DATA_URL_PREFIX_TEMPLATE.format(mime=mime_type))
    return total


def prepare_request(
    *,
    provider: str,
    model: str,
    endpoint: str,
    prompt: str,
    images: list[bytes] | None,
    json_mode: bool,
    max_tokens: int,
    use_data_url: bool,
) -> tuple[list[PreparedImage], LLMRequestMetrics]:
    _validate_prompt(
        provider=provider,
        model=model,
        endpoint=endpoint,
        prompt=prompt,
        images=images or [],
        json_mode=json_mode,
        max_tokens=max_tokens,
    )

    raw_images = images or []
    prepared = [
        _prepare_single_image(
            provider=provider,
            model=model,
            endpoint=endpoint,
            image_bytes=img,
            target_inline_bytes=settings.llm_image_max_inline_bytes,
            use_data_url=use_data_url,
        )
        for img in raw_images
    ]

    prompt_bytes = len(prompt.encode("utf-8"))
    metrics = _build_metrics(
        prompt=prompt,
        prompt_bytes=prompt_bytes,
        raw_images=raw_images,
        prepared=prepared,
        json_mode=json_mode,
        max_tokens=max_tokens,
    )
    if metrics.total_image_inline_bytes > settings.llm_request_max_inline_bytes and prepared:
        per_image_target = max(
            256 * 1024,
            settings.llm_request_max_inline_bytes // len(prepared),
        )
        prepared = [
            _prepare_single_image(
                provider=provider,
                model=model,
                endpoint=endpoint,
                image_bytes=img,
                target_inline_bytes=min(
                    settings.llm_image_max_inline_bytes,
                    per_image_target,
                ),
                use_data_url=use_data_url,
                force_jpeg=True,
            )
            for img in raw_images
        ]
        metrics = _build_metrics(
            prompt=prompt,
            prompt_bytes=prompt_bytes,
            raw_images=raw_images,
            prepared=prepared,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )

    if metrics.total_image_inline_bytes > settings.llm_request_max_inline_bytes:
        raise LLMClientRequestError(
            (
                "Estimated inline image payload exceeds request limit "
                f"({metrics.total_image_inline_bytes} > {settings.llm_request_max_inline_bytes})"
            ),
            provider=provider,
            model=model,
            endpoint=endpoint,
            error_kind="payload_too_large",
            retryable=False,
            allow_fallback=False,
            request_metrics=metrics,
        )

    return prepared, metrics


def raise_for_status_with_context(
    response: httpx.Response,
    *,
    provider: str,
    model: str,
    endpoint: str,
    request_metrics: LLMRequestMetrics,
) -> None:
    if not response.is_error:
        return

    response_text = _truncate(response.text, settings.llm_error_body_max_chars)
    err_message, err_type, err_code, err_param = _extract_error_fields(response_text)
    retryable, allow_fallback, error_kind = _classify_http_error(
        status_code=response.status_code,
        message=err_message,
    )
    raise LLMClientRequestError(
        err_message,
        provider=provider,
        model=model,
        endpoint=endpoint,
        status_code=response.status_code,
        retryable=retryable,
        allow_fallback=allow_fallback,
        error_kind=error_kind,
        error_type=err_type,
        error_code=err_code,
        error_param=err_param,
        response_body=response_text,
        request_metrics=request_metrics,
    )


def wrap_transport_error(
    exc: Exception,
    *,
    provider: str,
    model: str,
    endpoint: str,
    request_metrics: LLMRequestMetrics,
) -> LLMClientRequestError:
    error_kind = "transport_error"
    retryable = True
    if isinstance(exc, httpx.TimeoutException):
        error_kind = "transport_timeout"
    return LLMClientRequestError(
        str(exc),
        provider=provider,
        model=model,
        endpoint=endpoint,
        error_kind=error_kind,
        retryable=retryable,
        allow_fallback=True,
        request_metrics=request_metrics,
    )


def format_exception_for_reason(exc: Exception) -> str:
    if isinstance(exc, LLMClientRequestError):
        return exc.degrade_reason
    return _truncate(f"{type(exc).__name__}: {exc}", 1200)


def _validate_prompt(
    *,
    provider: str,
    model: str,
    endpoint: str,
    prompt: str,
    images: list[bytes],
    json_mode: bool,
    max_tokens: int,
) -> None:
    metrics = LLMRequestMetrics(
        prompt_chars=len(prompt),
        prompt_bytes=len(prompt.encode("utf-8")),
        image_count=len(images),
        raw_image_bytes=sum(len(img) for img in images),
        prepared_image_bytes=0,
        max_image_inline_bytes=0,
        total_image_inline_bytes=0,
        estimated_request_bytes=len(prompt.encode("utf-8")),
        json_mode=json_mode,
        max_tokens=max_tokens,
    )
    if not prompt or not prompt.strip():
        raise LLMClientRequestError(
            "Prompt is empty after trimming",
            provider=provider,
            model=model,
            endpoint=endpoint,
            error_kind="empty_prompt",
            retryable=False,
            allow_fallback=False,
            request_metrics=metrics,
        )
    if len(prompt) > settings.llm_prompt_max_chars:
        raise LLMClientRequestError(
            (
                "Prompt exceeds configured length limit "
                f"({len(prompt)} > {settings.llm_prompt_max_chars})"
            ),
            provider=provider,
            model=model,
            endpoint=endpoint,
            error_kind="prompt_too_long",
            retryable=False,
            allow_fallback=False,
            request_metrics=metrics,
        )
    if len(images) > settings.llm_max_images_per_request:
        raise LLMClientRequestError(
            (
                "Too many images for one request "
                f"({len(images)} > {settings.llm_max_images_per_request})"
            ),
            provider=provider,
            model=model,
            endpoint=endpoint,
            error_kind="too_many_images",
            retryable=False,
            allow_fallback=False,
            request_metrics=metrics,
        )


def _build_metrics(
    *,
    prompt: str,
    prompt_bytes: int,
    raw_images: list[bytes],
    prepared: list[PreparedImage],
    json_mode: bool,
    max_tokens: int,
) -> LLMRequestMetrics:
    total_image_inline_bytes = sum(img.inline_bytes for img in prepared)
    return LLMRequestMetrics(
        prompt_chars=len(prompt),
        prompt_bytes=prompt_bytes,
        image_count=len(raw_images),
        raw_image_bytes=sum(len(img) for img in raw_images),
        prepared_image_bytes=sum(img.prepared_bytes for img in prepared),
        max_image_inline_bytes=max((img.inline_bytes for img in prepared), default=0),
        total_image_inline_bytes=total_image_inline_bytes,
        estimated_request_bytes=prompt_bytes + total_image_inline_bytes + 2048,
        json_mode=json_mode,
        max_tokens=max_tokens,
    )


def _prepare_single_image(
    *,
    provider: str,
    model: str,
    endpoint: str,
    image_bytes: bytes,
    target_inline_bytes: int,
    use_data_url: bool,
    force_jpeg: bool = False,
) -> PreparedImage:
    if not image_bytes:
        raise LLMClientRequestError(
            "Encountered an empty image payload",
            provider=provider,
            model=model,
            endpoint=endpoint,
            error_kind="empty_image",
            retryable=False,
            allow_fallback=False,
        )

    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img.load()
            original_mime = _SUPPORTED_MIME_BY_FORMAT.get((img.format or "").upper(), "image/png")
            width, height = img.size
            original_inline_bytes = estimate_inline_bytes(
                len(image_bytes),
                original_mime,
                data_url=use_data_url,
            )
            if (
                not force_jpeg
                and original_inline_bytes <= target_inline_bytes
                and max(width, height) <= settings.llm_image_max_long_edge
                and original_mime in {"image/jpeg", "image/png", "image/webp"}
            ):
                return PreparedImage(
                    data=image_bytes,
                    mime_type=original_mime,
                    original_mime_type=original_mime,
                    original_bytes=len(image_bytes),
                    prepared_bytes=len(image_bytes),
                    inline_bytes=original_inline_bytes,
                    width=width,
                    height=height,
                    transformed=False,
                )

            prepared_bytes, prepared_w, prepared_h, quality = _compress_to_jpeg(
                img,
                provider=provider,
                model=model,
                endpoint=endpoint,
                target_inline_bytes=target_inline_bytes,
                use_data_url=use_data_url,
            )
            return PreparedImage(
                data=prepared_bytes,
                mime_type="image/jpeg",
                original_mime_type=original_mime,
                original_bytes=len(image_bytes),
                prepared_bytes=len(prepared_bytes),
                inline_bytes=estimate_inline_bytes(
                    len(prepared_bytes),
                    "image/jpeg",
                    data_url=use_data_url,
                ),
                width=prepared_w,
                height=prepared_h,
                transformed=True,
                quality=quality,
            )
    except UnidentifiedImageError as exc:
        raise LLMClientRequestError(
            f"Unsupported image payload: {exc}",
            provider=provider,
            model=model,
            endpoint=endpoint,
            error_kind="invalid_image",
            retryable=False,
            allow_fallback=False,
        ) from exc


def _compress_to_jpeg(
    image: Image.Image,
    *,
    provider: str,
    model: str,
    endpoint: str,
    target_inline_bytes: int,
    use_data_url: bool,
) -> tuple[bytes, int, int, int]:
    image_rgb = _normalize_image(image)
    current = _resize_if_needed(image_rgb, settings.llm_image_max_long_edge)
    last_inline_bytes = estimate_inline_bytes(
        len(image.tobytes()),
        "image/jpeg",
        data_url=use_data_url,
    )

    while True:
        for quality in range(
            settings.llm_image_jpeg_quality_start,
            settings.llm_image_jpeg_quality_min - 1,
            -5,
        ):
            buf = BytesIO()
            current.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            inline_bytes = estimate_inline_bytes(
                len(data),
                "image/jpeg",
                data_url=use_data_url,
            )
            last_inline_bytes = inline_bytes
            if inline_bytes <= target_inline_bytes:
                return data, current.width, current.height, quality

        if min(current.size) <= settings.llm_image_min_edge:
            break

        new_width = max(1, int(current.width * settings.llm_image_resize_ratio))
        new_height = max(1, int(current.height * settings.llm_image_resize_ratio))
        if min(new_width, new_height) < settings.llm_image_min_edge:
            break
        if (new_width, new_height) == current.size:
            break
        current = current.resize((new_width, new_height), Image.LANCZOS)

    raise LLMClientRequestError(
        (
            "Image could not be compressed under configured inline limit "
            f"({last_inline_bytes} > {target_inline_bytes})"
        ),
        provider=provider,
        model=model,
        endpoint=endpoint,
        error_kind="payload_too_large",
        retryable=False,
        allow_fallback=False,
    )


def _normalize_image(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        alpha_source = image.convert("RGBA")
        background = Image.new("RGB", alpha_source.size, (255, 255, 255))
        background.paste(alpha_source, mask=alpha_source.getchannel("A"))
        return background
    return image.convert("RGB")


def _resize_if_needed(image: Image.Image, max_long_edge: int) -> Image.Image:
    if max(image.size) <= max_long_edge:
        return image
    scale = max_long_edge / max(image.size)
    new_size = (
        max(1, int(image.width * scale)),
        max(1, int(image.height * scale)),
    )
    return image.resize(new_size, Image.LANCZOS)


def _extract_error_fields(response_text: str) -> tuple[str, str | None, str | None, str | None]:
    message = response_text.strip()
    error_type = None
    error_code = None
    error_param = None
    try:
        payload = json.loads(response_text)
    except Exception:
        return message or "HTTP request failed", error_type, error_code, error_param

    error_obj: Any = payload.get("error", payload)
    if isinstance(error_obj, dict):
        message = str(
            error_obj.get("message")
            or payload.get("message")
            or message
            or "HTTP request failed"
        )
        error_type = error_obj.get("type")
        error_code = error_obj.get("code")
        error_param = error_obj.get("param")
    else:
        message = str(payload.get("message") or message or "HTTP request failed")
    return _truncate(message, settings.llm_error_body_max_chars), error_type, error_code, error_param


def _classify_http_error(status_code: int, message: str) -> tuple[bool, bool, str]:
    lowered = message.lower()
    if "max bytes per data-uri item" in lowered:
        return False, False, "payload_too_large"
    if status_code in (400, 404, 422):
        return False, True, "invalid_request"
    if status_code in (401, 403):
        return False, False, "auth_error"
    if status_code == 429:
        return True, True, "rate_limited"
    if status_code >= 500:
        return True, True, "provider_error"
    return True, True, "provider_http_error"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."
