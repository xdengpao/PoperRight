"""
板块类型查询 & 覆盖率增强 API 单元测试

覆盖：
- GET /sector/types?data_source=THS — 板块类型列表（需求 22.8）
- GET /sector/types?data_source=DC  — DC 数据源板块类型列表
- GET /sector/coverage — type_breakdown 字段验证（需求 22.10）

Validates: Requirements 22.8, 22.10
"""

from __future__ import annotations

from collections import namedtuple
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# 辅助：构造 mock 查询结果行
# ---------------------------------------------------------------------------

# sector/types 端点返回的行结构
TypeRow = namedtuple("TypeRow", ["sector_type", "count"])

# sector/coverage 端点中 type_breakdown 查询返回的行结构
TypeSectorCountRow = namedtuple("TypeSectorCountRow", ["sector_type", "sector_count"])
TypeStockCountRow = namedtuple("TypeStockCountRow", ["sector_type", "stock_count"])


def _make_scalar_result(value):
    """构造一个 mock execute 返回对象，其 .scalar() 返回指定值。"""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_all_result(rows):
    """构造一个 mock execute 返回对象，其 .all() 返回指定行列表。"""
    result = MagicMock()
    result.all.return_value = rows
    return result


# ---------------------------------------------------------------------------
# 22.8 — GET /sector/types
# ---------------------------------------------------------------------------


class TestGetSectorTypes:
    """板块类型查询端点测试。Validates: Requirements 22.8"""

    @pytest.mark.asyncio
    async def test_ths_returns_correct_types_with_chinese_labels(self):
        """THS 数据源返回正确的 sector_type 列表和中文标签。"""
        # 模拟 THS 数据源下的板块类型分布（按 count 降序，与 SQL ORDER BY 一致）
        mock_rows = [
            TypeRow(sector_type="N", count=500),
            TypeRow(sector_type="I", count=120),
            TypeRow(sector_type="TH", count=80),
            TypeRow(sector_type="S", count=50),
            TypeRow(sector_type="R", count=31),
        ]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result(mock_rows))

        from app.core.database import get_pg_session

        async def _override():
            yield session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/types", params={"data_source": "THS"}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()

        # 验证返回列表长度
        assert len(data) == 5

        # 验证每个条目包含必要字段
        for item in data:
            assert "sector_type" in item
            assert "label" in item
            assert "count" in item

        # 验证中文标签映射正确
        label_map = {item["sector_type"]: item["label"] for item in data}
        assert label_map["N"] == "概念板块"
        assert label_map["I"] == "行业板块"
        assert label_map["R"] == "地域板块"
        assert label_map["S"] == "风格板块"
        assert label_map["TH"] == "主题板块"

        # 验证数量正确（按降序排列）
        counts = [item["count"] for item in data]
        assert counts == [500, 120, 80, 50, 31]

    @pytest.mark.asyncio
    async def test_dc_returns_correct_types(self):
        """DC 数据源返回正确的板块类型列表。"""
        mock_rows = [
            TypeRow(sector_type="概念板块", count=600),
            TypeRow(sector_type="行业板块", count=300),
            TypeRow(sector_type="地域板块", count=120),
        ]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result(mock_rows))

        from app.core.database import get_pg_session

        async def _override():
            yield session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/types", params={"data_source": "DC"}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()

        assert len(data) == 3

        # DC 的中文值直接作为标签
        label_map = {item["sector_type"]: item["label"] for item in data}
        assert label_map["概念板块"] == "概念板块"
        assert label_map["行业板块"] == "行业板块"
        assert label_map["地域板块"] == "地域板块"

    @pytest.mark.asyncio
    async def test_ti_returns_level_types(self):
        """TI（申万行业）数据源返回 L1/L2/L3 类型和中文标签。"""
        mock_rows = [
            TypeRow(sector_type="L1", count=31),
            TypeRow(sector_type="L2", count=134),
            TypeRow(sector_type="L3", count=350),
        ]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result(mock_rows))

        from app.core.database import get_pg_session

        async def _override():
            yield session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/types", params={"data_source": "TI"}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()

        assert len(data) == 3

        label_map = {item["sector_type"]: item["label"] for item in data}
        assert label_map["L1"] == "一级行业"
        assert label_map["L2"] == "二级行业"
        assert label_map["L3"] == "三级行业"

    @pytest.mark.asyncio
    async def test_empty_data_source_returns_empty_list(self):
        """数据源下无板块时返回空列表。"""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result([]))

        from app.core.database import get_pg_session

        async def _override():
            yield session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/types", params={"data_source": "CI"}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_null_sector_type_returns_unclassified_label(self):
        """sector_type 为 None 时标签显示为"未分类"。"""
        mock_rows = [
            TypeRow(sector_type=None, count=15),
            TypeRow(sector_type="I", count=100),
        ]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_all_result(mock_rows))

        from app.core.database import get_pg_session

        async def _override():
            yield session

        app.dependency_overrides[get_pg_session] = _override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/types", params={"data_source": "THS"}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()

        # 找到 sector_type 为 None 的条目
        null_item = [item for item in data if item["sector_type"] is None]
        assert len(null_item) == 1
        assert null_item[0]["label"] == "未分类"
        assert null_item[0]["count"] == 15

    @pytest.mark.asyncio
    async def test_missing_data_source_param_returns_422(self):
        """缺少 data_source 参数时返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/api/v1/sector/types")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 22.10 — GET /sector/coverage — type_breakdown 字段验证
# ---------------------------------------------------------------------------


def _build_coverage_mock_session(ds_data: dict[str, dict]) -> AsyncMock:
    """
    构造 mock pg_session，用于覆盖率端点测试。

    ds_data 格式:
    {
        "DC": {
            "total_sectors": 1030,
            "latest_date": date(2024, 6, 15),
            "sectors_with": 1030,
            "total_stocks": 5882,
            "type_sector_rows": [TypeSectorCountRow(...)],
            "type_stock_rows": [TypeStockCountRow(...)],
        },
        ...
    }

    覆盖率端点对每个数据源（DC, THS, TDX, TI, CI）执行以下查询：
    1. total_sectors (scalar)
    2. latest_date (scalar)
    3. sectors_with (scalar) — 仅当 latest_date 非 None
    4. total_stocks (scalar) — 仅当 latest_date 非 None
    5. type_sector_count_rows (.all())
    6. type_stock_count_rows (.all())
    """
    session = AsyncMock()
    results = []

    for ds in ["DC", "THS", "TDX", "TI", "CI"]:
        info = ds_data.get(ds, {})
        total_sectors = info.get("total_sectors", 0)
        latest_date = info.get("latest_date", None)
        sectors_with = info.get("sectors_with", 0)
        total_stocks = info.get("total_stocks", 0)
        type_sector_rows = info.get("type_sector_rows", [])
        type_stock_rows = info.get("type_stock_rows", [])

        # 查询 1: total_sectors
        results.append(_make_scalar_result(total_sectors))
        # 查询 2: latest_date
        results.append(_make_scalar_result(latest_date))
        if latest_date is not None:
            # 查询 3: sectors_with
            results.append(_make_scalar_result(sectors_with))
            # 查询 4: total_stocks
            results.append(_make_scalar_result(total_stocks))
        # 查询 5: type_sector_count_rows
        results.append(_make_all_result(type_sector_rows))
        # 查询 6: type_stock_count_rows
        results.append(_make_all_result(type_stock_rows))

    session.execute = AsyncMock(side_effect=results)
    return session


class TestGetSectorCoverageTypeBreakdown:
    """覆盖率端点 type_breakdown 字段测试。Validates: Requirements 22.10"""

    @pytest.mark.asyncio
    async def test_coverage_contains_type_breakdown_field(self):
        """每个数据源的统计中包含 type_breakdown 字段。"""
        mock_session = _build_coverage_mock_session(
            {
                "DC": {
                    "total_sectors": 500,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 400,
                    "total_stocks": 3000,
                    "type_sector_rows": [
                        TypeSectorCountRow(sector_type="概念板块", sector_count=300),
                        TypeSectorCountRow(sector_type="行业板块", sector_count=200),
                    ],
                    "type_stock_rows": [
                        TypeStockCountRow(sector_type="概念板块", stock_count=2500),
                        TypeStockCountRow(sector_type="行业板块", stock_count=1800),
                    ],
                },
                "THS": {
                    "total_sectors": 100,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 80,
                    "total_stocks": 2000,
                    "type_sector_rows": [
                        TypeSectorCountRow(sector_type="I", sector_count=50),
                        TypeSectorCountRow(sector_type="N", sector_count=50),
                    ],
                    "type_stock_rows": [
                        TypeStockCountRow(sector_type="I", stock_count=1500),
                        TypeStockCountRow(sector_type="N", stock_count=1800),
                    ],
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

        # 验证所有 5 个数据源都有 type_breakdown 字段
        for source in data["sources"]:
            assert "type_breakdown" in source, (
                f"数据源 {source['data_source']} 缺少 type_breakdown 字段"
            )

    @pytest.mark.asyncio
    async def test_type_breakdown_items_have_required_fields(self):
        """type_breakdown 中每个条目包含 sector_type、label、sector_count、stock_count 字段。"""
        mock_session = _build_coverage_mock_session(
            {
                "THS": {
                    "total_sectors": 850,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 820,
                    "total_stocks": 4500,
                    "type_sector_rows": [
                        TypeSectorCountRow(sector_type="I", sector_count=120),
                        TypeSectorCountRow(sector_type="N", sector_count=500),
                        TypeSectorCountRow(sector_type="R", sector_count=31),
                    ],
                    "type_stock_rows": [
                        TypeStockCountRow(sector_type="I", stock_count=3800),
                        TypeStockCountRow(sector_type="N", stock_count=4200),
                        TypeStockCountRow(sector_type="R", stock_count=2500),
                    ],
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

        # 找到 THS 数据源
        ths_source = next(
            s for s in data["sources"] if s["data_source"] == "THS"
        )
        breakdown = ths_source["type_breakdown"]

        # 验证有 3 个分组
        assert len(breakdown) == 3

        # 验证每个分组包含必要字段
        required_fields = {"sector_type", "label", "sector_count", "stock_count"}
        for item in breakdown:
            assert required_fields.issubset(item.keys()), (
                f"type_breakdown 条目缺少必要字段: {required_fields - item.keys()}"
            )

    @pytest.mark.asyncio
    async def test_type_breakdown_chinese_labels(self):
        """type_breakdown 中的 label 字段为正确的中文标签。"""
        mock_session = _build_coverage_mock_session(
            {
                "THS": {
                    "total_sectors": 200,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 180,
                    "total_stocks": 3000,
                    "type_sector_rows": [
                        TypeSectorCountRow(sector_type="I", sector_count=50),
                        TypeSectorCountRow(sector_type="N", sector_count=100),
                        TypeSectorCountRow(sector_type="S", sector_count=50),
                    ],
                    "type_stock_rows": [
                        TypeStockCountRow(sector_type="I", stock_count=2000),
                        TypeStockCountRow(sector_type="N", stock_count=2800),
                        TypeStockCountRow(sector_type="S", stock_count=1500),
                    ],
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

        ths_source = next(
            s for s in data["sources"] if s["data_source"] == "THS"
        )
        breakdown = ths_source["type_breakdown"]

        # 构建 sector_type → label 映射
        label_map = {item["sector_type"]: item["label"] for item in breakdown}
        assert label_map["I"] == "行业板块"
        assert label_map["N"] == "概念板块"
        assert label_map["S"] == "风格板块"

    @pytest.mark.asyncio
    async def test_type_breakdown_counts_match(self):
        """type_breakdown 中的 sector_count 和 stock_count 与 mock 数据一致。"""
        mock_session = _build_coverage_mock_session(
            {
                "DC": {
                    "total_sectors": 1020,
                    "latest_date": date(2024, 6, 15),
                    "sectors_with": 1000,
                    "total_stocks": 5595,
                    "type_sector_rows": [
                        TypeSectorCountRow(sector_type="概念板块", sector_count=600),
                        TypeSectorCountRow(sector_type="行业板块", sector_count=300),
                        TypeSectorCountRow(sector_type="地域板块", sector_count=120),
                    ],
                    "type_stock_rows": [
                        TypeStockCountRow(sector_type="概念板块", stock_count=4000),
                        TypeStockCountRow(sector_type="行业板块", stock_count=3500),
                        TypeStockCountRow(sector_type="地域板块", stock_count=2000),
                    ],
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

        dc_source = next(
            s for s in data["sources"] if s["data_source"] == "DC"
        )
        breakdown = dc_source["type_breakdown"]

        # 按 sector_type 构建映射
        by_type = {item["sector_type"]: item for item in breakdown}

        assert by_type["概念板块"]["sector_count"] == 600
        assert by_type["概念板块"]["stock_count"] == 4000
        assert by_type["行业板块"]["sector_count"] == 300
        assert by_type["行业板块"]["stock_count"] == 3500
        assert by_type["地域板块"]["sector_count"] == 120
        assert by_type["地域板块"]["stock_count"] == 2000

    @pytest.mark.asyncio
    async def test_empty_data_source_has_empty_type_breakdown(self):
        """无板块数据的数据源 type_breakdown 为空列表。"""
        mock_session = _build_coverage_mock_session(
            {
                "DC": {
                    "total_sectors": 0,
                    "latest_date": None,
                    "type_sector_rows": [],
                    "type_stock_rows": [],
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

        dc_source = next(
            s for s in data["sources"] if s["data_source"] == "DC"
        )
        assert dc_source["type_breakdown"] == []

    @pytest.mark.asyncio
    async def test_coverage_returns_five_data_sources(self):
        """覆盖率端点返回 DC、THS、TDX、TI、CI 五个数据源。"""
        mock_session = _build_coverage_mock_session({})

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
        ds_names = [s["data_source"] for s in data["sources"]]
        assert ds_names == ["DC", "THS", "TDX", "TI", "CI"]
