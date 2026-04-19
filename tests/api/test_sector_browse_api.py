"""
板块分页浏览 API 单元测试

覆盖：
- GET /sector/info/browse — 板块信息分页浏览
- GET /sector/constituent/browse — 板块成分股分页浏览
- GET /sector/kline/browse — 板块行情分页浏览
  - 正常响应格式（{total, page, page_size, items}）
  - 无效参数返回 422
  - page_size 边界（1 和 200）
  - 空结果返回 200

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.sector_repository import PaginatedResult


# ---------------------------------------------------------------------------
# 辅助数据
# ---------------------------------------------------------------------------


def _info_paginated(total: int = 3, page_items: list | None = None) -> PaginatedResult:
    """构造 browse_sector_info 的 mock 返回值。"""
    from unittest.mock import MagicMock
    from datetime import date
    from app.models.sector import SectorInfo

    if page_items is None:
        items = []
        for i in range(min(total, 3)):
            m = MagicMock(spec=SectorInfo)
            m.sector_code = f"BK000{i + 1}"
            m.name = f"板块{i + 1}"
            m.sector_type = "CONCEPT"
            m.data_source = "DC"
            m.list_date = date(2024, 1, 1)
            m.constituent_count = 50 + i
            items.append(m)
        page_items = items
    return PaginatedResult(total=total, items=page_items)


def _constituent_paginated(total: int = 2, page_items: list | None = None) -> PaginatedResult:
    """构造 browse_sector_constituent 的 mock 返回值。"""
    from unittest.mock import MagicMock
    from datetime import date
    from app.models.sector import SectorConstituent

    if page_items is None:
        items = []
        for i in range(min(total, 2)):
            m = MagicMock(spec=SectorConstituent)
            m.trade_date = date(2024, 6, 15)
            m.sector_code = "BK0001"
            m.data_source = "DC"
            m.symbol = f"60000{i}"
            m.stock_name = f"股票{i}"
            items.append(m)
        page_items = items
    return PaginatedResult(total=total, items=page_items)


def _kline_paginated(total: int = 2, page_items: list | None = None) -> PaginatedResult:
    """构造 browse_sector_kline 的 mock 返回值。"""
    from unittest.mock import MagicMock
    from datetime import datetime
    from decimal import Decimal
    from app.models.sector import SectorKline

    if page_items is None:
        items = []
        for i in range(min(total, 2)):
            m = MagicMock(spec=SectorKline)
            m.time = datetime(2024, 6, 15 - i, 0, 0, 0)
            m.sector_code = "BK0001"
            m.data_source = "DC"
            m.freq = "1d"
            m.open = Decimal("1200.00")
            m.high = Decimal("1250.00")
            m.low = Decimal("1190.00")
            m.close = Decimal("1234.56")
            m.volume = 100000
            m.amount = Decimal("5000000.00")
            m.change_pct = Decimal("2.50")
            items.append(m)
        page_items = items
    return PaginatedResult(total=total, items=page_items)


# ---------------------------------------------------------------------------
# GET /sector/info/browse
# ---------------------------------------------------------------------------


class TestBrowseSectorInfoAPI:
    """板块信息分页浏览端点测试。"""

    @pytest.mark.asyncio
    async def test_response_format(self):
        """正常响应包含 total、page、page_size、items 字段。

        Validates: Requirement 10.1, 10.4
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo = MockRepo.return_value
            repo.browse_sector_info = AsyncMock(return_value=_info_paginated(total=3))

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/info/browse")

        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 3

        # 验证 item 字段
        item = data["items"][0]
        assert "sector_code" in item
        assert "name" in item
        assert "sector_type" in item
        assert "data_source" in item

    @pytest.mark.asyncio
    async def test_invalid_data_source_422(self):
        """无效的 data_source 返回 422。

        Validates: Requirement 10.5
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/info/browse",
                params={"data_source": "INVALID"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_page_size_boundary_min(self):
        """page_size=1 边界值正常工作。

        Validates: Requirement 10.6
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo = MockRepo.return_value
            repo.browse_sector_info = AsyncMock(
                return_value=_info_paginated(total=100, page_items=[_info_paginated(total=1).items[0]])
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/info/browse",
                    params={"page_size": 1},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 1

    @pytest.mark.asyncio
    async def test_page_size_boundary_max(self):
        """page_size=200 边界值正常工作。

        Validates: Requirement 10.6
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo = MockRepo.return_value
            repo.browse_sector_info = AsyncMock(return_value=_info_paginated(total=0, page_items=[]))

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/info/browse",
                    params={"page_size": 200},
                )

        assert resp.status_code == 200
        assert resp.json()["page_size"] == 200

    @pytest.mark.asyncio
    async def test_empty_result_200(self):
        """空结果返回 200，total=0，items=[]。

        Validates: Requirement 10.4
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo = MockRepo.return_value
            repo.browse_sector_info = AsyncMock(
                return_value=PaginatedResult(total=0, items=[])
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/info/browse")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# ---------------------------------------------------------------------------
# GET /sector/constituent/browse
# ---------------------------------------------------------------------------


class TestBrowseSectorConstituentAPI:
    """板块成分股分页浏览端点测试。"""

    @pytest.mark.asyncio
    async def test_response_format(self):
        """正常响应包含 total、page、page_size、items 字段。

        Validates: Requirement 10.2, 10.4
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo = MockRepo.return_value
            repo.browse_sector_constituent = AsyncMock(
                return_value=_constituent_paginated(total=2)
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/constituent/browse",
                    params={"data_source": "DC"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert data["total"] == 2
        assert isinstance(data["items"], list)

        # 验证 item 字段
        item = data["items"][0]
        assert "trade_date" in item
        assert "sector_code" in item
        assert "symbol" in item
        assert "stock_name" in item

    @pytest.mark.asyncio
    async def test_invalid_data_source_422(self):
        """无效的 data_source 返回 422。

        Validates: Requirement 10.5
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/constituent/browse",
                params={"data_source": "INVALID"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_data_source_422(self):
        """缺少必填的 data_source 返回 422。

        Validates: Requirement 10.5
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/api/v1/sector/constituent/browse")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /sector/kline/browse
# ---------------------------------------------------------------------------


class TestBrowseSectorKlineAPI:
    """板块行情分页浏览端点测试。"""

    @pytest.mark.asyncio
    async def test_response_format(self):
        """正常响应包含 total、page、page_size、items 字段。

        Validates: Requirement 10.3, 10.4
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo = MockRepo.return_value
            repo.browse_sector_kline = AsyncMock(
                return_value=_kline_paginated(total=2)
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/kline/browse",
                    params={"data_source": "DC"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert data["total"] == 2
        assert isinstance(data["items"], list)

        # 验证 item 字段
        item = data["items"][0]
        assert "time" in item
        assert "sector_code" in item
        assert "open" in item
        assert "close" in item
        assert "volume" in item
        assert "change_pct" in item

    @pytest.mark.asyncio
    async def test_invalid_data_source_422(self):
        """无效的 data_source 返回 422。

        Validates: Requirement 10.5
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/kline/browse",
                params={"data_source": "INVALID"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_422(self):
        """无效的日期格式返回 422。

        Validates: Requirement 10.5
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/kline/browse",
                params={"data_source": "DC", "start": "not-a-date"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_data_source_422(self):
        """缺少必填的 data_source 返回 422。

        Validates: Requirement 10.5
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/api/v1/sector/kline/browse")

        assert resp.status_code == 422
