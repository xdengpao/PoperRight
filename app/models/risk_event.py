"""
风控事件日志 ORM 模型（PostgreSQL）

对应数据库表：
- risk_event_log：风控事件历史记录

需求 10：风控事件历史日志
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Float, String, Index
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class RiskEventLog(PGBase):
    """风控事件日志"""

    __tablename__ = "risk_event_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
    )  # ORDER_REJECTED / STOP_LOSS / POSITION_LIMIT / BREAKDOWN
    symbol: Mapped[str | None] = mapped_column(String(12), nullable=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    result: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )  # REJECTED / WARNING
    triggered_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False,
    )

    __table_args__ = (
        Index("ix_risk_event_log_user_triggered", "user_id", "triggered_at"),
        Index("ix_risk_event_log_event_type", "event_type"),
        Index("ix_risk_event_log_symbol", "symbol"),
    )

    def __repr__(self) -> str:
        return (
            f"<RiskEventLog {self.id} type={self.event_type} "
            f"symbol={self.symbol} result={self.result}>"
        )
