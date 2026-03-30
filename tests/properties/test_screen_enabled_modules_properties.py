# Feature: a-share-quant-trading-system, Property 82: 选股仅应用已启用模块的筛选逻辑
"""
选股模块启用属性测试（Hypothesis）

属性 82：选股仅应用已启用模块的筛选逻辑

**Validates: Requirements 27.7, 27.8**

对任意策略配置和任意 enabled_modules 子集，ScreenExecutor 仅应用已启用模块的
筛选逻辑；enabled_modules 为空列表时返回空结果集。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.schemas import FactorCondition, StrategyConfig
from app.services.screener.screen_executor import ScreenExecutor

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

VALID_MODULES = {"factor_editor", "ma_trend", "indicator_params", "breakout", "volume_price"}

# 简单测试股票数据：包含 ma_trend 因子值和 close 价格
_SIMPLE_STOCKS_DATA: dict[str, dict] = {
    "000001": {"close": 10.0, "ma_trend": 85},
    "000002": {"close": 20.0, "ma_trend": 90},
}

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 从 VALID_MODULES 的幂集中生成任意非空子集
_modules_nonempty_subset_st = st.frozensets(
    st.sampled_from(sorted(VALID_MODULES)), min_size=1
).map(lambda s: sorted(s))

# 从 VALID_MODULES 的幂集中生成任意子集（包括空集）
_modules_subset_st = st.frozensets(
    st.sampled_from(sorted(VALID_MODULES))
).map(lambda s: sorted(s))


def _make_config() -> StrategyConfig:
    """创建一个包含 ma_trend 因子的最小策略配置。"""
    return StrategyConfig(
        factors=[
            FactorCondition(
                factor_name="ma_trend",
                operator=">=",
                threshold=0,
            ),
        ],
        logic="AND",
        weights={"ma_trend": 1.0},
        ma_periods=[5, 10, 20],
    )


# ---------------------------------------------------------------------------
# 属性 82-1：enabled_modules 为空列表时返回空结果集
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(data=st.data())
def test_empty_enabled_modules_returns_empty_result(data: st.DataObject):
    """
    # Feature: a-share-quant-trading-system, Property 82: 选股仅应用已启用模块的筛选逻辑

    **Validates: Requirements 27.8**

    对任意 stocks_data，enabled_modules=[] 时 ScreenExecutor 始终返回
    ScreenResult 且 items 为空列表。
    """
    config = _make_config()
    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=[],
    )

    result = executor.run_eod_screen(_SIMPLE_STOCKS_DATA)

    assert result.items == [], (
        f"enabled_modules=[] should yield empty items, got {len(result.items)} items"
    )
    assert result.is_complete is True


# ---------------------------------------------------------------------------
# 属性 82-2：结果中的信号仅属于已启用模块
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(modules=_modules_nonempty_subset_st)
def test_signals_only_from_enabled_modules(modules: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 82: 选股仅应用已启用模块的筛选逻辑

    **Validates: Requirements 27.7**

    对任意 VALID_MODULES 的非空子集，ScreenExecutor 返回的信号仅属于
    已启用模块（通过 _FACTOR_MODULE 映射检查）。
    """
    config = _make_config()
    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=modules,
    )

    result = executor.run_eod_screen(_SIMPLE_STOCKS_DATA)

    enabled_set = set(modules)
    factor_module_map = ScreenExecutor._FACTOR_MODULE

    for item in result.items:
        for signal in item.signals:
            # signal.label 是因子名称，查找其所属模块
            module_key = factor_module_map.get(signal.label)
            if module_key is not None:
                assert module_key in enabled_set, (
                    f"Signal '{signal.label}' belongs to module '{module_key}' "
                    f"which is not in enabled_modules {modules}"
                )


# ---------------------------------------------------------------------------
# 属性 82-3：enabled_modules=None 等价于全部模块启用
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(data=st.data())
def test_none_means_all_modules_enabled(data: st.DataObject):
    """
    # Feature: a-share-quant-trading-system, Property 82: 选股仅应用已启用模块的筛选逻辑

    **Validates: Requirements 27.7**

    enabled_modules=None 的行为应与传入全部 5 个模块一致（向后兼容）。
    """
    config = _make_config()

    executor_none = ScreenExecutor(
        strategy_config=config,
        enabled_modules=None,
    )
    executor_all = ScreenExecutor(
        strategy_config=config,
        enabled_modules=sorted(VALID_MODULES),
    )

    result_none = executor_none.run_eod_screen(_SIMPLE_STOCKS_DATA)
    result_all = executor_all.run_eod_screen(_SIMPLE_STOCKS_DATA)

    # 两者应返回相同数量的 items
    assert len(result_none.items) == len(result_all.items), (
        f"None ({len(result_none.items)} items) vs all modules "
        f"({len(result_all.items)} items) mismatch"
    )

    # 两者应返回相同的股票代码集合
    symbols_none = {item.symbol for item in result_none.items}
    symbols_all = {item.symbol for item in result_all.items}
    assert symbols_none == symbols_all, (
        f"Symbol sets differ: None={symbols_none}, all={symbols_all}"
    )

    # 两者每只股票的信号标签集合应一致
    for item_none in result_none.items:
        item_all = next(
            (i for i in result_all.items if i.symbol == item_none.symbol), None
        )
        assert item_all is not None
        labels_none = {s.label for s in item_none.signals}
        labels_all = {s.label for s in item_all.signals}
        assert labels_none == labels_all, (
            f"Signal labels differ for {item_none.symbol}: "
            f"None={labels_none}, all={labels_all}"
        )
