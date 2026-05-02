"""未来收益计算器

计算选股结果中每只股票在未来 N 个交易日的实际收益，
用于评估选股质量。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.schemas import ScreenItem
from app.services.data_engine.kline_repository import KlineRepository
from app.services.data_engine.kline_normalizer import derive_trade_date

logger = logging.getLogger(__name__)

HOLDING_PERIODS = [1, 3, 5, 10, 20]


@dataclass
class ForwardReturn:
    """单只股票的未来收益数据。"""
    symbol: str
    screen_date: date
    ref_buy_price: Decimal
    next_day_open: Decimal | None = None
    can_buy: bool = True
    ref_price_deviation: float = 0.0
    returns: dict[int, float] = field(default_factory=dict)
    index_returns: dict[int, float] = field(default_factory=dict)
    excess_returns: dict[int, float] = field(default_factory=dict)
    # PLACEHOLDER_FORWARD_RETURN_CONTINUE


class ForwardReturnCalculator:
    """未来收益计算器。"""

    def __init__(self, kline_repo: KlineRepository) -> None:
        self._kline_repo = kline_repo

    async def calculate(
        self,
        screen_items: list[ScreenItem],
        screen_date: date,
        index_data: dict[date, dict[str, Any]],
        trading_dates: list[date],
    ) -> list[ForwardReturn]:
        """计算选股结果的未来收益。

        买入价 = T+1 开盘价（前复权）
        卖出价 = T+N 收盘价（前复权）
        """
        screen_idx = _find_date_index(trading_dates, screen_date)
        if screen_idx is None:
            return []

        max_forward = max(HOLDING_PERIODS)
        end_idx = min(screen_idx + max_forward + 1, len(trading_dates) - 1)
        if screen_idx + 1 > end_idx:
            return []

        forward_dates = trading_dates[screen_idx + 1: end_idx + 1]
        if not forward_dates:
            return []

        results: list[ForwardReturn] = []
        for item in screen_items:
            fr = await self._calc_single(
                item, screen_date, screen_idx, trading_dates,
                forward_dates, index_data,
            )
            results.append(fr)
        return results

    async def _calc_single(
        self,
        item: ScreenItem,
        screen_date: date,
        screen_idx: int,
        trading_dates: list[date],
        forward_dates: list[date],
        index_data: dict[date, dict[str, Any]],
    ) -> ForwardReturn:
        fr = ForwardReturn(
            symbol=item.symbol,
            screen_date=screen_date,
            ref_buy_price=item.ref_buy_price,
        )

        bars = await self._kline_repo.query(
            symbol=item.symbol,
            freq="1d",
            start=forward_dates[0],
            end=forward_dates[-1],
            adj_type=1,
        )
        if not bars:
            fr.can_buy = False
            return fr

        bar_map: dict[date, Any] = {}
        for b in bars:
            bd = derive_trade_date(b.time, getattr(b, "freq", "1d")) if hasattr(b.time, 'date') else b.time
            bar_map[bd] = b

        t1_date = forward_dates[0]
        t1_bar = bar_map.get(t1_date)
        if t1_bar is None:
            fr.can_buy = False
            return fr

        if not self._check_can_buy(t1_bar):
            fr.can_buy = False
            return fr

        buy_price = float(t1_bar.open)
        fr.next_day_open = Decimal(str(buy_price))

        if float(item.ref_buy_price) > 0:
            fr.ref_price_deviation = (
                (buy_price - float(item.ref_buy_price))
                / float(item.ref_buy_price)
                * 100
            )

        index_close_screen = index_data.get(screen_date, {}).get("close")

        for period in HOLDING_PERIODS:
            target_idx = screen_idx + 1 + period
            if target_idx >= len(trading_dates):
                break
            target_date = trading_dates[target_idx]
            target_bar = bar_map.get(target_date)
            if target_bar is None:
                continue

            sell_price = float(target_bar.close)
            ret = (sell_price - buy_price) / buy_price * 100
            fr.returns[period] = ret

            idx_data_target = index_data.get(target_date)
            idx_data_t1 = index_data.get(t1_date)
            if idx_data_target and idx_data_t1:
                idx_ret = (
                    (idx_data_target["close"] - idx_data_t1["close"])
                    / idx_data_t1["close"]
                    * 100
                )
                fr.index_returns[period] = idx_ret
                fr.excess_returns[period] = ret - idx_ret

        return fr

    @staticmethod
    def _check_can_buy(next_day_bar: Any) -> bool:
        """检查 T+1 是否可买入（非停牌、非一字涨停）。"""
        if next_day_bar is None:
            return False
        volume = int(next_day_bar.volume) if next_day_bar.volume else 0
        if volume == 0:
            return False
        o = float(next_day_bar.open)
        h = float(next_day_bar.high)
        l_ = float(next_day_bar.low)
        if o == h == l_ and volume < 1000:
            return False
        return True


def _find_date_index(dates: list[date], target: date) -> int | None:
    for i, d in enumerate(dates):
        if d == target:
            return i
        if d > target:
            return i - 1 if i > 0 else None
    return len(dates) - 1 if dates else None
