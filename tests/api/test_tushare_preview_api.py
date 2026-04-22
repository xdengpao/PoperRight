"""
Tushare 数据预览 API 端点集成测试

覆盖 /data/tushare/preview 下全部 3 个端点：
- GET  /{api_name}            — 查询预览数据（分页、时间筛选、增量查询）
- GET  /{api_name}/stats      — 获取数据统计信息
- GET  /{api_name}/import-logs — 获取该接口的导入记录列表

Mock TusharePreviewService，验证 API 层的参数传递、错误处理和响应格式。

对应需求：8.1-8.6, 9.3, 9.4
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.tushare_preview_service import (
    ColumnInfo,
    ImportLogItem,
    IncrementalInfo,
    PreviewDataResponse,
    PreviewStatsResponse,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost"
PREFIX = "/api/v1/data/tushare/preview"

# Mock 路径前缀（在 API 模块中导入的 TusharePreviewService）
_SVC_PATH = "app.api.v1.tushare_preview.TusharePreviewService"


def _make_preview_response(**overrides) -> PreviewDataResponse:
    """创建测试用 PreviewDataResponse。"""
    defaults = dict(
        columns=[
            ColumnInfo(name="symbol", label="symbol", type="string"),
            ColumnInfo(name="time", label="time", type="datetime"),
            ColumnInfo(name="close", label="close", type="number"),
        ],
        rows=[
            {"symbol": "600000.SH", "time": "2024-01-15", "close": 10.5},
            {"symbol": "600000.SH", "time": "2024-01-16", "close": 10.8},
        ],
        total=100,
        page=1,
        page_size=50,
        time_field="time",
        chart_type="candlestick",
        scope_info="freq=1d",
        incremental_info=None,
    )
    defaults.update(overrides)
    return PreviewDataResponse(**defaults)


def _make_stats_response(**overrides) -> PreviewStatsResponse:
    """创建测试用 PreviewStatsResponse。"""
    defaults = dict(
        total_count=50000,
        earliest_time="20230101",
        latest_time="20241231",
        last_import_at="2024-12-31T10:00:00",
        last_import_count=500,
    )
    defaults.update(overrides)
    return PreviewStatsResponse(**defaults)


def _make_import_log_items() -> list[ImportLogItem]:
    """创建测试用导入记录列表。"""
    return [
        ImportLogItem(
            id=2,
            api_name="daily",
            params_json={"start_date": "20240101", "end_date": "20240131"},
            status="completed",
            record_count=1000,
            error_message=None,
            started_at="2024-01-15T10:30:00",
            finished_at="2024-01-15T10:35:00",
        ),
        ImportLogItem(
            id=1,
            api_name="daily",
            params_json={"start_date": "20231201", "end_date": "20231231"},
            status="failed",
            record_count=0,
            error_message="连接超时",
            started_at="2024-01-10T08:00:00",
            finished_at="2024-01-10T08:05:00",
        ),
    ]


# ---------------------------------------------------------------------------
# GET /{api_name} — 查询预览数据
# ---------------------------------------------------------------------------


class TestPreviewEndpoint:
    """预览数据端点测试。"""

    @pytest.mark.asyncio
    async def test_preview_endpoint_returns_paginated_data(self):
        """预览端点返回分页数据，包含列信息、行数据和分页元数据。"""
        mock_response = _make_preview_response(total=100, page=2, page_size=20)

        with patch(
            f"{_SVC_PATH}.query_preview_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/daily", params={"page": 2, "page_size": 20}
                )

        assert resp.status_code == 200
        data = resp.json()

        # 验证分页元数据
        assert data["total"] == 100
        assert data["page"] == 2
        assert data["page_size"] == 20

        # 验证列信息
        assert len(data["columns"]) == 3
        col_names = [c["name"] for c in data["columns"]]
        assert "symbol" in col_names
        assert "time" in col_names
        assert "close" in col_names

        # 验证行数据
        assert len(data["rows"]) == 2
        assert data["rows"][0]["symbol"] == "600000.SH"

        # 验证图表类型和时间字段
        assert data["time_field"] == "time"
        assert data["chart_type"] == "candlestick"

        # 验证 service 方法被正确调用
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args
        assert call_kwargs[0][0] == "daily"  # api_name 位置参数

    @pytest.mark.asyncio
    async def test_import_time_filter(self):
        """导入时间范围参数正确传递到 service 层。"""
        mock_response = _make_preview_response()

        with patch(
            f"{_SVC_PATH}.query_preview_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/daily",
                    params={
                        "import_time_start": "2024-01-01T00:00:00",
                        "import_time_end": "2024-01-31T23:59:59",
                    },
                )

        assert resp.status_code == 200
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["import_time_start"] is not None
        assert call_kwargs["import_time_end"] is not None

    @pytest.mark.asyncio
    async def test_import_time_invalid_range_returns_400(self):
        """导入时间范围无效（start > end）时返回 HTTP 400。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=BASE_URL
        ) as client:
            resp = await client.get(
                f"{PREFIX}/daily",
                params={
                    "import_time_start": "2024-12-31T23:59:59",
                    "import_time_end": "2024-01-01T00:00:00",
                },
            )

        assert resp.status_code == 400
        assert "开始时间不能晚于结束时间" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_data_time_filter(self):
        """数据时间范围参数正确传递到 service 层。"""
        mock_response = _make_preview_response()

        with patch(
            f"{_SVC_PATH}.query_preview_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/daily",
                    params={
                        "data_time_start": "20240101",
                        "data_time_end": "20240131",
                    },
                )

        assert resp.status_code == 200
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["data_time_start"] == "20240101"
        assert call_kwargs["data_time_end"] == "20240131"

    @pytest.mark.asyncio
    async def test_incremental_query(self):
        """增量查询参数正确传递，响应包含 incremental_info。"""
        inc_info = IncrementalInfo(
            import_log_id=42,
            import_time="2024-02-01T08:00:00",
            record_count=500,
            status="completed",
            params_summary="20240101 ~ 20240131",
        )
        mock_response = _make_preview_response(incremental_info=inc_info)

        with patch(
            f"{_SVC_PATH}.query_preview_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/daily", params={"incremental": True}
                )

        assert resp.status_code == 200
        data = resp.json()

        # 验证增量信息
        assert data["incremental_info"] is not None
        assert data["incremental_info"]["import_log_id"] == 42
        assert data["incremental_info"]["status"] == "completed"
        assert data["incremental_info"]["record_count"] == 500
        assert "20240101" in data["incremental_info"]["params_summary"]

        # 验证 incremental 参数传递
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["incremental"] is True

    @pytest.mark.asyncio
    async def test_unknown_api_returns_404(self):
        """未注册的 api_name 返回 HTTP 404。"""
        with patch(
            f"{_SVC_PATH}.query_preview_data",
            new_callable=AsyncMock,
            side_effect=ValueError("接口 nonexistent_api 未注册"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/nonexistent_api")

        assert resp.status_code == 404
        assert "未注册" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_shared_table_scope_filter(self):
        """共享表作用域过滤：响应包含 scope_info 字段。"""
        mock_response = _make_preview_response(scope_info="freq=1d")

        with patch(
            f"{_SVC_PATH}.query_preview_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/daily")

        assert resp.status_code == 200
        data = resp.json()
        assert data["scope_info"] == "freq=1d"


# ---------------------------------------------------------------------------
# GET /{api_name}/stats — 获取数据统计信息
# ---------------------------------------------------------------------------


class TestStatsEndpoint:
    """统计信息端点测试。"""

    @pytest.mark.asyncio
    async def test_stats_endpoint_returns_statistics(self):
        """统计端点返回总记录数、时间范围和最近导入信息。"""
        mock_response = _make_stats_response()

        with patch(
            f"{_SVC_PATH}.query_stats",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/daily/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 50000
        assert data["earliest_time"] == "20230101"
        assert data["latest_time"] == "20241231"
        assert data["last_import_at"] == "2024-12-31T10:00:00"
        assert data["last_import_count"] == 500

    @pytest.mark.asyncio
    async def test_stats_unknown_api_returns_404(self):
        """统计端点对未注册的 api_name 返回 HTTP 404。"""
        with patch(
            f"{_SVC_PATH}.query_stats",
            new_callable=AsyncMock,
            side_effect=ValueError("接口 unknown_api 未注册"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/unknown_api/stats")

        assert resp.status_code == 404
        assert "未注册" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /{api_name}/import-logs — 获取导入记录列表
# ---------------------------------------------------------------------------


class TestImportLogsEndpoint:
    """导入记录端点测试。"""

    @pytest.mark.asyncio
    async def test_import_logs_endpoint(self):
        """导入记录端点返回按时间降序排列的记录列表。"""
        mock_logs = _make_import_log_items()

        with patch(
            f"{_SVC_PATH}.query_import_logs",
            new_callable=AsyncMock,
            return_value=mock_logs,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/daily/import-logs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        # 第一条记录（更晚的，降序排列）
        first = data[0]
        assert first["id"] == 2
        assert first["api_name"] == "daily"
        assert first["status"] == "completed"
        assert first["record_count"] == 1000
        assert first["error_message"] is None
        assert first["started_at"] == "2024-01-15T10:30:00"
        assert first["finished_at"] == "2024-01-15T10:35:00"
        assert first["params_json"]["start_date"] == "20240101"

        # 第二条记录（失败的）
        second = data[1]
        assert second["id"] == 1
        assert second["status"] == "failed"
        assert second["error_message"] == "连接超时"

    @pytest.mark.asyncio
    async def test_import_logs_with_custom_limit(self):
        """自定义 limit 参数查询导入记录。"""
        with patch(
            f"{_SVC_PATH}.query_import_logs",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/daily/import-logs", params={"limit": 5}
                )

        assert resp.status_code == 200
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args
        assert call_kwargs[1]["limit"] == 5
