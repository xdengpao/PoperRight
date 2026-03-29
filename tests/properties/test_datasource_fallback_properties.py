"""
数据源故障转移属性测试（Hypothesis）

属性 50：Tushare 失败自动切换 AkShare

**Validates: Requirements 1.9**

验证对任意数据请求类型和参数，当 Tushare 调用失败时
DataSourceRouter 自动切换至 AkShare，若 AkShare 返回有效数据则整体请求成功。
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.data_engine.data_source_router import DataSourceRouter


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 股票代码：6 位数字 + 交易所后缀
_symbol_strategy = st.builds(
    lambda code, suffix: f"{code:06d}.{suffix}",
    code=st.integers(min_value=1, max_value=999999),
    suffix=st.sampled_from(["SZ", "SH", "BJ"]),
)

# K 线频率
_freq_strategy = st.sampled_from(["D", "W", "M", "1m", "5m", "15m", "30m", "60m"])

# 日期范围：2010-01-01 ~ 2025-12-31
_date_strategy = st.dates(
    min_value=date(2010, 1, 1),
    max_value=date(2025, 12, 31),
)

# Tushare 失败异常类型
_exception_strategy = st.sampled_from([
    RuntimeError("Tushare timeout"),
    ConnectionError("connection refused"),
    TimeoutError("request timed out"),
    Exception("Tushare API error code=-1"),
    OSError("network unreachable"),
])

# 代理方法名称（DataSourceRouter 支持的四种数据请求）
_method_name_strategy = st.sampled_from([
    "fetch_kline",
    "fetch_fundamentals",
    "fetch_money_flow",
    "fetch_market_overview",
])


# ---------------------------------------------------------------------------
# 辅助：构建 mock 适配器
# ---------------------------------------------------------------------------

def _make_mock_adapters(method_name: str, exception: Exception, fallback_return):
    """创建 Tushare（抛异常）和 AkShare（返回有效数据）的 mock 适配器。"""
    tushare = AsyncMock()
    akshare = AsyncMock()

    # Tushare 对应方法抛出异常
    getattr(tushare, method_name).side_effect = exception
    # AkShare 对应方法返回有效数据
    getattr(akshare, method_name).return_value = fallback_return

    return tushare, akshare


# ---------------------------------------------------------------------------
# 属性 50：Tushare 失败自动切换 AkShare
# ---------------------------------------------------------------------------


@h_settings(max_examples=50)
@given(
    symbol=_symbol_strategy,
    freq=_freq_strategy,
    start_date=_date_strategy,
    exception=_exception_strategy,
)
def test_fallback_fetch_kline(
    symbol: str,
    freq: str,
    start_date: date,
    exception: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 50: Tushare 失败自动切换 AkShare

    **Validates: Requirements 1.9**

    对任意股票代码、K 线频率和日期范围，当 Tushare fetch_kline 抛出任意异常时，
    DataSourceRouter 应自动切换至 AkShare，若 AkShare 返回有效数据则整体请求成功。
    """
    end_date = start_date + timedelta(days=30)
    fallback_data = [{"symbol": symbol, "freq": freq, "close": Decimal("10.00")}]

    tushare, akshare = _make_mock_adapters("fetch_kline", exception, fallback_data)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    result = asyncio.run(router.fetch_kline(symbol, freq, start_date, end_date))

    # 验证：整体请求成功，返回 AkShare 的数据
    assert result == fallback_data
    # 验证：Tushare 被调用过（尝试了主数据源）
    tushare.fetch_kline.assert_awaited_once()
    # 验证：AkShare 被调用过（故障转移生效）
    akshare.fetch_kline.assert_awaited_once()


@h_settings(max_examples=50)
@given(
    symbol=_symbol_strategy,
    exception=_exception_strategy,
)
def test_fallback_fetch_fundamentals(
    symbol: str,
    exception: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 50: Tushare 失败自动切换 AkShare

    **Validates: Requirements 1.9**

    对任意股票代码，当 Tushare fetch_fundamentals 抛出任意异常时，
    DataSourceRouter 应自动切换至 AkShare，若 AkShare 返回有效数据则整体请求成功。
    """
    fallback_data = {"symbol": symbol, "roe": Decimal("12.5")}

    tushare, akshare = _make_mock_adapters("fetch_fundamentals", exception, fallback_data)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    result = asyncio.run(router.fetch_fundamentals(symbol))

    assert result == fallback_data
    tushare.fetch_fundamentals.assert_awaited_once()
    akshare.fetch_fundamentals.assert_awaited_once()


@h_settings(max_examples=50)
@given(
    symbol=_symbol_strategy,
    trade_date=_date_strategy,
    exception=_exception_strategy,
)
def test_fallback_fetch_money_flow(
    symbol: str,
    trade_date: date,
    exception: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 50: Tushare 失败自动切换 AkShare

    **Validates: Requirements 1.9**

    对任意股票代码和交易日期，当 Tushare fetch_money_flow 抛出任意异常时，
    DataSourceRouter 应自动切换至 AkShare，若 AkShare 返回有效数据则整体请求成功。
    """
    fallback_data = {"symbol": symbol, "main_net_inflow": Decimal("500")}

    tushare, akshare = _make_mock_adapters("fetch_money_flow", exception, fallback_data)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    result = asyncio.run(router.fetch_money_flow(symbol, trade_date))

    assert result == fallback_data
    tushare.fetch_money_flow.assert_awaited_once()
    akshare.fetch_money_flow.assert_awaited_once()


@h_settings(max_examples=50)
@given(
    trade_date=_date_strategy,
    exception=_exception_strategy,
)
def test_fallback_fetch_market_overview(
    trade_date: date,
    exception: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 50: Tushare 失败自动切换 AkShare

    **Validates: Requirements 1.9**

    对任意交易日期，当 Tushare fetch_market_overview 抛出任意异常时，
    DataSourceRouter 应自动切换至 AkShare，若 AkShare 返回有效数据则整体请求成功。
    """
    fallback_data = {"trade_date": trade_date, "sh_index": Decimal("3100")}

    tushare, akshare = _make_mock_adapters("fetch_market_overview", exception, fallback_data)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    result = asyncio.run(router.fetch_market_overview(trade_date))

    assert result == fallback_data
    tushare.fetch_market_overview.assert_awaited_once()
    akshare.fetch_market_overview.assert_awaited_once()


@h_settings(max_examples=50)
@given(
    method_name=_method_name_strategy,
    exception=_exception_strategy,
)
def test_fallback_generic_method(
    method_name: str,
    exception: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 50: Tushare 失败自动切换 AkShare

    **Validates: Requirements 1.9**

    对任意数据请求方法名和异常类型，当 Tushare 调用失败时，
    DataSourceRouter.fetch_with_fallback 应自动切换至 AkShare，
    若 AkShare 返回有效数据则整体请求成功。
    """
    fallback_data = {"source": "akshare", "method": method_name}

    tushare, akshare = _make_mock_adapters(method_name, exception, fallback_data)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    result = asyncio.run(router.fetch_with_fallback(method_name))

    assert result == fallback_data
    getattr(tushare, method_name).assert_awaited_once()
    getattr(akshare, method_name).assert_awaited_once()
