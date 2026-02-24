"""add product grouping columns to skus

Revision ID: 003
Revises: 002
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('skus', sa.Column('product_id', sa.Text(), nullable=True))
    op.add_column('skus', sa.Column('variant_label', sa.Text(), nullable=True))
    op.create_index('idx_skus_product', 'skus', ['job_id', 'product_id'])


def downgrade() -> None:
    op.drop_index('idx_skus_product', table_name='skus')
    op.drop_column('skus', 'variant_label')
    op.drop_column('skus', 'product_id')
