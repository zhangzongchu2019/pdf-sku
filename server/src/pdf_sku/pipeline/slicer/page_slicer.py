"""
页面切片模块。

对超大/超长/密集页面生成切片 bbox 列表，每片独立渲染+提取。
核心目标: 确保渲染后每片像素密度足够 LLM 识别细节（小字体型号等）。
"""
from __future__ import annotations

import fitz
import structlog

from pdf_sku.pipeline.classifier.fitz_classifier import (
    FitzPageMeta, PagePlan,
    SINGLE_LARGE, SINGLE_TALL, IMG_DENSE, IMG_LABEL,
)

logger = structlog.get_logger()

# 切片目标尺寸 (pt): 每片不超过此尺寸
MAX_SLICE_W = 1200.0
MAX_SLICE_H = 1200.0

# 纵向切片: 每片高度
TALL_SLICE_H = 1000.0
TALL_OVERLAP = 50.0  # 切片间重叠 (pt)


def plan_slices(meta: FitzPageMeta, plan: PagePlan) -> list[tuple] | None:
    """根据页面类型和特征生成切片 bbox 列表。

    Returns:
        切片 bbox 列表 [(x0, y0, x1, y1), ...] 或 None（不切片）
    """
    pc = plan.page_class

    if pc == SINGLE_LARGE:
        return _slice_single_large(meta)
    elif pc == SINGLE_TALL:
        return _slice_single_tall(meta)
    elif pc in (IMG_DENSE, IMG_LABEL):
        return _slice_img_dense(meta)

    return None


def render_slice(
    file_path: str,
    page_no: int,
    clip_bbox: tuple,
    dpi: int = 200,
) -> bytes:
    """用 fitz clip 参数渲染页面的指定区域。

    Args:
        file_path: PDF 文件路径
        page_no: 页码 (1-based)
        clip_bbox: (x0, y0, x1, y1) in pt
        dpi: 渲染 DPI

    Returns:
        PNG 图片字节
    """
    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        clip = fitz.Rect(*clip_bbox)
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def _slice_single_large(meta: FitzPageMeta) -> list[tuple] | None:
    """SINGLE_LARGE: 将页面分为 2-4 块，每块不超过 MAX_SLICE_W x MAX_SLICE_H。

    利用图片 bbox 找安全切割线（不穿过图片）。
    """
    pw, ph = meta.page_width, meta.page_height
    if pw <= 0 or ph <= 0:
        return None

    # 计算需要的行列数
    cols = max(1, int(pw / MAX_SLICE_W + 0.5))
    rows = max(1, int(ph / MAX_SLICE_H + 0.5))

    # 只有 1x1 不需要切片
    if rows <= 1 and cols <= 1:
        return None

    # 限制最大切片数
    cols = min(cols, 3)
    rows = min(rows, 3)

    # 收集禁切区间
    forbidden_y = _get_forbidden_intervals(meta.image_bboxes, axis="y")
    forbidden_x = _get_forbidden_intervals(meta.image_bboxes, axis="x")

    # 计算切割线
    y_cuts = _safe_cuts(rows, ph, forbidden_y)
    x_cuts = _safe_cuts(cols, pw, forbidden_x)

    slices = []
    for r in range(len(y_cuts) - 1):
        for c in range(len(x_cuts) - 1):
            slices.append((x_cuts[c], y_cuts[r], x_cuts[c + 1], y_cuts[r + 1]))

    return slices if len(slices) > 1 else None


def _slice_single_tall(meta: FitzPageMeta) -> list[tuple] | None:
    """SINGLE_TALL: 纵向等分，每片高度 ~TALL_SLICE_H，片间重叠 TALL_OVERLAP。"""
    pw, ph = meta.page_width, meta.page_height
    if ph <= TALL_SLICE_H * 1.5:
        return None  # 不够长，不切

    n_slices = max(2, int(ph / TALL_SLICE_H + 0.5))

    # 收集禁切区间
    forbidden_y = _get_forbidden_intervals(meta.image_bboxes, axis="y")

    step = ph / n_slices
    slices = []
    for i in range(n_slices):
        y0 = max(0, i * step - TALL_OVERLAP) if i > 0 else 0
        y1 = min(ph, (i + 1) * step + TALL_OVERLAP) if i < n_slices - 1 else ph
        slices.append((0, y0, pw, y1))

    return slices if len(slices) > 1 else None


def _slice_img_dense(meta: FitzPageMeta) -> list[tuple] | None:
    """IMG_DENSE: 按网格行分组，每片包含 2-3 行。若无网格则按高度等分。"""
    pw, ph = meta.page_width, meta.page_height

    if meta.grid and meta.grid[0] >= 2:
        rows = meta.grid[0]
        # 每行一片（密集页需要足够分辨率识别每个产品）
        n_slices = rows

        if n_slices <= 1:
            return None

        row_height = ph / rows
        slices = []
        for i in range(n_slices):
            y0 = max(0, i * row_height - TALL_OVERLAP) if i > 0 else 0
            y1 = min(ph, (i + 1) * row_height + TALL_OVERLAP) if i < n_slices - 1 else ph
            slices.append((0, y0, pw, y1))

        return slices if len(slices) > 1 else None

    # 无网格: 按高度等分 (每片 ~1000pt)
    if ph > TALL_SLICE_H * 1.5:
        return _slice_single_tall(meta)

    return None


def _get_forbidden_intervals(
    bboxes: list[tuple], axis: str = "y"
) -> list[tuple[float, float]]:
    """收集所有图片 bbox 在指定轴的 [min, max] 区间。"""
    intervals = []
    for b in bboxes:
        if axis == "y":
            intervals.append((b[1], b[3]))
        else:
            intervals.append((b[0], b[2]))
    # 合并重叠区间
    return _merge_intervals(intervals)


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """合并重叠区间。"""
    if not intervals:
        return []
    sorted_iv = sorted(intervals)
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _safe_cuts(n_parts: int, total: float, forbidden: list[tuple[float, float]]) -> list[float]:
    """生成 n_parts 个安全切割点 (不穿过禁切区间)。

    返回 n_parts+1 个边界值 [0, cut1, cut2, ..., total]。
    """
    if n_parts <= 1:
        return [0.0, total]

    step = total / n_parts
    cuts = [0.0]

    for i in range(1, n_parts):
        candidate = i * step
        # 检查是否落入禁切区间
        adjusted = _adjust_cut(candidate, forbidden, total)
        # 确保切割点递增
        if adjusted <= cuts[-1] + 10:
            adjusted = cuts[-1] + step * 0.5
        cuts.append(min(adjusted, total - 10))

    cuts.append(total)
    return cuts


def _adjust_cut(pos: float, forbidden: list[tuple[float, float]], total: float) -> float:
    """如果 pos 落入禁切区间，移到最近的间隙。"""
    for start, end in forbidden:
        if start <= pos <= end:
            # 选择离 pos 更近的边
            to_start = pos - start
            to_end = end - pos
            if to_start <= to_end:
                return max(0, start - 2)  # 切在图片上方
            else:
                return min(total, end + 2)  # 切在图片下方
    return pos
