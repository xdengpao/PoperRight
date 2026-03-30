# Feature: a-share-quant-trading-system, Property 79: 任意模块子集均可创建策略
"""
策略模块子集创建属性测试（Hypothesis）

属性 79：任意模块子集均可创建策略

**Validates: Requirements 27.2, 27.4**

对任意五个模块标识符的子集（包括空集），当策略名称非空时，
策略创建请求应被接受（201）且返回的 enabled_modules 与请求一致。
"""

from __future__ import annotations

import asyncio

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.api.v1.screen import VALID_MODULES, _strategies

# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 从 VALID_MODULES 的幂集中生成任意子集（包括空集）
_modules_subset_st = st.frozensets(st.sampled_from(sorted(VALID_MODULES))).map(
    lambda s: sorted(s)
)

# 非空策略名称
_strategy_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
)


# ---------------------------------------------------------------------------
# Fixture：每次测试前清空内存策略存储
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_strategies():
    _strategies.clear()
    yield
    _strategies.clear()


# ---------------------------------------------------------------------------
# 属性 79：任意模块子集均可创建策略
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(modules=_modules_subset_st, name=_strategy_name_st)
def test_any_module_subset_can_create_strategy(modules: list[str], name: str):
    """
    # Feature: a-share-quant-trading-system, Property 79: 任意模块子集均可创建策略

    **Validates: Requirements 27.2, 27.4**

    对任意五个模块标识符的子集（包括空集），当策略名称非空时，
    策略创建请求应被接受（201）且返回的 enabled_modules 与请求一致。
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        _strategies.clear()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.post(
                "/api/v1/strategies",
                json={
                    "name": name,
                    "config": {"factors": [], "logic": "AND"},
                    "enabled_modules": modules,
                },
            )
        return resp

    resp = asyncio.run(_run())

    # 1. 状态码应为 201
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    body = resp.json()

    # 2. 返回的 enabled_modules 应与请求一致
    assert sorted(body["enabled_modules"]) == sorted(modules), (
        f"enabled_modules mismatch: expected {sorted(modules)}, "
        f"got {sorted(body['enabled_modules'])}"
    )

    # 3. 策略名称应与请求一致
    assert body["name"] == name
