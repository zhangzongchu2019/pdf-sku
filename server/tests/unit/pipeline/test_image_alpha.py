import io

from PIL import Image

from pdf_sku.pipeline.ir import BindingResult, ImageInfo, SKUResult
from pdf_sku.pipeline.orchestrator import Orchestrator
from pdf_sku.pipeline.page_processor import PageProcessor


def _make_transparent_png(size: tuple[int, int] = (64, 64)) -> bytes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(16, 48):
        for y in range(16, 48):
            img.putpixel((x, y), (220, 30, 30, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_rgb_jpeg(
    size: tuple[int, int] = (64, 64),
    color: tuple[int, int, int] = (240, 240, 240),
) -> bytes:
    img = Image.new("RGB", size, color)
    for x in range(16, 48):
        for y in range(16, 48):
            img.putpixel((x, y), (220, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_compress_image_flattens_transparent_png_to_white_jpeg():
    out = Orchestrator._compress_image(_make_transparent_png(), max_edge=2000, quality=95)
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "JPEG"
        px = img.convert("RGB").getpixel((4, 4))
        assert px[0] >= 240 and px[1] >= 240 and px[2] >= 240


def test_apply_scene_crops_uses_page_background_for_transparent_source():
    original_img = ImageInfo(
        image_id="orig",
        bbox=(0, 0, 100, 100),
        data=_make_transparent_png((100, 100)),
        width=100,
        height=100,
        short_edge=100,
        role="unknown",
        search_eligible=True,
    )
    skus = [
        SKUResult(
            sku_id="sku-1",
            attributes={"product_name": "透明底单椅"},
            validity="valid",
        )
    ]
    bindings = [
        BindingResult(
            sku_id="sku-1",
            image_id="orig",
            confidence=0.90,
        )
    ]

    page_bg = (210, 225, 235)
    new_images, _ = PageProcessor._apply_scene_crops(
        original_img=original_img,
        regions=[{"label": "主图", "bbox": [0.05, 0.05, 0.95, 0.95]}],
        skus=skus,
        bindings=bindings,
        page_no=1,
        screenshot=_make_rgb_jpeg((100, 100), color=page_bg),
    )

    assert len(new_images) == 1
    with Image.open(io.BytesIO(new_images[0].data)) as img:
        px = img.convert("RGB").getpixel((2, 2))
        assert abs(px[0] - page_bg[0]) <= 20
        assert abs(px[1] - page_bg[1]) <= 20
        assert abs(px[2] - page_bg[2]) <= 20
