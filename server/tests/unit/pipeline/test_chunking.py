"""ChunkingStrategy 测试。"""
from pdf_sku.pipeline.chunking import ChunkingStrategy


def test_should_chunk_false():
    cs = ChunkingStrategy()
    assert not cs.should_chunk(50)
    assert not cs.should_chunk(100)


def test_should_chunk_true():
    cs = ChunkingStrategy()
    assert cs.should_chunk(101)


def test_create_chunks():
    cs = ChunkingStrategy()
    chunks = cs.create_chunks(120, blank_pages=[5, 10])
    assert len(chunks) >= 2
    # All pages except blanks are covered
    all_pages = []
    for c in chunks:
        all_pages.extend(c.pages)
    assert 5 not in all_pages
    assert 10 not in all_pages
    assert 1 in all_pages
    assert 120 in all_pages


def test_create_chunks_small():
    cs = ChunkingStrategy()
    chunks = cs.create_chunks(30, [])
    assert len(chunks) == 1
    assert len(chunks[0].pages) == 30
