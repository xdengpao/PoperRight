"""
板块 API 单元测试

覆盖：
- GET  /sector/list                 — 板块列表查询（含类型/来源筛选）
- GET  /sector/{code}/constituents  — 板块成分股查询
- GET  /sector/by-stock/{symbol}    — 股票所属板块反查
- GET  /sector/{code}/kline         — 板块行情K线查询
- POST /sector/import/full          — 触发全量导入
- POST /sector/import/incremental   — 触发增量导入
- GET  /sector/import/status        — 导入进度查询
- POST /sector/import/stop          — 停止导入
- GET  /sector/import/errors        — 导入错误查询（分页）
- GET  /sector/import/errors/export — 导入错误导出（CSV）

Validates: Requirements 7.1–7.5, 8.1–8.5, 17.5, 17.6
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Fake ORM objects (mimic SQLAlchemy model instances)
# ---------------------------------------------------------------------------


class _FakeSectorInfo:
    def __init__(
        self,
        sector_code: str,
        name: str,
        sector_type: str,
        data_source: str,
        list_date: date | None = None,
        constituent_count: int | None = None,
    ):
        self.sector_code = sector_code
        self.name = name
        self.sector_type = sector_type
        self.data_source = data_source
        self.list_date = list_date
        self.constituent_count = constituent_count


class _FakeConstituent:
    def __init__(
        self,
        trade_date: date,
        sector_code: str,
        data_source: str,
        symbol: str,
        stock_name: str | None = None,
    ):
        self.trade_date = trade_date
        self.sector_code = sector_code
        self.data_source = data_source
        self.symbol = symbol
        self.stock_name = stock_name


class _FakeKline:
    def __init__(
        self,
        time: datetime,
        sector_code: str,
        data_source: str,
        freq: str,
        open: Decimal | None = None,
        high: Decimal | None = None,
        low: Decimal | None = None,
        close: Decimal | None = None,
        volume: int | None = None,
        amount: Decimal | None = None,
        turnover: Decimal | None = None,
        change_pct: Decimal | None = None,
    ):
        self.time = time
        self.sector_code = sector_code
        self.data_source = data_source
        self.freq = freq
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.amount = amount
        self.turnover = turnover
        self.change_pct = change_pct


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_SECTORS = [
    _FakeSectorInfo("BK0001", "人工智能", "CONCEPT", "DC", date(2020, 1, 1), 120),
    _FakeSectorInfo("BK0002", "半导体", "CONCEPT", "DC", date(2019, 6, 15), 85),
]

SAMPLE_CONSTITUENTS = [
    _FakeConstituent(date(2024, 6, 15), "BK0001", "DC", "000001.SZ", "平安银行"),
    _FakeConstituent(date(2024, 6, 15), "BK0001", "DC", "600519.SH", "贵州茅台"),
]

SAMPLE_KLINES = [
    _FakeKline(
        time=datetime(2024, 6, 14),
        sector_code="BK0001",
        data_source="DC",
        freq="1d",
        open=Decimal("1000.00"),
        high=Decimal("1050.00"),
        low=Decimal("990.00"),
        close=Decimal("1030.00"),
        volume=100000,
        amount=Decimal("1030000.00"),
        turnover=Decimal("5.20"),
        change_pct=Decimal("1.50"),
    ),
    _FakeKline(
        time=datetime(2024, 6, 15),
        sector_code="BK0001",
        data_source="DC",
        freq="1d",
        open=Decimal("1030.00"),
        high=Decimal("1080.00"),
        low=Decimal("1020.00"),
        close=Decimal("1070.00"),
        volume=120000,
        amount=Decimal("1284000.00"),
        turnover=Decimal("6.10"),
        change_pct=Decimal("3.88"),
    ),
]


# ---------------------------------------------------------------------------
# 8.1 — GET /sector/list
# ---------------------------------------------------------------------------


class TestGetSectorList:
    """板块列表查询端点测试。"""

    @pytest.mark.asyncio
    async def test_get_sector_list(self):
        """返回全部板块列表。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_list = AsyncMock(return_value=SAMPLE_SECTORS)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/list")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["sector_code"] == "BK0001"
        assert data[0]["name"] == "人工智能"
        assert data[0]["sector_type"] == "CONCEPT"
        assert data[0]["data_source"] == "DC"
        assert data[0]["list_date"] == "2020-01-01"
        assert data[0]["constituent_count"] == 120
        repo_instance.get_sector_list.assert_awaited_once_with(
            sector_type=None, data_source=None
        )

    @pytest.mark.asyncio
    async def test_get_sector_list_with_filters(self):
        """按 sector_type 和 data_source 筛选。"""
        filtered = [SAMPLE_SECTORS[0]]
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_list = AsyncMock(return_value=filtered)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/list",
                    params={"sector_type": "CONCEPT", "data_source": "DC"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sector_code"] == "BK0001"
        # Verify the enum values were passed correctly
        from app.models.sector import DataSource, SectorType

        repo_instance.get_sector_list.assert_awaited_once_with(
            sector_type=SectorType.CONCEPT, data_source=DataSource.DC
        )

    @pytest.mark.asyncio
    async def test_get_sector_list_invalid_type(self):
        """无效的 sector_type 返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/list",
                params={"sector_type": "INVALID_TYPE"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_sector_list_empty(self):
        """无数据时返回空列表 200。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_list = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/list")

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# 8.2 — GET /sector/{code}/constituents
# ---------------------------------------------------------------------------


class TestGetConstituents:
    """板块成分股查询端点测试。"""

    @pytest.mark.asyncio
    async def test_get_constituents(self):
        """按板块代码和数据来源查询成分股。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_constituents = AsyncMock(
                return_value=SAMPLE_CONSTITUENTS
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/BK0001/constituents",
                    params={"data_source": "DC", "trade_date": "2024-06-15"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "000001.SZ"
        assert data[0]["stock_name"] == "平安银行"
        assert data[0]["trade_date"] == "2024-06-15"
        assert data[0]["sector_code"] == "BK0001"

        from app.models.sector import DataSource

        repo_instance.get_constituents.assert_awaited_once_with(
            sector_code="BK0001",
            data_source=DataSource.DC,
            trade_date=date(2024, 6, 15),
        )

    @pytest.mark.asyncio
    async def test_get_constituents_default_date(self):
        """未指定 trade_date 时传 None（由 repository 使用最新交易日）。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_constituents = AsyncMock(
                return_value=SAMPLE_CONSTITUENTS
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/BK0001/constituents",
                    params={"data_source": "DC"},
                )

        assert resp.status_code == 200
        from app.models.sector import DataSource

        repo_instance.get_constituents.assert_awaited_once_with(
            sector_code="BK0001",
            data_source=DataSource.DC,
            trade_date=None,
        )

    @pytest.mark.asyncio
    async def test_get_constituents_missing_data_source(self):
        """缺少必填参数 data_source 返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/api/v1/sector/BK0001/constituents")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8.3 — GET /sector/by-stock/{symbol}
# ---------------------------------------------------------------------------


class TestGetSectorsByStock:
    """股票所属板块反查端点测试。"""

    @pytest.mark.asyncio
    async def test_get_sectors_by_stock(self):
        """按股票代码查询所属板块。"""
        stock_sectors = [
            _FakeConstituent(date(2024, 6, 15), "BK0001", "DC", "000001.SZ", "平安银行"),
            _FakeConstituent(date(2024, 6, 15), "BK0003", "TI", "000001.SZ", "平安银行"),
        ]
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sectors_by_stock = AsyncMock(
                return_value=stock_sectors
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/by-stock/000001.SZ",
                    params={"trade_date": "2024-06-15"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "000001.SZ"
        assert data[0]["sector_code"] == "BK0001"
        assert data[1]["sector_code"] == "BK0003"

    @pytest.mark.asyncio
    async def test_get_sectors_by_stock_default_date(self):
        """未指定 trade_date 时传 None。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sectors_by_stock = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/by-stock/000001.SZ")

        assert resp.status_code == 200
        assert resp.json() == []
        repo_instance.get_sectors_by_stock.assert_awaited_once_with(
            symbol="000001.SZ", trade_date=None
        )


# ---------------------------------------------------------------------------
# 8.4 — GET /sector/{code}/kline
# ---------------------------------------------------------------------------


class TestGetSectorKline:
    """板块行情K线查询端点测试。"""

    @pytest.mark.asyncio
    async def test_get_sector_kline(self):
        """按板块代码、数据来源和日期范围查询K线。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_kline = AsyncMock(return_value=SAMPLE_KLINES)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/BK0001/kline",
                    params={
                        "data_source": "DC",
                        "freq": "1d",
                        "start": "2024-06-14",
                        "end": "2024-06-15",
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["sector_code"] == "BK0001"
        assert data[0]["open"] == 1000.00
        assert data[0]["close"] == 1030.00
        assert data[0]["volume"] == 100000
        assert data[1]["change_pct"] == 3.88

        from app.models.sector import DataSource

        repo_instance.get_sector_kline.assert_awaited_once_with(
            sector_code="BK0001",
            data_source=DataSource.DC,
            freq="1d",
            start=date(2024, 6, 14),
            end=date(2024, 6, 15),
        )

    @pytest.mark.asyncio
    async def test_get_sector_kline_no_date_range(self):
        """不指定日期范围时 start/end 为 None。"""
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_kline = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/BK0001/kline",
                    params={"data_source": "DC"},
                )

        assert resp.status_code == 200
        from app.models.sector import DataSource

        repo_instance.get_sector_kline.assert_awaited_once_with(
            sector_code="BK0001",
            data_source=DataSource.DC,
            freq="1d",
            start=None,
            end=None,
        )

    @pytest.mark.asyncio
    async def test_get_sector_kline_invalid_data_source(self):
        """无效的 data_source 返回 422。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/BK0001/kline",
                params={"data_source": "INVALID"},
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7.1 — POST /sector/import/full
# ---------------------------------------------------------------------------


class TestTriggerFullImport:
    """全量导入触发端点测试。"""

    @pytest.mark.asyncio
    async def test_trigger_full_import(self):
        """无运行中任务时成功触发全量导入。"""
        mock_task_result = MagicMock()
        mock_task_result.id = "task-uuid-001"

        with (
            patch(
                "app.api.v1.sector.SectorImportService"
            ) as MockSvc,
            patch(
                "app.api.v1.sector.sector_import_full"
            ) as mock_task,
        ):
            svc_instance = MockSvc.return_value
            svc_instance.is_running = AsyncMock(return_value=False)
            svc_instance.update_progress = AsyncMock()
            mock_task.delay.return_value = mock_task_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/sector/import/full")

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-uuid-001"
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_full_import_conflict(self):
        """已有导入任务运行中时返回 409。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.is_running = AsyncMock(return_value=True)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/sector/import/full")

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_trigger_full_import_with_params(self):
        """传入 data_sources 和 base_dir 参数。"""
        mock_task_result = MagicMock()
        mock_task_result.id = "task-uuid-002"

        with (
            patch(
                "app.api.v1.sector.SectorImportService"
            ) as MockSvc,
            patch(
                "app.api.v1.sector.sector_import_full"
            ) as mock_task,
        ):
            svc_instance = MockSvc.return_value
            svc_instance.is_running = AsyncMock(return_value=False)
            svc_instance.update_progress = AsyncMock()
            mock_task.delay.return_value = mock_task_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post(
                    "/api/v1/sector/import/full",
                    json={
                        "data_sources": ["DC", "TI"],
                        "base_dir": "/tmp/test",
                    },
                )

        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with(
            data_sources=["DC", "TI"], base_dir="/tmp/test"
        )


# ---------------------------------------------------------------------------
# 7.2 — POST /sector/import/incremental
# ---------------------------------------------------------------------------


class TestTriggerIncrementalImport:
    """增量导入触发端点测试。"""

    @pytest.mark.asyncio
    async def test_trigger_incremental_import(self):
        """无运行中任务时成功触发增量导入。"""
        mock_task_result = MagicMock()
        mock_task_result.id = "task-uuid-003"

        with (
            patch(
                "app.api.v1.sector.SectorImportService"
            ) as MockSvc,
            patch(
                "app.api.v1.sector.sector_import_incremental"
            ) as mock_task,
        ):
            svc_instance = MockSvc.return_value
            svc_instance.is_running = AsyncMock(return_value=False)
            svc_instance.update_progress = AsyncMock()
            mock_task.delay.return_value = mock_task_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/sector/import/incremental")

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-uuid-003"

    @pytest.mark.asyncio
    async def test_trigger_incremental_import_conflict(self):
        """已有导入任务运行中时返回 409。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.is_running = AsyncMock(return_value=True)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/sector/import/incremental")

        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 7.3 — GET /sector/import/status
# ---------------------------------------------------------------------------


class TestGetImportStatus:
    """导入进度查询端点测试。"""

    @pytest.mark.asyncio
    async def test_get_import_status_running(self):
        """有进度数据时返回当前状态。"""
        progress = {
            "status": "running",
            "stage": "板块成分",
            "processed_files": 15,
            "imported_records": 50000,
            "heartbeat": 1718400000.0,
        }
        with patch(
            "app.api.v1.sector.cache_get",
            new_callable=AsyncMock,
            return_value=json.dumps(progress),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["stage"] == "板块成分"
        assert data["processed_files"] == 15
        assert data["imported_records"] == 50000

    @pytest.mark.asyncio
    async def test_get_import_status_idle(self):
        """无进度数据时返回 idle 状态。"""
        with patch(
            "app.api.v1.sector.cache_get",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"

    @pytest.mark.asyncio
    async def test_get_import_status_completed_with_error(self):
        """导入失败时返回 error 字段。"""
        progress = {
            "status": "failed",
            "error": "数据库连接失败",
        }
        with patch(
            "app.api.v1.sector.cache_get",
            new_callable=AsyncMock,
            return_value=json.dumps(progress),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] == "数据库连接失败"


# ---------------------------------------------------------------------------
# 7.5 — POST /sector/import/stop
# ---------------------------------------------------------------------------


class TestStopImport:
    """停止导入端点测试。"""

    @pytest.mark.asyncio
    async def test_stop_import(self):
        """发送停止信号成功。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.request_stop = AsyncMock()

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.post("/api/v1/sector/import/stop")

        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        svc_instance.request_stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# 17.5 — GET /sector/import/errors
# 17.6 — GET /sector/import/errors/export
# ---------------------------------------------------------------------------

SAMPLE_ERRORS = [
    {
        "file": "东方财富_板块列表1.csv",
        "line": 42,
        "error_type": "parse_error",
        "message": "列数不匹配，期望 13 列，实际 10 列",
        "raw_data": "BK0001,人工智能,CONCEPT,...",
    },
    {
        "file": "通达信_板块行情汇总.csv",
        "line": 108,
        "error_type": "ohlc_invalid",
        "message": "OHLC 保序性验证失败: high < low",
        "raw_data": "BK0002,2024-06-15,100.00,90.00,110.00,95.00,...",
    },
]


class TestGetImportErrors:
    """导入错误查询端点测试。Validates: Requirements 17.5"""

    @pytest.mark.asyncio
    async def test_get_import_errors_empty(self):
        """无错误时返回空列表和 total=0。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.get_errors = AsyncMock(return_value=[])
            svc_instance.get_error_count = AsyncMock(return_value=0)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/errors")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["offset"] == 0
        assert data["limit"] == 50
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_import_errors_with_data(self):
        """有错误数据时返回正确的 items 和 total。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.get_errors = AsyncMock(return_value=SAMPLE_ERRORS)
            svc_instance.get_error_count = AsyncMock(return_value=2)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/errors")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["file"] == "东方财富_板块列表1.csv"
        assert data["items"][0]["line"] == 42
        assert data["items"][0]["error_type"] == "parse_error"
        assert data["items"][0]["message"] == "列数不匹配，期望 13 列，实际 10 列"
        assert data["items"][0]["raw_data"] == "BK0001,人工智能,CONCEPT,..."
        assert data["items"][1]["error_type"] == "ohlc_invalid"
        svc_instance.get_errors.assert_awaited_once_with(offset=0, limit=50)
        svc_instance.get_error_count.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_import_errors_pagination(self):
        """使用 offset 和 limit 参数分页查询。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.get_errors = AsyncMock(return_value=[SAMPLE_ERRORS[1]])
            svc_instance.get_error_count = AsyncMock(return_value=2)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/import/errors",
                    params={"offset": 1, "limit": 10},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["offset"] == 1
        assert data["limit"] == 10
        assert len(data["items"]) == 1
        svc_instance.get_errors.assert_awaited_once_with(offset=1, limit=10)


class TestExportImportErrorsCsv:
    """导入错误 CSV 导出端点测试。Validates: Requirements 17.6"""

    @pytest.mark.asyncio
    async def test_export_errors_csv_empty(self):
        """无错误时 CSV 仅包含表头行。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.get_errors = AsyncMock(return_value=[])
            svc_instance.get_error_count = AsyncMock(return_value=0)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/errors/export")

        assert resp.status_code == 200
        content = resp.text
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        # 仅有表头行
        assert len(lines) == 1
        assert "file" in lines[0]
        assert "line" in lines[0]
        assert "error_type" in lines[0]
        assert "message" in lines[0]
        assert "raw_data" in lines[0]

    @pytest.mark.asyncio
    async def test_export_errors_csv_with_data(self):
        """有错误数据时 CSV 包含表头和数据行。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.get_errors = AsyncMock(return_value=SAMPLE_ERRORS)
            svc_instance.get_error_count = AsyncMock(return_value=2)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/errors/export")

        assert resp.status_code == 200
        content = resp.text
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        # 表头 + 2 条数据
        assert len(lines) == 3
        # 验证表头
        header = lines[0]
        assert "file,line,error_type,message,raw_data" == header
        # 验证第一条数据行包含正确内容
        assert "东方财富_板块列表1.csv" in lines[1]
        assert "42" in lines[1]
        assert "parse_error" in lines[1]
        # 验证第二条数据行
        assert "通达信_板块行情汇总.csv" in lines[2]
        assert "ohlc_invalid" in lines[2]

    @pytest.mark.asyncio
    async def test_export_errors_csv_content_type(self):
        """验证响应 Content-Type 为 text/csv，Content-Disposition 包含文件名。"""
        with patch(
            "app.api.v1.sector.SectorImportService"
        ) as MockSvc:
            svc_instance = MockSvc.return_value
            svc_instance.get_errors = AsyncMock(return_value=[])
            svc_instance.get_error_count = AsyncMock(return_value=0)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get("/api/v1/sector/import/errors/export")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "import_errors.csv" in resp.headers["content-disposition"]
        assert "attachment" in resp.headers["content-disposition"]
