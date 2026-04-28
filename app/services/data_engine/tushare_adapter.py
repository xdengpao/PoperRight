"""
Tushare 数据源适配器（主数据源）

通过 HTTP POST + Token 认证方式访问 Tushare 平台，负责：
- K 线行情数据获取（daily 接口）
- 财务报表数据获取（fina_indicator 接口）
- 资金流向数据获取（moneyflow 接口）
- 大盘指数数据获取（index_daily 接口）
- 数据源连通性检查（trade_cal 接口）

对应需求：1.1, 1.3, 1.4, 1.7
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import settings
from app.core.schemas import KlineBar
from app.services.data_engine.base_adapter import BaseDataSourceAdapter
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData

logger = logging.getLogger(__name__)


class TushareAPIError(Exception):
    """Tushare API 调用异常"""

    def __init__(self, message: str, api_name: str = "", code: int | None = None) -> None:
        self.api_name = api_name
        self.code = code
        super().__init__(message)


class TushareAdapter(BaseDataSourceAdapter):
    """
    Tushare 数据源适配器（主数据源）

    - 通过 settings.tushare_api_token 和 settings.tushare_api_url 访问
    - 提供 K 线、财务报表、资金流向、市场概览数据
    - 返回数据经内联转换为统一数据结构
    """

    def __init__(
        self,
        api_token: str | None = None,
        api_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_token = api_token or settings.tushare_api_token
        self._api_url = (api_url or settings.tushare_api_url).rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建持久 HTTP 客户端（延迟初始化，自动重建）。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # 内部 API 调用
    # ------------------------------------------------------------------

    async def _call_api(self, api_name: str, **params: Any) -> dict[str, Any]:
        """调用 Tushare HTTP API。

        Tushare 接口统一使用 POST 请求，请求体格式：
        {
            "api_name": "<接口名>",
            "token": "<API Token>",
            "params": {<业务参数>},
            "fields": ""
        }

        Args:
            api_name: Tushare 接口名称，如 "daily", "fina_indicator"
            **params: 业务参数，如 ts_code, start_date 等

        Returns:
            Tushare 返回的 data 字典，包含 fields 和 items

        Raises:
            TushareAPIError: API 调用失败或返回错误
        """
        # 清理 None 值参数
        clean_params = {k: v for k, v in params.items() if v is not None}
        # 日期类型转为字符串
        for k, v in clean_params.items():
            if isinstance(v, date):
                clean_params[k] = v.strftime("%Y%m%d")

        payload = {
            "api_name": api_name,
            "token": self._api_token,
            "params": clean_params,
            "fields": "",
        }

        try:
            client = await self._get_client()
            resp = await client.post(self._api_url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Tushare HTTP 错误 [%s] api=%s: %s",
                exc.response.status_code, api_name, exc,
            )
            raise TushareAPIError(
                f"Tushare HTTP {exc.response.status_code}",
                api_name=api_name,
                code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Tushare 网络错误 api=%s: %s", api_name, exc)
            raise TushareAPIError(
                f"Tushare 网络错误: {exc}", api_name=api_name
            ) from exc

        body = resp.json()

        # Tushare 返回格式: {"code": 0, "msg": "", "data": {"fields": [...], "items": [...]}}
        code = body.get("code", -1)
        if code != 0:
            msg = body.get("msg", "未知错误")
            logger.error("Tushare API 错误 api=%s code=%s msg=%s", api_name, code, msg)
            raise TushareAPIError(msg, api_name=api_name, code=code)

        data: dict[str, Any] = body.get("data") or {}
        return data

    # ------------------------------------------------------------------
    # 内部转换辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _rows_from_data(data: dict[str, Any]) -> list[dict[str, Any]]:
        """将 Tushare fields + items 格式转为 dict 列表。"""
        fields: list[str] = data.get("fields", [])
        items: list[list[Any]] = data.get("items", [])
        return [dict(zip(fields, row)) for row in items]

    @staticmethod
    def _safe_decimal(value: Any) -> Decimal:
        """安全转换为 Decimal，无效值返回 Decimal(0)。"""
        if value is None:
            return Decimal(0)
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal(0)

    @staticmethod
    def _safe_decimal_or_none(value: Any) -> Decimal | None:
        """安全转换为 Decimal，无效值返回 None。"""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """安全转换为 int。"""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _parse_trade_date(value: Any) -> datetime:
        """解析 Tushare 日期字符串 (YYYYMMDD) 为 datetime。"""
        if value is None:
            return datetime.utcnow()
        s = str(value).strip()
        try:
            return datetime.strptime(s[:8], "%Y%m%d")
        except ValueError:
            return datetime.utcnow()

    # ------------------------------------------------------------------
    # 公开接口：fetch_kline
    # ------------------------------------------------------------------

    async def fetch_kline(
        self, symbol: str, freq: str, start: date, end: date
    ) -> list[KlineBar]:
        """获取 K 线行情数据（Tushare daily 接口）。

        Args:
            symbol: 股票代码，如 "000001.SZ" 或 "000001"（自动补全后缀）
            freq:   K 线频率（当前仅支持 "D" 日线）
            start:  起始日期
            end:    结束日期

        Returns:
            KlineBar 列表，按时间升序排列
        """
        # 自动补全 Tushare 格式后缀
        if "." not in symbol:
            symbol = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"

        logger.debug("Tushare fetch_kline symbol=%s freq=%s %s~%s", symbol, freq, start, end)

        data = await self._call_api(
            "daily",
            ts_code=symbol,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )

        rows = self._rows_from_data(data)
        bars: list[KlineBar] = []
        for row in rows:
            bars.append(KlineBar(
                time=self._parse_trade_date(row.get("trade_date")),
                symbol=row.get("ts_code", symbol),
                freq=freq,
                open=self._safe_decimal(row.get("open")),
                high=self._safe_decimal(row.get("high")),
                low=self._safe_decimal(row.get("low")),
                close=self._safe_decimal(row.get("close")),
                volume=self._safe_int(row.get("vol")),
                amount=self._safe_decimal(row.get("amount")),
                turnover=self._safe_decimal(row.get("turnover_rate", 0)),
                vol_ratio=self._safe_decimal(row.get("volume_ratio", 0)),
            ))

        # Tushare 返回数据按日期降序，转为升序
        bars.sort(key=lambda b: b.time)
        logger.info("Tushare fetch_kline 完成 symbol=%s 共 %d 条", symbol, len(bars))
        return bars

    # ------------------------------------------------------------------
    # 公开接口：fetch_fundamentals
    # ------------------------------------------------------------------

    async def fetch_fundamentals(self, symbol: str) -> FundamentalsData:
        """获取个股财务数据（Tushare fina_indicator 接口）。

        Args:
            symbol: 股票代码，如 "000001.SZ" 或 "000001"（自动补全后缀）

        Returns:
            FundamentalsData 数据对象
        """
        # 自动补全 Tushare 格式后缀
        if "." not in symbol:
            symbol = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"

        logger.debug("Tushare fetch_fundamentals symbol=%s", symbol)

        data = await self._call_api("fina_indicator", ts_code=symbol)
        rows = self._rows_from_data(data)

        if not rows:
            logger.warning("Tushare fina_indicator 无数据 symbol=%s", symbol)
            return FundamentalsData(symbol=symbol, updated_at=datetime.utcnow())

        # 取最新一期财务数据
        row = rows[0]
        result = FundamentalsData(
            symbol=symbol,
            name=row.get("name"),
            pe_ttm=self._safe_decimal_or_none(row.get("pe_ttm")),
            pb=self._safe_decimal_or_none(row.get("pb")),
            roe=self._safe_decimal_or_none(row.get("roe_dt")),
            net_profit_yoy=self._safe_decimal_or_none(row.get("netprofit_yoy")),
            revenue_yoy=self._safe_decimal_or_none(row.get("or_yoy")),
            updated_at=datetime.utcnow(),
            raw=row,
        )
        logger.info(
            "Tushare fetch_fundamentals 完成 symbol=%s pe_ttm=%s roe=%s",
            symbol, result.pe_ttm, result.roe,
        )
        return result

    # ------------------------------------------------------------------
    # 公开接口：fetch_money_flow
    # ------------------------------------------------------------------

    async def fetch_money_flow(
        self, symbol: str, trade_date: date
    ) -> MoneyFlowData:
        """获取个股资金流向数据（Tushare moneyflow 接口）。

        Args:
            symbol:     股票代码，如 "000001.SZ" 或 "000001"（自动补全后缀）
            trade_date: 交易日期

        Returns:
            MoneyFlowData 数据对象
        """
        # 自动补全 Tushare 格式后缀
        if "." not in symbol:
            symbol = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"

        logger.debug("Tushare fetch_money_flow symbol=%s date=%s", symbol, trade_date)

        data = await self._call_api(
            "moneyflow",
            ts_code=symbol,
            trade_date=trade_date.strftime("%Y%m%d"),
        )
        rows = self._rows_from_data(data)

        if not rows:
            logger.warning("Tushare moneyflow 无数据 symbol=%s date=%s", symbol, trade_date)
            return MoneyFlowData(
                symbol=symbol, trade_date=trade_date, updated_at=datetime.utcnow(),
            )

        row = rows[0]
        result = MoneyFlowData(
            symbol=symbol,
            trade_date=trade_date,
            main_net_inflow=self._safe_decimal_or_none(row.get("net_mf_amount")),
            main_inflow=self._safe_decimal_or_none(row.get("buy_elg_amount")),
            main_outflow=self._safe_decimal_or_none(row.get("sell_elg_amount")),
            large_order_net=self._safe_decimal_or_none(row.get("net_lg_amount")),
            updated_at=datetime.utcnow(),
            raw=row,
        )
        logger.info(
            "Tushare fetch_money_flow 完成 symbol=%s date=%s main_net=%s",
            symbol, trade_date, result.main_net_inflow,
        )
        return result

    # ------------------------------------------------------------------
    # 公开接口：fetch_market_overview
    # ------------------------------------------------------------------

    async def fetch_market_overview(self, trade_date: date) -> MarketOverview:
        """获取大盘指数数据（Tushare index_daily 接口）。

        Args:
            trade_date: 交易日期

        Returns:
            MarketOverview 数据对象
        """
        logger.debug("Tushare fetch_market_overview date=%s", trade_date)

        date_str = trade_date.strftime("%Y%m%d")

        # 查询主要指数：上证指数、深证成指、创业板指、科创50
        index_codes = {
            "000001.SH": ("sh_index", "sh_change_pct"),
            "399001.SZ": ("sz_index", "sz_change_pct"),
            "399006.SZ": ("cyb_index", "cyb_change_pct"),
            "000688.SH": ("kcb_index", "kcb_change_pct"),
        }

        overview_kwargs: dict[str, Any] = {"trade_date": trade_date}

        for ts_code, (idx_field, pct_field) in index_codes.items():
            try:
                data = await self._call_api(
                    "index_daily", ts_code=ts_code, trade_date=date_str,
                )
                rows = self._rows_from_data(data)
                if rows:
                    row = rows[0]
                    overview_kwargs[idx_field] = self._safe_decimal_or_none(row.get("close"))
                    overview_kwargs[pct_field] = self._safe_decimal_or_none(row.get("pct_chg"))
            except TushareAPIError:
                logger.warning("Tushare index_daily 获取失败 ts_code=%s", ts_code)

        result = MarketOverview(
            updated_at=datetime.utcnow(),
            **overview_kwargs,
        )
        logger.info(
            "Tushare fetch_market_overview 完成 date=%s sh=%s sz=%s",
            trade_date, result.sh_index, result.sz_index,
        )
        return result

    # ------------------------------------------------------------------
    # 公开接口：health_check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """检查 Tushare 数据源连通性（trade_cal 接口）。

        Returns:
            True 表示连通，False 表示不可用
        """
        try:
            await self._call_api("trade_cal", exchange="SSE", is_open="1")
            logger.debug("Tushare health_check 通过")
            return True
        except Exception as exc:
            logger.warning("Tushare health_check 失败: %s", exc)
            return False
