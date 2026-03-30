import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest
from PIL import Image

from pdf_sku.common.media_variants import (
    IMAGE_VARIANTS,
    _save_variant,
    ensure_image_variant,
    image_variant_path,
)


def test_ensure_image_variant_creates_local_thumbnail(tmp_path):
    job_dir = tmp_path / "jobs" / "job-1"
    original_dir = job_dir / "images"
    original_dir.mkdir(parents=True)
    source_path = original_dir / "sample.jpg"

    Image.new("RGB", (1200, 800), color="navy").save(source_path, format="JPEG", quality=90)

    target = ensure_image_variant(job_dir, "images/sample.jpg", "sample", "thumbnail")

    assert target == image_variant_path(job_dir, "sample", "thumbnail")
    assert target.exists()

    with Image.open(target) as thumb:
        assert thumb.width <= 128
        assert thumb.height <= 128


def test_save_variant_cleans_up_temp_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "thumb.jpg"
    source = io.BytesIO()
    Image.new("RGB", (320, 240), color="teal").save(source, format="PNG")
    source.seek(0)

    saved_tmp: Path | None = None

    def fail_save(self, fp, *args, **kwargs):
        nonlocal saved_tmp
        saved_tmp = Path(fp)
        raise RuntimeError("save failed")

    monkeypatch.setattr(Image.Image, "save", fail_save)

    with pytest.raises(RuntimeError, match="save failed"):
        _save_variant(source, target, IMAGE_VARIANTS["thumbnail"])

    assert saved_tmp is not None
    assert not saved_tmp.exists()


def test_save_variant_supports_concurrent_writers(tmp_path, monkeypatch):
    target = tmp_path / "thumb.jpg"
    source = io.BytesIO()
    Image.new("RGB", (1600, 1200), color="purple").save(source, format="PNG")
    source_bytes = source.getvalue()

    original_save = Image.Image.save
    barrier = threading.Barrier(2)

    def coordinated_save(self, fp, *args, **kwargs):
        result = original_save(self, fp, *args, **kwargs)
        barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(Image.Image, "save", coordinated_save)

    def render():
        _save_variant(io.BytesIO(source_bytes), target, IMAGE_VARIANTS["thumbnail"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(render) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)

    assert target.exists()
    with Image.open(target) as thumb:
        assert thumb.width <= 128
        assert thumb.height <= 128
