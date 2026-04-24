"""修复 stock_st 表列名：st_date → trade_date, st_type → type, 新增 type_name

ORM 模型定义的列名与数据库实际列名不一致，导致 INSERT 失败。

Revision ID: 20260424_0010
"""

from alembic import op

revision = "20260424_0010"
down_revision = "20260423_1440"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 重命名列
    op.execute('ALTER TABLE stock_st RENAME COLUMN "st_date" TO "trade_date"')
    op.execute('ALTER TABLE stock_st RENAME COLUMN "st_type" TO "type"')
    # 删除旧的 is_st 列（ORM 模型中没有）
    op.execute('ALTER TABLE stock_st DROP COLUMN IF EXISTS "is_st"')
    # 新增 type_name 列
    op.execute('ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS "type_name" VARCHAR(50)')
    # 重建唯一约束（列名变了）
    op.execute('ALTER TABLE stock_st DROP CONSTRAINT IF EXISTS "uq_stock_st"')
    op.execute(
        'ALTER TABLE stock_st ADD CONSTRAINT "uq_stock_st_ts_code_trade_date" '
        'UNIQUE ("ts_code", "trade_date")'
    )


def downgrade() -> None:
    op.execute('ALTER TABLE stock_st DROP CONSTRAINT IF EXISTS "uq_stock_st_ts_code_trade_date"')
    op.execute('ALTER TABLE stock_st RENAME COLUMN "trade_date" TO "st_date"')
    op.execute('ALTER TABLE stock_st RENAME COLUMN "type" TO "st_type"')
    op.execute('ALTER TABLE stock_st DROP COLUMN IF EXISTS "type_name"')
    op.execute('ALTER TABLE stock_st ADD COLUMN IF NOT EXISTS "is_st" VARCHAR(2)')
    op.execute(
        'ALTER TABLE stock_st ADD CONSTRAINT "uq_stock_st" '
        'UNIQUE ("ts_code", "st_date")'
    )
