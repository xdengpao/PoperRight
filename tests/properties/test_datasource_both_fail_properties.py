"""
双数据源均不可用时的错误处理属性测试（Hypothesis）

属性 51：双数据源均不可用时的错误处理

**Validates: Requirements 1.10**

验证当 Tushare 和 AkShare 均不可用时，DataSourceRouter：
1. 抛出 DataSourceUnavailableError
2. 记录包含两个数据源错误信息的 error 日志
3. 推送 DANGER 级别告警（通过 alert_service）
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, call

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from contextlib import contextmanager

from app.core.schemas import AlertType
from app.services.data_engine.base_adapter import DataSourceUnavailableError
from app.services.data_engine.data_source_router import DataSourceRouter


# ---------------------------------------------------------------------------
# 日志捕获上下文管理器（替代 caplog，兼容 Hypothesis）
# ---------------------------------------------------------------------------

@contextmanager
def _capture_logs(logger_name: str, level: int = logging.DEBUG):
    """捕获指定 logger 的日志记录，返回 LogRecord 列表。"""
    target_logger = logging.getLogger(logger_name)
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=level)
    target_logger.addHandler(handler)
    old_level = target_logger.level
    target_logger.setLevel(level)
    try:
        yield records
    finally:
        target_logger.removeHandler(handler)
        target_logger.setLevel(old_level)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 异常类型 + 消息
_exception_strategy = st.sampled_from([
    RuntimeError("Tushare timeout"),
    ConnectionError("connection refused"),
    TimeoutError("request timed out"),
    Exception("API error code=-1"),
    OSError("network unreachable"),
    ValueError("invalid response"),
])

# DataSourceRouter 支持的四种数据请求方法
_method_name_strategy = st.sampled_from([
    "fetch_kline",
    "fetch_fundamentals",
    "fetch_money_flow",
    "fetch_market_overview",
])


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_both_fail_adapters(
    method_name: str,
    primary_exc: Exception,
    fallback_exc: Exception,
):
    """创建 Tushare 和 AkShare 均抛异常的 mock 适配器。"""
    tushare = AsyncMock()
    akshare = AsyncMock()

    getattr(tushare, method_name).side_effect = primary_exc
    getattr(akshare, method_name).side_effect = fallback_exc

    return tushare, akshare


# ---------------------------------------------------------------------------
# 属性 51：双数据源均不可用时的错误处理
# ---------------------------------------------------------------------------


@h_settings(max_examples=50)
@given(
    method_name=_method_name_strategy,
    primary_exc=_exception_strategy,
    fallback_exc=_exception_strategy,
)
def test_both_fail_raises_datasource_unavailable_error(
    method_name: str,
    primary_exc: Exception,
    fallback_exc: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 51

    **Validates: Requirements 1.10**

    对任意数据请求方法和异常组合，当 Tushare 和 AkShare 均失败时，
    DataSourceRouter 应抛出 DataSourceUnavailableError。
    """
    tushare, akshare = _make_both_fail_adapters(method_name, primary_exc, fallback_exc)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    with pytest.raises(DataSourceUnavailableError):
        asyncio.run(router.fetch_with_fallback(method_name))

    # 验证两个数据源均被调用
    getattr(tushare, method_name).assert_awaited_once()
    getattr(akshare, method_name).assert_awaited_once()


@h_settings(max_examples=50)
@given(
    method_name=_method_name_strategy,
    primary_exc=_exception_strategy,
    fallback_exc=_exception_strategy,
)
def test_both_fail_logs_error_with_both_sources(
    method_name: str,
    primary_exc: Exception,
    fallback_exc: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 51

    **Validates: Requirements 1.10**

    当双数据源均失败时，DataSourceRouter 应记录 ERROR 级别日志，
    且日志内容包含 Tushare 和 AkShare 两个数据源的错误信息。
    """
    tushare, akshare = _make_both_fail_adapters(method_name, primary_exc, fallback_exc)
    router = DataSourceRouter(tushare=tushare, akshare=akshare)

    logger_name = "app.services.data_engine.data_source_router"
    with _capture_logs(logger_name) as records:
        with pytest.raises(DataSourceUnavailableError):
            asyncio.run(router.fetch_with_fallback(method_name))

    # 验证存在 ERROR 级别日志
    error_records = [r for r in records if r.levelno >= logging.ERROR]
    assert len(error_records) >= 1, "应至少记录一条 ERROR 日志"

    # 验证日志包含方法名和两个数据源的错误信息
    error_msg = error_records[0].message
    assert method_name in error_msg, f"日志应包含方法名 {method_name}"
    assert str(primary_exc) in error_msg, "日志应包含 Tushare 错误信息"
    assert str(fallback_exc) in error_msg, "日志应包含 AkShare 错误信息"


@h_settings(max_examples=50)
@given(
    method_name=_method_name_strategy,
    primary_exc=_exception_strategy,
    fallback_exc=_exception_strategy,
)
def test_both_fail_pushes_danger_alert(
    method_name: str,
    primary_exc: Exception,
    fallback_exc: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 51

    **Validates: Requirements 1.10**

    当双数据源均失败时，DataSourceRouter 应通过 alert_service
    推送 DANGER 级别（SYSTEM 类型）告警通知。
    """
    tushare, akshare = _make_both_fail_adapters(method_name, primary_exc, fallback_exc)
    mock_alert_service = AsyncMock()
    router = DataSourceRouter(
        tushare=tushare, akshare=akshare, alert_service=mock_alert_service
    )

    with pytest.raises(DataSourceUnavailableError):
        asyncio.run(router.fetch_with_fallback(method_name))

    # 验证 alert_service.push_alert 被调用
    mock_alert_service.push_alert.assert_awaited_once()

    # 验证告警参数
    call_kwargs = mock_alert_service.push_alert.call_args
    assert call_kwargs.kwargs.get("user_id") == "system" or (
        call_kwargs.args and call_kwargs.args[0] == "system"
    ), "告警应发送给 system 用户"

    # 提取 alert 参数（可能在 kwargs 或 args 中）
    alert = call_kwargs.kwargs.get("alert") or call_kwargs.args[1]
    assert alert.alert_type == AlertType.SYSTEM, "告警类型应为 SYSTEM"
    assert method_name in alert.message, "告警消息应包含方法名"


@h_settings(max_examples=50)
@given(
    method_name=_method_name_strategy,
    primary_exc=_exception_strategy,
    fallback_exc=_exception_strategy,
)
def test_both_fail_no_alert_service_still_raises(
    method_name: str,
    primary_exc: Exception,
    fallback_exc: Exception,
):
    """
    # Feature: a-share-quant-trading-system, Property 51

    **Validates: Requirements 1.10**

    当双数据源均失败且未配置 alert_service 时，
    DataSourceRouter 仍应正常抛出 DataSourceUnavailableError（不因缺少告警服务而崩溃）。
    """
    tushare, akshare = _make_both_fail_adapters(method_name, primary_exc, fallback_exc)
    router = DataSourceRouter(tushare=tushare, akshare=akshare, alert_service=None)

    with pytest.raises(DataSourceUnavailableError) as exc_info:
        asyncio.run(router.fetch_with_fallback(method_name))

    # 验证异常消息包含方法名
    assert method_name in str(exc_info.value)
