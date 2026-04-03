import io

import fitz
from PIL import Image

from pdf_sku.pipeline.parser.adapter import PDFExtractor


def _make_transparent_png(size: tuple[int, int] = (80, 80)) -> bytes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(16, 64):
        for y in range(12, 68):
            img.putpixel((x, y), (40, 120, 220, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extract_fitz_image_preserves_soft_mask_transparency(tmp_path):
    pdf_path = tmp_path / "transparent-image.pdf"
    png_bytes = _make_transparent_png()

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 20), "Transparent image sample", fontsize=12)
    page.insert_image(fitz.Rect(30, 40, 110, 120), stream=png_bytes)
    doc.save(pdf_path)
    doc.close()

    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        images = page.get_images(full=True)
        assert images
        assert images[0][1] > 0

        img_data, width, height = PDFExtractor._extract_fitz_image(doc, images[0])
        assert width == 80
        assert height == 80

        extracted = Image.open(io.BytesIO(img_data)).convert("RGBA")
        assert extracted.getpixel((1, 1))[3] < 10
        assert extracted.getpixel((40, 40))[3] == 255
    finally:
        doc.close()


def test_extract_pymupdf_uses_soft_mask_aware_image_data(tmp_path):
    pdf_path = tmp_path / "transparent-page.pdf"
    png_bytes = _make_transparent_png()

    doc = fitz.open()
    page = doc.new_page(width=220, height=220)
    page.insert_text((20, 20), "Transparent image sample", fontsize=12)
    page.insert_image(fitz.Rect(40, 60, 120, 140), stream=png_bytes)
    doc.save(pdf_path)
    doc.close()

    extractor = PDFExtractor()
    result = extractor._extract_pymupdf(str(pdf_path), 1)

    assert result.images
    extracted = Image.open(io.BytesIO(result.images[0].data)).convert("RGBA")
    assert extracted.getpixel((1, 1))[3] < 10
    assert extracted.getpixel((40, 40))[3] == 255
