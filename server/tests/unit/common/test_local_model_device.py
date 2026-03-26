"""本地模型 device 解析测试。"""
import os

from pdf_sku.common.local_model_device import (
    prepare_local_model_environment,
    resolve_local_model_device,
)


def test_resolve_local_model_device_cpu():
    resolved = resolve_local_model_device("cpu")
    assert resolved.requested == "cpu"
    assert resolved.layout_device == "cpu"
    assert resolved.ocr_use_cuda is False
    assert resolved.cuda_visible_devices is None


def test_resolve_local_model_device_auto_preserves_legacy_gpu_fallback():
    resolved = resolve_local_model_device("auto")
    assert resolved.requested == "auto"
    assert resolved.layout_device is None
    assert resolved.ocr_use_cuda is True
    assert resolved.cuda_visible_devices is None


def test_resolve_local_model_device_cuda_index():
    resolved = resolve_local_model_device("cuda:2")
    assert resolved.requested == "cuda:2"
    assert resolved.layout_device == "cuda:0"
    assert resolved.ocr_use_cuda is True
    assert resolved.cuda_visible_devices == "2"


def test_prepare_local_model_environment_sets_visible_device(monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    resolved = prepare_local_model_environment(resolve_local_model_device("cuda:3"))
    assert resolved.cuda_visible_devices == "3"
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "3"
