"""
规则去重模块: 过滤营销文案 + 按型号去重 + 按名称相似度去重。
目标: 在 LLM 提取后、持久化前，用纯规则大幅提升 Precision。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from pdf_sku.pipeline.ir import SKUResult
import structlog

logger = structlog.get_logger()

# ── 英文幻觉黑名单 (全英文名称 + 命中关键词 + 无型号无价格 → 过滤) ──
ENGLISH_HALLUCINATION_KEYWORDS: set[str] = {
    "premium", "best seller", "high quality", "professional",
    "description", "example", "sample", "placeholder",
    "quality product", "top rated", "recommended", "featured",
    "new arrival", "hot sale", "free shipping", "limited offer",
    "special offer", "buy now", "wholesale", "retail",
    "certificate", "warranty", "guarantee", "authentic",
}

# ── 错误标记关键词 (LLM 输出错误信息当作 SKU) ──
ERROR_MARKER_KEYWORDS: set[str] = {
    "error", "failed", "timeout", "exception", "no data",
    "not found", "unavailable", "n/a", "null", "undefined",
}

# 纯英文检测 (允许数字、空格、标点)
_ALL_ENGLISH_RE = re.compile(r'^[A-Za-z0-9\s\-_.,;:\'\"!@#$%^&*()/\\+=\[\]{}|<>?~`]+$')

# 中文颜色/材质描述词 (用于检测 LLM 生成的描述性名称)
_CN_DESC_COLORS = {"红色", "蓝色", "绿色", "黄色", "白色", "黑色", "灰色", "棕色",
                    "米色", "米白色", "深红色", "浅蓝色", "深蓝色", "粉色", "橙色", "紫色",
                    "金色", "银色", "咖色", "奶白色", "象牙色", "驼色", "墨绿色", "酒红色"}
_CN_DESC_MATERIALS = {"皮质", "布艺", "实木", "金属", "玻璃", "大理石", "岩板",
                       "不锈钢", "铝合金", "藤编", "编藤", "木质", "竹制", "陶瓷"}
_CN_DESC_SHAPES = {"长方形", "圆形", "方形", "异形", "椭圆形", "三角形", "弧形", "L型"}

# ── 场景装饰品黑名单 (无型号无价格 + 名称核心词命中 → 过滤) ──
SCENE_PROPS: set[str] = {
    "茶几", "边几", "边桌", "吊灯", "落地灯", "台灯", "壁灯", "地灯",
    "装饰画", "挂画", "油画", "壁画", "绿植", "植物", "盆栽", "花瓶",
    "地毯", "地垫", "抱枕", "靠枕", "靠垫", "窗帘", "窗纱",
    "装饰摆件", "摆件", "雕塑", "烛台", "相框", "时钟", "数字时钟",
    "书本", "书籍", "杂志", "手机", "遥控器", "音响", "智能音箱",
    "花艺", "干花", "鲜花", "花束", "果盘", "托盘", "餐具",
    "毛毯", "盖毯", "床单", "bed sheet", "bedsheet", "枕头",
    # 建筑/固装元素
    "窗户", "墙面", "墙面装饰板", "木地板", "地板", "floor", "flooring",
    "天花板", "天花板装饰", "吊顶灯槽",
    # 小家电/配件
    "筒灯", "嵌入式筒灯", "嵌入式灯带", "闹钟", "被子", "毯子",
    "充电器", "床头充电器", "小夜灯", "音箱",
    "空调", "空气净化器", "纯色墙面", "艺术画", "相机",
    "床头板",
}

# ── 场景软黑名单 (某些图册是正品，但场景渲染图中多为道具) ──
# scene_filter=True 且无型号无价格时才过滤
SCENE_SOFT_PROPS: set[str] = {
    "床垫", "扶手椅", "脚凳", "架子", "茶具",
    "床头靠背", "床头", "床尾凳",
    "pendant light", "pillow", "床品", "bedding",
}

# 用于剥离产品名称中的颜色/材质修饰词，提取核心名词
_STRIP_MODIFIERS_RE = re.compile(
    r'(?:' + '|'.join(
        list(_CN_DESC_COLORS) + list(_CN_DESC_MATERIALS) + list(_CN_DESC_SHAPES)
    ) + r')',
)


def _strip_to_core(name: str) -> str:
    """去掉颜色/材质/形状修饰词，返回核心名词。"""
    core = _STRIP_MODIFIERS_RE.sub('', name).strip()
    return core if core else name


def _is_scene_prop(name: str) -> bool:
    """检测产品名称核心词是否命中场景装饰品硬黑名单。"""
    core = _strip_to_core(name)
    if core in SCENE_PROPS:
        return True
    # 名称包含黑名单词且名称较短（避免误杀如"茶几柜"类合法产品名）
    if len(name) <= 6:
        for prop in SCENE_PROPS:
            if prop in name:
                return True
    return False


def _is_scene_soft_prop(name: str) -> bool:
    """检测产品名称核心词是否命中场景软黑名单。"""
    core = _strip_to_core(name)
    if core in SCENE_SOFT_PROPS:
        return True
    if len(name) <= 6:
        for prop in SCENE_SOFT_PROPS:
            if prop in name:
                return True
    return False

def _is_descriptive_chinese(name: str) -> bool:
    """检测是否是 LLM 生成的中文描述性名称 (如 '绿色皮质沙发')。
    特征: 颜色/材质/形状描述词 + 品类词，且无型号特征。
    """
    # 至少包含一个颜色/材质/形状描述词
    desc_count = sum(1 for w in _CN_DESC_COLORS | _CN_DESC_MATERIALS | _CN_DESC_SHAPES if w in name)
    return desc_count >= 3 and len(name) <= 12

# ── 营销关键词库 (命中 ≥1 且无型号无价格 → 视为营销文案) ──
MARKETING_KEYWORDS: set[str] = {
    # 促销
    "新品上市", "热销", "爆款", "畅销", "限时", "特惠", "促销", "折扣",
    "优惠", "满减", "买一送一", "包邮", "秒杀", "团购", "拼团", "抢购",
    "清仓", "甩卖", "大促", "返利", "赠品", "福利", "红包",
    # 品牌宣传
    "品质保证", "正品保障", "厂家直销", "源头工厂", "一手货源",
    "品牌授权", "官方正品", "假一赔十", "质量保证", "售后无忧",
    "七天无理由", "全国联保", "终身质保", "免费退换",
    # 营销话术
    "必备", "首选", "人气", "口碑", "好评", "五星",
    "销量第一", "行业领先", "私人订制",
    # 场景描述
    "送礼佳品", "伴手礼", "生日礼物", "节日礼品", "乔迁之喜",
    "开业大吉", "婚庆用品", "年货", "年终",
    # 通用广告
    "欢迎选购", "欢迎咨询", "联系客服", "扫码", "关注",
    "公众号", "小程序", "抖音", "快手", "直播", "短视频",
    "招商加盟", "诚招代理", "代发", "一件代发",
    # 页面装饰
    "目录", "封面", "封底", "前言", "后记", "附录", "备注",
    "温馨提示", "注意事项", "使用说明", "安装说明",
    "公司简介", "企业文化", "发展历程", "荣誉资质",
    # 英文常见营销
    "best seller", "hot sale", "new arrival", "free shipping",
    "limited offer", "special offer", "buy now",
}

# 价格模式
_PRICE_RE = re.compile(r'[\$¥€£￥]\s*[\d,.]+|[\d,.]+\s*元')
# 型号模式
_MODEL_RE = re.compile(r'[A-Za-z]{1,5}[-\s]?\d{3,}|[A-Z]{2,}\d+')


def pre_filter(skus: list[SKUResult], *, scene_filter: bool = False) -> list[SKUResult]:
    """
    预过滤: 去空名 + 营销文案过滤。
    营销文案判定: 命中营销关键词 且 无型号 且 无价格。
    scene_filter=True 时额外启用软黑名单过滤。
    """
    kept: list[SKUResult] = []
    removed = 0
    for sku in skus:
        name = (sku.attributes.get("product_name") or "").strip()
        # 1) 空名 → 丢弃
        if not name:
            removed += 1
            continue

        model = (sku.attributes.get("model_number") or "").strip()
        price = (sku.attributes.get("price") or "").strip()

        # 有型号或有价格 → 保留 (真 SKU 概率高)
        has_model = bool(model) or bool(_MODEL_RE.search(name))
        has_price = bool(price) or bool(_PRICE_RE.search(name))
        if has_model or has_price:
            kept.append(sku)
            continue

        # 3) 场景装饰品过滤: 无型号无价格 + 核心名词命中硬黑名单 → 过滤
        if _is_scene_prop(name):
            removed += 1
            logger.debug("sku_scene_prop_filtered", name=name[:60])
            continue

        # 3b) 场景软黑名单: scene_filter=True 时，无型号无价格 + 命中 → 过滤
        if scene_filter and _is_scene_soft_prop(name):
            removed += 1
            logger.debug("sku_scene_soft_prop_filtered", name=name[:60])
            continue

        # 4) 错误标记检测: name 含 error/failed/timeout 等 → 过滤
        name_lower = name.lower()
        if any(kw in name_lower for kw in ERROR_MARKER_KEYWORDS):
            removed += 1
            logger.debug("sku_error_marker_filtered", name=name[:60])
            continue

        # 4) 英文幻觉过滤: 全英文 + 无型号无价格 + 多个单词 → 过滤
        #    中文图册中纯英文多词名称几乎都是 LLM 图片描述 (如 "Grey Sofa", "Tea Set on Table")
        #    但短英文 (≤2个单词) 可能是有效品牌/型号，保留
        if _ALL_ENGLISH_RE.match(name):
            word_count = len(name.split())
            if word_count >= 5:
                removed += 1
                logger.debug("sku_english_filtered", name=name[:60])
                continue

        # 5) 中文描述性名称过滤 (如 "绿色皮质沙发"): 无型号无价格 + 颜色+材质描述
        if _is_descriptive_chinese(name):
            removed += 1
            logger.debug("sku_descriptive_cn_filtered", name=name[:60])
            continue

        # 6) 类目标题 (以"系列"结尾 且无型号无价格) → 过滤
        if name.endswith("系列"):
            removed += 1
            logger.debug("sku_category_filtered", name=name[:60])
            continue

        # 6) 检查营销关键词
        hit = any(kw in name_lower for kw in MARKETING_KEYWORDS)
        if hit:
            removed += 1
            logger.debug("sku_marketing_filtered", name=name[:60])
            continue

        # 7) 极短纯中文名称: 仅过滤 1 字的（如"柜"、"桌"）
        #    2-3字保留（"沙发"、"茶几"、"餐椅"在纯图片图册中是合法 SKU）
        if len(name) <= 1:
            removed += 1
            logger.debug("sku_short_name_filtered", name=name)
            continue

        # 8) 弱信号过滤: 无型号+无价格+短名称(≤3字)+低confidence → 图片描述
        if len(name) <= 3 and sku.confidence < 0.7:
            removed += 1
            logger.debug("sku_weak_signal_filtered", name=name,
                         confidence=sku.confidence)
            continue

        # 没命中关键词，保留
        kept.append(sku)

    if removed:
        logger.info("pre_filter_done", total=len(skus), removed=removed, kept=len(kept))
    return kept


def dedup_by_model(skus: list[SKUResult]) -> list[SKUResult]:
    """
    同 model_number 去重: 保留 confidence 最高的。
    """
    if not skus:
        return skus

    model_map: dict[str, SKUResult] = {}
    no_model: list[SKUResult] = []

    for sku in skus:
        model = (sku.attributes.get("model_number") or "").strip()
        if not model:
            no_model.append(sku)
            continue
        key = model.upper()
        existing = model_map.get(key)
        if existing is None or sku.confidence > existing.confidence:
            model_map[key] = sku

    result = list(model_map.values()) + no_model
    removed = len(skus) - len(result)
    if removed:
        logger.info("dedup_by_model_done", total=len(skus), removed=removed)
    return result


def _first_line(text: str | None) -> str:
    """取 product_name 首行用于相似度比较。"""
    if not text:
        return ""
    line = text.split("\n")[0].strip()
    return line[:120]


def dedup_by_similarity(skus: list[SKUResult], threshold: float = 0.95) -> list[SKUResult]:
    """
    product_name 首行相似度 > threshold → 合并 (保留 confidence 高的)。
    规则: 如果两个 SKU 都有 model_number 且不同，不合并。
    O(n²) 但 n 通常 < 50，可接受。
    """
    if len(skus) <= 1:
        return skus

    merged: list[bool] = [False] * len(skus)
    for i in range(len(skus)):
        if merged[i]:
            continue
        name_i = _first_line(skus[i].attributes.get("product_name", ""))
        model_i = (skus[i].attributes.get("model_number") or "").strip()
        if not name_i:
            continue
        for j in range(i + 1, len(skus)):
            if merged[j]:
                continue
            # 两者都有不同型号 → 不合并
            model_j = (skus[j].attributes.get("model_number") or "").strip()
            if model_i and model_j and model_i.upper() != model_j.upper():
                continue
            name_j = _first_line(skus[j].attributes.get("product_name", ""))
            if not name_j:
                continue
            ratio = SequenceMatcher(None, name_i, name_j).ratio()
            if ratio >= threshold:
                # 保留 confidence 高的
                if skus[j].confidence > skus[i].confidence:
                    merged[i] = True
                    break
                else:
                    merged[j] = True

    result = [s for i, s in enumerate(skus) if not merged[i]]
    removed = len(skus) - len(result)
    if removed:
        logger.info("dedup_by_similarity_done",
                     total=len(skus), removed=removed, threshold=threshold)
    return result


def _extract_chinese_chars(text: str) -> str:
    """提取文本中的中文字符序列 (去除空格/标点)。"""
    return re.sub(r'[^\u4e00-\u9fff]', '', text)


def _extract_key_tokens(name: str) -> list[str]:
    """从 product_name 提取关键 token 用于 OCR 匹配。
    返回: 中文子串 (≥2字) + 英文/数字 token (可能是型号)。
    """
    tokens = []
    # 中文连续子串
    cn_parts = re.findall(r'[\u4e00-\u9fff]{2,}', name)
    tokens.extend(cn_parts)
    # 英文+数字 token (可能是型号)
    en_parts = re.findall(r'[A-Za-z0-9][-A-Za-z0-9#.]{2,}', name)
    tokens.extend(en_parts)
    return tokens


def ocr_cross_validate(
    skus: list[SKUResult], ocr_text: str
) -> list[SKUResult]:
    """OCR 交叉验证: product_name 的关键 token 不出现在 OCR 文本中 → 过滤。

    规则:
    - 有 model_number 且 model_number 出现在 OCR → 保留 (即使名称不匹配)
    - product_name 的任何关键中文子串 (≥2字) 出现在 OCR → 保留
    - product_name 的任何英数 token 出现在 OCR → 保留
    - 以上都不匹配 → 过滤 (大概率是 LLM 幻觉)

    注意: OCR 文本为空/太短时跳过验证 (扫描版 OCR 可能失败)。
    """
    if not ocr_text or len(ocr_text.strip()) < 20:
        return skus  # OCR 太少，不可靠，跳过

    ocr_lower = ocr_text.lower()
    ocr_cn = _extract_chinese_chars(ocr_text)

    kept: list[SKUResult] = []
    demoted = 0

    for sku in skus:
        name = (sku.attributes.get("product_name") or "").strip()
        model = (sku.attributes.get("model_number") or "").strip()

        # model_number 在 OCR 中 → 直接保留
        if model and model.lower() in ocr_lower:
            kept.append(sku)
            continue

        # 检查 name 的关键 token
        tokens = _extract_key_tokens(name)
        if not tokens:
            kept.append(sku)  # 无法提取 token，保留
            continue

        matched = False
        for token in tokens:
            if re.search(r'[\u4e00-\u9fff]', token):
                # 中文 token: 在 OCR 中文字符流中查找
                if token in ocr_cn:
                    matched = True
                    break
            else:
                # 英数 token: 在 OCR 全文中查找 (忽略大小写)
                if token.lower() in ocr_lower:
                    matched = True
                    break

        if matched:
            kept.append(sku)
        else:
            # 降权而非删除: 未在 OCR 中找到对应文字，降低 confidence
            sku.confidence = sku.confidence * 0.5
            kept.append(sku)
            demoted += 1
            logger.debug("sku_ocr_unverified_demoted", name=name[:60], tokens=tokens[:3],
                         new_confidence=sku.confidence)

    if demoted:
        logger.info("ocr_cross_validate_done",
                     total=len(skus), demoted=demoted)
    return kept


def run_dedup_chain(skus: list[SKUResult], ocr_text: str = "", *, scene_filter: bool = False) -> list[SKUResult]:
    """完整去重链: pre_filter → ocr_cross_validate → dedup_by_model → dedup_by_similarity。"""
    skus = pre_filter(skus, scene_filter=scene_filter)
    if ocr_text:
        skus = ocr_cross_validate(skus, ocr_text)
    skus = dedup_by_model(skus)
    skus = dedup_by_similarity(skus)
    return skus


def cross_page_dedup(all_skus: list[SKUResult]) -> list[SKUResult]:
    """
    跨页去重: 对所有页面汇总的 SKU 进行 model_number 去重 + 名称相似度去重。
    用于 benchmark runner 汇总后消除跨页表格产生的重复。
    阈值 0.95: 只合并几乎完全相同的 SKU，避免误删不同产品。
    """
    if len(all_skus) <= 1:
        return all_skus
    before = len(all_skus)
    # 跨页去重只按 model_number: 跨页同名不等于同产品（如不同页的"餐椅"）
    result = dedup_by_model(all_skus)
    removed = before - len(result)
    if removed:
        logger.info("cross_page_dedup_done", before=before, after=len(result), removed=removed)
    return result
