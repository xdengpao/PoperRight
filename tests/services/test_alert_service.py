"""
AlertService 单元测试

覆盖：
- register_threshold / get_thresholds / clear_thresholds
- is_alert_active（交易时段 / 非交易时段）
- check_and_generate_alerts（趋势打分 / 资金流入 / 突破幅度阈值触发）
- 非交易时段预警停止逻辑
- 不满足阈值不触发预警
"""

from __future__ import annotations

from datetime import datetime, time

import pytest

from app.core.schemas import Alert, AlertConfig, AlertType
from app.services.alert_service import AlertService, ALERT_START, ALERT_END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_now(hour: int, minute: int = 0, second: int = 0):
    """返回一个固定时间的 now 函数"""
    def _now() -> datetime:
        return datetime(2025, 1, 6, hour, minute, second)
    return _now


def _make_config(
    user_id: str = "u1",
    *,
    trend_score_threshold: float | None = None,
    money_flow_threshold: float | None = None,
    breakout_amp_threshold: float | None = None,
    symbol: str | None = None,
    is_active: bool = True,
) -> AlertConfig:
    extra: dict = {}
    if trend_score_threshold is not None:
        extra["trend_score_threshold"] = trend_score_threshold
    if money_flow_threshold is not None:
        extra["money_flow_threshold"] = money_flow_threshold
    if breakout_amp_threshold is not None:
        extra["breakout_amp_threshold"] = breakout_amp_threshold
    return AlertConfig(
        user_id=user_id,
        alert_type=AlertType.SCREEN_RESULT,
        symbol=symbol,
        is_active=is_active,
        extra=extra,
    )


def _stock_data(
    symbol: str = "600000",
    trend_score: float = 85.0,
    money_flow: float = 1500.0,
    breakout_amp: float = 3.0,
) -> dict:
    return {
        "symbol": symbol,
        "trend_score": trend_score,
        "money_flow": money_flow,
        "breakout_amp": breakout_amp,
    }


# ---------------------------------------------------------------------------
# register / get / clear thresholds
# ---------------------------------------------------------------------------

class TestThresholdManagement:

    def test_register_and_get(self):
        svc = AlertService()
        cfg = _make_config("u1", trend_score_threshold=80)
        svc.register_threshold("u1", cfg)
        assert len(svc.get_thresholds("u1")) == 1
        assert svc.get_thresholds("u1")[0] is cfg

    def test_register_multiple(self):
        svc = AlertService()
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        svc.register_threshold("u1", _make_config("u1", money_flow_threshold=1000))
        assert len(svc.get_thresholds("u1")) == 2

    def test_get_empty(self):
        svc = AlertService()
        assert svc.get_thresholds("unknown") == []

    def test_clear(self):
        svc = AlertService()
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        svc.clear_thresholds("u1")
        assert svc.get_thresholds("u1") == []

    def test_clear_nonexistent_user(self):
        """清除不存在的用户不报错"""
        svc = AlertService()
        svc.clear_thresholds("nobody")  # should not raise


# ---------------------------------------------------------------------------
# is_alert_active
# ---------------------------------------------------------------------------

class TestIsAlertActive:

    def test_during_trading_hours(self):
        """交易时段内（10:00）预警应活跃"""
        svc = AlertService(now_fn=_make_now(10, 0))
        assert svc.is_alert_active() is True

    def test_at_start_boundary(self):
        """9:25 边界应活跃"""
        svc = AlertService(now_fn=_make_now(9, 25))
        assert svc.is_alert_active() is True

    def test_at_end_boundary(self):
        """15:00 边界应活跃"""
        svc = AlertService(now_fn=_make_now(15, 0))
        assert svc.is_alert_active() is True

    def test_before_trading_hours(self):
        """9:24 应不活跃"""
        svc = AlertService(now_fn=_make_now(9, 24))
        assert svc.is_alert_active() is False

    def test_after_trading_hours(self):
        """15:01 应不活跃"""
        svc = AlertService(now_fn=_make_now(15, 0, 1))
        assert svc.is_alert_active() is False

    def test_late_night(self):
        """深夜 23:00 应不活跃"""
        svc = AlertService(now_fn=_make_now(23, 0))
        assert svc.is_alert_active() is False

    def test_early_morning(self):
        """凌晨 6:00 应不活跃"""
        svc = AlertService(now_fn=_make_now(6, 0))
        assert svc.is_alert_active() is False


# ---------------------------------------------------------------------------
# check_and_generate_alerts — 触发场景
# ---------------------------------------------------------------------------

class TestAlertGeneration:

    def test_trend_score_triggers(self):
        """趋势打分 ≥ 阈值时触发预警"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=85))
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.SCREEN_RESULT
        assert alerts[0].symbol == "600000"

    def test_money_flow_triggers(self):
        """资金流入 ≥ 阈值时触发预警"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", money_flow_threshold=1000))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(money_flow=1500))
        assert len(alerts) == 1

    def test_breakout_amp_triggers(self):
        """突破幅度 ≥ 阈值时触发预警"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", breakout_amp_threshold=2.0))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(breakout_amp=3.0))
        assert len(alerts) == 1

    def test_exact_threshold_triggers(self):
        """恰好等于阈值时应触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=85))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=85))
        assert len(alerts) == 1

    def test_multiple_configs_multiple_alerts(self):
        """多个配置分别触发，生成多条预警"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        svc.register_threshold("u1", _make_config("u1", money_flow_threshold=1000))
        alerts = svc.check_and_generate_alerts(
            "u1", _stock_data(trend_score=90, money_flow=2000)
        )
        assert len(alerts) == 2


# ---------------------------------------------------------------------------
# check_and_generate_alerts — 不触发场景
# ---------------------------------------------------------------------------

class TestAlertNoTrigger:

    def test_below_trend_threshold(self):
        """趋势打分低于阈值不触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=90))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=85))
        assert alerts == []

    def test_below_money_flow_threshold(self):
        """资金流入低于阈值不触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", money_flow_threshold=2000))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(money_flow=1500))
        assert alerts == []

    def test_below_breakout_threshold(self):
        """突破幅度低于阈值不触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", breakout_amp_threshold=5.0))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(breakout_amp=3.0))
        assert alerts == []

    def test_no_configs_no_alerts(self):
        """没有配置时不生成预警"""
        svc = AlertService(now_fn=_make_now(10, 0))
        alerts = svc.check_and_generate_alerts("u1", _stock_data())
        assert alerts == []

    def test_inactive_config_ignored(self):
        """is_active=False 的配置不触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold(
            "u1", _make_config("u1", trend_score_threshold=80, is_active=False)
        )
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=90))
        assert alerts == []

    def test_symbol_mismatch_no_alert(self):
        """配置了特定股票但数据是其他股票，不触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold(
            "u1", _make_config("u1", trend_score_threshold=80, symbol="000001")
        )
        alerts = svc.check_and_generate_alerts("u1", _stock_data(symbol="600000", trend_score=90))
        assert alerts == []

    def test_no_threshold_in_extra(self):
        """extra 中没有任何阈值字段不触发"""
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1"))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=99))
        assert alerts == []


# ---------------------------------------------------------------------------
# 非交易时段预警停止
# ---------------------------------------------------------------------------

class TestNonTradingHoursStop:

    def test_no_alerts_after_market_close(self):
        """15:01 不生成预警"""
        svc = AlertService(now_fn=_make_now(15, 0, 1))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=90))
        assert alerts == []

    def test_no_alerts_before_market_open(self):
        """9:24 不生成预警"""
        svc = AlertService(now_fn=_make_now(9, 24))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=90))
        assert alerts == []

    def test_no_alerts_at_midnight(self):
        """午夜不生成预警"""
        svc = AlertService(now_fn=_make_now(0, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=90))
        assert alerts == []


# ---------------------------------------------------------------------------
# Alert 消息内容验证
# ---------------------------------------------------------------------------

class TestAlertContent:

    def test_alert_has_correct_user_id(self):
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=90))
        assert alerts[0].user_id == "u1"

    def test_alert_title_contains_symbol(self):
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(symbol="000001", trend_score=90))
        assert "000001" in alerts[0].title

    def test_alert_message_contains_threshold_info(self):
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(trend_score=90))
        assert "趋势打分" in alerts[0].message

    def test_alert_extra_contains_stock_data(self):
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80))
        data = _stock_data(trend_score=90)
        alerts = svc.check_and_generate_alerts("u1", data)
        assert alerts[0].extra["stock_data"] == data

    def test_alert_symbol_matches_stock(self):
        svc = AlertService(now_fn=_make_now(10, 0))
        svc.register_threshold("u1", _make_config("u1", trend_score_threshold=80, symbol="600000"))
        alerts = svc.check_and_generate_alerts("u1", _stock_data(symbol="600000", trend_score=90))
        assert alerts[0].symbol == "600000"
