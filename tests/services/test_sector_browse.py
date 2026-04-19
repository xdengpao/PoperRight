"""
SectorRepository 分页浏览方法单元测试

覆盖：
- browse_sector_info：基本分页、筛选组合（data_source + sector_type + keyword）、空结果
- browse_sector_constituent：基本分页、默认交易日（trade_date=None 时调用 get_latest_trade_date）
- browse_sector_kline：基本分页、日期范围过滤

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.sector import DataSource, SectorConstituent, SectorInfo, SectorKline, SectorType
from app.services.data_engine.sector_repository import PaginatedResult, SectorRepository


# ---------------------------------------------------------------------------
# Helpers: mock 数据构造
# ---------------------------------------------------------------------------


def _make_sector_info(
    sector_code: str = "BK0001",
    name: str = "测试板块",
    sector_type: str = "CONCEPT",
    data_source: str = "DC",
    list_date: date | None = None,
    constituent_count: int | None = 100,
) -> MagicMock:
    """构造 mock SectorInfo 对象。"""
    info = MagicMock(spec=SectorInfo)
    info.sector_code = sector_code
    info.name = name
    info.sector_type = sector_type
    info.data_source = data_source
    info.list_date = list_date
    info.constituent_count = constituent_count
    return info


def _make_constituent(
    trade_date: date = date(2024, 6, 15),
    sector_code: str = "BK0001",
    data_source: str = "DC",
    symbol: str = "600000",
    stock_name: str | None = "浦发银行",
) -> MagicMock:
    """构造 mock SectorConstituent 对象。"""
    c = MagicMock(spec=SectorConstituent)
    c.trade_date = trade_date
    c.sector_code = sector_code
    c.data_source = data_source
    c.symbol = symbol
    c.stock_name = stock_name
    return c


def _make_kline(
    time_val: datetime = datetime(2024, 6, 15, 0, 0, 0),
    sector_code: str = "BK0001",
    data_source: str = "DC",
    freq: str = "1d",
    close: Decimal | None = Decimal("1234.56"),
    change_pct: Decimal | None = Decimal("2.50"),
) -> MagicMock:
    """构造 mock SectorKline 对象。"""
    k = MagicMock(spec=SectorKline)
    k.time = time_val
    k.sector_code = sector_code
    k.data_source = data_source
    k.freq = freq
    k.open = Decimal("1200.00")
    k.high = Decimal("1250.00")
    k.low = Decimal("1190.00")
    k.close = close
    k.volume = 100000
    k.amount = Decimal("5000000.00")
    k.turnover = Decimal("3.20")
    k.change_pct = change_pct
    return k


def _build_pg_session(total: int, items: list) -> AsyncMock:
    """构造 mock AsyncSessionPG，支持 count 查询和数据查询。"""
    mock_session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count % 2 == 1:
            # 奇数次调用：count 查询
            m.scalar_one.return_value = total
        else:
            # 偶数次调用：数据查询
            m.scalars.return_value.all.return_value = items
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _build_ts_session(total: int, items: list) -> AsyncMock:
    """构造 mock AsyncSessionTS，支持 count 查询和数据查询。"""
    mock_session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count % 2 == 1:
            m.scalar_one.return_value = total
        else:
            m.scalars.return_value.all.return_value = items
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _build_pg_session_for_latest_date(latest_date: date | None) -> AsyncMock:
    """构造 mock AsyncSessionPG，仅返回最新交易日（用于 get_latest_trade_date）。"""
    mock_session = AsyncMock()

    async def mock_execute(stmt):
        m = MagicMock()
        m.scalar_one_or_none.return_value = latest_date
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ---------------------------------------------------------------------------
# browse_sector_info 测试
# ---------------------------------------------------------------------------


class TestBrowseSectorInfo:
    """browse_sector_info 分页查询测试。"""

    @pytest.mark.asyncio
    async def test_basic_pagination(self):
        """基本分页：返回 PaginatedResult，total 和 items 正确。

        Validates: Requirement 10.1, 10.4
        """
        items = [
            _make_sector_info("BK0001", name="人工智能"),
            _make_sector_info("BK0002", name="半导体"),
        ]
        pg_session = _build_pg_session(total=10, items=items)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_info(page=1, page_size=2)

        assert isinstance(result, PaginatedResult)
        assert result.total == 10
        assert len(result.items) == 2
        assert result.items[0].sector_code == "BK0001"
        assert result.items[1].sector_code == "BK0002"

    @pytest.mark.asyncio
    async def test_with_filters(self):
        """筛选组合：data_source + sector_type + keyword 同时传入。

        Validates: Requirement 10.1, 10.7
        """
        items = [_make_sector_info("BK0001", name="人工智能", sector_type="CONCEPT", data_source="DC")]
        pg_session = _build_pg_session(total=1, items=items)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_info(
                data_source=DataSource.DC,
                sector_type=SectorType.CONCEPT,
                keyword="人工",
                page=1,
                page_size=50,
            )

        assert isinstance(result, PaginatedResult)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].name == "人工智能"

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """空结果：total=0，items=[]。

        Validates: Requirement 10.4
        """
        pg_session = _build_pg_session(total=0, items=[])

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_info(
                data_source=DataSource.TI,
                keyword="不存在的板块",
            )

        assert result.total == 0
        assert result.items == []


# ---------------------------------------------------------------------------
# browse_sector_constituent 测试
# ---------------------------------------------------------------------------


class TestBrowseSectorConstituent:
    """browse_sector_constituent 分页查询测试。"""

    @pytest.mark.asyncio
    async def test_basic_pagination(self):
        """基本分页：指定 trade_date，返回正确的分页结果。

        Validates: Requirement 10.2, 10.4
        """
        items = [
            _make_constituent(symbol="600000", stock_name="浦发银行"),
            _make_constituent(symbol="600036", stock_name="招商银行"),
        ]
        pg_session = _build_pg_session(total=50, items=items)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_constituent(
                data_source=DataSource.DC,
                sector_code="BK0001",
                trade_date=date(2024, 6, 15),
                page=1,
                page_size=2,
            )

        assert isinstance(result, PaginatedResult)
        assert result.total == 50
        assert len(result.items) == 2
        assert result.items[0].symbol == "600000"
        assert result.items[1].symbol == "600036"

    @pytest.mark.asyncio
    async def test_default_trade_date(self):
        """默认交易日：trade_date=None 时调用 get_latest_trade_date。

        Validates: Requirement 10.2
        """
        items = [_make_constituent(symbol="600000")]

        # 第一次 PG session 调用：get_latest_trade_date 返回日期
        # 第二次 PG session 调用：browse 查询
        pg_session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            if call_count == 1:
                # get_latest_trade_date → scalar_one_or_none
                m.scalar_one_or_none.return_value = date(2024, 6, 15)
            elif call_count == 2:
                # count 查询
                m.scalar_one.return_value = 1
            else:
                # 数据查询
                m.scalars.return_value.all.return_value = items
            return m

        pg_session.execute = mock_execute
        pg_session.__aenter__ = AsyncMock(return_value=pg_session)
        pg_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_constituent(
                data_source=DataSource.DC,
                # trade_date 不传，触发 get_latest_trade_date
            )

        assert isinstance(result, PaginatedResult)
        assert result.total == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_default_trade_date_none_returns_empty(self):
        """当 get_latest_trade_date 返回 None 时，返回空结果。

        Validates: Requirement 10.2
        """
        pg_session = _build_pg_session_for_latest_date(None)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_constituent(
                data_source=DataSource.DC,
            )

        assert result.total == 0
        assert result.items == []


# ---------------------------------------------------------------------------
# browse_sector_kline 测试
# ---------------------------------------------------------------------------


class TestBrowseSectorKline:
    """browse_sector_kline 分页查询测试。"""

    @pytest.mark.asyncio
    async def test_basic_pagination(self):
        """基本分页：返回正确的分页结果。

        Validates: Requirement 10.3, 10.4
        """
        items = [
            _make_kline(time_val=datetime(2024, 6, 15)),
            _make_kline(time_val=datetime(2024, 6, 14)),
        ]
        ts_session = _build_ts_session(total=100, items=items)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_kline(
                data_source=DataSource.DC,
                sector_code="BK0001",
                page=1,
                page_size=2,
            )

        assert isinstance(result, PaginatedResult)
        assert result.total == 100
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_date_range_filter(self):
        """日期范围过滤：传入 start 和 end 参数。

        Validates: Requirement 10.3
        """
        items = [_make_kline(time_val=datetime(2024, 6, 10))]
        ts_session = _build_ts_session(total=5, items=items)

        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ):
            repo = SectorRepository()
            result = await repo.browse_sector_kline(
                data_source=DataSource.DC,
                sector_code="BK0001",
                start=date(2024, 6, 1),
                end=date(2024, 6, 15),
                page=1,
                page_size=50,
            )

        assert isinstance(result, PaginatedResult)
        assert result.total == 5
        assert len(result.items) == 1
