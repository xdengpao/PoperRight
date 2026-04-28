"""新增实操模块数据表

创建 6 张表：trading_plan, candidate_stock, buy_record, plan_position, daily_checklist, market_profile_log
含索引、外键、联合唯一约束。

Revision ID: 20260428_0020
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID, TIMESTAMP

revision = "20260428_0020"
down_revision = "20260428_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # trading_plan
    op.create_table(
        "trading_plan",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategy_template.id"), nullable=False),
        sa.Column("status", sa.String(10), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("candidate_filter", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("stage_stop_config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("market_profile", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("position_control", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_trading_plan_user_status", "trading_plan", ["user_id", "status"])

    # candidate_stock
    op.create_table(
        "candidate_stock",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("trading_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("screen_date", sa.Date, nullable=False),
        sa.Column("symbol", sa.String(12), nullable=False),
        sa.Column("trend_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ref_buy_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("signal_strength", sa.String(10), nullable=True),
        sa.Column("signal_freshness", sa.String(15), nullable=True),
        sa.Column("sector_rank", sa.Integer, nullable=True),
        sa.Column("risk_status", sa.String(20), server_default=sa.text("'NORMAL'"), nullable=False),
        sa.Column("signals_summary", JSONB, nullable=True),
        sa.Column("status", sa.String(10), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("plan_id", "screen_date", "symbol", name="uq_candidate_plan_date_symbol"),
    )
    op.create_index("idx_candidate_plan_date", "candidate_stock", ["plan_id", "screen_date"])

    # buy_record
    op.create_table(
        "buy_record",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("trading_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidate_stock.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("trade_order.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(12), nullable=False),
        sa.Column("buy_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("buy_quantity", sa.Integer, nullable=False),
        sa.Column("buy_time", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("trend_score_at_buy", sa.Numeric(5, 2), nullable=True),
        sa.Column("sector_rank_at_buy", sa.Integer, nullable=True),
        sa.Column("signals_at_buy", JSONB, nullable=True),
        sa.Column("initial_stop_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("target_profit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("is_manual", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_buy_record_plan_time", "buy_record", ["plan_id", "buy_time"])

    # plan_position
    op.create_table(
        "plan_position",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("trading_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buy_record_id", UUID(as_uuid=True), sa.ForeignKey("buy_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(12), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("cost_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("stop_stage", sa.SmallInteger, server_default=sa.text("1"), nullable=False),
        sa.Column("stop_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("peak_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("holding_days", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("latest_trend_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("latest_sector_rank", sa.Integer, nullable=True),
        sa.Column("status", sa.String(15), server_default=sa.text("'HOLDING'"), nullable=False),
        sa.Column("sell_signals", JSONB, nullable=True),
        sa.Column("opened_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("closed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sell_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("sell_quantity", sa.Integer, nullable=True),
        sa.Column("pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("pnl_pct", sa.Float, nullable=True),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_plan_position_plan_status", "plan_position", ["plan_id", "status"])

    # daily_checklist
    op.create_table(
        "daily_checklist",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("trading_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_date", sa.Date, nullable=False),
        sa.Column("items", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("summary_level", sa.String(10), server_default=sa.text("'OK'"), nullable=False),
        sa.Column("strategy_health", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("plan_id", "check_date", name="uq_checklist_plan_date"),
    )
    op.create_index("idx_checklist_plan_date", "daily_checklist", ["plan_id", "check_date"])

    # market_profile_log
    op.create_table(
        "market_profile_log",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("trading_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("prev_level", sa.String(10), nullable=False),
        sa.Column("new_level", sa.String(10), nullable=False),
        sa.Column("trigger_reason", sa.String(200), nullable=False),
        sa.Column("params_snapshot", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_profile_log")
    op.drop_table("daily_checklist")
    op.drop_table("plan_position")
    op.drop_table("buy_record")
    op.drop_table("candidate_stock")
    op.drop_table("trading_plan")
