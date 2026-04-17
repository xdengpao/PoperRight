"""add is_builtin and enabled_modules columns to strategy_template

Revision ID: 011
Revises: 010
Create Date: 2026-04-17 00:00:00.000000

ORM 模型 StrategyTemplate 新增了 is_builtin (BOOLEAN) 和
enabled_modules (JSONB) 两列，但建表迁移 002 中未包含。
本迁移补齐这两列。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE strategy_template
        ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT FALSE
    """)
    op.execute("""
        ALTER TABLE strategy_template
        ADD COLUMN IF NOT EXISTS enabled_modules JSONB NOT NULL DEFAULT '[]'::jsonb
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE strategy_template DROP COLUMN IF EXISTS enabled_modules")
    op.execute("ALTER TABLE strategy_template DROP COLUMN IF EXISTS is_builtin")
