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
        exit_cache = {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]}

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
        exit_cache = {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}

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
        exit_cache = {
            "macd_dif": [0.5, 0.3, 0.2, 0.1, -0.1],
            "macd_dea": [0.1, 0.1, 0.1, 0.1, 0.1],
        }

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
        exit_cache = {
            "macd_dif": [-0.1, -0.05, 0.0, 0.15, 0.3],
            "macd_dea": [0.1, 0.1, 0.1, 0.1, 0.1],
        }

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
        exit_cache = {
            "macd_dif": [0.5, 0.4, 0.3, 0.2, 0.15],
            "macd_dea": [0.1, 0.1, 0.1, 0.1, 0.1],
        }

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
        exit_cache = {
            "macd_dif": [0.5, 0.3],
            "macd_dea": [0.1, 0.1],
        }

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
        exit_cache = {"rsi": [50.0, 60.0, 70.0, 85.0, 90.0]}

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
        exit_cache = {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}

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
        exit_cache = {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}

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
        exit_cache = {"rsi": [50.0, 60.0, 70.0, 75.0, 78.0]}

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
        exit_cache = {"rsi": [float("nan")] * 5}

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
        exit_cache = {"ma_10": [100.0, 101.0, 102.0, 103.0, 104.0]}

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
        exit_cache = {"macd_dif_8_21_5": [0.1, 0.2, 0.3, 0.4, 0.5]}

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
        exit_cache = {"rsi_7": [50.0, 60.0, 70.0, 85.0, 90.0]}

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
        exit_cache = {"boll_upper_15": [110.0, 111.0, 112.0, 113.0, 114.0]}

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
        exit_cache = {"dma_5_20": [1.0, 1.5, 2.0, 2.5, 3.0]}

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
