"""选股模拟器

在历史数据上模拟运行选股引擎，生成每个交易日的选股结果。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.core.schemas import (
    MarketRiskLevel,
    ScreenItem,
    ScreenType,
    StrategyConfig,
)
from app.services.screener.screen_executor import ScreenExecutor

logger = logging.getLogger(__name__)


@dataclass
class DailyScreenResult:
    """单日选股模拟结果。"""
    trade_date: date
    strategy_id: str
    strategy_name: str
    items: list[ScreenItem] = field(default_factory=list)
    market_risk_level: MarketRiskLevel = MarketRiskLevel.NORMAL
    execution_time_ms: float = 0.0


class ScreeningSimulator:
    """选股模拟器，在历史数据上回放选股逻辑。"""

    def simulate_single_day(
        self,
        strategy_config: StrategyConfig,
        strategy_id: str,
        factor_data: dict[str, dict[str, Any]],
        index_closes: list[float] | None = None,
        enabled_modules: list[str] | None = None,
        previous_items: list[ScreenItem] | None = None,
    ) -> tuple[list[ScreenItem], MarketRiskLevel]:
        """模拟单日选股。

        直接调用 ScreenExecutor 的方法。
        """
        executor = ScreenExecutor(
            strategy_config=strategy_config,
            strategy_id=strategy_id,
            enabled_modules=enabled_modules,
        )
        result = executor.run_eod_screen(
            stocks_data=factor_data,
            index_closes=index_closes,
            previous_items=previous_items,
        )
        return result.items, result.market_risk_level or MarketRiskLevel.NORMAL

    async def simulate_period(
        self,
        strategy_config: StrategyConfig,
        strategy_id: str,
        strategy_name: str,
        data_preparer: Any,
        trading_dates: list[date],
        index_data: dict[date, dict[str, Any]] | None = None,
        enabled_modules: list[str] | None = None,
    ) -> list[DailyScreenResult]:
        """模拟评估期内每个交易日的选股。"""
        results: list[DailyScreenResult] = []
        previous_items: list[ScreenItem] | None = None

        for i, td in enumerate(trading_dates):
            t0 = time.time()

            snapshot = await data_preparer.load_daily_snapshot(td)
            if not snapshot:
                logger.warning("交易日 %s 无因子数据，跳过", td)
                continue

            idx_closes = self._extract_index_closes(index_data, td) if index_data else None

            items, mrl = self.simulate_single_day(
                strategy_config=strategy_config,
                strategy_id=strategy_id,
                factor_data=snapshot,
                index_closes=idx_closes,
                enabled_modules=enabled_modules,
                previous_items=previous_items,
            )

            elapsed_ms = (time.time() - t0) * 1000

            daily = DailyScreenResult(
                trade_date=td,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                items=items,
                market_risk_level=mrl,
                execution_time_ms=elapsed_ms,
            )
            results.append(daily)
            previous_items = items

            if (i + 1) % 10 == 0:
                logger.info(
                    "选股模拟进度: %d/%d (策略: %s)",
                    i + 1, len(trading_dates), strategy_name,
                )

        return results

    @staticmethod
    def _extract_index_closes(
        index_data: dict[date, dict[str, Any]],
        up_to_date: date,
    ) -> list[float]:
        """提取截至指定日期的指数收盘价序列。"""
        sorted_dates = sorted(d for d in index_data if d <= up_to_date)
        return [index_data[d]["close"] for d in sorted_dates[-60:]]
