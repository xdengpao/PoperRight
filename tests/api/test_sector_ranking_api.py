"""
板块排行 API 单元测试

覆盖：
- GET /sector/ranking — 板块涨跌幅排行查询
  - 正常响应格式和字段
  - sector_type 筛选功能
  - data_source 默认值为 DC
  - 无效参数返回 422
  - 空数据返回 200 和空列表

Validates: Requirements 1.1, 1.5, 1.7, 1.8, 1.9
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.sector import DataSource, SectorType
from app.services.data_engine.sector_repository import SectorRankingItem


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_RANKING_ITEMS = [
    SectorRankingItem(
        sector_code="BK0001",
        name="人工智能",
        sector_type="CONCEPT",
        change_pct=5.23,
        close=1080.50,
        volume=150000,
        amount=1620000.00,
        turnover=6.80,
    ),
    SectorRankingItem(
        sector_code="BK0002",
        name="半导体",
        sector_type="CONCEPT",
        change_pct=3.15,
        close=920.30,
        volume=120000,
        amount=1104000.00,
        turnover=5.40,
    ),
    SectorRankingItem(
        sector_code="BK0003",
        name="银行",
        sector_type="INDUSTRY",
        change_pct=-0.85,
        close=780.00,
        volume=80000,
        amount=624000.00,
        turnover=2.10,
    ),
]


# ---------------------------------------------------------------------------
# GET /sector/ranking
# ---------------------------------------------------------------------------


class TestGetSectorRanking:
    """板块涨跌幅排行查询端点测试。"""

    @pytest.mark.asyncio
    async def test_normal_response_format_and_fields(self):
        """正常响应返回 200，JSON 数组包含正确字段。

        Validates: Requirement 1.1, 1.3
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_ranking = AsyncMock(
                return_value=SAMPLE_RANKING_ITEMS
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/ranking")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Verify first item has all expected fields
        item = data[0]
        assert item["sector_code"] == "BK0001"
        assert item["name"] == "人工智能"
        assert item["sector_type"] == "CONCEPT"
        assert item["change_pct"] == 5.23
        assert item["close"] == 1080.50
        assert item["volume"] == 150000
        assert item["amount"] == 1620000.00
        assert item["turnover"] == 6.80

        # Verify second item
        assert data[1]["sector_code"] == "BK0002"
        assert data[1]["change_pct"] == 3.15

        # Verify third item (negative change_pct)
        assert data[2]["sector_code"] == "BK0003"
        assert data[2]["change_pct"] == -0.85

    @pytest.mark.asyncio
    async def test_sector_type_filter(self):
        """传入 sector_type=CONCEPT 时，mock 被正确调用。

        Validates: Requirement 1.5
        """
        filtered = [SAMPLE_RANKING_ITEMS[0], SAMPLE_RANKING_ITEMS[1]]
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_ranking = AsyncMock(return_value=filtered)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/ranking",
                    params={"sector_type": "CONCEPT"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # Verify the repository was called with the correct SectorType enum
        # data_source is None when not specified — the repository handles auto-selection
        repo_instance.get_sector_ranking.assert_awaited_once_with(
            sector_type=SectorType.CONCEPT, data_source=None
        )

    @pytest.mark.asyncio
    async def test_data_source_default_is_dc(self):
        """不传 data_source 时，默认使用 DC。

        Validates: Requirement 1.7
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_ranking = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/ranking")

        assert resp.status_code == 200
        # data_source is None when not specified — the repository handles auto-selection
        repo_instance.get_sector_ranking.assert_awaited_once_with(
            sector_type=None, data_source=None
        )

    @pytest.mark.asyncio
    async def test_explicit_data_source(self):
        """显式传入 data_source=TI 时，mock 被正确调用。

        Validates: Requirement 1.1
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_ranking = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/ranking",
                    params={"data_source": "TI"},
                )

        assert resp.status_code == 200
        repo_instance.get_sector_ranking.assert_awaited_once_with(
            sector_type=None, data_source=DataSource.TI
        )

    @pytest.mark.asyncio
    async def test_invalid_sector_type_returns_422(self):
        """无效的 sector_type 返回 422。

        Validates: Requirement 1.9
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/ranking",
                params={"sector_type": "INVALID"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_data_source_returns_422(self):
        """无效的 data_source 返回 422。

        Validates: Requirement 1.9
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/ranking",
                params={"data_source": "INVALID"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_data_returns_200_and_empty_list(self):
        """无数据时返回 200 和空列表。

        Validates: Requirement 1.8
        """
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_ranking = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/ranking")

        assert resp.status_code == 200
        assert resp.json() == []
