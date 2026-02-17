"""initial schema - auto-generated from ORM models

Revision ID: 001
Revises:
Create Date: 2026-02-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('annotation_examples',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_type', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('input_context', sa.Text(), nullable=True),
        sa.Column('output_json', postgresql.JSONB(), nullable=False),
        sa.Column('quality_score', sa.Float(), nullable=False),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )


    op.create_table('annotator_profiles',
        sa.Column('annotator_id', sa.Text(), nullable=False),
        sa.Column('avg_duration_sec', sa.Float(), nullable=False),
        sa.Column('accuracy_rate', sa.Float(), nullable=False),
        sa.Column('total_tasks', sa.Integer(), nullable=False),
        sa.Column('specialties', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('annotator_id'),
    )


    op.create_table('calibration_records',
        sa.Column('calibration_id', sa.Uuid(), nullable=False),
        sa.Column('profile_id', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('ai_correction_rate', sa.Float(), nullable=True),
        sa.Column('human_could_be_ai_rate', sa.Float(), nullable=True),
        sa.Column('route_accuracy', sa.Float(), nullable=True),
        sa.Column('suggested_adjustments', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('applied', sa.Boolean(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('calibration_id'),
    )


    op.create_table('custom_attr_upgrades',
        sa.Column('upgrade_id', sa.Uuid(), nullable=False),
        sa.Column('attr_name', sa.Text(), nullable=False),
        sa.Column('suggested_type', sa.Text(), nullable=False),
        sa.Column('merchant_id', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('source_feedback_count', sa.Integer(), nullable=False),
        sa.Column('sample_annotations', postgresql.ARRAY(sa.Uuid()), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('reviewer', sa.Text(), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('applied_config_version', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('upgrade_id'),
    )

    op.create_index('idx_upgrades_status', 'custom_attr_upgrades', ['status'])

    op.create_table('eval_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('golden_set_id', sa.Text(), nullable=False),
        sa.Column('config_version', sa.Text(), nullable=False),
        sa.Column('sku_precision', sa.Float(), nullable=True),
        sa.Column('sku_recall', sa.Float(), nullable=True),
        sa.Column('sku_f1', sa.Float(), nullable=True),
        sa.Column('binding_accuracy', sa.Float(), nullable=True),
        sa.Column('human_intervention_rate', sa.Float(), nullable=True),
        sa.Column('report_data', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )


    op.create_table('import_dedup',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dedup_key', sa.Text(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('import_status', sa.Text(), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )


    op.create_table('pdf_jobs',
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('source_file', sa.Text(), nullable=False),
        sa.Column('file_hash', sa.Text(), nullable=False),
        sa.Column('merchant_id', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('industry', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.Text(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('user_status', sa.Text(), nullable=False),
        sa.Column('action_hint', sa.Text(), nullable=True),
        sa.Column('route', sa.Text(), nullable=True),
        sa.Column('degrade_reason', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('frozen_config_version', sa.Text(), nullable=True),
        sa.Column('worker_id', sa.Text(), nullable=True),
        sa.Column('checkpoint_page', sa.Integer(), nullable=False),
        sa.Column('checkpoint_skus', sa.Integer(), nullable=False),
        sa.Column('checkpoint_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('output_base_url', sa.Text(), nullable=True),
        sa.Column('completion_source', sa.Text(), nullable=True),
        sa.Column('total_pages', sa.Integer(), nullable=False),
        sa.Column('blank_pages', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('ai_pages', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('human_pages', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('skipped_pages', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('failed_pages', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('total_skus', sa.Integer(), nullable=False),
        sa.Column('total_images', sa.Integer(), nullable=False),
        sa.Column('processing_trace', postgresql.JSONB(), nullable=True),
        sa.Column('token_consumption', postgresql.JSONB(), nullable=False),
        sa.Column('eval_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eval_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('process_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('process_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('parse_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('job_id'),
    )

    op.create_index('idx_jobs_created', 'pdf_jobs', ['created_at'])
    op.create_index('idx_jobs_status', 'pdf_jobs', ['status'])
    op.create_index('idx_jobs_user_status', 'pdf_jobs', ['user_status'])
    op.create_index('idx_jobs_merchant', 'pdf_jobs', ['merchant_id'])
    op.create_index('idx_jobs_file_hash', 'pdf_jobs', ['file_hash'])
    op.create_index('idx_jobs_worker', 'pdf_jobs', ['worker_id'])

    op.create_table('state_transitions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=False),
        sa.Column('entity_id', sa.Text(), nullable=False),
        sa.Column('from_status', sa.Text(), nullable=True),
        sa.Column('to_status', sa.Text(), nullable=False),
        sa.Column('trigger', sa.Text(), nullable=True),
        sa.Column('operator', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('idx_transitions_entity', 'state_transitions', ['entity_type', 'entity_id'])

    op.create_table('threshold_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.Text(), nullable=False),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('previous_version', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('industry', sa.Text(), nullable=True),
        sa.Column('thresholds', postgresql.JSONB(), nullable=False),
        sa.Column('confidence_weights', postgresql.JSONB(), nullable=False),
        sa.Column('prescan_rules', postgresql.JSONB(), nullable=False),
        sa.Column('classification_thresholds', postgresql.JSONB(), nullable=False),
        sa.Column('sku_validity_mode', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.Text(), nullable=True),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


    op.create_table('worker_heartbeats',
        sa.Column('worker_id', sa.Text(), nullable=False),
        sa.Column('hostname', sa.Text(), nullable=False),
        sa.Column('pod_ip', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('active_job_ids', postgresql.ARRAY(sa.Uuid()), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('version', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('worker_id'),
    )

    op.create_index('idx_heartbeats_status', 'worker_heartbeats', ['status', 'last_heartbeat'])

    op.create_table('evaluations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=True),
        sa.Column('file_hash', sa.Text(), nullable=False),
        sa.Column('config_version', sa.Text(), nullable=False),
        sa.Column('doc_confidence', sa.Float(), nullable=False),
        sa.Column('route', sa.Text(), nullable=False),
        sa.Column('route_reason', sa.Text(), nullable=True),
        sa.Column('degrade_reason', sa.Text(), nullable=True),
        sa.Column('dimension_scores', postgresql.JSONB(), nullable=False),
        sa.Column('weights_snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('thresholds_used', postgresql.JSONB(), nullable=True),
        sa.Column('prescan', postgresql.JSONB(), nullable=False),
        sa.Column('sampling', postgresql.JSONB(), nullable=False),
        sa.Column('page_evaluations', postgresql.JSONB(), nullable=True),
        sa.Column('model_used', sa.Text(), nullable=False),
        sa.Column('prompt_version', sa.Text(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )


    op.create_table('human_tasks',
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('priority', sa.Text(), nullable=False),
        sa.Column('assigned_to', sa.Text(), nullable=True),
        sa.Column('locked_by', sa.Text(), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rework_count', sa.Integer(), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('task_id'),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )

    op.create_index('idx_tasks_job', 'human_tasks', ['job_id'])
    op.create_index('idx_tasks_status', 'human_tasks', ['status'])

    op.create_table('images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('image_id', sa.Text(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('bbox', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('extracted_path', sa.Text(), nullable=False),
        sa.Column('format', sa.Text(), nullable=False),
        sa.Column('resolution', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('short_edge', sa.Integer(), nullable=True),
        sa.Column('quality_grade', sa.Text(), nullable=True),
        sa.Column('file_size_kb', sa.Integer(), nullable=True),
        sa.Column('search_eligible', sa.Boolean(), nullable=True),
        sa.Column('is_fragmented', sa.Boolean(), nullable=False),
        sa.Column('image_hash', sa.Text(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False),
        sa.Column('dedup_kept_version', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('parser_backend', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )

    op.create_index('idx_images_job', 'images', ['job_id'])

    op.create_table('pages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('attempt_no', sa.Integer(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('worker_id', sa.Text(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('processed_by', sa.Text(), nullable=True),
        sa.Column('import_confirmation', sa.Text(), nullable=False),
        sa.Column('page_confidence', sa.Float(), nullable=True),
        sa.Column('page_type', sa.Text(), nullable=True),
        sa.Column('layout_type', sa.Text(), nullable=True),
        sa.Column('classification_confidence', sa.Float(), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=False),
        sa.Column('table_continuation_from', sa.Integer(), nullable=True),
        sa.Column('validation_errors', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('parser_backend', sa.Text(), nullable=False),
        sa.Column('features', postgresql.JSONB(), nullable=True),
        sa.Column('product_description', postgresql.JSONB(), nullable=True),
        sa.Column('screenshot_path', sa.Text(), nullable=True),
        sa.Column('parse_time_ms', sa.Integer(), nullable=True),
        sa.Column('ocr_time_ms', sa.Integer(), nullable=True),
        sa.Column('llm_time_ms', sa.Integer(), nullable=True),
        sa.Column('sku_count', sa.Integer(), nullable=False),
        sa.Column('extraction_method', sa.Text(), nullable=True),
        sa.Column('llm_model_used', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )

    op.create_index('idx_pages_job_status', 'pages', ['job_id', 'status'])

    op.create_table('sku_image_bindings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sku_id', sa.Text(), nullable=False),
        sa.Column('image_id', sa.Text(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('image_role', sa.Text(), nullable=True),
        sa.Column('binding_method', sa.Text(), nullable=True),
        sa.Column('binding_confidence', sa.Float(), nullable=True),
        sa.Column('is_ambiguous', sa.Boolean(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('is_latest', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )


    op.create_table('skus',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sku_id', sa.Text(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('attempt_no', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('validity', sa.Text(), nullable=False),
        sa.Column('superseded', sa.Boolean(), nullable=False),
        sa.Column('attributes', postgresql.JSONB(), nullable=False),
        sa.Column('custom_attributes', postgresql.JSONB(), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('source_bbox', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('attribute_source', sa.Text(), nullable=False),
        sa.Column('import_status', sa.Text(), nullable=False),
        sa.Column('import_confirmation', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )

    op.create_index('idx_skus_status', 'skus', ['status'])
    op.create_index('idx_skus_job', 'skus', ['job_id'])

    op.create_table('annotations',
        sa.Column('annotation_id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=True),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('annotator', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('annotated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('annotation_id'),
        sa.ForeignKeyConstraint(['task_id'], ['human_tasks.task_id']),
        sa.ForeignKeyConstraint(['job_id'], ['pdf_jobs.job_id']),
    )

    op.create_index('idx_annotations_job', 'annotations', ['job_id'])


def downgrade() -> None:
    op.drop_table('annotations')
    op.drop_table('skus')
    op.drop_table('sku_image_bindings')
    op.drop_table('pages')
    op.drop_table('images')
    op.drop_table('human_tasks')
    op.drop_table('evaluations')
    op.drop_table('worker_heartbeats')
    op.drop_table('threshold_profiles')
    op.drop_table('state_transitions')
    op.drop_table('pdf_jobs')
    op.drop_table('import_dedup')
    op.drop_table('eval_reports')
    op.drop_table('custom_attr_upgrades')
    op.drop_table('calibration_records')
    op.drop_table('annotator_profiles')
    op.drop_table('annotation_examples')
