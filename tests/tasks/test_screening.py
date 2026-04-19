"""
选股执行调度单元测试

测试：
- ScreenExecutor: 盘后选股、实时选股、结果字段完整性
- screening tasks: Celery 任务调度逻辑
- export_screen_result_to_csv: CSV 导出
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.schemas import (
    FactorCondition,
    RiskLevel,
    ScreenType,
    StrategyConfig,
)
from app.services.screener.screen_executor import (
    ScreenExecutor,
    _classify_risk,
    export_screen_result_to_csv,
)
from app.tasks.screening import (
    TRADING_END,
    TRADING_START,
    _is_trading_hours,
)


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------

def _make_strategy_config() -> StrategyConfig:
    """创建一个简单的测试策略配置。"""
    return StrategyConfig(
        factors=[
            FactorCondition(factor_name="ma_trend", operator=">=", threshold=60.0),
        ],
        logic="AND",
        weights={"ma_trend": 1.0},
    )


def _make_stocks_data() -> dict[str, dict]:
    """创建测试用的股票因子数据。"""
    return {
        "000001.SZ": {"ma_trend": 85.0, "close": 15.50},
        "000002.SZ": {"ma_trend": 70.0, "close": 28.30},
        "600000.SH": {"ma_trend": 50.0, "close": 8.10},  # 不满足 >= 60
        "600519.SH": {"ma_trend": 92.0, "close": 1800.00},
    }


# ---------------------------------------------------------------------------
# _classify_risk 测试
# ---------------------------------------------------------------------------


class TestClassifyRisk:
    """风险等级分类测试"""

    def test_high_score_is_low_risk(self):
        assert _classify_risk(85.0) == RiskLevel.LOW

    def test_boundary_80_is_low_risk(self):
        assert _classify_risk(80.0) == RiskLevel.LOW

    def test_medium_score_is_medium_risk(self):
        assert _classify_risk(65.0) == RiskLevel.MEDIUM

    def test_boundary_50_is_medium_risk(self):
        assert _classify_risk(50.0) == RiskLevel.MEDIUM

    def test_low_score_is_high_risk(self):
        assert _classify_risk(30.0) == RiskLevel.HIGH

    def test_zero_is_high_risk(self):
        assert _classify_risk(0.0) == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# _is_trading_hours 测试
# ---------------------------------------------------------------------------


class TestIsTradingHours:
    """交易时段判断测试"""

    def test_within_trading_hours(self):
        dt = datetime(2024, 1, 15, 10, 0, 0)  # Monday
        assert _is_trading_hours(dt) is True

    def test_at_start_boundary(self):
        dt = datetime(2024, 1, 15, 9, 30, 0)
        assert _is_trading_hours(dt) is True

    def test_at_end_boundary(self):
        dt = datetime(2024, 1, 15, 15, 0, 0)
        assert _is_trading_hours(dt) is True

    def test_before_start(self):
        dt = datetime(2024, 1, 15, 9, 29, 0)
        assert _is_trading_hours(dt) is False

    def test_after_end(self):
        dt = datetime(2024, 1, 15, 15, 1, 0)
        assert _is_trading_hours(dt) is False

    def test_weekend(self):
        dt = datetime(2024, 1, 13, 10, 0, 0)  # Saturday
        assert _is_trading_hours(dt) is False


# ---------------------------------------------------------------------------
# ScreenExecutor 测试
# ---------------------------------------------------------------------------


class TestScreenExecutor:
    """选股执行器测试"""

    def test_eod_screen_returns_passing_stocks(self):
        """盘后选股应返回满足策略条件的股票"""
        config = _make_strategy_config()
        stocks = _make_stocks_data()
        executor = ScreenExecutor(config)

        result = executor.run_eod_screen(stocks)

        assert result.screen_type == ScreenType.EOD
        assert result.is_complete is True
        # 600000.SH (ma_trend=50) 不满足 >= 60
        symbols = [item.symbol for item in result.items]
        assert "000001.SZ" in symbols
        assert "000002.SZ" in symbols
        assert "600519.SH" in symbols
        assert "600000.SH" not in symbols

    def test_realtime_screen_returns_passing_stocks(self):
        """实时选股应返回满足策略条件的股票"""
        config = _make_strategy_config()
        stocks = _make_stocks_data()
        executor = ScreenExecutor(config)

        result = executor.run_realtime_screen(stocks)

        assert result.screen_type == ScreenType.REALTIME
        assert len(result.items) == 3

    def test_screen_items_have_required_fields(self):
        """选股结果每条记录应包含完整字段（需求 7.6）"""
        config = _make_strategy_config()
        stocks = _make_stocks_data()
        executor = ScreenExecutor(config)

        result = executor.run_eod_screen(stocks)

        for item in result.items:
            assert item.symbol is not None and item.symbol != ""
            assert isinstance(item.ref_buy_price, Decimal)
            assert 0.0 <= item.trend_score <= 100.0
            assert item.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)
            assert isinstance(item.signals, list)

    def test_ref_buy_price_from_close(self):
        """买入参考价应取自 close 字段"""
        config = _make_strategy_config()
        stocks = {"000001.SZ": {"ma_trend": 85.0, "close": 15.50}}
        executor = ScreenExecutor(config)

        result = executor.run_eod_screen(stocks)

        assert len(result.items) == 1
        assert result.items[0].ref_buy_price == Decimal("15.5")

    def test_empty_stocks_returns_empty_result(self):
        """空股票数据应返回空结果"""
        config = _make_strategy_config()
        executor = ScreenExecutor(config)

        result = executor.run_eod_screen({})

        assert len(result.items) == 0
        assert result.is_complete is True

    def test_custom_strategy_id(self):
        """应支持自定义 strategy_id"""
        sid = str(uuid.uuid4())
        config = _make_strategy_config()
        executor = ScreenExecutor(config, strategy_id=sid)

        result = executor.run_eod_screen({})

        assert str(result.strategy_id) == sid

    def test_signals_dict_populated(self):
        """选股结果的 signals 字段应包含因子评估详情"""
        from app.core.schemas import SignalCategory, SignalDetail

        config = _make_strategy_config()
        stocks = {"000001.SZ": {"ma_trend": 85.0, "close": 15.50}}
        executor = ScreenExecutor(config)

        result = executor.run_eod_screen(stocks)

        item = result.items[0]
        assert isinstance(item.signals, list)
        assert len(item.signals) == 1
        sig = item.signals[0]
        assert isinstance(sig, SignalDetail)
        assert sig.label == "ma_trend"
        assert sig.category == SignalCategory.MA_TREND


# ---------------------------------------------------------------------------
# CSV 导出测试
# ---------------------------------------------------------------------------


class TestExportCSV:
    """选股结果 CSV 导出测试"""

    def test_export_returns_bytes(self):
        """导出应返回 bytes"""
        config = _make_strategy_config()
        stocks = _make_stocks_data()
        executor = ScreenExecutor(config)
        result = executor.run_eod_screen(stocks)

        csv_bytes = export_screen_result_to_csv(result)

        assert isinstance(csv_bytes, bytes)

    def test_export_contains_bom(self):
        """导出应包含 UTF-8 BOM"""
        config = _make_strategy_config()
        result = ScreenExecutor(config).run_eod_screen({})

        csv_bytes = export_screen_result_to_csv(result)

        assert csv_bytes[:3] == b"\xef\xbb\xbf"

    def test_export_contains_headers(self):
        """导出应包含表头"""
        config = _make_strategy_config()
        result = ScreenExecutor(config).run_eod_screen({})

        csv_text = export_screen_result_to_csv(result).decode("utf-8-sig")

        assert "股票代码" in csv_text
        assert "买入参考价" in csv_text
        assert "趋势强度" in csv_text
        assert "风险等级" in csv_text

    def test_export_contains_data_rows(self):
        """导出应包含数据行"""
        config = _make_strategy_config()
        stocks = _make_stocks_data()
        result = ScreenExecutor(config).run_eod_screen(stocks)

        csv_text = export_screen_result_to_csv(result).decode("utf-8-sig")
        lines = csv_text.strip().split("\n")

        # 1 header + 3 data rows (600000.SH filtered out)
        assert len(lines) == 4

    def test_export_empty_result(self):
        """空结果导出应只有表头"""
        config = _make_strategy_config()
        result = ScreenExecutor(config).run_eod_screen({})

        csv_text = export_screen_result_to_csv(result).decode("utf-8-sig")
        lines = csv_text.strip().split("\n")

        assert len(lines) == 1  # header only


# ---------------------------------------------------------------------------
# Celery 任务测试
# ---------------------------------------------------------------------------


class TestRunEodScreening:
    """盘后选股 Celery 任务测试"""

    def test_returns_success_with_default_strategy(self):
        """默认策略应返回成功结果"""
        from unittest.mock import AsyncMock, MagicMock
        from app.tasks.screening import run_eod_screening

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_session),
            patch("app.tasks.screening.ScreenDataProvider") as mock_cls,
            patch("app.tasks.screening.get_redis_client", return_value=mock_redis),
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value={})
            mock_cls.return_value = mock_provider

            result = run_eod_screening()

        assert result["status"] == "success"
        assert result["screen_type"] == "EOD"
        assert "passed" in result
        assert "screen_time" in result

    def test_accepts_strategy_dict(self):
        """应接受策略字典参数"""
        from unittest.mock import AsyncMock
        from app.tasks.screening import run_eod_screening

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        strategy_dict = _make_strategy_config().to_dict()

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_session),
            patch("app.tasks.screening.ScreenDataProvider") as mock_cls,
            patch("app.tasks.screening.get_redis_client", return_value=mock_redis),
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value={})
            mock_cls.return_value = mock_provider

            result = run_eod_screening(strategy_dict=strategy_dict)

        assert result["status"] == "success"


class TestRunRealtimeScreening:
    """盘中实时选股 Celery 任务测试"""

    @patch("app.tasks.screening._is_trading_hours", return_value=False)
    def test_skips_outside_trading_hours(self, mock_hours):
        """非交易时段应跳过"""
        from app.tasks.screening import run_realtime_screening

        result = run_realtime_screening()

        assert result["status"] == "skipped"
        assert result["reason"] == "outside_trading_hours"

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_runs_during_trading_hours(self, mock_hours):
        """交易时段应执行选股"""
        from app.tasks.screening import run_realtime_screening

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # 未预热
        mock_redis.aclose = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = run_realtime_screening()

        assert result["status"] == "success"
        assert result["screen_type"] == "REALTIME"

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_accepts_strategy_dict(self, mock_hours):
        """应接受策略字典参数"""
        from app.tasks.screening import run_realtime_screening

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with (
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            strategy_dict = _make_strategy_config().to_dict()
            result = run_realtime_screening(strategy_dict=strategy_dict)

        assert result["status"] == "success"
