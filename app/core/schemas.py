"""
核心业务层数据类（Python dataclass）

本模块定义系统各层之间传递的纯数据对象，不依赖 ORM 或 Pydantic。
所有金额字段使用 Decimal，枚举类型使用 enum.Enum。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """个股风险等级"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MarketRiskLevel(str, Enum):
    """大盘风险等级（用于大盘风控状态）"""
    NORMAL = "NORMAL"          # 正常，趋势打分阈值 80
    CAUTION = "CAUTION"        # 警戒，跌破 20 日均线，阈值提升至 90
    DANGER = "DANGER"          # 危险，跌破 60 日均线，禁止买入信号


class OrderDirection(str, Enum):
    """委托方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """委托类型"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    CONDITION = "CONDITION"


class OrderStatus(str, Enum):
    """委托状态"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TradeMode(str, Enum):
    """交易模式"""
    LIVE = "LIVE"
    PAPER = "PAPER"


class ScreenType(str, Enum):
    """选股类型"""
    EOD = "EOD"
    REALTIME = "REALTIME"


class ConditionTriggerType(str, Enum):
    """条件单触发类型"""
    BREAKOUT_BUY = "BREAKOUT_BUY"       # 突破买入
    STOP_LOSS = "STOP_LOSS"             # 止损卖出
    TAKE_PROFIT = "TAKE_PROFIT"         # 止盈卖出
    TRAILING_STOP = "TRAILING_STOP"     # 移动止盈


class AlertType(str, Enum):
    """预警类型"""
    SCREEN_RESULT = "SCREEN_RESULT"     # 选股结果推送
    STOP_LOSS = "STOP_LOSS"             # 止损预警
    PRICE_THRESHOLD = "PRICE_THRESHOLD" # 价格阈值预警
    MARKET_RISK = "MARKET_RISK"         # 大盘风险预警
    SYSTEM = "SYSTEM"                   # 系统告警


class SignalCategory(str, Enum):
    """选股信号分类（需求 21.15）"""
    MA_TREND = "MA_TREND"               # 均线趋势信号
    MACD = "MACD"                       # MACD 信号
    BOLL = "BOLL"                       # 布林带信号
    RSI = "RSI"                         # RSI 信号
    DMA = "DMA"                         # DMA 信号
    BREAKOUT = "BREAKOUT"               # 形态突破信号
    CAPITAL_INFLOW = "CAPITAL_INFLOW"   # 资金流入信号
    LARGE_ORDER = "LARGE_ORDER"         # 大单活跃信号
    MA_SUPPORT = "MA_SUPPORT"           # 均线支撑信号
    SECTOR_STRONG = "SECTOR_STRONG"     # 板块强势信号


# ---------------------------------------------------------------------------
# 行情数据类
# ---------------------------------------------------------------------------


@dataclass
class KlineBar:
    """K线数据传输对象（业务层，从 app.models.kline.KlineBar 重导出并扩展）"""
    time: datetime
    symbol: str
    freq: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal
    turnover: Decimal       # 换手率 %
    vol_ratio: Decimal      # 量比
    limit_up: Decimal | None = None
    limit_down: Decimal | None = None
    adj_type: int = 0       # 0=不复权 1=前复权 2=后复权


# ---------------------------------------------------------------------------
# 选股数据类
# ---------------------------------------------------------------------------


@dataclass
class SignalDetail:
    """单条信号详情（需求 21.15）"""
    category: SignalCategory        # 信号分类
    label: str                      # 信号标签（如"多头排列"、"MACD 金叉"）
    is_fake_breakout: bool = False  # 是否为假突破标记


@dataclass
class ScreenItem:
    """单条选股结果"""
    symbol: str
    ref_buy_price: Decimal          # 买入参考价
    trend_score: float              # 趋势强度评分 0-100
    risk_level: RiskLevel           # 风险等级
    signals: list[SignalDetail] = field(default_factory=list)  # 触发的信号详情
    has_fake_breakout: bool = False  # 是否存在假突破信号


@dataclass
class ScreenResult:
    """选股结果集合"""
    strategy_id: UUID
    screen_time: datetime
    screen_type: ScreenType
    items: list[ScreenItem] = field(default_factory=list)
    is_complete: bool = True        # False 表示超时返回的不完整结果


# ---------------------------------------------------------------------------
# 策略配置数据类
# ---------------------------------------------------------------------------


@dataclass
class FactorCondition:
    """单个因子条件"""
    factor_name: str                # 因子名称，如 "ma_trend"、"macd"、"volume_price"
    operator: str                   # 比较运算符：">", "<", ">=", "<=", "==", "cross_up", "cross_down"
    threshold: float | None = None  # 阈值（数值型因子）
    params: dict = field(default_factory=dict)  # 因子专属参数


@dataclass
class StrategyConfig:
    """选股策略配置"""
    factors: list[FactorCondition] = field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"         # 因子间逻辑运算
    weights: dict[str, float] = field(default_factory=dict)  # 因子权重
    ma_periods: list[int] = field(default_factory=lambda: [5, 10, 20, 60, 120, 250])
    indicator_params: dict = field(default_factory=dict)     # 指标参数（MACD/BOLL/RSI 等）

    def to_dict(self) -> dict:
        """序列化为可 JSON 存储的字典"""
        return {
            "factors": [
                {
                    "factor_name": f.factor_name,
                    "operator": f.operator,
                    "threshold": f.threshold,
                    "params": f.params,
                }
                for f in self.factors
            ],
            "logic": self.logic,
            "weights": self.weights,
            "ma_periods": self.ma_periods,
            "indicator_params": self.indicator_params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyConfig":
        """从字典反序列化"""
        factors = [
            FactorCondition(
                factor_name=f["factor_name"],
                operator=f["operator"],
                threshold=f.get("threshold"),
                params=f.get("params", {}),
            )
            for f in data.get("factors", [])
        ]
        return cls(
            factors=factors,
            logic=data.get("logic", "AND"),
            weights=data.get("weights", {}),
            ma_periods=data.get("ma_periods", [5, 10, 20, 60, 120, 250]),
            indicator_params=data.get("indicator_params", {}),
        )


@dataclass
class MaTrendConfig:
    """均线趋势配置（需求 3 / 21.8）"""
    ma_periods: list[int] = field(default_factory=lambda: [5, 10, 20, 60, 120])
    slope_threshold: float = 0.0            # 多头排列斜率阈值
    trend_score_threshold: int = 80         # 趋势打分纳入初选池阈值
    support_ma_lines: list[int] = field(default_factory=lambda: [20, 60])

    def to_dict(self) -> dict:
        return {
            "ma_periods": self.ma_periods,
            "slope_threshold": self.slope_threshold,
            "trend_score_threshold": self.trend_score_threshold,
            "support_ma_lines": self.support_ma_lines,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaTrendConfig":
        return cls(
            ma_periods=data.get("ma_periods", [5, 10, 20, 60, 120]),
            slope_threshold=data.get("slope_threshold", 0.0),
            trend_score_threshold=data.get("trend_score_threshold", 80),
            support_ma_lines=data.get("support_ma_lines", [20, 60]),
        )


@dataclass
class IndicatorParamsConfig:
    """技术指标参数配置（需求 4 / 21.9）"""
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    boll_period: int = 20
    boll_std_dev: float = 2.0
    rsi_period: int = 14
    rsi_lower: int = 50
    rsi_upper: int = 80
    dma_short: int = 10
    dma_long: int = 50

    def to_dict(self) -> dict:
        return {
            "macd_fast": self.macd_fast,
            "macd_slow": self.macd_slow,
            "macd_signal": self.macd_signal,
            "boll_period": self.boll_period,
            "boll_std_dev": self.boll_std_dev,
            "rsi_period": self.rsi_period,
            "rsi_lower": self.rsi_lower,
            "rsi_upper": self.rsi_upper,
            "dma_short": self.dma_short,
            "dma_long": self.dma_long,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndicatorParamsConfig":
        return cls(
            macd_fast=data.get("macd_fast", 12),
            macd_slow=data.get("macd_slow", 26),
            macd_signal=data.get("macd_signal", 9),
            boll_period=data.get("boll_period", 20),
            boll_std_dev=data.get("boll_std_dev", 2.0),
            rsi_period=data.get("rsi_period", 14),
            rsi_lower=data.get("rsi_lower", 50),
            rsi_upper=data.get("rsi_upper", 80),
            dma_short=data.get("dma_short", 10),
            dma_long=data.get("dma_long", 50),
        )


@dataclass
class BreakoutConfig:
    """形态突破配置（需求 5 / 21.10）"""
    box_breakout: bool = True               # 箱体突破
    high_breakout: bool = True              # 前期高点突破
    trendline_breakout: bool = True         # 下降趋势线突破
    volume_ratio_threshold: float = 1.5     # 量比倍数阈值
    confirm_days: int = 1                   # 站稳确认天数

    def to_dict(self) -> dict:
        return {
            "box_breakout": self.box_breakout,
            "high_breakout": self.high_breakout,
            "trendline_breakout": self.trendline_breakout,
            "volume_ratio_threshold": self.volume_ratio_threshold,
            "confirm_days": self.confirm_days,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BreakoutConfig":
        return cls(
            box_breakout=data.get("box_breakout", True),
            high_breakout=data.get("high_breakout", True),
            trendline_breakout=data.get("trendline_breakout", True),
            volume_ratio_threshold=data.get("volume_ratio_threshold", 1.5),
            confirm_days=data.get("confirm_days", 1),
        )


@dataclass
class VolumePriceConfig:
    """量价资金筛选配置（需求 6 / 21.11）"""
    turnover_rate_min: float = 3.0          # 换手率下限 %
    turnover_rate_max: float = 15.0         # 换手率上限 %
    main_flow_threshold: float = 1000.0     # 主力净流入阈值（万元）
    main_flow_days: int = 2                 # 连续净流入天数
    large_order_ratio: float = 30.0         # 大单占比阈值 %
    min_daily_amount: float = 5000.0        # 日均成交额下限（万元）
    sector_rank_top: int = 30               # 板块排名范围

    def to_dict(self) -> dict:
        return {
            "turnover_rate_min": self.turnover_rate_min,
            "turnover_rate_max": self.turnover_rate_max,
            "main_flow_threshold": self.main_flow_threshold,
            "main_flow_days": self.main_flow_days,
            "large_order_ratio": self.large_order_ratio,
            "min_daily_amount": self.min_daily_amount,
            "sector_rank_top": self.sector_rank_top,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VolumePriceConfig":
        return cls(
            turnover_rate_min=data.get("turnover_rate_min", 3.0),
            turnover_rate_max=data.get("turnover_rate_max", 15.0),
            main_flow_threshold=data.get("main_flow_threshold", 1000.0),
            main_flow_days=data.get("main_flow_days", 2),
            large_order_ratio=data.get("large_order_ratio", 30.0),
            min_daily_amount=data.get("min_daily_amount", 5000.0),
            sector_rank_top=data.get("sector_rank_top", 30),
        )


@dataclass
class SectorScreenConfig:
    """板块筛选配置（需求 5.1）"""
    sector_data_source: str = "DC"       # DC（东方财富）/ TI（同花顺）/ TDX（通达信）
    sector_type: str = "CONCEPT"         # INDUSTRY / CONCEPT / REGION / STYLE
    sector_period: int = 5               # 涨幅计算周期（天）
    sector_top_n: int = 30               # 排名阈值

    def to_dict(self) -> dict:
        return {
            "sector_data_source": self.sector_data_source,
            "sector_type": self.sector_type,
            "sector_period": self.sector_period,
            "sector_top_n": self.sector_top_n,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SectorScreenConfig":
        return cls(
            sector_data_source=data.get("sector_data_source", "DC"),
            sector_type=data.get("sector_type", "CONCEPT"),
            sector_period=data.get("sector_period", 5),
            sector_top_n=data.get("sector_top_n", 30),
        )


@dataclass
class StrategyConfig:
    """选股策略配置"""
    factors: list[FactorCondition] = field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"         # 因子间逻辑运算
    weights: dict[str, float] = field(default_factory=dict)  # 因子权重
    ma_periods: list[int] = field(default_factory=lambda: [5, 10, 20, 60, 120, 250])
    indicator_params: IndicatorParamsConfig = field(default_factory=IndicatorParamsConfig)
    ma_trend: MaTrendConfig = field(default_factory=MaTrendConfig)
    breakout: BreakoutConfig = field(default_factory=BreakoutConfig)
    volume_price: VolumePriceConfig = field(default_factory=VolumePriceConfig)
    sector_config: SectorScreenConfig = field(default_factory=SectorScreenConfig)

    def to_dict(self) -> dict:
        """序列化为可 JSON 存储的字典"""
        # indicator_params: support both new typed config and legacy plain dict
        if isinstance(self.indicator_params, IndicatorParamsConfig):
            ip = self.indicator_params.to_dict()
        else:
            ip = self.indicator_params  # type: ignore[assignment]
        return {
            "factors": [
                {
                    "factor_name": f.factor_name,
                    "operator": f.operator,
                    "threshold": f.threshold,
                    "params": f.params,
                }
                for f in self.factors
            ],
            "logic": self.logic,
            "weights": self.weights,
            "ma_periods": self.ma_periods,
            "indicator_params": ip,
            "ma_trend": self.ma_trend.to_dict(),
            "breakout": self.breakout.to_dict(),
            "volume_price": self.volume_price.to_dict(),
            "sector_config": self.sector_config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyConfig":
        """从字典反序列化（向后兼容旧配置）"""
        factors = [
            FactorCondition(
                factor_name=f["factor_name"],
                operator=f["operator"],
                threshold=f.get("threshold"),
                params=f.get("params", {}),
            )
            for f in data.get("factors", [])
        ]
        # indicator_params: accept both plain dict (legacy) and structured dict
        raw_ip = data.get("indicator_params", {})
        indicator_params = IndicatorParamsConfig.from_dict(raw_ip) if isinstance(raw_ip, dict) else IndicatorParamsConfig()

        raw_ma = data.get("ma_trend")
        ma_trend = MaTrendConfig.from_dict(raw_ma) if isinstance(raw_ma, dict) else MaTrendConfig()

        raw_bo = data.get("breakout")
        breakout = BreakoutConfig.from_dict(raw_bo) if isinstance(raw_bo, dict) else BreakoutConfig()

        raw_vp = data.get("volume_price")
        volume_price = VolumePriceConfig.from_dict(raw_vp) if isinstance(raw_vp, dict) else VolumePriceConfig()

        raw_sc = data.get("sector_config")
        sector_config = SectorScreenConfig.from_dict(raw_sc) if isinstance(raw_sc, dict) else SectorScreenConfig()

        return cls(
            factors=factors,
            logic=data.get("logic", "AND"),
            weights=data.get("weights", {}),
            ma_periods=data.get("ma_periods", [5, 10, 20, 60, 120, 250]),
            indicator_params=indicator_params,
            ma_trend=ma_trend,
            breakout=breakout,
            volume_price=volume_price,
            sector_config=sector_config,
        )


# ---------------------------------------------------------------------------
# 风控数据类
# ---------------------------------------------------------------------------


@dataclass
class RiskCheckResult:
    """风控校验结果"""
    passed: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# 回测数据类
# ---------------------------------------------------------------------------


@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_config: StrategyConfig
    start_date: date
    end_date: date
    initial_capital: Decimal = Decimal("1000000")   # 初始资金，默认 100 万
    commission_buy: Decimal = Decimal("0.0003")     # 买入手续费率
    commission_sell: Decimal = Decimal("0.0013")    # 卖出手续费率（含印花税）
    slippage: Decimal = Decimal("0.001")            # 滑点
    max_position_pct: float = 0.15                  # 单股最大仓位比例
    max_sector_pct: float = 0.30                    # 单板块最大仓位比例
    max_holdings: int = 10                          # 最大同时持仓数量
    stop_loss_pct: float = 0.08                     # 固定止损阈值
    trailing_stop_pct: float = 0.05                 # 移动止盈回撤阈值
    max_holding_days: int = 20                      # 最大持仓交易日数
    allocation_mode: str = "equal"                  # 资金分配模式："equal" | "score_weighted"
    enable_market_risk: bool = True                 # 是否启用大盘风控模拟
    trend_stop_ma: int = 20                         # 趋势破位均线周期
    enabled_modules: list[str] | None = None        # 启用的选股模块列表
    raw_config: dict = field(default_factory=dict)  # 原始策略配置字典（含模块参数）
    exit_conditions: ExitConditionConfig | None = None  # 自定义平仓条件配置


@dataclass
class BacktestResult:
    """回测绩效结果（需求 12.2：9 项绩效指标）"""
    annual_return: float        # 年化收益率
    total_return: float         # 累计收益率
    win_rate: float             # 胜率 [0, 1]
    profit_loss_ratio: float    # 盈亏比
    max_drawdown: float         # 最大回撤 [0, 1]
    sharpe_ratio: float         # 夏普比率
    calmar_ratio: float         # 卡玛比率
    total_trades: int           # 总交易次数
    avg_holding_days: float     # 平均持仓天数
    equity_curve: list[tuple[date, float]] = field(default_factory=list)  # 净值曲线
    trade_records: list[dict] = field(default_factory=list)               # 交易记录


# ---------------------------------------------------------------------------
# 持仓与交易数据类
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """持仓（业务层，含实时计算字段）"""
    symbol: str
    quantity: int
    cost_price: Decimal
    current_price: Decimal
    market_value: Decimal       # 市值 = current_price × quantity
    pnl: Decimal                # 盈亏金额 = (current_price - cost_price) × quantity
    pnl_pct: float              # 盈亏比例 = pnl / (cost_price × quantity)
    weight: float               # 仓位占比（占总资产百分比）
    mode: TradeMode = TradeMode.LIVE

    @classmethod
    def from_cost(
        cls,
        symbol: str,
        quantity: int,
        cost_price: Decimal,
        current_price: Decimal,
        total_assets: Decimal,
        mode: TradeMode = TradeMode.LIVE,
    ) -> "Position":
        """根据成本价和当前价计算持仓各字段"""
        market_value = current_price * quantity
        pnl = (current_price - cost_price) * quantity
        cost_basis = cost_price * quantity
        pnl_pct = float(pnl / cost_basis) if cost_basis else 0.0
        weight = float(market_value / total_assets) if total_assets else 0.0
        return cls(
            symbol=symbol,
            quantity=quantity,
            cost_price=cost_price,
            current_price=current_price,
            market_value=market_value,
            pnl=pnl,
            pnl_pct=pnl_pct,
            weight=weight,
            mode=mode,
        )


@dataclass
class OrderRequest:
    """委托请求"""
    symbol: str
    direction: OrderDirection
    order_type: OrderType
    quantity: int
    price: Decimal | None = None            # MARKET 单可为 None
    stop_loss: Decimal | None = None        # 止损价
    take_profit: Decimal | None = None      # 止盈价
    mode: TradeMode = TradeMode.LIVE


@dataclass
class OrderResponse:
    """委托响应"""
    order_id: str
    symbol: str
    direction: OrderDirection
    order_type: OrderType
    quantity: int
    price: Decimal | None
    status: OrderStatus
    broker_order_id: str | None = None
    submitted_at: datetime | None = None
    message: str | None = None              # 拒绝原因或备注


# ---------------------------------------------------------------------------
# 条件单数据类
# ---------------------------------------------------------------------------


@dataclass
class ConditionOrder:
    """条件单（需求 14.2）"""
    symbol: str
    trigger_type: ConditionTriggerType
    trigger_price: Decimal                  # 触发价格
    order_request: OrderRequest             # 触发后提交的委托
    trailing_pct: float | None = None       # 移动止盈回撤比例（仅 TRAILING_STOP 使用）
    peak_price: Decimal | None = None       # 持仓期间最高价（移动止盈用）
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 预警数据类
# ---------------------------------------------------------------------------


@dataclass
class AlertConfig:
    """用户预警阈值配置（需求 8.1, 8.2）"""
    user_id: str
    alert_type: AlertType
    symbol: str | None = None               # None 表示全局预警
    price_above: Decimal | None = None      # 价格高于阈值触发
    price_below: Decimal | None = None      # 价格低于阈值触发
    pnl_pct_below: float | None = None      # 亏损比例触发（止损预警）
    is_active: bool = True
    extra: dict = field(default_factory=dict)  # 扩展参数


@dataclass
class Alert:
    """预警消息"""
    user_id: str
    alert_type: AlertType
    title: str
    message: str
    symbol: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 自定义平仓条件数据类
# ---------------------------------------------------------------------------

VALID_FREQS = {"daily", "1min", "5min", "15min", "30min", "60min"}

VALID_INDICATORS = {
    "ma", "macd_dif", "macd_dea", "macd_histogram",
    "boll_upper", "boll_middle", "boll_lower",
    "rsi", "dma", "ama", "close", "volume", "turnover",
}

VALID_OPERATORS = {">", "<", ">=", "<=", "cross_up", "cross_down"}

VALID_BASE_FIELDS = {
    "entry_price", "highest_price", "lowest_price",
    "prev_close", "prev_high", "prev_low",
    "today_open",
    "prev_bar_open", "prev_bar_high", "prev_bar_low", "prev_bar_close",
    "ma_volume",
}


@dataclass
class ExitCondition:
    """单条自定义平仓条件"""
    freq: str                          # 数据源频率："daily" | "1min" | "5min" | "15min" | "30min" | "60min"
    indicator: str                     # 指标名称
    operator: str                      # 比较运算符
    threshold: float | None = None     # 数值阈值（数值比较时使用）
    cross_target: str | None = None    # 交叉目标指标（cross_up/cross_down 时使用）
    params: dict = field(default_factory=dict)  # 指标参数（如 {"period": 10}）
    threshold_mode: str = "absolute"   # 阈值模式："absolute" | "relative"
    base_field: str | None = None      # 相对值基准字段（relative 模式时使用）
    factor: float | None = None        # 乘数因子（relative 模式时使用）

    def to_dict(self) -> dict:
        return {
            "freq": self.freq,
            "indicator": self.indicator,
            "operator": self.operator,
            "threshold": self.threshold,
            "cross_target": self.cross_target,
            "params": self.params,
            "threshold_mode": self.threshold_mode,
            "base_field": self.base_field,
            "factor": self.factor,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExitCondition":
        freq = data["freq"]
        # 向后兼容：旧版 "minute" 映射为 "1min"
        if freq == "minute":
            freq = "1min"
        return cls(
            freq=freq,
            indicator=data["indicator"],
            operator=data["operator"],
            threshold=data.get("threshold"),
            cross_target=data.get("cross_target"),
            params=data.get("params", {}),
            threshold_mode=data.get("threshold_mode", "absolute"),
            base_field=data.get("base_field"),
            factor=data.get("factor"),
        )


@dataclass
class ExitConditionConfig:
    """自定义平仓条件配置"""
    conditions: list[ExitCondition] = field(default_factory=list)
    logic: str = "AND"  # "AND" | "OR"

    def to_dict(self) -> dict:
        return {
            "conditions": [c.to_dict() for c in self.conditions],
            "logic": self.logic,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExitConditionConfig":
        conditions = [
            ExitCondition.from_dict(c)
            for c in data.get("conditions", [])
        ]
        return cls(
            conditions=conditions,
            logic=data.get("logic", "AND"),
        )


@dataclass
class HoldingContext:
    """持仓上下文，用于相对值阈值的动态解析。"""
    entry_price: float          # 买入价
    highest_price: float        # 买入后至当前交易日的最高收盘价
    lowest_price: float         # 买入后至当前交易日的最低收盘价
    entry_bar_index: int        # 买入时的 bar 索引
