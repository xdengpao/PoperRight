"""
板块涨跌幅排行 属性测试（Hypothesis）

Property 1: Dual-query merge correctness
"""

from __future__ import annotations

import asyncio
import string
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.sector import DataSource, SectorInfo, SectorKline, SectorType
from app.services.data_engine.sector_repository import SectorRankingItem, SectorRepository


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_sector_code_st = st.text(
    alphabet=string.ascii_uppercase + string.digits,
    min_size=2,
    max_size=10,
)

_name_st = st.text(
    alphabet=string.ascii_letters + string.digits,
    min_size=1,
    max_size=20,
)

_sector_type_st = st.sampled_from([e.value for e in SectorType])

_change_pct_st = st.one_of(
    st.none(),
    st.decimals(
        min_value=Decimal("-50"),
        max_value=Decimal("50"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)

_close_st = st.one_of(
    st.none(),
    st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("99999"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)

_volume_st = st.one_of(st.none(), st.integers(min_value=0, max_value=999999999))

_amount_st = st.one_of(
    st.none(),
    st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("9999999999"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)

_turnover_st = st.one_of(
    st.none(),
    st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("99999"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)


@st.composite
def sector_kline_strategy(draw):
    """Generate a fake SectorKline-like object with random fields."""
    code = draw(_sector_code_st)
    kline = MagicMock(spec=SectorKline)
    kline.sector_code = code
    kline.data_source = DataSource.DC.value
    kline.freq = "1d"
    kline.time = datetime(2024, 6, 15, 0, 0, 0)
    kline.change_pct = draw(_change_pct_st)
    kline.close = draw(_close_st)
    kline.volume = draw(_volume_st)
    kline.amount = draw(_amount_st)
    kline.turnover = draw(_turnover_st)
    return kline


@st.composite
def sector_info_strategy(draw, sector_code: str | None = None):
    """Generate a fake SectorInfo-like object with random fields."""
    code = sector_code if sector_code is not None else draw(_sector_code_st)
    info = MagicMock(spec=SectorInfo)
    info.sector_code = code
    info.name = draw(_name_st)
    info.sector_type = draw(_sector_type_st)
    info.data_source = DataSource.DC.value
    return info


# ---------------------------------------------------------------------------
# Helpers: mock session builders
# ---------------------------------------------------------------------------

def _build_ts_session_mock(klines: list):
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


def _build_pg_session_mock(infos: list):
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


# ---------------------------------------------------------------------------
# Property 1: Dual-query merge correctness
# Feature: sector-ranking-display, Property 1: Dual-query merge correctness
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    kline_data=st.lists(sector_kline_strategy(), min_size=0, max_size=15),
    extra_info_codes=st.lists(_sector_code_st, min_size=0, max_size=5),
)
def test_dual_query_merge_correctness(kline_data, extra_info_codes):
    """
    # Feature: sector-ranking-display, Property 1: Dual-query merge correctness

    **Validates: Requirements 1.2, 1.3, 2.3**

    For any set of SectorKline records and SectorInfo records sharing the same
    data_source, calling get_sector_ranking SHALL return items where each
    item's name and sector_type match the corresponding SectorInfo record, and
    each item's change_pct, close, volume, amount, turnover match the
    corresponding SectorKline record. Only sector_codes present in both tables
    SHALL appear in the result.
    """
    # Deduplicate klines by sector_code (keep first occurrence)
    seen_codes: set[str] = set()
    unique_klines: list = []
    for k in kline_data:
        if k.sector_code not in seen_codes:
            seen_codes.add(k.sector_code)
            unique_klines.append(k)

    # Build SectorInfo for a subset of kline codes + some extra codes not in klines
    kline_codes = [k.sector_code for k in unique_klines]

    # Create infos for all kline codes (so we have full overlap)
    infos: list = []
    info_map: dict[str, MagicMock] = {}
    for code in kline_codes:
        info = MagicMock(spec=SectorInfo)
        info.sector_code = code
        info.name = f"Name_{code}"
        info.sector_type = "CONCEPT"
        info.data_source = DataSource.DC.value
        infos.append(info)
        info_map[code] = info

    # Add extra infos that have no matching kline (should NOT appear in result)
    for code in extra_info_codes:
        if code not in info_map:
            extra_info = MagicMock(spec=SectorInfo)
            extra_info.sector_code = code
            extra_info.name = f"Extra_{code}"
            extra_info.sector_type = "INDUSTRY"
            extra_info.data_source = DataSource.DC.value
            infos.append(extra_info)

    # Build mock sessions
    ts_session = _build_ts_session_mock(unique_klines)
    pg_session = _build_pg_session_mock(infos)

    trade_date = date(2024, 6, 15)

    async def _run():
        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            return await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=trade_date,
            )

    results = asyncio.run(_run())

    # Build lookup maps for verification
    kline_map = {k.sector_code: k for k in unique_klines}
    result_codes = {r.sector_code for r in results}

    # 1) Only sector_codes present in BOTH klines and infos appear in result
    expected_codes = set(kline_codes) & {i.sector_code for i in infos}
    assert result_codes == expected_codes, (
        f"Result codes {result_codes} != expected intersection {expected_codes}"
    )

    # 2) Each result item's fields match the corresponding source records
    for item in results:
        assert isinstance(item, SectorRankingItem)

        # name and sector_type come from SectorInfo
        si = info_map[item.sector_code]
        assert item.name == si.name, (
            f"name mismatch for {item.sector_code}: {item.name} != {si.name}"
        )
        assert item.sector_type == si.sector_type, (
            f"sector_type mismatch for {item.sector_code}: "
            f"{item.sector_type} != {si.sector_type}"
        )

        # change_pct, close, volume, amount, turnover come from SectorKline
        k = kline_map[item.sector_code]
        expected_change_pct = float(k.change_pct) if k.change_pct is not None else None
        expected_close = float(k.close) if k.close is not None else None
        expected_amount = float(k.amount) if k.amount is not None else None
        expected_turnover = float(k.turnover) if k.turnover is not None else None

        assert item.change_pct == expected_change_pct, (
            f"change_pct mismatch for {item.sector_code}: "
            f"{item.change_pct} != {expected_change_pct}"
        )
        assert item.close == expected_close, (
            f"close mismatch for {item.sector_code}: {item.close} != {expected_close}"
        )
        assert item.volume == k.volume, (
            f"volume mismatch for {item.sector_code}: {item.volume} != {k.volume}"
        )
        assert item.amount == expected_amount, (
            f"amount mismatch for {item.sector_code}: {item.amount} != {expected_amount}"
        )
        assert item.turnover == expected_turnover, (
            f"turnover mismatch for {item.sector_code}: "
            f"{item.turnover} != {expected_turnover}"
        )


@settings(max_examples=100)
@given(
    kline_data=st.lists(sector_kline_strategy(), min_size=1, max_size=10),
)
def test_dual_query_merge_partial_info(kline_data):
    """
    # Feature: sector-ranking-display, Property 1: Dual-query merge correctness

    **Validates: Requirements 1.2, 1.3, 2.3**

    When SectorInfo records exist for only a subset of kline sector_codes,
    only the intersection SHALL appear in the result. Klines without matching
    SectorInfo SHALL be excluded.
    """
    # Deduplicate klines by sector_code
    seen_codes: set[str] = set()
    unique_klines: list = []
    for k in kline_data:
        if k.sector_code not in seen_codes:
            seen_codes.add(k.sector_code)
            unique_klines.append(k)

    if len(unique_klines) < 2:
        # Need at least 2 unique codes to test partial matching
        return

    # Only create infos for the first half of kline codes
    half = len(unique_klines) // 2
    codes_with_info = [k.sector_code for k in unique_klines[:half]]
    codes_without_info = [k.sector_code for k in unique_klines[half:]]

    infos: list = []
    for code in codes_with_info:
        info = MagicMock(spec=SectorInfo)
        info.sector_code = code
        info.name = f"Name_{code}"
        info.sector_type = "INDUSTRY"
        info.data_source = DataSource.DC.value
        infos.append(info)

    ts_session = _build_ts_session_mock(unique_klines)
    pg_session = _build_pg_session_mock(infos)

    trade_date = date(2024, 6, 15)

    async def _run():
        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            return await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=trade_date,
            )

    results = asyncio.run(_run())

    result_codes = {r.sector_code for r in results}

    # Only codes with info should appear
    assert result_codes == set(codes_with_info), (
        f"Expected only {codes_with_info} but got {result_codes}"
    )

    # Codes without info should NOT appear
    for code in codes_without_info:
        assert code not in result_codes, (
            f"Code {code} should not appear (no SectorInfo)"
        )


# ---------------------------------------------------------------------------
# Property 2: Ranking sort order invariant
# Feature: sector-ranking-display, Property 2: Ranking sort order invariant
# ---------------------------------------------------------------------------


@st.composite
def klines_with_varied_change_pct(draw):
    """Generate a list of unique-code klines with varied change_pct values (including None).

    Returns (klines, infos) where infos cover all kline sector_codes so the
    merge step keeps every record — isolating the sort-order property.
    """
    n = draw(st.integers(min_value=0, max_value=20))
    klines = []
    infos = []
    used_codes: set[str] = set()

    for i in range(n):
        # Ensure unique sector_code per kline
        code = draw(
            _sector_code_st.filter(lambda c, _used=used_codes: c not in _used)
        )
        used_codes.add(code)

        change_pct = draw(
            st.one_of(
                st.none(),
                st.floats(
                    min_value=-50.0,
                    max_value=50.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            )
        )

        kline = MagicMock(spec=SectorKline)
        kline.sector_code = code
        kline.data_source = DataSource.DC.value
        kline.freq = "1d"
        kline.time = datetime(2024, 6, 15, 0, 0, 0)
        kline.change_pct = Decimal(str(change_pct)) if change_pct is not None else None
        kline.close = Decimal("100.00")
        kline.volume = 10000
        kline.amount = Decimal("5000000.00")
        kline.turnover = Decimal("3.50")
        klines.append(kline)

        info = MagicMock(spec=SectorInfo)
        info.sector_code = code
        info.name = f"Sector_{code}"
        info.sector_type = "INDUSTRY"
        info.data_source = DataSource.DC.value
        infos.append(info)

    return klines, infos


@settings(max_examples=100)
@given(data=klines_with_varied_change_pct())
def test_ranking_sort_order_invariant(data):
    """
    # Feature: sector-ranking-display, Property 2: Ranking sort order invariant

    **Validates: Requirements 1.4, 2.4**

    For any list of SectorRankingItem results returned by get_sector_ranking,
    the items SHALL be sorted by change_pct in descending order. Items with
    non-null change_pct SHALL appear before items with null change_pct. Among
    non-null items, for any adjacent pair (item[i], item[i+1]),
    item[i].change_pct >= item[i+1].change_pct SHALL hold.
    """
    klines, infos = data

    ts_session = _build_ts_session_mock(klines)
    pg_session = _build_pg_session_mock(infos)

    trade_date = date(2024, 6, 15)

    async def _run():
        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            return await repo.get_sector_ranking(
                data_source=DataSource.DC,
                trade_date=trade_date,
            )

    results = asyncio.run(_run())

    # --- Verify sort order ---

    # Partition results into non-None and None change_pct groups
    non_none_items = [r for r in results if r.change_pct is not None]
    none_items = [r for r in results if r.change_pct is None]

    # 1) All non-None change_pct items must appear before all None items
    if non_none_items and none_items:
        # Find the index of the last non-None item and the first None item
        last_non_none_idx = max(
            i for i, r in enumerate(results) if r.change_pct is not None
        )
        first_none_idx = min(
            i for i, r in enumerate(results) if r.change_pct is None
        )
        assert last_non_none_idx < first_none_idx, (
            f"Non-None items must come before None items: "
            f"last non-None at index {last_non_none_idx}, "
            f"first None at index {first_none_idx}"
        )

    # 2) Among non-None items, descending order must hold for adjacent pairs
    for i in range(len(non_none_items) - 1):
        assert non_none_items[i].change_pct >= non_none_items[i + 1].change_pct, (
            f"Sort order violated at position {i}: "
            f"{non_none_items[i].change_pct} < {non_none_items[i + 1].change_pct}"
        )


# ---------------------------------------------------------------------------
# Property 3: Sector type filtering correctness
# Feature: sector-ranking-display, Property 3: Sector type filtering correctness
# ---------------------------------------------------------------------------

# Sets of enum values used to prevent sector_code collisions in strategies
_VALID_SECTOR_TYPES = {e.value for e in SectorType}
_VALID_DATA_SOURCES = {e.value for e in DataSource}

# Sector code strategy that avoids collisions with enum values
_safe_sector_code_st = _sector_code_st.filter(
    lambda c: c not in _VALID_SECTOR_TYPES and c not in _VALID_DATA_SOURCES
)


def _build_pg_session_mock_for_type(infos: list, filter_type: str | None):
    """Build a mock AsyncSessionPG that returns infos filtered by sector_type.

    Instead of inspecting compiled SQL (which is fragile), this mock accepts
    an explicit *filter_type* parameter:
    - When filter_type is a string, only infos with matching sector_type are returned.
    - When filter_type is None, all infos are returned.
    """
    if filter_type is not None:
        filtered_infos = [i for i in infos if i.sector_type == filter_type]
    else:
        filtered_infos = infos

    mock_session = AsyncMock()

    async def mock_execute(stmt):
        m = MagicMock()
        m.scalars.return_value.all.return_value = filtered_infos
        return m

    mock_session.execute = mock_execute
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


@st.composite
def mixed_type_sector_data(draw):
    """Generate klines and infos with mixed sector_types.

    Returns (klines, infos, type_to_codes) where:
    - klines: list of SectorKline mocks with unique sector_codes
    - infos: list of SectorInfo mocks with sector_types drawn from SectorType enum
    - type_to_codes: dict mapping each sector_type value to the set of sector_codes

    Sector codes are filtered to avoid collisions with SectorType / DataSource
    enum values, which previously caused false positives in SQL string inspection.
    """
    n = draw(st.integers(min_value=2, max_value=15))
    klines = []
    infos = []
    used_codes: set[str] = set()
    type_to_codes: dict[str, set[str]] = {e.value: set() for e in SectorType}

    for _ in range(n):
        code = draw(
            _safe_sector_code_st.filter(lambda c, _used=used_codes: c not in _used)
        )
        used_codes.add(code)
        sector_type = draw(_sector_type_st)

        kline = MagicMock(spec=SectorKline)
        kline.sector_code = code
        kline.data_source = DataSource.DC.value
        kline.freq = "1d"
        kline.time = datetime(2024, 6, 15, 0, 0, 0)
        kline.change_pct = draw(_change_pct_st)
        kline.close = Decimal("100.00")
        kline.volume = 10000
        kline.amount = Decimal("5000000.00")
        kline.turnover = Decimal("3.50")
        klines.append(kline)

        info = MagicMock(spec=SectorInfo)
        info.sector_code = code
        info.name = f"Sector_{code}"
        info.sector_type = sector_type
        info.data_source = DataSource.DC.value
        infos.append(info)

        type_to_codes[sector_type].add(code)

    return klines, infos, type_to_codes


@settings(max_examples=100)
@given(data=mixed_type_sector_data())
def test_sector_type_filter_returns_only_matching_type(data):
    """
    # Feature: sector-ranking-display, Property 3: Sector type filtering correctness

    **Validates: Requirements 1.5, 1.6**

    When get_sector_ranking is called with a specific sector_type filter,
    all returned items SHALL have sector_type equal to the filter value.
    """
    klines, infos, type_to_codes = data

    # Pick a sector_type that has at least one sector in the data
    non_empty_types = [t for t, codes in type_to_codes.items() if codes]
    if not non_empty_types:
        return

    trade_date = date(2024, 6, 15)

    for filter_type_value in non_empty_types:
        filter_type = SectorType(filter_type_value)

        ts_session = _build_ts_session_mock(klines)
        pg_session = _build_pg_session_mock_for_type(infos, filter_type_value)

        async def _run(_ts=ts_session, _pg=pg_session):
            with patch(
                "app.services.data_engine.sector_repository.AsyncSessionTS",
                return_value=_ts,
            ), patch(
                "app.services.data_engine.sector_repository.AsyncSessionPG",
                return_value=_pg,
            ):
                repo = SectorRepository()
                return await repo.get_sector_ranking(
                    sector_type=filter_type,
                    data_source=DataSource.DC,
                    trade_date=trade_date,
                )

        results = asyncio.run(_run())

        # All returned items must have the filtered sector_type
        for item in results:
            assert item.sector_type == filter_type_value, (
                f"Expected sector_type={filter_type_value} but got "
                f"{item.sector_type} for {item.sector_code}"
            )

        # The returned codes should match exactly the codes of that type
        result_codes = {r.sector_code for r in results}
        expected_codes = type_to_codes[filter_type_value]
        assert result_codes == expected_codes, (
            f"For type={filter_type_value}: result codes {result_codes} "
            f"!= expected {expected_codes}"
        )


@settings(max_examples=100)
@given(data=mixed_type_sector_data())
def test_sector_type_filter_none_returns_all_types(data):
    """
    # Feature: sector-ranking-display, Property 3: Sector type filtering correctness

    **Validates: Requirements 1.5, 1.6**

    When get_sector_ranking is called without a sector_type filter,
    the result SHALL contain items from all sector_types present in the data.
    """
    klines, infos, type_to_codes = data

    ts_session = _build_ts_session_mock(klines)
    pg_session = _build_pg_session_mock_for_type(infos, filter_type=None)

    trade_date = date(2024, 6, 15)

    async def _run():
        with patch(
            "app.services.data_engine.sector_repository.AsyncSessionTS",
            return_value=ts_session,
        ), patch(
            "app.services.data_engine.sector_repository.AsyncSessionPG",
            return_value=pg_session,
        ):
            repo = SectorRepository()
            return await repo.get_sector_ranking(
                sector_type=None,
                data_source=DataSource.DC,
                trade_date=trade_date,
            )

    results = asyncio.run(_run())

    # All sector_codes should be present (no filtering)
    result_codes = {r.sector_code for r in results}
    all_codes = {k.sector_code for k in klines}
    assert result_codes == all_codes, (
        f"Without filter: result codes {result_codes} != all codes {all_codes}"
    )

    # The result should contain items from all types that have data
    result_types = {r.sector_type for r in results}
    expected_types = {t for t, codes in type_to_codes.items() if codes}
    assert result_types == expected_types, (
        f"Without filter: result types {result_types} != expected {expected_types}"
    )


# ---------------------------------------------------------------------------
# Property 4: Invalid parameter rejection
# Feature: sector-ranking-display, Property 4: Invalid parameter rejection
# ---------------------------------------------------------------------------

_VALID_SECTOR_TYPES = {e.value for e in SectorType}
_VALID_DATA_SOURCES = {e.value for e in DataSource}

# Strategy: generate non-empty strings that are NOT valid enum values
_invalid_sector_type_st = st.text(min_size=1, max_size=30).filter(
    lambda s: s not in _VALID_SECTOR_TYPES
)
_invalid_data_source_st = st.text(min_size=1, max_size=30).filter(
    lambda s: s not in _VALID_DATA_SOURCES
)


@settings(max_examples=100)
@given(invalid_type=_invalid_sector_type_st)
def test_invalid_sector_type_returns_422(invalid_type):
    """
    # Feature: sector-ranking-display, Property 4: Invalid parameter rejection

    **Validates: Requirements 1.9**

    For any string that is not a valid SectorType value (not in
    {CONCEPT, INDUSTRY, REGION, STYLE}), the GET /sector/ranking endpoint
    SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/ranking",
                params={"sector_type": invalid_type},
            )
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code == 422, (
        f"Expected 422 for invalid sector_type={invalid_type!r}, "
        f"got {resp.status_code}"
    )


@settings(max_examples=100)
@given(invalid_source=_invalid_data_source_st)
def test_invalid_data_source_returns_422(invalid_source):
    """
    # Feature: sector-ranking-display, Property 4: Invalid parameter rejection

    **Validates: Requirements 1.9**

    For any string that is not a valid DataSource value (not in
    {DC, TI, TDX}), the GET /sector/ranking endpoint SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/ranking",
                params={"data_source": invalid_source},
            )
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code == 422, (
        f"Expected 422 for invalid data_source={invalid_source!r}, "
        f"got {resp.status_code}"
    )


@settings(max_examples=100)
@given(
    sector_type=st.sampled_from(list(SectorType)),
    data_source=st.sampled_from(list(DataSource)),
)
def test_valid_enum_values_accepted(sector_type, data_source):
    """
    # Feature: sector-ranking-display, Property 4: Invalid parameter rejection

    **Validates: Requirements 1.9**

    All valid SectorType and DataSource enum values SHALL be accepted
    without returning HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _run():
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_sector_ranking = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/ranking",
                    params={
                        "sector_type": sector_type.value,
                        "data_source": data_source.value,
                    },
                )
        return resp

    resp = asyncio.run(_run())
    assert resp.status_code != 422, (
        f"Valid enum values sector_type={sector_type.value}, "
        f"data_source={data_source.value} should NOT return 422, "
        f"got {resp.status_code}"
    )
