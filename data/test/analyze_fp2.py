"""Analyze FP root causes for 31 datasets with P<80%."""
import json
import os
from collections import Counter

CACHE_DIR = "/home/zzc/pdf-sku/server/data/benchmark_cache"
EXCEL_DIR = "/home/zzc/pdf-sku/server/data/benchmark_excel"

DATASETS = [
    ("2025相约餐饮家具", 29, 318),
    ("上下子母床2025-9", 9, 59),
    ("梦芯豪方腾家具新款电子图册", 8, 50),
    ("屏风图册", 15, 70),
    ("2025秋季新款电子画册", 8, 27),
    ("大理石圆桌（2025.10）", 32, 92),
    ("万日红美式轻奢BAIGAT(1)", 57, 134),
    ("皇钰思家具2025电子版", 66, 144),
    ("2024禧月【夏日贝壳】--30个商品0.6H", 30, 62),
    ("万日红家具美式中古图册", 81, 166),
    ("Elysium富誉", 129, 252),
    ("2025-7银星茶台-岛台图册-秋季版", 30, 57),
    ("2025新款精品妆台", 133, 244),
    ("2024图册-WS系列", 111, 203),
    ("万日红美式轻奢画册2024.1.1", 139, 253),
    ("茶台", 29, 50),
    ("2025新款电子版", 45, 76),
    ("组合茶几小件图册-24年9月", 97, 155),
    ("万日红2025中古风家具", 58, 89),
    ("经典美式套房2025", 102, 156),
    ("刘顺办公家具", 225, 343),
    ("鹏远家具梳妆台", 107, 163),
    ("2025主卧床合集图册", 48, 70),
    ("万日红极简现代沙发(1)", 42, 60),
    ("普通五金餐椅", 187, 264),
    ("壹业(1)", 600, 834),
    ("Elysium目居", 404, 548),
    ("万日红现代简约图册", 87, 117),
    ("PU8303电子图册", 145, 192),
    ("万日红美式香槟图册", 42, 55),
    ("不锈钢餐桌1", 312, 391),
]


def load_gt_models(name):
    """Try to load ground truth models from Excel benchmark data."""
    # Check if there's a benchmark config
    config_path = "/home/zzc/pdf-sku/server/data/benchmark_datasets.json"
    if os.path.exists(config_path):
        with open(config_path) as f:
            configs = json.load(f)
        for c in configs:
            if c.get("name") == name:
                excel = c.get("excel", "")
                if excel and os.path.exists(excel):
                    return load_excel_models(excel)
    return set()


def load_excel_models(path):
    """Load model numbers from Excel."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        models = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and len(row) > 0:
                m = str(row[0]).strip() if row[0] else ""
                if m:
                    models.add(m.upper())
        return models
    except Exception:
        return set()


def analyze_dataset(name, expected, actual):
    path = os.path.join(CACHE_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None

    with open(path) as f:
        data = json.load(f)

    # Collect all SKUs from pages
    all_skus = []
    for page in data.get("pages", []):
        for sku in page.get("skus", []):
            sku["_page_no"] = page["page_no"]
            sku["_page_type"] = page.get("page_type", "")
            sku["_fitz_page_class"] = page.get("fitz_page_class", "")
            all_skus.append(sku)

    fp_count = actual - expected

    # Analyze characteristics of ALL SKUs (since we can't easily distinguish TP/FP without GT matching)
    page_class_counter = Counter()
    page_type_counter = Counter()
    name_only_count = 0
    has_model_count = 0
    has_price_count = 0
    has_specs_count = 0
    low_conf_count = 0

    all_names = []
    all_models = []

    for sku in all_skus:
        attrs = sku.get("attributes", {})
        page_class_counter[sku["_fitz_page_class"]] += 1
        page_type_counter[sku["_page_type"]] += 1

        model = (attrs.get("model_number") or "").strip()
        price = (attrs.get("price") or "").strip()
        specs_raw = attrs.get("specs") or ""
        specs = str(specs_raw).strip() if specs_raw else ""
        pname = (attrs.get("product_name") or "").strip()

        if model:
            has_model_count += 1
            all_models.append(model.upper())
        if price:
            has_price_count += 1
        if specs:
            has_specs_count += 1

        conf = sku.get("confidence", 1.0)
        if conf < 0.5:
            low_conf_count += 1

        if not model and not price and not specs:
            name_only_count += 1

        all_names.append(pname)

    # Check duplicates (same model or same name on different pages)
    model_counts = Counter(all_models)
    dup_models = {m: c for m, c in model_counts.items() if c > 1 and m}
    dup_model_excess = sum(c - 1 for c in dup_models.values())

    name_counts = Counter(all_names)
    dup_names = {n: c for n, c in name_counts.items() if c > 1 and n}
    dup_name_excess = sum(c - 1 for c in dup_names.values())

    # Sample SKUs
    samples = []
    for sku in all_skus[:10]:
        attrs = sku.get("attributes", {})
        samples.append({
            "page": sku["_page_no"],
            "pc": sku["_fitz_page_class"],
            "pt": sku["_page_type"],
            "name": (attrs.get("product_name") or "")[:35],
            "model": (attrs.get("model_number") or "")[:20],
            "price": (attrs.get("price") or "")[:15],
            "conf": round(sku.get("confidence", 0), 3),
            "specs": (attrs.get("specs") or "")[:40],
        })

    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "fp": fp_count,
        "total_skus": len(all_skus),
        "page_classes": dict(page_class_counter.most_common(5)),
        "page_types": dict(page_type_counter.most_common(5)),
        "name_only": name_only_count,
        "has_model": has_model_count,
        "has_price": has_price_count,
        "has_specs": has_specs_count,
        "low_conf": low_conf_count,
        "dup_model_excess": dup_model_excess,
        "dup_name_excess": dup_name_excess,
        "dup_models_top": dict(list(sorted(dup_models.items(), key=lambda x: -x[1]))[:5]),
        "dup_names_top": dict(list(sorted(dup_names.items(), key=lambda x: -x[1]))[:3]),
        "samples": samples,
    }


for ds_name, expected, actual in DATASETS:
    r = analyze_dataset(ds_name, expected, actual)
    if not r:
        print(f"\n{'='*80}")
        print(f"DATASET: {ds_name} — FILE NOT FOUND")
        continue

    print(f"\n{'='*80}")
    print(f"DATASET: {ds_name}  |  期望={expected} 实际={r['total_skus']} FP≈{r['fp']}")
    print(f"  PageClass分布: {r['page_classes']}")
    print(f"  PageType分布: {r['page_types']}")
    print(f"  Name-only(无model/price/specs): {r['name_only']}/{r['total_skus']} ({100*r['name_only']//max(r['total_skus'],1)}%)")
    print(f"  有model: {r['has_model']}, 有price: {r['has_price']}, 有specs: {r['has_specs']}")
    print(f"  低置信度(<0.5): {r['low_conf']}")
    print(f"  重复model数(excess): {r['dup_model_excess']}, 重复name数(excess): {r['dup_name_excess']}")
    if r['dup_models_top']:
        print(f"  Top重复models: {r['dup_models_top']}")
    if r['dup_names_top']:
        print(f"  Top重复names: {r['dup_names_top']}")
    print(f"  样本SKUs:")
    for s in r['samples']:
        print(f"    p{s['page']:>2} [{s['pc']:<12}] {s['pt']} conf={s['conf']:.3f}: {s['name']:<35} model={s['model']:<20} price={s['price']}")
