"""
复盘分析服务单元测试

覆盖：
- ReviewAnalyzer.generate_daily_review: 胜率、盈亏统计、案例分析
- DailyReview 数据完整性
- 边界情况（空记录、全盈利、全亏损、单笔交易）
- StrategyReportGenerator: 周期报表、风险指标、多策略对比
- MarketReviewAnalyzer: 板块轮动、趋势分布、资金流向
- ReportExporter: CSV/JSON 导出
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.services.review_analyzer import (
    DailyReview,
    MarketReviewAnalyzer,
    ReportExporter,
    ReviewAnalyzer,
    StrategyReportGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trade(symbol: str, profit: float) -> dict:
    return {"symbol": symbol, "profit": profit}


# ===========================================================================
# 空记录
# ===========================================================================


class TestEmptyRecords:
    """空交易记录测试"""

    def test_empty_trades_returns_zero_stats(self):
        review = ReviewAnalyzer.generate_daily_review([], [])
        assert review.total_trades == 0
        assert review.win_rate == 0.0
        assert review.total_pnl == 0.0
        assert review.avg_pnl == 0.0
        assert review.winning_trades == 0
        assert review.losing_trades == 0
        assert review.best_trade is None
        assert review.worst_trade is None
        assert review.successful_cases == []
        assert review.failed_cases == []

    def test_empty_trades_uses_today_as_default_date(self):
        review = ReviewAnalyzer.generate_daily_review([], [])
        assert review.date == date.today()

    def test_empty_trades_with_custom_date(self):
        d = date(2024, 6, 15)
        review = ReviewAnalyzer.generate_daily_review([], [], review_date=d)
        assert review.date == d


# ===========================================================================
# 胜率计算
# ===========================================================================


class TestWinRate:
    """胜率计算测试"""

    def test_all_winning(self):
        trades = [_trade("A", 100), _trade("B", 200)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.win_rate == 1.0
        assert review.winning_trades == 2
        assert review.losing_trades == 0

    def test_all_losing(self):
        trades = [_trade("A", -100), _trade("B", -50)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.win_rate == 0.0
        assert review.winning_trades == 0
        assert review.losing_trades == 2

    def test_mixed_trades(self):
        trades = [_trade("A", 100), _trade("B", -50), _trade("C", 200)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.win_rate == pytest.approx(2 / 3)
        assert review.winning_trades == 2
        assert review.losing_trades == 1

    def test_zero_profit_counts_as_losing(self):
        """profit == 0 归为亏损（非盈利）"""
        trades = [_trade("A", 0)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.win_rate == 0.0
        assert review.losing_trades == 1


# ===========================================================================
# 盈亏统计
# ===========================================================================


class TestPnlStats:
    """盈亏统计测试"""

    def test_total_pnl(self):
        trades = [_trade("A", 100), _trade("B", -30), _trade("C", 50)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.total_pnl == pytest.approx(120.0)

    def test_avg_pnl(self):
        trades = [_trade("A", 100), _trade("B", -30), _trade("C", 50)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.avg_pnl == pytest.approx(40.0)

    def test_single_trade_avg_equals_total(self):
        trades = [_trade("A", 75)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.avg_pnl == review.total_pnl


# ===========================================================================
# 最佳/最差交易
# ===========================================================================


class TestBestWorstTrade:
    """最佳/最差交易识别测试"""

    def test_best_trade(self):
        trades = [_trade("A", 100), _trade("B", 300), _trade("C", -50)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.best_trade["symbol"] == "B"
        assert review.best_trade["profit"] == 300

    def test_worst_trade(self):
        trades = [_trade("A", 100), _trade("B", 300), _trade("C", -50)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.worst_trade["symbol"] == "C"
        assert review.worst_trade["profit"] == -50

    def test_single_trade_is_both_best_and_worst(self):
        trades = [_trade("A", 42)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert review.best_trade["symbol"] == "A"
        assert review.worst_trade["symbol"] == "A"


# ===========================================================================
# 成功/失败案例分析
# ===========================================================================


class TestCaseAnalysis:
    """成功/失败交易案例分析测试"""

    def test_successful_cases_contain_profitable_trades(self):
        trades = [_trade("A", 100), _trade("B", -50), _trade("C", 200)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        symbols = [c["symbol"] for c in review.successful_cases]
        assert "A" in symbols
        assert "C" in symbols
        assert "B" not in symbols

    def test_failed_cases_contain_losing_trades(self):
        trades = [_trade("A", 100), _trade("B", -50), _trade("C", 0)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        symbols = [c["symbol"] for c in review.failed_cases]
        assert "B" in symbols
        assert "C" in symbols  # profit == 0 is a failed case
        assert "A" not in symbols

    def test_case_counts_match_totals(self):
        trades = [_trade("A", 100), _trade("B", -50), _trade("C", 200)]
        review = ReviewAnalyzer.generate_daily_review(trades, [])
        assert len(review.successful_cases) == review.winning_trades
        assert len(review.failed_cases) == review.losing_trades
        assert review.winning_trades + review.losing_trades == review.total_trades


# ===========================================================================
# 9.2 StrategyReportGenerator
# ===========================================================================


class TestStrategyReportGenerator:
    """策略绩效报表生成器测试"""

    def test_empty_trades_report(self):
        report = StrategyReportGenerator.generate_period_report([], "daily")
        assert report["period"] == "daily"
        assert report["total_return"] == 0.0
        assert report["win_rate"] == 0.0
        assert report["total_trades"] == 0
        assert report["risk_metrics"]["max_drawdown"] == 0.0

    def test_invalid_period_raises(self):
        with pytest.raises(ValueError, match="period must be"):
            StrategyReportGenerator.generate_period_report([], "yearly")

    def test_daily_report_basic(self):
        trades = [_trade("A", 100), _trade("B", -30), _trade("C", 50)]
        report = StrategyReportGenerator.generate_period_report(trades, "daily")
        assert report["period"] == "daily"
        assert report["total_return"] == pytest.approx(120.0)
        assert report["win_rate"] == pytest.approx(2 / 3)
        assert report["total_trades"] == 3

    def test_weekly_and_monthly_periods_accepted(self):
        trades = [_trade("A", 10)]
        for period in ("weekly", "monthly"):
            report = StrategyReportGenerator.generate_period_report(trades, period)
            assert report["period"] == period

    def test_risk_metrics_present(self):
        trades = [_trade("A", 100), _trade("B", -50), _trade("C", 30)]
        report = StrategyReportGenerator.generate_period_report(trades, "daily")
        rm = report["risk_metrics"]
        assert "max_drawdown" in rm
        assert "sharpe_ratio" in rm
        assert "volatility" in rm

    def test_max_drawdown_positive(self):
        trades = [_trade("A", 100), _trade("B", -200), _trade("C", 50)]
        report = StrategyReportGenerator.generate_period_report(trades, "daily")
        assert report["risk_metrics"]["max_drawdown"] >= 0

    def test_compare_strategies_empty(self):
        result = StrategyReportGenerator.compare_strategies({})
        assert result["strategies"] == []
        assert result["best_strategy"] is None

    def test_compare_strategies_picks_best(self):
        r1 = StrategyReportGenerator.generate_period_report(
            [_trade("A", 100), _trade("B", 50)], "daily"
        )
        r2 = StrategyReportGenerator.generate_period_report(
            [_trade("A", 200)], "daily"
        )
        comparison = StrategyReportGenerator.compare_strategies({"s1": r1, "s2": r2})
        assert comparison["best_strategy"] == "s2"
        assert len(comparison["strategies"]) == 2


# ===========================================================================
# 9.3 MarketReviewAnalyzer
# ===========================================================================


class TestMarketReviewAnalyzer:
    """市场复盘分析测试"""

    # -- 板块轮动 --

    def test_sector_rotation_empty(self):
        result = MarketReviewAnalyzer.analyze_sector_rotation([])
        assert result["top_sectors"] == []
        assert result["bottom_sectors"] == []
        assert result["rotation_summary"] == "无数据"

    def test_sector_rotation_sorted(self):
        sectors = [
            {"name": "科技", "change_pct": 3.5},
            {"name": "金融", "change_pct": -1.2},
            {"name": "医药", "change_pct": 2.0},
        ]
        result = MarketReviewAnalyzer.analyze_sector_rotation(sectors)
        assert result["top_sectors"][0]["name"] == "科技"
        assert result["bottom_sectors"][-1]["name"] == "金融"

    def test_sector_rotation_summary_strong(self):
        sectors = [
            {"name": "A", "change_pct": 1.0},
            {"name": "B", "change_pct": 2.0},
            {"name": "C", "change_pct": -0.5},
        ]
        result = MarketReviewAnalyzer.analyze_sector_rotation(sectors)
        assert "上涨 2" in result["rotation_summary"]

    # -- 趋势分布 --

    def test_trend_distribution_empty(self):
        result = MarketReviewAnalyzer.generate_trend_distribution([])
        assert result["bins"] == ["0-20", "20-40", "40-60", "60-80", "80-100"]
        assert result["counts"] == [0, 0, 0, 0, 0]

    def test_trend_distribution_buckets(self):
        scores = [10, 25, 55, 75, 90, 85, 50, 5]
        result = MarketReviewAnalyzer.generate_trend_distribution(scores)
        assert result["counts"][0] == 2  # 0-20: 10, 5
        assert result["counts"][1] == 1  # 20-40: 25
        assert result["counts"][2] == 2  # 40-60: 55, 50
        assert result["counts"][3] == 1  # 60-80: 75
        assert result["counts"][4] == 2  # 80-100: 90, 85

    def test_trend_distribution_total_matches(self):
        scores = [10, 30, 50, 70, 90]
        result = MarketReviewAnalyzer.generate_trend_distribution(scores)
        assert sum(result["counts"]) == len(scores)

    # -- 资金流向 --

    def test_money_flow_empty(self):
        result = MarketReviewAnalyzer.analyze_money_flow([])
        assert result["net_inflow_total"] == 0.0
        assert result["top_inflow_sectors"] == []
        assert result["top_outflow_sectors"] == []

    def test_money_flow_basic(self):
        flows = [
            {"sector": "科技", "net_inflow": 5000},
            {"sector": "金融", "net_inflow": -3000},
            {"sector": "医药", "net_inflow": 2000},
        ]
        result = MarketReviewAnalyzer.analyze_money_flow(flows)
        assert result["net_inflow_total"] == pytest.approx(4000.0)
        assert result["top_inflow_sectors"][0]["sector"] == "科技"
        assert result["top_outflow_sectors"][0]["sector"] == "金融"


# ===========================================================================
# 9.4 ReportExporter
# ===========================================================================


class TestReportExporter:
    """报表导出测试"""

    # -- CSV --

    def test_csv_export_list_of_dicts(self):
        data = [{"name": "A", "value": 1}, {"name": "B", "value": 2}]
        result = ReportExporter.export_to_csv(data)
        assert isinstance(result, bytes)
        text = result.decode("utf-8-sig")
        assert "name" in text
        assert "A" in text
        assert "B" in text

    def test_csv_export_single_dict(self):
        data = {"total_return": 120.0, "win_rate": 0.67}
        result = ReportExporter.export_to_csv(data)
        text = result.decode("utf-8-sig")
        assert "total_return" in text
        assert "120.0" in text

    def test_csv_export_empty_list(self):
        result = ReportExporter.export_to_csv([])
        assert result == b""

    def test_csv_export_nested_dict(self):
        data = {"period": "daily", "risk_metrics": {"max_drawdown": 0.1}}
        result = ReportExporter.export_to_csv(data)
        text = result.decode("utf-8-sig")
        assert "risk_metrics.max_drawdown" in text

    # -- JSON --

    def test_json_export_dict(self):
        data = {"bins": ["0-20", "20-40"], "counts": [5, 10]}
        result = ReportExporter.export_to_json(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_json_export_list(self):
        data = [{"name": "A"}, {"name": "B"}]
        result = ReportExporter.export_to_json(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_json_export_chinese_chars(self):
        data = {"sector": "科技"}
        result = ReportExporter.export_to_json(data)
        assert "科技" in result  # ensure_ascii=False
