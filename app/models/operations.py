"""
实操模块 ORM 模型（PostgreSQL）

对应数据库表：
- trading_plan：交易计划（单用户最多 10 个非归档计划）
- candidate_stock：候选股记录
- buy_record：买入记录
- plan_position：交易计划持仓
- daily_checklist：每日复盘清单
- market_profile_log：市场环境切换日志
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class TradingPlan(PGBase):
    """交易计划（单用户最多 10 个非归档计划）"""

    __tablename__ = "trading_plan"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("strategy_template.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=sa_text("'ACTIVE'")
    )
    candidate_filter: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )
    stage_stop_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )
    market_profile: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )
    position_control: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_trading_plan_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<TradingPlan {self.id} name={self.name} status={self.status}>"


class CandidateStock(PGBase):
    """候选股记录"""

    __tablename__ = "candidate_stock"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trading_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    screen_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(12), nullable=False)
    trend_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ref_buy_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    signal_strength: Mapped[str | None] = mapped_column(String(10), nullable=True)
    signal_freshness: Mapped[str | None] = mapped_column(String(15), nullable=True)
    sector_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sa_text("'NORMAL'")
    )
    signals_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=sa_text("'PENDING'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "screen_date", "symbol", name="uq_candidate_plan_date_symbol"),
        Index("idx_candidate_plan_date", "plan_id", "screen_date"),
    )

    def __repr__(self) -> str:
        return f"<CandidateStock {self.symbol} plan={self.plan_id} date={self.screen_date}>"


class BuyRecord(PGBase):
    """买入记录"""

    __tablename__ = "buy_record"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trading_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("candidate_stock.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trade_order.id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(12), nullable=False)
    buy_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    buy_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    trend_score_at_buy: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sector_rank_at_buy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signals_at_buy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    initial_stop_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    target_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_buy_record_plan_time", "plan_id", "buy_time"),
    )

    def __repr__(self) -> str:
        return f"<BuyRecord {self.symbol} plan={self.plan_id} price={self.buy_price}>"


class PlanPosition(PGBase):
    """交易计划持仓"""

    __tablename__ = "plan_position"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trading_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    buy_record_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("buy_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(12), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    stop_stage: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa_text("1"))
    stop_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    peak_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    holding_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("0"))
    latest_trend_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    latest_sector_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(15), nullable=False, server_default=sa_text("'HOLDING'")
    )
    sell_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    sell_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_plan_position_plan_status", "plan_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<PlanPosition {self.symbol} stage={self.stop_stage} status={self.status}>"


class DailyChecklist(PGBase):
    """每日复盘清单"""

    __tablename__ = "daily_checklist"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trading_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    items: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'[]'::jsonb")
    )
    summary_level: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=sa_text("'OK'")
    )
    strategy_health: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "check_date", name="uq_checklist_plan_date"),
        Index("idx_checklist_plan_date", "plan_id", "check_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyChecklist plan={self.plan_id} date={self.check_date} level={self.summary_level}>"


class MarketProfileLog(PGBase):
    """市场环境切换日志"""

    __tablename__ = "market_profile_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trading_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    prev_level: Mapped[str] = mapped_column(String(10), nullable=False)
    new_level: Mapped[str] = mapped_column(String(10), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(200), nullable=False)
    params_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa_text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return f"<MarketProfileLog {self.prev_level}->{self.new_level} plan={self.plan_id}>"
