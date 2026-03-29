"""
数据源集成属性测试（Hypothesis）

属性 49：数据源配置驱动初始化

**Validates: Requirements 1.7, 1.8**

验证 TushareAdapter 使用 Settings 中的 tushare_api_token 和 tushare_api_url 初始化，
AkShareAdapter 使用 akshare_request_timeout 初始化，不包含硬编码凭证。
"""

from __future__ import annotations

import inspect
import re

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.config import settings
from app.services.data_engine.tushare_adapter import TushareAdapter
from app.services.data_engine.akshare_adapter import AkShareAdapter


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 有效的 API Token：非空字母数字字符串
_api_token_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
    min_size=8,
    max_size=64,
)

# 有效的 API URL：http(s) 开头的 URL
_api_url_strategy = st.builds(
    lambda scheme, host, port: f"{scheme}://{host}:{port}",
    scheme=st.sampled_from(["http", "https"]),
    host=st.sampled_from(["api.tushare.pro", "tushare.example.com", "10.0.0.1", "localhost"]),
    port=st.integers(min_value=80, max_value=65535),
)

# 有效的超时时间：正浮点数
_timeout_strategy = st.floats(min_value=1.0, max_value=300.0, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# 属性 49：数据源配置驱动初始化
# ---------------------------------------------------------------------------


@h_settings(max_examples=50)
@given(token=_api_token_strategy, url=_api_url_strategy)
def test_tushare_adapter_uses_explicit_config(token: str, url: str):
    """
    # Feature: a-share-quant-trading-system, Property 49: 数据源配置驱动初始化

    **Validates: Requirements 1.7**

    对任意有效的 API Token 和 API URL，当显式传入时，
    TushareAdapter 应使用传入的值初始化，而非硬编码值。
    """
    adapter = TushareAdapter(api_token=token, api_url=url)

    assert adapter._api_token == token, (
        f"TushareAdapter 应使用传入的 api_token='{token}'，"
        f"实际使用 '{adapter._api_token}'"
    )
    assert adapter._api_url == url.rstrip("/"), (
        f"TushareAdapter 应使用传入的 api_url='{url}'，"
        f"实际使用 '{adapter._api_url}'"
    )


@h_settings(max_examples=50)
@given(timeout=_timeout_strategy)
def test_akshare_adapter_uses_explicit_config(timeout: float):
    """
    # Feature: a-share-quant-trading-system, Property 49: 数据源配置驱动初始化

    **Validates: Requirements 1.8**

    对任意有效的超时时间，当显式传入时，
    AkShareAdapter 应使用传入的值初始化，而非硬编码值。
    """
    adapter = AkShareAdapter(timeout=timeout)

    assert adapter._timeout == timeout, (
        f"AkShareAdapter 应使用传入的 timeout={timeout}，"
        f"实际使用 {adapter._timeout}"
    )


def test_tushare_adapter_defaults_from_settings():
    """
    # Feature: a-share-quant-trading-system, Property 49: 数据源配置驱动初始化

    **Validates: Requirements 1.7**

    当不传入参数时，TushareAdapter 应从 Settings 单例读取
    tushare_api_token 和 tushare_api_url 配置。
    """
    adapter = TushareAdapter()

    assert adapter._api_token == settings.tushare_api_token, (
        f"TushareAdapter 默认应使用 settings.tushare_api_token='{settings.tushare_api_token}'，"
        f"实际使用 '{adapter._api_token}'"
    )
    expected_url = settings.tushare_api_url.rstrip("/")
    assert adapter._api_url == expected_url, (
        f"TushareAdapter 默认应使用 settings.tushare_api_url='{expected_url}'，"
        f"实际使用 '{adapter._api_url}'"
    )


def test_akshare_adapter_defaults_from_settings():
    """
    # Feature: a-share-quant-trading-system, Property 49: 数据源配置驱动初始化

    **Validates: Requirements 1.8**

    当不传入参数时，AkShareAdapter 应从 Settings 单例读取
    akshare_request_timeout 配置。
    """
    adapter = AkShareAdapter()

    assert adapter._timeout == settings.akshare_request_timeout, (
        f"AkShareAdapter 默认应使用 settings.akshare_request_timeout={settings.akshare_request_timeout}，"
        f"实际使用 {adapter._timeout}"
    )


def test_tushare_adapter_no_hardcoded_credentials():
    """
    # Feature: a-share-quant-trading-system, Property 49: 数据源配置驱动初始化

    **Validates: Requirements 1.7**

    TushareAdapter 源代码中不应包含硬编码的 API Token 或 API 地址字面量。
    凭证和地址应全部通过 settings 或构造函数参数注入。
    """
    source = inspect.getsource(TushareAdapter)

    # 排除注释和文档字符串后，检查是否有硬编码的 token 模式
    # 典型硬编码模式：直接赋值一个看起来像 token 的长字符串
    hardcoded_token_pattern = re.compile(
        r'["\'][a-f0-9]{32,}["\']',  # 32+ 位十六进制字符串（典型 API token）
        re.IGNORECASE,
    )
    matches = hardcoded_token_pattern.findall(source)
    assert not matches, (
        f"TushareAdapter 源代码中发现疑似硬编码 API Token: {matches}"
    )

    # 检查是否有硬编码的 tushare API 地址（排除 settings 引用和注释）
    # 只检查赋值语句中的硬编码 URL
    lines = source.split("\n")
    for line in lines:
        stripped = line.strip()
        # 跳过注释和文档字符串
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
            continue
        # 检查是否在非默认参数位置硬编码了 tushare URL
        if "api.tushare.pro" in stripped and "settings." not in stripped and "or " not in stripped:
            # 允许在默认参数中出现（如 api_url: str | None = None）
            if "def __init__" not in stripped and "None" not in stripped:
                assert False, (
                    f"TushareAdapter 源代码中发现硬编码 API 地址: {stripped}"
                )


def test_akshare_adapter_no_hardcoded_config():
    """
    # Feature: a-share-quant-trading-system, Property 49: 数据源配置驱动初始化

    **Validates: Requirements 1.8**

    AkShareAdapter 源代码中不应包含硬编码的超时时间等运行配置参数。
    运行配置应全部通过 settings 或构造函数参数注入。
    """
    source = inspect.getsource(AkShareAdapter)

    # 检查 __init__ 方法中超时值是否来自 settings 或参数
    # 不应出现类似 self._timeout = 30 这样的硬编码
    hardcoded_timeout_pattern = re.compile(
        r'self\._timeout\s*=\s*\d+',  # self._timeout = <数字>
    )
    matches = hardcoded_timeout_pattern.findall(source)
    assert not matches, (
        f"AkShareAdapter 源代码中发现硬编码超时配置: {matches}"
    )
