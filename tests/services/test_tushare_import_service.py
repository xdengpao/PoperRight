"""
TushareImportService 单元测试

覆盖：
- _resolve_token: 三级 Token 路由、回退、空 Token 报错
- _validate_params: 必填参数缺失、日期格式校验、代码格式校验、合法参数通过
- start_import: 成功分发 Celery 任务、未知接口报错、并发保护
- stop_import: 设置停止信号、更新进度、撤销 Celery 任务
- get_import_status: 返回进度数据、缺失键返回 unknown
- get_import_history: 返回格式化的日志记录
- check_health: 已连接和未连接状态

对应需求：20.1, 21.2, 22.1, 22a.3, 23.4, 24.5
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_engine.tushare_import_service import TushareImportService
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    CodeFormat,
    ParamType,
    RateLimitGroup,
    StorageEngine,
    TokenTier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entry(**overrides) -> ApiEntry:
    """创建测试用 ApiEntry，可覆盖任意字段。"""
    defaults = dict(
        api_name="daily",
        label="日线行情",
        category="stock_data",
        subcategory="行情数据（低频：日K/周K/月K）",
        token_tier=TokenTier.BASIC,
        target_table="kline",
        storage_engine=StorageEngine.TS,
        code_format=CodeFormat.STOCK_SYMBOL,
        conflict_columns=["time", "symbol", "freq", "adj_type"],
        conflict_action="do_nothing",
        update_columns=[],
        field_mappings=[],
        required_params=[ParamType.DATE_RANGE],
        optional_params=[ParamType.STOCK_CODE],
        rate_limit_group=RateLimitGroup.KLINE,
        batch_by_code=True,
    )
    defaults.update(overrides)
    return ApiEntry(**defaults)


@pytest.fixture
def svc() -> TushareImportService:
    return TushareImportService()


# ===========================================================================
# _resolve_token
# ===========================================================================


class TestResolveToken:
    """_resolve_token 三级 Token 路由测试。"""

    def test_basic_tier_returns_basic_token(self, svc: TushareImportService) -> None:
        """basic 级别 Token 已配置时直接返回。"""
        with patch("app.services.data_engine.tushare_import_service.settings") as m:
            m.tushare_token_basic = "tok_basic"
            m.tushare_token_advanced = ""
            m.tushare_token_special = ""
            m.tushare_api_token = "tok_default"
            assert svc._resolve_token(TokenTier.BASIC) == "tok_basic"

    def test_advanced_tier_returns_advanced_token(self, svc: TushareImportService) -> None:
        """advanced 级别 Token 已配置时直接返回。"""
        with patch("app.services.data_engine.tushare_import_service.settings") as m:
            m.tushare_token_basic = ""
            m.tushare_token_advanced = "tok_adv"
            m.tushare_token_special = ""
            m.tushare_api_token = ""
            assert svc._resolve_token(TokenTier.ADVANCED) == "tok_adv"

    def test_special_tier_returns_special_token(self, svc: TushareImportService) -> None:
        """special 级别 Token 已配置时直接返回。"""
        with patch("app.services.data_engine.tushare_import_service.settings") as m:
            m.tushare_token_basic = ""
            m.tushare_token_advanced = ""
            m.tushare_token_special = "tok_sp"
            m.tushare_api_token = ""
            assert svc._resolve_token(TokenTier.SPECIAL) == "tok_sp"

    def test_fallback_to_default_token(self, svc: TushareImportService) -> None:
        """对应级别 Token 为空时回退到 tushare_api_token。"""
        with patch("app.services.data_engine.tushare_import_service.settings") as m:
            m.tushare_token_basic = ""
            m.tushare_token_advanced = ""
            m.tushare_token_special = ""
            m.tushare_api_token = "tok_fallback"
            assert svc._resolve_token(TokenTier.BASIC) == "tok_fallback"
            assert svc._resolve_token(TokenTier.ADVANCED) == "tok_fallback"
            assert svc._resolve_token(TokenTier.SPECIAL) == "tok_fallback"

    def test_raises_when_all_empty(self, svc: TushareImportService) -> None:
        """对应级别和默认 Token 均为空时抛出 ValueError。"""
        with patch("app.services.data_engine.tushare_import_service.settings") as m:
            m.tushare_token_basic = ""
            m.tushare_token_advanced = ""
            m.tushare_token_special = ""
            m.tushare_api_token = ""
            with pytest.raises(ValueError, match="Token 未配置"):
                svc._resolve_token(TokenTier.BASIC)


# ===========================================================================
# _validate_params
# ===========================================================================


class TestValidateParams:
    """_validate_params 参数校验测试。"""

    def test_missing_required_date_range(self, svc: TushareImportService) -> None:
        """缺少必填的日期范围参数时抛出 ValueError。"""
        entry = _make_entry(required_params=[ParamType.DATE_RANGE])
        with pytest.raises(ValueError, match="必填参数缺失"):
            svc._validate_params(entry, {})

    def test_missing_required_stock_code(self, svc: TushareImportService) -> None:
        """缺少必填的股票代码参数时抛出 ValueError。"""
        entry = _make_entry(required_params=[ParamType.STOCK_CODE])
        with pytest.raises(ValueError, match="ts_code"):
            svc._validate_params(entry, {})

    def test_invalid_date_format(self, svc: TushareImportService) -> None:
        """日期格式不符合 YYYYMMDD 时抛出 ValueError。"""
        entry = _make_entry(required_params=[ParamType.DATE_RANGE])
        with pytest.raises(ValueError, match="日期格式错误"):
            svc._validate_params(entry, {"start_date": "2024-01-01"})

    def test_invalid_stock_code_format(self, svc: TushareImportService) -> None:
        """股票代码格式不符合 6 位数字时抛出 ValueError。"""
        entry = _make_entry(
            required_params=[ParamType.STOCK_CODE],
            code_format=CodeFormat.STOCK_SYMBOL,
        )
        with pytest.raises(ValueError, match="股票代码格式错误"):
            svc._validate_params(entry, {"ts_code": "ABC"})

    def test_valid_params_pass(self, svc: TushareImportService) -> None:
        """合法参数通过校验并原样返回。"""
        entry = _make_entry(required_params=[ParamType.DATE_RANGE])
        params = {"start_date": "20240101", "end_date": "20240131"}
        result = svc._validate_params(entry, params)
        assert result == params

    def test_valid_stock_code_with_suffix(self, svc: TushareImportService) -> None:
        """带后缀的股票代码（如 600000.SH）通过校验。"""
        entry = _make_entry(
            required_params=[ParamType.STOCK_CODE],
            code_format=CodeFormat.STOCK_SYMBOL,
        )
        params = {"ts_code": "600000.SH"}
        result = svc._validate_params(entry, params)
        assert result == params

    def test_valid_multiple_stock_codes(self, svc: TushareImportService) -> None:
        """逗号分隔的多个股票代码通过校验。"""
        entry = _make_entry(
            required_params=[ParamType.STOCK_CODE],
            code_format=CodeFormat.STOCK_SYMBOL,
        )
        params = {"ts_code": "600000.SH,000001.SZ"}
        result = svc._validate_params(entry, params)
        assert result == params

    def test_trade_date_satisfies_date_range(self, svc: TushareImportService) -> None:
        """trade_date 可替代 start_date 满足 DATE_RANGE 必填要求。"""
        entry = _make_entry(required_params=[ParamType.DATE_RANGE])
        params = {"trade_date": "20240115"}
        result = svc._validate_params(entry, params)
        assert result == params


# ===========================================================================
# start_import
# ===========================================================================


class TestStartImport:
    """start_import 任务分发测试。"""

    async def test_successful_dispatch(self, svc: TushareImportService) -> None:
        """成功分发 Celery 任务并返回 task_id。"""
        entry = _make_entry(api_name="stock_basic", required_params=[])
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = False
        mock_celery = MagicMock()

        with (
            patch("app.services.data_engine.tushare_import_service.get_entry", return_value=entry),
            patch("app.services.data_engine.tushare_import_service.settings") as mock_settings,
            patch("app.services.data_engine.tushare_import_service.get_redis_client", return_value=mock_redis),
            patch("app.services.data_engine.tushare_import_service.cache_set", new_callable=AsyncMock),
            patch.object(svc, "_create_import_log", new_callable=AsyncMock, return_value=42),
            patch("app.core.celery_app.celery_app", mock_celery),
        ):
            mock_settings.tushare_token_basic = "tok"
            mock_settings.tushare_token_advanced = ""
            mock_settings.tushare_token_special = ""
            mock_settings.tushare_api_token = ""

            result = await svc.start_import("stock_basic", {})

            assert "task_id" in result
            assert result["log_id"] == 42
            assert result["status"] == "pending"
            mock_celery.send_task.assert_called_once()

    async def test_unknown_api_name_raises(self, svc: TushareImportService) -> None:
        """未知接口名称抛出 ValueError。"""
        with patch("app.services.data_engine.tushare_import_service.get_entry", return_value=None):
            with pytest.raises(ValueError, match="未知的 Tushare 接口"):
                await svc.start_import("nonexistent_api", {})

    async def test_concurrent_protection_raises(self, svc: TushareImportService) -> None:
        """同一接口已有任务运行时抛出 RuntimeError。"""
        entry = _make_entry(api_name="daily", required_params=[ParamType.DATE_RANGE])
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True  # 锁已存在

        with (
            patch("app.services.data_engine.tushare_import_service.get_entry", return_value=entry),
            patch("app.services.data_engine.tushare_import_service.settings") as mock_settings,
            patch("app.services.data_engine.tushare_import_service.get_redis_client", return_value=mock_redis),
        ):
            mock_settings.tushare_token_basic = "tok"
            mock_settings.tushare_token_advanced = ""
            mock_settings.tushare_token_special = ""
            mock_settings.tushare_api_token = ""

            with pytest.raises(RuntimeError, match="已有导入任务在运行"):
                await svc.start_import("daily", {"start_date": "20240101"})


# ===========================================================================
# stop_import
# ===========================================================================


class TestStopImport:
    """stop_import 停止导入测试。"""

    async def test_sets_stop_signal_and_revokes(self, svc: TushareImportService) -> None:
        """停止导入时设置 Redis 停止信号并撤销 Celery 任务。"""
        progress_data = json.dumps({
            "total": 100,
            "completed": 50,
            "failed": 0,
            "status": "running",
            "current_item": "600000.SH",
        })
        mock_celery = MagicMock()

        with (
            patch("app.services.data_engine.tushare_import_service.cache_set", new_callable=AsyncMock) as mock_set,
            patch("app.services.data_engine.tushare_import_service.cache_get", new_callable=AsyncMock, return_value=progress_data),
            patch("app.core.celery_app.celery_app", mock_celery),
        ):
            result = await svc.stop_import("task-123")

            assert result == {"message": "停止信号已发送"}
            # 验证设置了停止信号
            calls = mock_set.call_args_list
            stop_call = [c for c in calls if "stop:" in str(c)]
            assert len(stop_call) >= 1
            # 验证撤销了 Celery 任务
            mock_celery.control.revoke.assert_called_once_with("task-123", terminate=True)

    async def test_updates_progress_to_stopped(self, svc: TushareImportService) -> None:
        """停止导入时更新 Redis 进度状态为 stopped。"""
        progress_data = json.dumps({
            "total": 100,
            "completed": 50,
            "failed": 0,
            "status": "running",
            "current_item": "",
        })

        with (
            patch("app.services.data_engine.tushare_import_service.cache_set", new_callable=AsyncMock) as mock_set,
            patch("app.services.data_engine.tushare_import_service.cache_get", new_callable=AsyncMock, return_value=progress_data),
            patch("app.core.celery_app.celery_app", MagicMock()),
        ):
            await svc.stop_import("task-456")

            # 找到更新进度的 cache_set 调用（非 stop 信号的那个）
            progress_calls = [
                c for c in mock_set.call_args_list
                if c.args and "stop:" not in str(c.args[0])
            ]
            assert len(progress_calls) >= 1
            # 验证进度中 status 被更新为 stopped
            for call in progress_calls:
                if call.args and "tushare:import:task-456" in str(call.args[0]):
                    saved = json.loads(call.args[1])
                    assert saved["status"] == "stopped"


# ===========================================================================
# get_import_status
# ===========================================================================


class TestGetImportStatus:
    """get_import_status 进度查询测试。"""

    async def test_returns_progress_data(self, svc: TushareImportService) -> None:
        """正常返回 Redis 中的进度数据。"""
        progress = {
            "total": 200,
            "completed": 150,
            "failed": 5,
            "status": "running",
            "current_item": "000001.SZ",
        }
        with patch(
            "app.services.data_engine.tushare_import_service.cache_get",
            new_callable=AsyncMock,
            return_value=json.dumps(progress),
        ):
            result = await svc.get_import_status("task-789")
            assert result["total"] == 200
            assert result["completed"] == 150
            assert result["failed"] == 5
            assert result["status"] == "running"
            assert result["current_item"] == "000001.SZ"

    async def test_returns_unknown_for_missing_key(self, svc: TushareImportService) -> None:
        """Redis 中不存在进度键时返回 status=unknown。"""
        with patch(
            "app.services.data_engine.tushare_import_service.cache_get",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await svc.get_import_status("nonexistent-task")
            assert result == {"status": "unknown"}

    async def test_returns_unknown_for_invalid_json(self, svc: TushareImportService) -> None:
        """Redis 中存储的数据不是有效 JSON 时返回 status=unknown。"""
        with patch(
            "app.services.data_engine.tushare_import_service.cache_get",
            new_callable=AsyncMock,
            return_value="not-valid-json{{{",
        ):
            result = await svc.get_import_status("bad-json-task")
            assert result == {"status": "unknown"}


# ===========================================================================
# get_import_history
# ===========================================================================


class TestGetImportHistory:
    """get_import_history 导入历史查询测试。"""

    async def test_returns_formatted_records(self, svc: TushareImportService) -> None:
        """返回格式化的导入日志记录列表。"""
        from datetime import datetime

        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.api_name = "stock_basic"
        mock_log.params_json = {"market": "SSE"}
        mock_log.status = "completed"
        mock_log.record_count = 5200
        mock_log.error_message = None
        mock_log.started_at = datetime(2024, 1, 15, 10, 30, 0)
        mock_log.finished_at = datetime(2024, 1, 15, 10, 30, 3)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.database.AsyncSessionPG",
            return_value=mock_session,
        ):
            result = await svc.get_import_history(limit=20)

            assert len(result) == 1
            record = result[0]
            assert record["id"] == 1
            assert record["api_name"] == "stock_basic"
            assert record["status"] == "completed"
            assert record["record_count"] == 5200
            assert record["error_message"] is None
            assert record["started_at"] == "2024-01-15T10:30:00"
            assert record["finished_at"] == "2024-01-15T10:30:03"


# ===========================================================================
# check_health
# ===========================================================================


class TestCheckHealth:
    """check_health 连通性检查测试。"""

    async def test_connected_state(self, svc: TushareImportService) -> None:
        """Token 已配置且连通性检查通过时返回 connected=True。"""
        mock_adapter = AsyncMock()
        mock_adapter.health_check.return_value = True

        with (
            patch("app.services.data_engine.tushare_import_service.settings") as mock_settings,
            patch(
                "app.services.data_engine.tushare_adapter.TushareAdapter",
                return_value=mock_adapter,
            ),
        ):
            mock_settings.tushare_token_basic = "tok_b"
            mock_settings.tushare_token_advanced = "tok_a"
            mock_settings.tushare_token_special = ""
            mock_settings.tushare_api_token = ""

            result = await svc.check_health()

            assert result["connected"] is True
            assert result["tokens"]["basic"]["configured"] is True
            assert result["tokens"]["advanced"]["configured"] is True
            assert result["tokens"]["special"]["configured"] is False

    async def test_disconnected_state(self, svc: TushareImportService) -> None:
        """所有 Token 均为空时返回 connected=False。"""
        with patch("app.services.data_engine.tushare_import_service.settings") as mock_settings:
            mock_settings.tushare_token_basic = ""
            mock_settings.tushare_token_advanced = ""
            mock_settings.tushare_token_special = ""
            mock_settings.tushare_api_token = ""

            result = await svc.check_health()

            assert result["connected"] is False
            assert result["tokens"]["basic"]["configured"] is False
            assert result["tokens"]["advanced"]["configured"] is False
            assert result["tokens"]["special"]["configured"] is False

    async def test_health_check_exception_returns_disconnected(self, svc: TushareImportService) -> None:
        """连通性检查抛出异常时返回 connected=False。"""
        mock_adapter = AsyncMock()
        mock_adapter.health_check.side_effect = ConnectionError("timeout")

        with (
            patch("app.services.data_engine.tushare_import_service.settings") as mock_settings,
            patch(
                "app.services.data_engine.tushare_adapter.TushareAdapter",
                return_value=mock_adapter,
            ),
        ):
            mock_settings.tushare_token_basic = "tok"
            mock_settings.tushare_token_advanced = ""
            mock_settings.tushare_token_special = ""
            mock_settings.tushare_api_token = ""

            result = await svc.check_health()

            assert result["connected"] is False
