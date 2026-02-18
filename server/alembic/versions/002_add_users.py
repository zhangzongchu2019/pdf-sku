"""add users table

Revision ID: 002
Revises: 001
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(128), nullable=False, server_default=''),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='uploader'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('merchant_id', sa.Text(), nullable=True),
        sa.Column('specialties', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_username', 'users', ['username'])


def downgrade() -> None:
    op.drop_index('idx_users_username', table_name='users')
    op.drop_index('idx_users_role', table_name='users')
    op.drop_table('users')
