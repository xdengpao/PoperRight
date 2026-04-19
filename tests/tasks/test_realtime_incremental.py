"""
实时选股增量计算架构单元测试（需求 9）

覆盖场景：
- 9.1 _warmup_factor_cache：全量预热因子数据到 Redis
- 9.2 _incremental_update：增量更新因子（缓存合并）
- 9.3 run_realtime_screening：首次预热 + 后续增量模式
- 9.4 执行耗时超过 8 秒记录 WARNING 日志
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.schemas import StrategyConfig
from app.tasks.screening import (
    FACTOR_CACHE_PREFIX,
    FACTOR_CACHE_TTL,
    _FACTOR_WARMUP_KEY,
    _REALTIME_SLOW_THRESHOLD,
    _incremental_update,
    _is_factor_cache_warmed,
    _serialize_factor_dict,
    _warmup_factor_cache,
)


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------


def _make_strategy_config() -> StrategyConfig:
    """创建测试用策略配置。"""
    return StrategyConfig(
        factors=[],
        logic="AND",
        weights={"ma_trend": 1.0},
    )


def _make_stocks_data() -> dict[str, dict[str, Any]]:
    """创建测试用的全市场股票因子数据。"""
    return {
        "000001.SZ": {
            "name": "平安银行",
            "close": Decimal("15.50"),
            "open": Decimal("15.30"),
            "high": Decimal("15.80"),
            "low": Decimal("15.20"),
            "volume": 1000000,
            "amount": Decimal("15500000"),
            "turnover": Decimal("1.5"),
            "vol_ratio": Decimal("1.2"),
            "closes": [Decimal("15.0"), Decimal("15.3"), Decimal("15.5")],
            "ma_trend": 85.0,
            "ma_support": True,
            "macd": True,
            "boll": False,
            "rsi": True,
            "dma": {"dma": 0.5, "ama": 0.3},
            "breakout": None,
            "breakout_list": [],
            "turnover_check": True,
            "pe_ttm": 8.5,
            "pb": 1.2,
            "roe": 12.0,
            "market_cap": 300000.0,
            "money_flow": True,
            "large_order": False,
            "main_net_inflow": 500.0,
            "large_order_ratio": 25.0,
            "sector_rank": 5,
            "sector_trend": True,
            "sector_name": "银行",
            "raw_close": Decimal("15.50"),
        },
        "600519.SH": {
            "name": "贵州茅台",
            "close": Decimal("1800.00"),
            "open": Decimal("1790.00"),
            "high": Decimal("1810.00"),
            "low": Decimal("1785.00"),
            "volume": 50000,
            "amount": Decimal("90000000"),
            "turnover": Decimal("0.5"),
            "vol_ratio": Decimal("0.8"),
            "closes": [Decimal("1780"), Decimal("1790"), Decimal("1800")],
            "ma_trend": 92.0,
            "ma_support": True,
            "macd": True,
            "boll": True,
            "rsi": False,
            "dma": None,
            "breakout": None,
            "breakout_list": [],
            "turnover_check": False,
            "pe_ttm": 35.0,
            "pb": 12.0,
            "roe": 30.0,
            "market_cap": 2200000.0,
            "money_flow": False,
            "large_order": True,
            "main_net_inflow": -200.0,
            "large_order_ratio": 40.0,
            "sector_rank": 10,
            "sector_trend": False,
            "sector_name": "白酒",
            "raw_close": Decimal("1800.00"),
        },
    }


def _make_cached_factor_json(factor_dict: dict[str, Any]) -> str:
    """将因子字典序列化为 Redis 中存储的 JSON 字符串。"""
    serialized = _serialize_factor_dict(factor_dict)
    return json.dumps(serialized, ensure_ascii=False)


# ---------------------------------------------------------------------------
# _serialize_factor_dict 测试
# ---------------------------------------------------------------------------


class TestSerializeFactorDict:
    """因子字典序列化测试"""

    def test_converts_decimal_to_str(self):
        """Decimal 值应转为字符串"""
        fd = {"close": Decimal("15.50"), "volume": 1000}
        result = _serialize_factor_dict(fd)
        assert result["close"] == "15.50"
        assert result["volume"] == 1000

    def test_converts_decimal_list_to_str_list(self):
        """Decimal 列表应转为字符串列表"""
        fd = {"closes": [Decimal("15.0"), Decimal("15.5")]}
        result = _serialize_factor_dict(fd)
        assert result["closes"] == ["15.0", "15.5"]

    def test_preserves_non_decimal_values(self):
        """非 Decimal 值应保持不变"""
        fd = {"ma_trend": 85.0, "macd": True, "name": "测试"}
        result = _serialize_factor_dict(fd)
        assert result == fd


# ---------------------------------------------------------------------------
# _warmup_factor_cache 测试（需求 9.1）
# ---------------------------------------------------------------------------


class TestWarmupFactorCache:
    """全量因子预热测试"""

    @pytest.mark.asyncio
    async def test_writes_all_symbols_to_redis(self):
        """应将所有股票因子数据写入 Redis"""
        stocks_data = _make_stocks_data()

        mock_pipe = AsyncMock()
        mock_pipe.set = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[True] * (len(stocks_data) + 1))

        mock_redis = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.aclose = AsyncMock()

        with (
            patch(
                "app.tasks.screening._load_market_data_async",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            result = await _warmup_factor_cache(strategy_config={"test": True})

        # 应返回全量数据
        assert result == stocks_data

        # 验证 pipeline 写入了每只股票 + 预热标记
        # 每只股票一次 set + 预热标记一次 set
        assert mock_pipe.set.call_count == len(stocks_data) + 1
        mock_pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_correct_cache_keys_and_ttl(self):
        """缓存键格式和 TTL 应正确"""
        stocks_data = {"000001.SZ": {"close": Decimal("15.50"), "ma_trend": 85.0}}

        mock_pipe = AsyncMock()
        set_calls = []
        mock_pipe.set = MagicMock(side_effect=lambda *a, **kw: set_calls.append((a, kw)))
        mock_pipe.execute = AsyncMock(return_value=[True, True])

        mock_redis = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.aclose = AsyncMock()

        with (
            patch(
                "app.tasks.screening._load_market_data_async",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            await _warmup_factor_cache()

        # 验证因子缓存键
        factor_call = set_calls[0]
        assert factor_call[0][0] == f"{FACTOR_CACHE_PREFIX}000001.SZ"
        assert factor_call[1]["ex"] == FACTOR_CACHE_TTL

        # 验证预热标记键
        warmup_call = set_calls[1]
        assert warmup_call[0][0] == _FACTOR_WARMUP_KEY
        assert warmup_call[0][1] == "1"
        assert warmup_call[1]["ex"] == FACTOR_CACHE_TTL

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_data(self):
        """无市场数据时应返回空字典"""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch(
                "app.tasks.screening._load_market_data_async",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            result = await _warmup_factor_cache()

        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_redis_failure_gracefully(self):
        """Redis 写入失败时不应抛出异常，仍返回数据"""
        stocks_data = _make_stocks_data()

        mock_pipe = AsyncMock()
        mock_pipe.set = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=ConnectionError("Redis 连接失败"))

        mock_redis = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.aclose = AsyncMock()

        with (
            patch(
                "app.tasks.screening._load_market_data_async",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            result = await _warmup_factor_cache()

        # 即使 Redis 失败，仍应返回数据
        assert result == stocks_data


# ---------------------------------------------------------------------------
# _incremental_update 测试（需求 9.2）
# ---------------------------------------------------------------------------


class TestIncrementalUpdate:
    """增量更新因子测试"""

    @pytest.mark.asyncio
    async def test_merges_cached_and_realtime_factors(self):
        """应合并缓存的基本面因子和实时因子"""
        # 缓存中的因子数据（包含基本面和板块因子）
        cached_factors = {
            "name": "平安银行",
            "pe_ttm": 8.5,
            "pb": 1.2,
            "roe": 12.0,
            "market_cap": 300000.0,
            "money_flow": True,
            "large_order": False,
            "main_net_inflow": 500.0,
            "large_order_ratio": 25.0,
            "sector_rank": 5,
            "sector_trend": True,
            "sector_name": "银行",
            "close": "15.30",  # 旧的收盘价
            "ma_trend": 80.0,  # 旧的均线趋势
        }

        # 最新实时数据（包含更新的实时因子）
        latest_bars = {
            "000001.SZ": {
                "close": Decimal("15.80"),
                "ma_trend": 88.0,
                "macd": True,
                "boll": False,
                "rsi": True,
                "volume": 1200000,
            },
        }

        cached_json = json.dumps(cached_factors, ensure_ascii=False)

        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=[cached_json])
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            result = await _incremental_update(latest_bars)

        assert "000001.SZ" in result
        merged = result["000001.SZ"]

        # 基本面因子应来自缓存
        assert merged["pe_ttm"] == 8.5
        assert merged["pb"] == 1.2
        assert merged["money_flow"] is True
        assert merged["sector_rank"] == 5
        assert merged["sector_trend"] is True
        assert merged["name"] == "平安银行"

        # 实时因子应来自最新数据
        assert merged["close"] == Decimal("15.80")
        assert merged["ma_trend"] == 88.0
        assert merged["macd"] is True
        assert merged["volume"] == 1200000

    @pytest.mark.asyncio
    async def test_skips_symbols_without_cache(self):
        """缓存未命中的股票应被跳过"""
        latest_bars = {
            "000001.SZ": {"close": Decimal("15.80"), "ma_trend": 88.0},
            "999999.SZ": {"close": Decimal("10.00"), "ma_trend": 50.0},
        }

        mock_redis = AsyncMock()
        # 第一只有缓存，第二只无缓存
        mock_redis.mget = AsyncMock(return_value=[
            json.dumps({"pe_ttm": 8.5, "name": "平安银行"}),
            None,
        ])
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            result = await _incremental_update(latest_bars)

        assert "000001.SZ" in result
        assert "999999.SZ" not in result

    @pytest.mark.asyncio
    async def test_returns_empty_on_empty_input(self):
        """空输入应返回空字典"""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            result = await _incremental_update({})

        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_redis_failure_gracefully(self):
        """Redis 读取失败时应返回空字典"""
        latest_bars = {"000001.SZ": {"close": Decimal("15.80")}}

        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(side_effect=ConnectionError("Redis 连接失败"))
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            result = await _incremental_update(latest_bars)

        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self):
        """缓存中的无效 JSON 应被跳过"""
        latest_bars = {"000001.SZ": {"close": Decimal("15.80")}}

        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=["not-valid-json{{{"])
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            result = await _incremental_update(latest_bars)

        assert "000001.SZ" not in result


# ---------------------------------------------------------------------------
# _is_factor_cache_warmed 测试
# ---------------------------------------------------------------------------


class TestIsFactorCacheWarmed:
    """因子缓存预热标记检查测试"""

    @pytest.mark.asyncio
    async def test_returns_true_when_warmed(self):
        """预热标记存在时应返回 True"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            assert await _is_factor_cache_warmed() is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_warmed(self):
        """预热标记不存在时应返回 False"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            assert await _is_factor_cache_warmed() is False

    @pytest.mark.asyncio
    async def test_returns_false_on_redis_failure(self):
        """Redis 连接失败时应返回 False"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis 连接失败"))
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.tasks.screening.get_redis_client",
            return_value=mock_redis,
        ):
            assert await _is_factor_cache_warmed() is False


# ---------------------------------------------------------------------------
# run_realtime_screening 任务测试（需求 9.3 + 9.4）
# ---------------------------------------------------------------------------


class TestRunRealtimeScreeningIncremental:
    """盘中实时选股增量计算模式测试"""

    @patch("app.tasks.screening._is_trading_hours", return_value=False)
    def test_skips_outside_trading_hours(self, mock_hours):
        """非交易时段应跳过"""
        from app.tasks.screening import run_realtime_screening

        result = run_realtime_screening()
        assert result["status"] == "skipped"
        assert result["reason"] == "outside_trading_hours"

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_warmup_on_first_execution(self, mock_hours):
        """首次执行应触发全量预热（需求 9.3）"""
        from app.tasks.screening import run_realtime_screening

        stocks_data = {"000001.SZ": {"ma_trend": 85.0, "close": Decimal("15.50")}}

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # 未预热
        mock_redis.aclose = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ) as mock_warmup,
        ):
            result = run_realtime_screening()

        assert result["status"] == "success"
        assert result["screen_type"] == "REALTIME"
        assert result["mode"] == "warmup"
        mock_warmup.assert_awaited_once()

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_incremental_mode_after_warmup(self, mock_hours):
        """预热后应使用增量模式（需求 9.3）"""
        from app.tasks.screening import run_realtime_screening

        stocks_data = {"000001.SZ": {"ma_trend": 85.0, "close": Decimal("15.50")}}
        merged_data = {
            "000001.SZ": {
                "ma_trend": 88.0,
                "close": Decimal("15.80"),
                "pe_ttm": 8.5,
            },
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")  # 已预热
        mock_redis.aclose = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._load_market_data_async",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
            patch(
                "app.tasks.screening._incremental_update",
                new_callable=AsyncMock,
                return_value=merged_data,
            ) as mock_incr,
        ):
            result = run_realtime_screening()

        assert result["status"] == "success"
        assert result["mode"] == "incremental"
        mock_incr.assert_awaited_once()

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_slow_execution_logs_warning(self, mock_hours, caplog):
        """执行耗时超过 8 秒应记录 WARNING 日志（需求 9.4）"""
        import time as time_mod_real
        from app.tasks.screening import run_realtime_screening

        stocks_data = {"000001.SZ": {"ma_trend": 85.0, "close": Decimal("15.50")}}

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # 模拟 time.monotonic 使得耗时超过 8 秒
        original_monotonic = time_mod_real.monotonic
        call_count = [0]

        def mock_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return 100.0  # start_time
            return 109.0  # elapsed = 9.0 秒

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
            patch("app.tasks.screening.time_mod.monotonic", side_effect=mock_monotonic),
            caplog.at_level(logging.WARNING, logger="app.tasks.screening"),
        ):
            result = run_realtime_screening()

        assert result["status"] == "success"
        assert result["elapsed_seconds"] == 9.0
        # 验证 WARNING 日志
        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("超过" in msg and "8" in msg for msg in warning_msgs), (
            f"未找到超时 WARNING 日志，实际日志: {warning_msgs}"
        )

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_fast_execution_no_warning(self, mock_hours, caplog):
        """执行耗时未超过 8 秒不应记录 WARNING 日志"""
        import time as time_mod_real
        from app.tasks.screening import run_realtime_screening

        stocks_data = {"000001.SZ": {"ma_trend": 85.0, "close": Decimal("15.50")}}

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        call_count = [0]

        def mock_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return 100.0
            return 102.0  # elapsed = 2.0 秒

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
            patch("app.tasks.screening.time_mod.monotonic", side_effect=mock_monotonic),
            caplog.at_level(logging.WARNING, logger="app.tasks.screening"),
        ):
            result = run_realtime_screening()

        assert result["status"] == "success"
        assert result["elapsed_seconds"] == 2.0
        # 不应有超时 WARNING
        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert not any("超过" in msg and "8" in msg for msg in warning_msgs)

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_accepts_strategy_dict(self, mock_hours):
        """应接受策略字典参数"""
        from app.tasks.screening import run_realtime_screening

        stocks_data = {}

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with (
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value=stocks_data,
            ),
        ):
            strategy_dict = _make_strategy_config().to_dict()
            result = run_realtime_screening(strategy_dict=strategy_dict)

        assert result["status"] == "success"
        assert result["screen_type"] == "REALTIME"

    @patch("app.tasks.screening._is_trading_hours", return_value=True)
    def test_result_includes_elapsed_seconds(self, mock_hours):
        """结果应包含 elapsed_seconds 字段"""
        from app.tasks.screening import run_realtime_screening

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.tasks.screening.AsyncSessionPG", return_value=mock_session),
            patch(
                "app.tasks.screening.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "app.tasks.screening._warmup_factor_cache",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = run_realtime_screening()

        assert "elapsed_seconds" in result
        assert isinstance(result["elapsed_seconds"], float)
