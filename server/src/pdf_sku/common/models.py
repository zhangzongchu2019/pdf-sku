"""
SQLAlchemy ORM 模型 — 对齐 DDL V1.2（17 张表）
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, Index, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ───────────────────────── 用户/认证 ─────────────────────────

class User(Base):
    """用户表 — 支持 uploader / annotator / admin 三种角色。"""
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="uploader")  # uploader | annotator | admin
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    merchant_id: Mapped[str | None] = mapped_column(Text)  # uploader 关联的商户
    specialties: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # annotator 擅长品类
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_username", "username"),
    )


# ───────────────────────── 业务模型 ─────────────────────────

class PDFJob(Base):
    __tablename__ = "pdf_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 状态
    status: Mapped[str] = mapped_column(Text, nullable=False, default="UPLOADED")
    user_status: Mapped[str] = mapped_column(Text, nullable=False, default="processing")
    action_hint: Mapped[str | None] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(Text)
    degrade_reason: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    frozen_config_version: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(Text)

    # Checkpoint
    checkpoint_page: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint_skus: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    output_base_url: Mapped[str | None] = mapped_column(Text)
    completion_source: Mapped[str | None] = mapped_column(Text)

    # 页面统计
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blank_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    ai_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    human_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    skipped_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    failed_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    total_skus: Mapped[int] = mapped_column(Integer, default=0)
    total_images: Mapped[int] = mapped_column(Integer, default=0)

    # 追踪
    processing_trace: Mapped[dict | None] = mapped_column(JSONB)
    token_consumption: Mapped[dict] = mapped_column(
        JSONB, default=lambda: {"eval_tokens": 0, "process_tokens": 0, "total_api_calls": 0}
    )

    # 时间线
    eval_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eval_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    pages: Mapped[list[Page]] = relationship(back_populates="job", lazy="selectin")
    evaluations_rel: Mapped[list[Evaluation]] = relationship(back_populates="job", lazy="noload")

    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_user_status", "user_status"),
        Index("idx_jobs_merchant", "merchant_id"),
        Index("idx_jobs_file_hash", "file_hash"),
        Index("idx_jobs_worker", "worker_id"),
        Index("idx_jobs_created", "created_at"),
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"))
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    config_version: Mapped[str] = mapped_column(Text, nullable=False)
    doc_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    route_reason: Mapped[str | None] = mapped_column(Text)
    degrade_reason: Mapped[str | None] = mapped_column(Text)
    dimension_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    weights_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    thresholds_used: Mapped[dict | None] = mapped_column(JSONB)
    prescan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sampling: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    page_evaluations: Mapped[dict | None] = mapped_column(JSONB)
    model_used: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_version: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[PDFJob | None] = relationship(back_populates="evaluations_rel")

    __table_args__ = (UniqueConstraint("file_hash", "config_version"),)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    worker_id: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_by: Mapped[str | None] = mapped_column(Text)
    import_confirmation: Mapped[str] = mapped_column(Text, default="not_imported")
    page_confidence: Mapped[float | None] = mapped_column(Float)
    page_type: Mapped[str | None] = mapped_column(Text)
    layout_type: Mapped[str | None] = mapped_column(Text)
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    table_continuation_from: Mapped[int | None] = mapped_column(Integer)
    validation_errors: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    parser_backend: Mapped[str] = mapped_column(Text, default="legacy")
    features: Mapped[dict | None] = mapped_column(JSONB)
    product_description: Mapped[dict | None] = mapped_column(JSONB)
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    parse_time_ms: Mapped[int | None] = mapped_column(Integer)
    ocr_time_ms: Mapped[int | None] = mapped_column(Integer)
    llm_time_ms: Mapped[int | None] = mapped_column(Integer)
    sku_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_method: Mapped[str | None] = mapped_column(Text)
    llm_model_used: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job: Mapped[PDFJob] = relationship(back_populates="pages")

    __table_args__ = (
        UniqueConstraint("job_id", "page_number", "attempt_no"),
        Index("idx_pages_job_status", "job_id", "status"),
    )


class SKU(Base):
    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    validity: Mapped[str] = mapped_column(Text, nullable=False, default="valid")
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    custom_attributes: Mapped[list] = mapped_column(JSONB, default=list)
    source_text: Mapped[str | None] = mapped_column(Text)
    source_bbox: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    attribute_source: Mapped[str] = mapped_column(Text, default="AI_EXTRACTED")
    import_status: Mapped[str] = mapped_column(Text, default="pending")
    import_confirmation: Mapped[str] = mapped_column(Text, default="pending")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="EXTRACTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_skus_job", "job_id"), Index("idx_skus_status", "status"))


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    extracted_path: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, default="jpg")
    resolution: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    short_edge: Mapped[int | None] = mapped_column(Integer)
    quality_grade: Mapped[str | None] = mapped_column(Text)
    file_size_kb: Mapped[int | None] = mapped_column(Integer)
    search_eligible: Mapped[bool | None] = mapped_column(Boolean)
    is_fragmented: Mapped[bool] = mapped_column(Boolean, default=False)
    image_hash: Mapped[str | None] = mapped_column(Text)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    dedup_kept_version: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="EXTRACTED")
    parser_backend: Mapped[str] = mapped_column(Text, default="legacy")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_images_job", "job_id"),)


class SKUImageBinding(Base):
    __tablename__ = "sku_image_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(Text, nullable=False)
    image_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"), nullable=False)
    image_role: Mapped[str | None] = mapped_column(Text)
    binding_method: Mapped[str | None] = mapped_column(Text)
    binding_confidence: Mapped[float | None] = mapped_column(Float)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    rank: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("sku_id", "image_id"),)


class HumanTask(Base):
    __tablename__ = "human_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="CREATED")
    priority: Mapped[str] = mapped_column(Text, default="NORMAL")
    assigned_to: Mapped[str | None] = mapped_column(Text)
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rework_count: Mapped[int] = mapped_column(Integer, default=0)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timeout_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now() + interval '4 hours'"))
    result: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index("idx_tasks_status", "status"), Index("idx_tasks_job", "job_id"))


class Annotation(Base):
    __tablename__ = "annotations"

    annotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("human_tasks.task_id"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pdf_jobs.job_id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    annotator: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    annotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_annotations_job", "job_id"),)


class StateTransition(Base):
    __tablename__ = "state_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str | None] = mapped_column(Text)
    operator: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_transitions_entity", "entity_type", "entity_id"),)


class AnnotationExample(Base):
    __tablename__ = "annotation_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    input_context: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnnotatorProfile(Base):
    __tablename__ = "annotator_profiles"

    annotator_id: Mapped[str] = mapped_column(Text, primary_key=True)
    avg_duration_sec: Mapped[float] = mapped_column(Float, default=300.0)
    accuracy_rate: Mapped[float] = mapped_column(Float, default=0.8)
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    specialties: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ThresholdProfileModel(Base):
    __tablename__ = "threshold_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    previous_version: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {"A": 0.85, "B": 0.45, "PV": 0.65})
    confidence_weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prescan_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    classification_thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sku_validity_mode: Mapped[str] = mapped_column(Text, default="strict")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(Text)
    change_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("profile_id", "version"),)


class CalibrationRecord(Base):
    __tablename__ = "calibration_records"

    calibration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, default="THRESHOLD")
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_correction_rate: Mapped[float | None] = mapped_column(Float)
    human_could_be_ai_rate: Mapped[float | None] = mapped_column(Float)
    route_accuracy: Mapped[float | None] = mapped_column(Float)
    suggested_adjustments: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="PENDING")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalReport(Base):
    __tablename__ = "eval_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    golden_set_id: Mapped[str] = mapped_column(Text, nullable=False)
    config_version: Mapped[str] = mapped_column(Text, nullable=False)
    sku_precision: Mapped[float | None] = mapped_column(Float)
    sku_recall: Mapped[float | None] = mapped_column(Float)
    sku_f1: Mapped[float | None] = mapped_column(Float)
    binding_accuracy: Mapped[float | None] = mapped_column(Float)
    human_intervention_rate: Mapped[float | None] = mapped_column(Float)
    report_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportDedup(Base):
    __tablename__ = "import_dedup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    import_status: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomAttrUpgrade(Base):
    __tablename__ = "custom_attr_upgrades"

    upgrade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attr_name: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_type: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_id: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    source_feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_annotations: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    reviewer: Mapped[str | None] = mapped_column(Text)
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_config_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_upgrades_status", "status"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    hostname: Mapped[str] = mapped_column(Text, nullable=False)
    pod_ip: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    active_job_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ALIVE")
    version: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("idx_heartbeats_status", "status", "last_heartbeat"),)
