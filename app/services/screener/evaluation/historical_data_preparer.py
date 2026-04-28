"""历史数据准备器

为评估期内的每个交易日准备选股所需的全市场因子快照。
复用 ScreenDataProvider 的因子计算逻辑，以指定日期为基准加载数据。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.models.kline import KlineBar
from app.models.stock import StockInfo
from app.services.data_engine.kline_repository import KlineRepository
from app.services.screener.screen_data_provider import (
    ScreenDataProvider,
    DEFAULT_LOOKBACK_DAYS,
)

logger = logging.getLogger(__name__)


class HistoricalDataPreparer:
    """历史数据准备器，为每个评估日加载市场数据快照。"""

    def __init__(
        self,
        pg_session: AsyncSession | None = None,
        ts_session: AsyncSession | None = None,
    ) -> None:
        self._pg_session = pg_session
        self._ts_session = ts_session
        self._kline_repo = KlineRepository(ts_session)
        self._snapshot_cache: dict[date, dict[str, dict[str, Any]]] = {}

    async def get_trading_dates(
        self, start_date: date, end_date: date
    ) -> list[date]:
        """从 K 线表查询评估期内的交易日列表。"""
        reference_symbol = "000001.SZ"
        bars = await self._kline_repo.query(
            symbol=reference_symbol,
            freq="1d",
            start=start_date,
            end=end_date,
        )
        trading_dates = sorted({b.time.date() if hasattr(b.time, 'date') else b.time for b in bars})
        logger.info("评估期 %s ~ %s 共 %d 个交易日", start_date, end_date, len(trading_dates))
        return trading_dates

    async def load_daily_snapshot(
        self,
        trade_date: date,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> dict[str, dict[str, Any]]:
        """加载指定交易日的全市场因子快照。

        复用 ScreenDataProvider.load_screen_data()，以 trade_date 为选股基准日。
        结果缓存避免重复查询。
        """
        if trade_date in self._snapshot_cache:
            return self._snapshot_cache[trade_date]

        provider = ScreenDataProvider(
            pg_session=self._pg_session,
            ts_session=self._ts_session,
        )
        snapshot = await provider.load_screen_data(
            lookback_days=lookback_days,
            screen_date=trade_date,
        )
        self._snapshot_cache[trade_date] = snapshot
        logger.info("加载 %s 因子快照：%d 只股票", trade_date, len(snapshot))
        return snapshot

    _DEFAULT_BENCHMARK = "000300.SH"
    _FALLBACK_BENCHMARK = "000001.SH"

    async def load_index_data(
        self,
        start_date: date,
        end_date: date,
        index_code: str = _DEFAULT_BENCHMARK,
        fallback_code: str = _FALLBACK_BENCHMARK,
    ) -> dict[date, dict[str, Any]]:
        """加载指数日线数据，用于计算超额收益和市场环境分类。

        默认使用沪深300作为基准，查询失败时回退到上证指数。
        返回: {date: {close, open, ma20, ma60, change_pct_20d}}
        """
        result = await self._load_index_kline(index_code, start_date, end_date)
        if not result and fallback_code != index_code:
            logger.warning("基准指数 %s 无数据，回退到 %s", index_code, fallback_code)
            result = await self._load_index_kline(fallback_code, start_date, end_date)
        if not result:
            logger.error("所有基准指数均无数据，超额收益和市场环境分类将不可用")
        return result

    async def _load_index_kline(
        self,
        index_code: str,
        start_date: date,
        end_date: date,
    ) -> dict[date, dict[str, Any]]:
        """从 kline 表加载指数日线并计算均线。"""
        extended_start = start_date - timedelta(days=90)
        bars = await self._kline_repo.query(
            symbol=index_code,
            freq="1d",
            start=extended_start,
            end=end_date,
        )
        if not bars:
            return {}

        closes = [float(b.close) for b in bars]
        result: dict[date, dict[str, Any]] = {}

        for i, bar in enumerate(bars):
            bar_date = bar.time.date() if hasattr(bar.time, 'date') else bar.time
            if bar_date < start_date:
                continue

            ma20 = sum(closes[max(0, i - 19):i + 1]) / min(20, i + 1) if i >= 0 else None
            ma60 = sum(closes[max(0, i - 59):i + 1]) / min(60, i + 1) if i >= 19 else None

            change_pct_20d = None
            if i >= 20:
                change_pct_20d = (closes[i] - closes[i - 20]) / closes[i - 20] * 100

            result[bar_date] = {
                "close": closes[i],
                "open": float(bar.open),
                "ma20": ma20,
                "ma60": ma60,
                "change_pct_20d": change_pct_20d,
            }

        logger.info("加载指数 %s 数据：%d 个交易日", index_code, len(result))
        return result

    async def load_stock_info(self) -> dict[str, dict[str, Any]]:
        """加载股票基本信息（行业、市值分组等），用于分组分析。"""
        if self._pg_session is None:
            async with AsyncSessionPG() as session:
                return await self._query_stock_info(session)
        return await self._query_stock_info(self._pg_session)

    @staticmethod
    async def _query_stock_info(session: AsyncSession) -> dict[str, dict[str, Any]]:
        stmt = select(StockInfo).where(
            StockInfo.is_st == False,  # noqa: E712
            StockInfo.is_delisted == False,  # noqa: E712
        )
        rows = (await session.execute(stmt)).scalars().all()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            market_cap = float(row.market_cap) if row.market_cap else 0
            if market_cap >= 50_000_000_000:
                cap_group = "大盘"
            elif market_cap >= 10_000_000_000:
                cap_group = "中盘"
            else:
                cap_group = "小盘"
            result[row.symbol] = {
                "name": row.name,
                "industry": row.industry_name,
                "market_cap": market_cap,
                "cap_group": cap_group,
            }
        return result
