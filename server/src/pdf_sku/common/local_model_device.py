"""本地模型 device 解析与运行时环境准备。"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import structlog

from pdf_sku.settings import settings

logger = structlog.get_logger()

_CUDA_ENV_LOCK = threading.Lock()


@dataclass(frozen=True)
class LocalModelDevice:
    """统一描述本地模型的设备选择。"""

    requested: str
    layout_device: str | None
    ocr_use_cuda: bool
    cuda_visible_devices: str | None


def resolve_local_model_device(device: str | None = None) -> LocalModelDevice:
    """解析统一的本地模型设备配置。

    支持:
    - auto: 保持原有行为; OCR 仍优先尝试 CUDA, Layout 保持框架默认选择
    - cpu: 强制 CPU
    - cuda: 使用默认 CUDA 设备
    - cuda:N: 通过 CUDA_VISIBLE_DEVICES 选择物理 GPU N
    - mps: Layout 使用 MPS，OCR 回退 CPU
    """
    raw = (device if device is not None else settings.local_model_device).strip().lower()
    if not raw or raw == "auto":
        # 保持改动前的默认策略: OCR 先尝试 CUDA, 失败后仍在调用方回退 CPU。
        return LocalModelDevice(
            requested="auto",
            layout_device=None,
            ocr_use_cuda=True,
            cuda_visible_devices=None,
        )

    if raw == "cpu":
        return LocalModelDevice(
            requested="cpu",
            layout_device="cpu",
            ocr_use_cuda=False,
            cuda_visible_devices=None,
        )

    if raw == "cuda":
        return LocalModelDevice(
            requested="cuda",
            layout_device="cuda",
            ocr_use_cuda=True,
            cuda_visible_devices=None,
        )

    if raw.startswith("cuda:"):
        _, _, index = raw.partition(":")
        if index.isdigit():
            return LocalModelDevice(
                requested=raw,
                layout_device="cuda:0",
                ocr_use_cuda=True,
                cuda_visible_devices=index,
            )

    if raw == "mps":
        return LocalModelDevice(
            requested="mps",
            layout_device="mps",
            ocr_use_cuda=False,
            cuda_visible_devices=None,
        )

    logger.warning("local_model_device_invalid", requested_device=raw, fallback="auto")
    return LocalModelDevice(
        requested="auto",
        layout_device=None,
        ocr_use_cuda=True,
        cuda_visible_devices=None,
    )


def prepare_local_model_environment(
    device: LocalModelDevice | None = None,
) -> LocalModelDevice:
    """为本地模型准备运行时环境。

    `cuda:N` 依赖 `CUDA_VISIBLE_DEVICES` 将物理卡号映射为框架里的逻辑 `cuda:0`。
    """
    resolved = device or resolve_local_model_device()
    if resolved.cuda_visible_devices is None:
        return resolved

    with _CUDA_ENV_LOCK:
        current = os.environ.get("CUDA_VISIBLE_DEVICES")
        if current != resolved.cuda_visible_devices:
            if current:
                logger.warning(
                    "local_model_cuda_visible_devices_override",
                    previous=current,
                    new=resolved.cuda_visible_devices,
                )
            os.environ["CUDA_VISIBLE_DEVICES"] = resolved.cuda_visible_devices
            logger.info(
                "local_model_cuda_visible_devices_set",
                requested_device=resolved.requested,
                cuda_visible_devices=resolved.cuda_visible_devices,
            )

    return resolved
