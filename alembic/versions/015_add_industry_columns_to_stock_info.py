"""add industry_code and industry_name columns to stock_info

Revision ID: 015
Revises: 014
Create Date: 2026-06-01 00:00:00.000000

为 stock_info 表新增申万一级行业分类字段：
- industry_code: 申万一级行业代码（VARCHAR(10)，可空）
- industry_name: 申万一级行业名称（VARCHAR(50)，可空）

需求 6：板块仓位使用真实行业分类
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE stock_info
        ADD COLUMN IF NOT EXISTS industry_code VARCHAR(10) DEFAULT NULL
    """)
    op.execute("""
        ALTER TABLE stock_info
        ADD COLUMN IF NOT EXISTS industry_name VARCHAR(50) DEFAULT NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE stock_info DROP COLUMN IF EXISTS industry_name")
    op.execute("ALTER TABLE stock_info DROP COLUMN IF EXISTS industry_code")
