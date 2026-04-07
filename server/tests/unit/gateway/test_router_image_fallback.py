from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.responses import FileResponse

from pdf_sku.gateway import router


class _ScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DBStub:
    def __init__(self, image=None):
        self._image = image

    async def execute(self, _query):
        return _ScalarResult(self._image)


@pytest.mark.asyncio
async def test_get_job_image_falls_back_to_disk_when_db_record_missing(tmp_path, monkeypatch):
    job_id = uuid4()
    job_dir = tmp_path / str(job_id)
    image_dir = job_dir / "images"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "p1_scene_0.jpg"
    image_path.write_bytes(b"fake-jpeg")

    async def _noop_get_job_checked(db, jid, user):
        return None

    monkeypatch.setattr(router.settings, "job_data_dir", str(tmp_path))
    monkeypatch.setattr(router, "_get_job_checked", _noop_get_job_checked)

    response = await router.get_job_image(
        job_id=job_id,
        image_id="p1_scene_0",
        db=_DBStub(),
        user=SimpleNamespace(role="admin", merchant_id=None),
        size="full",
    )

    assert isinstance(response, FileResponse)
    assert Path(response.path) == image_path


@pytest.mark.asyncio
async def test_get_job_image_prefers_current_job_image_over_db_extracted_path(tmp_path, monkeypatch):
    job_id = uuid4()
    job_dir = tmp_path / str(job_id)
    image_dir = job_dir / "images"
    legacy_dir = job_dir / "legacy"
    image_dir.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)

    current_path = image_dir / "p1_scene_0.jpg"
    current_path.write_bytes(b"new-jpeg")
    legacy_path = legacy_dir / "p1_scene_0.jpg"
    legacy_path.write_bytes(b"old-jpeg")

    async def _noop_get_job_checked(db, jid, user):
        return None

    monkeypatch.setattr(router.settings, "job_data_dir", str(tmp_path))
    monkeypatch.setattr(router, "_get_job_checked", _noop_get_job_checked)

    db_image = SimpleNamespace(extracted_path="legacy/p1_scene_0.jpg", format="jpeg")
    response = await router.get_job_image(
        job_id=job_id,
        image_id="p1_scene_0",
        db=_DBStub(image=db_image),
        user=SimpleNamespace(role="admin", merchant_id=None),
        size="full",
    )

    assert isinstance(response, FileResponse)
    assert Path(response.path) == current_path


@pytest.mark.asyncio
async def test_get_job_image_regenerates_stale_thumbnail_cache(tmp_path, monkeypatch):
    job_id = uuid4()
    job_dir = tmp_path / str(job_id)
    image_dir = job_dir / "images"
    cache_dir = image_dir / ".cache"
    image_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    image_path = image_dir / "p1_scene_0.jpg"
    image_path.write_bytes(b"new-image")
    cache_path = cache_dir / "p1_scene_0_thumb.jpg"
    cache_path.write_bytes(b"stale-cache")

    stale_time = image_path.stat().st_mtime - 100
    cache_path.touch()
    import os

    os.utime(cache_path, (stale_time, stale_time))

    called = {"count": 0}

    def _fake_generate_thumbnail(file_path: Path, cache_dir: Path, cache_path: Path, max_edge: int, quality: int) -> Path:
        called["count"] += 1
        cache_path.write_bytes(b"fresh-cache")
        return cache_path

    async def _noop_get_job_checked(db, jid, user):
        return None

    monkeypatch.setattr(router.settings, "job_data_dir", str(tmp_path))
    monkeypatch.setattr(router, "_get_job_checked", _noop_get_job_checked)
    monkeypatch.setattr(router, "_generate_thumbnail", _fake_generate_thumbnail)

    response = await router.get_job_image(
        job_id=job_id,
        image_id="p1_scene_0",
        db=_DBStub(),
        user=SimpleNamespace(role="admin", merchant_id=None),
        size="thumb",
    )

    assert isinstance(response, FileResponse)
    assert Path(response.path) == cache_path
    assert called["count"] == 1
    assert cache_path.read_bytes() == b"fresh-cache"
