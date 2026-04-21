"""
Tushare 数据导入相关 ORM 模型（PostgreSQL）

对应数据库表：
- tushare_import_log：导入日志
- trade_calendar：交易日历
- new_share：IPO 新股
- stock_st：ST 股票
- daily_share：每日股本
- suspend_info：停复牌信息
- financial_statement：财务报表
- dividend：分红送股
- forecast：业绩预告
- express：业绩快报
- index_info：指数基本信息
- index_weight：指数成分权重
- index_dailybasic：大盘指数每日指标
- index_global：国际主要指数
- index_tech：指数技术面因子
- tushare_money_flow：个股资金流向（Tushare 数据源）
- moneyflow_hsgt：沪深港通资金流向
- moneyflow_ind：行业资金流向
- moneyflow_mkt_dc：大盘资金流向
- stock_company：上市公司信息
- stock_namechange：股票曾用名
- hs_constituent：沪深股通成份股
- stk_rewards：管理层薪酬和持股
- stk_managers：上市公司管理层
- top_holders：前十大股东
- stk_holdernumber：股东人数
- stk_holdertrade：股东增减持
- stk_account：股票开户数据
- stk_limit：每日涨跌停价格
- stk_factor：股票技术面因子
- margin_data：融资融券汇总
- margin_detail：融资融券交易明细
- margin_target：融资融券标的
- slb_len：转融通出借
- slb_sec：转融通证券出借
- limit_list：每日涨跌停统计
- limit_step：涨停股票连板天梯
- hm_list：游资名录
- hm_detail：游资每日明细
- top_list：龙虎榜每日明细
- top_inst：龙虎榜机构交易明细
- ths_limit：同花顺涨跌停榜单
- dc_hot：东方财富App热榜
- ths_hot：同花顺App热榜
- kpl_list：开盘啦榜单
- block_trade：大宗交易
- market_daily_info：沪深市场每日交易统计
- sz_daily_info：深圳市场每日交易情况
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, Numeric, String, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP as TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import PGBase


# ---------------------------------------------------------------------------
# 2.1 导入日志和基础数据模型
# ---------------------------------------------------------------------------


class TushareImportLog(PGBase):
    """导入日志表"""

    __tablename__ = "tushare_import_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    api_name: Mapped[str] = mapped_column(String(50), nullable=False)
    params_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    record_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    def __repr__(self) -> str:
        return f"<TushareImportLog {self.id} api={self.api_name} status={self.status}>"


class TradeCalendar(PGBase):
    """交易日历表（exchange + cal_date 复合主键）"""

    __tablename__ = "trade_calendar"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True)
    cal_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def __repr__(self) -> str:
        return f"<TradeCalendar {self.exchange} {self.cal_date} open={self.is_open}>"


class NewShare(PGBase):
    """IPO 新股表"""

    __tablename__ = "new_share"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    sub_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ipo_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    market_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pe: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    limit_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    funds: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    ballot: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    def __repr__(self) -> str:
        return f"<NewShare {self.ts_code} {self.name}>"


class StockST(PGBase):
    """ST 股票表"""

    __tablename__ = "stock_st"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_st: Mapped[str | None] = mapped_column(String(2), nullable=True)
    st_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    st_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<StockST {self.ts_code} {self.name}>"


class DailyShare(PGBase):
    """每日股本表"""

    __tablename__ = "daily_share"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    total_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    free_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_daily_share"),
    )

    def __repr__(self) -> str:
        return f"<DailyShare {self.ts_code} {self.trade_date}>"


class SuspendInfo(PGBase):
    """停复牌信息表"""

    __tablename__ = "suspend_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    suspend_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    resume_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    suspend_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<SuspendInfo {self.ts_code} suspend={self.suspend_date}>"


# ---------------------------------------------------------------------------
# 2.2 财务数据模型
# ---------------------------------------------------------------------------


class FinancialStatement(PGBase):
    """财务报表表（income/balance/cashflow 统一存储，data_json 为 JSONB）"""

    __tablename__ = "financial_statement"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date", "report_type",
            name="uq_financial_statement",
        ),
    )

    def __repr__(self) -> str:
        return f"<FinancialStatement {self.ts_code} {self.end_date} {self.report_type}>"


class Dividend(PGBase):
    """分红送股表"""

    __tablename__ = "dividend"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    div_proc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stk_div: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    cash_div: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    def __repr__(self) -> str:
        return f"<Dividend {self.ts_code} {self.end_date}>"


class Forecast(PGBase):
    """业绩预告表"""

    __tablename__ = "forecast"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    p_change_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    p_change_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    net_profit_min: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_profit_max: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "end_date", name="uq_forecast"),
    )

    def __repr__(self) -> str:
        return f"<Forecast {self.ts_code} {self.end_date}>"


class Express(PGBase):
    """业绩快报表"""

    __tablename__ = "express"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    operate_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    total_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    n_income: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    total_hldr_eqy_exc_min_int: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    diluted_eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    yoy_net_profit: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    bps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    perf_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "end_date", name="uq_express"),
    )

    def __repr__(self) -> str:
        return f"<Express {self.ts_code} {self.end_date}>"


# ---------------------------------------------------------------------------
# 2.3 指数数据模型
# ---------------------------------------------------------------------------


class IndexInfo(PGBase):
    """指数基本信息表"""

    __tablename__ = "index_info"

    ts_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    base_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    base_point: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    list_date: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def __repr__(self) -> str:
        return f"<IndexInfo {self.ts_code} {self.name}>"


class IndexWeight(PGBase):
    """指数成分权重表"""

    __tablename__ = "index_weight"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(20), nullable=False)
    con_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "index_code", "con_code", "trade_date",
            name="uq_index_weight",
        ),
    )

    def __repr__(self) -> str:
        return f"<IndexWeight {self.index_code} {self.con_code} {self.trade_date}>"


class IndexDailybasic(PGBase):
    """大盘指数每日指标表"""

    __tablename__ = "index_dailybasic"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    pe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    pb: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    float_mv: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_index_dailybasic"),
    )

    def __repr__(self) -> str:
        return f"<IndexDailybasic {self.ts_code} {self.trade_date}>"


class IndexGlobal(PGBase):
    """国际主要指数表"""

    __tablename__ = "index_global"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    change: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_index_global"),
    )

    def __repr__(self) -> str:
        return f"<IndexGlobal {self.ts_code} {self.trade_date}>"


class IndexTech(PGBase):
    """指数技术面因子表"""

    __tablename__ = "index_tech"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    macd_dif: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    macd_dea: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    macd: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    kdj_k: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    kdj_d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    kdj_j: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    rsi_6: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    rsi_12: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    boll_upper: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    boll_mid: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    boll_lower: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_index_tech"),
    )

    def __repr__(self) -> str:
        return f"<IndexTech {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# 2.4 资金流向数据模型
# ---------------------------------------------------------------------------


class TushareMoneyFlow(PGBase):
    """个股资金流向表（Tushare 数据源，按大中小超大单分类）"""

    __tablename__ = "tushare_money_flow"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    buy_sm_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_sm_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    buy_md_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_md_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    buy_lg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_lg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    buy_elg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_elg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_mf_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_tushare_money_flow"),
    )

    def __repr__(self) -> str:
        return f"<TushareMoneyFlow {self.ts_code} {self.trade_date}>"


class MoneyflowHsgt(PGBase):
    """沪深港通资金流向表"""

    __tablename__ = "moneyflow_hsgt"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ggt_ss: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    ggt_sz: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    hgt: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sgt: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    north_money: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    south_money: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_moneyflow_hsgt"),
    )

    def __repr__(self) -> str:
        return f"<MoneyflowHsgt {self.trade_date}>"


class MoneyflowInd(PGBase):
    """行业资金流向表"""

    __tablename__ = "moneyflow_ind"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    industry_name: Mapped[str] = mapped_column(String(50), nullable=False)
    data_source: Mapped[str] = mapped_column(String(10), nullable=False)
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<MoneyflowInd {self.trade_date} {self.industry_name}>"


class MoneyflowMktDc(PGBase):
    """大盘资金流向表（东方财富）"""

    __tablename__ = "moneyflow_mkt_dc"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    change: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    net_mf_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    net_mf_amount_rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    buy_elg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_elg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    buy_lg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_lg_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    buy_md_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_md_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    buy_sm_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_sm_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_moneyflow_mkt_dc"),
    )

    def __repr__(self) -> str:
        return f"<MoneyflowMktDc {self.trade_date}>"


# ---------------------------------------------------------------------------
# 2.5 参考数据和特色数据模型
# ---------------------------------------------------------------------------


class StockCompany(PGBase):
    """上市公司信息表"""

    __tablename__ = "stock_company"

    ts_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    chairman: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secretary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reg_capital: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    setup_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<StockCompany {self.ts_code}>"


class StockNamechange(PGBase):
    """股票曾用名表"""

    __tablename__ = "stock_namechange"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<StockNamechange {self.ts_code} {self.name}>"


class HsConstituent(PGBase):
    """沪深股通成份股表"""

    __tablename__ = "hs_constituent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    hs_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    in_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    out_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_new: Mapped[str | None] = mapped_column(String(2), nullable=True)

    def __repr__(self) -> str:
        return f"<HsConstituent {self.ts_code} {self.hs_type}>"


class StkRewards(PGBase):
    """管理层薪酬和持股表"""

    __tablename__ = "stk_rewards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reward: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    hold_vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<StkRewards {self.ts_code} {self.name}>"


class StkManagers(PGBase):
    """上市公司管理层表"""

    __tablename__ = "stk_managers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lev: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    edu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    national: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birthday: Mapped[str | None] = mapped_column(String(8), nullable=True)
    begin_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def __repr__(self) -> str:
        return f"<StkManagers {self.ts_code} {self.name}>"


class TopHolders(PGBase):
    """前十大股东表"""

    __tablename__ = "top_holders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hold_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    hold_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    holder_type: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "end_date", "holder_name", "holder_type",
            name="uq_top_holders",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopHolders {self.ts_code} {self.holder_name}>"


class StkHoldernumber(PGBase):
    """股东人数表"""

    __tablename__ = "stk_holdernumber"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    holder_num: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    holder_num_change: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    def __repr__(self) -> str:
        return f"<StkHoldernumber {self.ts_code} {self.end_date}>"


class StkHoldertrade(PGBase):
    """股东增减持表"""

    __tablename__ = "stk_holdertrade"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    ann_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_vol: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    change_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    after_vol: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    after_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    in_de: Mapped[str | None] = mapped_column(String(10), nullable=True)

    def __repr__(self) -> str:
        return f"<StkHoldertrade {self.ts_code} {self.holder_name}>"


class StkAccount(PGBase):
    """股票开户数据表"""

    __tablename__ = "stk_account"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(8), nullable=False)
    weekly_new: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    weekly_hold: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    def __repr__(self) -> str:
        return f"<StkAccount {self.date}>"


class StkLimit(PGBase):
    """每日涨跌停价格表"""

    __tablename__ = "stk_limit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    up_limit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    down_limit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_limit"),
    )

    def __repr__(self) -> str:
        return f"<StkLimit {self.ts_code} {self.trade_date}>"


class StkFactor(PGBase):
    """股票技术面因子表"""

    __tablename__ = "stk_factor"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    macd_dif: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    macd_dea: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    macd: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    kdj_k: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    kdj_d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    kdj_j: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    rsi_6: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    rsi_12: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    rsi_24: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    boll_upper: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    boll_mid: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    boll_lower: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    cci: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_stk_factor"),
    )

    def __repr__(self) -> str:
        return f"<StkFactor {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# 2.6 两融及转融通数据模型
# ---------------------------------------------------------------------------


class MarginData(PGBase):
    """融资融券汇总表"""

    __tablename__ = "margin_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange_id: Mapped[str] = mapped_column(String(10), nullable=False)
    rzye: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rzmre: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rzche: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rqye: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rqmcl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rzrqye: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", "exchange_id", name="uq_margin_data"),
    )

    def __repr__(self) -> str:
        return f"<MarginData {self.trade_date} {self.exchange_id}>"


class MarginDetail(PGBase):
    """融资融券交易明细表"""

    __tablename__ = "margin_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    rzye: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rzmre: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rzche: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rqye: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rqmcl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    rqyl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_margin_detail"),
    )

    def __repr__(self) -> str:
        return f"<MarginDetail {self.ts_code} {self.trade_date}>"


class MarginTarget(PGBase):
    """融资融券标的表"""

    __tablename__ = "margin_target"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    mg_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_new: Mapped[str | None] = mapped_column(String(2), nullable=True)

    def __repr__(self) -> str:
        return f"<MarginTarget {self.ts_code}>"


class SlbLen(PGBase):
    """转融通出借表"""

    __tablename__ = "slb_len"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    len_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    len_amt: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<SlbLen {self.ts_code} {self.trade_date}>"


class SlbSec(PGBase):
    """转融通证券出借表"""

    __tablename__ = "slb_sec"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    sec_amt: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sec_vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<SlbSec {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# 2.7 打板专题数据模型
# ---------------------------------------------------------------------------


class LimitList(PGBase):
    """每日涨跌停统计表"""

    __tablename__ = "limit_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    limit_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    turnover_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    fd_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    first_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    up_stat: Mapped[str | None] = mapped_column(String(20), nullable=True)
    limit_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit: Mapped[str] = mapped_column(String(2), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "limit",
            name="uq_limit_list",
        ),
    )

    def __repr__(self) -> str:
        return f"<LimitList {self.ts_code} {self.trade_date} {self.limit}>"


class LimitStep(PGBase):
    """涨停股票连板天梯表"""

    __tablename__ = "limit_step"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    turnover_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    fd_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    first_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_times: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_limit_step"),
    )

    def __repr__(self) -> str:
        return f"<LimitStep {self.ts_code} {self.trade_date}>"


class HmList(PGBase):
    """游资名录表"""

    __tablename__ = "hm_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hm_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hm_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    desc: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<HmList {self.hm_name}>"


class HmDetail(PGBase):
    """游资每日明细表"""

    __tablename__ = "hm_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    hm_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sell_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<HmDetail {self.trade_date} {self.ts_code}>"


class TopList(PGBase):
    """龙虎榜每日明细表"""

    __tablename__ = "top_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    l_sell: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    l_buy: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    l_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    net_rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    amount_rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_values: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "reason",
            name="uq_top_list",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopList {self.trade_date} {self.ts_code}>"


class TopInst(PGBase):
    """龙虎榜机构交易明细表"""

    __tablename__ = "top_inst"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    exalter: Mapped[str] = mapped_column(String(200), nullable=False)
    buy: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    buy_rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    sell: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    sell_rate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    net_buy: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "ts_code", "exalter",
            name="uq_top_inst",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopInst {self.trade_date} {self.ts_code} {self.exalter}>"


class ThsLimit(PGBase):
    """同花顺涨跌停榜单表"""

    __tablename__ = "ths_limit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    fd_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    first_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit: Mapped[str] = mapped_column(String(2), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "limit",
            name="uq_ths_limit",
        ),
    )

    def __repr__(self) -> str:
        return f"<ThsLimit {self.ts_code} {self.trade_date} {self.limit}>"


class DcHot(PGBase):
    """东方财富App热榜表"""

    __tablename__ = "dc_hot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    hot_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    def __repr__(self) -> str:
        return f"<DcHot {self.trade_date} {self.ts_code}>"


class ThsHot(PGBase):
    """同花顺App热榜表"""

    __tablename__ = "ths_hot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    hot_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    def __repr__(self) -> str:
        return f"<ThsHot {self.trade_date} {self.ts_code}>"


class KplList(PGBase):
    """开盘啦榜单表"""

    __tablename__ = "kpl_list"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<KplList {self.trade_date} {self.ts_code}>"


class BlockTrade(PGBase):
    """大宗交易表"""

    __tablename__ = "block_trade"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    vol: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    buyer: Mapped[str] = mapped_column(String(200), nullable=False)
    seller: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ts_code", "trade_date", "buyer", "seller",
            name="uq_block_trade",
        ),
    )

    def __repr__(self) -> str:
        return f"<BlockTrade {self.ts_code} {self.trade_date}>"


# ---------------------------------------------------------------------------
# 2.8 市场交易统计数据模型
# ---------------------------------------------------------------------------


class MarketDailyInfo(PGBase):
    """沪深市场每日交易统计表"""

    __tablename__ = "market_daily_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ts_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    com_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    vol: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    trans_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "exchange", "ts_code",
            name="uq_market_daily_info",
        ),
    )

    def __repr__(self) -> str:
        return f"<MarketDailyInfo {self.trade_date} {self.exchange} {self.ts_code}>"


class SzDailyInfo(PGBase):
    """深圳市场每日交易情况表"""

    __tablename__ = "sz_daily_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(8), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(20), nullable=False)
    count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    vol: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_share: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    float_mv: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_sz_daily_info"),
    )

    def __repr__(self) -> str:
        return f"<SzDailyInfo {self.trade_date} {self.ts_code}>"
