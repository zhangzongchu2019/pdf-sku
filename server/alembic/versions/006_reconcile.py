"""reconcile: restore missing revision 006

Revision ID: 006
Revises: 005
Create Date: 2026-03-10 00:00:00.000000

NOTE: The database was already migrated to revision 006 but the migration
file was lost. This file re-establishes the revision marker so Alembic
can locate it. No schema changes are applied.
"""
from typing import Sequence, Union
from alembic import op

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
