"""
量价资金筛选模块单元测试

覆盖：
- check_turnover_rate: 换手率区间筛选（3%-15%）
- detect_volume_price_divergence: 量价背离检测与过滤
- check_avg_daily_amount: 日均成交额过滤（< 5000 万自动剔除）
- check_money_flow_signal: 主力资金净流入信号生成（≥ 1000 万且连续 2 日）
- check_large_order_signal: 大单成交占比信号生成（> 30%）
- check_sector_resonance: 板块共振筛选（板块涨幅前 30 且多头趋势）
"""

from __future__ import annotations

import pytest

from app.services.screener.volume_price import (
    DivergenceType,
    TurnoverCheckResult,
    DivergenceCheckResult,
    AvgAmountCheckResult,
    MoneyFlowSignal,
    LargeOrderSignal,
    SectorResonanceResult,
    check_turnover_rate,
    detect_volume_price_divergence,
    check_avg_daily_amount,
    check_money_flow_signal,
    check_large_order_signal,
    check_sector_resonance,
    DEFAULT_TURNOVER_MIN,
    DEFAULT_TURNOVER_MAX,
    DEFAULT_MIN_AVG_AMOUNT,
    DEFAULT_MONEY_FLOW_THRESHOLD,
    DEFAULT_MONEY_FLOW_CONSECUTIVE,
    DEFAULT_LARGE_ORDER_RATIO_THRESHOLD,
    DEFAULT_SECTOR_TOP_N,
)


# ---------------------------------------------------------------------------
# 换手率区间筛选
# ---------------------------------------------------------------------------

class TestCheckTurnoverRate:
    """测试换手率区间筛选"""

    def test_within_range(self):
        """换手率在 [3%, 15%] 区间内 → 通过"""
        result = check_turnover_rate(8.0)
        assert result.passed is True
        assert result.turnover_rate == 8.0

    def test_at_lower_bound(self):
        """换手率恰好 = 3% → 通过"""
        result = check_turnover_rate(3.0)
        assert result.passed is True

    def test_at_upper_bound(self):
        """换手率恰好 = 15% → 通过"""
        result = check_turnover_rate(15.0)
        assert result.passed is True

    def test_below_lower_bound(self):
        """换手率 < 3% → 不通过（流动性不足）"""
        result = check_turnover_rate(2.5)
        assert result.passed is False

    def test_above_upper_bound(self):
        """换手率 > 15% → 不通过（异常炒作）"""
        result = check_turnover_rate(20.0)
        assert result.passed is False

    def test_zero_turnover(self):
        """换手率 = 0 → 不通过"""
        result = check_turnover_rate(0.0)
        assert result.passed is False

    def test_custom_range(self):
        """自定义换手率区间"""
        result = check_turnover_rate(5.0, min_rate=1.0, max_rate=10.0)
        assert result.passed is True
        assert result.min_threshold == 1.0
        assert result.max_threshold == 10.0

    def test_custom_range_fail(self):
        result = check_turnover_rate(12.0, min_rate=1.0, max_rate=10.0)
        assert result.passed is False


# ---------------------------------------------------------------------------
# 量价背离检测
# ---------------------------------------------------------------------------

class TestDetectVolumePriceDivergence:
    """测试量价背离检测"""

    def test_no_divergence_normal(self):
        """正常量价配合 → 无背离"""
        closes = [50.0, 50.5, 51.0, 51.5, 52.0, 52.5]
        volumes = [1000, 1050, 1100, 1150, 1200, 1250]
        result = detect_volume_price_divergence(closes, volumes)
        assert result.has_divergence is False
        assert result.divergence_type == DivergenceType.NONE

    def test_price_up_volume_down(self):
        """价涨量缩 → 背离"""
        closes = [50.0, 50.0, 50.0, 50.0, 50.0, 55.0]  # 最后一天大涨
        volumes = [1000, 1000, 1000, 1000, 1000, 500]   # 最后一天缩量
        result = detect_volume_price_divergence(closes, volumes)
        assert result.has_divergence is True
        assert result.divergence_type == DivergenceType.PRICE_UP_VOLUME_DOWN

    def test_price_down_volume_up(self):
        """价跌量增 → 背离"""
        closes = [50.0, 50.0, 50.0, 50.0, 50.0, 47.0]  # 最后一天大跌
        volumes = [1000, 1000, 1000, 1000, 1000, 2000]  # 最后一天放量
        result = detect_volume_price_divergence(closes, volumes)
        assert result.has_divergence is True
        assert result.divergence_type == DivergenceType.PRICE_DOWN_VOLUME_UP

    def test_high_stagnation(self):
        """高位放量滞涨 → 背离"""
        # 价格在高位横盘，最后一天放量但不涨
        closes = [54.0, 54.0, 54.0, 54.0, 54.0, 54.0]
        highs = [54.5, 54.5, 54.5, 54.5, 54.5, 54.2]
        volumes = [1000, 1000, 1000, 1000, 1000, 2000]  # 最后一天放量
        result = detect_volume_price_divergence(closes, volumes, highs=highs)
        assert result.has_divergence is True
        assert result.divergence_type == DivergenceType.HIGH_STAGNATION

    def test_insufficient_data(self):
        """数据不足 → 无背离"""
        result = detect_volume_price_divergence([50.0], [1000])
        assert result.has_divergence is False

    def test_custom_lookback(self):
        """自定义回看天数"""
        closes = [50.0, 50.0, 50.0, 55.0]
        volumes = [1000, 1000, 1000, 400]
        result = detect_volume_price_divergence(closes, volumes, lookback=3)
        assert result.has_divergence is True
        assert result.divergence_type == DivergenceType.PRICE_UP_VOLUME_DOWN

    def test_small_price_change_no_divergence(self):
        """价格变化不大 → 不算背离"""
        closes = [50.0, 50.0, 50.0, 50.0, 50.0, 50.5]  # 仅 1% 涨幅
        volumes = [1000, 1000, 1000, 1000, 1000, 500]
        result = detect_volume_price_divergence(closes, volumes)
        assert result.has_divergence is False


# ---------------------------------------------------------------------------
# 日均成交额过滤
# ---------------------------------------------------------------------------

class TestCheckAvgDailyAmount:
    """测试日均成交额过滤"""

    def test_above_threshold(self):
        """日均成交额 >= 5000 万 → 通过"""
        amounts = [6000.0] * 20
        result = check_avg_daily_amount(amounts)
        assert result.passed is True
        assert result.avg_daily_amount == pytest.approx(6000.0)

    def test_below_threshold(self):
        """日均成交额 < 5000 万 → 不通过"""
        amounts = [3000.0] * 20
        result = check_avg_daily_amount(amounts)
        assert result.passed is False

    def test_exactly_at_threshold(self):
        """日均成交额恰好 = 5000 万 → 通过"""
        amounts = [5000.0] * 20
        result = check_avg_daily_amount(amounts)
        assert result.passed is True

    def test_fewer_days_than_period(self):
        """数据不足 20 日 → 使用可用数据"""
        amounts = [6000.0] * 10
        result = check_avg_daily_amount(amounts)
        assert result.passed is True
        assert result.avg_daily_amount == pytest.approx(6000.0)

    def test_empty_amounts(self):
        """空数据 → 不通过"""
        result = check_avg_daily_amount([])
        assert result.passed is False
        assert result.avg_daily_amount == 0.0

    def test_custom_threshold(self):
        """自定义阈值"""
        amounts = [3000.0] * 20
        result = check_avg_daily_amount(amounts, threshold=2000.0)
        assert result.passed is True

    def test_uses_recent_period(self):
        """只使用最近 N 日数据"""
        amounts = [1000.0] * 30 + [8000.0] * 20
        result = check_avg_daily_amount(amounts, period=20)
        assert result.passed is True
        assert result.avg_daily_amount == pytest.approx(8000.0)


# ---------------------------------------------------------------------------
# 主力资金净流入信号
# ---------------------------------------------------------------------------

class TestCheckMoneyFlowSignal:
    """测试主力资金净流入信号"""

    def test_signal_generated(self):
        """连续 2 日净流入 >= 1000 万 → 生成信号"""
        inflows = [500.0, 800.0, 1200.0, 1500.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is True
        assert result.consecutive_days == 2
        assert result.latest_inflow == 1500.0

    def test_no_signal_one_day(self):
        """仅 1 日满足 → 不生成信号"""
        inflows = [500.0, 800.0, 200.0, 1500.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is False
        assert result.consecutive_days == 1

    def test_no_signal_below_threshold(self):
        """净流入 < 1000 万 → 不生成信号"""
        inflows = [500.0, 800.0, 900.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is False
        assert result.consecutive_days == 0

    def test_exactly_at_threshold(self):
        """净流入恰好 = 1000 万，连续 2 日 → 生成信号"""
        inflows = [1000.0, 1000.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is True
        assert result.consecutive_days == 2

    def test_long_consecutive_streak(self):
        """连续多日满足"""
        inflows = [1500.0] * 5
        result = check_money_flow_signal(inflows)
        assert result.signal is True
        assert result.consecutive_days == 5

    def test_empty_inflows(self):
        """空数据 → 不生成信号"""
        result = check_money_flow_signal([])
        assert result.signal is False
        assert result.consecutive_days == 0

    def test_custom_threshold_and_consecutive(self):
        """自定义阈值和连续天数"""
        inflows = [600.0, 600.0, 600.0]
        result = check_money_flow_signal(inflows, threshold=500.0, consecutive=3)
        assert result.signal is True
        assert result.consecutive_days == 3

    def test_break_in_streak(self):
        """中间断流 → 从最近连续段计算"""
        inflows = [1500.0, 1500.0, 200.0, 1500.0, 1500.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is True
        assert result.consecutive_days == 2


# ---------------------------------------------------------------------------
# 大单成交占比信号
# ---------------------------------------------------------------------------

class TestCheckLargeOrderSignal:
    """测试大单成交占比信号"""

    def test_signal_above_threshold(self):
        """大单占比 > 30% → 生成信号"""
        result = check_large_order_signal(35.0)
        assert result.signal is True
        assert result.large_order_ratio == 35.0

    def test_no_signal_at_threshold(self):
        """大单占比 = 30% → 不生成信号（需 > 30%）"""
        result = check_large_order_signal(30.0)
        assert result.signal is False

    def test_no_signal_below_threshold(self):
        """大单占比 < 30% → 不生成信号"""
        result = check_large_order_signal(20.0)
        assert result.signal is False

    def test_zero_ratio(self):
        result = check_large_order_signal(0.0)
        assert result.signal is False

    def test_custom_threshold(self):
        """自定义阈值"""
        result = check_large_order_signal(25.0, threshold=20.0)
        assert result.signal is True


# ---------------------------------------------------------------------------
# 板块共振筛选
# ---------------------------------------------------------------------------

class TestCheckSectorResonance:
    """测试板块共振筛选"""

    def test_strong_sector_bullish(self):
        """板块排名前 30 且多头趋势 → 通过"""
        result = check_sector_resonance("半导体", sector_rank=5, sector_is_bullish=True)
        assert result.passed is True
        assert result.sector_name == "半导体"

    def test_strong_sector_not_bullish(self):
        """板块排名前 30 但非多头趋势 → 不通过"""
        result = check_sector_resonance("银行", sector_rank=10, sector_is_bullish=False)
        assert result.passed is False

    def test_weak_sector_bullish(self):
        """板块排名 > 30 即使多头趋势 → 不通过"""
        result = check_sector_resonance("煤炭", sector_rank=50, sector_is_bullish=True)
        assert result.passed is False

    def test_at_boundary_rank(self):
        """板块排名恰好 = 30 且多头 → 通过"""
        result = check_sector_resonance("医药", sector_rank=30, sector_is_bullish=True)
        assert result.passed is True

    def test_rank_just_outside(self):
        """板块排名 = 31 → 不通过"""
        result = check_sector_resonance("地产", sector_rank=31, sector_is_bullish=True)
        assert result.passed is False

    def test_custom_top_n(self):
        """自定义排名阈值"""
        result = check_sector_resonance("新能源", sector_rank=15, sector_is_bullish=True, top_n=10)
        assert result.passed is False

    def test_weak_sector_not_bullish(self):
        """弱势板块且非多头 → 不通过"""
        result = check_sector_resonance("房地产", sector_rank=80, sector_is_bullish=False)
        assert result.passed is False


# ---------------------------------------------------------------------------
# 集成场景测试
# ---------------------------------------------------------------------------

class TestVolumePriceIntegration:
    """端到端集成场景"""

    def test_full_screening_pass(self):
        """完整筛选流程 - 全部通过"""
        # 换手率
        turnover = check_turnover_rate(8.0)
        assert turnover.passed is True

        # 量价背离
        closes = [50.0, 50.5, 51.0, 51.5, 52.0, 52.5]
        volumes = [1000, 1050, 1100, 1150, 1200, 1250]
        divergence = detect_volume_price_divergence(closes, volumes)
        assert divergence.has_divergence is False

        # 日均成交额
        amounts = [6000.0] * 20
        avg_amount = check_avg_daily_amount(amounts)
        assert avg_amount.passed is True

        # 资金流入
        inflows = [1200.0, 1500.0]
        money_flow = check_money_flow_signal(inflows)
        assert money_flow.signal is True

        # 大单占比
        large_order = check_large_order_signal(35.0)
        assert large_order.signal is True

        # 板块共振
        sector = check_sector_resonance("半导体", sector_rank=5, sector_is_bullish=True)
        assert sector.passed is True

    def test_full_screening_fail_turnover(self):
        """换手率不通过 → 应剔除"""
        turnover = check_turnover_rate(1.0)
        assert turnover.passed is False

    def test_full_screening_fail_divergence(self):
        """量价背离 → 应剔除"""
        closes = [50.0, 50.0, 50.0, 50.0, 50.0, 55.0]
        volumes = [1000, 1000, 1000, 1000, 1000, 400]
        divergence = detect_volume_price_divergence(closes, volumes)
        assert divergence.has_divergence is True

    def test_full_screening_fail_amount(self):
        """日均成交额不足 → 应剔除"""
        amounts = [2000.0] * 20
        avg_amount = check_avg_daily_amount(amounts)
        assert avg_amount.passed is False


# ---------------------------------------------------------------------------
# 相对阈值模式的资金流信号（需求 6）
# ---------------------------------------------------------------------------

from app.services.screener.volume_price import (
    RelativeMoneyFlowSignal,
    check_money_flow_signal_relative,
)


class TestCheckMoneyFlowSignalRelative:
    """测试相对阈值模式的资金流信号（需求 6.1, 6.2, 6.3, 6.4, 6.5, 6.6）"""

    def test_signal_triggered_relative_threshold(self):
        """相对净流入 >= 5% 连续 2 日 → 生成信号"""
        # 日均成交额 = 10000 万，5% 阈值 = 500 万
        daily_amounts = [10000.0] * 20
        daily_inflows = [100.0, 200.0, 600.0, 700.0]  # 最后 2 日：6%, 7%
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is True
        assert result.consecutive_days == 2
        assert result.fallback_needed is False
        assert isinstance(result, RelativeMoneyFlowSignal)

    def test_no_signal_below_relative_threshold(self):
        """相对净流入 < 5% → 不生成信号"""
        daily_amounts = [10000.0] * 20
        daily_inflows = [100.0, 200.0, 300.0]  # 最大 3%，不满足 5%
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is False
        assert result.fallback_needed is False

    def test_signal_only_one_day(self):
        """仅 1 日满足相对阈值 → 不生成信号（需连续 2 日）"""
        daily_amounts = [10000.0] * 20
        daily_inflows = [100.0, 200.0, 300.0, 600.0]  # 仅最后 1 日 6%
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is False
        assert result.consecutive_days == 1

    def test_fallback_when_avg_amount_zero(self):
        """日均成交额 = 0 → 回退标记"""
        daily_amounts = [0.0] * 20
        daily_inflows = [1000.0, 2000.0]
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is False
        assert result.fallback_needed is True

    def test_fallback_when_avg_amount_negative(self):
        """日均成交额 < 0 → 回退标记"""
        daily_amounts = [-100.0] * 20
        daily_inflows = [1000.0, 2000.0]
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is False
        assert result.fallback_needed is True

    def test_fallback_when_empty_amounts(self):
        """成交额数据为空 → 回退标记"""
        result = check_money_flow_signal_relative([1000.0], [])
        assert result.signal is False
        assert result.fallback_needed is True

    def test_fallback_when_empty_inflows(self):
        """净流入数据为空 → 回退标记"""
        result = check_money_flow_signal_relative([], [10000.0] * 20)
        assert result.signal is False
        assert result.fallback_needed is True

    def test_custom_threshold_pct(self):
        """自定义相对阈值百分比"""
        daily_amounts = [10000.0] * 20
        # 3% 阈值 = 300 万，最后 2 日净流入 400, 500 → 4%, 5% → 满足
        daily_inflows = [100.0, 400.0, 500.0]
        result = check_money_flow_signal_relative(
            daily_inflows, daily_amounts, relative_threshold_pct=3.0,
        )
        assert result.signal is True
        assert result.consecutive_days == 2

    def test_custom_consecutive_days(self):
        """自定义连续天数要求"""
        daily_amounts = [10000.0] * 20
        daily_inflows = [600.0, 700.0, 800.0]  # 连续 3 日 >= 5%
        result = check_money_flow_signal_relative(
            daily_inflows, daily_amounts, consecutive=3,
        )
        assert result.signal is True
        assert result.consecutive_days == 3

    def test_custom_consecutive_days_not_met(self):
        """自定义连续天数要求未满足"""
        daily_amounts = [10000.0] * 20
        daily_inflows = [600.0, 700.0]  # 仅 2 日，要求 3 日
        result = check_money_flow_signal_relative(
            daily_inflows, daily_amounts, consecutive=3,
        )
        assert result.signal is False
        assert result.consecutive_days == 2

    def test_custom_amount_period(self):
        """自定义日均成交额计算周期"""
        # 前 10 日成交额 1000，后 5 日成交额 10000
        daily_amounts = [1000.0] * 10 + [10000.0] * 5
        # 使用最近 5 日计算 → avg = 10000，5% = 500
        daily_inflows = [100.0, 600.0, 700.0]
        result = check_money_flow_signal_relative(
            daily_inflows, daily_amounts, amount_period=5,
        )
        assert result.signal is True
        assert result.avg_daily_amount == pytest.approx(10000.0)

    def test_amounts_fewer_than_period(self):
        """成交额数据不足 period 天 → 使用可用数据"""
        daily_amounts = [10000.0] * 5  # 仅 5 日，period 默认 20
        daily_inflows = [600.0, 700.0]
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is True
        assert result.avg_daily_amount == pytest.approx(10000.0)

    def test_backward_compatible_original_function(self):
        """原 check_money_flow_signal 函数保持不变（向后兼容）"""
        # 验证原函数仍然可用且行为不变
        inflows = [1200.0, 1500.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is True
        assert result.consecutive_days == 2
        assert isinstance(result, MoneyFlowSignal)

    def test_backward_compatible_original_no_signal(self):
        """原函数：不满足绝对阈值 → 不生成信号"""
        inflows = [500.0, 800.0]
        result = check_money_flow_signal(inflows)
        assert result.signal is False

    def test_relative_vs_absolute_small_cap(self):
        """小盘股场景：绝对阈值可能不触发，相对阈值可以触发"""
        # 小盘股日均成交额 2000 万，净流入 150 万 = 7.5% → 相对阈值触发
        daily_amounts = [2000.0] * 20
        daily_inflows = [150.0, 160.0]
        relative_result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        absolute_result = check_money_flow_signal(daily_inflows)  # 阈值 1000 万
        assert relative_result.signal is True   # 相对阈值触发
        assert absolute_result.signal is False  # 绝对阈值不触发

    def test_latest_ratio_calculation(self):
        """验证最近一日净流入占比计算"""
        daily_amounts = [10000.0] * 20
        daily_inflows = [100.0, 800.0]  # 最后一日 800/10000 = 8%
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.latest_ratio == pytest.approx(8.0)

    def test_break_in_streak(self):
        """中间断流 → 从最近连续段计算"""
        daily_amounts = [10000.0] * 20
        # 600, 700 满足 5%，然后 100 不满足，然后 800, 900 满足
        daily_inflows = [600.0, 700.0, 100.0, 800.0, 900.0]
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is True
        assert result.consecutive_days == 2  # 最近连续 2 日

    def test_exactly_at_threshold(self):
        """净流入占比恰好 = 5% 连续 2 日 → 生成信号"""
        daily_amounts = [10000.0] * 20
        daily_inflows = [500.0, 500.0]  # 恰好 5%
        result = check_money_flow_signal_relative(daily_inflows, daily_amounts)
        assert result.signal is True
        assert result.consecutive_days == 2
