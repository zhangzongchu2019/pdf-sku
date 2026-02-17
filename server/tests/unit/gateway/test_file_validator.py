import pytest
import fitz
from pathlib import Path
from pdf_sku.gateway.file_validator import FileValidator

@pytest.fixture
def validator():
    return FileValidator()

@pytest.fixture
def good_pdf(tmp_path) -> Path:
    p = tmp_path / "good.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world")
    doc.save(str(p)); doc.close()
    return p

@pytest.fixture
def empty_file(tmp_path) -> Path:
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf")
    return p

@pytest.mark.asyncio
async def test_valid_pdf(validator, good_pdf):
    result = await validator.validate(good_pdf)
    assert result.valid is True
    assert result.page_count == 1

@pytest.mark.asyncio
async def test_invalid_mime(validator, empty_file):
    result = await validator.validate(empty_file)
    assert result.valid is False
    assert any(e.code == "INVALID_MIME" for e in result.errors)

@pytest.mark.asyncio
async def test_multi_page(validator, tmp_path):
    p = tmp_path / "multi.pdf"
    doc = fitz.open()
    for _ in range(5): doc.new_page()
    doc.save(str(p)); doc.close()
    result = await validator.validate(p)
    assert result.valid is True
    assert result.page_count == 5
