"""
板块数据浏览 分页属性测试（Hypothesis）

Property 7: Browse pagination response structure invariant
Property 8: Browse endpoint invalid parameter rejection
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.sector import SectorConstituent, SectorInfo, SectorKline
from app.services.data_engine.sector_repository import PaginatedResult


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_page_st = st.integers(min_value=1, max_value=100)
_page_size_st = st.integers(min_value=1, max_value=200)


# ---------------------------------------------------------------------------
# Helpers: 构建 mock items
# ---------------------------------------------------------------------------


def _make_sector_info_items(count: int) -> list:
    """构建 SectorInfo mock 对象列表。"""
    items = []
    for i in range(count):
        info = MagicMock(spec=SectorInfo)
        info.sector_code = f"BK{i:04d}"
        info.name = f"板块{i}"
        info.sector_type = "CONCEPT"
        info.data_source = "DC"
        info.list_date = date(2024, 1, 1)
        info.constituent_count = 10 + i
        items.append(info)
    return items


def _make_constituent_items(count: int) -> list:
    """构建 SectorConstituent mock 对象列表。"""
    items = []
    for i in range(count):
        c = MagicMock(spec=SectorConstituent)
        c.trade_date = date(2024, 6, 15)
        c.sector_code = f"BK{i:04d}"
        c.data_source = "DC"
        c.symbol = f"{600000 + i}"
        c.stock_name = f"股票{i}"
        items.append(c)
    return items


def _make_kline_items(count: int) -> list:
    """构建 SectorKline mock 对象列表。"""
    items = []
    for i in range(count):
        k = MagicMock(spec=SectorKline)
        k.time = datetime(2024, 6, 15, 0, 0, 0)
        k.sector_code = f"BK{i:04d}"
        k.data_source = "DC"
        k.freq = "1d"
        k.open = 100.0 + i
        k.high = 105.0 + i
        k.low = 95.0 + i
        k.close = 102.0 + i
        k.volume = 10000 * (i + 1)
        k.amount = 5000000.0 * (i + 1)
        k.change_pct = 1.5 - i * 0.3
        items.append(k)
    return items


def _make_paginated_result(
    page_size: int,
    total: int,
    item_factory,
) -> PaginatedResult:
    """构建 PaginatedResult，items 数量不超过 page_size 且不超过 total。"""
    item_count = min(page_size, total)
    items = item_factory(item_count)
    return PaginatedResult(total=total, items=items)


# ---------------------------------------------------------------------------
# Property 7: Browse pagination response structure invariant
# Feature: sector-ranking-display, Property 7: Browse pagination response structure invariant
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    page=_page_st,
    page_size=_page_size_st,
    total=st.integers(min_value=0, max_value=500),
)
def test_browse_sector_info_pagination_structure(page, page_size, total):
    """
    # Feature: sector-ranking-display, Property 7: Browse pagination response structure invariant

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

    For any valid page and page_size sent to /sector/info/browse,
    the response SHALL contain total >= 0, page >= 1, page_size >= 1,
    and len(items) <= page_size.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    paginated = _make_paginated_result(page_size, total, _make_sector_info_items)

    async def _run():
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.browse_sector_info = AsyncMock(return_value=paginated)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/info/browse",
                    params={"page": page, "page_size": page_size},
                )
            return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 200, (
        f"Expected 200 for page={page}, page_size={page_size}, got {resp.status_code}"
    )

    data = resp.json()

    # 验证响应结构不变量
    assert "total" in data, "Response missing 'total' field"
    assert "page" in data, "Response missing 'page' field"
    assert "page_size" in data, "Response missing 'page_size' field"
    assert "items" in data, "Response missing 'items' field"

    assert isinstance(data["total"], int) and data["total"] >= 0, (
        f"total should be int >= 0, got {data['total']}"
    )
    assert isinstance(data["page"], int) and data["page"] >= 1, (
        f"page should be int >= 1, got {data['page']}"
    )
    assert isinstance(data["page_size"], int) and data["page_size"] >= 1, (
        f"page_size should be int >= 1, got {data['page_size']}"
    )
    assert isinstance(data["items"], list), (
        f"items should be a list, got {type(data['items'])}"
    )
    assert len(data["items"]) <= data["page_size"], (
        f"len(items)={len(data['items'])} should be <= page_size={data['page_size']}"
    )


@settings(max_examples=100, deadline=None)
@given(
    page=_page_st,
    page_size=_page_size_st,
    total=st.integers(min_value=0, max_value=500),
)
def test_browse_sector_constituent_pagination_structure(page, page_size, total):
    """
    # Feature: sector-ranking-display, Property 7: Browse pagination response structure invariant

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

    For any valid page and page_size sent to /sector/constituent/browse,
    the response SHALL contain total >= 0, page >= 1, page_size >= 1,
    and len(items) <= page_size.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    paginated = _make_paginated_result(page_size, total, _make_constituent_items)

    async def _run():
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.browse_sector_constituent = AsyncMock(
                return_value=paginated
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/constituent/browse",
                    params={
                        "data_source": "DC",
                        "page": page,
                        "page_size": page_size,
                    },
                )
            return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 200, (
        f"Expected 200 for page={page}, page_size={page_size}, got {resp.status_code}"
    )

    data = resp.json()

    # 验证响应结构不变量
    assert "total" in data, "Response missing 'total' field"
    assert "page" in data, "Response missing 'page' field"
    assert "page_size" in data, "Response missing 'page_size' field"
    assert "items" in data, "Response missing 'items' field"

    assert isinstance(data["total"], int) and data["total"] >= 0, (
        f"total should be int >= 0, got {data['total']}"
    )
    assert isinstance(data["page"], int) and data["page"] >= 1, (
        f"page should be int >= 1, got {data['page']}"
    )
    assert isinstance(data["page_size"], int) and data["page_size"] >= 1, (
        f"page_size should be int >= 1, got {data['page_size']}"
    )
    assert isinstance(data["items"], list), (
        f"items should be a list, got {type(data['items'])}"
    )
    assert len(data["items"]) <= data["page_size"], (
        f"len(items)={len(data['items'])} should be <= page_size={data['page_size']}"
    )


@settings(max_examples=100, deadline=None)
@given(
    page=_page_st,
    page_size=_page_size_st,
    total=st.integers(min_value=0, max_value=500),
)
def test_browse_sector_kline_pagination_structure(page, page_size, total):
    """
    # Feature: sector-ranking-display, Property 7: Browse pagination response structure invariant

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

    For any valid page and page_size sent to /sector/kline/browse,
    the response SHALL contain total >= 0, page >= 1, page_size >= 1,
    and len(items) <= page_size.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    paginated = _make_paginated_result(page_size, total, _make_kline_items)

    async def _run():
        with patch(
            "app.api.v1.sector.SectorRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.browse_sector_kline = AsyncMock(return_value=paginated)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/kline/browse",
                    params={
                        "data_source": "DC",
                        "page": page,
                        "page_size": page_size,
                    },
                )
            return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 200, (
        f"Expected 200 for page={page}, page_size={page_size}, got {resp.status_code}"
    )

    data = resp.json()

    # 验证响应结构不变量
    assert "total" in data, "Response missing 'total' field"
    assert "page" in data, "Response missing 'page' field"
    assert "page_size" in data, "Response missing 'page_size' field"
    assert "items" in data, "Response missing 'items' field"

    assert isinstance(data["total"], int) and data["total"] >= 0, (
        f"total should be int >= 0, got {data['total']}"
    )
    assert isinstance(data["page"], int) and data["page"] >= 1, (
        f"page should be int >= 1, got {data['page']}"
    )
    assert isinstance(data["page_size"], int) and data["page_size"] >= 1, (
        f"page_size should be int >= 1, got {data['page_size']}"
    )
    assert isinstance(data["items"], list), (
        f"items should be a list, got {type(data['items'])}"
    )
    assert len(data["items"]) <= data["page_size"], (
        f"len(items)={len(data['items'])} should be <= page_size={data['page_size']}"
    )


# ---------------------------------------------------------------------------
# Property 8: Browse endpoint invalid parameter rejection
# Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection
# ---------------------------------------------------------------------------

_VALID_DATA_SOURCES = {"DC", "TI", "TDX"}
_VALID_SECTOR_TYPES = {"CONCEPT", "INDUSTRY", "REGION", "STYLE"}

# 生成非有效 DataSource 的随机字符串
_invalid_data_source_st = st.text(min_size=1).filter(
    lambda s: s not in _VALID_DATA_SOURCES
)

# 生成非有效 SectorType 的随机字符串
_invalid_sector_type_st = st.text(min_size=1).filter(
    lambda s: s not in _VALID_SECTOR_TYPES
)

# 生成非有效日期格式的随机字符串（排除 YYYY-MM-DD 格式）
_invalid_date_st = st.text(min_size=1).filter(
    lambda s: not _is_valid_date(s)
)


def _is_valid_date(s: str) -> bool:
    """检查字符串是否为有效的 YYYY-MM-DD 日期格式。"""
    try:
        date.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


@settings(max_examples=100, deadline=None)
@given(invalid_ds=_invalid_data_source_st)
def test_browse_sector_info_rejects_invalid_data_source(invalid_ds):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid DataSource value,
    GET /sector/info/browse SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/info/browse",
                params={"data_source": invalid_ds},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid data_source='{invalid_ds}', got {resp.status_code}"
    )


@settings(max_examples=100, deadline=None)
@given(invalid_st=_invalid_sector_type_st)
def test_browse_sector_info_rejects_invalid_sector_type(invalid_st):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid SectorType value,
    GET /sector/info/browse SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/info/browse",
                params={"sector_type": invalid_st},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid sector_type='{invalid_st}', got {resp.status_code}"
    )


@settings(max_examples=100, deadline=None)
@given(invalid_ds=_invalid_data_source_st)
def test_browse_sector_constituent_rejects_invalid_data_source(invalid_ds):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid DataSource value,
    GET /sector/constituent/browse SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/constituent/browse",
                params={"data_source": invalid_ds},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid data_source='{invalid_ds}', got {resp.status_code}"
    )


@settings(max_examples=100, deadline=None)
@given(invalid_date=_invalid_date_st)
def test_browse_sector_constituent_rejects_invalid_trade_date(invalid_date):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid YYYY-MM-DD date,
    GET /sector/constituent/browse SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/constituent/browse",
                params={"data_source": "DC", "trade_date": invalid_date},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid trade_date='{invalid_date}', got {resp.status_code}"
    )


@settings(max_examples=100, deadline=None)
@given(invalid_ds=_invalid_data_source_st)
def test_browse_sector_kline_rejects_invalid_data_source(invalid_ds):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid DataSource value,
    GET /sector/kline/browse SHALL return HTTP 422.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/kline/browse",
                params={"data_source": invalid_ds},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid data_source='{invalid_ds}', got {resp.status_code}"
    )


@settings(max_examples=100, deadline=None)
@given(invalid_date=_invalid_date_st)
def test_browse_sector_kline_rejects_invalid_start_date(invalid_date):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid YYYY-MM-DD date,
    GET /sector/kline/browse SHALL return HTTP 422 when passed as start parameter.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/kline/browse",
                params={"data_source": "DC", "start": invalid_date},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid start='{invalid_date}', got {resp.status_code}"
    )


@settings(max_examples=100, deadline=None)
@given(invalid_date=_invalid_date_st)
def test_browse_sector_kline_rejects_invalid_end_date(invalid_date):
    """
    # Feature: sector-ranking-display, Property 8: Browse endpoint invalid parameter rejection

    **Validates: Requirements 10.5**

    For any string that is not a valid YYYY-MM-DD date,
    GET /sector/kline/browse SHALL return HTTP 422 when passed as end parameter.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get(
                "/api/v1/sector/kline/browse",
                params={"data_source": "DC", "end": invalid_date},
            )
        return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 422, (
        f"Expected 422 for invalid end='{invalid_date}', got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Property 9: Keyword search filtering correctness
# Feature: sector-ranking-display, Property 9: Keyword search filtering correctness
# ---------------------------------------------------------------------------

# 策略：生成随机板块数据，从中提取子串作为 keyword，
# mock 仓储层返回仅包含匹配项的结果（模拟 ILIKE），
# 验证 API 返回的所有 item 的 sector_code 或 name 包含 keyword（不区分大小写）。

# 中文字符 + ASCII 字母数字混合策略，用于生成板块名称
_cn_char_st = st.sampled_from(
    list("科技金融医药消费能源材料工业信息电子汽车半导体芯片新能源光伏储能锂电")
)
_sector_name_st = st.lists(_cn_char_st, min_size=2, max_size=6).map(lambda cs: "".join(cs))

# 板块代码策略：BK + 4 位数字
_sector_code_st = st.integers(min_value=0, max_value=9999).map(lambda n: f"BK{n:04d}")

# 股票代码策略：6 位数字
_symbol_st = st.integers(min_value=0, max_value=999999).map(lambda n: f"{n:06d}")

# 股票名称策略
_stock_name_st = st.lists(_cn_char_st, min_size=2, max_size=4).map(lambda cs: "".join(cs))


def _make_sector_info_items_with_data(
    sector_codes: list[str],
    names: list[str],
) -> list:
    """根据给定的 sector_code 和 name 构建 SectorInfo mock 对象列表。"""
    items = []
    for code, name in zip(sector_codes, names):
        info = MagicMock(spec=SectorInfo)
        info.sector_code = code
        info.name = name
        info.sector_type = "CONCEPT"
        info.data_source = "DC"
        info.list_date = date(2024, 1, 1)
        info.constituent_count = 10
        items.append(info)
    return items


def _make_constituent_items_with_data(
    symbols: list[str],
    stock_names: list[str],
) -> list:
    """根据给定的 symbol 和 stock_name 构建 SectorConstituent mock 对象列表。"""
    items = []
    for sym, sname in zip(symbols, stock_names):
        c = MagicMock(spec=SectorConstituent)
        c.trade_date = date(2024, 6, 15)
        c.sector_code = "BK0001"
        c.data_source = "DC"
        c.symbol = sym
        c.stock_name = sname
        items.append(c)
    return items


@settings(max_examples=100, deadline=None)
@given(
    sector_codes=st.lists(_sector_code_st, min_size=1, max_size=10, unique=True),
    names=st.lists(_sector_name_st, min_size=1, max_size=10),
)
def test_browse_sector_info_keyword_filtering(sector_codes, names):
    """
    # Feature: sector-ranking-display, Property 9: Keyword search filtering correctness

    **Validates: Requirements 10.7**

    For any keyword string and any set of sector_info records,
    when /sector/info/browse is called with that keyword,
    all returned items SHALL have either sector_code or name
    containing the keyword (case-insensitive).
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    # 确保 names 和 sector_codes 长度一致
    min_len = min(len(sector_codes), len(names))
    sector_codes = sector_codes[:min_len]
    names = names[:min_len]

    # 从已有数据中提取一个 keyword（取某个 name 的子串或 sector_code 的子串）
    # 随机选择第一个 item 的 name 的前 2 个字符作为 keyword
    keyword = names[0][:2] if len(names[0]) >= 2 else names[0]

    # 模拟 ILIKE 过滤：只保留 sector_code 或 name 包含 keyword 的项
    kw_lower = keyword.lower()
    matching_codes = []
    matching_names = []
    for code, name in zip(sector_codes, names):
        if kw_lower in code.lower() or kw_lower in name.lower():
            matching_codes.append(code)
            matching_names.append(name)

    # 构建 mock 返回数据（仅匹配项）
    matching_items = _make_sector_info_items_with_data(matching_codes, matching_names)
    paginated = PaginatedResult(total=len(matching_items), items=matching_items)

    app = create_app()

    async def _run():
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.browse_sector_info = AsyncMock(return_value=paginated)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/info/browse",
                    params={"keyword": keyword},
                )
            return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 200, (
        f"Expected 200 for keyword='{keyword}', got {resp.status_code}"
    )

    data = resp.json()
    items = data.get("items", [])

    # 验证所有返回的 item 的 sector_code 或 name 包含 keyword（不区分大小写）
    for item in items:
        code_lower = item["sector_code"].lower()
        name_lower = item["name"].lower()
        assert kw_lower in code_lower or kw_lower in name_lower, (
            f"Item sector_code='{item['sector_code']}', name='{item['name']}' "
            f"does not contain keyword='{keyword}' (case-insensitive)"
        )


@settings(max_examples=100, deadline=None)
@given(
    symbols=st.lists(_symbol_st, min_size=1, max_size=10, unique=True),
    stock_names=st.lists(_stock_name_st, min_size=1, max_size=10),
)
def test_browse_sector_constituent_keyword_filtering(symbols, stock_names):
    """
    # Feature: sector-ranking-display, Property 9: Keyword search filtering correctness

    **Validates: Requirements 10.7**

    For any keyword string and any set of sector_constituent records,
    when /sector/constituent/browse is called with that keyword,
    all returned items SHALL have either symbol or stock_name
    containing the keyword (case-insensitive).
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    # 确保 symbols 和 stock_names 长度一致
    min_len = min(len(symbols), len(stock_names))
    symbols = symbols[:min_len]
    stock_names = stock_names[:min_len]

    # 从已有数据中提取一个 keyword（取某个 stock_name 的前 2 个字符或 symbol 的前 3 位）
    keyword = stock_names[0][:2] if len(stock_names[0]) >= 2 else stock_names[0]

    # 模拟 ILIKE 过滤：只保留 symbol 或 stock_name 包含 keyword 的项
    kw_lower = keyword.lower()
    matching_symbols = []
    matching_names = []
    for sym, sname in zip(symbols, stock_names):
        if kw_lower in sym.lower() or kw_lower in sname.lower():
            matching_symbols.append(sym)
            matching_names.append(sname)

    # 构建 mock 返回数据（仅匹配项）
    matching_items = _make_constituent_items_with_data(matching_symbols, matching_names)
    paginated = PaginatedResult(total=len(matching_items), items=matching_items)

    app = create_app()

    async def _run():
        with patch("app.api.v1.sector.SectorRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.browse_sector_constituent = AsyncMock(
                return_value=paginated
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                resp = await client.get(
                    "/api/v1/sector/constituent/browse",
                    params={"data_source": "DC", "keyword": keyword},
                )
            return resp

    resp = asyncio.run(_run())

    assert resp.status_code == 200, (
        f"Expected 200 for keyword='{keyword}', got {resp.status_code}"
    )

    data = resp.json()
    items = data.get("items", [])

    # 验证所有返回的 item 的 symbol 或 stock_name 包含 keyword（不区分大小写）
    for item in items:
        sym_lower = item["symbol"].lower()
        sname_lower = (item.get("stock_name") or "").lower()
        assert kw_lower in sym_lower or kw_lower in sname_lower, (
            f"Item symbol='{item['symbol']}', stock_name='{item.get('stock_name')}' "
            f"does not contain keyword='{keyword}' (case-insensitive)"
        )
