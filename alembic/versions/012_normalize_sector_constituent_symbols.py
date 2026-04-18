"""normalize sector_constituent symbol to bare format

Revision ID: 012
Revises: 011
Create Date: 2026-04-18 00:00:00.000000

sector_constituent.symbol 列中存储了带市场后缀的股票代码（如 000002.SZ），
但项目规范要求业务表统一使用裸代码（如 000002）。
参见 data-consistency.md §3.2。

本迁移将所有带后缀的 symbol 去掉 ".SZ" / ".SH" / ".BJ" 后缀。
使用分批更新避免长事务锁表。
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

_BATCH_SIZE = 500_000


def upgrade() -> None:
    # 分批更新，避免 45M 行单事务超时
    conn = op.get_bind()
    total = 0
    while True:
        result = conn.execute(
            __import__("sqlalchemy").text(f"""
                UPDATE sector_constituent
                SET symbol = split_part(symbol, '.', 1)
                WHERE id IN (
                    SELECT id FROM sector_constituent
                    WHERE symbol LIKE '%.%'
                    LIMIT {_BATCH_SIZE}
                )
            """)
        )
        updated = result.rowcount
        total += updated
        if updated == 0:
            break
    # 记录总数供审计
    print(f"012: normalized {total} sector_constituent symbols")


def downgrade() -> None:
    # 无法可靠恢复后缀（不知道原始后缀是 .SZ / .SH / .BJ），不做操作
    pass
