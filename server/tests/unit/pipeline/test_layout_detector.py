"""Layout detector device 配置测试。"""
from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from pdf_sku.pipeline import layout_detector


def _png_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_detect_figures_passes_device_and_confidence(monkeypatch):
    captured: dict[str, object] = {}

    class DummyModel:
        def predict(self, image, **kwargs):
            captured["size"] = image.size
            captured["kwargs"] = kwargs
            return []

    holder = SimpleNamespace(
        model=DummyModel(),
        available=True,
        predict_device="cuda:0",
        load=lambda: None,
    )
    monkeypatch.setattr(layout_detector._ModelHolder, "get", classmethod(lambda cls: holder))
    monkeypatch.setattr(layout_detector.settings, "layout_detect_confidence", 0.42)

    result = layout_detector.detect_figures_on_image(_png_bytes())

    assert result == []
    assert captured["size"] == (8, 8)
    assert captured["kwargs"] == {
        "conf": 0.42,
        "verbose": False,
        "device": "cuda:0",
    }


def test_detect_all_regions_keeps_legacy_confidence(monkeypatch):
    captured: dict[str, object] = {}

    class DummyModel:
        def predict(self, image, **kwargs):
            captured["size"] = image.size
            captured["kwargs"] = kwargs
            return []

    holder = SimpleNamespace(
        model=DummyModel(),
        available=True,
        predict_device="cuda:0",
        load=lambda: None,
    )
    monkeypatch.setattr(layout_detector._ModelHolder, "get", classmethod(lambda cls: holder))
    monkeypatch.setattr(layout_detector.settings, "layout_detect_confidence", 0.42)

    result = layout_detector.detect_all_regions(_png_bytes())

    assert result == []
    assert captured["size"] == (8, 8)
    assert captured["kwargs"] == {
        "conf": 0.20,
        "verbose": False,
        "device": "cuda:0",
    }
