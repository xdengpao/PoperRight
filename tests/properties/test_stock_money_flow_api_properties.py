# Feature: a-share-quant-trading-system, Property 70: 资金流向 API 记录数与字段完整性
"""
资金流向 API 属性测试（Hypothesis）

属性 70：资金流向 API 返回记录数不超过 days 参数

**Validates: Requirements 26.7**

对任意合法的 days（1–60），返回 records 长度 ≤ days，
每条记录包含全部 6 个字段：trade_date, main_net_inflow, north_net_inflow,
large_order_ratio, super_large_inflow, large_inflow。
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.data_engine.money_flow_adapter import MoneyFlowData


# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

_valid_days = st.integers(min_value=1, max_value=60)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _make_flow(symbol: str, trade_date: date) -> MoneyFlowData:
    """创建测试用 MoneyFlowData 实例，包含全部字段。"""
    return MoneyFlowData(
        symbol=symbol,
        trade_date=trade_date,
        main_net_inflow=Decimal("5000000"),
        north_net_inflow=Decimal("2000000"),
        large_order_ratio=Decimal("35.5"),
        large_order_net=Decimal("3000000"),
        updated_at=datetime(2024, 6, 1, 12, 0, 0),
        raw={"name": "测试股票"},
    )


EXPECTED_FIELDS = {
    "trade_date",
    "main_net_inflow",
    "north_net_inflow",
    "large_order_ratio",
    "super_large_inflow",
    "large_inflow",
}


# ---------------------------------------------------------------------------
# 属性 70：资金流向 API 返回记录数不超过 days 参数
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(days=_valid_days)
def test_money_flow_records_count_and_fields(days: int):
    """
    # Feature: a-share-quant-trading-system, Property 70: 资金流向 API 记录数与字段完整性

    **Validates: Requirements 26.7**

    对任意合法的 days（1–60）：
    1. 返回 records 长度 ≤ days
    2. 每条记录包含全部 6 个字段
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async def mock_fetch(symbol: str, td: date) -> MoneyFlowData:
        return _make_flow(symbol, td)

    async def _run():
        with patch(
            "app.api.v1.data.DataSourceRouter.fetch_money_flow",
            new_callable=AsyncMock,
            side_effect=mock_fetch,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    f"/api/v1/data/stock/600519.SH/money-flow?days={days}"
                )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 200
    data = resp.json()

    # 1. records 长度 ≤ days
    assert len(data["records"]) <= days

    # 2. 每条记录包含全部 6 个字段
    for record in data["records"]:
        assert EXPECTED_FIELDS.issubset(record.keys()), (
            f"记录缺少字段: {EXPECTED_FIELDS - record.keys()}"
        )
