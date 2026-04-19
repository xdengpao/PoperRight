"""
选股结果到回测闭环 API 测试（需求 11）

覆盖场景：
- 正常提交回测任务（从 Redis 缓存读取选股结果）
- 选股结果 ID 不存在返回 404
- 选股结果已过期返回 404
- 参数校验（initial_capital > 0）
- 默认日期使用选股时间
- 自定义起止日期
"""

from __future__ import annotations

import json
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


def _make_screen_result(
    strategy_id: str | None = None,
    screen_time: str | None = None,
    items: list[dict] | None = None,
) -> str:
    """构造 Redis 中缓存的选股结果 JSON 字符串。"""
    sid = strategy_id or str(uuid4())
    st = screen_time or datetime.now().isoformat()
    return json.dumps({
        "strategy_id": sid,
        "screen_type": "EOD",
        "screen_time": st,
        "items": items or [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "ref_buy_price": 1800.0,
                "trend_score": 85.0,
                "risk_level": "LOW",
                "signals": [],
                "has_fake_breakout": False,
                "screen_time": st,
            },
        ],
        "is_complete": True,
    })


# ---------------------------------------------------------------------------
# 正常提交回测任务
# ---------------------------------------------------------------------------


class TestScreenToBacktestSuccess:
    """正常提交回测任务场景。"""

    @pytest.mark.anyio
    async def test_submit_backtest_returns_202(self, client: AsyncClient):
        """正常提交回测任务，返回 202 和回测任务 ID。"""
        sid = str(uuid4())
        screen_result = _make_screen_result(strategy_id=sid, screen_time="2024-06-15T15:30:00")

        with (
            patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value=screen_result),
            patch("app.tasks.backtest.run_backtest_task") as mock_task,
        ):
            mock_task.delay = MagicMock()
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={
                    "screen_result_id": sid,
                    "end_date": "2024-12-31",
                    "initial_capital": 500000.0,
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "backtest_id" in data
        assert data["screen_result_id"] == sid
        assert data["strategy_id"] == sid
        assert data["status"] == "PENDING"
        assert data["stock_count"] == 1
        assert data["initial_capital"] == 500000.0
        # 默认 start_date 应从 screen_time 提取
        assert data["start_date"] == "2024-06-15"
        assert data["end_date"] == "2024-12-31"
        mock_task.delay.assert_called_once()

    @pytest.mark.anyio
    async def test_submit_backtest_with_custom_start_date(self, client: AsyncClient):
        """自定义起止日期覆盖选股时间。"""
        sid = str(uuid4())
        screen_result = _make_screen_result(strategy_id=sid, screen_time="2024-06-15T15:30:00")

        with (
            patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value=screen_result),
            patch("app.tasks.backtest.run_backtest_task") as mock_task,
        ):
            mock_task.delay = MagicMock()
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={
                    "screen_result_id": sid,
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30",
                    "initial_capital": 1000000.0,
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] == "2024-06-30"

    @pytest.mark.anyio
    async def test_submit_backtest_default_capital(self, client: AsyncClient):
        """不传 initial_capital 时使用默认值 100 万。"""
        sid = str(uuid4())
        screen_result = _make_screen_result(strategy_id=sid)

        with (
            patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value=screen_result),
            patch("app.tasks.backtest.run_backtest_task") as mock_task,
        ):
            mock_task.delay = MagicMock()
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={"screen_result_id": sid},
            )

        assert resp.status_code == 202
        assert resp.json()["initial_capital"] == 1000000.0

    @pytest.mark.anyio
    async def test_celery_task_receives_correct_params(self, client: AsyncClient):
        """验证 Celery 任务接收到正确的参数。"""
        sid = str(uuid4())
        screen_result = _make_screen_result(strategy_id=sid, screen_time="2024-03-01T15:30:00")

        with (
            patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value=screen_result),
            patch("app.tasks.backtest.run_backtest_task") as mock_task,
        ):
            mock_task.delay = MagicMock()
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={
                    "screen_result_id": sid,
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30",
                    "initial_capital": 200000.0,
                },
            )

        assert resp.status_code == 202
        call_kwargs = mock_task.delay.call_args
        assert call_kwargs.kwargs["strategy_id"] == sid
        assert call_kwargs.kwargs["start_date"] == "2024-01-01"
        assert call_kwargs.kwargs["end_date"] == "2024-06-30"
        assert call_kwargs.kwargs["initial_capital"] == 200000.0


# ---------------------------------------------------------------------------
# 选股结果不存在 → 404
# ---------------------------------------------------------------------------


class TestScreenToBacktestNotFound:
    """选股结果 ID 不存在或已过期返回 404。"""

    @pytest.mark.anyio
    async def test_nonexistent_result_returns_404(self, client: AsyncClient):
        """选股结果 ID 在 Redis 中不存在时返回 404。"""
        with patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value=None):
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={"screen_result_id": "nonexistent-id"},
            )

        assert resp.status_code == 404
        assert "不存在或已过期" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_expired_result_returns_404(self, client: AsyncClient):
        """选股结果已过期（Redis TTL 到期）时返回 404。"""
        with patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value=None):
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={"screen_result_id": str(uuid4())},
            )

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_corrupted_result_returns_404(self, client: AsyncClient):
        """选股结果数据损坏时返回 404。"""
        with patch("app.api.v1.screen.cache_get", new_callable=AsyncMock, return_value="not-valid-json{{{"):
            resp = await client.post(
                "/api/v1/screen/backtest",
                json={"screen_result_id": "corrupted-id"},
            )

        assert resp.status_code == 404
        assert "数据损坏" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------


class TestScreenToBacktestValidation:
    """请求参数校验场景。"""

    @pytest.mark.anyio
    async def test_missing_screen_result_id_returns_422(self, client: AsyncClient):
        """缺少必填字段 screen_result_id 返回 422。"""
        resp = await client.post(
            "/api/v1/screen/backtest",
            json={"initial_capital": 100000.0},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_negative_initial_capital_returns_422(self, client: AsyncClient):
        """initial_capital 为负数返回 422。"""
        resp = await client.post(
            "/api/v1/screen/backtest",
            json={"screen_result_id": "some-id", "initial_capital": -100.0},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_zero_initial_capital_returns_422(self, client: AsyncClient):
        """initial_capital 为 0 返回 422。"""
        resp = await client.post(
            "/api/v1/screen/backtest",
            json={"screen_result_id": "some-id", "initial_capital": 0},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_date_format_returns_422(self, client: AsyncClient):
        """无效日期格式返回 422。"""
        resp = await client.post(
            "/api/v1/screen/backtest",
            json={
                "screen_result_id": "some-id",
                "start_date": "not-a-date",
            },
        )
        assert resp.status_code == 422
