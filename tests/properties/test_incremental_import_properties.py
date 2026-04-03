# Feature: local-kline-import, Property 8: 增量导入跳过未变化文件
"""
本地K线导入 — 增量导入属性测试（Hypothesis）

Property 8：增量导入跳过未变化文件

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

对任意已成功导入的 ZIP 文件，若文件修改时间（mtime）未发生变化，
再次执行导入时该文件应被跳过。若 mtime 发生变化，该文件应被重新导入。
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.local_kline_import import LocalKlineImportService

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

# 合法的文件路径片段
_path_segment = st.from_regex(r"[a-zA-Z0-9_]{1,8}", fullmatch=True)

# 生成 ZIP 文件路径（1-3 层目录 + filename.zip）
_zip_path = st.tuples(
    st.lists(_path_segment, min_size=1, max_size=3),
    _path_segment,
).map(lambda t: Path("/".join(t[0])) / f"{t[1]}.zip")

# mtime 值（正浮点数，模拟 os.stat 返回的 st_mtime）
_mtime = st.floats(min_value=1_000_000_000.0, max_value=2_000_000_000.0, allow_nan=False, allow_infinity=False)


def _run(coro):
    """在同步测试中运行异步协程。"""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Property 8a: 未缓存的文件不应被跳过
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(zip_path=_zip_path, current_mtime=_mtime)
def test_uncached_file_is_not_skipped(zip_path: Path, current_mtime: float):
    """
    # Feature: local-kline-import, Property 8: 增量导入跳过未变化文件

    **Validates: Requirements 9.1, 9.2**

    对任意 ZIP 文件路径，若 Redis 中无缓存记录（首次导入），
    check_incremental 应返回 False（不跳过）。
    """
    svc = LocalKlineImportService.__new__(LocalKlineImportService)

    mock_client = AsyncMock()
    mock_client.hget = AsyncMock(return_value=None)
    mock_client.aclose = AsyncMock()

    with patch(
        "app.services.data_engine.local_kline_import.get_redis_client",
        return_value=mock_client,
    ):
        should_skip = _run(svc.check_incremental(zip_path))

    assert should_skip is False, (
        f"未缓存的文件 {zip_path} 应返回 False（不跳过），但返回了 True"
    )


# ---------------------------------------------------------------------------
# Property 8b: mtime 未变化的文件应被跳过
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(zip_path=_zip_path, mtime_val=_mtime)
def test_unchanged_mtime_file_is_skipped(zip_path: Path, mtime_val: float):
    """
    # Feature: local-kline-import, Property 8: 增量导入跳过未变化文件

    **Validates: Requirements 9.2, 9.3**

    对任意 ZIP 文件路径，若 Redis 缓存的 mtime 与当前文件 mtime 相同，
    check_incremental 应返回 True（跳过）。
    """
    svc = LocalKlineImportService.__new__(LocalKlineImportService)
    mtime_str = str(mtime_val)

    mock_client = AsyncMock()
    mock_client.hget = AsyncMock(return_value=mtime_str)
    mock_client.aclose = AsyncMock()

    # Mock Path.stat() to return matching mtime
    mock_stat = MagicMock()
    mock_stat.st_mtime = mtime_val

    with (
        patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_client,
        ),
        patch.object(Path, "stat", return_value=mock_stat),
    ):
        should_skip = _run(svc.check_incremental(zip_path))

    assert should_skip is True, (
        f"mtime 未变化的文件 {zip_path} 应返回 True（跳过），但返回了 False"
    )


# ---------------------------------------------------------------------------
# Property 8c: mtime 变化的文件不应被跳过
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(
    zip_path=_zip_path,
    cached_mtime=_mtime,
    current_mtime=_mtime,
)
def test_changed_mtime_file_is_not_skipped(
    zip_path: Path,
    cached_mtime: float,
    current_mtime: float,
):
    """
    # Feature: local-kline-import, Property 8: 增量导入跳过未变化文件

    **Validates: Requirements 9.3, 9.4**

    对任意 ZIP 文件路径，若 Redis 缓存的 mtime 与当前文件 mtime 不同，
    check_incremental 应返回 False（不跳过，需重新导入）。
    """
    # 确保两个 mtime 不同
    if str(cached_mtime) == str(current_mtime):
        return  # 跳过相同的情况，由 8b 覆盖

    svc = LocalKlineImportService.__new__(LocalKlineImportService)

    mock_client = AsyncMock()
    mock_client.hget = AsyncMock(return_value=str(cached_mtime))
    mock_client.aclose = AsyncMock()

    mock_stat = MagicMock()
    mock_stat.st_mtime = current_mtime

    with (
        patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_client,
        ),
        patch.object(Path, "stat", return_value=mock_stat),
    ):
        should_skip = _run(svc.check_incremental(zip_path))

    assert should_skip is False, (
        f"mtime 变化的文件 {zip_path} 应返回 False（不跳过），但返回了 True。"
        f" cached={cached_mtime}, current={current_mtime}"
    )


# ---------------------------------------------------------------------------
# Property 8d: mark_imported 正确记录文件 mtime
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(zip_path=_zip_path, mtime_val=_mtime)
def test_mark_imported_stores_correct_mtime(zip_path: Path, mtime_val: float):
    """
    # Feature: local-kline-import, Property 8: 增量导入跳过未变化文件

    **Validates: Requirements 9.1**

    对任意 ZIP 文件路径和 mtime，mark_imported 应将文件路径和 mtime
    写入 Redis 哈希表，使后续 check_incremental 能正确判断。
    """
    svc = LocalKlineImportService.__new__(LocalKlineImportService)

    mock_client = AsyncMock()
    mock_client.hset = AsyncMock()
    mock_client.aclose = AsyncMock()

    mock_stat = MagicMock()
    mock_stat.st_mtime = mtime_val

    with (
        patch(
            "app.services.data_engine.local_kline_import.get_redis_client",
            return_value=mock_client,
        ),
        patch.object(Path, "stat", return_value=mock_stat),
    ):
        _run(svc.mark_imported(zip_path))

    # 验证 hset 被调用，且参数正确
    mock_client.hset.assert_called_once_with(
        svc.REDIS_INCREMENTAL_KEY,
        str(zip_path),
        str(mtime_val),
    )
