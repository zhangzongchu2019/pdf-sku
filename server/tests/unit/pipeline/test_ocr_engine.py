"""OCR engine device 配置测试。"""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from pdf_sku.pipeline.parser import ocr_engine


def test_ocr_holder_load_uses_cuda_flags(monkeypatch):
    captured: list[dict[str, object]] = []

    class FakeRapidOCR:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    fake_module = ModuleType("rapidocr_onnxruntime")
    fake_module.RapidOCR = FakeRapidOCR

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", fake_module)
    monkeypatch.setattr(ocr_engine, "_ensure_nvidia_libs", lambda: None)
    monkeypatch.setattr(
        ocr_engine,
        "prepare_local_model_environment",
        lambda: SimpleNamespace(
            requested="cuda:1",
            ocr_use_cuda=True,
            cuda_visible_devices="1",
        ),
    )
    ocr_engine._OcrHolder._instance = None

    holder = ocr_engine._OcrHolder.get()
    holder.load()

    assert holder.available is True
    assert captured == [
        {
            "det_use_cuda": True,
            "rec_use_cuda": True,
            "cls_use_cuda": True,
        }
    ]
