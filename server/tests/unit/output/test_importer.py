"""IncrementalImporter 测试 (无 DB)。"""
import pytest
from pdf_sku.output.importer import IncrementalImporter
from pdf_sku.output.import_adapter import ImportAdapter
from pdf_sku.pipeline.ir import PageResult, SKUResult


def test_build_payload():
    sku = SKUResult(
        sku_id="abc_001_001",
        attributes={"product_name": "Widget"},
        confidence=0.9,
        extraction_method="two_stage",
    )
    payload = IncrementalImporter._build_payload(sku, "job1", 1)
    assert payload["sku_id"] == "abc_001_001"
    assert payload["job_id"] == "job1"
    assert payload["page_number"] == 1
    assert payload["attributes"]["product_name"] == "Widget"


def test_no_valid_skus():
    """无 valid SKU 时不需要导入。"""
    result = PageResult(
        status="AI_COMPLETED",
        skus=[SKUResult(validity="invalid")],
    )
    # valid_skus filter
    valid = [s for s in result.skus if s.validity == "valid"]
    assert len(valid) == 0
