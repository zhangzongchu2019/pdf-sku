"""
毫秒级 fitz 页面预分类器。

利用 PyMuPDF (fitz) 的 metadata 特征（文字量、图片数/位置/尺寸、表格、页面尺寸）
在 <1ms 内将页面归入 10 种类型，为后续渲染和提取策略提供决策依据。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


# ── 页面类型常量 ──
BLANK = "BLANK"
TABLE = "TABLE"
SINGLE_STD = "SINGLE_STD"
SINGLE_LARGE = "SINGLE_LARGE"
SINGLE_TALL = "SINGLE_TALL"
MULTI_SPARSE = "MULTI_SPARSE"
IMG_DENSE = "IMG_DENSE"
IMG_LABEL = "IMG_LABEL"
MIXED_TABLE = "MIXED_TABLE"
MIXED_OTHER = "MIXED_OTHER"

# 页面类型 → 旧 A/B/C/D 映射
_LEGACY_MAP = {
    BLANK: "D",
    TABLE: "A",
    SINGLE_STD: "C",
    SINGLE_LARGE: "C",
    SINGLE_TALL: "C",
    MULTI_SPARSE: "C",
    IMG_DENSE: "C",
    IMG_LABEL: "C",
    MIXED_TABLE: "A",
    MIXED_OTHER: "B",
}


@dataclass
class FitzPageMeta:
    """fitz 提取的毫秒级页面特征。"""
    page_width: float = 0.0        # pt
    page_height: float = 0.0       # pt
    text_len: int = 0              # strip 后字符数
    image_count: int = 0
    image_bboxes: list[tuple] = field(default_factory=list)   # [(x0,y0,x1,y1), ...]
    image_native_sizes: list[tuple] = field(default_factory=list)  # [(w,h), ...]
    img_coverage: float = 0.0      # 图片 bbox 面积 / 页面面积
    txt_area_ratio: float = 0.0    # 文字 bbox 面积 / 页面面积
    table_count: int = 0
    table_area_ratio: float = 0.0  # 表格面积 / 页面面积
    table_row_count: int = 0       # 最大表格的行数
    grid: tuple[int, int] | None = None  # 检测到的网格 (rows, cols)


@dataclass
class PagePlan:
    """基于页面分类的处理策略。"""
    page_class: str = MIXED_OTHER          # 10 种类型之一
    render_dpi: int = 200                  # 渲染 DPI
    slices: list[tuple] | None = None      # 切片 bbox 列表, None=不切片
    expected_sku_range: tuple[int, int] = (1, 10)  # 预估 SKU 数范围
    scene_filter: bool = False             # 是否启用场景过滤
    legacy_type: str = "B"                 # 映射到旧 A/B/C/D
    pure_visual: bool = False              # 纯图产品页: text≤30 + img_coverage>85%


def extract_fitz_meta(page) -> FitzPageMeta:
    """从 fitz.Page 对象提取特征 (调用方在进程池中执行)。

    Args:
        page: fitz.Page 对象 (已打开的页面)
    """
    pw = page.rect.width
    ph = page.rect.height
    page_area = pw * ph if pw > 0 and ph > 0 else 1.0

    # 文本长度
    text_len = len(page.get_text().strip())

    # 图片信息
    images_raw = page.get_images()
    image_infos = page.get_image_info()
    image_bboxes = []
    for ii in image_infos:
        bbox = ii.get("bbox")
        if bbox and len(bbox) >= 4:
            image_bboxes.append(tuple(bbox[:4]))

    image_native_sizes = []
    for img in images_raw:
        # img: (xref, smask, width, height, bpc, colorspace, ...)
        if len(img) >= 4:
            image_native_sizes.append((img[2], img[3]))

    # 图片覆盖率 (考虑重叠: 用 union 面积)
    img_coverage = _calc_bbox_coverage(image_bboxes, page_area)

    # 文字面积比
    txt_area_ratio = _calc_text_area_ratio(page, page_area)

    # 表格
    table_count = 0
    table_area_ratio = 0.0
    table_row_count = 0
    try:
        tables = page.find_tables()
        if tables and tables.tables:
            table_count = len(tables.tables)
            total_table_area = 0.0
            for t in tables.tables:
                if hasattr(t, 'bbox') and t.bbox:
                    b = t.bbox
                    total_table_area += abs(b[2] - b[0]) * abs(b[3] - b[1])
                # 行数
                row_cnt = len(t.extract()) if hasattr(t, 'extract') else 0
                table_row_count = max(table_row_count, row_cnt)
            table_area_ratio = total_table_area / page_area
    except Exception:
        pass

    # 网格检测
    grid = _detect_grid(image_bboxes, pw, ph) if len(image_bboxes) >= 4 else None

    return FitzPageMeta(
        page_width=pw,
        page_height=ph,
        text_len=text_len,
        image_count=len(images_raw),
        image_bboxes=image_bboxes,
        image_native_sizes=image_native_sizes,
        img_coverage=img_coverage,
        txt_area_ratio=txt_area_ratio,
        table_count=table_count,
        table_area_ratio=table_area_ratio,
        table_row_count=table_row_count,
        grid=grid,
    )


def _calc_bbox_coverage(bboxes: list[tuple], page_area: float) -> float:
    """计算 bbox 列表的 union 面积占页面比例。"""
    if not bboxes or page_area <= 0:
        return 0.0
    # 简单方法: 直接加总面积 (忽略重叠, 上限为 1.0)
    total = sum(
        max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        for b in bboxes
    )
    return min(total / page_area, 1.0)


def _calc_text_area_ratio(page, page_area: float) -> float:
    """计算文字 block 面积占页面比例。"""
    if page_area <= 0:
        return 0.0
    try:
        blocks = page.get_text("blocks")
        total = 0.0
        for b in blocks:
            if len(b) >= 5 and b[6] == 0:  # type=0 is text
                total += max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        return min(total / page_area, 1.0)
    except Exception:
        return 0.0


def _detect_grid(
    bboxes: list[tuple],
    page_width: float,
    page_height: float,
) -> tuple[int, int] | None:
    """检测图片是否排列成网格。

    算法: 对图片 bbox 的 Y 中心聚类 → 行数，X 中心聚类 → 列数。
    间距 < 图片平均高度×0.3 视为同行/同列。
    """
    if len(bboxes) < 4:
        return None

    # 计算中心坐标
    y_centers = sorted([(b[1] + b[3]) / 2 for b in bboxes])
    x_centers = sorted([(b[0] + b[2]) / 2 for b in bboxes])

    # 平均图片尺寸
    avg_h = sum(abs(b[3] - b[1]) for b in bboxes) / len(bboxes)
    avg_w = sum(abs(b[2] - b[0]) for b in bboxes) / len(bboxes)

    if avg_h <= 0 or avg_w <= 0:
        return None

    rows = _cluster_1d(y_centers, avg_h * 0.3)
    cols = _cluster_1d(x_centers, avg_w * 0.3)

    if rows < 2 or cols < 2:
        return None

    # 验证: 网格应大致均匀 (每行/列图片数相近)
    expected = rows * cols
    actual = len(bboxes)
    if actual < expected * 0.5 or actual > expected * 1.5:
        return None

    return (rows, cols)


def _cluster_1d(values: list[float], threshold: float) -> int:
    """一维聚类: 相邻值间距 < threshold 归为同簇，返回簇数。"""
    if not values:
        return 0
    clusters = 1
    for i in range(1, len(values)):
        if values[i] - values[i - 1] > threshold:
            clusters += 1
    return clusters


class FitzClassifier:
    """毫秒级页面分类器。"""

    def classify(self, meta: FitzPageMeta) -> PagePlan:
        """基于 fitz 特征的分类决策树。

        优先级:
        1. BLANK: text=0, imgs=0
        2. TABLE: find_tables()>0, table面积>30%
        3. SINGLE_* (imgs=1, text<50): TALL / LARGE / STD
        4. MULTI_SPARSE: imgs 2-4, text<50
        5. IMG_DENSE: imgs≥5, text<200
        6. IMG_LABEL: img_coverage>70%, txt_area<15%
        7. MIXED_TABLE: 有表格
        8. MIXED_OTHER: 其余
        """
        pc = self._decide_class(meta)
        plan = PagePlan(
            page_class=pc,
            legacy_type=_LEGACY_MAP.get(pc, "B"),
        )
        self._set_render_strategy(plan, meta)
        self._set_sku_range(plan, meta)
        return plan

    def _decide_class(self, m: FitzPageMeta) -> str:
        # 1. BLANK
        if m.text_len == 0 and m.image_count == 0:
            return BLANK

        # 2. TABLE (排除产品卡片：单行"表格" + 大图覆盖 → 实为 IMG_LABEL)
        if m.table_count > 0 and m.table_area_ratio > 0.30:
            if m.table_row_count <= 2 and m.image_count > 0 and m.img_coverage > 0.50:
                pass  # 不返回 TABLE，继续往下判断更合适的类型
            else:
                return TABLE

        # 3. SINGLE_* (单图为主页面)
        if m.image_count == 1 and m.text_len < 50:
            max_native_dim = 0
            if m.image_native_sizes:
                max_native_dim = max(m.image_native_sizes[0])
            # 也看 bbox 尺寸
            max_bbox_dim = 0
            if m.image_bboxes:
                b = m.image_bboxes[0]
                max_bbox_dim = max(abs(b[2] - b[0]), abs(b[3] - b[1]))

            if m.page_height > 3000 or max_native_dim > 3000:
                return SINGLE_TALL
            if (m.page_width > 1500 or m.page_height > 1500
                    or max_native_dim > 1500 or max_bbox_dim > 1500):
                return SINGLE_LARGE
            return SINGLE_STD

        # 4. MULTI_SPARSE
        if 2 <= m.image_count <= 4 and m.text_len < 50:
            return MULTI_SPARSE

        # 5. IMG_DENSE
        if m.image_count >= 5 and m.text_len < 200:
            return IMG_DENSE

        # 6. IMG_LABEL
        if m.img_coverage > 0.70 and m.txt_area_ratio < 0.15:
            return IMG_LABEL

        # 7. MIXED_TABLE
        if m.table_count > 0:
            return MIXED_TABLE

        # 8. MIXED_OTHER
        return MIXED_OTHER

    def _set_render_strategy(self, plan: PagePlan, m: FitzPageMeta) -> None:
        """设置渲染 DPI 和切片策略。"""
        if plan.page_class == BLANK:
            plan.render_dpi = 0
            return

        if plan.page_class == TABLE:
            plan.render_dpi = 150
            return

        if plan.page_class in (SINGLE_STD, MULTI_SPARSE, IMG_LABEL, MIXED_TABLE, MIXED_OTHER):
            plan.render_dpi = 200
            return

        # 需要切片的类型 — 切片由 page_slicer 计算, 这里只设 DPI
        if plan.page_class == SINGLE_LARGE:
            plan.render_dpi = 200
            # slices 在 page_processor 中由 page_slicer 填充

        elif plan.page_class == SINGLE_TALL:
            plan.render_dpi = 200

        elif plan.page_class == IMG_DENSE:
            plan.render_dpi = 200

    def _set_sku_range(self, plan: PagePlan, m: FitzPageMeta) -> None:
        """设置预估 SKU 数量范围。"""
        pc = plan.page_class

        if pc == BLANK:
            plan.expected_sku_range = (0, 0)

        elif pc in (SINGLE_STD, SINGLE_LARGE, SINGLE_TALL):
            if pc == SINGLE_TALL:
                # 长页面 SKU 密度按有效高度估算
                eff_h = m.page_height
                if m.image_native_sizes:
                    for _nw, nh in m.image_native_sizes:
                        eff_h = max(eff_h, nh)
                estimated = max(10, int(eff_h / 150))
                plan.expected_sku_range = (5, estimated)
            elif pc == SINGLE_LARGE and m.image_count >= 3:
                # 多图页: 用 image_count 估算 SKU 数
                plan.expected_sku_range = (
                    max(2, m.image_count),
                    max(10, m.image_count * 2),
                )
            else:
                plan.expected_sku_range = (1, 10)

        elif pc == MULTI_SPARSE:
            plan.expected_sku_range = (
                max(1, m.image_count - 1),
                m.image_count + 1,
            )

        elif pc == IMG_DENSE:
            if m.grid:
                total = m.grid[0] * m.grid[1]
                plan.expected_sku_range = (max(1, total - 2), total + 2)
            else:
                plan.expected_sku_range = (
                    max(1, m.image_count // 2),
                    m.image_count,
                )

        elif pc == IMG_LABEL:
            if m.grid:
                total = m.grid[0] * m.grid[1]
                plan.expected_sku_range = (max(1, total - 2), total + 2)
            else:
                plan.expected_sku_range = (1, 5)

        elif pc == TABLE:
            if m.table_row_count > 1:
                plan.expected_sku_range = (
                    max(1, m.table_row_count - 1),
                    m.table_row_count * 2,
                )
            else:
                plan.expected_sku_range = (1, 10)

        elif pc in (MIXED_TABLE, MIXED_OTHER):
            if pc == MIXED_OTHER and m.image_count >= 3 and m.text_len < 100:
                # 低文字+多图页: 用 image_count 估算
                plan.expected_sku_range = (
                    max(1, m.image_count // 2),
                    max(5, m.image_count + 2),
                )
            elif m.text_len > 0:
                plan.expected_sku_range = (
                    max(1, m.text_len // 200),
                    max(2, m.text_len // 100),
                )
            else:
                plan.expected_sku_range = (1, 5)

        # 场景过滤: 对大图覆盖但产品数少的页面启用
        # 纯图页(text_len≤30)不启用，避免误杀纯图目录中的产品
        if pc in (SINGLE_STD, SINGLE_LARGE, IMG_LABEL, MULTI_SPARSE) and m.img_coverage > 0.60:
            if m.text_len > 30:
                plan.scene_filter = True
        # IMG_DENSE: 不启用 scene_filter — 密集产品网格页的特征恰恰是高图覆盖+低文字
        # 由 pure_visual 逻辑接管，避免误杀纯图产品
        # if pc == IMG_DENSE and m.img_coverage > 0.60 and m.text_len < 50:
        #     plan.scene_filter = True
        # SINGLE_TALL: 高图片覆盖 → 长条场景图 (纯图页除外)
        if pc == SINGLE_TALL and m.img_coverage > 0.60:
            if m.text_len > 30:
                plan.scene_filter = True

        # 纯图产品页标记: 几乎无文字 + 高图片覆盖
        # 用于下游切片/提取/评分的特殊处理路径
        if m.text_len <= 30 and m.img_coverage > 0.85 and pc != BLANK:
            plan.pure_visual = True
            plan.scene_filter = False  # 纯图页产品无文字标注是正常的
        # 宽松级: 少量文字但图片几乎全覆盖 (如 text=46, img_cov=1.0)
        elif m.text_len <= 80 and m.img_coverage >= 0.95 and pc != BLANK:
            plan.pure_visual = True
            plan.scene_filter = False
        # IMG_DENSE: 文字量<=200 (分类条件本身就是 <200) → 标记 pure_visual
        elif pc == IMG_DENSE and m.text_len <= 200:
            plan.pure_visual = True
            plan.scene_filter = False
