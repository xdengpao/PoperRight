"""
StockFilter 数据清洗引擎单元测试

覆盖：
- StockFilter.is_excluded：各过滤条件
- AdjustmentCalculator：复权因子计算与前/后复权
- interpolate_missing：线性插值
- remove_outliers：3σ 异常值剔除
- normalize_minmax / normalize_zscore：归一化
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.data_engine.stock_filter import (
    AdjustmentCalculator,
    ExRightsRecord,
    FundamentalsSnapshot,
    StockBasicInfo,
    StockFilter,
    interpolate_missing,
    normalize_minmax,
    normalize_zscore,
    remove_outliers,
    REASON_ST,
    REASON_DELISTED,
    REASON_SUSPENDED,
    REASON_NEW_STOCK,
    REASON_HIGH_PLEDGE,
    REASON_PROFIT_LOSS,
)


# ---------------------------------------------------------------------------
# StockFilter.is_excluded
# ---------------------------------------------------------------------------

class TestStockFilterIsExcluded:
    """测试 StockFilter.is_excluded 各过滤条件"""

    def setup_method(self):
        self.sf = StockFilter()
        self.ref_date = date(2024, 6, 1)

    def _normal_stock(self, symbol: str = "000001.SZ") -> StockBasicInfo:
        """构造一只正常股票"""
        return StockBasicInfo(
            symbol=symbol,
            is_st=False,
            is_delisted=False,
            is_suspended=False,
            list_date=date(2020, 1, 1),
            trading_days_since_ipo=500,
        )

    def _normal_fundamentals(self, symbol: str = "000001.SZ") -> FundamentalsSnapshot:
        return FundamentalsSnapshot(
            symbol=symbol,
            pledge_ratio=Decimal("30"),
            net_profit_yoy=Decimal("10"),
        )

    # --- 正常股票不应被剔除 ---

    def test_normal_stock_not_excluded(self):
        excluded, reason = self.sf.is_excluded(
            self._normal_stock(),
            self._normal_fundamentals(),
            self.ref_date,
        )
        assert excluded is False
        assert reason == ""

    # --- ST 股 ---

    def test_st_stock_excluded(self):
        stock = self._normal_stock()
        stock.is_st = True
        excluded, reason = self.sf.is_excluded(stock, None, self.ref_date)
        assert excluded is True
        assert reason == REASON_ST

    # --- 退市股 ---

    def test_delisted_stock_excluded(self):
        stock = self._normal_stock()
        stock.is_delisted = True
        excluded, reason = self.sf.is_excluded(stock, None, self.ref_date)
        assert excluded is True
        assert reason == REASON_DELISTED

    # --- 停牌股 ---

    def test_suspended_stock_excluded(self):
        stock = self._normal_stock()
        stock.is_suspended = True
        excluded, reason = self.sf.is_excluded(stock, None, self.ref_date)
        assert excluded is True
        assert reason == REASON_SUSPENDED

    # --- 次新股（交易日数不足 20）---

    def test_new_stock_excluded_by_trading_days(self):
        stock = self._normal_stock()
        stock.trading_days_since_ipo = 15  # 不足 20 交易日
        excluded, reason = self.sf.is_excluded(stock, None, self.ref_date)
        assert excluded is True
        assert reason == REASON_NEW_STOCK

    def test_new_stock_excluded_by_calendar_days(self):
        """无交易日数时，用自然日粗估"""
        stock = StockBasicInfo(
            symbol="688001.SH",
            is_st=False,
            is_delisted=False,
            is_suspended=False,
            list_date=self.ref_date - timedelta(days=10),  # 10 天前上市
            trading_days_since_ipo=None,
        )
        excluded, reason = self.sf.is_excluded(stock, None, self.ref_date)
        assert excluded is True
        assert reason == REASON_NEW_STOCK

    def test_stock_with_enough_trading_days_not_excluded(self):
        stock = self._normal_stock()
        stock.trading_days_since_ipo = 20  # 恰好 20 交易日，不剔除
        excluded, reason = self.sf.is_excluded(stock, None, self.ref_date)
        assert excluded is False

    # --- 高质押率 ---

    def test_high_pledge_ratio_excluded(self):
        fund = self._normal_fundamentals()
        fund.pledge_ratio = Decimal("71")  # 超过 70%
        excluded, reason = self.sf.is_excluded(self._normal_stock(), fund, self.ref_date)
        assert excluded is True
        assert reason == REASON_HIGH_PLEDGE

    def test_pledge_ratio_exactly_70_not_excluded(self):
        fund = self._normal_fundamentals()
        fund.pledge_ratio = Decimal("70")  # 恰好 70%，不剔除
        excluded, reason = self.sf.is_excluded(self._normal_stock(), fund, self.ref_date)
        assert excluded is False

    # --- 业绩暴雷（净利润同比亏损 > 50%）---

    def test_profit_loss_excluded(self):
        fund = self._normal_fundamentals()
        fund.net_profit_yoy = Decimal("-51")  # 亏损超 50%
        excluded, reason = self.sf.is_excluded(self._normal_stock(), fund, self.ref_date)
        assert excluded is True
        assert reason == REASON_PROFIT_LOSS

    def test_profit_loss_exactly_50_not_excluded(self):
        fund = self._normal_fundamentals()
        fund.net_profit_yoy = Decimal("-50")  # 恰好 -50%，不剔除
        excluded, reason = self.sf.is_excluded(self._normal_stock(), fund, self.ref_date)
        assert excluded is False

    def test_no_fundamentals_skips_financial_filters(self):
        """无基本面数据时，跳过质押率和业绩过滤"""
        excluded, reason = self.sf.is_excluded(self._normal_stock(), None, self.ref_date)
        assert excluded is False

    # --- ST 优先级高于其他条件 ---

    def test_st_takes_priority_over_pledge(self):
        stock = self._normal_stock()
        stock.is_st = True
        fund = self._normal_fundamentals()
        fund.pledge_ratio = Decimal("80")
        excluded, reason = self.sf.is_excluded(stock, fund, self.ref_date)
        assert reason == REASON_ST


# ---------------------------------------------------------------------------
# AdjustmentCalculator
# ---------------------------------------------------------------------------

class TestAdjustmentCalculator:
    """测试复权因子计算与前/后复权"""

    def test_calc_adj_factor_no_ex_rights(self):
        """无除权除息时，所有日期因子均为 1"""
        dates = [date(2024, 1, i) for i in range(1, 6)]
        factors = AdjustmentCalculator.calc_adj_factor(dates, [])
        for d in dates:
            assert factors[d] == Decimal("1")

    def test_calc_adj_factor_single_event(self):
        """单次送股 10%，除权日后因子应为 1.1"""
        dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
        ex_record = ExRightsRecord(
            ex_date=date(2024, 1, 2),
            cash_dividend=Decimal("0"),
            stock_dividend=Decimal("0.1"),   # 每股送 0.1 股
            allotment_ratio=Decimal("0"),
            allotment_price=Decimal("0"),
        )
        factors = AdjustmentCalculator.calc_adj_factor(dates, [ex_record])
        assert factors[date(2024, 1, 1)] == Decimal("1")
        assert factors[date(2024, 1, 2)] == Decimal("1.1")
        assert factors[date(2024, 1, 3)] == Decimal("1.1")

    def test_calc_adj_factor_empty_dates(self):
        assert AdjustmentCalculator.calc_adj_factor([], []) == {}

    def test_apply_forward_adj_basic(self):
        """前复权：历史价格应低于原始价格（因子 > 1 时）"""
        bars = [
            {"date": date(2024, 1, 1), "open": Decimal("10"), "high": Decimal("11"),
             "low": Decimal("9"), "close": Decimal("10"), "volume": 1000},
            {"date": date(2024, 1, 2), "open": Decimal("11"), "high": Decimal("12"),
             "low": Decimal("10"), "close": Decimal("11"), "volume": 1000},
        ]
        adj_factors = {
            date(2024, 1, 1): Decimal("1"),
            date(2024, 1, 2): Decimal("1.1"),
        }
        result = AdjustmentCalculator.apply_forward_adj(bars, adj_factors)
        # 最新因子 = 1.1，第一天前复权因子 = 1.1/1 = 1.1
        # 第一天 close = 10 / 1.1 ≈ 9.09
        assert result[0]["close"] == Decimal("10") / Decimal("1.1")
        # 第二天前复权因子 = 1.1/1.1 = 1，价格不变
        assert result[1]["close"] == Decimal("11")

    def test_apply_backward_adj_basic(self):
        """后复权：历史价格应高于原始价格（因子 > 1 时）"""
        bars = [
            {"date": date(2024, 1, 1), "open": Decimal("10"), "high": Decimal("11"),
             "low": Decimal("9"), "close": Decimal("10"), "volume": 1000},
            {"date": date(2024, 1, 2), "open": Decimal("11"), "high": Decimal("12"),
             "low": Decimal("10"), "close": Decimal("11"), "volume": 1000},
        ]
        adj_factors = {
            date(2024, 1, 1): Decimal("1"),
            date(2024, 1, 2): Decimal("1.1"),
        }
        result = AdjustmentCalculator.apply_backward_adj(bars, adj_factors)
        # 第一天后复权因子 = 1，价格不变
        assert result[0]["close"] == Decimal("10")
        # 第二天后复权因子 = 1.1，close = 11 * 1.1 = 12.1
        assert result[1]["close"] == Decimal("11") * Decimal("1.1")

    def test_apply_forward_adj_empty(self):
        assert AdjustmentCalculator.apply_forward_adj([], {}) == []

    def test_apply_backward_adj_empty(self):
        assert AdjustmentCalculator.apply_backward_adj([], {}) == []

    def test_original_bars_not_modified(self):
        """复权操作不应修改原始数据"""
        bars = [
            {"date": date(2024, 1, 1), "close": Decimal("10"), "volume": 1000}
        ]
        adj_factors = {date(2024, 1, 1): Decimal("1.1")}
        original_close = bars[0]["close"]
        AdjustmentCalculator.apply_forward_adj(bars, adj_factors)
        assert bars[0]["close"] == original_close


# ---------------------------------------------------------------------------
# interpolate_missing
# ---------------------------------------------------------------------------

class TestInterpolateMissing:
    """测试线性插值补全"""

    def test_no_missing_values(self):
        values = [1.0, 2.0, 3.0, 4.0]
        result = interpolate_missing(values)
        assert result == [1.0, 2.0, 3.0, 4.0]

    def test_single_missing_in_middle(self):
        values = [1.0, None, 3.0]
        result = interpolate_missing(values)
        assert result[1] == pytest.approx(2.0)

    def test_multiple_missing_in_middle(self):
        values = [0.0, None, None, None, 4.0]
        result = interpolate_missing(values)
        assert result[1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)

    def test_missing_at_start(self):
        """左端缺失用第一个有效值填充"""
        values = [None, None, 5.0, 6.0]
        result = interpolate_missing(values)
        assert result[0] == pytest.approx(5.0)
        assert result[1] == pytest.approx(5.0)

    def test_missing_at_end(self):
        """右端缺失用最后一个有效值填充"""
        values = [1.0, 2.0, None, None]
        result = interpolate_missing(values)
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(2.0)

    def test_all_missing(self):
        values = [None, None, None]
        result = interpolate_missing(values)
        assert result == [0.0, 0.0, 0.0]

    def test_empty_list(self):
        assert interpolate_missing([]) == []

    def test_single_value(self):
        assert interpolate_missing([42.0]) == [42.0]

    def test_single_none(self):
        assert interpolate_missing([None]) == [0.0]

    def test_result_length_equals_input(self):
        values = [1.0, None, 3.0, None, 5.0]
        result = interpolate_missing(values)
        assert len(result) == len(values)

    def test_no_none_in_result(self):
        values = [None, 1.0, None, 3.0, None]
        result = interpolate_missing(values)
        assert all(v is not None for v in result)

    def test_interpolated_value_in_range(self):
        """属性 3：插值结果在左右有效值范围内"""
        values = [2.0, None, None, 8.0]
        result = interpolate_missing(values)
        left, right = 2.0, 8.0
        for v in result[1:3]:
            assert min(left, right) <= v <= max(left, right)

    def test_interpolated_decreasing_sequence(self):
        """下降序列的插值也应在范围内"""
        values = [10.0, None, None, 4.0]
        result = interpolate_missing(values)
        for v in result[1:3]:
            assert min(4.0, 10.0) <= v <= max(4.0, 10.0)


# ---------------------------------------------------------------------------
# remove_outliers
# ---------------------------------------------------------------------------

class TestRemoveOutliers:
    """测试 3σ 异常极值检测"""

    def test_no_outliers(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = remove_outliers(values)
        assert all(v is not None for v in result)

    def test_obvious_outlier_removed(self):
        # 正常值 1-10，加入一个极端值 1000
        values = list(range(1, 11)) + [1000.0]
        result = remove_outliers([float(v) for v in values])
        assert result[-1] is None  # 1000 应被剔除

    def test_all_same_values_no_outlier(self):
        values = [5.0] * 10
        result = remove_outliers(values)
        assert all(v == 5.0 for v in result)

    def test_single_value_unchanged(self):
        result = remove_outliers([42.0])
        assert result == [42.0]

    def test_empty_list(self):
        assert remove_outliers([]) == []

    def test_result_length_equals_input(self):
        values = [1.0, 2.0, 100.0, 3.0, 4.0]
        result = remove_outliers(values)
        assert len(result) == len(values)

    def test_custom_n_sigma(self):
        """使用更严格的 2σ 阈值"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 20.0]
        result_3sigma = remove_outliers(values, n_sigma=3.0)
        result_2sigma = remove_outliers(values, n_sigma=2.0)
        # 2σ 更严格，剔除的值应 >= 3σ 剔除的值
        none_count_3 = sum(1 for v in result_3sigma if v is None)
        none_count_2 = sum(1 for v in result_2sigma if v is None)
        assert none_count_2 >= none_count_3


# ---------------------------------------------------------------------------
# normalize_minmax
# ---------------------------------------------------------------------------

class TestNormalizeMinmax:
    """测试 Min-Max 归一化"""

    def test_basic_normalization(self):
        values = [0.0, 5.0, 10.0]
        result = normalize_minmax(values)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)

    def test_all_same_values(self):
        values = [3.0, 3.0, 3.0]
        result = normalize_minmax(values)
        assert all(v == pytest.approx(0.5) for v in result)

    def test_empty_list(self):
        assert normalize_minmax([]) == []

    def test_single_value(self):
        result = normalize_minmax([42.0])
        assert result == [0.5]

    def test_result_in_0_1_range(self):
        values = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        result = normalize_minmax(values)
        assert all(0.0 <= v <= 1.0 for v in result)

    def test_preserves_relative_order(self):
        """属性 4：归一化不改变相对排序"""
        values = [5.0, 2.0, 8.0, 1.0, 9.0]
        result = normalize_minmax(values)
        # 原始排序与归一化后排序一致
        original_order = sorted(range(len(values)), key=lambda i: values[i])
        normalized_order = sorted(range(len(result)), key=lambda i: result[i])
        assert original_order == normalized_order

    def test_negative_values(self):
        values = [-10.0, 0.0, 10.0]
        result = normalize_minmax(values)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# normalize_zscore
# ---------------------------------------------------------------------------

class TestNormalizeZscore:
    """测试 Z-Score 归一化"""

    def test_basic_normalization(self):
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = normalize_zscore(values)
        # 均值应接近 0
        assert abs(sum(result) / len(result)) < 1e-9

    def test_all_same_values(self):
        values = [5.0, 5.0, 5.0]
        result = normalize_zscore(values)
        assert all(v == pytest.approx(0.0) for v in result)

    def test_empty_list(self):
        assert normalize_zscore([]) == []

    def test_single_value(self):
        assert normalize_zscore([42.0]) == [0.0]

    def test_preserves_relative_order(self):
        """属性 4：归一化不改变相对排序"""
        values = [5.0, 2.0, 8.0, 1.0, 9.0]
        result = normalize_zscore(values)
        original_order = sorted(range(len(values)), key=lambda i: values[i])
        normalized_order = sorted(range(len(result)), key=lambda i: result[i])
        assert original_order == normalized_order

    def test_result_length_equals_input(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = normalize_zscore(values)
        assert len(result) == len(values)

    def test_known_values(self):
        """已知均值=3, std=sqrt(2) 的序列"""
        import statistics
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = normalize_zscore(values)
        mean = statistics.mean(values)
        std = statistics.stdev(values)
        expected = [(v - mean) / std for v in values]
        for r, e in zip(result, expected):
            assert r == pytest.approx(e)
