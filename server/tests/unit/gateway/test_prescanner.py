import pytest
import fitz
from pdf_sku.gateway.prescanner import Prescanner, PrescanRuleConfig

@pytest.fixture
def prescanner():
    return Prescanner()

@pytest.fixture
def text_pdf(tmp_path) -> str:
    p = tmp_path / "text.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Product catalog page {i+1}\nSKU-001 Widget $29.99\n" * 5)
    doc.save(str(p)); doc.close()
    return str(p)

@pytest.fixture
def blank_pdf(tmp_path) -> str:
    p = tmp_path / "blank.pdf"
    doc = fitz.open()
    for _ in range(3): doc.new_page()
    doc.save(str(p)); doc.close()
    return str(p)

@pytest.mark.asyncio
async def test_normal_pdf(prescanner, text_pdf):
    result = await prescanner.scan(text_pdf)
    assert result.all_blank is False
    assert result.raw_metrics["total_pages"] == 2
    assert result.raw_metrics["ocr_rate"] == 1.0

@pytest.mark.asyncio
async def test_all_blank(prescanner, blank_pdf):
    result = await prescanner.scan(blank_pdf)
    assert result.all_blank is True
    assert len(result.blank_pages) == 3

@pytest.mark.asyncio
async def test_penalties(prescanner, blank_pdf):
    result = await prescanner.scan(blank_pdf, PrescanRuleConfig(min_ocr_rate=0.5))
    assert result.total_penalty > 0

@pytest.mark.asyncio
async def test_raw_metrics_keys(prescanner, text_pdf):
    result = await prescanner.scan(text_pdf)
    assert {"total_pages", "blank_page_count", "blank_rate", "ocr_rate", "image_count"}.issubset(result.raw_metrics.keys())
