"""
资金流向 ORM 模型（PostgreSQL）

对应数据库表：
- money_flow：个股每日主力资金、北向资金、龙虎榜、大宗交易等数据

相关需求：需求 1（资金流因子数据接入）
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, String, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class MoneyFlow(PGBase):
    """资金流向 ORM 模型，映射 money_flow 表"""

    __tablename__ = "money_flow"

    # 复合主键
    symbol: Mapped[str] = mapped_column(
        String(12), primary_key=True, nullable=False
    )
    trade_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )

    # 主力资金
    main_net_inflow: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    main_inflow: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    main_outflow: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    main_net_inflow_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # 大单数据
    large_order_net: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    large_order_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # 北向资金
    north_net_inflow: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    north_hold_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # 龙虎榜
    on_dragon_tiger: Mapped[bool | None] = mapped_column(
        Boolean, default=False, nullable=True
    )
    dragon_tiger_net: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # 大宗交易
    block_trade_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    block_trade_discount: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # 买卖盘比
    bid_ask_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    inner_outer_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # 更新时间
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMPTZ, nullable=True
    )

    __table_args__ = (
        Index("ix_money_flow_symbol", "symbol"),
        Index("ix_money_flow_date", "trade_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MoneyFlow {self.symbol} {self.trade_date} "
            f"main_net_inflow={self.main_net_inflow}>"
        )
