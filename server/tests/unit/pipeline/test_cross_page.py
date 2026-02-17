"""CrossPageMerger 测试。"""
from pdf_sku.pipeline.ir import ParsedPageIR, TableData
from pdf_sku.pipeline.cross_page_merger import CrossPageMerger


def test_no_continuation():
    m = CrossPageMerger()
    raw = ParsedPageIR(page_no=2, tables=[TableData(rows=[["a"]], column_count=1)])
    result = m.find_continuation("job1", 2, raw)
    assert result is None  # No cached previous page


def test_continuation_by_column_count():
    m = CrossPageMerger()
    prev = ParsedPageIR(
        page_no=1,
        tables=[TableData(rows=[["h1", "h2"], ["a", "b"]], column_count=2, header_row=["h1", "h2"])],
    )
    m.cache_page("job1", 1, prev)

    curr = ParsedPageIR(
        page_no=2,
        tables=[TableData(rows=[["c", "d"]], column_count=2)],
    )
    result = m.find_continuation("job1", 2, curr)
    assert result is not None
    assert result.source_page == 1


def test_merge_tables():
    m = CrossPageMerger()
    source = [TableData(rows=[["h1", "h2"], ["a", "b"]], column_count=2, header_row=["h1", "h2"])]
    current = [TableData(rows=[["c", "d"]], column_count=2)]

    merged = m.merge(source, current)
    assert len(merged) == 1
    assert len(merged[0].rows) == 3  # 2 + 1


def test_clear_job():
    m = CrossPageMerger()
    m.cache_page("job1", 1, ParsedPageIR(page_no=1))
    m.clear_job("job1")
    assert "job1" not in m._page_cache
