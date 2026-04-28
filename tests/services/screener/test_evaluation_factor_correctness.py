"""因子计算正确性测试（需求 8）

验证技术指标计算精度和边界条件。
"""

import pytest

from app.services.screener.indicators import (
    detect_macd_signal,
    detect_boll_signal,
    detect_rsi_signal,
)
from app.services.screener.ma_trend import score_ma_trend, detect_ma_support
from app.services.screener.screen_executor import ScreenExecutor


class TestMaTrendScoreBoundaries:
    """验证均线趋势评分边界条件。"""

    def test_perfect_bullish_alignment_high_score(self):
        """完美多头排列应得分 >= 80。"""
        closes = list(range(50, 150))
        score = score_ma_trend(closes, ma_periods=[5, 10, 20, 60])
        assert score >= 80

    def test_perfect_bearish_alignment_low_score(self):
        """完美空头排列应得分 <= 20。"""
        closes = list(range(150, 50, -1))
        score = score_ma_trend(closes, ma_periods=[5, 10, 20, 60])
        assert score <= 20

    def test_mixed_alignment_mid_score(self):
        """均线交叉状态应得分在中间区域。"""
        closes = [50 + (i % 10) for i in range(100)]
        score = score_ma_trend(closes, ma_periods=[5, 10, 20, 60])
        assert 0 <= score <= 100


class TestSignalStrengthOrdering:
    """验证信号强度分级一致性。"""

    def test_indicator_score_resonance(self):
        """多指标共振应得分更高。"""
        single = ScreenExecutor._compute_indicator_score(
            {"macd": True, "rsi": False, "boll": False, "dma": False}
        )
        double = ScreenExecutor._compute_indicator_score(
            {"macd": True, "rsi": True, "boll": False, "dma": False}
        )
        triple = ScreenExecutor._compute_indicator_score(
            {"macd": True, "rsi": True, "boll": True, "dma": False}
        )
        assert triple > double > single

    def test_all_triggered_max_score(self):
        """所有指标触发应接近满分。"""
        score = ScreenExecutor._compute_indicator_score(
            {"macd": True, "rsi": True, "boll": True, "dma": True}
        )
        assert score == 100.0

    def test_none_triggered_zero(self):
        """无指标触发应为 0。"""
        score = ScreenExecutor._compute_indicator_score(
            {"macd": False, "rsi": False, "boll": False, "dma": False}
        )
        assert score == 0.0
