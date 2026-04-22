"""截断检测逻辑单元测试。

测试 check_chunk_config 预检查和 check_truncation 运行时检测函数，
以及 _process_batched_by_date 中的连续截断检测集成。

对应需求：6.1, 6.2, 6.3, 6.4
"""

from __future__ import annotations

import logging

import pytest

from app.tasks.tushare_import import (
    _CONSECUTIVE_TRUNCATION_THRESHOLD,
    check_chunk_config,
    check_truncation,
)


# ---------------------------------------------------------------------------
# check_chunk_config 预检查测试
# ---------------------------------------------------------------------------


class TestCheckChunkConfig:
    """预检查步长配置合理性。"""

    def test_reasonable_config_returns_true(self):
        """步长合理时返回 True。"""
        # 30天 × 50行/天 = 1500 < 3000
        result = check_chunk_config(
            date_chunk_days=30, max_rows=3000,
            estimated_daily_rows=50, api_name="test_api",
        )
        assert result is True

    def test_unreasonable_config_returns_false(self, caplog):
        """步长过大时返回 False 并记录 WARNING。"""
        # 30天 × 200行/天 = 6000 >= 3000
        with caplog.at_level(logging.WARNING):
            result = check_chunk_config(
                date_chunk_days=30, max_rows=3000,
                estimated_daily_rows=200, api_name="test_api",
            )
        assert result is False
        assert "步长配置可能过大" in caplog.text
        assert "test_api" in caplog.text

    def test_exact_boundary_returns_false(self, caplog):
        """步长恰好等于上限时返回 False（边界情况）。"""
        # 30天 × 100行/天 = 3000 >= 3000
        with caplog.at_level(logging.WARNING):
            result = check_chunk_config(
                date_chunk_days=30, max_rows=3000,
                estimated_daily_rows=100, api_name="boundary_api",
            )
        assert result is False
        assert "boundary_api" in caplog.text

    def test_none_estimated_rows_returns_true(self):
        """无预估行数时视为合理，返回 True。"""
        result = check_chunk_config(
            date_chunk_days=30, max_rows=3000,
            estimated_daily_rows=None, api_name="test_api",
        )
        assert result is True

    def test_zero_estimated_rows_returns_true(self):
        """预估行数为 0 时视为合理，返回 True。"""
        result = check_chunk_config(
            date_chunk_days=30, max_rows=3000,
            estimated_daily_rows=0, api_name="test_api",
        )
        assert result is True

    def test_negative_estimated_rows_returns_true(self):
        """预估行数为负数时视为合理，返回 True。"""
        result = check_chunk_config(
            date_chunk_days=30, max_rows=3000,
            estimated_daily_rows=-10, api_name="test_api",
        )
        assert result is True

    def test_custom_max_rows(self):
        """自定义 max_rows 阈值。"""
        # 160天 × 50行/天 = 8000 >= 8000
        result = check_chunk_config(
            date_chunk_days=160, max_rows=8000,
            estimated_daily_rows=50, api_name="idx_factor_pro",
        )
        assert result is False

    def test_warning_includes_all_details(self, caplog):
        """WARNING 日志包含所有关键信息。"""
        with caplog.at_level(logging.WARNING):
            check_chunk_config(
                date_chunk_days=60, max_rows=3000,
                estimated_daily_rows=100, api_name="detail_api",
            )
        assert "date_chunk_days=60" in caplog.text
        assert "estimated_daily_rows=100" in caplog.text
        assert "6000" in caplog.text  # 60 × 100
        assert "max_rows=3000" in caplog.text


# ---------------------------------------------------------------------------
# check_truncation 运行时检测测试
# ---------------------------------------------------------------------------


class TestCheckTruncation:
    """运行时截断检测。"""

    def test_no_truncation_returns_false(self):
        """返回行数低于上限时返回 False。"""
        result = check_truncation(
            row_count=2999, max_rows=3000,
            api_name="test_api", chunk_start="20230101", chunk_end="20230130",
        )
        assert result is False

    def test_exact_max_rows_returns_true(self, caplog):
        """返回行数恰好等于上限时返回 True。"""
        with caplog.at_level(logging.WARNING):
            result = check_truncation(
                row_count=3000, max_rows=3000,
                api_name="test_api", chunk_start="20230101", chunk_end="20230130",
            )
        assert result is True
        assert "数据可能被截断" in caplog.text

    def test_exceeds_max_rows_returns_true(self, caplog):
        """返回行数超过上限时返回 True。"""
        with caplog.at_level(logging.WARNING):
            result = check_truncation(
                row_count=3500, max_rows=3000,
                api_name="test_api", chunk_start="20230101", chunk_end="20230130",
            )
        assert result is True

    def test_warning_includes_details(self, caplog):
        """WARNING 日志包含接口名、子区间和行数信息。"""
        with caplog.at_level(logging.WARNING):
            check_truncation(
                row_count=3000, max_rows=3000,
                api_name="dc_daily", chunk_start="20230101", chunk_end="20230106",
            )
        assert "dc_daily" in caplog.text
        assert "20230101" in caplog.text
        assert "20230106" in caplog.text
        assert "3000" in caplog.text

    def test_custom_max_rows_threshold(self, caplog):
        """自定义 max_rows 阈值的截断检测。"""
        with caplog.at_level(logging.WARNING):
            result = check_truncation(
                row_count=8000, max_rows=8000,
                api_name="index_daily", chunk_start="20230101", chunk_end="20230601",
            )
        assert result is True
        assert "max_rows=8000" in caplog.text

    def test_zero_rows_no_truncation(self):
        """0 行返回不触发截断。"""
        result = check_truncation(
            row_count=0, max_rows=3000,
            api_name="test_api", chunk_start="20230101", chunk_end="20230130",
        )
        assert result is False


# ---------------------------------------------------------------------------
# 连续截断阈值常量测试
# ---------------------------------------------------------------------------


class TestConsecutiveTruncationThreshold:
    """连续截断告警阈值。"""

    def test_threshold_is_3(self):
        """连续截断阈值为 3。"""
        assert _CONSECUTIVE_TRUNCATION_THRESHOLD == 3
