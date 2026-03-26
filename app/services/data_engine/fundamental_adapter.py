"""
基本面数据适配器

FundamentalAdapter 封装第三方行情 API，提供：
- 个股财务报表、业绩预告、股东数据拉取
- 质押率、市值、PE/PB/ROE 估值数据同步
- 写入 stock_info 表（upsert）

对应需求 1.3：每日更新财务报表、业绩预告、违规处罚、股东减持、质押率、市值、PE/PB/ROE
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class FundamentalsData:
    """个股基本面数据"""
    symbol: str
    name: str | None = None
    market: str | None = None           # SH/SZ/BJ
    board: str | None = None            # 主板/创业板/科创板/北交所
    list_date: date | None = None
    is_st: bool = False
    is_delisted: bool = False
    # 估值
    pe_ttm: Decimal | None = None       # 市盈率（TTM）
    pb: Decimal | None = None           # 市净率
    roe: Decimal | None = None          # 净资产收益率
    market_cap: Decimal | None = None   # 总市值（元）
    # 财务
    net_profit_yoy: Decimal | None = None   # 净利润同比增长率（%）
    revenue_yoy: Decimal | None = None      # 营收同比增长率（%）
    # 股东/质押
    pledge_ratio: Decimal | None = None     # 质押率（%）
    major_holder_ratio: Decimal | None = None  # 大股东持股比例（%）
    # 业绩预告
    forecast_type: str | None = None        # 预增/预减/扭亏/续亏/续盈/略增/略减
    forecast_net_profit_low: Decimal | None = None
    forecast_net_profit_high: Decimal | None = None
    # 元数据
    updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# 适配器
# ---------------------------------------------------------------------------

class FundamentalAdapter:
    """
    基本面数据适配器（异步，基于 httpx.AsyncClient）

    使用方式：
        async with FundamentalAdapter() as adapter:
            data = await adapter.fetch_fundamentals("000001.SZ")
            await adapter.sync_stock_info("000001.SZ", session)
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

    async def __aenter__(self) -> "FundamentalAdapter":
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
                "FundamentalAdapter 未初始化，请使用 async with 语句"
            )
        return self._client

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        client = self._ensure_client()
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("基本面 API 请求失败 [%s] %s: %s", exc.response.status_code, path, exc)
            raise
        except httpx.RequestError as exc:
            logger.error("基本面 API 网络错误 %s: %s", path, exc)
            raise

    # ------------------------------------------------------------------
    # 解析层（实际对接时修改字段映射）
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: dict[str, Any], symbol: str) -> FundamentalsData:
        """将 API 返回的原始 JSON 解析为 FundamentalsData。"""
        data = raw.get("data", raw) if isinstance(raw, dict) else {}

        def _dec(key: str) -> Decimal | None:
            v = data.get(key)
            return Decimal(str(v)) if v is not None else None

        def _date(key: str) -> date | None:
            v = data.get(key)
            if v is None:
                return None
            try:
                return date.fromisoformat(str(v)[:10])
            except ValueError:
                return None

        return FundamentalsData(
            symbol=symbol,
            name=data.get("name"),
            market=data.get("market"),
            board=data.get("board"),
            list_date=_date("list_date"),
            is_st=bool(data.get("is_st", False)),
            is_delisted=bool(data.get("is_delisted", False)),
            pe_ttm=_dec("pe_ttm"),
            pb=_dec("pb"),
            roe=_dec("roe"),
            market_cap=_dec("market_cap"),
            net_profit_yoy=_dec("net_profit_yoy"),
            revenue_yoy=_dec("revenue_yoy"),
            pledge_ratio=_dec("pledge_ratio"),
            major_holder_ratio=_dec("major_holder_ratio"),
            forecast_type=data.get("forecast_type"),
            forecast_net_profit_low=_dec("forecast_net_profit_low"),
            forecast_net_profit_high=_dec("forecast_net_profit_high"),
            updated_at=datetime.utcnow(),
            raw=data,
        )

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def fetch_fundamentals(self, symbol: str) -> FundamentalsData:
        """
        拉取个股基本面数据（财务报表、估值、质押率、业绩预告等）。

        Args:
            symbol: 股票代码，如 "000001.SZ"

        Returns:
            FundamentalsData 数据对象
        """
        logger.debug("拉取基本面数据 symbol=%s", symbol)
        raw = await self._get("/fundamental", {"symbol": symbol})
        result = self._parse_response(raw, symbol)
        logger.info("获取基本面数据完成 symbol=%s pe_ttm=%s pb=%s roe=%s", symbol, result.pe_ttm, result.pb, result.roe)
        return result

    async def sync_stock_info(self, symbol: str, session: AsyncSession) -> FundamentalsData:
        """
        拉取基本面数据并 upsert 写入 stock_info 表。

        Args:
            symbol:  股票代码
            session: SQLAlchemy 异步 Session

        Returns:
            写入的 FundamentalsData 对象
        """
        data = await self.fetch_fundamentals(symbol)

        upsert_sql = text("""
            INSERT INTO stock_info (
                symbol, name, market, board, list_date,
                is_st, is_delisted, pledge_ratio,
                pe_ttm, pb, roe, market_cap, updated_at
            ) VALUES (
                :symbol, :name, :market, :board, :list_date,
                :is_st, :is_delisted, :pledge_ratio,
                :pe_ttm, :pb, :roe, :market_cap, :updated_at
            )
            ON CONFLICT (symbol) DO UPDATE SET
                name         = EXCLUDED.name,
                market       = EXCLUDED.market,
                board        = EXCLUDED.board,
                list_date    = EXCLUDED.list_date,
                is_st        = EXCLUDED.is_st,
                is_delisted  = EXCLUDED.is_delisted,
                pledge_ratio = EXCLUDED.pledge_ratio,
                pe_ttm       = EXCLUDED.pe_ttm,
                pb           = EXCLUDED.pb,
                roe          = EXCLUDED.roe,
                market_cap   = EXCLUDED.market_cap,
                updated_at   = EXCLUDED.updated_at
        """)

        await session.execute(upsert_sql, {
            "symbol":       data.symbol,
            "name":         data.name,
            "market":       data.market,
            "board":        data.board,
            "list_date":    data.list_date,
            "is_st":        data.is_st,
            "is_delisted":  data.is_delisted,
            "pledge_ratio": data.pledge_ratio,
            "pe_ttm":       data.pe_ttm,
            "pb":           data.pb,
            "roe":          data.roe,
            "market_cap":   data.market_cap,
            "updated_at":   data.updated_at,
        })
        await session.commit()
        logger.info("stock_info upsert 完成 symbol=%s", symbol)
        return data

    async def fetch_shareholder_data(self, symbol: str) -> dict[str, Any]:
        """
        拉取股东减持、质押率等股东相关数据。

        Returns:
            原始股东数据字典
        """
        logger.debug("拉取股东数据 symbol=%s", symbol)
        raw = await self._get("/shareholder", {"symbol": symbol})
        data: dict[str, Any] = raw.get("data", raw) if isinstance(raw, dict) else {}
        logger.info("获取股东数据完成 symbol=%s", symbol)
        return data

    async def fetch_performance_forecast(self, symbol: str) -> dict[str, Any]:
        """
        拉取业绩预告数据。

        Returns:
            原始业绩预告字典
        """
        logger.debug("拉取业绩预告 symbol=%s", symbol)
        raw = await self._get("/forecast", {"symbol": symbol})
        data: dict[str, Any] = raw.get("data", raw) if isinstance(raw, dict) else {}
        logger.info("获取业绩预告完成 symbol=%s", symbol)
        return data
