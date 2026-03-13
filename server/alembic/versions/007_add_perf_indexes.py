"""add performance indexes

Revision ID: 007
Revises: 006
Create Date: 2026-03-13 00:00:00.000000

性能优化: 补充缺失的高频查询索引。
- sku_image_bindings.sku_id: 导出时 IN(sku_ids) 查询
- sku_image_bindings.image_id: 按图片反查绑定
- images.page_number: 按页查询图片
"""
from typing import Sequence, Union
from alembic import op

revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('idx_sku_bindings_sku_id', 'sku_image_bindings', ['sku_id'])
    op.create_index('idx_sku_bindings_image_id', 'sku_image_bindings', ['image_id'])
    op.create_index('idx_images_job_page', 'images', ['job_id', 'page_number'])


def downgrade() -> None:
    op.drop_index('idx_images_job_page', 'images')
    op.drop_index('idx_sku_bindings_image_id', 'sku_image_bindings')
    op.drop_index('idx_sku_bindings_sku_id', 'sku_image_bindings')
