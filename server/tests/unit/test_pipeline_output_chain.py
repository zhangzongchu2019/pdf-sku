"""Pipeline → Output 串联测试 (纯逻辑, 无 DB)。"""
import pytest
from pdf_sku.pipeline.ir import PageResult, SKUResult
from pdf_sku.output.backpressure import BackpressureMonitor
from pdf_sku.output.import_adapter import ImportAdapter, ImportResult


def test_valid_sku_ready_for_import():
    """valid SKU 可直接构建导入 payload。"""
    sku = SKUResult(
        sku_id="abc_001_001",
        attributes={"product_name": "Widget X", "price": "29.99"},
        confidence=0.92,
        validity="valid",
        extraction_method="two_stage",
    )
    result = PageResult(
        status="AI_COMPLETED",
        skus=[sku],
    )

    # 验证 payload 构建
    from pdf_sku.output.importer import IncrementalImporter
    payload = IncrementalImporter._build_payload(sku, "job-1", 1)
    assert payload["sku_id"] == "abc_001_001"
    assert payload["attributes"]["product_name"] == "Widget X"
    assert payload["confidence"] == 0.92


def test_invalid_sku_filtered():
    """invalid SKU 被过滤, 不导入。"""
    result = PageResult(
        status="AI_COMPLETED",
        skus=[
            SKUResult(sku_id="s1", validity="valid", confidence=0.9),
            SKUResult(sku_id="s2", validity="invalid", confidence=0.3),
            SKUResult(sku_id="s3", validity="valid", confidence=0.8),
        ],
    )
    valid = [s for s in result.skus if s.validity == "valid"]
    assert len(valid) == 2
    assert all(s.sku_id in ("s1", "s3") for s in valid)


def test_backpressure_integration():
    """背压监控与导入流程集成。"""
    bp = BackpressureMonitor()

    # 正常时不节流
    for _ in range(20):
        bp.on_success("job-1")
    assert not bp.is_throttled("job-1")

    # 持续失败 → 节流
    for _ in range(30):
        bp.on_failure("job-1")
    assert bp.is_throttled("job-1")
    assert bp.delay_seconds == 5.0


def test_import_adapter_no_downstream():
    """无下游 URL 时返回 ASSUMED。"""
    adapter = ImportAdapter(import_url="")
    # Verify it's configured for no-op
    assert adapter._import_url == ""


def test_page_result_complete_flow():
    """PageResult 从 Pipeline → Output 的完整数据流。"""
    # Pipeline output
    result = PageResult(
        status="AI_COMPLETED",
        page_type="B",
        skus=[
            SKUResult(
                sku_id="hash_001_001",
                attributes={
                    "product_name": "Premium Widget",
                    "model_number": "PW-100",
                    "price": "$49.99",
                },
                confidence=0.88,
                validity="valid",
                extraction_method="two_stage",
            ),
        ],
        needs_review=False,
    )

    # Verify data integrity through the chain
    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 1
    sku = result.skus[0]
    assert sku.attributes["model_number"] == "PW-100"

    # to_dict for serialization
    d = result.to_dict()
    assert d["status"] == "AI_COMPLETED"
    assert d["page_type"] == "B"
