"""
行情数据适配器

MarketDataClient 封装第三方行情 API，提供：
- 历史 K 线批量拉取（1m/5m/15m/30m/60m/1d/1w/1M）
- 实时行情轮询订阅（每 10 秒）

实际对接时替换 _parse_kline_response 中的字段映射即可。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Awaitable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings
from app.models.kline import KlineBar

logger = logging.getLogger(__name__)

# 支持的 K 线频率
VALID_FREQS = frozenset({"1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"})

# 频率 → API 参数映射（实际对接时按第三方 API 文档调整）
FREQ_PARAM_MAP: dict[str, str] = {
    "1m":  "1",
    "5m":  "5",
    "15m": "15",
    "30m": "30",
    "60m": "60",
    "1d":  "D",
    "1w":  "W",
    "1M":  "M",
}


class MarketDataClient:
    """
    第三方行情 API 客户端（异步，基于 httpx.AsyncClient）

    使用方式：
        async with MarketDataClient() as client:
            bars = await client.fetch_kline("000001.SZ", "1d", date(2020,1,1), date(2024,1,1))
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_url = (api_url or settings.market_data_api_url).rstrip("/")
        self._api_key = api_key or settings.market_data_api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "MarketDataClient":
        self._client = httpx.AsyncClient(
            base_url=self._api_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "MarketDataClient 未初始化，请使用 async with 语句或先调用 __aenter__"
            )
        return self._client

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        """发起 GET 请求，返回解析后的 JSON 数据。"""
        client = self._ensure_client()
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("行情 API 请求失败 [%s] %s: %s", exc.response.status_code, path, exc)
            raise
        except httpx.RequestError as exc:
            logger.error("行情 API 网络错误 %s: %s", path, exc)
            raise

    # ------------------------------------------------------------------
    # K 线数据解析（适配层 — 实际对接时修改此方法）
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_kline_response(
        raw: list[dict[str, Any]],
        symbol: str,
        freq: str,
    ) -> list[KlineBar]:
        """
        将第三方 API 返回的原始 JSON 列表解析为 KlineBar 列表。

        字段映射（示例，按实际 API 文档调整）：
            raw item keys: time, open, high, low, close, volume, amount,
                           turnover, vol_ratio, limit_up, limit_down
        """
        bars: list[KlineBar] = []
        for item in raw:
            try:
                # 时间字段：支持 ISO 字符串或 Unix 时间戳（毫秒）
                raw_time = item.get("time") or item.get("datetime") or item.get("ts")
                if isinstance(raw_time, (int, float)):
                    ts = raw_time / 1000 if raw_time > 1e10 else raw_time
                    bar_time = datetime.utcfromtimestamp(ts)
                else:
                    bar_time = datetime.fromisoformat(str(raw_time))

                bar = KlineBar(
                    time=bar_time,
                    symbol=symbol,
                    freq=freq,
                    open=Decimal(str(item.get("open", 0))),
                    high=Decimal(str(item.get("high", 0))),
                    low=Decimal(str(item.get("low", 0))),
                    close=Decimal(str(item.get("close", 0))),
                    volume=int(item.get("volume", 0)),
                    amount=Decimal(str(item.get("amount", 0))),
                    turnover=Decimal(str(item.get("turnover", 0))),
                    vol_ratio=Decimal(str(item.get("vol_ratio", 0))),
                    limit_up=Decimal(str(item["limit_up"])) if item.get("limit_up") is not None else None,
                    limit_down=Decimal(str(item["limit_down"])) if item.get("limit_down") is not None else None,
                    adj_type=int(item.get("adj_type", 0)),
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("跳过无效 K 线数据 symbol=%s freq=%s: %s | raw=%s", symbol, freq, exc, item)
        return bars

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def fetch_kline(
        self,
        symbol: str,
        freq: str,
        start: date,
        end: date,
        adj_type: int = 0,
    ) -> list[KlineBar]:
        """
        获取历史 K 线数据。

        Args:
            symbol:   股票代码，如 "000001.SZ"
            freq:     K 线频率，支持 '1m','5m','15m','30m','60m','1d','1w','1M'
            start:    起始日期（含）
            end:      结束日期（含）
            adj_type: 复权类型 0=不复权 1=前复权 2=后复权

        Returns:
            按时间升序排列的 KlineBar 列表
        """
        if freq not in VALID_FREQS:
            raise ValueError(f"不支持的 K 线频率: {freq}，有效值: {VALID_FREQS}")

        params: dict[str, Any] = {
            "symbol": symbol,
            "period": FREQ_PARAM_MAP[freq],
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
            "adj": adj_type,
        }

        logger.debug("拉取 K 线 symbol=%s freq=%s %s~%s", symbol, freq, start, end)
        raw = await self._get("/kline", params)

        # 兼容 {"data": [...]} 或直接返回列表两种格式
        items: list[dict[str, Any]] = raw.get("data", raw) if isinstance(raw, dict) else raw
        bars = self._parse_kline_response(items, symbol, freq)
        bars.sort(key=lambda b: b.time)
        logger.info("获取 K 线完成 symbol=%s freq=%s 共 %d 条", symbol, freq, len(bars))
        return bars

    async def fetch_realtime_quote(self, symbols: list[str]) -> list[dict[str, Any]]:
        """
        拉取一批股票的实时快照行情（用于轮询订阅）。

        Returns:
            原始行情字典列表，每项至少包含 symbol、close、volume 等字段
        """
        params: dict[str, Any] = {"symbols": ",".join(symbols)}
        raw = await self._get("/quote/realtime", params)
        items: list[dict[str, Any]] = raw.get("data", raw) if isinstance(raw, dict) else raw
        return items

    async def subscribe_realtime(
        self,
        symbols: list[str],
        callback: Callable[[list[KlineBar]], Awaitable[None]],
        freq: str = "1m",
        interval: float = 10.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """
        实时行情轮询订阅（每 interval 秒拉取一次快照并回调）。

        Args:
            symbols:     订阅的股票代码列表
            callback:    异步回调函数，接收 list[KlineBar]
            freq:        K 线频率标记（写入 KlineBar.freq）
            interval:    轮询间隔秒数，默认 10 秒
            stop_event:  外部停止信号，置位后退出循环

        示例：
            stop = asyncio.Event()
            async def on_bars(bars):
                await repo.bulk_insert(bars)
            await client.subscribe_realtime(["000001.SZ"], on_bars, stop_event=stop)
        """
        if freq not in VALID_FREQS:
            raise ValueError(f"不支持的 K 线频率: {freq}")

        logger.info("启动实时行情轮询 symbols=%s freq=%s interval=%.1fs", symbols, freq, interval)

        while True:
            if stop_event and stop_event.is_set():
                logger.info("实时行情轮询已停止")
                break

            try:
                raw_quotes = await self.fetch_realtime_quote(symbols)
                bars = self._parse_kline_response(raw_quotes, symbol="", freq=freq)
                # 修正 symbol（实时快照每条数据自带 symbol 字段）
                for item, bar in zip(raw_quotes, bars):
                    if not bar.symbol:
                        bar.symbol = str(item.get("symbol", ""))

                if bars:
                    await callback(bars)
            except Exception as exc:  # noqa: BLE001
                logger.error("实时行情轮询异常: %s", exc)

            await asyncio.sleep(interval)
