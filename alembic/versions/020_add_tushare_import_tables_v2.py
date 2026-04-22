"""add tushare import tables v2

Revision ID: 020
Revises: 019_slb_fix
Create Date: 2026-04-22 01:00:00+08:00

新增 Tushare 数据导入 v2 表（PostgreSQL）：
- 扩展 DataSource 枚举（新增 CI、THS）
- 新建 v2 新增表（st_warning、stk_premarket、stock_hsgt、bse_mapping 等 40+ 张表）
- 为 stk_factor 添加 wr/dmi/trix/bias 列
- 扩展 tushare_import_log.celery_task_id 长度
- 重命名 tushare_money_flow → tushare_moneyflow（ORM 对齐）

需求 25.84
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "020"
down_revision = "019_slb_fix"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# 所有新建表名（用于 downgrade 批量删除）
# ---------------------------------------------------------------------------
_NEW_TABLES = [
    "dc_concept_cons",
    "dc_concept",
    "kpl_concept_cons",
    "stk_auction",
    "limit_cpt_list",
    "limit_list_ths",
    "moneyflow_cnt_ths",
    "moneyflow_dc",
    "moneyflow_ths",
    "tushare_moneyflow",
    "margin_secs",
    "broker_recommend",
    "stk_surv",
    "stk_ah_comparison",
    "stk_nineturn",
    "stk_auction_c",
    "stk_auction_o",
    "hk_hold",
    "ccass_hold_detail",
    "ccass_hold",
    "cyq_chips",
    "cyq_perf",
    "report_rc",
    "share_float",
    "repurchase",
    "pledge_detail",
    "pledge_stat",
    "stk_alert",
    "stk_high_shock",
    "stk_shock",
    "disclosure_date",
    "fina_mainbz",
    "ggt_monthly",
    "ggt_daily",
    "ggt_top10",
    "hsgt_top10",
    "bse_mapping",
    "stock_hsgt",
    "stk_premarket",
    "st_warning",
]


def upgrade() -> None:
    # ==================================================================
    # 0. DataSource 枚举扩展说明
    # ==================================================================
    # DataSource 在 ORM 中定义为 Python str Enum（app/models/sector.py），
    # 数据库中 data_source 列类型为 VARCHAR(10)，不是 PostgreSQL 原生枚举类型。
    # 因此无需 ALTER TYPE 语句，新增的 CI/THS 值可直接写入 VARCHAR 列。

    # ==================================================================
    # 0.1 扩展 tushare_import_log.celery_task_id 长度
    # ==================================================================
    op.alter_column(
        "tushare_import_log",
        "celery_task_id",
        type_=sa.String(100),
        existing_type=sa.String(50),
    )

    # ==================================================================
    # 0.2 为 stk_factor 添加 wr/dmi/trix/bias 列
    # ==================================================================
    op.add_column("stk_factor", sa.Column("wr", sa.Float, nullable=True))
    op.add_column("stk_factor", sa.Column("dmi", sa.Float, nullable=True))
    op.add_column("stk_factor", sa.Column("trix", sa.Float, nullable=True))
    op.add_column("stk_factor", sa.Column("bias", sa.Float, nullable=True))


    # ==================================================================
    # 1. 基础数据新增表
    # ==================================================================

    # --- st_warning ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS st_warning (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            name        VARCHAR(50),
            close       DOUBLE PRECISION,
            pct_chg     DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            CONSTRAINT uq_st_warning_ts_code_trade_date UNIQUE (ts_code, trade_date)
        )
    """)

    # --- stk_premarket ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_premarket (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            total_share DOUBLE PRECISION,
            float_share DOUBLE PRECISION,
            free_share  DOUBLE PRECISION,
            total_mv    DOUBLE PRECISION,
            float_mv    DOUBLE PRECISION,
            up_limit    DOUBLE PRECISION,
            down_limit  DOUBLE PRECISION,
            CONSTRAINT uq_stk_premarket_ts_code_trade_date UNIQUE (ts_code, trade_date)
        )
    """)

    # --- stock_hsgt ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_hsgt (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            hs_type     VARCHAR(5),
            in_date     VARCHAR(8),
            out_date    VARCHAR(8),
            is_new      VARCHAR(5)
        )
    """)

    # --- bse_mapping ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS bse_mapping (
            id          SERIAL PRIMARY KEY,
            old_code    VARCHAR(20),
            new_code    VARCHAR(20),
            name        VARCHAR(50),
            list_date   VARCHAR(8)
        )
    """)

    # ==================================================================
    # 2. 行情数据新增表
    # ==================================================================

    # --- hsgt_top10 ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS hsgt_top10 (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(20) NOT NULL,
            name        VARCHAR(50),
            close       DOUBLE PRECISION,
            change      DOUBLE PRECISION,
            rank        INTEGER,
            market_type VARCHAR(5),
            amount      DOUBLE PRECISION,
            net_amount  DOUBLE PRECISION,
            buy         DOUBLE PRECISION,
            sell        DOUBLE PRECISION,
            CONSTRAINT uq_hsgt_top10_trade_date_ts_code_market_type
                UNIQUE (trade_date, ts_code, market_type)
        )
    """)

    # --- ggt_top10 ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ggt_top10 (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(20) NOT NULL,
            name        VARCHAR(50),
            close       DOUBLE PRECISION,
            p_change    DOUBLE PRECISION,
            rank        INTEGER,
            market_type VARCHAR(5),
            amount      DOUBLE PRECISION,
            net_amount  DOUBLE PRECISION,
            buy         DOUBLE PRECISION,
            sell        DOUBLE PRECISION,
            CONSTRAINT uq_ggt_top10_trade_date_ts_code_market_type
                UNIQUE (trade_date, ts_code, market_type)
        )
    """)

    # --- ggt_daily ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ggt_daily (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            buy_amount  DOUBLE PRECISION,
            buy_volume  DOUBLE PRECISION,
            sell_amount DOUBLE PRECISION,
            sell_volume DOUBLE PRECISION,
            CONSTRAINT uq_ggt_daily_trade_date UNIQUE (trade_date)
        )
    """)

    # --- ggt_monthly ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ggt_monthly (
            id          SERIAL PRIMARY KEY,
            month       VARCHAR(6) NOT NULL,
            buy_amount  DOUBLE PRECISION,
            buy_volume  DOUBLE PRECISION,
            sell_amount DOUBLE PRECISION,
            sell_volume DOUBLE PRECISION,
            CONSTRAINT uq_ggt_monthly_month UNIQUE (month)
        )
    """)

    # ==================================================================
    # 3. 财务数据新增表
    # ==================================================================

    # --- fina_mainbz ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS fina_mainbz (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            end_date    VARCHAR(8) NOT NULL,
            bz_item     VARCHAR(100) NOT NULL,
            bz_sales    DOUBLE PRECISION,
            bz_profit   DOUBLE PRECISION,
            bz_cost     DOUBLE PRECISION,
            curr_type   VARCHAR(10),
            CONSTRAINT uq_fina_mainbz_ts_code_end_date_bz_item
                UNIQUE (ts_code, end_date, bz_item)
        )
    """)

    # --- disclosure_date ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS disclosure_date (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            ann_date    VARCHAR(8),
            end_date    VARCHAR(8) NOT NULL,
            pre_date    VARCHAR(8),
            actual_date VARCHAR(8),
            CONSTRAINT uq_disclosure_date_ts_code_end_date
                UNIQUE (ts_code, end_date)
        )
    """)

    # ==================================================================
    # 4. 参考数据新增表
    # ==================================================================

    # --- stk_shock ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_shock (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            shock_type  VARCHAR(20) NOT NULL,
            pct_chg     DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            CONSTRAINT uq_stk_shock_ts_code_trade_date_shock_type
                UNIQUE (ts_code, trade_date, shock_type)
        )
    """)

    # --- stk_high_shock ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_high_shock (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            shock_type  VARCHAR(20) NOT NULL,
            pct_chg     DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            CONSTRAINT uq_stk_high_shock_ts_code_trade_date_shock_type
                UNIQUE (ts_code, trade_date, shock_type)
        )
    """)

    # --- stk_alert ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_alert (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            alert_type  VARCHAR(50),
            alert_desc  VARCHAR(500)
        )
    """)

    # --- pledge_stat ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS pledge_stat (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            end_date        VARCHAR(8) NOT NULL,
            pledge_count    INTEGER,
            unrest_pledge   DOUBLE PRECISION,
            rest_pledge     DOUBLE PRECISION,
            total_share     DOUBLE PRECISION,
            pledge_ratio    DOUBLE PRECISION,
            CONSTRAINT uq_pledge_stat_ts_code_end_date
                UNIQUE (ts_code, end_date)
        )
    """)

    # --- pledge_detail ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS pledge_detail (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            ann_date        VARCHAR(8),
            holder_name     VARCHAR(200),
            pledge_amount   DOUBLE PRECISION,
            start_date      VARCHAR(8),
            end_date        VARCHAR(8),
            is_release      VARCHAR(5)
        )
    """)

    # --- repurchase ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS repurchase (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            ann_date    VARCHAR(8),
            end_date    VARCHAR(8),
            proc        VARCHAR(50),
            exp_date    VARCHAR(8),
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            high_limit  DOUBLE PRECISION,
            low_limit   DOUBLE PRECISION
        )
    """)

    # --- share_float ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS share_float (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            ann_date    VARCHAR(8),
            float_date  VARCHAR(8),
            float_share DOUBLE PRECISION,
            float_ratio DOUBLE PRECISION,
            holder_name VARCHAR(200),
            share_type  VARCHAR(50)
        )
    """)


    # ==================================================================
    # 5. 特色数据新增表
    # ==================================================================

    # --- report_rc ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS report_rc (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            report_date     VARCHAR(8),
            broker_name     VARCHAR(100),
            analyst_name    VARCHAR(50),
            target_price    DOUBLE PRECISION,
            rating          VARCHAR(20),
            eps_est         DOUBLE PRECISION
        )
    """)

    # --- cyq_perf ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS cyq_perf (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            his_low     DOUBLE PRECISION,
            his_high    DOUBLE PRECISION,
            cost_5pct   DOUBLE PRECISION,
            cost_15pct  DOUBLE PRECISION,
            cost_50pct  DOUBLE PRECISION,
            cost_85pct  DOUBLE PRECISION,
            cost_95pct  DOUBLE PRECISION,
            weight_avg  DOUBLE PRECISION,
            winner_rate DOUBLE PRECISION,
            CONSTRAINT uq_cyq_perf_ts_code_trade_date UNIQUE (ts_code, trade_date)
        )
    """)

    # --- cyq_chips ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS cyq_chips (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            price       DOUBLE PRECISION,
            percent     DOUBLE PRECISION
        )
    """)

    # --- ccass_hold ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ccass_hold (
            id                  SERIAL PRIMARY KEY,
            ts_code             VARCHAR(20) NOT NULL,
            trade_date          VARCHAR(8) NOT NULL,
            participant_id      VARCHAR(20),
            participant_name    VARCHAR(200),
            hold_amount         DOUBLE PRECISION,
            hold_ratio          DOUBLE PRECISION
        )
    """)

    # --- ccass_hold_detail ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ccass_hold_detail (
            id                  SERIAL PRIMARY KEY,
            ts_code             VARCHAR(20) NOT NULL,
            trade_date          VARCHAR(8) NOT NULL,
            participant_id      VARCHAR(20),
            participant_name    VARCHAR(200),
            hold_amount         DOUBLE PRECISION,
            hold_ratio          DOUBLE PRECISION
        )
    """)

    # --- hk_hold ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS hk_hold (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            code        VARCHAR(20),
            vol         DOUBLE PRECISION,
            ratio       DOUBLE PRECISION,
            exchange    VARCHAR(10),
            CONSTRAINT uq_hk_hold_ts_code_trade_date_exchange
                UNIQUE (ts_code, trade_date, exchange)
        )
    """)

    # --- stk_auction_o ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_auction_o (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            open        DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            CONSTRAINT uq_stk_auction_o_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- stk_auction_c ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_auction_c (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            close       DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            CONSTRAINT uq_stk_auction_c_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- stk_nineturn ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_nineturn (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            turn_type   VARCHAR(10),
            turn_number INTEGER,
            CONSTRAINT uq_stk_nineturn_ts_code_trade_date_turn_type
                UNIQUE (ts_code, trade_date, turn_type)
        )
    """)

    # --- stk_ah_comparison ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_ah_comparison (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            a_close     DOUBLE PRECISION,
            h_close     DOUBLE PRECISION,
            ah_ratio    DOUBLE PRECISION,
            CONSTRAINT uq_stk_ah_comparison_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- stk_surv ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_surv (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            surv_date       VARCHAR(8),
            fund_name       VARCHAR(200),
            surv_type       VARCHAR(50),
            participants    VARCHAR(500)
        )
    """)

    # --- broker_recommend ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS broker_recommend (
            id          SERIAL PRIMARY KEY,
            month       VARCHAR(6),
            broker      VARCHAR(100),
            ts_code     VARCHAR(20) NOT NULL,
            name        VARCHAR(50),
            rating      VARCHAR(20)
        )
    """)

    # ==================================================================
    # 6. 两融及转融通新增表
    # ==================================================================

    # --- margin_secs ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS margin_secs (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            mg_type     VARCHAR(10),
            is_new      VARCHAR(5)
        )
    """)

    # ==================================================================
    # 7. 资金流向新增表
    # ==================================================================

    # --- tushare_moneyflow ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS tushare_moneyflow (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            buy_sm_amount   DOUBLE PRECISION,
            sell_sm_amount  DOUBLE PRECISION,
            buy_md_amount   DOUBLE PRECISION,
            sell_md_amount  DOUBLE PRECISION,
            buy_lg_amount   DOUBLE PRECISION,
            sell_lg_amount  DOUBLE PRECISION,
            buy_elg_amount  DOUBLE PRECISION,
            sell_elg_amount DOUBLE PRECISION,
            net_mf_amount   DOUBLE PRECISION,
            CONSTRAINT uq_tushare_moneyflow_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- moneyflow_ths ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS moneyflow_ths (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            buy_sm_amount   DOUBLE PRECISION,
            sell_sm_amount  DOUBLE PRECISION,
            buy_md_amount   DOUBLE PRECISION,
            sell_md_amount  DOUBLE PRECISION,
            buy_lg_amount   DOUBLE PRECISION,
            sell_lg_amount  DOUBLE PRECISION,
            buy_elg_amount  DOUBLE PRECISION,
            sell_elg_amount DOUBLE PRECISION,
            net_mf_amount   DOUBLE PRECISION,
            CONSTRAINT uq_moneyflow_ths_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- moneyflow_dc ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS moneyflow_dc (
            id              SERIAL PRIMARY KEY,
            ts_code         VARCHAR(20) NOT NULL,
            trade_date      VARCHAR(8) NOT NULL,
            buy_sm_amount   DOUBLE PRECISION,
            sell_sm_amount  DOUBLE PRECISION,
            buy_md_amount   DOUBLE PRECISION,
            sell_md_amount  DOUBLE PRECISION,
            buy_lg_amount   DOUBLE PRECISION,
            sell_lg_amount  DOUBLE PRECISION,
            buy_elg_amount  DOUBLE PRECISION,
            sell_elg_amount DOUBLE PRECISION,
            net_mf_amount   DOUBLE PRECISION,
            CONSTRAINT uq_moneyflow_dc_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- moneyflow_cnt_ths ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS moneyflow_cnt_ths (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(20) NOT NULL,
            name        VARCHAR(50),
            buy_amount  DOUBLE PRECISION,
            sell_amount DOUBLE PRECISION,
            net_amount  DOUBLE PRECISION
        )
    """)


    # ==================================================================
    # 8. 打板专题新增表
    # ==================================================================

    # --- limit_list_ths ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS limit_list_ths (
            id          SERIAL PRIMARY KEY,
            trade_date  VARCHAR(8) NOT NULL,
            ts_code     VARCHAR(20) NOT NULL,
            name        VARCHAR(50),
            close       DOUBLE PRECISION,
            pct_chg     DOUBLE PRECISION,
            fd_amount   DOUBLE PRECISION,
            first_time  VARCHAR(20),
            last_time   VARCHAR(20),
            open_times  INTEGER,
            "limit"     VARCHAR(5),
            CONSTRAINT uq_limit_list_ths_ts_code_trade_date_limit
                UNIQUE (ts_code, trade_date, "limit")
        )
    """)

    # --- limit_cpt_list ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS limit_cpt_list (
            id              SERIAL PRIMARY KEY,
            trade_date      VARCHAR(8) NOT NULL,
            concept_name    VARCHAR(100),
            limit_count     INTEGER,
            up_count        INTEGER,
            down_count      INTEGER,
            amount          DOUBLE PRECISION
        )
    """)

    # --- stk_auction ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS stk_auction (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            open        DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            bid_price   DOUBLE PRECISION,
            bid_vol     DOUBLE PRECISION,
            CONSTRAINT uq_stk_auction_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)

    # --- kpl_concept_cons ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS kpl_concept_cons (
            id              SERIAL PRIMARY KEY,
            concept_code    VARCHAR(20) NOT NULL,
            ts_code         VARCHAR(20) NOT NULL,
            name            VARCHAR(50)
        )
    """)

    # --- dc_concept ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS dc_concept (
            id              SERIAL PRIMARY KEY,
            concept_code    VARCHAR(20) NOT NULL,
            concept_name    VARCHAR(100),
            src             VARCHAR(20)
        )
    """)

    # --- dc_concept_cons ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS dc_concept_cons (
            id              SERIAL PRIMARY KEY,
            concept_code    VARCHAR(20) NOT NULL,
            ts_code         VARCHAR(20) NOT NULL,
            name            VARCHAR(50)
        )
    """)


def downgrade() -> None:
    # 删除新建表
    for table in _NEW_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

    # 移除 stk_factor 新增列
    op.drop_column("stk_factor", "bias")
    op.drop_column("stk_factor", "trix")
    op.drop_column("stk_factor", "dmi")
    op.drop_column("stk_factor", "wr")

    # 恢复 tushare_import_log.celery_task_id 长度
    op.alter_column(
        "tushare_import_log",
        "celery_task_id",
        type_=sa.String(50),
        existing_type=sa.String(100),
    )

    # 注意：DataSource 枚举在数据库中为 VARCHAR(10) 列，
    # CI/THS 值无需特殊处理即可在 downgrade 中忽略。
