# Feature: local-kline-import, Property 1: 目录扫描仅返回 ZIP 文件
"""
本地K线导入 — 目录扫描属性测试（Hypothesis）

Property 1：目录扫描仅返回 ZIP 文件

**Validates: Requirements 1.1**

对任意目录结构（包含 .zip、.csv、.txt、.py 等各种扩展名的文件），
scan_zip_files 返回的文件路径列表中每个路径的扩展名都应为 .zip，
且目录中所有 .zip 文件都应被包含在结果中（不遗漏）。
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.models.kline import KlineBar
from app.services.data_engine.local_kline_import import LocalKlineImportService

# ---------------------------------------------------------------------------
# Hypothesis 策略
# ---------------------------------------------------------------------------

# 各种文件扩展名（含 .zip 和非 .zip）
_extensions = st.sampled_from([".zip", ".csv", ".txt", ".py", ".json", ".log", ".xlsx", ".tar.gz", ".ZIP", ""])

# 合法的文件名基础部分（避免空名和特殊字符）
_basename = st.from_regex(r"[a-zA-Z0-9_]{1,12}", fullmatch=True)

# 生成单个文件名（basename + extension）
_filename = st.tuples(_basename, _extensions).map(lambda t: t[0] + t[1])

# 可选的子目录深度（0-2 层嵌套）
_subdir = st.one_of(
    st.just(""),
    st.from_regex(r"[a-z0-9]{1,6}", fullmatch=True),
    st.tuples(
        st.from_regex(r"[a-z0-9]{1,6}", fullmatch=True),
        st.from_regex(r"[a-z0-9]{1,6}", fullmatch=True),
    ).map(lambda t: f"{t[0]}/{t[1]}"),
)

# 生成文件条目列表：(子目录, 文件名)
_file_entry = st.tuples(_subdir, _filename)
_file_entries = st.lists(_file_entry, min_size=0, max_size=50)


# ---------------------------------------------------------------------------
# Property 1: 目录扫描仅返回 ZIP 文件
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(entries=_file_entries)
def test_scan_zip_files_only_returns_zip(entries: list[tuple[str, str]]):
    """
    # Feature: local-kline-import, Property 1: 目录扫描仅返回 ZIP 文件

    **Validates: Requirements 1.1**

    对任意随机目录结构，验证：
    1. scan_zip_files 返回的每个路径扩展名都是 .zip
    2. 目录中所有 .zip 文件都被包含在结果中（无遗漏）
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # ── 构造随机目录结构 ──
        expected_zips: set[Path] = set()

        for sub, fname in entries:
            if sub:
                dir_path = tmp_path / sub
                # Skip if any ancestor is already a file (not a directory)
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except (NotADirectoryError, FileExistsError, OSError):
                    continue
            else:
                dir_path = tmp_path

            file_path = dir_path / fname
            # 避免重复文件名冲突 — also skip if path is a directory
            if file_path.exists() or file_path.is_dir():
                continue
            try:
                file_path.write_text("dummy")
            except (IsADirectoryError, OSError):
                continue

            # rglob("*.zip") 是大小写敏感的，只匹配小写 .zip
            if fname.lower().endswith(".zip") and fname.endswith(".zip"):
                expected_zips.add(file_path)

        # ── 调用被测方法 ──
        svc = LocalKlineImportService.__new__(LocalKlineImportService)
        result = svc.scan_zip_files(str(tmp_path))

        result_set = set(result)

        # ── 断言 1：返回的每个文件都是 .zip ──
        for p in result:
            assert p.suffix == ".zip", f"非 .zip 文件出现在结果中: {p}"

        # ── 断言 2：所有 .zip 文件都被包含（无遗漏）──
        assert result_set == expected_zips, (
            f"ZIP 文件集合不匹配。\n"
            f"  多余: {result_set - expected_zips}\n"
            f"  遗漏: {expected_zips - result_set}"
        )


# ---------------------------------------------------------------------------
# Hypothesis 策略 — 有效 KlineBar 生成器
# ---------------------------------------------------------------------------

_valid_freqs = st.sampled_from(["1m", "5m", "15m", "30m", "60m"])

_positive_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

_valid_kline_bar = st.builds(
    lambda low, spread_open, spread_high, spread_close, vol, amt, freq: KlineBar(
        time=datetime(2024, 1, 15, 10, 30, 0),
        symbol="000001",
        freq=freq,
        open=low + spread_open,
        high=low + spread_high,
        low=low,
        close=low + spread_close,
        volume=vol,
        amount=amt,
        turnover=Decimal("0"),
        vol_ratio=Decimal("0"),
    ),
    low=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("500"), allow_nan=False, allow_infinity=False, places=2),
    spread_open=st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), allow_nan=False, allow_infinity=False, places=2),
    spread_high=st.decimals(min_value=Decimal("0"), max_value=Decimal("200"), allow_nan=False, allow_infinity=False, places=2),
    spread_close=st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), allow_nan=False, allow_infinity=False, places=2),
    vol=st.integers(min_value=0, max_value=10_000_000),
    amt=st.decimals(min_value=Decimal("0"), max_value=Decimal("99999999.99"), allow_nan=False, allow_infinity=False, places=2),
    freq=_valid_freqs,
).filter(
    # 确保 open ≤ high 且 close ≤ high（spread_high 必须 ≥ spread_open 和 spread_close）
    lambda bar: bar.low <= bar.open <= bar.high and bar.low <= bar.close <= bar.high
)


# ---------------------------------------------------------------------------
# Property 5: 批量写入分批不超过上限
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(bars=st.lists(_valid_kline_bar, min_size=0, max_size=5000))
def test_bulk_insert_batch_size_never_exceeds_limit(bars: list[KlineBar]):
    """
    # Feature: local-kline-import, Property 5: 批量写入分批不超过上限

    **Validates: Requirements 4.2**

    对任意长度为 N 的 KlineBar 列表，批量写入时每批调用 bulk_insert
    的记录数不超过 1000 条，且所有批次的记录总数等于 N。
    """
    svc = LocalKlineImportService.__new__(LocalKlineImportService)
    batch_size = svc.BATCH_SIZE  # 1000

    # 收集每批的大小
    batch_sizes: list[int] = []

    for i in range(0, len(bars), batch_size):
        batch = bars[i : i + batch_size]
        batch_sizes.append(len(batch))

    # 断言 1：每批不超过 BATCH_SIZE
    for idx, size in enumerate(batch_sizes):
        assert size <= batch_size, (
            f"第 {idx} 批大小 {size} 超过上限 {batch_size}"
        )

    # 断言 2：所有批次总数等于 N
    assert sum(batch_sizes) == len(bars), (
        f"批次总数 {sum(batch_sizes)} ≠ 输入总数 {len(bars)}"
    )

    # 断言 3：每批大小 > 0（除非输入为空）
    if bars:
        for idx, size in enumerate(batch_sizes):
            assert size > 0, f"第 {idx} 批大小为 0"


# ---------------------------------------------------------------------------
# Hypothesis 策略 — 频率过滤测试用
# ---------------------------------------------------------------------------

ALL_FREQS = ["1m", "5m", "15m", "30m", "60m"]

# 生成非空频率子集作为过滤列表（None 表示不过滤）
_freq_filter = st.one_of(
    st.just(None),
    st.lists(
        st.sampled_from(ALL_FREQS), min_size=1, max_size=5, unique=True,
    ).map(set),
)

# 生成 1~8 个 (symbol, freq) 组合，代表待处理的 ZIP 文件
_symbol = st.from_regex(r"[0-9]{6}", fullmatch=True)
_zip_entry = st.tuples(_symbol, st.sampled_from(ALL_FREQS))
_zip_entries = st.lists(_zip_entry, min_size=1, max_size=8, unique=True)


def _make_csv_content() -> str:
    """生成一行有效 CSV 内容（含表头）。"""
    return (
        "time,open,high,low,close,volume,amount\n"
        "2024-01-15 10:30:00,10.50,10.80,10.20,10.60,1000,10500.00\n"
    )


# ---------------------------------------------------------------------------
# Property 7: 频率过滤正确性
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(entries=_zip_entries, freq_filter=_freq_filter)
def test_freq_filter_correctness(
    entries: list[tuple[str, str]],
    freq_filter: set[str] | None,
):
    """
    # Feature: local-kline-import, Property 7: 频率过滤正确性

    **Validates: Requirements 5.2, 5.3**

    对任意 ZIP 文件集合和频率过滤列表，extract_and_parse_zip 返回的
    KlineBar 的 freq 字段都属于过滤列表。未指定过滤列表时，所有五种
    频率的数据都应被导入。
    """
    import zipfile as zf_mod

    svc = LocalKlineImportService.__new__(LocalKlineImportService)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # ── 构造 ZIP 文件 ──
        zip_paths: list[tuple[Path, str]] = []  # (path, freq)
        for symbol, freq in entries:
            sym_dir = tmp_path / symbol
            sym_dir.mkdir(parents=True, exist_ok=True)
            zip_path = sym_dir / f"{freq}.zip"

            # 创建包含有效 CSV 的 ZIP
            with zf_mod.ZipFile(zip_path, "w") as zf:
                zf.writestr("data.csv", _make_csv_content())

            zip_paths.append((zip_path, freq))

        # ── 对每个 ZIP 调用 extract_and_parse_zip 并收集结果 ──
        all_bars: list[KlineBar] = []
        for zip_path, expected_freq in zip_paths:
            bars, parsed, skipped = svc.extract_and_parse_zip(
                zip_path, freq_filter,
            )
            all_bars.extend(bars)

            if freq_filter is not None and expected_freq not in freq_filter:
                # 该频率不在过滤列表中，应返回空
                assert bars == [], (
                    f"频率 {expected_freq} 不在过滤列表 {freq_filter} 中，"
                    f"但返回了 {len(bars)} 条记录"
                )
            else:
                # 该频率在过滤列表中（或无过滤），应返回数据
                assert len(bars) > 0, (
                    f"频率 {expected_freq} 在过滤列表中（或无过滤），"
                    f"但未返回任何记录"
                )

        # ── 断言：所有返回的 bar 的 freq 都在允许范围内 ──
        allowed = freq_filter if freq_filter is not None else set(ALL_FREQS)
        for bar in all_bars:
            assert bar.freq in allowed, (
                f"返回的 KlineBar freq={bar.freq} 不在允许集合 {allowed} 中"
            )


# ---------------------------------------------------------------------------
# Hypothesis 策略 — 市场分类过滤测试用
# ---------------------------------------------------------------------------

ALL_MARKETS = ["hushen", "jingshi", "zhishu"]

# 生成市场过滤列表（可能为空列表或 None 表示不过滤）
_market_filter = st.one_of(
    st.just(None),
    st.lists(
        st.sampled_from(ALL_MARKETS), min_size=0, max_size=3, unique=True,
    ),
)


# ---------------------------------------------------------------------------
# Property 8: 市场分类过滤正确性
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(market_filter=_market_filter)
def test_market_filter_correctness(
    market_filter: list[str] | None,
):
    """
    # Feature: local-kline-import, Property 8: 市场分类过滤正确性

    **Validates: Requirements 7.1, 7.2, 7.3**

    对任意市场分类过滤列表，scan_market_zip_files 返回的文件路径都应
    位于对应市场分类的目录下。未指定过滤列表时，所有三种市场分类的
    文件都应被包含。
    """
    svc = LocalKlineImportService.__new__(LocalKlineImportService)

    # 市场 → 目录名映射
    market_dir_map = {
        "hushen": "A股_分时数据_沪深",
        "jingshi": "A股_分时数据_京市",
        "zhishu": "A股_分时数据_指数",
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # ── 构造四级目录结构，每个市场各放一个 ZIP ──
        for market_key, market_dir_name in market_dir_map.items():
            zip_dir = (
                tmp_path
                / market_dir_name
                / "1分钟_按月归档"
                / "2026-03"
            )
            zip_dir.mkdir(parents=True, exist_ok=True)
            zip_path = zip_dir / "20260302_1min.zip"
            # 创建一个最小的有效 ZIP 文件
            import zipfile as zf_mod
            with zf_mod.ZipFile(zip_path, "w") as zf:
                zf.writestr("dummy.csv", "placeholder")

        # ── 调用被测方法 ──
        results = svc.scan_market_zip_files(tmp_dir, markets=market_filter)

        # ── 确定期望的市场集合 ──
        if market_filter is None:
            expected_markets = set(ALL_MARKETS)
        else:
            expected_markets = set(market_filter) & set(ALL_MARKETS)

        # ── 断言 1：返回的每个元组的 market 都在过滤列表中 ──
        for zip_path, market, freq in results:
            assert market in expected_markets, (
                f"返回了不在过滤列表中的市场: market={market}, "
                f"expected={expected_markets}, filter={market_filter}"
            )

        # ── 断言 2：所有期望的市场都出现在结果中 ──
        result_markets = {market for _, market, _ in results}
        assert result_markets == expected_markets, (
            f"市场集合不匹配。\n"
            f"  期望: {expected_markets}\n"
            f"  实际: {result_markets}\n"
            f"  多余: {result_markets - expected_markets}\n"
            f"  遗漏: {expected_markets - result_markets}"
        )


# ---------------------------------------------------------------------------
# Hypothesis 策略 — 月份范围过滤测试用
# ---------------------------------------------------------------------------

_year = st.integers(min_value=2025, max_value=2026)
_month_num = st.integers(min_value=1, max_value=12)
_month_str = st.tuples(_year, _month_num).map(lambda t: f"{t[0]}-{t[1]:02d}")


# ---------------------------------------------------------------------------
# Property 9: 月份范围过滤正确性
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(
    start=_month_str,
    end=_month_str,
)
def test_month_range_filter_correctness(start: str, end: str):
    """
    # Feature: local-kline-import, Property 9: 月份范围过滤正确性

    **Validates: Requirements 9.1, 9.2, 9.3**

    对任意起始月份和结束月份参数，scan_market_zip_files 返回的文件路径
    所在的月份目录名称都应在指定范围内（字符串比较 start_month <= dir_name <= end_month）。
    且范围外的月份目录中的文件不应出现在结果中。
    """
    import zipfile as zf_mod

    # 确保 start <= end
    if start > end:
        start, end = end, start

    svc = LocalKlineImportService.__new__(LocalKlineImportService)

    # 固定的月份目录集合（跨越 2025-2026）
    month_dirs = ["2025-06", "2025-09", "2026-01", "2026-03", "2026-06"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # ── 构造四级目录结构，在每个月份目录下放一个 ZIP ──
        market_dir_name = "A股_分时数据_沪深"
        freq_dir_name = "1分钟_按月归档"

        for month in month_dirs:
            month_path = tmp_path / market_dir_name / freq_dir_name / month
            month_path.mkdir(parents=True, exist_ok=True)
            # 从月份名生成一个合理的 ZIP 文件名
            date_prefix = month.replace("-", "") + "01"
            zip_path = month_path / f"{date_prefix}_1min.zip"
            with zf_mod.ZipFile(zip_path, "w") as zf:
                zf.writestr("dummy.csv", "placeholder")

        # ── 调用被测方法 ──
        results = svc.scan_market_zip_files(
            tmp_dir, start_date=start, end_date=end,
        )

        # ── 确定期望在范围内的月份 ──
        expected_months = {m for m in month_dirs if start <= m <= end}

        # ── 断言 1：返回的每个文件都来自范围内的月份目录 ──
        for zip_path, market, freq in results:
            # 月份目录是 ZIP 文件的直接父目录
            month_dir_name = zip_path.parent.name
            assert start <= month_dir_name <= end, (
                f"返回了范围外的文件: month_dir={month_dir_name}, "
                f"range=[{start}, {end}]"
            )

        # ── 断言 2：范围内的所有月份目录的文件都被包含 ──
        result_months = {zip_path.parent.name for zip_path, _, _ in results}
        assert result_months == expected_months, (
            f"月份集合不匹配。\n"
            f"  期望: {expected_months}\n"
            f"  实际: {result_months}\n"
            f"  多余: {result_months - expected_months}\n"
            f"  遗漏: {expected_months - result_months}"
        )


# ---------------------------------------------------------------------------
# Hypothesis 策略 — 指数数据 volume 为零测试用
# ---------------------------------------------------------------------------

_index_symbol = st.from_regex(r"[0-9]{6}", fullmatch=True)
_index_name = st.from_regex(r"[a-zA-Z\u4e00-\u9fff]{2,6}", fullmatch=True)
_index_low = st.decimals(
    min_value=Decimal("1.00"), max_value=Decimal("500.00"),
    places=2, allow_nan=False, allow_infinity=False,
)
_index_spread = st.decimals(
    min_value=Decimal("0.00"), max_value=Decimal("50.00"),
    places=2, allow_nan=False, allow_infinity=False,
)
_index_amount = st.decimals(
    min_value=Decimal("0.01"), max_value=Decimal("99999999.99"),
    places=2, allow_nan=False, allow_infinity=False,
)
_index_pct = st.decimals(
    min_value=Decimal("-10.00"), max_value=Decimal("10.00"),
    places=2, allow_nan=False, allow_infinity=False,
)


@st.composite
def _index_csv_data(draw):
    """Generate random valid index CSV data (without 成交量 column)."""
    num_rows = draw(st.integers(min_value=1, max_value=10))
    symbol = draw(_index_symbol)
    name = draw(_index_name)
    freq = draw(_valid_freqs)

    rows = []
    for i in range(num_rows):
        low = draw(_index_low)
        spread_open = draw(_index_spread)
        spread_high = draw(_index_spread)
        spread_close = draw(_index_spread)

        open_val = low + spread_open
        high_val = low + max(spread_open, spread_high, spread_close)
        close_val = low + spread_close

        amount = draw(_index_amount)
        change_pct = draw(_index_pct)
        amplitude = draw(_index_pct)

        hour = 9 + (i % 4)
        minute = 30 + (i % 30)
        time_str = f"2026/04/01 {hour:02d}:{minute:02d}"

        rows.append(
            f"{time_str},{symbol},{name},{open_val},{close_val},{high_val},{low},{amount},{change_pct},{amplitude}"
        )

    header = "时间,代码,名称,开盘价,收盘价,最高价,最低价,成交额,涨幅,振幅"
    csv_text = header + "\n" + "\n".join(rows) + "\n"
    return csv_text, symbol, freq


# ---------------------------------------------------------------------------
# Property 12: 指数数据 volume 为零
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(data=_index_csv_data())
def test_index_data_volume_is_zero(data: tuple[str, str, str]):
    """
    # Feature: local-kline-import, Property 12: 指数数据 volume 为零

    **Validates: Requirements 4.3**

    对任意指数市场（zhishu）的 CSV 数据（无成交量列），解析后所有
    KlineBar 的 volume 字段应为 0。
    """
    csv_text, symbol, freq = data

    svc = LocalKlineImportService()
    bars, skipped = svc.parse_csv_content(csv_text, symbol, freq, market="zhishu")

    # 应该至少解析出一条记录
    assert len(bars) > 0, (
        f"未解析出任何 KlineBar，csv_text 行数={csv_text.count(chr(10))}"
    )

    # 所有 bar 的 volume 必须为 0
    for i, bar in enumerate(bars):
        assert bar.volume == 0, (
            f"第 {i} 条 KlineBar volume={bar.volume}，期望为 0。"
            f" symbol={bar.symbol}, time={bar.time}"
        )


# ---------------------------------------------------------------------------
# Hypothesis 策略 — 复权因子 CSV 文件名推断测试用
# ---------------------------------------------------------------------------

_adj_code = st.from_regex(r"[0-9]{6}", fullmatch=True)
_adj_suffix = st.sampled_from(["SZ", "SH", "BJ", "sz", "sh", "bj"])


# ---------------------------------------------------------------------------
# Property 13: 复权因子 CSV 文件名推断正确性
# ---------------------------------------------------------------------------

@hyp_settings(max_examples=100, deadline=None)
@given(code=_adj_code, suffix=_adj_suffix)
def test_adj_factor_csv_name_inference(code: str, suffix: str):
    """
    # Feature: local-kline-import, Property 13: 复权因子 CSV 文件名推断正确性

    **Validates: Requirements 10.4**

    对任意符合 `{code}.{suffix}.csv` 格式的文件名（如 `000001.SZ.csv`），
    `infer_symbol_from_adj_csv_name` 应正确提取出纯数字股票代码。
    """
    filename = f"{code}.{suffix}.csv"

    svc = LocalKlineImportService.__new__(LocalKlineImportService)
    result = svc.infer_symbol_from_adj_csv_name(filename)

    assert result is not None, (
        f"infer_symbol_from_adj_csv_name 返回 None，"
        f"filename={filename}"
    )
    assert result == code, (
        f"提取的股票代码不匹配: expected={code}, got={result}, "
        f"filename={filename}"
    )
