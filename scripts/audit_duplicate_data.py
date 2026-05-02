#!/usr/bin/env python
"""全库重复数据审计脚本。

默认只读，输出 TimescaleDB 与 PostgreSQL 中可识别业务唯一键的重复情况。
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import text

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.services.data_engine.tushare_registry import TUSHARE_API_REGISTRY

DatabaseName = Literal["ts", "pg"]


@dataclass(frozen=True)
class DuplicateSpec:
    database: DatabaseName
    table: str
    key_exprs: tuple[str, ...]
    source: str
    action: str
    where_clause: str = ""


@dataclass
class DuplicateAuditResult:
    database: str
    table: str
    key: list[str]
    source: str
    action: str
    duplicate_groups: int
    duplicate_rows: int
    extra_rows: int
    sample_rows: list[dict]
    error: str | None = None


EVENT_TABLES = {
    "tushare_import_log",
    "audit_log",
    "risk_event_log",
}


BASE_SPECS: tuple[DuplicateSpec, ...] = (
    DuplicateSpec(
        database="ts",
        table="kline",
        key_exprs=(
            "symbol",
            "freq",
            "adj_type",
            "date(time at time zone 'Asia/Shanghai')",
        ),
        source="spec:kline_trade_day",
        action="merge_then_delete",
        where_clause="freq in ('1d', '1w', '1M')",
    ),
    DuplicateSpec(
        database="ts",
        table="sector_kline",
        key_exprs=("sector_code", "data_source", "freq", "date(time)"),
        source="spec:sector_trade_day",
        action="merge_then_delete",
        where_clause="freq in ('1d', '1w', '1M')",
    ),
    DuplicateSpec(
        database="ts",
        table="adjustment_factor",
        key_exprs=("symbol", "trade_date", "adj_type"),
        source="primary_key",
        action="auto_delete",
    ),
)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _registry_specs() -> list[DuplicateSpec]:
    specs: list[DuplicateSpec] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for entry in TUSHARE_API_REGISTRY.values():
        if not entry.conflict_columns:
            continue
        if entry.target_table in {"kline", "sector_kline", "adjustment_factor"}:
            continue
        database: DatabaseName = "ts" if entry.storage_engine.value == "ts" else "pg"
        key = tuple(_quote_ident(col) for col in entry.conflict_columns)
        dedupe_key = (entry.target_table, key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        action = "no_action" if entry.target_table in EVENT_TABLES else "auto_delete"
        specs.append(
            DuplicateSpec(
                database=database,
                table=entry.target_table,
                key_exprs=key,
                source=f"tushare_registry:{entry.api_name}",
                action=action,
            )
        )
    return specs


async def _table_exists(session, table: str) -> bool:
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public' AND table_name = :table
            )
            """
        ),
        {"table": table},
    )
    return bool(result.scalar())


async def _audit_spec(session, spec: DuplicateSpec, sample_limit: int) -> DuplicateAuditResult:
    if not await _table_exists(session, spec.table):
        return DuplicateAuditResult(
            database=spec.database,
            table=spec.table,
            key=list(spec.key_exprs),
            source=spec.source,
            action="no_action",
            duplicate_groups=0,
            duplicate_rows=0,
            extra_rows=0,
            sample_rows=[],
            error="table_not_found",
        )

    if spec.database == "ts" and spec.table == "kline" and spec.source == "spec:kline_trade_day":
        return await _audit_kline_trade_day(session, spec, sample_limit)

    key_sql = ", ".join(spec.key_exprs)
    where_sql = f"WHERE {spec.where_clause}" if spec.where_clause else ""
    group_sql = f"""
        WITH dup AS (
          SELECT {key_sql}, COUNT(*) AS rows
          FROM {_quote_ident(spec.table)}
          {where_sql}
          GROUP BY {key_sql}
          HAVING COUNT(*) > 1
        )
        SELECT
          COUNT(*) AS duplicate_groups,
          COALESCE(SUM(rows), 0) AS duplicate_rows,
          COALESCE(SUM(rows - 1), 0) AS extra_rows
        FROM dup
    """
    sample_sql = f"""
        SELECT {key_sql}, COUNT(*) AS rows
        FROM {_quote_ident(spec.table)}
        {where_sql}
        GROUP BY {key_sql}
        HAVING COUNT(*) > 1
        ORDER BY rows DESC
        LIMIT :sample_limit
    """

    summary = (await session.execute(text(group_sql))).mappings().one()
    samples = (await session.execute(text(sample_sql), {"sample_limit": sample_limit})).mappings().all()

    return DuplicateAuditResult(
        database=spec.database,
        table=spec.table,
        key=list(spec.key_exprs),
        source=spec.source,
        action=spec.action,
        duplicate_groups=int(summary["duplicate_groups"] or 0),
        duplicate_rows=int(summary["duplicate_rows"] or 0),
        extra_rows=int(summary["extra_rows"] or 0),
        sample_rows=[dict(row) for row in samples],
    )


async def _audit_kline_trade_day(
    session,
    spec: DuplicateSpec,
    sample_limit: int,
) -> DuplicateAuditResult:
    """审计本次已知的 16:00 UTC 日级偏移重复，避免整表表达式聚合超时。"""
    start_day = datetime(2024, 1, 1, tzinfo=timezone.utc).date()
    end_day = datetime.now(timezone.utc).date()
    duplicate_groups = 0
    duplicate_rows = 0
    extra_rows = 0
    samples: list[dict] = []

    current = start_day
    while current <= end_day:
        target_time = datetime.combine(current, datetime.min.time(), tzinfo=timezone.utc)
        source_time = target_time - timedelta(hours=8)
        rows = (await session.execute(text("""
            SELECT
              src.symbol,
              src.freq,
              src.adj_type,
              :trade_date AS trade_date,
              src.time AS source_time,
              dst.time AS target_time
            FROM kline src
            JOIN kline dst
              ON dst.time = :target_time
             AND dst.symbol = src.symbol
             AND dst.freq = src.freq
             AND dst.adj_type = src.adj_type
            WHERE src.time = :source_time
              AND src.freq in ('1d', '1w', '1M')
            LIMIT :sample_limit
        """), {
            "trade_date": current.isoformat(),
            "source_time": source_time,
            "target_time": target_time,
            "sample_limit": sample_limit,
        })).mappings().all()

        if rows:
            count_rows = await session.scalar(text("""
                SELECT COUNT(*)
                FROM kline src
                JOIN kline dst
                  ON dst.time = :target_time
                 AND dst.symbol = src.symbol
                 AND dst.freq = src.freq
                 AND dst.adj_type = src.adj_type
                WHERE src.time = :source_time
                  AND src.freq in ('1d', '1w', '1M')
            """), {
                "source_time": source_time,
                "target_time": target_time,
            })
            count = int(count_rows or 0)
            duplicate_groups += count
            duplicate_rows += count * 2
            extra_rows += count
            if len(samples) < sample_limit:
                samples.extend(dict(row) for row in rows[: sample_limit - len(samples)])

        current += timedelta(days=1)

    return DuplicateAuditResult(
        database=spec.database,
        table=spec.table,
        key=list(spec.key_exprs),
        source=spec.source,
        action=spec.action,
        duplicate_groups=duplicate_groups,
        duplicate_rows=duplicate_rows,
        extra_rows=extra_rows,
        sample_rows=samples,
    )


async def audit_duplicates(database: str, sample_limit: int) -> list[DuplicateAuditResult]:
    specs = list(BASE_SPECS) + _registry_specs()
    if database != "all":
        specs = [spec for spec in specs if spec.database == database]

    results: list[DuplicateAuditResult] = []
    for db_name in ("ts", "pg"):
        db_specs = [spec for spec in specs if spec.database == db_name]
        if not db_specs:
            continue
        session_factory = AsyncSessionTS if db_name == "ts" else AsyncSessionPG
        async with session_factory() as session:
            await session.execute(text("SET statement_timeout = '60s'"))
            for spec in db_specs:
                try:
                    results.append(await _audit_spec(session, spec, sample_limit))
                except Exception as exc:  # noqa: BLE001 - 审计脚本需要继续扫描其他表
                    await session.rollback()
                    results.append(
                        DuplicateAuditResult(
                            database=spec.database,
                            table=spec.table,
                            key=list(spec.key_exprs),
                            source=spec.source,
                            action="manual_review",
                            duplicate_groups=0,
                            duplicate_rows=0,
                            extra_rows=0,
                            sample_rows=[],
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
    return results


def _write_reports(results: list[DuplicateAuditResult], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    json_path = output_dir / f"duplicate_audit_{stamp}.json"
    md_path = output_dir / f"duplicate_audit_{stamp}.md"

    json_path.write_text(
        json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    lines = ["# 全库重复数据审计报告", ""]
    for result in results:
        if result.duplicate_groups == 0 and not result.error:
            continue
        lines.extend(
            [
                f"## {result.database}.{result.table}",
                "",
                f"- 口径: `{', '.join(result.key)}`",
                f"- 来源: `{result.source}`",
                f"- 动作: `{result.action}`",
                f"- 重复组: `{result.duplicate_groups}`",
                f"- 重复行: `{result.duplicate_rows}`",
                f"- 多余行: `{result.extra_rows}`",
            ]
        )
        if result.error:
            lines.append(f"- 错误: `{result.error}`")
        if result.sample_rows:
            lines.append(f"- 样例: `{result.sample_rows[:3]}`")
        lines.append("")
    if len(lines) == 2:
        lines.append("未发现可识别重复数据。")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="全库重复数据审计")
    parser.add_argument("--database", choices=["ts", "pg", "all"], default="all")
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    results = asyncio.run(audit_duplicates(args.database, args.sample_limit))
    json_path, md_path = _write_reports(results, Path(args.output_dir))
    print(f"审计完成: {json_path}")
    print(f"Markdown 报告: {md_path}")
    for result in results:
        if result.duplicate_groups or result.error:
            print(
                f"{result.database}.{result.table}: groups={result.duplicate_groups} "
                f"extra={result.extra_rows} action={result.action} error={result.error or '-'}"
            )


if __name__ == "__main__":
    main()
