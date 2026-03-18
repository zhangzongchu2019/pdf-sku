"""逐个重跑受影响数据集，每个完成后立即显示 compare 结果。"""
import asyncio
import logging
import os
import sys
import time

# 抑制所有 structlog/logging 输出，只显示我们的进度
logging.disable(logging.CRITICAL)
os.environ["STRUCTLOG_LEVEL"] = "CRITICAL"

import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
)

from pdf_sku.benchmark.excel_parser import scan_datasets, load_dataset
from pdf_sku.benchmark.comparator import compare_dataset
from pdf_sku.benchmark.runner import BenchmarkRunner

EXCLUDE_GT = {
    '恒瑞', '封面底编藤_纯图版', '扫描版-新中古图册（K）', '艾星-餐桌椅配套系列',
    '新中古图册（K）--42个商品75分钟', '新中古图册（K）--42个商品75分钟 - 副本',
    '万鑫休闲椅-货号WX-01开始',  # 纯图片GT，无文字标注，无法精确评测
}

# 全量模式: TARGET 为空则跑所有有效数据集
TARGET: set[str] = {
    '万日红现代软床Y图册',          # text_rule_fallback + IMG_LABEL
    '万鑫极简沙发图(2)',            # pure_image_text_fallback
    '万日红家具—原创设计师合集(1)',   # expected_sku_range fix + slice_range
}


async def main():
    datasets = scan_datasets()
    runner = BenchmarkRunner()

    if TARGET:
        to_run = [ds for ds in datasets
                  if ds.name in TARGET and ds.pdf_path and ds.excel_path]
    else:
        to_run = [ds for ds in datasets
                  if ds.pdf_path and ds.excel_path and ds.name not in EXCLUDE_GT]

    if not to_run:
        print("没有匹配的数据集")
        return

    print(f"{'='*80}")
    print(f"待重跑: {len(to_run)} 个数据集")
    print(f"{'='*80}\n")

    for i, ds in enumerate(to_run, 1):
        print(f"[{i}/{len(to_run)}] 正在运行: {ds.name} ...", flush=True)
        t0 = time.time()

        try:
            result = await runner.run_dataset(ds, force=True)
            elapsed = time.time() - t0
            total_skus = result.get("total_skus", 0)
            total_pages = result.get("total_pages", 0)

            # 立即 compare
            try:
                load_dataset(ds)
                comp = compare_dataset(ds, result)
                p = comp.precision
                r = comp.recall
                f1 = comp.f1
                fp = comp.actual_count - comp.matched_count
                fn = comp.expected_count - comp.matched_count

                print(f"  ✓ 完成 ({elapsed:.0f}s) | "
                      f"页={total_pages} SKU={total_skus} | "
                      f"P={p:.1%} R={r:.1%} F1={f1:.1%} | "
                      f"期望={comp.expected_count} 匹配={comp.matched_count} "
                      f"FP={fp} FN={fn}")
            except Exception as e:
                print(f"  ✓ 完成 ({elapsed:.0f}s) | "
                      f"页={total_pages} SKU={total_skus} | "
                      f"Compare 失败: {e}")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ✗ 失败 ({elapsed:.0f}s): {e}")

        sys.stdout.flush()

    runner.shutdown()
    print(f"\n{'='*80}")
    print("全部完成!")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
