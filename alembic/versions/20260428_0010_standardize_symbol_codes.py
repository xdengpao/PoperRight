"""统一股票代码为标准格式（symbol 列宽 VARCHAR(10) → VARCHAR(12)，数据添加交易所后缀）

将所有业务表和时序表的 symbol 字段从纯 6 位数字格式统一为带交易所后缀的标准格式
（如 600000 → 600000.SH），与行业标准接轨。

Revision ID: 20260428_0010
"""

from alembic import op

revision = "20260428_0010"
down_revision = "20260424_0040"
branch_labels = None
depends_on = None

# 需要扩列和数据转换的表（表名, 是否有唯一约束需要重建）
_PG_TABLES = [
    "stock_info",
    "permanent_exclusion",
    "stock_list",
    "money_flow",
    "screen_result",
    "trade_order",
    "position",
    "risk_event_log",
    "stock_pool_item",
    "sector_constituent",
]

_TS_TABLES = [
    "kline",
    "adjustment_factor",
]

_ALL_TABLES = _PG_TABLES + _TS_TABLES


def _add_suffix(table: str) -> None:
    """为单张表的 symbol 字段添加交易所后缀。

    处理混合格式：先删除与裸代码重复的已带后缀行（保留裸代码行，
    因为裸代码行通常数据更完整），再统一加后缀。
    """
    # 删除已带后缀且与裸代码行主键冲突的记录（裸代码行优先保留）
    op.execute(
        f"DELETE FROM {table} WHERE symbol LIKE '%.%' "
        f"AND split_part(symbol, '.', 1) IN "
        f"(SELECT symbol FROM {table} WHERE symbol NOT LIKE '%.%')"
    )
    # 对仅存在带后缀格式的行不做处理（已是标准格式）
    # 对裸代码行添加后缀
    op.execute(f"UPDATE {table} SET symbol = symbol || '.SH' WHERE symbol ~ '^6' AND symbol NOT LIKE '%.%'")
    op.execute(f"UPDATE {table} SET symbol = symbol || '.SZ' WHERE symbol ~ '^[03]' AND symbol NOT LIKE '%.%'")
    op.execute(f"UPDATE {table} SET symbol = symbol || '.BJ' WHERE symbol ~ '^[489]' AND symbol NOT LIKE '%.%'")


def _strip_suffix(table: str) -> None:
    """去除单张表 symbol 字段的交易所后缀。"""
    op.execute(f"UPDATE {table} SET symbol = split_part(symbol, '.', 1) WHERE symbol LIKE '%.%'")


def upgrade() -> None:
    # 第一步：扩列宽度
    for table in _ALL_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN symbol TYPE VARCHAR(12)")

    # 第二步：批量添加交易所后缀
    for table in _ALL_TABLES:
        _add_suffix(table)

    # 第三步：重建受影响的唯一约束（每条语句单独执行）
    op.execute("ALTER TABLE position DROP CONSTRAINT IF EXISTS uq_position_user_symbol_mode")
    op.execute("ALTER TABLE position ADD CONSTRAINT uq_position_user_symbol_mode UNIQUE (user_id, symbol, mode)")
    op.execute("ALTER TABLE sector_constituent DROP CONSTRAINT IF EXISTS uq_sector_constituent_date_code_source_symbol")
    op.execute("ALTER TABLE sector_constituent ADD CONSTRAINT uq_sector_constituent_date_code_source_symbol UNIQUE (trade_date, sector_code, data_source, symbol)")


def downgrade() -> None:
    # 第一步：去除后缀
    for table in _ALL_TABLES:
        _strip_suffix(table)

    # 第二步：缩列宽度
    for table in _ALL_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN symbol TYPE VARCHAR(10)")

    # 第三步：重建约束
    op.execute("ALTER TABLE position DROP CONSTRAINT IF EXISTS uq_position_user_symbol_mode")
    op.execute("ALTER TABLE position ADD CONSTRAINT uq_position_user_symbol_mode UNIQUE (user_id, symbol, mode)")
    op.execute("ALTER TABLE sector_constituent DROP CONSTRAINT IF EXISTS uq_sector_constituent_date_code_source_symbol")
    op.execute("ALTER TABLE sector_constituent ADD CONSTRAINT uq_sector_constituent_date_code_source_symbol UNIQUE (trade_date, sector_code, data_source, symbol)")
