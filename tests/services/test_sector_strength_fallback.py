"""
SectorStrengthFilter._aggregate_change_pct fallback 单元测试

测试 change_pct 全 NULL 时使用收盘价 fallback 计算板块涨跌幅的各种边界情况。

Tests:
- change_pct 全 NULL + 有效收盘价 ≥ 2 → 使用收盘价 fallback (Req 15.1)
- 部分 change_pct NULL → 使用 change_pct 累加 (Req 15.3)
- 有效收盘价 < 2 → 返回 0.0 (Req 15.2)
- 最早收盘价 = 0.0 → 返回 0.0（除零保护）
- change_pct 和 close 全 NULL → 返回 0.0
- 返回类型始终为 float (Req 15.4)

Requirements: 15.1, 15.2, 15.3, 15.4
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.services.screener.sector_strength import SectorStrengthFilter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class MockSectorKline:
    """模拟 SectorKline 对象，仅包含 _aggregate_change_pct 所需字段。"""

    change_pct: Decimal | None = None
    close: Decimal | None = None


def _kline(
    change_pct: float | None = None,
    close: float | None = None,
) -> MockSectorKline:
    """快捷构建 MockSectorKline。"""
    return MockSectorKline(
        change_pct=Decimal(str(change_pct)) if change_pct is not None else None,
        close=Decimal(str(close)) if close is not None else None,
    )


# ---------------------------------------------------------------------------
# Test: change_pct 全 NULL + 有效收盘价 fallback (Req 15.1)
# ---------------------------------------------------------------------------


class TestChangePctAllNullFallback:
    """change_pct 全 NULL 时使用收盘价 fallback 计算涨跌幅 (Req 15.1)。"""

    def test_fallback_basic(self):
        """收盘价从 100 涨到 110，涨跌幅应为 10.0%。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=105.0),
                _kline(change_pct=None, close=110.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == pytest.approx(10.0)

    def test_fallback_negative_change(self):
        """收盘价从 200 跌到 180，涨跌幅应为 -10.0%。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=200.0),
                _kline(change_pct=None, close=190.0),
                _kline(change_pct=None, close=180.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == pytest.approx(-10.0)

    def test_fallback_exactly_two_closes(self):
        """仅有 2 个有效收盘价时也应正常计算。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=50.0),
                _kline(change_pct=None, close=60.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == pytest.approx(20.0)

    def test_fallback_with_intermediate_null_close(self):
        """中间有 NULL close 时，仅使用有效收盘价的首尾计算。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=None),   # NULL close
                _kline(change_pct=None, close=120.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        # valid_closes = [100.0, 120.0], earliest=100, latest=120
        assert result["BK001"] == pytest.approx(20.0)

    def test_fallback_multiple_sectors(self):
        """多个板块同时使用 fallback。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=110.0),
            ],
            "BK002": [
                _kline(change_pct=None, close=200.0),
                _kline(change_pct=None, close=220.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == pytest.approx(10.0)
        assert result["BK002"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Test: 部分 change_pct NULL → 使用 change_pct 累加 (Req 15.3)
# ---------------------------------------------------------------------------


class TestPartialChangePctNull:
    """有部分 change_pct 非 NULL 时优先使用 change_pct 累加 (Req 15.3)。"""

    def test_partial_null_uses_sum(self):
        """部分 change_pct 为 NULL，仅累加非 NULL 值。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=2.0, close=100.0),
                _kline(change_pct=None, close=105.0),
                _kline(change_pct=3.0, close=110.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        # 有效 change_pct: [2.0, 3.0]，sum = 5.0（不使用 fallback）
        assert result["BK001"] == pytest.approx(5.0)

    def test_single_valid_change_pct_uses_sum(self):
        """仅 1 个有效 change_pct 也使用累加路径。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=105.0),
                _kline(change_pct=5.0, close=110.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        # 有效 change_pct: [5.0]，sum = 5.0
        assert result["BK001"] == pytest.approx(5.0)

    def test_all_change_pct_valid(self):
        """所有 change_pct 均有效时正常累加。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=1.5, close=100.0),
                _kline(change_pct=2.5, close=104.0),
                _kline(change_pct=-0.5, close=103.5),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == pytest.approx(3.5)

    def test_mixed_sectors_primary_and_fallback(self):
        """一个板块用 change_pct 累加，另一个板块用 fallback。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=2.0, close=100.0),
                _kline(change_pct=3.0, close=105.0),
            ],
            "BK002": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=115.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == pytest.approx(5.0)   # change_pct 累加
        assert result["BK002"] == pytest.approx(15.0)   # 收盘价 fallback


# ---------------------------------------------------------------------------
# Test: 有效收盘价 < 2 → 返回 0.0 (Req 15.2)
# ---------------------------------------------------------------------------


class TestFewerThanTwoCloses:
    """有效收盘价少于 2 个时返回 0.0 (Req 15.2)。"""

    def test_single_close_returns_zero(self):
        """仅 1 个有效收盘价，无法计算涨跌幅。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=None),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0

    def test_zero_closes_returns_zero(self):
        """所有 close 均为 NULL，有效收盘价为 0 个。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=None),
                _kline(change_pct=None, close=None),
                _kline(change_pct=None, close=None),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0

    def test_single_kline_returns_zero(self):
        """仅 1 条 K 线记录（有效收盘价 = 1）。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0


# ---------------------------------------------------------------------------
# Test: 最早收盘价 = 0.0 → 除零保护
# ---------------------------------------------------------------------------


class TestDivisionByZeroProtection:
    """最早收盘价为 0.0 时返回 0.0（除零保护）。"""

    def test_earliest_close_zero(self):
        """最早收盘价为 0.0，应返回 0.0 而非抛出异常。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=0.0),
                _kline(change_pct=None, close=100.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0

    def test_both_closes_zero(self):
        """最早和最新收盘价均为 0.0。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=0.0),
                _kline(change_pct=None, close=0.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0


# ---------------------------------------------------------------------------
# Test: change_pct 和 close 全 NULL → 返回 0.0
# ---------------------------------------------------------------------------


class TestAllFieldsNull:
    """change_pct 和 close 全部为 NULL 时返回 0.0。"""

    def test_all_null(self):
        """所有字段均为 NULL。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=None),
                _kline(change_pct=None, close=None),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0

    def test_empty_kline_list(self):
        """板块有空的 K 线列表。"""
        kline_data: dict = {
            "BK001": [],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert result["BK001"] == 0.0


# ---------------------------------------------------------------------------
# Test: 返回类型始终为 float (Req 15.4)
# ---------------------------------------------------------------------------


class TestReturnTypeFloat:
    """返回值类型始终为 float (Req 15.4)。"""

    def test_change_pct_path_returns_float(self):
        """change_pct 累加路径返回 float。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=2.5, close=100.0),
                _kline(change_pct=3.5, close=106.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert isinstance(result["BK001"], float)

    def test_fallback_path_returns_float(self):
        """收盘价 fallback 路径返回 float。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=100.0),
                _kline(change_pct=None, close=110.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert isinstance(result["BK001"], float)

    def test_zero_fallback_returns_float(self):
        """有效收盘价不足时返回 0.0 也是 float。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=None),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert isinstance(result["BK001"], float)
        assert result["BK001"] == 0.0

    def test_division_by_zero_returns_float(self):
        """除零保护返回 0.0 也是 float。"""
        kline_data = {
            "BK001": [
                _kline(change_pct=None, close=0.0),
                _kline(change_pct=None, close=50.0),
            ],
        }

        result = SectorStrengthFilter._aggregate_change_pct(kline_data)

        assert isinstance(result["BK001"], float)

    def test_empty_dict_returns_empty(self):
        """空输入返回空字典。"""
        result = SectorStrengthFilter._aggregate_change_pct({})

        assert result == {}
        assert isinstance(result, dict)
