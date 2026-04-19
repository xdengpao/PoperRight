"""
SectorImportService 单元测试

Tests:
- File scanning discovers correct files per data source
- Batch size splitting logic
- Progress update and heartbeat
- Stop signal detection
- Zombie task detection (heartbeat timeout)
- Error handling: skip failed files, continue processing

Requirements: 4.1–4.15, 5.1–5.8, 6.1–6.6, 7.1–7.10
"""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import time
import zipfile
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
        self._lists: dict[str, list[str]] = {}

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
            if k in self._lists:
                del self._lists[k]
                count += 1
        return count

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hset(self, name: str, key: str, value: str) -> int:
        self._hashes.setdefault(name, {})[key] = value
        return 1

    async def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        lst = self._lists.get(key, [])
        return lst[start : stop + 1]

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def aclose(self) -> None:
        pass


def _make_zip(path: Path) -> None:
    """创建一个包含 dummy CSV 的最小有效 ZIP 文件。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dummy.csv", "col1,col2\nval1,val2\n")
    path.write_bytes(buf.getvalue())


def _build_dir_structure(base: Path) -> None:
    """Create a directory structure matching the new per-source layout.

    东方财富/ (DC), 同花顺/ (TI), 通达信/ (TDX) 三个独立子目录。
    """
    # ==================================================================
    # 东方财富 (DC)
    # ==================================================================
    dc = base / "东方财富"
    dc.mkdir()

    # --- 板块列表 ---
    dc_list = dc / "东方财富_板块列表"
    dc_list.mkdir()
    (dc_list / "东方财富_板块列表1.csv").write_text("header\n", encoding="utf-8")
    (dc_list / "东方财富_板块列表2.csv").write_text("header\n", encoding="utf-8")
    dc_concept_list = dc_list / "东方财富_概念板块列表"
    dc_concept_list.mkdir()
    (dc_concept_list / "BK0001.DC.csv").write_text("header\n", encoding="utf-8")
    (dc_concept_list / "BK0002.DC.csv").write_text("header\n", encoding="utf-8")

    # --- 板块行情 ---
    dc_kline = dc / "东方财富_板块行情"
    dc_kline.mkdir()
    dc_region_kline = dc_kline / "东方财富_地区板块行情"
    dc_region_kline.mkdir()
    (dc_region_kline / "BK0004.DC.csv").write_text("header\n", encoding="utf-8")
    dc_industry_kline = dc_kline / "东方财富_行业板块行情"
    dc_industry_kline.mkdir()
    (dc_industry_kline / "BK0003_daily.csv").write_text("header\n", encoding="utf-8")

    # --- 板块成分 ---
    dc_const = dc / "东方财富_板块成分" / "2024-12"
    dc_const.mkdir(parents=True)
    _make_zip(dc_const / "板块成分_DC_20241215.zip")

    # --- 增量数据 ---
    dc_incr_kline = dc / "东方财富_增量数据" / "东方财富_板块行情" / "2025-01"
    dc_incr_kline.mkdir(parents=True)
    (dc_incr_kline / "2025-01-15.csv").write_text("header\n", encoding="utf-8")

    dc_incr_list = dc / "东方财富_增量数据" / "东方财富_板块列表" / "2025-01"
    dc_incr_list.mkdir(parents=True)
    (dc_incr_list / "2025-01-15.csv").write_text("header\n", encoding="utf-8")

    # ==================================================================
    # 同花顺 (TI)
    # ==================================================================
    ti = base / "同花顺"
    ti.mkdir()

    # --- 板块列表 ---
    ti_list = ti / "同花顺_板块列表"
    ti_list.mkdir()
    (ti_list / "同花顺_板块列表.csv").write_text("header\n", encoding="utf-8")

    # --- 散装行情 ---
    ti_kline = ti / "同花顺_板块行情"
    ti_kline.mkdir()
    (ti_kline / "700001.TI.csv").write_text("header\n", encoding="utf-8")
    (ti_kline / "700002.TI.csv").write_text("header\n", encoding="utf-8")

    # --- 板块成分 ---
    ti_const = ti / "同花顺_板块成分"
    ti_const.mkdir()
    (ti_const / "同花顺_概念板块成分汇总.csv").write_text("header\n", encoding="utf-8")
    (ti_const / "同花顺_行业板块成分汇总.csv").write_text("header\n", encoding="utf-8")

    # --- 增量数据 ---
    ti_incr_kline = ti / "同花顺_增量数据" / "同花顺_板块行情" / "2025-01"
    ti_incr_kline.mkdir(parents=True)
    (ti_incr_kline / "2025-01-15.csv").write_text("header\n", encoding="utf-8")

    ti_incr_concept = ti / "同花顺_增量数据" / "同花顺_概念板块成分" / "2026-01"
    ti_incr_concept.mkdir(parents=True)
    (ti_incr_concept / "概念板块成分_20260115.csv").write_text(
        "header\n", encoding="utf-8",
    )

    ti_incr_industry = ti / "同花顺_增量数据" / "同花顺_行业板块成分" / "2026-01"
    ti_incr_industry.mkdir(parents=True)
    (ti_incr_industry / "行业板块成分汇总_同花顺_20260115.csv").write_text(
        "header\n", encoding="utf-8",
    )

    # ==================================================================
    # 通达信 (TDX)
    # ==================================================================
    tdx = base / "通达信"
    tdx.mkdir()

    # --- 板块列表 ---
    tdx_list = tdx / "通达信_板块列表"
    tdx_list.mkdir()
    (tdx_list / "通达信_板块列表.csv").write_text("header\n", encoding="utf-8")
    tdx_list_summary = tdx_list / "通达信_板块列表汇总"
    tdx_list_summary.mkdir()
    (tdx_list_summary / "880201.TDX.csv").write_text("header\n", encoding="utf-8")
    (tdx_list_summary / "880202.TDX.csv").write_text("header\n", encoding="utf-8")

    # --- 板块行情 ---
    tdx_kline = tdx / "通达信_板块行情"
    tdx_kline.mkdir()
    tdx_kline_summary = tdx_kline / "通达信_板块行情汇总"
    tdx_kline_summary.mkdir()
    (tdx_kline_summary / "880201.TDX.csv").write_text("header\n", encoding="utf-8")
    (tdx_kline_summary / "880202.TDX.csv").write_text("header\n", encoding="utf-8")

    # 四个历史行情 ZIP 目录（嵌套在 通达信_板块行情 下）
    for sub_name, zip_name in (
        ("通达信_概念板块历史行情", "概念板块_日k_K线.zip"),
        ("通达信_行业板块历史行情", "行业板块_日k_K线.zip"),
        ("通达信_地区板块历史行情", "地区板块_日k_K线.zip"),
        ("通达信_风格板块历史行情", "风格板块_日k_K线.zip"),
    ):
        d = tdx_kline / sub_name
        d.mkdir()
        _make_zip(d / zip_name)

    # --- 板块成分 ---
    tdx_const = tdx / "通达信_板块成分" / "2024-12"
    tdx_const.mkdir(parents=True)
    _make_zip(tdx_const / "板块成分_TDX_20241215.zip")

    # --- 增量数据 ---
    tdx_incr_list = tdx / "通达信_增量数据" / "通达信_板块列表" / "2025-01"
    tdx_incr_list.mkdir(parents=True)
    (tdx_incr_list / "2025-01-15.csv").write_text("header\n", encoding="utf-8")

    tdx_incr_kline = tdx / "通达信_增量数据" / "通达信_板块行情" / "2025-01"
    tdx_incr_kline.mkdir(parents=True)
    (tdx_incr_kline / "2025-01-15.csv").write_text("header\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Test: File scanning discovers correct files per data source
# ---------------------------------------------------------------------------


class TestFileScanning:
    """Test _scan_sector_list_files, _scan_constituent_files, _scan_kline_files."""

    def test_scan_sector_list_dc(self):
        """DC 板块列表: 列表1 + 列表2 + 2 概念板块列表 CSV + 1 增量 = 5 files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_sector_list_files(DataSource.DC)
            # 东方财富_板块列表1.csv + 东方财富_板块列表2.csv
            # + BK0001.DC.csv + BK0002.DC.csv (概念板块列表目录)
            # + 1 incremental
            assert len(files) == 5

    def test_scan_sector_list_ti(self):
        """TI 板块列表: 仅根级 1 file."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_sector_list_files(DataSource.TI)
            assert len(files) == 1
            assert files[0].name == "同花顺_板块列表.csv"

    def test_scan_sector_list_tdx(self):
        """TDX 板块列表: 根级 + 2 散装列表汇总 CSV + 1 增量 = 4 files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_sector_list_files(DataSource.TDX)
            # 通达信_板块列表.csv + 880201.TDX.csv + 880202.TDX.csv + 1 incremental
            assert len(files) == 4

    def test_scan_constituent_files_dc(self):
        """DC 板块成分: 1 ZIP."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_constituent_files(DataSource.DC)
            assert len(files) == 1
            assert files[0].name == "板块成分_DC_20241215.zip"

    def test_scan_constituent_files_ti(self):
        """TI 板块成分: 概念汇总 + 行业汇总 + 1 增量概念 + 1 增量行业 = 4 files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_constituent_files(DataSource.TI)
            # 同花顺_概念板块成分汇总.csv + 同花顺_行业板块成分汇总.csv
            # + 概念板块成分_20260115.csv + 行业板块成分汇总_同花顺_20260115.csv
            assert len(files) == 4

    def test_scan_constituent_files_tdx(self):
        """TDX 板块成分: 1 ZIP."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_constituent_files(DataSource.TDX)
            assert len(files) == 1
            assert files[0].name == "板块成分_TDX_20241215.zip"

    def test_scan_kline_files_dc(self):
        """DC 板块行情: 1 地区 + 1 行业 + 1 增量 = 3 files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_kline_files(DataSource.DC)
            # BK0004.DC.csv (地区) + BK0003_daily.csv (行业) + 1 incremental
            assert len(files) == 3

    def test_scan_kline_files_ti(self):
        """TI 板块行情: 2 散装 + 1 增量 = 3 files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_kline_files(DataSource.TI)
            # 700001.TI.csv + 700002.TI.csv + 1 incremental
            assert len(files) == 3

    def test_scan_kline_files_tdx(self):
        """TDX 板块行情: 2 散装 + 4 历史 ZIP + 1 增量 = 7 files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _build_dir_structure(base)
            svc = SectorImportService(base_dir=str(base))

            files = svc._scan_kline_files(DataSource.TDX)
            # 880201.TDX.csv + 880202.TDX.csv
            # + 概念板块_日k_K线.zip + 行业板块_日k_K线.zip
            # + 地区板块_日k_K线.zip + 风格板块_日k_K线.zip
            # + 1 incremental
            assert len(files) == 7

    def test_scan_empty_directory(self):
        """Scanning a non-existent source directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            svc = SectorImportService(base_dir=tmp)
            files = svc._scan_sector_list_files(DataSource.DC)
            assert files == []

    def test_scan_missing_source_dir(self):
        """Scanning a source whose subdirectory doesn't exist returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # 只创建 东方财富 目录，不创建 同花顺 和 通达信
            (base / "东方财富").mkdir()
            svc = SectorImportService(base_dir=str(base))

            assert svc._scan_sector_list_files(DataSource.TI) == []
            assert svc._scan_kline_files(DataSource.TDX) == []
            assert svc._scan_constituent_files(DataSource.TI) == []


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
            # Create file at the path _scan_sector_list_files(DC) expects
            dc_dir = base / "东方财富"
            dc_dir.mkdir()
            dc_list = dc_dir / "东方财富_板块列表"
            dc_list.mkdir()
            (dc_list / "东方财富_板块列表1.csv").write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            # Mock engine to raise on parse
            call_count = 0

            def failing_parser(f):
                nonlocal call_count
                call_count += 1
                raise ValueError("Simulated parse error")

            svc.dc_engine.parse_sector_list = failing_parser

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
            # Create file at the path _scan_kline_files(DC) expects
            dc_dir = base / "东方财富"
            dc_dir.mkdir()
            region_kline = dc_dir / "东方财富_板块行情" / "东方财富_地区板块行情"
            region_kline.mkdir(parents=True)
            (region_kline / "BK0001.DC.csv").write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            svc.dc_engine.parse_kline_csv = MagicMock(
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
            # Create file at the path _scan_sector_list_files(DC) expects
            dc_dir = base / "东方财富"
            dc_dir.mkdir()
            dc_list = dc_dir / "东方财富_板块列表"
            dc_list.mkdir()
            csv_file = dc_list / "东方财富_板块列表1.csv"
            csv_file.write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            fake_redis = FakeRedis()
            # Pre-mark the file as imported
            mtime = str(csv_file.stat().st_mtime)
            fake_redis._hashes[svc.REDIS_INCREMENTAL_KEY] = {
                str(csv_file): mtime,
            }

            parse_calls = []
            original_parse = svc.dc_engine.parse_sector_list

            def tracking_parser(f):
                parse_calls.append(f)
                return original_parse(f)

            svc.dc_engine.parse_sector_list = tracking_parser

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


# ---------------------------------------------------------------------------
# Test: 错误统计与记录
# ---------------------------------------------------------------------------


class TestErrorTracking:
    """测试 _record_error、_clear_errors、get_errors、get_error_count 方法。

    Requirements: 17.1, 17.2, 17.3
    """

    def _make_service_with_fake_redis(self):
        """创建 SectorImportService 实例和共享 FakeRedis，返回 (svc, fake_redis, stored_values)。

        stored_values 用于模拟 cache_get / cache_set（进度 JSON），
        fake_redis 用于模拟 get_redis_client()（错误列表 rpush/lrange/llen/delete）。
        """
        svc = SectorImportService()
        fake_redis = FakeRedis()
        stored_values: dict[str, str] = {}

        async def mock_cache_get(key):
            return stored_values.get(key)

        async def mock_cache_set(key, value, ex=None):
            stored_values[key] = value

        return svc, fake_redis, stored_values, mock_cache_get, mock_cache_set

    @pytest.mark.asyncio
    async def test_record_error_writes_to_redis(self):
        """_record_error 将错误详情 JSON 追加到 Redis 列表。"""
        svc, fake_redis, stored_values, mock_cg, mock_cs = (
            self._make_service_with_fake_redis()
        )

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ), patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cg,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cs,
        ):
            await svc._record_error(
                file="test.csv",
                line=10,
                error_type="parse_error",
                message="列数不匹配",
                raw_data="some,raw,data",
            )

        # 验证 Redis 列表中有一条错误记录
        items = fake_redis._lists.get(svc.REDIS_ERRORS_KEY, [])
        assert len(items) == 1
        detail = json.loads(items[0])
        assert detail["file"] == "test.csv"
        assert detail["line"] == 10
        assert detail["error_type"] == "parse_error"
        assert detail["message"] == "列数不匹配"
        assert detail["raw_data"] == "some,raw,data"

    @pytest.mark.asyncio
    async def test_record_error_increments_error_count(self):
        """多次调用 _record_error 后，进度 JSON 中 error_count 递增。"""
        svc, fake_redis, stored_values, mock_cg, mock_cs = (
            self._make_service_with_fake_redis()
        )

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ), patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cg,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cs,
        ):
            await svc._record_error(
                file="a.csv", line=1, error_type="parse_error",
                message="err1", raw_data="",
            )
            await svc._record_error(
                file="b.csv", line=2, error_type="db_error",
                message="err2", raw_data="",
            )
            await svc._record_error(
                file="c.csv", line=3, error_type="parse_error",
                message="err3", raw_data="",
            )

        progress = json.loads(stored_values[svc.REDIS_PROGRESS_KEY])
        assert progress["error_count"] == 3

    @pytest.mark.asyncio
    async def test_record_error_adds_to_failed_files(self):
        """_record_error 将文件名添加到进度 JSON 的 failed_files 列表。"""
        svc, fake_redis, stored_values, mock_cg, mock_cs = (
            self._make_service_with_fake_redis()
        )

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ), patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cg,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cs,
        ):
            await svc._record_error(
                file="fail.csv", line=0, error_type="parse_error",
                message="解析失败", raw_data="",
            )

        progress = json.loads(stored_values[svc.REDIS_PROGRESS_KEY])
        failed_files = progress["failed_files"]
        assert len(failed_files) == 1
        assert failed_files[0]["file"] == "fail.csv"
        assert "解析失败" in failed_files[0]["error"]

    @pytest.mark.asyncio
    async def test_record_error_deduplicates_failed_files(self):
        """同一文件多次出错时，failed_files 中只保留一条记录。"""
        svc, fake_redis, stored_values, mock_cg, mock_cs = (
            self._make_service_with_fake_redis()
        )

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ), patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cg,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cs,
        ):
            await svc._record_error(
                file="same.csv", line=1, error_type="parse_error",
                message="第一次出错", raw_data="",
            )
            await svc._record_error(
                file="same.csv", line=5, error_type="parse_error",
                message="第二次出错", raw_data="",
            )

        progress = json.loads(stored_values[svc.REDIS_PROGRESS_KEY])
        failed_files = progress["failed_files"]
        # 同一文件只出现一次
        assert len(failed_files) == 1
        assert failed_files[0]["file"] == "same.csv"
        # error_count 仍然递增两次
        assert progress["error_count"] == 2

    @pytest.mark.asyncio
    async def test_record_error_truncates_raw_data(self):
        """raw_data 超过 200 字符时被截断。"""
        svc, fake_redis, stored_values, mock_cg, mock_cs = (
            self._make_service_with_fake_redis()
        )

        long_data = "x" * 500

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ), patch(
            "app.services.data_engine.sector_import.cache_get",
            side_effect=mock_cg,
        ), patch(
            "app.services.data_engine.sector_import.cache_set",
            side_effect=mock_cs,
        ):
            await svc._record_error(
                file="big.csv", line=1, error_type="parse_error",
                message="数据过长", raw_data=long_data,
            )

        items = fake_redis._lists.get(svc.REDIS_ERRORS_KEY, [])
        detail = json.loads(items[0])
        assert len(detail["raw_data"]) == 200

    @pytest.mark.asyncio
    async def test_clear_errors(self):
        """_clear_errors 清空 Redis 错误列表。"""
        svc = SectorImportService()
        fake_redis = FakeRedis()
        # 预填充一些错误
        fake_redis._lists[svc.REDIS_ERRORS_KEY] = ["err1", "err2"]

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ):
            await svc._clear_errors()

        assert svc.REDIS_ERRORS_KEY not in fake_redis._lists

    @pytest.mark.asyncio
    async def test_get_errors_pagination(self):
        """get_errors 按 offset/limit 分页读取错误详情。"""
        svc = SectorImportService()
        fake_redis = FakeRedis()

        # 预填充 5 条错误
        errors = []
        for i in range(5):
            err = json.dumps({"file": f"f{i}.csv", "line": i, "error_type": "parse_error",
                              "message": f"err{i}", "raw_data": ""})
            errors.append(err)
        fake_redis._lists[svc.REDIS_ERRORS_KEY] = errors

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ):
            # 第一页：offset=0, limit=2
            page1 = await svc.get_errors(offset=0, limit=2)
            assert len(page1) == 2
            assert page1[0]["file"] == "f0.csv"
            assert page1[1]["file"] == "f1.csv"

            # 第二页：offset=2, limit=2
            page2 = await svc.get_errors(offset=2, limit=2)
            assert len(page2) == 2
            assert page2[0]["file"] == "f2.csv"
            assert page2[1]["file"] == "f3.csv"

            # 第三页：offset=4, limit=2（只剩 1 条）
            page3 = await svc.get_errors(offset=4, limit=2)
            assert len(page3) == 1
            assert page3[0]["file"] == "f4.csv"

    @pytest.mark.asyncio
    async def test_get_error_count(self):
        """get_error_count 返回错误总数。"""
        svc = SectorImportService()
        fake_redis = FakeRedis()

        # 空列表
        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ):
            assert await svc.get_error_count() == 0

        # 添加 3 条错误
        fake_redis._lists[svc.REDIS_ERRORS_KEY] = ["e1", "e2", "e3"]

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ):
            assert await svc.get_error_count() == 3

    @pytest.mark.asyncio
    async def test_import_records_error_on_parse_failure(self):
        """导入过程中解析失败时调用 _record_error，error_type 为 parse_error。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # 创建 DC 板块列表文件
            dc_dir = base / "东方财富"
            dc_dir.mkdir()
            dc_list = dc_dir / "东方财富_板块列表"
            dc_list.mkdir()
            (dc_list / "东方财富_板块列表1.csv").write_text("header\n", encoding="utf-8")

            svc = SectorImportService(base_dir=str(base))

            # 让解析引擎抛出异常
            svc.dc_engine.parse_sector_list = MagicMock(
                side_effect=ValueError("模拟解析失败"),
            )

            fake_redis = FakeRedis()
            stored_values: dict[str, str] = {}

            async def mock_cache_get(key):
                return stored_values.get(key)

            async def mock_cache_set(key, value, ex=None):
                stored_values[key] = value

            with patch(
                "app.services.data_engine.sector_import.get_redis_client",
                return_value=fake_redis,
            ), patch(
                "app.services.data_engine.sector_import.cache_get",
                side_effect=mock_cache_get,
            ), patch(
                "app.services.data_engine.sector_import.cache_set",
                side_effect=mock_cache_set,
            ):
                total = await svc._import_sector_list([DataSource.DC])

            # 导入返回 0（解析失败）
            assert total == 0

            # 验证 _record_error 被调用：Redis 列表中有错误记录
            items = fake_redis._lists.get(svc.REDIS_ERRORS_KEY, [])
            assert len(items) == 1
            detail = json.loads(items[0])
            assert detail["error_type"] == "parse_error"
            assert "模拟解析失败" in detail["message"]

            # 验证进度 JSON 中 error_count 递增
            progress = json.loads(stored_values[svc.REDIS_PROGRESS_KEY])
            assert progress["error_count"] == 1
