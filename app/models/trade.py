"""
交易相关 ORM 模型（PostgreSQL）

对应数据库表：
- trade_order：委托记录
- position：持仓
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Integer, Numeric, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class TradeOrder(PGBase):
    """委托记录"""

    __tablename__ = "trade_order"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(20), nullable=True)   # 'LIMIT'|'MARKET'|'CONDITION'
    direction: Mapped[str | None] = mapped_column(String(5), nullable=True)     # 'BUY'|'SELL'
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)       # 'PENDING'|'FILLED'|'CANCELLED'|'REJECTED'
    broker_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(10), nullable=True)         # 'LIVE'|'PAPER'
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    filled_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    filled_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TradeOrder {self.id} {self.direction} {self.symbol} status={self.status}>"


class Position(PGBase):
    """持仓"""

    __tablename__ = "position"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(10), nullable=True)     # 'LIVE'|'PAPER'
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "mode", name="uq_position_user_symbol_mode"),
    )

    def __repr__(self) -> str:
        return f"<Position {self.symbol} qty={self.quantity} cost={self.cost_price} user={self.user_id}>"
