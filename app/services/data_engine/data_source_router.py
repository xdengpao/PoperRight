"""
数据源路由与故障转移管理器

DataSourceRouter 统一管理 Tushare（主）和 AkShare（备）两个数据源，
实现优先使用 Tushare、失败自动切换 AkShare 的故障转移逻辑。

对应需求：
- 1.9：Tushare 失败时自动切换至 AkShare
- 1.10：两个数据源均不可用时记录错误日志并推送告警
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.core.schemas import Alert, AlertType, KlineBar
from app.services.data_engine.base_adapter import (
    DataSourceUnavailableError,
)
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData
from app.services.data_engine.tushare_adapter import TushareAdapter
from app.services.data_engine.akshare_adapter import AkShareAdapter

logger = logging.getLogger(__name__)


class DataSourceRouter:
    """
    数据源路由器

    - 所有数据请求优先通过 Tushare 获取（需求 1.1）
    - Tushare 调用失败时自动切换至 AkShare（需求 1.9）
    - 两个数据源均不可用时记录错误日志并推送告警，抛出异常（需求 1.10）
    """

    def __init__(
        self,
        tushare: TushareAdapter | None = None,
        akshare: AkShareAdapter | None = None,
        alert_service: Any | None = None,
    ) -> None:
        self._primary = tushare or TushareAdapter()
        self._fallback = akshare or AkShareAdapter()
        self._alert_service = alert_service

    async def fetch_with_fallback(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        带故障转移的数据获取。

        1. 优先调用 Tushare（主数据源）
        2. Tushare 失败 → 记录 warning 日志，自动切换 AkShare（备用数据源）
        3. 两者均失败 → 记录 error 日志 + 推送 DANGER 告警 + 抛出 DataSourceUnavailableError
        """
        primary_err: Exception | None = None

        # 尝试主数据源（Tushare）
        try:
            primary_method = getattr(self._primary, method_name)
            return await primary_method(*args, **kwargs)
        except Exception as exc:
            primary_err = exc
            logger.warning(
                "Tushare 数据源调用失败 method=%s: %s，切换至 AkShare",
                method_name,
                exc,
            )

        # 尝试备用数据源（AkShare）
        try:
            fallback_method = getattr(self._fallback, method_name)
            return await fallback_method(*args, **kwargs)
        except Exception as fallback_err:
            logger.error(
                "Tushare 和 AkShare 均不可用 method=%s: primary=%s fallback=%s",
                method_name,
                primary_err,
                fallback_err,
            )

            # 推送数据源异常告警（需求 1.10）
            if self._alert_service is not None:
                try:
                    await self._alert_service.push_alert(
                        user_id="system",
                        alert=Alert(
                            user_id="system",
                            alert_type=AlertType.SYSTEM,
                            title="数据源异常",
                            message=f"数据源异常：Tushare 和 AkShare 均不可用（{method_name}）",
                        ),
                    )
                except Exception as alert_exc:
                    logger.warning("推送数据源异常告警失败: %s", alert_exc)

            raise DataSourceUnavailableError(
                f"所有数据源均不可用（{method_name}）: "
                f"Tushare={primary_err}, AkShare={fallback_err}"
            )


    async def fetch_with_fallback_info(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, str, bool]:
        """
        带故障转移的数据获取，返回数据源标识信息。

        返回三元组 (data, data_source_name, is_fallback)：
        - 主数据源成功：(data, "Tushare", False)
        - 回退成功：(data, "AkShare", True)
        - 两者均失败：同 fetch_with_fallback()，记录日志 + 推送告警 + 抛出异常
        """
        primary_err: Exception | None = None

        # 尝试主数据源（Tushare）
        try:
            primary_method = getattr(self._primary, method_name)
            result = await primary_method(*args, **kwargs)
            return result, "Tushare", False
        except Exception as exc:
            primary_err = exc
            logger.warning(
                "Tushare 数据源调用失败 method=%s: %s，切换至 AkShare",
                method_name,
                exc,
            )

        # 尝试备用数据源（AkShare）
        try:
            fallback_method = getattr(self._fallback, method_name)
            result = await fallback_method(*args, **kwargs)
            return result, "AkShare", True
        except Exception as fallback_err:
            logger.error(
                "Tushare 和 AkShare 均不可用 method=%s: primary=%s fallback=%s",
                method_name,
                primary_err,
                fallback_err,
            )

            # 推送数据源异常告警（需求 1.10）
            if self._alert_service is not None:
                try:
                    await self._alert_service.push_alert(
                        user_id="system",
                        alert=Alert(
                            user_id="system",
                            alert_type=AlertType.SYSTEM,
                            title="数据源异常",
                            message=f"数据源异常：Tushare 和 AkShare 均不可用（{method_name}）",
                        ),
                    )
                except Exception as alert_exc:
                    logger.warning("推送数据源异常告警失败: %s", alert_exc)

            raise DataSourceUnavailableError(
                f"所有数据源均不可用（{method_name}）: "
                f"Tushare={primary_err}, AkShare={fallback_err}"
            )


    # ------------------------------------------------------------------
    # 代理方法
    # ------------------------------------------------------------------

    async def fetch_kline(
        self, symbol: str, freq: str, start: date, end: date
    ) -> list[KlineBar]:
        """获取 K 线数据（带故障转移）。"""
        return await self.fetch_with_fallback(
            "fetch_kline", symbol, freq, start, end
        )

    async def fetch_fundamentals(self, symbol: str) -> FundamentalsData:
        """获取基本面数据（带故障转移）。"""
        return await self.fetch_with_fallback("fetch_fundamentals", symbol)

    async def fetch_money_flow(
        self, symbol: str, trade_date: date
    ) -> MoneyFlowData:
        """获取资金流向数据（带故障转移）。"""
        return await self.fetch_with_fallback(
            "fetch_money_flow", symbol, trade_date
        )

    async def fetch_market_overview(self, trade_date: date) -> MarketOverview:
        """获取大盘市场概览数据（带故障转移）。"""
        return await self.fetch_with_fallback(
            "fetch_market_overview", trade_date
        )
