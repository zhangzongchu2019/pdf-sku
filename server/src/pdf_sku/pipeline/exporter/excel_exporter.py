"""
Excel 导出器 — 将 Job 的 SKU 识别结果导出为两个 Excel 文件。

File 1 (full_export.xlsx):   商品子图 + 所有提取到的 SKU 属性（动态列）
File 2 (keywords_export.xlsx): 固定关键词模板（平台导入格式）

多图支持 (keywords_export): 同一 SKU 的多张商品子图各占一列，
  列名均为"商品图片"（不编号，可重复）。
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

logger = structlog.get_logger()

# ─────────────────────── 关键词列定义 ───────────────────────
# 平台导入模板列顺序（不含首列"商品图片"）
# 每项: (列标题, 语义描述)  语义描述为空字符串的列固定留空
KEYWORD_FIELDS: list[tuple[str, str]] = [
    ('规格图片',           ''),
    ('商品名称/描述',       '商品型号 + 规格拼接，例如"WS X-683 950W*760D*850H"'),
    ('售价',              '商品零售单价或市场价，面向终端消费者'),
    ('货号',              '商品型号/货号编号，例如"A105#"、"WS X-683"'),
    ('商品ID',            ''),
    ('标签',              ''),
    ('来源(仅自己可见)',    ''),    # 特殊列: PDF 文件名
    ('商品简称',           ''),
    ('商品规格',           '商品的规格、尺寸，例如"130x70x55cm"'),
    ('颜色',              '商品颜色或色号，例如"红色"、"深蓝"'),
    ('规格编码',           ''),
    ('批发价',             '批量采购价格，通常低于零售价'),
    ('打包价',             '打包装或组合销售价格'),
    ('代发价',             '供货商代发货价格（dropship），直接发给终端买家'),
    ('拿货价(仅自己可见)', ''),
    ('活动类型',           ''),
    ('活动价',             '促销、活动或限时优惠价格'),
    ('库存',              '商品库存数量'),
    ('重量(kg)',           '商品重量，单位 kg'),
    ('备注(公开)',         ''),
    ('自动下架时间',        '商品自动下架或到期时间'),
]

# 固定留空的列
_EMPTY_KW_COLS: frozenset[str] = frozenset({
    '规格图片', '商品ID', '标签', '商品简称',
    '规格编码', '拿货价(仅自己可见)', '活动类型', '备注(公开)',
})

# 特殊处理列（不走 LLM 映射，从 ExportRow 字段直接计算）
_SOURCE_COL = '来源(仅自己可见)'   # PDF 文件名
_NAME_COL   = '商品名称/描述'      # 型号 + 规格
_MODEL_COL  = '货号'               # 型号

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
    images: list[bytes] = field(default_factory=list)   # 多图：每张占一列
    image_ids: list[str] = field(default_factory=list)
    source_text: str = ""   # PDF 原始 OCR 文字（按页）


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
        logger.warning("excel_embed_image_failed", row=row, col=col, error=str(e))


def _apply_header_style(ws, headers: list[str], n_img_cols: int = 1) -> None:
    """统一设置首行表头样式：浅蓝底色 + 加粗 + 居中。图片列宽 14，文字列宽 20。"""
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill("solid", fgColor="BDD7EE")
    header_font = Font(bold=True)

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 图片列宽 14，其余列宽 20
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        if col_idx <= n_img_cols:
            ws.column_dimensions[col_letter].width = 14
        else:
            ws.column_dimensions[col_letter].width = 20

    ws.freeze_panes = f"{get_column_letter(n_img_cols + 1)}2"


# ─────────────────────── LLM 语义映射 ───────────────────────

async def build_keyword_mapping_via_llm(
    rows: list[ExportRow],
    llm_service,
) -> dict[str, list[str]]:
    """
    通过一次 LLM 调用，将 SKU 属性键语义映射到标准关键词列。

    返回: {关键词列标题: [匹配的属性键, ...]}（按置信度从高到低）
    如某列无匹配，则对应值为空列表。
    """
    # 1. 收集所有属性键及各自的示例值（最多 3 个不同值）
    key_samples: dict[str, list[str]] = {}
    for row in rows:
        for k, v in row.attributes.items():
            if v is None or v == "":
                continue
            samples = key_samples.setdefault(k, [])
            sv = str(v).strip()
            if sv and sv not in samples and len(samples) < 3:
                samples.append(sv)

    if not key_samples:
        return {kf[0]: [] for kf in KEYWORD_FIELDS}

    # 2. 构造 LLM prompt（仅映射有语义描述的非空列）
    mappable_fields = [
        kf for kf in KEYWORD_FIELDS
        if kf[1]  # 语义描述非空 → 需要 LLM 映射
        and kf[0] not in (_NAME_COL, _MODEL_COL)  # 这两列直接从属性提取，不走 LLM
    ]

    attr_lines = "\n".join(
        f'  "{k}": {json.dumps(v, ensure_ascii=False)}'
        for k, v in key_samples.items()
    )
    keyword_lines = "\n".join(
        f'  "{kf[0]}": {kf[1]}'
        for kf in mappable_fields
    )

    prompt = f"""你是一个商品数据结构专家。请根据语义理解，将 SKU 属性字段映射到标准导出列。

## SKU 属性字段（字段名: [示例值列表]）
{{{attr_lines}
}}

## 标准导出列（列名: 语义说明）
{{{keyword_lines}
}}

## 任务
对于每个标准导出列，从属性字段中找出语义上最匹配的字段名（可能有多个，按匹配度从高到低排列）。
如果没有任何字段与某个列语义相关，则返回空数组 []。

## 返回格式（严格 JSON，不要有任何额外文字）
{{
  "售价": ["最匹配的字段名", "次匹配的字段名"],
  ...（覆盖所有 {len(mappable_fields)} 个标准列）
}}"""

    try:
        resp = await llm_service.call_llm(
            operation="keyword_mapping",
            prompt=prompt,
        )

        # 3. 解析 LLM 返回的 JSON
        raw = resp.content.strip()
        # 兼容 LLM 可能输出 ```json ... ``` 包裹
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        mapping: dict = json.loads(raw.strip())

        # 4. 验证并规范化：仅保留 mappable_fields 中存在的列，且值必须是列表
        result: dict[str, list[str]] = {}
        for col_name, _ in KEYWORD_FIELDS:
            matched = mapping.get(col_name, [])
            if not isinstance(matched, list):
                matched = [str(matched)] if matched else []
            # 只保留实际存在于数据中的属性键
            matched = [k for k in matched if k in key_samples]
            result[col_name] = matched

        logger.info(
            "keyword_mapping_llm_done",
            attr_keys=len(key_samples),
            mapped_cols=sum(1 for v in result.values() if v),
        )
        return result

    except Exception as e:
        logger.warning("keyword_mapping_llm_failed", error=str(e))
        return {kf[0]: [] for kf in KEYWORD_FIELDS}


def _apply_keyword_mapping(attrs: dict, keyword_mapping: dict[str, list[str]]) -> dict[str, str]:
    """
    给定单行 SKU 的 attributes 和 LLM 生成的 keyword_mapping，
    提取每个关键词列对应的值。
    """
    result: dict[str, str] = {}
    for col_name, _ in KEYWORD_FIELDS:
        candidates = keyword_mapping.get(col_name, [])
        value = ""
        for key in candidates:
            v = attrs.get(key)
            if v is not None and str(v).strip():
                value = str(v).strip()
                break
        result[col_name] = value
    return result


# ─────────────────────── 主类 ───────────────────────

class ExcelExporter:
    def __init__(self, job_data_dir: str) -> None:
        self._job_data_dir = Path(job_data_dir)

    async def load_job_data(self, db: AsyncSession, job_id: UUID) -> list[ExportRow]:
        """查询 SKU + 绑定图片（每 SKU 可多图），构建导出行列表。"""
        from pdf_sku.common.models import SKU, SKUImageBinding, Image, PDFJob

        # 1. 所有非 superseded 的 SKU，按页码 + 插入顺序排序
        skus = (await db.execute(
            select(SKU)
            .where(SKU.job_id == job_id, SKU.superseded == False)
            .order_by(SKU.page_number, SKU.id)
        )).scalars().all()

        if not skus:
            return []

        sku_ids = [s.sku_id for s in skus]

        # 2. 每个 SKU 的所有有效图片绑定（不限 rank），按置信度降序
        bindings = (await db.execute(
            select(SKUImageBinding)
            .where(
                SKUImageBinding.job_id == job_id,
                SKUImageBinding.sku_id.in_(sku_ids),
                SKUImageBinding.is_latest == True,
                SKUImageBinding.image_id.isnot(None),
            )
            .order_by(
                SKUImageBinding.sku_id,
                SKUImageBinding.binding_confidence.desc(),
                SKUImageBinding.image_id,
            )
        )).scalars().all()

        # 3. 按 SKU 分组，保留有序去重的 image_id 列表
        from collections import defaultdict
        sku_image_ids: dict[str, list[str]] = defaultdict(list)
        for b in bindings:
            if b.image_id and b.image_id not in sku_image_ids[b.sku_id]:
                sku_image_ids[b.sku_id].append(b.image_id)

        # 4. 批量查询图片元数据
        all_image_ids = list({iid for ids in sku_image_ids.values() for iid in ids})
        images: dict[str, object] = {}
        if all_image_ids:
            img_rows = (await db.execute(
                select(Image)
                .where(Image.job_id == job_id, Image.image_id.in_(all_image_ids))
            )).scalars().all()
            images = {img.image_id: img for img in img_rows}

        # 5. 读取图片文件，构建导出行
        job_dir = self._job_data_dir / str(job_id)

        # 5a. 查询 PDF 原始文件名（用于"来源"列）
        source_filename = ""
        try:
            pdf_job = (await db.execute(
                select(PDFJob).where(PDFJob.job_id == job_id)
            )).scalar_one_or_none()
            if pdf_job:
                source_filename = pdf_job.source_file or ""
        except Exception as e:
            logger.warning("excel_source_filename_failed", error=str(e))

        rows: list[ExportRow] = []

        for sku in skus:
            image_ids = sku_image_ids.get(sku.sku_id, [])
            image_bytes_list: list[bytes] = []
            for image_id in image_ids:
                img = images.get(image_id)
                if img:
                    img_path = job_dir / img.extracted_path
                    try:
                        image_bytes_list.append(img_path.read_bytes())
                    except Exception as e:
                        logger.warning(
                            "excel_export_image_read_failed",
                            image_id=image_id, path=str(img_path), error=str(e),
                        )

            rows.append(ExportRow(
                page_number=sku.page_number,
                sku_id=sku.sku_id,
                attributes=dict(sku.attributes or {}),
                images=image_bytes_list,
                image_ids=image_ids,
                source_text=source_filename,
            ))

        logger.info("excel_export_rows_loaded", job_id=str(job_id), count=len(rows))
        return rows

    def build_full_excel(self, rows: list[ExportRow]) -> io.BytesIO:
        """
        File 1: 商品图片1 | 商品图片2 | ... | 页码 | SKU ID | 固定属性列 | 动态属性列
        多图支持: 每张子图占一列，最大列数 = max(len(row.images))。
        """
        import openpyxl
        from openpyxl.styles import Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "全量导出"

        # 确定最多图片数
        n_img_cols = max((len(row.images) for row in rows), default=1)
        n_img_cols = max(n_img_cols, 1)

        # 图片列表头
        if n_img_cols == 1:
            img_headers = ["商品图片"]
        else:
            img_headers = [f"商品图片{i + 1}" for i in range(n_img_cols)]

        # 收集所有属性键，按频率降序
        key_freq: dict[str, int] = {}
        for row in rows:
            for k in row.attributes:
                key_freq[k] = key_freq.get(k, 0) + 1
        all_keys_by_freq = sorted(key_freq, key=lambda k: -key_freq[k])

        # 固定列定义
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
            img_headers
            + ["页码", "SKU ID"]
            + [col[0] for col in fixed_cols]
            + extra_keys
        )
        _apply_header_style(ws, headers, n_img_cols=n_img_cols)

        # 数据行
        for row_idx, row in enumerate(rows, 2):
            attrs = row.attributes

            # 文字列（图片列之后）
            text_data: list = [
                row.page_number,
                row.sku_id,
            ]
            for _, candidates in fixed_cols:
                text_data.append(_get_field_value(attrs, candidates))
            for k in extra_keys:
                v = attrs.get(k)
                text_data.append(str(v) if v is not None else "")

            # 写文字列（从第 n_img_cols+1 列开始）
            for col_offset, val in enumerate(text_data):
                ws.cell(
                    row=row_idx,
                    column=n_img_cols + 1 + col_offset,
                    value=val,
                ).alignment = Alignment(vertical="center", wrap_text=True)

            # 嵌入图片（每张占一列）
            has_image = False
            for img_idx, img_bytes in enumerate(row.images[:n_img_cols]):
                if img_bytes:
                    _embed_image(ws, img_bytes, row_idx, col=img_idx + 1, max_px=60)
                    has_image = True

            ws.row_dimensions[row_idx].height = 60 if has_image else 15

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    async def build_keywords_excel(
        self,
        rows: list[ExportRow],
        llm_service=None,
    ) -> io.BytesIO:
        """
        关键词导出 Excel（平台导入格式）:
          列: 商品图片 | 规格图片 | 商品名称/描述 | 售价 | 货号 | 商品ID | 标签 |
              来源(仅自己可见) | 商品简称 | 商品规格 | 颜色 | 规格编码 | 批发价 |
              打包价 | 代发价 | 拿货价(仅自己可见) | 活动类型 | 活动价 | 库存 |
              重量(kg) | 备注(公开) | 自动下架时间
          多图: 同一 SKU 的多张图片各展开为独立行，其余列数据重复。
        """
        import openpyxl
        from openpyxl.styles import Alignment

        # ── 决定映射策略 ──
        keyword_mapping: dict[str, list[str]] | None = None
        if llm_service is not None and rows:
            keyword_mapping = await build_keyword_mapping_via_llm(rows, llm_service)
            logger.info("keywords_excel_using_llm_mapping")
        else:
            logger.info("keywords_excel_using_fallback_mapping")

        # 确定最多图片数（决定"商品图片"重复列数）
        n_img_cols = max((len(row.images) for row in rows), default=1)
        n_img_cols = max(n_img_cols, 1)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "关键词导出"

        # N 张图片 → N 个同名"商品图片"列 + 21 个关键词列
        headers = ["商品图片"] * n_img_cols + [kf[0] for kf in KEYWORD_FIELDS]
        _apply_header_style(ws, headers, n_img_cols=n_img_cols)

        # 备用候选键（fallback）
        _FALLBACK_CANDIDATES: dict[str, list[str]] = {
            '售价':          ['unit_price', 'price', 'retail_price', '单价', '售价'],
            '商品规格':      ['size', 'spec', 'specification', '规格', '尺寸'],
            '颜色':          ['color', 'colour', '颜色', '色号'],
            '批发价':        ['wholesale_price', '批发价', '批发'],
            '打包价':        ['package_price', '打包价', '打包'],
            '代发价':        ['dropship_price', '代发价', '代发'],
            '活动价':        ['promotion_price', 'activity_price', '活动价', '促销价'],
            '库存':          ['stock', 'inventory', '库存', '数量'],
            '重量(kg)':      ['weight', '重量', 'weight_kg', '毛重'],
            '自动下架时间':  ['auto_offline_time', '下架时间', 'offline_time'],
        }

        for row_idx, row in enumerate(rows, 2):
            attrs = row.attributes

            # 商品名称/描述 = 型号 + 规格
            model = _get_field_value(attrs, ['model_number', 'model', '型号'])
            size  = _get_field_value(attrs, ['size', 'spec', 'specification', '规格', '尺寸'])
            product_name_val = " ".join(p for p in [model, size] if p)

            # 构建每个关键词列的值（固定顺序，对应 KEYWORD_FIELDS）
            kw_data: list[str] = []
            for col_name, _ in KEYWORD_FIELDS:
                if col_name in _EMPTY_KW_COLS:
                    kw_data.append("")
                elif col_name == _SOURCE_COL:
                    kw_data.append(row.source_text)
                elif col_name == _NAME_COL:
                    kw_data.append(product_name_val)
                elif col_name == _MODEL_COL:
                    kw_data.append(model)
                elif keyword_mapping is not None:
                    candidates = keyword_mapping.get(col_name, [])
                    value = ""
                    for key in candidates:
                        v = attrs.get(key)
                        if v is not None and str(v).strip():
                            value = str(v).strip()
                            break
                    kw_data.append(value)
                else:
                    candidates = _FALLBACK_CANDIDATES.get(col_name, [])
                    kw_data.append(_get_field_value(attrs, candidates))

            # 写关键词列（从第 n_img_cols+1 列开始）
            for col_offset, val in enumerate(kw_data):
                ws.cell(
                    row=row_idx,
                    column=n_img_cols + 1 + col_offset,
                    value=val,
                ).alignment = Alignment(vertical="center", wrap_text=True)

            # 嵌入图片（每张各占一列，列名均为"商品图片"）
            has_image = False
            for img_idx, img_bytes in enumerate(row.images[:n_img_cols]):
                if img_bytes:
                    _embed_image(ws, img_bytes, row_idx, col=img_idx + 1, max_px=60)
                    has_image = True

            ws.row_dimensions[row_idx].height = 60 if has_image else 15

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
