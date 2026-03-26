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
class ScreenItem:
    """单条选股结果"""
    symbol: str
    ref_buy_price: Decimal          # 买入参考价
    trend_score: float              # 趋势强度评分 0-100
    risk_level: RiskLevel           # 风险等级
    signals: dict = field(default_factory=dict)  # 触发的信号详情


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
