"""重建 st_warning 表以匹配 Tushare st 接口实际返回字段

旧表结构（trade_date, close, pct_chg, vol, amount）与 Tushare 返回的
字段（pub_date, imp_date, st_tpye, st_reason, st_explain）完全不匹配。

Revision ID: 20260424_0020
"""

from alembic import op

revision = "20260424_0020"
down_revision = "20260424_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除旧表并重建
    op.execute("DROP TABLE IF EXISTS st_warning CASCADE")
    op.execute("""
        CREATE TABLE st_warning (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            name        VARCHAR(50),
            pub_date    VARCHAR(8),
            imp_date    VARCHAR(8),
            st_tpye     VARCHAR(20),
            st_reason   TEXT,
            st_explain  TEXT,
            CONSTRAINT uq_st_warning_ts_code_imp_date
                UNIQUE (ts_code, imp_date)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS st_warning CASCADE")
    op.execute("""
        CREATE TABLE st_warning (
            id          SERIAL PRIMARY KEY,
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(8) NOT NULL,
            name        VARCHAR(50),
            close       DOUBLE PRECISION,
            pct_chg     DOUBLE PRECISION,
            vol         DOUBLE PRECISION,
            amount      DOUBLE PRECISION,
            CONSTRAINT uq_st_warning_ts_code_trade_date
                UNIQUE (ts_code, trade_date)
        )
    """)
