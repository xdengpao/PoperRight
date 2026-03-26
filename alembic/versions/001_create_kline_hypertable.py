"""create kline hypertable

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

创建 K线行情超表（TimescaleDB），配置时间分区和复合索引。
历史数据保留不少于 10 年，支持按股票代码、时间范围快速查询。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 kline 普通表
    op.execute("""
        CREATE TABLE IF NOT EXISTS kline (
            time        TIMESTAMPTZ NOT NULL,
            symbol      VARCHAR(10) NOT NULL,
            freq        VARCHAR(5)  NOT NULL,
            open        NUMERIC(12,4),
            high        NUMERIC(12,4),
            low         NUMERIC(12,4),
            close       NUMERIC(12,4),
            volume      BIGINT,
            amount      NUMERIC(18,2),
            turnover    NUMERIC(8,4),
            vol_ratio   NUMERIC(8,4),
            limit_up    NUMERIC(12,4),
            limit_down  NUMERIC(12,4),
            adj_type    SMALLINT DEFAULT 0
        )
    """)

    # 2. 将 kline 转换为 TimescaleDB 超表，按 time 列分区
    op.execute("SELECT create_hypertable('kline', 'time', if_not_exists => TRUE)")

    # 3. 创建复合索引，支持按股票代码、频率、时间范围快速查询
    op.execute("CREATE INDEX IF NOT EXISTS ix_kline_symbol_freq_time ON kline (symbol, freq, time DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kline CASCADE")
