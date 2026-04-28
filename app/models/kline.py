"""
K线行情数据 ORM 模型（TimescaleDB 超表）

对应数据库表：kline
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TSBase


class Kline(TSBase):
    """K线数据 ORM 模型，对应 TimescaleDB 超表 kline"""

    __tablename__ = "kline"

    # 时间轴（超表分区键）
    time: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)
    # 股票代码，标准格式如 000001.SZ
    symbol: Mapped[str] = mapped_column(String(12), primary_key=True, nullable=False)
    # 频率：'1m','5m','15m','30m','60m','1d','1w','1M'
    freq: Mapped[str] = mapped_column(String(5), primary_key=True, nullable=False)

    open: Mapped[Decimal | None] = mapped_column("open", nullable=True)
    high: Mapped[Decimal | None] = mapped_column("high", nullable=True)
    low: Mapped[Decimal | None] = mapped_column("low", nullable=True)
    close: Mapped[Decimal | None] = mapped_column("close", nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column("amount", nullable=True)
    turnover: Mapped[Decimal | None] = mapped_column("turnover", nullable=True)
    vol_ratio: Mapped[Decimal | None] = mapped_column("vol_ratio", nullable=True)
    limit_up: Mapped[Decimal | None] = mapped_column("limit_up", nullable=True)
    limit_down: Mapped[Decimal | None] = mapped_column("limit_down", nullable=True)
    # 复权类型：0=不复权 1=前复权 2=后复权
    adj_type: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    __table_args__ = (
        Index("ix_kline_symbol_freq_time", "symbol", "freq", "time"),
        Index("uq_kline_time_symbol_freq_adj", "time", "symbol", "freq", "adj_type", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Kline {self.symbol} {self.freq} {self.time} close={self.close}>"


# ---------------------------------------------------------------------------
# 纯数据类（用于业务层传递，不依赖 ORM）
# ---------------------------------------------------------------------------


@dataclass
class KlineBar:
    """K线数据传输对象"""

    time: datetime
    symbol: str
    freq: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal
    turnover: Decimal
    vol_ratio: Decimal
    limit_up: Decimal | None = None
    limit_down: Decimal | None = None
    adj_type: int = 0

    def to_orm(self) -> Kline:
        """转换为 ORM 模型实例"""
        return Kline(
            time=self.time,
            symbol=self.symbol,
            freq=self.freq,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            amount=self.amount,
            turnover=self.turnover,
            vol_ratio=self.vol_ratio,
            limit_up=self.limit_up,
            limit_down=self.limit_down,
            adj_type=self.adj_type,
        )

    @classmethod
    def from_orm(cls, obj: Kline) -> "KlineBar":
        """从 ORM 模型实例转换"""
        return cls(
            time=obj.time,
            symbol=obj.symbol,
            freq=obj.freq,
            open=obj.open,
            high=obj.high,
            low=obj.low,
            close=obj.close,
            volume=obj.volume,
            amount=obj.amount,
            turnover=obj.turnover,
            vol_ratio=obj.vol_ratio,
            limit_up=obj.limit_up,
            limit_down=obj.limit_down,
            adj_type=obj.adj_type,
        )
