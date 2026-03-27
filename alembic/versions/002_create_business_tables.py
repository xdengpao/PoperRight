"""create business tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:01.000000

创建 PostgreSQL 业务数据表：
- stock_info：股票基础信息
- permanent_exclusion：永久剔除名单
- stock_list：黑白名单
- strategy_template：选股策略模板（单用户最多 20 套）
- screen_result：选股结果
- backtest_run：回测配置与结果
- trade_order：委托记录
- position：持仓
- app_user：系统用户
- audit_log：操作日志（BIGSERIAL 主键）
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. stock_info - 股票基础信息
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_info (
            symbol          VARCHAR(10) PRIMARY KEY,
            name            VARCHAR(50),
            market          VARCHAR(10),
            board           VARCHAR(10),
            list_date       DATE,
            is_st           BOOLEAN DEFAULT FALSE,
            is_delisted     BOOLEAN DEFAULT FALSE,
            pledge_ratio    NUMERIC(6,2),
            pe_ttm          NUMERIC(10,2),
            pb              NUMERIC(10,2),
            roe             NUMERIC(8,4),
            market_cap      NUMERIC(20,2),
            updated_at      TIMESTAMPTZ
        )
    """)

    # ------------------------------------------------------------------
    # 2. permanent_exclusion - 永久剔除名单
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS permanent_exclusion (
            symbol      VARCHAR(10) PRIMARY KEY,
            reason      VARCHAR(50),
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 3. app_user - 系统用户（strategy_template 外键依赖）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_user (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username        VARCHAR(50) UNIQUE NOT NULL,
            password_hash   VARCHAR(128) NOT NULL,
            role            VARCHAR(30),
            is_active       BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 4. strategy_template - 选股策略模板（单用户最多 20 套）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS strategy_template (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL,
            name        VARCHAR(100),
            config      JSONB NOT NULL,
            is_active   BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 5. screen_result - 选股结果
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS screen_result (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            strategy_id     UUID REFERENCES strategy_template(id),
            screen_time     TIMESTAMPTZ NOT NULL,
            screen_type     VARCHAR(10),
            symbol          VARCHAR(10),
            ref_buy_price   NUMERIC(12,4),
            trend_score     NUMERIC(5,2),
            risk_level      VARCHAR(10),
            signals         JSONB,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 6. stock_list - 黑白名单
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_list (
            symbol      VARCHAR(10) NOT NULL,
            list_type   VARCHAR(10) NOT NULL,
            user_id     UUID NOT NULL,
            reason      VARCHAR(200),
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (symbol, list_type, user_id)
        )
    """)

    # ------------------------------------------------------------------
    # 7. backtest_run - 回测配置与结果
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS backtest_run (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            strategy_id     UUID REFERENCES strategy_template(id),
            user_id         UUID NOT NULL,
            start_date      DATE,
            end_date        DATE,
            initial_capital NUMERIC(18,2),
            commission_buy  NUMERIC(8,6) DEFAULT 0.0003,
            commission_sell NUMERIC(8,6) DEFAULT 0.0013,
            slippage        NUMERIC(8,6) DEFAULT 0.001,
            status          VARCHAR(20),
            result          JSONB,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 8. trade_order - 委托记录
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS trade_order (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL,
            symbol          VARCHAR(10),
            order_type      VARCHAR(20),
            direction       VARCHAR(5),
            price           NUMERIC(12,4),
            quantity        INTEGER,
            status          VARCHAR(20),
            broker_order_id VARCHAR(50),
            mode            VARCHAR(10),
            submitted_at    TIMESTAMPTZ,
            filled_at       TIMESTAMPTZ,
            filled_price    NUMERIC(12,4),
            filled_qty      INTEGER,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 9. position - 持仓
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS position (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL,
            symbol      VARCHAR(10),
            quantity    INTEGER,
            cost_price  NUMERIC(12,4),
            mode        VARCHAR(10),
            updated_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, symbol, mode)
        )
    """)

    # ------------------------------------------------------------------
    # 10. audit_log - 操作日志（BIGSERIAL 主键，保留 1 年）
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          BIGSERIAL PRIMARY KEY,
            user_id     UUID,
            action      VARCHAR(100),
            target      VARCHAR(200),
            detail      JSONB,
            ip_addr     INET,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # 索引
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX IF NOT EXISTS ix_screen_result_strategy_time ON screen_result (strategy_id, screen_time DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_screen_result_symbol ON screen_result (symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_backtest_run_user ON backtest_run (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trade_order_user_time ON trade_order (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trade_order_symbol ON trade_order (symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_user_time ON audit_log (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_strategy_template_user ON strategy_template (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS position CASCADE")
    op.execute("DROP TABLE IF EXISTS trade_order CASCADE")
    op.execute("DROP TABLE IF EXISTS backtest_run CASCADE")
    op.execute("DROP TABLE IF EXISTS stock_list CASCADE")
    op.execute("DROP TABLE IF EXISTS screen_result CASCADE")
    op.execute("DROP TABLE IF EXISTS strategy_template CASCADE")
    op.execute("DROP TABLE IF EXISTS app_user CASCADE")
    op.execute("DROP TABLE IF EXISTS permanent_exclusion CASCADE")
    op.execute("DROP TABLE IF EXISTS stock_info CASCADE")
