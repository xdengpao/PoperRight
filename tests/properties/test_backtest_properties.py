"""
BacktestEngine 属性测试（Hypothesis）

**Validates: Requirements 12.1, 12.2, 12.5, 13.3, 13.4**

属性 20：回测 T+1 规则不变量
属性 21：回测绩效指标完整性
属性 22：回测手续费计算正确性
属性 23：数据集划分比例测试
属性 24：过拟合检测正确性测试
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.backtest_engine import BacktestEngine
from app.services.param_optimizer import DataSplitter, OverfitDetector
from app.core.schemas import BacktestConfig, BacktestResult, StrategyConfig


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

_symbol = st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True)

_price = st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False)

_quantity = st.integers(min_value=100, max_value=10000)

_commission_rate = st.floats(
    min_value=0.0001, max_value=0.01, allow_nan=False, allow_infinity=False,
)

_slippage_rate = st.floats(
    min_value=0.0001, max_value=0.01, allow_nan=False, allow_infinity=False,
)


def _default_config(**overrides) -> BacktestConfig:
    kwargs = dict(
        strategy_config=StrategyConfig(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("10000000"),
        commission_buy=Decimal("0.0003"),
        commission_sell=Decimal("0.0013"),
        slippage=Decimal("0.001"),
    )
    kwargs.update(overrides)
    return BacktestConfig(**kwargs)


@st.composite
def buy_sell_signal_pairs(draw):
    """
    生成随机的买卖信号对列表。
    每对包含一个 BUY 和一个 SELL（SELL 日期严格晚于 BUY）。
    可能包含同日买卖尝试（用于验证 T+1 过滤）。
    """
    n_pairs = draw(st.integers(min_value=1, max_value=5))
    signals = []
    base_date = date(2024, 1, 2)

    for i in range(n_pairs):
        symbol = draw(_symbol)
        buy_price = draw(_price)
        sell_price = draw(_price)
        qty = draw(st.integers(min_value=100, max_value=500))

        buy_day_offset = i * 10
        # 卖出日期偏移：0 表示同日（T+1 应阻止），>=1 表示次日或更晚
        sell_day_gap = draw(st.integers(min_value=0, max_value=5))

        buy_date = base_date + timedelta(days=buy_day_offset)
        sell_date = buy_date + timedelta(days=sell_day_gap)

        signals.append({
            "date": buy_date,
            "symbol": symbol,
            "action": "BUY",
            "price": buy_price,
            "quantity": qty,
        })
        signals.append({
            "date": sell_date,
            "symbol": symbol,
            "action": "SELL",
            "price": sell_price,
            "quantity": qty,
        })

    return signals



# ---------------------------------------------------------------------------
# 属性 20：回测 T+1 规则不变量
# Feature: a-share-quant-trading-system, Property 20: 回测 T+1 规则不变量
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(signals=buy_sell_signal_pairs())
def test_t1_rule_invariant(signals):
    """
    # Feature: a-share-quant-trading-system, Property 20: 回测 T+1 规则不变量

    **Validates: Requirements 12.5**

    对任意回测结果的交易记录，不应存在同一标的在同一交易日
    既有买入成交又有卖出成交的记录（严格遵守 A 股 T+1 规则）。
    """
    engine = BacktestEngine()
    config = _default_config()
    result = engine.run_backtest(config, signals)

    # 检查交易记录中不存在同一标的同日买卖
    for tr in result.trade_records:
        same_day_opposite = [
            r for r in result.trade_records
            if r["date"] == tr["date"]
            and r["symbol"] == tr["symbol"]
            and r["action"] != tr["action"]
        ]
        assert len(same_day_opposite) == 0, (
            f"T+1 违规：{tr['symbol']} 在 {tr['date']} 同日存在买入和卖出"
        )


# ---------------------------------------------------------------------------
# 属性 21：回测绩效指标完整性
# Feature: a-share-quant-trading-system, Property 21: 回测绩效指标完整性
# ---------------------------------------------------------------------------


@st.composite
def complete_backtest_signals(draw):
    """生成至少包含一对完整买卖的信号列表"""
    n_pairs = draw(st.integers(min_value=1, max_value=3))
    signals = []
    base_date = date(2024, 1, 2)

    for i in range(n_pairs):
        symbol = draw(_symbol)
        buy_price = draw(_price)
        sell_price = draw(_price)
        qty = draw(st.integers(min_value=100, max_value=500))

        buy_date = base_date + timedelta(days=i * 10)
        sell_date = buy_date + timedelta(days=draw(st.integers(min_value=1, max_value=5)))

        signals.append({
            "date": buy_date,
            "symbol": symbol,
            "action": "BUY",
            "price": buy_price,
            "quantity": qty,
        })
        signals.append({
            "date": sell_date,
            "symbol": symbol,
            "action": "SELL",
            "price": sell_price,
            "quantity": qty,
        })

    return signals


@settings(max_examples=100)
@given(signals=complete_backtest_signals())
def test_backtest_metrics_completeness(signals):
    """
    # Feature: a-share-quant-trading-system, Property 21: 回测绩效指标完整性

    **Validates: Requirements 12.2**

    对任意完成的回测任务，其结果应包含全部 9 项绩效指标，
    且所有指标值应在数学上合理的范围内：
    - win_rate in [0, 1]
    - max_drawdown in [0, 1]
    - total_trades >= 0
    - avg_holding_days >= 0
    """
    engine = BacktestEngine()
    config = _default_config()
    result = engine.run_backtest(config, signals)

    # 9 项指标全部存在
    assert hasattr(result, "annual_return")
    assert hasattr(result, "total_return")
    assert hasattr(result, "win_rate")
    assert hasattr(result, "profit_loss_ratio")
    assert hasattr(result, "max_drawdown")
    assert hasattr(result, "sharpe_ratio")
    assert hasattr(result, "calmar_ratio")
    assert hasattr(result, "total_trades")
    assert hasattr(result, "avg_holding_days")

    # 值域合理性
    assert 0.0 <= result.win_rate <= 1.0, (
        f"胜率 {result.win_rate} 不在 [0, 1] 范围内"
    )
    assert 0.0 <= result.max_drawdown <= 1.0, (
        f"最大回撤 {result.max_drawdown} 不在 [0, 1] 范围内"
    )
    assert result.total_trades >= 0, (
        f"总交易次数 {result.total_trades} < 0"
    )
    assert result.avg_holding_days >= 0, (
        f"平均持仓天数 {result.avg_holding_days} < 0"
    )


# ---------------------------------------------------------------------------
# 属性 22：回测手续费计算正确性
# Feature: a-share-quant-trading-system, Property 22: 回测手续费计算正确性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    price=st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    quantity=st.integers(min_value=100, max_value=10000),
    commission_buy=_commission_rate,
    commission_sell=_commission_rate,
    slippage=_slippage_rate,
)
def test_commission_calculation_correctness(
    price: float,
    quantity: int,
    commission_buy: float,
    commission_sell: float,
    slippage: float,
):
    """
    # Feature: a-share-quant-trading-system, Property 22: 回测手续费计算正确性

    **Validates: Requirements 12.1**

    对任意回测配置中的手续费率和滑点参数：
    - buy_cost = amount * commission_buy + amount * slippage
    - sell_cost = amount * commission_sell + amount * slippage
    误差不超过 0.01%。
    """
    config = _default_config(
        commission_buy=Decimal(str(commission_buy)),
        commission_sell=Decimal(str(commission_sell)),
        slippage=Decimal(str(slippage)),
    )
    dec_price = Decimal(str(price))

    # 买入成本验证
    actual_buy_cost = BacktestEngine._calc_buy_cost(dec_price, quantity, config)
    amount = dec_price * quantity
    expected_buy_cost = amount * Decimal(str(commission_buy)) + amount * Decimal(str(slippage))

    if expected_buy_cost > 0:
        buy_error = abs(float(actual_buy_cost - expected_buy_cost)) / float(expected_buy_cost)
        assert buy_error < 0.0001, (
            f"买入成本误差 {buy_error:.6f} 超过 0.01%，"
            f"实际={actual_buy_cost}，期望={expected_buy_cost}"
        )
    else:
        assert actual_buy_cost == expected_buy_cost

    # 卖出成本验证
    actual_sell_cost = BacktestEngine._calc_sell_cost(dec_price, quantity, config)
    expected_sell_cost = amount * Decimal(str(commission_sell)) + amount * Decimal(str(slippage))

    if expected_sell_cost > 0:
        sell_error = abs(float(actual_sell_cost - expected_sell_cost)) / float(expected_sell_cost)
        assert sell_error < 0.0001, (
            f"卖出成本误差 {sell_error:.6f} 超过 0.01%，"
            f"实际={actual_sell_cost}，期望={expected_sell_cost}"
        )
    else:
        assert actual_sell_cost == expected_sell_cost


# ---------------------------------------------------------------------------
# 属性 23：数据集划分比例测试
# Feature: a-share-quant-trading-system, Property 23: 数据集划分比例测试
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    n=st.integers(min_value=2, max_value=500),
)
def test_data_split_ratio(n: int):
    """
    # Feature: a-share-quant-trading-system, Property 23: 数据集划分比例测试

    **Validates: Requirements 13.3**

    对任意历史数据集，按时间顺序划分后：
    - 训练集 = 前 70% 的数据
    - 测试集 = 后 30% 的数据
    - 两个数据集不应有时间重叠
    - 训练集 + 测试集 = 原始数据
    """
    # 生成按时间升序排列的数据
    base_date = date(2020, 1, 1)
    data = [base_date + timedelta(days=i) for i in range(n)]

    train, test = DataSplitter.split_train_test(data, train_ratio=0.7)

    # 属性 23a：训练集 + 测试集 = 原始数据
    assert train + test == data, "训练集 + 测试集应等于原始数据"

    # 属性 23b：无重叠
    assert set(train).isdisjoint(set(test)), "训练集和测试集不应有重叠"

    # 属性 23c：训练集是前面的，测试集是后面的（时间顺序）
    if train and test:
        assert train[-1] < test[0], "训练集最后一条应早于测试集第一条"

    # 属性 23d：训练集约占 70%（允许取整误差 ±1）
    expected_train_len = int(n * 0.7)
    # DataSplitter 有边界保护：至少各 1 条
    assert abs(len(train) - expected_train_len) <= 1, (
        f"训练集长度 {len(train)} 与期望 {expected_train_len} 偏差过大"
    )


# ---------------------------------------------------------------------------
# 属性 24：过拟合检测正确性测试
# Feature: a-share-quant-trading-system, Property 24: 过拟合检测正确性测试
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    train_return=st.floats(min_value=-0.99, max_value=5.0, allow_nan=False, allow_infinity=False),
    test_return=st.floats(min_value=-0.99, max_value=5.0, allow_nan=False, allow_infinity=False),
)
def test_overfit_detection_correctness(train_return: float, test_return: float):
    """
    # Feature: a-share-quant-trading-system, Property 24: 过拟合检测正确性测试

    **Validates: Requirements 13.4**

    对任意训练集和测试集的回测结果：
    - 当 train_return != 0 时：
      overfit iff |test_return - train_return| / |train_return| > 0.20
    - 当 train_return == 0 时：
      overfit iff |test_return| > 0.20
    """
    is_overfit, deviation = OverfitDetector.detect(train_return, test_return, threshold=0.20)

    if train_return == 0.0:
        expected_deviation = abs(test_return)
        expected_overfit = expected_deviation > 0.20
    else:
        expected_deviation = abs(test_return - train_return) / abs(train_return)
        expected_overfit = expected_deviation > 0.20

    assert is_overfit == expected_overfit, (
        f"过拟合判定错误：train={train_return}, test={test_return}, "
        f"deviation={deviation:.4f}, expected_overfit={expected_overfit}, "
        f"actual_overfit={is_overfit}"
    )

    # 偏差值应与预期一致（浮点误差容忍）
    assert abs(deviation - expected_deviation) < 1e-9, (
        f"偏差值不一致：expected={expected_deviation:.6f}, actual={deviation:.6f}"
    )
