"""add extra_info to tushare_import_log

Revision ID: 20260422_1200
Revises: 20260422_1100
Create Date: 2026-04-22

为 tushare_import_log 表新增 extra_info 列，用于存储 JSON 格式的分批统计信息
（batch_mode、total_chunks、success_chunks、truncation_count、truncation_details）。
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260422_1200"
down_revision = "20260422_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tushare_import_log",
        sa.Column("extra_info", sa.String(2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tushare_import_log", "extra_info")
