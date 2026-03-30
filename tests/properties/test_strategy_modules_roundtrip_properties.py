# Feature: a-share-quant-trading-system, Property 81: enabled_modules 持久化 round-trip
"""
策略模块持久化 round-trip 属性测试（Hypothesis）

属性 81：enabled_modules 持久化 round-trip

**Validates: Requirements 27.4, 27.6**

对任意合法的 enabled_modules 值，通过 POST 创建策略后，再通过 GET 查询该策略，
返回的 enabled_modules 应与创建时传入的值完全一致；通过 PUT 更新 enabled_modules
后再查询，返回值应与更新时传入的值完全一致。
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
# 属性 81a：POST 创建后 GET 查询 round-trip
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(modules=_modules_subset_st, name=_strategy_name_st)
def test_post_then_get_roundtrip(modules: list[str], name: str):
    """
    # Feature: a-share-quant-trading-system, Property 81: enabled_modules 持久化 round-trip

    **Validates: Requirements 27.4, 27.6**

    对任意合法 enabled_modules，通过 POST 创建策略后 GET 查询返回值一致。
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        _strategies.clear()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            # POST 创建策略
            create_resp = await client.post(
                "/api/v1/strategies",
                json={
                    "name": name,
                    "config": {"factors": [], "logic": "AND"},
                    "enabled_modules": modules,
                },
            )
            assert create_resp.status_code == 201, (
                f"POST expected 201, got {create_resp.status_code}: {create_resp.text}"
            )
            created = create_resp.json()
            strategy_id = created["id"]

            # GET 查询策略
            get_resp = await client.get(f"/api/v1/strategies/{strategy_id}")
            assert get_resp.status_code == 200, (
                f"GET expected 200, got {get_resp.status_code}: {get_resp.text}"
            )
            fetched = get_resp.json()

        return created, fetched

    created, fetched = asyncio.run(_run())

    # enabled_modules 应与创建时传入的值完全一致
    assert sorted(fetched["enabled_modules"]) == sorted(modules), (
        f"GET round-trip mismatch: expected {sorted(modules)}, "
        f"got {sorted(fetched['enabled_modules'])}"
    )


# ---------------------------------------------------------------------------
# 属性 81b：PUT 更新后 GET 查询 round-trip
# ---------------------------------------------------------------------------


@h_settings(max_examples=100)
@given(
    initial_modules=_modules_subset_st,
    updated_modules=_modules_subset_st,
    name=_strategy_name_st,
)
def test_put_then_get_roundtrip(
    initial_modules: list[str], updated_modules: list[str], name: str
):
    """
    # Feature: a-share-quant-trading-system, Property 81: enabled_modules 持久化 round-trip

    **Validates: Requirements 27.4, 27.6**

    创建策略后通过 PUT 更新 enabled_modules，再 GET 查询返回值应与 PUT 值一致。
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        _strategies.clear()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            # POST 创建策略（使用 initial_modules）
            create_resp = await client.post(
                "/api/v1/strategies",
                json={
                    "name": name,
                    "config": {"factors": [], "logic": "AND"},
                    "enabled_modules": initial_modules,
                },
            )
            assert create_resp.status_code == 201, (
                f"POST expected 201, got {create_resp.status_code}: {create_resp.text}"
            )
            strategy_id = create_resp.json()["id"]

            # PUT 更新 enabled_modules
            put_resp = await client.put(
                f"/api/v1/strategies/{strategy_id}",
                json={"enabled_modules": updated_modules},
            )
            assert put_resp.status_code == 200, (
                f"PUT expected 200, got {put_resp.status_code}: {put_resp.text}"
            )

            # GET 查询策略
            get_resp = await client.get(f"/api/v1/strategies/{strategy_id}")
            assert get_resp.status_code == 200, (
                f"GET expected 200, got {get_resp.status_code}: {get_resp.text}"
            )
            fetched = get_resp.json()

        return fetched

    fetched = asyncio.run(_run())

    # enabled_modules 应与 PUT 更新时传入的值完全一致
    assert sorted(fetched["enabled_modules"]) == sorted(updated_modules), (
        f"PUT round-trip mismatch: expected {sorted(updated_modules)}, "
        f"got {sorted(fetched['enabled_modules'])}"
    )
