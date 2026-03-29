# Feature: a-share-quant-trading-system, Property 60: 回填参数默认值填充正确性
"""
回填参数默认值填充正确性 属性测试（Hypothesis）

属性 60：回填参数默认值填充正确性

**Validates: Requirements 25.2, 25.3**

对任意缺省 symbols 和/或缺省 start_date 的回填请求，BackfillService 应将：
- symbols 填充为 StockInfo 表中全部 is_st=False AND is_delisted=False 的有效股票列表
- start_date 填充为 today - settings.kline_history_years 年
"""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.services.data_engine.backfill_service import BackfillService

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

# 生成有效的 A 股股票代码列表（用于模拟 DB 返回）
_symbol_st = st.from_regex(r"[036]\d{5}\.(SH|SZ|BJ)", fullmatch=True)
_db_symbols_st = st.lists(_symbol_st, min_size=1, max_size=20).map(sorted)

# kline_history_years: 合理范围 1-30
_history_years_st = st.integers(min_value=1, max_value=30)


# ---------------------------------------------------------------------------
# Property 60a: symbols 为 None/空时填充为 DB 有效股票
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50)
@given(db_symbols=_db_symbols_st)
def test_resolve_symbols_fills_from_db_when_none(db_symbols: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 60: 回填参数默认值填充正确性

    **Validates: Requirements 25.2**

    当 symbols 为 None 时，_resolve_symbols 应查询 StockInfo 表中
    is_st=False AND is_delisted=False 的有效股票列表。
    """
    service = BackfillService()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = db_symbols
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.core.database.AsyncSessionPG", return_value=mock_session):
        result = asyncio.run(service._resolve_symbols(None))

    assert result == db_symbols
    mock_session.execute.assert_called_once()


@hyp_settings(max_examples=50)
@given(db_symbols=_db_symbols_st)
def test_resolve_symbols_fills_from_db_when_empty_list(db_symbols: list[str]):
    """
    # Feature: a-share-quant-trading-system, Property 60: 回填参数默认值填充正确性

    **Validates: Requirements 25.2**

    当 symbols 为空列表时，_resolve_symbols 应查询 StockInfo 表中
    is_st=False AND is_delisted=False 的有效股票列表。
    """
    service = BackfillService()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = db_symbols
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("app.core.database.AsyncSessionPG", return_value=mock_session):
        result = asyncio.run(service._resolve_symbols([]))

    assert result == db_symbols
    mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Property 60b: start_date 为 None 时填充为 today - kline_history_years
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50)
@given(history_years=_history_years_st)
def test_resolve_start_date_fills_default_when_none(history_years: int):
    """
    # Feature: a-share-quant-trading-system, Property 60: 回填参数默认值填充正确性

    **Validates: Requirements 25.3**

    当 start_date 为 None 时，_resolve_start_date 应返回
    today - settings.kline_history_years 年。
    """
    service = BackfillService()

    with patch("app.services.data_engine.backfill_service.settings") as mock_settings:
        mock_settings.kline_history_years = history_years
        result = service._resolve_start_date(None)

    today = date.today()
    expected = today.replace(year=today.year - history_years)
    assert result == expected


# ---------------------------------------------------------------------------
# Property 60c: 提供了 symbols / start_date 时保持原值
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50)
@given(
    symbols=st.lists(_symbol_st, min_size=1, max_size=10),
    start_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2024, 12, 31)),
)
def test_provided_values_are_preserved(symbols: list[str], start_date: date):
    """
    # Feature: a-share-quant-trading-system, Property 60: 回填参数默认值填充正确性

    **Validates: Requirements 25.2, 25.3**

    当 symbols 和 start_date 已提供时，_resolve_symbols 和 _resolve_start_date
    应直接返回原值，不做任何修改。
    """
    service = BackfillService()

    # _resolve_symbols with non-empty list should return as-is (no DB call)
    result_symbols = asyncio.run(service._resolve_symbols(symbols))
    assert result_symbols == symbols

    # _resolve_start_date with a date should return as-is
    result_date = service._resolve_start_date(start_date)
    assert result_date == start_date
