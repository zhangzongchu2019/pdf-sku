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
    # 零部件/材料
    "铝合金脚", "椅脚", "家具腿", "桌腿", "椅腿",
    "坐垫", "海绵坐垫", "座垫",
    "板材", "木纹板材", "背板", "面板",
    "连接件", "横梁", "脚杯", "脚垫",
    "写字板",
    "涂料桶", "工人", "背景板", "装饰板",
    "屏风", "壁挂镜",
    # 收纳/展示类
    "置物架", "壁挂置物架", "展示柜", "储物柜", "收纳柜",
    # 装饰类
    "装饰台", "装饰柜", "装饰镜", "镜子", "穿衣镜",
    "墙板", "木纹墙板", "护墙板",
    # 纺织/软装
    "床品套件", "四件套",
    # 企业/材料信息
    "涂料", "华润涂料",
}

# ── 场景软黑名单 (某些图册是正品，但场景渲染图中多为道具) ──
# scene_filter=True 且无型号无价格时才过滤
SCENE_SOFT_PROPS: set[str] = {
    "床垫", "扶手椅", "脚凳", "架子", "茶具",
    "床头靠背", "床头", "床尾凳",
    "pendant light", "pillow", "床品", "bedding",
    # 配套家具 (在沙发/床图册中通常是道具)
    "餐椅", "餐桌", "酒柜", "书柜", "电视柜",
    "角几", "圆凳", "方凳", "矮凳",
    "梳妆镜", "化妆镜",
    "懒人沙发", "单人沙发椅",
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
    # 品牌文化/理念
    "高素养", "高质量", "高标准", "服务理念", "生产体系",
    "以和为贵", "真材实料", "匠心",
    "品牌故事", "品牌介绍",
    # 联系方式
    "联系方式", "联系我们", "地址", "电话", "传真", "邮箱", "网址",
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

        # 9) 无型号 + 无价格 + confidence < 0.4 → 高概率 FP
        if not has_model and not has_price and sku.confidence < 0.4:
            removed += 1
            logger.debug("sku_low_conf_no_model_filtered", name=name[:60],
                         confidence=sku.confidence)
            continue

        # 没命中关键词，保留
        kept.append(sku)

    if removed:
        logger.info("pre_filter_done", total=len(skus), removed=removed, kept=len(kept))
    return kept


def normalize_model(model: str) -> str:
    """标准化型号: 全角→半角、去尾部 #*、去空格、大写。"""
    import unicodedata
    m = model.strip()
    m = unicodedata.normalize('NFKC', m)  # 全角→半角 (Ｗ→W, ０→0)
    m = re.sub(r'[#*]+$', '', m)   # 去尾部 #*
    m = re.sub(r'\s+', '', m)      # 去所有空格
    return m.upper()


_FAKE_MODEL_VALUES = {
    "null", "n/a", "na", "not visible", "none", "-", "--",
    "无", "暂无", "无型号",
}


def _merge_variant_color(source: SKUResult, target: SKUResult) -> None:
    """将 source 的颜色合并到 target（规格维度）。"""
    src_color = (source.attributes.get("color") or "").strip()
    tgt_color = (target.attributes.get("color") or "").strip()
    if src_color and src_color != tgt_color:
        combined = f"{tgt_color} / {src_color}" if tgt_color else src_color
        target.attributes["color"] = combined


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
        if not model or model.lower() in _FAKE_MODEL_VALUES:
            no_model.append(sku)
            continue
        norm = normalize_model(model)
        key = norm  # 同型号合并，颜色/尺寸作为规格 (用户确认: 同编号不同颜色尺寸=同一产品)
        existing = model_map.get(key)
        if existing is None:
            model_map[key] = sku
        elif sku.confidence > existing.confidence:
            _merge_variant_color(existing, sku)
            model_map[key] = sku
        else:
            _merge_variant_color(sku, existing)

    # 后缀合并: 纯数字短型号 (如 "01") 可能是长型号 (如 "BK(贝壳)01") 的片段
    # 当短型号是某个长型号的结尾部分时，合并到长型号
    _PURE_NUM_RE = re.compile(r'^\d{1,4}$')
    keys = list(model_map.keys())
    remove_keys: set[str] = set()
    for short_key in keys:
        norm_short = short_key.split("||")[0]  # 去掉颜色部分
        if not _PURE_NUM_RE.match(norm_short):
            continue
        for long_key in keys:
            if long_key == short_key or long_key in remove_keys:
                continue
            norm_long = long_key.split("||")[0]
            if len(norm_long) > len(norm_short) and norm_long.endswith(norm_short):
                # 短型号是长型号的后缀 → 合并，保留 confidence 高的
                if model_map[long_key].confidence >= model_map[short_key].confidence:
                    remove_keys.add(short_key)
                else:
                    # 短型号 conf 更高，保留长型号的名称信息但用短的 conf
                    model_map[long_key].confidence = model_map[short_key].confidence
                    remove_keys.add(short_key)
                break
    for k in remove_keys:
        del model_map[k]

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


_VARIANT_SUFFIX_RE = re.compile(
    r'[-_]\s*(\d{1,2})\s*$'        # -1, -2, -3, -4
    r'|[-_]\s*\d\.\d+\s*[Mm]?\s*$' # -1.8M, -1.5
)


def dedup_by_model_variant(skus: list[SKUResult]) -> list[SKUResult]:
    """同 base model 的尺寸变体合并为 1 个 SKU。

    BT-SF711-1, BT-SF711-2, BT-SF711-3 → 保留 BT-SF711-1
    BT-BD718-1, BT-BD718-2 → 保留 BT-BD718-1
    """
    if len(skus) <= 1:
        return skus

    base_groups: dict[str, list[tuple[int, SKUResult]]] = {}
    for i, sku in enumerate(skus):
        model = (sku.attributes.get("model_number") or "").strip()
        if not model:
            continue
        base = _VARIANT_SUFFIX_RE.sub('', model).strip()
        if base != model:  # 有变体后缀
            # base 本身必须含数字才算合法 base model
            # (避免 FP-21, FP-22 → base="FP" 被误合并)
            if not re.search(r'\d', base):
                continue
            # base 太短 (< 4 字符) → 不是合法 base，而是独立短型号
            # (避免 24-07, 24-08 → base="24" 被误合并;
            #  22-71, 22-72 → base="22" 被误合并)
            if len(base) < 4:
                continue
            key = base.upper()
            base_groups.setdefault(key, []).append((i, sku))

    remove_indices: set[int] = set()
    for base, group in base_groups.items():
        if len(group) <= 1:
            continue
        # 保留 confidence 最高的
        group.sort(key=lambda x: x[1].confidence, reverse=True)
        keeper = group[0][1]
        # 将所有变体的 model_number 合并到 keeper
        all_models = [g[1].attributes.get("model_number", "") for g in group]
        keeper.attributes["model_number"] = " / ".join(all_models)
        for idx, _ in group[1:]:
            remove_indices.add(idx)

    if remove_indices:
        logger.info("dedup_by_model_variant_done",
                     total=len(skus), removed=len(remove_indices))

    result = [s for i, s in enumerate(skus) if i not in remove_indices]
    return result


_MATERIAL_PREFIX_RE = re.compile(r'^(BU|NAV)[-\s]?(\d+.*)$', re.IGNORECASE)


def dedup_material_variants(skus: list[SKUResult]) -> list[SKUResult]:
    """布艺/皮艺型号对去重: BU332 + NAV332 → 保留 1 个。"""
    if len(skus) <= 1:
        return skus

    num_groups: dict[str, list[tuple[int, SKUResult]]] = {}
    for i, sku in enumerate(skus):
        model = (sku.attributes.get("model_number") or "").strip()
        m = _MATERIAL_PREFIX_RE.match(model)
        if m:
            num_part = m.group(2).upper()
            num_groups.setdefault(num_part, []).append((i, sku))

    remove_indices: set[int] = set()
    for num, group in num_groups.items():
        if len(group) <= 1:
            continue
        # 有 BU 和 NAV 同时存在 → 变体对
        prefixes = set()
        for _, sku in group:
            m = _MATERIAL_PREFIX_RE.match(sku.attributes.get("model_number", ""))
            if m:
                prefixes.add(m.group(1).upper())
        if len(prefixes) >= 2:
            group.sort(key=lambda x: x[1].confidence, reverse=True)
            for idx, _ in group[1:]:
                remove_indices.add(idx)

    if remove_indices:
        logger.info("dedup_material_variants_done",
                     total=len(skus), removed=len(remove_indices))

    result = [s for i, s in enumerate(skus) if i not in remove_indices]
    return result


_COMPOUND_MODEL_PART_RE = re.compile(
    r'[A-Za-z]{1,5}[-\s]?\d{2,}'   # FP-35, BT-SF711
    r'|[A-Z]{2,}\d+'               # NAV332
    r'|\d{3,}#'                     # 123#
    r'|\d{2,}[-]\d+'               # 35-1
)

def split_compound_models(skus: list[SKUResult]) -> list[SKUResult]:
    """model_number 含 3+ 个分隔符分割的型号时，拆分为多条 SKU。

    规则:
    - 仅当 / , ; 分隔的部分 ≥ 3 个且每个匹配型号格式时才拆分
    - 2 个部分不拆（可能是 "型号A / 型号B" 的合法复合型号）
    - 拆分后 confidence *= 0.9
    """
    if not skus:
        return skus

    result: list[SKUResult] = []
    split_count = 0

    for sku in skus:
        model = (sku.attributes.get("model_number") or "").strip()
        if not model:
            result.append(sku)
            continue

        # 按 / , ; 分割
        parts = re.split(r'\s*[/,;]\s*', model)
        parts = [p.strip() for p in parts if p.strip()]

        # 仅 3+ 个部分且每个都像型号才拆分
        if len(parts) >= 3 and all(_COMPOUND_MODEL_PART_RE.search(p) for p in parts):
            from copy import deepcopy
            for p in parts:
                new_sku = deepcopy(sku)
                new_sku.attributes["model_number"] = p
                new_sku.confidence = sku.confidence * 0.9
                new_sku.extraction_method = "compound_split"
                result.append(new_sku)
            split_count += 1
        else:
            result.append(sku)

    if split_count:
        logger.info("split_compound_models_done",
                     split_skus=split_count,
                     before=len(skus), after=len(result))
    return result


def _merge_variant_size(skus: list[SKUResult]) -> list[SKUResult]:
    """同 model_number 的 SKU，仅尺寸(specs)不同 → 合并为一个。

    目标: 丽轩地毯 Kris01 多尺寸拆分问题 (Kris01 160x230, Kris01 200x300 → 1个)。
    实现: 同 normalized model → 合并 specs，保留 confidence 最高的。
    """
    if len(skus) <= 1:
        return skus

    model_groups: dict[str, list[tuple[int, SKUResult]]] = {}
    for i, sku in enumerate(skus):
        model = (sku.attributes.get("model_number") or "").strip()
        if not model or model.lower() in _FAKE_MODEL_VALUES:
            continue
        norm = normalize_model(model)
        model_groups.setdefault(norm, []).append((i, sku))

    remove_indices: set[int] = set()
    for norm, group in model_groups.items():
        if len(group) <= 1:
            continue

        # 检查是否仅 specs 不同 (product_name 相同或高度相似)
        names = [
            (s.attributes.get("product_name") or "").strip().lower()
            for _, s in group
        ]
        # 名称全部相同或高度相似 (>= 0.85) 才合并
        base_name = names[0]
        all_similar = all(
            n == base_name or SequenceMatcher(None, base_name, n).ratio() >= 0.85
            for n in names[1:]
        )
        if not all_similar:
            continue

        # 保留 confidence 最高的，合并 specs
        group.sort(key=lambda x: x[1].confidence, reverse=True)
        keeper_idx, keeper = group[0]
        all_specs: list[str] = []
        for _, s in group:
            spec = (s.attributes.get("specs") or s.attributes.get("size") or "").strip()
            if spec and spec not in all_specs:
                all_specs.append(spec)

        if all_specs:
            keeper.attributes["specs"] = " / ".join(all_specs)

        # 合并颜色
        all_colors: list[str] = []
        for _, s in group:
            c = (s.attributes.get("color") or "").strip()
            if c and c not in all_colors:
                all_colors.append(c)
        if len(all_colors) > 1:
            keeper.attributes["color"] = " / ".join(all_colors)

        for idx, _ in group[1:]:
            remove_indices.add(idx)

    if remove_indices:
        logger.info("merge_variant_size_done",
                     total=len(skus), removed=len(remove_indices))
        return [s for i, s in enumerate(skus) if i not in remove_indices]
    return skus


def _merge_no_model_into_model_bearing(skus: list[SKUResult]) -> list[SKUResult]:
    """无型号 SKU 若名称与有型号 SKU 高度相似(>=0.80)，合并掉。

    处理: 场景页提取"沙发" vs 产品页有"沙发 BT-123" 的重复。
    """
    if len(skus) <= 1:
        return skus

    model_bearing: list[SKUResult] = []
    no_model: list[tuple[int, SKUResult]] = []

    for i, sku in enumerate(skus):
        model = (sku.attributes.get("model_number") or "").strip()
        if model and model.lower() not in _FAKE_MODEL_VALUES:
            model_bearing.append(sku)
        else:
            no_model.append((i, sku))

    if not model_bearing or not no_model:
        return skus

    # 预处理有型号 SKU 的核心名
    mb_cores = [
        _strip_to_core(
            (s.attributes.get("product_name") or "").strip().lower()
        )
        for s in model_bearing
    ]

    remove_indices: set[int] = set()
    for idx, sku in no_model:
        name = (sku.attributes.get("product_name") or "").strip().lower()
        core = _strip_to_core(name)
        if len(core) <= 2:
            continue  # 太短，避免误匹配
        for mb_core in mb_cores:
            if not mb_core:
                continue
            ratio = SequenceMatcher(None, core, mb_core).ratio()
            if ratio >= 0.80:
                remove_indices.add(idx)
                break

    if remove_indices:
        logger.info("merge_no_model_into_model_bearing",
                     total=len(skus), removed=len(remove_indices))
        return [s for i, s in enumerate(skus) if i not in remove_indices]
    return skus


def _dedup_cross_page_by_name_similarity(
    skus: list[SKUResult], threshold: float = 0.85,
) -> list[SKUResult]:
    """仅对无型号 SKU，名称核心部分相似度 >= threshold 的去重。"""
    if len(skus) <= 1:
        return skus

    # 分离有型号 / 无型号
    with_model: list[SKUResult] = []
    no_model_indexed: list[tuple[int, SKUResult]] = []
    for i, sku in enumerate(skus):
        model = (sku.attributes.get("model_number") or "").strip()
        if model and model.lower() not in _FAKE_MODEL_VALUES:
            with_model.append(sku)
        else:
            no_model_indexed.append((i, sku))

    if len(no_model_indexed) <= 1:
        return skus

    merged: set[int] = set()
    for ai, (idx_a, sku_a) in enumerate(no_model_indexed):
        if idx_a in merged:
            continue
        name_a = _strip_to_core(
            (sku_a.attributes.get("product_name") or "").strip().lower()
        )
        if len(name_a) <= 2:
            continue
        for bi in range(ai + 1, len(no_model_indexed)):
            idx_b, sku_b = no_model_indexed[bi]
            if idx_b in merged:
                continue
            name_b = _strip_to_core(
                (sku_b.attributes.get("product_name") or "").strip().lower()
            )
            if len(name_b) <= 2:
                continue
            ratio = SequenceMatcher(None, name_a, name_b).ratio()
            if ratio >= threshold:
                # 豁免: 颜色不同 → 是不同产品变体，不去重
                color_a = (sku_a.attributes.get("color") or "").strip().lower()
                color_b = (sku_b.attributes.get("color") or "").strip().lower()
                if color_a and color_b and color_a != color_b:
                    continue
                # 豁免: 来自不同页面且都是 pure_visual 提取
                page_a = getattr(sku_a, "page_no", None)
                page_b = getattr(sku_b, "page_no", None)
                if (page_a and page_b and page_a != page_b
                        and getattr(sku_a, "extraction_method", "") in ("pure_visual_rescue", "img_dense_figure_rescue")
                        and getattr(sku_b, "extraction_method", "") in ("pure_visual_rescue", "img_dense_figure_rescue")):
                    continue
                # 保留 confidence 高的
                if sku_b.confidence > sku_a.confidence:
                    merged.add(idx_a)
                    break
                else:
                    merged.add(idx_b)

    if merged:
        logger.info("dedup_cross_page_by_name_similarity",
                     total=len(skus), removed=len(merged))
        return [s for i, s in enumerate(skus) if i not in merged]
    return skus


def _filter_cross_page_props(
    skus: list[SKUResult],
    catalog_profile: "CatalogProfile | None" = None,
) -> list[SKUResult]:
    """跨页汇总后清理: 无真实型号 + 无价格 + 命中道具黑名单 → 移除。

    page-level 可以宽容 (单页可能就是产品页),
    但跨页汇总后无型号无价格的道具几乎必定是 FP。
    主营品类豁免: 命中主营品类的不移除。
    """
    _PRICE_RE_LOCAL = re.compile(r'[\$¥€£￥]\s*[\d,.]+|[\d,.]+\s*元')
    kept: list[SKUResult] = []
    removed = 0

    for sku in skus:
        model = (sku.attributes.get("model_number") or "").strip()
        if model and model.lower() not in _FAKE_MODEL_VALUES:
            kept.append(sku)
            continue

        name = (sku.attributes.get("product_name") or "").strip()
        price = (sku.attributes.get("price") or "").strip()
        has_price = bool(price) or bool(_PRICE_RE_LOCAL.search(name))
        if has_price:
            kept.append(sku)
            continue

        is_prop = _is_scene_prop(name) or _is_scene_soft_prop(name)
        if not is_prop:
            kept.append(sku)
            continue

        # 主营品类豁免
        if catalog_profile and catalog_profile.main_categories:
            from pdf_sku.pipeline.catalog_profiler import _SYNONYM_TO_CATEGORY
            name_lower = name.lower()
            matched_cat = None
            best_len = 0
            for synonym, cat_name in _SYNONYM_TO_CATEGORY.items():
                if synonym in name_lower and len(synonym) > best_len:
                    matched_cat = cat_name
                    best_len = len(synonym)
            if matched_cat and matched_cat in catalog_profile.main_categories:
                kept.append(sku)
                continue

        removed += 1
        logger.debug("cross_page_prop_filtered", name=name[:60])

    if removed:
        logger.info("filter_cross_page_props_done",
                     total=len(skus), removed=removed)
    return kept


_COLOR_SPLIT_RE = re.compile(r'[/、，,；;]\s*')


def expand_color_variants(skus: list[SKUResult]) -> list[SKUResult]:
    """将 color 字段包含多个颜色值的 SKU 展开为独立 SKU。

    例如: model=801#, color="浅灰色/深灰色/白色" → 3 个独立 SKU。
    仅对有 model_number 且 color 含分隔符的 SKU 执行。
    """
    result: list[SKUResult] = []
    expanded_total = 0
    for sku in skus:
        model = (sku.attributes.get("model_number") or "").strip()
        color = (sku.attributes.get("color") or "").strip()
        if not model or not color:
            result.append(sku)
            continue
        colors = [c.strip() for c in _COLOR_SPLIT_RE.split(color) if c.strip()]
        if len(colors) <= 1:
            result.append(sku)
            continue
        # 展开: 每个颜色一个独立 SKU
        for c in colors:
            new_attrs = dict(sku.attributes)
            new_attrs["color"] = c
            new_sku = SKUResult(
                sku_id=sku.sku_id,
                attributes=new_attrs,
                confidence=sku.confidence,
                extraction_method=sku.extraction_method,
            )
            if hasattr(sku, "page_no"):
                new_sku.page_no = sku.page_no
            result.append(new_sku)
        expanded_total += len(colors) - 1
    if expanded_total:
        logger.info("expand_color_variants", original=len(skus),
                     expanded=expanded_total, total=len(result))
    return result


def cross_page_dedup(
    all_skus: list[SKUResult],
    catalog_profile: "CatalogProfile | None" = None,
) -> list[SKUResult]:
    """
    跨页去重: 对所有页面汇总的 SKU 进行多步去重。
    用于 benchmark runner 汇总后消除跨页表格产生的重复。
    """
    if len(all_skus) <= 1:
        return all_skus
    before = len(all_skus)
    result = dedup_by_model(all_skus)                      # 型号去重
    result = _merge_variant_size(result)                    # 同型号尺寸变体合并
    result = _merge_no_model_into_model_bearing(result)     # 无型号→有型号合并
    result = _dedup_cross_page_by_name_similarity(result)   # 名称相似度去重
    result = _dedup_no_model_safe(result, catalog_profile)  # 高频重名去重
    result = _filter_cross_page_props(result, catalog_profile)  # 跨页道具清理
    # 颜色变体展开 (在所有去重之后，确保不被 dedup_by_model 合并回去)
    result = expand_color_variants(result)
    removed = before - len(result)
    if removed:
        logger.info("cross_page_dedup_done", before=before, after=len(result), removed=removed)
    return result


def _dedup_no_model_safe(
    skus: list[SKUResult],
    catalog_profile: "CatalogProfile | None" = None,
) -> list[SKUResult]:
    """安全去重无型号同名 SKU。

    规则（同时满足才去重）:
    - 无 model_number
    - 同名出现 ≥ 5 次
    - 或同名 ≥ 3 次 且 名称是品牌名 / 短通用词 (≤3 字)

    保留策略: 每组保留 confidence 最高的 1 个。
    安全阀: 同名 < 3 次绝不去重。
    """
    if len(skus) <= 2:
        return skus

    # 按名称分组 (仅无型号)
    from collections import defaultdict
    name_groups: dict[str, list[int]] = defaultdict(list)  # name_lower → [indices]
    for i, sku in enumerate(skus):
        model = (sku.attributes.get("model_number") or "").strip()
        if model:
            continue
        name = (sku.attributes.get("product_name") or "").strip().lower()
        if name:
            name_groups[name].append(i)

    # 品牌名集合 (小写)
    brand_lower: set[str] = set()
    if catalog_profile and catalog_profile.brand_names:
        brand_lower = {b.lower() for b in catalog_profile.brand_names}

    remove_indices: set[int] = set()
    for name, indices in name_groups.items():
        count = len(indices)
        if count < 3:
            continue  # 安全阀: < 3 次绝不去重

        should_dedup = False
        if count >= 3:
            should_dedup = True
        elif count >= 2:
            # 品牌名 或 短通用词 (≤4 字)
            if name in brand_lower or len(name) <= 4:
                should_dedup = True

        if should_dedup:
            # 保留 confidence 最高的 1 个
            best_idx = max(indices, key=lambda i: skus[i].confidence)
            for idx in indices:
                if idx != best_idx:
                    remove_indices.add(idx)

    if remove_indices:
        logger.info("dedup_no_model_safe_done",
                     total=len(skus), removed=len(remove_indices))
        return [s for i, s in enumerate(skus) if i not in remove_indices]
    return skus
