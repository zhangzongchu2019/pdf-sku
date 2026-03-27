"""CLI 入口: python -m pdf_sku.benchmark <command>"""
from __future__ import annotations

import argparse
import asyncio
import fnmatch
import sys
from pathlib import Path

from .excel_parser import scan_datasets, load_dataset, analyze_gt_dup, DEFAULT_DATA_ROOT
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
    from .runner import BenchmarkRunner, DATASET_CONCURRENCY, archive_cache, clear_cache

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path]

    if not datasets:
        print("没有匹配的数据集")
        return

    # --force 时自动归档旧缓存并清空
    if args.force:
        tag = args.tag or ""
        archived = archive_cache(tag=tag)
        if archived:
            print(f"旧缓存已归档: {archived}")
        removed = clear_cache()
        if removed:
            print(f"已清空 {removed} 个缓存文件")

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
    from .report import (
        print_comparison, print_summary, generate_markdown_report,
        _print_page_class_distribution, _print_extra_by_class,
    )
    from .runner import BenchmarkRunner

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path and ds.excel_path]

    runner = BenchmarkRunner()
    results = []
    run_results = []

    for ds in datasets:
        try:
            load_dataset(ds)
        except Exception as e:
            print(f"跳过 {ds.name}: Excel 加载失败 ({e})")
            continue
        cached = runner.load_cached(ds)
        if not cached:
            print(f"跳过 {ds.name}: 无 Pipeline 运行结果 (先执行 run)")
            continue

        result = compare_dataset(ds, cached)
        results.append(result)
        run_results.append(cached)
        print_comparison(result)

    if results:
        print_summary(results)
        _print_page_class_distribution(run_results)
        _print_extra_by_class(results)

        report_path = Path("data/benchmark_reports/report.md")
        generate_markdown_report(results, report_path, run_results=run_results)


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
    from .report import (
        print_comparison, print_summary, generate_markdown_report,
        _print_page_class_distribution, _print_extra_by_class,
    )
    from .runner import BenchmarkRunner, DATASET_CONCURRENCY

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path and ds.excel_path]

    if not datasets:
        print("没有匹配的数据集")
        return

    # --force 时自动归档旧缓存并清空
    if args.force:
        from .runner import archive_cache, clear_cache
        tag = args.tag if hasattr(args, 'tag') and args.tag else ""
        archived = archive_cache(tag=tag)
        if archived:
            print(f"旧缓存已归档: {archived}")
        removed = clear_cache()
        if removed:
            print(f"已清空 {removed} 个缓存文件")

    runner = BenchmarkRunner()
    results = []
    run_results = []
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
                run_results.append(run_result)
            print_comparison(result)

            # 3. Export
            out_path = output_dir / f"{ds.name}_pipeline.xlsx"
            export_dataset(run_result, out_path, source_name=ds.name)

    try:
        await asyncio.gather(*[process_one(ds) for ds in datasets])

        if results:
            print_summary(results)
            _print_page_class_distribution(run_results)
            _print_extra_by_class(results)
            report_path = Path("data/benchmark_reports/report.md")
            generate_markdown_report(results, report_path, run_results=run_results)

    finally:
        runner.shutdown()


def cmd_full_db(args: argparse.Namespace) -> None:
    """全流程 + 逐个数据集写入数据库。"""
    asyncio.run(_async_full_db(args))


async def _async_full_db(args: argparse.Namespace) -> None:
    import subprocess
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from .comparator import compare_dataset
    from .report import print_comparison, print_summary
    from .runner import BenchmarkRunner, DATASET_CONCURRENCY, PAGE_CONCURRENCY
    from pdf_sku.common.models import BenchmarkRun, BenchmarkDatasetResult
    from pdf_sku.settings import settings

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path and ds.excel_path]

    # --dataset-list: 只保留 JSON 列表中指定的数据集
    if hasattr(args, 'dataset_list') and args.dataset_list:
        import json as _json
        allowed = set(_json.loads(Path(args.dataset_list).read_text()))
        datasets = [ds for ds in datasets if ds.name in allowed]

    if not datasets:
        print("没有匹配的数据集")
        return

    # --force 时自动归档旧缓存并清空
    if args.force:
        from .runner import archive_cache, clear_cache
        tag = args.tag if hasattr(args, 'tag') and args.tag else ""
        archived = archive_cache(tag=tag)
        if archived:
            print(f"旧缓存已归档: {archived}")
        removed = clear_cache()
        if removed:
            print(f"已清空 {removed} 个缓存文件")

    # DB 连接
    engine = create_async_engine(settings.database_url, pool_size=5)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # git info
    git_commit = git_branch = None
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, timeout=5
        ).strip()[:40]
        git_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, timeout=5
        ).strip()[:200]
    except Exception:
        pass

    run_tag = args.tag or f"full-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    started_at = datetime.now()

    # 创建 BenchmarkRun
    run = BenchmarkRun(
        run_tag=run_tag,
        git_commit=git_commit,
        git_branch=git_branch,
        description=args.desc or None,
        total_datasets=len(datasets),
        config={
            "page_concurrency": PAGE_CONCURRENCY,
            "dataset_concurrency": DATASET_CONCURRENCY,
        },
        started_at=started_at,
    )
    async with session_factory() as session:
        session.add(run)
        await session.commit()
        run_id = run.run_id
    print(f"\nBenchmark Run: {run_id}  tag={run_tag}")
    print(f"数据集: {len(datasets)} 个\n")

    runner = BenchmarkRunner()
    results = []
    run_results = []
    results_lock = asyncio.Lock()
    ds_sem = asyncio.Semaphore(DATASET_CONCURRENCY)
    completed = [0]

    async def process_one(ds: ReferenceDataset):
        async with ds_sem:
            print(f"\n{'='*60}")
            print(f"[{completed[0]+1}/{len(datasets)}] {ds.name}")
            print(f"{'='*60}")

            # 1. Run
            run_result = await runner.run_dataset(ds, force=args.force)

            # 2. Compare
            load_dataset(ds)
            cr = compare_dataset(ds, run_result)
            print_comparison(cr)

            # 3. 写入数据库
            details = {
                "fn_names": [
                    s.product_name or s.model_number or ""
                    for s in cr.missing_skus[:50]
                ],
                "fp_names": [
                    s.get("attributes", {}).get("product_name", "")
                    or s.get("attributes", {}).get("model_number", "")
                    for s in cr.extra_skus[:50]
                ],
            }
            gt_dup_info = analyze_gt_dup(ds.skus)
            if gt_dup_info:
                details["gt_dup_info"] = gt_dup_info

            ds_result = BenchmarkDatasetResult(
                run_id=run_id,
                dataset_name=cr.dataset_name,
                pdf_path=str(ds.pdf_path) if ds.pdf_path else None,
                gt_count=cr.expected_count,
                pred_count=cr.actual_count,
                matched_count=cr.matched_count,
                precision=cr.precision,
                recall=cr.recall,
                f1=cr.f1,
                fn_count=len(cr.missing_skus),
                fp_count=len(cr.extra_skus),
                elapsed_seconds=run_result.get("elapsed_seconds"),
                total_pages=run_result.get("total_pages"),
                details=details,
            )
            async with session_factory() as session:
                session.add(ds_result)
                await session.commit()

            async with results_lock:
                results.append(cr)
                run_results.append(run_result)
                completed[0] += 1

            print(f"  -> 已存入 DB  P={cr.precision:.1%} R={cr.recall:.1%} F1={cr.f1:.1%}")

    try:
        await asyncio.gather(*[process_one(ds) for ds in datasets])

        # 更新 BenchmarkRun 汇总
        n = len(results)
        avg_p = sum(r.precision for r in results) / n if n else None
        avg_r = sum(r.recall for r in results) / n if n else None
        avg_f1 = sum(r.f1 for r in results) / n if n else None

        async with session_factory() as session:
            from sqlalchemy import update
            await session.execute(
                update(BenchmarkRun).where(BenchmarkRun.run_id == run_id).values(
                    avg_precision=avg_p,
                    avg_recall=avg_r,
                    avg_f1=avg_f1,
                    completed_at=datetime.now(),
                )
            )
            await session.commit()

        if results:
            print_summary(results)

        print(f"\n全部完成! run_id={run_id} avg_P={avg_p:.1%} avg_R={avg_r:.1%} avg_F1={avg_f1:.1%}")

    finally:
        runner.shutdown()
        await engine.dispose()


def cmd_history(args: argparse.Namespace) -> None:
    """查看历史归档列表。"""
    from .runner import list_history

    dirs = list_history()
    if not dirs:
        print("暂无历史归档")
        return

    print(f"\n{'='*70}")
    print(f"{'归档目录':<35} {'文件数':>6} {'大小(KB)':>10}")
    print(f"{'-'*70}")
    for d in dirs:
        files = list(d.glob("*.json"))
        size_kb = sum(f.stat().st_size for f in files) / 1024
        print(f"{d.name:<35} {len(files):>6} {size_kb:>9.0f}")
    print(f"{'='*70}\n")


def cmd_compare_history(args: argparse.Namespace) -> None:
    """对比当前缓存与历史归档的 P/R/F1 变化。"""
    from .comparator import compare_dataset
    from .runner import BenchmarkRunner, list_history, HISTORY_DIR

    data_root = Path(args.data_root) if args.data_root else None
    datasets = scan_datasets(data_root)
    datasets = _filter_datasets(datasets, args.filter)
    datasets = [ds for ds in datasets if ds.pdf_path and ds.excel_path]

    # 确定历史目录
    if args.archive:
        hist_dir = HISTORY_DIR / args.archive
    else:
        dirs = list_history()
        if not dirs:
            print("暂无历史归档")
            return
        hist_dir = dirs[0]

    if not hist_dir.exists():
        print(f"归档不存在: {hist_dir}")
        return

    print(f"\n对比基准: {hist_dir.name}")

    runner = BenchmarkRunner()

    print(f"\n{'数据集':<25} {'旧P':>7} {'新P':>7} {'ΔP':>7} {'旧R':>7} {'新R':>7} {'ΔR':>7} {'旧F1':>7} {'新F1':>7} {'ΔF1':>7}")
    print(f"{'-'*90}")

    total_old_p = total_new_p = total_old_r = total_new_r = 0
    count = 0

    for ds in datasets:
        load_dataset(ds)

        # 当前结果
        current = runner.load_cached(ds)
        if not current:
            continue

        # 历史结果
        safe_name = ds.name.replace("/", "_").replace(" ", "_")
        hist_file = hist_dir / f"{safe_name}.json"
        if not hist_file.exists():
            continue

        import json
        old_data = json.loads(hist_file.read_text(encoding="utf-8"))

        old_result = compare_dataset(ds, old_data)
        new_result = compare_dataset(ds, current)

        dp = new_result.precision - old_result.precision
        dr = new_result.recall - old_result.recall
        df1 = new_result.f1 - old_result.f1

        # 颜色标记
        dp_s = f"{dp:+.1%}"
        dr_s = f"{dr:+.1%}"
        df1_s = f"{df1:+.1%}"

        print(
            f"{ds.name[:25]:<25} {old_result.precision:>6.1%} {new_result.precision:>6.1%} {dp_s:>7} "
            f"{old_result.recall:>6.1%} {new_result.recall:>6.1%} {dr_s:>7} "
            f"{old_result.f1:>6.1%} {new_result.f1:>6.1%} {df1_s:>7}"
        )

        total_old_p += old_result.precision
        total_new_p += new_result.precision
        total_old_r += old_result.recall
        total_new_r += new_result.recall
        count += 1

    if count:
        print(f"{'-'*90}")
        avg_old_p = total_old_p / count
        avg_new_p = total_new_p / count
        avg_old_r = total_old_r / count
        avg_new_r = total_new_r / count
        avg_old_f1 = 2*avg_old_p*avg_old_r/(avg_old_p+avg_old_r) if (avg_old_p+avg_old_r) else 0
        avg_new_f1 = 2*avg_new_p*avg_new_r/(avg_new_p+avg_new_r) if (avg_new_p+avg_new_r) else 0
        print(
            f"{'平均':<25} {avg_old_p:>6.1%} {avg_new_p:>6.1%} {avg_new_p-avg_old_p:>+6.1%} "
            f"{avg_old_r:>6.1%} {avg_new_r:>6.1%} {avg_new_r-avg_old_r:>+6.1%} "
            f"{avg_old_f1:>6.1%} {avg_new_f1:>6.1%} {avg_new_f1-avg_old_f1:>+6.1%}"
        )
    print()


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
    p_run.add_argument("--force", action="store_true", help="强制重新运行（自动归档旧缓存并清空）")
    p_run.add_argument("--tag", default="", help="归档标签 (如 'baseline', 'v2-scene-filter')")

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
    p_full.add_argument("--tag", default="", help="归档标签")
    p_full.add_argument("--output", default=None, help="输出目录")

    # full-db
    p_fdb = sub.add_parser("full-db", help="全流程 + 逐个写入数据库")
    p_fdb.add_argument("--filter", default=None, help="文件名模式")
    p_fdb.add_argument("--dataset-list", default=None, help="JSON文件，包含数据集名称列表")
    p_fdb.add_argument("--force", action="store_true", help="强制重新运行")
    p_fdb.add_argument("--tag", default="", help="运行标签")
    p_fdb.add_argument("--desc", default="", help="本轮修改说明")

    # history
    p_hist = sub.add_parser("history", help="查看历史归档")

    # compare-history
    p_ch = sub.add_parser("compare-history", help="对比当前结果与历史归档")
    p_ch.add_argument("archive", nargs="?", default=None, help="历史归档目录名 (默认最近一次)")
    p_ch.add_argument("--filter", default=None, help="文件名模式")

    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "run": cmd_run,
        "compare": cmd_compare,
        "export": cmd_export,
        "full": cmd_full,
        "full-db": cmd_full_db,
        "history": cmd_history,
        "compare-history": cmd_compare_history,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
