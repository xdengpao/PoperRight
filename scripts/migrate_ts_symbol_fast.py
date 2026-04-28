"""TimescaleDB 大表 symbol 迁移（psycopg2 同步直连，无分批）

直接用 psycopg2 同步连接执行 UPDATE，绕过 asyncpg 单语句限制。
每条 UPDATE 处理一个交易所的全部数据，autocommit 模式避免长事务。

用法: python scripts/migrate_ts_symbol_fast.py
"""

import time
import psycopg2

DSN = "host=localhost dbname=quant_ts user=postgres password=password"

TABLES = ["kline", "adjustment_factor"]

SUFFIX_RULES = [
    ("SH", "^6"),
    ("SZ", "^[03]"),
    ("BJ", "^[489]"),
]


def migrate():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()

    for table in TABLES:
        print(f"\n{'='*60}")
        print(f"开始迁移 {table}")
        print(f"{'='*60}")

        # 扩列（幂等）
        cur.execute(f"ALTER TABLE {table} ALTER COLUMN symbol TYPE VARCHAR(12)")
        print(f"[{table}] 列宽 VARCHAR(12) OK")

        # 删除冲突的带后缀行
        cur.execute(
            f"DELETE FROM {table} WHERE symbol LIKE '%%.__' "
            f"AND split_part(symbol, '.', 1) IN "
            f"(SELECT symbol FROM {table} WHERE symbol NOT LIKE '%%.%%')"
        )
        print(f"[{table}] 冲突清理: {cur.rowcount} 行")

        # 逐交易所 UPDATE
        for suffix, regex in SUFFIX_RULES:
            t0 = time.time()
            cur.execute(
                f"UPDATE {table} SET symbol = symbol || '.{suffix}' "
                f"WHERE symbol ~ '{regex}' AND symbol NOT LIKE '%%.%%' "
                f"AND length(symbol) = 6"
            )
            elapsed = time.time() - t0
            print(f"[{table}] .{suffix}: {cur.rowcount:,} 行 ({elapsed:.1f}s)")

        # 验证
        cur.execute(f"SELECT count(*) FROM {table} WHERE symbol LIKE '%%.__'")
        done = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {table} WHERE symbol NOT LIKE '%%.%%' AND length(symbol)=6")
        todo = cur.fetchone()[0]
        print(f"[{table}] 验证: 标准={done:,}, 裸码={todo:,}")

    cur.close()
    conn.close()
    print("\n迁移完成!")


if __name__ == "__main__":
    migrate()
