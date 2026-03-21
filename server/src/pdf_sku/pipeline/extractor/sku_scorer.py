"""
SKU 综合打分: 6 维信号加权评分，替代二值 pre_filter + ocr_cross_validate。

设计目标:
- 有型号+有价格+OCR 验证 → ~0.85 (保留)
- "床头柜"在床头柜图册 (主营豁免) → ~0.55 (保留)
- "床头柜"在沙发图册+无型号 → ~0.20 (过滤)
- "Bed" conf=0.45 OCR 未验证 → ~0.12 (过滤)
- 场景道具+无型号+非主营 → ~0.15 (过滤)
"""
from __future__ import annotations

import re

from pdf_sku.pipeline.ir import SKUResult
from pdf_sku.pipeline.catalog_profiler import CatalogProfile
from pdf_sku.pipeline.extractor.sku_dedup import (
    _extract_key_tokens, _extract_chinese_chars,
    _is_scene_prop, _is_scene_soft_prop,
    _ALL_ENGLISH_RE, MARKETING_KEYWORDS, ERROR_MARKER_KEYWORDS,
    _is_descriptive_chinese,
)
import structlog

logger = structlog.get_logger()

# 价格 / 型号模式 (与 sku_dedup 保持一致)
_PRICE_RE = re.compile(r'[\$¥€£￥]\s*[\d,.]+|[\d,.]+\s*元')
_MODEL_RE = re.compile(r'[A-Za-z]{1,5}[-\s]?\d{3,}|[A-Z]{2,}\d+|\d{3,}#')

# ── 权重 ──
W_HAS_MODEL = 0.30
W_HAS_PRICE = 0.25
W_OCR_GROUNDED = 0.20
W_CATALOG_RELEVANCE = 0.15
W_NAME_QUALITY = 0.10
W_LLM_CONFIDENCE = 0.15

# 总权重 = 1.15 (有意大于 1.0, 最终 clamp 到 [0, 1])

# ── 场景惩罚 ──
PENALTY_HARD_BLACKLIST = -0.20   # 硬黑名单 + 无型号无价格
PENALTY_SOFT_BLACKLIST = -0.18   # 软黑名单 + scene_filter  # was -0.12
PENALTY_PURE_IMG_NO_OCR = -0.15  # 纯图目录: OCR 有产品信号但 SKU 未被 OCR 验证

# ── name-only 结构性惩罚（行业无关）──
PENALTY_NAME_ONLY_BASE       = -0.15   # 完全无属性的基础惩罚
PENALTY_NAME_ONLY_NO_OCR     = -0.10   # OCR 有产品信号但此 name 未验证
PENALTY_NAME_ONLY_PAGE_MODEL = -0.15   # 同页已有 model-bearing SKU
PENALTY_NAME_ONLY_SHORT      = -0.15   # 名称极短 (≤3字)  # was -0.10

# ── 品类感知过滤 ──
PENALTY_CATEGORY_IRRELEVANT = -0.20  # 方案A: 名称不属于主营品类 + 无型号无价格

# ── 阈值 ──
SCORE_THRESHOLD = 0.25


def _score_has_model(sku: SKUResult) -> float:
    """有型号 → 1.0，名称中含型号模式 → 0.5，否则 0。"""
    model = (sku.attributes.get("model_number") or "").strip()
    if model:
        return 1.0
    name = (sku.attributes.get("product_name") or "").strip()
    if _MODEL_RE.search(name):
        return 0.5
    return 0.0


def _score_has_price(sku: SKUResult) -> float:
    """有价格 → 1.0，名称中含价格模式 → 0.5，否则 0。"""
    price = (sku.attributes.get("price") or "").strip()
    if price:
        return 1.0
    name = (sku.attributes.get("product_name") or "").strip()
    if _PRICE_RE.search(name):
        return 0.5
    return 0.0


def _score_ocr_grounded(sku: SKUResult, ocr_text: str) -> float:
    """OCR 文本中找到关键 token → 1.0，部分匹配 → 0.5，未找到 → 0。"""
    if not ocr_text or len(ocr_text.strip()) < 20:
        return 0.5  # OCR 不可靠时给中性分

    name = (sku.attributes.get("product_name") or "").strip()
    model = (sku.attributes.get("model_number") or "").strip()
    ocr_lower = ocr_text.lower()
    ocr_cn = _extract_chinese_chars(ocr_text)

    # model_number 在 OCR 中 → 直接满分
    if model and model.lower() in ocr_lower:
        return 1.0

    tokens = _extract_key_tokens(name)
    if not tokens:
        return 0.5  # 无法提取 token，给中性分

    matched = 0
    for token in tokens:
        if re.search(r'[\u4e00-\u9fff]', token):
            if token in ocr_cn:
                matched += 1
        else:
            if token.lower() in ocr_lower:
                matched += 1

    if matched == len(tokens):
        return 1.0
    elif matched > 0:
        return 0.5
    return 0.0


def _extract_prefix(model: str) -> str:
    """从型号中提取字母前缀用于匹配。"""
    from pdf_sku.pipeline.catalog_profiler import _PREFIX_RE
    m = _PREFIX_RE.match(model)
    return m.group(1).upper() if m else ""


def _score_catalog_relevance(
    sku: SKUResult, catalog_profile: CatalogProfile | None,
    *, pure_visual: bool = False,
) -> float:
    """名称命中图册主营品类 → 1.0，出现过但非主营 → 0.3，完全无关 → 0。"""
    if not catalog_profile or not catalog_profile.main_categories:
        return 0.5  # 无 profile 时给中性分

    name = (sku.attributes.get("product_name") or "").strip().lower()
    model = (sku.attributes.get("model_number") or "").strip()
    if not name:
        return 0.0

    # 优先级 1: 型号匹配已知前缀 → 1.0
    if model and catalog_profile.model_prefixes:
        prefix = _extract_prefix(model)
        if prefix and prefix in catalog_profile.model_prefixes:
            return 1.0

    # 优先级 2: 产品名 == 品牌名 → 0.0（品牌名不是产品）
    if catalog_profile.brand_names:
        name_stripped = name.strip().lower()
        if name_stripped in {b.lower() for b in catalog_profile.brand_names}:
            return 0.0

    # 检查是否命中主营品类 (最长匹配优先, 避免 "床头柜" 误匹配 "床")
    from pdf_sku.pipeline.catalog_profiler import _SYNONYM_TO_CATEGORY
    best_match: tuple[str, str, int] | None = None  # (synonym, cat_name, len)
    for synonym, cat_name in _SYNONYM_TO_CATEGORY.items():
        if synonym in name:
            if best_match is None or len(synonym) > best_match[2]:
                best_match = (synonym, cat_name, len(synonym))

    if best_match:
        synonym, cat_name, _ = best_match
        if cat_name in catalog_profile.main_categories:
            # 名称本身就是品类同义词 (如 "床", "bed") → 不加分
            # 太泛化的名称不应该因为"显而易见"而加分
            stripped = name.strip().lower()
            if stripped == synonym and len(stripped) <= 4:
                return 0.7 if pure_visual else 0.0
            return 1.0
        elif cat_name in catalog_profile.category_page_counts:
            return 0.3
    return 0.0


# ── 通用家具名词 (无型号时极低分) ──
_GENERIC_FURNITURE_NAMES = {
    "沙发", "床", "茶几", "椅子", "桌子", "柜子", "书架", "衣柜",
    "餐桌", "餐椅", "边柜", "床头柜", "妆台", "脚踏", "凳子",
    "床头", "地板", "布艺款", "皮艺款",
    "nightstand", "dresser", "bed", "sofa", "chair", "table",
    "desk", "cabinet", "shelf", "wardrobe", "rug", "lamp",
    "bedside table", "bedroom set", "floor lamp",
}

# ── 知名品牌词 (全英文+品牌词 → 设计参考来源) ──
_BRAND_KEYWORDS = {
    "poliform", "minotti", "porada", "edra", "fendi", "bentley",
    "versace", "armani", "hermes", "gucci", "cassina", "b&b italia",
    "roche bobois", "natuzzi", "flexform", "molteni",
}

_MATTRESS_RE = re.compile(r'床垫|mattress', re.IGNORECASE)
_DIMENSION_RE = re.compile(
    r'^\d+[Xx×]\d+|^外径|^床外径|^尺寸|^常规款|^宽屏款|^加宽款|^标准款'
    r'|^【[^】]*】宽屏款|^【[^】]*】常规款|^配\d+[*×Xx]\d+.*床垫'
)


def _score_name_quality(sku: SKUResult) -> float:
    """名称质量评分: 正常名称 → 1.0, 极短/幻觉特征 → 0。"""
    name = (sku.attributes.get("product_name") or "").strip()
    if not name:
        return 0.0

    model = (sku.attributes.get("model_number") or "").strip()

    # 1字 → 极短
    if len(name) <= 1:
        return 0.0

    # 错误标记
    name_lower = name.lower()
    if any(kw in name_lower for kw in ERROR_MARKER_KEYWORDS):
        return 0.0

    # 纯 "组合X" 名称 (组合+字母/数字，无实际产品描述) → 不是产品
    _COMBO_CODE_RE = re.compile(r'^组合\s*[A-Za-z0-9]{1,3}$')
    if _COMBO_CODE_RE.match(name.strip()):
        return 0.0

    # "MODEL XXX" 文本 → 不是产品名
    if name.strip().upper().startswith("MODEL"):
        return 0.0

    # 纯材质描述 (布艺款/皮艺款 单独出现无其他产品词) → 不是独立产品
    _MATERIAL_ONLY_RE = re.compile(r'^(布艺款?|皮艺款?|皮艺|布艺)\s*$')
    if _MATERIAL_ONLY_RE.match(name.strip()):
        return 0.0

    # 尺寸/变体描述 (不是产品名称)
    if _DIMENSION_RE.search(name):
        return 0.0

    # 床垫描述 (非独立产品，是主品的配件规格) — 无型号时大概率是规格描述
    if _MATTRESS_RE.search(name_lower) and not model:
        return 0.0

    # 营销文案
    if any(kw in name_lower for kw in MARKETING_KEYWORDS):
        return 0.1

    # 中文描述性名称 (如 "绿色皮质沙发")
    if _is_descriptive_chinese(name):
        return 0.2

    # 通用家具名词 + 无型号 → 硬过滤 (如 "沙发", "床", "nightstand")
    name_stripped = name.strip().lower()
    if name_stripped in _GENERIC_FURNITURE_NAMES and not model:
        return 0.0

    # 全英文 + 包含知名品牌词 → 设计参考来源，不是在售商品
    is_all_english = _ALL_ENGLISH_RE.match(name)
    if is_all_english and any(b in name_stripped for b in _BRAND_KEYWORDS):
        return 0.0

    # 全英文 ≥5 词 → 大概率 LLM 图片描述
    if is_all_english and len(name.split()) >= 5:
        return 0.1

    # 全英文 2-4 词 + 无型号 → 大概率品牌描述/场景描述
    if is_all_english and 2 <= len(name.split()) <= 4 and not model:
        return 0.1

    # 极短全英文 (≤4字符如 "Bed", "Rug") → 大概率通用描述
    if is_all_english and len(name) <= 4:
        return 0.2

    # 以"系列"结尾
    if name.endswith("系列"):
        return 0.2

    # 2-3 字短名称
    if len(name) <= 3:
        return 0.5

    return 1.0


def _check_scene_exemption(
    name: str,
    catalog_profile: CatalogProfile | None,
    strict: bool = True,
) -> bool:
    """检查场景黑名单项是否应豁免。

    strict=True (硬黑名单): 需要 exclusive_pages ≥ 1 或 (model_co_occurred + dominant)
    strict=False (软黑名单): main_categories 即可
    """
    if not catalog_profile:
        return False

    from pdf_sku.pipeline.catalog_profiler import _SYNONYM_TO_CATEGORY
    name_lower = name.lower()

    # 最长匹配优先
    best_match: tuple[str, str] | None = None
    for synonym, cat_name in _SYNONYM_TO_CATEGORY.items():
        if synonym in name_lower:
            if best_match is None or len(synonym) > len(best_match[0]):
                best_match = (synonym, cat_name)

    if not best_match:
        return False

    _, cat_name = best_match

    if not strict:
        # 软黑名单: 需要在 main_categories 且有更强证据
        if cat_name not in catalog_profile.main_categories:
            return False
        return (catalog_profile.exclusive_pages.get(cat_name, 0) >= 1
                or cat_name in catalog_profile.model_co_occurred)
    else:
        # 严格: 需要独占页面 (该品类是某些页面的唯一品类)
        if catalog_profile.exclusive_pages.get(cat_name, 0) >= 1:
            return True
        # 或者: 品类是图册 dominant 且在 model_co_occurred 中
        if (cat_name == catalog_profile.dominant_category
                and cat_name in catalog_profile.model_co_occurred):
            return True

    return False


def _compute_penalty(
    sku: SKUResult,
    *,
    has_model: float,
    has_price: float,
    scene_filter: bool,
    catalog_profile: CatalogProfile | None,
) -> float:
    """场景惩罚计算。

    主营品类豁免规则:
    - 硬黑名单项: 只有 model_co_occurred 才能豁免 (page_count 不够)
    - 软黑名单项: main_categories 即可豁免
    """
    name = (sku.attributes.get("product_name") or "").strip()
    if not name:
        return 0.0

    no_model_price = has_model == 0.0 and has_price == 0.0
    penalty = 0.0

    # 品牌名充当产品名 + 无型号无价格 → 强惩罚
    if catalog_profile and catalog_profile.brand_names and no_model_price:
        name_stripped = name.strip().lower()
        if name_stripped in {b.lower() for b in catalog_profile.brand_names}:
            penalty -= 0.25
            return penalty  # 直接返回，不再检查黑名单

    # 纯图片 PDF (profiler 无品类数据): 无品类→跳过软黑名单，硬黑名单仍生效
    if catalog_profile and not catalog_profile.category_page_counts:
        if _is_scene_prop(name) and no_model_price:
            penalty += PENALTY_HARD_BLACKLIST
        return penalty

    # 硬黑名单 + 无型号无价格
    if _is_scene_prop(name) and no_model_price:
        # 严格豁免: 需要 exclusive_pages ≥ 1 (该品类在图册中有独占页面)
        # 或者 model_co_occurred + 品类是 dominant
        exempt = _check_scene_exemption(name, catalog_profile, strict=True)
        if not exempt:
            penalty += PENALTY_HARD_BLACKLIST

    # 软黑名单 + scene_filter
    if scene_filter and _is_scene_soft_prop(name) and no_model_price:
        # 宽松豁免: main_categories 即可
        exempt = _check_scene_exemption(name, catalog_profile, strict=False)
        if not exempt:
            penalty += PENALTY_SOFT_BLACKLIST

    return penalty


def score_and_filter(
    skus: list[SKUResult],
    *,
    ocr_text: str = "",
    catalog_profile: CatalogProfile | None = None,
    scene_filter: bool = False,
    page_has_model_bearing: bool = False,
    pure_visual: bool = False,
) -> list[SKUResult]:
    """多维打分 + 阈值过滤，替代 pre_filter + ocr_cross_validate。

    pure_visual=True 时对纯图产品页放宽过滤:
    - 通用家具名词豁免硬过滤
    - name-only 惩罚豁免

    过滤后将综合分数调制回写到 sku.confidence。
    """
    if not skus:
        return skus

    kept: list[SKUResult] = []
    removed = 0
    is_combo = catalog_profile and catalog_profile.is_combo_catalog
    is_pure_img = catalog_profile and catalog_profile.is_pure_image_catalog

    for sku in skus:
        name = (sku.attributes.get("product_name") or "").strip()
        # 空名 → 直接丢弃
        if not name:
            removed += 1
            continue

        # 计算 6 维分数
        s_model = _score_has_model(sku)
        s_price = _score_has_price(sku)
        s_ocr = _score_ocr_grounded(sku, ocr_text)
        s_catalog = _score_catalog_relevance(
            sku, catalog_profile,
            pure_visual=(pure_visual or bool(is_pure_img)),
        )
        s_name = _score_name_quality(sku)
        s_llm = min(1.0, max(0.0, sku.confidence))

        # 硬过滤: name_quality=0 表示确定不是产品 (尺寸描述/变体规格/无型号床垫等)
        # 组合图册/纯图目录/纯图页面中通用家具名词（如"床""沙发"）是合法产品名，跳过硬过滤
        generic_exempt = ((is_combo or is_pure_img or pure_visual)
                          and name.strip().lower() in _GENERIC_FURNITURE_NAMES)
        if s_name == 0.0 and not generic_exempt:
            removed += 1
            logger.debug("sku_name_quality_hard_filtered", name=name[:60])
            continue

        # 纯图目录中通用家具名是合法产品名，给予基础分
        if generic_exempt and s_name == 0.0:
            s_name = 0.5

        # 加权求和
        raw_score = (
            W_HAS_MODEL * s_model
            + W_HAS_PRICE * s_price
            + W_OCR_GROUNDED * s_ocr
            + W_CATALOG_RELEVANCE * s_catalog
            + W_NAME_QUALITY * s_name
            + W_LLM_CONFIDENCE * s_llm
        )

        # 纯图目录 OCR 反向验证: OCR 明确有产品信息但此 SKU 不在其中
        ocr_has_product_signal = bool(
            ocr_text and len(ocr_text) >= 50
            and (_MODEL_RE.search(ocr_text) or _PRICE_RE.search(ocr_text))
        )
        if (is_pure_img and ocr_has_product_signal
                and s_model == 0.0 and s_price == 0.0 and s_ocr == 0.0):
            raw_score += PENALTY_PURE_IMG_NO_OCR
            logger.debug("pure_img_ocr_penalty", name=name[:60],
                         penalty=PENALTY_PURE_IMG_NO_OCR)

        # 弱信号惩罚: 极短名称 + 无型号无价格 + 低 LLM confidence
        if s_model == 0.0 and s_price == 0.0 and s_llm < 0.5:
            # 极短英文 (Bed, Rug) 或 1 字中文 (床, 柜)
            is_short_en = _ALL_ENGLISH_RE.match(name) and len(name) <= 4
            is_single_cn = len(name) <= 1
            if is_short_en or is_single_cn:
                raw_score -= 0.15

        # 全英文名称 + 无硬信号 → 大概率是 LLM 图片描述
        # 纯图目录/纯图页面豁免: 英文产品名是合法的
        is_all_english = _ALL_ENGLISH_RE.match(name)
        if (is_all_english and s_model == 0.0 and s_price == 0.0 and s_catalog == 0.0
                and not pure_visual and not is_pure_img):
            raw_score -= 0.15

        # ── name-only 结构性惩罚（行业无关）──
        attrs = sku.attributes or {}
        _specs = (attrs.get("specs") or attrs.get("size") or "").strip()
        _color = (attrs.get("color") or "").strip()
        is_name_only = (s_model == 0.0 and s_price == 0.0
                        and not _specs and not _color)

        if is_name_only:
            # 豁免: 组合图册 或 (纯图目录 且 同批无 model-bearing SKU)
            # 或 pure_visual 页面 (text≤30, img>85%): 纯图页面不可能有型号/价格,
            # name-only 是此类页面的正常产出, 不应被惩罚
            name_only_exempt = (is_combo
                                or (is_pure_img and not page_has_model_bearing)
                                or (pure_visual and not page_has_model_bearing))

            if not name_only_exempt:
                raw_score += PENALTY_NAME_ONLY_BASE           # -0.15

                if ocr_has_product_signal and s_ocr == 0.0:   # OCR 有信号但 name 未验证
                    raw_score += PENALTY_NAME_ONLY_NO_OCR      # -0.10

                if page_has_model_bearing:                     # 同页有型号产品
                    raw_score += PENALTY_NAME_ONLY_PAGE_MODEL  # -0.15

                if len(name.replace(" ", "")) <= 3:            # 极短名称
                    raw_score += PENALTY_NAME_ONLY_SHORT       # -0.10

                logger.debug("name_only_penalty", name=name[:60],
                             base=PENALTY_NAME_ONLY_BASE,
                             no_ocr=PENALTY_NAME_ONLY_NO_OCR if (ocr_has_product_signal and s_ocr == 0.0) else 0,
                             page_model=PENALTY_NAME_ONLY_PAGE_MODEL if page_has_model_bearing else 0,
                             short=PENALTY_NAME_ONLY_SHORT if len(name.replace(" ", "")) <= 3 else 0)

        # 场景惩罚
        penalty = _compute_penalty(
            sku,
            has_model=s_model,
            has_price=s_price,
            scene_filter=scene_filter,
            catalog_profile=catalog_profile,
        )

        # ── 品类感知过滤 (AND 策略: 方案A∩B 交集) ──
        # 无价格即触发；有型号但无价格的非主营品类给予较轻惩罚
        if (s_price == 0.0
                and catalog_profile and catalog_profile.main_categories):
            from pdf_sku.pipeline.catalog_profiler import _SYNONYM_TO_CATEGORY
            name_lower = name.lower()

            # 最长匹配: SKU 名称命中的品类词
            matched_cat: str | None = None
            best_len = 0
            for synonym, cat_name in _SYNONYM_TO_CATEGORY.items():
                if synonym in name_lower and len(synonym) > best_len:
                    matched_cat = cat_name
                    best_len = len(synonym)

            # 命中了品类词，但不属于主营品类 → 惩罚
            if matched_cat and matched_cat not in catalog_profile.main_categories:
                if s_model == 0.0:
                    penalty += PENALTY_CATEGORY_IRRELEVANT       # -0.20 (无型号)
                else:
                    penalty += PENALTY_CATEGORY_IRRELEVANT / 2   # -0.10 (有型号但非主营)
                logger.debug("category_irrelevant_penalty",
                             name=name[:60],
                             matched_cat=matched_cat,
                             has_model=s_model > 0,
                             main_cats=list(catalog_profile.main_categories)[:5])

        final_score = max(0.0, min(1.0, raw_score + penalty))

        if final_score >= SCORE_THRESHOLD:
            # 将综合分数调制回写 confidence
            sku.confidence = round(final_score, 3)
            kept.append(sku)
        else:
            removed += 1
            logger.debug("sku_score_filtered",
                         name=name[:60],
                         score=round(final_score, 3),
                         model=round(s_model, 2),
                         price=round(s_price, 2),
                         ocr=round(s_ocr, 2),
                         catalog=round(s_catalog, 2),
                         name_q=round(s_name, 2),
                         llm=round(s_llm, 2),
                         penalty=round(penalty, 2))

    if removed:
        logger.info("score_and_filter_done",
                     total=len(skus), removed=removed, kept=len(kept))
    return kept
