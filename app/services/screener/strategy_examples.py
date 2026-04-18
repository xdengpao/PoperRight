"""
实战选股策略示例库（Strategy Examples Library）

提供：
- StrategyExample: 策略示例数据类
- STRATEGY_EXAMPLES: 12 个可直接加载为 StrategyConfig 的实战选股策略示例

每个示例包含完整的因子条件列表、逻辑运算、权重、启用模块和板块筛选配置，
可通过 GET /api/v1/screen/strategy-examples 端点暴露给前端。

对应需求：
- 需求 14：实战选股策略示例库
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StrategyExample:
    """策略示例"""

    name: str
    description: str
    factors: list[dict]
    logic: str
    weights: dict[str, float]
    enabled_modules: list[str]
    sector_config: dict | None = None


# ---------------------------------------------------------------------------
# STRATEGY_EXAMPLES: 12 个实战选股策略示例
# ---------------------------------------------------------------------------

STRATEGY_EXAMPLES: list[StrategyExample] = [
    # ── 示例 1：强势多头趋势追踪 ──
    StrategyExample(
        name="强势多头趋势追踪",
        description="捕捉处于强势上升趋势中的个股，适合趋势跟踪型交易",
        factors=[
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 85,
                "params": {},
            },
            {
                "factor_name": "ma_support",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "dma",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
        ],
        logic="AND",
        weights={"ma_trend": 0.5, "ma_support": 0.3, "dma": 0.2},
        enabled_modules=["ma_trend"],
    ),
    # ── 示例 2：MACD 金叉放量突破 ──
    StrategyExample(
        name="MACD 金叉放量突破",
        description="MACD 金叉配合成交量放大，确认短期多头启动信号",
        factors=[
            {
                "factor_name": "macd",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "turnover",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 5.0, "threshold_high": 15.0},
            },
            {
                "factor_name": "volume_price",
                "operator": ">=",
                "threshold": 80,
                "params": {},
            },
        ],
        logic="AND",
        weights={"macd": 0.4, "turnover": 0.3, "volume_price": 0.3},
        enabled_modules=["indicator_params", "volume_price"],
    ),
    # ── 示例 3：概念板块热点龙头 ──
    StrategyExample(
        name="概念板块热点龙头",
        description="追踪概念板块轮动热点，筛选强势概念板块中的龙头股",
        factors=[
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 15,
                "params": {},
            },
            {
                "factor_name": "sector_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
        ],
        logic="AND",
        weights={"sector_rank": 0.4, "sector_trend": 0.3, "ma_trend": 0.3},
        enabled_modules=["ma_trend"],
        sector_config={
            "sector_data_source": "DC",
            "sector_type": "CONCEPT",
            "sector_period": 3,
            "sector_top_n": 15,
        },
    ),
    # ── 示例 4：行业板块轮动策略 ──
    StrategyExample(
        name="行业板块轮动策略",
        description="跟踪行业板块轮动节奏，在强势行业中选择技术面共振的个股",
        factors=[
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 20,
                "params": {},
            },
            {
                "factor_name": "sector_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "macd",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "rsi",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 55, "threshold_high": 75},
            },
        ],
        logic="AND",
        weights={"sector_rank": 0.3, "sector_trend": 0.2, "macd": 0.3, "rsi": 0.2},
        enabled_modules=["indicator_params"],
        sector_config={
            "sector_data_source": "TI",
            "sector_type": "INDUSTRY",
            "sector_period": 5,
            "sector_top_n": 20,
        },
    ),
    # ── 示例 5：形态突破放量买入 ──
    StrategyExample(
        name="形态突破放量买入",
        description="捕捉箱体突破或前高突破的个股，要求量价配合确认突破有效性",
        factors=[
            {
                "factor_name": "breakout",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "turnover",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 5.0, "threshold_high": 20.0},
            },
            {
                "factor_name": "large_order",
                "operator": ">=",
                "threshold": 35,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 60,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "breakout": 0.35,
            "turnover": 0.2,
            "large_order": 0.25,
            "ma_trend": 0.2,
        },
        enabled_modules=["breakout", "ma_trend", "volume_price"],
    ),
    # ── 示例 6：技术指标多重共振 ──
    StrategyExample(
        name="技术指标多重共振",
        description="多个技术指标同时发出多头信号，形成共振确认，提高信号可靠性",
        factors=[
            {
                "factor_name": "macd",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "boll",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "rsi",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 50, "threshold_high": 80},
            },
            {
                "factor_name": "dma",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 75,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "macd": 0.25,
            "boll": 0.2,
            "rsi": 0.2,
            "dma": 0.15,
            "ma_trend": 0.2,
        },
        enabled_modules=["indicator_params", "ma_trend"],
    ),
    # ── 示例 7：均线支撑反弹策略 ──
    StrategyExample(
        name="均线支撑反弹策略",
        description="在上升趋势中回调至均线支撑位企稳反弹的买入机会",
        factors=[
            {
                "factor_name": "ma_support",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 65,
                "params": {},
            },
            {
                "factor_name": "rsi",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 40, "threshold_high": 60},
            },
            {
                "factor_name": "turnover",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 3.0, "threshold_high": 10.0},
            },
        ],
        logic="AND",
        weights={
            "ma_support": 0.35,
            "ma_trend": 0.3,
            "rsi": 0.2,
            "turnover": 0.15,
        },
        enabled_modules=["ma_trend", "indicator_params", "volume_price"],
    ),
    # ── 示例 8：板块强势 + 布林突破 ──
    StrategyExample(
        name="板块强势 + 布林突破",
        description="在强势板块中寻找布林带突破的个股，板块动量与个股技术面双重确认",
        factors=[
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 25,
                "params": {},
            },
            {
                "factor_name": "boll",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
            {
                "factor_name": "volume_price",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "sector_rank": 0.3,
            "boll": 0.3,
            "ma_trend": 0.2,
            "volume_price": 0.2,
        },
        enabled_modules=["indicator_params", "ma_trend", "volume_price"],
        sector_config={
            "sector_data_source": "DC",
            "sector_type": "CONCEPT",
            "sector_period": 5,
            "sector_top_n": 25,
        },
    ),
    # ── 示例 9：主力资金驱动策略 ──
    StrategyExample(
        name="主力资金驱动策略",
        description="筛选主力资金持续流入且技术面配合的个股，适合中短线波段操作",
        factors=[
            {
                "factor_name": "money_flow",
                "operator": ">=",
                "threshold": 85,
                "params": {},
            },
            {
                "factor_name": "large_order",
                "operator": ">=",
                "threshold": 30,
                "params": {},
            },
            {
                "factor_name": "macd",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "money_flow": 0.3,
            "large_order": 0.25,
            "macd": 0.25,
            "ma_trend": 0.2,
        },
        enabled_modules=["indicator_params", "ma_trend", "volume_price"],
    ),
    # ── 示例 10：概念板块 + 形态突破联动 ──
    StrategyExample(
        name="概念板块 + 形态突破联动",
        description="在热门概念板块中寻找形态突破的个股，板块热度与技术突破共振",
        factors=[
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 10,
                "params": {},
            },
            {
                "factor_name": "sector_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "breakout",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "turnover",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 5.0, "threshold_high": 20.0},
            },
        ],
        logic="AND",
        weights={
            "sector_rank": 0.3,
            "sector_trend": 0.2,
            "breakout": 0.3,
            "turnover": 0.2,
        },
        enabled_modules=["breakout", "volume_price"],
        sector_config={
            "sector_data_source": "DC",
            "sector_type": "CONCEPT",
            "sector_period": 3,
            "sector_top_n": 10,
        },
    ),
    # ── 示例 11：多数据源板块交叉验证 ──
    StrategyExample(
        name="多数据源板块交叉验证",
        description="使用通达信行业数据与东方财富概念数据交叉验证，筛选同时处于强势行业和热门概念的个股",
        factors=[
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 30,
                "params": {
                    "sector_data_source": "TDX",
                    "sector_type": "INDUSTRY",
                    "sector_period": 5,
                },
            },
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 20,
                "params": {
                    "sector_data_source": "DC",
                    "sector_type": "CONCEPT",
                    "sector_period": 3,
                },
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
        ],
        logic="AND",
        weights={"sector_rank": 0.6, "ma_trend": 0.4},
        enabled_modules=["ma_trend"],
    ),
    # ── 示例 12：RSI 超卖反弹 + 板块支撑 ──
    StrategyExample(
        name="RSI 超卖反弹 + 板块支撑",
        description="在强势板块中寻找 RSI 短期超卖后反弹的个股，逆向买入但有板块趋势保护",
        factors=[
            {
                "factor_name": "rsi",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 30, "threshold_high": 50},
            },
            {
                "factor_name": "sector_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 30,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 55,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "rsi": 0.3,
            "sector_trend": 0.25,
            "sector_rank": 0.25,
            "ma_trend": 0.2,
        },
        enabled_modules=["indicator_params", "ma_trend"],
        sector_config={
            "sector_data_source": "TI",
            "sector_type": "INDUSTRY",
            "sector_period": 5,
            "sector_top_n": 30,
        },
    ),
]
