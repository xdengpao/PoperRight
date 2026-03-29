"""
数据源适配器抽象基类

定义所有数据源适配器（Tushare、AkShare 等）必须实现的统一接口，
便于 DataSourceRouter 在故障转移时无缝切换数据源。

对应需求：
- 1.1：对接 Tushare / AkShare 获取 A 股全市场行情数据
- 1.9：Tushare 失败时自动切换至 AkShare
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.core.schemas import KlineBar
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData


class DataSourceUnavailableError(Exception):
    """所有数据源均不可用时抛出"""

    pass


class BaseDataSourceAdapter(ABC):
    """数据源适配器抽象基类"""

    @abstractmethod
    async def fetch_kline(
        self, symbol: str, freq: str, start: date, end: date
    ) -> list[KlineBar]:
        """获取 K 线行情数据。

        Args:
            symbol: 股票代码，如 "000001.SZ"
            freq:   K 线频率，如 "1min", "5min", "D", "W", "M"
            start:  起始日期
            end:    结束日期

        Returns:
            KlineBar 列表
        """
        ...

    @abstractmethod
    async def fetch_fundamentals(self, symbol: str) -> FundamentalsData:
        """获取个股基本面数据（财务报表、估值、质押率等）。

        Args:
            symbol: 股票代码

        Returns:
            FundamentalsData 数据对象
        """
        ...

    @abstractmethod
    async def fetch_money_flow(
        self, symbol: str, trade_date: date
    ) -> MoneyFlowData:
        """获取个股资金流向数据（主力资金、北向资金、龙虎榜等）。

        Args:
            symbol:     股票代码
            trade_date: 交易日期

        Returns:
            MoneyFlowData 数据对象
        """
        ...

    @abstractmethod
    async def fetch_market_overview(self, trade_date: date) -> MarketOverview:
        """获取大盘市场概览数据（指数、涨跌家数、板块、市场情绪等）。

        Args:
            trade_date: 交易日期

        Returns:
            MarketOverview 数据对象
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查数据源连通性。

        Returns:
            True 表示数据源可用，False 表示不可用
        """
        ...
