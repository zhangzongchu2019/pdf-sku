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
TALL_SLICE_H = 900.0
TALL_OVERLAP = 80.0  # 切片间重叠 (pt)


def plan_slices(meta: FitzPageMeta, plan: PagePlan) -> list[tuple] | None:
    """根据页面类型和特征生成切片 bbox 列表。

    Returns:
        切片 bbox 列表 [(x0, y0, x1, y1), ...] 或 None（不切片）
    """
    pc = plan.page_class

    if pc == SINGLE_LARGE:
        return _slice_single_large(meta, pure_visual=plan.pure_visual)
    elif pc == SINGLE_TALL:
        return _slice_single_tall(meta)
    elif pc in (IMG_DENSE, IMG_LABEL):
        return _slice_img_dense(meta)

    return None


MAX_LONG_EDGE = 3000  # 发送给 LLM 的图片最长边限制


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
        JPEG 图片字节 (长边不超过 MAX_LONG_EDGE)
    """
    from PIL import Image
    import io

    doc = fitz.open(file_path)
    try:
        page = doc[page_no - 1]
        zoom = dpi / 72.0
        clip = fitz.Rect(*clip_bbox)
        # 计算渲染后尺寸，超出限制则降低缩放
        w = clip.width * zoom
        h = clip.height * zoom
        long_edge = max(w, h)
        if long_edge > MAX_LONG_EDGE:
            zoom = zoom * MAX_LONG_EDGE / long_edge
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        # PNG → JPEG 压缩 (体积缩小 5-10 倍)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    finally:
        doc.close()


def _slice_single_large(meta: FitzPageMeta, *, pure_visual: bool = False) -> list[tuple] | None:
    """SINGLE_LARGE: 将页面分为 2-9 块，每块不超过目标尺寸。

    利用图片 bbox 找安全切割线（不穿过图片）。
    注意: 页面可能因嵌入高分辨率图片而被分类为 SINGLE_LARGE，
    即使 PDF 页面尺寸 < MAX_SLICE_W/H，仍应切片以获得足够像素密度。

    pure_visual=True 时使用更小的目标尺寸 (700)，产生更多切片，
    适用于单张合成图内含多个产品的纯图目录页。
    """
    pw, ph = meta.page_width, meta.page_height
    if pw <= 0 or ph <= 0:
        return None

    # pure_visual: 更激进的切片 (700) — 合成产品图需要高密度
    # 普通 SINGLE_LARGE: 适中切片 (900)
    target_w = 700.0 if pure_visual else 900.0
    target_h = 700.0 if pure_visual else 900.0

    # 考虑原生图片分辨率: 高分辨率嵌入图需要更多切片
    eff_w, eff_h = pw, ph
    if meta.image_native_sizes:
        for nw, nh in meta.image_native_sizes:
            eff_w = max(eff_w, nw)
            eff_h = max(eff_h, nh)

    # 计算需要的行列数 (基于有效尺寸)
    cols = max(1, int(eff_w / target_w + 0.5))
    rows = max(1, int(eff_h / target_h + 0.5))

    # 多图页面: 确保切片数匹配图片密度
    if meta.image_count >= 6:
        rows = max(rows, 2)
        cols = max(cols, 2)

    # 已被分类为 SINGLE_LARGE → 保证至少 2 片
    # (分类可能基于 native_dim > 1500 而非 page pt)
    if rows <= 1 and cols <= 1:
        if pw >= ph:
            cols = 2
        else:
            rows = 2

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
    """SINGLE_TALL: 纵向等分，每片高度 ~TALL_SLICE_H，片间重叠 TALL_OVERLAP。

    注意: 页面可能因嵌入高分辨率图片 (native_dim > 3000) 而被分类为 SINGLE_TALL，
    即使 PDF 页面高度 < 1500pt，仍应至少切 2 片。
    """
    pw, ph = meta.page_width, meta.page_height
    if ph <= 0:
        return None

    # 考虑原生图片分辨率
    eff_h = ph
    if meta.image_native_sizes:
        for _nw, nh in meta.image_native_sizes:
            eff_h = max(eff_h, nh)

    n_slices = max(2, int(eff_h / TALL_SLICE_H + 0.5))

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
    """IMG_DENSE: 按网格行分组，每行一片。若无网格则按高度等分。"""
    pw, ph = meta.page_width, meta.page_height

    if meta.grid and meta.grid[0] >= 2:
        rows = meta.grid[0]
        cols = meta.grid[1] if len(meta.grid) > 1 else 1

        # 每行产品多 (cols>=3) 时每行切两片，确保每片不超过 ~4 个产品
        if cols >= 3:
            n_slices = rows * 2
        else:
            n_slices = rows

        n_slices = min(n_slices, 20)  # 上限 (佛山奢品嘉 avg 20图/页)

        if n_slices <= 1:
            return None

        row_height = ph / n_slices
        slices = []
        for i in range(n_slices):
            y0 = max(0, i * row_height - TALL_OVERLAP) if i > 0 else 0
            y1 = min(ph, (i + 1) * row_height + TALL_OVERLAP) if i < n_slices - 1 else ph
            slices.append((0, y0, pw, y1))

        return slices if len(slices) > 1 else None

    # 无网格回退: 用 image_count 估算需要的切片数，每片覆盖 ~2 张图
    if meta.image_count >= 4:
        n_slices = min(max(4, (meta.image_count + 1) // 2), 16)
        row_height = ph / n_slices
        slices = []
        for i in range(n_slices):
            y0 = max(0, i * row_height - TALL_OVERLAP) if i > 0 else 0
            y1 = min(ph, (i + 1) * row_height + TALL_OVERLAP) if i < n_slices - 1 else ph
            slices.append((0, y0, pw, y1))
        return slices if len(slices) > 1 else None
    return _slice_single_tall(meta)


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
