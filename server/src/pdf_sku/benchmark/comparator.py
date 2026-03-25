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
    # 纯中文 2-4 字核心词子串匹配
    # 场景: GT "沙发" vs Pipeline "现代轻奢沙发", ratio<0.6 但应匹配
    cn_a = re.sub(r'[^\u4e00-\u9fff]', '', na)
    cn_b = re.sub(r'[^\u4e00-\u9fff]', '', nb)
    if cn_a and cn_b and len(cn_a) >= 2 and len(cn_b) >= 2:
        if len(cn_a) <= 4 and cn_a in cn_b:
            return True
        if len(cn_b) <= 4 and cn_b in cn_a:
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


def _dedup_gt_no_model_by_name(expected: list[GroundTruthSKU]) -> list[GroundTruthSKU]:
    """GT 无型号同名去重: 多行无型号同名（如5行"沙发"）→ 去重保留1行。

    降低 expected_count 分母，减少假性 FN/FP。
    仅对 model_number 为空且 product_name 相同的条目去重。
    """
    seen_names: set[str] = set()
    deduped: list[GroundTruthSKU] = []
    for gt in expected:
        if gt.model_number:
            deduped.append(gt)
            continue
        # 从 product_name 提取型号，有型号的不在此去重（由 _dedup_gt_by_model 处理）
        prefix = _extract_model_prefix(gt.product_name)
        if prefix:
            deduped.append(gt)
            continue
        name_key = _normalize(gt.product_name) if gt.product_name else ""
        if not name_key:
            deduped.append(gt)
            continue
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        deduped.append(gt)
    return deduped


def compare_dataset(
    ds: ReferenceDataset,
    run_result: dict,
) -> ComparisonResult:
    """对比单个数据集的 Pipeline 输出与参考 Excel。"""
    raw_expected = ds.skus
    expected = _dedup_gt_by_model(raw_expected)
    expected = _dedup_gt_no_model_by_name(expected)
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
    # 先收集所有候选 (score 排序) 再贪心匹配，避免短前缀误匹配
    _pass0_candidates: list[tuple[float, int, int]] = []  # (score, ei, ai)
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        exp_prefix = _extract_model_prefix(exp.product_name)
        if not exp_prefix:
            continue
        exp_norm_prefix = _normalize_model(exp_prefix)
        exp_name_n = _normalize(exp.product_name)
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model = str(act.get("model_number", ""))
            act_name = str(act.get("product_name", ""))
            act_name_n = _normalize(act_name)
            matched_prefix = False
            if act_model and _normalize_model(act_model) == exp_norm_prefix:
                matched_prefix = True
            if not matched_prefix:
                act_prefix = _extract_model_prefix(act_name)
                if act_prefix and exp_norm_prefix == _normalize_model(act_prefix):
                    matched_prefix = True
            if matched_prefix:
                # 计算 product_name 亲和度作为排序依据
                name_score = SequenceMatcher(None, exp_name_n, act_name_n).ratio()
                _pass0_candidates.append((name_score, ei, ai))
    # 按 name_score 降序贪心匹配
    _pass0_candidates.sort(key=lambda x: -x[0])
    for _score, ei, ai in _pass0_candidates:
        if ei in matched_expected or ai in matched_actual:
            continue
        result.matches.append(_make_match(expected[ei], actual_list[ai], "model_prefix"))
        matched_expected.add(ei)
        matched_actual.add(ai)

    # Pass 0.5: GT model_number 为空时，用 product_name 直接匹配 Pipeline model_number
    # 处理纯数字型号（如 "2202"）和中文混合型号（如 "巴塞罗那2217"）
    # 收集候选后按亲和度排序，避免错误的先到先得
    _pass05_candidates: list[tuple[float, int, int]] = []
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        if exp.model_number:
            continue
        exp_name = _normalize(exp.product_name)
        if not exp_name or len(exp_name) > 20:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model = _normalize(str(act.get("model_number", "")))
            act_name_n = _normalize(str(act.get("product_name", "")))
            if act_model and (act_model == exp_name
                              or (len(act_model) >= 3 and act_model in exp_name)):
                name_score = SequenceMatcher(None, exp_name, act_name_n).ratio()
                _pass05_candidates.append((name_score, ei, ai))
    _pass05_candidates.sort(key=lambda x: -x[0])
    for _score, ei, ai in _pass05_candidates:
        if ei in matched_expected or ai in matched_actual:
            continue
        result.matches.append(_make_match(expected[ei], actual_list[ai], "name_as_model"))
        matched_expected.add(ei)
        matched_actual.add(ai)

    # Pass 1: model_number 精确匹配 (规范化: 去尾缀 #/*)
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

    # Pass 1.5: model_number 前缀匹配 (FP-11 匹配 FP-11B)
    for ei, exp in enumerate(expected):
        if ei in matched_expected or not exp.model_number:
            continue
        exp_model_n = _normalize_model(exp.model_number)
        if not exp_model_n:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model_n = _normalize_model(str(act.get("model_number", "")))
            if not act_model_n:
                continue
            # 一方是另一方的前缀 + 尾部仅 1-2 个字母 (变体后缀)
            if (act_model_n.startswith(exp_model_n)
                    and len(act_model_n) - len(exp_model_n) <= 2
                    and act_model_n[len(exp_model_n):].isalpha()):
                result.matches.append(_make_match(exp, act, "model_suffix"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break
            if (exp_model_n.startswith(act_model_n)
                    and len(exp_model_n) - len(act_model_n) <= 2
                    and exp_model_n[len(act_model_n):].isalpha()):
                result.matches.append(_make_match(exp, act, "model_suffix"))
                matched_expected.add(ei)
                matched_actual.add(ai)
                break

    # Pass 1.6: 反向型号匹配 — pipeline.model_number 在 GT.product_name 中做子串匹配
    # 场景: GT 无 model_number 但 product_name 含型号（如"BT-SF711沙发"），
    #       pipeline 提取了 model="BT-SF711"
    _pass16_candidates: list[tuple[float, int, int]] = []
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        if exp.model_number:
            continue  # GT 有型号的已在 Pass 1/1.5 处理
        exp_name_n = _normalize(exp.product_name)
        if not exp_name_n:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model = str(act.get("model_number", ""))
            if not act_model or len(act_model) < 3:
                continue
            act_model_n = _normalize(act_model)
            if act_model_n in exp_name_n:
                # 额外验证: product_name 也要有一定相似度
                act_name_n = _normalize(str(act.get("product_name", "")))
                name_score = SequenceMatcher(None, exp_name_n, act_name_n).ratio()
                _pass16_candidates.append((name_score, ei, ai))
    _pass16_candidates.sort(key=lambda x: -x[0])
    for _score, ei, ai in _pass16_candidates:
        if ei in matched_expected or ai in matched_actual:
            continue
        result.matches.append(_make_match(expected[ei], actual_list[ai], "reverse_model"))
        matched_expected.add(ei)
        matched_actual.add(ai)

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
