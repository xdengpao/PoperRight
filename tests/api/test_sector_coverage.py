"""
板块数据源覆盖率 API 单元测试

覆盖：
- GET /sector/coverage — 数据源覆盖率统计

Validates: Requirements 16.2
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# 辅助：构造 mock pg_session
# ---------------------------------------------------------------------------


def _make_scalar_result(value):
    """构造一个 mock execute 返回对象，其 .scalar() 返回指定值。"""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _build_mock_session(ds_data: dict[str, dict]) -> AsyncMock:
    """
    构造 mock pg_session，根据 SQL 查询内容返回对应的统计值。

    ds_data 格式:
    {
        "DC": {
            "total_sectors": 1030,
            "latest_date": date(2024, 6, 15),
            "sectors_with": 1030,
            "total_stocks": 5882,
        },
        ...
    }

    endpoint 对每个数据源执行 4 次查询（按顺序）：
    1. total_sectors (count from SectorInfo)
    2. latest_date (max trade_date from SectorConstituent)
    3. sectors_with (count distinct sector_code) — 仅当 latest_date 非 None
    4. total_stocks (count distinct symbol) — 仅当 latest_date 非 None
    """
    session = AsyncMock()
    results = []
    for ds in ["DC", "TI", "TDX"]:
        info = ds_data.get(ds, {})
        total_sectors = info.get("total_sectors", 0)
        latest_date = info.get("latest_date", None)
        sectors_with = info.get("sectors_with", 0)
        total_stocks = info.get("total_stocks", 0)

        results.append(_make_scalar_result(total_sectors))
        results.append(_make_scalar_result(latest_date))
        if latest_date is not None:
            results.append(_make_scalar_result(sectors_with))
            results.append(_make_scalar_result(total_stocks))

    session.execute = AsyncMock(side_effect=results)
    return session


# ---------------------------------------------------------------------------
# 16.2 — GET /sector/coverage
# ---------------------------------------------------------------------------


class TestGetSectorCoverage:
    """板块数据源覆盖率统计端点测试。Validates: Requirements 16.2"""

    @pytest.mark.asyncio
    async def test_returns_all_three_data_sources(self):
        """响应包含 DC、TI、TDX 三个数据源的统计。"""
        mock_session = _build_mock_session(
            {
                "DC": {
                    "total_sectors": 1030,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 1030,
                    "total_stocks": 5882,
                },
                "TI": {
                    "total_sectors": 1724,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 90,
                    "total_stocks": 5755,
                },
                "TDX": {
                    "total_sectors": 615,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 615,
                    "total_stocks": 7122,
                },
            }
        )

        from app.core.database import get_pg_session

        async def _override():
            yield mock_session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/coverage")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        sources = data["sources"]
        assert len(sources) == 3

        ds_names = [s["data_source"] for s in sources]
        assert ds_names == ["DC", "TI", "TDX"]

    @pytest.mark.asyncio
    async def test_response_structure_contains_required_fields(self):
        """每个数据源统计包含 data_source、total_sectors、sectors_with_constituents、total_stocks、coverage_ratio 字段。"""
        mock_session = _build_mock_session(
            {
                "DC": {
                    "total_sectors": 500,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 400,
                    "total_stocks": 3000,
                },
                "TI": {
                    "total_sectors": 200,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 50,
                    "total_stocks": 1000,
                },
                "TDX": {
                    "total_sectors": 300,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 300,
                    "total_stocks": 4000,
                },
            }
        )

        from app.core.database import get_pg_session

        async def _override():
            yield mock_session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/coverage")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        required_fields = {
            "data_source",
            "total_sectors",
            "sectors_with_constituents",
            "total_stocks",
            "coverage_ratio",
        }
        for source in data["sources"]:
            assert required_fields.issubset(source.keys()), (
                f"缺少必要字段: {required_fields - source.keys()}"
            )

        # 验证 DC 的具体数值
        dc = data["sources"][0]
        assert dc["data_source"] == "DC"
        assert dc["total_sectors"] == 500
        assert dc["sectors_with_constituents"] == 400
        assert dc["total_stocks"] == 3000
        assert dc["coverage_ratio"] == round(400 / 500, 4)

    @pytest.mark.asyncio
    async def test_coverage_ratio_computation(self):
        """coverage_ratio 正确计算为 sectors_with_constituents / total_sectors。"""
        mock_session = _build_mock_session(
            {
                "DC": {
                    "total_sectors": 1000,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 750,
                    "total_stocks": 5000,
                },
                "TI": {
                    "total_sectors": 1724,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 90,
                    "total_stocks": 5755,
                },
                "TDX": {
                    "total_sectors": 615,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 615,
                    "total_stocks": 7122,
                },
            }
        )

        from app.core.database import get_pg_session

        async def _override():
            yield mock_session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/coverage")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        sources = resp.json()["sources"]

        dc = sources[0]
        assert dc["coverage_ratio"] == round(750 / 1000, 4)

        ti = sources[1]
        assert ti["coverage_ratio"] == round(90 / 1724, 4)

        tdx = sources[2]
        # 615 / 615 = 1.0
        assert tdx["coverage_ratio"] == 1.0

    @pytest.mark.asyncio
    async def test_empty_data_source_returns_zero_values(self):
        """某数据源无 SectorInfo 记录时返回零值，coverage_ratio 为 0.0。"""
        mock_session = _build_mock_session(
            {
                "DC": {
                    "total_sectors": 100,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 80,
                    "total_stocks": 2000,
                },
                "TI": {
                    "total_sectors": 0,
                    "latest_date": None,
                },
                "TDX": {
                    "total_sectors": 0,
                    "latest_date": None,
                },
            }
        )

        from app.core.database import get_pg_session

        async def _override():
            yield mock_session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/coverage")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        sources = resp.json()["sources"]

        # TI — 无数据
        ti = sources[1]
        assert ti["data_source"] == "TI"
        assert ti["total_sectors"] == 0
        assert ti["sectors_with_constituents"] == 0
        assert ti["total_stocks"] == 0
        assert ti["coverage_ratio"] == 0.0

        # TDX — 无数据
        tdx = sources[2]
        assert tdx["data_source"] == "TDX"
        assert tdx["total_sectors"] == 0
        assert tdx["sectors_with_constituents"] == 0
        assert tdx["total_stocks"] == 0
        assert tdx["coverage_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_no_constituent_data_returns_zero_coverage(self):
        """数据源有板块但无成分股数据时，sectors_with 和 total_stocks 为 0。"""
        mock_session = _build_mock_session(
            {
                "DC": {
                    "total_sectors": 500,
                    "latest_date": None,  # 无成分股数据
                },
                "TI": {
                    "total_sectors": 1724,
                    "latest_date": None,
                },
                "TDX": {
                    "total_sectors": 615,
                    "latest_date": None,
                },
            }
        )

        from app.core.database import get_pg_session

        async def _override():
            yield mock_session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/coverage")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        sources = resp.json()["sources"]

        for source in sources:
            assert source["sectors_with_constituents"] == 0
            assert source["total_stocks"] == 0
            assert source["coverage_ratio"] == 0.0
            # total_sectors 仍有值
            assert source["total_sectors"] > 0
