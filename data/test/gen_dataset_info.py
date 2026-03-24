#!/usr/bin/env python3
"""生成全量数据集信息 JSON（含文件路径、GT数量、基线指标）。"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pdf-sku/server/src"))
sys.path.insert(0, "/home/zzc/pdf-sku/server/src")

from pdf_sku.benchmark.excel_parser import scan_datasets, load_dataset

# Load baseline
baseline = {}
with open("/home/zzc/.claude/projects/-home-zzc-pdf-sku/memory/benchmark-142-datasets.json") as f:
    for ds in json.load(f):
        baseline[ds["name"]] = ds

# Scan all datasets
all_ds = scan_datasets()

# Load sample list
with open("/tmp/sample_datasets.json") as f:
    sample_names = set(json.load(f))

results = []
for ds in all_ds:
    load_dataset(ds)
    gt_count = len(ds.skus) if ds.skus else 0
    bl = baseline.get(ds.name, {})

    results.append({
        "name": ds.name,
        "folder": str(ds.folder),
        "pdf_path": str(ds.pdf_path) if ds.pdf_path else "",
        "pdf_filename": ds.pdf_path.name if ds.pdf_path else "",
        "excel_path": str(ds.excel_path) if ds.excel_path else "",
        "excel_filename": ds.excel_path.name if ds.excel_path else "",
        "gt_count": gt_count,
        "in_sample": ds.name in sample_names,
        "baseline_actual": bl.get("actual", None),
        "baseline_matched": bl.get("matched", None),
        "baseline_fp": bl.get("fp", None),
        "baseline_fn": bl.get("fn", None),
        "baseline_p": bl.get("p", None),
        "baseline_r": bl.get("r", None),
        "baseline_f1": bl.get("f1", None),
    })

# Save as JSON
out_path = "/tmp/all_datasets_info.json"
with open(out_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Summary
in_sample = [r for r in results if r["in_sample"]]
has_baseline = [r for r in results if r["baseline_p"] is not None]
print(f"总数据集: {len(results)}")
print(f"在 sample 中: {len(in_sample)}")
print(f"有基线数据: {len(has_baseline)}")
print(f"已保存到 {out_path}")
