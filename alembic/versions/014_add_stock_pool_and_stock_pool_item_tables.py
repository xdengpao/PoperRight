"""add stock_pool and stock_pool_item tables

Revision ID: 014
Revises: 013
Create Date: 2026-05-01 00:00:00.000000

创建选股池相关表：
- stock_pool：选股池元数据（含 uq_stock_pool_user_name 唯一约束）
- stock_pool_item：选股池条目（联合主键 pool_id + symbol，ON DELETE CASCADE 外键）

需求 3：创建和管理自选股池
需求 6：选股池数据持久化
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. stock_pool — 选股池元数据
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_pool (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL,
            name        VARCHAR(50) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # 同一用户下选股池名称唯一
    op.execute("""
        ALTER TABLE stock_pool
        ADD CONSTRAINT uq_stock_pool_user_name
        UNIQUE (user_id, name)
    """)

    # ------------------------------------------------------------------
    # 2. stock_pool_item — 选股池条目（联合主键 + CASCADE 外键）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_pool_item (
            pool_id     UUID NOT NULL REFERENCES stock_pool(id) ON DELETE CASCADE,
            symbol      VARCHAR(10) NOT NULL,
            added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (pool_id, symbol)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stock_pool_item CASCADE")
    op.execute("DROP TABLE IF EXISTS stock_pool CASCADE")
