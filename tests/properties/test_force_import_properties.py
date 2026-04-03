# Feature: local-kline-import, Property 9: 强制导入忽略增量缓存
"""
本地K线导入 — 强制导入属性测试（Hypothesis）

Property 9：强制导入忽略增量缓存

**Validates: Requirements 9.5**

对任意已成功导入的 ZIP 文件集合，当 force=True 时，
所有文件都应被重新处理，无论其 mtime 是否变化。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.local_kline_import import LocalKlineImportService

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

_path_segment = st.from_regex(r"[a-zA-Z0-9_]{1,8}", fullmatch=True)
_freq = st.sampled_from(["1m", "5m", "15m", "30m", "60m"])
_mtime = st.floats(
    min_value=1_000_000_000.0,
    max_value=2_000_000_000.0,
    allow_nan=False,
    allow_infinity=False,
)

# 生成 (symbol_segment, freq) 对，用于构造合法 ZIP 路径
_zip_entry = st.tuples(_path_segment, _freq)

# 生成 1-5 个 ZIP 文件条目
_zip_entries = st.lists(_zip_entry, min_size=1, max_size=5)


def _run(coro):
    """在同步测试中运行异步协程。"""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Property 9a: force=True 时 check_incremental 不被调用
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(entries=_zip_entries, mtimes=st.lists(_mtime, min_size=5, max_size=5))
def test_force_import_skips_incremental_check(
    entries: list[tuple[str, str]],
    mtimes: list[float],
):
    """
    # Feature: local-kline-import, Property 9: 强制导入忽略增量缓存

    **Validates: Requirements 9.5**

    对任意已导入文件集合，force=True 时 check_incremental 不应被调用，
    所有文件都应被处理（extract_and_parse_zip 被调用）。
    """
    base_dir = "/tmp/test_force"

    # 构造 ZIP 路径列表
    zip_paths = [Path(base_dir) / sym / f"{freq}.zip" for sym, freq in entries]

    svc = LocalKlineImportService()

    # Mock Redis client for update_progress / is_running / mark_imported / result write
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.aclose = AsyncMock()

    # Mock scan_zip_files to return our generated paths
    mock_scan = MagicMock(return_value=zip_paths)

    # Mock extract_and_parse_zip to return empty results (we only care about call count)
    mock_extract = MagicMock(return_value=([], 0, 0))

    # Mock check_incremental — should NOT be called when force=True
    mock_check = AsyncMock(return_value=True)  # would skip if called

    # Mock mark_imported
    mock_mark = AsyncMock()

    # Mock KlineRepository
    mock_repo_cls = MagicMock()
    mock_repo_cls.return_value = MagicMock()

    # Mock Path.exists / is_dir for the directory check in execute
    mock_path_exists = MagicMock(return_value=True)
    mock_path_is_dir = MagicMock(return_value=True)

    with (
        patch.object(svc, "scan_zip_files", mock_scan),
        patch.object(svc, "extract_and_parse_zip", mock_extract),
        patch.object(svc, "check_incremental", mock_check),
        patch.object(svc, "mark_imported", mock_mark),
        patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "app.services.data_engine.local_kline_import.KlineRepository",
            mock_repo_cls,
        ),
        patch.object(Path, "exists", mock_path_exists),
        patch.object(Path, "is_dir", mock_path_is_dir),
        patch(
            "app.services.data_engine.local_kline_import.settings",
            MagicMock(local_kline_data_dir=base_dir),
        ),
    ):
        result = _run(svc.execute(freqs=None, sub_dir=None, force=True))

    # check_incremental must never be called when force=True
    mock_check.assert_not_called()

    # extract_and_parse_zip must be called for every file
    assert mock_extract.call_count == len(zip_paths), (
        f"force=True 时应处理所有 {len(zip_paths)} 个文件，"
        f"但 extract_and_parse_zip 仅被调用 {mock_extract.call_count} 次"
    )


# ---------------------------------------------------------------------------
# Property 9b: force=True 时已缓存文件仍被重新处理
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(entries=_zip_entries)
def test_force_import_processes_all_cached_files(
    entries: list[tuple[str, str]],
):
    """
    # Feature: local-kline-import, Property 9: 强制导入忽略增量缓存

    **Validates: Requirements 9.5**

    对任意已缓存（mtime 未变化）的文件集合，force=True 时
    所有文件都应被重新处理，结果中 skipped_files 应为 0。
    """
    base_dir = "/tmp/test_force"
    zip_paths = [Path(base_dir) / sym / f"{freq}.zip" for sym, freq in entries]

    svc = LocalKlineImportService()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.hset = AsyncMock()
    # Simulate all files being cached with matching mtime
    mock_redis.hget = AsyncMock(return_value="1500000000.0")
    mock_redis.aclose = AsyncMock()

    mock_scan = MagicMock(return_value=zip_paths)
    mock_extract = MagicMock(return_value=([], 0, 0))
    mock_mark = AsyncMock()

    mock_repo_cls = MagicMock()
    mock_repo_cls.return_value = MagicMock()

    with (
        patch.object(svc, "scan_zip_files", mock_scan),
        patch.object(svc, "extract_and_parse_zip", mock_extract),
        patch.object(svc, "mark_imported", mock_mark),
        patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "app.services.data_engine.local_kline_import.KlineRepository",
            mock_repo_cls,
        ),
        patch.object(Path, "exists", MagicMock(return_value=True)),
        patch.object(Path, "is_dir", MagicMock(return_value=True)),
        patch(
            "app.services.data_engine.local_kline_import.settings",
            MagicMock(local_kline_data_dir=base_dir),
        ),
    ):
        result = _run(svc.execute(freqs=None, sub_dir=None, force=True))

    # No files should be skipped
    assert result["skipped_files"] == 0, (
        f"force=True 时 skipped_files 应为 0，但实际为 {result['skipped_files']}"
    )

    # All files should be processed
    assert mock_extract.call_count == len(zip_paths), (
        f"force=True 时应处理所有 {len(zip_paths)} 个文件，"
        f"但仅处理了 {mock_extract.call_count} 个"
    )

    # success_files should equal total since extract returns empty (no errors)
    assert result["success_files"] == len(zip_paths), (
        f"force=True 时 success_files 应为 {len(zip_paths)}，"
        f"但实际为 {result['success_files']}"
    )
