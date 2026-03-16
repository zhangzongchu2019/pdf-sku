"""终端表格 + Markdown 报告生成。"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import ComparisonResult


def print_scan_summary(datasets: list) -> None:
    """打印 scan 结果摘要表格。"""
    print(f"\n{'='*80}")
    print(f"{'数据集名称':<30} {'PDF':^5} {'Excel':^5} {'期望SKU':>8} {'实际SKU':>8} {'耗时(分)':>8}")
    print(f"{'-'*80}")

    total_skus = 0
    paired = 0
    for ds in datasets:
        has_pdf = "✓" if ds.pdf_path else "✗"
        has_excel = "✓" if ds.excel_path else "✗"
        sku_count = len(ds.skus) if ds.skus else ds.expected_sku_count
        total_skus += sku_count
        if ds.pdf_path and ds.excel_path:
            paired += 1

        print(
            f"{ds.name[:30]:<30} {has_pdf:^5} {has_excel:^5} "
            f"{ds.expected_sku_count:>8} {sku_count:>8} {ds.manual_minutes:>8}"
        )

    print(f"{'-'*80}")
    print(f"总计: {len(datasets)} 个数据集, {paired} 个完整配对, {total_skus} 个 SKU")
    print(f"{'='*80}\n")


def print_comparison(result: ComparisonResult) -> None:
    """打印单个对比结果。"""
    print(f"\n--- {result.dataset_name} ---")
    print(f"  期望: {result.expected_count}  实际: {result.actual_count}  匹配: {result.matched_count}")
    print(f"  Precision: {result.precision:.2%}  Recall: {result.recall:.2%}  F1: {result.f1:.2%}")
    print(f"  字段精确匹配率: {result.field_exact_match_rate:.2%}")

    if result.missing_skus:
        print(f"  缺失 ({len(result.missing_skus)}):")
        for s in result.missing_skus[:5]:
            print(f"    - {s.product_name or s.model_number}")
        if len(result.missing_skus) > 5:
            print(f"    ... 还有 {len(result.missing_skus) - 5} 个")

    if result.extra_skus:
        print(f"  多余 ({len(result.extra_skus)}):")
        for s in result.extra_skus[:5]:
            print(f"    - {s.get('product_name', s.get('model_number', '?'))}")
        if len(result.extra_skus) > 5:
            print(f"    ... 还有 {len(result.extra_skus) - 5} 个")


def print_summary(results: list[ComparisonResult]) -> None:
    """打印汇总表格。"""
    print(f"\n{'='*90}")
    print(f"{'数据集':<25} {'期望':>6} {'实际':>6} {'匹配':>6} {'P':>8} {'R':>8} {'F1':>8} {'字段':>8}")
    print(f"{'-'*90}")

    total_exp = total_act = total_match = 0
    for r in results:
        total_exp += r.expected_count
        total_act += r.actual_count
        total_match += r.matched_count
        print(
            f"{r.dataset_name[:25]:<25} {r.expected_count:>6} {r.actual_count:>6} "
            f"{r.matched_count:>6} {r.precision:>7.1%} {r.recall:>7.1%} "
            f"{r.f1:>7.1%} {r.field_exact_match_rate:>7.1%}"
        )

    print(f"{'-'*90}")
    if total_exp > 0:
        macro_p = total_match / total_act if total_act else 0
        macro_r = total_match / total_exp
        macro_f1 = 2 * macro_p * macro_r / (macro_p + macro_r) if (macro_p + macro_r) else 0
        print(
            f"{'总计':<25} {total_exp:>6} {total_act:>6} {total_match:>6} "
            f"{macro_p:>7.1%} {macro_r:>7.1%} {macro_f1:>7.1%}"
        )
    print(f"{'='*90}\n")


def _print_page_class_distribution(run_results: list[dict]) -> None:
    """打印所有数据集的 fitz_page_class 分布。"""
    class_counter: Counter = Counter()
    class_sku_counter: Counter = Counter()
    method_counter: Counter = Counter()

    for run_result in run_results:
        for page in run_result.get("pages", []):
            cls = page.get("fitz_page_class") or page.get("page_type", "?")
            sku_count = len(page.get("skus", []))
            class_counter[cls] += 1
            class_sku_counter[cls] += sku_count
            method = page.get("extraction_method") or "none"
            method_counter[method] += 1

    total_pages = sum(class_counter.values())
    total_skus = sum(class_sku_counter.values())

    if not total_pages:
        return

    print(f"\n{'='*70}")
    print("页面分类分布 (fitz_page_class)")
    print(f"{'='*70}")
    print(f"{'分类':<16} {'页数':>6} {'占比':>8} {'SKU数':>8} {'SKU/页':>8}")
    print(f"{'-'*70}")
    for cls, cnt in class_counter.most_common():
        sku_cnt = class_sku_counter[cls]
        avg = sku_cnt / cnt if cnt else 0
        print(f"{cls:<16} {cnt:>6} {cnt/total_pages:>7.1%} {sku_cnt:>8} {avg:>7.1f}")
    print(f"{'-'*70}")
    print(f"{'总计':<16} {total_pages:>6} {'100%':>8} {total_skus:>8}")

    print(f"\n{'提取方法':<20} {'页数':>6} {'占比':>8}")
    print(f"{'-'*40}")
    for m, cnt in method_counter.most_common():
        print(f"{m:<20} {cnt:>6} {cnt/total_pages:>7.1%}")
    print(f"{'='*70}\n")


def _print_extra_by_class(results: list[ComparisonResult]) -> None:
    """按 fitz_page_class 分组统计多余 SKU，定位 Precision 问题来源。"""
    class_extra: Counter = Counter()
    for r in results:
        for s in r.extra_skus:
            cls = s.get("_fitz_page_class") or "?"
            class_extra[cls] += 1

    if not class_extra:
        return

    total = sum(class_extra.values())
    print(f"\n多余 SKU 按页面分类分布 (共 {total} 个 false positive):")
    for cls, cnt in class_extra.most_common():
        print(f"  {cls:<16} {cnt:>5} ({cnt/total:.1%})")


def generate_markdown_report(
    results: list[ComparisonResult],
    output_path: Path,
    run_results: list[dict] | None = None,
) -> None:
    """生成 Markdown 报告文件。"""
    lines = ["# Benchmark 对比报告\n"]

    # 汇总表
    lines.append("## 汇总\n")
    lines.append("| 数据集 | 期望 | 实际 | 匹配 | Precision | Recall | F1 | 字段匹配率 |")
    lines.append("|--------|------|------|------|-----------|--------|-----|-----------|")
    total_exp = total_act = total_match = 0
    for r in results:
        total_exp += r.expected_count
        total_act += r.actual_count
        total_match += r.matched_count
        lines.append(
            f"| {r.dataset_name} | {r.expected_count} | {r.actual_count} | "
            f"{r.matched_count} | {r.precision:.1%} | {r.recall:.1%} | "
            f"{r.f1:.1%} | {r.field_exact_match_rate:.1%} |"
        )
    if total_exp > 0:
        macro_p = total_match / total_act if total_act else 0
        macro_r = total_match / total_exp
        macro_f1 = 2 * macro_p * macro_r / (macro_p + macro_r) if (macro_p + macro_r) else 0
        lines.append(
            f"| **总计** | **{total_exp}** | **{total_act}** | "
            f"**{total_match}** | **{macro_p:.1%}** | **{macro_r:.1%}** | "
            f"**{macro_f1:.1%}** | |"
        )

    # 页面分类分布
    if run_results:
        lines.append("\n## 页面分类分布\n")
        class_counter: Counter = Counter()
        class_sku_counter: Counter = Counter()
        for rr in run_results:
            for page in rr.get("pages", []):
                cls = page.get("fitz_page_class") or page.get("page_type", "?")
                class_counter[cls] += 1
                class_sku_counter[cls] += len(page.get("skus", []))
        lines.append("| 分类 | 页数 | 占比 | SKU数 | SKU/页 |")
        lines.append("|------|------|------|-------|--------|")
        tp = sum(class_counter.values())
        for cls, cnt in class_counter.most_common():
            sc = class_sku_counter[cls]
            lines.append(f"| {cls} | {cnt} | {cnt/tp:.1%} | {sc} | {sc/cnt:.1f} |")

    # 多余 SKU 按分类分布
    class_extra: Counter = Counter()
    for r in results:
        for s in r.extra_skus:
            cls = s.get("_fitz_page_class") or "?"
            class_extra[cls] += 1
    if class_extra:
        total_extra = sum(class_extra.values())
        lines.append("\n## 多余 SKU 来源分析\n")
        lines.append("| 页面分类 | 多余数 | 占比 |")
        lines.append("|----------|--------|------|")
        for cls, cnt in class_extra.most_common():
            lines.append(f"| {cls} | {cnt} | {cnt/total_extra:.1%} |")

    # 详细 diff
    lines.append("\n## 详细差异\n")
    for r in results:
        lines.append(f"### {r.dataset_name}\n")
        if r.missing_skus:
            lines.append(f"**缺失 SKU ({len(r.missing_skus)}):**\n")
            for s in r.missing_skus:
                lines.append(f"- {s.product_name or s.model_number} (行 {s.row_index})")
            lines.append("")

        if r.extra_skus:
            lines.append(f"**多余 SKU ({len(r.extra_skus)}):**\n")
            for s in r.extra_skus:
                lines.append(f"- {s.get('product_name', s.get('model_number', '?'))}")
            lines.append("")

        # 字段差异示例 (前10个)
        diffs_with_issues = [
            m for m in r.matches
            if any(d.expected != d.actual for d in m.field_diffs if d.expected)
        ]
        if diffs_with_issues:
            lines.append(f"**字段差异 (前10):**\n")
            for m in diffs_with_issues[:10]:
                name = m.expected.product_name or m.expected.model_number if m.expected else "?"
                lines.append(f"- **{name}** (匹配方法: {m.match_method})")
                for d in m.field_diffs:
                    if d.expected and d.expected != d.actual:
                        lines.append(f"  - {d.field_name}: `{d.expected}` → `{d.actual}`")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已保存: {output_path}")
