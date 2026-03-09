"""
Phase 2c: 合成大图布局检测。

当页面只有 1 张 search_eligible 图片且覆盖 >60% 页面面积时，
用 DocLayout-YOLO 检测其中的 Figure 区域并拆分为独立子图。
"""
from __future__ import annotations

import io
import threading
from pathlib import Path

import structlog

from pdf_sku.pipeline.ir import ImageInfo, PageMetadata
from pdf_sku.settings import settings

logger = structlog.get_logger()

# DocLayout-YOLO 中 Figure 类的常见标签名
_FIGURE_LABELS = {"figure", "picture", "image", "photo"}


class _ModelHolder:
    """懒加载单例，线程安全，进程内只加载一次 YOLO 模型。"""

    _instance: _ModelHolder | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.model = None
        self.available = False
        self._loaded = False

    @classmethod
    def get(cls) -> _ModelHolder:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            try:
                from doclayout_yolo import YOLOv10  # noqa: F811
            except ImportError:
                logger.info("layout_detect_skip", reason="doclayout_yolo not installed")
                return

            model_path = settings.doclayout_model_path
            if not model_path:
                model_path = str(
                    Path(__file__).resolve().parents[3] / "models" / "doclayout_yolo.pt"
                )
            if not Path(model_path).is_file():
                logger.info("layout_detect_skip", reason="model not found", path=model_path)
                return

            try:
                self.model = YOLOv10(model_path)
                self.available = True
                logger.info("layout_detect_model_loaded", path=model_path)
            except Exception as exc:
                logger.warning("layout_detect_load_failed", error=str(exc))


def _remove_containing_boxes(
    figures: list[tuple[float, float, float, float, float]],
) -> list[tuple[float, float, float, float, float]]:
    """去掉包含其他小框的大框。

    如果大框包含了 ≥1 个小框（overlap_ratio > 80%），则移除大框。
    输入: [(x0, y0, x1, y1, conf), ...]
    """
    if len(figures) <= 1:
        return figures

    def _area(b: tuple) -> float:
        return max(0, b[2] - b[0]) * max(0, b[3] - b[1])

    def _overlap_ratio(small: tuple, big: tuple) -> float:
        """small 被 big 包含的比例。"""
        ox0 = max(small[0], big[0])
        oy0 = max(small[1], big[1])
        ox1 = min(small[2], big[2])
        oy1 = min(small[3], big[3])
        overlap = max(0, ox1 - ox0) * max(0, oy1 - oy0)
        sa = _area(small)
        return overlap / sa if sa > 0 else 0.0

    # 按面积降序排列
    sorted_figs = sorted(figures, key=lambda f: _area(f), reverse=True)
    keep = []

    for i, fig_i in enumerate(sorted_figs):
        # 检查是否有面积更小的框被本框包含
        contains_smaller = False
        for j, fig_j in enumerate(sorted_figs):
            if j <= i:
                continue
            if _overlap_ratio(fig_j, fig_i) > 0.80:
                contains_smaller = True
                break
        if not contains_smaller:
            keep.append(fig_i)

    if len(keep) < len(figures):
        logger.info(
            "layout_nms_removed",
            before=len(figures),
            after=len(keep),
        )

    return keep


def detect_figures_on_image(
    image_data: bytes,
    conf_override: float | None = None,
) -> list[tuple[float, float, float, float]]:
    """在图片上跑 YOLO 检测，返回 Figure 类 bbox 列表 (像素坐标 x0,y0,x1,y1)。

    conf_override: 覆盖 settings.layout_detect_confidence，用于需要更高置信度的场景。
    """
    holder = _ModelHolder.get()
    holder.load()
    if not holder.available:
        return []

    from PIL import Image as PILImage

    pil_img = PILImage.open(io.BytesIO(image_data))
    conf_threshold = conf_override if conf_override is not None else settings.layout_detect_confidence
    results = holder.model.predict(pil_img, conf=conf_threshold, verbose=False)
    if not results:
        return []

    raw_figures: list[tuple[float, float, float, float, float]] = []

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        names = result.names  # {class_id: label_name}
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            label = names.get(cls_id, "").lower()
            conf = float(boxes.conf[i].item())
            if label in _FIGURE_LABELS:
                xyxy = boxes.xyxy[i].tolist()
                raw_figures.append((xyxy[0], xyxy[1], xyxy[2], xyxy[3], conf))

    # 去掉包含其他小框的大框
    filtered = _remove_containing_boxes(raw_figures)

    return [(f[0], f[1], f[2], f[3]) for f in filtered]


def split_composite_image(
    images: list[ImageInfo],
    page_no: int,
    page_width: float,
    page_height: float,
) -> list[ImageInfo]:
    """Phase 2c 入口：检测并拆分合成大图。

    触发条件：页面仅 1 张 search_eligible 图片，且 bbox 面积 > 60% 页面面积。
    检测到 ≥2 个 Figure 区域才拆分，否则原样返回。

    坐标转换：YOLO 输出像素坐标 → 缩放回 PDF points。
    """
    if not settings.layout_detect_enabled:
        return images

    eligible = [img for img in images if img.search_eligible]
    if len(eligible) != 1:
        return images

    big_img = eligible[0]

    # 只对瓦片拼合图（_merge_tile_fragments 创建）运行 YOLO。
    # 扫描版全页图或单品展示图不应拆分：YOLO 只能检测到产品图片区域，
    # 无法覆盖旁边的文字标签，拆分后会导致绑定错位并引入多余 SKU。
    if not getattr(big_img, "is_tile_composite", False):
        return images

    bx0, by0, bx1, by1 = big_img.bbox
    img_area = abs(bx1 - bx0) * abs(by1 - by0)
    page_area = page_width * page_height
    if page_area <= 0 or img_area / page_area <= 0.60:
        return images

    # 需要图片数据来跑检测
    if not big_img.data:
        return images

    figures = detect_figures_on_image(big_img.data)
    if len(figures) < 2:
        return images

    # 计算缩放比：图片像素 → PDF points
    from PIL import Image as PILImage

    pil_img = PILImage.open(io.BytesIO(big_img.data))
    img_px_w, img_px_h = pil_img.size
    bbox_w_pt = abs(bx1 - bx0)
    bbox_h_pt = abs(by1 - by0)
    scale_x = bbox_w_pt / img_px_w if img_px_w > 0 else 1.0
    scale_y = bbox_h_pt / img_px_h if img_px_h > 0 else 1.0

    # 原大图标记为不可搜索
    big_img.search_eligible = False

    new_images: list[ImageInfo] = []
    for idx, (fx0, fy0, fx1, fy1) in enumerate(figures):
        # YOLO 像素坐标 → PDF points（相对页面原点）
        pdf_x0 = bx0 + fx0 * scale_x
        pdf_y0 = by0 + fy0 * scale_y
        pdf_x1 = bx0 + fx1 * scale_x
        pdf_y1 = by0 + fy1 * scale_y

        dpi_scale = 150 / 72.0
        dw = abs(pdf_x1 - pdf_x0) * dpi_scale
        dh = abs(pdf_y1 - pdf_y0) * dpi_scale
        short = int(min(dw, dh))

        region = ImageInfo(
            image_id=f"p{page_no}_region_{idx}",
            bbox=(pdf_x0, pdf_y0, pdf_x1, pdf_y1),
            width=int(dw),
            height=int(dh),
            short_edge=short,
            search_eligible=short >= 200,
            role="unknown",
            data=b"",  # Phase 8 _crop_composites 会从截图裁剪
        )
        new_images.append(region)

    logger.info(
        "layout_split_composite",
        page=page_no,
        original_id=big_img.image_id,
        regions=len(new_images),
        img_px=f"{img_px_w}x{img_px_h}",
        bbox_area_ratio=round(img_area / page_area, 2),
    )

    # 返回：所有原图 + 新子图
    return images + new_images
