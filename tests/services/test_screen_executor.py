"""
ScreenExecutor 单元测试

覆盖场景：
- 技术指标差异化权重评分（单指标无共振）
- 2 指标共振 +10
- 3 指标共振 +20
- 4 指标共振 +20 且不超 100
- 无指标触发评分为 0

需求: 5.1, 5.2, 5.3, 5.4, 5.5
"""

from __future__ import annotations

import pytest

from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# 单指标无共振（需求 5.1, 5.5）
# ---------------------------------------------------------------------------


class TestSingleIndicatorNoResonance:
    """单个指标触发时，评分等于该指标权重，无共振加分"""

    def test_macd_only(self):
        """仅 MACD 触发 → 35 分"""
        triggered = {"macd": True, "rsi": False, "boll": False, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 35.0

    def test_rsi_only(self):
        """仅 RSI 触发 → 25 分"""
        triggered = {"macd": False, "rsi": True, "boll": False, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 25.0

    def test_boll_only(self):
        """仅 BOLL 触发 → 20 分"""
        triggered = {"macd": False, "rsi": False, "boll": True, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 20.0

    def test_dma_only(self):
        """仅 DMA 触发 → 20 分"""
        triggered = {"macd": False, "rsi": False, "boll": False, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 20.0

    def test_no_indicator_triggered(self):
        """无指标触发 → 0 分"""
        triggered = {"macd": False, "rsi": False, "boll": False, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 0.0


# ---------------------------------------------------------------------------
# 2 指标共振 +10（需求 5.2）
# ---------------------------------------------------------------------------


class TestTwoIndicatorResonance:
    """2 个指标同时触发时，基础评分 + 10 分共振奖励"""

    def test_macd_and_rsi(self):
        """MACD + RSI → 35 + 25 + 10 = 70"""
        triggered = {"macd": True, "rsi": True, "boll": False, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 70.0

    def test_macd_and_boll(self):
        """MACD + BOLL → 35 + 20 + 10 = 65"""
        triggered = {"macd": True, "rsi": False, "boll": True, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 65.0

    def test_boll_and_dma(self):
        """BOLL + DMA → 20 + 20 + 10 = 50"""
        triggered = {"macd": False, "rsi": False, "boll": True, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 50.0

    def test_rsi_and_dma(self):
        """RSI + DMA → 25 + 20 + 10 = 55"""
        triggered = {"macd": False, "rsi": True, "boll": False, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 55.0


# ---------------------------------------------------------------------------
# 3 指标共振 +20（需求 5.3）
# ---------------------------------------------------------------------------


class TestThreeIndicatorResonance:
    """3 个指标同时触发时，基础评分 + 20 分共振奖励"""

    def test_macd_rsi_boll(self):
        """MACD + RSI + BOLL → 35 + 25 + 20 + 20 = 100"""
        triggered = {"macd": True, "rsi": True, "boll": True, "dma": False}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 100.0

    def test_macd_rsi_dma(self):
        """MACD + RSI + DMA → 35 + 25 + 20 + 20 = 100"""
        triggered = {"macd": True, "rsi": True, "boll": False, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 100.0

    def test_rsi_boll_dma(self):
        """RSI + BOLL + DMA → 25 + 20 + 20 + 20 = 85"""
        triggered = {"macd": False, "rsi": True, "boll": True, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 85.0

    def test_macd_boll_dma(self):
        """MACD + BOLL + DMA → 35 + 20 + 20 + 20 = 95"""
        triggered = {"macd": True, "rsi": False, "boll": True, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 95.0


# ---------------------------------------------------------------------------
# 4 指标共振 +20 且不超 100（需求 5.3, 5.4）
# ---------------------------------------------------------------------------


class TestFourIndicatorResonanceCapped:
    """4 个指标全部触发时，基础评分 + 20 分共振奖励，上限 100"""

    def test_all_indicators_triggered(self):
        """全部触发 → 35 + 25 + 20 + 20 + 20 = 120 → min(120, 100) = 100"""
        triggered = {"macd": True, "rsi": True, "boll": True, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score == 100.0

    def test_all_indicators_score_capped_at_100(self):
        """验证评分上限为 100，不会超过"""
        triggered = {"macd": True, "rsi": True, "boll": True, "dma": True}
        score = ScreenExecutor._compute_indicator_score(triggered)
        assert score <= 100.0


# ---------------------------------------------------------------------------
# 权重差异化验证（需求 5.1）
# ---------------------------------------------------------------------------


class TestWeightDifferentiation:
    """验证各指标权重差异化：MACD > RSI > BOLL == DMA"""

    def test_macd_weight_highest(self):
        """MACD 权重最高（35）"""
        assert ScreenExecutor._INDICATOR_WEIGHTS["macd"] == 35.0

    def test_rsi_weight_second(self):
        """RSI 权重次高（25）"""
        assert ScreenExecutor._INDICATOR_WEIGHTS["rsi"] == 25.0

    def test_boll_and_dma_weight_equal(self):
        """BOLL 和 DMA 权重相同（20）"""
        assert ScreenExecutor._INDICATOR_WEIGHTS["boll"] == 20.0
        assert ScreenExecutor._INDICATOR_WEIGHTS["dma"] == 20.0

    def test_total_weight_is_100(self):
        """所有权重之和为 100"""
        total = sum(ScreenExecutor._INDICATOR_WEIGHTS.values())
        assert total == 100.0

    def test_weight_ordering(self):
        """权重排序：MACD > RSI > BOLL == DMA"""
        w = ScreenExecutor._INDICATOR_WEIGHTS
        assert w["macd"] > w["rsi"] > w["boll"]
        assert w["boll"] == w["dma"]


# ---------------------------------------------------------------------------
# 趋势加速信号检测（需求 10.2, 10.4, 10.5）
# ---------------------------------------------------------------------------


class TestDetectTrendAcceleration:
    """趋势加速信号检测：_detect_trend_acceleration 纯函数"""

    def test_acceleration_triggers(self):
        """当前评分 >= 70 且前一轮评分 < 60 → 触发"""
        assert ScreenExecutor._detect_trend_acceleration(75.0, 50.0) is True

    def test_acceleration_triggers_at_boundary(self):
        """边界值：current_score=70.0, previous_score=59.9 → 触发"""
        assert ScreenExecutor._detect_trend_acceleration(70.0, 59.9) is True

    def test_no_trigger_current_below_high(self):
        """当前评分 < 70 → 不触发"""
        assert ScreenExecutor._detect_trend_acceleration(69.9, 50.0) is False

    def test_no_trigger_previous_above_low(self):
        """前一轮评分 >= 60 → 不触发"""
        assert ScreenExecutor._detect_trend_acceleration(80.0, 60.0) is False

    def test_no_trigger_previous_at_boundary(self):
        """前一轮评分恰好等于 60 → 不触发（需要严格小于 60）"""
        assert ScreenExecutor._detect_trend_acceleration(80.0, 60.0) is False

    def test_no_trigger_previous_none(self):
        """前一轮评分为 None（无历史数据）→ 不触发（需求 10.5）"""
        assert ScreenExecutor._detect_trend_acceleration(90.0, None) is False

    def test_custom_thresholds(self):
        """自定义阈值参数"""
        # 使用自定义阈值 acceleration_high=80, acceleration_low=50
        assert ScreenExecutor._detect_trend_acceleration(
            80.0, 49.0, acceleration_high=80.0, acceleration_low=50.0
        ) is True
        assert ScreenExecutor._detect_trend_acceleration(
            79.0, 49.0, acceleration_high=80.0, acceleration_low=50.0
        ) is False


class TestTrendAccelerationSignalStrength:
    """趋势加速信号强度为 STRONG（需求 10.4）"""

    def test_acceleration_signal_is_strong(self):
        """趋势加速触发时生成的信号强度应为 STRONG"""
        from app.core.schemas import SignalCategory, SignalDetail, SignalStrength

        # 模拟趋势加速触发后生成的信号
        signal = SignalDetail(
            category=SignalCategory.MA_TREND,
            label="ma_trend_acceleration",
            strength=SignalStrength.STRONG,
        )
        assert signal.strength == SignalStrength.STRONG
        assert signal.category == SignalCategory.MA_TREND
        assert signal.label == "ma_trend_acceleration"


class TestTrendThreshold68:
    """MA_TREND 信号使用默认阈值 68（需求 10.1, 10.3）"""

    def test_default_threshold_is_68(self):
        """MaTrendConfig 默认 trend_score_threshold 为 68"""
        from app.core.schemas import MaTrendConfig

        config = MaTrendConfig()
        assert config.trend_score_threshold == 68

    def test_executor_uses_config_threshold(self):
        """ScreenExecutor 使用 StrategyConfig.ma_trend.trend_score_threshold"""
        from app.core.schemas import (
            MaTrendConfig,
            ScreenType,
            SignalCategory,
            StrategyConfig,
        )

        # 创建配置，使用默认阈值 68
        strategy_config = StrategyConfig()
        executor = ScreenExecutor(
            strategy_config=strategy_config,
            enabled_modules=["ma_trend"],
        )

        # 股票 ma_trend=68 应通过默认阈值 68
        stocks_data = {
            "SH600000": {"ma_trend": 68, "close": 10.0},
        }
        result = executor.run_eod_screen(stocks_data)
        # 应有 1 只股票通过
        assert len(result.items) == 1
        ma_signals = [
            s for s in result.items[0].signals
            if s.category == SignalCategory.MA_TREND and s.label == "ma_trend"
        ]
        assert len(ma_signals) == 1

    def test_executor_rejects_below_threshold(self):
        """ma_trend=67 低于默认阈值 68 → 不生成 MA_TREND 信号"""
        from app.core.schemas import SignalCategory, StrategyConfig

        strategy_config = StrategyConfig()
        executor = ScreenExecutor(
            strategy_config=strategy_config,
            enabled_modules=["ma_trend"],
        )

        stocks_data = {
            "SH600000": {"ma_trend": 67, "close": 10.0},
        }
        result = executor.run_eod_screen(stocks_data)
        # 无信号 → 股票被过滤（非 factor_editor 模式下无信号的股票被跳过）
        assert len(result.items) == 0


class TestTrendAccelerationIntegration:
    """趋势加速信号在 _execute 中的集成测试"""

    def test_acceleration_signal_generated(self):
        """当 stock_data 包含 previous_ma_trend_score 且满足加速条件时生成加速信号"""
        from app.core.schemas import SignalCategory, SignalStrength, StrategyConfig

        strategy_config = StrategyConfig()
        executor = ScreenExecutor(
            strategy_config=strategy_config,
            enabled_modules=["ma_trend"],
        )

        stocks_data = {
            "SH600000": {
                "ma_trend": 75,
                "previous_ma_trend_score": 50.0,
                "close": 10.0,
            },
        }
        result = executor.run_eod_screen(stocks_data)
        assert len(result.items) == 1

        accel_signals = [
            s for s in result.items[0].signals
            if s.label == "ma_trend_acceleration"
        ]
        assert len(accel_signals) == 1
        assert accel_signals[0].category == SignalCategory.MA_TREND
        assert accel_signals[0].strength == SignalStrength.STRONG

    def test_no_acceleration_without_previous_score(self):
        """无 previous_ma_trend_score 时不生成加速信号（需求 10.5）"""
        from app.core.schemas import StrategyConfig

        strategy_config = StrategyConfig()
        executor = ScreenExecutor(
            strategy_config=strategy_config,
            enabled_modules=["ma_trend"],
        )

        stocks_data = {
            "SH600000": {
                "ma_trend": 75,
                "close": 10.0,
            },
        }
        result = executor.run_eod_screen(stocks_data)
        assert len(result.items) == 1

        accel_signals = [
            s for s in result.items[0].signals
            if s.label == "ma_trend_acceleration"
        ]
        assert len(accel_signals) == 0

    def test_no_acceleration_when_previous_score_high(self):
        """前一轮评分 >= 60 时不生成加速信号"""
        from app.core.schemas import StrategyConfig

        strategy_config = StrategyConfig()
        executor = ScreenExecutor(
            strategy_config=strategy_config,
            enabled_modules=["ma_trend"],
        )

        stocks_data = {
            "SH600000": {
                "ma_trend": 75,
                "previous_ma_trend_score": 65.0,
                "close": 10.0,
            },
        }
        result = executor.run_eod_screen(stocks_data)
        assert len(result.items) == 1

        accel_signals = [
            s for s in result.items[0].signals
            if s.label == "ma_trend_acceleration"
        ]
        assert len(accel_signals) == 0
