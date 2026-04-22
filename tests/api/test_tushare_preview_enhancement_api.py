"""
Tushare 数据预览增强 API 端点集成测试

覆盖增强功能新增的 2 个端点：
- POST /{api_name}/check-integrity — 完整性校验
- GET  /{api_name}/chart-data      — 图表数据独立加载

Mock TusharePreviewService，验证 API 层的参数传递、错误处理和响应格式。

对应需求：2.1, 8.1, 8.5, 10.1-10.4
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.data_engine.tushare_preview_service import (
    ChartDataResponse,
    ColumnInfo,
    CompletenessReport,
)


# ---------------------------------------------------------------------------
# 辅助常量与工厂函数
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost"
PREFIX = "/api/v1/data/tushare/preview"

# Mock 路径前缀（在 API 模块中导入的 TusharePreviewService）
_SVC_PATH = "app.api.v1.tushare_preview.TusharePreviewService"


def _make_completeness_report_time_series(**overrides) -> CompletenessReport:
    """创建时序数据完整性校验结果。"""
    defaults = dict(
        check_type="time_series",
        expected_count=20,
        actual_count=18,
        missing_count=2,
        completeness_rate=0.9,
        missing_items=["20240115", "20240122"],
        time_range={"start": "20240101", "end": "20240131"},
        message=None,
    )
    defaults.update(overrides)
    return CompletenessReport(**defaults)


def _make_completeness_report_code_based(**overrides) -> CompletenessReport:
    """创建非时序数据完整性校验结果。"""
    defaults = dict(
        check_type="code_based",
        expected_count=5000,
        actual_count=4990,
        missing_count=10,
        completeness_rate=0.998,
        missing_items=["000001.SZ", "000002.SZ"],
        time_range=None,
        message="预期集合基于全部 A 股代码，实际覆盖范围可能因接口特性而异",
    )
    defaults.update(overrides)
    return CompletenessReport(**defaults)


def _make_chart_data_response(**overrides) -> ChartDataResponse:
    """创建图表数据响应。"""
    defaults = dict(
        rows=[
            {"trade_date": "20240101", "close": 10.5, "vol": 1000},
            {"trade_date": "20240102", "close": 10.8, "vol": 1200},
            {"trade_date": "20240103", "close": 11.0, "vol": 900},
        ],
        time_field="trade_date",
        chart_type="candlestick",
        columns=[
            ColumnInfo(name="trade_date", label="trade_date", type="date"),
            ColumnInfo(name="close", label="close", type="number"),
            ColumnInfo(name="vol", label="vol", type="number"),
        ],
        total_available=500,
    )
    defaults.update(overrides)
    return ChartDataResponse(**defaults)


# ---------------------------------------------------------------------------
# POST /{api_name}/check-integrity — 完整性校验端点
# ---------------------------------------------------------------------------


class TestCheckIntegrityEndpoint:
    """完整性校验端点测试。"""

    @pytest.mark.asyncio
    async def test_check_integrity_endpoint_time_series(self):
        """完整性校验端点（时序）：返回时序数据校验结果，包含缺失交易日。"""
        mock_report = _make_completeness_report_time_series()

        with patch(
            f"{_SVC_PATH}.check_integrity",
            new_callable=AsyncMock,
            return_value=mock_report,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(
                    f"{PREFIX}/daily/check-integrity",
                    json={
                        "data_time_start": "20240101",
                        "data_time_end": "20240131",
                    },
                )

        assert resp.status_code == 200
        data = resp.json()

        # 验证校验类型
        assert data["check_type"] == "time_series"

        # 验证数量统计
        assert data["expected_count"] == 20
        assert data["actual_count"] == 18
        assert data["missing_count"] == 2
        assert data["completeness_rate"] == 0.9

        # 验证缺失项
        assert data["missing_items"] == ["20240115", "20240122"]

        # 验证时间范围
        assert data["time_range"] == {"start": "20240101", "end": "20240131"}

        # 验证 service 方法被正确调用
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["data_time_start"] == "20240101"
        assert call_kwargs["data_time_end"] == "20240131"

    @pytest.mark.asyncio
    async def test_check_integrity_endpoint_code_based(self):
        """完整性校验端点（非时序）：返回非时序数据校验结果，包含缺失代码。"""
        mock_report = _make_completeness_report_code_based()

        with patch(
            f"{_SVC_PATH}.check_integrity",
            new_callable=AsyncMock,
            return_value=mock_report,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(
                    f"{PREFIX}/stock_basic/check-integrity",
                    json={},
                )

        assert resp.status_code == 200
        data = resp.json()

        # 验证校验类型
        assert data["check_type"] == "code_based"

        # 验证数量统计
        assert data["expected_count"] == 5000
        assert data["actual_count"] == 4990
        assert data["missing_count"] == 10
        assert data["completeness_rate"] == 0.998

        # 验证缺失项
        assert "000001.SZ" in data["missing_items"]
        assert "000002.SZ" in data["missing_items"]

        # 验证提示信息
        assert data["message"] is not None
        assert "A 股代码" in data["message"]

        # 验证时间范围为空（非时序数据）
        assert data["time_range"] is None

        # 验证 service 方法被正确调用
        mock_fn.assert_called_once()
        call_args = mock_fn.call_args
        assert call_args[0][0] == "stock_basic"

    @pytest.mark.asyncio
    async def test_check_integrity_endpoint_unknown_api(self):
        """完整性校验端点：未注册的 api_name 返回 HTTP 404。"""
        with patch(
            f"{_SVC_PATH}.check_integrity",
            new_callable=AsyncMock,
            side_effect=ValueError("接口 nonexistent_api 未注册"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(
                    f"{PREFIX}/nonexistent_api/check-integrity",
                    json={},
                )

        assert resp.status_code == 404
        assert "未注册" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /{api_name}/chart-data — 图表数据端点
# ---------------------------------------------------------------------------


class TestChartDataEndpoint:
    """图表数据端点测试。"""

    @pytest.mark.asyncio
    async def test_chart_data_endpoint_returns_data(self):
        """图表数据端点返回数据：包含行数据、时间字段、图表类型和列信息。"""
        mock_response = _make_chart_data_response()

        with patch(
            f"{_SVC_PATH}.query_chart_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/daily/chart-data")

        assert resp.status_code == 200
        data = resp.json()

        # 验证行数据
        assert len(data["rows"]) == 3
        assert data["rows"][0]["trade_date"] == "20240101"
        assert data["rows"][0]["close"] == 10.5

        # 验证时间字段
        assert data["time_field"] == "trade_date"

        # 验证图表类型
        assert data["chart_type"] == "candlestick"

        # 验证列信息
        assert len(data["columns"]) == 3
        col_names = [c["name"] for c in data["columns"]]
        assert "trade_date" in col_names
        assert "close" in col_names
        assert "vol" in col_names

        # 验证可用数据总量
        assert data["total_available"] == 500

        # 验证 service 方法被正确调用（默认 limit=250）
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["limit"] == 250

    @pytest.mark.asyncio
    async def test_chart_data_endpoint_with_filters(self):
        """图表数据端点带筛选参数：时间范围和 limit 正确传递到 service 层。"""
        mock_response = _make_chart_data_response()

        with patch(
            f"{_SVC_PATH}.query_chart_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/daily/chart-data",
                    params={
                        "limit": 100,
                        "data_time_start": "20240101",
                        "data_time_end": "20240331",
                    },
                )

        assert resp.status_code == 200

        # 验证参数正确传递
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["limit"] == 100
        assert call_kwargs["data_time_start"] == "20240101"
        assert call_kwargs["data_time_end"] == "20240331"

    @pytest.mark.asyncio
    async def test_chart_data_endpoint_limit_clamping(self):
        """图表数据端点 limit 参数 clamp：超出范围的 limit 传递到 service 层由其 clamp。"""
        mock_response = _make_chart_data_response()

        with patch(
            f"{_SVC_PATH}.query_chart_data",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_fn:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                # 传入超大 limit 值
                resp = await client.get(
                    f"{PREFIX}/daily/chart-data",
                    params={"limit": 9999},
                )

        assert resp.status_code == 200

        # 验证超大 limit 值被传递到 service 层（service 内部负责 clamp）
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["limit"] == 9999

    @pytest.mark.asyncio
    async def test_chart_data_endpoint_unknown_api(self):
        """图表数据端点：未注册的 api_name 返回 HTTP 404。"""
        with patch(
            f"{_SVC_PATH}.query_chart_data",
            new_callable=AsyncMock,
            side_effect=ValueError("接口 nonexistent_api 未注册"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(
                    f"{PREFIX}/nonexistent_api/chart-data",
                )

        assert resp.status_code == 404
        assert "未注册" in resp.json()["detail"]
