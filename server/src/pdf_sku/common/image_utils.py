"""Image helpers shared by pipeline and gateway."""
from __future__ import annotations

import io

from PIL import Image as PILImage
from PIL import ImageOps

WHITE_RGB = (255, 255, 255)


def image_has_transparency(im: PILImage.Image) -> bool:
    """Return True when the image contains alpha/transparency information."""
    if im.mode in ("RGBA", "LA"):
        alpha = im.getchannel("A")
        lo, _hi = alpha.getextrema()
        return lo < 255
    if im.mode == "P":
        return "transparency" in im.info
    return False


def flatten_for_jpeg(
    im: PILImage.Image,
    background_rgb: tuple[int, int, int] = WHITE_RGB,
) -> PILImage.Image:
    """Convert images to a JPEG-safe mode, compositing transparency onto a background."""
    normalized = ImageOps.exif_transpose(im)
    if image_has_transparency(normalized):
        rgba = normalized.convert("RGBA")
        bg = PILImage.new("RGBA", rgba.size, (*background_rgb, 255))
        return PILImage.alpha_composite(bg, rgba).convert("RGB")
    if normalized.mode in ("RGB", "L"):
        return normalized
    return normalized.convert("RGB")


def encode_as_jpeg(
    data: bytes,
    *,
    max_edge: int | None = None,
    quality: int = 85,
    background_rgb: tuple[int, int, int] = WHITE_RGB,
) -> bytes:
    """Load image bytes, flatten transparency if needed, and encode to JPEG."""
    with PILImage.open(io.BytesIO(data)) as im:
        normalized = flatten_for_jpeg(im, background_rgb=background_rgb)
        if max_edge and max(normalized.size) > max_edge:
            normalized.thumbnail((max_edge, max_edge), PILImage.LANCZOS)
        out = io.BytesIO()
        normalized.save(out, "JPEG", quality=quality)
        return out.getvalue()
