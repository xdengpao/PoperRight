"""
Celery 选股任务数据管线单元测试（需求 2）

覆盖场景：
- 2.1 _load_market_data_async：通过 ScreenDataProvider 异步加载全市场数据
- 2.2 _load_active_strategy_async：从 strategy_template 表查询活跃策略
- 2.3 Redis 缓存写入：选股结果写入 screen:results:{strategy_id} 和 screen:eod:last_run
- 2.4 数据库连接失败时的 Celery 重试逻辑
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.schemas import StrategyConfig
from app.tasks.screening import (
    _cache_screen_results,
    _load_active_strategy_async,
    _load_market_data_async,
    _RESULT_CACHE_PREFIX,
    _LAST_RUN_KEY,
    _RESULT_CACHE_TTL,
    _LAST_RUN_TTL,
)


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------


def _make_strategy_template_mock(
    *,
    template_id: uuid.UUID | None = None,
    name: str = "测试策略",
    config: dict | None = None,
    is_active: bool = True,
    enabled_modules: list[str] | None = None,
) -> MagicMock:
    """创建 StrategyTemplate ORM 对象的 mock。"""
    mock = MagicMock()
    mock.id = template_id or uuid.uuid4()
    mock.name = name
    mock.config = config or {
        "factors": [
            {"factor_name": "ma_trend", "operator": ">=", "threshold": 60.0}
        ],
        "logic": "AND",
        "weights": {"ma_trend": 1.0},
    }
    mock.is_active = is_active
    mock.enabled_modules = enabled_modules or ["ma_trend", "indicator_params"]
    return mock


def _make_stocks_data() -> dict[str, dict[str, Any]]:
    """创建测试用的股票因子数据。"""
    return {
        "000001.SZ": {"ma_trend": 85.0, "close": Decimal("15.50")},
        "600519.SH": {"ma_trend": 92.0, "close": Decimal("1800.00")},
    }


# ---------------------------------------------------------------------------
# _load_active_strategy_async 测试（需求 2.2）
# ---------------------------------------------------------------------------


class TestLoadActiveStrategyAsync:
    """从 strategy_template 表查询活跃策略模板"""

    @pytest.mark.asyncio
    async def test_returns_active_strategy(self):
        """应返回 is_active=True 的策略模板配置"""
        template = _make_strategy_template_mock(
            enabled_modules=["ma_trend", "breakout"],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = template

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.tasks.screening.AsyncSessionPG",
            return_value=mock_session,
        ):
            config, strategy_id, enabled_modules = await _load_active_strategy_async()

        assert isinstance(config, StrategyConfig)
        assert strategy_id == str(template.id)
        assert enabled_modules == ["ma_trend", "breakout"]

    @pytest.mark.asyncio
    async def test_returns_default_when_no_active_strategy(self):
        """无活跃策略时应返回默认空策略"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.tasks.screening.AsyncSessionPG",
            return_value=mock_session,
        ):
            config, strategy_id, enabled_modules = await _load_active_strategy_async()

        assert isinstance(config, StrategyConfig)
        assert strategy_id == ""
        assert enabled_modules == []

    @pytest.mark.asyncio
    async def test_returns_empty_modules_when_none(self):
        """enabled_modules 为 None 时应返回空列表"""
        template = _make_strategy_template_mock(enabled_modules=None)
        template.enabled_modules = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = template

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.tasks.screening.AsyncSessionPG",
            return_value=mock_session,
        ):
            config, strategy_id, enabled_modules = await _load_active_strategy_async()

        assert enabled_modules == []


# ---------------------------------------------------------------------------
# _load_market_data_async 测试（需求 2.1）
# ---------------------------------------------------------------------------


class TestLoadMarketDataAsync:
    """通过 ScreenDataProvider 异步加载全市场数据"""

    @pytest.mark.asyncio
    async def test_loads_data_via_provider(self):
        """应通过 ScreenDataProvider.load_screen_data() 加载数据"""
        expected_data = _make_stocks_data()

        mock_pg = AsyncMock()
        mock_pg.__aenter__ = AsyncMock(return_value=mock_pg)
        mock_pg.__aexit__ = AsyncMock(return_value=False)

        mock_ts = AsyncMock()
        mock_ts.__aenter__ = AsyncMock(return_value=mock_ts)
        mock_ts.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_pg),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_ts),
            patch(
                "app.tasks.screening.ScreenDataProvider"
            ) as mock_provider_cls,
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value=expected_data)
            mock_provider_cls.return_value = mock_provider

            result = await _load_market_data_async(strategy_config={"test": True})

        assert result == expected_data
        mock_provider_cls.assert_called_once_with(
            pg_session=mock_pg,
            ts_session=mock_ts,
            strategy_config={"test": True},
        )
        mock_provider.load_screen_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_empty_config_when_none(self):
        """strategy_config 为 None 时应传递空字典"""
        mock_pg = AsyncMock()
        mock_pg.__aenter__ = AsyncMock(return_value=mock_pg)
        mock_pg.__aexit__ = AsyncMock(return_value=False)

        mock_ts = AsyncMock()
        mock_ts.__aenter__ = AsyncMock(return_value=mock_ts)
        mock_ts.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_pg),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_ts),
            patch(
                "app.tasks.screening.ScreenDataProvider"
            ) as mock_provider_cls,
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value={})
            mock_provider_cls.return_value = mock_provider

            result = await _load_market_data_async(strategy_config=None)

        assert result == {}
        mock_provider_cls.assert_called_once_with(
            pg_session=mock_pg,
            ts_session=mock_ts,
            strategy_config={},
        )


# ---------------------------------------------------------------------------
# _cache_screen_results 测试（需求 2.3）
# ---------------------------------------------------------------------------


class TestCacheScreenResults:
    """选股结果写入 Redis 缓存"""

    @pytest.mark.asyncio
    async def test_writes_result_and_last_run(self):
        """应同时写入 screen:results:{strategy_id} 和 screen:eod:last_run"""
        strategy_id = str(uuid.uuid4())
        result_summary = {"status": "success", "passed": 5}

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            await _cache_screen_results(
                strategy_id=strategy_id,
                result_summary=result_summary,
                elapsed_seconds=1.234,
                passed_count=5,
            )

        # 验证写入了两个 key
        assert mock_redis.set.call_count == 2

        # 验证 screen:results:{strategy_id}
        first_call = mock_redis.set.call_args_list[0]
        assert first_call[0][0] == f"{_RESULT_CACHE_PREFIX}{strategy_id}"
        cached_result = json.loads(first_call[0][1])
        assert cached_result["status"] == "success"
        assert cached_result["passed"] == 5
        assert first_call[1]["ex"] == _RESULT_CACHE_TTL

        # 验证 screen:eod:last_run
        second_call = mock_redis.set.call_args_list[1]
        assert second_call[0][0] == _LAST_RUN_KEY
        last_run = json.loads(second_call[0][1])
        assert last_run["strategy_id"] == strategy_id
        assert last_run["elapsed_seconds"] == 1.234
        assert last_run["passed_count"] == 5
        assert "run_time" in last_run
        assert second_call[1]["ex"] == _LAST_RUN_TTL

    @pytest.mark.asyncio
    async def test_handles_redis_failure_gracefully(self):
        """Redis 写入失败时不应抛出异常"""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis 连接失败"))
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            # 不应抛出异常
            await _cache_screen_results(
                strategy_id="test-id",
                result_summary={"status": "success"},
                elapsed_seconds=1.0,
                passed_count=3,
            )

    @pytest.mark.asyncio
    async def test_closes_redis_connection(self):
        """应始终关闭 Redis 连接"""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            await _cache_screen_results(
                strategy_id="test-id",
                result_summary={},
                elapsed_seconds=0.5,
                passed_count=0,
            )

        mock_redis.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# run_eod_screening 任务测试（需求 2 集成）
# ---------------------------------------------------------------------------


class TestRunEodScreeningPipeline:
    """盘后选股任务数据管线集成测试"""

    def test_uses_async_data_loading(self):
        """应通过异步函数加载策略和市场数据"""
        from app.tasks.screening import run_eod_screening

        template = _make_strategy_template_mock()
        stocks_data = _make_stocks_data()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = template

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_session),
            patch(
                "app.tasks.screening.ScreenDataProvider"
            ) as mock_provider_cls,
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value=stocks_data)
            mock_provider_cls.return_value = mock_provider

            result = run_eod_screening()

        assert result["status"] == "success"
        assert result["screen_type"] == "EOD"
        assert result["total_screened"] == 2
        assert "strategy_id" in result
        assert "elapsed_seconds" in result

    def test_uses_strategy_dict_when_provided(self):
        """传入 strategy_dict 时应使用该配置而非从数据库加载"""
        from app.tasks.screening import run_eod_screening

        strategy_dict = StrategyConfig().to_dict()

        mock_pg = AsyncMock()
        mock_pg.__aenter__ = AsyncMock(return_value=mock_pg)
        mock_pg.__aexit__ = AsyncMock(return_value=False)

        mock_ts = AsyncMock()
        mock_ts.__aenter__ = AsyncMock(return_value=mock_ts)
        mock_ts.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_pg),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_ts),
            patch(
                "app.tasks.screening.ScreenDataProvider"
            ) as mock_provider_cls,
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value={})
            mock_provider_cls.return_value = mock_provider

            result = run_eod_screening(strategy_dict=strategy_dict)

        assert result["status"] == "success"
        # strategy_id 应为空字符串（未从数据库加载）
        assert result["strategy_id"] == ""

    def test_writes_redis_cache_on_success(self):
        """成功完成后应写入 Redis 缓存"""
        from app.tasks.screening import run_eod_screening

        template = _make_strategy_template_mock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = template

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_session),
            patch(
                "app.tasks.screening.ScreenDataProvider"
            ) as mock_provider_cls,
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(return_value={})
            mock_provider_cls.return_value = mock_provider

            run_eod_screening()

        # 验证 Redis 写入被调用（2 次：结果缓存 + last_run）
        assert mock_redis.set.call_count == 2


# ---------------------------------------------------------------------------
# 重试逻辑测试（需求 2.4）
# ---------------------------------------------------------------------------


class TestRetryOnDatabaseFailure:
    """数据库连接失败时的 Celery 重试逻辑"""

    def test_retries_on_operational_error(self):
        """OperationalError 应触发重试"""
        from sqlalchemy.exc import OperationalError

        from app.tasks.screening import run_eod_screening

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=OperationalError("connection refused", {}, None)
        )
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch.object(
                run_eod_screening,
                "retry_with_backoff",
                side_effect=Exception("retry triggered"),
            ) as mock_retry,
        ):
            with pytest.raises(Exception, match="retry triggered"):
                run_eod_screening()

            mock_retry.assert_called_once()
            # 验证传入的异常是 OperationalError
            call_args = mock_retry.call_args
            assert isinstance(call_args[0][0], OperationalError)

    def test_retries_on_connection_error(self):
        """ConnectionError 应触发重试"""
        from app.tasks.screening import run_eod_screening

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=ConnectionError("Redis 连接失败")
        )
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch.object(
                run_eod_screening,
                "retry_with_backoff",
                side_effect=Exception("retry triggered"),
            ) as mock_retry,
        ):
            with pytest.raises(Exception, match="retry triggered"):
                run_eod_screening()

            mock_retry.assert_called_once()

    def test_retries_on_sqlalchemy_error(self):
        """SQLAlchemyError 应触发重试"""
        from sqlalchemy.exc import SQLAlchemyError

        from app.tasks.screening import run_eod_screening

        # 使用 strategy_dict 跳过策略加载，让错误发生在市场数据加载阶段
        strategy_dict = StrategyConfig().to_dict()

        mock_pg = AsyncMock()
        mock_pg.__aenter__ = AsyncMock(return_value=mock_pg)
        mock_pg.__aexit__ = AsyncMock(return_value=False)

        mock_ts = AsyncMock()
        mock_ts.__aenter__ = AsyncMock(return_value=mock_ts)
        mock_ts.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_pg),
            patch("app.tasks.screening.AsyncSessionTS", return_value=mock_ts),
            patch(
                "app.tasks.screening.ScreenDataProvider"
            ) as mock_provider_cls,
            patch.object(
                run_eod_screening,
                "retry_with_backoff",
                side_effect=Exception("retry triggered"),
            ) as mock_retry,
        ):
            mock_provider = AsyncMock()
            mock_provider.load_screen_data = AsyncMock(
                side_effect=SQLAlchemyError("数据库查询异常")
            )
            mock_provider_cls.return_value = mock_provider

            with pytest.raises(Exception, match="retry triggered"):
                run_eod_screening(strategy_dict=strategy_dict)

            mock_retry.assert_called_once()
