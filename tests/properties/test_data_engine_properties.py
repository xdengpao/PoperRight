"""
DataEngine 属性测试（Hypothesis）

**Validates: Requirements 2.1, 2.2, 2.3, 2.5, 2.6**

属性 1：数据清洗过滤不变量
属性 2：复权处理连续性不变量
属性 3：缺失值插值完整性
属性 4：归一化范围不变量
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.data_engine.stock_filter import (
    AdjustmentCalculator,
    ExRightsRecord,
    FundamentalsSnapshot,
    StockBasicInfo,
    StockFilter,
    interpolate_missing,
    normalize_minmax,
    normalize_zscore,
    REASON_ST,
    REASON_DELISTED,
    REASON_SUSPENDED,
    REASON_NEW_STOCK,
    REASON_HIGH_PLEDGE,
    REASON_PROFIT_LOSS,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 股票代码策略：6位数字 + 交易所后缀
_symbol_strategy = st.builds(
    lambda code, suffix: f"{code:06d}.{suffix}",
    code=st.integers(min_value=1, max_value=999999),
    suffix=st.sampled_from(["SZ", "SH", "BJ"]),
)

# 正常股票（不应被任何规则剔除）
@st.composite
def normal_stock_strategy(draw) -> StockBasicInfo:
    symbol = draw(_symbol_strategy)
    return StockBasicInfo(
        symbol=symbol,
        is_st=False,
        is_delisted=False,
        is_suspended=False,
        list_date=date(2020, 1, 1),
        trading_days_since_ipo=draw(st.integers(min_value=20, max_value=2000)),
    )


@st.composite
def normal_fundamentals_strategy(draw, symbol: str = "000001.SZ") -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol,
        pledge_ratio=Decimal(str(draw(st.floats(min_value=0.0, max_value=70.0, allow_nan=False)))),
        net_profit_yoy=Decimal(str(draw(st.floats(min_value=-50.0, max_value=500.0, allow_nan=False)))),
    )


# 应被剔除的股票（各种剔除原因）
@st.composite
def excluded_stock_strategy(draw) -> tuple[StockBasicInfo, FundamentalsSnapshot | None, str]:
    """生成一只应被剔除的股票，返回 (stock_info, fundamentals, expected_reason)"""
    reason = draw(st.sampled_from([
        REASON_ST, REASON_DELISTED, REASON_SUSPENDED,
        REASON_NEW_STOCK, REASON_HIGH_PLEDGE, REASON_PROFIT_LOSS,
    ]))
    symbol = draw(_symbol_strategy)

    stock = StockBasicInfo(
        symbol=symbol,
        is_st=False,
        is_delisted=False,
        is_suspended=False,
        list_date=date(2020, 1, 1),
        trading_days_since_ipo=500,
    )
    fund: FundamentalsSnapshot | None = None

    if reason == REASON_ST:
        stock.is_st = True
    elif reason == REASON_DELISTED:
        stock.is_delisted = True
    elif reason == REASON_SUSPENDED:
        stock.is_suspended = True
    elif reason == REASON_NEW_STOCK:
        stock.trading_days_since_ipo = draw(st.integers(min_value=0, max_value=19))
    elif reason == REASON_HIGH_PLEDGE:
        pledge = draw(st.floats(min_value=70.01, max_value=100.0, allow_nan=False))
        fund = FundamentalsSnapshot(
            symbol=symbol,
            pledge_ratio=Decimal(str(round(pledge, 2))),
            net_profit_yoy=Decimal("10"),
        )
    elif reason == REASON_PROFIT_LOSS:
        loss = draw(st.floats(min_value=-500.0, max_value=-50.01, allow_nan=False))
        fund = FundamentalsSnapshot(
            symbol=symbol,
            pledge_ratio=Decimal("30"),
            net_profit_yoy=Decimal(str(round(loss, 2))),
        )

    return stock, fund, reason


# ---------------------------------------------------------------------------
# 属性 1：数据清洗过滤不变量
# Feature: a-share-quant-trading-system, Property 1: 数据清洗过滤不变量
# ---------------------------------------------------------------------------

_EXCLUDED_REASONS = {
    REASON_ST, REASON_DELISTED, REASON_SUSPENDED,
    REASON_NEW_STOCK, REASON_HIGH_PLEDGE, REASON_PROFIT_LOSS,
}

_REF_DATE = date(2024, 6, 1)


@settings(max_examples=100)
@given(excluded=excluded_stock_strategy())
def test_data_cleaning_invariant_excluded_stocks(excluded):
    """
    # Feature: a-share-quant-trading-system, Property 1: 数据清洗过滤不变量

    **Validates: Requirements 2.1, 2.6**

    对任意应被剔除的股票，StockFilter.is_excluded 应返回 True，
    且原因应在已知剔除原因集合中。
    """
    stock_info, fundamentals, expected_reason = excluded
    sf = StockFilter()
    is_excl, reason = sf.is_excluded(stock_info, fundamentals, _REF_DATE)

    assert is_excl is True, (
        f"股票 {stock_info.symbol} 应被剔除（原因：{expected_reason}），但未被剔除"
    )
    assert reason in _EXCLUDED_REASONS, (
        f"剔除原因 '{reason}' 不在已知原因集合中"
    )


@settings(max_examples=100)
@given(stock=normal_stock_strategy(), fund=normal_fundamentals_strategy())
def test_data_cleaning_invariant_normal_stocks(stock, fund):
    """
    # Feature: a-share-quant-trading-system, Property 1: 数据清洗过滤不变量

    **Validates: Requirements 2.1**

    对任意正常股票（无 ST/退市/停牌/次新/高质押/业绩暴雷），
    StockFilter.is_excluded 应返回 False。
    """
    # 确保基本面数据的 symbol 与股票一致（不影响过滤逻辑）
    fund.symbol = stock.symbol
    sf = StockFilter()
    is_excl, reason = sf.is_excluded(stock, fund, _REF_DATE)

    assert is_excl is False, (
        f"正常股票 {stock.symbol} 不应被剔除，但被剔除，原因：{reason}"
    )
    assert reason == "", f"正常股票剔除原因应为空，实际：{reason}"


# ---------------------------------------------------------------------------
# 属性 2：复权处理连续性不变量
# Feature: a-share-quant-trading-system, Property 2: 复权处理连续性不变量
# ---------------------------------------------------------------------------

@st.composite
def ex_rights_sequence_strategy(draw):
    """
    生成一段含除权事件的 K 线序列。
    返回 (bars_before, bars_after, ex_record, adj_factors)
    """
    # 除权日
    ex_date = date(2024, 3, 15)
    # 除权前最后一天
    day_before = ex_date - timedelta(days=1)
    # 除权日当天
    day_of = ex_date

    # 除权前收盘价
    close_before = Decimal(str(draw(st.floats(
        min_value=5.0, max_value=200.0, allow_nan=False, allow_infinity=False
    ))))
    # 送股比例（每股送 N 股）
    stock_div = Decimal(str(draw(st.floats(
        min_value=0.05, max_value=0.5, allow_nan=False
    ))))
    # 除权后开盘价（理论上 = 除权前收盘价 / (1 + 送股比例)）
    open_after = close_before / (Decimal("1") + stock_div)

    bars = [
        {"date": day_before, "open": close_before * Decimal("0.99"),
         "high": close_before * Decimal("1.01"), "low": close_before * Decimal("0.98"),
         "close": close_before, "volume": 100000},
        {"date": day_of, "open": open_after,
         "high": open_after * Decimal("1.02"), "low": open_after * Decimal("0.98"),
         "close": open_after * Decimal("1.01"), "volume": 120000},
    ]

    ex_record = ExRightsRecord(
        ex_date=ex_date,
        cash_dividend=Decimal("0"),
        stock_dividend=stock_div,
        allotment_ratio=Decimal("0"),
        allotment_price=Decimal("0"),
    )

    adj_factors = AdjustmentCalculator.calc_adj_factor(
        [day_before, day_of], [ex_record]
    )

    return bars, ex_record, adj_factors


@settings(max_examples=100)
@given(data=ex_rights_sequence_strategy())
def test_adj_continuity(data):
    """
    # Feature: a-share-quant-trading-system, Property 2: 复权处理连续性不变量

    **Validates: Requirements 2.2**

    前复权模式下，除权日前后价格序列应保持连续：
    除权日前一日的前复权收盘价，应等于除权日当日前复权开盘价乘以相应复权因子的比值，
    即两者之间不应因除权产生价格跳空。

    验证：前复权后，除权日前一日收盘价 ≈ 除权日当日开盘价（连续性）
    """
    bars, ex_record, adj_factors = data

    fwd_bars = AdjustmentCalculator.apply_forward_adj(bars, adj_factors)

    close_before_adj = fwd_bars[0]["close"]
    open_after_adj = fwd_bars[1]["open"]

    # 前复权后，除权日前一日收盘价与除权日开盘价之比
    # 应接近原始价格之比（即连续性：前复权消除了价格跳空）
    # 原始：close_before / open_after = (1 + stock_div)（除权跳空）
    # 前复权后：两者应接近（比值接近 1）
    ratio = float(close_before_adj) / float(open_after_adj)

    # 前复权后，除权日前后价格比值应接近 1（连续性），允许 1% 误差
    assert abs(ratio - 1.0) < 0.01, (
        f"前复权后价格不连续：除权前收盘={close_before_adj:.4f}，"
        f"除权后开盘={open_after_adj:.4f}，比值={ratio:.4f}"
    )


# ---------------------------------------------------------------------------
# 属性 3：缺失值插值完整性
# Feature: a-share-quant-trading-system, Property 3: 缺失值插值完整性
# ---------------------------------------------------------------------------

@st.composite
def values_with_missing_strategy(draw):
    """生成含缺失值的浮点数序列（至少有一个有效值）"""
    n = draw(st.integers(min_value=2, max_value=50))
    # 生成原始值
    raw = draw(st.lists(
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=n, max_size=n,
    ))
    # 随机将部分值设为 None（保留至少一个有效值）
    mask = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    values = [v if keep else None for v, keep in zip(raw, mask)]
    # 确保至少有一个非 None
    if all(v is None for v in values):
        idx = draw(st.integers(min_value=0, max_value=n - 1))
        values[idx] = raw[idx]
    return values


@settings(max_examples=100)
@given(values=values_with_missing_strategy())
def test_interpolation_completeness(values):
    """
    # Feature: a-share-quant-trading-system, Property 3: 缺失值插值完整性

    **Validates: Requirements 2.3**

    线性插值后：
    1. 结果序列中不应存在缺失值（None）
    2. 所有插值点的数值应在其相邻两个有效数据点的线性范围内
       即 min(left, right) ≤ interpolated ≤ max(left, right)
    """
    result = interpolate_missing(values)

    # 属性 3a：结果长度与输入相同
    assert len(result) == len(values), "插值后长度应与输入相同"

    # 属性 3b：结果中不含 None
    assert all(v is not None for v in result), "插值后不应存在缺失值"

    # 属性 3c：插值点在相邻有效值的线性范围内
    valid_indices = [i for i, v in enumerate(values) if v is not None]
    if len(valid_indices) < 2:
        return  # 只有一个有效值，无法验证插值范围

    for seg_idx in range(len(valid_indices) - 1):
        left_pos = valid_indices[seg_idx]
        right_pos = valid_indices[seg_idx + 1]

        if right_pos - left_pos <= 1:
            continue  # 相邻，无插值点

        left_val = float(values[left_pos])
        right_val = float(values[right_pos])
        lo = min(left_val, right_val)
        hi = max(left_val, right_val)

        for i in range(left_pos + 1, right_pos):
            interp_val = result[i]
            assert lo <= interp_val <= hi, (
                f"插值点 result[{i}]={interp_val:.4f} 超出范围 "
                f"[{lo:.4f}, {hi:.4f}]（左={left_val:.4f}，右={right_val:.4f}）"
            )


# ---------------------------------------------------------------------------
# 属性 4：归一化范围不变量
# Feature: a-share-quant-trading-system, Property 4: 归一化范围不变量
# ---------------------------------------------------------------------------

@st.composite
def numeric_list_strategy(draw):
    """生成至少含 2 个不同值的浮点数列表"""
    values = draw(st.lists(
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=2, max_size=100,
    ))
    return values


@settings(max_examples=100)
@given(values=numeric_list_strategy())
def test_normalization_invariant_minmax(values):
    """
    # Feature: a-share-quant-trading-system, Property 4: 归一化范围不变量（Min-Max）

    **Validates: Requirements 2.5**

    Min-Max 归一化后：
    1. 所有值应在 [0, 1] 范围内
    2. 归一化不改变相对排序关系
    """
    result = normalize_minmax(values)

    assert len(result) == len(values), "归一化后长度应与输入相同"

    # 属性 4a：值域在 [0, 1]
    for i, v in enumerate(result):
        assert 0.0 <= v <= 1.0, (
            f"Min-Max 归一化后 result[{i}]={v:.6f} 超出 [0, 1] 范围"
        )

    # 属性 4b：相对排序不变
    # 对于任意 i, j：若 values[i] < values[j]，则 result[i] <= result[j]
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            if values[i] < values[j]:
                assert result[i] <= result[j], (
                    f"排序关系被破坏：values[{i}]={values[i]} < values[{j}]={values[j]}，"
                    f"但 result[{i}]={result[i]:.6f} > result[{j}]={result[j]:.6f}"
                )
            elif values[i] > values[j]:
                assert result[i] >= result[j], (
                    f"排序关系被破坏：values[{i}]={values[i]} > values[{j}]={values[j]}，"
                    f"但 result[{i}]={result[i]:.6f} < result[{j}]={result[j]:.6f}"
                )


@settings(max_examples=100)
@given(values=numeric_list_strategy())
def test_normalization_invariant_zscore(values):
    """
    # Feature: a-share-quant-trading-system, Property 4: 归一化范围不变量（Z-Score）

    **Validates: Requirements 2.5**

    Z-Score 归一化后：
    1. 归一化不改变相对排序关系
    2. 若输入有多个不同值，归一化后均值应接近 0
    """
    result = normalize_zscore(values)

    assert len(result) == len(values), "归一化后长度应与输入相同"

    # 属性 4b：相对排序不变
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            if values[i] < values[j]:
                assert result[i] <= result[j], (
                    f"Z-Score 排序关系被破坏：values[{i}]={values[i]} < values[{j}]={values[j]}，"
                    f"但 result[{i}]={result[i]:.6f} > result[{j}]={result[j]:.6f}"
                )
            elif values[i] > values[j]:
                assert result[i] >= result[j], (
                    f"Z-Score 排序关系被破坏：values[{i}]={values[i]} > values[{j}]={values[j]}，"
                    f"但 result[{i}]={result[i]:.6f} < result[{j}]={result[j]:.6f}"
                )

    # 属性 4c：若有多个不同值，均值应接近 0
    unique_vals = set(values)
    if len(unique_vals) > 1 and len(values) > 1:
        mean_result = sum(result) / len(result)
        assert abs(mean_result) < 1e-9, (
            f"Z-Score 归一化后均值应接近 0，实际均值={mean_result:.2e}"
        )
