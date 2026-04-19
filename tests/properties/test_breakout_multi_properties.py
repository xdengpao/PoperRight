"""
多重突破信号并发属性测试（Hypothesis）

Property 6: 多重突破信号完整检测
Property 7: 突破信号到 SignalDetail 的映射

对应需求 6.1、6.2、6.3

验证：
- ScreenDataProvider._detect_all_breakouts() 对所有启用的突破类型逐一检测
- ScreenExecutor._build_breakout_signals() 为每个有效突破生成独立 SignalDetail
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import SignalCategory, SignalDetail
from app.services.screener.screen_data_provider import ScreenDataProvider
from app.services.screener.screen_executor import ScreenExecutor
from app.services.screener.breakout import (
    BreakoutType,
    detect_box_breakout,
    detect_previous_high_breakout,
    detect_descending_trendline_breakout,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 突破类型启用标志策略
_bool_st = st.booleans()

# 量比阈值策略
_vol_threshold_st = st.floats(
    min_value=1.0, max_value=3.0,
    allow_nan=False, allow_infinity=False,
)


@st.composite
def breakout_config_strategy(draw):
    """
    生成随机的突破配置字典。

    包含 box_breakout、high_breakout、trendline_breakout 启用标志，
    以及 volume_ratio_threshold 和 confirm_days。
    """
    return {
        "box_breakout": draw(_bool_st),
        "high_breakout": draw(_bool_st),
        "trendline_breakout": draw(_bool_st),
        "volume_ratio_threshold": draw(_vol_threshold_st),
        "confirm_days": draw(st.integers(min_value=0, max_value=1)),
    }


@st.composite
def breakout_list_strategy(draw):
    """
    生成随机的 breakout_list（突破信号列表）。

    每个信号包含 type、is_valid、is_false_breakout、volume_ratio 等字段。
    """
    breakout_types = ["BOX", "PREVIOUS_HIGH", "TRENDLINE"]
    n = draw(st.integers(min_value=0, max_value=3))
    selected_types = draw(
        st.lists(
            st.sampled_from(breakout_types),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )

    signals: list[dict] = []
    for bt in selected_types:
        is_valid = draw(_bool_st)
        signals.append({
            "type": bt,
            "resistance": draw(st.floats(
                min_value=1.0, max_value=100.0,
                allow_nan=False, allow_infinity=False,
            )),
            "is_valid": is_valid,
            "is_false_breakout": draw(_bool_st) if is_valid else False,
            "volume_ratio": draw(st.floats(
                min_value=0.5, max_value=5.0,
                allow_nan=False, allow_infinity=False,
            )),
            "generates_buy_signal": is_valid,
        })
    return signals


@st.composite
def stock_data_with_breakout_list_strategy(draw):
    """
    生成包含 breakout_list 的 stock_data 字典。
    """
    breakout_list = draw(breakout_list_strategy())
    stock_data = {
        "breakout": breakout_list[0] if breakout_list else None,
        "breakout_list": breakout_list,
    }
    return stock_data


@st.composite
def stock_data_legacy_breakout_strategy(draw):
    """
    生成仅包含旧格式 breakout（单字典）的 stock_data 字典，
    不包含 breakout_list 字段。
    """
    breakout_types = ["BOX", "PREVIOUS_HIGH", "TRENDLINE"]
    has_breakout = draw(_bool_st)
    if has_breakout:
        is_valid = draw(_bool_st)
        breakout = {
            "type": draw(st.sampled_from(breakout_types)),
            "resistance": draw(st.floats(
                min_value=1.0, max_value=100.0,
                allow_nan=False, allow_infinity=False,
            )),
            "is_valid": is_valid,
            "is_false_breakout": draw(_bool_st) if is_valid else False,
            "volume_ratio": draw(st.floats(
                min_value=0.5, max_value=5.0,
                allow_nan=False, allow_infinity=False,
            )),
            "generates_buy_signal": is_valid,
        }
    else:
        breakout = None

    return {"breakout": breakout}


# ---------------------------------------------------------------------------
# Property 6: 多重突破信号完整检测
# Feature: screening-system-enhancement, Property 6: 完整检测
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(bo_cfg=breakout_config_strategy())
def test_detect_all_breakouts_completeness(bo_cfg):
    """
    # Feature: screening-system-enhancement, Property 6: 完整检测

    **Validates: Requirements 6.1, 6.2**

    For any 突破配置，_detect_all_breakouts() 返回的 breakout_list 长度
    应等于实际触发的突破类型数量，且每种触发的突破类型都应在列表中有对应条目。

    使用固定的价格数据确保突破条件可控。
    """
    # 构造一组价格数据，使得所有三种突破类型都能触发
    # 箱体突破：20 天窄幅震荡后突破
    n = 100
    base_price = 10.0
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[int] = []

    # 前 80 天：稳定在 base_price 附近（窄幅震荡）
    for i in range(n - 1):
        c = base_price + (i % 3) * 0.01  # 微小波动
        closes.append(c)
        highs.append(c + 0.05)
        lows.append(c - 0.05)
        volumes.append(1000)

    # 最后一天：大幅突破
    closes.append(base_price * 1.15)
    highs.append(base_price * 1.16)
    lows.append(base_price * 1.01)
    volumes.append(5000)  # 高成交量

    vol_threshold = bo_cfg.get("volume_ratio_threshold", 1.5)

    result = ScreenDataProvider._detect_all_breakouts(
        closes, highs, lows, volumes, bo_cfg,
    )

    # 独立检测每种类型，统计预期触发数
    expected_types: set[str] = set()

    if bo_cfg.get("box_breakout", True):
        box = detect_box_breakout(
            closes, highs, lows, volumes,
            volume_multiplier=vol_threshold,
        )
        if box is not None:
            expected_types.add(box.breakout_type.value)

    if bo_cfg.get("high_breakout", True):
        prev = detect_previous_high_breakout(
            closes, volumes,
            volume_multiplier=vol_threshold,
        )
        if prev is not None:
            expected_types.add(prev.breakout_type.value)

    if bo_cfg.get("trendline_breakout", True):
        trend = detect_descending_trendline_breakout(
            closes, highs, volumes,
            volume_multiplier=vol_threshold,
        )
        if trend is not None:
            expected_types.add(trend.breakout_type.value)

    # 验证：breakout_list 长度等于实际触发的突破类型数量
    actual_types = {bo["type"] for bo in result}
    assert len(result) == len(expected_types), (
        f"breakout_list 长度 {len(result)} 应等于触发的突破类型数 {len(expected_types)}。"
        f"期望类型: {expected_types}，实际类型: {actual_types}"
    )

    # 验证：每种触发的突破类型都在列表中
    assert actual_types == expected_types, (
        f"breakout_list 中的突破类型 {actual_types} 应等于预期 {expected_types}"
    )


@settings(max_examples=200)
@given(bo_cfg=breakout_config_strategy())
def test_detect_all_breakouts_disabled_types_excluded(bo_cfg):
    """
    # Feature: screening-system-enhancement, Property 6: 完整检测

    **Validates: Requirements 6.1**

    未启用的突破类型不应出现在 breakout_list 中。
    """
    # 使用相同的价格数据
    n = 100
    base_price = 10.0
    closes = [base_price + (i % 3) * 0.01 for i in range(n - 1)]
    closes.append(base_price * 1.15)
    highs = [c + 0.05 for c in closes[:-1]] + [base_price * 1.16]
    lows = [c - 0.05 for c in closes[:-1]] + [base_price * 1.01]
    volumes = [1000] * (n - 1) + [5000]

    result = ScreenDataProvider._detect_all_breakouts(
        closes, highs, lows, volumes, bo_cfg,
    )

    actual_types = {bo["type"] for bo in result}

    # 未启用的类型不应出现
    if not bo_cfg.get("box_breakout", True):
        assert "BOX" not in actual_types, "未启用的 BOX 突破不应出现在结果中"
    if not bo_cfg.get("high_breakout", True):
        assert "PREVIOUS_HIGH" not in actual_types, "未启用的 PREVIOUS_HIGH 突破不应出现在结果中"
    if not bo_cfg.get("trendline_breakout", True):
        assert "TRENDLINE" not in actual_types, "未启用的 TRENDLINE 突破不应出现在结果中"


# ---------------------------------------------------------------------------
# Property 7: 突破信号到 SignalDetail 的映射
# Feature: screening-system-enhancement, Property 7: 信号映射
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(stock_data=stock_data_with_breakout_list_strategy())
def test_breakout_signals_mapping_count(stock_data):
    """
    # Feature: screening-system-enhancement, Property 7: 信号映射

    **Validates: Requirements 6.3**

    For any 包含 N 个有效突破信号的 breakout_list，
    _build_breakout_signals() 应生成恰好 N 个 category=BREAKOUT 的 SignalDetail。
    """
    breakout_list = stock_data.get("breakout_list", [])
    expected_count = sum(
        1 for bo in breakout_list
        if isinstance(bo, dict) and bo.get("is_valid")
    )

    signals = ScreenExecutor._build_breakout_signals(stock_data)

    breakout_signals = [s for s in signals if s.category == SignalCategory.BREAKOUT]
    assert len(breakout_signals) == expected_count, (
        f"有效突破信号数 {expected_count} 应等于生成的 BREAKOUT SignalDetail 数 "
        f"{len(breakout_signals)}。breakout_list={breakout_list}"
    )


@settings(max_examples=200)
@given(stock_data=stock_data_with_breakout_list_strategy())
def test_breakout_signals_type_preserved(stock_data):
    """
    # Feature: screening-system-enhancement, Property 7: 信号映射

    **Validates: Requirements 6.3**

    每个生成的 SignalDetail 的 breakout_type 应与原始突破信号的 type 一致。
    """
    breakout_list = stock_data.get("breakout_list", [])
    expected_types = [
        bo["type"]
        for bo in breakout_list
        if isinstance(bo, dict) and bo.get("is_valid")
    ]

    signals = ScreenExecutor._build_breakout_signals(stock_data)

    actual_types = [s.breakout_type for s in signals]
    assert actual_types == expected_types, (
        f"SignalDetail 的 breakout_type {actual_types} 应与原始类型 {expected_types} 一致"
    )


@settings(max_examples=200)
@given(stock_data=stock_data_with_breakout_list_strategy())
def test_breakout_signals_fake_breakout_preserved(stock_data):
    """
    # Feature: screening-system-enhancement, Property 7: 信号映射

    **Validates: Requirements 6.3**

    每个生成的 SignalDetail 的 is_fake_breakout 应与原始突破信号一致。
    """
    breakout_list = stock_data.get("breakout_list", [])
    expected_fakes = [
        bool(bo.get("is_false_breakout", False))
        for bo in breakout_list
        if isinstance(bo, dict) and bo.get("is_valid")
    ]

    signals = ScreenExecutor._build_breakout_signals(stock_data)

    actual_fakes = [s.is_fake_breakout for s in signals]
    assert actual_fakes == expected_fakes, (
        f"SignalDetail 的 is_fake_breakout {actual_fakes} 应与原始 {expected_fakes} 一致"
    )


# ---------------------------------------------------------------------------
# Property 7 补充：向后兼容旧格式
# Feature: screening-system-enhancement, Property 7: 向后兼容
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(stock_data=stock_data_legacy_breakout_strategy())
def test_breakout_signals_legacy_compat(stock_data):
    """
    # Feature: screening-system-enhancement, Property 7: 向后兼容

    **Validates: Requirements 6.3**

    当 breakout 为单个字典（旧格式）且无 breakout_list 时，
    _build_breakout_signals() 仍能正确处理。
    """
    breakout_data = stock_data.get("breakout")
    expected_count = (
        1 if isinstance(breakout_data, dict) and breakout_data.get("is_valid")
        else 0
    )

    signals = ScreenExecutor._build_breakout_signals(stock_data)

    breakout_signals = [s for s in signals if s.category == SignalCategory.BREAKOUT]
    assert len(breakout_signals) == expected_count, (
        f"旧格式 breakout 有效信号数 {expected_count} 应等于生成的 BREAKOUT SignalDetail 数 "
        f"{len(breakout_signals)}。breakout={breakout_data}"
    )

    # 验证 breakout_type 正确传递
    if expected_count == 1:
        assert breakout_signals[0].breakout_type == breakout_data["type"], (
            f"旧格式 breakout_type 应为 {breakout_data['type']}，"
            f"实际为 {breakout_signals[0].breakout_type}"
        )
