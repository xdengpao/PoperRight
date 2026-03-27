"""
历史回测核心引擎

需求 12：策略历史回测
- 12.1: 可配置起止日期、初始资金、买入手续费(0.03%)、卖出手续费(0.13%+0.1%印花税)、滑点(0.1%)
- 12.2: 输出 9 项绩效指标
- 12.3: 收益曲线、最大回撤曲线、持仓明细、交易流水；支持数据导出
- 12.4: 按牛市/熊市/震荡市分段回测
- 12.5: 严格遵守 A 股 T+1 规则
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.core.schemas import BacktestConfig, BacktestResult


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class _PositionEntry:
    """内部持仓记录"""
    symbol: str
    quantity: int
    cost_price: Decimal
    buy_date: date  # 买入日期，用于 T+1 判定


@dataclass
class _TradeRecord:
    """内部交易流水"""
    date: date
    symbol: str
    action: str  # "BUY" / "SELL"
    price: Decimal
    quantity: int
    cost: Decimal  # 手续费 + 滑点
    amount: Decimal  # 成交金额（不含费用）


# ---------------------------------------------------------------------------
# MarketEnvironmentClassifier（需求 12.4）
# ---------------------------------------------------------------------------

class MarketEnvironmentClassifier:
    """市场环境分类器：识别牛市/熊市/震荡市"""

    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"

    @staticmethod
    def classify_market(index_closes: list[float], lookback: int = 60) -> str:
        """
        根据指数收盘价序列判断当前市场环境。

        规则：
        - BULL: price > MA60 且 MA20 > MA60
        - BEAR: price < MA60 且 MA20 < MA60
        - SIDEWAYS: 其他情况

        Parameters
        ----------
        index_closes : list[float]
            指数收盘价序列（按时间升序），长度应 >= lookback
        lookback : int
            MA 长周期，默认 60

        Returns
        -------
        str  "BULL" / "BEAR" / "SIDEWAYS"
        """
        if len(index_closes) < lookback:
            return MarketEnvironmentClassifier.SIDEWAYS

        ma60 = sum(index_closes[-lookback:]) / lookback
        ma20 = sum(index_closes[-20:]) / 20 if len(index_closes) >= 20 else ma60
        price = index_closes[-1]

        if price > ma60 and ma20 > ma60:
            return MarketEnvironmentClassifier.BULL
        elif price < ma60 and ma20 < ma60:
            return MarketEnvironmentClassifier.BEAR
        else:
            return MarketEnvironmentClassifier.SIDEWAYS

    @staticmethod
    def segment_by_environment(
        index_data: list[tuple[date, float]],
        lookback: int = 60,
    ) -> list[tuple[str, date, date]]:
        """
        将指数时间序列按市场环境分段。

        Parameters
        ----------
        index_data : list[tuple[date, float]]
            (日期, 收盘价) 列表，按日期升序
        lookback : int
            MA 长周期

        Returns
        -------
        list[tuple[str, date, date]]
            [(环境, 起始日期, 结束日期), ...]
        """
        if not index_data:
            return []

        classifier = MarketEnvironmentClassifier
        segments: list[tuple[str, date, date]] = []
        closes: list[float] = []

        current_env: str | None = None
        seg_start: date | None = None

        for d, close in index_data:
            closes.append(close)
            env = classifier.classify_market(closes, lookback)

            if current_env is None:
                current_env = env
                seg_start = d
            elif env != current_env:
                # 结束上一段，开始新段
                segments.append((current_env, seg_start, d))
                current_env = env
                seg_start = d

        # 关闭最后一段
        if current_env is not None and seg_start is not None:
            segments.append((current_env, seg_start, index_data[-1][0]))

        return segments


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """历史回测引擎"""

    def run_backtest(
        self,
        config: BacktestConfig,
        signals: list[dict],
    ) -> BacktestResult:
        """
        执行回测。

        Parameters
        ----------
        config : BacktestConfig
            回测参数配置
        signals : list[dict]
            交易信号列表，每条包含:
            - date: date  交易日期
            - symbol: str  股票代码
            - action: str  "BUY" / "SELL"
            - price: Decimal | float  成交价格
            - quantity: int  成交数量

        Returns
        -------
        BacktestResult
        """
        cash = config.initial_capital
        positions: dict[str, _PositionEntry] = {}
        trade_records: list[_TradeRecord] = []
        # 按日期排序的净值快照: {date: equity}
        equity_snapshots: dict[date, Decimal] = {}

        # 按日期排序信号
        sorted_signals = sorted(signals, key=lambda s: s["date"])

        for sig in sorted_signals:
            sig_date: date = sig["date"]
            symbol: str = sig["symbol"]
            action: str = sig["action"].upper()
            price = Decimal(str(sig["price"]))
            quantity: int = int(sig["quantity"])

            if action == "BUY":
                buy_cost = self._calc_buy_cost(price, quantity, config)
                total_cost = price * quantity + buy_cost
                if total_cost > cash:
                    continue  # 资金不足，跳过
                cash -= total_cost
                if symbol in positions:
                    pos = positions[symbol]
                    old_total = pos.cost_price * pos.quantity
                    new_total = price * quantity
                    pos.quantity += quantity
                    pos.cost_price = (old_total + new_total) / pos.quantity
                    # 更新买入日期为最新买入日（T+1 约束用最新买入日）
                    pos.buy_date = sig_date
                else:
                    positions[symbol] = _PositionEntry(
                        symbol=symbol,
                        quantity=quantity,
                        cost_price=price,
                        buy_date=sig_date,
                    )
                trade_records.append(_TradeRecord(
                    date=sig_date, symbol=symbol, action="BUY",
                    price=price, quantity=quantity,
                    cost=buy_cost, amount=price * quantity,
                ))

            elif action == "SELL":
                if symbol not in positions:
                    continue  # 无持仓，跳过
                pos = positions[symbol]
                # T+1 规则：买入当日不可卖出
                if pos.buy_date >= sig_date:
                    continue
                sell_qty = min(quantity, pos.quantity)
                if sell_qty <= 0:
                    continue
                sell_cost = self._calc_sell_cost(price, sell_qty, config)
                proceeds = price * sell_qty - sell_cost
                cash += proceeds
                pos.quantity -= sell_qty
                trade_records.append(_TradeRecord(
                    date=sig_date, symbol=symbol, action="SELL",
                    price=price, quantity=sell_qty,
                    cost=sell_cost, amount=price * sell_qty,
                ))
                if pos.quantity <= 0:
                    del positions[symbol]

            # 记录当日净值快照
            equity = cash + sum(
                Decimal(str(sig["price"])) * p.quantity
                if p.symbol == symbol else p.cost_price * p.quantity
                for p in positions.values()
            )
            equity_snapshots[sig_date] = equity

        # 构建净值曲线（按日期排序）
        sorted_dates = sorted(equity_snapshots.keys())
        initial = config.initial_capital
        equity_curve: list[tuple[date, float]] = []
        for d in sorted_dates:
            nav = float(equity_snapshots[d] / initial) if initial else 1.0
            equity_curve.append((d, nav))

        # 如果没有交易，返回空结果
        if not equity_curve:
            return BacktestResult(
                annual_return=0.0,
                total_return=0.0,
                win_rate=0.0,
                profit_loss_ratio=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
                avg_holding_days=0.0,
                equity_curve=[],
                trade_records=[],
            )

        # 计算绩效指标
        metrics = self._calculate_metrics(
            equity_curve, trade_records, config,
        )

        # 序列化交易记录
        serialized_records = [
            {
                "date": str(tr.date),
                "symbol": tr.symbol,
                "action": tr.action,
                "price": float(tr.price),
                "quantity": tr.quantity,
                "cost": float(tr.cost),
                "amount": float(tr.amount),
            }
            for tr in trade_records
        ]

        return BacktestResult(
            annual_return=metrics["annual_return"],
            total_return=metrics["total_return"],
            win_rate=metrics["win_rate"],
            profit_loss_ratio=metrics["profit_loss_ratio"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            calmar_ratio=metrics["calmar_ratio"],
            total_trades=metrics["total_trades"],
            avg_holding_days=metrics["avg_holding_days"],
            equity_curve=equity_curve,
            trade_records=serialized_records,
        )

    # ------------------------------------------------------------------
    # 分段回测（需求 12.4）
    # ------------------------------------------------------------------

    def run_segment_backtest(
        self,
        config: BacktestConfig,
        signals: list[dict],
        segments: list[tuple[str, date, date]],
    ) -> dict[str, BacktestResult]:
        """
        按市场环境分段执行回测，分别输出各阶段绩效指标。

        Parameters
        ----------
        config : BacktestConfig
            回测参数配置
        signals : list[dict]
            完整交易信号列表
        segments : list[tuple[str, date, date]]
            市场环境分段列表 [(环境, 起始日期, 结束日期), ...]

        Returns
        -------
        dict[str, BacktestResult]
            键为市场环境名称，值为该环境下的回测结果
        """
        results: dict[str, BacktestResult] = {}

        for env, start, end in segments:
            seg_signals = [
                s for s in signals
                if start <= s["date"] <= end
            ]
            result = self.run_backtest(config, seg_signals)
            # 如果同一环境出现多段，合并到已有结果（取最后一段）
            # 简单实现：按 "ENV" 键存储，多段同环境覆盖
            results[env] = result

        return results

    # ------------------------------------------------------------------
    # 手续费计算
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_buy_cost(
        price: Decimal, quantity: int, config: BacktestConfig,
    ) -> Decimal:
        """买入成本 = 成交金额 * 买入费率 + 成交金额 * 滑点"""
        amount = price * quantity
        return amount * config.commission_buy + amount * config.slippage

    @staticmethod
    def _calc_sell_cost(
        price: Decimal, quantity: int, config: BacktestConfig,
    ) -> Decimal:
        """卖出成本 = 成交金额 * 卖出费率 + 成交金额 * 滑点"""
        amount = price * quantity
        return amount * config.commission_sell + amount * config.slippage

    # ------------------------------------------------------------------
    # 绩效指标计算
    # ------------------------------------------------------------------

    def _calculate_metrics(
        self,
        equity_curve: list[tuple[date, float]],
        trade_records: list[_TradeRecord],
        config: BacktestConfig,
    ) -> dict:
        """
        计算 9 项绩效指标。

        Returns dict with keys:
            annual_return, total_return, win_rate, profit_loss_ratio,
            max_drawdown, sharpe_ratio, calmar_ratio, total_trades,
            avg_holding_days
        """
        # --- 累计收益率 ---
        final_nav = equity_curve[-1][1] if equity_curve else 1.0
        total_return = final_nav - 1.0

        # --- 年化收益率 ---
        if len(equity_curve) >= 2:
            days = (equity_curve[-1][0] - equity_curve[0][0]).days
            years = max(days / 365.0, 1.0 / 365.0)
            if final_nav > 0:
                annual_return = final_nav ** (1.0 / years) - 1.0
            else:
                annual_return = -1.0
        else:
            annual_return = total_return

        # --- 最大回撤 ---
        max_drawdown = self._calc_max_drawdown(equity_curve)

        # --- 日收益率序列（用于夏普比率）---
        daily_returns: list[float] = []
        for i in range(1, len(equity_curve)):
            prev_nav = equity_curve[i - 1][1]
            curr_nav = equity_curve[i][1]
            if prev_nav != 0:
                daily_returns.append(curr_nav / prev_nav - 1.0)

        # --- 夏普比率（无风险利率 = 0）---
        if daily_returns and len(daily_returns) >= 2:
            avg_ret = sum(daily_returns) / len(daily_returns)
            std_ret = (
                sum((r - avg_ret) ** 2 for r in daily_returns)
                / (len(daily_returns) - 1)
            ) ** 0.5
            if std_ret > 0:
                sharpe_ratio = (avg_ret / std_ret) * (252 ** 0.5)
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # --- 卡玛比率 ---
        if max_drawdown > 0:
            calmar_ratio = annual_return / max_drawdown
        else:
            calmar_ratio = 0.0

        # --- 交易次数、胜率、盈亏比、平均持仓天数 ---
        sell_records = [r for r in trade_records if r.action == "SELL"]
        buy_records = [r for r in trade_records if r.action == "BUY"]
        total_trades = len(sell_records)

        # 匹配买卖对计算胜率和盈亏比
        wins = 0
        total_profit = Decimal("0")
        total_loss = Decimal("0")
        holding_days_sum = 0
        matched_trades = 0

        # 按 symbol 分组匹配 FIFO
        buy_queue: dict[str, list[_TradeRecord]] = {}
        for br in buy_records:
            buy_queue.setdefault(br.symbol, []).append(br)

        for sr in sell_records:
            if sr.symbol in buy_queue and buy_queue[sr.symbol]:
                br = buy_queue[sr.symbol].pop(0)
                pnl = (sr.price - br.price) * sr.quantity - sr.cost - br.cost
                days_held = (sr.date - br.date).days
                holding_days_sum += max(days_held, 1)
                matched_trades += 1
                if pnl > 0:
                    wins += 1
                    total_profit += pnl
                elif pnl < 0:
                    total_loss += abs(pnl)

        win_rate = wins / total_trades if total_trades > 0 else 0.0
        if total_loss > 0:
            profit_loss_ratio = float(total_profit / total_loss)
        else:
            profit_loss_ratio = float(total_profit) if total_profit > 0 else 0.0
        avg_holding_days = (
            holding_days_sum / matched_trades if matched_trades > 0 else 0.0
        )

        return {
            "annual_return": annual_return,
            "total_return": total_return,
            "win_rate": win_rate,
            "profit_loss_ratio": profit_loss_ratio,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "calmar_ratio": calmar_ratio,
            "total_trades": total_trades,
            "avg_holding_days": avg_holding_days,
        }

    @staticmethod
    def _calc_max_drawdown(equity_curve: list[tuple[date, float]]) -> float:
        """计算最大回撤 [0, 1]"""
        if not equity_curve:
            return 0.0
        peak = equity_curve[0][1]
        max_dd = 0.0
        for _, nav in equity_curve:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    # ------------------------------------------------------------------
    # 收益曲线 & 最大回撤曲线数据
    # ------------------------------------------------------------------

    @staticmethod
    def generate_drawdown_curve(
        equity_curve: list[tuple[date, float]],
    ) -> list[tuple[date, float]]:
        """
        根据净值曲线生成最大回撤曲线数据。

        Returns list of (date, drawdown_pct) where drawdown_pct in [0, 1].
        """
        if not equity_curve:
            return []
        peak = equity_curve[0][1]
        result: list[tuple[date, float]] = []
        for d, nav in equity_curve:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak if peak > 0 else 0.0
            result.append((d, dd))
        return result

    # ------------------------------------------------------------------
    # CSV 导出
    # ------------------------------------------------------------------

    @staticmethod
    def export_result_to_csv(result: BacktestResult) -> bytes:
        """
        将回测结果导出为 CSV 字节流。

        包含两个部分：
        1. 绩效指标摘要
        2. 交易流水明细
        """
        buf = io.StringIO()
        writer = csv.writer(buf)

        # 绩效指标
        writer.writerow(["=== 绩效指标 ==="])
        writer.writerow(["指标", "值"])
        writer.writerow(["年化收益率", f"{result.annual_return:.4f}"])
        writer.writerow(["累计收益率", f"{result.total_return:.4f}"])
        writer.writerow(["胜率", f"{result.win_rate:.4f}"])
        writer.writerow(["盈亏比", f"{result.profit_loss_ratio:.4f}"])
        writer.writerow(["最大回撤", f"{result.max_drawdown:.4f}"])
        writer.writerow(["夏普比率", f"{result.sharpe_ratio:.4f}"])
        writer.writerow(["卡玛比率", f"{result.calmar_ratio:.4f}"])
        writer.writerow(["总交易次数", result.total_trades])
        writer.writerow(["平均持仓天数", f"{result.avg_holding_days:.1f}"])
        writer.writerow([])

        # 交易流水
        writer.writerow(["=== 交易流水 ==="])
        writer.writerow(["日期", "股票代码", "方向", "价格", "数量", "手续费", "成交金额"])
        for tr in result.trade_records:
            writer.writerow([
                tr.get("date", ""),
                tr.get("symbol", ""),
                tr.get("action", ""),
                tr.get("price", ""),
                tr.get("quantity", ""),
                tr.get("cost", ""),
                tr.get("amount", ""),
            ])

        return buf.getvalue().encode("utf-8-sig")
