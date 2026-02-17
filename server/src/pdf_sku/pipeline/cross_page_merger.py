"""
跨页表格检测与合并。对齐: Pipeline 详设 §5.2 Phase 4

检测当前页是否是前页表格的续表，如果是则合并。
"""
from __future__ import annotations
from dataclasses import dataclass
from pdf_sku.pipeline.ir import ParsedPageIR, TableData
import structlog

logger = structlog.get_logger()

CONTINUATION_KEYWORDS = {"续", "cont", "continued", "(续)", "..."}


@dataclass
class TableContinuation:
    source_page: int = 0
    source_tables: list[TableData] = None

    def __post_init__(self):
        if self.source_tables is None:
            self.source_tables = []


class CrossPageMerger:
    """跨页表格检测器。"""

    def __init__(self):
        self._page_cache: dict[str, dict[int, ParsedPageIR]] = {}  # job_id → {page_no → IR}

    def cache_page(self, job_id: str, page_no: int, raw: ParsedPageIR) -> None:
        """缓存已处理页面的 IR。"""
        self._page_cache.setdefault(job_id, {})[page_no] = raw

    def find_continuation(
        self, job_id: str, current_page: int, raw: ParsedPageIR
    ) -> TableContinuation | None:
        """
        检测当前页是否是续表。

        判断条件:
        1. 前一页有表格
        2. 当前页首行包含续表关键词 或 列数与前页表格一致
        """
        prev_page = current_page - 1
        cached = self._page_cache.get(job_id, {}).get(prev_page)
        if not cached or not cached.tables:
            return None

        if not raw.tables:
            return None

        prev_table = cached.tables[-1]  # 前页最后一个表格
        curr_table = raw.tables[0]      # 当前页第一个表格

        # 条件1: 续表关键词
        first_text = raw.raw_text[:100].lower()
        if any(kw in first_text for kw in CONTINUATION_KEYWORDS):
            return TableContinuation(source_page=prev_page, source_tables=[prev_table])

        # 条件2: 列数匹配
        if (prev_table.column_count > 0 and
            curr_table.column_count == prev_table.column_count):
            return TableContinuation(source_page=prev_page, source_tables=[prev_table])

        return None

    @staticmethod
    def merge(source_tables: list[TableData], current_tables: list[TableData]) -> list[TableData]:
        """合并续表。"""
        if not source_tables or not current_tables:
            return current_tables

        merged = list(current_tables)
        if merged:
            src = source_tables[-1]
            merged[0] = TableData(
                rows=src.rows + merged[0].rows,
                bbox=merged[0].bbox,
                header_row=src.header_row or merged[0].header_row,
                column_count=max(src.column_count, merged[0].column_count),
                is_continuation=True,
            )
        return merged

    def clear_job(self, job_id: str) -> None:
        self._page_cache.pop(job_id, None)
