"""add sector tables

Revision ID: 010
Revises: 009
Create Date: 2026-05-01 00:00:00.000000

创建板块数据相关表：
- sector_info：板块元数据（PostgreSQL）
- sector_constituent：板块成分股快照（PostgreSQL）
- sector_kline：板块指数行情（TimescaleDB 超表）
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. sector_info — 板块元数据（PostgreSQL）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sector_info (
            id                  SERIAL PRIMARY KEY,
            sector_code         VARCHAR(20) NOT NULL,
            name                VARCHAR(100) NOT NULL,
            sector_type         VARCHAR(20) NOT NULL,
            data_source         VARCHAR(10) NOT NULL,
            list_date           DATE,
            constituent_count   INTEGER,
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # 唯一约束：同一数据源下板块代码不重复
    op.execute("""
        ALTER TABLE sector_info
        ADD CONSTRAINT uq_sector_info_code_source
        UNIQUE (sector_code, data_source)
    """)

    # 查询索引：按板块类型和数据来源筛选
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sector_info_type_source
        ON sector_info (sector_type, data_source)
    """)

    # ------------------------------------------------------------------
    # 2. sector_constituent — 板块成分股快照（PostgreSQL）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sector_constituent (
            id              SERIAL PRIMARY KEY,
            trade_date      DATE NOT NULL,
            sector_code     VARCHAR(20) NOT NULL,
            data_source     VARCHAR(10) NOT NULL,
            symbol          VARCHAR(10) NOT NULL,
            stock_name      VARCHAR(50)
        )
    """)

    # 唯一约束：同一交易日同一板块同一数据源下成分股不重复
    op.execute("""
        ALTER TABLE sector_constituent
        ADD CONSTRAINT uq_sector_constituent_date_code_source_symbol
        UNIQUE (trade_date, sector_code, data_source, symbol)
    """)

    # 查询索引：按股票代码和交易日期查询（股票所属板块）
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sector_constituent_symbol_date
        ON sector_constituent (symbol, trade_date)
    """)

    # 查询索引：按板块代码、数据来源和交易日期查询（板块成分股）
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sector_constituent_code_source_date
        ON sector_constituent (sector_code, data_source, trade_date)
    """)

    # ------------------------------------------------------------------
    # 3. sector_kline — 板块指数行情（TimescaleDB 超表）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sector_kline (
            time            TIMESTAMP NOT NULL,
            sector_code     VARCHAR(20) NOT NULL,
            data_source     VARCHAR(10) NOT NULL,
            freq            VARCHAR(5) NOT NULL,
            open            NUMERIC,
            high            NUMERIC,
            low             NUMERIC,
            close           NUMERIC,
            volume          BIGINT,
            amount          NUMERIC,
            turnover        NUMERIC,
            change_pct      NUMERIC,
            PRIMARY KEY (time, sector_code, data_source, freq)
        )
    """)

    # 将 sector_kline 转换为 TimescaleDB 超表
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable('sector_kline', 'time', if_not_exists => TRUE);
            END IF;
        END $$;
    """)

    # 唯一索引（与复合主键一致，显式命名供 ORM 引用）
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sector_kline_time_code_source_freq
        ON sector_kline (time, sector_code, data_source, freq)
    """)

    # 查询索引：按板块代码、数据来源、频率和时间范围查询
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sector_kline_code_source_freq_time
        ON sector_kline (sector_code, data_source, freq, time)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sector_kline CASCADE")
    op.execute("DROP TABLE IF EXISTS sector_constituent CASCADE")
    op.execute("DROP TABLE IF EXISTS sector_info CASCADE")
