"""table-pdf 预处理与续页表头继承。"""
from __future__ import annotations

import hashlib
import re
import statistics
from collections import defaultdict
from typing import Any

from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
from pdf_sku.pipeline.ir import ParsedPageIR, TextBlock

from .models import TableRowRecord, TableSchema

_HEADER_ALIASES: dict[str, list[str]] = {
    "product_name": ["商品名称/描述", "*商品名称/描述", "商品名称", "产品名称", "名称", "品名", "商品描述", "product name", "description", "name"],
    "price": ["售价", "价格", "单价", "price"],
    "model_number": ["货号", "型号", "编号", "model", "model number", "sku"],
    "product_id": ["商品ID", "product id"],
    "tag": ["标签", "tag"],
    "source": ["来源(仅自己可见)", "来源", "source"],
    "short_name": ["商品简称", "short name"],
    "specs": ["商品规格", "规格", "尺寸", "spec", "specs", "size"],
    "color": ["颜色", "colour", "color"],
    "spec_code": ["规格编码", "spec code"],
    "wholesale_price": ["批发价", "wholesale price"],
    "pack_price": ["打包价", "pack price"],
    "dropship_price": ["代发价", "dropship price"],
    "purchase_price": ["拿货价(仅自己可见)", "拿货价", "purchase price"],
    "campaign_type": ["活动类型", "campaign type"],
    "campaign_price": ["活动价", "campaign price"],
    "stock": ["库存", "stock"],
    "weight_kg": ["重量(kg)", "重量", "weight(kg)", "weight"],
    "remark": ["备注(公开)", "备注", "材质说明", "材质", "remark", "material"],
    "auto_unpublish_time": ["自动下架时间", "auto unpublish time"],
}

_FIELD_ORDER = [
    "product_name",
    "price",
    "model_number",
    "product_id",
    "tag",
    "source",
    "short_name",
    "specs",
    "color",
    "spec_code",
    "wholesale_price",
    "pack_price",
    "dropship_price",
    "purchase_price",
    "campaign_type",
    "campaign_price",
    "stock",
    "weight_kg",
    "remark",
    "auto_unpublish_time",
]

_CANONICAL_HEADER_LOOKUP = {
    re.sub(r"[\s\u3000]+", "", alias).replace("*", "").replace("（", "(").replace("）", ")").lower(): key
    for key, aliases in _HEADER_ALIASES.items()
    for alias in aliases
}
_parser = ResponseParser()
_ROW_SERIAL_RE = re.compile(r"^\d{1,3}$")


def _canonicalize(text: str) -> str:
    return re.sub(r"[\s\u3000]+", "", (text or "")).replace("*", "").replace("（", "(").replace("）", ")").lower()


def normalize_header(text: str) -> str:
    return _CANONICAL_HEADER_LOOKUP.get(_canonicalize(text), "")


def _page_width(raw: ParsedPageIR) -> float:
    width = float(raw.metadata.page_width or 0)
    if width > 0:
        return width
    if raw.text_blocks:
        return max(block.bbox[2] for block in raw.text_blocks)
    return 1000.0


def _pick_header_row(raw: ParsedPageIR) -> list[str]:
    if not raw.tables:
        return []
    table = max(raw.tables, key=lambda item: (item.column_count, len(item.rows)))
    if table.header_row:
        return [str(cell or "").strip() for cell in table.header_row]
    if table.rows:
        return [str(cell or "").strip() for cell in table.rows[0]]
    return []


def _pick_header_row_from_text_blocks(raw: ParsedPageIR) -> list[str]:
    if not raw.text_blocks:
        return []
    for row_blocks in _group_blocks_by_row(raw.text_blocks):
        ordered = [block.content.strip() for block in sorted(row_blocks, key=lambda block: block.bbox[0]) if block.content.strip()]
        if len(ordered) < 2:
            continue
        normalized = [normalize_header(cell) for cell in ordered]
        if sum(bool(cell) for cell in normalized) >= 2:
            return ordered
    return []


def _raw_lines(raw_text: str) -> list[str]:
    return [line.strip() for line in (raw_text or "").splitlines() if line.strip()]


def _block_text(block: TextBlock) -> str:
    return (block.content or "").strip()


def _block_center_x(block: TextBlock) -> float:
    return (block.bbox[0] + block.bbox[2]) / 2


def _block_center_y(block: TextBlock) -> float:
    return (block.bbox[1] + block.bbox[3]) / 2


def _serialize_table_text(raw: ParsedPageIR) -> list[str]:
    if raw.text_blocks:
        ordered_blocks = sorted(raw.text_blocks, key=lambda block: (block.bbox[1], block.bbox[0]))
        lines = [block.content.strip() for block in ordered_blocks if block.content.strip()]
        if lines:
            return lines[:80]
    return _raw_lines(raw.raw_text)[:80]


def _pick_header_row_from_raw_text(raw: ParsedPageIR) -> list[str]:
    lines = _raw_lines(raw.raw_text)
    if len(lines) < 2:
        return []

    headers: list[str] = []
    for line in lines[:16]:
        if normalize_header(line):
            headers.append(line)
            continue
        if headers:
            break
    if sum(bool(normalize_header(header)) for header in headers) >= 2:
        return headers
    return []


def _infer_column_centers(raw: ParsedPageIR, headers: list[str]) -> list[float]:
    if not headers:
        return []

    centers: list[float] = []
    for index, header in enumerate(headers):
        header_key = _canonicalize(header)
        matches = [
            (block.bbox[0] + block.bbox[2]) / 2
            for block in raw.text_blocks
            if _canonicalize(block.content) and (
                header_key in _canonicalize(block.content)
                or _canonicalize(block.content) in header_key
            )
        ]
        if matches:
            centers.append(sum(matches) / len(matches))
        else:
            centers.append(-1.0)

    if any(center < 0 for center in centers) or any(
        centers[i] >= centers[i + 1] for i in range(len(centers) - 1) if centers[i] >= 0 and centers[i + 1] >= 0
    ):
        width = _page_width(raw)
        step = width / max(1, len(headers))
        centers = [step * (index + 0.5) for index in range(len(headers))]
    return centers


def build_table_schema(raw: ParsedPageIR, source_page: int = 1) -> TableSchema | None:
    """从首页结构化表格构建继承 schema。"""
    headers = _pick_header_row(raw) or _pick_header_row_from_text_blocks(raw) or _pick_header_row_from_raw_text(raw)
    if not headers:
        return None

    normalized_headers = [normalize_header(header) for header in headers]
    if sum(bool(header) for header in normalized_headers) < 2:
        return None

    schema_id = hashlib.md5("|".join(normalized_headers).encode("utf-8")).hexdigest()[:12]
    return TableSchema(
        header_source_page=source_page,
        raw_headers=headers,
        normalized_headers=normalized_headers,
        column_centers=_infer_column_centers(raw, headers),
        table_schema_id=schema_id,
    )


def _row_is_header_like(cells: list[str], schema: TableSchema) -> bool:
    matched = 0
    for cell, normalized in zip(cells, schema.normalized_headers, strict=False):
        if not normalized:
            continue
        if normalize_header(cell) == normalized:
            matched += 1
    return matched >= max(2, min(3, sum(bool(header) for header in schema.normalized_headers)))


def _cells_to_values(cells: list[str], schema: TableSchema) -> dict[str, str]:
    values: dict[str, str] = {}
    for index, normalized in enumerate(schema.normalized_headers):
        if not normalized or index >= len(cells):
            continue
        value = str(cells[index] or "").strip()
        if value:
            values[normalized] = value
    return values


def _extract_rows_from_tables(raw: ParsedPageIR, schema: TableSchema) -> list[TableRowRecord]:
    records: list[TableRowRecord] = []
    row_index = 0
    expected_columns = len(schema.normalized_headers)

    for table in raw.tables:
        rows = table.rows or []
        if not rows:
            continue
        if table.column_count and abs(table.column_count - expected_columns) > 1:
            continue
        for row in rows:
            cells = [str(cell or "").strip() for cell in row]
            if not any(cells):
                continue
            if _row_is_header_like(cells, schema):
                continue
            values = _cells_to_values(cells, schema)
            if not values:
                continue
            row_index += 1
            records.append(
                TableRowRecord(
                    row_index=row_index,
                    values=values,
                    bbox=table.bbox or (0, 0, 0, 0),
                    source="table_rows",
                )
            )
    return records


def _group_blocks_by_row(text_blocks: list[TextBlock]) -> list[list[TextBlock]]:
    if not text_blocks:
        return []

    ordered = sorted(text_blocks, key=lambda block: ((block.bbox[1] + block.bbox[3]) / 2, block.bbox[0]))
    heights = [max(1.0, block.bbox[3] - block.bbox[1]) for block in ordered]
    threshold = max(8.0, statistics.median(heights) * 0.8) if heights else 8.0

    rows: list[list[TextBlock]] = [[ordered[0]]]
    prev_center = (ordered[0].bbox[1] + ordered[0].bbox[3]) / 2
    for block in ordered[1:]:
        center_y = (block.bbox[1] + block.bbox[3]) / 2
        if abs(center_y - prev_center) > threshold:
            rows.append([block])
        else:
            rows[-1].append(block)
        prev_center = center_y
    return rows


def _extract_rows_from_text_blocks(raw: ParsedPageIR, schema: TableSchema) -> list[TableRowRecord]:
    if not raw.text_blocks or not schema.column_centers:
        return []
    if len(raw.text_blocks) == 1 and "\n" in (raw.text_blocks[0].content or ""):
        return []

    records: list[TableRowRecord] = []
    row_index = 0
    for row_blocks in _group_blocks_by_row(raw.text_blocks):
        if not row_blocks:
            continue
        row_blocks = sorted(row_blocks, key=lambda block: block.bbox[0])
        cell_buckets: dict[int, list[TextBlock]] = defaultdict(list)
        for block in row_blocks:
            center_x = (block.bbox[0] + block.bbox[2]) / 2
            target_index = min(
                range(len(schema.column_centers)),
                key=lambda index: abs(schema.column_centers[index] - center_x),
            )
            cell_buckets[target_index].append(block)

        cells = []
        for column_index in range(len(schema.normalized_headers)):
            blocks = sorted(cell_buckets.get(column_index, []), key=lambda block: block.bbox[0])
            cells.append(" ".join(block.content.strip() for block in blocks if block.content.strip()))

        if not any(cells):
            continue
        if _row_is_header_like(cells, schema):
            continue

        values = _cells_to_values(cells, schema)
        if not values:
            continue

        row_index += 1
        bbox = (
            min(block.bbox[0] for block in row_blocks),
            min(block.bbox[1] for block in row_blocks),
            max(block.bbox[2] for block in row_blocks),
            max(block.bbox[3] for block in row_blocks),
        )
        records.append(
            TableRowRecord(
                row_index=row_index,
                values=values,
                bbox=bbox,
                source="text_blocks",
            )
        )
    return records


def _infer_column_centers_from_precise_lines(
    raw: ParsedPageIR,
    schema: TableSchema,
    text_lines: list[TextBlock],
) -> list[float]:
    centers: list[float] = []
    for index, (header, normalized) in enumerate(zip(schema.raw_headers, schema.normalized_headers, strict=False)):
        if not normalized:
            centers.append(
                schema.column_centers[index] if index < len(schema.column_centers) else -1.0
            )
            continue
        header_key = _canonicalize(header) or normalized
        matches = [
            _block_center_x(block)
            for block in text_lines
            if _canonicalize(block.content) and (
                normalize_header(block.content) == normalized
                or header_key in _canonicalize(block.content)
                or _canonicalize(block.content) in header_key
            )
        ]
        if matches:
            centers.append(sum(matches) / len(matches))
        elif index < len(schema.column_centers):
            centers.append(schema.column_centers[index])
        else:
            centers.append(-1.0)

    if any(center < 0 for center in centers) or any(
        centers[i] >= centers[i + 1]
        for i in range(len(centers) - 1)
        if centers[i] >= 0 and centers[i + 1] >= 0
    ):
        return _infer_column_centers(raw, schema.raw_headers)
    return centers


def _extract_rows_from_precise_lines(
    raw: ParsedPageIR,
    schema: TableSchema,
    text_lines: list[TextBlock],
) -> list[TableRowRecord]:
    if not text_lines:
        return []

    ordered = sorted(text_lines, key=lambda block: (_block_center_y(block), block.bbox[0]))
    header_bottom = max(
        (block.bbox[3] for block in ordered if normalize_header(block.content)),
        default=0.0,
    )
    page_width = max(1.0, _page_width(raw))
    row_anchors = [
        block
        for block in ordered
        if _ROW_SERIAL_RE.fullmatch(_block_text(block))
        and block.bbox[0] <= page_width * 0.08
        and _block_center_y(block) > header_bottom + 8
    ]
    if len(row_anchors) < 2:
        return []

    column_centers = _infer_column_centers_from_precise_lines(raw, schema, ordered)
    anchor_centers = [_block_center_y(block) for block in row_anchors]
    records: list[TableRowRecord] = []

    for index, anchor in enumerate(row_anchors):
        current_center = anchor_centers[index]
        if index == 0:
            next_center = anchor_centers[index + 1]
            start_y = max(header_bottom + 4.0, current_center - (next_center - current_center) * 0.55)
        else:
            start_y = (anchor_centers[index - 1] + current_center) / 2

        if index == len(row_anchors) - 1:
            prev_center = anchor_centers[index - 1]
            start_y = max(start_y, current_center - (current_center - prev_center) * 0.5)
            end_y = min(raw.metadata.page_height or current_center + 40.0, current_center + (current_center - prev_center) * 0.8)
        else:
            end_y = (current_center + anchor_centers[index + 1]) / 2

        row_blocks = [
            block
            for block in ordered
            if start_y <= _block_center_y(block) < end_y
            and not normalize_header(block.content)
        ]
        if not row_blocks:
            continue

        cell_buckets: dict[int, list[TextBlock]] = defaultdict(list)
        for block in row_blocks:
            text = _block_text(block)
            if not text:
                continue
            if _ROW_SERIAL_RE.fullmatch(text) and block.bbox[0] <= page_width * 0.08:
                continue
            target_index = min(
                range(len(column_centers)),
                key=lambda column_index: abs(column_centers[column_index] - _block_center_x(block)),
            )
            cell_buckets[target_index].append(block)

        cells: list[str] = []
        for column_index in range(len(schema.normalized_headers)):
            blocks = sorted(
                cell_buckets.get(column_index, []),
                key=lambda block: (_block_center_y(block), block.bbox[0]),
            )
            parts = [_block_text(block) for block in blocks if _block_text(block)]
            cells.append(" ".join(parts))

        if not any(cells):
            continue

        values = _cells_to_values(cells, schema)
        if not values:
            continue

        records.append(
            TableRowRecord(
                row_index=int(_block_text(anchor)),
                values=values,
                bbox=(
                    min(block.bbox[0] for block in row_blocks),
                    min(block.bbox[1] for block in row_blocks),
                    max(block.bbox[2] for block in row_blocks),
                    max(block.bbox[3] for block in row_blocks),
                ),
                source="precise_text_lines",
            )
        )
    return records


def _extract_rows_from_raw_text(raw: ParsedPageIR, schema: TableSchema) -> list[TableRowRecord]:
    lines = _raw_lines(raw.raw_text)
    if not lines:
        return []

    records: list[TableRowRecord] = []
    expected_columns = len(schema.normalized_headers)
    if expected_columns <= 0:
        return records

    if len(lines) >= expected_columns and _row_is_header_like(lines[:expected_columns], schema):
        lines = lines[expected_columns:]

    row_index = 0
    for start in range(0, len(lines), expected_columns):
        cells = lines[start:start + expected_columns]
        if len(cells) < expected_columns:
            continue
        values = _cells_to_values(cells, schema)
        if not values:
            continue
        row_index += 1
        records.append(
            TableRowRecord(
                row_index=row_index,
                values=values,
                bbox=(0, 0, raw.metadata.page_width, raw.metadata.page_height),
                source="raw_text_lines",
            )
        )
    return records


def extract_table_rows(
    raw: ParsedPageIR,
    schema: TableSchema,
    *,
    precise_text_lines: list[TextBlock] | None = None,
) -> list[TableRowRecord]:
    """从当前页恢复表格行。优先结构化表格，再退化到文本块聚行。"""
    records = _extract_rows_from_tables(raw, schema)
    if records:
        return records
    records = _extract_rows_from_precise_lines(raw, schema, precise_text_lines or [])
    if records:
        return records
    records = _extract_rows_from_text_blocks(raw, schema)
    if records:
        return records
    return _extract_rows_from_raw_text(raw, schema)


def row_values_to_attributes(values: dict[str, str]) -> dict[str, str]:
    """将表格行字段转换为 SKU attributes。"""
    attributes: dict[str, str] = {"evidence_mode": "text_backed"}

    ordered_values = []
    seen_values: set[str] = set()
    for field in _FIELD_ORDER:
        value = str(values.get(field, "") or "").strip()
        if not value:
            continue
        attributes[field] = value
        if value not in seen_values:
            ordered_values.append(value)
            seen_values.add(value)

    for field, raw_value in values.items():
        if field in attributes:
            continue
        value = str(raw_value or "").strip()
        if not value:
            continue
        attributes[field] = value
        if value not in seen_values:
            ordered_values.append(value)
            seen_values.add(value)

    if ordered_values:
        attributes["raw_attribute_text"] = " ".join(ordered_values)
        attributes["product_description"] = attributes["raw_attribute_text"]
    if not attributes.get("product_name") and attributes.get("raw_attribute_text"):
        attributes["product_name"] = attributes["raw_attribute_text"]
    return attributes


class TablePreprocessor:
    """V2 表格预处理器。"""

    def __init__(self, llm_service=None) -> None:
        self._llm = llm_service

    def build_schema(self, raw: ParsedPageIR, source_page: int = 1) -> TableSchema | None:
        return build_table_schema(raw, source_page=source_page)

    def extract_rows(
        self,
        raw: ParsedPageIR,
        schema: TableSchema,
        *,
        precise_text_lines: list[TextBlock] | None = None,
    ) -> list[TableRowRecord]:
        return extract_table_rows(raw, schema, precise_text_lines=precise_text_lines)

    def row_to_attributes(self, row: TableRowRecord) -> dict[str, str]:
        return row_values_to_attributes(row.values)

    async def fallback_rows_with_llm(
        self,
        raw: ParsedPageIR,
        schema: TableSchema,
        *,
        screenshot: bytes | None = None,
    ) -> list[TableRowRecord]:
        if not self._llm or not screenshot:
            return []
        return await self._fallback_rows_from_llm(raw, schema, screenshot=screenshot)

    async def extract_rows_with_vlm_fallback(
        self,
        raw: ParsedPageIR,
        schema: TableSchema,
        *,
        screenshot: bytes | None = None,
    ) -> list[TableRowRecord]:
        records = extract_table_rows(raw, schema)
        if records or not self._llm or not screenshot:
            return records

        payload = await self._fallback_rows_from_llm(raw, schema, screenshot=screenshot)
        return payload or records

    async def _fallback_rows_from_llm(
        self,
        raw: ParsedPageIR,
        schema: TableSchema,
        *,
        screenshot: bytes,
    ) -> list[TableRowRecord]:
        prompt = self._table_fallback_prompt(raw, schema)
        try:
            response = await self._llm._call_llm(
                operation="table_fallback_v2",
                prompt=prompt,
                images=[screenshot],
            )
            parsed = _parser.parse(response.text, expected_type="object")
            if not parsed.success or not isinstance(parsed.data, dict):
                return []
            return self._rows_from_llm_payload(parsed.data, raw, schema)
        except Exception:
            return []

    @staticmethod
    def _table_fallback_prompt(raw: ParsedPageIR, schema: TableSchema) -> str:
        headers_json = schema.raw_headers or schema.normalized_headers
        text_lines = _serialize_table_text(raw)
        return """你现在处理的是一个表格页，不是普通商品宣传页。

已知条件：
1. 这页是长表格的一部分。
2. 首页表头已经确定，当前页沿用这些表头。
3. 你的任务是把当前页的每一行数据对齐到给定表头，不要新增字段名。

要求：
1. 只能使用给定的表头。
2. 不允许猜测新的列含义。
3. 若某个单元格无法确定，保留空值或原始文本。
4. 只输出结构化 JSON。

已知表头：
{headers}

页面文本：
{lines}

返回 ONLY JSON：
{{
  "headers": {headers},
  "rows": [
    {{
      "{first_header}": "value"
    }}
  ]
}}""".format(
            headers=headers_json,
            lines=text_lines,
            first_header=headers_json[0] if headers_json else "列1",
        )

    @staticmethod
    def _rows_from_llm_payload(
        payload: dict[str, Any],
        raw: ParsedPageIR,
        schema: TableSchema,
    ) -> list[TableRowRecord]:
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            return []

        records: list[TableRowRecord] = []
        bbox = (0, 0, raw.metadata.page_width, raw.metadata.page_height)
        for index, item in enumerate(rows, start=1):
            if not isinstance(item, dict):
                continue
            values: dict[str, str] = {}
            for raw_header, normalized in zip(schema.raw_headers, schema.normalized_headers, strict=False):
                if not normalized:
                    continue
                candidate = item.get(raw_header)
                if candidate in (None, ""):
                    candidate = item.get(normalized)
                value = str(candidate or "").strip()
                if value:
                    values[normalized] = value
            if not values:
                continue
            records.append(
                TableRowRecord(
                    row_index=index,
                    values=values,
                    bbox=bbox,
                    source="llm_table_fallback",
                )
            )
        return records
