# Feature: data-manage-dual-source-integration, Property 69: 基本面 API 响应包含全部必需字段
"""
基本面 API 响应字段完整性属性测试（Hypothesis）

属性 69：基本面 API 响应包含全部必需字段

**Validates: Requirements 26.6**

对任意合法的 FundamentalsData 实例，通过 mock DataSourceRouter.fetch_fundamentals
调用端点后，响应 JSON 应包含全部 8 个必需字段：
symbol, pe_ttm, pb, roe, market_cap, revenue_growth, net_profit_growth, report_period
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.data_engine.fundamental_adapter import FundamentalsData


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# A股股票代码策略：6位数字 + 后缀
_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ)", fullmatch=True)

# 可选 Decimal 策略
_optional_decimal = st.one_of(
    st.none(),
    st.decimals(
        min_value=Decimal("-9999"),
        max_value=Decimal("9999999"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
)

# 可选字符串策略
_optional_str = st.one_of(st.none(), st.text(min_size=1, max_size=20))

# 报告期策略
_report_period_st = st.one_of(
    st.none(),
    st.from_regex(r"20[12]\d Q[1-4]", fullmatch=True),
)

# FundamentalsData 策略
_fundamentals_st = st.builds(
    FundamentalsData,
    symbol=_symbol_st,
    name=_optional_str,
    pe_ttm=_optional_decimal,
    pb=_optional_decimal,
    roe=_optional_decimal,
    market_cap=_optional_decimal,
    revenue_yoy=_optional_decimal,
    net_profit_yoy=_optional_decimal,
    updated_at=st.one_of(st.none(), st.just(datetime(2024, 6, 1, 12, 0, 0))),
    raw=st.one_of(
        st.just({}),
        st.builds(lambda rp: {"report_period": rp}, rp=_report_period_st),
    ),
)

# 必需字段集合
REQUIRED_FIELDS = {
    "symbol",
    "pe_ttm",
    "pb",
    "roe",
    "market_cap",
    "revenue_growth",
    "net_profit_growth",
    "report_period",
}


# ---------------------------------------------------------------------------
# 属性 69：基本面 API 响应包含全部必需字段
# ---------------------------------------------------------------------------


@h_settings(max_examples=50)
@given(fund_data=_fundamentals_st)
def test_fundamentals_api_response_contains_all_required_fields(fund_data: FundamentalsData):
    """
    # Feature: data-manage-dual-source-integration, Property 69: 基本面 API 响应包含全部必需字段

    **Validates: Requirements 26.6**

    对任意合法的 FundamentalsData，响应 JSON 应包含全部 8 个必需字段：
    symbol, pe_ttm, pb, roe, market_cap, revenue_growth, net_profit_growth, report_period
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async def _run():
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_fundamentals",
            new_callable=AsyncMock,
            return_value=fund_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    f"/api/v1/data/stock/{fund_data.symbol}/fundamentals"
                )
        return resp

    resp = asyncio.run(_run())

    # 1. 状态码 200
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    body = resp.json()

    # 2. 响应包含全部 8 个必需字段
    missing = REQUIRED_FIELDS - set(body.keys())
    assert not missing, f"响应缺少必需字段: {missing}"

    # 3. symbol 字段值与输入一致
    assert body["symbol"] == fund_data.symbol
