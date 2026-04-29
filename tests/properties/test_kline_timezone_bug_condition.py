"""
Bug Condition 探索性测试：K线数据时间戳时区处理不一致

**Validates: Requirements 2.1, 2.4**

Property 1: Bug Condition - 日线数据解析后时间戳应为 00:00:00 UTC

对任意日线数据日期字符串输入：
  - `_parse_datetime("2024-01-15")` 应返回 datetime 对象，具有 hour=0, minute=0, second=0, tzinfo=timezone.utc
  - `_parse_trade_date(20240115)` 应返回 datetime 对象，具有 hour=0, minute=0, second=0, tzinfo=timezone.utc

此测试编码了期望行为。在未修复代码上运行时应失败（确认缺陷存在）。
修复后运行应通过（确认修复正确性）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.local_kline_import import LocalKlineImportService
from app.services.data_engine.tushare_adapter import TushareAdapter


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 日期字符串格式：YYYY-MM-DD
_date_str_yyyy_mm_dd = st.dates(
    min_value=datetime(2000, 1, 1).date(),
    max_value=datetime(2030, 12, 31).date(),
).map(lambda d: d.strftime("%Y-%m-%d"))

# 日期字符串格式：YYYY/MM/DD
_date_str_yyyy_slash_mm_slash_dd = st.dates(
    min_value=datetime(2000, 1, 1).date(),
    max_value=datetime(2030, 12, 31).date(),
).map(lambda d: d.strftime("%Y/%m/%d"))

# 日期字符串格式：YYYYMMDD
_date_str_yyyymmdd = st.dates(
    min_value=datetime(2000, 1, 1).date(),
    max_value=datetime(2030, 12, 31).date(),
).map(lambda d: d.strftime("%Y%m%d"))

# Tushare 交易日期整数：YYYYMMDD
_trade_date_int = st.integers(
    min_value=20000101,
    max_value=20301231,
).filter(
    lambda n: 1 <= (n % 100) <= 31  # 简单过滤：日期部分 01-31
).filter(
    lambda n: 1 <= ((n // 100) % 100) <= 12  # 简单过滤：月份部分 01-12
)


# ---------------------------------------------------------------------------
# Bug Condition 探索性测试
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(date_str=_date_str_yyyy_mm_dd)
def test_parse_datetime_returns_utc_timezone_yyyy_mm_dd(date_str):
    """
    Property 1: Bug Condition - _parse_datetime("YYYY-MM-DD") 应返回 UTC 时区 datetime

    **Validates: Requirements 2.1, 2.4**

    GIVEN 日期字符串格式 "YYYY-MM-DD"（如 "2024-01-15"）
    WHEN 调用 LocalKlineImportService._parse_datetime(date_str)
    THEN 返回的 datetime 对象应满足：
      - hour = 0
      - minute = 0
      - second = 0
      - tzinfo = timezone.utc

    在未修复代码上，返回 naive datetime（无 tzinfo），此测试应失败。
    """
    result = LocalKlineImportService._parse_datetime(date_str)

    # 断言：时间部分应为 00:00:00
    assert result.hour == 0, (
        f"解析 '{date_str}' 后 hour 应为 0，实际为 {result.hour}"
    )
    assert result.minute == 0, (
        f"解析 '{date_str}' 后 minute 应为 0，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{date_str}' 后 second 应为 0，实际为 {result.second}"
    )

    # 断言：必须包含 UTC 时区信息
    assert result.tzinfo is not None, (
        f"解析 '{date_str}' 返回 naive datetime，缺少 tzinfo。"
        f"期望: datetime with tzinfo=timezone.utc，实际: {result}"
    )
    assert result.tzinfo == timezone.utc, (
        f"解析 '{date_str}' 后 tzinfo 应为 timezone.utc，实际为 {result.tzinfo}"
    )


@settings(max_examples=50)
@given(date_str=_date_str_yyyy_slash_mm_slash_dd)
def test_parse_datetime_returns_utc_timezone_yyyy_slash_mm_slash_dd(date_str):
    """
    Property 1: Bug Condition - _parse_datetime("YYYY/MM/DD") 应返回 UTC 时区 datetime

    **Validates: Requirements 2.1, 2.4**

    GIVEN 日期字符串格式 "YYYY/MM/DD"（如 "2024/01/15"）
    WHEN 调用 LocalKlineImportService._parse_datetime(date_str)
    THEN 返回的 datetime 对象应满足：
      - hour = 0
      - minute = 0
      - second = 0
      - tzinfo = timezone.utc

    在未修复代码上，返回 naive datetime（无 tzinfo），此测试应失败。
    """
    result = LocalKlineImportService._parse_datetime(date_str)

    assert result.hour == 0, (
        f"解析 '{date_str}' 后 hour 应为 0，实际为 {result.hour}"
    )
    assert result.minute == 0, (
        f"解析 '{date_str}' 后 minute 应为 0，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{date_str}' 后 second 应为 0，实际为 {result.second}"
    )

    assert result.tzinfo is not None, (
        f"解析 '{date_str}' 返回 naive datetime，缺少 tzinfo。"
        f"期望: datetime with tzinfo=timezone.utc，实际: {result}"
    )
    assert result.tzinfo == timezone.utc, (
        f"解析 '{date_str}' 后 tzinfo 应为 timezone.utc，实际为 {result.tzinfo}"
    )


@settings(max_examples=50)
@given(date_str=_date_str_yyyymmdd)
def test_parse_datetime_returns_utc_timezone_yyyymmdd(date_str):
    """
    Property 1: Bug Condition - _parse_datetime("YYYYMMDD") 应返回 UTC 时区 datetime

    **Validates: Requirements 2.1, 2.4**

    GIVEN 日期字符串格式 "YYYYMMDD"（如 "20240115"）
    WHEN 调用 LocalKlineImportService._parse_datetime(date_str)
    THEN 返回的 datetime 对象应满足：
      - hour = 0
      - minute = 0
      - second = 0
      - tzinfo = timezone.utc

    在未修复代码上，返回 naive datetime（无 tzinfo），此测试应失败。
    """
    result = LocalKlineImportService._parse_datetime(date_str)

    assert result.hour == 0, (
        f"解析 '{date_str}' 后 hour 应为 0，实际为 {result.hour}"
    )
    assert result.minute == 0, (
        f"解析 '{date_str}' 后 minute 应为 0，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{date_str}' 后 second 应为 0，实际为 {result.second}"
    )

    assert result.tzinfo is not None, (
        f"解析 '{date_str}' 返回 naive datetime，缺少 tzinfo。"
        f"期望: datetime with tzinfo=timezone.utc，实际: {result}"
    )
    assert result.tzinfo == timezone.utc, (
        f"解析 '{date_str}' 后 tzinfo 应为 timezone.utc，实际为 {result.tzinfo}"
    )


@settings(max_examples=50)
@given(trade_date=_trade_date_int)
def test_parse_trade_date_returns_utc_timezone(trade_date):
    """
    Property 1: Bug Condition - _parse_trade_date(YYYYMMDD) 应返回 UTC 时区 datetime

    **Validates: Requirements 2.1, 2.4**

    GIVEN Tushare 交易日期整数（如 20240115）
    WHEN 调用 TushareAdapter._parse_trade_date(trade_date)
    THEN 返回的 datetime 对象应满足：
      - hour = 0
      - minute = 0
      - second = 0
      - tzinfo = timezone.utc

    在未修复代码上，返回 naive datetime（无 tzinfo），此测试应失败。
    """
    result = TushareAdapter._parse_trade_date(trade_date)

    # 断言：时间部分应为 00:00:00
    assert result.hour == 0, (
        f"解析交易日期 {trade_date} 后 hour 应为 0，实际为 {result.hour}"
    )
    assert result.minute == 0, (
        f"解析交易日期 {trade_date} 后 minute 应为 0，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析交易日期 {trade_date} 后 second 应为 0，实际为 {result.second}"
    )

    # 断言：必须包含 UTC 时区信息
    assert result.tzinfo is not None, (
        f"解析交易日期 {trade_date} 返回 naive datetime，缺少 tzinfo。"
        f"期望: datetime with tzinfo=timezone.utc，实际: {result}"
    )
    assert result.tzinfo == timezone.utc, (
        f"解析交易日期 {trade_date} 后 tzinfo 应为 timezone.utc，实际为 {result.tzinfo}"
    )


# ---------------------------------------------------------------------------
# 具体示例测试（非属性测试，用于明确记录失败案例）
# ---------------------------------------------------------------------------


def test_parse_datetime_concrete_example_2024_01_15():
    """
    具体示例测试：_parse_datetime("2024-01-15") 应返回 00:00:00 UTC

    **Validates: Requirements 2.1, 2.4**

    这是一个明确的失败案例，用于演示 bug 存在。
    在未修复代码上，此测试应失败。
    """
    result = LocalKlineImportService._parse_datetime("2024-01-15")

    # 期望：2024-01-15 00:00:00+00:00
    expected = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    assert result == expected, (
        f"_parse_datetime('2024-01-15') 应返回 {expected}，实际返回 {result}。"
        f"Bug: 返回 naive datetime，存入数据库后被解释为 UTC，"
        f"但不同数据源对日期的时区假设不同，导致重复存储。"
    )


def test_parse_trade_date_concrete_example_20240115():
    """
    具体示例测试：_parse_trade_date(20240115) 应返回 00:00:00 UTC

    **Validates: Requirements 2.1, 2.4**

    这是一个明确的失败案例，用于演示 bug 存在。
    在未修复代码上，此测试应失败。
    """
    result = TushareAdapter._parse_trade_date(20240115)

    # 期望：2024-01-15 00:00:00+00:00
    expected = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    assert result == expected, (
        f"_parse_trade_date(20240115) 应返回 {expected}，实际返回 {result}。"
        f"Bug: 返回 naive datetime，存入数据库后被解释为 UTC，"
        f"但不同数据源对日期的时区假设不同，导致重复存储。"
    )
