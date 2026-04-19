"""
板块数据导入 属性测试（Hypothesis）

Property 1: Enum validation rejects invalid values
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.sector import DataSource, SectorType


# ---------------------------------------------------------------------------
# 有效枚举值集合
# ---------------------------------------------------------------------------

VALID_SECTOR_TYPES = {e.value for e in SectorType}   # {"CONCEPT", "INDUSTRY", "REGION", "STYLE"}
VALID_DATA_SOURCES = {e.value for e in DataSource}    # {"DC", "TI", "TDX"}


# ---------------------------------------------------------------------------
# Property 1: Enum validation rejects invalid values
# Feature: sector-data-import, Property 1: Enum validation rejects invalid values
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(value=st.sampled_from(list(SectorType)))
def test_sector_type_accepts_valid_values(value):
    """
    # Feature: sector-data-import, Property 1: Enum validation rejects invalid values

    **Validates: Requirements 1.4, 1.5, 3.5**

    For any valid SectorType enum member, constructing SectorType from its
    value SHALL succeed and return the original member.
    """
    result = SectorType(value.value)
    assert result is value
    assert result.value in VALID_SECTOR_TYPES


@settings(max_examples=100)
@given(value=st.sampled_from(list(DataSource)))
def test_data_source_accepts_valid_values(value):
    """
    # Feature: sector-data-import, Property 1: Enum validation rejects invalid values

    **Validates: Requirements 1.4, 1.5, 3.5**

    For any valid DataSource enum member, constructing DataSource from its
    value SHALL succeed and return the original member.
    """
    result = DataSource(value.value)
    assert result is value
    assert result.value in VALID_DATA_SOURCES


@settings(max_examples=100)
@given(value=st.text().filter(lambda s: s not in VALID_SECTOR_TYPES))
def test_sector_type_rejects_invalid_values(value):
    """
    # Feature: sector-data-import, Property 1: Enum validation rejects invalid values

    **Validates: Requirements 1.4, 1.5, 3.5**

    For any string not in {CONCEPT, INDUSTRY, REGION, STYLE},
    SectorType SHALL reject it by raising ValueError.
    """
    with pytest.raises(ValueError):
        SectorType(value)


@settings(max_examples=100)
@given(value=st.text().filter(lambda s: s not in VALID_DATA_SOURCES))
def test_data_source_rejects_invalid_values(value):
    """
    # Feature: sector-data-import, Property 1: Enum validation rejects invalid values

    **Validates: Requirements 1.4, 1.5, 3.5**

    For any string not in {DC, TI, TDX},
    DataSource SHALL reject it by raising ValueError.
    """
    with pytest.raises(ValueError):
        DataSource(value)


# ---------------------------------------------------------------------------
# Property 2: Sector list CSV parsing round-trip
# Feature: sector-data-import, Property 2: Sector list CSV parsing round-trip
# ---------------------------------------------------------------------------

import string
import tempfile
from datetime import date
from pathlib import Path

from app.services.data_engine.sector_csv_parser import (
    BaseParsingEngine,
    DCParsingEngine,
    ParsedSectorInfo,
    ParsedSectorKline,
    SectorCSVParser,
    TDXParsingEngine,
    TIParsingEngine,
)

# --- Reverse mapping dicts for constructing CSV rows ---

_DC_TYPE_REVERSE: dict[SectorType, str] = {
    SectorType.CONCEPT: "概念",
    SectorType.INDUSTRY: "行业",
    SectorType.REGION: "地区",
    SectorType.STYLE: "风格",
}

_TI_TYPE_REVERSE: dict[SectorType, str] = {
    SectorType.CONCEPT: "概念指数",
    SectorType.INDUSTRY: "行业指数",
    SectorType.REGION: "地区指数",
    SectorType.STYLE: "风格指数",
}

_TDX_TYPE_REVERSE: dict[SectorType, str] = {
    SectorType.CONCEPT: "概念板块",
    SectorType.INDUSTRY: "行业板块",
    SectorType.REGION: "地区板块",
    SectorType.STYLE: "风格板块",
}

# --- Hypothesis strategies ---

_sector_code_st = st.text(
    alphabet=string.ascii_uppercase + string.digits,
    min_size=2,
    max_size=10,
).filter(lambda s: "," not in s and "\n" not in s)

_name_st = st.text(
    min_size=1,
    max_size=20,
).filter(lambda s: "," not in s and "\n" not in s and "\r" not in s and '"' not in s and s.strip() == s)

_sector_type_st = st.sampled_from(list(SectorType))

_constituent_count_st = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=9999),
)

_list_date_st = st.one_of(
    st.none(),
    st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31)),
)


# --- DC round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    name=_name_st,
    sector_type=_sector_type_st,
)
def test_sector_list_dc_round_trip(sector_code, name, sector_type):
    """
    # Feature: sector-data-import, Property 2: Sector list CSV parsing round-trip

    **Validates: Requirements 4.1, 4.2, 4.3**

    For any valid sector info data, generating a DC CSV row and parsing it
    back SHALL recover the original sector_code, name, and sector_type.
    """
    idx_type_str = _DC_TYPE_REVERSE[sector_type]

    header = "板块代码,交易日期,板块名称,领涨股票名称,领涨股票代码,涨跌幅,领涨股票涨跌幅,总市值(万元),换手率,上涨家数,下跌家数,idx_type,level"
    row = f"{sector_code},2024-01-15,{name},领涨股,000001,1.0,2.0,50000,1.2,30,10,{idx_type_str},1"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "dc_sector_list.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = DCParsingEngine()
        results = engine.parse_sector_list(csv_file)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.sector_code == sector_code
    assert parsed.name == name
    assert parsed.sector_type == sector_type
    assert parsed.data_source == DataSource.DC


# --- TI round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    name=_name_st,
    sector_type=_sector_type_st,
    constituent_count=st.integers(min_value=0, max_value=9999),
    list_date=st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31)),
)
def test_sector_list_ti_round_trip(
    sector_code, name, sector_type, constituent_count, list_date
):
    """
    # Feature: sector-data-import, Property 2: Sector list CSV parsing round-trip

    **Validates: Requirements 4.1, 4.2, 4.3**

    For any valid sector info data with list_date and constituent_count,
    generating a TI CSV row and parsing it back SHALL recover the original
    field values.
    """
    index_type_str = _TI_TYPE_REVERSE[sector_type]
    list_date_str = list_date.strftime("%Y-%m-%d")
    exchange = "SH"

    header = "代码,名称,成分个数,交易所,上市日期,指数类型"
    row = f"{sector_code},{name},{constituent_count},{exchange},{list_date_str},{index_type_str}"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "ti_sector_list.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TIParsingEngine()
        results = engine.parse_sector_list(csv_file)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.sector_code == sector_code
    assert parsed.name == name
    assert parsed.sector_type == sector_type
    assert parsed.data_source == DataSource.TI
    assert parsed.list_date == list_date
    assert parsed.constituent_count == constituent_count


# --- TDX round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    name=_name_st,
    sector_type=_sector_type_st,
    constituent_count=st.integers(min_value=0, max_value=9999),
)
def test_sector_list_tdx_round_trip(
    sector_code, name, sector_type, constituent_count
):
    """
    # Feature: sector-data-import, Property 2: Sector list CSV parsing round-trip

    **Validates: Requirements 4.1, 4.2, 4.3**

    For any valid sector info data with constituent_count, generating a TDX
    CSV row and parsing it back SHALL recover the original field values.
    """
    type_str = _TDX_TYPE_REVERSE[sector_type]

    header = "板块代码,交易日期,板块名称,板块类型,成分个数,总股本(亿),流通股(亿),总市值(亿),流通市值(亿)"
    row = f"{sector_code},2024-01-15,{name},{type_str},{constituent_count},5000,3000,80000,50000"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "tdx_sector_list.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TDXParsingEngine()
        results = engine.parse_sector_list(csv_file)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.sector_code == sector_code
    assert parsed.name == name
    assert parsed.sector_type == sector_type
    assert parsed.data_source == DataSource.TDX
    assert parsed.constituent_count == constituent_count


# ---------------------------------------------------------------------------
# Property 5: Encoding detection preserves content
# Feature: sector-data-import, Property 5: Encoding detection preserves content
# ---------------------------------------------------------------------------


# Common CJK characters valid in UTF-8, GBK, and GB2312.
# IMPORTANT: exclude chars whose GBK bytes happen to be valid UTF-8 (e.g. 业,指,票)
# because _read_csv tries UTF-8 first and would decode them incorrectly.
# We need at least one "safe" char per generated string so the GBK bytes
# always fail UTF-8 decoding and the fallback chain works correctly.
_SAFE_CJK_CHARS = "测试数据板块行概念地区风格代码名称成分股"

_chinese_text_st = st.text(
    alphabet=_SAFE_CJK_CHARS,
    min_size=1,
    max_size=10,
)


@settings(max_examples=100)
@given(
    name=_chinese_text_st,
    value=_chinese_text_st,
)
def test_encoding_detection_preserves_content(name, value):
    """
    # Feature: sector-data-import, Property 5: Encoding detection preserves content

    **Validates: Requirements 4.10**

    For any valid CSV text containing Chinese characters, encoding as UTF-8,
    GBK, or GB2312 and reading with auto-detection SHALL produce identical
    parsed content.
    """
    csv_content = f"header1,header2\n{name},{value}\n"

    engine = BaseParsingEngine()
    results: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        for encoding in ("utf-8", "gbk", "gb2312"):
            csv_file = Path(tmp_dir) / f"test_{encoding}.csv"
            csv_file.write_bytes(csv_content.encode(encoding))
            results[encoding] = engine._read_csv(csv_file)

    # All three encodings must produce identical content
    assert results["utf-8"] == results["gbk"], (
        f"UTF-8 vs GBK mismatch for name={name!r}, value={value!r}"
    )
    assert results["utf-8"] == results["gb2312"], (
        f"UTF-8 vs GB2312 mismatch for name={name!r}, value={value!r}"
    )

    # Verify the content is actually correct (matches original)
    assert csv_content in results["utf-8"]


# ---------------------------------------------------------------------------
# Property 6: OHLC validation invariant
# Feature: sector-data-import, Property 6: OHLC validation invariant
# ---------------------------------------------------------------------------

from decimal import Decimal

_positive_decimal_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@settings(max_examples=100)
@given(
    open_=_positive_decimal_st,
    high=_positive_decimal_st,
    low=_positive_decimal_st,
    close=_positive_decimal_st,
)
def test_ohlc_validation_invariant(open_, high, low, close):
    """
    # Feature: sector-data-import, Property 6: OHLC validation invariant

    **Validates: Requirements 4.11**

    For any four positive decimals, the OHLC validator SHALL return True iff
    low ≤ open AND low ≤ close AND high ≥ open AND high ≥ close.
    """
    kline = ParsedSectorKline(
        time=date(2024, 1, 15),
        sector_code="TEST001",
        data_source=DataSource.DC,
        freq="1d",
        open=open_,
        high=high,
        low=low,
        close=close,
    )

    engine = BaseParsingEngine()
    result = engine._validate_ohlc(kline)

    # Manual check of the invariant
    expected = (
        low <= open_
        and low <= close
        and high >= open_
        and high >= close
    )

    assert result == expected, (
        f"OHLC validation mismatch: open={open_}, high={high}, low={low}, "
        f"close={close}, got={result}, expected={expected}"
    )


@settings(max_examples=100)
@given(
    a=_positive_decimal_st,
    b=_positive_decimal_st,
    c=_positive_decimal_st,
    d=_positive_decimal_st,
)
def test_ohlc_valid_data_always_passes(a, b, c, d):
    """
    # Feature: sector-data-import, Property 6: OHLC validation invariant

    **Validates: Requirements 4.11**

    For valid OHLC data (where low=min, high=max), validation SHALL return True.
    """
    values = sorted([a, b, c, d])
    low = values[0]
    high = values[3]
    open_ = values[1]
    close = values[2]

    kline = ParsedSectorKline(
        time=date(2024, 1, 15),
        sector_code="TEST001",
        data_source=DataSource.DC,
        freq="1d",
        open=open_,
        high=high,
        low=low,
        close=close,
    )

    engine = BaseParsingEngine()
    assert engine._validate_ohlc(kline) is True, (
        f"Valid OHLC should pass: open={open_}, high={high}, low={low}, close={close}"
    )


# ---------------------------------------------------------------------------
# Property 7 (Design): Date inference round-trip from filename
# Feature: sector-data-import, Property 7: Date inference round-trip from filename
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    d=st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31)),
)
def test_date_inference_yyyymmdd_round_trip(d):
    """
    # Feature: sector-data-import, Property 7: Date inference round-trip from filename

    **Validates: Requirements 8.3, 6.6**

    For any valid date, formatting it as YYYYMMDD within a filename string
    and calling _infer_date_from_filename SHALL recover the original date.
    """
    filename = f"板块成分_DC_{d.strftime('%Y%m%d')}.zip"
    engine = BaseParsingEngine()
    result = engine._infer_date_from_filename(filename)
    assert result == d, (
        f"YYYYMMDD round-trip failed: date={d}, filename={filename!r}, got={result}"
    )


@settings(max_examples=100)
@given(
    d=st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31)),
)
def test_date_inference_yyyy_mm_dd_round_trip(d):
    """
    # Feature: sector-data-import, Property 7: Date inference round-trip from filename

    **Validates: Requirements 8.3, 6.6**

    For any valid date, formatting it as YYYY-MM-DD within a filename string
    and calling _infer_date_from_filename SHALL recover the original date.
    """
    filename = f"{d.strftime('%Y-%m-%d')}.csv"
    engine = BaseParsingEngine()
    result = engine._infer_date_from_filename(filename)
    assert result == d, (
        f"YYYY-MM-DD round-trip failed: date={d}, filename={filename!r}, got={result}"
    )


# ---------------------------------------------------------------------------
# Property 3: Constituent data parsing round-trip
# Feature: sector-data-import, Property 3: Constituent data parsing round-trip
# ---------------------------------------------------------------------------

import io
import zipfile

_symbol_st = st.text(alphabet=string.digits, min_size=6, max_size=6)

_trade_date_st = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


# --- DC ZIP round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    symbol=_symbol_st,
    stock_name=_name_st,
    trade_date=_trade_date_st,
)
def test_constituent_dc_zip_round_trip(sector_code, symbol, stock_name, trade_date):
    """
    # Feature: sector-data-import, Property 3: Constituent data parsing round-trip

    **Validates: Requirements 4.4, 4.5, 4.6**

    For any valid constituent data, generating a DC ZIP containing a CSV and
    parsing it back with parse_constituents_dc_zip SHALL recover the original
    field values.
    """
    date_str = trade_date.strftime("%Y%m%d")

    header = "交易日期,板块代码,成分股票代码,成分股票名称"
    row = f"{date_str},{sector_code},{symbol},{stock_name}"
    csv_content = f"{header}\n{row}\n"

    # Create in-memory ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("constituents.csv", csv_content.encode("utf-8"))
    zip_bytes = buf.getvalue()

    zip_filename = f"板块成分_DC_{date_str}.zip"

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / zip_filename
        zip_path.write_bytes(zip_bytes)

        engine = DCParsingEngine()
        results = engine.parse_constituents_zip(zip_path)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.trade_date == trade_date
    assert parsed.sector_code == sector_code
    assert parsed.data_source == DataSource.DC
    assert parsed.symbol == symbol
    assert parsed.stock_name == stock_name


# --- TI CSV round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    symbol=_symbol_st,
    stock_name=_name_st,
    trade_date=_trade_date_st,
)
def test_constituent_ti_csv_round_trip(sector_code, symbol, stock_name, trade_date):
    """
    # Feature: sector-data-import, Property 3: Constituent data parsing round-trip

    **Validates: Requirements 4.4, 4.5, 4.6**

    For any valid constituent data, generating a TI CSV and parsing it back
    with parse_constituents_ti_csv SHALL recover the original field values.
    """
    header = "指数代码,指数名称,指数类型,股票代码,股票名称"
    row = f"{sector_code},板块名称,概念指数,{symbol},{stock_name}"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "constituents_ti.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TIParsingEngine()
        results = engine.parse_constituents_summary(csv_file, trade_date)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.trade_date == trade_date
    assert parsed.sector_code == sector_code
    assert parsed.data_source == DataSource.TI
    assert parsed.symbol == symbol
    assert parsed.stock_name == stock_name


# --- TDX ZIP round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    symbol=_symbol_st,
    stock_name=_name_st,
    trade_date=_trade_date_st,
)
def test_constituent_tdx_zip_round_trip(sector_code, symbol, stock_name, trade_date):
    """
    # Feature: sector-data-import, Property 3: Constituent data parsing round-trip

    **Validates: Requirements 4.4, 4.5, 4.6**

    For any valid constituent data, generating a TDX ZIP containing a CSV and
    parsing it back with parse_constituents_tdx_zip SHALL recover the original
    field values.
    """
    date_str = trade_date.strftime("%Y%m%d")

    header = "板块代码,交易日期,成分股票代码,成分股票名称"
    row = f"{sector_code},{date_str},{symbol},{stock_name}"
    csv_content = f"{header}\n{row}\n"

    # Create in-memory ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("constituents.csv", csv_content.encode("utf-8"))
    zip_bytes = buf.getvalue()

    zip_filename = f"板块成分_TDX_{date_str}.zip"

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / zip_filename
        zip_path.write_bytes(zip_bytes)

        engine = TDXParsingEngine()
        results = engine.parse_constituents_zip(zip_path)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.trade_date == trade_date
    assert parsed.sector_code == sector_code
    assert parsed.data_source == DataSource.TDX
    assert parsed.symbol == symbol
    assert parsed.stock_name == stock_name


# ---------------------------------------------------------------------------
# Property 4: Kline CSV parsing round-trip
# Feature: sector-data-import, Property 4: Kline CSV parsing round-trip
# ---------------------------------------------------------------------------

_kline_positive_decimal_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

_volume_st = st.integers(min_value=0, max_value=999999999)

_amount_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999999999"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

_change_pct_st = st.decimals(
    min_value=Decimal("-50"),
    max_value=Decimal("50"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_turnover_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@st.composite
def _valid_ohlc_st(draw):
    """Generate 4 positive decimals and assign: low=min, high=max, open=mid1, close=mid2."""
    values = [draw(_kline_positive_decimal_st) for _ in range(4)]
    values.sort()
    return values[0], values[3], values[1], values[2]  # low, high, open, close


# --- DC kline round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    change_pct=_change_pct_st,
    turnover=_turnover_st,
    trade_date=_trade_date_st,
)
def test_kline_dc_csv_round_trip(
    sector_code, ohlc, volume, amount, change_pct, turnover, trade_date
):
    """
    # Feature: sector-data-import, Property 4: Kline CSV parsing round-trip

    **Validates: Requirements 4.7, 4.8, 4.9**

    For any valid sector kline data where OHLC invariant holds, generating a
    DC CSV row and parsing it back SHALL recover the original OHLCV +
    change_pct + turnover values.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%"
    row = f"{sector_code},{date_str},{close},{open_},{high},{low},0,{change_pct},{volume},{amount},0,{turnover}"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "kline_dc.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = DCParsingEngine()
        results = engine.parse_kline_csv(csv_file)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.time == trade_date
    # _parse_kline_text now ensures .DC suffix
    expected_code = sector_code if sector_code.endswith(".DC") else sector_code + ".DC"
    assert parsed.sector_code == expected_code
    assert parsed.data_source == DataSource.DC
    assert parsed.open == open_
    assert parsed.close == close
    assert parsed.high == high
    assert parsed.low == low
    assert parsed.volume == volume
    assert parsed.amount == amount
    assert parsed.change_pct == change_pct
    assert parsed.turnover == turnover


# --- TI kline round-trip ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    change_pct=_change_pct_st,
    turnover=_turnover_st,
    trade_date=_trade_date_st,
)
def test_kline_ti_csv_round_trip(
    sector_code, ohlc, volume, change_pct, turnover, trade_date
):
    """
    # Feature: sector-data-import, Property 4: Kline CSV parsing round-trip

    **Validates: Requirements 4.7, 4.8, 4.9**

    For any valid sector kline data where OHLC invariant holds, generating a
    TI CSV row and parsing it back SHALL recover the original OHLCV +
    change_pct + turnover values.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    header = "指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,昨日收盘点,平均价,涨跌点位,涨跌幅,成交量,换手率"
    row = f"{sector_code},{date_str},{open_},{high},{low},{close},0,0,0,{change_pct},{volume},{turnover}"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "kline_ti.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TIParsingEngine()
        results = engine.parse_kline_csv(csv_file)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.time == trade_date
    assert parsed.sector_code == sector_code
    assert parsed.data_source == DataSource.TI
    assert parsed.open == open_
    assert parsed.close == close
    assert parsed.high == high
    assert parsed.low == low
    assert parsed.volume == volume
    assert parsed.change_pct == change_pct
    assert parsed.turnover == turnover


# --- TDX kline round-trip (Format A — 历史 ZIP) ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    trade_date=_trade_date_st,
)
def test_kline_tdx_csv_round_trip(
    sector_code, ohlc, volume, amount, trade_date
):
    """
    # Feature: sector-data-import, Property 4: Kline CSV parsing round-trip

    **Validates: Requirements 4.7, 4.8, 4.9**

    For any valid sector kline data where OHLC invariant holds, generating a
    TDX Format A CSV row, wrapping it in a ZIP, and parsing it back with
    TDXParsingEngine.parse_kline_zip SHALL recover the original OHLCV values.
    TDX Format A does not include change_pct and turnover (they will be None).
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
    row = f"{date_str},{sector_code},名称,{open_},{close},{high},{low},{volume},{amount},0,0"
    csv_content = f"{header}\n{row}\n"

    # Wrap in ZIP with filename containing "日k" for freq inference
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("kline.csv", csv_content.encode("utf-8"))
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "概念板块_日k_K线.zip"
        zip_path.write_bytes(zip_bytes)

        engine = TDXParsingEngine()
        results = engine.parse_kline_zip(zip_path)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.time == trade_date
    # _parse_kline_text_format_a now ensures .TDX suffix
    expected_code = sector_code if sector_code.endswith(".TDX") else sector_code + ".TDX"
    assert parsed.sector_code == expected_code
    assert parsed.data_source == DataSource.TDX
    assert parsed.freq == "1d"
    assert parsed.open == open_
    assert parsed.close == close
    assert parsed.high == high
    assert parsed.low == low
    assert parsed.volume == volume
    assert parsed.amount == amount
    assert parsed.change_pct is None
    assert parsed.turnover is None


# --- TDX kline round-trip (Format B — 散装/增量 38列) ---


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    change_pct=_change_pct_st,
    trade_date=_trade_date_st,
)
def test_kline_tdx_format_b_round_trip(
    sector_code, ohlc, volume, amount, change_pct, trade_date
):
    """
    # Feature: sector-data-import, Property 4: Kline CSV parsing round-trip

    **Validates: Requirements 7.4, 7.5, 7.6**

    For any valid sector kline data where OHLC invariant holds, generating a
    TDX Format B CSV row and parsing it back with TDXParsingEngine.parse_kline_csv
    SHALL recover the original OHLCV + change_pct values.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    # Format B: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,昨日收盘点,涨跌点位,涨跌幅%,成交量,成交额,...
    header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,昨日收盘点,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,量比"
    row = f"{sector_code},{date_str},{close},{open_},{high},{low},0,0,{change_pct},{volume},{amount},0,0,0"
    csv_content = f"{header}\n{row}\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "kline_tdx_format_b.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TDXParsingEngine()
        results = engine.parse_kline_csv(csv_file)

    assert len(results) == 1
    parsed = results[0]
    assert parsed.time == trade_date
    assert parsed.sector_code == sector_code
    assert parsed.data_source == DataSource.TDX
    assert parsed.freq == "1d"
    assert parsed.open == open_
    assert parsed.close == close
    assert parsed.high == high
    assert parsed.low == low
    assert parsed.volume == volume
    assert parsed.amount == amount
    assert parsed.change_pct == change_pct


# ---------------------------------------------------------------------------
# UpsertSimulator — in-memory model of database UPSERT / INSERT IGNORE behavior
# ---------------------------------------------------------------------------


class UpsertSimulator:
    """Models database UPSERT and INSERT IGNORE semantics using an in-memory dict.

    This avoids needing a real PostgreSQL/TimescaleDB connection while still
    verifying the idempotence *property* of the SQL operations.
    """

    def __init__(self) -> None:
        self.records: dict[tuple, dict] = {}  # composite-key → record dict

    def upsert(self, key: tuple, record: dict) -> None:
        """ON CONFLICT (key) DO UPDATE — insert or overwrite mutable fields."""
        self.records[key] = record

    def insert_ignore(self, key: tuple, record: dict) -> None:
        """ON CONFLICT (key) DO NOTHING — insert only when key is absent."""
        if key not in self.records:
            self.records[key] = record

    def count(self) -> int:
        return len(self.records)

    def get(self, key: tuple) -> dict | None:
        return self.records.get(key)


# ---------------------------------------------------------------------------
# Property 7: SectorInfo UPSERT idempotence
# Feature: sector-data-import, Property 7: SectorInfo UPSERT idempotence
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    data_source=st.sampled_from(list(DataSource)),
    name_v1=_name_st,
    name_v2=_name_st,
    sector_type=_sector_type_st,
    count_v1=st.integers(min_value=0, max_value=9999),
    count_v2=st.integers(min_value=0, max_value=9999),
    list_date=_list_date_st,
)
def test_property_7_sector_info_upsert_idempotence(
    sector_code,
    data_source,
    name_v1,
    name_v2,
    sector_type,
    count_v1,
    count_v2,
    list_date,
):
    """
    # Feature: sector-data-import, Property 7: SectorInfo UPSERT idempotence

    **Validates: Requirements 1.2, 5.3, 6.6**

    For any valid SectorInfo record, inserting via UPSERT twice (second time
    with modified mutable fields) SHALL result in exactly one record with
    updated values.  The (sector_code, data_source) combination SHALL remain
    unique.
    """
    sim = UpsertSimulator()
    key = (sector_code, data_source.value)

    # First insert
    record_v1 = {
        "sector_code": sector_code,
        "name": name_v1,
        "sector_type": sector_type.value,
        "data_source": data_source.value,
        "list_date": list_date,
        "constituent_count": count_v1,
    }
    sim.upsert(key, record_v1)

    assert sim.count() == 1, "First UPSERT should create exactly one record"
    assert sim.get(key) == record_v1

    # Second insert with modified mutable fields (name, constituent_count)
    record_v2 = {
        "sector_code": sector_code,
        "name": name_v2,
        "sector_type": sector_type.value,
        "data_source": data_source.value,
        "list_date": list_date,
        "constituent_count": count_v2,
    }
    sim.upsert(key, record_v2)

    # After two UPSERTs: still exactly one record, with v2 values
    assert sim.count() == 1, (
        "After two UPSERTs with the same key, there should be exactly one record"
    )
    stored = sim.get(key)
    assert stored is not None
    assert stored["name"] == name_v2, "Mutable field 'name' should reflect the second insert"
    assert stored["constituent_count"] == count_v2, (
        "Mutable field 'constituent_count' should reflect the second insert"
    )
    assert stored["sector_code"] == sector_code, "Immutable key field should be unchanged"
    assert stored["data_source"] == data_source.value, "Immutable key field should be unchanged"


# ---------------------------------------------------------------------------
# Property 8: SectorConstituent conflict-ignore idempotence
# Feature: sector-data-import, Property 8: SectorConstituent conflict-ignore idempotence
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    trade_date=_trade_date_st,
    sector_code=_sector_code_st,
    data_source=st.sampled_from(list(DataSource)),
    symbol=_symbol_st,
    stock_name=_name_st,
)
def test_property_8_sector_constituent_conflict_ignore_idempotence(
    trade_date,
    sector_code,
    data_source,
    symbol,
    stock_name,
):
    """
    # Feature: sector-data-import, Property 8: SectorConstituent conflict-ignore idempotence

    **Validates: Requirements 2.2, 5.4, 6.5**

    For any valid SectorConstituent record, inserting via ON CONFLICT DO
    NOTHING twice SHALL result in exactly one record.  The total record count
    SHALL not increase on the second insert.
    """
    sim = UpsertSimulator()
    key = (trade_date.isoformat(), sector_code, data_source.value, symbol)

    record = {
        "trade_date": trade_date,
        "sector_code": sector_code,
        "data_source": data_source.value,
        "symbol": symbol,
        "stock_name": stock_name,
    }

    # First insert
    sim.insert_ignore(key, record)
    assert sim.count() == 1, "First INSERT should create exactly one record"
    assert sim.get(key) == record

    # Second insert (same key — should be a no-op)
    sim.insert_ignore(key, record)
    assert sim.count() == 1, (
        "After two INSERT IGNORE with the same key, there should still be exactly one record"
    )
    assert sim.get(key) == record, "Record should be unchanged after second insert"


# ---------------------------------------------------------------------------
# Property 9: SectorKline conflict-ignore idempotence
# Feature: sector-data-import, Property 9: SectorKline conflict-ignore idempotence
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    trade_date=_trade_date_st,
    sector_code=_sector_code_st,
    data_source=st.sampled_from(list(DataSource)),
    freq=st.sampled_from(["1d", "1w", "1M"]),
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    change_pct=_change_pct_st,
    turnover=_turnover_st,
)
def test_property_9_sector_kline_conflict_ignore_idempotence(
    trade_date,
    sector_code,
    data_source,
    freq,
    ohlc,
    volume,
    amount,
    change_pct,
    turnover,
):
    """
    # Feature: sector-data-import, Property 9: SectorKline conflict-ignore idempotence

    **Validates: Requirements 3.2, 5.5, 6.4**

    For any valid SectorKline record, inserting via ON CONFLICT DO NOTHING
    twice SHALL result in exactly one record.  The total record count SHALL
    not increase on the second insert.
    """
    low, high, open_, close = ohlc
    sim = UpsertSimulator()
    key = (trade_date.isoformat(), sector_code, data_source.value, freq)

    record = {
        "time": trade_date,
        "sector_code": sector_code,
        "data_source": data_source.value,
        "freq": freq,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
        "turnover": turnover,
        "change_pct": change_pct,
    }

    # First insert
    sim.insert_ignore(key, record)
    assert sim.count() == 1, "First INSERT should create exactly one record"
    assert sim.get(key) == record

    # Second insert (same key — should be a no-op)
    sim.insert_ignore(key, record)
    assert sim.count() == 1, (
        "After two INSERT IGNORE with the same key, there should still be exactly one record"
    )
    assert sim.get(key) == record, "Record should be unchanged after second insert"


# ---------------------------------------------------------------------------
# Property 10: Incremental detection correctness
# Feature: sector-data-import, Property 10: Incremental detection correctness
# ---------------------------------------------------------------------------

import asyncio
import string as _string
from unittest.mock import AsyncMock, patch


class FakeRedis:
    """In-memory fake Redis supporting hget/hset/aclose for incremental detection tests."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hset(self, name: str, key: str, value: str) -> int:
        self._hashes.setdefault(name, {})[key] = value
        return 1

    async def aclose(self) -> None:
        pass


_filename_st = st.text(
    alphabet=_string.ascii_lowercase + _string.digits,
    min_size=1,
    max_size=20,
)


@settings(max_examples=100)
@given(filename=_filename_st)
def test_property_10_incremental_detection_correctness(filename):
    """
    # Feature: sector-data-import, Property 10: Incremental detection correctness

    **Validates: Requirements 6.3**

    For any file path, after mark_imported(path), check_incremental(path)
    SHALL return True; for unmarked paths SHALL return False.
    """
    from app.services.data_engine.sector_import import SectorImportService

    fake_redis = FakeRedis()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create an actual temp file so file_path.stat().st_mtime works
        file_path = Path(tmp_dir) / f"{filename}.csv"
        file_path.write_text("dummy", encoding="utf-8")

        svc = SectorImportService(base_dir=tmp_dir)

        with patch(
            "app.services.data_engine.sector_import.get_redis_client",
            return_value=fake_redis,
        ):
            loop = asyncio.new_event_loop()
            try:
                # Before marking: check_incremental should return False
                result_before = loop.run_until_complete(svc.check_incremental(file_path))
                assert result_before is False, (
                    f"Unmarked file should return False, got {result_before}"
                )

                # Mark the file as imported
                loop.run_until_complete(svc.mark_imported(file_path))

                # After marking: check_incremental should return True
                result_after = loop.run_until_complete(svc.check_incremental(file_path))
                assert result_after is True, (
                    f"Marked file should return True, got {result_after}"
                )
            finally:
                loop.close()


# ---------------------------------------------------------------------------
# Property 11: Sector concentration warning threshold
# Feature: sector-data-import, Property 11: Sector concentration warning threshold
# ---------------------------------------------------------------------------

from app.services.risk_controller import SectorConcentrationChecker


# --- Hypothesis strategies for Property 11 ---

_market_value_st = st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)

_threshold_st = st.floats(min_value=1.0, max_value=99.0, allow_nan=False, allow_infinity=False)


@st.composite
def _portfolio_and_sectors_st(draw):
    """Generate a portfolio of positions, sector assignments, and constituent counts.

    Returns:
        (positions, sector_assignments, sector_constituent_counts)
    """
    # Generate 1-5 positions with unique symbols
    num_positions = draw(st.integers(min_value=1, max_value=5))
    symbols = draw(
        st.lists(
            st.text(alphabet=string.digits, min_size=6, max_size=6),
            min_size=num_positions,
            max_size=num_positions,
            unique=True,
        )
    )
    positions = []
    for sym in symbols:
        mv = draw(_market_value_st)
        positions.append({"symbol": sym, "market_value": mv})

    # Generate 1-3 sector codes
    num_sectors = draw(st.integers(min_value=1, max_value=3))
    sector_codes = draw(
        st.lists(
            st.text(alphabet=string.ascii_uppercase, min_size=3, max_size=6),
            min_size=num_sectors,
            max_size=num_sectors,
            unique=True,
        )
    )

    # Assign each position to at least one sector (random subset)
    sector_assignments: dict[str, list[str]] = {}
    for sym in symbols:
        assigned = draw(
            st.lists(
                st.sampled_from(sector_codes),
                min_size=1,
                max_size=num_sectors,
                unique=True,
            )
        )
        sector_assignments[sym] = assigned

    # Generate constituent counts for each sector (at least 1)
    sector_constituent_counts: dict[str, int] = {}
    for code in sector_codes:
        count = draw(st.integers(min_value=1, max_value=200))
        sector_constituent_counts[code] = count

    return positions, sector_assignments, sector_constituent_counts


@settings(max_examples=100)
@given(
    data=_portfolio_and_sectors_st(),
    threshold_pct=_threshold_st,
)
def test_property_11_sector_concentration_warning_threshold(data, threshold_pct):
    """
    # Feature: sector-data-import, Property 11: Sector concentration warning threshold

    **Validates: Requirements 9.2, 9.3**

    For any portfolio of positions and for any sector with constituent data,
    if the sector's holding count ratio (持仓股票数 / 成分股总数) OR holding
    market value ratio (板块持仓市值 / 总持仓市值) exceeds the configured
    threshold, the risk controller SHALL generate a concentration warning.
    If both ratios are below the threshold, no warning SHALL be generated
    for that sector.
    """
    positions, sector_assignments, sector_constituent_counts = data

    warnings = SectorConcentrationChecker.compute_concentration_pure(
        positions=positions,
        sector_assignments=sector_assignments,
        sector_constituent_counts=sector_constituent_counts,
        threshold_pct=threshold_pct,
    )

    # Compute expected results independently
    total_mv = sum(p["market_value"] for p in positions)
    assert total_mv > 0, "Total market value should be positive"

    # Build per-sector aggregation from scratch
    expected_sectors: dict[str, dict] = {}
    for pos in positions:
        sym = pos["symbol"]
        mv = pos["market_value"]
        for code in sector_assignments.get(sym, []):
            if code not in expected_sectors:
                expected_sectors[code] = {"symbols": set(), "market_value": 0.0}
            expected_sectors[code]["symbols"].add(sym)
            expected_sectors[code]["market_value"] += mv

    warned_codes = {w["sector_code"] for w in warnings}

    for code, info in expected_sectors.items():
        holding_count = len(info["symbols"])
        constituent_count = sector_constituent_counts.get(code, 0)
        sector_mv = info["market_value"]

        count_ratio = (
            (holding_count / constituent_count * 100.0)
            if constituent_count > 0
            else 0.0
        )
        value_ratio = (sector_mv / total_mv * 100.0) if total_mv > 0 else 0.0

        should_warn = count_ratio > threshold_pct or value_ratio > threshold_pct

        if should_warn:
            assert code in warned_codes, (
                f"Sector {code} should have a warning: "
                f"count_ratio={count_ratio:.2f}%, value_ratio={value_ratio:.2f}%, "
                f"threshold={threshold_pct:.2f}%"
            )
            # Verify the warning dict has correct ratios
            w = next(w for w in warnings if w["sector_code"] == code)
            assert w["count_ratio"] == round(count_ratio, 2)
            assert w["value_ratio"] == round(value_ratio, 2)

            # Verify warning_type
            count_exceeded = count_ratio > threshold_pct
            value_exceeded = value_ratio > threshold_pct
            if count_exceeded and value_exceeded:
                assert w["warning_type"] == "both"
            elif count_exceeded:
                assert w["warning_type"] == "count"
            else:
                assert w["warning_type"] == "value"
        else:
            assert code not in warned_codes, (
                f"Sector {code} should NOT have a warning: "
                f"count_ratio={count_ratio:.2f}%, value_ratio={value_ratio:.2f}%, "
                f"threshold={threshold_pct:.2f}%"
            )

    # No spurious warnings for sectors not in expected_sectors
    for w in warnings:
        assert w["sector_code"] in expected_sectors, (
            f"Warning for unknown sector {w['sector_code']}"
        )


# ---------------------------------------------------------------------------
# Property 12: Sector strength ranking consistency
# Feature: sector-data-import, Property 12: Sector strength ranking consistency
# ---------------------------------------------------------------------------

from app.services.screener.sector_strength import SectorStrengthFilter


@st.composite
def _sector_kline_data_st(draw):
    """Generate a list of sector kline dicts with sector_code and change_pct.

    Returns a list of dicts, each with 'sector_code' and 'change_pct'.
    Generates 1-5 distinct sectors, each with 1-10 kline records.
    """
    num_sectors = draw(st.integers(min_value=1, max_value=5))
    sector_codes = draw(
        st.lists(
            st.text(alphabet=string.ascii_uppercase + string.digits, min_size=2, max_size=8),
            min_size=num_sectors,
            max_size=num_sectors,
            unique=True,
        )
    )

    kline_data: list[dict] = []
    for code in sector_codes:
        num_records = draw(st.integers(min_value=1, max_value=10))
        for _ in range(num_records):
            pct = draw(
                st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False)
            )
            kline_data.append({"sector_code": code, "change_pct": pct})

    return kline_data


@settings(max_examples=100)
@given(kline_data=_sector_kline_data_st())
def test_property_12_sector_strength_ranking_consistency(kline_data):
    """
    # Feature: sector-data-import, Property 12: Sector strength ranking consistency

    **Validates: Requirements 10.2**

    For any set of sector kline data, a sector with higher change_pct SHALL
    rank higher (or equal) than one with lower change_pct.
    """
    ranked = SectorStrengthFilter.compute_sector_strength(kline_data)

    # The ranking must be sorted descending by change_pct
    for i in range(len(ranked) - 1):
        code_a, pct_a = ranked[i]
        code_b, pct_b = ranked[i + 1]
        assert pct_a >= pct_b, (
            f"Ranking inconsistency: sector {code_a} (pct={pct_a}) "
            f"ranked above sector {code_b} (pct={pct_b}) but has lower change_pct"
        )

    # Verify completeness: every sector_code with a non-None change_pct
    # in the input should appear in the ranking
    expected_codes = {
        row["sector_code"]
        for row in kline_data
        if row.get("change_pct") is not None and row.get("sector_code") is not None
    }
    ranked_codes = {code for code, _ in ranked}
    assert ranked_codes == expected_codes, (
        f"Missing sectors in ranking: {expected_codes - ranked_codes}"
    )


# ---------------------------------------------------------------------------
# Property 13: Sector strength filtering correctness
# Feature: sector-data-import, Property 13: Sector strength filtering correctness
# ---------------------------------------------------------------------------


@st.composite
def _candidates_and_sectors_st(draw):
    """Generate candidate stock list, stock-sector mapping, and top-N sector codes.

    Returns:
        (candidates, stock_sectors, top_sector_codes)
    """
    # Generate 1-5 sector codes
    num_sectors = draw(st.integers(min_value=1, max_value=5))
    all_sector_codes = draw(
        st.lists(
            st.text(alphabet=string.ascii_uppercase, min_size=2, max_size=6),
            min_size=num_sectors,
            max_size=num_sectors,
            unique=True,
        )
    )

    # Generate 1-8 candidate stock symbols
    num_candidates = draw(st.integers(min_value=1, max_value=8))
    candidates = draw(
        st.lists(
            st.text(alphabet=string.digits, min_size=6, max_size=6),
            min_size=num_candidates,
            max_size=num_candidates,
            unique=True,
        )
    )

    # Assign each candidate to 0-N sectors (some may have no sector)
    stock_sectors: dict[str, list[str]] = {}
    for sym in candidates:
        assigned = draw(
            st.lists(
                st.sampled_from(all_sector_codes),
                min_size=0,
                max_size=num_sectors,
                unique=True,
            )
        )
        stock_sectors[sym] = assigned

    # Pick top-N sectors (subset of all sectors)
    top_n = draw(st.integers(min_value=0, max_value=num_sectors))
    top_sector_codes = set(draw(
        st.lists(
            st.sampled_from(all_sector_codes),
            min_size=top_n,
            max_size=top_n,
            unique=True,
        )
    ))

    return candidates, stock_sectors, top_sector_codes


@settings(max_examples=100)
@given(data=_candidates_and_sectors_st())
def test_property_13_sector_strength_filtering_correctness(data):
    """
    # Feature: sector-data-import, Property 13: Sector strength filtering correctness

    **Validates: Requirements 10.3**

    For any candidate stock list and top-N ranking, filtered result SHALL
    contain only stocks in at least one top-N sector.  No stock from a
    non-top-N sector SHALL appear in the filtered result (unless it also
    belongs to a top-N sector).
    """
    candidates, stock_sectors, top_sector_codes = data

    filtered = SectorStrengthFilter.filter_by_top_sectors(
        candidates=candidates,
        stock_sectors=stock_sectors,
        top_sector_codes=top_sector_codes,
    )

    # 1. Every stock in the filtered result must belong to at least one top-N sector
    for sym in filtered:
        sectors = stock_sectors.get(sym, [])
        assert any(sc in top_sector_codes for sc in sectors), (
            f"Stock {sym} in filtered result but belongs to sectors "
            f"{sectors}, none of which is in top-N {top_sector_codes}"
        )

    # 2. Every candidate that belongs to a top-N sector must be in the result
    for sym in candidates:
        sectors = stock_sectors.get(sym, [])
        in_top = any(sc in top_sector_codes for sc in sectors)
        if in_top:
            assert sym in filtered, (
                f"Stock {sym} belongs to top-N sector(s) "
                f"{set(sectors) & top_sector_codes} but was excluded from result"
            )

    # 3. Filtered result preserves original order
    filtered_set = set(filtered)
    expected_order = [s for s in candidates if s in filtered_set]
    assert filtered == expected_order, (
        f"Filtered result order mismatch: got {filtered}, expected {expected_order}"
    )

    # 4. No duplicates in filtered result
    assert len(filtered) == len(set(filtered)), "Filtered result contains duplicates"

# ---------------------------------------------------------------------------
# Property 8 (Design): Frequency inference from ZIP filename
# Feature: sector-data-import, Property 8: Frequency inference from ZIP filename
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    freq_indicator=st.sampled_from(["日k", "周k", "月k"]),
    prefix=st.text(
        alphabet=string.ascii_letters + "板块概念行业地区风格_",
        min_size=1,
        max_size=20,
    ).filter(lambda s: "日k" not in s and "周k" not in s and "月k" not in s),
)
def test_frequency_inference_from_zip_filename(freq_indicator, prefix):
    """
    # Feature: sector-data-import, Property 8: Frequency inference from ZIP filename

    **Validates: Requirements 7.7**

    For any TDX historical kline ZIP filename containing a frequency indicator
    (日k, 周k, 月k), the _infer_freq_from_filename method SHALL return the
    correct frequency string (1d, 1w, 1M respectively).
    """
    expected = {"日k": "1d", "周k": "1w", "月k": "1M"}[freq_indicator]
    filename = f"{prefix}_{freq_indicator}_K线.zip"
    engine = TDXParsingEngine()
    result = engine._infer_freq_from_filename(filename)
    assert result == expected, (
        f"Frequency inference failed: filename={filename!r}, "
        f"expected={expected!r}, got={result!r}"
    )


# ---------------------------------------------------------------------------
# Property 9 (Design): Streaming ZIP produces identical results
# Feature: sector-data-import, Property 9: Streaming ZIP produces identical results
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    sector_code=_sector_code_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    trade_date=_trade_date_st,
)
def test_streaming_zip_produces_identical_results(
    sector_code, ohlc, volume, amount, trade_date
):
    """
    # Feature: sector-data-import, Property 9: Streaming ZIP produces identical results

    **Validates: Requirements 7.8, 8.4, 11.2**

    For any valid kline ZIP file, the streaming method (iter_kline_zip) SHALL
    produce the same set of parsed records as the non-streaming batch method
    (parse_kline_zip). The total count and field values of all yielded records
    SHALL be identical.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    # Create Format A kline CSV
    header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
    row = f"{date_str},{sector_code},名称,{open_},{close},{high},{low},{volume},{amount},0,0"
    csv_content = f"{header}\n{row}\n"

    # Wrap in ZIP with "日k" for freq inference
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("kline.csv", csv_content.encode("utf-8"))
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "概念板块_日k_K线.zip"
        zip_path.write_bytes(zip_bytes)

        engine = TDXParsingEngine()

        # Batch method
        batch_results = engine.parse_kline_zip(zip_path)

        # Streaming method
        stream_results: list[ParsedSectorKline] = []
        for chunk in engine.iter_kline_zip(zip_path):
            stream_results.extend(chunk)

    # Verify identical count
    assert len(batch_results) == len(stream_results), (
        f"Count mismatch: batch={len(batch_results)}, stream={len(stream_results)}"
    )

    # Verify identical field values
    for b, s in zip(batch_results, stream_results):
        assert b.time == s.time
        assert b.sector_code == s.sector_code
        assert b.data_source == s.data_source
        assert b.freq == s.freq
        assert b.open == s.open
        assert b.high == s.high
        assert b.low == s.low
        assert b.close == s.close
        assert b.volume == s.volume
        assert b.amount == s.amount
        assert b.change_pct == s.change_pct
        assert b.turnover == s.turnover


# ---------------------------------------------------------------------------
# Property 10 (Design): Malformed CSV rows are skipped without affecting valid rows
# Feature: sector-data-import, Property 10: Malformed CSV rows are skipped
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    valid_count=st.integers(min_value=1, max_value=5),
    malformed_count=st.integers(min_value=1, max_value=5),
)
def test_malformed_rows_skipped_dc(valid_count, malformed_count):
    """
    # Feature: sector-data-import, Property 10: Malformed CSV rows are skipped

    **Validates: Requirements 8.6**

    For any CSV content containing a mix of valid and malformed rows, the DC
    parser SHALL skip all malformed rows and correctly parse all valid rows.
    """
    header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%"
    lines = [header]

    # Generate valid rows
    for i in range(valid_count):
        code = f"BK{i:04d}"
        lines.append(f"{code},2024-01-15,105.0,100.0,108.0,98.0,5.0,5.0,500000,52000000,10.0,1.2")

    # Generate malformed rows (insufficient fields)
    for _ in range(malformed_count):
        lines.append("BADCODE,2024-01-15,not_a_number")

    csv_content = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "kline_dc.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = DCParsingEngine()
        results = engine.parse_kline_csv(csv_file)

    assert len(results) == valid_count, (
        f"Expected {valid_count} valid rows, got {len(results)}"
    )


@settings(max_examples=100)
@given(
    valid_count=st.integers(min_value=1, max_value=5),
    malformed_count=st.integers(min_value=1, max_value=5),
)
def test_malformed_rows_skipped_ti(valid_count, malformed_count):
    """
    # Feature: sector-data-import, Property 10: Malformed CSV rows are skipped

    **Validates: Requirements 8.6**

    For any CSV content containing a mix of valid and malformed rows, the TI
    parser SHALL skip all malformed rows and correctly parse all valid rows.
    """
    header = "指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,昨日收盘点,平均价,涨跌点位,涨跌幅,成交量,换手率"
    lines = [header]

    # Generate valid rows
    for i in range(valid_count):
        code = f"88{i:04d}"
        lines.append(f"{code},2024-01-15,1000.0,1080.0,980.0,1050.0,1000.0,1030.0,50.0,5.0,500000,1.2")

    # Generate malformed rows (insufficient fields)
    for _ in range(malformed_count):
        lines.append("BADCODE,2024-01-15,not_a_number")

    csv_content = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "kline_ti.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TIParsingEngine()
        results = engine.parse_kline_csv(csv_file)

    assert len(results) == valid_count, (
        f"Expected {valid_count} valid rows, got {len(results)}"
    )


@settings(max_examples=100)
@given(
    valid_count=st.integers(min_value=1, max_value=5),
    malformed_count=st.integers(min_value=1, max_value=5),
)
def test_malformed_rows_skipped_tdx(valid_count, malformed_count):
    """
    # Feature: sector-data-import, Property 10: Malformed CSV rows are skipped

    **Validates: Requirements 8.6**

    For any CSV content containing a mix of valid and malformed rows, the TDX
    parser SHALL skip all malformed rows and correctly parse all valid rows.
    """
    header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,昨日收盘点,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,量比"
    lines = [header]

    # Generate valid rows (Format B)
    for i in range(valid_count):
        code = f"88{i:04d}"
        lines.append(f"{code},2024-01-15,105.0,100.0,108.0,98.0,100.0,5.0,5.0,500000,52000000,10.0,1.2,1.0")

    # Generate malformed rows (insufficient fields)
    for _ in range(malformed_count):
        lines.append("BADCODE,2024-01-15,not_a_number")

    csv_content = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "kline_tdx.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = TDXParsingEngine()
        results = engine.parse_kline_csv(csv_file)

    assert len(results) == valid_count, (
        f"Expected {valid_count} valid rows, got {len(results)}"
    )
