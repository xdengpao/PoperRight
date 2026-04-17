"""
SectorRepository.get_sector_ranking 单元测试

Tests:
- 正常数据的查询和合并
- 空数据处理（SectorKline 无数据 → 返回空列表）
- 默认数据源（未指定 data_source 时使用 DC）
- 最新交易日自动查询
- 部分匹配（SectorKline 有记录但 SectorInfo 无对应记录 → 跳过）
- 排序顺序（按 change_pct 降序）

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.sector import DataSource, SectorInfo, SectorKline, SectorType
from app.services.data_engine.sector_repository import SectorRankingItem, SectorRepository


# ---------------------------------------------------------------------------
# Helpers: mock session builders
# ---------------------------------------------------------------------------


def _make_kline(
    sector_code: str,
    change_pct: Decimal | None = Decimal("2.50"),
    close: Decimal | None = Decimal("1234.56"),
    volume: int | None = 100_000,
    amount: Decimal | None = Decimal("5000000.00"),
    turnover: Decimal | None = Decimal("3.20"),
    data_source: str = "DC",
    time_val: datetime | None = None,
) -> MagicMock:
    """Create a mock SectorKline object with the given fields."""
    kline = MagicMock(spec=SectorKline)
    kline.sector_code = sector_code
    kline.data_source = data_source
    kline.freq = "1d"
    kline.time = time_val or datetime(2024, 6, 15, 0, 0, 0)
    kline.change_pct = change_pct
    kline.close = close
    kline.volume = volume
    kline.amount = amount
    kline.turnover = turnover
    return kline


def _make_info(
    sector_code: str,
    name: str = "测试板块",
    sector_type: str = "CONCEPT",
    data_source: str = "DC",
) -> MagicMock:
    """Create a mock SectorInfo object with the given fields."""
    info = MagicMock(spec=SectorInfo)
    info.sector_code = sector_code
    info.name = name
    info.sector_type = sector_type
    info.data_source = data_source
    return info


def _build_ts_session(klines: list) -> AsyncMock:
    """Build a mock AsyncSessionTS that returns the given klines."""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        m = MagicMock()
        m.scalars.return_value.all.return_value = klines
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _build_pg_session(infos: list) -> AsyncMock:
    """Build a mock AsyncSessionPG that returns the given infos."""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        m = MagicMock()
        m.scalars.return_value.all.return_value = infos
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _build_ts_session_for_latest_date(
    latest_dt: datetime | None,
    klines: list,
) -> AsyncMock:
    """Build a mock AsyncSessionTS that handles both the latest-date query
    and the kline query in sequence."""
    mock_session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count == 1:
            # First call: _get_latest_kline_trade_date → scalar_one_or_none
            m.scalar_one_or_none.return_value = latest_dt
        else:
            # Second call: kline query → scalars().all()
            m.scalars.return_value.all.return_value = klines
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ---------------------------------------------------------------------------
# Test: 正常数据查询和合并
# ---------------------------------------------------------------------------


class TestNormalMerge:
    """Test normal data query and merge — 3 klines + 3 matching infos → 3 results."""

    @pytest.mark.asyncio
    async def test_normal_merge_returns_correct_items(self):
        """3 klines with 3 matching infos should produce 3 results with correct fields."""
        klines = [
            _make_kline("BK001", change_pct=Decimal("5.20"), close=Decimal("100.00"),
                        volume=200_000, amount=Decimal("8000000"), turnover=Decimal("4.10")),
            _make_kline("BK002", change_pct=Decimal("2.30"), close=Decimal("50.00"),
                        volume=150_000, amount=Decimal("3000000"), turnover=Decimal("2.50")),
            _make_kline("BK003", change_pct=Decimal("-1.10"), close=Decimal("80.00"),
                        volume=300_000, amount=Decimal("12000000"), turnover=Decimal("6.00")),
        ]
        infos = [
            _make_info("BK001", name="人工智能", sector_type="CONCEPT"),
            _make_info("BK002", name="银行", sector_type="INDUSTRY"),
            _make_info("BK003", name="深圳", sector_type="REGION"),
        ]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert len(results) == 3

        # Results should be sorted by change_pct descending
        assert results[0].sector_code == "BK001"
        assert results[0].name == "人工智能"
        assert results[0].sector_type == "CONCEPT"
        assert results[0].change_pct == 5.20
        assert results[0].close == 100.00
        assert results[0].volume == 200_000
        assert results[0].amount == 8000000.0
        assert results[0].turnover == 4.10

        assert results[1].sector_code == "BK002"
        assert results[1].name == "银行"
        assert results[1].change_pct == 2.30

        assert results[2].sector_code == "BK003"
        assert results[2].name == "深圳"
        assert results[2].change_pct == -1.10

    @pytest.mark.asyncio
    async def test_all_results_are_sector_ranking_items(self):
        """Every result should be a SectorRankingItem instance."""
        klines = [_make_kline("BK001")]
        infos = [_make_info("BK001", name="测试")]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert len(results) == 1
        assert isinstance(results[0], SectorRankingItem)


# ---------------------------------------------------------------------------
# Test: 空数据处理
# ---------------------------------------------------------------------------


class TestEmptyData:
    """Test empty data handling — SectorKline has no data → return empty list."""

    @pytest.mark.asyncio
    async def test_empty_klines_returns_empty_list(self):
        """When SectorKline has no records, get_sector_ranking returns []."""
        klines: list = []
        infos = [_make_info("BK001", name="人工智能")]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert results == []

    @pytest.mark.asyncio
    async def test_no_latest_trade_date_returns_empty_list(self):
        """When _get_latest_kline_trade_date returns None (no data at all),
        get_sector_ranking returns []."""
        ts_session = _build_ts_session_for_latest_date(
            latest_dt=None,
            klines=[],
        )

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                # trade_date not specified → triggers _get_latest_kline_trade_date
            )

        assert results == []


# ---------------------------------------------------------------------------
# Test: 默认数据源
# ---------------------------------------------------------------------------


class TestDefaultDataSource:
    """Test default data source — when data_source not specified, auto-select."""

    @pytest.mark.asyncio
    async def test_default_data_source_auto_selects(self):
        """Calling get_sector_ranking without data_source triggers auto-selection.

        When data_source=None and sector_type=None, the repository queries
        multiple sources: DC (CONCEPT+INDUSTRY), TDX (REGION), TDX (STYLE).
        We mock both sessions to return the same data for each call, so we
        verify the auto-selection path works and returns merged results.
        """
        klines = [_make_kline("BK001", data_source="DC")]
        infos = [_make_info("BK001", name="测试", data_source="DC")]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            # Call without data_source — auto-selects DC + TDX combos
            # With sector_type specified, only one query pair is used
            results = await repo.get_sector_ranking(
                sector_type=SectorType.CONCEPT,
                trade_date=date(2024, 6, 15),
            )

        # With sector_type=CONCEPT and no data_source, auto-selects DC
        assert len(results) == 1
        assert results[0].sector_code == "BK001"

    @pytest.mark.asyncio
    async def test_explicit_dc_data_source(self):
        """Calling get_sector_ranking with data_source=DC explicitly."""
        klines = [_make_kline("BK001", data_source="DC")]
        infos = [_make_info("BK001", name="测试", data_source="DC")]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert len(results) == 1
        assert results[0].sector_code == "BK001"


# ---------------------------------------------------------------------------
# Test: 最新交易日自动查询
# ---------------------------------------------------------------------------


class TestAutoLatestTradeDate:
    """Test automatic latest trade date query when trade_date is not specified."""

    @pytest.mark.asyncio
    async def test_auto_latest_trade_date(self):
        """When trade_date is None, the method queries _get_latest_kline_trade_date
        and uses that date for the kline query."""
        latest_dt = datetime(2024, 6, 15, 0, 0, 0)
        klines = [_make_kline("BK001", change_pct=Decimal("3.00"))]
        infos = [_make_info("BK001", name="自动日期测试")]

        ts_session = _build_ts_session_for_latest_date(latest_dt, klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                # trade_date not specified → auto-query
            )

        assert len(results) == 1
        assert results[0].sector_code == "BK001"
        assert results[0].name == "自动日期测试"
        assert results[0].change_pct == 3.00


# ---------------------------------------------------------------------------
# Test: 部分匹配
# ---------------------------------------------------------------------------


class TestPartialMatch:
    """Test partial matching — SectorKline has records but SectorInfo has no
    corresponding record → skip those klines."""

    @pytest.mark.asyncio
    async def test_partial_match_skips_missing_info(self):
        """3 klines but only 2 infos → 2 results (missing one skipped)."""
        klines = [
            _make_kline("BK001", change_pct=Decimal("5.00")),
            _make_kline("BK002", change_pct=Decimal("3.00")),
            _make_kline("BK003", change_pct=Decimal("1.00")),
        ]
        # Only provide infos for BK001 and BK003 — BK002 has no SectorInfo
        infos = [
            _make_info("BK001", name="有信息A"),
            _make_info("BK003", name="有信息C"),
        ]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert len(results) == 2
        result_codes = {r.sector_code for r in results}
        assert result_codes == {"BK001", "BK003"}
        # BK002 should not appear
        assert "BK002" not in result_codes


# ---------------------------------------------------------------------------
# Test: 排序顺序
# ---------------------------------------------------------------------------


class TestSortOrder:
    """Test that results are sorted by change_pct descending, None values last."""

    @pytest.mark.asyncio
    async def test_sort_descending_by_change_pct(self):
        """Results should be sorted by change_pct descending."""
        klines = [
            _make_kline("BK001", change_pct=Decimal("-2.00")),
            _make_kline("BK002", change_pct=Decimal("8.50")),
            _make_kline("BK003", change_pct=Decimal("3.10")),
        ]
        infos = [
            _make_info("BK001", name="跌板块"),
            _make_info("BK002", name="涨板块"),
            _make_info("BK003", name="中板块"),
        ]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert len(results) == 3
        assert results[0].sector_code == "BK002"  # 8.50
        assert results[1].sector_code == "BK003"  # 3.10
        assert results[2].sector_code == "BK001"  # -2.00

    @pytest.mark.asyncio
    async def test_none_change_pct_sorted_last(self):
        """Items with None change_pct should appear after non-None items."""
        klines = [
            _make_kline("BK001", change_pct=None),
            _make_kline("BK002", change_pct=Decimal("1.50")),
            _make_kline("BK003", change_pct=None),
            _make_kline("BK004", change_pct=Decimal("-0.50")),
        ]
        infos = [
            _make_info("BK001", name="空涨幅A"),
            _make_info("BK002", name="有涨幅B"),
            _make_info("BK003", name="空涨幅C"),
            _make_info("BK004", name="有涨幅D"),
        ]

        ts_session = _build_ts_session(klines)
        pg_session = _build_pg_session(infos)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            results = await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=date(2024, 6, 15),
            )

        assert len(results) == 4
        # First two should have non-None change_pct, sorted descending
        assert results[0].change_pct == 1.50
        assert results[1].change_pct == -0.50
        # Last two should have None change_pct
        assert results[2].change_pct is None
        assert results[3].change_pct is None
