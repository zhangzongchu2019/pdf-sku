"""pipeline_v2 PageProcessor 测试。"""
from __future__ import annotations

import io

import pytest
from PIL import Image as PILImage, ImageDraw

from pdf_sku.llm_adapter.client.base import LLMResponse
from pdf_sku.pipeline.catalog_profiler import CatalogProfile
from pdf_sku.pipeline.layout_detector import LayoutRegion
from pdf_sku.pipeline.ir import ImageInfo, PageMetadata, PageResult, ParsedPageIR, SKUResult, TableData, TextBlock
from pdf_sku.pipeline.parser.ocr_engine import OcrBlock
from pdf_sku.pipeline_v2.attribute_extractor import RegionAttributeExtractor
from pdf_sku.pipeline_v2.document_hints import build_document_hints
from pdf_sku.pipeline_v2.model_anchor_extractor import ModelAnchorExtractor
from pdf_sku.pipeline_v2.models import DocumentHints, EvidenceObject, PageEvidence, RegionProposal
from pdf_sku.pipeline_v2.page_processor import PageProcessor
from pdf_sku.pipeline_v2.page_verifier import PageVerifier
from pdf_sku.pipeline_v2.region_refiner import RegionRefiner
from pdf_sku.pipeline_v2.scene_image_splitter import SceneImageSplitter
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


def test_model_anchor_extractor_prefers_precise_pdf_text_over_ocr_noise():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[ImageInfo(image_id="img-main", bbox=(260, 40, 500, 280), width=240, height=240, search_eligible=True)],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="pdf_title",
                object_type="text_block",
                bbox=(40, 40, 220, 70),
                text="Wood Rope Back Chair",
                source="pdf_text_precise",
                font_size=18,
            ),
            EvidenceObject(
                object_id="pdf_model",
                object_type="text_block",
                bbox=(40, 110, 150, 130),
                text="HR-WOOD5114",
                source="pdf_text_precise",
                font_size=12,
            ),
            EvidenceObject(
                object_id="pdf_spec",
                object_type="text_block",
                bbox=(40, 135, 200, 155),
                text="H 89 cm   W 49 cm   D 41 cm",
                source="pdf_text_precise",
                font_size=12,
            ),
            EvidenceObject(
                object_id="ocr_noise",
                object_type="ocr_block",
                bbox=(42, 136, 205, 158),
                text="H89CMW49CMD41CM",
                source="ocr_text",
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "HR-WOOD5114"
    assert skus[0].attributes["product_name"] == "Wood Rope Back Chair"
    assert skus[0].attributes["specs"] == "H 89 cm W 49 cm D 41 cm"
    assert len(bindings) == 1
    assert bindings[0].image_id == "img-main"


def test_model_anchor_extractor_keeps_product_name_empty_for_ocr_noise_title():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=1606,
        page_height=1100,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(
                    image_id="scene-main",
                    bbox=(0, 0, 1606, 1100),
                    width=1606,
                    height=1100,
                    search_eligible=True,
                ),
            ],
            metadata=PageMetadata(page_width=1606, page_height=1100),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-noise",
                object_type="ocr_block",
                bbox=(980, 270, 1132, 493),
                text="厂",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-model",
                object_type="ocr_block",
                bbox=(1284, 916, 1383, 940),
                text="SC-9901",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-spec-1",
                object_type="ocr_block",
                bbox=(1283, 940, 1485, 964),
                text="单人位：1170*920*890mm",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-spec-2",
                object_type="ocr_block",
                bbox=(1282, 958, 1484, 981),
                text="三人位：2170*920*890mm",
                source="ocr_text",
            ),
        ],
    )

    skus, _bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "SC-9901"
    assert "product_name" not in skus[0].attributes


def test_model_anchor_extractor_keeps_product_name_empty_for_ocr_slogan():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=1606,
        page_height=1100,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(
                    image_id="scene-main",
                    bbox=(0, 0, 1606, 1100),
                    width=1606,
                    height=1100,
                    search_eligible=True,
                ),
            ],
            metadata=PageMetadata(page_width=1606, page_height=1100),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-slogan",
                object_type="ocr_block",
                bbox=(903, 796, 1120, 839),
                text="Sit in peace_",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-model",
                object_type="ocr_block",
                bbox=(1310, 789, 1410, 811),
                text="SC-2316",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-spec-1",
                object_type="ocr_block",
                bbox=(1310, 811, 1512, 832),
                text="单人位：1010*830*850mm",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-spec-2",
                object_type="ocr_block",
                bbox=(1310, 828, 1512, 848),
                text="三人位：1880*820*850mm",
                source="ocr_text",
            ),
        ],
    )

    skus, _bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "SC-2316"
    assert "product_name" not in skus[0].attributes


def test_model_anchor_extractor_keeps_product_name_empty_for_far_ocr_phrase():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=1606,
        page_height=1100,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(
                    image_id="scene-main",
                    bbox=(0, 0, 1606, 1100),
                    width=1606,
                    height=1100,
                    search_eligible=True,
                ),
            ],
            metadata=PageMetadata(page_width=1606, page_height=1100),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-phrase",
                object_type="ocr_block",
                bbox=(1119, 182, 1182, 199),
                text="雅致与精细",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-model",
                object_type="ocr_block",
                bbox=(1121, 506, 1222, 531),
                text="SC-2318",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-spec-1",
                object_type="ocr_block",
                bbox=(1125, 532, 1320, 556),
                text="单人位：840*840*850mm",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-spec-2",
                object_type="ocr_block",
                bbox=(1125, 549, 1328, 572),
                text="三人位：1850*840*850mm",
                source="ocr_text",
            ),
        ],
    )

    skus, _bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "SC-2318"
    assert "product_name" not in skus[0].attributes


def test_model_anchor_extractor_matches_models_to_nearest_local_images():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=1190.55,
        page_height=737.01,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-y-main", bbox=(55, 129, 189, 306), width=268, height=354, search_eligible=True),
                ImageInfo(image_id="img-y-distractor", bbox=(234, 129, 362, 306), width=257, height=355, search_eligible=True),
                ImageInfo(image_id="img-y-high", bbox=(407, 67, 539, 307), width=265, height=480, search_eligible=True),
                ImageInfo(image_id="img-rope-main", bbox=(647, 220, 714, 320), width=128, height=196, search_eligible=True),
                ImageInfo(image_id="img-rope-high", bbox=(1005, 114, 1173, 341), width=257, height=410, search_eligible=True),
                ImageInfo(image_id="img-rope-bottom", bbox=(626, 475, 787, 669), width=270, height=349, search_eligible=True),
                ImageInfo(image_id="img-y-bottom", bbox=(55, 453, 191, 643), width=272, height=380, search_eligible=True),
                ImageInfo(image_id="img-divider", bbox=(595, 0, 683, 738), width=88, height=738, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=1190.55, page_height=737.01),
        ),
        objects=[
            EvidenceObject(
                object_id="title-rope",
                object_type="text_block",
                bbox=(652, 55, 825, 97),
                text="Rope Back Chair",
                source="pdf_text_precise",
                font_size=26,
            ),
            EvidenceObject(
                object_id="title-y",
                object_type="text_block",
                bbox=(56, 58, 132, 99),
                text="Y-chair",
                source="pdf_text_precise",
                font_size=26,
            ),
            EvidenceObject(
                object_id="m-wood-y",
                object_type="text_block",
                bbox=(56, 310, 122, 326),
                text="HR-WOOD5001C",
                source="pdf_text_precise",
                font_size=10,
            ),
            EvidenceObject(
                object_id="m-wood-y-high",
                object_type="text_block",
                bbox=(408, 310, 474, 326),
                text="HR-WOOD5001H",
                source="pdf_text_precise",
                font_size=10,
            ),
            EvidenceObject(
                object_id="title-wood-y",
                object_type="text_block",
                bbox=(56, 344, 130, 367),
                text="Wood Y-chair",
                source="pdf_text_precise",
                font_size=14,
            ),
            EvidenceObject(
                object_id="m-wood-rope",
                object_type="text_block",
                bbox=(652, 329, 710, 345),
                text="HR-WOOD5115",
                source="pdf_text_precise",
                font_size=10,
            ),
            EvidenceObject(
                object_id="m-wood-rope-high",
                object_type="text_block",
                bbox=(1028, 329, 1092, 345),
                text="HR-WOOD5115H",
                source="pdf_text_precise",
                font_size=10,
            ),
            EvidenceObject(
                object_id="title-resin-rope",
                object_type="text_block",
                bbox=(653, 450, 781, 473),
                text="Resin Rope Back Chair",
                source="pdf_text_precise",
                font_size=14,
            ),
            EvidenceObject(
                object_id="title-resin-y",
                object_type="text_block",
                bbox=(377, 637, 456, 659),
                text="Resin Y-chair",
                source="pdf_text_precise",
                font_size=14,
            ),
            EvidenceObject(
                object_id="m-resin-y",
                object_type="text_block",
                bbox=(56, 646, 105, 662),
                text="HR-PP5001",
                source="pdf_text_precise",
                font_size=10,
            ),
            EvidenceObject(
                object_id="m-resin-rope",
                object_type="text_block",
                bbox=(652, 646, 696, 662),
                text="HR-PP5115",
                source="pdf_text_precise",
                font_size=10,
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert [sku.attributes["model_number"] for sku in skus] == [
        "HR-WOOD5001C",
        "HR-WOOD5001H",
        "HR-WOOD5115",
        "HR-WOOD5115H",
        "HR-PP5001",
        "HR-PP5115",
    ]
    assert [binding.image_id for binding in bindings if binding.rank == 1] == [
        "img-y-main",
        "img-y-high",
        "img-rope-main",
        "img-rope-high",
        "img-y-bottom",
        "img-rope-bottom",
    ]


def test_model_anchor_extractor_recalls_local_companions_without_crossing_h_variant():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=1190.55,
        page_height=737.01,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-rope-main", bbox=(646.7, 220.0, 714.4, 320.3), width=128, height=196, search_eligible=True),
                ImageInfo(image_id="img-rope-top-left", bbox=(651.0, 121.4, 708.6, 217.7), width=116, height=193, search_eligible=True),
                ImageInfo(image_id="img-rope-top-right", bbox=(762.8, 121.3, 825.4, 216.7), width=126, height=191, search_eligible=True),
                ImageInfo(image_id="img-rope-high", bbox=(1004.5, 114.1, 1173.4, 341.3), width=257, height=410, search_eligible=True),
                ImageInfo(image_id="img-rope-normal-near-high", bbox=(932.1, 121.4, 988.3, 217.7), width=113, height=193, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=1190.55, page_height=737.01),
        ),
        objects=[
            EvidenceObject(
                object_id="title-rope",
                object_type="text_block",
                bbox=(652, 55, 825, 97),
                text="Rope Back Chair",
                source="pdf_text_precise",
                font_size=26,
            ),
            EvidenceObject(
                object_id="m-wood-rope",
                object_type="text_block",
                bbox=(652, 329, 710, 345),
                text="HR-WOOD5115",
                source="pdf_text_precise",
                font_size=10,
            ),
            EvidenceObject(
                object_id="m-wood-rope-high",
                object_type="text_block",
                bbox=(1028, 329, 1092, 345),
                text="HR-WOOD5115H",
                source="pdf_text_precise",
                font_size=10,
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    binding_groups: dict[str, list[str]] = {}
    current_model = ""
    model_iter = iter([sku.attributes["model_number"] for sku in skus])
    for binding in bindings:
        if binding.rank == 1:
            current_model = next(model_iter)
        binding_groups.setdefault(current_model, []).append(binding.image_id)

    assert binding_groups["HR-WOOD5115"] == [
        "img-rope-main",
        "img-rope-top-left",
        "img-rope-top-right",
    ]
    assert binding_groups["HR-WOOD5115H"] == ["img-rope-high"]


def test_model_anchor_extractor_supports_labeled_numeric_models_from_ocr():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=2,
        page_width=1303.94,
        page_height=864.57,
        raw=ParsedPageIR(
            page_no=2,
            images=[
                ImageInfo(image_id="img-right-main", bbox=(650.9, 0.0, 1304.9, 483.1), width=1091, height=807, search_eligible=True),
                ImageInfo(image_id="img-right-detail", bbox=(988.9, 519.2, 1303.4, 810.6), width=441, height=387, search_eligible=True),
                ImageInfo(image_id="img-left-detail", bbox=(39.6, 61.3, 241.1, 231.4), width=336, height=284, search_eligible=True),
                ImageInfo(image_id="img-left-inset", bbox=(243.8, 62.1, 464.3, 232.3), width=368, height=284, search_eligible=True),
                ImageInfo(image_id="img-left-main", bbox=(-1.1, 290.4, 654.9, 865.4), width=1094, height=959, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=1303.94, page_height=864.57),
        ),
        objects=[
            EvidenceObject(object_id="ocr-title", object_type="ocr_block", bbox=(794.6, 595.2, 1013.4, 618.3), text="Perfect space utilization", source="ocr_text"),
            EvidenceObject(object_id="ocr-right-1", object_type="ocr_block", bbox=(794.6, 690.7, 901.8, 707.4), text="茶几（TeaTable）：:201#", source="ocr_text"),
            EvidenceObject(object_id="ocr-right-2", object_type="ocr_block", bbox=(794.6, 707.4, 927.9, 722.6), text="规格（Size）：1300x700+拖mm", source="ocr_text"),
            EvidenceObject(object_id="ocr-right-3", object_type="ocr_block", bbox=(795.4, 721.9, 916.3, 738.5), text="电视柜（TVCabinet）：201#", source="ocr_text"),
            EvidenceObject(object_id="ocr-right-4", object_type="ocr_block", bbox=(794.6, 736.4, 915.6, 753.7), text="规格（Size）：2800-2000mm", source="ocr_text"),
            EvidenceObject(object_id="ocr-left-1", object_type="ocr_block", bbox=(134.7, 763.1, 260.0, 781.2), text="餐桌（DiningTable）：202", source="ocr_text"),
            EvidenceObject(object_id="ocr-left-2", object_type="ocr_block", bbox=(134.7, 780.5, 243.4, 795.7), text="规格（Size）：中1300mm", source="ocr_text"),
            EvidenceObject(object_id="ocr-left-3", object_type="ocr_block", bbox=(134.7, 793.6, 256.4, 813.1), text="餐椅（DiningChair）:202#", source="ocr_text"),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert [sku.attributes["model_number"] for sku in skus] == ["201#", "202"]
    assert skus[0].attributes["product_name"] == "茶几（TeaTable） / 电视柜（TVCabinet）"
    assert skus[1].attributes["product_name"] == "餐桌（DiningTable） / 餐椅（DiningChair）"
    assert skus[0].attributes["specs"] == "规格（Size）：1300x700+拖mm 规格（Size）：2800-2000mm"
    assert skus[1].attributes["specs"] == "规格（Size）：中1300mm"

    binding_groups: dict[str, list[str]] = {}
    current_model = ""
    model_iter = iter([sku.attributes["model_number"] for sku in skus])
    for binding in bindings:
        if binding.rank == 1:
            current_model = next(model_iter)
        binding_groups.setdefault(current_model, []).append(binding.image_id)

    assert binding_groups["201#"] == ["img-right-main", "img-right-detail"]
    assert binding_groups["202"] == ["img-left-main", "img-left-inset", "img-left-detail"]


def test_model_anchor_extractor_ignores_page_markers_as_models():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-main", bbox=(180, 40, 520, 620), width=680, height=1160, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-model",
                object_type="ocr_block",
                bbox=(220, 650, 360, 680),
                text="型号：868#",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-page",
                object_type="ocr_block",
                bbox=(520, 760, 590, 790),
                text="PAGE/03",
                source="ocr_text",
            ),
        ],
    )

    skus, _bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "868#"


def test_model_anchor_extractor_does_not_misclassify_pack_substring_product_label():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-main", bbox=(150, 40, 540, 620), width=780, height=1160, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-labeled-model",
                object_type="ocr_block",
                bbox=(180, 655, 430, 690),
                text="Backpack Lounge: ZX-204",
                source="ocr_text",
            ),
        ],
    )

    skus, _bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "ZX-204"
    assert skus[0].attributes["product_name"] == "Backpack Lounge"


def test_model_anchor_extractor_falls_back_to_labeled_product_name_anchor():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-main", bbox=(60, 40, 560, 640), width=1000, height=1200, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-product",
                object_type="ocr_block",
                bbox=(250, 735, 430, 768),
                text="型号：圣日耳曼沙发",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-page",
                object_type="ocr_block",
                bbox=(40, 772, 120, 796),
                text="PAGE/02",
                source="ocr_text",
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert "model_number" not in skus[0].attributes
    assert skus[0].attributes["product_name"] == "圣日耳曼沙发"
    assert [binding.image_id for binding in bindings] == ["img-main"]


def test_model_anchor_extractor_accepts_generic_labeled_model_without_furniture_terms():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-main", bbox=(180, 60, 520, 520), width=680, height=920, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-labeled-model",
                object_type="ocr_block",
                bbox=(80, 620, 300, 650),
                text="Series A：ZX-204",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-size",
                object_type="ocr_block",
                bbox=(80, 655, 320, 685),
                text="Size: 1200x700mm",
                source="ocr_text",
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "ZX-204"
    assert skus[0].attributes["product_name"] == "Series A"
    assert skus[0].attributes["specs"] == "Size: 1200x700mm"
    assert [binding.image_id for binding in bindings] == ["img-main"]


def test_model_anchor_extractor_accepts_generic_product_name_label_in_english():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(image_id="img-main", bbox=(100, 40, 560, 620), width=920, height=1160, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-product",
                object_type="ocr_block",
                bbox=(240, 700, 500, 730),
                text="Product Name: Aurora Modular",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-page",
                object_type="ocr_block",
                bbox=(40, 760, 120, 790),
                text="PAGE/05",
                source="ocr_text",
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert "model_number" not in skus[0].attributes
    assert skus[0].attributes["product_name"] == "Aurora Modular"
    assert [binding.image_id for binding in bindings] == ["img-main"]


def test_region_attribute_extractor_keeps_backpack_name_as_non_label_line():
    extractor = RegionAttributeExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=600,
        page_height=800,
        objects=[
            EvidenceObject(
                object_id="text_name",
                object_type="text_block",
                bbox=(60, 80, 220, 100),
                text="Backpack Lounge",
                source="pdf_text",
            ),
            EvidenceObject(
                object_id="text_color",
                object_type="text_block",
                bbox=(60, 110, 220, 130),
                text="Color: Black",
                source="pdf_text",
            ),
        ],
    )
    region = RegionProposal(
        region_id="region_1",
        bbox=(50, 70, 230, 140),
        member_object_ids=["text_name", "text_color"],
        score=0.8,
        reason="test",
    )

    attributes = extractor.extract(region, evidence)

    assert attributes["product_name"] == "Backpack Lounge"


def test_model_anchor_extractor_filters_text_heavy_images():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=3,
        page_width=600,
        page_height=800,
        raw=ParsedPageIR(
            page_no=3,
            images=[
                ImageInfo(image_id="img-product-a", bbox=(180, 20, 560, 360), width=760, height=680, search_eligible=True),
                ImageInfo(image_id="img-product-b", bbox=(160, 420, 560, 720), width=800, height=600, search_eligible=True),
                ImageInfo(image_id="img-text-title", bbox=(40, 80, 210, 145), width=340, height=130, search_eligible=True),
                ImageInfo(image_id="img-text-copy", bbox=(40, 150, 230, 245), width=380, height=190, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="ocr-name",
                object_type="ocr_block",
                bbox=(280, 742, 420, 772),
                text="型号：SC-9901",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-page",
                object_type="ocr_block",
                bbox=(30, 770, 110, 794),
                text="PAGE/04",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-text-title-1",
                object_type="ocr_block",
                bbox=(42, 82, 208, 110),
                text="ELEGANT",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-text-title-2",
                object_type="ocr_block",
                bbox=(42, 112, 180, 142),
                text="COLOR",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-text-copy-1",
                object_type="ocr_block",
                bbox=(42, 154, 220, 182),
                text="The clean and elegant color and",
                source="ocr_text",
            ),
            EvidenceObject(
                object_id="ocr-text-copy-2",
                object_type="ocr_block",
                bbox=(42, 186, 222, 214),
                text="structure co-locate",
                source="ocr_text",
            ),
        ],
    )

    skus, bindings = extractor.extract(evidence)

    assert len(skus) == 1
    assert skus[0].attributes["model_number"] == "SC-9901"
    assert [binding.image_id for binding in bindings] == ["img-product-b", "img-product-a"]


def test_model_anchor_source_bbox_stays_local_for_page_spanning_image():
    extractor = ModelAnchorExtractor()
    evidence = PageEvidence(
        page_no=1,
        page_width=1200,
        page_height=800,
        raw=ParsedPageIR(
            page_no=1,
            images=[
                ImageInfo(
                    image_id="img-full",
                    bbox=(0, 0, 1200, 800),
                    width=1200,
                    height=800,
                    search_eligible=True,
                ),
            ],
            metadata=PageMetadata(page_width=1200, page_height=800),
        ),
        objects=[
            EvidenceObject(
                object_id="title-left",
                object_type="text_block",
                bbox=(80, 660, 260, 690),
                text="MODEL: RT-8295",
                source="pdf_text_precise",
                font_size=16,
            ),
        ],
    )

    skus, _bindings = extractor.extract(evidence)

    assert len(skus) == 1
    x0, y0, x1, y1 = skus[0].source_bbox
    assert x1 - x0 < 400
    assert y1 - y0 < 120


def _scene_image_bytes() -> bytes:
    img = PILImage.new("RGB", (900, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((45, 50, 855, 545), fill=(220, 220, 220))
    draw.rectangle((60, 160, 230, 470), fill=(95, 95, 95))
    draw.rectangle((325, 110, 590, 430), fill=(120, 120, 120))
    draw.rectangle((665, 160, 840, 470), fill=(95, 95, 95))
    draw.rectangle((350, 435, 560, 515), fill=(75, 75, 75))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _wide_scene_panel_bytes(*, with_inset: bool = False) -> bytes:
    img = PILImage.new("RGB", (1200, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((50, 60, 1150, 560), fill=(220, 220, 220))
    draw.rectangle((110, 260, 300, 520), fill=(95, 95, 95))
    draw.rectangle((430, 180, 760, 500), fill=(110, 110, 110))
    draw.rectangle((860, 260, 1060, 520), fill=(95, 95, 95))
    draw.rectangle((470, 470, 700, 545), fill=(70, 70, 70))
    if with_inset:
        draw.rectangle((120, 620, 430, 760), fill=(205, 205, 205))
        draw.rectangle((160, 655, 255, 745), fill=(95, 95, 95))
        draw.rectangle((275, 640, 395, 748), fill=(110, 110, 110))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _scene_image_with_detached_text_bytes() -> bytes:
    img = PILImage.new("RGB", (1200, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((60, 60, 1020, 640), fill=(225, 225, 225))
    draw.rectangle((110, 260, 320, 560), fill=(95, 95, 95))
    draw.rectangle((430, 180, 760, 500), fill=(110, 110, 110))
    draw.rectangle((820, 260, 980, 560), fill=(95, 95, 95))
    draw.rectangle((1030, 675, 1120, 690), fill=(20, 20, 20))
    draw.rectangle((1030, 708, 1160, 720), fill=(50, 50, 50))
    draw.rectangle((1030, 735, 1170, 747), fill=(50, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _wide_scene_with_inset_and_text_bytes() -> bytes:
    img = PILImage.new("RGB", (1400, 900), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((70, 70, 1120, 620), fill=(220, 220, 220))
    draw.rectangle((150, 250, 360, 540), fill=(95, 95, 95))
    draw.rectangle((470, 180, 810, 500), fill=(110, 110, 110))
    draw.rectangle((880, 250, 1050, 540), fill=(95, 95, 95))
    draw.rectangle((90, 690, 520, 845), fill=(205, 205, 205))
    draw.rectangle((160, 730, 305, 825), fill=(95, 95, 95))
    draw.rectangle((330, 715, 465, 830), fill=(110, 110, 110))
    draw.rectangle((760, 705, 1030, 745), fill=(40, 40, 40))
    draw.rectangle((1090, 700, 1270, 728), fill=(40, 40, 40))
    draw.rectangle((1090, 748, 1310, 776), fill=(65, 65, 65))
    draw.rectangle((1090, 793, 1330, 821), fill=(65, 65, 65))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _triple_panel_scene_bytes() -> bytes:
    img = PILImage.new("RGB", (1400, 900), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 80, 680, 820), fill=(210, 210, 210))
    draw.rectangle((760, 80, 1340, 420), fill=(200, 200, 200))
    draw.rectangle((760, 500, 1340, 820), fill=(190, 190, 190))
    draw.rectangle((120, 260, 260, 620), fill=(90, 90, 90))
    draw.rectangle((320, 280, 560, 620), fill=(110, 110, 110))
    draw.rectangle((860, 180, 1180, 360), fill=(90, 90, 90))
    draw.rectangle((870, 580, 1220, 760), fill=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_scene_image_splitter_can_split_single_large_scene(monkeypatch):
    splitter = SceneImageSplitter()
    images = splitter.extract(
        ImageInfo(
            image_id="scene-full",
            bbox=(0, 0, 900, 600),
            data=_scene_image_bytes(),
            width=900,
            height=600,
            short_edge=600,
            search_eligible=True,
        ),
        page_no=1,
        page_width=900,
        page_height=600,
    )

    assert len(images) == 1
    assert all(image.search_eligible for image in images)
    assert all(image.data for image in images)
    assert all(image.width < 900 and image.height < 600 for image in images)


def test_scene_image_splitter_can_split_wide_scene_without_text_hint(monkeypatch):
    splitter = SceneImageSplitter()
    images = splitter.extract(
        ImageInfo(
            image_id="scene-wide",
            bbox=(0, 0, 1200, 800),
            data=_wide_scene_panel_bytes(),
            width=1200,
            height=800,
            short_edge=800,
            search_eligible=True,
        ),
        page_no=1,
        page_width=1200,
        page_height=800,
    )

    assert len(images) == 1
    assert all(image.data for image in images)
    assert images[0].width < 1200
    assert images[0].height < 800


def test_scene_image_splitter_keeps_inset_panel_alongside_scene_split(monkeypatch):
    splitter = SceneImageSplitter()
    images = splitter.extract(
        ImageInfo(
            image_id="scene-wide",
            bbox=(0, 0, 1200, 800),
            data=_wide_scene_panel_bytes(with_inset=True),
            width=1200,
            height=800,
            short_edge=800,
            search_eligible=True,
        ),
        page_no=1,
        page_width=1200,
        page_height=800,
    )

    assert len(images) == 2
    assert images[0].width < 1200
    assert images[0].height < 800
    assert images[1].width < images[0].width
    assert images[1].height < images[0].height


def test_scene_image_splitter_prefers_single_main_panel_over_detached_text(monkeypatch):
    splitter = SceneImageSplitter()
    images = splitter.extract(
        ImageInfo(
            image_id="scene-with-text",
            bbox=(0, 0, 1200, 800),
            data=_scene_image_with_detached_text_bytes(),
            width=1200,
            height=800,
            short_edge=800,
            search_eligible=True,
        ),
        page_no=1,
        page_width=1200,
        page_height=800,
        text_boxes=[
            (1030, 675, 1120, 690),
            (1030, 708, 1160, 720),
            (1030, 735, 1170, 747),
        ],
    )

    assert len(images) == 1
    assert images[0].width < 1100
    assert images[0].height < 700


def test_scene_image_splitter_keeps_inset_panel_when_detached_text_exists(monkeypatch):
    splitter = SceneImageSplitter()
    images = splitter.extract(
        ImageInfo(
            image_id="scene-inset-text",
            bbox=(0, 0, 1400, 900),
            data=_wide_scene_with_inset_and_text_bytes(),
            width=1400,
            height=900,
            short_edge=900,
            search_eligible=True,
        ),
        page_no=4,
        page_width=1400,
        page_height=900,
        text_boxes=[
            (760, 705, 1030, 745),
            (1090, 700, 1270, 728),
            (1090, 748, 1310, 776),
            (1090, 793, 1330, 821),
        ],
    )

    assert len(images) == 2
    widths = sorted((image.width for image in images), reverse=True)
    assert widths[0] > widths[1]


def test_scene_image_splitter_can_split_three_panel_montage():
    splitter = SceneImageSplitter()
    images = splitter.extract(
        ImageInfo(
            image_id="scene-three",
            bbox=(0, 0, 1400, 900),
            data=_triple_panel_scene_bytes(),
            width=1400,
            height=900,
            short_edge=900,
            search_eligible=True,
        ),
        page_no=1,
        page_width=1400,
        page_height=900,
    )

    assert len(images) == 3
    widths = sorted((image.width for image in images), reverse=True)
    assert widths[0] > widths[1] >= widths[2]


def test_page_processor_assigns_split_scene_panels_to_multiple_skus():
    processor = PageProcessor()
    raw = ParsedPageIR(
        page_no=1,
        images=[
            ImageInfo(
                image_id="img-full",
                bbox=(0, 0, 1200, 800),
                data=_wide_scene_with_inset_and_text_bytes(),
                width=1200,
                height=800,
                short_edge=800,
                search_eligible=True,
            ),
        ],
        metadata=PageMetadata(page_width=1200, page_height=800),
    )
    skus = [
        SKUResult(source_bbox=(100, 610, 400, 690), attributes={"model_number": "RT-8298"}),
        SKUResult(source_bbox=(770, 360, 1120, 430), attributes={"model_number": "RT-8299"}),
        SKUResult(source_bbox=(780, 690, 1140, 790), attributes={"model_number": "RT-8300"}),
    ]
    split_images = [
        ImageInfo(image_id="p1_scene_0", bbox=(70, 70, 640, 620), width=570, height=550, short_edge=550, search_eligible=True),
        ImageInfo(image_id="p1_scene_1", bbox=(700, 70, 1140, 420), width=440, height=350, short_edge=350, search_eligible=True),
        ImageInfo(image_id="p1_scene_2", bbox=(700, 470, 1140, 845), width=440, height=375, short_edge=375, search_eligible=True),
    ]
    processor._scene_splitter.extract = lambda *args, **kwargs: split_images  # type: ignore[method-assign]

    groups = processor._scene_image_group_for_single_sku(raw, skus, page_no=1)

    assert groups is not None
    assert len(groups) == 3
    assert all(groups)
    assert sum(len(group) for group in groups) == 3
    flattened = [image_id for group in groups for image_id in group]
    assert len(flattened) == len(set(flattened))
    assert flattened == ["p1_scene_0", "p1_scene_1", "p1_scene_2"]


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


@pytest.mark.asyncio
async def test_v2_regular_page_single_large_image_can_emit_scene_subimages(monkeypatch):
    processor = PageProcessor(allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(content="SC-9901", bbox=(680, 520, 820, 550)),
                TextBlock(content="单人位：1170*920*890mm", bbox=(680, 555, 860, 580)),
                TextBlock(content="三人位：2170*920*890mm", bbox=(680, 585, 860, 610)),
            ],
            images=[
                ImageInfo(
                    image_id="scene-full",
                    bbox=(0, 0, 900, 600),
                    data=_scene_image_bytes(),
                    width=900,
                    height=600,
                    short_edge=600,
                    search_eligible=True,
                )
            ],
            raw_text="SC-9901 单人位：1170*920*890mm 三人位：2170*920*890mm",
            metadata=PageMetadata(page_width=900, page_height=600),
        )

    processor._extract_page = fake_extract

    result = await processor.process_page(
        job_id="job-scene-subimages",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="scene1234",
    )

    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 1
    bound_image_ids = [binding.image_id for binding in result.bindings if binding.image_id]
    assert len(bound_image_ids) == 1
    assert all(image_id.startswith("p1_scene_") for image_id in bound_image_ids)


@pytest.mark.asyncio
async def test_v2_regular_page_prefers_model_anchor_extraction(monkeypatch):
    legacy = _LegacyStub()
    processor = PageProcessor(fallback_processor=legacy)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(
                    content="Catalog spread page\nwith all text collapsed into one block",
                    bbox=(0, 0, 600, 800),
                )
            ],
            images=[
                ImageInfo(image_id="img-a", bbox=(260, 40, 420, 220), width=240, height=240, search_eligible=True),
                ImageInfo(image_id="img-b", bbox=(260, 260, 420, 440), width=240, height=240, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    async def fake_precise(file_path: str, page_no: int):
        return [
            EvidenceObject(
                object_id="line-1",
                object_type="text_block",
                bbox=(40, 40, 220, 70),
                text="Wood Rope Back Chair",
                source="pdf_text_precise",
                font_size=18,
            ),
            EvidenceObject(
                object_id="line-2",
                object_type="text_block",
                bbox=(40, 110, 150, 130),
                text="HR-WOOD5114",
                source="pdf_text_precise",
                font_size=12,
            ),
            EvidenceObject(
                object_id="line-3",
                object_type="text_block",
                bbox=(40, 135, 210, 155),
                text="H 89 cm   W 49 cm   D 41 cm",
                source="pdf_text_precise",
                font_size=12,
            ),
            EvidenceObject(
                object_id="line-4",
                object_type="text_block",
                bbox=(40, 260, 220, 290),
                text="Resin Rope Back Chair",
                source="pdf_text_precise",
                font_size=18,
            ),
            EvidenceObject(
                object_id="line-5",
                object_type="text_block",
                bbox=(40, 330, 130, 350),
                text="HR-PP5115",
                source="pdf_text_precise",
                font_size=12,
            ),
            EvidenceObject(
                object_id="line-6",
                object_type="text_block",
                bbox=(40, 355, 210, 375),
                text="H 89 cm   W 49 cm   D 41 cm",
                source="pdf_text_precise",
                font_size=12,
            ),
        ]

    monkeypatch.setattr(processor, "_extract_page", fake_extract)
    monkeypatch.setattr(processor, "_extract_precise_pdf_text_objects", fake_precise)

    result = await processor.process_page(
        job_id="job-model-anchor",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    assert result.status == "AI_COMPLETED"
    assert result.extraction_method == "model_anchor_v2"
    assert [sku.attributes["model_number"] for sku in result.skus] == ["HR-WOOD5114", "HR-PP5115"]
    assert [sku.attributes["product_name"] for sku in result.skus] == ["Wood Rope Back Chair", "Resin Rope Back Chair"]
    assert result.bindings[0].image_id == "img-a"
    assert result.bindings[1].image_id == "img-b"
    assert legacy.calls == []


@pytest.mark.asyncio
async def test_v2_model_anchor_page_can_keep_multiple_images_per_model(monkeypatch):
    processor = PageProcessor(allow_legacy_fallback=False)

    async def fake_extract(file_path: str, page_no: int) -> ParsedPageIR:
        return ParsedPageIR(
            page_no=1,
            text_blocks=[
                TextBlock(content="spread", bbox=(0, 0, 600, 800)),
            ],
            images=[
                ImageInfo(image_id="img-a-main", bbox=(260, 40, 420, 220), width=240, height=240, search_eligible=True),
                ImageInfo(image_id="img-a-detail", bbox=(430, 60, 520, 180), width=140, height=180, search_eligible=True),
                ImageInfo(image_id="img-b-main", bbox=(260, 260, 420, 440), width=240, height=240, search_eligible=True),
                ImageInfo(image_id="img-b-detail", bbox=(430, 280, 520, 400), width=140, height=180, search_eligible=True),
            ],
            metadata=PageMetadata(page_width=600, page_height=800),
        )

    async def fake_precise(file_path: str, page_no: int):
        return [
            EvidenceObject(
                object_id="line-1",
                object_type="text_block",
                bbox=(40, 40, 220, 70),
                text="Wood Rope Back Chair",
                source="pdf_text_precise",
                font_size=18,
            ),
            EvidenceObject(
                object_id="line-2",
                object_type="text_block",
                bbox=(40, 110, 150, 130),
                text="HR-WOOD5114",
                source="pdf_text_precise",
                font_size=12,
            ),
            EvidenceObject(
                object_id="line-3",
                object_type="text_block",
                bbox=(40, 260, 220, 290),
                text="Resin Rope Back Chair",
                source="pdf_text_precise",
                font_size=18,
            ),
            EvidenceObject(
                object_id="line-4",
                object_type="text_block",
                bbox=(40, 330, 130, 350),
                text="HR-PP5115",
                source="pdf_text_precise",
                font_size=12,
            ),
        ]

    monkeypatch.setattr(processor, "_extract_page", fake_extract)
    monkeypatch.setattr(processor, "_extract_precise_pdf_text_objects", fake_precise)

    result = await processor.process_page(
        job_id="job-model-anchor-multi-image",
        file_path="/tmp/fake.pdf",
        page_no=1,
        file_hash="abc12345",
    )

    bindings_by_sku = {}
    for binding in result.bindings:
        bindings_by_sku.setdefault(binding.sku_id, []).append(binding.image_id)

    assert result.status == "AI_COMPLETED"
    assert len(result.skus) == 2
    assert list(bindings_by_sku.values()) == [
        ["img-a-main", "img-a-detail"],
        ["img-b-main", "img-b-detail"],
    ]


def test_v2_build_regular_page_result_keeps_preferred_images_aligned_after_sort():
    processor = PageProcessor(allow_legacy_fallback=False)
    raw = ParsedPageIR(
        page_no=1,
        images=[
            ImageInfo(image_id="img-left", bbox=(20, 40, 160, 220), width=280, height=360),
            ImageInfo(image_id="img-right", bbox=(260, 40, 400, 260), width=280, height=440),
        ],
        metadata=PageMetadata(page_width=500, page_height=700),
    )
    skus = [
        SKUResult(
            sku_id="",
            attributes={"model_number": "RIGHT"},
            source_bbox=(260, 40, 400, 260),
            validity="valid",
            confidence=0.9,
            extraction_method="model_anchor_v2",
        ),
        SKUResult(
            sku_id="",
            attributes={"model_number": "LEFT"},
            source_bbox=(20, 40, 160, 220),
            validity="valid",
            confidence=0.9,
            extraction_method="model_anchor_v2",
        ),
    ]

    result = processor._build_regular_page_result(
        raw,
        evidence=PageEvidence(page_no=1, page_width=500, page_height=700, raw=raw),
        proposals=[],
        skus=skus,
        file_hash="sortbind",
        page_no=1,
        preferred_image_ids=["img-right", "img-left"],
        page_extraction_method="model_anchor_v2",
    )

    assert [sku.attributes["model_number"] for sku in result.skus] == ["LEFT", "RIGHT"]
    assert [binding.image_id for binding in result.bindings] == ["img-left", "img-right"]


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
