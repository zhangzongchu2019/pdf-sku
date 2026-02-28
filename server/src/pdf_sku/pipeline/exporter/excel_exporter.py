"""
Excel 导出器 — 将 Job 的 SKU 识别结果导出为两个 Excel 文件。

File 1 (full_export.xlsx):   商品子图 + 所有提取到的 SKU 属性（动态列）
File 2 (keywords_export.xlsx): 商品子图 + 固定关键词字段映射
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

logger = structlog.get_logger()

# ─────────────────────── 关键词映射 ───────────────────────

KEYWORD_FIELDS: list[tuple[str, list[str]]] = [
    ('商品名称/描述', ['product_name', 'name', 'description', '产品名称', '品名']),
    ('售价',         ['unit_price', 'price', 'retail_price', '单价', '售价']),
    ('商品规格',     ['size', 'spec', 'specification', '规格', '尺寸', '型号']),
    ('颜色',         ['color', 'colour', '颜色', '色号']),
    ('批发价',       ['wholesale_price', '批发价', '批发']),
    ('打包价',       ['package_price', '打包价', '打包']),
    ('代发价',       ['dropship_price', '代发价', '代发']),
    ('活动价',       ['promotion_price', 'activity_price', '活动价', '促销价']),
    ('库存',         ['stock', 'inventory', '库存', '数量']),
    ('重量(kg)',     ['weight', '重量', 'weight_kg', '毛重']),
    ('自动下架时间', ['auto_offline_time', '下架时间', 'offline_time']),
]

# 固定列的候选键集合（用于从动态列中去除已覆盖的字段）
_FIXED_CANDIDATES: set[str] = {
    'product_name', 'name', '产品名称',
    'spec', 'specification', 'size', '规格', '尺寸',
    'unit_price', 'price', '单价',
    'color', 'colour', '颜色',
    'remark', 'note', '备注', '说明',
    'weight', 'weight_kg', '重量',
}


# ─────────────────────── 数据结构 ───────────────────────

@dataclass
class ExportRow:
    page_number: int
    sku_id: str
    attributes: dict
    image_bytes: bytes = field(default_factory=bytes)
    image_id: str = ""


# ─────────────────────── 辅助函数 ───────────────────────

def _get_field_value(attrs: dict, candidates: list[str]) -> str:
    """遍历候选键列表，返回第一个命中的非空值，否则返回空字符串。"""
    for key in candidates:
        val = attrs.get(key)
        if val is not None and val != "":
            return str(val)
    return ""


def _embed_image(ws, img_bytes: bytes, row: int, col: int = 1, max_px: int = 60) -> None:
    """将图片 bytes 缩放后嵌入到指定单元格。"""
    if not img_bytes:
        return
    try:
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.utils import get_column_letter
        from PIL import Image as PILImage

        pil = PILImage.open(io.BytesIO(img_bytes))
        pil.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        buf.seek(0)

        xl_img = XLImage(buf)
        xl_img.anchor = f"{get_column_letter(col)}{row}"
        ws.add_image(xl_img)
    except Exception as e:
        logger.warning("excel_embed_image_failed", row=row, error=str(e))


def _apply_header_style(ws, headers: list[str]) -> None:
    """统一设置首行表头样式：浅蓝底色 + 加粗 + 居中。"""
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill("solid", fgColor="BDD7EE")
    header_font = Font(bold=True)

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 图片列（A 列）宽度 14，文字列预设 20
    ws.column_dimensions["A"].width = 14
    for col_idx in range(2, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 20

    ws.freeze_panes = "A2"


# ─────────────────────── 主类 ───────────────────────

class ExcelExporter:
    def __init__(self, job_data_dir: str) -> None:
        self._job_data_dir = Path(job_data_dir)

    async def load_job_data(self, db: AsyncSession, job_id: UUID) -> list[ExportRow]:
        """查询 SKU + 绑定图片，构建导出行列表。"""
        from pdf_sku.common.models import SKU, SKUImageBinding, Image

        # 1. 所有非 superseded 的 SKU，按页码 + 插入顺序排序
        skus = (await db.execute(
            select(SKU)
            .where(SKU.job_id == job_id, SKU.superseded == False)
            .order_by(SKU.page_number, SKU.id)
        )).scalars().all()

        if not skus:
            return []

        sku_ids = [s.sku_id for s in skus]

        # 2. 每个 SKU 的 rank=1 主图绑定
        bindings = (await db.execute(
            select(SKUImageBinding)
            .where(
                SKUImageBinding.job_id == job_id,
                SKUImageBinding.sku_id.in_(sku_ids),
                SKUImageBinding.rank == 1,
                SKUImageBinding.is_latest == True,
            )
        )).scalars().all()

        sku_to_image_id: dict[str, str] = {b.sku_id: b.image_id for b in bindings}
        image_ids = list(set(sku_to_image_id.values()))

        # 3. 批量查询图片元数据
        images: dict[str, object] = {}
        if image_ids:
            img_rows = (await db.execute(
                select(Image)
                .where(Image.job_id == job_id, Image.image_id.in_(image_ids))
            )).scalars().all()
            images = {img.image_id: img for img in img_rows}

        # 4. 读取图片文件，构建导出行
        job_dir = self._job_data_dir / str(job_id)
        rows: list[ExportRow] = []

        for sku in skus:
            image_id = sku_to_image_id.get(sku.sku_id, "")
            image_bytes = b""
            if image_id and image_id in images:
                img = images[image_id]
                img_path = job_dir / img.extracted_path
                try:
                    image_bytes = img_path.read_bytes()
                except Exception as e:
                    logger.warning(
                        "excel_export_image_read_failed",
                        image_id=image_id, path=str(img_path), error=str(e),
                    )

            rows.append(ExportRow(
                page_number=sku.page_number,
                sku_id=sku.sku_id,
                attributes=dict(sku.attributes or {}),
                image_bytes=image_bytes,
                image_id=image_id,
            ))

        logger.info("excel_export_rows_loaded", job_id=str(job_id), count=len(rows))
        return rows

    def build_full_excel(self, rows: list[ExportRow]) -> io.BytesIO:
        """
        File 1: 图片 | 固定属性列 | 动态属性列（按出现频率排序）
        """
        import openpyxl
        from openpyxl.styles import Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "全量导出"

        # 收集所有行中出现过的属性键，按频率降序
        key_freq: dict[str, int] = {}
        for row in rows:
            for k in row.attributes:
                key_freq[k] = key_freq.get(k, 0) + 1
        all_keys_by_freq = sorted(key_freq, key=lambda k: -key_freq[k])

        # 固定列定义（列标题 → 候选键列表）
        fixed_cols: list[tuple[str, list[str]]] = [
            ("产品名称", ["product_name", "name", "产品名称"]),
            ("规格",     ["spec", "specification", "size", "规格", "尺寸"]),
            ("单价",     ["unit_price", "price", "单价"]),
            ("颜色",     ["color", "colour", "颜色"]),
            ("备注",     ["remark", "note", "备注", "说明"]),
            ("重量",     ["weight", "weight_kg", "重量"]),
        ]

        # 动态列：排除已被固定列覆盖的键
        extra_keys = [k for k in all_keys_by_freq if k not in _FIXED_CANDIDATES]

        headers = (
            ["图片", "页码", "SKU ID"]
            + [col[0] for col in fixed_cols]
            + extra_keys
        )
        _apply_header_style(ws, headers)

        # 数据行
        for row_idx, row in enumerate(rows, 2):
            attrs = row.attributes

            row_data: list = [
                None,                   # A 列：图片占位
                row.page_number,        # B
                row.sku_id,             # C
            ]
            for _, candidates in fixed_cols:
                row_data.append(_get_field_value(attrs, candidates))
            for k in extra_keys:
                v = attrs.get(k)
                row_data.append(str(v) if v is not None else "")

            for col_idx, val in enumerate(row_data, 1):
                if col_idx == 1:
                    continue  # 图片列由 _embed_image 处理
                ws.cell(row=row_idx, column=col_idx, value=val).alignment = Alignment(
                    vertical="center", wrap_text=True
                )

            if row.image_bytes:
                _embed_image(ws, row.image_bytes, row_idx, col=1, max_px=60)
                ws.row_dimensions[row_idx].height = 60
            else:
                ws.row_dimensions[row_idx].height = 15

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def build_keywords_excel(self, rows: list[ExportRow]) -> io.BytesIO:
        """
        File 2: 图片 + 固定 11 个关键词字段（缺失留空）
        """
        import openpyxl
        from openpyxl.styles import Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "关键词导出"

        headers = ["图片"] + [kf[0] for kf in KEYWORD_FIELDS]
        _apply_header_style(ws, headers)

        for row_idx, row in enumerate(rows, 2):
            row_data: list = [None]  # A 列图片占位
            for _, candidates in KEYWORD_FIELDS:
                row_data.append(_get_field_value(row.attributes, candidates))

            for col_idx, val in enumerate(row_data, 1):
                if col_idx == 1:
                    continue
                ws.cell(row=row_idx, column=col_idx, value=val).alignment = Alignment(
                    vertical="center", wrap_text=True
                )

            if row.image_bytes:
                _embed_image(ws, row.image_bytes, row_idx, col=1, max_px=60)
                ws.row_dimensions[row_idx].height = 60
            else:
                ws.row_dimensions[row_idx].height = 15

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
