"""
图册级预扫描: fitz 全文扫描 → 主营品类识别。

~50ms / 100 页。在 Pipeline 入口调用一次，结果传递给每页的 sku_scorer。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

# 型号模式 (与 sku_dedup 保持一致)
_MODEL_RE = re.compile(r'[A-Za-z]{1,5}[-\s]?\d{3,}|[A-Z]{2,}\d+|\d{3,}#')

# ── 家具品类词典: 标准名 → 同义词/变体列表 ──
FURNITURE_CATEGORIES: dict[str, list[str]] = {
    "沙发": ["沙发", "sofa", "couch"],
    "床": ["床", "大床", "双人床", "单人床", "bed"],
    "床头柜": ["床头柜", "床边柜", "nightstand", "bedside"],
    "衣柜": ["衣柜", "衣橱", "wardrobe", "closet"],
    "餐桌": ["餐桌", "饭桌", "dining table"],
    "餐椅": ["餐椅", "dining chair"],
    "书桌": ["书桌", "办公桌", "写字台", "desk"],
    "书柜": ["书柜", "书架", "bookcase", "bookshelf"],
    "电视柜": ["电视柜", "tv cabinet"],
    "茶几": ["茶几", "coffee table"],
    "边几": ["边几", "边桌", "side table", "end table"],
    "鞋柜": ["鞋柜", "shoe cabinet"],
    "梳妆台": ["梳妆台", "化妆台", "dresser", "vanity"],
    "斗柜": ["斗柜", "五斗柜", "chest"],
    "玄关柜": ["玄关柜", "entrance cabinet"],
    "酒柜": ["酒柜", "wine cabinet"],
    "椅子": ["椅子", "chair", "休闲椅", "扶手椅", "躺椅"],
    "柜子": ["柜子", "柜", "cabinet"],
    "床垫": ["床垫", "mattress"],
    "沙发床": ["沙发床", "sofa bed"],
}

# 构建: 同义词 → 标准品类名 映射 (小写)
_SYNONYM_TO_CATEGORY: dict[str, str] = {}
for _cat, _synonyms in FURNITURE_CATEGORIES.items():
    for _syn in _synonyms:
        _SYNONYM_TO_CATEGORY[_syn.lower()] = _cat

# 组合图册关键词
_COMBO_KEYWORDS = {"配套", "套间", "套装", "组合", "含", "搭配", "成套"}


@dataclass
class CatalogProfile:
    """图册级品类画像。"""
    main_categories: set[str] = field(default_factory=set)      # 主营品类
    category_page_counts: dict[str, int] = field(default_factory=dict)
    total_pages: int = 0
    dominant_category: str = ""                                  # 最高频品类
    model_co_occurred: set[str] = field(default_factory=set)     # 与型号共现的品类
    exclusive_pages: dict[str, int] = field(default_factory=dict)  # 品类独占页数
    is_combo_catalog: bool = False                               # 是否为组合图册
    combo_keyword_ratio: float = 0.0                             # 组合关键词页占比
    multi_category_page_ratio: float = 0.0                       # 多品类共现页占比
    is_pure_image_catalog: bool = False                          # 纯图产品目录（大部分页面无文字）
    is_one_product_per_page: bool = False                        # 每页一个产品（多视图纯图目录）
    brand_names: set[str] = field(default_factory=set)           # 封面/扉页大字体品牌名
    model_prefixes: set[str] = field(default_factory=set)        # 高频型号前缀 (BT-、NAV、FP-)
    all_model_numbers: set[str] = field(default_factory=set)     # 全文出现的所有型号


_PREFIX_RE = re.compile(r'^([A-Za-z]{1,5})[-\s]?\d')


def _extract_model_prefix(model: str) -> str:
    """从型号中提取字母前缀: BT-SF711 → BT, NAV332 → NAV, FP-35 → FP。"""
    m = _PREFIX_RE.match(model)
    return m.group(1).upper() if m else ""


def _collect_brand_candidate(span: dict, brand_set: set[str]) -> None:
    """从 span 级别信息中采集品牌名候选。"""
    size = span.get("size", 0)
    text = (span.get("text") or "").strip()
    if size >= 16 and 2 <= len(text) <= 15:
        # 排除纯数字、纯标点、品类同义词
        if re.match(r'^[\d\s\-_.,:;!?]+$', text):
            return
        text_lower = text.lower()
        if text_lower in _SYNONYM_TO_CATEGORY:
            return
        # 排除常见非品牌大字: 目录、前言、产品等
        _NON_BRAND = {"目录", "前言", "后记", "附录", "产品", "系列", "index",
                       "contents", "catalog", "catalogue", "page", "product"}
        if text_lower in _NON_BRAND:
            return
        brand_set.add(text)


def scan_catalog(pdf_path: str) -> CatalogProfile:
    """fitz 全文预扫描，识别图册主营品类。

    主营品类判定:
    - 与型号共现 (同页存在型号模式)
    - 或出现页数 ≥ max(2, total_pages × 0.1)
    """
    import fitz

    profile = CatalogProfile()

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning("catalog_scan_failed", error=str(e))
        return profile

    try:
        profile.total_pages = doc.page_count

        # 逐页扫描
        page_cats: dict[str, set[int]] = {}  # 品类 → 出现页号集合
        model_cats: set[str] = set()         # 与型号共现的品类
        # 独占页: 某品类是该页唯一品类 (判断是否为真正产品线)
        exclusive_cats: dict[str, int] = {}  # 品类 → 独占页数
        # 组合检测计数器
        combo_keyword_pages = 0              # 含组合关键词的页数
        multi_cat_pages = 0                  # 含 ≥2 品类的页数
        content_pages = 0                    # 有内容的页数
        # 型号采集
        all_models: set[str] = set()
        prefix_counter: dict[str, int] = {}  # 型号前缀 → 出现次数
        # 每页一产品检测: 无文字 + 少量图片 (1-4 张, 多视图)
        sparse_img_pages = 0  # 无文字 + 有图片的页面数
        # 品牌名检测页: 前 3 页 + 末页
        brand_scan_pages = set(range(min(3, doc.page_count)))
        if doc.page_count > 1:
            brand_scan_pages.add(doc.page_count - 1)

        for page_idx in range(doc.page_count):
            try:
                page = doc[page_idx]
                text = page.get_text().lower()
            except Exception:
                continue

            if not text or len(text.strip()) < 5:
                # 统计无文字但有少量图片的页面 (多视图产品页)
                try:
                    img_count = len(page.get_images())
                    if 1 <= img_count <= 4:
                        sparse_img_pages += 1
                except Exception:
                    pass
                continue

            content_pages += 1
            has_model = bool(_MODEL_RE.search(text))

            # ── 型号采集 ──
            page_models = _MODEL_RE.findall(text.upper())
            for m in page_models:
                all_models.add(m)
                prefix = _extract_model_prefix(m)
                if prefix:
                    prefix_counter[prefix] = prefix_counter.get(prefix, 0) + 1

            # ── 品牌名检测 (前 3 页 + 末页) ──
            if page_idx in brand_scan_pages:
                try:
                    page_dict = page.get_text("dict")
                    for block in page_dict.get("blocks", []):
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                _collect_brand_candidate(
                                    span, profile.brand_names)
                except Exception:
                    pass  # dict 解析失败不影响主流程

            # 组合关键词检测
            if any(kw in text for kw in _COMBO_KEYWORDS):
                combo_keyword_pages += 1

            # 检测品类词
            found_cats: set[str] = set()
            for synonym, cat_name in _SYNONYM_TO_CATEGORY.items():
                if synonym in text:
                    found_cats.add(cat_name)

            for cat in found_cats:
                if cat not in page_cats:
                    page_cats[cat] = set()
                page_cats[cat].add(page_idx)
                if has_model:
                    model_cats.add(cat)

            # 多品类共现页
            if len(found_cats) >= 2:
                multi_cat_pages += 1

            # 独占页: 该页只出现一个品类
            if len(found_cats) == 1 and has_model:
                cat = next(iter(found_cats))
                exclusive_cats[cat] = exclusive_cats.get(cat, 0) + 1

        # 型号前缀: 频次 ≥ 3 的加入 profile
        profile.all_model_numbers = all_models
        profile.model_prefixes = {
            p for p, cnt in prefix_counter.items() if cnt >= 3
        }
    finally:
        doc.close()

    # 统计
    profile.category_page_counts = {
        cat: len(pages) for cat, pages in page_cats.items()
    }
    profile.model_co_occurred = model_cats
    profile.exclusive_pages = exclusive_cats

    # 主营品类判定
    threshold = max(2, int(profile.total_pages * 0.1))
    for cat, pages in page_cats.items():
        if cat in model_cats or len(pages) >= threshold:
            profile.main_categories.add(cat)

    # 最高频品类
    if profile.category_page_counts:
        profile.dominant_category = max(
            profile.category_page_counts,
            key=profile.category_page_counts.get,  # type: ignore
        )

    # 组合图册检测
    from pdf_sku.settings import settings as _settings
    if _settings.combo_detect_enabled and content_pages > 0:
        kw_ratio = combo_keyword_pages / content_pages
        mc_ratio = multi_cat_pages / content_pages
        profile.combo_keyword_ratio = round(kw_ratio, 3)
        profile.multi_category_page_ratio = round(mc_ratio, 3)
        # 判定: 多品类共现比高 + 品类数少 (≤4, 排除多品类综合图册)
        few_categories = len(profile.main_categories) <= 4
        if (mc_ratio >= _settings.combo_multi_category_page_ratio
                and few_categories):
            profile.is_combo_catalog = True

    # 纯图目录检测：大部分页面无文字 → 产品展示目录，不是场景图册
    if profile.total_pages >= 3:
        text_sparse_pages = profile.total_pages - content_pages
        if text_sparse_pages / profile.total_pages > 0.60:
            profile.is_pure_image_catalog = True

        # 每页一产品检测：大部分页面是无文字+少量图片(1-4张多视图)
        # 典型场景：每页展示同一产品的正面/侧面/背面照片
        if (profile.is_pure_image_catalog
                and sparse_img_pages >= 3
                and sparse_img_pages / profile.total_pages > 0.50):
            profile.is_one_product_per_page = True

    logger.info("catalog_scan_done",
                total_pages=profile.total_pages,
                main_categories=sorted(profile.main_categories),
                dominant=profile.dominant_category,
                model_co_occurred=sorted(profile.model_co_occurred),
                is_combo=profile.is_combo_catalog,
                combo_kw_ratio=profile.combo_keyword_ratio,
                multi_cat_ratio=profile.multi_category_page_ratio,
                is_pure_image=profile.is_pure_image_catalog,
                is_one_product_per_page=profile.is_one_product_per_page,
                brand_names=sorted(profile.brand_names),
                model_prefixes=sorted(profile.model_prefixes),
                model_count=len(profile.all_model_numbers))

    return profile
