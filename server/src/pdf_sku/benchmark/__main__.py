"""CLI 入口: python -m pdf_sku.benchmark <command>"""
from __future__ import annotations

import argparse
import asyncio
import fnmatch
import sys
from pathlib import Path

from .excel_parser import scan_datasets, load_dataset, DEFAULT_DATA_ROOT
from .models import ReferenceDataset


def _filter_datasets(
    datasets: list[ReferenceDataset], pattern: str | None
) -> list[ReferenceDataset]:
    if not pattern:
        return datasets
    return [ds for ds in datasets if fnmatch.fnmatch(ds.name, pattern)]


def cmd_scan(args: argparse.Namespace) -> None:
    """扫描参考数据目录。"""
    from .report import print_scan_summary

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)

    # 加载 Excel 统计
    for ds in datasets:
        load_dataset(ds)

    print_scan_summary(datasets)

    # 统计
    paired = sum(1 for ds in datasets if ds.pdf_path and ds.excel_path)
    no_excel = [ds.name for ds in datasets if ds.pdf_path and not ds.excel_path]

    if no_excel:
        print(f"缺少 Excel ({len(no_excel)}): {', '.join(no_excel[:5])}")


def cmd_run(args: argparse.Namespace) -> None:
    """运行 Pipeline。"""
    asyncio.run(_async_run(args))


async def _async_run(args: argparse.Namespace) -> None:
    from .runner import BenchmarkRunner, DATASET_CONCURRENCY

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path]

    if not datasets:
        print("没有匹配的数据集")
        return

    runner = BenchmarkRunner()
    ds_sem = asyncio.Semaphore(DATASET_CONCURRENCY)

    async def run_one(ds: ReferenceDataset):
        async with ds_sem:
            print(f"\n处理: {ds.name} ...")
            await runner.run_dataset(ds, force=args.force)

    try:
        await asyncio.gather(*[run_one(ds) for ds in datasets])
    finally:
        runner.shutdown()


def cmd_compare(args: argparse.Namespace) -> None:
    """对比 Pipeline 输出与参考 Excel。"""
    from .comparator import compare_dataset
    from .report import print_comparison, print_summary, generate_markdown_report
    from .runner import BenchmarkRunner

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path and ds.excel_path]

    runner = BenchmarkRunner()
    results = []

    for ds in datasets:
        load_dataset(ds)
        cached = runner.load_cached(ds)
        if not cached:
            print(f"跳过 {ds.name}: 无 Pipeline 运行结果 (先执行 run)")
            continue

        result = compare_dataset(ds, cached)
        results.append(result)
        print_comparison(result)

    if results:
        print_summary(results)

        report_path = Path("data/benchmark_reports/report.md")
        generate_markdown_report(results, report_path)


def cmd_export(args: argparse.Namespace) -> None:
    """导出 Pipeline 结果为标准 Excel。"""
    from .excel_exporter import export_dataset
    from .runner import BenchmarkRunner

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)

    runner = BenchmarkRunner()
    output_dir = Path(args.output or "data/benchmark_exports")

    for ds in datasets:
        cached = runner.load_cached(ds)
        if not cached:
            print(f"跳过 {ds.name}: 无 Pipeline 运行结果")
            continue

        out_path = output_dir / f"{ds.name}_pipeline.xlsx"
        export_dataset(cached, out_path, source_name=ds.name)


def cmd_full(args: argparse.Namespace) -> None:
    """全流程: run → compare → export。"""
    asyncio.run(_async_full(args))


async def _async_full(args: argparse.Namespace) -> None:
    from .comparator import compare_dataset
    from .excel_exporter import export_dataset
    from .report import print_comparison, print_summary, generate_markdown_report
    from .runner import BenchmarkRunner, DATASET_CONCURRENCY

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path and ds.excel_path]

    if not datasets:
        print("没有匹配的数据集")
        return

    runner = BenchmarkRunner()
    results = []
    results_lock = asyncio.Lock()
    output_dir = Path(args.output or "data/benchmark_exports")
    ds_sem = asyncio.Semaphore(DATASET_CONCURRENCY)

    async def process_one(ds: ReferenceDataset):
        async with ds_sem:
            print(f"\n{'='*60}")
            print(f"全流程: {ds.name}")
            print(f"{'='*60}")

            # 1. Run (并行页面处理)
            run_result = await runner.run_dataset(ds, force=args.force)

            # 2. Compare
            load_dataset(ds)
            result = compare_dataset(ds, run_result)
            async with results_lock:
                results.append(result)
            print_comparison(result)

            # 3. Export
            out_path = output_dir / f"{ds.name}_pipeline.xlsx"
            export_dataset(run_result, out_path, source_name=ds.name)

    try:
        await asyncio.gather(*[process_one(ds) for ds in datasets])

        if results:
            print_summary(results)
            report_path = Path("data/benchmark_reports/report.md")
            generate_markdown_report(results, report_path)

    finally:
        runner.shutdown()


def main():
    parser = argparse.ArgumentParser(
        prog="pdf_sku.benchmark",
        description="PDF-SKU 批量对比验证工具",
    )
    parser.add_argument(
        "--data-root", default=None,
        help=f"参考数据根目录 (默认: {DEFAULT_DATA_ROOT})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="扫描参考数据")
    p_scan.add_argument("--filter", default=None, help="文件名模式 (如 '铝合金*')")

    # run
    p_run = sub.add_parser("run", help="运行 Pipeline")
    p_run.add_argument("--filter", default=None, help="文件名模式")
    p_run.add_argument("--force", action="store_true", help="强制重新运行（忽略缓存）")

    # compare
    p_cmp = sub.add_parser("compare", help="对比结果")
    p_cmp.add_argument("--filter", default=None, help="文件名模式")

    # export
    p_exp = sub.add_parser("export", help="导出 Excel")
    p_exp.add_argument("--filter", default=None, help="文件名模式")
    p_exp.add_argument("--output", default=None, help="输出目录")

    # full
    p_full = sub.add_parser("full", help="全流程 (run + compare + export)")
    p_full.add_argument("--filter", default=None, help="文件名模式")
    p_full.add_argument("--force", action="store_true", help="强制重新运行")
    p_full.add_argument("--output", default=None, help="输出目录")

    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "run": cmd_run,
        "compare": cmd_compare,
        "export": cmd_export,
        "full": cmd_full,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
