#!/usr/bin/env python
"""全库重复数据安全清理入口。

默认 dry-run。当前自动清理仅处理 `auto_delete` 口径，即相同业务键下
保留一条 canonical 行并删除其余行；需要字段合并的表输出提示，交由
专项脚本处理。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionPG, AsyncSessionTS
from scripts.audit_duplicate_data import BASE_SPECS, DuplicateSpec, _quote_ident, _registry_specs


def _selected_specs(database: str, table: str | None, exclude_tables: set[str]) -> list[DuplicateSpec]:
    specs = list(BASE_SPECS) + _registry_specs()
    if database != "all":
        specs = [spec for spec in specs if spec.database == database]
    if table:
        specs = [spec for spec in specs if spec.table == table]
    if exclude_tables:
        specs = [spec for spec in specs if spec.table not in exclude_tables]
    return specs


async def _count_extra_rows(session, spec: DuplicateSpec) -> int:
    key_sql = ", ".join(spec.key_exprs)
    where_sql = f"WHERE {spec.where_clause}" if spec.where_clause else ""
    sql = f"""
        WITH dup AS (
          SELECT {key_sql}, COUNT(*) AS rows
          FROM {_quote_ident(spec.table)}
          {where_sql}
          GROUP BY {key_sql}
          HAVING COUNT(*) > 1
        )
        SELECT COALESCE(SUM(rows - 1), 0) FROM dup
    """
    return int((await session.execute(text(sql))).scalar() or 0)


async def _backup_duplicates(session, spec: DuplicateSpec, backup_table: str) -> None:
    key_sql = ", ".join(spec.key_exprs)
    where_sql = f"WHERE {spec.where_clause}" if spec.where_clause else ""
    sql = f"""
        CREATE TABLE {_quote_ident(backup_table)} AS
        WITH dup_key AS (
          SELECT {key_sql}
          FROM {_quote_ident(spec.table)}
          {where_sql}
          GROUP BY {key_sql}
          HAVING COUNT(*) > 1
        )
        SELECT src.*, src.ctid::text AS source_ctid
        FROM {_quote_ident(spec.table)} src
        JOIN dup_key USING ({_using_columns(spec)})
    """
    await session.execute(text(sql))


def _using_columns(spec: DuplicateSpec) -> str:
    columns: list[str] = []
    for expr in spec.key_exprs:
        stripped = expr.strip().strip('"')
        if not stripped.replace("_", "").isalnum():
            raise ValueError(f"{spec.table} 的 key 表达式不是普通列，不能使用通用 auto_delete: {expr}")
        columns.append(_quote_ident(stripped))
    return ", ".join(columns)


async def _delete_duplicate_rows(session, spec: DuplicateSpec, batch_size: int) -> int:
    key_sql = ", ".join(spec.key_exprs)
    where_sql = f"WHERE {spec.where_clause}" if spec.where_clause else ""
    sql = f"""
        WITH ranked AS (
          SELECT ctid,
                 row_number() OVER (
                   PARTITION BY {key_sql}
                   ORDER BY ctid
                 ) AS rn
          FROM {_quote_ident(spec.table)}
          {where_sql}
        ),
        victims AS (
          SELECT ctid FROM ranked WHERE rn > 1 LIMIT :batch_size
        )
        DELETE FROM {_quote_ident(spec.table)} t
        USING victims
        WHERE t.ctid = victims.ctid
    """
    result = await session.execute(text(sql), {"batch_size": batch_size})
    return int(result.rowcount or 0)


async def repair_duplicates(
    *,
    database: str,
    table: str | None,
    exclude_tables: set[str],
    execute: bool,
    batch_size: int,
) -> None:
    specs = _selected_specs(database, table, exclude_tables)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    for db_name in ("ts", "pg"):
        db_specs = [spec for spec in specs if spec.database == db_name]
        if not db_specs:
            continue
        session_factory = AsyncSessionTS if db_name == "ts" else AsyncSessionPG
        async with session_factory() as session:
            await session.execute(text("SET statement_timeout = '120s'"))
            for spec in db_specs:
                if spec.action != "auto_delete":
                    extra = await _count_extra_rows(session, spec)
                    print(
                        f"SKIP {spec.database}.{spec.table}: action={spec.action}, "
                        f"extra_rows={extra}，需专项合并或人工确认"
                    )
                    continue
                try:
                    extra = await _count_extra_rows(session, spec)
                    if extra == 0:
                        print(f"OK {spec.database}.{spec.table}: 无重复")
                        continue
                    print(f"FOUND {spec.database}.{spec.table}: extra_rows={extra}")
                    if not execute:
                        continue

                    backup_table = f"duplicate_backup_{spec.table}_{stamp}"
                    await _backup_duplicates(session, spec, backup_table)
                    deleted_total = 0
                    while True:
                        deleted = await _delete_duplicate_rows(session, spec, batch_size)
                        deleted_total += deleted
                        if deleted == 0:
                            break
                    await session.commit()
                    remaining = await _count_extra_rows(session, spec)
                    print(
                        f"DONE {spec.database}.{spec.table}: deleted={deleted_total}, "
                        f"backup={backup_table}, remaining_extra={remaining}"
                    )
                except Exception as exc:  # noqa: BLE001 - 每表独立回滚并继续
                    await session.rollback()
                    print(f"ERROR {spec.database}.{spec.table}: {type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="全库重复数据清理")
    parser.add_argument("--database", choices=["ts", "pg", "all"], default="all")
    parser.add_argument("--table")
    parser.add_argument("--exclude-table", action="append", default=[])
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        repair_duplicates(
            database=args.database,
            table=args.table,
            exclude_tables=set(args.exclude_table),
            execute=args.execute,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()
