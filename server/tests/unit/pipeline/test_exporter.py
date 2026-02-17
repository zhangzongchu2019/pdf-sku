"""SKUIdGenerator + SKUExporter 测试。"""
import pytest
from pdf_sku.pipeline.ir import SKUResult
from pdf_sku.pipeline.exporter.exporter import SKUIdGenerator, SKUExporter


def test_id_assignment_sorted():
    gen = SKUIdGenerator()
    skus = [
        SKUResult(source_bbox=(10, 300, 200, 400)),
        SKUResult(source_bbox=(10, 100, 200, 200)),
        SKUResult(source_bbox=(10, 500, 200, 600)),
    ]
    result = gen.assign_ids(skus, "abc12345", 1, page_height=800)
    # Should be sorted by y coordinate
    assert result[0].sku_id == "abc12345_001_001"
    assert result[0].source_bbox[1] == 100  # y=100 first
    assert result[1].source_bbox[1] == 300
    assert result[2].source_bbox[1] == 500


@pytest.mark.asyncio
async def test_exporter_filters_invalid():
    exporter = SKUExporter()
    skus = [
        SKUResult(sku_id="s1", validity="valid", attributes={"name": "A"}, confidence=0.9),
        SKUResult(sku_id="s2", validity="invalid", attributes={}, confidence=0.1),
    ]
    exported = await exporter.export(skus, "job1", 1)
    assert len(exported) == 1
    assert exported[0]["sku_id"] == "s1"
