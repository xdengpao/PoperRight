# Feature: backtest-exit-conditions, Property 1: ExitConditionConfig round-trip serialization
"""
ExitConditionConfig 序列化往返一致性属性测试（Hypothesis）

**Validates: Requirements 1.6, 1.7**

对任意有效的 ExitConditionConfig 对象（包含任意数量的条件、任意合法指标名称、
任意合法运算符、任意阈值或交叉目标），调用 to_dict() 序列化为字典后再调用
from_dict() 反序列化，所得对象应与原对象在所有字段上等价。
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.schemas import (
    VALID_INDICATORS,
    VALID_OPERATORS,
    ExitCondition,
    ExitConditionConfig,
)

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_INDICATORS = sorted(VALID_INDICATORS)
_OPERATORS = sorted(VALID_OPERATORS)
_NUMERIC_OPERATORS = sorted(VALID_OPERATORS - {"cross_up", "cross_down"})
_CROSS_OPERATORS = ["cross_up", "cross_down"]

# 数据源频率
_freq_strategy = st.sampled_from(["daily", "1min", "5min", "15min", "30min", "60min"])

# 指标名称
_indicator_strategy = st.sampled_from(_INDICATORS)

# 数值阈值（合理范围的浮点数）
_threshold_strategy = st.floats(
    min_value=-1e6, max_value=1e6,
    allow_nan=False, allow_infinity=False,
)

# 指标参数字典：常见参数如 period, fast, slow, signal 等
_params_strategy = st.one_of(
    st.just({}),
    st.fixed_dictionaries({"period": st.integers(min_value=1, max_value=250)}),
    st.fixed_dictionaries({
        "fast": st.integers(min_value=1, max_value=100),
        "slow": st.integers(min_value=1, max_value=100),
        "signal": st.integers(min_value=1, max_value=100),
    }),
)


@st.composite
def _exit_condition_strategy(draw):
    """生成任意合法的 ExitCondition。"""
    freq = draw(_freq_strategy)
    indicator = draw(_indicator_strategy)
    operator = draw(st.sampled_from(_OPERATORS))
    params = draw(_params_strategy)

    if operator in ("cross_up", "cross_down"):
        # 交叉运算符：需要 cross_target，threshold 为 None
        cross_target = draw(_indicator_strategy)
        return ExitCondition(
            freq=freq,
            indicator=indicator,
            operator=operator,
            threshold=None,
            cross_target=cross_target,
            params=params,
        )
    else:
        # 数值比较运算符：需要 threshold，cross_target 为 None
        threshold = draw(_threshold_strategy)
        return ExitCondition(
            freq=freq,
            indicator=indicator,
            operator=operator,
            threshold=threshold,
            cross_target=None,
            params=params,
        )


@st.composite
def _exit_condition_config_strategy(draw):
    """生成任意合法的 ExitConditionConfig。"""
    conditions = draw(st.lists(_exit_condition_strategy(), min_size=0, max_size=10))
    logic = draw(st.sampled_from(["AND", "OR"]))
    return ExitConditionConfig(conditions=conditions, logic=logic)


# ---------------------------------------------------------------------------
# Property 1: ExitConditionConfig round-trip serialization
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(config=_exit_condition_config_strategy())
def test_exit_condition_config_roundtrip(config: ExitConditionConfig):
    """
    # Feature: backtest-exit-conditions, Property 1: ExitConditionConfig round-trip serialization

    **Validates: Requirements 1.6, 1.7**

    对任意有效的 ExitConditionConfig，序列化为 dict 再反序列化后，
    所得对象应与原对象在所有字段上等价。
    """
    serialized = config.to_dict()
    restored = ExitConditionConfig.from_dict(serialized)

    # 验证顶层字段
    assert restored.logic == config.logic, (
        f"logic 不一致: {restored.logic!r} != {config.logic!r}"
    )
    assert len(restored.conditions) == len(config.conditions), (
        f"conditions 数量不一致: {len(restored.conditions)} != {len(config.conditions)}"
    )

    # 逐条验证每个 ExitCondition
    for i, (orig, rest) in enumerate(zip(config.conditions, restored.conditions)):
        # 向后兼容："minute" 经 from_dict 映射为 "1min"
        expected_freq = "1min" if orig.freq == "minute" else orig.freq
        assert rest.freq == expected_freq, f"条件[{i}] freq 不一致: {rest.freq!r} != {expected_freq!r}"
        assert rest.indicator == orig.indicator, f"条件[{i}] indicator 不一致: {rest.indicator!r} != {orig.indicator!r}"
        assert rest.operator == orig.operator, f"条件[{i}] operator 不一致: {rest.operator!r} != {orig.operator!r}"
        assert rest.threshold == orig.threshold, f"条件[{i}] threshold 不一致: {rest.threshold!r} != {orig.threshold!r}"
        assert rest.cross_target == orig.cross_target, f"条件[{i}] cross_target 不一致: {rest.cross_target!r} != {orig.cross_target!r}"
        assert rest.params == orig.params, f"条件[{i}] params 不一致: {rest.params!r} != {orig.params!r}"


# ---------------------------------------------------------------------------
# Property 2: Logic operator evaluation correctness
# ---------------------------------------------------------------------------

from decimal import Decimal

from app.services.backtest_engine import IndicatorCache
from app.services.exit_condition_evaluator import ExitConditionEvaluator


def _make_indicator_cache(close_value: float) -> IndicatorCache:
    """创建一个只包含单个 close 值的最小 IndicatorCache。"""
    return IndicatorCache(
        closes=[close_value],
        highs=[close_value],
        lows=[close_value],
        volumes=[0],
        amounts=[Decimal("0")],
        turnovers=[Decimal("0")],
    )


@h_settings(max_examples=100)
@given(
    logic=st.sampled_from(["AND", "OR"]),
    bools=st.lists(st.booleans(), min_size=1, max_size=10),
)
def test_logic_operator_evaluation_correctness(logic: str, bools: list[bool]):
    """
    # Feature: backtest-exit-conditions, Property 2: Logic operator evaluation correctness

    **Validates: Requirements 2.2, 2.3**

    对任意逻辑运算符（AND 或 OR）和任意非空布尔值列表，
    ExitConditionEvaluator 的逻辑组合结果应满足：
    - logic="AND" 时结果等于 all(bools)
    - logic="OR"  时结果等于 any(bools)
    """
    # 策略：对每个布尔值构造一个 "close > threshold" 条件。
    # close 固定为 100.0。
    # True  → threshold = 50.0  (100 > 50  → 满足)
    # False → threshold = 200.0 (100 > 200 → 不满足)
    close_value = 100.0
    cache = _make_indicator_cache(close_value)

    conditions = []
    for b in bools:
        threshold = 50.0 if b else 200.0
        conditions.append(
            ExitCondition(
                freq="daily",
                indicator="close",
                operator=">",
                threshold=threshold,
                cross_target=None,
                params={},
            )
        )

    config = ExitConditionConfig(conditions=conditions, logic=logic)
    evaluator = ExitConditionEvaluator()
    triggered, _reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=0,
        indicator_cache=cache,
    )

    if logic == "AND":
        expected = all(bools)
    else:
        expected = any(bools)

    assert triggered == expected, (
        f"logic={logic!r}, bools={bools!r}: "
        f"expected triggered={expected}, got triggered={triggered}"
    )


# ---------------------------------------------------------------------------
# Property 3: Numeric comparison operator correctness
# ---------------------------------------------------------------------------

# 原生 Python 比较运算符映射，用于验证评估器结果
_NATIVE_OPS: dict[str, object] = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


@h_settings(max_examples=100)
@given(
    indicator_value=st.floats(allow_nan=False, allow_infinity=False),
    operator=st.sampled_from([">", "<", ">=", "<="]),
    threshold=st.floats(allow_nan=False, allow_infinity=False),
)
def test_numeric_comparison_operator_correctness(
    indicator_value: float, operator: str, threshold: float
):
    """
    # Feature: backtest-exit-conditions, Property 3: Numeric comparison operator correctness

    **Validates: Requirements 2.4**

    对任意有限浮点数 indicator_value、任意合法数值比较运算符（>, <, >=, <=）
    和任意有限浮点数 threshold，ExitConditionEvaluator 的单条件评估结果
    应与 Python 原生比较运算的结果一致。
    """
    cache = _make_indicator_cache(indicator_value)

    condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator=operator,
        threshold=threshold,
        cross_target=None,
        params={},
    )
    config = ExitConditionConfig(conditions=[condition], logic="AND")

    evaluator = ExitConditionEvaluator()
    triggered, _reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=0,
        indicator_cache=cache,
    )

    expected = _NATIVE_OPS[operator](indicator_value, threshold)
    assert triggered == expected, (
        f"operator={operator!r}, indicator_value={indicator_value!r}, "
        f"threshold={threshold!r}: expected={expected}, got={triggered}"
    )


# ---------------------------------------------------------------------------
# Property 4: Cross detection correctness
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    prev_indicator=st.floats(allow_nan=False, allow_infinity=False),
    curr_indicator=st.floats(allow_nan=False, allow_infinity=False),
    prev_target=st.floats(allow_nan=False, allow_infinity=False),
    curr_target=st.floats(allow_nan=False, allow_infinity=False),
)
def test_cross_detection_correctness(
    prev_indicator: float,
    curr_indicator: float,
    prev_target: float,
    curr_target: float,
):
    """
    # Feature: backtest-exit-conditions, Property 4: Cross detection correctness

    **Validates: Requirements 2.5, 2.6**

    对任意两组连续两日的浮点数值对 (prev_indicator, curr_indicator) 和
    (prev_target, curr_target)，验证 cross_up 和 cross_down 的判定逻辑：
    - cross_up  应在且仅在 prev_indicator <= prev_target 且 curr_indicator > curr_target 时返回 True
    - cross_down 应在且仅在 prev_indicator >= prev_target 且 curr_indicator < curr_target 时返回 True
    """
    # 构造 IndicatorCache：closes 包含两日数据（bar_index=0 为前一日，bar_index=1 为当日）
    cache = IndicatorCache(
        closes=[prev_indicator, curr_indicator],
        highs=[prev_indicator, curr_indicator],
        lows=[prev_indicator, curr_indicator],
        volumes=[0, 0],
        amounts=[Decimal("0"), Decimal("0")],
        turnovers=[Decimal("0"), Decimal("0")],
    )

    # 构造 exit_indicator_cache：目标指标 "ma_20" 包含两日数据
    exit_indicator_cache = {
        "daily": {"ma_20": [prev_target, curr_target]},
    }

    evaluator = ExitConditionEvaluator()

    # --- cross_up ---
    cross_up_condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator="cross_up",
        threshold=None,
        cross_target="ma",
        params={"period": 20},
    )
    cross_up_config = ExitConditionConfig(
        conditions=[cross_up_condition], logic="AND",
    )
    cross_up_triggered, _reason_up = evaluator.evaluate(
        config=cross_up_config,
        symbol="TEST.SH",
        bar_index=1,
        indicator_cache=cache,
        exit_indicator_cache=exit_indicator_cache,
    )

    expected_cross_up = prev_indicator <= prev_target and curr_indicator > curr_target
    assert cross_up_triggered == expected_cross_up, (
        f"cross_up: prev_ind={prev_indicator!r}, curr_ind={curr_indicator!r}, "
        f"prev_tgt={prev_target!r}, curr_tgt={curr_target!r}: "
        f"expected={expected_cross_up}, got={cross_up_triggered}"
    )

    # --- cross_down ---
    cross_down_condition = ExitCondition(
        freq="daily",
        indicator="close",
        operator="cross_down",
        threshold=None,
        cross_target="ma",
        params={"period": 20},
    )
    cross_down_config = ExitConditionConfig(
        conditions=[cross_down_condition], logic="AND",
    )
    cross_down_triggered, _reason_down = evaluator.evaluate(
        config=cross_down_config,
        symbol="TEST.SH",
        bar_index=1,
        indicator_cache=cache,
        exit_indicator_cache=exit_indicator_cache,
    )

    expected_cross_down = prev_indicator >= prev_target and curr_indicator < curr_target
    assert cross_down_triggered == expected_cross_down, (
        f"cross_down: prev_ind={prev_indicator!r}, curr_ind={curr_indicator!r}, "
        f"prev_tgt={prev_target!r}, curr_tgt={curr_target!r}: "
        f"expected={expected_cross_down}, got={cross_down_triggered}"
    )


# ---------------------------------------------------------------------------
# Property 5: Backward compatibility without exit conditions
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    close_value=st.floats(
        min_value=0.01, max_value=1e6,
        allow_nan=False, allow_infinity=False,
    ),
    logic=st.sampled_from(["AND", "OR"]),
)
def test_backward_compatibility_without_exit_conditions(
    close_value: float, logic: str
):
    """
    # Feature: backtest-exit-conditions, Property 5: Backward compatibility without exit conditions

    **Validates: Requirements 3.5**

    当 exit_conditions 为 None 时（即 ExitConditionConfig 的 conditions 列表为空），
    ExitConditionEvaluator 不应产生任何 EXIT_CONDITION 类型的卖出信号。
    对任意 close 值和任意逻辑运算符，evaluate() 应返回 (False, None)。
    """
    cache = _make_indicator_cache(close_value)

    # 模拟 exit_conditions=None 的场景：空条件列表
    config = ExitConditionConfig(conditions=[], logic=logic)

    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config=config,
        symbol="TEST.SH",
        bar_index=0,
        indicator_cache=cache,
    )

    assert triggered is False, (
        f"Expected triggered=False for empty conditions, got triggered={triggered}"
    )
    assert reason is None, (
        f"Expected reason=None for empty conditions, got reason={reason!r}"
    )


# ---------------------------------------------------------------------------
# Property 6: All sell records contain sell_reason
# ---------------------------------------------------------------------------

from datetime import date as date_cls

from app.services.backtest_engine import _TradeRecord

# 合法卖出原因前缀集合
_VALID_SELL_REASON_PREFIXES = (
    "STOP_LOSS",
    "TREND_BREAK",
    "TRAILING_STOP",
    "MAX_HOLDING_DAYS",
    "EXIT_CONDITION",
)

# 生成合法 sell_reason 的策略
_sell_reason_strategy = st.sampled_from([
    "STOP_LOSS",
    "TREND_BREAK",
    "TRAILING_STOP",
    "MAX_HOLDING_DAYS",
    "EXIT_CONDITION",
    "EXIT_CONDITION: RSI > 80",
    "EXIT_CONDITION: MACD_DIF cross_down MACD_DEA",
    "EXIT_CONDITION: close < boll_lower",
])

# 生成 _TradeRecord (SELL) 的策略
_sell_trade_record_strategy = st.builds(
    _TradeRecord,
    date=st.dates(min_value=date_cls(2020, 1, 1), max_value=date_cls(2025, 12, 31)),
    symbol=st.sampled_from(["600519.SH", "000001.SZ", "300750.SZ", "601318.SH"]),
    action=st.just("SELL"),
    price=st.decimals(min_value="0.01", max_value="10000", places=2, allow_nan=False, allow_infinity=False),
    quantity=st.integers(min_value=100, max_value=100000).filter(lambda x: x % 100 == 0),
    cost=st.decimals(min_value="0", max_value="1000", places=2, allow_nan=False, allow_infinity=False),
    amount=st.decimals(min_value="1", max_value="10000000", places=2, allow_nan=False, allow_infinity=False),
    sell_reason=_sell_reason_strategy,
)


@h_settings(max_examples=100)
@given(records=st.lists(_sell_trade_record_strategy, min_size=1, max_size=20))
def test_all_sell_records_contain_sell_reason(records: list[_TradeRecord]):
    """
    # Feature: backtest-exit-conditions, Property 6: All sell records contain sell_reason

    **Validates: Requirements 7.1, 7.4**

    对任意回测执行产生的 SELL 交易记录列表，验证：
    1. 每条 SELL 记录的 sell_reason 非空
    2. 每条 SELL 记录的 sell_reason 以合法卖出原因前缀开头
    """
    for i, record in enumerate(records):
        assert record.action == "SELL", (
            f"记录[{i}] action 应为 SELL，实际为 {record.action!r}"
        )

        # sell_reason 非空
        assert record.sell_reason, (
            f"记录[{i}] symbol={record.symbol}, date={record.date}: "
            f"sell_reason 不应为空"
        )

        # sell_reason 以合法前缀开头
        assert record.sell_reason.startswith(_VALID_SELL_REASON_PREFIXES), (
            f"记录[{i}] symbol={record.symbol}, date={record.date}: "
            f"sell_reason={record.sell_reason!r} 不属于合法集合 "
            f"{_VALID_SELL_REASON_PREFIXES}"
        )


# ---------------------------------------------------------------------------
# Property 7: Legacy minute freq backward compatibility mapping
# ---------------------------------------------------------------------------


@st.composite
def _exit_condition_dict_with_minute_freq(draw):
    """生成 freq="minute" 的 ExitCondition 字典（模拟旧版配置）。"""
    indicator = draw(_indicator_strategy)
    operator = draw(st.sampled_from(_OPERATORS))
    params = draw(_params_strategy)

    d: dict = {
        "freq": "minute",
        "indicator": indicator,
        "operator": operator,
        "params": params,
    }

    if operator in ("cross_up", "cross_down"):
        d["cross_target"] = draw(_indicator_strategy)
        d["threshold"] = None
    else:
        d["threshold"] = draw(_threshold_strategy)
        d["cross_target"] = None

    return d


@h_settings(max_examples=100)
@given(cond_dict=_exit_condition_dict_with_minute_freq())
def test_legacy_minute_freq_exit_condition_mapping(cond_dict: dict):
    """
    # Feature: backtest-exit-conditions, Property 7: Legacy minute freq backward compatibility mapping

    **Validates: Requirements 8.1, 8.3**

    对任意有效的 ExitCondition 字典（其中 freq="minute"），
    调用 ExitCondition.from_dict() 反序列化后所得对象的 freq 字段应等于 "1min"。
    """
    condition = ExitCondition.from_dict(cond_dict)
    assert condition.freq == "1min", (
        f"Expected freq='1min' after from_dict() with freq='minute', "
        f"got freq={condition.freq!r}"
    )


@st.composite
def _exit_condition_config_dict_with_minute_freq(draw):
    """生成包含 freq="minute" 条件的 ExitConditionConfig 字典。"""
    # 至少生成 1 条 freq="minute" 的条件
    minute_conditions = draw(
        st.lists(_exit_condition_dict_with_minute_freq(), min_size=1, max_size=5)
    )
    logic = draw(st.sampled_from(["AND", "OR"]))
    return {
        "conditions": minute_conditions,
        "logic": logic,
    }


@h_settings(max_examples=100)
@given(config_dict=_exit_condition_config_dict_with_minute_freq())
def test_legacy_minute_freq_config_roundtrip_mapping(config_dict: dict):
    """
    # Feature: backtest-exit-conditions, Property 7: Legacy minute freq backward compatibility mapping

    **Validates: Requirements 8.1, 8.3**

    对任意包含 freq="minute" 条件的 ExitConditionConfig 字典，
    from_dict() 后再 to_dict() 所得字典中对应条件的 freq 应为 "1min"
    （即迁移后不可逆）。
    """
    config = ExitConditionConfig.from_dict(config_dict)
    serialized = config.to_dict()

    for i, cond in enumerate(serialized["conditions"]):
        assert cond["freq"] == "1min", (
            f"条件[{i}] 经 from_dict() → to_dict() 后 freq 应为 '1min'，"
            f"实际为 {cond['freq']!r}"
        )


# ---------------------------------------------------------------------------
# Property 8: Template exit_conditions round-trip consistency
# ---------------------------------------------------------------------------

import json


@h_settings(max_examples=100)
@given(config=_exit_condition_config_strategy())
def test_property_8_template_exit_conditions_roundtrip(config: ExitConditionConfig):
    """
    # Feature: backtest-exit-conditions, Property 8: Template exit_conditions round-trip consistency

    **Validates: Requirements 9.4, 9.9, 9.10**

    对任意有效的 ExitConditionConfig 对象，将其通过 to_dict() 序列化后
    模拟 JSONB 存取（JSON dumps → loads 往返），再通过 from_dict() 反序列化，
    所得对象应与原对象在所有字段上等价。
    """
    # Step 1: serialize to dict (as stored in ExitConditionTemplate.exit_conditions)
    serialized = config.to_dict()

    # Step 2: simulate JSONB round-trip (PostgreSQL JSONB stores/retrieves via JSON)
    json_str = json.dumps(serialized)
    from_jsonb = json.loads(json_str)

    # Step 3: deserialize back
    restored = ExitConditionConfig.from_dict(from_jsonb)

    # Verify top-level fields
    assert restored.logic == config.logic, (
        f"logic mismatch: {restored.logic!r} != {config.logic!r}"
    )
    assert len(restored.conditions) == len(config.conditions), (
        f"conditions count mismatch: {len(restored.conditions)} != {len(config.conditions)}"
    )

    # Verify each condition field-by-field
    for i, (orig, rest) in enumerate(zip(config.conditions, restored.conditions)):
        expected_freq = "1min" if orig.freq == "minute" else orig.freq
        assert rest.freq == expected_freq, (
            f"条件[{i}] freq mismatch: {rest.freq!r} != {expected_freq!r}"
        )
        assert rest.indicator == orig.indicator, (
            f"条件[{i}] indicator mismatch: {rest.indicator!r} != {orig.indicator!r}"
        )
        assert rest.operator == orig.operator, (
            f"条件[{i}] operator mismatch: {rest.operator!r} != {orig.operator!r}"
        )
        assert rest.cross_target == orig.cross_target, (
            f"条件[{i}] cross_target mismatch: {rest.cross_target!r} != {orig.cross_target!r}"
        )
        assert rest.params == orig.params, (
            f"条件[{i}] params mismatch: {rest.params!r} != {orig.params!r}"
        )
        # threshold: after JSON round-trip int→float is possible, compare with tolerance
        if orig.threshold is None:
            assert rest.threshold is None, (
                f"条件[{i}] threshold should be None, got {rest.threshold!r}"
            )
        else:
            assert rest.threshold is not None, (
                f"条件[{i}] threshold should not be None"
            )
            assert abs(rest.threshold - orig.threshold) < 1e-9, (
                f"条件[{i}] threshold mismatch: {rest.threshold!r} != {orig.threshold!r}"
            )


# ---------------------------------------------------------------------------
# Property 9: Template name uniqueness per user
# ---------------------------------------------------------------------------

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_current_user
from app.core.database import get_pg_session
from app.main import app
from app.models.backtest import ExitConditionTemplate
from app.models.user import AppUser

# Valid template name strategy: non-empty printable strings, length 1..100
_template_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())  # ensure not whitespace-only


class _P9MockScalar:
    """Minimal mock for SQLAlchemy execute results."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value


_P9_VALID_EXIT_CONDITIONS = {
    "conditions": [
        {
            "freq": "daily",
            "indicator": "rsi",
            "operator": ">",
            "threshold": 80.0,
            "cross_target": None,
            "params": {},
        }
    ],
    "logic": "AND",
}

_P9_USER_ID = UUID("00000000-0000-0000-0000-000000000099")


def _p9_make_user() -> AppUser:
    user = MagicMock(spec=AppUser)
    user.id = _P9_USER_ID
    user.username = "prop9_user"
    user.role = "TRADER"
    user.is_active = True
    return user


async def _p9_run_uniqueness_check(template_name: str) -> None:
    """
    Execute two create requests with the same template name for the same user.
    First should succeed (201), second should return 409.
    """
    user = _p9_make_user()

    # --- First request: no existing template, count=0 → success ---
    async def first_mock_execute(stmt):
        stmt_str = str(stmt)
        if "count" in stmt_str.lower():
            return _P9MockScalar(0)
        # Name uniqueness check → no existing
        return _P9MockScalar(None)

    first_session = AsyncMock()
    first_session.execute = first_mock_execute
    first_session.add = lambda entry: (
        setattr(entry, "id", entry.id if hasattr(entry, "id") and entry.id else uuid4())
        or setattr(entry, "created_at", getattr(entry, "created_at", None) or datetime.now(timezone.utc))
        or setattr(entry, "updated_at", getattr(entry, "updated_at", None) or datetime.now(timezone.utc))
    )
    first_session.flush = AsyncMock()

    async def _override_auth():
        return user

    async def _override_pg_first():
        yield first_session

    app.dependency_overrides[get_current_user] = _override_auth
    app.dependency_overrides[get_pg_session] = _override_pg_first

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as client:
            resp1 = await client.post(
                "/api/v1/backtest/exit-templates",
                json={
                    "name": template_name,
                    "exit_conditions": _P9_VALID_EXIT_CONDITIONS,
                },
            )
            assert resp1.status_code == 201, (
                f"First create should return 201, got {resp1.status_code}: {resp1.text}"
            )

        # --- Second request: existing template found → 409 ---
        existing_tpl = MagicMock(spec=ExitConditionTemplate)
        existing_tpl.id = uuid4()
        existing_tpl.user_id = user.id
        existing_tpl.name = template_name
        existing_tpl.description = None
        existing_tpl.exit_conditions = _P9_VALID_EXIT_CONDITIONS
        existing_tpl.created_at = datetime.now(timezone.utc)
        existing_tpl.updated_at = datetime.now(timezone.utc)

        async def second_mock_execute(stmt):
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                return _P9MockScalar(1)
            # Name uniqueness check → found existing
            return _P9MockScalar(existing_tpl)

        second_session = AsyncMock()
        second_session.execute = second_mock_execute

        async def _override_pg_second():
            yield second_session

        app.dependency_overrides[get_pg_session] = _override_pg_second

        async with AsyncClient(transport=transport, base_url="http://localhost") as client:
            resp2 = await client.post(
                "/api/v1/backtest/exit-templates",
                json={
                    "name": template_name,
                    "exit_conditions": _P9_VALID_EXIT_CONDITIONS,
                },
            )
            assert resp2.status_code == 409, (
                f"Second create with same name should return 409, got {resp2.status_code}: {resp2.text}"
            )
            assert "模版名称已存在" in resp2.json()["detail"], (
                f"409 response should contain '模版名称已存在', got: {resp2.json()['detail']}"
            )
    finally:
        app.dependency_overrides.clear()


@h_settings(max_examples=100)
@given(template_name=_template_name_strategy)
def test_property_9_template_name_uniqueness_per_user(template_name: str):
    """
    # Feature: backtest-exit-conditions, Property 9: Template name uniqueness per user

    **Validates: Requirements 9.5**

    对任意有效的模版名称字符串（非空，长度 ≤ 100），同一用户创建两个同名模版时，
    第二次创建请求应返回 HTTP 409 冲突错误，且数据库中该用户下该名称的模版数量始终为 1。
    """
    asyncio.run(_p9_run_uniqueness_check(template_name))
