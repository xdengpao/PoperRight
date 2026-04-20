"""
因子元数据注册表（Factor Metadata Registry）

提供：
- ThresholdType: 因子阈值类型枚举
- FactorCategory: 因子类别枚举
- FactorMeta: 因子元数据冻结数据类
- FACTOR_REGISTRY: 全量因子元数据常量字典（19 个因子）
- get_factor_meta(): 按因子名称查询元数据
- get_factors_by_category(): 按类别筛选因子列表

对应需求：
- 需求 1：因子元数据注册表
- 需求 2：技术面因子阈值评估与优化
- 需求 3：资金面因子阈值评估与优化
- 需求 4：基本面因子阈值评估与优化
- 需求 6：板块面因子元数据定义
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------


class ThresholdType(str, Enum):
    """因子阈值类型"""
    ABSOLUTE = "absolute"                    # 绝对值
    PERCENTILE = "percentile"                # 百分位排名 (0-100)
    INDUSTRY_RELATIVE = "industry_relative"  # 行业相对值
    Z_SCORE = "z_score"                      # 标准化分数
    BOOLEAN = "boolean"                      # 布尔型
    RANGE = "range"                          # 区间型


class FactorCategory(str, Enum):
    """因子类别"""
    TECHNICAL = "technical"
    MONEY_FLOW = "money_flow"
    FUNDAMENTAL = "fundamental"
    SECTOR = "sector"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FactorMeta:
    """因子元数据（不可变）"""
    factor_name: str                                    # 因子标识符，如 "ma_trend"
    label: str                                          # 中文标签，如 "MA趋势打分"
    category: FactorCategory                            # 所属类别
    threshold_type: ThresholdType                       # 阈值类型
    default_threshold: float | None = None              # 默认阈值
    value_min: float | None = None                      # 取值范围下限
    value_max: float | None = None                      # 取值范围上限
    unit: str = ""                                      # 单位
    description: str = ""                               # 说明文本
    examples: list[dict] = field(default_factory=list)  # 配置示例
    default_range: tuple[float, float] | None = None    # range 类型默认区间


# ---------------------------------------------------------------------------
# FACTOR_REGISTRY: 全量因子元数据常量字典
# ---------------------------------------------------------------------------


FACTOR_REGISTRY: dict[str, FactorMeta] = {
    # ── 技术面（7 个） ──
    "ma_trend": FactorMeta(
        factor_name="ma_trend",
        label="MA趋势打分",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=80,
        value_min=0,
        value_max=100,
        unit="分",
        description="基于均线排列程度、斜率和价格距离的综合打分，≥80 表示强势多头趋势",
        examples=[
            {"operator": ">=", "threshold": 80, "说明": "筛选趋势强度 ≥ 80 的强势股"},
        ],
    ),
    "ma_support": FactorMeta(
        factor_name="ma_support",
        label="均线支撑信号",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="价格回调至 20/60 日均线附近后企稳反弹的信号",
        examples=[
            {"说明": "筛选回调至 20 日或 60 日均线附近企稳反弹的个股"},
        ],
    ),
    "macd": FactorMeta(
        factor_name="macd",
        label="MACD金叉信号",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="DIF/DEA 零轴上方金叉 + 红柱放大 + DEA 向上的多头信号",
        examples=[
            {"说明": "筛选 MACD 零轴上方金叉且红柱放大的个股"},
        ],
    ),
    "boll": FactorMeta(
        factor_name="boll",
        label="布林带突破信号",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="股价站稳中轨、触碰上轨且布林带开口向上的突破信号",
        examples=[
            {"说明": "筛选连续 2 日站稳布林带中轨的个股"},
        ],
    ),
    "rsi": FactorMeta(
        factor_name="rsi",
        label="RSI强势信号",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(50, 80),
        value_min=0,
        value_max=100,
        description="RSI 处于强势区间且无超买背离，50-80 为适中强势区间",
        examples=[
            {"operator": "range", "threshold": [55, 75], "说明": "筛选 RSI 在 55-75 强势区间内的个股"},
        ],
    ),
    "dma": FactorMeta(
        factor_name="dma",
        label="DMA平行线差",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="DMA 线在 AMA 线上方，表示短期均线强于长期均线",
        examples=[
            {"说明": "筛选 DMA 线在 AMA 线上方的个股，表示短期趋势强于长期"},
        ],
    ),
    "breakout": FactorMeta(
        factor_name="breakout",
        label="形态突破",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="箱体突破/前期高点突破/下降趋势线突破，需量价确认（量比 ≥ 1.5 倍）",
        examples=[
            {"说明": "筛选放量突破箱体或前期高点的个股，量比 ≥ 1.5"},
        ],
    ),

    # ── 资金面（4 个） ──
    "turnover": FactorMeta(
        factor_name="turnover",
        label="换手率",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.RANGE,
        default_range=(3.0, 15.0),
        value_min=0,
        value_max=100,
        unit="%",
        description="换手率反映交易活跃度，3%-15% 为适中活跃区间",
        examples=[
            {"operator": "range", "threshold": [3.0, 15.0], "说明": "筛选换手率在 3%-15% 的适中活跃个股"},
        ],
    ),
    "money_flow": FactorMeta(
        factor_name="money_flow",
        label="主力资金净流入",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=80,
        value_min=0,
        value_max=100,
        description="主力资金净流入的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 80, "说明": "筛选主力资金净流入排名前 20% 的个股"},
        ],
    ),
    "large_order": FactorMeta(
        factor_name="large_order",
        label="大单成交占比",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=30,
        value_min=0,
        value_max=100,
        unit="%",
        description="大单成交额占总成交额的比例，>30% 表示主力资金活跃",
        examples=[
            {"operator": ">=", "threshold": 30, "说明": "筛选大单成交占比 ≥ 30% 的个股"},
        ],
    ),
    "volume_price": FactorMeta(
        factor_name="volume_price",
        label="日均成交额",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        description="近 20 日日均成交额的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选日均成交额排名前 30% 的个股，确保流动性充足"},
        ],
    ),

    # ── 基本面（6 个） ──
    "pe": FactorMeta(
        factor_name="pe",
        label="市盈率 TTM",
        category=FactorCategory.FUNDAMENTAL,
        threshold_type=ThresholdType.INDUSTRY_RELATIVE,
        default_threshold=1.0,
        value_min=0,
        value_max=5.0,
        description="市盈率的行业相对值（当前 PE / 行业中位数 PE）",
        examples=[
            {"operator": "<=", "threshold": 1.0, "说明": "筛选 PE 低于行业中位数的个股（相对低估）"},
        ],
    ),
    "pb": FactorMeta(
        factor_name="pb",
        label="市净率",
        category=FactorCategory.FUNDAMENTAL,
        threshold_type=ThresholdType.INDUSTRY_RELATIVE,
        default_threshold=1.0,
        value_min=0,
        value_max=5.0,
        description="市净率的行业相对值（当前 PB / 行业中位数 PB）",
        examples=[
            {"operator": "<=", "threshold": 1.0, "说明": "筛选 PB 低于行业中位数的个股（相对低估）"},
        ],
    ),
    "roe": FactorMeta(
        factor_name="roe",
        label="净资产收益率",
        category=FactorCategory.FUNDAMENTAL,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        description="ROE 的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选 ROE 排名前 30% 的高盈利能力个股"},
        ],
    ),
    "profit_growth": FactorMeta(
        factor_name="profit_growth",
        label="利润增长率",
        category=FactorCategory.FUNDAMENTAL,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        description="净利润同比增长率的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选利润增速排名前 30% 的高成长个股"},
        ],
    ),
    "market_cap": FactorMeta(
        factor_name="market_cap",
        label="总市值",
        category=FactorCategory.FUNDAMENTAL,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=30,
        value_min=0,
        value_max=100,
        description="总市值的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 30, "说明": "筛选总市值排名前 70% 的个股，排除微盘股"},
        ],
    ),
    "revenue_growth": FactorMeta(
        factor_name="revenue_growth",
        label="营收增长率",
        category=FactorCategory.FUNDAMENTAL,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        description="营业收入同比增长率的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选营收增速排名前 30% 的高成长个股"},
        ],
    ),

    # ── 板块面（2 个） ──
    "sector_rank": FactorMeta(
        factor_name="sector_rank",
        label="板块涨幅排名",
        category=FactorCategory.SECTOR,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=30,
        value_min=1,
        value_max=300,
        description="股票所属板块在全市场板块涨幅排名中的位次，≤30 表示处于强势板块前 30 名",
        examples=[
            {
                "operator": "<=",
                "threshold": 30,
                "说明": "筛选板块涨幅排名前 30 的个股",
                "数据来源": "DC/TI/TDX 可选",
                "板块类型": "INDUSTRY/CONCEPT/REGION/STYLE 可选",
            },
        ],
    ),
    "sector_trend": FactorMeta(
        factor_name="sector_trend",
        label="板块趋势",
        category=FactorCategory.SECTOR,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="股票所属板块是否处于多头趋势（板块指数短期均线在长期均线上方）",
        examples=[
            {
                "说明": "筛选处于多头趋势板块中的个股",
                "数据来源": "DC/TI/TDX 可选",
                "板块类型": "INDUSTRY/CONCEPT/REGION/STYLE 可选",
            },
        ],
    ),
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def get_factor_meta(factor_name: str) -> FactorMeta | None:
    """
    按因子名称查询元数据。

    Args:
        factor_name: 因子标识符，如 "ma_trend"

    Returns:
        FactorMeta 实例，未找到时返回 None
    """
    return FACTOR_REGISTRY.get(factor_name)


def get_factors_by_category(category: FactorCategory) -> list[FactorMeta]:
    """
    按类别筛选因子列表。

    Args:
        category: 因子类别枚举值

    Returns:
        该类别下所有因子的 FactorMeta 列表
    """
    return [
        meta
        for meta in FACTOR_REGISTRY.values()
        if meta.category == category
    ]
