"""TimescaleDB 大表 symbol 分批迁移脚本

对 kline（5.7亿行）和 adjustment_factor（1879万行）执行分批 UPDATE，
每批 50 万行，避免长事务锁表。

用法: python scripts/migrate_ts_symbol.py
"""

import asyncio
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

BATCH_SIZE = 500_000

TABLES = ["kline", "adjustment_factor"]

SUFFIX_RULES = [
    ("SH", "'^6'"),
    ("SZ", "'^[03]'"),
    ("BJ", "'^[489]'"),
]


async def migrate_table(engine, table: str) -> None:
    """分批为单张表添加交易所后缀。"""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 先扩列（幂等）
    async with async_session() as session:
        await session.execute(text(
            f"ALTER TABLE {table} ALTER COLUMN symbol TYPE VARCHAR(12)"
        ))
        await session.commit()
        print(f"[{table}] 列宽已扩展为 VARCHAR(12)")

    # 先处理已有带后缀数据的冲突
    async with async_session() as session:
        r = await session.execute(text(
            f"DELETE FROM {table} WHERE symbol LIKE '%.%' "
            f"AND split_part(symbol, '.', 1) IN "
            f"(SELECT symbol FROM {table} WHERE symbol NOT LIKE '%.%')"
        ))
        await session.commit()
        if r.rowcount > 0:
            print(f"[{table}] 删除 {r.rowcount} 条冲突的带后缀行")

    # 分批 UPDATE（仅处理 6 位纯数字裸代码，跳过已带后缀或异常数据）
    for suffix, regex in SUFFIX_RULES:
        total_updated = 0
        batch_num = 0
        while True:
            batch_num += 1
            t0 = time.time()
            async with async_session() as session:
                result = await session.execute(text(
                    f"UPDATE {table} SET symbol = symbol || '.{suffix}' "
                    f"WHERE ctid = ANY(ARRAY("
                    f"  SELECT ctid FROM {table} "
                    f"  WHERE symbol ~ {regex} AND symbol NOT LIKE '%.%' "
                    f"  AND length(symbol) = 6 "
                    f"  LIMIT {BATCH_SIZE}"
                    f"))"
                ))
                await session.commit()
                updated = result.rowcount
            total_updated += updated
            elapsed = time.time() - t0
            print(f"[{table}] .{suffix} 批次 {batch_num}: {updated} 行 ({elapsed:.1f}s)")
            if updated < BATCH_SIZE:
                break
        print(f"[{table}] .{suffix} 完成，共 {total_updated} 行")

    # 验证
    async with async_session() as session:
        r1 = await session.execute(text(
            f"SELECT count(*) FROM {table} WHERE symbol LIKE '%.%'"
        ))
        r2 = await session.execute(text(
            f"SELECT count(*) FROM {table} WHERE symbol NOT LIKE '%.%'"
        ))
        print(f"[{table}] 验证: 标准={r1.scalar()}, 裸码={r2.scalar()}")


async def main():
    engine = create_async_engine(str(settings.timescale_url), pool_size=2)
    for table in TABLES:
        print(f"\n{'='*60}")
        print(f"开始迁移 {table}")
        print(f"{'='*60}")
        await migrate_table(engine, table)
    await engine.dispose()
    print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(main())
