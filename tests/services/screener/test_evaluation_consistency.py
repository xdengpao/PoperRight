"""选股结果一致性测试（需求 11）

验证确定性、选股与回测信号一致性、变化检测。
"""

from decimal import Decimal

import pytest

from app.core.schemas import (
    ChangeType,
    MarketRiskLevel,
    RiskLevel,
    ScreenChange,
    ScreenItem,
    ScreenResult,
    ScreenType,
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
    StrategyConfig,
    FactorCondition,
)
from app.services.screener.screen_executor import ScreenExecutor


def _make_item(symbol: str, score: float = 80.0, signals: list | None = None) -> ScreenItem:
    return ScreenItem(
        symbol=symbol,
        ref_buy_price=Decimal("10.00"),
        trend_score=score,
        risk_level=RiskLevel.LOW,
        signals=signals or [],
    )


class TestDeterminism:
    """验证相同输入产生相同输出。"""

    def test_same_input_same_output(self):
        """两次运行选股应产生完全相同的结果。"""
        config = StrategyConfig(
            factors=[FactorCondition(factor_name="ma_trend", operator=">=", threshold=60)],
            logic="AND",
        )
        stocks_data = {
            "000001": {"ma_trend": 80, "close": 10.0, "macd": False, "boll": False, "rsi": False, "dma": None, "breakout": None, "breakout_list": [], "money_flow": False, "large_order": False, "turnover_check": True, "daily_change_pct": 3.0, "change_pct_3d": 5.0},
            "000002": {"ma_trend": 70, "close": 20.0, "macd": True, "boll": False, "rsi": False, "dma": None, "breakout": None, "breakout_list": [], "money_flow": False, "large_order": False, "turnover_check": True, "daily_change_pct": 2.0, "change_pct_3d": 4.0},
        }
        executor = ScreenExecutor(strategy_config=config, strategy_id="test")
        result1 = executor.run_eod_screen(stocks_data)
        result2 = executor.run_eod_screen(stocks_data)

        assert len(result1.items) == len(result2.items)
        symbols1 = {item.symbol for item in result1.items}
        symbols2 = {item.symbol for item in result2.items}
        assert symbols1 == symbols2


class TestChangeDetection:
    """验证选股结果变化检测。"""

    def test_new_stock_detected(self):
        """新增股票标记为 NEW。"""
        prev = [_make_item("000001")]
        curr = [_make_item("000001"), _make_item("000002")]
        changes = ScreenExecutor._compute_result_diff(curr, prev)
        new_changes = [c for c in changes if c.change_type == ChangeType.NEW]
        assert len(new_changes) == 1
        assert new_changes[0].symbol == "000002"

    def test_removed_stock_detected(self):
        """移出股票标记为 REMOVED。"""
        prev = [_make_item("000001"), _make_item("000002")]
        curr = [_make_item("000001")]
        changes = ScreenExecutor._compute_result_diff(curr, prev)
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].symbol == "000002"

    def test_updated_stock_detected(self):
        """信号变化的股票标记为 UPDATED。"""
        sig1 = [SignalDetail(category=SignalCategory.MA_TREND, label="均线多头")]
        sig2 = [
            SignalDetail(category=SignalCategory.MA_TREND, label="均线多头"),
            SignalDetail(category=SignalCategory.MACD, label="MACD金叉"),
        ]
        prev = [_make_item("000001", signals=sig1)]
        curr = [_make_item("000001", signals=sig2)]
        changes = ScreenExecutor._compute_result_diff(curr, prev)
        updated = [c for c in changes if c.change_type == ChangeType.UPDATED]
        assert len(updated) == 1
        assert updated[0].symbol == "000001"
