"""fix sector_info.sector_type nullable

Revision ID: 20260422_1050
Revises: 20260422_0010
Create Date: 2026-04-22

sector_info.sector_type 应为 nullable，与 ORM 模型一致。
东方财富概念板块（dc_index）等数据源不一定返回 sector_type 字段。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260422_1050"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE sector_info ALTER COLUMN sector_type DROP NOT NULL"
    )


def downgrade() -> None:
    # 先将 NULL 值填充为默认值，再恢复 NOT NULL 约束
    op.execute(
        "UPDATE sector_info SET sector_type = 'CONCEPT' WHERE sector_type IS NULL"
    )
    op.execute(
        "ALTER TABLE sector_info ALTER COLUMN sector_type SET NOT NULL"
    )
