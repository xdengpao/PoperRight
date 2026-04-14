"""create adjustment_factor table

Revision ID: 005
Revises: 004
Create Date: 2024-01-01 00:00:00.000000

创建复权因子表，存储前复权/后复权因子数据。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 adjustment_factor 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS adjustment_factor (
            symbol      VARCHAR(10)    NOT NULL,
            trade_date  DATE           NOT NULL,
            adj_type    SMALLINT       NOT NULL,
            adj_factor  NUMERIC(18,8)  NOT NULL,
            PRIMARY KEY (symbol, trade_date, adj_type)
        )
    """)

    # 2. 创建索引，支持按股票代码和复权类型查询
    op.execute("CREATE INDEX IF NOT EXISTS ix_adj_factor_symbol_type ON adjustment_factor (symbol, adj_type)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS adjustment_factor CASCADE")
