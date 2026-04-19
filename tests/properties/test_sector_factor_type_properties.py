"""
板块因子类型不变量 属性测试（Hypothesis）

Property 1: 板块因子类型不变量
对应需求 3.1、3.2

验证 SectorStrengthFilter.filter_by_sector_strength() 执行完毕后，
每只股票的 factor_dict 中 sector_rank 为 int 或 None 类型，
sector_trend 为 bool 类型。
"""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.screener.sector_strength import (
    SectorRankResult,
    SectorStrengthFilter,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# 股票代码策略：6 位数字字符串
_symbol_st = st.from_regex(r"[036]\d{5}", fullmatch=True)

# 板块代码策略
_sector_code_st = st.text(
    alphabet=string.ascii_uppercase + string.digits,
    min_size=2,
    max_size=10,
)

# 板块名称策略
_sector_name_st = st.text(
    alphabet=string.ascii_letters + string.digits + "板块行业概念",
    min_size=1,
    max_size=20,
)

# 板块排名策略
_rank_st = st.integers(min_value=1, max_value=500)

# 涨跌幅策略
_change_pct_st = st.floats(
    min_value=-50.0,
    max_value=50.0,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def sector_rank_result_strategy(draw):
    """生成随机的 SectorRankResult 实例。"""
    return SectorRankResult(
        sector_code=draw(_sector_code_st),
        sector_name=draw(_sector_name_st),
        rank=draw(_rank_st),
        change_pct=draw(_change_pct_st),
        is_bullish=draw(st.booleans()),
    )


@st.composite
def stocks_data_strategy(draw):
    """
    生成随机的 stocks_data 字典。

    结构：{symbol: factor_dict}，factor_dict 中包含选股所需的基本因子。
    不预设 sector_rank / sector_trend，由 filter_by_sector_strength() 写入。
    """
    n_stocks = draw(st.integers(min_value=0, max_value=20))
    symbols = draw(
        st.lists(
            _symbol_st,
            min_size=n_stocks,
            max_size=n_stocks,
            unique=True,
        )
    )
    stocks_data: dict[str, dict] = {}
    for sym in symbols:
        stocks_data[sym] = {
            "close": draw(st.floats(min_value=1.0, max_value=500.0,
                                    allow_nan=False, allow_infinity=False)),
            "ma_trend": draw(st.floats(min_value=0.0, max_value=100.0,
                                       allow_nan=False, allow_infinity=False)),
        }
    return stocks_data


@st.composite
def stock_sector_map_strategy(draw, symbols: list[str], sector_codes: list[str]):
    """
    生成随机的 symbol → [sector_code] 映射。

    部分股票可能不属于任何板块（空列表），部分股票可能属于多个板块。
    """
    mapping: dict[str, list[str]] = {}
    for sym in symbols:
        if not sector_codes:
            mapping[sym] = []
            continue
        # 随机决定该股票属于 0~3 个板块
        n_sectors = draw(st.integers(min_value=0, max_value=min(3, len(sector_codes))))
        if n_sectors == 0:
            mapping[sym] = []
        else:
            chosen = draw(
                st.lists(
                    st.sampled_from(sector_codes),
                    min_size=n_sectors,
                    max_size=n_sectors,
                    unique=True,
                )
            )
            mapping[sym] = chosen
    return mapping


# ---------------------------------------------------------------------------
# Property 1: 板块因子类型不变量
# Feature: screening-system-enhancement, Property 1: 板块因子类型不变量
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    stocks_data=stocks_data_strategy(),
    sector_ranks=st.lists(
        sector_rank_result_strategy(),
        min_size=0,
        max_size=15,
    ),
)
def test_sector_factor_type_invariant(stocks_data, sector_ranks):
    """
    # Feature: screening-system-enhancement, Property 1: 板块因子类型不变量

    **Validates: Requirements 3.1, 3.2**

    For any stocks_data 字典和 sector_ranks 列表，在
    filter_by_sector_strength() 执行完毕后，每只股票的 factor_dict 中
    sector_rank 应为 int 或 None 类型，sector_trend 应为 bool 类型。
    """
    # 去重 sector_ranks（按 sector_code 保留第一个）
    seen_codes: set[str] = set()
    unique_ranks: list[SectorRankResult] = []
    for r in sector_ranks:
        if r.sector_code not in seen_codes:
            seen_codes.add(r.sector_code)
            unique_ranks.append(r)

    sector_codes = [r.sector_code for r in unique_ranks]
    symbols = list(stocks_data.keys())

    # 构建 stock_sector_map：随机分配板块
    # 为简化，直接构建确定性映射
    stock_sector_map: dict[str, list[str]] = {}
    for i, sym in enumerate(symbols):
        if not sector_codes:
            stock_sector_map[sym] = []
        else:
            # 轮询分配板块，确保覆盖有板块和无板块的情况
            if i % 3 == 0:
                # 无板块
                stock_sector_map[sym] = []
            elif i % 3 == 1:
                # 单板块
                stock_sector_map[sym] = [sector_codes[i % len(sector_codes)]]
            else:
                # 多板块
                stock_sector_map[sym] = sector_codes[:min(2, len(sector_codes))]

    ssf = SectorStrengthFilter()
    ssf.filter_by_sector_strength(
        stocks_data=stocks_data,
        sector_ranks=unique_ranks,
        stock_sector_map=stock_sector_map,
    )

    # 验证类型不变量
    for sym, factor_dict in stocks_data.items():
        # sector_rank 必须存在且为 int 或 None
        assert "sector_rank" in factor_dict, (
            f"股票 {sym} 的 factor_dict 中缺少 sector_rank 字段"
        )
        sr = factor_dict["sector_rank"]
        assert sr is None or isinstance(sr, int), (
            f"股票 {sym} 的 sector_rank 类型错误: "
            f"期望 int|None，实际 {type(sr).__name__}={sr!r}"
        )

        # sector_trend 必须存在且为 bool
        assert "sector_trend" in factor_dict, (
            f"股票 {sym} 的 factor_dict 中缺少 sector_trend 字段"
        )
        st_val = factor_dict["sector_trend"]
        assert isinstance(st_val, bool), (
            f"股票 {sym} 的 sector_trend 类型错误: "
            f"期望 bool，实际 {type(st_val).__name__}={st_val!r}"
        )


@settings(max_examples=200)
@given(stocks_data=stocks_data_strategy())
def test_sector_factor_type_invariant_empty_ranks(stocks_data):
    """
    # Feature: screening-system-enhancement, Property 1: 板块因子类型不变量

    **Validates: Requirements 3.1, 3.2**

    当 sector_ranks 为空列表时（模拟板块数据不可用），
    所有股票的 sector_rank 应为 None，sector_trend 应为 False。
    """
    ssf = SectorStrengthFilter()
    ssf.filter_by_sector_strength(
        stocks_data=stocks_data,
        sector_ranks=[],
        stock_sector_map={sym: ["FAKE_CODE"] for sym in stocks_data},
    )

    for sym, factor_dict in stocks_data.items():
        # sector_rank 应为 None（无板块排名数据）
        assert factor_dict["sector_rank"] is None, (
            f"股票 {sym} 的 sector_rank 应为 None（空排名列表），"
            f"实际 {factor_dict['sector_rank']!r}"
        )
        assert isinstance(factor_dict["sector_rank"], type(None))

        # sector_trend 应为 False
        assert factor_dict["sector_trend"] is False, (
            f"股票 {sym} 的 sector_trend 应为 False（空排名列表），"
            f"实际 {factor_dict['sector_trend']!r}"
        )
        assert isinstance(factor_dict["sector_trend"], bool)


@settings(max_examples=200)
@given(
    stocks_data=stocks_data_strategy(),
    sector_ranks=st.lists(
        sector_rank_result_strategy(),
        min_size=1,
        max_size=10,
    ),
)
def test_sector_factor_type_invariant_no_sector_mapping(stocks_data, sector_ranks):
    """
    # Feature: screening-system-enhancement, Property 1: 板块因子类型不变量

    **Validates: Requirements 3.1, 3.2**

    当所有股票都不属于任何板块时（stock_sector_map 全为空列表），
    所有股票的 sector_rank 应为 None，sector_trend 应为 False。
    """
    # 去重 sector_ranks
    seen: set[str] = set()
    unique: list[SectorRankResult] = []
    for r in sector_ranks:
        if r.sector_code not in seen:
            seen.add(r.sector_code)
            unique.append(r)

    ssf = SectorStrengthFilter()
    ssf.filter_by_sector_strength(
        stocks_data=stocks_data,
        sector_ranks=unique,
        stock_sector_map={sym: [] for sym in stocks_data},
    )

    for sym, factor_dict in stocks_data.items():
        sr = factor_dict["sector_rank"]
        assert sr is None, (
            f"股票 {sym} 无板块映射，sector_rank 应为 None，实际 {sr!r}"
        )

        st_val = factor_dict["sector_trend"]
        assert st_val is False, (
            f"股票 {sym} 无板块映射，sector_trend 应为 False，实际 {st_val!r}"
        )
        assert isinstance(st_val, bool)
