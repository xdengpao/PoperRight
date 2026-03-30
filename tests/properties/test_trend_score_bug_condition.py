"""
Bug Condition 探索性测试：trend_score 未使用 ma_trend 评分

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2**

Property 1: Bug Condition - 非 factor_editor 路径下 trend_score 应使用 ma_trend 评分

对任意 enabled_modules=["ma_trend"]、factors=[] 的策略配置，
当 stock_data 包含有效的 ma_trend 评分（>= 80，确保股票通过信号过滤）时，
ScreenExecutor.run_eod_screen() 返回的 ScreenItem.trend_score 应等于
stock_data["ma_trend"] 的值，而非 0.0。

此测试编码了期望行为。在未修复代码上运行时应失败（确认缺陷存在）。
修复后运行应通过（确认修复正确性）。
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import StrategyConfig, RiskLevel
from app.services.screener.screen_executor import ScreenExecutor, _classify_risk


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# ma_trend 评分：限定 >= 80 确保股票产生 MA_TREND 信号不被过滤
_ma_trend_score = st.floats(min_value=80.0, max_value=100.0, allow_nan=False)

# 收盘价（合理 A 股价格范围）
_close_price = st.floats(min_value=1.0, max_value=500.0, allow_nan=False)

# 股票代码
_symbol = st.from_regex(r"[0-9]{6}\.(SH|SZ)", fullmatch=True)


@st.composite
def stocks_data_strategy(draw):
    """
    生成 {symbol: stock_data} 字典，包含 1-3 只股票。
    每只股票的 stock_data 包含 close 和 ma_trend 字段。
    ma_trend >= 80 确保股票通过信号过滤进入结果。
    """
    num_stocks = draw(st.integers(min_value=1, max_value=3))
    stocks_data = {}
    for i in range(num_stocks):
        symbol = f"{600000 + i:06d}.SH"
        ma_trend = draw(_ma_trend_score)
        close = draw(_close_price)
        stocks_data[symbol] = {
            "close": close,
            "ma_trend": ma_trend,
        }
    return stocks_data


# ---------------------------------------------------------------------------
# Bug Condition 探索性测试
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(stocks_data=stocks_data_strategy())
def test_trend_score_reflects_ma_trend_value(stocks_data):
    """
    Property 1: Bug Condition - trend_score 应反映 ma_trend 评分

    **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2**

    GIVEN enabled_modules=["ma_trend"], factors=[] 的策略配置
    AND stock_data 包含 ma_trend >= 80 的有效评分
    WHEN 执行 run_eod_screen()
    THEN 每个 ScreenItem.trend_score 应等于对应 stock_data["ma_trend"]
    AND ScreenItem.risk_level 应等于 _classify_risk(trend_score)

    在未修复代码上，trend_score 始终为 0.0（来自空 factors 的 weighted_score），
    risk_level 始终为 HIGH。此测试应失败，确认缺陷存在。
    """
    config = StrategyConfig(factors=[])
    executor = ScreenExecutor(
        strategy_config=config,
        enabled_modules=["ma_trend"],
    )

    result = executor.run_eod_screen(stocks_data)

    # 所有股票的 ma_trend >= 80，应全部产生信号并出现在结果中
    assert len(result.items) == len(stocks_data), (
        f"期望 {len(stocks_data)} 个结果项，实际 {len(result.items)} 个。"
        f"部分股票可能被错误过滤。"
    )

    for item in result.items:
        expected_ma_trend = stocks_data[item.symbol]["ma_trend"]

        # trend_score 应等于 stock_data["ma_trend"]（而非 0.0）
        assert item.trend_score == expected_ma_trend, (
            f"股票 {item.symbol}: trend_score 应为 {expected_ma_trend}，"
            f"实际为 {item.trend_score}。"
            f"Bug: trend_score 使用了 eval_result.weighted_score (0.0) "
            f"而非 stock_data['ma_trend'] ({expected_ma_trend})"
        )

        # risk_level 应与 trend_score 对应
        expected_risk = _classify_risk(item.trend_score)
        assert item.risk_level == expected_risk, (
            f"股票 {item.symbol}: risk_level 应为 {expected_risk.value}，"
            f"实际为 {item.risk_level.value}。"
            f"trend_score={item.trend_score}"
        )
