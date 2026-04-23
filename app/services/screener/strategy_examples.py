"""
实战选股策略示例库（Strategy Examples Library）

提供：
- StrategyExample: 策略示例数据类（含 config_doc 配置说明书字段）
- STRATEGY_EXAMPLES: 22 个可直接加载为 StrategyConfig 的实战选股策略示例

每个示例包含完整的因子条件列表、逻辑运算、权重、启用模块、板块筛选配置和配置说明书，
可通过 GET /api/v1/screen/strategy-examples 端点暴露给前端。

对应需求：
- 需求 14：实战选股策略示例库
- 需求 19：优化选股组合方案（新增 10 个策略示例）
- 需求 20：选股组合配置说明书（config_doc 字段）
- 需求 22.9：移除现有策略示例中的 sector_type 字段
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StrategyExample:
    """策略示例（需求 19、20）"""

    name: str
    description: str
    factors: list[dict]
    logic: str
    weights: dict[str, float]
    enabled_modules: list[str]
    sector_config: dict | None = None
    config_doc: str = ""  # 配置说明书（需求 20.1）


# ---------------------------------------------------------------------------
# STRATEGY_EXAMPLES: 22 个实战选股策略示例（需求 19、20、22.9）
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
        config_doc=(
            "## 策略概述\n"
            "基于均线多头排列捕捉强势上升趋势个股，三因子 AND 逻辑确认趋势强度。\n\n"
            "## 因子构成\n"
            "- **ma_trend ≥ 85**：均线趋势打分，权重 0.5，可调范围 [70, 95]\n"
            "- **ma_support = True**：均线支撑信号，权重 0.3\n"
            "- **dma = True**：DMA 平行线差多头，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：牛市或震荡偏强\n"
            "- 交易周期：中短线（3-15 个交易日）\n"
            "- 标的类型：中大盘趋势股\n\n"
            "## 参数调优建议\n"
            "- 牛市：ma_trend 可放宽至 75，捕捉更多标的\n"
            "- 震荡市：ma_trend 收紧至 90，提高胜率\n\n"
            "## 风险提示\n"
            "- 趋势末端追高风险，注意均线拐头信号\n"
            "- 大盘系统性下跌时趋势股回撤较大\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1-2 年，覆盖牛熊转换\n"
            "- 关注指标：胜率、最大回撤、夏普比率"
        ),
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
        config_doc=(
            "## 策略概述\n"
            "MACD 零轴上方金叉配合成交量放大，确认短期多头启动信号。\n\n"
            "## 因子构成\n"
            "- **macd = True**：MACD 金叉信号，权重 0.4\n"
            "- **turnover 5%-15%**：换手率适中区间，权重 0.3\n"
            "- **volume_price ≥ 80**：日均成交额百分位，权重 0.3\n\n"
            "## 适用场景\n"
            "- 市场环境：震荡市或牛市初期\n"
            "- 交易周期：短线（2-10 个交易日）\n"
            "- 标的类型：活跃交易个股\n\n"
            "## 参数调优建议\n"
            "- 换手率上限可调至 20% 以覆盖更活跃标的\n"
            "- volume_price 可降至 70 以扩大选股范围\n\n"
            "## 风险提示\n"
            "- MACD 金叉可能出现假信号，需量价配合确认\n"
            "- 高换手率个股波动较大，注意止损\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 6 个月至 1 年\n"
            "- 关注指标：胜率、盈亏比、平均持仓天数"
        ),
    ),
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
            "sector_period": 3,
            "sector_top_n": 15,
        },
        config_doc=(
            "## 策略概述\n"
            "追踪东方财富概念板块轮动热点，筛选强势概念板块中的龙头股。\n\n"
            "## 因子构成\n"
            "- **sector_rank ≤ 15**：板块涨幅排名前 15，权重 0.4\n"
            "- **sector_trend = True**：板块处于多头趋势，权重 0.3\n"
            "- **ma_trend ≥ 70**：个股均线趋势，权重 0.3\n\n"
            "## 适用场景\n"
            "- 市场环境：概念炒作活跃期\n"
            "- 交易周期：短线（1-5 个交易日）\n"
            "- 标的类型：概念龙头股\n\n"
            "## 参数调优建议\n"
            "- sector_rank 可收紧至 10 以聚焦最强板块\n"
            "- sector_period 可调至 1-3 日以捕捉短期热点\n\n"
            "## 风险提示\n"
            "- 概念炒作持续性不确定，注意及时止盈\n"
            "- 龙头股高位接力风险较大\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 3-6 个月\n"
            "- 关注指标：胜率、最大单笔亏损、换手率"
        ),
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
            "sector_period": 5,
            "sector_top_n": 20,
        },
        config_doc=(
            "## 策略概述\n"
            "跟踪申万行业板块轮动节奏，在强势行业中选择技术面共振的个股。\n\n"
            "## 因子构成\n"
            "- **sector_rank ≤ 20**：行业涨幅排名前 20，权重 0.3\n"
            "- **sector_trend = True**：行业处于多头趋势，权重 0.2\n"
            "- **macd = True**：MACD 金叉信号，权重 0.3\n"
            "- **rsi [55, 75]**：RSI 强势区间，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：行业轮动明显的震荡市或结构性牛市\n"
            "- 交易周期：中短线（5-20 个交易日）\n"
            "- 标的类型：行业龙头或细分赛道领军\n\n"
            "## 参数调优建议\n"
            "- 牛市：sector_rank 可放宽至 30\n"
            "- 震荡市：RSI 区间收窄至 [60, 75]\n\n"
            "## 风险提示\n"
            "- 行业轮动节奏快，需及时跟踪板块变化\n"
            "- 行业政策风险可能导致板块急跌\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：行业胜率、超额收益、最大回撤"
        ),
    ),
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
        config_doc=(
            "## 策略概述\n"
            "捕捉箱体突破或前高突破的个股，要求量价配合确认突破有效性。\n\n"
            "## 因子构成\n"
            "- **breakout = True**：形态突破信号，权重 0.35\n"
            "- **turnover 5%-20%**：换手率适中区间，权重 0.2\n"
            "- **large_order ≥ 35**：大单成交占比，权重 0.25\n"
            "- **ma_trend ≥ 60**：均线趋势打分，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：震荡市突破行情\n"
            "- 交易周期：短线至中线（3-15 个交易日）\n"
            "- 标的类型：横盘整理后放量突破的个股\n\n"
            "## 参数调优建议\n"
            "- large_order 可调至 30 以扩大选股范围\n"
            "- ma_trend 可提高至 70 以确保趋势配合\n\n"
            "## 风险提示\n"
            "- 假突破风险，需关注突破后回踩确认\n"
            "- 放量突破后可能出现获利回吐\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：突破成功率、平均涨幅、最大回撤"
        ),
    ),
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
        config_doc=(
            "## 策略概述\n"
            "多个技术指标同时发出多头信号，形成共振确认，提高信号可靠性。\n\n"
            "## 因子构成\n"
            "- **macd = True**：MACD 金叉信号，权重 0.25\n"
            "- **boll = True**：布林带突破信号，权重 0.2\n"
            "- **rsi [50, 80]**：RSI 强势区间，权重 0.2\n"
            "- **dma = True**：DMA 多头信号，权重 0.15\n"
            "- **ma_trend ≥ 75**：均线趋势打分，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：趋势明确的上涨行情\n"
            "- 交易周期：短线（3-10 个交易日）\n"
            "- 标的类型：技术面活跃个股\n\n"
            "## 参数调优建议\n"
            "- RSI 上限可调至 75 以避免超买区域\n"
            "- ma_trend 可放宽至 70 以增加选股数量\n\n"
            "## 风险提示\n"
            "- 多指标共振信号较少，可能错过部分机会\n"
            "- 技术指标在极端行情中可能失效\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：信号频率、胜率、盈亏比"
        ),
    ),
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
        config_doc=(
            "## 策略概述\n"
            "在上升趋势中回调至均线支撑位企稳反弹的买入机会。\n\n"
            "## 因子构成\n"
            "- **ma_support = True**：均线支撑信号，权重 0.35\n"
            "- **ma_trend ≥ 65**：均线趋势打分，权重 0.3\n"
            "- **rsi [40, 60]**：RSI 中性偏弱区间（回调），权重 0.2\n"
            "- **turnover 3%-10%**：换手率适中，权重 0.15\n\n"
            "## 适用场景\n"
            "- 市场环境：上升趋势中的回调阶段\n"
            "- 交易周期：中短线（5-15 个交易日）\n"
            "- 标的类型：趋势回调企稳个股\n\n"
            "## 参数调优建议\n"
            "- RSI 下限可调至 35 以捕捉更深回调\n"
            "- ma_trend 可提高至 70 以确保趋势强度\n\n"
            "## 风险提示\n"
            "- 回调可能演变为趋势反转，需设置止损\n"
            "- 均线支撑位可能被跌破\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：反弹成功率、平均反弹幅度、止损触发率"
        ),
    ),
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
            "sector_period": 5,
            "sector_top_n": 25,
        },
        config_doc=(
            "## 策略概述\n"
            "在强势板块中寻找布林带突破的个股，板块动量与个股技术面双重确认。\n\n"
            "## 因子构成\n"
            "- **sector_rank ≤ 25**：板块涨幅排名前 25，权重 0.3\n"
            "- **boll = True**：布林带突破信号，权重 0.3\n"
            "- **ma_trend ≥ 70**：均线趋势打分，权重 0.2\n"
            "- **volume_price ≥ 70**：日均成交额百分位，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：板块轮动活跃期\n"
            "- 交易周期：短线（3-10 个交易日）\n"
            "- 标的类型：强势板块中的技术突破股\n\n"
            "## 参数调优建议\n"
            "- sector_rank 可收紧至 15 以聚焦最强板块\n"
            "- volume_price 可降至 60 以扩大选股范围\n\n"
            "## 风险提示\n"
            "- 板块热度消退后个股可能快速回落\n"
            "- 布林带突破后可能出现假突破回落\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 6 个月至 1 年\n"
            "- 关注指标：胜率、平均持仓天数、最大回撤"
        ),
    ),
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
        config_doc=(
            "## 策略概述\n"
            "筛选主力资金持续流入且技术面配合的个股，适合中短线波段操作。\n\n"
            "## 因子构成\n"
            "- **money_flow ≥ 85**：主力资金净流入百分位，权重 0.3\n"
            "- **large_order ≥ 30**：大单成交占比，权重 0.25\n"
            "- **macd = True**：MACD 金叉信号，权重 0.25\n"
            "- **ma_trend ≥ 70**：均线趋势打分，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：资金面活跃的上涨行情\n"
            "- 交易周期：中短线（3-15 个交易日）\n"
            "- 标的类型：主力资金关注的中大盘股\n\n"
            "## 参数调优建议\n"
            "- money_flow 可降至 75 以扩大选股范围\n"
            "- large_order 可提高至 35 以确认主力参与度\n\n"
            "## 风险提示\n"
            "- 主力资金可能短期流入后快速撤出\n"
            "- 资金流数据存在滞后性\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 6 个月至 1 年\n"
            "- 关注指标：资金流持续性、胜率、盈亏比"
        ),
    ),
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
            "sector_period": 3,
            "sector_top_n": 10,
        },
        config_doc=(
            "## 策略概述\n"
            "在热门概念板块中寻找形态突破的个股，板块热度与技术突破共振。\n\n"
            "## 因子构成\n"
            "- **sector_rank ≤ 10**：板块涨幅排名前 10，权重 0.3\n"
            "- **sector_trend = True**：板块多头趋势，权重 0.2\n"
            "- **breakout = True**：形态突破信号，权重 0.3\n"
            "- **turnover 5%-20%**：换手率适中区间，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：概念炒作活跃期\n"
            "- 交易周期：短线（1-5 个交易日）\n"
            "- 标的类型：热门概念中的突破股\n\n"
            "## 参数调优建议\n"
            "- sector_rank 可放宽至 15 以增加选股数量\n"
            "- sector_period 可调至 1 日以捕捉最新热点\n\n"
            "## 风险提示\n"
            "- 概念炒作退潮后可能快速回落\n"
            "- 突破后追高风险较大\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 3-6 个月\n"
            "- 关注指标：胜率、最大单笔亏损、持仓天数"
        ),
    ),
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
                    "sector_period": 5,
                },
            },
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 20,
                "params": {
                    "sector_data_source": "DC",
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
        config_doc=(
            "## 策略概述\n"
            "使用通达信行业数据与东方财富概念数据交叉验证，筛选同时处于强势行业和热门概念的个股。\n\n"
            "## 因子构成\n"
            "- **sector_rank ≤ 30**（TDX）：通达信行业排名前 30，权重 0.3\n"
            "- **sector_rank ≤ 20**（DC）：东方财富概念排名前 20，权重 0.3\n"
            "- **ma_trend ≥ 70**：均线趋势打分，权重 0.4\n\n"
            "## 适用场景\n"
            "- 市场环境：行业与概念共振的结构性行情\n"
            "- 交易周期：中短线（5-15 个交易日）\n"
            "- 标的类型：行业与概念双重强势个股\n\n"
            "## 参数调优建议\n"
            "- 可调整两个 sector_rank 阈值以平衡选股数量\n"
            "- 可替换数据来源为 TI/THS 等\n\n"
            "## 风险提示\n"
            "- 多数据源可能存在数据延迟差异\n"
            "- 交叉验证条件较严格，信号较少\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：信号频率、胜率、超额收益"
        ),
    ),
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
            "sector_period": 5,
            "sector_top_n": 30,
        },
        config_doc=(
            "## 策略概述\n"
            "在强势板块中寻找 RSI 短期超卖后反弹的个股，逆向买入但有板块趋势保护。\n\n"
            "## 因子构成\n"
            "- **rsi [30, 50]**：RSI 超卖反弹区间，权重 0.3\n"
            "- **sector_trend = True**：板块多头趋势保护，权重 0.25\n"
            "- **sector_rank ≤ 30**：板块排名前 30，权重 0.25\n"
            "- **ma_trend ≥ 55**：均线趋势基本向好，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：强势板块中的个股短期回调\n"
            "- 交易周期：短线（3-8 个交易日）\n"
            "- 标的类型：强势板块中的超卖反弹股\n\n"
            "## 参数调优建议\n"
            "- RSI 下限可调至 25 以捕捉更深超卖\n"
            "- ma_trend 可提高至 60 以增强趋势保护\n\n"
            "## 风险提示\n"
            "- 超卖可能继续下跌，需严格止损\n"
            "- 板块趋势反转时策略失效\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：反弹成功率、平均反弹幅度、最大回撤"
        ),
    ),
    StrategyExample(
        name="筹码集中突破型",
        description="组合筹码集中度与形态突破，在筹码高度集中时捕捉放量突破信号，适用于中线波段操作",
        factors=[
            {
                "factor_name": "chip_concentration",
                "operator": ">=",
                "threshold": 70,
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
                "params": {"threshold_low": 5.0, "threshold_high": 15.0},
            },
        ],
        logic="AND",
        weights={"chip_concentration": 0.4, "breakout": 0.35, "turnover": 0.25},
        enabled_modules=["breakout", "volume_price"],
        config_doc=(
            "## 策略概述\n"
            "组合筹码集中度与形态突破，在筹码高度集中时捕捉放量突破信号，适用于中线波段操作。\n\n"
            "## 因子构成\n"
            "- **chip_concentration ≥ 70**：筹码集中度综合评分百分位，权重 0.4，可调范围 [60, 80]\n"
            "- **breakout = True**：形态突破信号（箱体/前高/趋势线），权重 0.35\n"
            "- **turnover 5%-15%**：换手率适中区间，权重 0.25\n\n"
            "## 适用场景\n"
            "- 市场环境：震荡市或牛市初期\n"
            "- 交易周期：中线（10-30 个交易日）\n"
            "- 标的类型：筹码集中后放量突破的个股\n\n"
            "## 参数调优建议\n"
            "- 牛市：chip_concentration 可放宽至 60\n"
            "- 震荡市：chip_concentration 收紧至 75，换手率上限调至 12%\n\n"
            "## 风险提示\n"
            "- 筹码集中不代表一定上涨，需配合突破确认\n"
            "- 假突破后筹码松动可能导致快速下跌\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1-2 年\n"
            "- 关注指标：突破成功率、持仓收益率、最大回撤"
        ),
    ),
    StrategyExample(
        name="两融资金驱动型",
        description="融资净买入配合两融余额趋势与主力资金流入，多维度确认资金持续流入，适用于中短线",
        factors=[
            {
                "factor_name": "margin_net_buy",
                "operator": ">=",
                "threshold": 75,
                "params": {},
            },
            {
                "factor_name": "rzrq_balance_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "money_flow",
                "operator": ">=",
                "threshold": 80,
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
            "margin_net_buy": 0.3,
            "rzrq_balance_trend": 0.2,
            "money_flow": 0.3,
            "ma_trend": 0.2,
        },
        enabled_modules=["ma_trend", "volume_price"],
        config_doc=(
            "## 策略概述\n"
            "融资净买入配合两融余额趋势与主力资金流入，多维度确认资金持续流入。\n\n"
            "## 因子构成\n"
            "- **margin_net_buy ≥ 75**：融资净买入额百分位，权重 0.3，可调范围 [65, 85]\n"
            "- **rzrq_balance_trend = True**：近 5 日融资余额连续增加，权重 0.2\n"
            "- **money_flow ≥ 80**：主力资金净流入百分位，权重 0.3\n"
            "- **ma_trend ≥ 70**：均线趋势打分，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：两融活跃的上涨行情\n"
            "- 交易周期：中短线（5-15 个交易日）\n"
            "- 标的类型：两融标的中的资金驱动股\n\n"
            "## 参数调优建议\n"
            "- 牛市：margin_net_buy 可放宽至 65\n"
            "- 震荡市：money_flow 收紧至 85\n\n"
            "## 风险提示\n"
            "- 两融数据仅覆盖融资融券标的，非全市场\n"
            "- 融资余额趋势反转时需及时止损\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1 年\n"
            "- 关注指标：资金流持续性、胜率、夏普比率"
        ),
    ),
    StrategyExample(
        name="多维资金共振型",
        description="超大单、大单、小单、资金流强度四维共振，确认主力资金大幅流入且散户离场，适用于短线",
        factors=[
            {
                "factor_name": "super_large_net_inflow",
                "operator": ">=",
                "threshold": 85,
                "params": {},
            },
            {
                "factor_name": "large_net_inflow",
                "operator": ">=",
                "threshold": 80,
                "params": {},
            },
            {
                "factor_name": "small_net_outflow",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "money_flow_strength",
                "operator": ">=",
                "threshold": 75,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "super_large_net_inflow": 0.35,
            "large_net_inflow": 0.25,
            "small_net_outflow": 0.15,
            "money_flow_strength": 0.25,
        },
        enabled_modules=["volume_price"],
        config_doc=(
            "## 策略概述\n"
            "超大单、大单、小单、资金流强度四维共振，确认主力资金大幅流入且散户离场。\n\n"
            "## 因子构成\n"
            "- **super_large_net_inflow ≥ 85**：超大单净流入百分位，权重 0.35\n"
            "- **large_net_inflow ≥ 80**：大单净流入百分位，权重 0.25\n"
            "- **small_net_outflow = True**：小单净流出（散户离场），权重 0.15\n"
            "- **money_flow_strength ≥ 75**：资金流强度综合评分，权重 0.25\n\n"
            "## 适用场景\n"
            "- 市场环境：资金面活跃的短线行情\n"
            "- 交易周期：短线（1-5 个交易日）\n"
            "- 标的类型：主力资金大幅流入的活跃股\n\n"
            "## 参数调优建议\n"
            "- 可降低 super_large_net_inflow 至 80 以增加信号\n"
            "- money_flow_strength 可调至 70 以放宽条件\n\n"
            "## 风险提示\n"
            "- 资金流数据存在日内波动，盘后数据更可靠\n"
            "- 短线策略需严格止损，防止资金撤退\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 3-6 个月\n"
            "- 关注指标：日均收益率、胜率、最大连续亏损"
        ),
    ),
    StrategyExample(
        name="首板打板策略",
        description="首板涨停配合封板率与换手率，龙虎榜净买入作为加分项（OR 逻辑），适用于超短线打板",
        factors=[
            {
                "factor_name": "first_limit_up",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "limit_up_open_pct",
                "operator": ">=",
                "threshold": 80,
                "params": {},
            },
            {
                "factor_name": "turnover",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 5.0, "threshold_high": 20.0},
            },
            {
                "factor_name": "dragon_tiger_net_buy",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
        ],
        logic="OR",
        weights={
            "first_limit_up": 0.3,
            "limit_up_open_pct": 0.25,
            "turnover": 0.2,
            "dragon_tiger_net_buy": 0.25,
        },
        enabled_modules=["volume_price"],
        config_doc=(
            "## 策略概述\n"
            "首板涨停配合封板率与换手率，龙虎榜净买入作为加分项（OR 逻辑），适用于超短线打板。\n\n"
            "## 因子构成\n"
            "- **first_limit_up = True**：当日首次涨停标记，权重 0.3\n"
            "- **limit_up_open_pct ≥ 80**：涨停封板率，权重 0.25，可调范围 [70, 90]\n"
            "- **turnover 5%-20%**：换手率适中区间，权重 0.2\n"
            "- **dragon_tiger_net_buy = True**：龙虎榜机构净买入（OR 加分项），权重 0.25\n\n"
            "## 适用场景\n"
            "- 市场环境：题材炒作活跃期\n"
            "- 交易周期：超短线（1-3 个交易日）\n"
            "- 标的类型：首板涨停个股\n\n"
            "## 参数调优建议\n"
            "- 封板率可提高至 85 以筛选更坚决的涨停\n"
            "- 换手率上限可调至 25% 以覆盖更多标的\n\n"
            "## 风险提示\n"
            "- 打板策略风险极高，次日可能大幅低开\n"
            "- 涨停板炸板风险，需关注封单量\n"
            "- 建议严格控制仓位，单票不超过总仓位 10%\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 3 个月\n"
            "- 关注指标：次日溢价率、封板成功率、最大亏损"
        ),
    ),
    StrategyExample(
        name="价值成长筹码型",
        description="ROE 与利润增长确认基本面优质，PE 行业相对低估，筹码集中且趋势向好，适用于中长线",
        factors=[
            {
                "factor_name": "roe",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
            {
                "factor_name": "profit_growth",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
            {
                "factor_name": "pe",
                "operator": "<=",
                "threshold": 1.0,
                "params": {},
            },
            {
                "factor_name": "chip_concentration",
                "operator": ">=",
                "threshold": 60,
                "params": {},
            },
            {
                "factor_name": "ma_trend",
                "operator": ">=",
                "threshold": 65,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "roe": 0.25,
            "profit_growth": 0.2,
            "pe": 0.2,
            "chip_concentration": 0.2,
            "ma_trend": 0.15,
        },
        enabled_modules=["ma_trend"],
        config_doc=(
            "## 策略概述\n"
            "ROE 与利润增长确认基本面优质，PE 行业相对低估，筹码集中且趋势向好，适用于中长线。\n\n"
            "## 因子构成\n"
            "- **roe ≥ 70**：ROE 百分位排名，权重 0.25\n"
            "- **profit_growth ≥ 70**：利润增长率百分位，权重 0.2\n"
            "- **pe ≤ 1.0**：PE 行业相对值（低于行业中位数），权重 0.2\n"
            "- **chip_concentration ≥ 60**：筹码集中度百分位，权重 0.2\n"
            "- **ma_trend ≥ 65**：均线趋势打分，权重 0.15\n\n"
            "## 适用场景\n"
            "- 市场环境：价值回归行情或慢牛市\n"
            "- 交易周期：中长线（20-60 个交易日）\n"
            "- 标的类型：基本面优质的价值成长股\n\n"
            "## 参数调优建议\n"
            "- 牛市：pe 可放宽至 1.2，chip_concentration 降至 55\n"
            "- 熊市：roe 提高至 80，pe 收紧至 0.8\n\n"
            "## 风险提示\n"
            "- 价值股可能长期横盘，需耐心持有\n"
            "- 基本面数据更新频率较低（季报），存在滞后性\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 2-3 年\n"
            "- 关注指标：年化收益率、夏普比率、最大回撤、卡玛比率"
        ),
    ),
    StrategyExample(
        name="指数增强型",
        description="跟随大盘趋势，在强势板块中选择技术指标共振且资金流入的个股，适用于跟随大盘趋势",
        factors=[
            {
                "factor_name": "index_ma_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 20,
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
            {
                "factor_name": "money_flow_strength",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "index_ma_trend": 0.2,
            "sector_rank": 0.2,
            "macd": 0.2,
            "rsi": 0.2,
            "money_flow_strength": 0.2,
        },
        enabled_modules=["indicator_params", "ma_trend", "volume_price"],
        sector_config={
            "sector_data_source": "DC",
            "sector_period": 5,
            "sector_top_n": 20,
        },
        config_doc=(
            "## 策略概述\n"
            "跟随大盘趋势，在强势板块中选择技术指标共振且资金流入的个股。\n\n"
            "## 因子构成\n"
            "- **index_ma_trend = True**：指数均线趋势多头，权重 0.2\n"
            "- **sector_rank ≤ 20**：板块涨幅排名前 20，权重 0.2\n"
            "- **macd = True**：MACD 金叉信号，权重 0.2\n"
            "- **rsi [55, 75]**：RSI 强势区间，权重 0.2\n"
            "- **money_flow_strength ≥ 70**：资金流强度评分，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：大盘趋势向上的牛市或反弹行情\n"
            "- 交易周期：中短线（5-20 个交易日）\n"
            "- 标的类型：跟随大盘趋势的强势个股\n\n"
            "## 参数调优建议\n"
            "- 牛市：sector_rank 可放宽至 30\n"
            "- 震荡市：money_flow_strength 提高至 75\n\n"
            "## 风险提示\n"
            "- 大盘趋势反转时策略整体失效\n"
            "- 指数均线趋势信号存在滞后性\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1-2 年\n"
            "- 关注指标：相对基准超额收益、信息比率、最大回撤"
        ),
    ),
    StrategyExample(
        name="连板接力型",
        description="连板天数与封板率双重确认强势，龙虎榜与超大单资金验证主力参与，适用于超短线连板接力",
        factors=[
            {
                "factor_name": "limit_up_streak",
                "operator": ">=",
                "threshold": 2,
                "params": {},
            },
            {
                "factor_name": "limit_up_open_pct",
                "operator": ">=",
                "threshold": 85,
                "params": {},
            },
            {
                "factor_name": "dragon_tiger_net_buy",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "super_large_net_inflow",
                "operator": ">=",
                "threshold": 85,
                "params": {},
            },
            {
                "factor_name": "turnover",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 8.0, "threshold_high": 25.0},
            },
        ],
        logic="AND",
        weights={
            "limit_up_streak": 0.25,
            "limit_up_open_pct": 0.2,
            "dragon_tiger_net_buy": 0.2,
            "super_large_net_inflow": 0.2,
            "turnover": 0.15,
        },
        enabled_modules=["volume_price"],
        config_doc=(
            "## 策略概述\n"
            "连板天数与封板率双重确认强势，龙虎榜与超大单资金验证主力参与，适用于超短线连板接力。\n\n"
            "## 因子构成\n"
            "- **limit_up_streak ≥ 2**：连板天数，权重 0.25\n"
            "- **limit_up_open_pct ≥ 85**：涨停封板率，权重 0.2\n"
            "- **dragon_tiger_net_buy = True**：龙虎榜机构净买入，权重 0.2\n"
            "- **super_large_net_inflow ≥ 85**：超大单净流入百分位，权重 0.2\n"
            "- **turnover 8%-25%**：换手率区间，权重 0.15\n\n"
            "## 适用场景\n"
            "- 市场环境：题材炒作高潮期\n"
            "- 交易周期：超短线（1-3 个交易日）\n"
            "- 标的类型：连板强势股\n\n"
            "## 参数调优建议\n"
            "- limit_up_streak 可调至 3 以筛选更强势标的\n"
            "- 封板率可降至 80 以增加选股数量\n\n"
            "## 风险提示\n"
            "- 连板接力风险极高，断板后可能连续跌停\n"
            "- 高位连板股流动性风险大\n"
            "- 建议严格控制仓位，单票不超过总仓位 5%\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 3 个月\n"
            "- 关注指标：接力成功率、断板亏损率、最大连续亏损"
        ),
    ),
    StrategyExample(
        name="主力吸筹型",
        description="筹码集中且散户流出，融资余额持续增加，获利比例低位表明底部吸筹，适用于中短线底部布局",
        factors=[
            {
                "factor_name": "chip_concentration",
                "operator": ">=",
                "threshold": 65,
                "params": {},
            },
            {
                "factor_name": "small_net_outflow",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "rzrq_balance_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "chip_winner_rate",
                "operator": "<=",
                "threshold": 30,
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
            "chip_concentration": 0.25,
            "small_net_outflow": 0.2,
            "rzrq_balance_trend": 0.2,
            "chip_winner_rate": 0.2,
            "ma_trend": 0.15,
        },
        enabled_modules=["ma_trend"],
        config_doc=(
            "## 策略概述\n"
            "筹码集中且散户流出，融资余额持续增加，获利比例低位表明底部吸筹。\n\n"
            "## 因子构成\n"
            "- **chip_concentration ≥ 65**：筹码集中度百分位，权重 0.25\n"
            "- **small_net_outflow = True**：小单净流出（散户离场），权重 0.2\n"
            "- **rzrq_balance_trend = True**：近 5 日融资余额连续增加，权重 0.2\n"
            "- **chip_winner_rate ≤ 30**：获利比例低位百分位，权重 0.2\n"
            "- **ma_trend ≥ 60**：均线趋势基本向好，权重 0.15\n\n"
            "## 适用场景\n"
            "- 市场环境：底部震荡或熊市末期\n"
            "- 交易周期：中短线（10-30 个交易日）\n"
            "- 标的类型：底部吸筹阶段的个股\n\n"
            "## 参数调优建议\n"
            "- chip_winner_rate 可调至 25 以筛选更深底部\n"
            "- ma_trend 可降至 55 以捕捉更早期信号\n\n"
            "## 风险提示\n"
            "- 底部吸筹阶段可能持续较长时间\n"
            "- 主力吸筹后不一定立即拉升\n"
            "- 需耐心持有，设置合理止损\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1-2 年\n"
            "- 关注指标：持仓周期、收益率、最大回撤"
        ),
    ),
    StrategyExample(
        name="技术共振型",
        description="KDJ 金叉区间配合 MACD、RSI、布林带多指标共振，资金流强度确认量能配合，适用于短线波段",
        factors=[
            {
                "factor_name": "kdj_k",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 20, "threshold_high": 50},
            },
            {
                "factor_name": "kdj_d",
                "operator": "BETWEEN",
                "threshold": None,
                "params": {"threshold_low": 20, "threshold_high": 50},
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
                "params": {"threshold_low": 50, "threshold_high": 70},
            },
            {
                "factor_name": "boll",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "money_flow_strength",
                "operator": ">=",
                "threshold": 65,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "kdj_k": 0.15,
            "kdj_d": 0.15,
            "macd": 0.2,
            "rsi": 0.2,
            "boll": 0.15,
            "money_flow_strength": 0.15,
        },
        enabled_modules=["indicator_params", "volume_price"],
        config_doc=(
            "## 策略概述\n"
            "KDJ 金叉区间配合 MACD、RSI、布林带多指标共振，资金流强度确认量能配合。\n\n"
            "## 因子构成\n"
            "- **kdj_k [20, 50]**：KDJ-K 值金叉区间，权重 0.15\n"
            "- **kdj_d [20, 50]**：KDJ-D 值金叉区间，权重 0.15\n"
            "- **macd = True**：MACD 金叉信号，权重 0.2\n"
            "- **rsi [50, 70]**：RSI 强势区间，权重 0.2\n"
            "- **boll = True**：布林带突破信号，权重 0.15\n"
            "- **money_flow_strength ≥ 65**：资金流强度评分，权重 0.15\n\n"
            "## 适用场景\n"
            "- 市场环境：震荡市或上涨初期\n"
            "- 交易周期：短线（3-10 个交易日）\n"
            "- 标的类型：技术面活跃的中小盘股\n\n"
            "## 参数调优建议\n"
            "- KDJ 区间可调至 [25, 45] 以更精准捕捉金叉\n"
            "- RSI 区间可调至 [55, 75] 以确认更强势\n\n"
            "## 风险提示\n"
            "- 多指标共振条件严格，信号较少\n"
            "- 技术指标在极端行情中可能同时失效\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 6 个月至 1 年\n"
            "- 关注指标：信号频率、胜率、盈亏比、平均持仓天数"
        ),
    ),
    StrategyExample(
        name="行业轮动增强型",
        description="申万行业排名配合指数趋势，ROE 与融资净买入确认基本面与资金面，形态突破确认启动信号，适用于中线行业轮动",
        factors=[
            {
                "factor_name": "sector_rank",
                "operator": "<=",
                "threshold": 15,
                "params": {},
            },
            {
                "factor_name": "index_ma_trend",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
            {
                "factor_name": "roe",
                "operator": ">=",
                "threshold": 65,
                "params": {},
            },
            {
                "factor_name": "margin_net_buy",
                "operator": ">=",
                "threshold": 70,
                "params": {},
            },
            {
                "factor_name": "breakout",
                "operator": "==",
                "threshold": None,
                "params": {},
            },
        ],
        logic="AND",
        weights={
            "sector_rank": 0.25,
            "index_ma_trend": 0.15,
            "roe": 0.2,
            "margin_net_buy": 0.2,
            "breakout": 0.2,
        },
        enabled_modules=["breakout", "ma_trend"],
        sector_config={
            "sector_data_source": "TI",
            "sector_period": 5,
            "sector_top_n": 15,
        },
        config_doc=(
            "## 策略概述\n"
            "申万行业排名配合指数趋势，ROE 与融资净买入确认基本面与资金面，形态突破确认启动信号。\n\n"
            "## 因子构成\n"
            "- **sector_rank ≤ 15**：申万行业排名前 15（TI 数据源），权重 0.25\n"
            "- **index_ma_trend = True**：指数均线趋势多头，权重 0.15\n"
            "- **roe ≥ 65**：ROE 百分位排名，权重 0.2\n"
            "- **margin_net_buy ≥ 70**：融资净买入额百分位，权重 0.2\n"
            "- **breakout = True**：形态突破信号，权重 0.2\n\n"
            "## 适用场景\n"
            "- 市场环境：行业轮动明显的结构性行情\n"
            "- 交易周期：中线（10-30 个交易日）\n"
            "- 标的类型：强势行业中的优质个股\n\n"
            "## 参数调优建议\n"
            "- 牛市：sector_rank 可放宽至 20，roe 降至 60\n"
            "- 震荡市：sector_rank 收紧至 10，margin_net_buy 提高至 75\n\n"
            "## 风险提示\n"
            "- 行业政策变化可能导致板块急跌\n"
            "- 两融数据仅覆盖融资融券标的\n\n"
            "## 回测建议\n"
            "- 建议回测周期：近 1-2 年\n"
            "- 关注指标：行业超额收益、夏普比率、最大回撤、卡玛比率"
        ),
    ),
]
