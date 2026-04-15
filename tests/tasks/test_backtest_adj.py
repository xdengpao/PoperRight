"""Unit tests for BacktestTask forward-adjustment integration.

Validates:
- Requirements 7.1: BacktestTask loads forward-adjustment factors for all stocks
- Requirements 7.2: BacktestTask applies adjust_kline_bars before passing data to BacktestEngine
- Requirements 7.6: Symbols without factors use raw bars and log a warning
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.adjustment_factor import AdjustmentFactor
from app.core.schemas import KlineBar


# ---------------------------------------------------------------------------
# Helpers — build known test data
# ---------------------------------------------------------------------------

def _make_bar(symbol: str, dt: datetime, close: Decimal) -> KlineBar:
    """Create a minimal KlineBar for testing."""
    return KlineBar(
        time=dt,
        symbol=symbol,
        freq="1d",
        open=close,
        high=close + Decimal("1"),
        low=close - Decimal("1"),
        close=close,
        volume=10000,
        amount=Decimal("500000"),
        turnover=Decimal("2.5"),
        vol_ratio=Decimal("1.1"),
    )


# ---------------------------------------------------------------------------
# Fixtures — mock rows returned by SQL queries
# ---------------------------------------------------------------------------

# Two stocks: 000001.SZ has factors, 000002.SZ does not
KLINE_ROWS = [
    # symbol, time, open, high, low, close, volume, amount, turnover, vol_ratio
    ("000001.SZ", datetime(2024, 6, 3), 10, 11, 9, 10, 10000, 500000, 2.5, 1.1),
    ("000001.SZ", datetime(2024, 6, 4), 10, 11, 9, 10, 10000, 500000, 2.5, 1.1),
    ("000002.SZ", datetime(2024, 6, 3), 20, 21, 19, 20, 20000, 800000, 3.0, 1.2),
    ("000002.SZ", datetime(2024, 6, 4), 20, 21, 19, 20, 20000, 800000, 3.0, 1.2),
]

# Only 000001.SZ has adjustment factors
ADJ_FACTOR_ROWS = [
    ("000001.SZ", date(2024, 6, 3), Decimal("1.05")),
    ("000001.SZ", date(2024, 6, 4), Decimal("1.10")),
]

# Latest factors — only 000001.SZ
LATEST_FACTOR_ROWS = [
    ("000001.SZ", Decimal("1.10")),
]


# ---------------------------------------------------------------------------
# Helper to build a mock Session that returns different results per query
# ---------------------------------------------------------------------------

def _build_mock_session(kline_rows, adj_rows, latest_rows):
    """Return a mock Session whose execute().fetchall() returns the right rows
    depending on the SQL text passed to execute()."""
    session = MagicMock()

    def _execute_side_effect(stmt, params=None):
        result = MagicMock()
        sql_text = str(stmt.text) if hasattr(stmt, "text") else str(stmt)
        if "DISTINCT ON" in sql_text:
            result.fetchall.return_value = latest_rows
        elif "adjustment_factor" in sql_text:
            result.fetchall.return_value = adj_rows
        elif "kline" in sql_text:
            result.fetchall.return_value = kline_rows
        else:
            result.fetchall.return_value = []
        return result

    session.execute.side_effect = _execute_side_effect
    return session


def _setup_mocks(mock_create_engine, mock_adjust, mock_engine_cls, mock_redis,
                 kline_rows=KLINE_ROWS, adj_rows=ADJ_FACTOR_ROWS,
                 latest_rows=LATEST_FACTOR_ROWS, adjust_side_effect=None):
    """Common mock setup for all tests."""
    # Setup mock adjust
    if adjust_side_effect is None:
        mock_adjust.side_effect = lambda bars, factors, latest: bars
    else:
        mock_adjust.side_effect = adjust_side_effect

    # Setup mock BacktestEngine
    mock_engine = MagicMock()
    mock_result = MagicMock(
        total_trades=0, total_return=0.0, annual_return=0.0,
        win_rate=0.0, profit_loss_ratio=0.0, max_drawdown=0.0,
        sharpe_ratio=0.0, calmar_ratio=0.0, avg_holding_days=0.0,
        equity_curve=[], trade_records=[],
    )
    mock_engine.run_backtest.return_value = mock_result
    mock_engine_cls.return_value = mock_engine

    # Build mock sessions
    kline_session = _build_mock_session(kline_rows, [], [])
    adj_session = _build_mock_session([], adj_rows, latest_rows)

    # Mock create_engine to return disposable engine mocks
    engine_call_count = [0]

    def _create_engine_side_effect(url):
        eng = MagicMock()
        eng.dispose = MagicMock()
        engine_call_count[0] += 1
        return eng

    mock_create_engine.side_effect = _create_engine_side_effect

    return mock_engine, kline_session, adj_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBacktestAdjustmentIntegration:
    """Tests for forward-adjustment integration in run_backtest_task."""

    @patch("app.tasks.backtest._redis_set")
    @patch("app.services.backtest_engine.BacktestEngine")
    @patch("app.tasks.backtest.adjust_kline_bars")
    @patch("app.tasks.backtest.create_engine")
    def test_adjust_kline_bars_called_with_correct_args(
        self,
        mock_create_engine,
        mock_adjust,
        mock_engine_cls,
        mock_redis,
    ):
        """Validates Requirement 7.1, 7.2: factors are loaded and adjust_kline_bars
        is called with the correct bars, factors list, and latest factor."""
        mock_engine, kline_session, adj_session = _setup_mocks(
            mock_create_engine, mock_adjust, mock_engine_cls, mock_redis,
        )

        with patch("app.tasks.backtest.Session") as mock_session_cls:
            session_call_count = [0]

            def _session_side_effect(engine):
                ctx = MagicMock()
                idx = session_call_count[0]
                session_call_count[0] += 1
                if idx == 0:
                    ctx.__enter__ = MagicMock(return_value=kline_session)
                else:
                    ctx.__enter__ = MagicMock(return_value=adj_session)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_session_cls.side_effect = _session_side_effect

            from app.tasks.backtest import run_backtest_task

            # Call the task function directly (not via Celery)
            result = run_backtest_task.apply(
                args=("test-run-001",),
                kwargs={
                    "start_date": "2024-06-01",
                    "end_date": "2024-06-30",
                },
            ).get()

        # adjust_kline_bars should be called once — only for 000001.SZ
        assert mock_adjust.call_count == 1

        call_args = mock_adjust.call_args
        bars_arg = call_args[0][0]
        factors_arg = call_args[0][1]
        latest_arg = call_args[0][2]

        # Verify bars are for 000001.SZ
        assert len(bars_arg) == 2
        assert all(b.symbol == "000001.SZ" for b in bars_arg)

        # Verify factors are AdjustmentFactor objects with correct values
        assert len(factors_arg) == 2
        assert factors_arg[0].symbol == "000001.SZ"
        assert factors_arg[0].adj_factor == Decimal("1.05")
        assert factors_arg[1].adj_factor == Decimal("1.10")

        # Verify latest factor
        assert latest_arg == Decimal("1.10")

    @patch("app.tasks.backtest._redis_set")
    @patch("app.services.backtest_engine.BacktestEngine")
    @patch("app.tasks.backtest.adjust_kline_bars")
    @patch("app.tasks.backtest.create_engine")
    def test_symbols_without_factors_use_raw_bars_and_log_warning(
        self,
        mock_create_engine,
        mock_adjust,
        mock_engine_cls,
        mock_redis,
        caplog,
    ):
        """Validates Requirement 7.6: symbols without adjustment factors use raw
        bars and a warning is logged."""
        mock_engine, kline_session, adj_session = _setup_mocks(
            mock_create_engine, mock_adjust, mock_engine_cls, mock_redis,
        )

        with patch("app.tasks.backtest.Session") as mock_session_cls:
            session_call_count = [0]

            def _session_side_effect(engine):
                ctx = MagicMock()
                idx = session_call_count[0]
                session_call_count[0] += 1
                if idx == 0:
                    ctx.__enter__ = MagicMock(return_value=kline_session)
                else:
                    ctx.__enter__ = MagicMock(return_value=adj_session)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_session_cls.side_effect = _session_side_effect

            from app.tasks.backtest import run_backtest_task

            with caplog.at_level(logging.WARNING, logger="app.tasks.backtest"):
                result = run_backtest_task.apply(
                    args=("test-run-002",),
                    kwargs={
                        "start_date": "2024-06-01",
                        "end_date": "2024-06-30",
                    },
                ).get()

        # 000002.SZ has no factors → should NOT be passed to adjust_kline_bars
        for c in mock_adjust.call_args_list:
            bars_arg = c[0][0]
            assert all(b.symbol != "000002.SZ" for b in bars_arg)

        # A warning should be logged for 000002.SZ
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("000002.SZ" in msg and "无前复权因子" in msg for msg in warning_messages), (
            f"Expected warning about 000002.SZ missing factors, got: {warning_messages}"
        )

    @patch("app.tasks.backtest._redis_set")
    @patch("app.services.backtest_engine.BacktestEngine")
    @patch("app.tasks.backtest.adjust_kline_bars")
    @patch("app.tasks.backtest.create_engine")
    def test_adjusted_data_passed_to_backtest_engine(
        self,
        mock_create_engine,
        mock_adjust,
        mock_engine_cls,
        mock_redis,
    ):
        """Validates Requirement 7.2: BacktestEngine receives forward-adjusted
        kline data (not raw bars) for stocks that have factors."""

        def _fake_adjust(bars, factors, latest):
            """Return bars with a distinctive close to verify engine gets adjusted data."""
            adjusted = []
            for b in bars:
                adjusted.append(KlineBar(
                    time=b.time, symbol=b.symbol, freq=b.freq,
                    open=Decimal("99.99"), high=Decimal("99.99"),
                    low=Decimal("99.99"), close=Decimal("99.99"),
                    volume=b.volume, amount=b.amount,
                    turnover=b.turnover, vol_ratio=b.vol_ratio,
                ))
            return adjusted

        mock_engine, kline_session, adj_session = _setup_mocks(
            mock_create_engine, mock_adjust, mock_engine_cls, mock_redis,
            adjust_side_effect=_fake_adjust,
        )

        with patch("app.tasks.backtest.Session") as mock_session_cls:
            session_call_count = [0]

            def _session_side_effect(engine):
                ctx = MagicMock()
                idx = session_call_count[0]
                session_call_count[0] += 1
                if idx == 0:
                    ctx.__enter__ = MagicMock(return_value=kline_session)
                else:
                    ctx.__enter__ = MagicMock(return_value=adj_session)
                ctx.__exit__ = MagicMock(return_value=False)
                return ctx

            mock_session_cls.side_effect = _session_side_effect

            from app.tasks.backtest import run_backtest_task

            result = run_backtest_task.apply(
                args=("test-run-003",),
                kwargs={
                    "start_date": "2024-06-01",
                    "end_date": "2024-06-30",
                },
            ).get()

        # Verify BacktestEngine.run_backtest was called
        mock_engine.run_backtest.assert_called_once()
        call_kwargs = mock_engine.run_backtest.call_args[1]
        kline_data = call_kwargs["kline_data"]

        # 000001.SZ bars should have the adjusted close of 99.99
        assert "000001.SZ" in kline_data
        for bar in kline_data["000001.SZ"]:
            assert bar.close == Decimal("99.99"), (
                "BacktestEngine should receive adjusted bars for stocks with factors"
            )

        # 000002.SZ bars should retain original close of 20
        assert "000002.SZ" in kline_data
        for bar in kline_data["000002.SZ"]:
            assert bar.close == Decimal("20"), (
                "BacktestEngine should receive raw bars for stocks without factors"
            )
