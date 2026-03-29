"""create money_flow table

Revision ID: 003
Revises: 002
Create Date: 2026-03-29 00:00:00.000000

创建 PostgreSQL 资金流向表 money_flow，
存储个股每日主力资金、北向资金、龙虎榜、大宗交易等数据。
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS money_flow (
            symbol              VARCHAR(10) NOT NULL,
            trade_date          DATE        NOT NULL,
            main_net_inflow     NUMERIC(18,2),
            main_inflow         NUMERIC(18,2),
            main_outflow        NUMERIC(18,2),
            main_net_inflow_pct NUMERIC(8,4),
            large_order_net     NUMERIC(18,2),
            large_order_ratio   NUMERIC(8,4),
            north_net_inflow    NUMERIC(18,2),
            north_hold_ratio    NUMERIC(8,4),
            on_dragon_tiger     BOOLEAN DEFAULT FALSE,
            dragon_tiger_net    NUMERIC(18,2),
            block_trade_amount  NUMERIC(18,2),
            block_trade_discount NUMERIC(8,4),
            bid_ask_ratio       NUMERIC(8,4),
            inner_outer_ratio   NUMERIC(8,4),
            updated_at          TIMESTAMPTZ,
            PRIMARY KEY (symbol, trade_date)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_money_flow_symbol ON money_flow (symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_money_flow_date ON money_flow (trade_date DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS money_flow CASCADE")
