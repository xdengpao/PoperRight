"""
股票基础数据 ORM 模型（PostgreSQL）

对应数据库表：
- stock_info：股票基础信息
- permanent_exclusion：永久剔除名单
- stock_list：黑白名单
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, Numeric, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import INET, UUID as PG_UUID
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


class StockInfo(PGBase):
    """股票基础信息"""

    __tablename__ = "stock_info"

    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    market: Mapped[str | None] = mapped_column(String(10), nullable=True)   # SH/SZ/BJ
    board: Mapped[str | None] = mapped_column(String(10), nullable=True)    # 主板/创业板/科创板/北交所
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_st: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_delisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pledge_ratio: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    pb: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    industry_code: Mapped[str | None] = mapped_column(String(10), nullable=True)   # 申万一级行业代码
    industry_name: Mapped[str | None] = mapped_column(String(50), nullable=True)   # 申万一级行业名称
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    def __repr__(self) -> str:
        return f"<StockInfo {self.symbol} {self.name}>"


class PermanentExclusion(PGBase):
    """永久剔除名单"""

    __tablename__ = "permanent_exclusion"

    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    reason: Mapped[str | None] = mapped_column(String(50), nullable=True)   # 'ST','DELISTED','NEW_STOCK'
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PermanentExclusion {self.symbol} reason={self.reason}>"


class StockList(PGBase):
    """黑白名单"""

    __tablename__ = "stock_list"

    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    list_type: Mapped[str] = mapped_column(String(10), primary_key=True)    # 'BLACK'|'WHITE'
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<StockList {self.symbol} {self.list_type} user={self.user_id}>"
