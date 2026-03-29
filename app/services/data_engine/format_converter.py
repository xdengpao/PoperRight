"""
统一格式转换层

将 Tushare 和 AkShare 返回的原始数据统一映射为系统内部数据结构，
确保不同数据源输出的 KlineBar、FundamentalsData、MoneyFlowData、MarketOverview
结构完全一致（统一字段名、数据类型、单位）。

对应需求：1.11
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.schemas import KlineBar
from app.services.data_engine.fundamental_adapter import FundamentalsData
from app.services.data_engine.money_flow_adapter import MarketOverview, MoneyFlowData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 共用安全转换辅助
# ---------------------------------------------------------------------------


def _safe_decimal(value: Any) -> Decimal:
    """安全转换为 Decimal，无效值返回 Decimal(0)。"""
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _safe_decimal_or_none(value: Any) -> Decimal | None:
    """安全转换为 Decimal，无效值返回 None。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int。"""
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# TushareFormatConverter
# ---------------------------------------------------------------------------


class TushareFormatConverter:
    """
    Tushare 数据格式转换器

    将 Tushare API 返回的 dict（fields + items 格式）映射为系统内部统一结构。

    Tushare K线字段：ts_code, trade_date, open, high, low, close, vol, amount,
                     turnover_rate, volume_ratio
    - trade_date 格式：YYYYMMDD
    - amount 单位：千元（转换时乘以 1000 转为元）
    """

    @staticmethod
    def _rows_from_raw(raw: dict[str, Any]) -> list[dict[str, Any]]:
        """将 Tushare fields + items 格式转为 dict 列表。"""
        fields: list[str] = raw.get("fields", [])
        items: list[list[Any]] = raw.get("items", [])
        return [dict(zip(fields, row)) for row in items]

    def to_kline_bars(self, raw: dict[str, Any], symbol: str, freq: str) -> list[KlineBar]:
        """将 Tushare 原始数据转换为 KlineBar 列表。

        Args:
            raw: Tushare API 返回的 data 字典（含 fields 和 items）
            symbol: 股票代码
            freq: K线频率

        Returns:
            KlineBar 列表
        """
        rows = self._rows_from_raw(raw)
        bars: list[KlineBar] = []
        for row in rows:
            # 解析日期 YYYYMMDD
            trade_date = row.get("trade_date")
            if trade_date is not None:
                try:
                    dt = datetime.strptime(str(trade_date)[:8], "%Y%m%d")
                except ValueError:
                    dt = datetime.utcnow()
            else:
                dt = datetime.utcnow()

            bars.append(KlineBar(
                time=dt,
                symbol=symbol,
                freq=freq,
                open=_safe_decimal(row.get("open")),
                high=_safe_decimal(row.get("high")),
                low=_safe_decimal(row.get("low")),
                close=_safe_decimal(row.get("close")),
                volume=_safe_int(row.get("vol")),
                amount=_safe_decimal(row.get("amount")) * 1000,  # 千元 → 元
                turnover=_safe_decimal(row.get("turnover_rate", 0)),
                vol_ratio=_safe_decimal(row.get("volume_ratio", 0)),
                limit_up=None,
                limit_down=None,
                adj_type=0,
            ))
        return bars

    def to_fundamentals(self, raw: dict[str, Any], symbol: str) -> FundamentalsData:
        """将 Tushare fina_indicator 原始数据转换为 FundamentalsData。

        Args:
            raw: Tushare API 返回的 data 字典（含 fields 和 items）
            symbol: 股票代码

        Returns:
            FundamentalsData 数据对象
        """
        rows = self._rows_from_raw(raw)
        if not rows:
            return FundamentalsData(symbol=symbol, updated_at=datetime.utcnow())

        row = rows[0]
        return FundamentalsData(
            symbol=symbol,
            name=row.get("name"),
            pe_ttm=_safe_decimal_or_none(row.get("pe_ttm")),
            pb=_safe_decimal_or_none(row.get("pb")),
            roe=_safe_decimal_or_none(row.get("roe_dt")),
            net_profit_yoy=_safe_decimal_or_none(row.get("netprofit_yoy")),
            revenue_yoy=_safe_decimal_or_none(row.get("or_yoy")),
            updated_at=datetime.utcnow(),
            raw=row,
        )

    def to_money_flow(self, raw: dict[str, Any], symbol: str, trade_date: date) -> MoneyFlowData:
        """将 Tushare moneyflow 原始数据转换为 MoneyFlowData。

        Args:
            raw: Tushare API 返回的 data 字典
            symbol: 股票代码
            trade_date: 交易日期

        Returns:
            MoneyFlowData 数据对象
        """
        rows = self._rows_from_raw(raw)
        if not rows:
            return MoneyFlowData(
                symbol=symbol, trade_date=trade_date, updated_at=datetime.utcnow(),
            )

        row = rows[0]
        return MoneyFlowData(
            symbol=symbol,
            trade_date=trade_date,
            main_net_inflow=_safe_decimal_or_none(row.get("net_mf_amount")),
            main_inflow=_safe_decimal_or_none(row.get("buy_elg_amount")),
            main_outflow=_safe_decimal_or_none(row.get("sell_elg_amount")),
            large_order_net=_safe_decimal_or_none(row.get("net_lg_amount")),
            updated_at=datetime.utcnow(),
            raw=row,
        )

    def to_market_overview(self, raw: dict[str, Any], trade_date: date) -> MarketOverview:
        """将 Tushare index_daily 原始数据转换为 MarketOverview。

        Args:
            raw: Tushare API 返回的 data 字典
            trade_date: 交易日期

        Returns:
            MarketOverview 数据对象
        """
        rows = self._rows_from_raw(raw)
        if not rows:
            return MarketOverview(trade_date=trade_date, updated_at=datetime.utcnow())

        row = rows[0]
        return MarketOverview(
            trade_date=trade_date,
            sh_index=_safe_decimal_or_none(row.get("close")),
            sh_change_pct=_safe_decimal_or_none(row.get("pct_chg")),
            updated_at=datetime.utcnow(),
            raw=row,
        )



# ---------------------------------------------------------------------------
# AkShareFormatConverter
# ---------------------------------------------------------------------------


class AkShareFormatConverter:
    """
    AkShare 数据格式转换器

    将 AkShare SDK 返回的 pandas DataFrame（中文列名）映射为系统内部统一结构。

    AkShare K线列名：日期, 开盘, 最高, 最低, 收盘, 成交量, 成交额, 换手率
    - 日期格式：YYYY-MM-DD
    - 成交额单位：元（无需转换）
    - AkShare 不直接提供量比，vol_ratio 固定为 Decimal(0)
    """

    def to_kline_bars(self, df: Any, symbol: str, freq: str) -> list[KlineBar]:
        """将 AkShare DataFrame 转换为 KlineBar 列表。

        Args:
            df: AkShare 返回的 pandas DataFrame
            symbol: 股票代码
            freq: K线频率

        Returns:
            KlineBar 列表
        """
        if df is None or (hasattr(df, "empty") and df.empty):
            return []

        bars: list[KlineBar] = []
        for _, row in df.iterrows():
            # 解析日期 YYYY-MM-DD
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
                open=_safe_decimal(row.get("开盘")),
                high=_safe_decimal(row.get("最高")),
                low=_safe_decimal(row.get("最低")),
                close=_safe_decimal(row.get("收盘")),
                volume=_safe_int(row.get("成交量")),
                amount=_safe_decimal(row.get("成交额")),  # 已经是元
                turnover=_safe_decimal(row.get("换手率", 0)),
                vol_ratio=Decimal(0),  # AkShare 不直接提供量比
                limit_up=None,
                limit_down=None,
                adj_type=0,
            ))
        return bars

    def to_fundamentals(self, df: Any, symbol: str) -> FundamentalsData:
        """将 AkShare 财务数据 DataFrame 转换为 FundamentalsData。

        Args:
            df: AkShare 返回的 pandas DataFrame
            symbol: 股票代码

        Returns:
            FundamentalsData 数据对象
        """
        if df is None or (hasattr(df, "empty") and df.empty):
            return FundamentalsData(symbol=symbol, updated_at=datetime.utcnow())

        row = df.iloc[0]
        return FundamentalsData(
            symbol=symbol,
            roe=_safe_decimal_or_none(row.get("净资产收益率(%)")),
            net_profit_yoy=_safe_decimal_or_none(row.get("净利润同比增长率(%)")),
            revenue_yoy=_safe_decimal_or_none(row.get("主营业务收入同比增长率(%)")),
            updated_at=datetime.utcnow(),
            raw=row.to_dict() if hasattr(row, "to_dict") else {},
        )

    def to_money_flow(self, df: Any, symbol: str, trade_date: date) -> MoneyFlowData:
        """将 AkShare 资金流向 DataFrame 转换为 MoneyFlowData。

        Args:
            df: AkShare 返回的 pandas DataFrame
            symbol: 股票代码
            trade_date: 交易日期

        Returns:
            MoneyFlowData 数据对象
        """
        if df is None or (hasattr(df, "empty") and df.empty):
            return MoneyFlowData(
                symbol=symbol, trade_date=trade_date, updated_at=datetime.utcnow(),
            )

        # 尝试匹配指定日期
        target_row = None
        date_str = trade_date.strftime("%Y-%m-%d")
        if "日期" in df.columns:
            matched = df[df["日期"].astype(str).str[:10] == date_str]
            if not matched.empty:
                target_row = matched.iloc[0]

        if target_row is None:
            target_row = df.iloc[0]

        return MoneyFlowData(
            symbol=symbol,
            trade_date=trade_date,
            main_net_inflow=_safe_decimal_or_none(target_row.get("主力净流入-净额")),
            main_inflow=_safe_decimal_or_none(target_row.get("主力净流入-净占比")),
            large_order_net=_safe_decimal_or_none(target_row.get("超大单净流入-净额")),
            updated_at=datetime.utcnow(),
            raw=target_row.to_dict() if hasattr(target_row, "to_dict") else {},
        )

    def to_market_overview(self, df: Any, trade_date: date) -> MarketOverview:
        """将 AkShare 大盘指数 DataFrame 转换为 MarketOverview。

        Args:
            df: AkShare 返回的 pandas DataFrame
            trade_date: 交易日期

        Returns:
            MarketOverview 数据对象
        """
        if df is None or (hasattr(df, "empty") and df.empty):
            return MarketOverview(trade_date=trade_date, updated_at=datetime.utcnow())

        # 尝试匹配指定日期
        target_row = None
        date_str = trade_date.strftime("%Y-%m-%d")
        if "date" in df.columns:
            matched = df[df["date"].astype(str).str[:10] == date_str]
            if not matched.empty:
                target_row = matched.iloc[0]

        if target_row is None:
            target_row = df.iloc[-1]

        return MarketOverview(
            trade_date=trade_date,
            sh_index=_safe_decimal_or_none(target_row.get("close")),
            sh_change_pct=_safe_decimal_or_none(
                target_row.get("pct_chg", target_row.get("change"))
            ),
            updated_at=datetime.utcnow(),
            raw=target_row.to_dict() if hasattr(target_row, "to_dict") else {},
        )
