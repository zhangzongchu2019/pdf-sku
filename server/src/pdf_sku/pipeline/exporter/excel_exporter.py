"""导出标准 22 列 Excel，商品图片直接嵌入单元格。"""
from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage

import structlog

logger = structlog.get_logger()

# 固定列头（去掉动态的"商品图片"前缀列，运行时按最大图片数动态生成）
_FIXED_HEADERS = [
    "规格图片",            # after image cols
    "商品名称/描述",
    "售价",
    "货号",
    "商品ID",
    "标签",
    "来源(仅自己可见)",
    "商品简称",
    "商品规格",
    "颜色",
    "规格编码",
    "批发价",
    "打包价",
    "代发价",
    "拿货价(仅自己可见)",
    "活动类型",
    "活动价",
    "库存",
    "重量(kg)",
    "备注(公开)",
    "自动下架时间",
]

# SKU attributes → 固定列 header 名映射
_ATTR_MAP: dict[str, str] = {
    "product_name": "商品名称/描述",
    "price": "售价",
    "model_number": "货号",
    "tag": "标签",
    "specs": "商品规格",
    "size": "商品规格",
    "color": "颜色",
}

# 图片嵌入尺寸（像素）
_IMG_WIDTH_PX = 80
_IMG_HEIGHT_PX = 80
# 行高 / 列宽 对应 (openpyxl 单位: 行高=points, 列宽≈字符数)
_ROW_HEIGHT = 65
_IMG_COL_WIDTH = 13


def _resolve_image_disk_path(url_path: str, job_dir: Path) -> Path | None:
    """将 /images/jobs/{job_id}/images/xxx.jpg 风格的 URL 转为磁盘路径。"""
    # url_path 形如 "/images/jobs/<job_id>/images/p1_img3.jpg"
    # job_dir 形如 "/data/jobs/<job_id>"
    # 磁盘路径 = job_dir / "images/p1_img3.jpg"
    parts = url_path.split("/")
    # 找到 job_id 后面的相对路径
    try:
        idx = parts.index("jobs")
        # parts[idx+1] = job_id, parts[idx+2:] = relative path
        relative = "/".join(parts[idx + 2:])
    except (ValueError, IndexError):
        relative = url_path.lstrip("/")
    p = job_dir / relative
    return p if p.exists() else None


def _prepare_thumbnail(img_path: Path) -> bytes | None:
    """读取图片并缩放到缩略图大小，返回 PNG bytes。"""
    try:
        with PILImage.open(img_path) as img:
            img.thumbnail((_IMG_WIDTH_PX * 2, _IMG_HEIGHT_PX * 2))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as e:
        logger.warning("thumbnail_failed", path=str(img_path), error=str(e))
        return None


def export_job_excel(
    result_json: dict,
    job_dir: Path,
    output_path: Path,
    source_name: str | None = None,
) -> None:
    """
    从 result.json 结构导出带嵌入图片的 Excel。

    Args:
        result_json: result.json 的 dict 内容
        job_dir: /data/jobs/{job_id}/ 目录
        output_path: 输出 xlsx 路径
        source_name: 原始文件名（覆盖 result_json 中的 dataset）
    """
    if source_name is None:
        source_name = result_json.get("dataset", "")

    # ── 第一遍: 收集所有 SKU 数据，确定最大图片数 ──
    sku_rows: list[dict[str, Any]] = []
    max_images = 1  # 至少 1 列"商品图片"

    for page in result_json.get("pages", []):
        for sku in page.get("skus", []):
            if sku.get("validity", "valid") != "valid":
                continue
            imgs = sku.get("image_paths", [])
            if len(imgs) > max_images:
                max_images = len(imgs)
            sku_rows.append(sku)

    # ── 构建表头 ──
    # [商品图片, 商品图片, ..., 规格图片, 商品名称/描述, ...]
    headers: list[str] = ["商品图片"] * max_images + _FIXED_HEADERS

    # 列名 → 列号 (1-based) 映射（固定列取第一个匹配）
    fixed_col_map: dict[str, int] = {}
    for i, h in enumerate(headers):
        if h not in fixed_col_map or h == "商品图片":
            # 商品图片列不放 fixed_col_map，单独处理
            if h != "商品图片":
                fixed_col_map[h] = i + 1

    # ── 写入 ──
    wb = Workbook()
    ws = wb.active
    ws.title = "商品数据"

    header_font = Font(bold=True)
    header_align = Alignment(horizontal="center", vertical="center")
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.alignment = header_align

    # 图片列列宽
    for ci in range(1, max_images + 1):
        ws.column_dimensions[get_column_letter(ci)].width = _IMG_COL_WIDTH

    # 所有数据单元格的对齐方式：自动换行 + 垂直居中
    data_align = Alignment(wrap_text=True, vertical="center")

    row_num = 2
    embedded_count = 0

    for sku in sku_rows:
        attrs = sku.get("attributes", {})
        imgs = sku.get("image_paths", [])

        ws.row_dimensions[row_num].height = _ROW_HEIGHT

        # ── 嵌入商品图片 ──
        for img_idx, img_url in enumerate(imgs):
            if img_idx >= max_images:
                break
            col = img_idx + 1  # 1-based
            disk_path = _resolve_image_disk_path(img_url, job_dir)
            if not disk_path:
                continue
            thumb_bytes = _prepare_thumbnail(disk_path)
            if not thumb_bytes:
                continue
            try:
                xl_img = XlImage(BytesIO(thumb_bytes))
                xl_img.width = _IMG_WIDTH_PX
                xl_img.height = _IMG_HEIGHT_PX
                anchor = f"{get_column_letter(col)}{row_num}"
                ws.add_image(xl_img, anchor)
                embedded_count += 1
            except Exception as e:
                logger.warning("embed_image_failed", error=str(e))

        # ── 辅助：写单元格并设置对齐 ──
        def _set(header: str, value: str) -> None:
            col = fixed_col_map.get(header)
            if col and value:
                c = ws.cell(row=row_num, column=col, value=value)
                c.alignment = data_align

        # ── 文本列 ──
        # 商品名称/描述
        pname = attrs.get("product_name", "")
        model = attrs.get("model_number", "")
        variant = attrs.get("variant", "")
        specs = attrs.get("specs", "") or attrs.get("size", "")
        desc_parts = [p for p in [pname, model, variant, specs] if p]
        # 去重: 如果 model == pname 则不重复
        if model and model == pname and len(desc_parts) > 1:
            desc_parts.remove(model)
        _set("商品名称/描述", " ".join(desc_parts))
        _set("售价", str(attrs.get("price", "")))
        _set("货号", str(attrs.get("model_number", "")))
        _set("标签", str(attrs.get("tag", "")))
        _set("来源(仅自己可见)", source_name)
        _set("商品规格", str(attrs.get("specs", "") or attrs.get("size", "")))
        _set("颜色", str(attrs.get("color", "")))

        row_num += 1

    # ── 列宽微调 ──
    _col_widths = {
        "规格图片": 13,
        "商品名称/描述": 40,
        "售价": 12,
        "货号": 18,
        "商品ID": 12,
        "标签": 15,
        "来源(仅自己可见)": 25,
        "商品简称": 15,
        "商品规格": 20,
        "颜色": 15,
        "规格编码": 15,
        "批发价": 12,
        "打包价": 12,
        "代发价": 12,
        "拿货价(仅自己可见)": 18,
        "活动类型": 12,
        "活动价": 12,
        "库存": 10,
        "重量(kg)": 12,
        "备注(公开)": 20,
        "自动下架时间": 18,
    }
    for header, width in _col_widths.items():
        col = fixed_col_map.get(header)
        if col:
            ws.column_dimensions[get_column_letter(col)].width = width

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    logger.info("excel_exported", path=str(output_path),
                skus=len(sku_rows), images=embedded_count)
