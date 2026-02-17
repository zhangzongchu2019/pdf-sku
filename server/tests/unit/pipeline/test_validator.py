"""ConsistencyValidator 测试。"""
from pdf_sku.pipeline.ir import SKUResult, ImageInfo, BindingResult
from pdf_sku.pipeline.extractor.consistency_validator import ConsistencyValidator


def test_validate_no_skus_error():
    v = ConsistencyValidator()
    result = v.validate("B", [], [])
    assert result.has_errors
    assert any(i.rule == "no_skus_found" for i in result.issues)


def test_validate_d_page_no_skus_ok():
    v = ConsistencyValidator()
    result = v.validate("D", [], [])
    assert not result.has_errors


def test_validate_low_confidence():
    v = ConsistencyValidator()
    skus = [SKUResult(sku_id="s1", confidence=0.3)]
    result = v.validate("B", skus, [])
    assert result.has_warnings
    assert any(i.rule == "low_confidence" for i in result.issues)


def test_validate_duplicate_model():
    v = ConsistencyValidator()
    skus = [
        SKUResult(sku_id="s1", attributes={"model_number": "XZ-100"}, confidence=0.9),
        SKUResult(sku_id="s2", attributes={"model_number": "XZ-100"}, confidence=0.9),
    ]
    result = v.validate("B", skus, [])
    assert any(i.rule == "duplicate_model" for i in result.issues)


def test_enforce_validity_strict():
    v = ConsistencyValidator()
    skus = [
        SKUResult(attributes={"product_name": "Widget"}),
        SKUResult(attributes={"price": "10"}),  # no product_name
    ]
    skus = v.enforce_sku_validity(skus)
    assert skus[0].validity == "valid"
    assert skus[1].validity == "invalid"


def test_enforce_validity_relaxed():
    v = ConsistencyValidator()
    skus = [SKUResult(attributes={"price": "10"})]
    skus = v.enforce_sku_validity(skus, {"sku_validity_mode": "relaxed"})
    assert skus[0].validity == "valid"
