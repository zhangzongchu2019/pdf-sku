"""SKU 对比引擎 — 匹配 + F1 指标 + 字段级 diff。"""
from __future__ import annotations

import re
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
    "specs": "specs",
    "size": "specs",        # 兼容旧字段
    "color": "color",
    "tag": "tag",
    "source": "source",
}


def _normalize(s: str) -> str:
    """归一化字符串用于比较。"""
    return s.strip().lower().replace(" ", "").replace("\u3000", "")


def _normalize_model(s: str) -> str:
    """归一化型号用于匹配: 去除尾部 #/*，统一大小写去空格。"""
    n = s.strip().lower().replace(" ", "").replace("\u3000", "")
    return n.rstrip("#*")


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


def _extract_model_prefix(name: str) -> str | None:
    """从 product_name 提取完整型号（如 SJ-2001、H-303-1A、BT-BD711-2）。"""
    m = re.search(
        r'[A-Za-z]{1,5}[-\s]?[A-Za-z]{0,3}\d{2,10}[A-Za-z]?(?:[-][A-Za-z0-9]{1,4})*',
        name,
    )
    return m.group(0).upper().replace(" ", "") if m else None


def _first_line(s: str) -> str:
    """取 product_name 首行用于模糊比较。"""
    if not s:
        return ""
    return s.split("\n")[0].strip()


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
                attrs["_fitz_page_class"] = page.get("fitz_page_class", "")
                attrs["_extraction_method"] = page.get("extraction_method", "")
                skus.append(attrs)
    return skus


def extraction_method_stats(run_result: dict) -> dict[str, int]:
    """统计 Pipeline 输出中各提取方法的 SKU 数量。"""
    stats: dict[str, int] = {}
    for page in run_result.get("pages", []):
        method = page.get("extraction_method") or "unknown"
        sku_count = len(page.get("skus", []))
        if sku_count > 0:
            stats[method] = stats.get(method, 0) + sku_count
    return stats


def _dedup_gt_by_model(expected: list[GroundTruthSKU]) -> list[GroundTruthSKU]:
    """去重 GT: 同一 model_number 只保留首次出现的条目。

    场景: 配件在多个套系中重复出现 (如 A13# 床头柜出现 9 次)，
    Pipeline 正确去重后只提取 1 次 → 不应算 8 条 FN。

    同时从 product_name 中提取型号 (如 "A13#床头柜" → A13#)，
    处理 model_number 为空但 product_name 含型号的重复条目。
    """
    seen_models: set[str] = set()
    deduped: list[GroundTruthSKU] = []
    for gt in expected:
        # 尝试从 model_number 字段获取型号
        norm = _normalize_model(gt.model_number) if gt.model_number else ""
        # 若 model_number 为空，从 product_name 提取型号
        if not norm:
            prefix = _extract_model_prefix(gt.product_name)
            if prefix:
                norm = _normalize_model(prefix)
        if norm and norm in seen_models:
            continue
        if norm:
            seen_models.add(norm)
        deduped.append(gt)
    return deduped


def compare_dataset(
    ds: ReferenceDataset,
    run_result: dict,
) -> ComparisonResult:
    """对比单个数据集的 Pipeline 输出与参考 Excel。"""
    raw_expected = ds.skus
    expected = _dedup_gt_by_model(raw_expected)
    actual_list = _extract_all_skus(run_result)

    result = ComparisonResult(
        dataset_name=ds.name,
        expected_count=len(expected),
        actual_count=len(actual_list),
    )

    # 跟踪已匹配的
    matched_expected: set[int] = set()
    matched_actual: set[int] = set()

    # Pass 0: 从 product_name 提取型号前缀匹配
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        exp_prefix = _extract_model_prefix(exp.product_name)
        if not exp_prefix:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            # 先尝试用 actual 的 model_number
            act_model = str(act.get("model_number", ""))
            if act_model and _normalize_model(act_model) == _normalize_model(exp_prefix):
                result.matches.append(_make_match(exp, act, "model_prefix"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break
            # 再尝试从 actual 的 product_name 提取
            act_name = str(act.get("product_name", ""))
            act_prefix = _extract_model_prefix(act_name)
            if act_prefix and _normalize_model(exp_prefix) == _normalize_model(act_prefix):
                result.matches.append(_make_match(exp, act, "model_prefix"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break

    # Pass 1: model_number 匹配 (规范化: 去尾缀 #/*)
    for ei, exp in enumerate(expected):
        if ei in matched_expected or not exp.model_number:
            continue
        exp_model_n = _normalize_model(exp.model_number)
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model = str(act.get("model_number", ""))
            if _normalize_model(act_model) == exp_model_n:
                result.matches.append(_make_match(exp, act, "model_number"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break

    # Pass 2: product_name 首行模糊匹配
    for ei, exp in enumerate(expected):
        if ei in matched_expected or not exp.product_name:
            continue
        exp_first = _first_line(exp.product_name)
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_name = str(act.get("product_name", ""))
            act_first = _first_line(act_name)
            if _fuzzy_match(exp_first, act_first):
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
    seen_fields: set[str] = set()
    for attr_key, field_name in ATTR_FIELD_MAP.items():
        if field_name in seen_fields:
            continue
        seen_fields.add(field_name)
        exp_val = getattr(exp, field_name, "") or ""
        # 尝试新字段名，回退到旧字段名
        act_val = str(act.get(attr_key, "") or "")
        # product_name 比较用首行
        if field_name == "product_name":
            exp_val = _first_line(exp_val)
            act_val = _first_line(act_val)
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
