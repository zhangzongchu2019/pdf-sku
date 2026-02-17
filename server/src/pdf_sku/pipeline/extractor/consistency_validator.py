"""
一致性校验。对齐: Pipeline 详设 §5.6

规则:
- sku_without_image (warning): SKU 无绑定图片
- duplicate_model (warning): 页内重复型号
- low_confidence (warning): 提取置信度 < 0.5
- no_skus_found (error): 非 D 类页无 SKU
- [C6] enforce_sku_validity: 仅 valid/invalid
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import (
    SKUResult, ImageInfo, BindingResult,
    ValidationResult, ValidationIssue,
)
import structlog

logger = structlog.get_logger()


class ConsistencyValidator:

    def validate(
        self,
        page_type: str,
        skus: list[SKUResult],
        images: list[ImageInfo],
        bindings: list[BindingResult] | None = None,
        profile: dict | None = None,
    ) -> ValidationResult:
        """运行全部校验规则。"""
        issues: list[ValidationIssue] = []
        bindings = bindings or []

        # R1: 非 D 类页无 SKU
        if page_type not in ("D", "d") and not skus:
            issues.append(ValidationIssue(
                rule="no_skus_found", severity="error",
                message=f"No SKUs found on {page_type} page"))

        # R2: SKU 无绑定图片
        bound_sku_ids = {b.sku_id for b in bindings if b.image_id}
        for sku in skus:
            if sku.sku_id and sku.sku_id not in bound_sku_ids and page_type != "A":
                issues.append(ValidationIssue(
                    rule="sku_without_image", severity="warning",
                    message=f"SKU {sku.sku_id} has no bound image"))

        # R3: 页内重复型号
        models = [s.attributes.get("model_number") for s in skus
                  if s.attributes.get("model_number")]
        seen = set()
        for m in models:
            if m in seen:
                issues.append(ValidationIssue(
                    rule="duplicate_model", severity="warning",
                    message=f"Duplicate model number: {m}"))
            seen.add(m)

        # R4: 低置信度
        for sku in skus:
            if sku.confidence < 0.5:
                issues.append(ValidationIssue(
                    rule="low_confidence", severity="warning",
                    message=f"SKU confidence {sku.confidence:.2f} < 0.5",
                    context={"sku_id": sku.sku_id}))

        has_errors = any(i.severity == "error" for i in issues)
        has_warnings = any(i.severity == "warning" for i in issues)

        return ValidationResult(
            issues=issues, has_errors=has_errors, has_warnings=has_warnings)

    @staticmethod
    def enforce_sku_validity(
        skus: list[SKUResult], profile: dict | None = None
    ) -> list[SKUResult]:
        """
        [C6] 强制 SKU validity: valid/invalid (无 partial)。
        strict 模式: 必须有 product_name
        """
        mode = (profile or {}).get("sku_validity_mode", "strict")
        for sku in skus:
            attrs = sku.attributes
            if mode == "strict":
                has_name = bool(attrs.get("product_name"))
                sku.validity = "valid" if has_name else "invalid"
            else:
                sku.validity = "valid" if any(attrs.values()) else "invalid"
        return skus
