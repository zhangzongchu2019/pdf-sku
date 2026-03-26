#!/usr/bin/env python3
"""
Benchmark 评估报告生成器 — 从缓存结果生成完整的对比表格。

用法:
    .venv/bin/python data/test/benchmark_report.py [选项]

选项:
    --cache-dir DIR       缓存目录 (默认: server/data/benchmark_cache)
    --baseline FILE       基线 JSON 文件 (默认: data/test/baseline_141_datasets.json)
    --sort FIELD          排序字段: r/p/f1/dr/dp/df1/name (默认: r)
    --asc                 升序排列 (默认降序)
    --filter EXPR         过滤条件: r<90, p<80, dr>5, dr<-5, f1<70 等
    --format FMT          输出格式: markdown/csv/text (默认: markdown)
    --output FILE         输出到文件 (默认: 标准输出)
    --no-summary          不输出汇总统计
    --no-sections         不输出分段分析 (R<90%、ΔR>5% 等)

示例:
    # 默认完整报告 (markdown 表格, 按 R 降序)
    .venv/bin/python data/test/benchmark_report.py

    # 只看 R<90% 的数据集, 按 R 升序
    .venv/bin/python data/test/benchmark_report.py --filter "r<90" --asc

    # 输出 CSV 到文件
    .venv/bin/python data/test/benchmark_report.py --format csv --output report.csv

    # 按 ΔR 降序看变化最大的
    .venv/bin/python data/test/benchmark_report.py --sort dr
"""
import argparse
import csv
import io
import json
import pathlib
import sys

# 设置 Python 路径
_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "server" / "src"))

from pdf_sku.benchmark.excel_parser import scan_datasets, load_dataset  # noqa: E402
from pdf_sku.benchmark.comparator import compare_dataset  # noqa: E402


def collect_results(cache_dir: pathlib.Path, baseline_path: pathlib.Path):
    """从缓存文件和基线数据收集所有评估结果。"""
    # 加载基线
    baseline = {}
    if baseline_path.exists():
        with open(baseline_path) as f:
            for d in json.load(f):
                baseline[d["name"]] = d

    # 扫描参考数据集
    all_ds = scan_datasets()
    ds_map = {ds.name: ds for ds in all_ds}

    # 遍历缓存文件
    cache_files = sorted(cache_dir.glob("*.json"))
    results = []

    for fp in cache_files:
        cache_name = fp.stem
        with open(fp) as f:
            run_result = json.load(f)

        ds_name = run_result.get("dataset", cache_name)
        total_pages = run_result.get("total_pages", 0)

        # 匹配参考数据集
        ref_ds = ds_map.get(ds_name) or ds_map.get(cache_name)
        if not ref_ds:
            # 模糊匹配
            for k in ds_map:
                if cache_name in k or k in cache_name:
                    ref_ds = ds_map[k]
                    break

        if not ref_ds:
            results.append({
                "name": cache_name, "pages": total_pages,
                "gt": 0, "pred": run_result.get("total_skus", 0),
                "tp": 0, "fp": 0, "fn": 0,
                "p": 0.0, "r": 0.0, "f1": 0.0,
                "bl_p": None, "bl_r": None, "bl_f1": None,
                "dp": None, "dr": None, "df1": None,
            })
            continue

        # 加载 GT 并对比
        load_dataset(ref_ds)
        comp = compare_dataset(ref_ds, run_result)

        tp = comp.matched_count
        fp_count = len(comp.extra_skus)
        fn = len(comp.missing_skus)
        p = comp.precision
        r = comp.recall
        f1 = comp.f1

        # 基线查找 (值为百分比 0-100, 转为 0-1)
        bl = baseline.get(ds_name, baseline.get(cache_name, {}))
        bl_p = bl.get("baseline_p")
        bl_r = bl.get("baseline_r")
        bl_f1 = bl.get("baseline_f1")
        if bl_p is not None:
            bl_p /= 100.0
        if bl_r is not None:
            bl_r /= 100.0
        if bl_f1 is not None:
            bl_f1 /= 100.0

        results.append({
            "name": ds_name, "pages": total_pages,
            "gt": comp.expected_count, "pred": comp.actual_count,
            "tp": tp, "fp": fp_count, "fn": fn,
            "p": p, "r": r, "f1": f1,
            "bl_p": bl_p, "bl_r": bl_r, "bl_f1": bl_f1,
            "dp": (p - bl_p) if bl_p is not None else None,
            "dr": (r - bl_r) if bl_r is not None else None,
            "df1": (f1 - bl_f1) if bl_f1 is not None else None,
        })

    return results


def apply_filter(results: list[dict], expr: str) -> list[dict]:
    """根据过滤表达式筛选结果。支持: r<90, p<80, dr>5, dr<-5, f1<70 等。"""
    import re
    m = re.match(r"(d?(?:r|p|f1))\s*([<>]=?)\s*(-?[\d.]+)", expr.strip())
    if not m:
        print(f"警告: 无法解析过滤条件 '{expr}', 忽略", file=sys.stderr)
        return results

    field, op, val = m.group(1), m.group(2), float(m.group(3))
    # 用户输入百分比值, 内部存储为小数
    val /= 100.0

    ops = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
           ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
    cmp_fn = ops[op]

    filtered = []
    for r in results:
        v = r.get(field)
        if v is not None and cmp_fn(v, val):
            filtered.append(r)
    return filtered


def sort_results(results: list[dict], field: str, ascending: bool):
    """排序结果列表。"""
    def sort_key(r):
        v = r.get(field)
        if v is None:
            return float("-inf") if not ascending else float("inf")
        return v

    results.sort(key=sort_key, reverse=not ascending)


def format_summary(results: list[dict]) -> str:
    """生成汇总统计文本。"""
    has_gt = [r for r in results if r["gt"] > 0]
    if not has_gt:
        return "无有效数据集\n"

    total_tp = sum(r["tp"] for r in has_gt)
    total_fp = sum(r["fp"] for r in has_gt)
    total_fn = sum(r["fn"] for r in has_gt)
    total_gt = sum(r["gt"] for r in has_gt)
    total_pred = sum(r["pred"] for r in has_gt)
    op = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    orr = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    of1 = 2 * op * orr / (op + orr) if (op + orr) else 0

    r100 = sum(1 for r in has_gt if r["r"] >= 0.995)
    r95 = sum(1 for r in has_gt if r["r"] >= 0.95)
    r90 = sum(1 for r in has_gt if r["r"] >= 0.90)
    rlt90 = sum(1 for r in has_gt if r["r"] < 0.90)
    rlt80 = sum(1 for r in has_gt if r["r"] < 0.80)
    r_up = sum(1 for r in has_gt if r["dr"] is not None and r["dr"] > 0.005)
    r_dn = sum(1 for r in has_gt if r["dr"] is not None and r["dr"] < -0.005)
    r_eq = sum(1 for r in has_gt if r["dr"] is not None and abs(r["dr"]) <= 0.005)
    r_na = sum(1 for r in has_gt if r["dr"] is None)

    p_up = sum(1 for r in has_gt if r["dp"] is not None and r["dp"] > 0.005)
    p_dn = sum(1 for r in has_gt if r["dp"] is not None and r["dp"] < -0.005)

    lines = [
        f"## Benchmark 报告 — {len(results)} 个数据集 ({len(has_gt)} 有GT)",
        "",
        f"**整体: P={op*100:.1f}%  R={orr*100:.1f}%  F1={of1*100:.1f}%**  "
        f"(GT={total_gt} Pred={total_pred} TP={total_tp} FP={total_fp} FN={total_fn})",
        "",
        f"R分布: R=100%:{r100} | R≥95%:{r95} | R≥90%:{r90} | R<90%:{rlt90} | R<80%:{rlt80}",
        f"R变化: 提升:{r_up} | 下降:{r_dn} | 不变:{r_eq} | 无基线:{r_na}",
        f"P变化: 提升:{p_up} | 下降:{p_dn}",
        "",
    ]
    return "\n".join(lines)


def format_sections(results: list[dict]) -> str:
    """生成分段分析: R<90% 问题数据集、|ΔR|>5% 变化最大等。"""
    has_gt = [r for r in results if r["gt"] > 0]
    lines = []

    # R<90% 问题数据集
    low_r = [r for r in has_gt if r["r"] < 0.90]
    if low_r:
        low_r.sort(key=lambda x: x["r"])
        lines.append("### R<90% 问题数据集")
        for r in low_r:
            dr_str = f"ΔR={r['dr']*100:+.1f}%" if r["dr"] is not None else "无基线"
            lines.append(
                f"  {r['name']:<34} R={r['r']*100:5.1f}%  "
                f"P={r['p']*100:5.1f}%  FN={r['fn']:>3}  {dr_str}"
            )
        lines.append("")

    # |ΔR|>5% 变化最大
    big_dr = [(r, r["dr"]) for r in has_gt if r["dr"] is not None and abs(r["dr"]) > 0.05]
    if big_dr:
        big_dr.sort(key=lambda x: -x[1])
        lines.append("### |ΔR|>5% 变化最大")
        for r, dr in big_dr:
            lines.append(
                f"  {r['name']:<34} R: {r['bl_r']*100:5.1f}% → {r['r']*100:5.1f}%  "
                f"(ΔR={dr*100:+.1f}%)"
            )
        lines.append("")

    # P<50% 严重低 P 数据集
    low_p = [r for r in has_gt if r["p"] < 0.50 and r["gt"] > 0]
    if low_p:
        low_p.sort(key=lambda x: x["p"])
        lines.append("### P<50% 低精度数据集")
        for r in low_p:
            dp_str = f"ΔP={r['dp']*100:+.1f}%" if r["dp"] is not None else "无基线"
            lines.append(
                f"  {r['name']:<34} P={r['p']*100:5.1f}%  "
                f"R={r['r']*100:5.1f}%  FP={r['fp']:>3}  {dp_str}"
            )
        lines.append("")

    return "\n".join(lines)


# ANSI 颜色
_BLUE = "\033[34m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_RESET = "\033[0m"


def _fmt_pct(v):
    return "N/A" if v is None else f"{v*100:.1f}"


def _fmt_delta(v):
    return "N/A" if v is None else f"{v*100:+.1f}"


def _fmt_pct_blue(v):
    """新P/新R: 蓝色。"""
    if v is None:
        return "   N/A"
    s = f"{v*100:6.1f}"
    return f"{_BLUE}{s}{_RESET}"


def _fmt_delta_color(v):
    """ΔP/ΔR: 正数红色, 负数绿色, 零黑色。"""
    if v is None:
        return "   N/A"
    s = f"{v*100:+6.1f}"
    if v > 0.005:
        return f"{_RED}{s}{_RESET}"
    elif v < -0.005:
        return f"{_GREEN}{s}{_RESET}"
    else:
        return s


def format_markdown_table(results: list[dict]) -> str:
    """生成 Markdown 格式的对比表格。"""
    lines = [
        "| # | 数据集 | 页 | GT | Pred | TP | FP | FN "
        "| 旧P | 新P | ΔP | 旧R | 新R | ΔR | 旧F1 | 新F1 | ΔF1 |",
        "|--:|--------|---:|---:|-----:|---:|---:|---:"
        "|----:|----:|---:|----:|----:|---:|-----:|-----:|----:|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"| {i} | {r['name']} | {r['pages']} | {r['gt']} | {r['pred']} "
            f"| {r['tp']} | {r['fp']} | {r['fn']} "
            f"| {_fmt_pct(r['bl_p'])} | {_fmt_pct(r['p'])} | {_fmt_delta(r['dp'])} "
            f"| {_fmt_pct(r['bl_r'])} | {_fmt_pct(r['r'])} | {_fmt_delta(r['dr'])} "
            f"| {_fmt_pct(r['bl_f1'])} | {_fmt_pct(r['f1'])} | {_fmt_delta(r['df1'])} |"
        )
    return "\n".join(lines)


def format_csv(results: list[dict]) -> str:
    """生成 CSV 格式输出。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "#", "数据集", "页", "GT", "Pred", "TP", "FP", "FN",
        "旧P%", "新P%", "ΔP%", "旧R%", "新R%", "ΔR%", "旧F1%", "新F1%", "ΔF1%",
    ])
    for i, r in enumerate(results, 1):
        writer.writerow([
            i, r["name"], r["pages"], r["gt"], r["pred"],
            r["tp"], r["fp"], r["fn"],
            _fmt_pct(r["bl_p"]), _fmt_pct(r["p"]), _fmt_delta(r["dp"]),
            _fmt_pct(r["bl_r"]), _fmt_pct(r["r"]), _fmt_delta(r["dr"]),
            _fmt_pct(r["bl_f1"]), _fmt_pct(r["f1"]), _fmt_delta(r["df1"]),
        ])
    return buf.getvalue()


def format_text_table(results: list[dict]) -> str:
    """生成纯文本对齐表格。"""
    hdr = (
        f"{'#':>3}  {'数据集':<30}  {'页':>3}  {'GT':>4}  {'Pred':>5}  "
        f"{'TP':>4}  {'FP':>4}  {'FN':>4}  "
        f"{'旧P':>6}  {'新P':>6}  {'ΔP':>6}  "
        f"{'旧R':>6}  {'新R':>6}  {'ΔR':>6}  "
        f"{'旧F1':>6}  {'新F1':>6}  {'ΔF1':>6}"
    )
    sep = "─" * len(hdr)
    lines = [hdr, sep]

    for i, r in enumerate(results, 1):
        name = r["name"]
        if len(name) > 29:
            name = name[:28] + "…"

        def fp(v):
            return "   N/A" if v is None else f"{v*100:6.1f}"

        def fd(v):
            return "   N/A" if v is None else f"{v*100:+6.1f}"

        lines.append(
            f"{i:>3}  {name:<30}  {r['pages']:>3}  {r['gt']:>4}  {r['pred']:>5}  "
            f"{r['tp']:>4}  {r['fp']:>4}  {r['fn']:>4}  "
            f"{fp(r['bl_p'])}  {_fmt_pct_blue(r['p'])}  {_fmt_delta_color(r['dp'])}  "
            f"{fp(r['bl_r'])}  {_fmt_pct_blue(r['r'])}  {_fmt_delta_color(r['dr'])}  "
            f"{fp(r['bl_f1'])}  {fp(r['f1'])}  {fd(r['df1'])}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Benchmark 评估报告生成器")
    parser.add_argument("--cache-dir", type=str, default=None,
                        help="缓存目录 (默认: server/data/benchmark_cache)")
    parser.add_argument("--baseline", type=str, default=None,
                        help="基线 JSON 文件 (默认: data/test/baseline_141_datasets.json)")
    parser.add_argument("--sort", type=str, default="r",
                        choices=["r", "p", "f1", "dr", "dp", "df1", "name", "gt", "fn", "fp"],
                        help="排序字段 (默认: r)")
    parser.add_argument("--asc", action="store_true", help="升序排列 (默认降序)")
    parser.add_argument("--filter", type=str, default=None,
                        help="过滤条件: r<90, p<80, dr>5 等")
    parser.add_argument("--format", type=str, default="text",
                        choices=["markdown", "csv", "text"],
                        help="输出格式 (默认: text)")
    parser.add_argument("--output", type=str, default=None, help="输出到文件")
    parser.add_argument("--no-summary", action="store_true", help="不输出汇总统计")
    parser.add_argument("--no-sections", action="store_true", help="不输出分段分析")

    args = parser.parse_args()

    # 解析路径
    cache_dir = pathlib.Path(args.cache_dir) if args.cache_dir else _ROOT / "server" / "data" / "benchmark_cache"
    baseline_path = pathlib.Path(args.baseline) if args.baseline else _ROOT / "data" / "test" / "baseline_141_datasets.json"

    if not cache_dir.exists():
        print(f"错误: 缓存目录不存在: {cache_dir}", file=sys.stderr)
        sys.exit(1)

    cache_count = len(list(cache_dir.glob("*.json")))
    print(f"加载缓存: {cache_dir} ({cache_count} 个文件)", file=sys.stderr)

    # 收集结果
    results = collect_results(cache_dir, baseline_path)
    print(f"评估完成: {len(results)} 个数据集", file=sys.stderr)

    # 过滤
    if args.filter:
        results = apply_filter(results, args.filter)
        print(f"过滤后: {len(results)} 个数据集 (条件: {args.filter})", file=sys.stderr)

    # 排序
    sort_results(results, args.sort, args.asc)

    # 生成输出
    output_parts = []

    if not args.no_summary:
        output_parts.append(format_summary(results))

    if args.format == "markdown":
        output_parts.append(format_markdown_table(results))
    elif args.format == "csv":
        output_parts.append(format_csv(results))
    else:
        output_parts.append(format_text_table(results))

    if not args.no_sections and args.format != "csv":
        output_parts.append("")
        output_parts.append(format_sections(results))

    output = "\n".join(output_parts)

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"报告已保存: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
