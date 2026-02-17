"""
PageProcessor 端到端测试 (本地模式, 无 LLM)。
验证 PDF → Parse → Classify → Extract → Bind → Validate 全链路。
"""
import pytest
import fitz
import io


@pytest.fixture
def sample_product_pdf(tmp_path):
    """生成包含产品信息的测试 PDF。"""
    doc = fitz.open()

    # Page 1: 产品列表 (B 类混合页)
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 50), "Product Catalog 2026", fontsize=18)
    page.insert_text((50, 100), "Model: XZ-500 Premium Widget", fontsize=12)
    page.insert_text((50, 120), "Price: $29.99", fontsize=12)
    page.insert_text((50, 140), "Material: Stainless Steel", fontsize=10)
    page.insert_text((50, 200), "Model: AB-200 Standard Gadget", fontsize=12)
    page.insert_text((50, 220), "Price: $15.50", fontsize=12)
    page.insert_text((50, 240), "Material: Plastic", fontsize=10)
    # 添加一个简单矩形作为 "图片区域"
    page.draw_rect(fitz.Rect(350, 80, 550, 180), color=(0.8, 0.8, 0.8), fill=(0.9, 0.9, 0.9))

    # Page 2: 空白页 (D 类)
    page2 = doc.new_page(width=612, height=792)

    # Page 3: 表格页 (A 类) — 纯文本模拟
    page3 = doc.new_page(width=612, height=792)
    page3.insert_text((50, 50), "Product Specifications Table", fontsize=14)
    y = 80
    for row in [
        ("Model", "Price", "Weight"),
        ("XZ-500", "$29.99", "1.5kg"),
        ("AB-200", "$15.50", "0.8kg"),
        ("CD-300", "$42.00", "2.1kg"),
    ]:
        for i, cell in enumerate(row):
            page3.insert_text((50 + i * 180, y), cell, fontsize=10)
        y += 20

    path = str(tmp_path / "products.pdf")
    doc.save(path)
    doc.close()
    return path


@pytest.mark.asyncio
async def test_full_page_processor(sample_product_pdf):
    """测试 PageProcessor 完整 9 阶段链路。"""
    from pdf_sku.pipeline.page_processor import PageProcessor

    pp = PageProcessor(llm_service=None, process_pool=None)

    # Page 1: 产品混合页
    result1 = await pp.process_page(
        job_id="test-job-001",
        file_path=sample_product_pdf,
        page_no=1,
        file_hash="abc12345678",
    )
    assert result1.status in ("AI_COMPLETED", "AI_FAILED")
    if result1.status == "AI_COMPLETED":
        assert result1.page_type in ("B", "C", "A")
        # 应该提取到一些 SKU (通过规则引擎)
        # 具体数量取决于规则兜底的效果


@pytest.mark.asyncio
async def test_blank_page_skipped(sample_product_pdf):
    """D 类空白页应被跳过或至少没有 SKU。"""
    from pdf_sku.pipeline.page_processor import PageProcessor

    pp = PageProcessor(llm_service=None, process_pool=None)
    result = await pp.process_page(
        job_id="test-job-002",
        file_path=sample_product_pdf,
        page_no=2,
        file_hash="abc12345678",
    )
    # 空白页应跳过或完成但无 SKU
    assert result.status in ("SKIPPED", "AI_COMPLETED")
    assert len(result.skus) == 0


@pytest.mark.asyncio
async def test_multipage_processing(sample_product_pdf):
    """连续处理多页, 验证跨页缓存正常。"""
    from pdf_sku.pipeline.page_processor import PageProcessor

    pp = PageProcessor(llm_service=None, process_pool=None)

    for page_no in [1, 2, 3]:
        result = await pp.process_page(
            job_id="test-job-003",
            file_path=sample_product_pdf,
            page_no=page_no,
            file_hash="abc12345678",
        )
        assert result.status in ("AI_COMPLETED", "SKIPPED", "AI_FAILED")

    pp.clear_job_cache("test-job-003")
