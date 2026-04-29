"""
Preservation 属性测试：分钟级数据时间戳保持不变

**Validates: Requirements 3.3**

Property 2: Preservation - 分钟级 K 线数据时间戳保持不变

对任意分钟级时间字符串输入：
  - `_parse_datetime("2024-01-15 09:30:00")` 应返回 datetime 对象，保持 hour=9, minute=30
  - 时间组件（hour, minute, second）应与输入字符串一致

此测试编码了需要保留的行为。在未修复代码上运行时应通过（确认基线行为）。
修复后运行应继续通过（确认无回归）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.local_kline_import import LocalKlineImportService


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 小时：0-23（分钟级 K 线交易时间通常在 9:30-15:00，但这里测试所有可能值）
_hour = st.integers(min_value=0, max_value=23)

# 分钟：0-59
_minute = st.integers(min_value=0, max_value=59)

# 秒：0-59
_second = st.integers(min_value=0, max_value=59)

# 日期：2000-01-01 到 2030-12-31
_date = st.dates(
    min_value=datetime(2000, 1, 1).date(),
    max_value=datetime(2030, 12, 31).date(),
)


def _format_time_component(value: int) -> str:
    """格式化时间组件为两位数字符串。"""
    return f"{value:02d}"


# ---------------------------------------------------------------------------
# Preservation 属性测试
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(date=_date, hour=_hour, minute=_minute)
def test_preservation_minute_level_time_components_yyyy_mm_dd_hh_mm_ss(date, hour, minute):
    """
    Property 2: Preservation - 分钟级时间字符串解析后时间组件保持不变

    **Validates: Requirements 3.3**

    GIVEN 分钟级时间字符串格式 "YYYY-MM-DD HH:MM:SS"（如 "2024-01-15 09:30:00"）
    WHEN 调用 LocalKlineImportService._parse_datetime(time_str)
    THEN 返回的 datetime 对象应满足：
      - hour 与输入一致
      - minute 与输入一致
      - second 与输入一致（默认为 0）

    此测试验证分钟级数据的时间精度不受修复影响。
    """
    time_str = f"{date.strftime('%Y-%m-%d')} {_format_time_component(hour)}:{_format_time_component(minute)}:00"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 断言：时间组件应与输入一致
    assert result.hour == hour, (
        f"解析 '{time_str}' 后 hour 应为 {hour}，实际为 {result.hour}"
    )
    assert result.minute == minute, (
        f"解析 '{time_str}' 后 minute 应为 {minute}，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{time_str}' 后 second 应为 0，实际为 {result.second}"
    )


@settings(max_examples=50)
@given(date=_date, hour=_hour, minute=_minute)
def test_preservation_minute_level_time_components_yyyy_mm_dd_hh_mm(date, hour, minute):
    """
    Property 2: Preservation - 分钟级时间字符串解析后时间组件保持不变（无秒）

    **Validates: Requirements 3.3**

    GIVEN 分钟级时间字符串格式 "YYYY-MM-DD HH:MM"（如 "2024-01-15 09:30"）
    WHEN 调用 LocalKlineImportService._parse_datetime(time_str)
    THEN 返回的 datetime 对象应满足：
      - hour 与输入一致
      - minute 与输入一致
      - second 默认为 0

    此测试验证分钟级数据的时间精度不受修复影响。
    """
    time_str = f"{date.strftime('%Y-%m-%d')} {_format_time_component(hour)}:{_format_time_component(minute)}"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 断言：时间组件应与输入一致
    assert result.hour == hour, (
        f"解析 '{time_str}' 后 hour 应为 {hour}，实际为 {result.hour}"
    )
    assert result.minute == minute, (
        f"解析 '{time_str}' 后 minute 应为 {minute}，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{time_str}' 后 second 应为 0，实际为 {result.second}"
    )


@settings(max_examples=50)
@given(date=_date, hour=_hour, minute=_minute)
def test_preservation_minute_level_time_components_yyyy_slash_mm_slash_dd_hh_mm_ss(date, hour, minute):
    """
    Property 2: Preservation - 分钟级时间字符串解析后时间组件保持不变（斜杠格式）

    **Validates: Requirements 3.3**

    GIVEN 分钟级时间字符串格式 "YYYY/MM/DD HH:MM:SS"（如 "2024/01/15 09:30:00"）
    WHEN 调用 LocalKlineImportService._parse_datetime(time_str)
    THEN 返回的 datetime 对象应满足：
      - hour 与输入一致
      - minute 与输入一致
      - second 与输入一致（默认为 0）

    此测试验证分钟级数据的时间精度不受修复影响。
    """
    time_str = f"{date.strftime('%Y/%m/%d')} {_format_time_component(hour)}:{_format_time_component(minute)}:00"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 断言：时间组件应与输入一致
    assert result.hour == hour, (
        f"解析 '{time_str}' 后 hour 应为 {hour}，实际为 {result.hour}"
    )
    assert result.minute == minute, (
        f"解析 '{time_str}' 后 minute 应为 {minute}，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{time_str}' 后 second 应为 0，实际为 {result.second}"
    )


@settings(max_examples=50)
@given(date=_date, hour=_hour, minute=_minute)
def test_preservation_minute_level_time_components_yyyymmdd_hh_mm_ss(date, hour, minute):
    """
    Property 2: Preservation - 分钟级时间字符串解析后时间组件保持不变（紧凑格式）

    **Validates: Requirements 3.3**

    GIVEN 分钟级时间字符串格式 "YYYYMMDD HH:MM:SS"（如 "20240115 09:30:00"）
    WHEN 调用 LocalKlineImportService._parse_datetime(time_str)
    THEN 返回的 datetime 对象应满足：
      - hour 与输入一致
      - minute 与输入一致
      - second 与输入一致（默认为 0）

    此测试验证分钟级数据的时间精度不受修复影响。
    """
    time_str = f"{date.strftime('%Y%m%d')} {_format_time_component(hour)}:{_format_time_component(minute)}:00"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 断言：时间组件应与输入一致
    assert result.hour == hour, (
        f"解析 '{time_str}' 后 hour 应为 {hour}，实际为 {result.hour}"
    )
    assert result.minute == minute, (
        f"解析 '{time_str}' 后 minute 应为 {minute}，实际为 {result.minute}"
    )
    assert result.second == 0, (
        f"解析 '{time_str}' 后 second 应为 0，实际为 {result.second}"
    )


# ---------------------------------------------------------------------------
# 具体示例测试（非属性测试，用于明确记录保留案例）
# ---------------------------------------------------------------------------


def test_preservation_concrete_example_09_30():
    """
    具体示例测试：_parse_datetime("2024-01-15 09:30:00") 应保持时间组件

    **Validates: Requirements 3.3**

    这是一个明确的保留案例，用于验证分钟级数据时间精度不受影响。
    在未修复代码上，此测试应通过。
    """
    time_str = "2024-01-15 09:30:00"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 期望：2024-01-15 09:30:00（时间组件保持不变）
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 9, f"hour 应为 9，实际为 {result.hour}"
    assert result.minute == 30, f"minute 应为 30，实际为 {result.minute}"
    assert result.second == 0, f"second 应为 0，实际为 {result.second}"


def test_preservation_concrete_example_14_55():
    """
    具体示例测试：_parse_datetime("2024-01-15 14:55:00") 应保持时间组件

    **Validates: Requirements 3.3**

    这是一个明确的保留案例，用于验证分钟级数据时间精度不受影响。
    在未修复代码上，此测试应通过。
    """
    time_str = "2024-01-15 14:55:00"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 期望：2024-01-15 14:55:00（时间组件保持不变）
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 14, f"hour 应为 14，实际为 {result.hour}"
    assert result.minute == 55, f"minute 应为 55，实际为 {result.minute}"
    assert result.second == 0, f"second 应为 0，实际为 {result.second}"


def test_preservation_concrete_example_midnight():
    """
    具体示例测试：_parse_datetime("2024-01-15 00:00:00") 应保持时间组件

    **Validates: Requirements 3.3**

    这是一个边界案例：午夜时间（00:00:00）与日线数据时间戳相同。
    验证即使时间组件为 0，分钟级数据的时间精度仍应保持。
    在未修复代码上，此测试应通过。
    """
    time_str = "2024-01-15 00:00:00"
    result = LocalKlineImportService._parse_datetime(time_str)

    # 期望：2024-01-15 00:00:00（时间组件保持不变）
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 0, f"hour 应为 0，实际为 {result.hour}"
    assert result.minute == 0, f"minute 应为 0，实际为 {result.minute}"
    assert result.second == 0, f"second 应为 0，实际为 {result.second}"
