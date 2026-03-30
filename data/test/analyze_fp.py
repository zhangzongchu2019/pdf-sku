"""Analyze FP root causes for 31 datasets with P<80%."""
import json
import os
from collections import Counter, defaultdict

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", "data", "benchmark_cache")

DATASETS = [
    "2025相约餐饮家具",
    "上下子母床2025-9",
    "梦芯豪方腾家具新款电子图册",
    "屏风图册",
    "2025秋季新款电子画册",
    "大理石圆桌（2025.10）",
    "万日红美式轻奢BAIGAT(1)",
    "皇钰思家具2025电子版",
    "2024禧月【夏日贝壳】--30个商品0.6H",
    "万日红家具美式中古图册",
    "Elysium富誉",
    "2025-7银星茶台-岛台图册-秋季版",
    "2025新款精品妆台",
    "2024图册-WS系列",
    "万日红美式轻奢画册2024.1.1",
    "茶台",
    "2025新款电子版",
    "组合茶几小件图册-24年9月",
    "万日红2025中古风家具",
    "经典美式套房2025",
    "刘顺办公家具",
    "鹏远家具梳妆台",
    "2025主卧床合集图册",
    "万日红极简现代沙发(1)",
    "普通五金餐椅",
    "壹业(1)",
    "Elysium目居",
    "万日红现代简约图册",
    "PU8303电子图册",
    "万日红美式香槟图册",
    "不锈钢餐桌1",
]

def analyze_dataset(name):
    path = os.path.join(CACHE_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {"name": name, "error": "file not found"}

    with open(path, "r") as f:
        data = json.load(f)

    # Get pipeline results
    skus = data.get("skus", [])
    gt_models = set()
    gt_data = data.get("ground_truth", {})
    if isinstance(gt_data, dict):
        for item in gt_data.get("items", []):
            m = item.get("model", "").strip()
            if m:
                gt_models.add(m.upper())
    elif isinstance(gt_data, list):
        for item in gt_data:
            m = item.get("model", "").strip()
            if m:
                gt_models.add(m.upper())

    # Classify each SKU as TP or FP
    # We need to figure out matching logic - let's check what fields exist
    fp_skus = []
    tp_skus = []

    for sku in skus:
        model = (sku.get("model") or "").strip().upper()
        # Simple match: if model matches any GT model
        matched = False
        if model and model in gt_models:
            matched = True
        if not matched and model:
            # Try partial match
            for gt_m in gt_models:
                if model in gt_m or gt_m in model:
                    matched = True
                    break
        if matched:
            tp_skus.append(sku)
        else:
            fp_skus.append(sku)

    # Analyze FP characteristics
    # 1. Page class distribution
    page_classes = Counter()
    for sku in fp_skus:
        pc = sku.get("page_class", "unknown")
        page_classes[pc] += 1

    # 2. Name-only analysis
    name_only_count = 0
    has_model_count = 0
    has_price_count = 0
    has_specs_count = 0
    has_dimensions_count = 0

    for sku in fp_skus:
        model = (sku.get("model") or "").strip()
        price = sku.get("price")
        specs = sku.get("specifications") or sku.get("specs") or {}
        dimensions = sku.get("dimensions") or ""
        material = sku.get("material") or ""

        has_model = bool(model)
        has_price_val = bool(price)
        has_specs_val = bool(specs) and len(specs) > 0 if isinstance(specs, dict) else bool(specs)
        has_dim = bool(dimensions)
        has_mat = bool(material)

        if has_model:
            has_model_count += 1
        if has_price_val:
            has_price_count += 1
        if has_specs_val:
            has_specs_count += 1
        if has_dim:
            has_dimensions_count += 1

        if not has_model and not has_price_val and not has_dim and not has_mat:
            name_only_count += 1

    # 3. Check for duplicate names (slice duplication)
    fp_names = [sku.get("name", "") for sku in fp_skus]
    name_counts = Counter(fp_names)
    duplicate_names = {n: c for n, c in name_counts.items() if c > 1 and n}
    duplicate_count = sum(c - 1 for c in duplicate_names.values())

    # 4. Sample FP SKUs for inspection
    sample_fps = []
    for sku in fp_skus[:8]:
        sample_fps.append({
            "name": sku.get("name", ""),
            "model": sku.get("model", ""),
            "price": sku.get("price"),
            "page": sku.get("page_number", ""),
            "page_class": sku.get("page_class", ""),
            "confidence": sku.get("confidence", ""),
            "material": sku.get("material", ""),
            "dimensions": sku.get("dimensions", ""),
        })

    return {
        "name": name,
        "total_skus": len(skus),
        "fp_count": len(fp_skus),
        "tp_count": len(tp_skus),
        "gt_count": len(gt_models),
        "page_classes": dict(page_classes.most_common(5)),
        "name_only_count": name_only_count,
        "has_model_count": has_model_count,
        "has_price_count": has_price_count,
        "duplicate_count": duplicate_count,
        "duplicate_names_top": dict(Counter(duplicate_names).most_common(5)),
        "sample_fps": sample_fps,
    }

for ds_name in DATASETS:
    result = analyze_dataset(ds_name)
    if "error" in result:
        print(f"\n{'='*60}")
        print(f"DATASET: {ds_name} — ERROR: {result['error']}")
        continue

    print(f"\n{'='*60}")
    print(f"DATASET: {ds_name}")
    print(f"  Total SKUs: {result['total_skus']}, FP: {result['fp_count']}, TP: {result['tp_count']}, GT models: {result['gt_count']}")
    print(f"  Page classes: {result['page_classes']}")
    print(f"  Name-only (no model/price/dims/material): {result['name_only_count']}/{result['fp_count']}")
    print(f"  Has model: {result['has_model_count']}, Has price: {result['has_price_count']}")
    print(f"  Duplicate names (slice dup): {result['duplicate_count']}")
    if result['duplicate_names_top']:
        print(f"  Top duplicates: {result['duplicate_names_top']}")
    print(f"  Sample FPs:")
    for s in result['sample_fps']:
        print(f"    p{s['page']} [{s['page_class']}] conf={s['confidence']}: {s['name'][:40]} | model={s['model']} | price={s['price']} | mat={s['material'][:20] if s['material'] else ''} | dim={s['dimensions'][:20] if s['dimensions'] else ''}")
