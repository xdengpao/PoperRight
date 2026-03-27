"""
交易执行服务 — 券商接口对接

实现需求 14.3 / 14.4 / 14.5：
- 券商交易 API 客户端（委托/撤单/查询）
- 实盘/模拟盘模式切换，两种模式下交易流程完全一致
- 交易指令加密传输（SSL）
- 非交易时段（9:25-15:00 之外）委托拒绝
"""

from __future__ import annotations

import abc
import ssl
import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import Callable

from app.core.schemas import (
    ConditionOrder,
    ConditionTriggerType,
    OrderDirection,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    ScreenItem,
    TradeMode,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

TRADING_START = time(9, 25)
TRADING_END = time(15, 0)


# ---------------------------------------------------------------------------
# 券商 API 客户端（抽象 + 模拟实现）
# ---------------------------------------------------------------------------


class BrokerClient(abc.ABC):
    """券商交易 API 抽象基类。

    所有通信应通过 SSL 加密通道进行（需求 14.4）。
    """

    @abc.abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResponse:
        """提交委托至券商。"""

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> dict:
        """撤销委托。"""

    @abc.abstractmethod
    def query_orders(self, start: datetime, end: datetime) -> list[dict]:
        """查询委托记录。"""


class _PaperBrokerClient(BrokerClient):
    """模拟盘券商客户端 — 内存存储，不发送真实委托。"""

    def __init__(self) -> None:
        self._orders: dict[str, dict] = {}

    def submit_order(self, order: OrderRequest) -> OrderResponse:
        order_id = uuid.uuid4().hex[:12]
        now = datetime.now()
        record = {
            "order_id": order_id,
            "symbol": order.symbol,
            "direction": order.direction,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "status": OrderStatus.FILLED,
            "submitted_at": now,
        }
        self._orders[order_id] = record
        return OrderResponse(
            order_id=order_id,
            symbol=order.symbol,
            direction=order.direction,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=OrderStatus.FILLED,
            submitted_at=now,
        )

    def cancel_order(self, order_id: str) -> dict:
        rec = self._orders.get(order_id)
        if rec is None:
            return {"success": False, "message": "order not found"}
        rec["status"] = OrderStatus.CANCELLED
        return {"success": True, "order_id": order_id}

    def query_orders(self, start: datetime, end: datetime) -> list[dict]:
        return [
            r
            for r in self._orders.values()
            if start <= r["submitted_at"] <= end
        ]


class _LiveBrokerClient(BrokerClient):
    """实盘券商客户端存根 — 通过 SSL 加密通道提交委托。

    实际对接时替换为真实券商 SDK 调用。
    SSL 上下文在初始化时创建，确保所有通信加密（需求 14.4）。
    """

    def __init__(self) -> None:
        self._ssl_context = ssl.create_default_context()

    @property
    def ssl_context(self) -> ssl.SSLContext:
        return self._ssl_context

    def submit_order(self, order: OrderRequest) -> OrderResponse:
        # 真实实现中通过 self._ssl_context 建立加密连接并提交
        order_id = uuid.uuid4().hex[:12]
        return OrderResponse(
            order_id=order_id,
            symbol=order.symbol,
            direction=order.direction,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=OrderStatus.PENDING,
            submitted_at=datetime.now(),
        )

    def cancel_order(self, order_id: str) -> dict:
        return {"success": True, "order_id": order_id}

    def query_orders(self, start: datetime, end: datetime) -> list[dict]:
        return []


# ---------------------------------------------------------------------------
# 交易执行器
# ---------------------------------------------------------------------------


class TradeExecutor:
    """交易执行器 — 统一入口，支持实盘/模拟盘切换。

    Parameters
    ----------
    mode : TradeMode
        初始交易模式，默认 LIVE。
    now_fn : Callable[[], datetime] | None
        可注入的时间函数，便于测试。默认使用 ``datetime.now``。
    """

    def __init__(
        self,
        mode: TradeMode = TradeMode.LIVE,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._mode = mode
        self._now_fn = now_fn or datetime.now
        self._paper_client = _PaperBrokerClient()
        self._live_client = _LiveBrokerClient()

    # -- 属性 ---------------------------------------------------------------

    @property
    def mode(self) -> TradeMode:
        return self._mode

    @property
    def broker(self) -> BrokerClient:
        """返回当前模式对应的券商客户端。"""
        if self._mode == TradeMode.PAPER:
            return self._paper_client
        return self._live_client

    # -- 模式切换 -----------------------------------------------------------

    def switch_mode(self, mode: TradeMode) -> None:
        """切换实盘/模拟盘模式（需求 14.3）。"""
        self._mode = mode

    # -- 交易时段判断 -------------------------------------------------------

    def is_trading_hours(self) -> bool:
        """判断当前是否处于交易时段 9:25-15:00（工作日）。

        需求 14.5：非交易时段拒绝委托。
        """
        now = self._now_fn()
        # 周六=5, 周日=6
        if now.weekday() >= 5:
            return False
        return TRADING_START <= now.time() <= TRADING_END

    # -- 委托 ---------------------------------------------------------------

    def submit_order(self, order: OrderRequest) -> OrderResponse:
        """提交委托。

        非交易时段自动拒绝（需求 14.5 / 属性 26）。
        """
        if not self.is_trading_hours():
            return OrderResponse(
                order_id="",
                symbol=order.symbol,
                direction=order.direction,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price,
                status=OrderStatus.REJECTED,
                message="OUTSIDE_TRADING_HOURS",
            )
        return self.broker.submit_order(order)

    # -- 撤单 ---------------------------------------------------------------

    def cancel_order(self, order_id: str) -> dict:
        """撤销委托。"""
        return self.broker.cancel_order(order_id)


# ---------------------------------------------------------------------------
# 手动交易辅助（需求 14.1 / 任务 8.2）
# ---------------------------------------------------------------------------


class ManualTradeHelper:
    """选股池标的一键下单辅助类。

    - 从 ScreenItem 自动带入参考买入价、止损价、止盈价
    - 支持限价/市价委托
    - 通过 TradeExecutor 提交委托

    需求 14.1：一键下单 + 自动带入参考价/止损价/止盈价
    """

    #: 默认止损比例（8%）
    DEFAULT_STOP_LOSS_PCT: float = 0.08
    #: 默认止盈比例（15%）
    DEFAULT_TAKE_PROFIT_PCT: float = 0.15

    def __init__(
        self,
        stop_loss_pct: float = 0.08,
        take_profit_pct: float = 0.15,
    ) -> None:
        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct

    # -- 内部工具 -----------------------------------------------------------

    @staticmethod
    def _round_price(price: Decimal) -> Decimal:
        """将价格四舍五入到两位小数（A 股最小价格变动单位 0.01）。"""
        return price.quantize(Decimal("0.01"))

    # -- 核心方法 -----------------------------------------------------------

    def create_order_from_screen_item(
        self,
        item: "ScreenItem",
        order_type: OrderType,
        quantity: int,
    ) -> OrderRequest:
        """根据选股池标的创建委托请求。

        Parameters
        ----------
        item : ScreenItem
            选股结果条目，包含 ``ref_buy_price`` 等字段。
        order_type : OrderType
            委托类型（LIMIT / MARKET）。
        quantity : int
            委托数量（股）。

        Returns
        -------
        OrderRequest
            自动填充参考买入价、止损价、止盈价的委托请求。
        """
        ref_price = item.ref_buy_price
        stop_loss = self._round_price(
            ref_price * (1 - Decimal(str(self._stop_loss_pct)))
        )
        take_profit = self._round_price(
            ref_price * (1 + Decimal(str(self._take_profit_pct)))
        )

        return OrderRequest(
            symbol=item.symbol,
            direction=OrderDirection.BUY,
            order_type=order_type,
            quantity=quantity,
            price=ref_price if order_type == OrderType.LIMIT else None,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def submit_one_click_order(
        self,
        executor: TradeExecutor,
        item: "ScreenItem",
        order_type: OrderType,
        quantity: int,
    ) -> OrderResponse:
        """一键下单：创建委托并通过 TradeExecutor 提交。

        Parameters
        ----------
        executor : TradeExecutor
            交易执行器实例。
        item : ScreenItem
            选股结果条目。
        order_type : OrderType
            委托类型。
        quantity : int
            委托数量。

        Returns
        -------
        OrderResponse
            券商返回的委托响应。
        """
        order = self.create_order_from_screen_item(item, order_type, quantity)
        return executor.submit_order(order)


# ---------------------------------------------------------------------------
# 条件单管理器（需求 14.2 / 任务 8.3）
# ---------------------------------------------------------------------------


class ConditionOrderManager:
    """条件单管理器 — 注册、取消、监控触发。

    支持四种条件单类型（需求 14.2）：
    - BREAKOUT_BUY：突破买入，current_price >= trigger_price 时触发
    - STOP_LOSS：止损卖出，current_price <= trigger_price 时触发
    - TAKE_PROFIT：止盈卖出，current_price >= trigger_price 时触发
    - TRAILING_STOP：移动止盈，current_price <= peak_price * (1 - trailing_pct) 时触发；
      若 current_price > peak_price 则更新 peak_price
    """

    def __init__(self) -> None:
        self._orders: dict[str, ConditionOrder] = {}

    def register(self, order: ConditionOrder) -> str:
        """注册条件单，返回唯一 ID。"""
        order_id = uuid.uuid4().hex[:12]
        self._orders[order_id] = order
        return order_id

    def cancel(self, order_id: str) -> bool:
        """取消条件单。成功返回 True，未找到返回 False。"""
        order = self._orders.get(order_id)
        if order is None or not order.is_active:
            return False
        order.is_active = False
        return True

    def get_active_orders(self) -> list[ConditionOrder]:
        """返回所有活跃条件单。"""
        return [o for o in self._orders.values() if o.is_active]

    def check_and_trigger(
        self,
        current_prices: dict[str, float],
        executor: TradeExecutor,
    ) -> list[OrderResponse]:
        """检查所有活跃条件单，满足条件时通过 executor 提交委托。

        Parameters
        ----------
        current_prices : dict[str, float]
            股票代码 -> 当前价格映射。
        executor : TradeExecutor
            交易执行器，用于提交触发后的委托。

        Returns
        -------
        list[OrderResponse]
            本次触发提交的委托响应列表。
        """
        triggered: list[OrderResponse] = []
        for order in list(self._orders.values()):
            if not order.is_active:
                continue
            price = current_prices.get(order.symbol)
            if price is None:
                continue
            if self._should_trigger(order, price):
                resp = executor.submit_order(order.order_request)
                order.is_active = False
                triggered.append(resp)
        return triggered

    @staticmethod
    def _should_trigger(order: ConditionOrder, current_price: float) -> bool:
        """判断条件单是否满足触发条件。"""
        trigger = float(order.trigger_price)
        tt = order.trigger_type

        if tt == ConditionTriggerType.BREAKOUT_BUY:
            return current_price >= trigger

        if tt == ConditionTriggerType.STOP_LOSS:
            return current_price <= trigger

        if tt == ConditionTriggerType.TAKE_PROFIT:
            return current_price >= trigger

        if tt == ConditionTriggerType.TRAILING_STOP:
            # 更新 peak_price
            peak = float(order.peak_price) if order.peak_price is not None else current_price
            if current_price > peak:
                peak = current_price
                order.peak_price = Decimal(str(current_price))
            pct = order.trailing_pct or 0.0
            return current_price <= peak * (1 - pct)

        return False  # pragma: no cover


# ---------------------------------------------------------------------------
# 持仓管理器（需求 15 / 任务 8.4）
# ---------------------------------------------------------------------------


class PositionManager:
    """持仓管理器 — 持仓同步、趋势破位预警、交易记录存储与导出。

    需求 15.1：实时同步持仓数据（持仓股数/成本价/市值/盈亏/盈亏比例/仓位占比）
    需求 15.2：持仓个股趋势破位预警
    需求 15.3：委托/成交/撤单记录存储、按时间范围查询、CSV 导出
    """

    def __init__(self) -> None:
        self._positions: dict[str, "Position"] = {}
        self._trade_records: list[dict] = []

    # -- 持仓同步 -----------------------------------------------------------

    def update_position(
        self,
        symbol: str,
        quantity: int,
        cost_price: Decimal,
        current_price: Decimal,
        total_assets: Decimal,
    ) -> "Position":
        """更新/新增持仓，自动计算市值、盈亏、仓位占比。

        属性 27：PnL = (current_price - cost_price) * quantity
                 PnL% = PnL / (cost_price * quantity)
        """
        from app.core.schemas import Position

        pos = Position.from_cost(
            symbol=symbol,
            quantity=quantity,
            cost_price=cost_price,
            current_price=current_price,
            total_assets=total_assets,
        )
        self._positions[symbol] = pos
        return pos

    def get_positions(self) -> list["Position"]:
        """返回所有持仓列表。"""
        return list(self._positions.values())

    def remove_position(self, symbol: str) -> None:
        """移除指定持仓。"""
        self._positions.pop(symbol, None)

    # -- 趋势破位预警 -------------------------------------------------------

    @staticmethod
    def check_trend_breakdown(
        symbol: str,
        current_price: float,
        ma20: float,
    ) -> dict | None:
        """检查持仓个股是否趋势破位（需求 15.2）。

        当 current_price < ma20 时视为不再满足右侧趋势条件，返回预警信息。
        """
        if current_price < ma20:
            return {
                "symbol": symbol,
                "alert": "TREND_BREAKDOWN",
                "current_price": current_price,
                "ma20": ma20,
                "message": f"{symbol} 跌破20日均线 ({current_price} < {ma20})，趋势破位预警",
            }
        return None

    # -- 交易记录 -----------------------------------------------------------

    def add_trade_record(self, record: dict) -> None:
        """添加委托/成交/撤单记录（需求 15.3）。"""
        self._trade_records.append(record)

    def get_trade_records(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """按时间范围查询交易记录。

        若 start_date / end_date 为 None 则不限制对应边界。
        """
        results = self._trade_records
        if start_date is not None:
            results = [r for r in results if r.get("time", datetime.min) >= start_date]
        if end_date is not None:
            results = [r for r in results if r.get("time", datetime.max) <= end_date]
        return results

    def export_trade_records_csv(self) -> bytes:
        """将所有交易记录导出为 CSV 字节流（需求 15.3）。"""
        import csv
        import io

        if not self._trade_records:
            return b""

        # 收集所有字段名
        fieldnames: list[str] = []
        for rec in self._trade_records:
            for k in rec:
                if k not in fieldnames:
                    fieldnames.append(k)

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for rec in self._trade_records:
            writer.writerow(rec)
        return buf.getvalue().encode("utf-8")
