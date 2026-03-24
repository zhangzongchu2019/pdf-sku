"""快速检查 benchmark 进度和结果"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

from pdf_sku.benchmark.excel_parser import scan_datasets, load_dataset
from pdf_sku.benchmark.comparator import compare_dataset

cache = pathlib.Path("data/benchmark_cache")
cached = list(cache.glob("*.json"))
print(f"已完成: {len(cached)}/64\n")

datasets = scan_datasets()
# 只看有缓存的
ds_map = {ds.name: ds for ds in datasets}

print(f"{'数据集':<40} {'期望':>5} {'实际':>5} {'匹配':>5} {'FP':>5} {'FN':>5} {'P':>7} {'R':>7} {'F1':>7}")
print("-" * 115)

total_exp = total_act = total_match = 0
rows = []

for cp in sorted(cached):
    name = cp.stem
    ds = ds_map.get(name)
    if not ds:
        continue
    load_dataset(ds)
    try:
        run_data = json.loads(cp.read_text())
        result = compare_dataset(ds, run_data)
    except Exception as e:
        print(f"{name:<40} ERROR: {e}")
        continue

    exp = result.expected_count
    act = result.actual_count
    m = result.matched_count
    fp = act - m
    fn = exp - m
    p = result.precision * 100
    r = result.recall * 100
    f1 = result.f1 * 100

    total_exp += exp
    total_act += act
    total_match += m
    rows.append((name, exp, act, m, fp, fn, p, r, f1))

for name, exp, act, m, fp, fn, p, r, f1 in rows:
    flag = " ⚠" if r < 60 or p < 50 else ""
    print(f"{name:<40} {exp:>5} {act:>5} {m:>5} {fp:>5} {fn:>5} {p:>6.1f}% {r:>6.1f}% {f1:>6.1f}%{flag}")

print("-" * 115)
fp = total_act - total_match
fn = total_exp - total_match
p = total_match / total_act * 100 if total_act else 0
r = total_match / total_exp * 100 if total_exp else 0
f1 = 2 * p * r / (p + r) if (p + r) else 0
print(f"{'总计':<40} {total_exp:>5} {total_act:>5} {total_match:>5} {fp:>5} {fn:>5} {p:>6.1f}% {r:>6.1f}% {f1:>6.1f}%")
