"""
Pipeline 中间表示 (Intermediate Representation)。
对齐: Pipeline 详设 §3 类图 + §5.3

所有 Pipeline 阶段通过这些数据结构传递信息。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    """文本块 (来自 PDF 解析)。"""
    content: str = ""
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)  # x0, y0, x1, y1
    confidence: float = 1.0
    block_type: str = "paragraph"  # paragraph | heading | caption | label
    font_size: float = 0.0
    font_name: str = ""
    is_bold: bool = False


@dataclass
class TableData:
    """表格数据。"""
    rows: list[list[str]] = field(default_factory=list)
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    header_row: list[str] | None = None
    column_count: int = 0
    is_continuation: bool = False
    # 每行是否有独立图片单元格 (True=非合并, False=pdfplumber None=竖向合并共享上行图片)
    # 与 rows 等长，仅 _plumber_tables 时填充；CrossPageMerger 修改后可能为空列表
    row_image_flags: list[bool] = field(default_factory=list)


@dataclass
class ImageInfo:
    """图片信息。"""
    image_id: str = ""
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    data: bytes = b""
    width: int = 0
    height: int = 0
    short_edge: int = 0
    role: str = ""  # product_main | product_detail | logo | decoration | unknown
    is_fragmented: bool = False
    is_duplicate: bool = False
    is_tile_composite: bool = False  # 由 _merge_tile_fragments 聚类创建的复合图片
    image_hash: str = ""
    quality_warning: str = ""
    search_eligible: bool = False


@dataclass
class PageMetadata:
    """页面元数据。"""
    page_width: float = 0.0
    page_height: float = 0.0
    ocr_confidence: float = 0.0
    rotation: int = 0


@dataclass
class ParsedPageIR:
    """单页解析结果 (Phase 1 输出)。"""
    page_no: int = 0
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageInfo] = field(default_factory=list)
    raw_text: str = ""
    metadata: PageMetadata = field(default_factory=PageMetadata)
    reading_order: list[int] = field(default_factory=list)
    text_coverage: float = 0.0
    parser_backend: str = ""


@dataclass
class FeatureVector:
    """结构化特征向量 (Phase 3 输出)。"""
    text_density: float = 0.0
    image_density: float = 0.0
    table_area_ratio: float = 0.0
    avg_font_size: float = 0.0
    has_price_pattern: bool = False
    has_model_pattern: bool = False
    text_block_count: int = 0
    image_count: int = 0
    table_count: int = 0
    layout_complexity: float = 0.0  # 0-1

    def to_prompt_context(self) -> str:
        parts = [
            f"text_density={self.text_density:.2f}",
            f"images={self.image_count}",
            f"tables={self.table_count}",
        ]
        if self.has_price_pattern:
            parts.append("has_prices")
        if self.has_model_pattern:
            parts.append("has_model_numbers")
        return ", ".join(parts)


@dataclass
class ClassifyResult:
    """页面分类结果 (Phase 5 输出)。"""
    page_type: str = "B"  # A(table) | B(mixed) | C(image-heavy) | D(blank/toc)
    layout_type: str = "freeform"  # grid | table | list | freeform | single_product
    confidence: float = 0.0
    raw_response: str = ""


@dataclass
class SKUBoundary:
    """SKU 边界 (两阶段 Phase 6 Step 1)。"""
    boundary_id: int = 0
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    text_content: str = ""
    confidence: float = 0.0


@dataclass
class SKUResult:
    """SKU 提取结果 (Phase 6 输出)。"""
    sku_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    source_bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    validity: str = "valid"  # valid | invalid
    confidence: float = 0.0
    extraction_method: str = ""  # two_stage | single_stage | table_rule | final_fallback
    raw_response: str = ""
    product_id: str = ""         # 所属产品组 ID（同一产品的多个 SKU 变体共享）
    variant_label: str = ""      # 变体描述（如 "双人位"、"红色"）
    has_own_image: bool = True   # 表格行是否有独立图片单元格（False=合并共享上行图片）


@dataclass
class BindingCandidate:
    """绑定候选。"""
    image_id: str = ""
    confidence: float = 0.0
    method: str = "spatial_proximity"


@dataclass
class BindingResult:
    """SKU-图片绑定结果。"""
    sku_id: str = ""
    image_id: str | None = None
    confidence: float = 0.0
    method: str = "spatial_proximity"
    is_ambiguous: bool = False
    candidates: list[BindingCandidate] = field(default_factory=list)
    rank: int = 1


@dataclass
class ValidationIssue:
    """校验问题。"""
    rule: str = ""
    severity: str = "warning"  # info | warning | error
    message: str = ""
    context: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """一致性校验结果。"""
    issues: list[ValidationIssue] = field(default_factory=list)
    has_errors: bool = False
    has_warnings: bool = False


@dataclass
class PageResult:
    """单页处理最终结果 (PageProcessor 输出)。"""
    status: str = "AI_COMPLETED"  # AI_COMPLETED | SKIPPED | AI_FAILED | HUMAN_QUEUED
    page_type: str | None = None
    needs_review: bool = False
    skus: list[SKUResult] = field(default_factory=list)
    images: list[ImageInfo] = field(default_factory=list)
    bindings: list[BindingResult] = field(default_factory=list)
    validation: ValidationResult | None = None
    classification_confidence: float = 0.0
    extraction_method: str | None = None
    llm_model_used: str | None = None
    page_confidence: float = 0.0
    fallback_reason: str | None = None
    degrade_reason: str | None = None
    error: str | None = None
    screenshot: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "page_type": self.page_type,
            "needs_review": self.needs_review,
            "sku_count": len(self.skus),
            "image_count": len(self.images),
            "binding_count": len(self.bindings),
            "extraction_method": self.extraction_method,
            "fallback_reason": self.fallback_reason,
        }


@dataclass
class PageChunk:
    """分片信息。"""
    chunk_id: int = 0
    pages: list[int] = field(default_factory=list)
    boundary_overlap: int = 0
