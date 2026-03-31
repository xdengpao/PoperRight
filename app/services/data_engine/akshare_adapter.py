"""
AkShare 数据源适配器（备用数据源）

通过 akshare Python SDK 访问 AkShare 平台，负责：
- K 线行情数据获取（stock_zh_a_hist 接口）
- 财务数据获取（stock_financial_analysis_indicator 接口）
- 资金流向数据获取（stock_individual_fund_flow 接口）
- 大盘指数数据获取（stock_zh_index_daily 接口）
- 数据源连通性检查（stock_zh_a_spot_em 接口）

AkShare SDK 为同步调用，通过 asyncio.to_thread() 在线程池中执行。

对应需求：1.1, 1.4, 1.5, 1.8
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.config import settings
from app.core.schemas import KlineBar
from app.services.data_engine.base_adapter import BaseDataSourceAdapter
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData

# AkShare 可能未安装，优雅处理
try:
    import akshare as ak  # type: ignore[import-untyped]
except ImportError:
    ak = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class AkShareAPIError(Exception):
    """AkShare API 调用异常"""

    def __init__(self, message: str, api_name: str = "") -> None:
        self.api_name = api_name
        super().__init__(message)


class AkShareAdapter(BaseDataSourceAdapter):
    """
    AkShare 数据源适配器（备用数据源）

    - 通过 settings.akshare_request_timeout 读取超时配置
    - 通过 asyncio.to_thread() 在线程池中执行同步 akshare SDK 调用
    - 提供 K 线、财务报表、资金流向、市场概览数据
    - 返回数据经内联转换为统一数据结构
    """

    def __init__(self, timeout: float | None = None) -> None:
        self._timeout = timeout or settings.akshare_request_timeout
        if ak is None:
            logger.warning("akshare 未安装，AkShareAdapter 功能不可用")

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_akshare() -> None:
        """确保 akshare 已安装。"""
        if ak is None:
            raise AkShareAPIError(
                "akshare 未安装，请执行 pip install akshare",
                api_name="import",
            )

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
            return int(float(value))
        except (ValueError, TypeError):
            return default

    # ------------------------------------------------------------------
    # 公开接口：fetch_kline
    # ------------------------------------------------------------------

    async def fetch_kline(
        self, symbol: str, freq: str, start: date, end: date
    ) -> list[KlineBar]:
        """获取 K 线行情数据（AkShare stock_zh_a_hist 接口）。

        AkShare 返回 DataFrame 列名（中文）：
        日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率

        Args:
            symbol: 股票代码，如 "000001" 或 "000001.SZ"（自动去除后缀）
            freq:   K 线频率（当前仅支持 "D" 日线）
            start:  起始日期
            end:    结束日期

        Returns:
            KlineBar 列表，按时间升序排列
        """
        self._ensure_akshare()
        clean_symbol = symbol.split(".")[0]

        logger.debug(
            "AkShare fetch_kline symbol=%s freq=%s %s~%s",
            clean_symbol, freq, start, end,
        )

        try:
            raw_df = await asyncio.to_thread(
                ak.stock_zh_a_hist,
                symbol=clean_symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        except Exception as exc:
            logger.error("AkShare stock_zh_a_hist 调用失败: %s", exc)
            raise AkShareAPIError(
                f"AkShare K线数据获取失败: {exc}",
                api_name="stock_zh_a_hist",
            ) from exc

        if raw_df is None or raw_df.empty:
            logger.warning("AkShare stock_zh_a_hist 无数据 symbol=%s", clean_symbol)
            return []

        bars: list[KlineBar] = []
        for _, row in raw_df.iterrows():
            # 解析日期
            date_val = row.get("日期")
            if date_val is not None:
                try:
                    dt = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
                except ValueError:
                    dt = datetime.utcnow()
            else:
                dt = datetime.utcnow()

            bars.append(KlineBar(
                time=dt,
                symbol=symbol,
                freq=freq,
                open=self._safe_decimal(row.get("开盘")),
                high=self._safe_decimal(row.get("最高")),
                low=self._safe_decimal(row.get("最低")),
                close=self._safe_decimal(row.get("收盘")),
                volume=self._safe_int(row.get("成交量")),
                amount=self._safe_decimal(row.get("成交额")),
                turnover=self._safe_decimal(row.get("换手率", 0)),
                vol_ratio=Decimal(0),  # AkShare 不直接提供量比
            ))

        bars.sort(key=lambda b: b.time)
        logger.info("AkShare fetch_kline 完成 symbol=%s 共 %d 条", clean_symbol, len(bars))
        return bars

    # ------------------------------------------------------------------
    # 公开接口：fetch_fundamentals
    # ------------------------------------------------------------------

    async def fetch_fundamentals(self, symbol: str) -> FundamentalsData:
        """获取个股财务数据（AkShare stock_financial_analysis_indicator 接口）。

        Args:
            symbol: 股票代码，如 "000001" 或 "000001.SZ"

        Returns:
            FundamentalsData 数据对象
        """
        self._ensure_akshare()
        clean_symbol = symbol.split(".")[0]

        logger.debug("AkShare fetch_fundamentals symbol=%s", clean_symbol)

        try:
            raw_df = await asyncio.to_thread(
                ak.stock_financial_analysis_indicator,
                symbol=clean_symbol,
            )
        except Exception as exc:
            logger.error("AkShare stock_financial_analysis_indicator 调用失败: %s", exc)
            raise AkShareAPIError(
                f"AkShare 财务数据获取失败: {exc}",
                api_name="stock_financial_analysis_indicator",
            ) from exc

        if raw_df is None or raw_df.empty:
            logger.warning("AkShare 财务数据无数据 symbol=%s", clean_symbol)
            return FundamentalsData(symbol=symbol, updated_at=datetime.utcnow())

        # 取最新一期数据（第一行）
        row = raw_df.iloc[0]
        result = FundamentalsData(
            symbol=symbol,
            roe=self._safe_decimal_or_none(row.get("净资产收益率(%)")),
            net_profit_yoy=self._safe_decimal_or_none(row.get("净利润同比增长率(%)")),
            revenue_yoy=self._safe_decimal_or_none(row.get("主营业务收入同比增长率(%)")),
            updated_at=datetime.utcnow(),
            raw=row.to_dict() if hasattr(row, "to_dict") else {},
        )
        logger.info(
            "AkShare fetch_fundamentals 完成 symbol=%s roe=%s",
            clean_symbol, result.roe,
        )
        return result

    # ------------------------------------------------------------------
    # 公开接口：fetch_money_flow
    # ------------------------------------------------------------------

    async def fetch_money_flow(
        self, symbol: str, trade_date: date
    ) -> MoneyFlowData:
        """获取个股资金流向数据（AkShare stock_individual_fund_flow 接口）。

        Args:
            symbol:     股票代码，如 "000001" 或 "000001.SZ"
            trade_date: 交易日期

        Returns:
            MoneyFlowData 数据对象
        """
        self._ensure_akshare()
        clean_symbol = symbol.split(".")[0]

        logger.debug("AkShare fetch_money_flow symbol=%s date=%s", clean_symbol, trade_date)

        try:
            raw_df = await asyncio.to_thread(
                ak.stock_individual_fund_flow,
                stock=clean_symbol,
                market="sh",
            )
        except Exception as exc:
            logger.error("AkShare stock_individual_fund_flow 调用失败: %s", exc)
            raise AkShareAPIError(
                f"AkShare 资金流向获取失败: {exc}",
                api_name="stock_individual_fund_flow",
            ) from exc

        if raw_df is None or raw_df.empty:
            logger.warning("AkShare 资金流向无数据 symbol=%s", clean_symbol)
            return MoneyFlowData(
                symbol=symbol, trade_date=trade_date, updated_at=datetime.utcnow(),
            )

        # 尝试匹配指定日期的数据行
        target_row = None
        date_str = trade_date.strftime("%Y-%m-%d")
        if "日期" in raw_df.columns:
            matched = raw_df[raw_df["日期"].astype(str).str[:10] == date_str]
            if not matched.empty:
                target_row = matched.iloc[0]

        # 未匹配到指定日期则取最新一行
        if target_row is None:
            target_row = raw_df.iloc[0]

        result = MoneyFlowData(
            symbol=symbol,
            trade_date=trade_date,
            main_net_inflow=self._safe_decimal_or_none(target_row.get("主力净流入-净额")),
            main_inflow=self._safe_decimal_or_none(target_row.get("主力净流入-净占比")),
            large_order_net=self._safe_decimal_or_none(target_row.get("超大单净流入-净额")),
            updated_at=datetime.utcnow(),
            raw=target_row.to_dict() if hasattr(target_row, "to_dict") else {},
        )
        logger.info(
            "AkShare fetch_money_flow 完成 symbol=%s date=%s main_net=%s",
            clean_symbol, trade_date, result.main_net_inflow,
        )
        return result

    # ------------------------------------------------------------------
    # 公开接口：fetch_market_overview
    # ------------------------------------------------------------------

    async def fetch_market_overview(self, trade_date: date) -> MarketOverview:
        """获取大盘指数数据（AkShare stock_zh_index_daily 接口）。

        Args:
            trade_date: 交易日期

        Returns:
            MarketOverview 数据对象
        """
        self._ensure_akshare()

        logger.debug("AkShare fetch_market_overview date=%s", trade_date)

        try:
            raw_df = await asyncio.to_thread(
                ak.stock_zh_index_daily,
                symbol="sh000001",
            )
        except Exception as exc:
            logger.error("AkShare stock_zh_index_daily 调用失败: %s", exc)
            raise AkShareAPIError(
                f"AkShare 大盘数据获取失败: {exc}",
                api_name="stock_zh_index_daily",
            ) from exc

        overview_kwargs: dict[str, Any] = {"trade_date": trade_date}

        if raw_df is not None and not raw_df.empty:
            # 尝试匹配指定日期
            date_str = trade_date.strftime("%Y-%m-%d")
            target_row = None
            if "date" in raw_df.columns:
                matched = raw_df[raw_df["date"].astype(str).str[:10] == date_str]
                if not matched.empty:
                    target_row = matched.iloc[0]

            if target_row is None:
                target_row = raw_df.iloc[-1]

            overview_kwargs["sh_index"] = self._safe_decimal_or_none(target_row.get("close"))
            overview_kwargs["sh_change_pct"] = self._safe_decimal_or_none(
                target_row.get("pct_chg", target_row.get("change"))
            )

        result = MarketOverview(
            updated_at=datetime.utcnow(),
            **overview_kwargs,
        )
        logger.info(
            "AkShare fetch_market_overview 完成 date=%s sh=%s",
            trade_date, result.sh_index,
        )
        return result

    # ------------------------------------------------------------------
    # 公开接口：health_check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """检查 AkShare 数据源连通性（使用轻量级交易日历接口）。

        Returns:
            True 表示连通，False 表示不可用
        """
        if ak is None:
            logger.warning("AkShare health_check 失败: akshare 未安装")
            return False

        try:
            # 使用交易日历接口，数据量极小，比 stock_zh_index_spot_em 更快
            await asyncio.wait_for(
                asyncio.to_thread(ak.tool_trade_date_hist_sina),
                timeout=self._timeout,
            )
            logger.debug("AkShare health_check 通过")
            return True
        except asyncio.TimeoutError:
            logger.warning("AkShare health_check 超时 (%ss)", self._timeout)
            return False
        except Exception as exc:
            # 如果 tool_trade_date_hist_sina 不可用，回退到 stock_zh_index_spot_em
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(ak.stock_zh_index_spot_em),
                    timeout=self._timeout,
                )
                logger.debug("AkShare health_check 通过（回退接口）")
                return True
            except Exception as exc2:
                logger.warning("AkShare health_check 失败: %s / %s", exc, exc2)
                return False
