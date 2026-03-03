"""fix sku_image_bindings unique constraint to include job_id

Revision ID: 004
Revises: e04905bbfd43
Create Date: 2026-03-03
"""
from alembic import op

revision = '004'
down_revision = 'e04905bbfd43'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除旧约束（只有 sku_id, image_id）
    op.drop_constraint('sku_image_bindings_sku_id_image_id_key', 'sku_image_bindings', type_='unique')
    # 新约束加入 job_id，允许同一文件被不同 job 绑定
    op.create_unique_constraint('uq_sku_image_job', 'sku_image_bindings', ['sku_id', 'image_id', 'job_id'])


def downgrade() -> None:
    op.drop_constraint('uq_sku_image_job', 'sku_image_bindings', type_='unique')
    op.create_unique_constraint('sku_image_bindings_sku_id_image_id_key', 'sku_image_bindings', ['sku_id', 'image_id'])
