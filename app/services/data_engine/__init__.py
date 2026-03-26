"""
DataEngine 数据引擎模块

提供行情数据适配器、基本面数据适配器、资金数据适配器与 K 线数据入库功能。
"""

from app.services.data_engine.market_adapter import MarketDataClient
from app.services.data_engine.kline_repository import KlineRepository
from app.services.data_engine.fundamental_adapter import FundamentalAdapter, FundamentalsData
from app.services.data_engine.money_flow_adapter import MoneyFlowAdapter, MoneyFlowData, MarketOverview, SectorData
from app.services.data_engine.stock_filter import (
    StockFilter,
    AdjustmentCalculator,
    StockBasicInfo,
    FundamentalsSnapshot,
    ExRightsRecord,
    interpolate_missing,
    remove_outliers,
    normalize_minmax,
    normalize_zscore,
)

__all__ = [
    "MarketDataClient",
    "KlineRepository",
    "FundamentalAdapter",
    "FundamentalsData",
    "MoneyFlowAdapter",
    "MoneyFlowData",
    "MarketOverview",
    "SectorData",
    "StockFilter",
    "AdjustmentCalculator",
    "StockBasicInfo",
    "FundamentalsSnapshot",
    "ExRightsRecord",
    "interpolate_missing",
    "remove_outliers",
    "normalize_minmax",
    "normalize_zscore",
]
