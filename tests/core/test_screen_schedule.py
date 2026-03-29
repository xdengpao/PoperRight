"""
盘后选股调度状态 API 测试

测试 GET /api/v1/screen/schedule 端点：
- next_run_at 正确计算为下一个工作日 15:30 CST
- Redis 有数据时正确返回 last_run_* 字段
- Redis 无数据时 last_run_* 字段返回 null
- Redis 数据损坏时优雅降级
- _next_weekday_1530 辅助函数的各种边界情况
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.screen import _next_weekday_1530, router as screen_router
from app.core.redis_client import get_redis

_CST = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# 最小测试应用（不含 lifespan，避免连接真实 DB/Redis）
# ---------------------------------------------------------------------------


def _make_test_app(redis_return_value: str | None) -> FastAPI:
    """创建仅包含 screen 路由的最小 FastAPI 应用，并注入 mock Redis。"""
    test_app = FastAPI()
    test_app.include_router(screen_router, prefix="/api/v1")

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=redis_return_value)
    redis_mock.aclose = AsyncMock()

    async def _override_redis():
        yield redis_mock

    test_app.dependency_overrides[get_redis] = _override_redis
    return test_app


# ---------------------------------------------------------------------------
# _next_weekday_1530 单元测试
# ---------------------------------------------------------------------------


class TestNextWeekday1530:
    """测试 next_run_at 计算逻辑。"""

    def _cst(self, year: int, month: int, day: int, hour: int, minute: int) -> datetime:
        return datetime(year, month, day, hour, minute, tzinfo=_CST)

    def test_weekday_before_1530_returns_today(self):
        # 周一 14:00 → 今天 15:30
        now = self._cst(2024, 1, 8, 14, 0)  # 周一
        result = _next_weekday_1530(now)
        assert result.weekday() == 0  # 周一
        assert result.hour == 15
        assert result.minute == 30
        assert result.date() == now.date()

    def test_weekday_after_1530_returns_next_weekday(self):
        # 周一 16:00 → 周二 15:30
        now = self._cst(2024, 1, 8, 16, 0)  # 周一
        result = _next_weekday_1530(now)
        assert result.weekday() == 1  # 周二
        assert result.hour == 15
        assert result.minute == 30

    def test_weekday_exactly_at_1530_returns_next_weekday(self):
        # 周一 15:30 整点 → 已过，返回周二
        now = self._cst(2024, 1, 8, 15, 30)  # 周一
        result = _next_weekday_1530(now)
        assert result.weekday() == 1  # 周二

    def test_friday_after_1530_skips_weekend_to_monday(self):
        # 周五 16:00 → 下周一 15:30
        now = self._cst(2024, 1, 12, 16, 0)  # 周五
        result = _next_weekday_1530(now)
        assert result.weekday() == 0  # 周一
        assert result.hour == 15
        assert result.minute == 30

    def test_saturday_returns_monday(self):
        # 周六 → 下周一 15:30
        now = self._cst(2024, 1, 13, 10, 0)  # 周六
        result = _next_weekday_1530(now)
        assert result.weekday() == 0  # 周一

    def test_sunday_returns_monday(self):
        # 周日 → 下周一 15:30
        now = self._cst(2024, 1, 14, 10, 0)  # 周日
        result = _next_weekday_1530(now)
        assert result.weekday() == 0  # 周一

    def test_result_always_has_timezone(self):
        now = self._cst(2024, 1, 8, 14, 0)
        result = _next_weekday_1530(now)
        assert result.tzinfo is not None

    def test_naive_datetime_treated_as_cst(self):
        # 无时区的 datetime 应被当作 CST 处理
        now = datetime(2024, 1, 8, 14, 0)  # 周一，无时区
        result = _next_weekday_1530(now)
        assert result.hour == 15
        assert result.minute == 30
        assert result.weekday() == 0  # 今天（周一）


# ---------------------------------------------------------------------------
# API 端点测试（使用最小测试应用 + mock Redis）
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_no_redis():
    """Redis 返回 None（无历史数据）的测试客户端。"""
    return TestClient(_make_test_app(None))


@pytest.fixture()
def client_with_redis_data():
    """Redis 返回有效 JSON 数据的测试客户端。"""
    payload = json.dumps({
        "run_at": "2024-01-08T15:30:00+08:00",
        "duration_ms": 1234,
        "result_count": 42,
    })
    return TestClient(_make_test_app(payload))


@pytest.fixture()
def client_with_corrupt_redis():
    """Redis 返回损坏 JSON 的测试客户端。"""
    return TestClient(_make_test_app("not-valid-json{{{"))


class TestGetEodScheduleStatus:
    """GET /api/v1/screen/schedule 端点测试。"""

    def test_returns_200(self, client_no_redis):
        resp = client_no_redis.get("/api/v1/screen/schedule")
        assert resp.status_code == 200

    def test_next_run_at_is_present(self, client_no_redis):
        data = client_no_redis.get("/api/v1/screen/schedule").json()
        assert "next_run_at" in data
        assert data["next_run_at"] is not None

    def test_next_run_at_is_weekday_1530(self, client_no_redis):
        data = client_no_redis.get("/api/v1/screen/schedule").json()
        dt = datetime.fromisoformat(data["next_run_at"])
        assert dt.weekday() < 5  # 工作日
        assert dt.hour == 15
        assert dt.minute == 30

    def test_no_redis_data_returns_nulls(self, client_no_redis):
        data = client_no_redis.get("/api/v1/screen/schedule").json()
        assert data["last_run_at"] is None
        assert data["last_run_duration_ms"] is None
        assert data["last_run_result_count"] is None

    def test_with_redis_data_returns_last_run_fields(self, client_with_redis_data):
        data = client_with_redis_data.get("/api/v1/screen/schedule").json()
        assert data["last_run_at"] is not None
        assert data["last_run_duration_ms"] == 1234
        assert data["last_run_result_count"] == 42

    def test_with_redis_data_last_run_at_parseable(self, client_with_redis_data):
        data = client_with_redis_data.get("/api/v1/screen/schedule").json()
        dt = datetime.fromisoformat(data["last_run_at"])
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 8

    def test_corrupt_redis_data_returns_nulls(self, client_with_corrupt_redis):
        data = client_with_corrupt_redis.get("/api/v1/screen/schedule").json()
        assert data["last_run_at"] is None
        assert data["last_run_duration_ms"] is None
        assert data["last_run_result_count"] is None

    def test_corrupt_redis_still_returns_next_run_at(self, client_with_corrupt_redis):
        data = client_with_corrupt_redis.get("/api/v1/screen/schedule").json()
        assert data["next_run_at"] is not None

    def test_response_schema_fields(self, client_no_redis):
        data = client_no_redis.get("/api/v1/screen/schedule").json()
        assert set(data.keys()) == {
            "next_run_at",
            "last_run_at",
            "last_run_duration_ms",
            "last_run_result_count",
        }
