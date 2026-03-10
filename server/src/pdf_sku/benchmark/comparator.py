"""SKU 对比引擎 — 匹配 + F1 指标 + 字段级 diff。"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from .models import (
    ComparisonResult,
    FieldDiff,
    GroundTruthSKU,
    ReferenceDataset,
    SKUMatch,
)

# Pipeline attributes 到 GroundTruthSKU 字段的映射
ATTR_FIELD_MAP = {
    "product_name": "product_name",
    "model_number": "model_number",
    "price": "price",
    "size": "specs",
    "color": "color",
}


def _normalize(s: str) -> str:
    """归一化字符串用于比较。"""
    return s.strip().lower().replace(" ", "").replace("\u3000", "")


def _fuzzy_match(a: str, b: str, threshold: float = 0.6) -> bool:
    if not a or not b:
        return False
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return True
    # 包含关系
    if na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def _extract_all_skus(run_result: dict) -> list[dict[str, Any]]:
    """从 runner 输出提取所有 valid SKU 的 attributes。"""
    skus = []
    for page in run_result.get("pages", []):
        for sku in page.get("skus", []):
            if sku.get("validity", "valid") == "valid":
                attrs = dict(sku.get("attributes", {}))
                attrs["_sku_id"] = sku.get("sku_id", "")
                attrs["_page_no"] = page.get("page_no", 0)
                attrs["_confidence"] = sku.get("confidence", 0)
                skus.append(attrs)
    return skus


def compare_dataset(
    ds: ReferenceDataset,
    run_result: dict,
) -> ComparisonResult:
    """对比单个数据集的 Pipeline 输出与参考 Excel。"""
    expected = ds.skus
    actual_list = _extract_all_skus(run_result)

    result = ComparisonResult(
        dataset_name=ds.name,
        expected_count=len(expected),
        actual_count=len(actual_list),
    )

    # 跟踪已匹配的
    matched_expected: set[int] = set()
    matched_actual: set[int] = set()

    # Pass 1: model_number 精确匹配
    for ei, exp in enumerate(expected):
        if not exp.model_number:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model = str(act.get("model_number", ""))
            if _normalize(exp.model_number) == _normalize(act_model):
                result.matches.append(_make_match(exp, act, "model_number"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break

    # Pass 2: product_name 模糊匹配
    for ei, exp in enumerate(expected):
        if ei in matched_expected or not exp.product_name:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_name = str(act.get("product_name", ""))
            if _fuzzy_match(exp.product_name, act_name):
                result.matches.append(_make_match(exp, act, "product_name"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break

    # Pass 3: 位置对齐（按顺序匹配剩余的）
    unmatched_exp = [i for i in range(len(expected)) if i not in matched_expected]
    unmatched_act = [i for i in range(len(actual_list)) if i not in matched_actual]
    for ei, ai in zip(unmatched_exp, unmatched_act):
        result.matches.append(_make_match(expected[ei], actual_list[ai], "position"))
        matched_expected.add(ei)
        matched_actual.add(ai)

    result.matched_count = len(result.matches)

    # Missing / Extra
    result.missing_skus = [expected[i] for i in range(len(expected)) if i not in matched_expected]
    result.extra_skus = [actual_list[i] for i in range(len(actual_list)) if i not in matched_actual]

    return result


def _make_match(
    exp: GroundTruthSKU, act: dict[str, Any], method: str
) -> SKUMatch:
    diffs = []
    for attr_key, field_name in ATTR_FIELD_MAP.items():
        exp_val = getattr(exp, field_name, "")
        act_val = str(act.get(attr_key, ""))
        diffs.append(FieldDiff(
            field_name=field_name,
            expected=exp_val,
            actual=act_val,
        ))
    return SKUMatch(
        expected=exp,
        actual_attrs=act,
        match_method=method,
        field_diffs=diffs,
    )
