"""
ExitConditionEvaluator 单元测试

测试核心评估逻辑：数值比较、交叉检测、AND/OR 逻辑组合、边界条件。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from app.core.schemas import ExitCondition, ExitConditionConfig
from app.services.exit_condition_evaluator import ExitConditionEvaluator
from app.services.backtest_engine import IndicatorCache


def _make_cache(
    closes: list[float] | None = None,
    volumes: list[int] | None = None,
    turnovers: list[float] | None = None,
    n: int = 10,
) -> IndicatorCache:
    """创建一个简单的 IndicatorCache 用于测试。"""
    if closes is None:
        closes = [100.0 + i for i in range(n)]
    if volumes is None:
        volumes = [1000] * len(closes)
    if turnovers is None:
        turnovers_dec = [Decimal("5.0")] * len(closes)
    else:
        turnovers_dec = [Decimal(str(t)) for t in turnovers]
    return IndicatorCache(
        closes=closes,
        highs=[c + 1 for c in closes],
        lows=[c - 1 for c in closes],
        volumes=volumes,
        amounts=[Decimal("100000")] * len(closes),
        turnovers=turnovers_dec,
    )


class TestNumericComparison:
    """数值比较运算符测试"""

    def test_rsi_greater_than_threshold_triggered(self):
        """RSI > 80 应触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
            logic="AND",
        )
        triggered, reason = evaluator.evaluate(config, "600519.SH", 3, cache, exit_cache)
        assert triggered is True
        assert "RSI" in reason
        assert "> 80" in reason

    def test_rsi_not_triggered_when_below(self):
        """RSI < 80 不应触发 > 80 条件"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "600519.SH", 3, cache, exit_cache)
        assert triggered is False

    def test_close_less_than_threshold(self):
        """close < 105 应触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(closes=[100.0, 101.0, 102.0, 103.0, 104.0])

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator="<", threshold=105.0),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "TEST", 2, cache, None)
        assert triggered is True

    def test_volume_greater_equal(self):
        """volume >= 1000 应触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(volumes=[500, 800, 1000, 1200, 900])

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="volume", operator=">=", threshold=1000.0),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 2, cache, None)
        assert triggered is True

    def test_turnover_less_equal(self):
        """turnover <= 3.0 应触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(turnovers=[5.0, 4.0, 3.0, 2.0, 1.0])

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="turnover", operator="<=", threshold=3.0),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 2, cache, None)
        assert triggered is True


class TestCrossDetection:
    """交叉检测测试"""

    def test_macd_dif_cross_down_dea(self):
        """MACD_DIF cross_down MACD_DEA"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        # prev: dif >= dea, curr: dif < dea
        exit_cache = {"daily": {
            "macd_dif": [0.5, 0.3, 0.2, 0.1, -0.1],
            "macd_dea": [0.1, 0.1, 0.1, 0.1, 0.1],
        }}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "TEST", 4, cache, exit_cache)
        assert triggered is True
        assert "cross_down" in reason
        assert "MACD_DIF" in reason
        assert "MACD_DEA" in reason

    def test_cross_up_detection(self):
        """cross_up: prev <= target, curr > target"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {
            "macd_dif": [-0.1, -0.05, 0.0, 0.15, 0.3],
            "macd_dea": [0.1, 0.1, 0.1, 0.1, 0.1],
        }}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator="cross_up",
                    cross_target="macd_dea",
                ),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True
        assert "cross_up" in reason

    def test_cross_not_triggered_when_no_crossover(self):
        """无交叉时不应触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {
            "macd_dif": [0.5, 0.4, 0.3, 0.2, 0.15],
            "macd_dea": [0.1, 0.1, 0.1, 0.1, 0.1],
        }}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 4, cache, exit_cache)
        assert triggered is False

    def test_cross_at_bar_index_0_skipped(self):
        """bar_index=0 时交叉检测应跳过"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {
            "macd_dif": [0.5, 0.3],
            "macd_dea": [0.1, 0.1],
        }}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 0, cache, exit_cache)
        assert triggered is False


class TestLogicCombination:
    """AND / OR 逻辑组合测试"""

    def test_and_all_true(self):
        """AND: 所有条件满足时触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(closes=[100.0, 101.0, 102.0, 103.0, 104.0])
        exit_cache = {"daily": {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=100.0),
            ],
            logic="AND",
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True

    def test_and_one_false(self):
        """AND: 一个条件不满足时不触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(closes=[100.0, 101.0, 102.0, 103.0, 104.0])
        exit_cache = {"daily": {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=100.0),
            ],
            logic="AND",
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is False

    def test_or_one_true(self):
        """OR: 任一条件满足时触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(closes=[100.0, 101.0, 102.0, 103.0, 104.0])
        exit_cache = {"daily": {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=100.0),
            ],
            logic="OR",
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True

    def test_or_none_true(self):
        """OR: 所有条件不满足时不触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(closes=[100.0, 101.0, 102.0, 103.0, 104.0])
        exit_cache = {"daily": {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=110.0),
            ],
            logic="OR",
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is False


class TestEdgeCases:
    """边界条件测试"""

    def test_empty_conditions_list(self):
        """空条件列表不触发"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        config = ExitConditionConfig(conditions=[], logic="AND")
        triggered, reason = evaluator.evaluate(config, "TEST", 3, cache, None)
        assert triggered is False
        assert reason is None

    def test_nan_indicator_value_skipped(self):
        """NaN 指标值应跳过条件"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"rsi": [float("nan")] * 5}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is False

    def test_missing_exit_cache_returns_false(self):
        """exit_indicator_cache 为 None 时，需要它的指标应跳过"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, None)
        assert triggered is False

    def test_unknown_indicator_skipped(self):
        """未知指标名称应跳过"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="unknown_xyz", operator=">", threshold=50.0),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, None)
        assert triggered is False

    def test_ma_with_period_param(self):
        """MA 指标需要 period 参数"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"ma_10": [100.0, 101.0, 102.0, 103.0, 104.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="ma", operator="<",
                    threshold=105.0, params={"period": 10},
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True

    def test_ma_without_period_skipped(self):
        """MA 指标缺少 period 参数应跳过"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="ma", operator=">", threshold=50.0),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, None)
        assert triggered is False

    def test_cross_without_cross_target_skipped(self):
        """cross 运算符缺少 cross_target 应跳过"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator="cross_down",
                    cross_target=None,
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, None)
        assert triggered is False

    def test_single_condition_and_logic(self):
        """单条件 AND 逻辑正常工作"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(closes=[100.0, 101.0, 102.0, 103.0, 104.0])

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="close", operator=">", threshold=102.0),
            ],
            logic="AND",
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, None)
        assert triggered is True


class TestCustomParamIndicators:
    """自定义参数指标测试"""

    def test_macd_with_custom_params(self):
        """MACD 自定义参数从 exit_indicator_cache 获取"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"macd_dif_8_21_5": [0.1, 0.2, 0.3, 0.4, 0.5]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator=">",
                    threshold=0.3,
                    params={"macd_fast": 8, "macd_slow": 21, "macd_signal": 5},
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 4, cache, exit_cache)
        assert triggered is True

    def test_rsi_with_custom_period(self):
        """RSI 自定义周期"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"rsi_7": [50.0, 60.0, 70.0, 85.0, 90.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="rsi", operator=">",
                    threshold=80.0,
                    params={"rsi_period": 7},
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True

    def test_boll_upper_with_custom_params(self):
        """BOLL 自定义参数"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"boll_upper_15": [110.0, 111.0, 112.0, 113.0, 114.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="boll_upper", operator="<",
                    threshold=115.0,
                    params={"boll_period": 15},
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True

    def test_dma_with_custom_params(self):
        """DMA 自定义参数"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {"daily": {"dma_5_20": [1.0, 1.5, 2.0, 2.5, 3.0]}}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="dma", operator=">",
                    threshold=2.0,
                    params={"dma_short": 5, "dma_long": 20},
                ),
            ],
        )
        triggered, _ = evaluator.evaluate(config, "TEST", 4, cache, exit_cache)
        assert triggered is True


class TestFreqResolution:
    """频率解析与按频率缓存选择测试 (需求 2.7, 2.8, 8.1)"""

    def test_resolve_freq_minute_returns_1min(self):
        """_resolve_freq('minute') 应返回 '1min' (向后兼容)"""
        assert ExitConditionEvaluator._resolve_freq("minute") == "1min"

    def test_resolve_freq_daily_unchanged(self):
        """_resolve_freq('daily') 应返回 'daily' (无变化)"""
        assert ExitConditionEvaluator._resolve_freq("daily") == "daily"

    def test_resolve_freq_5min_unchanged(self):
        """_resolve_freq('5min') 应返回 '5min' (无变化)"""
        assert ExitConditionEvaluator._resolve_freq("5min") == "5min"

    def test_condition_with_5min_uses_5min_cache(self):
        """freq='5min' 的条件应使用 '5min' 频率缓存"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {
            "daily": {"rsi": [50.0, 50.0, 50.0, 50.0, 50.0]},
            "5min": {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]},
        }

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True
        assert "RSI" in reason

    def test_condition_with_5min_falls_back_to_daily(self):
        """freq='5min' 缓存不可用时应回退到 daily 缓存"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        # 只有 daily 缓存，没有 5min 缓存
        exit_cache = {
            "daily": {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]},
        }

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True
        assert "RSI" in reason

    def test_condition_with_minute_treated_as_1min(self):
        """freq='minute' 的条件应被视为 '1min' (向后兼容)"""
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {
            "1min": {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]},
        }

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="minute", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, reason = evaluator.evaluate(config, "TEST", 3, cache, exit_cache)
        assert triggered is True
        assert "RSI" in reason


class TestMinuteScanning:
    """分钟频率日内扫描评估测试 (需求 2.1, 2.3, 2.4, 2.6, 3.1)

    Tests for _evaluate_single_minute_scanning() via the evaluate() routing.
    When minute_day_ranges is provided, minute-frequency conditions scan all
    bars in the day range instead of using bar_index directly.
    """

    # ------------------------------------------------------------------
    # Numeric condition: one bar satisfies threshold → triggers
    # ------------------------------------------------------------------

    def test_numeric_one_bar_satisfies_threshold(self):
        """5min RSI > 80: one bar in day range has RSI=85 → should trigger

        Validates: Requirements 2.1, 2.3
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Build a 5min RSI cache with 10 bars (simulating 2 days × 5 bars each)
        # Day 0 → bars 0..4, Day 1 → bars 5..9
        # Only bar index 7 has RSI=85 (above threshold), rest are below
        rsi_values = [50.0, 55.0, 60.0, 45.0, 50.0,   # day 0
                      50.0, 55.0, 85.0, 60.0, 50.0]    # day 1
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 4), (5, 9)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=1 → day 1 → scan bars 5..9, bar 7 has RSI=85 > 80
        triggered, reason = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is True
        assert "RSI" in reason
        assert "> 80" in reason

    # ------------------------------------------------------------------
    # Numeric condition: no bar satisfies threshold → does NOT trigger
    # ------------------------------------------------------------------

    def test_numeric_no_bar_satisfies_threshold(self):
        """5min RSI > 80: no bar in day range exceeds threshold → should NOT trigger

        Validates: Requirements 2.1, 2.3
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # All RSI values in day 1 (bars 5..9) are below 80
        rsi_values = [50.0, 55.0, 60.0, 45.0, 50.0,   # day 0
                      50.0, 55.0, 70.0, 60.0, 50.0]    # day 1
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 4), (5, 9)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=1 → day 1 → scan bars 5..9, none > 80
        triggered, reason = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    # ------------------------------------------------------------------
    # Cross condition: one pair shows crossover → triggers
    # ------------------------------------------------------------------

    def test_cross_one_pair_shows_crossover(self):
        """5min MACD DIF cross_down DEA: one pair in day range crosses → should trigger

        Validates: Requirements 2.1, 2.4
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Day 0 → bars 0..4, Day 1 → bars 5..9
        # In day 1: bar 6→7 shows cross_down (DIF goes from above DEA to below)
        dif_values = [0.5, 0.4, 0.3, 0.2, 0.1,        # day 0
                      0.3, 0.2, -0.1, -0.2, -0.3]      # day 1
        dea_values = [0.1, 0.1, 0.1, 0.1, 0.1,         # day 0
                      0.1, 0.1, 0.1, 0.1, 0.1]          # day 1
        exit_cache = {"5min": {"macd_dif": dif_values, "macd_dea": dea_values}}

        minute_day_ranges = {"5min": [(0, 4), (5, 9)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        # bar_index=1 → day 1 → scan pairs (5,6),(6,7),(7,8),(8,9)
        # Pair (6,7): prev DIF=0.2 >= DEA=0.1, curr DIF=-0.1 < DEA=0.1 → cross_down
        triggered, reason = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is True
        assert "cross_down" in reason
        assert "MACD_DIF" in reason
        assert "MACD_DEA" in reason

    # ------------------------------------------------------------------
    # Cross condition: no pair shows crossover → does NOT trigger
    # ------------------------------------------------------------------

    def test_cross_no_pair_shows_crossover(self):
        """5min MACD DIF cross_down DEA: no pair in day range crosses → should NOT trigger

        Validates: Requirements 2.1, 2.4
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Day 1: DIF stays above DEA throughout → no cross_down
        dif_values = [0.5, 0.4, 0.3, 0.2, 0.1,        # day 0
                      0.5, 0.4, 0.3, 0.2, 0.15]        # day 1
        dea_values = [0.1, 0.1, 0.1, 0.1, 0.1,         # day 0
                      0.1, 0.1, 0.1, 0.1, 0.1]          # day 1
        exit_cache = {"5min": {"macd_dif": dif_values, "macd_dea": dea_values}}

        minute_day_ranges = {"5min": [(0, 4), (5, 9)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        # bar_index=1 → day 1 → no cross_down in any pair
        triggered, _ = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    # ------------------------------------------------------------------
    # Edge case: single-bar day range (start_idx == end_idx)
    # ------------------------------------------------------------------

    def test_single_bar_day_range_numeric(self):
        """Single-bar day range for numeric condition → should evaluate that one bar

        Validates: Requirements 2.1, 2.3
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Day 0 has only 1 bar (index 0), Day 1 has only 1 bar (index 1)
        rsi_values = [50.0, 85.0]
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 0), (1, 1)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=1 → day 1 → single bar at index 1, RSI=85 > 80
        triggered, reason = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is True
        assert "RSI" in reason

    def test_single_bar_day_range_cross_not_triggered(self):
        """Single-bar day range for cross condition → no pair to check → should NOT trigger

        Validates: Requirements 2.4
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        dif_values = [0.5, -0.1]
        dea_values = [0.1, 0.1]
        exit_cache = {"5min": {"macd_dif": dif_values, "macd_dea": dea_values}}

        # Single bar per day → range(start+1, end+1) is empty for cross
        minute_day_ranges = {"5min": [(0, 0), (1, 1)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        # bar_index=1 → day 1 → single bar, no consecutive pair → no cross
        triggered, _ = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    # ------------------------------------------------------------------
    # Edge case: NaN values in minute cache
    # ------------------------------------------------------------------

    def test_nan_values_in_minute_cache_skipped(self):
        """NaN values in minute cache should be skipped, scanning continues

        Validates: Requirements 2.1, 2.6
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Day 0 → bars 0..3: first two are NaN, bar 2 has RSI=85, bar 3 is NaN
        rsi_values = [float("nan"), float("nan"), 85.0, float("nan")]
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 3)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=0 → day 0 → scan bars 0..3, NaN skipped, bar 2 RSI=85 > 80
        triggered, reason = evaluator.evaluate(
            config, "TEST", 0, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is True
        assert "RSI" in reason

    def test_all_nan_values_not_triggered(self):
        """All NaN values in minute cache → should NOT trigger

        Validates: Requirements 2.6
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        rsi_values = [float("nan"), float("nan"), float("nan")]
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 2)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        triggered, _ = evaluator.evaluate(
            config, "TEST", 0, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    # ------------------------------------------------------------------
    # Edge case: bar_index out of range for minute_day_ranges
    # ------------------------------------------------------------------

    def test_bar_index_out_of_range_returns_false(self):
        """bar_index exceeding minute_day_ranges length → should return (False, ...) with warning

        Validates: Requirements 2.6
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        rsi_values = [85.0, 90.0, 95.0]
        exit_cache = {"5min": {"rsi": rsi_values}}

        # Only 1 day range available
        minute_day_ranges = {"5min": [(0, 2)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=5 is out of range (only 1 entry in minute_day_ranges)
        triggered, _ = evaluator.evaluate(
            config, "TEST", 5, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    # ------------------------------------------------------------------
    # Preservation: daily-frequency NOT affected by minute_day_ranges
    # ------------------------------------------------------------------

    def test_daily_condition_unaffected_by_minute_day_ranges(self):
        """Daily-frequency condition should use bar_index directly, ignoring minute_day_ranges

        Validates: Requirements 3.1
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {
            "daily": {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]},
            "5min": {"rsi": [10.0] * 25},  # irrelevant for daily condition
        }

        # Provide minute_day_ranges — should be ignored for daily conditions
        minute_day_ranges = {"5min": [(0, 4), (5, 9), (10, 14), (15, 19), (20, 24)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=3 → daily RSI=85 > 80 → triggers via normal _evaluate_single
        triggered, reason = evaluator.evaluate(
            config, "TEST", 3, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is True
        assert "RSI" in reason
        assert "> 80" in reason

    def test_daily_condition_not_triggered_with_minute_day_ranges(self):
        """Daily-frequency condition below threshold stays false even with minute_day_ranges

        Validates: Requirements 3.1
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)
        exit_cache = {
            "daily": {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]},
            "5min": {"rsi": [85.0] * 25},  # high values, but irrelevant for daily
        }

        minute_day_ranges = {"5min": [(0, 4), (5, 9), (10, 14), (15, 19), (20, 24)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=3 → daily RSI=75 < 80 → NOT triggered
        # Even though 5min RSI values are all 85, daily condition ignores them
        triggered, _ = evaluator.evaluate(
            config, "TEST", 3, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    # ------------------------------------------------------------------
    # Additional fix-checking tests (Task 6.3)
    # ------------------------------------------------------------------

    def test_missing_minute_data_sentinel_skips_gracefully(self):
        """Sentinel (-1, -1) in minute_day_ranges → condition skipped, returns False

        When a trading day has no minute data, minute_day_ranges stores (-1, -1)
        as a sentinel. The evaluator should skip the condition gracefully.

        Validates: Requirements 2.6, 2.7
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        rsi_values = [85.0, 90.0, 95.0, 80.0, 75.0]
        exit_cache = {"5min": {"rsi": rsi_values}}

        # Day 0 has data, Day 1 is missing (sentinel), Day 2 has data
        minute_day_ranges = {"5min": [(0, 2), (-1, -1), (3, 4)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=70.0),
            ],
        )
        # bar_index=1 → sentinel (-1, -1) → should skip gracefully
        triggered, _ = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    def test_missing_minute_data_sentinel_cross_skips_gracefully(self):
        """Sentinel (-1, -1) for cross condition → condition skipped, returns False

        Validates: Requirements 2.4, 2.6
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        dif_values = [0.5, -0.1, 0.3, -0.2, 0.1]
        dea_values = [0.1, 0.1, 0.1, 0.1, 0.1]
        exit_cache = {"5min": {"macd_dif": dif_values, "macd_dea": dea_values}}

        minute_day_ranges = {"5min": [(0, 2), (-1, -1), (3, 4)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        # bar_index=1 → sentinel (-1, -1) → should skip gracefully
        triggered, _ = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is False

    def test_multiple_bars_satisfy_numeric_triggers_on_first(self):
        """Multiple bars in day range satisfy threshold → triggers (first match suffices)

        Validates: Requirements 2.1, 2.3
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Day 1 (bars 5..9): bars 6, 7, 8 all have RSI > 80
        rsi_values = [50.0, 55.0, 60.0, 45.0, 50.0,   # day 0
                      50.0, 85.0, 90.0, 82.0, 50.0]    # day 1
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 4), (5, 9)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        # bar_index=1 → day 1 → scan bars 5..9, multiple bars > 80
        triggered, reason = evaluator.evaluate(
            config, "TEST", 1, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )
        assert triggered is True
        assert "RSI" in reason
        assert "> 80" in reason

    def test_out_of_range_bar_index_logs_warning(self, caplog):
        """bar_index exceeding minute_day_ranges length logs a WARNING

        Validates: Requirements 2.6
        """
        import logging

        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        rsi_values = [85.0, 90.0, 95.0]
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 2)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        with caplog.at_level(logging.WARNING, logger="app.services.exit_condition_evaluator"):
            triggered, _ = evaluator.evaluate(
                config, "TEST", 5, cache, exit_cache,
                minute_day_ranges=minute_day_ranges,
            )
        assert triggered is False
        assert any("out of range" in record.message for record in caplog.records)

    def test_minute_numeric_reason_format_matches_daily(self):
        """Minute-frequency numeric condition reason format matches daily format

        The reason string should be e.g. "RSI > 80.0" — same format as daily conditions.

        Validates: Requirements 2.7
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        rsi_values = [85.0, 90.0, 95.0, 80.0, 75.0]
        exit_cache = {"5min": {"rsi": rsi_values}}

        minute_day_ranges = {"5min": [(0, 4)]}

        config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="5min", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        _, minute_reason = evaluator.evaluate(
            config, "TEST", 0, cache, exit_cache,
            minute_day_ranges=minute_day_ranges,
        )

        # Compare with daily format
        daily_exit_cache = {"daily": {"rsi": [85.0, 90.0, 95.0, 80.0, 75.0]}}
        daily_config = ExitConditionConfig(
            conditions=[
                ExitCondition(freq="daily", indicator="rsi", operator=">", threshold=80.0),
            ],
        )
        _, daily_reason = evaluator.evaluate(
            daily_config, "TEST", 0, cache, daily_exit_cache,
        )

        assert minute_reason == daily_reason

    def test_minute_cross_reason_format_matches_daily(self):
        """Minute-frequency cross condition reason format matches daily format

        The reason string should be e.g. "MACD_DIF cross_down MACD_DEA".

        Validates: Requirements 2.7
        """
        evaluator = ExitConditionEvaluator()
        cache = _make_cache(n=5)

        # Minute: cross_down at bars 1→2
        dif_values = [0.5, 0.2, -0.1, -0.2, -0.3]
        dea_values = [0.1, 0.1, 0.1, 0.1, 0.1]
        exit_cache_minute = {"5min": {"macd_dif": dif_values, "macd_dea": dea_values}}

        minute_day_ranges = {"5min": [(0, 4)]}

        config_minute = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="5min", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        _, minute_reason = evaluator.evaluate(
            config_minute, "TEST", 0, cache, exit_cache_minute,
            minute_day_ranges=minute_day_ranges,
        )

        # Compare with daily format
        exit_cache_daily = {"daily": {"macd_dif": dif_values, "macd_dea": dea_values}}
        config_daily = ExitConditionConfig(
            conditions=[
                ExitCondition(
                    freq="daily", indicator="macd_dif", operator="cross_down",
                    cross_target="macd_dea",
                ),
            ],
        )
        _, daily_reason = evaluator.evaluate(
            config_daily, "TEST", 2, cache, exit_cache_daily,
        )

        assert minute_reason == daily_reason
