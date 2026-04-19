"""
板块解析修复 属性测试（Hypothesis）

Property 14: TDX sector_code suffix invariant
"""

from __future__ import annotations

import string
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_engine.sector_csv_parser import TDXParsingEngine


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 生成不含逗号、换行的板块代码（纯大写字母+数字，模拟真实 TDX 代码如 880201）
_base_code_st = st.text(
    alphabet=string.ascii_uppercase + string.digits,
    min_size=2,
    max_size=10,
).filter(lambda s: "," not in s and "\n" not in s and s.strip() == s)

# 生成带或不带 .TDX 后缀的 sector_code
_sector_code_with_optional_suffix_st = _base_code_st.flatmap(
    lambda code: st.sampled_from([code, code + ".TDX"])
)

# 生成合法 OHLC（low ≤ open, low ≤ close, high ≥ open, high ≥ close）
_positive_decimal_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@st.composite
def _valid_ohlc_st(draw):
    """生成 4 个正 Decimal 并分配: low=min, high=max, open=mid1, close=mid2。"""
    values = sorted([draw(_positive_decimal_st) for _ in range(4)])
    return values[0], values[3], values[1], values[2]  # low, high, open, close


_volume_st = st.integers(min_value=0, max_value=999999999)
_amount_st = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999999999"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
_trade_date_st = st.dates(
    min_value=__import__("datetime").date(2020, 1, 1),
    max_value=__import__("datetime").date(2030, 12, 31),
)


# ---------------------------------------------------------------------------
# Property 14: TDX sector_code suffix invariant
# Feature: sector-data-import, Property 14: TDX sector_code suffix invariant
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    sector_code=_sector_code_with_optional_suffix_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    trade_date=_trade_date_st,
)
def test_tdx_format_a_sector_code_ends_with_tdx(
    sector_code, ohlc, volume, amount, trade_date
):
    """
    # Feature: sector-data-import, Property 14: TDX sector_code suffix invariant

    **Validates: Requirements 18.1, 18.2, 18.6**

    For any sector_code (with or without .TDX suffix), constructing a Format A
    CSV row and parsing it with _parse_kline_text_format_a SHALL produce output
    where every sector_code ends with '.TDX'.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
    row = f"{date_str},{sector_code},测试板块,{open_},{close},{high},{low},{volume},{amount},0,0"
    csv_text = f"{header}\n{row}\n"

    engine = TDXParsingEngine()
    results = engine._parse_kline_text_format_a(csv_text, "1d")

    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    parsed_code = results[0].sector_code

    # 所有输出的 sector_code 必须以 .TDX 结尾
    assert parsed_code.endswith(".TDX"), (
        f"sector_code should end with '.TDX', got {parsed_code!r}"
    )


@settings(max_examples=100)
@given(
    sector_code=_sector_code_with_optional_suffix_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    trade_date=_trade_date_st,
)
def test_tdx_format_a_no_double_suffix(
    sector_code, ohlc, volume, amount, trade_date
):
    """
    # Feature: sector-data-import, Property 14: TDX sector_code suffix invariant

    **Validates: Requirements 18.1, 18.2, 18.6**

    For any sector_code that already ends with '.TDX', parsing SHALL NOT produce
    a double suffix '.TDX.TDX'. The suffix append operation is idempotent.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
    row = f"{date_str},{sector_code},测试板块,{open_},{close},{high},{low},{volume},{amount},0,0"
    csv_text = f"{header}\n{row}\n"

    engine = TDXParsingEngine()
    results = engine._parse_kline_text_format_a(csv_text, "1d")

    assert len(results) == 1
    parsed_code = results[0].sector_code

    # 幂等性：不应出现 .TDX.TDX 双后缀
    assert ".TDX.TDX" not in parsed_code, (
        f"Double suffix detected: {parsed_code!r} (input: {sector_code!r})"
    )


# ---------------------------------------------------------------------------
# Property 15: DC simple format parsing with BK validation
# Feature: sector-data-import, Property 15: DC simple format parsing with BK validation
# ---------------------------------------------------------------------------

import tempfile
from pathlib import Path

from app.services.data_engine.sector_csv_parser import DCParsingEngine


# --- Hypothesis strategies for DC simple format ---

# 生成 BK 开头的板块代码（如 BK0001, BK1234）
_bk_code_st = st.from_regex(r"BK[0-9]{4}", fullmatch=True)

# 生成非 BK 开头的字符串（模拟日期、价格等垃圾数据）
_non_bk_code_st = st.one_of(
    # 日期格式（如 2024-01-15）
    st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]", fullmatch=True),
    # 纯数字（如 12345）
    st.from_regex(r"[0-9]{3,6}", fullmatch=True),
    # 字母开头但非 BK（如 SH600000）
    st.from_regex(r"SH[0-9]{6}", fullmatch=True),
)

# 板块名称（不含逗号、换行、引号，非空）
_simple_name_st = st.text(
    min_size=1,
    max_size=15,
).filter(
    lambda s: "," not in s
    and "\n" not in s
    and "\r" not in s
    and '"' not in s
    and s.strip() == s
)


@settings(max_examples=100)
@given(
    bk_codes=st.lists(_bk_code_st, min_size=1, max_size=10, unique=True),
    non_bk_codes=st.lists(_non_bk_code_st, min_size=0, max_size=10),
    names=st.lists(_simple_name_st, min_size=20, max_size=20),
)
def test_dc_simple_format_bk_validation(bk_codes, non_bk_codes, names):
    """
    # Feature: sector-data-import, Property 15: DC simple format parsing with BK validation

    **Validates: Requirements 19.1, 19.2, 19.5**

    For any 2-column CSV with header "名称,代码" containing a mix of BK-prefixed
    and non-BK-prefixed sector_codes:
    - All output sector_codes SHALL start with 'BK' and end with '.DC'
    - Non-BK-prefixed rows SHALL be excluded from the output
    - The number of output records SHALL equal the number of unique BK-prefixed input rows
    """
    # 构造混合行：BK 开头的有效行 + 非 BK 开头的垃圾行
    rows: list[tuple[str, str]] = []
    name_idx = 0

    for code in bk_codes:
        rows.append((names[name_idx % len(names)], code))
        name_idx += 1

    for code in non_bk_codes:
        rows.append((names[name_idx % len(names)], code))
        name_idx += 1

    # 打乱行顺序
    import random
    rng = random.Random(42)
    rng.shuffle(rows)

    # 构造 CSV 内容（简版格式：名称,代码）
    lines = ["名称,代码"]
    for name, code in rows:
        lines.append(f"{name},{code}")
    csv_content = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "东方财富_板块列表1.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        engine = DCParsingEngine()
        results = engine.parse_sector_list(csv_file)

    # 属性 1：所有输出的 sector_code 以 BK 开头
    for r in results:
        assert r.sector_code.startswith("BK"), (
            f"sector_code should start with 'BK', got {r.sector_code!r}"
        )

    # 属性 2：所有输出的 sector_code 以 .DC 结尾
    for r in results:
        assert r.sector_code.endswith(".DC"), (
            f"sector_code should end with '.DC', got {r.sector_code!r}"
        )

    # 属性 3：非 BK 开头的行被排除 — 输出数量等于唯一 BK 代码数量
    # 注意：BK 代码可能带或不带 .DC 后缀，去重后比较
    expected_count = len(set(bk_codes))
    assert len(results) == expected_count, (
        f"Expected {expected_count} results (unique BK codes), got {len(results)}. "
        f"BK codes: {bk_codes}, non-BK codes: {non_bk_codes}"
    )

    # 属性 4：输出中不包含任何非 BK 开头的原始代码
    output_codes = {r.sector_code for r in results}
    for code in non_bk_codes:
        # 非 BK 代码不应出现在输出中（无论是否带 .DC 后缀）
        assert code not in output_codes, (
            f"Non-BK code {code!r} should not appear in output"
        )
        assert code + ".DC" not in output_codes, (
            f"Non-BK code {code + '.DC'!r} should not appear in output"
        )


@settings(max_examples=100)
@given(
    bk_code=_bk_code_st,
    name=_simple_name_st,
)
def test_dc_simple_format_sector_code_dc_suffix_idempotent(bk_code, name):
    """
    # Feature: sector-data-import, Property 15: DC simple format parsing with BK validation

    **Validates: Requirements 19.1, 19.2, 19.5**

    For any BK-prefixed sector_code (with or without .DC suffix), parsing a
    simple format CSV SHALL produce a sector_code ending with '.DC' exactly
    once (no double suffix '.DC.DC').
    """
    # 测试两种输入：不带后缀和带后缀
    for input_code in [bk_code, bk_code + ".DC"]:
        csv_content = f"名称,代码\n{name},{input_code}\n"

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file = Path(tmp_dir) / "东方财富_板块列表.csv"
            csv_file.write_text(csv_content, encoding="utf-8")

            engine = DCParsingEngine()
            results = engine.parse_sector_list(csv_file)

        assert len(results) == 1, (
            f"Expected 1 result for input_code={input_code!r}, got {len(results)}"
        )
        parsed_code = results[0].sector_code

        # 必须以 .DC 结尾
        assert parsed_code.endswith(".DC"), (
            f"sector_code should end with '.DC', got {parsed_code!r}"
        )

        # 不应出现双后缀
        assert ".DC.DC" not in parsed_code, (
            f"Double suffix detected: {parsed_code!r} (input: {input_code!r})"
        )


# ---------------------------------------------------------------------------
# Hypothesis strategies for DC kline suffix tests
# ---------------------------------------------------------------------------

# 生成带或不带 .DC 后缀的 sector_code
_sector_code_with_optional_dc_suffix_st = _base_code_st.flatmap(
    lambda code: st.sampled_from([code, code + ".DC"])
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


# ---------------------------------------------------------------------------
# Property 16: DC sector_code kline suffix invariant
# Feature: sector-data-import, Property 16: DC sector_code kline suffix invariant
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    sector_code=_sector_code_with_optional_dc_suffix_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    change_pct=_change_pct_st,
    turnover=_turnover_st,
    trade_date=_trade_date_st,
)
def test_dc_format_a_sector_code_ends_with_dc(
    sector_code, ohlc, volume, amount, change_pct, turnover, trade_date
):
    """
    # Feature: sector-data-import, Property 16: DC sector_code kline suffix invariant

    **Validates: Requirements 20.1, 20.2, 20.6**

    For any sector_code (with or without .DC suffix), constructing a Format A
    CSV text (板块代码,交易日期,收盘点位,开盘点位,...) and parsing it with
    _parse_kline_text SHALL produce output where every sector_code ends with '.DC'.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    # 格式 A：板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%
    header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%"
    row = f"{sector_code},{date_str},{close},{open_},{high},{low},0,{change_pct},{volume},{amount},0,{turnover}"
    csv_text = f"{header}\n{row}\n"

    engine = DCParsingEngine()
    results = engine._parse_kline_text(csv_text)

    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    parsed_code = results[0].sector_code

    # 所有输出的 sector_code 必须以 .DC 结尾
    assert parsed_code.endswith(".DC"), (
        f"sector_code should end with '.DC', got {parsed_code!r}"
    )

    # 幂等性：不应出现 .DC.DC 双后缀
    assert ".DC.DC" not in parsed_code, (
        f"Double suffix detected: {parsed_code!r} (input: {sector_code!r})"
    )


@settings(max_examples=100)
@given(
    sector_code=_sector_code_with_optional_dc_suffix_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    change_pct=_change_pct_st,
    turnover=_turnover_st,
    trade_date=_trade_date_st,
)
def test_dc_format_b_sector_code_ends_with_dc(
    sector_code, ohlc, volume, amount, change_pct, turnover, trade_date
):
    """
    # Feature: sector-data-import, Property 16: DC sector_code kline suffix invariant

    **Validates: Requirements 20.1, 20.2, 20.6**

    For any sector_code (with or without .DC suffix), constructing a Format B
    CSV text (日期,行业代码,开盘,收盘,...) and parsing it with _parse_kline_text
    SHALL produce output where every sector_code ends with '.DC'.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    # 格式 B：日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
    header = "日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
    row = f"{date_str},{sector_code},{open_},{close},{high},{low},{volume},{amount},0,{change_pct},0,{turnover}"
    csv_text = f"{header}\n{row}\n"

    engine = DCParsingEngine()
    results = engine._parse_kline_text(csv_text)

    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    parsed_code = results[0].sector_code

    # 所有输出的 sector_code 必须以 .DC 结尾
    assert parsed_code.endswith(".DC"), (
        f"sector_code should end with '.DC', got {parsed_code!r}"
    )

    # 幂等性：不应出现 .DC.DC 双后缀
    assert ".DC.DC" not in parsed_code, (
        f"Double suffix detected: {parsed_code!r} (input: {sector_code!r})"
    )


@settings(max_examples=100)
@given(
    sector_code=_sector_code_with_optional_dc_suffix_st,
    ohlc=_valid_ohlc_st(),
    volume=_volume_st,
    amount=_amount_st,
    change_pct=_change_pct_st,
    turnover=_turnover_st,
    trade_date=_trade_date_st,
)
def test_dc_both_formats_produce_consistent_suffix(
    sector_code, ohlc, volume, amount, change_pct, turnover, trade_date
):
    """
    # Feature: sector-data-import, Property 16: DC sector_code kline suffix invariant

    **Validates: Requirements 20.1, 20.2, 20.6**

    For any sector_code (with or without .DC suffix), parsing via Format A and
    Format B SHALL produce the same sector_code output. Both formats apply the
    same suffix normalization logic.
    """
    low, high, open_, close = ohlc
    date_str = trade_date.strftime("%Y-%m-%d")

    # 格式 A
    header_a = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%"
    row_a = f"{sector_code},{date_str},{close},{open_},{high},{low},0,{change_pct},{volume},{amount},0,{turnover}"
    csv_text_a = f"{header_a}\n{row_a}\n"

    # 格式 B
    header_b = "日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
    row_b = f"{date_str},{sector_code},{open_},{close},{high},{low},{volume},{amount},0,{change_pct},0,{turnover}"
    csv_text_b = f"{header_b}\n{row_b}\n"

    engine = DCParsingEngine()
    results_a = engine._parse_kline_text(csv_text_a)
    results_b = engine._parse_kline_text(csv_text_b)

    assert len(results_a) == 1 and len(results_b) == 1
    code_a = results_a[0].sector_code
    code_b = results_b[0].sector_code

    # 两种格式输出的 sector_code 应一致
    assert code_a == code_b, (
        f"Format A and B produced different sector_codes: "
        f"A={code_a!r}, B={code_b!r} (input: {sector_code!r})"
    )
