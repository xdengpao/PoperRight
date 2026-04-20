"""create risk_event_log table

Revision ID: 016
Revises: 015
Create Date: 2026-06-01 00:00:00.000000

新增 risk_event_log 表，用于持久化风控事件历史记录。

需求 10：风控事件历史日志
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS risk_event_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            event_type VARCHAR(30) NOT NULL,
            symbol VARCHAR(10),
            rule_name VARCHAR(100) NOT NULL,
            trigger_value DOUBLE PRECISION NOT NULL,
            threshold DOUBLE PRECISION NOT NULL,
            result VARCHAR(20) NOT NULL,
            triggered_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_risk_event_log_user_triggered
        ON risk_event_log (user_id, triggered_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_risk_event_log_event_type
        ON risk_event_log (event_type)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_risk_event_log_symbol
        ON risk_event_log (symbol)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS risk_event_log")
