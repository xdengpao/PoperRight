"""add tushare import tables

Revision ID: 017
Revises: 016
Create Date: 2026-06-15 00:00:00.000000

创建 Tushare 数据导入相关表（PostgreSQL）：
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

需求 25：数据模型扩展
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# 所有新建表名（用于 downgrade 批量删除）
# ---------------------------------------------------------------------------
_NEW_TABLES = [
    "sz_daily_info",
    "market_daily_info",
    "block_trade",
    "kpl_list",
    "ths_hot",
    "dc_hot",
    "ths_limit",
    "top_inst",
    "top_list",
    "hm_detail",
    "hm_list",
    "limit_step",
    "limit_list",
    "slb_sec",
    "slb_len",
    "margin_target",
    "margin_detail",
    "margin_data",
    "stk_factor",
    "stk_limit",
    "stk_account",
    "stk_holdertrade",
    "stk_holdernumber",
    "top_holders",
    "stk_managers",
    "stk_rewards",
    "hs_constituent",
    "stock_namechange",
    "stock_company",
    "moneyflow_mkt_dc",
    "moneyflow_ind",
    "moneyflow_hsgt",
    "tushare_money_flow",
    "index_tech",
    "index_global",
    "index_dailybasic",
    "index_weight",
    "index_info",
    "express",
    "forecast",
    "dividend",
    "financial_statement",
    "suspend_info",
    "daily_share",
    "stock_st",
    "new_share",
    "trade_calendar",
    "tushare_import_log",
]


def upgrade() -> None:
    # ==================================================================
    # 2.1 导入日志和基础数据模型
    # ==================================================================

    # --- tushare_import_log ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS tushare_import_log (
            id              SERIAL PRIMARY KEY,
            api_name        VARCHAR(50) NOT NULL,
            params_json     JSONB,
            status          VARCHAR(20) NOT NULL,
            record_count    INTEGER NOT NULL DEFAULT 0,
            error_message   VARCHAR(500),
            celery_task_id  VARCHAR(50),
            started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at     TIMESTAMPTZ
        )
    """)

    # --- trade_calendar ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS trade_calendar (
            exchange    VARCHAR(10) NOT NULL,
            cal_date    DATE NOT NULL,
            is_open     BOOLEAN NOT NULL,
            PRIMARY KEY (exchange, cal_date)
        )
    """)

    # --- new_share ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS new_share (
            ts_code         VARCHAR(10) PRIMARY KEY,
            sub_code        VARCHAR(10),
            name            VARCHAR(50),
            ipo_date        VARCHAR(8),
            issue_date      VARCHAR(8),
            amount          NUMERIC,
            market_amount   NUMERIC,
            price           NUMERIC,
            pe              NUMERIC,
            limit_amount    NUMERIC,
            funds           NUMERIC,
            ballot          NUMERIC
        )
    """)

    # --- stock_st ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_st (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            name        VARCHAR(50),
            is_st       VARCHAR(2),
            st_date     VARCHAR(8),
            st_type     VARCHAR(20)
        )
    """)

    # --- daily_share ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_share (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            total_share     NUMERIC,
            float_share     NUMERIC,
            free_share      NUMERIC,
            total_mv        NUMERIC,
            float_mv        NUMERIC
        )
    """)
    op.execute("""
        ALTER TABLE daily_share
        ADD CONSTRAINT uq_daily_share UNIQUE (ts_code, trade_date)
    """)

    # --- suspend_info ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS suspend_info (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            suspend_date    VARCHAR(8),
            resume_date     VARCHAR(8),
            suspend_type    VARCHAR(20)
        )
    """)

    # ==================================================================
    # 2.2 财务数据模型
    # ==================================================================

    # --- financial_statement ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS financial_statement (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            ann_date        VARCHAR(8),
            end_date        VARCHAR(8) NOT NULL,
            report_type     VARCHAR(20) NOT NULL,
            data_json       JSONB NOT NULL
        )
    """)
    op.execute("""
        ALTER TABLE financial_statement
        ADD CONSTRAINT uq_financial_statement UNIQUE (ts_code, end_date, report_type)
    """)

    # --- dividend ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS dividend (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            ann_date    VARCHAR(8),
            end_date    VARCHAR(8),
            div_proc    VARCHAR(20),
            stk_div     NUMERIC(10, 4),
            cash_div    NUMERIC(10, 4)
        )
    """)

    # --- forecast ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS forecast (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            ann_date        VARCHAR(8),
            end_date        VARCHAR(8) NOT NULL,
            type            VARCHAR(20),
            p_change_min    NUMERIC(10, 2),
            p_change_max    NUMERIC(10, 2),
            net_profit_min  NUMERIC(20, 2),
            net_profit_max  NUMERIC(20, 2),
            summary         VARCHAR(1000)
        )
    """)
    op.execute("""
        ALTER TABLE forecast
        ADD CONSTRAINT uq_forecast UNIQUE (ts_code, end_date)
    """)

    # --- express ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS express (
            id                              SERIAL PRIMARY KEY,
            ts_code                         VARCHAR(10) NOT NULL,
            ann_date                        VARCHAR(8),
            end_date                        VARCHAR(8) NOT NULL,
            revenue                         NUMERIC(20, 2),
            operate_profit                  NUMERIC(20, 2),
            total_profit                    NUMERIC(20, 2),
            n_income                        NUMERIC(20, 2),
            total_assets                    NUMERIC(20, 2),
            total_hldr_eqy_exc_min_int      NUMERIC(20, 2),
            diluted_eps                     NUMERIC(10, 4),
            yoy_net_profit                  NUMERIC(10, 4),
            bps                             NUMERIC(10, 4),
            perf_summary                    VARCHAR(1000)
        )
    """)
    op.execute("""
        ALTER TABLE express
        ADD CONSTRAINT uq_express UNIQUE (ts_code, end_date)
    """)

    # ==================================================================
    # 2.3 指数数据模型
    # ==================================================================

    # --- index_info ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_info (
            ts_code     VARCHAR(20) PRIMARY KEY,
            name        VARCHAR(100),
            market      VARCHAR(20),
            publisher   VARCHAR(50),
            category    VARCHAR(50),
            base_date   VARCHAR(8),
            base_point  NUMERIC(10, 2),
            list_date   VARCHAR(8)
        )
    """)

    # --- index_weight ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_weight (
            id          SERIAL PRIMARY KEY,
            index_code  VARCHAR(20) NOT NULL,
            con_code    VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            weight      NUMERIC(10, 6)
        )
    """)
    op.execute("""
        ALTER TABLE index_weight
        ADD CONSTRAINT uq_index_weight UNIQUE (index_code, con_code, trade_date)
    """)

    # --- index_dailybasic ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_dailybasic (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            pe              NUMERIC(10, 4),
            pb              NUMERIC(10, 4),
            turnover_rate   NUMERIC(10, 4),
            total_mv        NUMERIC(20, 2),
            float_mv        NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE index_dailybasic
        ADD CONSTRAINT uq_index_dailybasic UNIQUE (ts_code, trade_date)
    """)

    # --- index_global ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_global (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            open        NUMERIC(20, 4),
            close       NUMERIC(20, 4),
            high        NUMERIC(20, 4),
            low         NUMERIC(20, 4),
            pre_close   NUMERIC(20, 4),
            change      NUMERIC(20, 4),
            pct_chg     NUMERIC(10, 4),
            vol         NUMERIC(20, 2),
            amount      NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE index_global
        ADD CONSTRAINT uq_index_global UNIQUE (ts_code, trade_date)
    """)

    # --- index_tech ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_tech (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            close       NUMERIC(20, 4),
            macd_dif    NUMERIC(20, 6),
            macd_dea    NUMERIC(20, 6),
            macd        NUMERIC(20, 6),
            kdj_k       NUMERIC(10, 4),
            kdj_d       NUMERIC(10, 4),
            kdj_j       NUMERIC(10, 4),
            rsi_6       NUMERIC(10, 4),
            rsi_12      NUMERIC(10, 4),
            boll_upper  NUMERIC(20, 4),
            boll_mid    NUMERIC(20, 4),
            boll_lower  NUMERIC(20, 4)
        )
    """)
    op.execute("""
        ALTER TABLE index_tech
        ADD CONSTRAINT uq_index_tech UNIQUE (ts_code, trade_date)
    """)

    # ==================================================================
    # 2.4 资金流向数据模型
    # ==================================================================

    # --- tushare_money_flow ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS tushare_money_flow (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            buy_sm_amount   NUMERIC(20, 2),
            sell_sm_amount  NUMERIC(20, 2),
            buy_md_amount   NUMERIC(20, 2),
            sell_md_amount  NUMERIC(20, 2),
            buy_lg_amount   NUMERIC(20, 2),
            sell_lg_amount  NUMERIC(20, 2),
            buy_elg_amount  NUMERIC(20, 2),
            sell_elg_amount NUMERIC(20, 2),
            net_mf_amount   NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE tushare_money_flow
        ADD CONSTRAINT uq_tushare_money_flow UNIQUE (ts_code, trade_date)
    """)

    # --- moneyflow_hsgt ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS moneyflow_hsgt (
            id              SERIAL PRIMARY KEY,
            trade_date      VARCHAR(8) NOT NULL,
            ggt_ss          NUMERIC(20, 2),
            ggt_sz          NUMERIC(20, 2),
            hgt             NUMERIC(20, 2),
            sgt             NUMERIC(20, 2),
            north_money     NUMERIC(20, 2),
            south_money     NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE moneyflow_hsgt
        ADD CONSTRAINT uq_moneyflow_hsgt UNIQUE (trade_date)
    """)

    # --- moneyflow_ind ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS moneyflow_ind (
            id              SERIAL PRIMARY KEY,
            trade_date      VARCHAR(8) NOT NULL,
            industry_name   VARCHAR(50) NOT NULL,
            data_source     VARCHAR(10) NOT NULL,
            buy_amount      NUMERIC(20, 2),
            sell_amount     NUMERIC(20, 2),
            net_amount      NUMERIC(20, 2)
        )
    """)

    # --- moneyflow_mkt_dc ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS moneyflow_mkt_dc (
            id                  SERIAL PRIMARY KEY,
            trade_date          VARCHAR(8) NOT NULL,
            close               NUMERIC,
            change              NUMERIC,
            pct_change          NUMERIC,
            net_mf_amount       NUMERIC,
            net_mf_amount_rate  NUMERIC,
            buy_elg_amount      NUMERIC(20, 2),
            sell_elg_amount     NUMERIC(20, 2),
            buy_lg_amount       NUMERIC(20, 2),
            sell_lg_amount      NUMERIC(20, 2),
            buy_md_amount       NUMERIC(20, 2),
            sell_md_amount      NUMERIC(20, 2),
            buy_sm_amount       NUMERIC(20, 2),
            sell_sm_amount      NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE moneyflow_mkt_dc
        ADD CONSTRAINT uq_moneyflow_mkt_dc UNIQUE (trade_date)
    """)

    # ==================================================================
    # 2.5 参考数据和特色数据模型
    # ==================================================================

    # --- stock_company ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_company (
            ts_code     VARCHAR(10) PRIMARY KEY,
            chairman    VARCHAR(100),
            manager     VARCHAR(100),
            secretary   VARCHAR(100),
            reg_capital NUMERIC,
            setup_date  VARCHAR(8),
            province    VARCHAR(50),
            city        VARCHAR(50),
            website     VARCHAR(200)
        )
    """)

    # --- stock_namechange ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_namechange (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            name            VARCHAR(50),
            start_date      VARCHAR(8),
            end_date        VARCHAR(8),
            change_reason   VARCHAR(200)
        )
    """)

    # --- hs_constituent ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS hs_constituent (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            hs_type     VARCHAR(10),
            in_date     VARCHAR(8),
            out_date    VARCHAR(8),
            is_new      VARCHAR(2)
        )
    """)

    # --- stk_rewards ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_rewards (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            ann_date    VARCHAR(8),
            name        VARCHAR(100),
            title       VARCHAR(100),
            reward      NUMERIC(20, 2),
            hold_vol    NUMERIC(20, 2)
        )
    """)

    # --- stk_managers ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_managers (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            ann_date    VARCHAR(8),
            name        VARCHAR(100),
            gender      VARCHAR(10),
            lev         VARCHAR(50),
            title       VARCHAR(100),
            edu         VARCHAR(50),
            national    VARCHAR(50),
            birthday    VARCHAR(8),
            begin_date  VARCHAR(8),
            end_date    VARCHAR(8)
        )
    """)

    # --- top_holders ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS top_holders (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            ann_date        VARCHAR(8),
            end_date        VARCHAR(8) NOT NULL,
            holder_name     VARCHAR(200) NOT NULL,
            hold_amount     NUMERIC(20, 2),
            hold_ratio      NUMERIC(10, 6),
            holder_type     VARCHAR(20) NOT NULL
        )
    """)
    op.execute("""
        ALTER TABLE top_holders
        ADD CONSTRAINT uq_top_holders UNIQUE (ts_code, end_date, holder_name, holder_type)
    """)

    # --- stk_holdernumber ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_holdernumber (
            id                  SERIAL PRIMARY KEY,
            ts_code             VARCHAR(10) NOT NULL,
            ann_date            VARCHAR(8),
            end_date            VARCHAR(8),
            holder_num          NUMERIC,
            holder_num_change   NUMERIC
        )
    """)

    # --- stk_holdertrade ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_holdertrade (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            ann_date        VARCHAR(8),
            holder_name     VARCHAR(200),
            change_vol      NUMERIC,
            change_ratio    NUMERIC,
            after_vol       NUMERIC,
            after_ratio     NUMERIC,
            in_de           VARCHAR(10)
        )
    """)

    # --- stk_account ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_account (
            id          SERIAL PRIMARY KEY,
            date        VARCHAR(8) NOT NULL,
            weekly_new  NUMERIC,
            total       NUMERIC,
            weekly_hold NUMERIC
        )
    """)

    # --- stk_limit ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_limit (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            up_limit    NUMERIC(10, 2),
            down_limit  NUMERIC(10, 2)
        )
    """)
    op.execute("""
        ALTER TABLE stk_limit
        ADD CONSTRAINT uq_stk_limit UNIQUE (ts_code, trade_date)
    """)

    # --- stk_factor ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_factor (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            close       NUMERIC(20, 4),
            macd_dif    NUMERIC(20, 6),
            macd_dea    NUMERIC(20, 6),
            macd        NUMERIC(20, 6),
            kdj_k       NUMERIC(10, 4),
            kdj_d       NUMERIC(10, 4),
            kdj_j       NUMERIC(10, 4),
            rsi_6       NUMERIC(10, 4),
            rsi_12      NUMERIC(10, 4),
            rsi_24      NUMERIC(10, 4),
            boll_upper  NUMERIC(20, 4),
            boll_mid    NUMERIC(20, 4),
            boll_lower  NUMERIC(20, 4),
            cci         NUMERIC(10, 4)
        )
    """)
    op.execute("""
        ALTER TABLE stk_factor
        ADD CONSTRAINT uq_stk_factor UNIQUE (ts_code, trade_date)
    """)

    # ==================================================================
    # 2.6 两融及转融通数据模型
    # ==================================================================

    # --- margin_data ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS margin_data (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            exchange_id VARCHAR(10) NOT NULL,
            rzye        NUMERIC(20, 2),
            rzmre       NUMERIC(20, 2),
            rzche       NUMERIC(20, 2),
            rqye        NUMERIC(20, 2),
            rqmcl       NUMERIC(20, 2),
            rzrqye      NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE margin_data
        ADD CONSTRAINT uq_margin_data UNIQUE (trade_date, exchange_id)
    """)

    # --- margin_detail ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS margin_detail (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            rzye        NUMERIC(20, 2),
            rzmre       NUMERIC(20, 2),
            rzche       NUMERIC(20, 2),
            rqye        NUMERIC(20, 2),
            rqmcl       NUMERIC(20, 2),
            rqyl        NUMERIC(20, 2)
        )
    """)
    op.execute("""
        ALTER TABLE margin_detail
        ADD CONSTRAINT uq_margin_detail UNIQUE (ts_code, trade_date)
    """)

    # --- margin_target ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS margin_target (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            mg_type     VARCHAR(10),
            is_new      VARCHAR(2)
        )
    """)

    # --- slb_len ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS slb_len (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            len_rate    NUMERIC(10, 6),
            len_amt     NUMERIC(20, 2)
        )
    """)

    # --- slb_sec ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS slb_sec (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            sec_amt     NUMERIC(20, 2),
            sec_vol     NUMERIC(20, 2)
        )
    """)

    # ==================================================================
    # 2.7 打板专题数据模型
    # ==================================================================

    # --- limit_list ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS limit_list (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            industry        VARCHAR(50),
            close           NUMERIC,
            pct_chg         NUMERIC,
            amount          NUMERIC,
            limit_amount    NUMERIC,
            float_mv        NUMERIC,
            total_mv        NUMERIC,
            turnover_ratio  NUMERIC,
            fd_amount       NUMERIC,
            first_time      VARCHAR(20),
            last_time       VARCHAR(20),
            open_times      INTEGER,
            up_stat         VARCHAR(20),
            limit_times     INTEGER,
            "limit"         VARCHAR(2) NOT NULL
        )
    """)
    op.execute("""
        ALTER TABLE limit_list
        ADD CONSTRAINT uq_limit_list UNIQUE (ts_code, trade_date, "limit")
    """)

    # --- limit_step ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS limit_step (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(10) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            name            VARCHAR(50),
            close           NUMERIC,
            pct_chg         NUMERIC,
            step            INTEGER,
            limit_order     INTEGER,
            amount          NUMERIC,
            turnover_ratio  NUMERIC,
            fd_amount       NUMERIC,
            first_time      VARCHAR(20),
            last_time       VARCHAR(20),
            open_times      INTEGER
        )
    """)
    op.execute("""
        ALTER TABLE limit_step
        ADD CONSTRAINT uq_limit_step UNIQUE (ts_code, trade_date)
    """)

    # --- hm_list ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS hm_list (
            id          SERIAL PRIMARY KEY,
            hm_name     VARCHAR(100),
            hm_code     VARCHAR(50),
            market      VARCHAR(20),
            "desc"      VARCHAR(500)
        )
    """)

    # --- hm_detail ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS hm_detail (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(10) NOT NULL,
            hm_name     VARCHAR(100),
            buy_amount  NUMERIC(20, 2),
            sell_amount NUMERIC(20, 2),
            net_amount  NUMERIC(20, 2)
        )
    """)

    # --- top_list ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS top_list (
            id              SERIAL PRIMARY KEY,
            trade_date      VARCHAR(8) NOT NULL,
            ts_code         VARCHAR(10) NOT NULL,
            name            VARCHAR(50),
            close           NUMERIC,
            pct_change      NUMERIC,
            turnover_rate   NUMERIC,
            amount          NUMERIC,
            l_sell          NUMERIC,
            l_buy           NUMERIC,
            l_amount        NUMERIC,
            net_amount      NUMERIC,
            net_rate        NUMERIC,
            amount_rate     NUMERIC,
            float_values    NUMERIC,
            reason          VARCHAR(200)
        )
    """)
    op.execute("""
        ALTER TABLE top_list
        ADD CONSTRAINT uq_top_list UNIQUE (trade_date, ts_code, reason)
    """)

    # --- top_inst ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS top_inst (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(10) NOT NULL,
            exalter     VARCHAR(200) NOT NULL,
            buy         NUMERIC,
            buy_rate    NUMERIC,
            sell        NUMERIC,
            sell_rate   NUMERIC,
            net_buy     NUMERIC
        )
    """)
    op.execute("""
        ALTER TABLE top_inst
        ADD CONSTRAINT uq_top_inst UNIQUE (trade_date, ts_code, exalter)
    """)

    # --- ths_limit ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ths_limit (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(10) NOT NULL,
            name        VARCHAR(50),
            close       NUMERIC,
            pct_chg     NUMERIC,
            fd_amount   NUMERIC,
            first_time  VARCHAR(20),
            last_time   VARCHAR(20),
            open_times  INTEGER,
            "limit"     VARCHAR(2) NOT NULL
        )
    """)
    op.execute("""
        ALTER TABLE ths_limit
        ADD CONSTRAINT uq_ths_limit UNIQUE (ts_code, trade_date, "limit")
    """)

    # --- dc_hot ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS dc_hot (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(10) NOT NULL,
            name        VARCHAR(50),
            rank        INTEGER,
            pct_chg     NUMERIC,
            hot_value   NUMERIC
        )
    """)

    # --- ths_hot ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ths_hot (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(10) NOT NULL,
            name        VARCHAR(50),
            rank        INTEGER,
            pct_chg     NUMERIC,
            hot_value   NUMERIC
        )
    """)

    # --- kpl_list ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpl_list (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(10) NOT NULL,
            name        VARCHAR(50),
            close       NUMERIC,
            pct_chg     NUMERIC,
            tag         VARCHAR(100)
        )
    """)

    # --- block_trade ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS block_trade (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(10) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            price       NUMERIC,
            vol         NUMERIC,
            amount      NUMERIC,
            buyer       VARCHAR(200) NOT NULL,
            seller      VARCHAR(200) NOT NULL
        )
    """)
    op.execute("""
        ALTER TABLE block_trade
        ADD CONSTRAINT uq_block_trade UNIQUE (ts_code, trade_date, buyer, seller)
    """)

    # ==================================================================
    # 2.8 市场交易统计数据模型
    # ==================================================================

    # --- market_daily_info ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS market_daily_info (
            id              SERIAL PRIMARY KEY,
            trade_date      VARCHAR(8) NOT NULL,
            exchange        VARCHAR(10) NOT NULL,
            ts_code         VARCHAR(20) NOT NULL,
            ts_name         VARCHAR(50),
            com_count       INTEGER,
            total_share     NUMERIC,
            float_share     NUMERIC,
            total_mv        NUMERIC,
            float_mv        NUMERIC,
            amount          NUMERIC,
            vol             NUMERIC,
            trans_count     INTEGER
        )
    """)
    op.execute("""
        ALTER TABLE market_daily_info
        ADD CONSTRAINT uq_market_daily_info UNIQUE (trade_date, exchange, ts_code)
    """)

    # --- sz_daily_info ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS sz_daily_info (
            id              SERIAL PRIMARY KEY,
            trade_date      VARCHAR(8) NOT NULL,
            ts_code         VARCHAR(20) NOT NULL,
            count           INTEGER,
            amount          NUMERIC,
            vol             NUMERIC,
            total_share     NUMERIC,
            total_mv        NUMERIC,
            float_share     NUMERIC,
            float_mv        NUMERIC
        )
    """)
    op.execute("""
        ALTER TABLE sz_daily_info
        ADD CONSTRAINT uq_sz_daily_info UNIQUE (trade_date, ts_code)
    """)


def downgrade() -> None:
    for table in _NEW_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
