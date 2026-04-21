"""
Tushare 数据导入相关 ORM 模型（PostgreSQL）

对应数据库表：
- tushare_import_log：导入日志
- trade_calendar：交易日历
- new_share：IPO 新股
- stock_st：ST 股票
- st_warning：ST 风险警示板
- stk_premarket：每日股本盘前
- stock_hsgt：沪深港通股票列表
- stock_namechange：股票曾用名
- stock_company：上市公司基本信息
- stk_managers：上市公司管理层
- stk_rewards：管理层薪酬和持股
- bse_mapping：北交所新旧代码对照
- suspend_info：停复牌信息
- stk_limit：每日涨跌停价格
- hsgt_top10：沪深股通十大成交股
- ggt_top10：港股通十大成交股
- ggt_daily：港股通每日成交统计
- ggt_monthly：港股通每月成交统计
- financial_statement：财务报表（利润表/资产负债表/现金流量表）
- dividend：分红送股
- forecast：业绩预告
- express：业绩快报
- fina_mainbz：主营业务构成
- disclosure_date：财报披露日期
- stk_shock：个股异常波动
- stk_high_shock：个股严重异常波动
- stk_alert：交易所重点提示证券
- top_holders：前十大股东
- pledge_stat：股权质押统计
- pledge_detail：股权质押明细
- repurchase：股票回购
- share_float：限售股解禁
- block_trade：大宗交易
- stk_holdernumber：股东人数
- stk_holdertrade：股东增减持
- report_rc：券商盈利预测
- cyq_perf：每日筹码及胜率
- cyq_chips：每日筹码分布
- stk_factor：股票技术面因子
- ccass_hold：中央结算系统持股统计
- ccass_hold_detail：中央结算系统持股明细
- hk_hold：沪深股通持股明细
- stk_auction_o：股票开盘集合竞价
- stk_auction_c：股票收盘集合竞价
- stk_nineturn：神奇九转指标
- stk_ah_comparison：AH股比价
- stk_surv：机构调研数据
- broker_recommend：券商每月金股
- margin_data：融资融券汇总
- margin_detail：融资融券交易明细
- margin_secs：融资融券标的盘前
- slb_len：转融资交易汇总
- money_flow：个股资金流向（Tushare，表名 tushare_moneyflow）
- moneyflow_ths：个股资金流向THS
- moneyflow_dc：个股资金流向DC
- moneyflow_cnt_ths：板块资金流向THS
- moneyflow_ind：行业资金流向
- moneyflow_hsgt：沪深港通资金流向
- moneyflow_mkt_dc：大盘资金流向
- top_list：龙虎榜每日统计单
- top_inst：龙虎榜机构交易单
- limit_list_ths：同花顺涨跌停榜单
- limit_list：涨跌停和炸板数据
- limit_step：涨停股票连板天梯
- limit_cpt_list：涨停最强板块统计
- stk_auction：开盘竞价成交当日
- hm_list：游资名录
- hm_detail：游资每日明细
- ths_hot：同花顺热榜
- dc_hot：东方财富热榜
- kpl_list：开盘啦榜单
- kpl_concept_cons：开盘啦题材成分
- dc_concept：东方财富题材库
- dc_concept_cons：东方财富题材成分
- index_info：指数基本信息
- index_weight：指数成分权重
- index_dailybasic：大盘指数每日指标
- index_tech：指数技术面因子
- index_global：国际主要指数
- market_daily_info：沪深市场每日交易统计
- sz_daily_info：深圳市场每日交易情况

需求 3.2-3.16, 4.8-4.14, 5.3-5.9, 6.1-6.12, 7.1-7.13, 8.1-8.4, 9.2-9.9, 10.1-10.24,
11.3, 13.2, 16.2, 17.2, 18.1, 18.2, 19.2,
25.1-25.3, 25.4-25.6, 25.7-25.12, 25.13, 25.14, 25.15, 25.16, 25.17, 25.18-25.28,
25.29, 25.30, 25.31, 25.32, 25.33, 25.34, 25.35-25.39, 25.41, 25.42, 25.43-25.45,
25.46, 25.49-25.83
"""

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


# ---------------------------------------------------------------------------
# TushareImportLog — 导入日志
# ---------------------------------------------------------------------------


class TushareImportLog(PGBase):
    """Tushare 数据导入日志"""

    __tablename__ = "tushare_import_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    api_name: Mapped[str] = mapped_column(String(50), nullable=False)
    params_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    def __repr__(self) -> str:
        return f"<TushareImportLog {self.id} {self.api_name} {self.status}>"


# ---------------------------------------------------------------------------
# TradeCalendar — 交易日历
# ---------------------------------------------------------------------------


class TradeCalendar(PGBase):
    """交易日历"""

    __tablename__ = "trade_calendar"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True)
    cal_date: Mapped[str] = mapped_column(String(8), primary_key=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def __repr__(self) -> str:
        return f"<TradeCalendar {self.exchange} {self.cal_date} open={self.is_open}>"


# ---------------------------------------------------------------------------
# NewShare — IPO 新股
# ---------------------------------------------------------------------------


class NewShare(PGBase):
    """IPO 新股上市"""

    __tablename__ = "new_share"

    ts_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    sub_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ipo_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    funds: Mapped[float | None] = mapped_column(Float, nullable=True)
    ballot: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<NewShare {self.ts_code} {self.name}>"


# ---------------------------------------------------------------------------
# StockST — ST 股票
# ---------------------------------------------------------------------------


class StockST(PGBase):
    """ST 股票列表"""

    __tablename__ = "stock_st"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_st: Mapped[str | None] = mapped_column(String(5), nullable=True)
    st_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    st_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<StockST {self.ts_code} {self.name} is_st={self.is_st}>"


# ---------------------------------------------------------------------------
# StWarning — ST 风险警示板
# ---------------------------------------------------------------------------


class StWarning(PGBase):
    """ST 风险警示板"""

    __tablename__ = "st_warning"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_st_warning_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StWarning {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StkPremarket — 每日股本盘前
# ---------------------------------------------------------------------------


class StkPremarket(PGBase):
    """每日股本盘前"""

    __tablename__ = "stk_premarket"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    total_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    up_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    down_limit: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_premarket_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StkPremarket {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StockHsgt — 沪深港通股票列表
# ---------------------------------------------------------------------------


class StockHsgt(PGBase):
    """沪深港通股票列表"""

    __tablename__ = "stock_hsgt"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    hs_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    in_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    out_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_new: Mapped[str | None] = mapped_column(String(5), nullable=True)

    def __repr__(self) -> str:
        return f"<StockHsgt {self.ts_code} {self.hs_type}>"


# ---------------------------------------------------------------------------
# StockNamechange — 股票曾用名
# ---------------------------------------------------------------------------


class StockNamechange(PGBase):
    """股票曾用名"""

    __tablename__ = "stock_namechange"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<StockNamechange {self.ts_code} {self.name}>"


# ---------------------------------------------------------------------------
# StockCompany — 上市公司基本信息
# ---------------------------------------------------------------------------


class StockCompany(PGBase):
    """上市公司基本信息"""

    __tablename__ = "stock_company"

    ts_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    chairman: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secretary: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reg_capital: Mapped[float | None] = mapped_column(Float, nullable=True)
    setup_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<StockCompany {self.ts_code}>"


# ---------------------------------------------------------------------------
# StkManagers — 上市公司管理层
# ---------------------------------------------------------------------------


class StkManagers(PGBase):
    """上市公司管理层"""

    __tablename__ = "stk_managers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lev: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    edu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    national: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birthday: Mapped[str | None] = mapped_column(String(8), nullable=True)
    begin_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def __repr__(self) -> str:
        return f"<StkManagers {self.ts_code} {self.name}>"


# ---------------------------------------------------------------------------
# StkRewards — 管理层薪酬和持股
# ---------------------------------------------------------------------------


class StkRewards(PGBase):
    """管理层薪酬和持股"""

    __tablename__ = "stk_rewards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_vol: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<StkRewards {self.ts_code} {self.name}>"


# ---------------------------------------------------------------------------
# BseMapping — 北交所新旧代码对照
# ---------------------------------------------------------------------------


class BseMapping(PGBase):
    """北交所新旧代码对照"""

    __tablename__ = "bse_mapping"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    old_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    list_date: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def __repr__(self) -> str:
        return f"<BseMapping {self.old_code} → {self.new_code}>"


# ---------------------------------------------------------------------------
# SuspendInfo — 停复牌信息
# ---------------------------------------------------------------------------


class SuspendInfo(PGBase):
    """停复牌信息"""

    __tablename__ = "suspend_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    suspend_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    resume_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    suspend_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<SuspendInfo {self.ts_code} {self.suspend_date}>"


# ---------------------------------------------------------------------------
# StkLimit — 每日涨跌停价格
# ---------------------------------------------------------------------------


class StkLimit(PGBase):
    """每日涨跌停价格"""

    __tablename__ = "stk_limit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    up_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    down_limit: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_limit_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StkLimit {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# HsgtTop10 — 沪深股通十大成交股
# ---------------------------------------------------------------------------


class HsgtTop10(PGBase):
    """沪深股通十大成交股"""

    __tablename__ = "hsgt_top10"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    change: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "market_type",
            name="uq_hsgt_top10_trade_date_ts_code_market_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<HsgtTop10 {self.ts_code} {self.trade_date} {self.market_type}>"


# ---------------------------------------------------------------------------
# GgtTop10 — 港股通十大成交股
# ---------------------------------------------------------------------------


class GgtTop10(PGBase):
    """港股通十大成交股"""

    __tablename__ = "ggt_top10"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "market_type",
            name="uq_ggt_top10_trade_date_ts_code_market_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<GgtTop10 {self.ts_code} {self.trade_date} {self.market_type}>"


# ---------------------------------------------------------------------------
# GgtDaily — 港股通每日成交统计
# ---------------------------------------------------------------------------


class GgtDaily(PGBase):
    """港股通每日成交统计"""

    __tablename__ = "ggt_daily"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    buy_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_ggt_daily_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<GgtDaily {self.trade_date}>"


# ---------------------------------------------------------------------------
# GgtMonthly — 港股通每月成交统计
# ---------------------------------------------------------------------------


class GgtMonthly(PGBase):
    """港股通每月成交统计"""

    __tablename__ = "ggt_monthly"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[str] = mapped_column(String(6), nullable=False)
    buy_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("month", name="uq_ggt_monthly_month"),
    )

    def __repr__(self) -> str:
        return f"<GgtMonthly {self.month}>"


# ---------------------------------------------------------------------------
# FinancialStatement — 财务报表
# ---------------------------------------------------------------------------


class FinancialStatement(PGBase):
    """财务报表（利润表/资产负债表/现金流量表）"""

    __tablename__ = "financial_statement"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    data_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date", "report_type",
            name="uq_financial_statement_ts_code_end_date_report_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<FinancialStatement {self.ts_code} {self.end_date} {self.report_type}>"


# ---------------------------------------------------------------------------
# Dividend — 分红送股
# ---------------------------------------------------------------------------


class Dividend(PGBase):
    """分红送股"""

    __tablename__ = "dividend"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    div_proc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stk_div: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_div: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<Dividend {self.ts_code} {self.end_date}>"


# ---------------------------------------------------------------------------
# Forecast — 业绩预告
# ---------------------------------------------------------------------------


class Forecast(PGBase):
    """业绩预告"""

    __tablename__ = "forecast"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    p_change_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_change_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date",
            name="uq_forecast_ts_code_end_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<Forecast {self.ts_code} {self.end_date} {self.type}>"


# ---------------------------------------------------------------------------
# Express — 业绩快报
# ---------------------------------------------------------------------------


class Express(PGBase):
    """业绩快报"""

    __tablename__ = "express"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    operate_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_hldr_eqy_exc_min_int: Mapped[float | None] = mapped_column(Float, nullable=True)
    diluted_eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    yoy_net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    perf_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date",
            name="uq_express_ts_code_end_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<Express {self.ts_code} {self.end_date}>"


# ---------------------------------------------------------------------------
# FinaMainbz — 主营业务构成
# ---------------------------------------------------------------------------


class FinaMainbz(PGBase):
    """主营业务构成"""

    __tablename__ = "fina_mainbz"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    bz_item: Mapped[str] = mapped_column(String(100), nullable=False)
    bz_sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    bz_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    bz_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    curr_type: Mapped[str | None] = mapped_column(String(10), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date", "bz_item",
            name="uq_fina_mainbz_ts_code_end_date_bz_item",
        ),
    )

    def __repr__(self) -> str:
        return f"<FinaMainbz {self.ts_code} {self.end_date} {self.bz_item}>"


# ---------------------------------------------------------------------------
# DisclosureDate — 财报披露日期
# ---------------------------------------------------------------------------


class DisclosureDate(PGBase):
    """财报披露日期"""

    __tablename__ = "disclosure_date"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    pre_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    actual_date: Mapped[str | None] = mapped_column(String(8), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date",
            name="uq_disclosure_date_ts_code_end_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<DisclosureDate {self.ts_code} {self.end_date}>"


# ---------------------------------------------------------------------------
# StkShock — 个股异常波动
# ---------------------------------------------------------------------------


class StkShock(PGBase):
    """个股异常波动"""

    __tablename__ = "stk_shock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    shock_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "shock_type",
            name="uq_stk_shock_ts_code_trade_date_shock_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<StkShock {self.ts_code} {self.trade_date} {self.shock_type}>"


# ---------------------------------------------------------------------------
# StkHighShock — 个股严重异常波动
# ---------------------------------------------------------------------------


class StkHighShock(PGBase):
    """个股严重异常波动"""

    __tablename__ = "stk_high_shock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    shock_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "shock_type",
            name="uq_stk_high_shock_ts_code_trade_date_shock_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<StkHighShock {self.ts_code} {self.trade_date} {self.shock_type}>"


# ---------------------------------------------------------------------------
# StkAlert — 交易所重点提示证券
# ---------------------------------------------------------------------------


class StkAlert(PGBase):
    """交易所重点提示证券"""

    __tablename__ = "stk_alert"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    alert_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    alert_desc: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<StkAlert {self.ts_code} {self.trade_date} {self.alert_type}>"


# ---------------------------------------------------------------------------
# TopHolders — 前十大股东
# ---------------------------------------------------------------------------


class TopHolders(PGBase):
    """前十大股东"""

    __tablename__ = "top_holders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hold_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    holder_type: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date", "holder_name", "holder_type",
            name="uq_top_holders_ts_code_end_date_holder_name_holder_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopHolders {self.ts_code} {self.end_date} {self.holder_name}>"


# ---------------------------------------------------------------------------
# PledgeStat — 股权质押统计
# ---------------------------------------------------------------------------


class PledgeStat(PGBase):
    """股权质押统计"""

    __tablename__ = "pledge_stat"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    pledge_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unrest_pledge: Mapped[float | None] = mapped_column(Float, nullable=True)
    rest_pledge: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    pledge_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date",
            name="uq_pledge_stat_ts_code_end_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<PledgeStat {self.ts_code} {self.end_date}>"


# ---------------------------------------------------------------------------
# PledgeDetail — 股权质押明细
# ---------------------------------------------------------------------------


class PledgeDetail(PGBase):
    """股权质押明细"""

    __tablename__ = "pledge_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pledge_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_release: Mapped[str | None] = mapped_column(String(5), nullable=True)

    def __repr__(self) -> str:
        return f"<PledgeDetail {self.ts_code} {self.holder_name}>"


# ---------------------------------------------------------------------------
# Repurchase — 股票回购
# ---------------------------------------------------------------------------


class Repurchase(PGBase):
    """股票回购"""

    __tablename__ = "repurchase"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    proc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    exp_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_limit: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<Repurchase {self.ts_code} {self.ann_date}>"


# ---------------------------------------------------------------------------
# ShareFloat — 限售股解禁
# ---------------------------------------------------------------------------


class ShareFloat(PGBase):
    """限售股解禁"""

    __tablename__ = "share_float"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    float_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    float_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    share_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<ShareFloat {self.ts_code} {self.float_date}>"


# ---------------------------------------------------------------------------
# BlockTrade — 大宗交易
# ---------------------------------------------------------------------------


class BlockTrade(PGBase):
    """大宗交易"""

    __tablename__ = "block_trade"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buyer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seller: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "buyer", "seller",
            name="uq_block_trade_ts_code_trade_date_buyer_seller",
        ),
    )

    def __repr__(self) -> str:
        return f"<BlockTrade {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StkHoldernumber — 股东人数
# ---------------------------------------------------------------------------


class StkHoldernumber(PGBase):
    """股东人数"""

    __tablename__ = "stk_holdernumber"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    holder_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    holder_num_change: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<StkHoldernumber {self.ts_code} {self.end_date}>"


# ---------------------------------------------------------------------------
# StkHoldertrade — 股东增减持
# ---------------------------------------------------------------------------


class StkHoldertrade(PGBase):
    """股东增减持"""

    __tablename__ = "stk_holdertrade"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_de: Mapped[str | None] = mapped_column(String(10), nullable=True)

    def __repr__(self) -> str:
        return f"<StkHoldertrade {self.ts_code} {self.holder_name} {self.in_de}>"


# ---------------------------------------------------------------------------
# ReportRc — 券商盈利预测
# ---------------------------------------------------------------------------


class ReportRc(PGBase):
    """券商盈利预测"""

    __tablename__ = "report_rc"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    report_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    broker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analyst_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    eps_est: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<ReportRc {self.ts_code} {self.report_date} {self.broker_name}>"


# ---------------------------------------------------------------------------
# CyqPerf — 每日筹码及胜率
# ---------------------------------------------------------------------------


class CyqPerf(PGBase):
    """每日筹码及胜率"""

    __tablename__ = "cyq_perf"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    his_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    his_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_5pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_15pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_50pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_85pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_95pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    winner_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_cyq_perf_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<CyqPerf {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# CyqChips — 每日筹码分布
# ---------------------------------------------------------------------------


class CyqChips(PGBase):
    """每日筹码分布"""

    __tablename__ = "cyq_chips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<CyqChips {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StkFactor — 股票技术面因子
# ---------------------------------------------------------------------------


class StkFactor(PGBase):
    """股票技术面因子"""

    __tablename__ = "stk_factor"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_dif: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_dea: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    kdj_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    kdj_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    kdj_j: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_6: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_12: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_24: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_mid: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    cci: Mapped[float | None] = mapped_column(Float, nullable=True)
    wr: Mapped[float | None] = mapped_column(Float, nullable=True)
    dmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    trix: Mapped[float | None] = mapped_column(Float, nullable=True)
    bias: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_factor_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StkFactor {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# CcassHold — 中央结算系统持股统计
# ---------------------------------------------------------------------------


class CcassHold(PGBase):
    """中央结算系统持股统计"""

    __tablename__ = "ccass_hold"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    participant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hold_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<CcassHold {self.ts_code} {self.trade_date} {self.participant_id}>"


# ---------------------------------------------------------------------------
# CcassHoldDetail — 中央结算系统持股明细
# ---------------------------------------------------------------------------


class CcassHoldDetail(PGBase):
    """中央结算系统持股明细"""

    __tablename__ = "ccass_hold_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    participant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hold_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<CcassHoldDetail {self.ts_code} {self.trade_date} {self.participant_id}>"


# ---------------------------------------------------------------------------
# HkHold — 沪深股通持股明细
# ---------------------------------------------------------------------------


class HkHold(PGBase):
    """沪深股通持股明细"""

    __tablename__ = "hk_hold"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "exchange",
            name="uq_hk_hold_ts_code_trade_date_exchange",
        ),
    )

    def __repr__(self) -> str:
        return f"<HkHold {self.ts_code} {self.trade_date} {self.exchange}>"


# ---------------------------------------------------------------------------
# StkAuctionO — 股票开盘集合竞价
# ---------------------------------------------------------------------------


class StkAuctionO(PGBase):
    """股票开盘集合竞价"""

    __tablename__ = "stk_auction_o"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_auction_o_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StkAuctionO {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StkAuctionC — 股票收盘集合竞价
# ---------------------------------------------------------------------------


class StkAuctionC(PGBase):
    """股票收盘集合竞价"""

    __tablename__ = "stk_auction_c"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_auction_c_ts_code_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<StkAuctionC {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StkNineturn — 神奇九转指标
# ---------------------------------------------------------------------------


class StkNineturn(PGBase):
    """神奇九转指标"""

    __tablename__ = "stk_nineturn"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    turn_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    turn_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "turn_type",
            name="uq_stk_nineturn_ts_code_trade_date_turn_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<StkNineturn {self.ts_code} {self.trade_date} {self.turn_type}>"


# ---------------------------------------------------------------------------
# StkAhComparison — AH股比价
# ---------------------------------------------------------------------------


class StkAhComparison(PGBase):
    """AH股比价"""

    __tablename__ = "stk_ah_comparison"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    a_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    h_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    ah_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_stk_ah_comparison_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<StkAhComparison {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# StkSurv — 机构调研数据
# ---------------------------------------------------------------------------


class StkSurv(PGBase):
    """机构调研数据"""

    __tablename__ = "stk_surv"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    surv_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    fund_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    surv_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    participants: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<StkSurv {self.ts_code} {self.surv_date}>"


# ---------------------------------------------------------------------------
# BrokerRecommend — 券商每月金股
# ---------------------------------------------------------------------------


class BrokerRecommend(PGBase):
    """券商每月金股"""

    __tablename__ = "broker_recommend"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[str | None] = mapped_column(String(6), nullable=True)
    broker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<BrokerRecommend {self.ts_code} {self.month} {self.broker}>"


# ---------------------------------------------------------------------------
# MarginData — 融资融券汇总
# ---------------------------------------------------------------------------


class MarginData(PGBase):
    """融资融券汇总"""

    __tablename__ = "margin_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange_id: Mapped[str] = mapped_column(String(10), nullable=False)
    rzye: Mapped[float | None] = mapped_column(Float, nullable=True)
    rzmre: Mapped[float | None] = mapped_column(Float, nullable=True)
    rzche: Mapped[float | None] = mapped_column(Float, nullable=True)
    rqye: Mapped[float | None] = mapped_column(Float, nullable=True)
    rqmcl: Mapped[float | None] = mapped_column(Float, nullable=True)
    rzrqye: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "exchange_id",
            name="uq_margin_data_trade_date_exchange_id",
        ),
    )

    def __repr__(self) -> str:
        return f"<MarginData {self.trade_date} {self.exchange_id}>"


# ---------------------------------------------------------------------------
# MarginDetail — 融资融券交易明细
# ---------------------------------------------------------------------------


class MarginDetail(PGBase):
    """融资融券交易明细"""

    __tablename__ = "margin_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    rzye: Mapped[float | None] = mapped_column(Float, nullable=True)
    rzmre: Mapped[float | None] = mapped_column(Float, nullable=True)
    rzche: Mapped[float | None] = mapped_column(Float, nullable=True)
    rqye: Mapped[float | None] = mapped_column(Float, nullable=True)
    rqmcl: Mapped[float | None] = mapped_column(Float, nullable=True)
    rqyl: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_margin_detail_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<MarginDetail {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MarginSecs — 融资融券标的盘前
# ---------------------------------------------------------------------------


class MarginSecs(PGBase):
    """融资融券标的盘前"""

    __tablename__ = "margin_secs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    mg_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_new: Mapped[str | None] = mapped_column(String(5), nullable=True)

    def __repr__(self) -> str:
        return f"<MarginSecs {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# SlbLen — 转融资交易汇总
# ---------------------------------------------------------------------------


class SlbLen(PGBase):
    """转融资交易汇总"""

    __tablename__ = "slb_len"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    len_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    len_amt: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<SlbLen {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# TushareMoneyflow — 个股资金流向（Tushare 导入）
# ---------------------------------------------------------------------------


class TushareMoneyflow(PGBase):
    """个股资金流向（Tushare 导入，区别于现有 money_flow 选股因子表）"""

    __tablename__ = "tushare_moneyflow"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    buy_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_mf_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_tushare_moneyflow_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<TushareMoneyflow {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MoneyflowThs — 个股资金流向THS
# ---------------------------------------------------------------------------


class MoneyflowThs(PGBase):
    """个股资金流向THS"""

    __tablename__ = "moneyflow_ths"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    buy_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_mf_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_moneyflow_ths_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<MoneyflowThs {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MoneyflowDc — 个股资金流向DC
# ---------------------------------------------------------------------------


class MoneyflowDc(PGBase):
    """个股资金流向DC"""

    __tablename__ = "moneyflow_dc"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    buy_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_mf_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_moneyflow_dc_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<MoneyflowDc {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MoneyflowCntThs — 板块资金流向THS
# ---------------------------------------------------------------------------


class MoneyflowCntThs(PGBase):
    """板块资金流向THS"""

    __tablename__ = "moneyflow_cnt_ths"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buy_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<MoneyflowCntThs {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MoneyflowInd — 行业资金流向
# ---------------------------------------------------------------------------


class MoneyflowInd(PGBase):
    """行业资金流向"""

    __tablename__ = "moneyflow_ind"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    industry_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(10), nullable=True)
    buy_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<MoneyflowInd {self.industry_name} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MoneyflowHsgt — 沪深港通资金流向
# ---------------------------------------------------------------------------


class MoneyflowHsgt(PGBase):
    """沪深港通资金流向"""

    __tablename__ = "moneyflow_hsgt"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ggt_ss: Mapped[float | None] = mapped_column(Float, nullable=True)
    ggt_sz: Mapped[float | None] = mapped_column(Float, nullable=True)
    hgt: Mapped[float | None] = mapped_column(Float, nullable=True)
    sgt: Mapped[float | None] = mapped_column(Float, nullable=True)
    north_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    south_money: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_moneyflow_hsgt_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<MoneyflowHsgt {self.trade_date}>"


# ---------------------------------------------------------------------------
# MoneyflowMktDc — 大盘资金流向
# ---------------------------------------------------------------------------


class MoneyflowMktDc(PGBase):
    """大盘资金流向"""

    __tablename__ = "moneyflow_mkt_dc"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    change: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_mf_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_mf_amount_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_elg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_lg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_md_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_sm_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_moneyflow_mkt_dc_trade_date"),
    )

    def __repr__(self) -> str:
        return f"<MoneyflowMktDc {self.trade_date}>"


# ---------------------------------------------------------------------------
# TopList — 龙虎榜每日统计单
# ---------------------------------------------------------------------------


class TopList(PGBase):
    """龙虎榜每日统计单"""

    __tablename__ = "top_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    l_sell: Mapped[float | None] = mapped_column(Float, nullable=True)
    l_buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    l_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_values: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "reason",
            name="uq_top_list_trade_date_ts_code_reason",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopList {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# TopInst — 龙虎榜机构交易单
# ---------------------------------------------------------------------------


class TopInst(PGBase):
    """龙虎榜机构交易单"""

    __tablename__ = "top_inst"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    exalter: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_buy: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "exalter",
            name="uq_top_inst_trade_date_ts_code_exalter",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopInst {self.ts_code} {self.trade_date} {self.exalter}>"


# ---------------------------------------------------------------------------
# LimitListThs — 同花顺涨跌停榜单
# ---------------------------------------------------------------------------


class LimitListThs(PGBase):
    """同花顺涨跌停榜单"""

    __tablename__ = "limit_list_ths"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fd_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit: Mapped[str | None] = mapped_column(String(5), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "limit",
            name="uq_limit_list_ths_ts_code_trade_date_limit",
        ),
    )

    def __repr__(self) -> str:
        return f"<LimitListThs {self.ts_code} {self.trade_date} {self.limit}>"


# ---------------------------------------------------------------------------
# LimitList — 涨跌停和炸板数据
# ---------------------------------------------------------------------------


class LimitList(PGBase):
    """涨跌停和炸板数据"""

    __tablename__ = "limit_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    fd_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    up_stat: Mapped[str | None] = mapped_column(String(20), nullable=True)
    limit_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit: Mapped[str | None] = mapped_column(String(5), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "limit",
            name="uq_limit_list_ts_code_trade_date_limit",
        ),
    )

    def __repr__(self) -> str:
        return f"<LimitList {self.ts_code} {self.trade_date} {self.limit}>"


# ---------------------------------------------------------------------------
# LimitStep — 涨停股票连板天梯
# ---------------------------------------------------------------------------


class LimitStep(PGBase):
    """涨停股票连板天梯"""

    __tablename__ = "limit_step"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    fd_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_times: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_limit_step_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<LimitStep {self.ts_code} {self.trade_date} step={self.step}>"


# ---------------------------------------------------------------------------
# LimitCptList — 涨停最强板块统计
# ---------------------------------------------------------------------------


class LimitCptList(PGBase):
    """涨停最强板块统计"""

    __tablename__ = "limit_cpt_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    concept_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    limit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    up_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    down_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<LimitCptList {self.trade_date} {self.concept_name}>"


# ---------------------------------------------------------------------------
# StkAuction — 开盘竞价成交当日
# ---------------------------------------------------------------------------


class StkAuction(PGBase):
    """开盘竞价成交当日"""

    __tablename__ = "stk_auction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_vol: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_stk_auction_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<StkAuction {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# HmList — 游资名录
# ---------------------------------------------------------------------------


class HmList(PGBase):
    """游资名录"""

    __tablename__ = "hm_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hm_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hm_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    desc: Mapped[str | None] = mapped_column(
        String(500), name="description", nullable=True
    )

    def __repr__(self) -> str:
        return f"<HmList {self.hm_name} {self.hm_code}>"


# ---------------------------------------------------------------------------
# HmDetail — 游资每日明细
# ---------------------------------------------------------------------------


class HmDetail(PGBase):
    """游资每日明细"""

    __tablename__ = "hm_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    hm_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buy_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<HmDetail {self.ts_code} {self.trade_date} {self.hm_name}>"


# ---------------------------------------------------------------------------
# ThsHot — 同花顺热榜
# ---------------------------------------------------------------------------


class ThsHot(PGBase):
    """同花顺热榜"""

    __tablename__ = "ths_hot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    hot_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<ThsHot {self.ts_code} {self.trade_date} rank={self.rank}>"


# ---------------------------------------------------------------------------
# DcHot — 东方财富热榜
# ---------------------------------------------------------------------------


class DcHot(PGBase):
    """东方财富热榜"""

    __tablename__ = "dc_hot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    hot_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<DcHot {self.ts_code} {self.trade_date} rank={self.rank}>"


# ---------------------------------------------------------------------------
# KplList — 开盘啦榜单
# ---------------------------------------------------------------------------


class KplList(PGBase):
    """开盘啦榜单"""

    __tablename__ = "kpl_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<KplList {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# KplConceptCons — 开盘啦题材成分
# ---------------------------------------------------------------------------


class KplConceptCons(PGBase):
    """开盘啦题材成分"""

    __tablename__ = "kpl_concept_cons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    concept_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<KplConceptCons {self.concept_code} {self.ts_code}>"


# ---------------------------------------------------------------------------
# DcConcept — 东方财富题材库
# ---------------------------------------------------------------------------


class DcConcept(PGBase):
    """东方财富题材库"""

    __tablename__ = "dc_concept"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    concept_code: Mapped[str] = mapped_column(String(20), nullable=False)
    concept_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    src: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<DcConcept {self.concept_code} {self.concept_name}>"


# ---------------------------------------------------------------------------
# DcConceptCons — 东方财富题材成分
# ---------------------------------------------------------------------------


class DcConceptCons(PGBase):
    """东方财富题材成分"""

    __tablename__ = "dc_concept_cons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    concept_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<DcConceptCons {self.concept_code} {self.ts_code}>"


# ---------------------------------------------------------------------------
# IndexInfo — 指数基本信息
# ---------------------------------------------------------------------------


class IndexInfo(PGBase):
    """指数基本信息"""

    __tablename__ = "index_info"

    ts_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    base_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    base_point: Mapped[float | None] = mapped_column(Float, nullable=True)
    list_date: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def __repr__(self) -> str:
        return f"<IndexInfo {self.ts_code} {self.name}>"


# ---------------------------------------------------------------------------
# IndexWeight — 指数成分权重
# ---------------------------------------------------------------------------


class IndexWeight(PGBase):
    """指数成分权重"""

    __tablename__ = "index_weight"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(20), nullable=False)
    con_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "index_code", "con_code", "trade_date",
            name="uq_index_weight_index_code_con_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<IndexWeight {self.index_code} {self.con_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# IndexDailybasic — 大盘指数每日指标
# ---------------------------------------------------------------------------


class IndexDailybasic(PGBase):
    """大盘指数每日指标"""

    __tablename__ = "index_dailybasic"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_index_dailybasic_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<IndexDailybasic {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# IndexTech — 指数技术面因子
# ---------------------------------------------------------------------------


class IndexTech(PGBase):
    """指数技术面因子"""

    __tablename__ = "index_tech"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_dif: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_dea: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    kdj_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    kdj_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    kdj_j: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_6: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_12: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_mid: Mapped[float | None] = mapped_column(Float, nullable=True)
    boll_lower: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_index_tech_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<IndexTech {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# IndexGlobal — 国际主要指数
# ---------------------------------------------------------------------------


class IndexGlobal(PGBase):
    """国际主要指数"""

    __tablename__ = "index_global"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    change: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date",
            name="uq_index_global_ts_code_trade_date",
        ),
    )

    def __repr__(self) -> str:
        return f"<IndexGlobal {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# MarketDailyInfo — 沪深市场每日交易统计
# ---------------------------------------------------------------------------


class MarketDailyInfo(PGBase):
    """沪深市场每日交易统计"""

    __tablename__ = "market_daily_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ts_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    com_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    trans_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "exchange", "ts_code",
            name="uq_market_daily_info_trade_date_exchange_ts_code",
        ),
    )

    def __repr__(self) -> str:
        return f"<MarketDailyInfo {self.trade_date} {self.exchange} {self.ts_code}>"


# ---------------------------------------------------------------------------
# SzDailyInfo — 深圳市场每日交易情况
# ---------------------------------------------------------------------------


class SzDailyInfo(PGBase):
    """深圳市场每日交易情况"""

    __tablename__ = "sz_daily_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code",
            name="uq_sz_daily_info_trade_date_ts_code",
        ),
    )

    def __repr__(self) -> str:
        return f"<SzDailyInfo {self.trade_date} {self.ts_code}>"
