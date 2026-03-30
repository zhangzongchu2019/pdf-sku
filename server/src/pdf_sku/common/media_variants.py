from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


_RESAMPLING = getattr(Image, "Resampling", Image)


@dataclass(frozen=True)
class RasterVariantSpec:
    folder: str
    max_width: int
    max_height: int
    quality: int
    suffix: str = "jpg"
    media_type: str = "image/jpeg"


PAGE_VARIANTS: dict[str, RasterVariantSpec] = {
    "thumbnail": RasterVariantSpec(
        folder="screenshots/thumbnail", max_width=240, max_height=320, quality=70,
    ),
    "preview": RasterVariantSpec(
        folder="screenshots/preview", max_width=1440, max_height=2048, quality=82,
    ),
}

IMAGE_VARIANTS: dict[str, RasterVariantSpec] = {
    "thumbnail": RasterVariantSpec(
        folder="images/thumbnail", max_width=128, max_height=128, quality=72,
    ),
    "preview": RasterVariantSpec(
        folder="images/preview", max_width=480, max_height=480, quality=82,
    ),
}

_DERIVED_CACHE_CONTROL = "public, max-age=604800, immutable"
_ORIGINAL_CACHE_CONTROL = "private, max-age=300"


def derived_cache_headers() -> dict[str, str]:
    return {"Cache-Control": _DERIVED_CACHE_CONTROL}


def original_cache_headers() -> dict[str, str]:
    return {"Cache-Control": _ORIGINAL_CACHE_CONTROL}


def page_variant_path(job_dir: Path, page_number: int, variant: str) -> Path:
    spec = PAGE_VARIANTS[variant]
    return job_dir / spec.folder / f"page-{page_number}.{spec.suffix}"


def image_variant_path(job_dir: Path, image_id: str, variant: str) -> Path:
    spec = IMAGE_VARIANTS[variant]
    return job_dir / spec.folder / f"{image_id}.{spec.suffix}"


def ensure_page_variant(
    job_dir: Path,
    source_pdf: Path,
    page_number: int,
    variant: str,
) -> Path:
    spec = PAGE_VARIANTS[variant]
    target = page_variant_path(job_dir, page_number, variant)
    if target.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(source_pdf)
    try:
        pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), alpha=False)
        _save_variant(io.BytesIO(pix.tobytes("png")), target, spec)
    finally:
        doc.close()
    return target


def ensure_image_variant(
    job_dir: Path,
    original_rel_path: str,
    image_id: str,
    variant: str,
) -> Path:
    spec = IMAGE_VARIANTS[variant]
    target = image_variant_path(job_dir, image_id, variant)
    if target.exists():
        return target

    source = job_dir / original_rel_path
    if not source.exists():
        raise FileNotFoundError(source)

    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as fh:
        _save_variant(fh, target, spec)
    return target


def precompute_page_variants(job_dir: Path, source_pdf: Path, page_number: int) -> None:
    for variant in PAGE_VARIANTS:
        ensure_page_variant(job_dir, source_pdf, page_number, variant)


def precompute_image_variants(job_dir: Path, original_rel_path: str, image_id: str) -> None:
    for variant in IMAGE_VARIANTS:
        ensure_image_variant(job_dir, original_rel_path, image_id, variant)


def _save_variant(source_stream, target: Path, spec: RasterVariantSpec) -> None:
    with Image.open(source_stream) as img:
        image = img.convert("RGB")
        image.thumbnail((spec.max_width, spec.max_height), _RESAMPLING.LANCZOS)
        fd, tmp_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            image.save(tmp, format="JPEG", quality=spec.quality, optimize=True)
            os.replace(tmp, target)
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
