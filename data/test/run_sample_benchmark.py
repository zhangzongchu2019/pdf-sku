#!/usr/bin/env python3
"""跑 81 个抽样数据集的 benchmark。"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "server" / "src"))

from pdf_sku.benchmark.excel_parser import scan_datasets
from pdf_sku.benchmark.runner import BenchmarkRunner, archive_cache, clear_cache

SAMPLE_FILE = "/tmp/sample_datasets.json"
DATASET_CONCURRENCY = 3


async def main():
    with open(SAMPLE_FILE) as f:
        sample_names = set(json.load(f))

    all_ds = scan_datasets()
    datasets = [ds for ds in all_ds if ds.name in sample_names and ds.pdf_path]

    found_names = {ds.name for ds in datasets}
    missing = sample_names - found_names
    if missing:
        print(f"警告: {len(missing)} 个数据集未找到: {missing}")

    print(f"共 {len(datasets)} 个数据集待处理")

    # 归档并清空旧缓存
    archived = archive_cache(tag="pre-81-sample")
    if archived:
        print(f"旧缓存已归档: {archived}")
    removed = clear_cache()
    if removed:
        print(f"已清空 {removed} 个缓存文件")

    runner = BenchmarkRunner()
    sem = asyncio.Semaphore(DATASET_CONCURRENCY)
    done = 0

    async def run_one(ds):
        nonlocal done
        async with sem:
            print(f"  [{done+1}/{len(datasets)}] {ds.name} ...")
            await runner.run_dataset(ds, force=True)
            done += 1
            print(f"  [{done}/{len(datasets)}] {ds.name} 完成")

    try:
        await asyncio.gather(*[run_one(ds) for ds in datasets])
    finally:
        runner.shutdown()

    print(f"\n全部完成! 共处理 {done} 个数据集")
    print("运行 compare: .venv/bin/python -m pdf_sku.benchmark compare")


if __name__ == "__main__":
    asyncio.run(main())
