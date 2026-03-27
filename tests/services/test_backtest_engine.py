"""
回测引擎单元测试

覆盖：
- BacktestEngine.run_backtest: 回测执行（含 T+1 规则、手续费、绩效指标）
- BacktestEngine._calc_buy_cost / _calc_sell_cost: 手续费计算
- BacktestEngine._calc_max_drawdown: 最大回撤计算
- BacktestEngine.generate_drawdown_curve: 回撤曲线生成
- BacktestEngine.export_result_to_csv: CSV 导出
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.schemas import BacktestConfig, BacktestResult, StrategyConfig
from app.services.backtest_engine import BacktestEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config(**overrides) -> BacktestConfig:
    """创建默认回测配置"""
    kwargs = dict(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("1000000"),
        commission_buy=Decimal("0.0003"),
        commission_sell=Decimal("0.0013"),
        slippage=Decimal("0.001"),
    )
    kwargs.update(overrides)
    return BacktestConfig(**kwargs)


def _make_signal(
    d: date, symbol: str, action: str, price: float, quantity: int,
) -> dict:
    return {
        "date": d,
        "symbol": symbol,
        "action": action,
        "price": price,
        "quantity": quantity,
    }


# ===========================================================================
# 手续费计算
# ===========================================================================


class TestCommissionCalculation:
    """手续费计算测试（需求 12.1）"""

    def test_buy_cost_formula(self):
        """买入成本 = amount * commission_buy + amount * slippage"""
        config = _default_config()
        price = Decimal("10.00")
        qty = 1000
        cost = BacktestEngine._calc_buy_cost(price, qty, config)
        amount = price * qty  # 10000
        expected = amount * Decimal("0.0003") + amount * Decimal("0.001")
        assert cost == expected

    def test_sell_cost_formula(self):
        """卖出成本 = amount * commission_sell + amount * slippage"""
        config = _default_config()
        price = Decimal("10.00")
        qty = 1000
        cost = BacktestEngine._calc_sell_cost(price, qty, config)
        amount = price * qty
        expected = amount * Decimal("0.0013") + amount * Decimal("0.001")
        assert cost == expected

    def test_zero_quantity_zero_cost(self):
        """数量为 0 → 成本为 0"""
        config = _default_config()
        assert BacktestEngine._calc_buy_cost(Decimal("10"), 0, config) == Decimal("0")
        assert BacktestEngine._calc_sell_cost(Decimal("10"), 0, config) == Decimal("0")

    def test_custom_rates(self):
        """自定义费率"""
        config = _default_config(
            commission_buy=Decimal("0.001"),
            commission_sell=Decimal("0.002"),
            slippage=Decimal("0.005"),
        )
        price = Decimal("20.00")
        qty = 500
        amount = price * qty  # 10000
        buy_cost = BacktestEngine._calc_buy_cost(price, qty, config)
        assert buy_cost == amount * Decimal("0.001") + amount * Decimal("0.005")
        sell_cost = BacktestEngine._calc_sell_cost(price, qty, config)
        assert sell_cost == amount * Decimal("0.002") + amount * Decimal("0.005")


# ===========================================================================
# T+1 规则
# ===========================================================================


class TestT1Rule:
    """T+1 规则测试（需求 12.5）"""

    def test_same_day_sell_blocked(self):
        """同日买入卖出被阻止"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 3, 1), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 3, 1), "600000", "SELL", 11.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        # 只有买入记录，卖出被 T+1 阻止
        actions = [r["action"] for r in result.trade_records]
        assert actions == ["BUY"]

    def test_next_day_sell_allowed(self):
        """次日卖出允许"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 3, 1), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 3, 4), "600000", "SELL", 11.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        actions = [r["action"] for r in result.trade_records]
        assert actions == ["BUY", "SELL"]

    def test_no_same_day_buy_sell_in_results(self):
        """回测结果中不存在同一标的同日买卖"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 2), "600000", "SELL", 10.5, 100),
            _make_signal(date(2024, 1, 3), "600000", "SELL", 10.5, 100),
            _make_signal(date(2024, 1, 3), "000001", "BUY", 20.0, 50),
            _make_signal(date(2024, 1, 3), "000001", "SELL", 21.0, 50),
        ]
        result = engine.run_backtest(config, signals)
        # 检查不存在同一标的同日买卖
        for tr in result.trade_records:
            same_day_same_stock = [
                r for r in result.trade_records
                if r["date"] == tr["date"]
                and r["symbol"] == tr["symbol"]
                and r["action"] != tr["action"]
            ]
            assert len(same_day_same_stock) == 0, (
                f"T+1 violation: {tr['symbol']} on {tr['date']}"
            )

    def test_different_stocks_same_day_ok(self):
        """不同股票同日买卖互不影响"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 2), "000001", "BUY", 20.0, 50),
            # 次日卖出 600000
            _make_signal(date(2024, 1, 3), "600000", "SELL", 11.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        actions = [(r["symbol"], r["action"]) for r in result.trade_records]
        assert ("600000", "BUY") in actions
        assert ("000001", "BUY") in actions
        assert ("600000", "SELL") in actions


# ===========================================================================
# 绩效指标完整性
# ===========================================================================


class TestMetricsCompleteness:
    """绩效指标完整性测试（需求 12.2）"""

    def test_all_9_metrics_present(self):
        """回测结果包含全部 9 项指标"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 11.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        assert hasattr(result, "annual_return")
        assert hasattr(result, "total_return")
        assert hasattr(result, "win_rate")
        assert hasattr(result, "profit_loss_ratio")
        assert hasattr(result, "max_drawdown")
        assert hasattr(result, "sharpe_ratio")
        assert hasattr(result, "calmar_ratio")
        assert hasattr(result, "total_trades")
        assert hasattr(result, "avg_holding_days")

    def test_win_rate_in_range(self):
        """胜率在 [0, 1] 范围内"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 11.0, 100),
            _make_signal(date(2024, 2, 1), "000001", "BUY", 20.0, 50),
            _make_signal(date(2024, 2, 5), "000001", "SELL", 19.0, 50),
        ]
        result = engine.run_backtest(config, signals)
        assert 0.0 <= result.win_rate <= 1.0

    def test_max_drawdown_in_range(self):
        """最大回撤在 [0, 1] 范围内"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 1000),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 8.0, 1000),
        ]
        result = engine.run_backtest(config, signals)
        assert 0.0 <= result.max_drawdown <= 1.0

    def test_total_trades_nonnegative(self):
        """总交易次数 >= 0"""
        engine = BacktestEngine()
        config = _default_config()
        result = engine.run_backtest(config, [])
        assert result.total_trades >= 0

    def test_avg_holding_days_nonnegative(self):
        """平均持仓天数 >= 0"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 10), "600000", "SELL", 11.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        assert result.avg_holding_days >= 0

    def test_profit_loss_ratio_nonnegative(self):
        """盈亏比 >= 0"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 11.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        assert result.profit_loss_ratio >= 0


# ===========================================================================
# 空信号 / 边界情况
# ===========================================================================


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_signals(self):
        """空信号列表 → 零指标"""
        engine = BacktestEngine()
        config = _default_config()
        result = engine.run_backtest(config, [])
        assert result.total_trades == 0
        assert result.total_return == 0.0
        assert result.equity_curve == []

    def test_only_buys_no_sells(self):
        """只有买入没有卖出"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        assert result.total_trades == 0  # 没有卖出 = 没有完成交易
        assert len(result.equity_curve) > 0

    def test_sell_without_position_ignored(self):
        """无持仓时卖出被忽略"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "SELL", 10.0, 100),
        ]
        result = engine.run_backtest(config, signals)
        assert result.total_trades == 0
        assert len(result.trade_records) == 0

    def test_insufficient_funds_skipped(self):
        """资金不足时买入被跳过"""
        engine = BacktestEngine()
        config = _default_config(initial_capital=Decimal("100"))
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 1000),
        ]
        result = engine.run_backtest(config, signals)
        assert len(result.trade_records) == 0


# ===========================================================================
# 最大回撤计算
# ===========================================================================


class TestMaxDrawdown:
    """最大回撤计算测试"""

    def test_no_drawdown(self):
        """单调上升 → 回撤 = 0"""
        curve = [
            (date(2024, 1, 1), 1.0),
            (date(2024, 1, 2), 1.1),
            (date(2024, 1, 3), 1.2),
        ]
        assert BacktestEngine._calc_max_drawdown(curve) == 0.0

    def test_simple_drawdown(self):
        """简单回撤"""
        curve = [
            (date(2024, 1, 1), 1.0),
            (date(2024, 1, 2), 1.2),
            (date(2024, 1, 3), 0.9),
        ]
        dd = BacktestEngine._calc_max_drawdown(curve)
        # peak=1.2, trough=0.9, dd = 0.3/1.2 = 0.25
        assert abs(dd - 0.25) < 1e-9

    def test_empty_curve(self):
        """空曲线 → 0"""
        assert BacktestEngine._calc_max_drawdown([]) == 0.0

    def test_flat_curve(self):
        """平坦曲线 → 0"""
        curve = [(date(2024, 1, i), 1.0) for i in range(1, 5)]
        assert BacktestEngine._calc_max_drawdown(curve) == 0.0


# ===========================================================================
# 回撤曲线生成
# ===========================================================================


class TestDrawdownCurve:
    """回撤曲线生成测试（需求 12.3）"""

    def test_drawdown_curve_values(self):
        """回撤曲线值正确"""
        curve = [
            (date(2024, 1, 1), 1.0),
            (date(2024, 1, 2), 1.2),
            (date(2024, 1, 3), 0.9),
            (date(2024, 1, 4), 1.1),
        ]
        dd_curve = BacktestEngine.generate_drawdown_curve(curve)
        assert len(dd_curve) == 4
        assert dd_curve[0][1] == 0.0  # 第一天无回撤
        assert dd_curve[1][1] == 0.0  # 新高无回撤
        assert abs(dd_curve[2][1] - 0.25) < 1e-9  # 0.3/1.2
        assert abs(dd_curve[3][1] - (1.2 - 1.1) / 1.2) < 1e-9

    def test_empty_curve(self):
        """空曲线 → 空结果"""
        assert BacktestEngine.generate_drawdown_curve([]) == []


# ===========================================================================
# CSV 导出
# ===========================================================================


class TestCsvExport:
    """CSV 导出测试（需求 12.3）"""

    def test_export_returns_bytes(self):
        """导出返回 bytes"""
        result = BacktestResult(
            annual_return=0.15,
            total_return=0.30,
            win_rate=0.6,
            profit_loss_ratio=1.5,
            max_drawdown=0.1,
            sharpe_ratio=1.2,
            calmar_ratio=1.5,
            total_trades=10,
            avg_holding_days=5.0,
            equity_curve=[],
            trade_records=[],
        )
        data = BacktestEngine.export_result_to_csv(result)
        assert isinstance(data, bytes)

    def test_export_contains_metrics(self):
        """导出包含绩效指标"""
        result = BacktestResult(
            annual_return=0.15,
            total_return=0.30,
            win_rate=0.6,
            profit_loss_ratio=1.5,
            max_drawdown=0.1,
            sharpe_ratio=1.2,
            calmar_ratio=1.5,
            total_trades=10,
            avg_holding_days=5.0,
            equity_curve=[],
            trade_records=[],
        )
        text = BacktestEngine.export_result_to_csv(result).decode("utf-8-sig")
        assert "年化收益率" in text
        assert "累计收益率" in text
        assert "胜率" in text
        assert "盈亏比" in text
        assert "最大回撤" in text
        assert "夏普比率" in text
        assert "卡玛比率" in text
        assert "总交易次数" in text
        assert "平均持仓天数" in text

    def test_export_contains_trade_records(self):
        """导出包含交易流水"""
        result = BacktestResult(
            annual_return=0.0,
            total_return=0.0,
            win_rate=0.0,
            profit_loss_ratio=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            calmar_ratio=0.0,
            total_trades=1,
            avg_holding_days=3.0,
            equity_curve=[],
            trade_records=[{
                "date": "2024-01-02",
                "symbol": "600000",
                "action": "BUY",
                "price": 10.0,
                "quantity": 100,
                "cost": 1.3,
                "amount": 10000.0,
            }],
        )
        text = BacktestEngine.export_result_to_csv(result).decode("utf-8-sig")
        assert "600000" in text
        assert "BUY" in text


# ===========================================================================
# 完整回测流程
# ===========================================================================


class TestFullBacktest:
    """完整回测流程测试"""

    def test_profitable_round_trip(self):
        """盈利的完整买卖"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 1000),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 12.0, 1000),
        ]
        result = engine.run_backtest(config, signals)
        assert result.total_trades == 1
        assert result.win_rate == 1.0
        assert result.total_return > 0
        assert len(result.equity_curve) > 0
        assert len(result.trade_records) == 2

    def test_losing_round_trip(self):
        """亏损的完整买卖"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 1000),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 8.0, 1000),
        ]
        result = engine.run_backtest(config, signals)
        assert result.total_trades == 1
        assert result.win_rate == 0.0
        assert result.total_return < 0

    def test_multiple_trades(self):
        """多笔交易"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 12.0, 100),
            _make_signal(date(2024, 2, 1), "000001", "BUY", 20.0, 50),
            _make_signal(date(2024, 2, 5), "000001", "SELL", 18.0, 50),
        ]
        result = engine.run_backtest(config, signals)
        assert result.total_trades == 2
        assert 0.0 <= result.win_rate <= 1.0
        assert result.win_rate == 0.5  # 1 win, 1 loss


# ===========================================================================
# 市场环境分类器
# ===========================================================================


class TestMarketEnvironmentClassifier:
    """市场环境分类器测试（需求 12.4）"""

    def test_bull_market(self):
        """价格 > MA60 且 MA20 > MA60 → BULL"""
        from app.services.backtest_engine import MarketEnvironmentClassifier

        # 构造上升趋势：60 个递增价格
        closes = [100.0 + i * 0.5 for i in range(60)]
        # 最后价格 = 129.5, MA60 ≈ 114.75, MA20 的均值也高于 MA60
        result = MarketEnvironmentClassifier.classify_market(closes)
        assert result == "BULL"

    def test_bear_market(self):
        """价格 < MA60 且 MA20 < MA60 → BEAR"""
        from app.services.backtest_engine import MarketEnvironmentClassifier

        # 构造下降趋势：60 个递减价格
        closes = [200.0 - i * 0.5 for i in range(60)]
        # 最后价格 = 170.5, MA60 ≈ 185.25, MA20 均值也低于 MA60
        result = MarketEnvironmentClassifier.classify_market(closes)
        assert result == "BEAR"

    def test_sideways_market_insufficient_data(self):
        """数据不足 lookback → SIDEWAYS"""
        from app.services.backtest_engine import MarketEnvironmentClassifier

        closes = [100.0] * 10
        result = MarketEnvironmentClassifier.classify_market(closes, lookback=60)
        assert result == "SIDEWAYS"

    def test_sideways_mixed_signals(self):
        """价格 > MA60 但 MA20 < MA60 → SIDEWAYS"""
        from app.services.backtest_engine import MarketEnvironmentClassifier

        # 前 40 个高价，后 20 个低价，最后一个高价
        closes = [200.0] * 40 + [100.0] * 19 + [180.0]
        # MA60 ≈ (200*40 + 100*19 + 180) / 60 ≈ 168.0
        # MA20 = (100*19 + 180) / 20 = 104.0
        # price = 180 > MA60 但 MA20 < MA60 → SIDEWAYS
        result = MarketEnvironmentClassifier.classify_market(closes)
        assert result == "SIDEWAYS"

    def test_segment_by_environment_empty(self):
        """空数据 → 空分段"""
        from app.services.backtest_engine import MarketEnvironmentClassifier

        assert MarketEnvironmentClassifier.segment_by_environment([]) == []

    def test_segment_by_environment_single_env(self):
        """所有数据同一环境 → 单段"""
        from app.services.backtest_engine import MarketEnvironmentClassifier

        # 60+ 个递增数据点 → 全部 BULL（数据足够后）
        data = [
            (date(2024, 1, 1) + __import__("datetime").timedelta(days=i), 100.0 + i)
            for i in range(80)
        ]
        segments = MarketEnvironmentClassifier.segment_by_environment(data)
        assert len(segments) >= 1
        # 最后一段应该是 BULL
        assert segments[-1][0] == "BULL"

    def test_segment_by_environment_has_dates(self):
        """分段结果包含正确的日期范围"""
        from app.services.backtest_engine import MarketEnvironmentClassifier
        import datetime

        data = [
            (date(2024, 1, 1) + datetime.timedelta(days=i), 100.0 + i)
            for i in range(80)
        ]
        segments = MarketEnvironmentClassifier.segment_by_environment(data)
        for env, start, end in segments:
            assert env in ("BULL", "BEAR", "SIDEWAYS")
            assert start <= end


# ===========================================================================
# 分段回测
# ===========================================================================


class TestSegmentBacktest:
    """分段回测测试（需求 12.4）"""

    def test_segment_backtest_returns_per_env(self):
        """分段回测按环境返回结果"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 12.0, 100),
            _make_signal(date(2024, 6, 1), "600000", "BUY", 15.0, 100),
            _make_signal(date(2024, 6, 5), "600000", "SELL", 13.0, 100),
        ]
        segments = [
            ("BULL", date(2024, 1, 1), date(2024, 3, 31)),
            ("BEAR", date(2024, 4, 1), date(2024, 12, 31)),
        ]
        results = engine.run_segment_backtest(config, signals, segments)
        assert "BULL" in results
        assert "BEAR" in results
        assert isinstance(results["BULL"], BacktestResult)
        assert isinstance(results["BEAR"], BacktestResult)

    def test_segment_backtest_filters_signals(self):
        """分段回测正确过滤信号到对应时间段"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 12.0, 100),
            _make_signal(date(2024, 6, 1), "000001", "BUY", 20.0, 50),
            _make_signal(date(2024, 6, 5), "000001", "SELL", 18.0, 50),
        ]
        segments = [
            ("BULL", date(2024, 1, 1), date(2024, 3, 31)),
            ("BEAR", date(2024, 4, 1), date(2024, 12, 31)),
        ]
        results = engine.run_segment_backtest(config, signals, segments)
        # BULL 段有 1 笔盈利交易
        assert results["BULL"].total_trades == 1
        assert results["BULL"].win_rate == 1.0
        # BEAR 段有 1 笔亏损交易
        assert results["BEAR"].total_trades == 1
        assert results["BEAR"].win_rate == 0.0

    def test_segment_backtest_empty_segments(self):
        """空分段列表 → 空结果"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
        ]
        results = engine.run_segment_backtest(config, signals, [])
        assert results == {}

    def test_segment_backtest_no_signals_in_segment(self):
        """某段内无信号 → 该段零指标"""
        engine = BacktestEngine()
        config = _default_config()
        signals = [
            _make_signal(date(2024, 1, 2), "600000", "BUY", 10.0, 100),
            _make_signal(date(2024, 1, 5), "600000", "SELL", 12.0, 100),
        ]
        segments = [
            ("BULL", date(2024, 1, 1), date(2024, 3, 31)),
            ("SIDEWAYS", date(2024, 7, 1), date(2024, 9, 30)),
        ]
        results = engine.run_segment_backtest(config, signals, segments)
        assert results["SIDEWAYS"].total_trades == 0
        assert results["SIDEWAYS"].total_return == 0.0
