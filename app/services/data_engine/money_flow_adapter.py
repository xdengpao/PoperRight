"""
资金数据适配器

MoneyFlowAdapter 封装第三方行情 API，提供：
- 主力资金流向、北向资金、龙虎榜数据拉取
- 大盘指数、板块数据、涨跌家数、市场情绪指标同步

对应需求：
- 1.4：实时同步主力资金流向、北向资金、龙虎榜、大宗交易、盘口委比/内外盘
- 1.5：实时同步大盘指数、行业/概念板块、涨跌家数、涨跌停数量、市场情绪指标
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class MoneyFlowData:
    """个股资金流向数据"""
    symbol: str
    trade_date: date
    # 主力资金
    main_net_inflow: Decimal | None = None      # 主力净流入（元）
    main_inflow: Decimal | None = None          # 主力流入（元）
    main_outflow: Decimal | None = None         # 主力流出（元）
    main_net_inflow_pct: Decimal | None = None  # 主力净流入占比（%）
    # 大单（超大单 + 大单）
    large_order_net: Decimal | None = None      # 大单净流入（元）
    large_order_ratio: Decimal | None = None    # 大单成交占比（%）
    # 北向资金（沪深港通）
    north_net_inflow: Decimal | None = None     # 北向净流入（元）
    north_hold_ratio: Decimal | None = None     # 北向持股比例（%）
    # 龙虎榜
    on_dragon_tiger: bool = False               # 是否上龙虎榜
    dragon_tiger_net: Decimal | None = None     # 龙虎榜净买入（元）
    # 大宗交易
    block_trade_amount: Decimal | None = None   # 大宗交易金额（元）
    block_trade_discount: Decimal | None = None # 大宗交易折价率（%）
    # 盘口
    bid_ask_ratio: Decimal | None = None        # 委比（%）
    inner_outer_ratio: Decimal | None = None    # 内外盘比
    # 元数据
    updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class SectorData:
    """板块数据"""
    sector_code: str
    sector_name: str
    sector_type: str | None = None          # 'INDUSTRY' | 'CONCEPT'
    change_pct: Decimal | None = None       # 涨跌幅（%）
    turnover: Decimal | None = None         # 换手率（%）
    net_inflow: Decimal | None = None       # 资金净流入（元）
    leading_stock: str | None = None        # 领涨股
    stocks_count: int | None = None         # 成分股数量
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class MarketOverview:
    """大盘市场概览数据"""
    trade_date: date
    # 大盘指数
    sh_index: Decimal | None = None         # 上证指数
    sh_change_pct: Decimal | None = None    # 上证涨跌幅（%）
    sz_index: Decimal | None = None         # 深证成指
    sz_change_pct: Decimal | None = None    # 深证涨跌幅（%）
    cyb_index: Decimal | None = None        # 创业板指
    cyb_change_pct: Decimal | None = None   # 创业板涨跌幅（%）
    kcb_index: Decimal | None = None        # 科创50
    kcb_change_pct: Decimal | None = None   # 科创50涨跌幅（%）
    # 涨跌家数
    advance_count: int | None = None        # 上涨家数
    decline_count: int | None = None        # 下跌家数
    flat_count: int | None = None           # 平盘家数
    # 涨跌停数量
    limit_up_count: int | None = None       # 涨停家数
    limit_down_count: int | None = None     # 跌停家数
    # 市场情绪
    total_amount: Decimal | None = None     # 全市场成交额（元）
    north_net_inflow: Decimal | None = None # 北向资金净流入（元）
    market_sentiment: Decimal | None = None # 市场情绪指数（0-100）
    fear_greed_index: Decimal | None = None # 恐贪指数
    # 板块数据
    top_sectors: list[SectorData] = field(default_factory=list)
    # 元数据
    updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# 适配器
# ---------------------------------------------------------------------------

class MoneyFlowAdapter:
    """
    资金数据适配器（异步，基于 httpx.AsyncClient）

    使用方式：
        async with MoneyFlowAdapter() as adapter:
            flow = await adapter.fetch_money_flow("000001.SZ", date.today())
            overview = await adapter.fetch_market_overview(date.today())
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

    async def __aenter__(self) -> "MoneyFlowAdapter":
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
                "MoneyFlowAdapter 未初始化，请使用 async with 语句"
            )
        return self._client

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        client = self._ensure_client()
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("资金 API 请求失败 [%s] %s: %s", exc.response.status_code, path, exc)
            raise
        except httpx.RequestError as exc:
            logger.error("资金 API 网络错误 %s: %s", path, exc)
            raise

    # ------------------------------------------------------------------
    # 解析层（实际对接时修改字段映射）
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_money_flow(raw: dict[str, Any], symbol: str, trade_date: date) -> MoneyFlowData:
        data = raw.get("data", raw) if isinstance(raw, dict) else {}

        def _dec(key: str) -> Decimal | None:
            v = data.get(key)
            return Decimal(str(v)) if v is not None else None

        return MoneyFlowData(
            symbol=symbol,
            trade_date=trade_date,
            main_net_inflow=_dec("main_net_inflow"),
            main_inflow=_dec("main_inflow"),
            main_outflow=_dec("main_outflow"),
            main_net_inflow_pct=_dec("main_net_inflow_pct"),
            large_order_net=_dec("large_order_net"),
            large_order_ratio=_dec("large_order_ratio"),
            north_net_inflow=_dec("north_net_inflow"),
            north_hold_ratio=_dec("north_hold_ratio"),
            on_dragon_tiger=bool(data.get("on_dragon_tiger", False)),
            dragon_tiger_net=_dec("dragon_tiger_net"),
            block_trade_amount=_dec("block_trade_amount"),
            block_trade_discount=_dec("block_trade_discount"),
            bid_ask_ratio=_dec("bid_ask_ratio"),
            inner_outer_ratio=_dec("inner_outer_ratio"),
            updated_at=datetime.utcnow(),
            raw=data,
        )

    @staticmethod
    def _parse_sector(item: dict[str, Any]) -> SectorData:
        def _dec(key: str) -> Decimal | None:
            v = item.get(key)
            return Decimal(str(v)) if v is not None else None

        return SectorData(
            sector_code=str(item.get("sector_code", "")),
            sector_name=str(item.get("sector_name", "")),
            sector_type=item.get("sector_type"),
            change_pct=_dec("change_pct"),
            turnover=_dec("turnover"),
            net_inflow=_dec("net_inflow"),
            leading_stock=item.get("leading_stock"),
            stocks_count=int(item["stocks_count"]) if item.get("stocks_count") is not None else None,
            raw=item,
        )

    @classmethod
    def _parse_market_overview(cls, raw: dict[str, Any], trade_date: date) -> MarketOverview:
        data = raw.get("data", raw) if isinstance(raw, dict) else {}

        def _dec(key: str) -> Decimal | None:
            v = data.get(key)
            return Decimal(str(v)) if v is not None else None

        def _int(key: str) -> int | None:
            v = data.get(key)
            return int(v) if v is not None else None

        sectors_raw: list[dict[str, Any]] = data.get("top_sectors", [])
        top_sectors = [cls._parse_sector(s) for s in sectors_raw]

        return MarketOverview(
            trade_date=trade_date,
            sh_index=_dec("sh_index"),
            sh_change_pct=_dec("sh_change_pct"),
            sz_index=_dec("sz_index"),
            sz_change_pct=_dec("sz_change_pct"),
            cyb_index=_dec("cyb_index"),
            cyb_change_pct=_dec("cyb_change_pct"),
            kcb_index=_dec("kcb_index"),
            kcb_change_pct=_dec("kcb_change_pct"),
            advance_count=_int("advance_count"),
            decline_count=_int("decline_count"),
            flat_count=_int("flat_count"),
            limit_up_count=_int("limit_up_count"),
            limit_down_count=_int("limit_down_count"),
            total_amount=_dec("total_amount"),
            north_net_inflow=_dec("north_net_inflow"),
            market_sentiment=_dec("market_sentiment"),
            fear_greed_index=_dec("fear_greed_index"),
            top_sectors=top_sectors,
            updated_at=datetime.utcnow(),
            raw=data,
        )

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def fetch_money_flow(self, symbol: str, trade_date: date) -> MoneyFlowData:
        """
        拉取个股资金流向数据（主力资金、北向资金、龙虎榜、大宗交易、盘口）。

        Args:
            symbol:     股票代码，如 "000001.SZ"
            trade_date: 交易日期

        Returns:
            MoneyFlowData 数据对象
        """
        logger.debug("拉取资金流向 symbol=%s date=%s", symbol, trade_date)
        raw = await self._get("/money_flow", {
            "symbol": symbol,
            "date": trade_date.strftime("%Y%m%d"),
        })
        result = self._parse_money_flow(raw, symbol, trade_date)
        logger.info(
            "获取资金流向完成 symbol=%s date=%s main_net_inflow=%s",
            symbol, trade_date, result.main_net_inflow,
        )
        return result

    async def fetch_market_overview(self, trade_date: date) -> MarketOverview:
        """
        拉取大盘市场概览数据（指数、涨跌家数、涨跌停数量、板块、市场情绪）。

        Args:
            trade_date: 交易日期

        Returns:
            MarketOverview 数据对象
        """
        logger.debug("拉取大盘概览 date=%s", trade_date)
        raw = await self._get("/market_overview", {
            "date": trade_date.strftime("%Y%m%d"),
        })
        result = self._parse_market_overview(raw, trade_date)
        logger.info(
            "获取大盘概览完成 date=%s sh_index=%s advance=%s decline=%s limit_up=%s",
            trade_date, result.sh_index, result.advance_count,
            result.decline_count, result.limit_up_count,
        )
        return result

    async def fetch_north_bound_flow(self, trade_date: date) -> dict[str, Any]:
        """
        拉取北向资金（沪深港通）汇总数据。

        Returns:
            原始北向资金数据字典
        """
        logger.debug("拉取北向资金 date=%s", trade_date)
        raw = await self._get("/north_flow", {"date": trade_date.strftime("%Y%m%d")})
        data: dict[str, Any] = raw.get("data", raw) if isinstance(raw, dict) else {}
        logger.info("获取北向资金完成 date=%s", trade_date)
        return data

    async def fetch_dragon_tiger_list(self, trade_date: date) -> list[dict[str, Any]]:
        """
        拉取龙虎榜数据。

        Returns:
            龙虎榜条目列表
        """
        logger.debug("拉取龙虎榜 date=%s", trade_date)
        raw = await self._get("/dragon_tiger", {"date": trade_date.strftime("%Y%m%d")})
        items: list[dict[str, Any]] = raw.get("data", raw) if isinstance(raw, dict) else raw
        logger.info("获取龙虎榜完成 date=%s 共 %d 条", trade_date, len(items))
        return items

    async def fetch_sector_data(
        self,
        trade_date: date,
        sector_type: str | None = None,
    ) -> list[SectorData]:
        """
        拉取行业/概念板块数据。

        Args:
            trade_date:  交易日期
            sector_type: 'INDUSTRY'（行业）| 'CONCEPT'（概念）| None（全部）

        Returns:
            SectorData 列表
        """
        params: dict[str, Any] = {"date": trade_date.strftime("%Y%m%d")}
        if sector_type:
            params["type"] = sector_type

        logger.debug("拉取板块数据 date=%s type=%s", trade_date, sector_type)
        raw = await self._get("/sector", params)
        items: list[dict[str, Any]] = raw.get("data", raw) if isinstance(raw, dict) else raw
        sectors = [self._parse_sector(item) for item in items]
        logger.info("获取板块数据完成 date=%s 共 %d 个板块", trade_date, len(sectors))
        return sectors
