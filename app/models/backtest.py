"""
回测 ORM 模型（PostgreSQL）

对应数据库表：
- backtest_run：回测配置与结果
- exit_condition_template：平仓条件模版
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class BacktestRun(PGBase):
    """回测配置与结果"""

    __tablename__ = "backtest_run"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    strategy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("strategy_template.id"),
        nullable=True,
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_capital: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    commission_buy: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), server_default=sa_text("0.0003"), nullable=False
    )
    commission_sell: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), server_default=sa_text("0.0013"), nullable=False
    )
    slippage: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), server_default=sa_text("0.001"), nullable=False
    )
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)   # 'PENDING'|'RUNNING'|'DONE'|'FAILED'
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)       # BacktestResult 序列化
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<BacktestRun {self.id} status={self.status} user={self.user_id}>"


class ExitConditionTemplate(PGBase):
    """平仓条件模版"""

    __tablename__ = "exit_condition_template"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exit_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)  # ExitConditionConfig.to_dict()
    is_system: Mapped[bool] = mapped_column(
        Boolean, server_default=sa_text("false"), nullable=False
    )  # 系统内置模版(True) vs 用户自定义模版(False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ExitConditionTemplate {self.id} name={self.name} user={self.user_id}>"
