"""
AdjFactorRepository 查询方法单元测试

覆盖：
- query_by_symbol：按日期升序返回、无数据返回空列表
- query_latest_factor：返回最新因子值、无数据返回 None
- query_batch：按 symbol 分组、空列表返回空字典

Requirements: 1.1, 1.2, 1.3, 1.4
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.adjustment_factor import AdjustmentFactor
from app.services.data_engine.adj_factor_repository import AdjFactorRepository


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_factor(
    symbol: str,
    trade_date: date,
    adj_factor: Decimal,
    adj_type: int = 1,
) -> AdjustmentFactor:
    """构造 AdjustmentFactor ORM 实例。"""
    f = AdjustmentFactor()
    f.symbol = symbol
    f.trade_date = trade_date
    f.adj_type = adj_type
    f.adj_factor = adj_factor
    return f


def _mock_session_with_scalars(return_values):
    """
    创建一个 mock AsyncSession，其 execute().scalars().all() 返回 return_values。
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = return_values
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


def _mock_session_with_scalar_one_or_none(return_value):
    """
    创建一个 mock AsyncSession，其 execute().scalar_one_or_none() 返回 return_value。
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


# ---------------------------------------------------------------------------
# 需求 1.1：query_by_symbol 按日期升序返回
# ---------------------------------------------------------------------------


class TestQueryBySymbol:
    async def test_returns_factors_in_ascending_date_order(self):
        """query_by_symbol 返回按 trade_date 升序排列的因子列表。"""
        factors = [
            _make_factor("000001", date(2024, 1, 10), Decimal("1.0000")),
            _make_factor("000001", date(2024, 1, 15), Decimal("1.1000")),
            _make_factor("000001", date(2024, 1, 20), Decimal("1.2000")),
        ]
        mock_session = _mock_session_with_scalars(factors)
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_by_symbol("000001", adj_type=1)

        assert len(result) == 3
        assert result[0].trade_date < result[1].trade_date < result[2].trade_date
        assert result[0].adj_factor == Decimal("1.0000")
        assert result[2].adj_factor == Decimal("1.2000")

    async def test_returns_empty_list_when_no_data(self):
        """query_by_symbol 无数据时返回空列表。"""
        mock_session = _mock_session_with_scalars([])
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_by_symbol("999999", adj_type=1)

        assert result == []

    async def test_passes_date_filters_to_query(self):
        """query_by_symbol 传入 start/end 时正确过滤。"""
        factors = [
            _make_factor("000001", date(2024, 1, 15), Decimal("1.1000")),
        ]
        mock_session = _mock_session_with_scalars(factors)
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_by_symbol(
            "000001",
            adj_type=1,
            start=date(2024, 1, 10),
            end=date(2024, 1, 20),
        )

        assert len(result) == 1
        # Verify execute was called (the SQL filtering is handled by SQLAlchemy)
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# 需求 1.2：query_latest_factor 返回最新因子值
# ---------------------------------------------------------------------------


class TestQueryLatestFactor:
    async def test_returns_most_recent_factor_value(self):
        """query_latest_factor 返回最新交易日的复权因子值。"""
        mock_session = _mock_session_with_scalar_one_or_none(Decimal("1.2500"))
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_latest_factor("000001", adj_type=1)

        assert result == Decimal("1.2500")
        mock_session.execute.assert_called_once()

    async def test_returns_none_when_no_data(self):
        """query_latest_factor 无数据时返回 None。"""
        mock_session = _mock_session_with_scalar_one_or_none(None)
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_latest_factor("999999", adj_type=1)

        assert result is None


# ---------------------------------------------------------------------------
# 需求 1.4：query_batch 批量查询并按 symbol 分组
# ---------------------------------------------------------------------------


class TestQueryBatch:
    async def test_groups_results_by_symbol(self):
        """query_batch 返回按 symbol 分组的字典。"""
        factors = [
            _make_factor("000001", date(2024, 1, 10), Decimal("1.0000")),
            _make_factor("000001", date(2024, 1, 15), Decimal("1.1000")),
            _make_factor("600519", date(2024, 1, 10), Decimal("2.0000")),
            _make_factor("600519", date(2024, 1, 15), Decimal("2.1000")),
            _make_factor("600519", date(2024, 1, 20), Decimal("2.2000")),
        ]
        mock_session = _mock_session_with_scalars(factors)
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_batch(["000001", "600519"], adj_type=1)

        assert set(result.keys()) == {"000001", "600519"}
        assert len(result["000001"]) == 2
        assert len(result["600519"]) == 3
        # Verify each group's factors belong to the correct symbol
        for f in result["000001"]:
            assert f.symbol == "000001"
        for f in result["600519"]:
            assert f.symbol == "600519"

    async def test_returns_empty_dict_for_empty_symbols_list(self):
        """query_batch 空 symbols 列表返回空字典。"""
        mock_session = _mock_session_with_scalars([])
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_batch([], adj_type=1)

        assert result == {}
        # Should short-circuit without hitting the database
        mock_session.execute.assert_not_called()

    async def test_returns_only_requested_symbols(self):
        """query_batch 仅返回请求的 symbol 的数据。"""
        factors = [
            _make_factor("000001", date(2024, 1, 10), Decimal("1.0000")),
        ]
        mock_session = _mock_session_with_scalars(factors)
        repo = AdjFactorRepository(session=mock_session)

        result = await repo.query_batch(["000001"], adj_type=1)

        assert "000001" in result
        assert len(result) == 1
