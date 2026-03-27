"""
StockScreener 属性测试（Hypothesis）

**Validates: Requirements 3.1, 3.3, 3.4, 4.2, 4.3, 4.4, 4.5, 5.2, 5.3, 5.4,
             6.1, 6.3, 6.4, 6.6, 7.1, 7.2, 7.6**

属性 5：均线计算正确性
属性 6：趋势打分范围与阈值不变量
属性 7：技术指标信号生成正确性
属性 8：多因子逻辑运算正确性
属性 9：突破有效性判定
属性 10：量价资金筛选不变量
属性 11：资金信号生成正确性
属性 12：选股结果字段完整性
属性 13：策略模板数量上限与序列化 round-trip
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.ma_trend import calculate_ma, score_ma_trend
from app.services.screener.indicators import (
    calculate_macd,
    detect_macd_signal,
    calculate_rsi,
    detect_rsi_signal,
    calculate_boll,
    detect_boll_signal,
)
from app.services.screener.breakout import (
    BreakoutSignal,
    BreakoutType,
    validate_breakout,
    check_false_breakout,
)
from app.services.screener.volume_price import (
    check_turnover_rate,
    check_avg_daily_amount,
    check_money_flow_signal,
    check_large_order_signal,
)
from app.services.screener.strategy_engine import (
    StrategyEngine,
    StrategyTemplateManager,
    MAX_STRATEGIES_PER_USER,
)
from app.services.screener.screen_executor import ScreenExecutor
from app.core.schemas import (
    FactorCondition,
    StrategyConfig,
    RiskLevel,
    ScreenType,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 正浮点价格序列
_price_strategy = st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False)

_price_list_strategy = st.lists(
    _price_strategy,
    min_size=2,
    max_size=200,
)

# 较长价格序列（用于需要足够数据的指标）
_long_price_list_strategy = st.lists(
    _price_strategy,
    min_size=60,
    max_size=200,
)

# MA 周期
_ma_period_strategy = st.integers(min_value=1, max_value=60)


# ---------------------------------------------------------------------------
# 属性 5：均线计算正确性
# Feature: a-share-quant-trading-system, Property 5: 均线计算正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    closes=_price_list_strategy,
    period=_ma_period_strategy,
)
def test_ma_calculation_correctness(closes: list[float], period: int):
    """
    # Feature: a-share-quant-trading-system, Property 5: 均线计算正确性

    **Validates: Requirements 3.1**

    对任意价格序列和周期 N，第 t 日 N 日 MA 应等于
    closes[t-N+1:t+1] 的算术平均值，误差不超过 0.01%。
    """
    result = calculate_ma(closes, period)

    assert len(result) == len(closes), "MA 长度应与输入相同"

    n = len(closes)
    for t in range(n):
        if t < period - 1:
            # 数据不足时应为 NaN
            assert math.isnan(result[t]), f"MA[{t}] 应为 NaN（数据不足 {period} 天）"
        else:
            # 计算期望值：closes[t-N+1:t+1] 的算术平均
            window = closes[t - period + 1: t + 1]
            expected = sum(window) / period
            assert not math.isnan(result[t]), f"MA[{t}] 不应为 NaN"
            if expected != 0:
                rel_error = abs(result[t] - expected) / abs(expected)
                assert rel_error < 1e-4, (
                    f"MA[{t}] 误差超过 0.01%: 实际={result[t]:.6f}, "
                    f"期望={expected:.6f}, 相对误差={rel_error:.2e}"
                )
            else:
                assert abs(result[t] - expected) < 1e-10


# ---------------------------------------------------------------------------
# 属性 6：趋势打分范围与阈值不变量
# Feature: a-share-quant-trading-system, Property 6: 趋势打分范围与阈值不变量
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_price_list_strategy)
def test_trend_score_range_invariant(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 6: 趋势打分范围与阈值不变量

    **Validates: Requirements 3.3, 3.4**

    对任意股票价格序列，趋势打分应始终在 [0, 100] 范围内。
    """
    result = score_ma_trend(closes, [5, 10, 20])

    assert 0.0 <= result.score <= 100.0, (
        f"趋势打分 {result.score} 超出 [0, 100] 范围"
    )
    assert 0.0 <= result.alignment_score <= 100.0
    assert 0.0 <= result.slope_score <= 100.0
    assert 0.0 <= result.distance_score <= 100.0


# ---------------------------------------------------------------------------
# 属性 7：技术指标信号生成正确性
# Feature: a-share-quant-trading-system, Property 7: 技术指标信号生成正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(closes=_long_price_list_strategy)
def test_macd_signal_correctness(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 7: 技术指标信号生成正确性 (MACD)

    **Validates: Requirements 4.2**

    MACD 金叉信号仅当 DIF/DEA 均在零轴上方且 DIF 上穿 DEA 时生成。
    """
    result = detect_macd_signal(closes)
    n = len(result.dif)

    if n < 2:
        assert result.signal is False
        return

    last = n - 1
    prev = n - 2

    if result.signal:
        # 信号为 True 时，验证所有条件成立
        assert not math.isnan(result.dif[last])
        assert not math.isnan(result.dea[last])
        # 条件 1：DIF 和 DEA 均在零轴上方
        assert result.dif[last] > 0, "MACD 信号要求 DIF > 0"
        assert result.dea[last] > 0, "MACD 信号要求 DEA > 0"
        # 条件 2：DIF 上穿 DEA（金叉）
        assert result.dif[prev] <= result.dea[prev], "金叉要求前一日 DIF <= DEA"
        assert result.dif[last] > result.dea[last], "金叉要求当日 DIF > DEA"


@settings(max_examples=100)
@given(closes=_long_price_list_strategy)
def test_rsi_signal_correctness(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 7: 技术指标信号生成正确性 (RSI)

    **Validates: Requirements 4.4**

    RSI 强势信号仅当 RSI 在 [50, 80] 区间内时生成。
    """
    result = detect_rsi_signal(closes, period=14)
    n = len(result.values)

    if n < 15:
        assert result.signal is False
        return

    last = n - 1
    if result.signal:
        assert not math.isnan(result.values[last])
        assert 50.0 <= result.values[last] <= 80.0, (
            f"RSI 信号要求 RSI 在 [50, 80]，实际 RSI={result.values[last]:.2f}"
        )


@settings(max_examples=100)
@given(closes=_long_price_list_strategy)
def test_boll_signal_correctness(closes: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 7: 技术指标信号生成正确性 (BOLL)

    **Validates: Requirements 4.3**

    BOLL 突破信号仅当价格站稳中轨时生成。
    """
    result = detect_boll_signal(closes, period=20)
    n = len(closes)

    if n < 2:
        assert result.signal is False
        return

    last = n - 1
    if result.signal:
        assert not math.isnan(result.middle[last])
        # 条件 1：股价站稳中轨
        assert closes[last] > result.middle[last], (
            f"BOLL 信号要求价格 > 中轨，实际价格={closes[last]:.2f}，中轨={result.middle[last]:.2f}"
        )



# ---------------------------------------------------------------------------
# 属性 8：多因子逻辑运算正确性
# Feature: a-share-quant-trading-system, Property 8: 多因子逻辑运算正确性
# ---------------------------------------------------------------------------


@st.composite
def factor_and_stock_data_strategy(draw):
    """
    生成因子条件列表、逻辑运算符和对应的股票数据。
    """
    num_factors = draw(st.integers(min_value=1, max_value=5))
    factor_names = [f"factor_{i}" for i in range(num_factors)]
    logic = draw(st.sampled_from(["AND", "OR"]))

    factors = []
    stock_data: dict[str, Any] = {}
    weights: dict[str, float] = {}

    for name in factor_names:
        threshold = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        value = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        weight = draw(st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False))

        factors.append(FactorCondition(
            factor_name=name,
            operator=">=",
            threshold=threshold,
        ))
        stock_data[name] = value
        weights[name] = weight

    config = StrategyConfig(
        factors=factors,
        logic=logic,
        weights=weights,
    )
    return config, stock_data


@settings(max_examples=100)
@given(data=factor_and_stock_data_strategy())
def test_multi_factor_logic_correctness(data):
    """
    # Feature: a-share-quant-trading-system, Property 8: 多因子逻辑运算正确性

    **Validates: Requirements 4.5, 7.1**

    AND 模式：所有因子条件都必须满足。
    OR 模式：至少一个因子条件满足。
    """
    config, stock_data = data

    result = StrategyEngine.evaluate(config, stock_data)

    # 独立计算每个因子是否通过
    individual_results = []
    for factor in config.factors:
        value = stock_data.get(factor.factor_name)
        if value is not None and factor.threshold is not None:
            passed = value >= factor.threshold
        else:
            passed = False
        individual_results.append(passed)

    if config.logic == "AND":
        expected_passed = all(individual_results)
    else:  # OR
        expected_passed = any(individual_results)

    assert result.passed == expected_passed, (
        f"逻辑运算不一致：logic={config.logic}, "
        f"各因子结果={individual_results}, "
        f"期望={expected_passed}, 实际={result.passed}"
    )
    assert result.logic == config.logic


# ---------------------------------------------------------------------------
# 属性 9：突破有效性判定
# Feature: a-share-quant-trading-system, Property 9: 突破有效性判定
# ---------------------------------------------------------------------------


@st.composite
def breakout_signal_strategy(draw):
    """生成一个 BreakoutSignal 用于测试。"""
    resistance = draw(st.floats(min_value=5.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    close_price = draw(st.floats(
        min_value=resistance * 1.001, max_value=resistance * 1.5,
        allow_nan=False, allow_infinity=False,
    ))
    avg_volume = draw(st.floats(min_value=100.0, max_value=1e8, allow_nan=False, allow_infinity=False))
    volume_ratio = draw(st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False))
    volume = int(avg_volume * volume_ratio)

    return BreakoutSignal(
        breakout_type=draw(st.sampled_from(list(BreakoutType))),
        resistance_level=resistance,
        close_price=close_price,
        volume=volume,
        avg_volume_20d=avg_volume,
        volume_ratio=volume_ratio,
        is_valid=False,
        is_false_breakout=False,
        generates_buy_signal=False,
    )


@settings(max_examples=100)
@given(signal=breakout_signal_strategy())
def test_breakout_validity(signal: BreakoutSignal):
    """
    # Feature: a-share-quant-trading-system, Property 9: 突破有效性判定

    **Validates: Requirements 5.2, 5.4**

    有效突破要求成交量 >= 1.5 倍均量；
    无量突破不生成买入信号。
    """
    validated = validate_breakout(signal, volume_multiplier=1.5)

    if validated.volume_ratio >= 1.5:
        assert validated.is_valid is True, "成交量达标应判定为有效突破"
        assert validated.generates_buy_signal is True, "有效突破应生成买入信号"
    else:
        assert validated.is_valid is False, "成交量不足应判定为无效突破"
        assert validated.generates_buy_signal is False, "无量突破不应生成买入信号"


@settings(max_examples=100)
@given(
    signal=breakout_signal_strategy(),
    next_day_close_factor=st.floats(min_value=0.8, max_value=1.2, allow_nan=False, allow_infinity=False),
)
def test_false_breakout_detection(signal: BreakoutSignal, next_day_close_factor: float):
    """
    # Feature: a-share-quant-trading-system, Property 9: 突破有效性判定（假突破）

    **Validates: Requirements 5.3**

    突破后次日收盘价 < 压力位 → 假突破，撤销买入信号。
    """
    # 先 validate 使 is_valid 正确
    validated = validate_breakout(signal, volume_multiplier=1.5)
    next_day_close = validated.resistance_level * next_day_close_factor

    result = check_false_breakout(validated, next_day_close)

    if next_day_close < validated.resistance_level:
        assert result.is_false_breakout is True, "次日收盘价 < 压力位应标记为假突破"
        assert result.generates_buy_signal is False, "假突破不应生成买入信号"
    else:
        assert result.is_false_breakout is False, "次日收盘价 >= 压力位不应标记为假突破"


# ---------------------------------------------------------------------------
# 属性 10：量价资金筛选不变量
# Feature: a-share-quant-trading-system, Property 10: 量价资金筛选不变量
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    turnover_rate=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_turnover_rate_screening_invariant(turnover_rate: float):
    """
    # Feature: a-share-quant-trading-system, Property 10: 量价资金筛选不变量（换手率）

    **Validates: Requirements 6.1**

    换手率在 [3%, 15%] 区间内通过筛选。
    """
    result = check_turnover_rate(turnover_rate)

    if 3.0 <= turnover_rate <= 15.0:
        assert result.passed is True, (
            f"换手率 {turnover_rate}% 在 [3, 15] 区间内应通过"
        )
    else:
        assert result.passed is False, (
            f"换手率 {turnover_rate}% 不在 [3, 15] 区间内应不通过"
        )


@settings(max_examples=100)
@given(
    amounts=st.lists(
        st.floats(min_value=0.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=40,
    ),
)
def test_avg_daily_amount_screening_invariant(amounts: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 10: 量价资金筛选不变量（日均成交额）

    **Validates: Requirements 6.6**

    近 20 日日均成交额 >= 5000 万通过筛选。
    """
    result = check_avg_daily_amount(amounts, period=20, threshold=5000.0)

    # 手动计算期望值
    window = amounts[-20:] if len(amounts) >= 20 else amounts
    expected_avg = sum(window) / len(window)

    if expected_avg >= 5000.0:
        assert result.passed is True
    else:
        assert result.passed is False

    assert abs(result.avg_daily_amount - expected_avg) < 1e-6


# ---------------------------------------------------------------------------
# 属性 11：资金信号生成正确性
# Feature: a-share-quant-trading-system, Property 11: 资金信号生成正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    daily_inflows=st.lists(
        st.floats(min_value=-5000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    ),
)
def test_money_flow_signal_correctness(daily_inflows: list[float]):
    """
    # Feature: a-share-quant-trading-system, Property 11: 资金信号生成正确性（主力资金）

    **Validates: Requirements 6.3**

    信号仅当主力资金净流入 >= 1000 万且连续 2 日时生成。
    """
    result = check_money_flow_signal(daily_inflows, threshold=1000.0, consecutive=2)

    # 手动计算从末尾向前连续满足条件的天数
    count = 0
    for i in range(len(daily_inflows) - 1, -1, -1):
        if daily_inflows[i] >= 1000.0:
            count += 1
        else:
            break

    expected_signal = count >= 2

    assert result.signal == expected_signal, (
        f"资金信号不一致：连续天数={count}, 期望={expected_signal}, 实际={result.signal}"
    )
    assert result.consecutive_days == count


@settings(max_examples=100)
@given(
    ratio=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_large_order_signal_correctness(ratio: float):
    """
    # Feature: a-share-quant-trading-system, Property 11: 资金信号生成正确性（大单占比）

    **Validates: Requirements 6.4**

    大单成交占比 > 30% 时生成信号。
    """
    result = check_large_order_signal(ratio, threshold=30.0)

    if ratio > 30.0:
        assert result.signal is True, f"大单占比 {ratio}% > 30% 应生成信号"
    else:
        assert result.signal is False, f"大单占比 {ratio}% <= 30% 不应生成信号"



# ---------------------------------------------------------------------------
# 属性 12：选股结果字段完整性
# Feature: a-share-quant-trading-system, Property 12: 选股结果字段完整性
# ---------------------------------------------------------------------------


@st.composite
def screen_stocks_data_strategy(draw):
    """生成用于选股执行的股票数据和策略配置。"""
    num_stocks = draw(st.integers(min_value=1, max_value=10))
    factor_name = "ma_trend"
    threshold = draw(st.floats(min_value=10.0, max_value=90.0, allow_nan=False, allow_infinity=False))

    config = StrategyConfig(
        factors=[FactorCondition(factor_name=factor_name, operator=">=", threshold=threshold)],
        logic="AND",
        weights={factor_name: 1.0},
    )

    stocks_data: dict[str, dict[str, Any]] = {}
    for i in range(num_stocks):
        symbol = f"{600000 + i:06d}.SH"
        value = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        close = draw(st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False))
        stocks_data[symbol] = {
            factor_name: value,
            "close": close,
        }

    return config, stocks_data


@settings(max_examples=100)
@given(data=screen_stocks_data_strategy())
def test_screen_result_field_completeness(data):
    """
    # Feature: a-share-quant-trading-system, Property 12: 选股结果字段完整性

    **Validates: Requirements 7.6**

    每条选股结果应包含非空 symbol、有效 ref_buy_price、
    trend_score 在 [0, 100]、有效 risk_level。
    """
    config, stocks_data = data

    executor = ScreenExecutor(config)
    result = executor.run_eod_screen(stocks_data)

    for item in result.items:
        # symbol 非空
        assert item.symbol is not None and len(item.symbol) > 0, (
            "选股结果 symbol 不应为空"
        )
        # ref_buy_price 有效（>= 0）
        assert isinstance(item.ref_buy_price, Decimal), (
            f"ref_buy_price 应为 Decimal，实际类型={type(item.ref_buy_price)}"
        )
        assert item.ref_buy_price >= 0, (
            f"ref_buy_price 应 >= 0，实际={item.ref_buy_price}"
        )
        # trend_score 在 [0, 100]
        assert 0.0 <= item.trend_score <= 100.0, (
            f"trend_score 应在 [0, 100]，实际={item.trend_score}"
        )
        # risk_level 有效
        assert item.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH), (
            f"risk_level 应为有效枚举值，实际={item.risk_level}"
        )


# ---------------------------------------------------------------------------
# 属性 13：策略模板数量上限与序列化 round-trip
# Feature: a-share-quant-trading-system, Property 13: 策略模板数量上限与序列化 round-trip
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    num_strategies=st.integers(min_value=1, max_value=25),
)
def test_strategy_template_count_limit(num_strategies: int):
    """
    # Feature: a-share-quant-trading-system, Property 13: 策略模板数量上限

    **Validates: Requirements 7.2**

    单用户策略模板数量不应超过 20 套。
    """
    manager = StrategyTemplateManager()
    user_id = "test_user"

    created = 0
    for i in range(num_strategies):
        config = StrategyConfig(
            factors=[FactorCondition(factor_name=f"factor_{i}", operator=">=", threshold=50.0)],
            logic="AND",
        )
        if created < MAX_STRATEGIES_PER_USER:
            template = manager.create(user_id, f"策略_{i}", config)
            created += 1
            assert manager.count(user_id) == created
        else:
            with pytest.raises(ValueError):
                manager.create(user_id, f"策略_{i}", config)

    assert manager.count(user_id) <= MAX_STRATEGIES_PER_USER, (
        f"策略数量 {manager.count(user_id)} 超过上限 {MAX_STRATEGIES_PER_USER}"
    )


@st.composite
def strategy_config_strategy(draw):
    """生成随机 StrategyConfig 用于序列化 round-trip 测试。"""
    num_factors = draw(st.integers(min_value=0, max_value=5))
    factors = []
    weights: dict[str, float] = {}

    for i in range(num_factors):
        name = f"factor_{i}"
        operator = draw(st.sampled_from([">", "<", ">=", "<=", "=="]))
        threshold = draw(st.one_of(
            st.none(),
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        ))
        factors.append(FactorCondition(
            factor_name=name,
            operator=operator,
            threshold=threshold,
            params={},
        ))
        weights[name] = draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))

    logic = draw(st.sampled_from(["AND", "OR"]))
    ma_periods = draw(st.lists(
        st.integers(min_value=1, max_value=250),
        min_size=1,
        max_size=6,
    ))

    return StrategyConfig(
        factors=factors,
        logic=logic,
        weights=weights,
        ma_periods=ma_periods,
        indicator_params={},
    )


@settings(max_examples=100)
@given(config=strategy_config_strategy())
def test_strategy_serialization_round_trip(config: StrategyConfig):
    """
    # Feature: a-share-quant-trading-system, Property 13: 序列化 round-trip

    **Validates: Requirements 7.2**

    StrategyConfig 序列化为 dict 后再反序列化，应得到等价对象。
    """
    serialized = config.to_dict()
    deserialized = StrategyConfig.from_dict(serialized)

    # 验证因子条件
    assert len(deserialized.factors) == len(config.factors)
    for orig, restored in zip(config.factors, deserialized.factors):
        assert restored.factor_name == orig.factor_name
        assert restored.operator == orig.operator
        assert restored.threshold == orig.threshold
        assert restored.params == orig.params

    # 验证逻辑运算符
    assert deserialized.logic == config.logic

    # 验证权重
    assert deserialized.weights == config.weights

    # 验证均线周期
    assert deserialized.ma_periods == config.ma_periods

    # 验证指标参数
    assert deserialized.indicator_params == config.indicator_params
