"""
复权因子 ORM 模型

对应数据库表：adjustment_factor
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TSBase


class AdjustmentFactor(TSBase):
    """复权因子 ORM 模型"""

    __tablename__ = "adjustment_factor"

    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    adj_type: Mapped[int] = mapped_column(SmallInteger, primary_key=True)  # 1=前复权, 2=后复权
    adj_factor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    __table_args__ = (
        Index("ix_adj_factor_symbol_type", "symbol", "adj_type"),
    )

    def __repr__(self) -> str:
        return f"<AdjustmentFactor {self.symbol} {self.trade_date} type={self.adj_type} factor={self.adj_factor}>"
