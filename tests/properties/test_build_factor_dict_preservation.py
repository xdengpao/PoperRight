"""
Preservation 属性测试：原始行情与基本面数据不变

**Validates: Requirements 3.1, 3.3, 3.6**

Property 2: Preservation - 原始行情与基本面数据不变

对任意输入的 StockInfo + KlineBar 列表，_build_factor_dict() 返回的因子字典中：
  - 最新行情字段（close, open, high, low, volume, amount, turnover, vol_ratio）
    与 bars[-1] 的对应属性完全一致
  - 历史序列字段（closes, highs, lows, volumes, amounts, turnovers）
    与从所有 bars 提取的序列完全一致
  - 基本面字段（pe_ttm, pb, roe, market_cap）与 stock 的对应属性一致

此测试在未修复代码上应通过（确认基线行为需要保持）。
修复后运行也应通过（确认无回归）。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import ScreenResult, ScreenType, StrategyConfig
from app.services.screener.screen_data_provider import ScreenDataProvider
from app.services.screener.screen_executor import ScreenExecutor

# Reuse strategies from the bug condition test
from tests.properties.test_build_factor_dict_bug_condition import (
    stock_and_bars_strategy,
)


# ---------------------------------------------------------------------------
# Property 2a: 原始行情数据保持
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(data=stock_and_bars_strategy())
def test_build_factor_dict_preserves_latest_bar_fields(data):
    """
    Preservation: 最新 K 线行情字段与 bars[-1] 完全一致。

    **Validates: Requirements 3.1, 3.6**

    For any StockInfo + KlineBar list, _build_factor_dict() must return
    a factor dict where the latest bar fields exactly match bars[-1].
    """
    stock, bars = data
    factor_dict = ScreenDataProvider._build_factor_dict(stock, bars)
    latest = bars[-1]

    assert factor_dict["close"] == latest.close, (
        f"close 不一致: {factor_dict['close']} != {latest.close}"
    )
    assert factor_dict["open"] == latest.open, (
        f"open 不一致: {factor_dict['open']} != {latest.open}"
    )
    assert factor_dict["high"] == latest.high, (
        f"high 不一致: {factor_dict['high']} != {latest.high}"
    )
    assert factor_dict["low"] == latest.low, (
        f"low 不一致: {factor_dict['low']} != {latest.low}"
    )
    assert factor_dict["volume"] == latest.volume, (
        f"volume 不一致: {factor_dict['volume']} != {latest.volume}"
    )
    assert factor_dict["amount"] == latest.amount, (
        f"amount 不一致: {factor_dict['amount']} != {latest.amount}"
    )
    assert factor_dict["turnover"] == latest.turnover, (
        f"turnover 不一致: {factor_dict['turnover']} != {latest.turnover}"
    )
    assert factor_dict["vol_ratio"] == latest.vol_ratio, (
        f"vol_ratio 不一致: {factor_dict['vol_ratio']} != {latest.vol_ratio}"
    )


# ---------------------------------------------------------------------------
# Property 2b: 历史序列数据保持
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(data=stock_and_bars_strategy())
def test_build_factor_dict_preserves_historical_sequences(data):
    """
    Preservation: 历史序列字段与从所有 bars 提取的序列完全一致。

    **Validates: Requirements 3.1, 3.6**

    For any StockInfo + KlineBar list, _build_factor_dict() must return
    sequences (closes, highs, lows, volumes, amounts, turnovers) that
    exactly match the values extracted from all bars in order.
    """
    stock, bars = data
    factor_dict = ScreenDataProvider._build_factor_dict(stock, bars)

    expected_closes = [b.close for b in bars]
    expected_highs = [b.high for b in bars]
    expected_lows = [b.low for b in bars]
    expected_volumes = [b.volume for b in bars]
    expected_amounts = [b.amount for b in bars]
    expected_turnovers = [b.turnover for b in bars]

    assert factor_dict["closes"] == expected_closes, (
        f"closes 序列不一致 (len={len(factor_dict['closes'])} vs {len(expected_closes)})"
    )
    assert factor_dict["highs"] == expected_highs, (
        f"highs 序列不一致"
    )
    assert factor_dict["lows"] == expected_lows, (
        f"lows 序列不一致"
    )
    assert factor_dict["volumes"] == expected_volumes, (
        f"volumes 序列不一致"
    )
    assert factor_dict["amounts"] == expected_amounts, (
        f"amounts 序列不一致"
    )
    assert factor_dict["turnovers"] == expected_turnovers, (
        f"turnovers 序列不一致"
    )


# ---------------------------------------------------------------------------
# Property 2c: 基本面数据保持
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(data=stock_and_bars_strategy())
def test_build_factor_dict_preserves_fundamental_fields(data):
    """
    Preservation: 基本面字段与 stock 的对应属性一致。

    **Validates: Requirements 3.1, 3.6**

    For any StockInfo + KlineBar list, _build_factor_dict() must return
    fundamental fields (pe_ttm, pb, roe, market_cap) that match the
    stock's attributes (converted to float or None).
    """
    stock, bars = data
    factor_dict = ScreenDataProvider._build_factor_dict(stock, bars)

    expected_pe = float(stock.pe_ttm) if stock.pe_ttm is not None else None
    expected_pb = float(stock.pb) if stock.pb is not None else None
    expected_roe = float(stock.roe) if stock.roe is not None else None
    expected_mc = float(stock.market_cap) if stock.market_cap is not None else None

    assert factor_dict["pe_ttm"] == expected_pe, (
        f"pe_ttm 不一致: {factor_dict['pe_ttm']} != {expected_pe}"
    )
    assert factor_dict["pb"] == expected_pb, (
        f"pb 不一致: {factor_dict['pb']} != {expected_pb}"
    )
    assert factor_dict["roe"] == expected_roe, (
        f"roe 不一致: {factor_dict['roe']} != {expected_roe}"
    )
    assert factor_dict["market_cap"] == expected_mc, (
        f"market_cap 不一致: {factor_dict['market_cap']} != {expected_mc}"
    )


# ---------------------------------------------------------------------------
# Property 2d: enabled_modules 为空集时返回空 ScreenResult
# ---------------------------------------------------------------------------


@settings(max_examples=20)
@given(data=stock_and_bars_strategy())
def test_empty_enabled_modules_returns_empty_screen_result(data):
    """
    Preservation: enabled_modules 为空集时 ScreenExecutor 返回空 ScreenResult。

    **Validates: Requirements 3.3**

    When enabled_modules is an empty list (empty set), ScreenExecutor
    must return a ScreenResult with an empty items list, regardless of
    the input stocks_data.
    """
    stock, bars = data

    factor_dict = ScreenDataProvider._build_factor_dict(stock, bars)
    stocks_data = {stock.symbol: factor_dict}

    config = StrategyConfig()
    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=[],  # empty set
    )

    result = executor.run_eod_screen(stocks_data)

    assert isinstance(result, ScreenResult), (
        f"返回类型应为 ScreenResult，实际: {type(result)}"
    )
    assert result.items == [], (
        f"enabled_modules 为空集时 items 应为空列表，实际: {len(result.items)} 项"
    )
    assert result.is_complete is True, (
        "enabled_modules 为空集时 is_complete 应为 True"
    )
    assert result.screen_type == ScreenType.EOD, (
        f"screen_type 应为 EOD，实际: {result.screen_type}"
    )
