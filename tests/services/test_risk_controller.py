"""
风控模块单元测试

覆盖：
- MarketRiskChecker: 大盘风控状态检测
  - check_market_risk: NORMAL / CAUTION / DANGER 判定
  - get_trend_threshold: 阈值返回
  - is_buy_suspended: 买入暂停判定
- StockRiskFilter: 个股风控过滤
  - check_daily_gain: 单日涨幅 > 9% 剔除
  - check_3day_cumulative_gain: 连续 3 日累计涨幅 > 20% 剔除
- BlackWhiteListManager: 黑白名单管理
  - 增删查操作
  - 黑名单/白名单独立性
- PositionRiskChecker: 事中风控
  - check_stock_position_limit: 单只个股仓位 ≤ 15%
  - check_sector_position_limit: 单一板块仓位 ≤ 30%
  - check_position_breakdown: 持仓破位预警
"""

from __future__ import annotations

import pytest

from app.core.schemas import MarketRiskLevel
from app.services.risk_controller import (
    MarketRiskChecker,
    StockRiskFilter,
    BlackWhiteListManager,
    PositionRiskChecker,
    _NORMAL_THRESHOLD,
    _CAUTION_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_closes(base: float, count: int) -> list[float]:
    """生成 count 个相同值的收盘价序列"""
    return [base] * count


def _make_uptrend(base: float, count: int, step: float = 1.0) -> list[float]:
    """生成上升趋势的收盘价序列"""
    return [base + i * step for i in range(count)]


def _make_downtrend(base: float, count: int, step: float = 1.0) -> list[float]:
    """生成下降趋势的收盘价序列"""
    return [base - i * step for i in range(count)]


# ===========================================================================
# MarketRiskChecker
# ===========================================================================


class TestCheckMarketRisk:
    """check_market_risk 测试"""

    def test_empty_closes_returns_normal(self):
        """空数据返回 NORMAL"""
        checker = MarketRiskChecker()
        assert checker.check_market_risk([]) == MarketRiskLevel.NORMAL

    def test_insufficient_data_returns_normal(self):
        """数据不足 20 日返回 NORMAL"""
        checker = MarketRiskChecker()
        assert checker.check_market_risk([100.0] * 10) == MarketRiskLevel.NORMAL

    def test_price_above_all_ma_returns_normal(self):
        """价格在所有均线上方 → NORMAL"""
        checker = MarketRiskChecker()
        # 60 日均线 = 100，最新价 = 110
        closes = [100.0] * 59 + [110.0]
        assert checker.check_market_risk(closes) == MarketRiskLevel.NORMAL

    def test_price_below_ma20_above_ma60_returns_caution(self):
        """价格跌破 20 日均线但在 60 日均线上方 → CAUTION"""
        checker = MarketRiskChecker()
        # 构造：前 40 日 = 100，后 19 日 = 110，最新 = 105
        # MA60 ≈ (40*100 + 19*110 + 105) / 60 ≈ 103.4
        # MA20 = (19*110 + 105) / 20 = 109.75
        # 最新价 105 < MA20(109.75) 但 > MA60(103.4)
        closes = [100.0] * 40 + [110.0] * 19 + [105.0]
        result = checker.check_market_risk(closes)
        assert result == MarketRiskLevel.CAUTION

    def test_price_below_ma60_returns_danger(self):
        """价格跌破 60 日均线 → DANGER"""
        checker = MarketRiskChecker()
        # 前 59 日 = 100，最新 = 90 → MA60 ≈ 99.83，最新 < MA60
        closes = [100.0] * 59 + [90.0]
        result = checker.check_market_risk(closes)
        assert result == MarketRiskLevel.DANGER

    def test_price_exactly_at_ma20_returns_normal(self):
        """价格恰好等于 20 日均线 → NORMAL（不是 < 才触发）"""
        checker = MarketRiskChecker()
        closes = [100.0] * 60
        result = checker.check_market_risk(closes)
        assert result == MarketRiskLevel.NORMAL

    def test_price_exactly_at_ma60_returns_normal(self):
        """价格恰好等于 60 日均线 → NORMAL"""
        checker = MarketRiskChecker()
        closes = [100.0] * 60
        result = checker.check_market_risk(closes)
        assert result == MarketRiskLevel.NORMAL

    def test_data_between_20_and_60_only_checks_ma20(self):
        """数据量在 20-59 之间，只检查 MA20"""
        checker = MarketRiskChecker()
        # 30 日数据，前 29 日 = 100，最新 = 95
        # MA20 = (9*100 + 10*100 + 95) / 20 ≈ 99.75
        closes = [100.0] * 29 + [95.0]
        result = checker.check_market_risk(closes)
        assert result == MarketRiskLevel.CAUTION

    def test_downtrend_triggers_danger(self):
        """持续下跌趋势 → DANGER"""
        checker = MarketRiskChecker()
        closes = _make_downtrend(200.0, 70, step=1.0)
        result = checker.check_market_risk(closes)
        assert result == MarketRiskLevel.DANGER


class TestGetTrendThreshold:
    """get_trend_threshold 测试"""

    def test_normal_returns_80(self):
        assert MarketRiskChecker.get_trend_threshold(MarketRiskLevel.NORMAL) == _NORMAL_THRESHOLD

    def test_caution_returns_90(self):
        assert MarketRiskChecker.get_trend_threshold(MarketRiskLevel.CAUTION) == _CAUTION_THRESHOLD

    def test_danger_returns_90(self):
        assert MarketRiskChecker.get_trend_threshold(MarketRiskLevel.DANGER) == _CAUTION_THRESHOLD


class TestIsBuySuspended:
    """is_buy_suspended 测试"""

    def test_normal_not_suspended(self):
        assert MarketRiskChecker.is_buy_suspended(MarketRiskLevel.NORMAL) is False

    def test_caution_not_suspended(self):
        assert MarketRiskChecker.is_buy_suspended(MarketRiskLevel.CAUTION) is False

    def test_danger_is_suspended(self):
        assert MarketRiskChecker.is_buy_suspended(MarketRiskLevel.DANGER) is True


# ===========================================================================
# StockRiskFilter
# ===========================================================================


class TestCheckDailyGain:
    """check_daily_gain 测试"""

    def test_gain_above_9_excluded(self):
        """涨幅 > 9% 应剔除"""
        assert StockRiskFilter.check_daily_gain(9.5) is True

    def test_gain_exactly_9_not_excluded(self):
        """涨幅恰好 9% 不剔除"""
        assert StockRiskFilter.check_daily_gain(9.0) is False

    def test_gain_below_9_not_excluded(self):
        """涨幅 < 9% 不剔除"""
        assert StockRiskFilter.check_daily_gain(5.0) is False

    def test_negative_gain_not_excluded(self):
        """跌幅不剔除"""
        assert StockRiskFilter.check_daily_gain(-5.0) is False

    def test_zero_gain_not_excluded(self):
        """零涨幅不剔除"""
        assert StockRiskFilter.check_daily_gain(0.0) is False

    def test_limit_up_10_excluded(self):
        """涨停 10% 应剔除"""
        assert StockRiskFilter.check_daily_gain(10.0) is True

    def test_limit_up_20_excluded(self):
        """创业板涨停 20% 应剔除"""
        assert StockRiskFilter.check_daily_gain(20.0) is True


class TestCheck3DayCumulativeGain:
    """check_3day_cumulative_gain 测试"""

    def test_cumulative_above_20_excluded(self):
        """3 日累计涨幅 > 20% 应剔除"""
        # (1.08)(1.08)(1.08) - 1 = 0.2597 → 25.97% > 20%
        assert StockRiskFilter.check_3day_cumulative_gain([8.0, 8.0, 8.0]) is True

    def test_cumulative_below_20_not_excluded(self):
        """3 日累计涨幅 < 20% 不剔除"""
        # (1.05)(1.05)(1.05) - 1 = 0.1576 → 15.76% < 20%
        assert StockRiskFilter.check_3day_cumulative_gain([5.0, 5.0, 5.0]) is False

    def test_cumulative_at_boundary_not_excluded(self):
        """3 日累计涨幅接近但不超过 20% 不剔除"""
        # (1.06)(1.06)(1.06) - 1 = 0.1910 → 19.10% < 20%
        assert StockRiskFilter.check_3day_cumulative_gain([6.0, 6.0, 6.0]) is False

    def test_insufficient_data_not_excluded(self):
        """数据不足 3 日不剔除"""
        assert StockRiskFilter.check_3day_cumulative_gain([10.0, 10.0]) is False
        assert StockRiskFilter.check_3day_cumulative_gain([10.0]) is False
        assert StockRiskFilter.check_3day_cumulative_gain([]) is False

    def test_uses_last_3_days(self):
        """使用最近 3 日数据"""
        # 前面的数据不影响结果
        # 最近 3 日：[2.0, 2.0, 2.0] → 累计 ≈ 6.12% < 20%
        assert StockRiskFilter.check_3day_cumulative_gain([10.0, 10.0, 2.0, 2.0, 2.0]) is False

    def test_negative_days_reduce_cumulative(self):
        """含跌幅的日子降低累计涨幅"""
        # [10.0, -5.0, 10.0] → (1.10)(0.95)(1.10) = 1.1495 → 14.95% < 20%
        assert StockRiskFilter.check_3day_cumulative_gain([10.0, -5.0, 10.0]) is False

    def test_large_single_day_with_small_others(self):
        """单日大涨 + 其他小涨"""
        # [15.0, 3.0, 3.0] → (1.15)(1.03)(1.03) = 1.2204 → 22.04% > 20%
        assert StockRiskFilter.check_3day_cumulative_gain([15.0, 3.0, 3.0]) is True


# ===========================================================================
# BlackWhiteListManager
# ===========================================================================


class TestBlacklistOperations:
    """黑名单操作测试"""

    def test_add_and_check(self):
        mgr = BlackWhiteListManager()
        mgr.add_to_blacklist("600000", "异常波动")
        assert mgr.is_blacklisted("600000") is True

    def test_not_blacklisted_by_default(self):
        mgr = BlackWhiteListManager()
        assert mgr.is_blacklisted("600000") is False

    def test_remove_from_blacklist(self):
        mgr = BlackWhiteListManager()
        mgr.add_to_blacklist("600000", "异常波动")
        mgr.remove_from_blacklist("600000")
        assert mgr.is_blacklisted("600000") is False

    def test_remove_nonexistent_no_error(self):
        """移除不存在的股票不报错"""
        mgr = BlackWhiteListManager()
        mgr.remove_from_blacklist("999999")  # should not raise

    def test_get_blacklist(self):
        mgr = BlackWhiteListManager()
        mgr.add_to_blacklist("600000", "reason1")
        mgr.add_to_blacklist("000001", "reason2")
        assert mgr.get_blacklist() == {"600000", "000001"}

    def test_get_blacklist_empty(self):
        mgr = BlackWhiteListManager()
        assert mgr.get_blacklist() == set()

    def test_overwrite_reason(self):
        """重复添加更新原因"""
        mgr = BlackWhiteListManager()
        mgr.add_to_blacklist("600000", "reason1")
        mgr.add_to_blacklist("600000", "reason2")
        assert mgr.is_blacklisted("600000") is True
        assert mgr.get_blacklist() == {"600000"}


class TestWhitelistOperations:
    """白名单操作测试"""

    def test_add_and_check(self):
        mgr = BlackWhiteListManager()
        mgr.add_to_whitelist("600000")
        assert mgr.is_whitelisted("600000") is True

    def test_not_whitelisted_by_default(self):
        mgr = BlackWhiteListManager()
        assert mgr.is_whitelisted("600000") is False

    def test_remove_from_whitelist(self):
        mgr = BlackWhiteListManager()
        mgr.add_to_whitelist("600000")
        mgr.remove_from_whitelist("600000")
        assert mgr.is_whitelisted("600000") is False

    def test_remove_nonexistent_no_error(self):
        """移除不存在的股票不报错"""
        mgr = BlackWhiteListManager()
        mgr.remove_from_whitelist("999999")  # should not raise

    def test_get_whitelist(self):
        mgr = BlackWhiteListManager()
        mgr.add_to_whitelist("600000")
        mgr.add_to_whitelist("000001")
        assert mgr.get_whitelist() == {"600000", "000001"}

    def test_get_whitelist_empty(self):
        mgr = BlackWhiteListManager()
        assert mgr.get_whitelist() == set()

    def test_duplicate_add_idempotent(self):
        """重复添加幂等"""
        mgr = BlackWhiteListManager()
        mgr.add_to_whitelist("600000")
        mgr.add_to_whitelist("600000")
        assert mgr.get_whitelist() == {"600000"}


class TestBlackWhiteListIndependence:
    """黑白名单独立性测试"""

    def test_blacklist_and_whitelist_independent(self):
        """黑名单和白名单互不影响"""
        mgr = BlackWhiteListManager()
        mgr.add_to_blacklist("600000", "bad")
        mgr.add_to_whitelist("000001")
        assert mgr.is_blacklisted("600000") is True
        assert mgr.is_whitelisted("600000") is False
        assert mgr.is_blacklisted("000001") is False
        assert mgr.is_whitelisted("000001") is True

    def test_same_stock_can_be_in_both(self):
        """同一股票可以同时在黑名单和白名单中（业务层决定优先级）"""
        mgr = BlackWhiteListManager()
        mgr.add_to_blacklist("600000", "bad")
        mgr.add_to_whitelist("600000")
        assert mgr.is_blacklisted("600000") is True
        assert mgr.is_whitelisted("600000") is True


# ===========================================================================
# PositionRiskChecker — 事中风控
# ===========================================================================


class TestCheckStockPositionLimit:
    """check_stock_position_limit 测试（需求 10.1）"""

    def test_within_limit_passes(self):
        """仓位 < 15% → 通过"""
        result = PositionRiskChecker.check_stock_position_limit(10.0)
        assert result.passed is True
        assert result.reason is None

    def test_at_limit_passes(self):
        """仓位恰好 15% → 通过（不是 > 才拒绝）"""
        result = PositionRiskChecker.check_stock_position_limit(15.0)
        assert result.passed is True

    def test_above_limit_rejected(self):
        """仓位 > 15% → 拒绝"""
        result = PositionRiskChecker.check_stock_position_limit(15.5)
        assert result.passed is False
        assert result.reason is not None
        assert "15" in result.reason

    def test_zero_weight_passes(self):
        """零仓位 → 通过"""
        result = PositionRiskChecker.check_stock_position_limit(0.0)
        assert result.passed is True

    def test_custom_max_pct(self):
        """自定义上限"""
        result = PositionRiskChecker.check_stock_position_limit(12.0, max_pct=10.0)
        assert result.passed is False

    def test_custom_max_pct_within(self):
        """自定义上限内 → 通过"""
        result = PositionRiskChecker.check_stock_position_limit(8.0, max_pct=10.0)
        assert result.passed is True

    def test_slightly_above_limit(self):
        """仓位略超上限"""
        result = PositionRiskChecker.check_stock_position_limit(15.01)
        assert result.passed is False


class TestCheckSectorPositionLimit:
    """check_sector_position_limit 测试（需求 10.2）"""

    def test_within_limit_passes(self):
        """板块仓位 < 30% → 通过"""
        result = PositionRiskChecker.check_sector_position_limit(20.0)
        assert result.passed is True
        assert result.reason is None

    def test_at_limit_passes(self):
        """板块仓位恰好 30% → 通过"""
        result = PositionRiskChecker.check_sector_position_limit(30.0)
        assert result.passed is True

    def test_above_limit_rejected(self):
        """板块仓位 > 30% → 拒绝"""
        result = PositionRiskChecker.check_sector_position_limit(31.0)
        assert result.passed is False
        assert result.reason is not None
        assert "30" in result.reason

    def test_zero_weight_passes(self):
        """零仓位 → 通过"""
        result = PositionRiskChecker.check_sector_position_limit(0.0)
        assert result.passed is True

    def test_custom_max_pct(self):
        """自定义上限"""
        result = PositionRiskChecker.check_sector_position_limit(25.0, max_pct=20.0)
        assert result.passed is False

    def test_custom_max_pct_within(self):
        """自定义上限内 → 通过"""
        result = PositionRiskChecker.check_sector_position_limit(15.0, max_pct=20.0)
        assert result.passed is True

    def test_slightly_above_limit(self):
        """板块仓位略超上限"""
        result = PositionRiskChecker.check_sector_position_limit(30.01)
        assert result.passed is False


class TestCheckPositionBreakdown:
    """check_position_breakdown 测试（需求 10.3）"""

    def test_all_conditions_met_triggers_alert(self):
        """三个条件全满足 → 触发预警"""
        # price < ma20, decline > 5%, volume_ratio > 1.0
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=1.5
        ) is True

    def test_price_above_ma20_no_alert(self):
        """价格在 MA20 上方 → 不触发"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=11.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=1.5
        ) is False

    def test_decline_less_than_5_no_alert(self):
        """跌幅不足 5% → 不触发"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-3.0, volume_ratio=1.5
        ) is False

    def test_low_volume_no_alert(self):
        """缩量（量比 ≤ 1.0）→ 不触发"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=0.8
        ) is False

    def test_exactly_at_ma20_no_alert(self):
        """价格恰好等于 MA20 → 不触发（需要 < 才触发）"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=10.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=1.5
        ) is False

    def test_exactly_5pct_decline_no_alert(self):
        """跌幅恰好 5% → 不触发（需要 < -5% 才触发）"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-5.0, volume_ratio=1.5
        ) is False

    def test_exactly_volume_ratio_1_no_alert(self):
        """量比恰好 1.0 → 不触发（需要 > 1.0 才触发）"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=1.0
        ) is False

    def test_severe_breakdown_triggers(self):
        """严重破位 → 触发"""
        assert PositionRiskChecker.check_position_breakdown(
            current_price=8.0, ma20=12.0, daily_change_pct=-10.0, volume_ratio=3.0
        ) is True

    def test_only_two_conditions_no_alert(self):
        """只满足两个条件 → 不触发"""
        # below ma20 + heavy decline, but low volume
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=0.5
        ) is False
        # below ma20 + heavy volume, but small decline
        assert PositionRiskChecker.check_position_breakdown(
            current_price=9.0, ma20=10.0, daily_change_pct=-2.0, volume_ratio=1.5
        ) is False
        # heavy decline + heavy volume, but above ma20
        assert PositionRiskChecker.check_position_breakdown(
            current_price=11.0, ma20=10.0, daily_change_pct=-6.0, volume_ratio=1.5
        ) is False


# ===========================================================================
# StopLossChecker — 事后止损止盈
# ===========================================================================

from app.services.risk_controller import StopLossChecker


class TestCheckFixedStopLoss:
    """check_fixed_stop_loss 测试（需求 11.1）"""

    def test_loss_exceeds_5pct_triggers(self):
        """亏损 >= 5% → 触发"""
        # cost=100, current=94 → loss=6% >= 5%
        assert StopLossChecker.check_fixed_stop_loss(100.0, 94.0, 0.05) is True

    def test_loss_exactly_5pct_triggers(self):
        """亏损恰好 5% → 触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 95.0, 0.05) is True

    def test_loss_below_5pct_no_trigger(self):
        """亏损 < 5% → 不触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 96.0, 0.05) is False

    def test_loss_exceeds_8pct_triggers(self):
        """亏损 >= 8% → 触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 91.0, 0.08) is True

    def test_loss_exactly_8pct_triggers(self):
        """亏损恰好 8% → 触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 92.0, 0.08) is True

    def test_loss_below_8pct_no_trigger(self):
        """亏损 < 8% → 不触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 93.0, 0.08) is False

    def test_loss_exceeds_10pct_triggers(self):
        """亏损 >= 10% → 触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 89.0, 0.10) is True

    def test_loss_exactly_10pct_triggers(self):
        """亏损恰好 10% → 触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 90.0, 0.10) is True

    def test_loss_below_10pct_no_trigger(self):
        """亏损 < 10% → 不触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 91.0, 0.10) is False

    def test_price_above_cost_no_trigger(self):
        """盈利状态 → 不触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 110.0, 0.05) is False

    def test_price_equal_cost_no_trigger(self):
        """持平 → 不触发"""
        assert StopLossChecker.check_fixed_stop_loss(100.0, 100.0, 0.05) is False

    def test_zero_cost_price_no_trigger(self):
        """成本价为 0 → 不触发（防除零）"""
        assert StopLossChecker.check_fixed_stop_loss(0.0, 50.0, 0.05) is False


class TestCheckTrailingStopLoss:
    """check_trailing_stop_loss 测试（需求 11.2）"""

    def test_retrace_exceeds_3pct_triggers(self):
        """从最高价回撤 >= 3% → 触发"""
        # peak=100, current=96 → retrace=4% >= 3%
        assert StopLossChecker.check_trailing_stop_loss(100.0, 96.0, 0.03) is True

    def test_retrace_exactly_3pct_triggers(self):
        """从最高价回撤恰好 3% → 触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 97.0, 0.03) is True

    def test_retrace_below_3pct_no_trigger(self):
        """从最高价回撤 < 3% → 不触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 98.0, 0.03) is False

    def test_retrace_exceeds_5pct_triggers(self):
        """从最高价回撤 >= 5% → 触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 94.0, 0.05) is True

    def test_retrace_exactly_5pct_triggers(self):
        """从最高价回撤恰好 5% → 触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 95.0, 0.05) is True

    def test_retrace_below_5pct_no_trigger(self):
        """从最高价回撤 < 5% → 不触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 96.0, 0.05) is False

    def test_price_at_peak_no_trigger(self):
        """价格在最高价 → 不触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 100.0, 0.03) is False

    def test_price_above_peak_no_trigger(self):
        """价格超过最高价（新高）→ 不触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 105.0, 0.03) is False

    def test_zero_peak_price_no_trigger(self):
        """最高价为 0 → 不触发（防除零）"""
        assert StopLossChecker.check_trailing_stop_loss(0.0, 50.0, 0.03) is False

    def test_large_retrace_triggers(self):
        """大幅回撤 → 触发"""
        assert StopLossChecker.check_trailing_stop_loss(100.0, 80.0, 0.05) is True


class TestCheckTrendStopLoss:
    """check_trend_stop_loss 测试（需求 11.3）"""

    def test_price_below_ma_triggers(self):
        """收盘价 < 均线 → 触发"""
        assert StopLossChecker.check_trend_stop_loss(9.5, 10.0) is True

    def test_price_above_ma_no_trigger(self):
        """收盘价 > 均线 → 不触发"""
        assert StopLossChecker.check_trend_stop_loss(10.5, 10.0) is False

    def test_price_equal_ma_no_trigger(self):
        """收盘价 = 均线 → 不触发（需要 < 才触发）"""
        assert StopLossChecker.check_trend_stop_loss(10.0, 10.0) is False

    def test_price_slightly_below_ma_triggers(self):
        """收盘价略低于均线 → 触发"""
        assert StopLossChecker.check_trend_stop_loss(9.99, 10.0) is True

    def test_price_far_below_ma_triggers(self):
        """收盘价远低于均线 → 触发"""
        assert StopLossChecker.check_trend_stop_loss(5.0, 10.0) is True


class TestCheckStrategyHealth:
    """check_strategy_health 测试（需求 11.4）"""

    def test_low_win_rate_unhealthy(self):
        """胜率 < 50% → 不健康"""
        assert StopLossChecker.check_strategy_health(0.45, 0.10) is True

    def test_high_drawdown_unhealthy(self):
        """最大回撤 > 15% → 不健康"""
        assert StopLossChecker.check_strategy_health(0.60, 0.20) is True

    def test_both_bad_unhealthy(self):
        """胜率低且回撤大 → 不健康"""
        assert StopLossChecker.check_strategy_health(0.30, 0.25) is True

    def test_healthy_strategy(self):
        """胜率 >= 50% 且回撤 <= 15% → 健康"""
        assert StopLossChecker.check_strategy_health(0.60, 0.10) is False

    def test_win_rate_exactly_50_healthy(self):
        """胜率恰好 50% → 健康（不是 < 才触发）"""
        assert StopLossChecker.check_strategy_health(0.50, 0.10) is False

    def test_drawdown_exactly_15_healthy(self):
        """回撤恰好 15% → 健康（不是 > 才触发）"""
        assert StopLossChecker.check_strategy_health(0.60, 0.15) is False

    def test_win_rate_exactly_50_drawdown_exactly_15_healthy(self):
        """胜率恰好 50% 且回撤恰好 15% → 健康"""
        assert StopLossChecker.check_strategy_health(0.50, 0.15) is False

    def test_win_rate_just_below_50_unhealthy(self):
        """胜率略低于 50% → 不健康"""
        assert StopLossChecker.check_strategy_health(0.499, 0.10) is True

    def test_drawdown_just_above_15_unhealthy(self):
        """回撤略高于 15% → 不健康"""
        assert StopLossChecker.check_strategy_health(0.60, 0.151) is True

    def test_zero_win_rate_unhealthy(self):
        """零胜率 → 不健康"""
        assert StopLossChecker.check_strategy_health(0.0, 0.10) is True

    def test_zero_drawdown_with_good_win_rate_healthy(self):
        """零回撤 + 高胜率 → 健康"""
        assert StopLossChecker.check_strategy_health(0.70, 0.0) is False
