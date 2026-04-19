"""
Preservation 属性测试：非 bug 条件路径行为不变

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

Property 2: Preservation - factor_editor 路径及 ma_trend 未启用路径行为不变

这些测试验证不满足 bug 条件的代码路径在修复前后行为一致。
在未修复代码上运行时应全部通过（确认基线行为）。
修复后运行仍应通过（确认无回归）。
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.schemas import (
    FactorCondition,
    RiskLevel,
    ScreenItem,
    StrategyConfig,
)
from app.services.screener.screen_executor import ScreenExecutor, _classify_risk
from app.services.screener.strategy_engine import StrategyEngine


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 收盘价（合理 A 股价格范围）
_close_price = st.floats(min_value=1.0, max_value=500.0, allow_nan=False)

# ma_trend 评分（0-100）
_ma_trend_score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)


@st.composite
def factor_editor_stocks_data(draw):
    """
    生成 factor_editor 路径的测试数据：
    - 非空 factors（单个 ma_trend >= 阈值条件）
    - stock_data 中包含对应因子值，确保股票通过筛选
    - enabled_modules 包含 "factor_editor"

    返回 (config, stocks_data, enabled_modules)
    """
    # 生成一个简单的因子条件：ma_trend >= threshold
    threshold = draw(st.floats(min_value=10.0, max_value=80.0, allow_nan=False))
    factor = FactorCondition(
        factor_name="ma_trend",
        operator=">=",
        threshold=threshold,
    )
    config = StrategyConfig(
        factors=[factor],
        logic="AND",
        weights={"ma_trend": 1.0},
    )

    # 生成 1-3 只股票，ma_trend 值确保通过条件
    num_stocks = draw(st.integers(min_value=1, max_value=3))
    stocks_data = {}
    for i in range(num_stocks):
        symbol = f"{600000 + i:06d}.SH"
        # 确保 ma_trend 值 >= threshold 以通过筛选
        ma_trend_val = draw(st.floats(
            min_value=threshold,
            max_value=100.0,
            allow_nan=False,
        ))
        close = draw(_close_price)
        stocks_data[symbol] = {
            "close": close,
            "ma_trend": ma_trend_val,
        }

    enabled_modules = ["factor_editor"]
    return config, stocks_data, enabled_modules


# ---------------------------------------------------------------------------
# Property Test 1: factor_editor 路径 trend_score 等于 weighted_score
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(data=factor_editor_stocks_data())
def test_factor_editor_trend_score_equals_weighted_score(data):
    """
    Property Test 1: factor_editor 启用且 factors 非空时，
    trend_score 等于加权求和结果（需求 5 重构后）。

    **Validates: Requirements 3.1, 3.2, 5.1**

    GIVEN enabled_modules 包含 "factor_editor" 且 factors 非空
    WHEN 执行 run_eod_screen()
    THEN 每个 ScreenItem.trend_score == _compute_weighted_score({"factor_editor": weighted_score})
    """
    config, stocks_data, enabled_modules = data

    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=enabled_modules,
    )
    result = executor.run_eod_screen(stocks_data)

    for item in result.items:
        stock_data = stocks_data[item.symbol]
        eval_result = StrategyEngine.evaluate(config, stock_data)
        # 需求 5 重构后：仅 factor_editor 启用时，
        # 加权求和 = weighted_score * 0.30 / 0.30 = weighted_score（clamped [0, 100]）
        module_scores: dict[str, float] = {}
        if eval_result.weighted_score > 0:
            module_scores["factor_editor"] = eval_result.weighted_score
        expected_score = ScreenExecutor._compute_weighted_score(module_scores)

        assert item.trend_score == expected_score, (
            f"股票 {item.symbol}: trend_score 应为 {expected_score}，"
            f"实际为 {item.trend_score}。"
            f"factor_editor 路径下 trend_score 应等于加权求和结果"
        )


# ---------------------------------------------------------------------------
# Property Test 2: ma_trend 未启用时 trend_score 等于 weighted_score
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(
    close=_close_price,
    ma_trend_val=_ma_trend_score,
)
def test_no_ma_trend_module_trend_score_equals_weighted_score(close, ma_trend_val):
    """
    Property Test 2: ma_trend 模块未启用时（enabled_modules=["indicator_params"]），
    trend_score 等于加权求和结果（需求 5 重构后）。

    **Validates: Requirements 3.2, 3.3, 5.1**

    GIVEN enabled_modules=["indicator_params"]（不含 "ma_trend"）
    AND factors=[]（空因子列表）
    AND stock_data 包含 macd=True 以产生 indicator_params 信号
    WHEN 执行 run_eod_screen()
    THEN trend_score == _compute_weighted_score({"indicator_params": 25.0})
    """
    config = StrategyConfig(factors=[])
    stocks_data = {
        "600000.SH": {
            "close": close,
            "ma_trend": ma_trend_val,
            "macd": True,  # 产生 indicator_params 信号，避免被过滤
        },
    }

    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=["indicator_params"],
    )
    result = executor.run_eod_screen(stocks_data)

    # 因为 macd=True 产生了信号，股票应出现在结果中
    assert len(result.items) == 1, (
        f"期望 1 个结果项，实际 {len(result.items)} 个"
    )

    item = result.items[0]
    # 需求 5 重构后：indicator_params 模块评分 25.0（macd=True），
    # 加权求和 = 25.0 * 0.20 / 0.20 = 25.0
    expected_score = ScreenExecutor._compute_weighted_score(
        {"indicator_params": 25.0}
    )

    assert item.trend_score == expected_score, (
        f"trend_score 应为 {expected_score}，实际为 {item.trend_score}。"
        f"加权求和后 indicator_params=25.0 的结果应为 {expected_score}"
    )


# ---------------------------------------------------------------------------
# Property Test 3: enabled_modules=[] 时返回空结果
# ---------------------------------------------------------------------------


@settings(max_examples=30)
@given(
    close=_close_price,
    ma_trend_val=_ma_trend_score,
)
def test_empty_modules_returns_empty_result(close, ma_trend_val):
    """
    Property Test 3: enabled_modules=[]（空集，非 None）时，
    ScreenResult.items 为空列表。

    **Validates: Requirements 3.4**

    GIVEN enabled_modules=[]（空集）
    WHEN 执行 run_eod_screen()
    THEN result.items 为空列表
    """
    config = StrategyConfig(factors=[])
    stocks_data = {
        "600000.SH": {
            "close": close,
            "ma_trend": ma_trend_val,
            "macd": True,
        },
    }

    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=[],  # 空集
    )
    result = executor.run_eod_screen(stocks_data)

    assert result.items == [], (
        f"enabled_modules=[] 时应返回空结果，实际返回 {len(result.items)} 个项"
    )


# ---------------------------------------------------------------------------
# Property Test 4: _classify_risk 分类规则
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
def test_classify_risk_follows_threshold_rules(score):
    """
    Property Test 4: 对任意 score ∈ [0, 100]，_classify_risk(score) 遵循：
    >= 80 → LOW，>= 50 → MEDIUM，< 50 → HIGH。

    **Validates: Requirements 3.2**

    GIVEN score ∈ [0, 100]
    WHEN 调用 _classify_risk(score)
    THEN 返回值遵循阈值规则
    """
    result = _classify_risk(score)

    if score >= 80:
        assert result == RiskLevel.LOW, (
            f"score={score} >= 80 应返回 LOW，实际返回 {result.value}"
        )
    elif score >= 50:
        assert result == RiskLevel.MEDIUM, (
            f"score={score} >= 50 应返回 MEDIUM，实际返回 {result.value}"
        )
    else:
        assert result == RiskLevel.HIGH, (
            f"score={score} < 50 应返回 HIGH，实际返回 {result.value}"
        )
