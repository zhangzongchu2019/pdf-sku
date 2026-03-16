"""解析参考 Excel 文件，自适应 22/27 列格式。"""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from .models import GroundTruthSKU, ReferenceDataset

# 参考数据根目录
DEFAULT_DATA_ROOT = Path("/home/zzc/Documents/pdf整理")

# 通过表头名称定位列（不依赖固定列号）
HEADER_MAP = {
    "product_name": ["*商品名称/描述", "商品名称/描述", "商品名称", "产品名称", "名称"],
    "price": ["售价", "*售价", "单价"],
    "model_number": ["货号", "型号"],
    "tag": ["标签"],
    "source": ["来源(仅自己可见)", "来源"],
    "specs": ["商品规格", "规格", "尺寸"],
    "color": ["颜色"],
}

# 非标准格式: 可能表头不在第一行
ALT_HEADER_KEYWORDS = ["商品名称", "产品名称", "货号", "型号", "售价", "单价", "品名"]


def _find_columns(header_row: list[str | None]) -> dict[str, int]:
    """从表头行找到各字段的列索引 (0-based)。"""
    col_map: dict[str, int] = {}
    for field_name, possible_headers in HEADER_MAP.items():
        for col_idx, cell_val in enumerate(header_row):
            if cell_val and any(h in str(cell_val) for h in possible_headers):
                col_map[field_name] = col_idx
                break
    return col_map


def _parse_folder_meta(folder_name: str) -> tuple[str, int, int]:
    """从文件夹名解析: 名称, SKU 数, 耗时分钟。
    格式: "铝合金洽谈桌--17个商品5分钟"
    """
    m = re.match(r"(.+?)--(\d+)个商品(\d+)分钟", folder_name)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3))
    # 无后缀的文件夹
    name = folder_name.rstrip("/")
    return name, 0, 0


def parse_excel(excel_path: Path) -> list[GroundTruthSKU]:
    """解析单个参考 Excel，返回 SKU 列表。"""
    wb = load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return []

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        return []

    # 尝试前5行找表头
    header_row_idx = 0
    col_map: dict[str, int] = {}
    for try_idx in range(min(5, len(rows))):
        candidate = [str(v) if v else None for v in rows[try_idx]]
        candidate_map = _find_columns(candidate)
        # 至少匹配 2 个字段才算找到表头
        if len(candidate_map) >= 2:
            header_row_idx = try_idx
            col_map = candidate_map
            break

    if not col_map:
        return []

    skus: list[GroundTruthSKU] = []
    data_start = header_row_idx + 1
    for row_idx, row in enumerate(rows[data_start:], start=data_start + 1):
        # 跳过全空行
        if not any(row):
            continue

        def _get(field: str) -> str:
            idx = col_map.get(field)
            if idx is None or idx >= len(row):
                return ""
            v = row[idx]
            return str(v).strip() if v else ""

        name = _get("product_name")
        model = _get("model_number")
        tag = _get("tag")
        # 跳过无名称、无货号且无标签的空行
        if not name and not model and not tag:
            continue

        skus.append(GroundTruthSKU(
            row_index=row_idx,
            product_name=name,
            model_number=model,
            price=_get("price"),
            specs=_get("specs"),
            color=_get("color"),
            tag=_get("tag"),
            source=_get("source"),
            raw_row={k: _get(k) for k in HEADER_MAP},
        ))

    return skus


def scan_datasets(data_root: Path | None = None) -> list[ReferenceDataset]:
    """扫描参考数据目录，返回所有 PDF+Excel 配对。"""
    root = data_root or DEFAULT_DATA_ROOT
    if not root.exists():
        return []

    datasets: list[ReferenceDataset] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue

        name, expected_count, minutes = _parse_folder_meta(folder.name)

        # 找 PDF 和 Excel
        pdfs = list(folder.glob("*.pdf")) + list(folder.glob("*.PDF"))
        excels = list(folder.glob("*.xlsx")) + list(folder.glob("*.XLSX"))

        # 排除临时文件
        excels = [e for e in excels if not e.name.startswith("~$")]

        pdf_path = pdfs[0] if pdfs else None
        excel_path = excels[0] if excels else None

        # 排除没有 PDF 的目录
        if not pdf_path:
            continue

        ds = ReferenceDataset(
            name=name,
            folder=folder,
            pdf_path=pdf_path,
            excel_path=excel_path,
            expected_sku_count=expected_count,
            manual_minutes=minutes,
        )
        datasets.append(ds)

    return datasets


def _split_multiline_skus(skus: list[GroundTruthSKU]) -> list[GroundTruthSKU]:
    """拆分多行 product_name 中包含多条 SKU 的情况。

    模式 A (HQ系列): 每 2 行一组 (型号+品名, 尺寸+价格)
      B617-2018 班台
      2000Wx1800Dx750Hmm P4667
      B617-2218 班台
      ...

    模式 B (卡奇尔): 多个 "品类：型号#" 子产品
      大床：3009#
      床头柜：201#
      规格：1500/1800
    """
    result: list[GroundTruthSKU] = []

    # 型号行检测: 以型号开头 (如 B617-2018, H102-3212, HW040, BT-BD711)
    # 支持: 字母+数字 | 字母-字母数字 (如 BT-BD711, BT-NT713)
    model_line_re = re.compile(
        r'^[A-Za-z]{1,5}[-]?[A-Za-z]{0,3}\d{1,5}\s*[-]?\s*\d{0,6}\s*[#*]?\s*[\u4e00-\u9fff]')
    # 子产品检测: "品类：型号#" (型号必须含字母或纯数字+#结尾)
    _attr_prefixes = {"规格", "颜色", "尺寸", "材质", "品牌", "型号", "货号", "价格", "备注",
                      "单人", "双人", "三人", "四人", "单人位", "双人位", "三人位", "四人位",
                      "贵妃位", "贵妃", "脚踏", "台面", "副柜", "主柜", "镜子", "凳子",
                      "抽屉", "搁板", "层板", "柜门", "柜体"}
    sub_product_re = re.compile(
        r'^([\u4e00-\u9fff]{1,6})[：:]\s*([A-Za-z][-A-Za-z0-9#]+|\d{2,6}[#])')

    for sku in skus:
        name = sku.product_name
        if '\n' not in name:
            result.append(sku)
            continue

        lines = [l.strip() for l in name.split('\n') if l.strip()]

        # 模式 B: 检测 "大床：3009#\n床头柜：201#" 格式
        sub_matches = [sub_product_re.match(l) for l in lines]
        # 排除属性行 (规格、颜色等)
        sub_matches = [
            m if m and m.group(1) not in _attr_prefixes else None
            for m in sub_matches
        ]
        sub_count = sum(1 for m in sub_matches if m)
        if sub_count >= 2:
            # 提取共享属性 (规格、颜色等)
            shared_specs = []
            for l in lines:
                if not sub_product_re.match(l):
                    shared_specs.append(l)
            shared_text = ' '.join(shared_specs)

            for m in sub_matches:
                if m:
                    category, model = m.group(1), m.group(2)
                    result.append(GroundTruthSKU(
                        row_index=sku.row_index,
                        product_name=category,
                        model_number=model.rstrip('#*'),
                        price=sku.price,
                        specs=shared_text or sku.specs,
                        color=sku.color,
                        tag=sku.tag,
                        source=sku.source,
                        raw_row=sku.raw_row,
                    ))
            continue

        # 模式 A: 检测交替的 "型号行 + 规格行" 格式
        model_lines = [i for i, l in enumerate(lines) if model_line_re.match(l)]
        if len(model_lines) >= 2:
            for ml_idx in model_lines:
                line = lines[ml_idx]
                # 提取型号和品名
                pm = re.match(r'^([A-Za-z]{1,5}[-]?[A-Za-z]{0,3}\d{1,5}\s*[-]?\s*\d{0,6}\s*[#*]?)\s*([\u4e00-\u9fff]+)', line)
                if pm:
                    model = pm.group(1).replace(' ', '')
                    pname = pm.group(2)
                    # 下一行通常是尺寸+价格
                    spec_line = lines[ml_idx + 1] if ml_idx + 1 < len(lines) and ml_idx + 1 not in model_lines else ""
                    result.append(GroundTruthSKU(
                        row_index=sku.row_index,
                        product_name=pname,
                        model_number=model,
                        price=sku.price,
                        specs=spec_line or sku.specs,
                        color=sku.color,
                        tag=sku.tag,
                        source=sku.source,
                        raw_row=sku.raw_row,
                    ))
            continue

        # 无法拆分，保持原样
        result.append(sku)

    return result


def load_dataset(ds: ReferenceDataset) -> ReferenceDataset:
    """加载数据集的 Excel 内容。"""
    if ds.excel_path and ds.excel_path.exists():
        ds.skus = parse_excel(ds.excel_path)
        ds.skus = _split_multiline_skus(ds.skus)
    return ds
