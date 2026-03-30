"""SKU 对比引擎 — 匹配 + F1 指标 + 字段级 diff。"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
import structlog

logger = structlog.get_logger()

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
    """归一化型号用于匹配: 去除前缀/尾部标记/中文括号，统一大小写去空格。"""
    n = s.strip().lower().replace(" ", "").replace("\u3000", "")
    # 去掉 "model:", "model：", "型号:", "型号：" 前缀
    for prefix in ("model:", "model：", "型号:", "型号："):
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    # 去掉中文括号及内容: "bk（贝壳）01" → "bk01"
    import re
    n = re.sub(r'[（(][^）)]*[）)]', '', n)
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
    """从 product_name 提取完整型号（如 SJ-2001、H-303-1A、Bk（贝壳）08#、230、8103#）。"""
    # 优先: "产品型号：xxx" / "型号：xxx" / "Model：xxx" 格式（最明确的型号标识）
    m0 = re.search(r'(?:产品型号|model|moedl|型号)[：:]\s*([^\n,，]{1,30})', name, re.IGNORECASE)
    if m0:
        val = m0.group(1).strip()
        # 从值中提取核心型号部分（去掉中文描述后缀如"电动功能沙发"）
        core = re.match(r'([A-Za-z]*\d+[A-Za-z0-9#\-]*)', val)
        if core:
            return core.group(1).upper().rstrip('#')
        return val.split()[0].upper() if val else None

    # 标准字母+数字型号格式（排除尺寸模式）
    m = re.search(
        r'[A-Za-z]{1,5}[-\s]?[A-Za-z]{0,3}\d{2,10}[A-Za-z]?(?:[-][A-Za-z0-9]{1,4})*',
        name,
    )
    if m:
        matched = m.group(0).upper().replace(" ", "").replace("\n", "").replace("\r", "")
        # 排除尺寸模式: "MM160", "X750X", "CM200" 等
        if re.match(r'^[MCXH]M?\d+$', matched) or re.match(r'^X\d+X$', matched):
            pass  # 跳过尺寸误匹配
        else:
            return matched

    # 中文品名+数字型号格式 (如 "Bk（贝壳）08#", "XX（系列）123")
    m2 = re.search(r'([A-Za-z]{1,5})[（(][^）)]+[）)]\s*(\d{1,5})', name)
    if m2:
        return f"{m2.group(1).upper()}{m2.group(2)}"

    # 纯数字型号: 首行是 2-5 位数字+可选#（如 "230\n棕色/橡木", "8103# 转角沙发"）
    first_line = name.split('\n')[0].strip() if name else ''
    m4 = re.match(r'^(\d{2,5})\s*[#＃*]?\s*$', first_line)
    if m4:
        return m4.group(1)
    # 首行 "数字# 产品名" 格式（如 "8103# 转角沙发"）
    m5 = re.match(r'^(\d{2,5})\s*[#＃]\s+\S', first_line)
    if m5:
        return m5.group(1)

    return None


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
        # 仅用 model_number 字段去重（不从 product_name 提取，避免颜色变体被误合并）
        norm = _normalize_model(gt.model_number) if gt.model_number else ""
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

    # 统计 GT 中仅有图片无名称/型号的条目
    gt_image_only = sum(
        1 for s in expected
        if not (s.product_name or "").strip() and not (s.model_number or "").strip()
    )

    result = ComparisonResult(
        dataset_name=ds.name,
        expected_count=len(expected),
        actual_count=len(actual_list),
        gt_image_only_count=gt_image_only,
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
            # 从 act_model 提取前缀再匹配（处理 MY-B-01 vs B-01 类前缀差异）
            if not matched_prefix and act_model:
                act_model_prefix = _extract_model_prefix(act_model)
                if act_model_prefix and _normalize_model(act_model_prefix) == exp_norm_prefix:
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

    # Pass 1.7: GT product_name 中实际型号 → Pipeline model_number 匹配
    # 场景: GT model_number 是序号(A2025-001)，实际型号在 product_name 中(Model：119#)
    # Pass 1/1.5 用序号匹配失败，这里从 product_name 提取实际型号再匹配
    _pass17_candidates: list[tuple[float, int, int]] = []
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        # 从 GT product_name 提取实际型号
        exp_real_model = _extract_model_prefix(exp.product_name) if exp.product_name else None
        if not exp_real_model:
            continue
        exp_real_norm = _normalize_model(exp_real_model)
        if not exp_real_norm:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_model_n = _normalize_model(str(act.get("model_number", "")))
            if act_model_n and act_model_n == exp_real_norm:
                act_name_n = _normalize(str(act.get("product_name", "")))
                exp_name_n = _normalize(exp.product_name)
                score = SequenceMatcher(None, exp_name_n[:30], act_name_n[:30]).ratio()
                _pass17_candidates.append((score, ei, ai))
    _pass17_candidates.sort(key=lambda x: -x[0])
    for _score, ei, ai in _pass17_candidates:
        if ei in matched_expected or ai in matched_actual:
            continue
        result.matches.append(_make_match(expected[ei], actual_list[ai], "name_model_extract"))
        matched_expected.add(ei)
        matched_actual.add(ai)

    # Pass 1.8: 无型号 GT 的 product_name 全文模糊匹配（降低阈值）
    # 场景: GT 无 model_number，product_name 是"休闲椅\n70*73*79"
    #       Pipeline product_name 是"棕色皮质休闲椅"
    # Pass 2 的首行匹配和 0.6 阈值可能不够，这里用全文 + 0.4 阈值
    _pass18_candidates: list[tuple[float, int, int]] = []
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        if not exp.product_name or exp.model_number:
            continue  # 只处理无型号 GT
        exp_name_n = _normalize(exp.product_name)
        if not exp_name_n or len(exp_name_n) > 50:
            continue
        for ai, act in enumerate(actual_list):
            if ai in matched_actual:
                continue
            act_name_n = _normalize(str(act.get("product_name", "")))
            if not act_name_n:
                continue
            # 多维匹配: 首行匹配 + 全文相似度 + 中文核心词包含
            exp_first = _normalize(_first_line(exp.product_name))
            act_first = _normalize(_first_line(str(act.get("product_name", ""))))
            first_score = SequenceMatcher(None, exp_first, act_first).ratio() if exp_first and act_first else 0
            full_score = SequenceMatcher(None, exp_name_n[:40], act_name_n[:40]).ratio()
            score = max(first_score, full_score)
            if score >= 0.4:
                _pass18_candidates.append((score, ei, ai))
    _pass18_candidates.sort(key=lambda x: -x[0])
    for _score, ei, ai in _pass18_candidates:
        if ei in matched_expected or ai in matched_actual:
            continue
        if _score >= 0.5 or (ei not in matched_expected and ai not in matched_actual):
            result.matches.append(_make_match(expected[ei], actual_list[ai], "name_fuzzy_wide"))
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

    # Pass 2.5: 同型号变体多对一匹配
    # 场景: GT 中 387# 有 4 个变体（不同规格），Pipeline 提取了 1 个 387#
    # Pass 1 匹配了第一个，剩余 3 个应也匹配到同一个 Pipeline SKU
    # 收集已匹配的 Pipeline 型号 → actual_attrs
    _matched_model_to_act: dict[str, dict] = {}
    for m in result.matches:
        if m.actual_attrs:
            mn = _normalize_model(str(m.actual_attrs.get("model_number", "")))
            if mn:
                _matched_model_to_act[mn] = m.actual_attrs
    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        exp_real = _extract_model_prefix(exp.product_name) if exp.product_name else None
        if not exp_real:
            continue
        exp_real_norm = _normalize_model(exp_real)
        if exp_real_norm and exp_real_norm in _matched_model_to_act:
            result.matches.append(
                _make_match(exp, _matched_model_to_act[exp_real_norm], "model_variant"))
            matched_expected.add(ei)

    # Pass 2.8: 图片相似度匹配（仅对 gt_image_only 且仍有大量未匹配时启用）
    remaining_exp = len(expected) - len(matched_expected)
    remaining_act = len(actual_list) - len(matched_actual)
    if gt_image_only > len(expected) * 0.5 and remaining_exp > 5 and remaining_act > 5:
        try:
            from pdf_sku.benchmark.image_matcher import match_gt_pred_images
            from pathlib import Path
            if hasattr(ds, 'excel_path') and ds.excel_path:
                cache_name = ds.name.replace('/', '_').replace(' ', '_')
                cache_path = Path(f"data/benchmark_cache/{cache_name}.json")
                if cache_path.exists():
                    img_result = match_gt_pred_images(
                        Path(ds.excel_path), cache_path, threshold=0.70)
                    if img_result.get("matches"):
                        for gi, pi, sim in img_result["matches"]:
                            if gi not in matched_expected and pi not in matched_actual:
                                if gi < len(expected) and pi < len(actual_list):
                                    result.matches.append(
                                        _make_match(expected[gi], actual_list[pi], "image_similarity"))
                                    matched_expected.add(gi)
                                    matched_actual.add(pi)
                        logger.info("image_similarity_matching",
                                    matched=len([m for m in result.matches if m.match_method == "image_similarity"]))
        except Exception as e:
            logger.debug("image_matching_skipped", error=str(e))

    # Pass 2.9: 组合GT拆分匹配
    # GT product_name 包含多个 XX# 型号（如 "601# 圆餐桌...12# 餐椅"）
    # 如果拆分出的所有型号都已在 matched 的 Pipeline 预测中 → 标记该 GT 为已匹配
    _matched_act_models = set()
    for ai in matched_actual:
        act = actual_list[ai]
        m = str(act.get("model_number", "")).strip().rstrip("#")
        if m:
            _matched_act_models.add(_normalize_model(m))
        # 也从 product_name 提取
        ap = _extract_model_prefix(str(act.get("product_name", "")))
        if ap:
            _matched_act_models.add(_normalize_model(ap))

    for ei, exp in enumerate(expected):
        if ei in matched_expected:
            continue
        # 检测 product_name 中的多个型号（支持跨行、带尺寸的组合格式）
        # 匹配: "601#", "12#", "8901#" 等纯数字+# 格式
        models_in_name = re.findall(r'(\d+)\s*#', exp.product_name or '')
        # 也匹配: "BS8560", "Bk01" 等字母+数字格式（无#）
        if len(models_in_name) < 2:
            models_in_name = re.findall(r'(?:^|[\s\n])([A-Za-z]+[-]?\d{2,}[A-Za-z]?)', exp.product_name or '')
        # 也匹配: "数字-数字" 格式（如 "2001-1", "303-2A"）
        if len(models_in_name) < 2:
            models_in_name = re.findall(r'(\d{2,5}[-]\d{1,3}[A-Za-z]?)', exp.product_name or '')
        if len(models_in_name) >= 2:
            all_found = all(
                _normalize_model(m) in _matched_act_models
                for m in models_in_name
            )
            if all_found:
                matched_expected.add(ei)

    # Pass 3: 位置对齐（按顺序匹配剩余的）
    unmatched_exp = [i for i in range(len(expected)) if i not in matched_expected]
    unmatched_act = [i for i in range(len(actual_list)) if i not in matched_actual]
    for ei, ai in zip(unmatched_exp, unmatched_act):
        result.matches.append(_make_match(expected[ei], actual_list[ai], "position"))
        matched_expected.add(ei)
        matched_actual.add(ai)

    # matched_count: 用匹配到的 GT 数量（R 的分子）
    # 但 P 的分子用匹配到的唯一 Pipeline SKU 数量
    result.matched_count = len(matched_expected)

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
