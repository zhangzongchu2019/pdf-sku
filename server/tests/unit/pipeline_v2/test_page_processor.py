"""pipeline_v2 PageProcessor 测试。"""
from __future__ import annotations

import pytest

from pdf_sku.llm_adapter.client.base import LLMResponse
from pdf_sku.pipeline.catalog_profiler import CatalogProfile
from pdf_sku.pipeline.layout_detector import LayoutRegion
from pdf_sku.pipeline.ir import ImageInfo, PageMetadata, PageResult, ParsedPageIR, SKUResult, TableData, TextBlock
from pdf_sku.pipeline.parser.ocr_engine import OcrBlock
from pdf_sku.pipeline_v2.document_hints import build_document_hints
from pdf_sku.pipeline_v2.models import DocumentHints, EvidenceObject, PageEvidence, RegionProposal
from pdf_sku.pipeline_v2.page_processor import PageProcessor
from pdf_sku.pipeline_v2.page_verifier import PageVerifier
from pdf_sku.pipeline_v2.region_refiner import RegionRefiner
from pdf_sku.settings import settings


class _LegacyStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.cleared: list[str] = []

    async def process_page(self, **kwargs) -> PageResult:
        self.calls.append(kwargs)
        return PageResult(status="AI_COMPLETED", page_type="B", extraction_method="legacy_stub")

    def clear_job_cache(self, job_id: str) -> None:
        self.cleared.append(job_id)


class _LLMStub:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def _call_llm(self, **kwargs):
        self.calls.append(kwargs)
        return LLMResponse(content=self.payload, model="mock")


def test_build_document_hints_from_catalog_profile():
    profile = CatalogProfile(
        dominant_category="沙发",
        is_pure_image_catalog=True,
        brand_names={"ACME"},
    )
    hints = build_document_hints(category="furniture", catalog_profile=profile)

    assert "furniture" in hints.document_theme
    assert "沙发" in hints.document_theme
    assert "纯图商品目录" in hints.document_theme
    assert "品牌logo" in hints.ignore_hints


def test_build_document_hints_from_sampled_pages():
    hints = build_document_hints(
        sampled_pages=[
            ParsedPageIR(
                page_no=1,
                images=[ImageInfo(image_id="img-1", bbox=(0, 0, 100, 100), width=100, height=100)],
                metadata=PageMetadata(page_width=300, page_height=500),
            ),
            ParsedPageIR(
                page_no=2,
                images=[ImageInfo(image_id="img-2", bbox=(0, 0, 120, 120), width=120, height=120)],
                metadata=PageMetadata(page_width=300, page_height=500),
            ),
        ]
    )

    assert "纯图商品目录" in hints.document_theme


def _table_page_one() -> ParsedPageIR:
    headers = ["商品名称/描述", "售价", "颜色"]
    rows = [
        headers,
        ["云朵沙发", "899", "米白"],
    ]
    return ParsedPageIR(
        page_no=1,
        tables=[TableData(rows=rows, header_row=headers, column_count=3)],
        text_blocks=[
            TextBlock(content="商品名称/描述", bbox=(10, 10, 90, 30)),
            TextBlock(content="售价", bbox=(120, 10, 160, 30)),
            TextBlock(content="颜色", bbox=(220, 10, 260, 30)),
        ],
        raw_text="商品名称/描述 售价 颜色 云朵沙发 899 米白",
        metadata=PageMetadata(page_width=300, page_height=500),
    )


def _table_page_two() -> ParsedPageIR:
    return ParsedPageIR(
        page_no=2,
        text_blocks=[
            TextBlock(content="山丘沙发", bbox=(10, 100, 90, 120)),
            TextBlock(content="1299", bbox=(120, 100, 160, 120)),
            TextBlock(content="浅灰", bbox=(220, 100, 260, 120)),
        ],
        raw_text="山丘沙发 1299 浅灰",
        metadata=PageMetadata(page_width=300, page_height=500),
    )


@pytest.mark.asyncio
async def test_v2_uses_first_page_headers_for_later_table_pages():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return _table_page_one() if page_no == 1 else _table_page_two()

    processor._extract_page = fake_extract

    result = await processor.process_page(
        job_id="job-table",
        file_path="/tmp/fake.pdf",
        page_no=2,
        file_hash="abc12345",
    )

    assert result.status == "AI_COMPLETED"
    assert result.page_type == "A"
    assert result.extraction_method == "table_schema_v2"
    assert len(result.skus) == 1
    attrs = result.skus[0].attributes
    assert attrs["product_name"] == "山丘沙发"
    assert attrs["price"] == "1299"
    assert attrs["color"] == "浅灰"
    assert attrs["evidence_mode"] == "text_backed"
    assert attrs["product_description"] == "山丘沙发 1299 浅灰"
    assert legacy.calls == []


@pytest.mark.asyncio
async def test_v2_falls_back_to_legacy_when_regular_pipeline_fails():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy, allow_legacy_fallback=True)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[TextBlock(content="普通产品页", bbox=(0, 0, 100, 20))],
            raw_text="普通产品页",
            metadata=PageMetadata(page_width=300, page_height=500),
        )

    processor._extract_page = fake_extract
    async def fake_process_regular_page(raw, *, file_path, file_hash, page_no, document_hints):
        return PageResult(
            status="AI_FAILED",
            page_type="B",
            error="forced_failure",
            needs_review=True,
        )
    processor._process_regular_page = fake_process_regular_page  # type: ignore[method-assign]

    result = await processor.process_page(
        job_id="job-normal",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.extraction_method == "legacy_stub"
    assert len(legacy.calls) == 1


@pytest.mark.asyncio
async def test_v2_regular_page_builds_region_sku_without_legacy():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(content="云朵沙发", bbox=(20, 20, 120, 40)),
                TextBlock(content="售价: 899", bbox=(20, 50, 110, 70)),
                TextBlock(content="颜色: 米白", bbox=(20, 80, 110, 100)),
            ],
            images=[
                ImageInfo(image_id="img-main", bbox=(200, 20, 420, 240), width=600, height=600),
                ImageInfo(image_id="img-detail", bbox=(430, 40, 520, 130), width=200, height=200),
            ],
            raw_text="云朵沙发 售价:899 颜色:米白",
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    processor._extract_page = fake_extract

    result = await processor.process_page(
        job_id="job-region",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.status == "AI_COMPLETED"
    assert result.extraction_method == "region_rule_v2"
    assert len(result.skus) == 1
    assert result.skus[0].attributes["product_name"] == "云朵沙发"
    assert result.skus[0].attributes["price"] == "899"
    assert result.skus[0].attributes["color"] == "米白"
    assert result.skus[0].attributes["product_description"] == "云朵沙发 售价: 899 颜色: 米白"
    assert result.bindings[0].image_id == "img-main"
    assert result.images[0].image_id == "img-main"
    assert result.images[0].role == "product_main"
    assert result.images[1].role == "product_detail"
    assert legacy.calls == []


@pytest.mark.asyncio
async def test_v2_regular_page_outputs_visual_only_regions():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-a", bbox=(20, 20, 180, 220), width=300, height=400),
                ImageInfo(image_id="img-b", bbox=(220, 20, 380, 220), width=300, height=400),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    processor._extract_page = fake_extract

    result = await processor.process_page(
        job_id="job-visual",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.status == "AI_COMPLETED"
    assert result.extraction_method == "region_rule_v2"
    assert len(result.skus) == 2
    assert all(sku.attributes["evidence_mode"] == "visual_only" for sku in result.skus)
    assert legacy.calls == []


def test_v2_clear_job_cache_clears_local_and_legacy_cache():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy)
    processor._job_contexts["job-1"] = object()  # type: ignore[assignment]
    processor._job_locks["job-1"] = object()  # type: ignore[assignment]

    processor.clear_job_cache("job-1")

    assert "job-1" not in processor._job_contexts
    assert "job-1" not in processor._job_locks
    assert legacy.cleared == ["job-1"]


@pytest.mark.asyncio
async def test_v2_blank_page_is_skipped_without_legacy():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    processor._extract_page = fake_extract

    result = await processor.process_page(
        job_id="job-blank",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.status == "SKIPPED"
    assert legacy.calls == []


@pytest.mark.asyncio
async def test_v2_failed_page_does_not_fallback_when_disabled():
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy, allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[TextBlock(content="普通产品页", bbox=(0, 0, 100, 20))],
            raw_text="普通产品页",
            metadata=PageMetadata(page_width=300, page_height=500),
        )

    processor._extract_page = fake_extract
    async def fake_process_regular_page(raw, *, file_path, file_hash, page_no, document_hints):
        return PageResult(
            status="AI_FAILED",
            page_type="B",
            error="forced_failure",
            needs_review=True,
        )
    processor._process_regular_page = fake_process_regular_page  # type: ignore[method-assign]

    result = await processor.process_page(
        job_id="job-no-fallback",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.status == "AI_FAILED"
    assert legacy.calls == []


@pytest.mark.asyncio
async def test_v2_vlm_refine_can_split_single_heuristic_region():
    llm = _LLMStub(
        '{"regions": ['
        '{"member_object_ids": ["text_0_0", "text_0_1", "text_0_2", "image_0"], "score": 0.91, "reason": "first"},'
        '{"member_object_ids": ["text_0_3", "text_0_4", "text_0_5", "image_1"], "score": 0.89, "reason": "second"}'
        '], "ignored_object_ids": []}'
    )
    processor = PageProcessor(llm_service=llm, allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(
                    content="\n".join([
                        "Cloud Sofa",
                        "Price: 899",
                        "Color: Ivory",
                        "Hill Sofa",
                        "Price: 1299",
                        "Color: Ash Gray",
                    ]),
                    bbox=(20, 20, 200, 260),
                ),
            ],
            images=[
                ImageInfo(image_id="img-1", bbox=(220, 20, 360, 180), width=200, height=200),
                ImageInfo(image_id="img-2", bbox=(380, 20, 520, 180), width=200, height=200),
            ],
            raw_text="Cloud Sofa\nPrice: 899\nColor: Ivory\nHill Sofa\nPrice: 1299\nColor: Ash Gray\n",
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    async def fake_render(file_path: str, page_no: int, *, dpi: int = 160, max_long_edge: int = 1800):
        return b"fake-image"

    processor._extract_page = fake_extract
    processor._render_page_screenshot = fake_render  # type: ignore[method-assign]

    result = await processor.process_page(
        job_id="job-vlm",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
        category="furniture",
        catalog_profile=CatalogProfile(dominant_category="沙发"),
    )

    assert result.status == "AI_COMPLETED"
    assert result.extraction_method == "region_rule_v2"
    assert len(result.skus) == 2
    assert result.skus[0].attributes["product_name"] == "Cloud Sofa"
    assert result.skus[1].attributes["product_name"] == "Hill Sofa"
    operations = [call["operation"] for call in llm.calls]
    assert "region_refine_v2" in operations
    assert "page_verify_v2" in operations
    assert any("document_theme:" in call["prompt"] and "furniture" in call["prompt"] and "沙发" in call["prompt"] for call in llm.calls)


@pytest.mark.asyncio
async def test_v2_page_verify_can_merge_duplicate_candidates():
    llm = _LLMStub(
        '{"regions": [{"member_object_ids": ["text_0_0", "text_0_1", "text_0_2", "text_0_3", "image_0", "image_1"], "score": 0.91, "reason": "keep"}], "ignored_object_ids": []}'
    )
    processor = PageProcessor(llm_service=llm, allow_legacy_fallback=False)

    verify_calls = []

    async def fake_verify(skus, *, screenshot=None, document_hints=None):
        verify_calls.append((len(skus), screenshot, document_hints))
        return [skus[0]]

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(
                    content="\n".join([
                        "Cloud Sofa",
                        "Price: 899",
                        "Cloud Sofa",
                        "Price: 899",
                    ]),
                    bbox=(20, 20, 200, 180),
                ),
            ],
            images=[
                ImageInfo(image_id="img-1", bbox=(220, 20, 360, 180), width=200, height=200),
                ImageInfo(image_id="img-2", bbox=(380, 20, 520, 180), width=200, height=200),
            ],
            raw_text="Cloud Sofa\nPrice: 899\nCloud Sofa\nPrice: 899\n",
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    async def fake_render(file_path: str, page_no: int, *, dpi: int = 160, max_long_edge: int = 1800):
        return b"fake-image"

    processor._extract_page = fake_extract
    processor._render_page_screenshot = fake_render  # type: ignore[method-assign]
    processor._page_verifier.verify = fake_verify  # type: ignore[method-assign]

    result = await processor.process_page(
        job_id="job-verify",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 1
    assert verify_calls and verify_calls[0][0] == 1


@pytest.mark.asyncio
async def test_v2_can_use_ocr_and_layout_evidence_without_pdf_text():
    processor = PageProcessor(allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    async def fake_render(file_path: str, page_no: int, *, dpi: int = 160, max_long_edge: int = 1800):
        return b"fake-image"

    async def fake_run_ocr(screenshot: bytes | None):
        return [
            OcrBlock(text="Cloud Sofa", bbox=(20, 20, 160, 50), confidence=0.98),
            OcrBlock(text="Price: 899", bbox=(20, 60, 160, 90), confidence=0.98),
            OcrBlock(text="Color: Ivory", bbox=(20, 100, 160, 130), confidence=0.98),
        ]

    async def fake_run_layout(screenshot: bytes | None):
        return [
            LayoutRegion(label="figure", bbox=(220, 20, 420, 220), confidence=0.94),
        ]

    processor._extract_page = fake_extract
    processor._render_page_screenshot = fake_render  # type: ignore[method-assign]
    processor._run_ocr = fake_run_ocr  # type: ignore[method-assign]
    processor._run_layout_detection = fake_run_layout  # type: ignore[method-assign]

    result = await processor.process_page(
        job_id="job-ocr-layout",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="ocr12345",
    )

    assert result.status == "AI_COMPLETED"
    assert result.extraction_method == "region_rule_v2"
    assert len(result.skus) == 1
    assert result.skus[0].attributes["product_name"] == "Cloud Sofa"
    assert result.skus[0].attributes["price"] == "899"
    assert result.skus[0].attributes["color"] == "Ivory"
    assert result.skus[0].attributes["product_description"] == "Cloud Sofa Price: 899 Color: Ivory"


@pytest.mark.asyncio
async def test_v2_regular_page_extracts_export_contract_fields():
    processor = PageProcessor(allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(content="云朵沙发", bbox=(20, 20, 120, 40)),
                TextBlock(content="批发价: 799", bbox=(20, 50, 140, 70)),
                TextBlock(content="打包价: 699", bbox=(20, 80, 140, 100)),
                TextBlock(content="代发价: 659", bbox=(20, 110, 140, 130)),
                TextBlock(content="活动价: 629", bbox=(20, 140, 140, 160)),
                TextBlock(content="库存: 12", bbox=(20, 170, 140, 190)),
                TextBlock(content="重量(kg): 18.5", bbox=(20, 200, 180, 220)),
                TextBlock(content="自动下架时间: 2026-05-01", bbox=(20, 230, 240, 250)),
            ],
            raw_text=(
                "云朵沙发\n批发价: 799\n打包价: 699\n代发价: 659\n"
                "活动价: 629\n库存: 12\n重量(kg): 18.5\n自动下架时间: 2026-05-01\n"
            ),
            metadata=PageMetadata(page_width=400, page_height=600),
        )

    processor._extract_page = fake_extract

    result = await processor.process_page(
        job_id="job-export-fields",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="field1234",
    )

    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 1
    attrs = result.skus[0].attributes
    assert attrs["product_name"] == "云朵沙发"
    assert attrs["wholesale_price"] == "799"
    assert attrs["pack_price"] == "699"
    assert attrs["dropship_price"] == "659"
    assert attrs["campaign_price"] == "629"
    assert attrs["stock"] == "12"
    assert attrs["weight_kg"] == "18.5"
    assert attrs["auto_unpublish_time"] == "2026-05-01"


@pytest.mark.asyncio
async def test_v2_can_disable_refine_and_verify_via_settings(monkeypatch):
    llm = _LLMStub('{"regions": [], "ignored_object_ids": []}')
    processor = PageProcessor(llm_service=llm, allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(content="Cloud Sofa", bbox=(20, 20, 140, 40)),
                TextBlock(content="Price: 899", bbox=(20, 50, 140, 70)),
            ],
            images=[
                ImageInfo(image_id="img-main", bbox=(220, 20, 420, 220), width=400, height=400),
            ],
            raw_text="Cloud Sofa\nPrice: 899\n",
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    async def fake_render(file_path: str, page_no: int, *, dpi: int = 160, max_long_edge: int = 1800):
        return b"fake-image"

    processor._extract_page = fake_extract
    processor._render_page_screenshot = fake_render  # type: ignore[method-assign]
    monkeypatch.setattr(settings, "pipeline_v2_region_refine_enabled", False)
    monkeypatch.setattr(settings, "pipeline_v2_page_verify_enabled", False)

    result = await processor.process_page(
        job_id="job-disable-vlm-steps",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="disable12",
    )

    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 1
    assert llm.calls == []


@pytest.mark.asyncio
async def test_v2_table_page_can_fallback_to_vlm_rows():
    llm = _LLMStub(
        '{"headers": ["商品名称/描述", "售价", "颜色"], "rows": ['
        '{"商品名称/描述": "山丘沙发", "售价": "1299", "颜色": "浅灰"}'
        "]}",
    )
    processor = PageProcessor(llm_service=llm, allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        if page_no == 1:
            return _table_page_one()
        return ParsedPageIR(
            page_no=2,
            metadata=PageMetadata(page_width=300, page_height=500),
        )

    async def fake_render(file_path: str, page_no: int, *, dpi: int = 160, max_long_edge: int = 1800):
        return b"fake-image"

    processor._extract_page = fake_extract
    processor._render_page_screenshot = fake_render  # type: ignore[method-assign]

    result = await processor.process_page(
        job_id="job-table-vlm-fallback",
        file_path="/tmp/fake.pdf",
        page_no=2,
        file_hash="abc12345",
    )

    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 1
    assert result.skus[0].attributes["product_name"] == "山丘沙发"
    assert result.skus[0].attributes["price"] == "1299"
    assert result.skus[0].attributes["color"] == "浅灰"
    assert llm.calls[0]["operation"] == "table_fallback_v2"


@pytest.mark.asyncio
async def test_region_refiner_prompt_contains_document_hints():
    llm = _LLMStub('{"regions": [], "ignored_object_ids": []}')
    refiner = RegionRefiner(llm_service=llm)
    evidence = PageEvidence(
        page_no=1,
        page_width=100,
        page_height=100,
        objects=[EvidenceObject(object_id="text_0", object_type="text_block", bbox=(0, 0, 10, 10), text="Cloud Sofa")],
    )
    proposals = [RegionProposal(region_id="r1", bbox=(0, 0, 10, 10), member_object_ids=["text_0"])]
    hints = DocumentHints(document_theme="家具目录 / 沙发", ignore_hints=["品牌logo", "背景装饰图"])

    await refiner.refine(evidence, proposals, screenshot=b"img", document_hints=hints)

    assert "document_theme: 家具目录 / 沙发" in llm.calls[0]["prompt"]
    assert "ignore_hints: 品牌logo, 背景装饰图" in llm.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_page_verifier_prompt_contains_document_hints():
    llm = _LLMStub('{"discard_indexes": [], "merge_groups": []}')
    verifier = PageVerifier(llm_service=llm)
    hints = DocumentHints(document_theme="家具目录 / 沙发", ignore_hints=["品牌logo", "背景装饰图"])
    candidates = [
        SKUResult(attributes={"product_name": "Cloud Sofa"}, source_bbox=(0, 0, 10, 10), confidence=0.8),
        SKUResult(attributes={"product_name": "Hill Sofa"}, source_bbox=(20, 0, 30, 10), confidence=0.8),
    ]

    await verifier.verify(candidates, screenshot=b"img", document_hints=hints)

    assert "document_theme: 家具目录 / 沙发" in llm.calls[0]["prompt"]
    assert "ignore_hints: 品牌logo, 背景装饰图" in llm.calls[0]["prompt"]
