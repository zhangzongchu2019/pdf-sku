"""pipeline_v2 内部数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field

from pdf_sku.pipeline.ir import ParsedPageIR


@dataclass
class DocumentHints:
    """文档级弱先验。"""

    document_theme: str = ""
    ignore_hints: list[str] = field(default_factory=list)

    def has_hints(self) -> bool:
        return bool(self.document_theme or self.ignore_hints)


@dataclass
class TableSchema:
    """首表头派生出的表格 schema。"""

    header_source_page: int = 1
    raw_headers: list[str] = field(default_factory=list)
    normalized_headers: list[str] = field(default_factory=list)
    column_centers: list[float] = field(default_factory=list)
    table_schema_id: str = ""


@dataclass
class TableDocumentContext:
    """作业级表格上下文。"""

    job_id: str = ""
    table_pdf_mode: bool = False
    schema: TableSchema | None = None
    first_page_raw: ParsedPageIR | None = None
    document_hints: DocumentHints = field(default_factory=DocumentHints)


@dataclass
class TableRowRecord:
    """结构化后的单行表格记录。"""

    row_index: int = 0
    values: dict[str, str] = field(default_factory=dict)
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    source: str = "table_rows"


@dataclass
class EvidenceObject:
    """页面原子对象。"""

    object_id: str = ""
    object_type: str = ""  # text_block | ocr_block | image_block | layout_block
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    text: str = ""
    label: str = ""
    source: str = ""
    confidence: float = 1.0


@dataclass
class PageEvidence:
    """普通页证据表示。"""

    page_no: int = 0
    page_width: float = 0.0
    page_height: float = 0.0
    objects: list[EvidenceObject] = field(default_factory=list)
    raw: ParsedPageIR | None = None


@dataclass
class RegionProposal:
    """区域提议。"""

    region_id: str = ""
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    region_type: str = "product_unit"
    proposal_source: str = "heuristic_v1"
    score: float = 0.0
    member_object_ids: list[str] = field(default_factory=list)
    reason: str = ""
