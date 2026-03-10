"""Benchmark 数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GroundTruthSKU:
    """参考 Excel 中一行 SKU 数据。"""
    row_index: int = 0
    product_name: str = ""
    model_number: str = ""
    price: str = ""
    specs: str = ""
    color: str = ""
    tag: str = ""
    source: str = ""
    raw_row: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceDataset:
    """一组参考数据 (PDF + Excel)。"""
    name: str = ""
    folder: Path = field(default_factory=Path)
    pdf_path: Path | None = None
    excel_path: Path | None = None
    expected_sku_count: int = 0
    manual_minutes: int = 0
    skus: list[GroundTruthSKU] = field(default_factory=list)


@dataclass
class FieldDiff:
    """单个字段的差异。"""
    field_name: str = ""
    expected: str = ""
    actual: str = ""


@dataclass
class SKUMatch:
    """一对匹配的 SKU。"""
    expected: GroundTruthSKU | None = None
    actual_attrs: dict[str, Any] | None = None
    match_method: str = ""  # model_number | product_name | position
    field_diffs: list[FieldDiff] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """单个数据集的对比结果。"""
    dataset_name: str = ""
    expected_count: int = 0
    actual_count: int = 0
    matched_count: int = 0
    missing_skus: list[GroundTruthSKU] = field(default_factory=list)
    extra_skus: list[dict[str, Any]] = field(default_factory=list)
    matches: list[SKUMatch] = field(default_factory=list)

    @property
    def precision(self) -> float:
        if self.actual_count == 0:
            return 0.0
        return self.matched_count / self.actual_count

    @property
    def recall(self) -> float:
        if self.expected_count == 0:
            return 0.0
        return self.matched_count / self.expected_count

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def field_exact_match_rate(self) -> float:
        if not self.matches:
            return 0.0
        total_fields = 0
        exact_fields = 0
        for m in self.matches:
            for d in m.field_diffs:
                total_fields += 1
                if d.expected == d.actual:
                    exact_fields += 1
        return exact_fields / total_fields if total_fields else 1.0
