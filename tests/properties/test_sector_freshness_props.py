"""
板块数据新鲜度属性测试（Hypothesis）

**Validates: Requirements 9.2, 9.5**

Property 15: 板块数据新鲜度降级
"""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.screener.sector_strength import SectorStrengthFilter


# ---------------------------------------------------------------------------
# 辅助函数：计算两个日期之间的工作日数（与被测函数逻辑一致的参考实现）
# ---------------------------------------------------------------------------


def _count_business_days(start: date, end: date) -> int:
    """参考实现：统计 start 到 end 之间的工作日数（不含 start，含 end）。"""
    count = 0
    d = start + timedelta(days=1)
    while d <= end:
        if d.weekday() < 5:  # 周一到周五
            count += 1
        d += timedelta(days=1)
    return count


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 日期范围：2020-01-01 到 2030-12-31
_date_strategy = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


# ---------------------------------------------------------------------------
# Property 15: 板块数据新鲜度降级
# Feature: screening-parameter-optimization, Property 15: 板块数据新鲜度降级
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    latest_data_date=_date_strategy,
    current_date=_date_strategy,
)
def test_freshness_degrade_when_exceeds_threshold(
    latest_data_date: date,
    current_date: date,
):
    """
    # Feature: screening-parameter-optimization, Property 15: 板块数据新鲜度降级

    **Validates: Requirements 9.2, 9.5**

    当数据延迟交易日数 > degrade_threshold（默认 5）时，should_degrade 应为 True；
    当延迟交易日数 <= degrade_threshold 时，should_degrade 应为 False。
    """
    assume(current_date >= latest_data_date)

    should_warn, should_degrade, stale_days = SectorStrengthFilter.check_data_freshness(
        latest_data_date, current_date,
    )

    expected_stale = _count_business_days(latest_data_date, current_date)
    assert stale_days == expected_stale, (
        f"stale_days 计算不一致：expected={expected_stale}, actual={stale_days}, "
        f"latest={latest_data_date}, current={current_date}"
    )

    # 默认降级阈值为 5
    if stale_days > 5:
        assert should_degrade is True, (
            f"延迟 {stale_days} 天应降级，latest={latest_data_date}, "
            f"current={current_date}"
        )
    else:
        assert should_degrade is False, (
            f"延迟 {stale_days} 天不应降级，latest={latest_data_date}, "
            f"current={current_date}"
        )


@settings(max_examples=200)
@given(
    latest_data_date=_date_strategy,
    current_date=_date_strategy,
)
def test_freshness_warn_when_exceeds_threshold(
    latest_data_date: date,
    current_date: date,
):
    """
    # Feature: screening-parameter-optimization, Property 15: 板块数据新鲜度降级

    **Validates: Requirements 9.2, 9.5**

    当数据延迟交易日数 > warning_threshold（默认 2）时，should_warn 应为 True；
    当延迟交易日数 <= warning_threshold 时，should_warn 应为 False。
    """
    assume(current_date >= latest_data_date)

    should_warn, should_degrade, stale_days = SectorStrengthFilter.check_data_freshness(
        latest_data_date, current_date,
    )

    # 默认 WARNING 阈值为 2
    if stale_days > 2:
        assert should_warn is True, (
            f"延迟 {stale_days} 天应 WARNING，latest={latest_data_date}, "
            f"current={current_date}"
        )
    else:
        assert should_warn is False, (
            f"延迟 {stale_days} 天不应 WARNING，latest={latest_data_date}, "
            f"current={current_date}"
        )


@settings(max_examples=200)
@given(
    latest_data_date=_date_strategy,
    current_date=_date_strategy,
)
def test_freshness_degrade_implies_warn(
    latest_data_date: date,
    current_date: date,
):
    """
    # Feature: screening-parameter-optimization, Property 15: 板块数据新鲜度降级

    **Validates: Requirements 9.2, 9.5**

    should_degrade=True 时必然 should_warn=True（降级阈值 > 警告阈值）。
    """
    assume(current_date >= latest_data_date)

    should_warn, should_degrade, stale_days = SectorStrengthFilter.check_data_freshness(
        latest_data_date, current_date,
    )

    if should_degrade:
        assert should_warn is True, (
            f"should_degrade=True 时 should_warn 也应为 True，"
            f"stale_days={stale_days}"
        )


@settings(max_examples=200)
@given(
    latest_data_date=_date_strategy,
    current_date=_date_strategy,
)
def test_freshness_stale_days_non_negative(
    latest_data_date: date,
    current_date: date,
):
    """
    # Feature: screening-parameter-optimization, Property 15: 板块数据新鲜度降级

    **Validates: Requirements 9.2, 9.5**

    当 current_date >= latest_data_date 时，stale_days 应 >= 0。
    """
    assume(current_date >= latest_data_date)

    _, _, stale_days = SectorStrengthFilter.check_data_freshness(
        latest_data_date, current_date,
    )

    assert stale_days >= 0, (
        f"stale_days 应非负，actual={stale_days}, "
        f"latest={latest_data_date}, current={current_date}"
    )


@settings(max_examples=200)
@given(
    latest_data_date=_date_strategy,
    current_date=_date_strategy,
    warning_threshold=st.integers(min_value=1, max_value=20),
    degrade_threshold=st.integers(min_value=1, max_value=30),
)
def test_freshness_custom_thresholds(
    latest_data_date: date,
    current_date: date,
    warning_threshold: int,
    degrade_threshold: int,
):
    """
    # Feature: screening-parameter-optimization, Property 15: 板块数据新鲜度降级

    **Validates: Requirements 9.2, 9.5**

    对任意自定义阈值，should_warn 和 should_degrade 应与 stale_days 的比较一致。
    """
    assume(current_date >= latest_data_date)
    assume(degrade_threshold >= warning_threshold)

    should_warn, should_degrade, stale_days = SectorStrengthFilter.check_data_freshness(
        latest_data_date,
        current_date,
        warning_threshold_days=warning_threshold,
        degrade_threshold_days=degrade_threshold,
    )

    assert should_warn == (stale_days > warning_threshold), (
        f"should_warn 与阈值比较不一致：stale_days={stale_days}, "
        f"threshold={warning_threshold}, should_warn={should_warn}"
    )
    assert should_degrade == (stale_days > degrade_threshold), (
        f"should_degrade 与阈值比较不一致：stale_days={stale_days}, "
        f"threshold={degrade_threshold}, should_degrade={should_degrade}"
    )
