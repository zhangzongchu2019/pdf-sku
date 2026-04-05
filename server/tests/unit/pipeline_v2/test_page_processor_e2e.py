"""pipeline_v2 真实 PDF 端到端测试。"""
from __future__ import annotations

import io

import fitz
import pytest
from PIL import Image as PILImage

from pdf_sku.pipeline_v2.page_processor import PageProcessor


def _make_table_pdf(path) -> str:
    doc = fitz.open()

    page1 = doc.new_page(width=500, height=700)
    headers = ["Name", "Price", "Color"]
    row1 = ["Cloud Sofa", "899", "Ivory"]
    x_positions = [40, 220, 340]

    for x, header in zip(x_positions, headers, strict=False):
        page1.insert_text((x, 60), header, fontsize=12)
    for x, value in zip(x_positions, row1, strict=False):
        page1.insert_text((x, 110), value, fontsize=12)

    page2 = doc.new_page(width=500, height=700)
    row2 = ["Hill Sofa", "1299", "Ash Gray"]
    for x, value in zip(x_positions, row2, strict=False):
        page2.insert_text((x, 60), value, fontsize=12)

    doc.save(path)
    doc.close()
    return str(path)


def _make_regular_pdf(path) -> str:
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((40, 60), "Cloud Sofa", fontsize=16)
    page.insert_text((40, 95), "Price: 899", fontsize=12)
    page.insert_text((40, 125), "Color: Ivory", fontsize=12)

    image = PILImage.new("RGB", (240, 240), color=(230, 230, 230))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    page.insert_image(fitz.Rect(260, 40, 500, 280), stream=buf.getvalue())

    doc.save(path)
    doc.close()
    return str(path)


@pytest.mark.asyncio
async def test_v2_processes_real_table_pdf_with_header_inheritance(tmp_path):
    pdf_path = _make_table_pdf(tmp_path / "table.pdf")
    processor = PageProcessor()

    result = await processor.process_page(
        job_id="e2e-table",
        file_path=pdf_path,
        page_no=2,
        file_hash="table123",
    )

    assert result.status == "AI_COMPLETED"
    assert result.page_type == "A"
    assert result.extraction_method == "table_schema_v2"
    assert len(result.skus) == 1
    attrs = result.skus[0].attributes
    assert attrs["product_name"] == "Hill Sofa"
    assert attrs["price"] == "1299"
    assert attrs["color"] == "Ash Gray"

    processor.clear_job_cache("e2e-table")


@pytest.mark.asyncio
async def test_v2_processes_real_regular_pdf(tmp_path):
    pdf_path = _make_regular_pdf(tmp_path / "regular.pdf")
    processor = PageProcessor()

    result = await processor.process_page(
        job_id="e2e-regular",
        file_path=pdf_path,
        page_no=1,
        file_hash="regular12",
    )

    assert result.status == "AI_COMPLETED"
    assert result.extraction_method == "region_rule_v2"
    assert len(result.skus) == 1
    assert result.skus[0].attributes["product_name"] == "Cloud Sofa"
    assert result.skus[0].attributes["price"] == "899"
    assert result.skus[0].attributes["color"] == "Ivory"
    assert result.bindings and result.bindings[0].image_id is not None

    processor.clear_job_cache("e2e-regular")
