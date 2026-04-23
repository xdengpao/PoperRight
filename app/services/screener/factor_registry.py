"""
因子元数据注册表（Factor Metadata Registry）

提供：
- ThresholdType: 因子阈值类型枚举
- FactorCategory: 因子类别枚举（含 CHIP、MARGIN、BOARD_HIT 新增类别）
- FactorMeta: 因子元数据冻结数据类
- FACTOR_REGISTRY: 全量因子元数据常量字典（52 个因子）
- get_factor_meta(): 按因子名称查询元数据
- get_factors_by_category(): 按类别筛选因子列表

对应需求：
- 需求 1：因子元数据注册表
- 需求 2：技术面因子阈值评估与优化
- 需求 3：资金面因子阈值评估与优化
- 需求 4：基本面因子阈值评估与优化
- 需求 6：板块面因子元数据定义
- 需求 12：技术面专业因子扩展（stk_factor_pro）
- 需求 13：筹码分析因子扩展（cyq_perf）
- 需求 14：两融数据因子扩展（margin_detail）
- 需求 15：增强资金流因子扩展（moneyflow_ths/dc）
- 需求 16：打板专题因子扩展（limit_list_d 等）
- 需求 17：指数专题因子扩展（index_dailybasic 等）
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
    """因子类别（需求 13.1, 14.1, 16.1, 21.4）"""
    TECHNICAL = "technical"
    MONEY_FLOW = "money_flow"
    FUNDAMENTAL = "fundamental"
    SECTOR = "sector"
    CHIP = "chip"           # 筹码面（需求 13.1）
    MARGIN = "margin"       # 两融面（需求 14.1）
    BOARD_HIT = "board_hit" # 打板面（需求 16.1）


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

    # ── 技术面专业因子（需求 12.1，stk_factor_pro，9 个） ──
    "kdj_k": FactorMeta(
        factor_name="kdj_k",
        label="KDJ-K值",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(20, 80),
        value_min=0,
        value_max=100,
        description="KDJ 指标中的 K 值，20-80 为常用区间，低于 20 超卖，高于 80 超买",
        examples=[
            {"operator": "range", "threshold": [20, 80], "说明": "筛选 KDJ-K 值在 20-80 区间内的个股"},
        ],
    ),
    "kdj_d": FactorMeta(
        factor_name="kdj_d",
        label="KDJ-D值",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(20, 80),
        value_min=0,
        value_max=100,
        description="KDJ 指标中的 D 值，20-80 为常用区间，低于 20 超卖，高于 80 超买",
        examples=[
            {"operator": "range", "threshold": [20, 80], "说明": "筛选 KDJ-D 值在 20-80 区间内的个股"},
        ],
    ),
    "kdj_j": FactorMeta(
        factor_name="kdj_j",
        label="KDJ-J值",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(0, 100),
        value_min=-50,
        value_max=150,
        description="KDJ 指标中的 J 值，0-100 为常用区间，可超出 [0, 100] 范围",
        examples=[
            {"operator": "range", "threshold": [0, 100], "说明": "筛选 KDJ-J 值在 0-100 区间内的个股"},
        ],
    ),
    "cci": FactorMeta(
        factor_name="cci",
        label="CCI顺势指标",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=100,
        value_min=-300,
        value_max=300,
        description="CCI 顺势指标，>100 为超买区间，<-100 为超卖区间",
        examples=[
            {"operator": ">=", "threshold": 100, "说明": "筛选 CCI ≥ 100 的强势个股"},
        ],
    ),
    "wr": FactorMeta(
        factor_name="wr",
        label="威廉指标",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(0, 20),
        value_min=0,
        value_max=100,
        description="威廉指标（WR），WR 越低表示越超买，0-20 为超买区间",
        examples=[
            {"operator": "range", "threshold": [0, 20], "说明": "筛选 WR 在 0-20 超买区间的个股"},
        ],
    ),
    "trix": FactorMeta(
        factor_name="trix",
        label="TRIX三重指数平滑",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="TRIX 上穿信号线为多头信号",
        examples=[
            {"说明": "筛选 TRIX 上穿信号线的个股，表示中长期趋势转多"},
        ],
    ),
    "bias": FactorMeta(
        factor_name="bias",
        label="乖离率",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(-5, 5),
        unit="%",
        description="乖离率（BIAS），衡量股价偏离均线的程度，-5% 到 5% 为正常区间",
        examples=[
            {"operator": "range", "threshold": [-5, 5], "说明": "筛选乖离率在 -5% 到 5% 正常区间的个股"},
        ],
    ),
    "psy": FactorMeta(
        factor_name="psy",
        label="心理线指标",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.RANGE,
        default_range=(40, 75),
        value_min=0,
        value_max=100,
        unit="%",
        description="心理线指标（PSY），反映投资者心理状态，40-75 为适中区间",
        examples=[
            {"operator": "range", "threshold": [40, 75], "说明": "筛选心理线在 40-75 适中区间的个股"},
        ],
    ),
    "obv_signal": FactorMeta(
        factor_name="obv_signal",
        label="OBV能量潮信号",
        category=FactorCategory.TECHNICAL,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="OBV 趋势向上为多头信号，表示量能配合价格上涨",
        examples=[
            {"说明": "筛选 OBV 趋势向上的个股，表示量能配合价格上涨"},
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

    # ── 增强资金面因子（需求 15.1，moneyflow_ths/dc，5 个） ──
    "super_large_net_inflow": FactorMeta(
        factor_name="super_large_net_inflow",
        label="超大单净流入",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=80,
        value_min=0,
        value_max=100,
        description="超大单（≥100万）净流入额的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 80, "说明": "筛选超大单净流入排名前 20% 的个股"},
        ],
    ),
    "large_net_inflow": FactorMeta(
        factor_name="large_net_inflow",
        label="大单净流入",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=75,
        value_min=0,
        value_max=100,
        description="大单（20-100万）净流入额的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 75, "说明": "筛选大单净流入排名前 25% 的个股"},
        ],
    ),
    "small_net_outflow": FactorMeta(
        factor_name="small_net_outflow",
        label="小单净流出",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="小单净流出为 True 时表示散户在卖出、主力在吸筹",
        examples=[
            {"说明": "筛选小单净流出的个股，表示散户卖出、主力吸筹"},
        ],
    ),
    "money_flow_strength": FactorMeta(
        factor_name="money_flow_strength",
        label="资金流强度综合评分",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        unit="分",
        description="基于超大单、大单、中单、小单净流入的综合评分",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选资金流强度综合评分 ≥ 70 的个股"},
        ],
    ),
    "net_inflow_rate": FactorMeta(
        factor_name="net_inflow_rate",
        label="净流入占比",
        category=FactorCategory.MONEY_FLOW,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=5,
        unit="%",
        description="主力净流入额占当日总成交额的比例",
        examples=[
            {"operator": ">=", "threshold": 5, "说明": "筛选净流入占比 ≥ 5% 的个股"},
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

    # ── 指数专题因子（需求 17.1，index_dailybasic/idx_factor_pro，4 个） ──
    "index_pe": FactorMeta(
        factor_name="index_pe",
        label="指数市盈率",
        category=FactorCategory.SECTOR,
        threshold_type=ThresholdType.RANGE,
        default_range=(10, 25),
        description="所属指数的市盈率，用于判断市场估值水平",
        examples=[
            {"operator": "range", "threshold": [10, 25], "说明": "筛选所属指数 PE 在 10-25 合理区间的个股"},
        ],
    ),
    "index_turnover": FactorMeta(
        factor_name="index_turnover",
        label="指数换手率",
        category=FactorCategory.SECTOR,
        threshold_type=ThresholdType.RANGE,
        default_range=(0.5, 3.0),
        unit="%",
        description="所属指数的换手率，反映市场活跃度",
        examples=[
            {"operator": "range", "threshold": [0.5, 3.0], "说明": "筛选所属指数换手率在 0.5%-3.0% 的个股"},
        ],
    ),
    "index_ma_trend": FactorMeta(
        factor_name="index_ma_trend",
        label="指数均线趋势",
        category=FactorCategory.SECTOR,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="所属指数短期均线在长期均线上方为 True",
        examples=[
            {"说明": "筛选所属指数处于多头趋势的个股"},
        ],
    ),
    "index_vol_ratio": FactorMeta(
        factor_name="index_vol_ratio",
        label="指数量比",
        category=FactorCategory.SECTOR,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=1.0,
        description="所属指数的量比，> 1 表示放量",
        examples=[
            {"operator": ">=", "threshold": 1.0, "说明": "筛选所属指数量比 ≥ 1.0 的个股"},
        ],
    ),

    # ── 筹码面（需求 13.2，cyq_perf，6 个） ──
    "chip_winner_rate": FactorMeta(
        factor_name="chip_winner_rate",
        label="获利比例",
        category=FactorCategory.CHIP,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=50,
        value_min=0,
        value_max=100,
        unit="%",
        description="当前价格下的获利筹码占比",
        examples=[
            {"operator": ">=", "threshold": 50, "说明": "筛选获利比例排名前 50% 的个股"},
        ],
    ),
    "chip_cost_5pct": FactorMeta(
        factor_name="chip_cost_5pct",
        label="5%成本集中度",
        category=FactorCategory.CHIP,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=10,
        unit="%",
        description="5%筹码集中度，值越小表示筹码越集中",
        examples=[
            {"operator": "<=", "threshold": 10, "说明": "筛选 5% 成本集中度 ≤ 10% 的筹码集中个股"},
        ],
    ),
    "chip_cost_15pct": FactorMeta(
        factor_name="chip_cost_15pct",
        label="15%成本集中度",
        category=FactorCategory.CHIP,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=20,
        unit="%",
        description="15%筹码集中度",
        examples=[
            {"operator": "<=", "threshold": 20, "说明": "筛选 15% 成本集中度 ≤ 20% 的个股"},
        ],
    ),
    "chip_cost_50pct": FactorMeta(
        factor_name="chip_cost_50pct",
        label="50%成本集中度",
        category=FactorCategory.CHIP,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=30,
        unit="%",
        description="50%筹码集中度",
        examples=[
            {"operator": "<=", "threshold": 30, "说明": "筛选 50% 成本集中度 ≤ 30% 的个股"},
        ],
    ),
    "chip_weight_avg": FactorMeta(
        factor_name="chip_weight_avg",
        label="筹码加权平均成本",
        category=FactorCategory.CHIP,
        threshold_type=ThresholdType.INDUSTRY_RELATIVE,
        default_threshold=1.0,
        description="加权平均成本与当前价格的比值，< 1 表示当前价格低于平均成本",
        examples=[
            {"operator": "<=", "threshold": 1.0, "说明": "筛选当前价格低于筹码加权平均成本的个股"},
        ],
    ),
    "chip_concentration": FactorMeta(
        factor_name="chip_concentration",
        label="筹码集中度综合评分",
        category=FactorCategory.CHIP,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        description="基于 cost_5pct/cost_15pct/cost_50pct 综合计算的筹码集中度评分，值越高表示筹码越集中",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选筹码集中度综合评分排名前 30% 的个股"},
        ],
    ),

    # ── 两融面（需求 14.2，margin_detail，4 个） ──
    "rzye_change": FactorMeta(
        factor_name="rzye_change",
        label="融资余额变化率",
        category=FactorCategory.MARGIN,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=70,
        value_min=0,
        value_max=100,
        description="融资余额日环比变化率的全市场百分位排名，值越高表示融资买入意愿越强",
        examples=[
            {"operator": ">=", "threshold": 70, "说明": "筛选融资余额变化率排名前 30% 的个股"},
        ],
    ),
    "rqye_ratio": FactorMeta(
        factor_name="rqye_ratio",
        label="融券余额占比",
        category=FactorCategory.MARGIN,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=5,
        unit="%",
        description="融券余额占流通市值的比例，过高表示做空压力大",
        examples=[
            {"operator": "<=", "threshold": 5, "说明": "筛选融券余额占比 ≤ 5% 的个股，排除做空压力大的标的"},
        ],
    ),
    "rzrq_balance_trend": FactorMeta(
        factor_name="rzrq_balance_trend",
        label="两融余额趋势",
        category=FactorCategory.MARGIN,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="近 5 日融资余额连续增加为 True，表示资金持续流入",
        examples=[
            {"说明": "筛选近 5 日融资余额连续增加的个股"},
        ],
    ),
    "margin_net_buy": FactorMeta(
        factor_name="margin_net_buy",
        label="融资净买入额",
        category=FactorCategory.MARGIN,
        threshold_type=ThresholdType.PERCENTILE,
        default_threshold=75,
        value_min=0,
        value_max=100,
        description="当日融资净买入额的全市场百分位排名",
        examples=[
            {"operator": ">=", "threshold": 75, "说明": "筛选融资净买入额排名前 25% 的个股"},
        ],
    ),

    # ── 打板面（需求 16.2，limit_list/limit_step/top_list，5 个） ──
    "limit_up_count": FactorMeta(
        factor_name="limit_up_count",
        label="近期涨停次数",
        category=FactorCategory.BOARD_HIT,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=1,
        value_min=0,
        value_max=20,
        description="近 10 个交易日内涨停次数",
        examples=[
            {"operator": ">=", "threshold": 1, "说明": "筛选近 10 日内至少涨停 1 次的个股"},
        ],
    ),
    "limit_up_streak": FactorMeta(
        factor_name="limit_up_streak",
        label="连板天数",
        category=FactorCategory.BOARD_HIT,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=2,
        value_min=0,
        value_max=15,
        description="当前连续涨停天数，0 表示非连板",
        examples=[
            {"operator": ">=", "threshold": 2, "说明": "筛选连板天数 ≥ 2 的个股"},
        ],
    ),
    "limit_up_open_pct": FactorMeta(
        factor_name="limit_up_open_pct",
        label="涨停封板率",
        category=FactorCategory.BOARD_HIT,
        threshold_type=ThresholdType.ABSOLUTE,
        default_threshold=80,
        value_min=0,
        value_max=100,
        unit="%",
        description="涨停后封板时间占比，越高表示封板越坚决",
        examples=[
            {"operator": ">=", "threshold": 80, "说明": "筛选涨停封板率 ≥ 80% 的个股"},
        ],
    ),
    "dragon_tiger_net_buy": FactorMeta(
        factor_name="dragon_tiger_net_buy",
        label="龙虎榜净买入",
        category=FactorCategory.BOARD_HIT,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="近 3 日出现在龙虎榜且机构净买入为正",
        examples=[
            {"说明": "筛选近 3 日龙虎榜机构净买入为正的个股"},
        ],
    ),
    "first_limit_up": FactorMeta(
        factor_name="first_limit_up",
        label="首板涨停标记",
        category=FactorCategory.BOARD_HIT,
        threshold_type=ThresholdType.BOOLEAN,
        default_threshold=None,
        description="当日为首次涨停（非连板），适合打首板策略",
        examples=[
            {"说明": "筛选当日首次涨停的个股，适合打首板策略"},
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
