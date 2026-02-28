"""
跨页表格检测与合并。对齐: Pipeline 详设 §5.2 Phase 4

检测当前页是否是前页表格的续表，如果是则合并。
"""
from __future__ import annotations
import asyncio
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
    """跨页表格检测器（并发安全）。"""

    def __init__(self):
        self._page_cache: dict[str, dict[int, ParsedPageIR]] = {}  # job_id → {page_no → IR}
        self._locks: dict[str, asyncio.Lock] = {}  # per-job lock

    def _get_lock(self, job_id: str) -> asyncio.Lock:
        if job_id not in self._locks:
            self._locks[job_id] = asyncio.Lock()
        return self._locks[job_id]

    async def cache_page(self, job_id: str, page_no: int, raw: ParsedPageIR) -> None:
        """缓存已处理页面的 IR（加锁写入）。"""
        async with self._get_lock(job_id):
            self._page_cache.setdefault(job_id, {})[page_no] = raw

    async def find_continuation(
        self, job_id: str, current_page: int, raw: ParsedPageIR,
        file_path: str | None = None,
    ) -> TableContinuation | None:
        """
        检测当前页是否是续表。

        判断条件:
        1. 前一页有表格
        2. 当前页首行包含续表关键词 或 列数与前页表格一致

        若前页未缓存（并行时可能发生），尝试从 PDF 文件按需加载前页表格；
        仍失败则优雅降级返回 None。
        """
        prev_page = current_page - 1

        # 快速路径: 内存缓存命中
        async with self._get_lock(job_id):
            cached = self._page_cache.get(job_id, {}).get(prev_page)

        # 缓存 miss: 按需从 PDF 提取前页表格（IO 在锁外执行，不阻塞事件循环）
        if cached is None and file_path and prev_page >= 1:
            loop = asyncio.get_event_loop()
            on_demand = await loop.run_in_executor(
                None, CrossPageMerger._load_page_tables_from_file, file_path, prev_page)
            if on_demand and on_demand.tables:
                async with self._get_lock(job_id):
                    job_cache = self._page_cache.setdefault(job_id, {})
                    # 仅在尚未被其他并发任务填充时写入
                    if prev_page not in job_cache:
                        job_cache[prev_page] = on_demand
                    cached = job_cache[prev_page]
                logger.info("cross_page_cache_loaded_on_demand",
                            job_id=job_id, prev_page=prev_page,
                            table_count=len(on_demand.tables))

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
    def _load_page_tables_from_file(file_path: str, page_no: int) -> "ParsedPageIR | None":
        """按需从 PDF 文件同步加载指定页的表格数据。

        仅在跨页续表检测的内存缓存 miss 时调用（通常是单页重处理场景）。
        使用 pdfplumber find_tables() 以获取正确的 bbox。
        """
        try:
            import pdfplumber
            from pdf_sku.pipeline.ir import ParsedPageIR, TableData
            with pdfplumber.open(file_path) as pdf:
                if page_no < 1 or page_no > len(pdf.pages):
                    return None
                page = pdf.pages[page_no - 1]
                tables = []
                for tbl_obj in (page.find_tables() or []):
                    tbl = tbl_obj.extract()
                    if tbl:
                        rows = [[str(c or "") for c in row] for row in tbl]
                        tables.append(TableData(
                            rows=rows,
                            bbox=tbl_obj.bbox,
                            header_row=rows[0] if rows else None,
                            column_count=len(rows[0]) if rows else 0,
                        ))
                return ParsedPageIR(page_no=page_no, tables=tables) if tables else None
        except Exception as exc:
            logger.debug("load_page_tables_failed", page=page_no, error=str(exc))
            return None

    @staticmethod
    def _find_column_header(rows: list[list[str]], column_count: int) -> list[str] | None:
        """从源表格行中找到列标题行。

        策略：从上到下扫描，返回第一个"多列非空"的行
        （非空格子数 >= max(2, column_count // 2)）。
        标题行之前的行通常是页面标题/说明文字，只有 1 个非空格子。
        """
        min_nonempty = max(2, column_count // 2)
        for row in rows:
            nonempty = sum(1 for c in row if c and c.strip())
            if nonempty >= min_nonempty:
                return row
        return None

    @staticmethod
    def merge(source_tables: list[TableData], current_tables: list[TableData]) -> list[TableData]:
        """合并续表。

        只将源表格的列标题行前置到当前页表格，而非全量前置，
        避免把源页的说明行/数据行污染当前页的表头检测。
        """
        if not source_tables or not current_tables:
            return current_tables

        merged = list(current_tables)
        if merged:
            src = source_tables[-1]
            col_count = max(src.column_count, merged[0].column_count)
            header_row = CrossPageMerger._find_column_header(src.rows, col_count)
            orig_flags = merged[0].row_image_flags
            if header_row:
                # 只前置列标题行，当前页数据行保持原样，避免重复提取源页 SKU
                # row_image_flags 也同步前置 True（代表新增的标题行自身有独立列）
                merged[0] = TableData(
                    rows=[header_row] + merged[0].rows,
                    bbox=merged[0].bbox,
                    header_row=header_row,
                    column_count=col_count,
                    is_continuation=True,
                    row_image_flags=[True] + orig_flags if orig_flags else [],
                )
                logger.info("cross_page_merge_header",
                            source_col_count=src.column_count,
                            curr_rows=len(merged[0].rows) - 1,
                            header_preview=str(header_row)[:80])
            else:
                # 找不到明确标题行时，退化为全量前置（原有行为）
                src_flags = [True] * len(src.rows)
                merged[0] = TableData(
                    rows=src.rows + merged[0].rows,
                    bbox=merged[0].bbox,
                    header_row=src.header_row or merged[0].header_row,
                    column_count=col_count,
                    is_continuation=True,
                    row_image_flags=(src_flags + orig_flags) if orig_flags else [],
                )
        return merged

    def clear_job(self, job_id: str) -> None:
        self._page_cache.pop(job_id, None)
        self._locks.pop(job_id, None)
