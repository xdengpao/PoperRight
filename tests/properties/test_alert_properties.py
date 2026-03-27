"""
AlertService 属性测试（Hypothesis）

**Validates: Requirements 8.1, 8.2, 8.3**

属性 14：预警触发正确性
"""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import AlertConfig, AlertType
from app.services.alert_service import AlertService, ALERT_START, ALERT_END


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 阈值策略：正浮点数
_threshold_strategy = st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False)

# 股票数据值策略
_value_strategy = st.floats(min_value=-500.0, max_value=1500.0, allow_nan=False, allow_infinity=False)

# 股票代码策略
_symbol_strategy = st.from_regex(r"[0-9]{6}", fullmatch=True)


@st.composite
def alert_config_strategy(draw, *, force_active: bool = True, force_has_threshold: bool = True):
    """生成随机 AlertConfig，extra 中包含 0~3 个阈值字段。"""
    user_id = draw(st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnop"))
    symbol = draw(st.one_of(st.none(), _symbol_strategy))
    is_active = force_active or draw(st.booleans())
    alert_type = draw(st.sampled_from(list(AlertType)))

    extra: dict = {}
    has_trend = draw(st.booleans())
    has_money = draw(st.booleans())
    has_breakout = draw(st.booleans())

    if has_trend:
        extra["trend_score_threshold"] = draw(_threshold_strategy)
    if has_money:
        extra["money_flow_threshold"] = draw(_threshold_strategy)
    if has_breakout:
        extra["breakout_amp_threshold"] = draw(_threshold_strategy)

    if force_has_threshold and not extra:
        # Ensure at least one threshold is present
        key = draw(st.sampled_from([
            "trend_score_threshold", "money_flow_threshold", "breakout_amp_threshold",
        ]))
        extra[key] = draw(_threshold_strategy)

    return AlertConfig(
        user_id=user_id,
        alert_type=alert_type,
        symbol=symbol,
        is_active=is_active,
        extra=extra,
    )


@st.composite
def stock_data_strategy(draw, symbol: str | None = None):
    """生成随机股票数据 dict。"""
    sym = symbol or draw(_symbol_strategy)
    return {
        "symbol": sym,
        "trend_score": draw(_value_strategy),
        "money_flow": draw(_value_strategy),
        "breakout_amp": draw(_value_strategy),
    }


def _make_trading_hours_now(hour: int, minute: int = 0):
    """返回交易时段内的固定时间函数。"""
    def _now() -> datetime:
        return datetime(2025, 1, 6, hour, minute, 0)
    return _now


def _meets_any_threshold(cfg: AlertConfig, stock_data: dict) -> bool:
    """独立计算：股票数据是否满足配置中的任一阈值条件（OR 逻辑）。"""
    extra = cfg.extra

    trend_th = extra.get("trend_score_threshold")
    money_th = extra.get("money_flow_threshold")
    breakout_th = extra.get("breakout_amp_threshold")

    if trend_th is None and money_th is None and breakout_th is None:
        return False

    if trend_th is not None:
        score = stock_data.get("trend_score")
        if score is not None and score >= trend_th:
            return True

    if money_th is not None:
        flow = stock_data.get("money_flow")
        if flow is not None and flow >= money_th:
            return True

    if breakout_th is not None:
        amp = stock_data.get("breakout_amp")
        if amp is not None and amp >= breakout_th:
            return True

    return False


# ---------------------------------------------------------------------------
# 属性 14：预警触发正确性
# Feature: a-share-quant-trading-system, Property 14: 预警触发正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    config=alert_config_strategy(force_active=True, force_has_threshold=True),
    stock_data=stock_data_strategy(),
)
def test_alert_trigger_correctness_meets_threshold(config, stock_data):
    """
    # Feature: a-share-quant-trading-system, Property 14: 预警触发正确性

    **Validates: Requirements 8.1, 8.2**

    交易时段内，当股票数据满足至少一个配置阈值时应生成预警；
    不满足任何阈值时不应生成预警。
    """
    # 使用全局匹配（symbol=None）以排除 symbol 不匹配的干扰
    config.symbol = None

    svc = AlertService(now_fn=_make_trading_hours_now(10, 30))
    svc.register_threshold("test_user", config)

    alerts = svc.check_and_generate_alerts("test_user", stock_data)
    expected_trigger = _meets_any_threshold(config, stock_data)

    if expected_trigger:
        assert len(alerts) == 1, (
            f"满足阈值条件应生成 1 条预警，实际生成 {len(alerts)} 条。"
            f"\n配置 extra={config.extra}, 股票数据={stock_data}"
        )
        assert alerts[0].user_id == "test_user"
    else:
        assert len(alerts) == 0, (
            f"不满足阈值条件不应生成预警，实际生成 {len(alerts)} 条。"
            f"\n配置 extra={config.extra}, 股票数据={stock_data}"
        )


@settings(max_examples=100)
@given(
    config=alert_config_strategy(force_active=True, force_has_threshold=True),
    stock_data=stock_data_strategy(),
    hour=st.one_of(
        st.integers(min_value=0, max_value=9),
        st.integers(min_value=16, max_value=23),
    ),
    minute=st.integers(min_value=0, max_value=59),
)
def test_non_trading_hours_suppress_all_alerts(config, stock_data, hour, minute):
    """
    # Feature: a-share-quant-trading-system, Property 14: 预警触发正确性

    **Validates: Requirements 8.3**

    非交易时段（9:25 之前或 15:00 之后）不应生成任何预警，
    无论股票数据是否满足阈值条件。
    """
    # Ensure we're outside trading hours
    if hour == 9:
        assume(minute < 25)

    config.symbol = None

    svc = AlertService(now_fn=_make_trading_hours_now(hour, minute))
    svc.register_threshold("test_user", config)

    alerts = svc.check_and_generate_alerts("test_user", stock_data)

    assert len(alerts) == 0, (
        f"非交易时段 {hour:02d}:{minute:02d} 不应生成预警，"
        f"实际生成 {len(alerts)} 条"
    )


@settings(max_examples=100)
@given(
    config=alert_config_strategy(force_active=False, force_has_threshold=True),
    stock_data=stock_data_strategy(),
)
def test_inactive_config_no_alerts(config, stock_data):
    """
    # Feature: a-share-quant-trading-system, Property 14: 预警触发正确性

    **Validates: Requirements 8.1**

    is_active=False 的配置不应触发任何预警，即使数据满足阈值。
    """
    config.is_active = False
    config.symbol = None

    svc = AlertService(now_fn=_make_trading_hours_now(10, 30))
    svc.register_threshold("test_user", config)

    alerts = svc.check_and_generate_alerts("test_user", stock_data)

    assert len(alerts) == 0, (
        f"is_active=False 的配置不应触发预警，实际生成 {len(alerts)} 条"
    )
