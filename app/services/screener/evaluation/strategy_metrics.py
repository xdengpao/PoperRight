"""策略对比评价计算器

对 22 个策略模板进行横向对比，按市场环境分组评估。
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.screener.evaluation.forward_return_calculator import ForwardReturn
from app.services.screener.evaluation.screening_simulator import DailyScreenResult


@dataclass
class StrategyMetric:
    """单策略评价指标。"""
    strategy_name: str
    hit_rate: float = 0.0
    avg_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_stock_count: float = 0.0
    turnover: float = 0.0
    composite_score: float = 0.0


@dataclass
class MarketEnvMetric:
    """按市场环境分组的策略指标。"""
    env_type: str
    strategy_metrics: list[StrategyMetric] = field(default_factory=list)


class StrategyMetricsCalculator:
    """策略对比评价计算器。"""

    EVAL_PERIOD = 5

    def calculate(
        self,
        all_strategy_results: dict[str, list[DailyScreenResult]],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
        index_data: dict[date, dict[str, Any]],
    ) -> dict[str, Any]:
        """计算策略对比指标。"""
        overall: list[StrategyMetric] = []

        for strategy_name, daily_results in all_strategy_results.items():
            metric = self._compute_strategy_metric(
                strategy_name, daily_results, forward_returns_map,
            )
            overall.append(metric)

        overall.sort(key=lambda m: m.composite_score, reverse=True)

        by_env: list[MarketEnvMetric] = []
        for env_type in ["上涨市", "震荡市", "下跌市"]:
            env_metrics: list[StrategyMetric] = []
            for strategy_name, daily_results in all_strategy_results.items():
                filtered = [
                    d for d in daily_results
                    if self._classify_market_env(index_data, d.trade_date) == env_type
                ]
                if filtered:
                    m = self._compute_strategy_metric(
                        strategy_name, filtered, forward_returns_map,
                    )
                    env_metrics.append(m)
            env_metrics.sort(key=lambda m: m.composite_score, reverse=True)
            by_env.append(MarketEnvMetric(env_type=env_type, strategy_metrics=env_metrics))

        n = len(overall)
        bottom_20pct = [m.strategy_name for m in overall[int(n * 0.8):]] if n >= 5 else []

        return {
            "overall": overall,
            "by_market_env": by_env,
            "bottom_20pct": bottom_20pct,
        }

    def _compute_strategy_metric(
        self,
        strategy_name: str,
        daily_results: list[DailyScreenResult],
        forward_returns_map: dict[tuple[date, str], ForwardReturn],
    ) -> StrategyMetric:
        all_returns: list[float] = []
        stock_counts: list[int] = []
        daily_portfolio_returns: list[float] = []
        prev_symbols: set[str] = set()
        turnovers: list[float] = []

        for daily in daily_results:
            stock_counts.append(len(daily.items))
            curr_symbols = {item.symbol for item in daily.items}

            if prev_symbols:
                union = prev_symbols | curr_symbols
                if union:
                    changed = len(prev_symbols.symmetric_difference(curr_symbols))
                    turnovers.append(changed / len(union) * 100)
            prev_symbols = curr_symbols

            day_rets: list[float] = []
            for item in daily.items:
                key = (daily.trade_date, item.symbol)
                fr = forward_returns_map.get(key)
                if fr and self.EVAL_PERIOD in fr.returns:
                    day_rets.append(fr.returns[self.EVAL_PERIOD])
                    all_returns.append(fr.returns[self.EVAL_PERIOD])

            if day_rets:
                daily_portfolio_returns.append(statistics.mean(day_rets))

        if not all_returns:
            return StrategyMetric(strategy_name=strategy_name)

        hit_rate = sum(1 for r in all_returns if r > 0) / len(all_returns) * 100
        avg_return = statistics.mean(all_returns)
        sharpe = self._compute_sharpe(daily_portfolio_returns)
        max_dd = self._compute_max_drawdown(daily_portfolio_returns)
        avg_count = statistics.mean(stock_counts) if stock_counts else 0
        avg_turnover = statistics.mean(turnovers) if turnovers else 0

        composite = self._compute_composite_score(hit_rate, avg_return, sharpe)

        return StrategyMetric(
            strategy_name=strategy_name,
            hit_rate=hit_rate,
            avg_return=avg_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            avg_stock_count=avg_count,
            turnover=avg_turnover,
            composite_score=composite,
        )

    @staticmethod
    def _classify_market_env(index_data: dict[date, dict[str, Any]], trade_date: date) -> str:
        """基于沪深300判断市场环境（按需求 5 定义的规则）。"""
        data = index_data.get(trade_date)
        if data is None:
            return "震荡市"

        ma20 = data.get("ma20")
        ma60 = data.get("ma60")
        change_20d = data.get("change_pct_20d")

        if ma20 and ma60 and change_20d is not None:
            if ma20 > ma60 and change_20d > 5:
                return "上涨市"
            if ma20 < ma60 and change_20d < -5:
                return "下跌市"
            if -3 <= change_20d <= 3:
                return "震荡市"

        return "震荡市"

    @staticmethod
    def _compute_composite_score(hit_rate: float, avg_return: float, sharpe: float) -> float:
        """综合得分 = hit_rate × 0.4 + avg_return_normalized × 0.3 + sharpe_normalized × 0.3"""
        ret_score = min(max(avg_return + 5, 0), 10) * 10
        sharpe_score = min(max(sharpe + 1, 0), 3) / 3 * 100
        return hit_rate * 0.4 + ret_score * 0.3 + sharpe_score * 0.3

    @staticmethod
    def _compute_sharpe(daily_returns: list[float], risk_free_rate: float = 3.0) -> float:
        if len(daily_returns) < 5:
            return 0.0
        mean_ret = statistics.mean(daily_returns)
        std_ret = statistics.stdev(daily_returns)
        if std_ret == 0:
            return 0.0
        annualized_ret = mean_ret * 252 / 5
        annualized_std = std_ret * math.sqrt(252 / 5)
        return (annualized_ret - risk_free_rate) / annualized_std

    @staticmethod
    def _compute_max_drawdown(daily_returns: list[float]) -> float:
        if not daily_returns:
            return 0.0
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        for ret in daily_returns:
            cumulative *= (1 + ret / 100)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak * 100
            max_dd = max(max_dd, dd)
        return max_dd
