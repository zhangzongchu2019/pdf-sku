"""add_owner_id_to_pdf_jobs

Revision ID: 005
Revises: e04905bbfd43
Create Date: 2026-03-05 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pdf_jobs',
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('idx_pdf_jobs_owner_id', 'pdf_jobs', ['owner_id'])
    op.create_foreign_key(
        'fk_pdf_jobs_owner_id',
        'pdf_jobs', 'users',
        ['owner_id'], ['user_id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_pdf_jobs_owner_id', 'pdf_jobs', type_='foreignkey')
    op.drop_index('idx_pdf_jobs_owner_id', table_name='pdf_jobs')
    op.drop_column('pdf_jobs', 'owner_id')
