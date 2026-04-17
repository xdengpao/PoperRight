"""
SectorImportService 单元测试

Tests:
- File scanning discovers correct files per data source
- Batch size splitting logic
- Progress update and heartbeat
- Stop signal detection
- Zombie task detection (heartbeat timeout)
- Error handling: skip failed files, continue processing

Requirements: 5.1–5.8, 6.1–6.6
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.sector import DataSource
from app.services.data_engine.sector_import import SectorImportService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRedis:
    """In-memory fake Redis for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hset(self, name: str, key: str, value: str) -> int:
        self._hashes.setdefault(name, {})[key] = value
        return 1

    async def aclose(self) -> None:
        pass


def _build_dir_structure(base: Path) -> None:
    """Create a directory structure matching the actual file system layout."""
    # DC sector list
    (base / "概念板块列表_东财.csv").write_text("header\n", encoding="utf-8")
    # DC historical kline dirs with sector lists
    dc_concept = base / "东方财富_概念板块_历史行情数据"
    dc_concept.mkdir(parents=True)
    (dc_concept / "东方财富概念板块列表.csv").write_text("header\n", encoding="utf-8")
    (dc_concept / "概念板块_日k.zip").write_bytes(b"PK\x03\x04dummy")
    dc_industry = base / "东方财富_行业板块_历史行情数据"
    dc_industry.mkdir(parents=True)
    (dc_industry / "东方财富行业板块列表.csv").write_text("header\n", encoding="utf-8")
    (dc_industry / "行业板块_日k.zip").write_bytes(b"PK\x03\x04dummy")
    # DC incremental sector list
    dc_incr_list = base / "增量数据" / "概念板块_东财" / "2024-01"
    dc_incr_list.mkdir(parents=True)
    (dc_incr_list / "2024-01-15.csv").write_text("header\n", encoding="utf-8")

    # DC constituents
    (base / "概念板块_东财.zip").write_bytes(b"PK\x03\x04dummy")
    dc_const = base / "板块成分_东财" / "2024-01"
    dc_const.mkdir(parents=True)
    (dc_const / "板块成分_DC_20240115.zip").write_bytes(b"PK\x03\x04dummy")

    # DC kline
    (base / "板块行情_东财.zip").write_bytes(b"PK\x03\x04dummy")
    dc_incr_kline = base / "增量数据" / "板块行情_东财" / "2024-01"
    dc_incr_kline.mkdir(parents=True)
    (dc_incr_kline / "2024-01-15.csv").write_text("header\n", encoding="utf-8")

    # TI sector list
    (base / "行业概念板块_同花顺.csv").write_text("header\n", encoding="utf-8")

    # TI constituents
    (base / "概念板块成分汇总_同花顺.csv").write_text("header\n", encoding="utf-8")
    (base / "行业板块成分汇总_同花顺.csv").write_text("header\n", encoding="utf-8")
    (base / "概念板块成分_同花顺.zip").write_bytes(b"PK\x03\x04dummy")
    ti_const = base / "板块成分_同花顺" / "概念板块成分汇总_同花顺" / "2024-01"
    ti_const.mkdir(parents=True)
    (ti_const / "概念板块成分汇总_同花顺_20240115.csv").write_text("header\n", encoding="utf-8")

    # TI kline
    (base / "板块指数行情_同花顺.zip").write_bytes(b"PK\x03\x04dummy")
    ti_incr_kline = base / "增量数据" / "板块指数行情_同花顺" / "2024-01"
    ti_incr_kline.mkdir(parents=True)
    (ti_incr_kline / "2024-01-15.csv").write_text("header\n", encoding="utf-8")

    # TDX sector list
    (base / "通达信板块列表.csv").write_text("header\n", encoding="utf-8")
    (base / "板块信息_通达信.zip").write_bytes(b"PK\x03\x04dummy")
    tdx_incr_info = base / "增量数据" / "板块信息_通达信" / "2024-01"
    tdx_incr_info.mkdir(parents=True)
    (tdx_incr_info / "2024-01-15.csv").write_text("header\n", encoding="utf-8")

    # TDX constituents
    tdx_const = base / "板块成分_通达信" / "2024-01"
    tdx_const.mkdir(parents=True)
    (tdx_const / "板块成分_TDX_20240115.zip").write_bytes(b"PK\x03\x04dummy")

    # TDX kline
    (base / "板块行情_通达信.zip").write_bytes(b"PK\x03\x04dummy")
    tdx_concept = base / "通达信_概念板块_历史行情数据"
    tdx_concept.mkdir(parents=True)
    (tdx_concept / "概念板块_日k_K线.zip").write_bytes(b"PK\x03\x04dummy")
    tdx_incr_kline = base / "增量数据" / "板块行情_通达信" / "2024-01"
    tdx_incr_kline.mkdir(parents=True)
    (tdx_incr_kline / "2024-01-15.csv").write_text("header\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Test: File scanning discovers correct files per data source
# ---------------------------------------------------------------------------


class TestFileScanning:
    """Test _scan_sector_list_files, _scan_constituent_files, _scan_kline_files."""

    def test_scan_sector_list_dc(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_sector_list_files(DataSource.DC)
            # 概念板块列表_东财.csv + 2 historical dir lists + 1 incremental
            assert len(files) == 4

    def test_scan_sector_list_ti(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_sector_list_files(DataSource.TI)
            assert len(files) == 1
            assert files[0].name == "行业概念板块_同花顺.csv"

    def test_scan_sector_list_tdx(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_sector_list_files(DataSource.TDX)
            # 通达信板块列表.csv + 板块信息_通达信.zip + 1 incremental
            assert len(files) == 3

    def test_scan_constituent_files_dc(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_constituent_files(DataSource.DC)
            # 概念板块_东财.zip + 板块成分_DC_20240115.zip
            assert len(files) == 2

    def test_scan_constituent_files_ti(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_constituent_files(DataSource.TI)
            # 2 root CSVs + 1 root ZIP + 1 incremental CSV
            assert len(files) == 4

    def test_scan_kline_files_dc(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_kline_files(DataSource.DC)
            # 板块行情_东财.zip + 2 historical ZIPs + 1 incremental CSV
            assert len(files) == 4

    def test_scan_kline_files_ti(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_kline_files(DataSource.TI)
            # 板块指数行情_同花顺.zip + 1 incremental CSV
            assert len(files) == 2

    def test_scan_empty_directory(self):
        """Scanning a non-existent source directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            svc = SectorImportService(base_dir=tmp)
            files = svc._scan_sector_list_files(DataSource.DC)
            assert files == []

    def test_scan_kline_files_tdx(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_kline_files(DataSource.TDX)
            # 板块行情_通达信.zip + 1 historical ZIP + 1 incremental CSV
            assert len(files) == 3


# ---------------------------------------------------------------------------
# Test: Batch size splitting logic
# ---------------------------------------------------------------------------


class TestBatchSplitting:
    """Verify that bulk write methods split items into BATCH_SIZE chunks."""

    @pytest.mark.asyncio
    async def test_bulk_upsert_batching(self):
        """Items exceeding BATCH_SIZE are split into multiple batches."""
        from app.services.data_engine.sector_csv_parser import ParsedSectorInfo
        from app.models.sector import SectorType

        svc = SectorImportService()
        svc.BATCH_SIZE = 3  # small batch for testing

        items = [
            ParsedSectorInfo(
                sector_code=f"CODE{i:04d}",
                name=f"Name{i}",
                sector_type=SectorType.CONCEPT,
                data_source=DataSource.DC,
            )
            for i in range(7)
        ]

        execute_calls = []

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def execute(self, stmt, params):
                execute_calls.append(params)

            async def commit(self):
                pass

        with patch(
            "app.services.data_engine.sector_import.AsyncSessionPG",
            return_value=FakeSession(),
        ), patch.object(
            svc, "_check_stop_signal", new_callable=AsyncMock, return_value=False,
        ):
            total = await svc._bulk_upsert_sector_info(items)

        # 7 items with batch_size=3 → 3 batches (3+3+1) → 3 executemany calls
        assert total == 7
        assert len(execute_calls) == 3
        # First batch: 3 params, second: 3 params, third: 1 param
        assert len(execute_calls[0]) == 3
        assert len(execute_calls[1]) == 3
        assert len(execute_calls[2]) == 1

    @pytest.mark.asyncio
    async def test_bulk_insert_empty_list(self):
        """Empty item list returns 0 without any DB calls."""
        svc = SectorImportService()
        total = await svc._bulk_upsert_sector_info([])
        assert total == 0


# ---------------------------------------------------------------------------
# Test: Progress update and heartbeat
# ---------------------------------------------------------------------------


class TestProgressTracking:
    """Test update_progress and is_running methods."""

    @pytest.mark.asyncio
    async def test_update_progress_writes_heartbeat(self):
        """update_progress should write heartbeat timestamp to Redis."""
        svc = SectorImportService()

        stored_values: dict[str, str] = {}

        async def mock_cache_get(key):
            return stored_values.get(key)

        async def mock_cache_set(key, value, ex=None):
            stored_values[key] = value

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cache_get,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cache_set,
        ):
            await svc.update_progress(status="running", stage="板块列表")

        raw = stored_values.get(svc.REDIS_PROGRESS_KEY)
        assert raw is not None
        progress = json.loads(raw)
        assert progress["status"] == "running"
        assert progress["stage"] == "板块列表"
        assert "heartbeat" in progress
        assert isinstance(progress["heartbeat"], float)

    @pytest.mark.asyncio
    async def test_update_progress_merges_fields(self):
        """Subsequent calls merge new fields into existing progress."""
        svc = SectorImportService()

        stored_values: dict[str, str] = {}

        async def mock_cache_get(key):
            return stored_values.get(key)

        async def mock_cache_set(key, value, ex=None):
            stored_values[key] = value

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cache_get,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cache_set,
        ):
            await svc.update_progress(status="running", stage="板块列表")
            await svc.update_progress(processed_files=5)

        raw = stored_values[svc.REDIS_PROGRESS_KEY]
        progress = json.loads(raw)
        assert progress["status"] == "running"
        assert progress["processed_files"] == 5

    @pytest.mark.asyncio
    async def test_is_running_returns_true_for_active_task(self):
        """is_running returns True when status is running and heartbeat is fresh."""
        svc = SectorImportService()

        progress = json.dumps({
            "status": "running",
            "heartbeat": time.time(),
        })

        async def mock_cache_get(key):
            if key == svc.REDIS_PROGRESS_KEY:
                return progress
            return None

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cache_get,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            new_callable=AsyncMock,
        ):
            result = await svc.is_running()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_running_returns_false_when_no_progress(self):
        """is_running returns False when no progress key exists."""
        svc = SectorImportService()

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await svc.is_running()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_running_returns_false_for_completed(self):
        """is_running returns False when status is completed."""
        svc = SectorImportService()

        progress = json.dumps({
            "status": "completed",
            "heartbeat": time.time(),
        })

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            new_callable=AsyncMock,
            return_value=progress,
        ):
            result = await svc.is_running()

        assert result is False


# ---------------------------------------------------------------------------
# Test: Stop signal detection
# ---------------------------------------------------------------------------


class TestStopSignal:
    """Test request_stop and _check_stop_signal."""

    @pytest.mark.asyncio
    async def test_stop_signal_detection(self):
        """After request_stop, _check_stop_signal should return True."""
        svc = SectorImportService()
        fake_redis = FakeRedis()

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ):
            # Initially no stop signal
            result = await svc._check_stop_signal()
            assert result is False

            # Request stop
            await svc.request_stop()

            # Now stop signal should be detected
            result = await svc._check_stop_signal()
            assert result is True

    @pytest.mark.asyncio
    async def test_clear_stop_signal(self):
        """_clear_stop_signal removes the stop key."""
        svc = SectorImportService()
        fake_redis = FakeRedis()

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ), patch(
            "app.services.data_engine.sector_import.cache_delete",
            new_callable=AsyncMock,
        ) as mock_delete:
            await svc._clear_stop_signal()
            mock_delete.assert_called_once_with(svc.REDIS_STOP_KEY)


# ---------------------------------------------------------------------------
# Test: Zombie task detection (heartbeat timeout)
# ---------------------------------------------------------------------------


class TestZombieDetection:
    """Test is_running with stale heartbeat."""

    @pytest.mark.asyncio
    async def test_zombie_task_detected_by_heartbeat_timeout(self):
        """is_running returns False and marks failed when heartbeat is stale."""
        svc = SectorImportService()

        stored_values: dict[str, str] = {}
        stale_heartbeat = time.time() - svc.HEARTBEAT_TIMEOUT - 10
        progress = json.dumps({
            "status": "running",
            "heartbeat": stale_heartbeat,
        })
        stored_values[svc.REDIS_PROGRESS_KEY] = progress

        async def mock_cache_get(key):
            return stored_values.get(key)

        async def mock_cache_set(key, value, ex=None):
            stored_values[key] = value

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cache_get,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cache_set,
        ):
            result = await svc.is_running()

        assert result is False

        # Verify status was updated to failed
        updated = json.loads(stored_values[svc.REDIS_PROGRESS_KEY])
        assert updated["status"] == "failed"
        assert "心跳超时" in updated["error"]

    @pytest.mark.asyncio
    async def test_zombie_task_no_heartbeat_field(self):
        """is_running returns False when heartbeat field is missing."""
        svc = SectorImportService()

        stored_values: dict[str, str] = {}
        progress = json.dumps({"status": "running"})
        stored_values[svc.REDIS_PROGRESS_KEY] = progress

        async def mock_cache_get(key):
            return stored_values.get(key)

        async def mock_cache_set(key, value, ex=None):
            stored_values[key] = value

        with patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cache_get,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cache_set,
        ):
            result = await svc.is_running()

        assert result is False

        updated = json.loads(stored_values[svc.REDIS_PROGRESS_KEY])
        assert updated["status"] == "failed"


# ---------------------------------------------------------------------------
# Test: Error handling — skip failed files, continue processing
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test that import methods skip failed files and continue."""

    @pytest.mark.asyncio
    async def test_import_sector_list_skips_failed_files(self):
        """If a parser raises an exception, the file is skipped and processing continues."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "概念板块列表_东财.csv").write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            # Mock parser to raise on first call
            call_count = 0
            original_parse = svc.parser.parse_sector_list_dc

            def failing_parser(f):
                nonlocal call_count
                call_count += 1
                raise ValueError("Simulated parse error")

            svc.parser.parse_sector_list_dc = failing_parser

            fake_redis = FakeRedis()

            with patch(
                "app.services.data_engine.sector_import.get_redis_client",
                return_value=fake_redis,
            ), patch(
                "app.services.data_engine.sector_import.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ), patch(
                "app.services.data_engine.sector_import.cache_set",
                new_callable=AsyncMock,
            ):
                # Should not raise — error is caught and logged
                total = await svc._import_sector_list([DataSource.DC])

            assert total == 0
            assert call_count == 1  # parser was called but failed

    @pytest.mark.asyncio
    async def test_import_klines_skips_failed_files(self):
        """Kline import skips files that fail to parse."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            incr_dir = base / "增量数据" / "板块行情_东财" / "2024-01"
            incr_dir.mkdir(parents=True)
            (incr_dir / "2024-01-15.csv").write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            svc.parser.parse_kline_dc_csv = MagicMock(
                side_effect=ValueError("bad kline"),
            )

            fake_redis = FakeRedis()

            with patch(
                "app.services.data_engine.sector_import.get_redis_client",
                return_value=fake_redis,
            ), patch(
                "app.services.data_engine.sector_import.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ), patch(
                "app.services.data_engine.sector_import.cache_set",
                new_callable=AsyncMock,
            ):
                total = await svc._import_klines([DataSource.DC])

            assert total == 0

    @pytest.mark.asyncio
    async def test_incremental_skips_already_imported(self):
        """Incremental import skips files that are already marked as imported."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_file = base / "概念板块列表_东财.csv"
            csv_file.write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            fake_redis = FakeRedis()
            # Pre-mark the file as imported
            mtime = str(csv_file.stat().st_mtime)
            fake_redis._hashes[svc.REDIS_INCREMENTAL_KEY] = {
                str(csv_file): mtime,
            }

            parse_calls = []
            original_parse = svc.parser.parse_sector_list_dc

            def tracking_parser(f):
                parse_calls.append(f)
                return original_parse(f)

            svc.parser.parse_sector_list_dc = tracking_parser

            with patch(
                "app.services.data_engine.sector_import.get_redis_client",
                return_value=fake_redis,
            ), patch(
                "app.services.data_engine.sector_import.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ), patch(
                "app.services.data_engine.sector_import.cache_set",
                new_callable=AsyncMock,
            ):
                total = await svc._import_sector_list_incremental([DataSource.DC])

            # Parser should NOT have been called since file was already imported
            assert len(parse_calls) == 0
            assert total == 0
