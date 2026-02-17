"""核心 DTO。对齐: 接口契约 V1.2 + OpenAPI V2.0"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from pdf_sku.common.enums import *

class RawMetrics(BaseModel):
    total_pages: int = 0; blank_page_count: int = 0; blank_rate: float = 0.0
    ocr_rate: float = 0.0; image_count: int = 0

class PrescanResult(BaseModel):
    total_pages: int = 0; blank_pages: list[int] = Field(default_factory=list)
    encrypted: bool = False; has_js: bool = False
    raw_metrics: RawMetrics | None = None

class SamplingInfo(BaseModel):
    sampled_pages: list[int] = Field(default_factory=list); sample_ratio: float = 1.0

class EvaluationDTO(BaseModel):
    file_hash: str; config_version: str; doc_confidence: float
    route: RouteDecision; route_reason: str | None = None
    degrade_reason: str | None = None; dimension_scores: dict = Field(default_factory=dict)
    prescan: PrescanResult = Field(default_factory=PrescanResult)
    sampling: SamplingInfo = Field(default_factory=SamplingInfo)
    page_evaluations: dict[str, float] = Field(default_factory=dict)
    model_used: str = ""; prompt_version: str | None = None
    thresholds_used: dict | None = None; evaluated_at: datetime | None = None

class SKUResultDTO(BaseModel):
    sku_id: str; attributes: dict = Field(default_factory=dict)
    validity: SKUValidity = SKUValidity.VALID; confidence: float = 0.0

class ImageResultDTO(BaseModel):
    image_id: str; role: str = ""; path: str = ""
    short_edge: int = 0; search_eligible: bool = False
    image_hash: str | None = None; is_duplicate: bool = False

class BindingResultDTO(BaseModel):
    sku_id: str; image_id: str; method: BindingMethod = BindingMethod.SPATIAL_PROXIMITY
    confidence: float = 0.0; is_ambiguous: bool = False; rank: int = 1

class PageResultDTO(BaseModel):
    status: str = ""; page_type: str | None = None; needs_review: bool = False
    skus: list[SKUResultDTO] = Field(default_factory=list)
    images: list[ImageResultDTO] = Field(default_factory=list)
    bindings: list[BindingResultDTO] = Field(default_factory=list)

class ImportResultDTO(BaseModel):
    sku_id: str; success: bool = False; downstream_id: str | None = None
    import_confirmation: ImportConfirmation = ImportConfirmation.PENDING

class SyncResultDTO(BaseModel):
    job_id: str; synced_skus: int = 0; failed_skus: int = 0

class ThresholdSet(BaseModel):
    A: float = 0.85; B: float = 0.45; PV: float = 0.65

class ThresholdProfileDTO(BaseModel):
    profile_id: str; version: str; previous_version: str | None = None
    category: str | None = None; industry: str | None = None
    thresholds: ThresholdSet = Field(default_factory=ThresholdSet)
    confidence_weights: dict = Field(default_factory=dict)
    sku_validity_mode: str = "strict"; is_active: bool = True

class ImpactPreviewDTO(BaseModel):
    sample_period_days: int = 7; current_auto_rate: float = 0.0
    predicted_auto_rate: float = 0.0; affected_jobs_estimate: int = 0

class BatchResultDTO(BaseModel):
    total: int = 0; succeeded: int = 0; failed: int = 0
    errors: list[dict] = Field(default_factory=list)

class PaginationMeta(BaseModel):
    page: int = 1; size: int = 20; total: int = 0; total_pages: int = 0

class ErrorResponse(BaseModel):
    code: str; message: str; details: dict | None = None
    severity: ErrorSeverity = ErrorSeverity.ERROR

# SSE Event DTOs
class SSEPageCompletedDTO(BaseModel):
    page_no: int; status: str; confidence: float | None = None; sku_count: int = 0
class SSEJobCompletedDTO(BaseModel):
    job_id: str; status: str; total_skus: int = 0; total_images: int = 0; duration_sec: float = 0.0
class SSEJobFailedDTO(BaseModel):
    job_id: str; error_code: str; error_message: str
class SSEHumanNeededDTO(BaseModel):
    job_id: str; task_count: int; priority: str
class SSESlaEscalatedDTO(BaseModel):
    task_id: str; sla_level: str; deadline: datetime
