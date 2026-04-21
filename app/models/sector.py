"""
板块数据 ORM 模型

- SectorInfo: 板块元数据（PostgreSQL）
- SectorConstituent: 板块成分股快照（PostgreSQL）
- SectorKline: 板块指数行情（TimescaleDB 超表）
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import BigInteger, Date, Index, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase, TSBase


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------


class DataSource(str, Enum):
    """板块数据来源"""

    DC = "DC"    # 东方财富
    TI = "TI"    # 同花顺
    TDX = "TDX"  # 通达信
    CI = "CI"    # 中信行业
    THS = "THS"  # 同花顺概念/行业板块


class SectorType(str, Enum):
    """板块类型"""

    CONCEPT = "CONCEPT"    # 概念板块
    INDUSTRY = "INDUSTRY"  # 行业板块
    REGION = "REGION"      # 地区板块
    STYLE = "STYLE"        # 风格板块


# ---------------------------------------------------------------------------
# SectorInfo — 板块元数据（PostgreSQL）
# ---------------------------------------------------------------------------


class SectorInfo(PGBase):
    """板块信息 ORM 模型"""

    __tablename__ = "sector_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sector_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_type: Mapped[str] = mapped_column(String(20), nullable=False)
    data_source: Mapped[str] = mapped_column(String(10), nullable=False)
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    constituent_count: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "sector_code", "data_source", name="uq_sector_info_code_source"
        ),
        Index("ix_sector_info_type_source", "sector_type", "data_source"),
    )

    def __repr__(self) -> str:
        return f"<SectorInfo {self.sector_code} {self.data_source} {self.name}>"


# ---------------------------------------------------------------------------
# SectorConstituent — 板块成分股快照（PostgreSQL）
# ---------------------------------------------------------------------------


class SectorConstituent(PGBase):
    """板块成分股快照 ORM 模型"""

    __tablename__ = "sector_constituent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    sector_code: Mapped[str] = mapped_column(String(20), nullable=False)
    data_source: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "sector_code",
            "data_source",
            "symbol",
            name="uq_sector_constituent_date_code_source_symbol",
        ),
        Index("ix_sector_constituent_symbol_date", "symbol", "trade_date"),
        Index(
            "ix_sector_constituent_code_source_date",
            "sector_code",
            "data_source",
            "trade_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SectorConstituent {self.sector_code} {self.symbol} "
            f"{self.trade_date}>"
        )


# ---------------------------------------------------------------------------
# SectorKline — 板块指数行情（TimescaleDB 超表）
# ---------------------------------------------------------------------------


class SectorKline(TSBase):
    """板块指数行情 ORM 模型，对应 TimescaleDB 超表 sector_kline"""

    __tablename__ = "sector_kline"

    # 复合主键
    time: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)
    sector_code: Mapped[str] = mapped_column(
        String(20), primary_key=True, nullable=False
    )
    data_source: Mapped[str] = mapped_column(
        String(10), primary_key=True, nullable=False
    )
    freq: Mapped[str] = mapped_column(String(5), primary_key=True, nullable=False)

    # OHLCV + 涨跌幅 + 换手率
    open: Mapped[Decimal | None] = mapped_column(nullable=True)
    high: Mapped[Decimal | None] = mapped_column(nullable=True)
    low: Mapped[Decimal | None] = mapped_column(nullable=True)
    close: Mapped[Decimal | None] = mapped_column(nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(nullable=True)
    turnover: Mapped[Decimal | None] = mapped_column(nullable=True)
    change_pct: Mapped[Decimal | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index(
            "uq_sector_kline_time_code_source_freq",
            "time",
            "sector_code",
            "data_source",
            "freq",
            unique=True,
        ),
        Index(
            "ix_sector_kline_code_source_freq_time",
            "sector_code",
            "data_source",
            "freq",
            "time",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SectorKline {self.sector_code} {self.data_source} "
            f"{self.freq} {self.time} close={self.close}>"
        )
