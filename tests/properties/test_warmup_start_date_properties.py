"""
calculate_warmup_start_date 属性测试（Hypothesis）

**Validates: Requirements 1.2, 1.3, 1.5**

Property 1: 预热期充分性
For any valid start_date, strategy_config, and buffer_days,
calculate_warmup_start_date returns warmup_date such that:
- warmup_date < start_date
- (start_date - warmup_date).days >= max(strategy_config.ma_periods)
- (start_date - warmup_date).days >= buffer_days
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import IndicatorParamsConfig, StrategyConfig
from app.tasks.backtest import calculate_warmup_start_date


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 生成合理的 ma_periods 列表：至少 1 个元素，值在 [1, 500]
_ma_periods = st.lists(
    st.integers(min_value=1, max_value=500),
    min_size=1,
    max_size=10,
)

# 生成 IndicatorParamsConfig 的各参数
_indicator_params = st.builds(
    IndicatorParamsConfig,
    macd_fast=st.integers(min_value=1, max_value=50),
    macd_slow=st.integers(min_value=1, max_value=100),
    macd_signal=st.integers(min_value=1, max_value=50),
    boll_period=st.integers(min_value=1, max_value=100),
    rsi_period=st.integers(min_value=1, max_value=100),
    dma_short=st.integers(min_value=1, max_value=100),
    dma_long=st.integers(min_value=1, max_value=200),
)

# 生成 StrategyConfig
_strategy_config = st.builds(
    StrategyConfig,
    ma_periods=_ma_periods,
    indicator_params=_indicator_params,
)

# 生成合理的 start_date（2020-2030 范围内）
_start_date = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31),
)

# 生成 buffer_days（0 到 500）
_buffer_days = st.integers(min_value=0, max_value=500)


# ---------------------------------------------------------------------------
# Property 1: 预热期充分性
# ---------------------------------------------------------------------------


class TestWarmupStartDateSufficiency:
    """Property 1: 预热期充分性

    **Validates: Requirements 1.2, 1.3, 1.5**
    """

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_date_strictly_before_start_date(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """warmup_date must be strictly earlier than start_date.

        **Validates: Requirements 1.2**
        """
        warmup_date = calculate_warmup_start_date(
            start_date, strategy_config, buffer_days
        )
        assert warmup_date < start_date

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_max_ma_period(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """The gap must be >= max(ma_periods).

        **Validates: Requirements 1.2**
        """
        warmup_date = calculate_warmup_start_date(
            start_date, strategy_config, buffer_days
        )
        diff = (start_date - warmup_date).days
        max_ma = max(strategy_config.ma_periods)
        assert diff >= max_ma

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_covers_buffer_days(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """The gap must be >= buffer_days.

        **Validates: Requirements 1.3**
        """
        warmup_date = calculate_warmup_start_date(
            start_date, strategy_config, buffer_days
        )
        diff = (start_date - warmup_date).days
        assert diff >= buffer_days

    @given(
        start_date=_start_date,
        strategy_config=_strategy_config,
        buffer_days=_buffer_days,
    )
    @settings(max_examples=200)
    def test_warmup_applies_safety_factor(
        self,
        start_date: date,
        strategy_config: StrategyConfig,
        buffer_days: int,
    ):
        """The 1.5x safety factor ensures calendar days exceed the raw requirement.

        **Validates: Requirements 1.5**
        """
        warmup_date = calculate_warmup_start_date(
            start_date, strategy_config, buffer_days
        )
        diff = (start_date - warmup_date).days

        # Compute the raw required_days the same way the function does
        max_lookback = max(strategy_config.ma_periods)
        ind = strategy_config.indicator_params
        if hasattr(ind, "macd_slow"):
            macd_warmup = ind.macd_slow + ind.macd_signal
            max_lookback = max(max_lookback, macd_warmup)
            max_lookback = max(max_lookback, ind.boll_period)
            max_lookback = max(max_lookback, ind.rsi_period + 1)
            max_lookback = max(max_lookback, ind.dma_long)
        required_days = max(buffer_days, max_lookback)

        # The actual gap should be at least int(required_days * 1.5)
        expected_calendar_days = int(required_days * 1.5)
        assert diff >= expected_calendar_days
