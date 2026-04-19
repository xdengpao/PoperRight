#!/usr/bin/env python3
"""
板块数据清理脚本

清理数据库中因解析缺陷产生的脏数据：
1. 删除 sector_kline 表中 data_source='TDX' 且 sector_code 不以 '.TDX' 结尾的记录
   （TDX 历史行情 ZIP 解析时未补充 .TDX 后缀导致的不一致数据）
2. 删除 sector_kline 表中 data_source='DC' 且 sector_code 不以 '.DC' 结尾的记录
   （DC 行业板块行情格式 B 解析时未补充 .DC 后缀导致的不一致数据）
3. 删除 sector_info 表中 data_source='DC' 且 sector_code 不以 'BK' 开头的记录
   （DC 简版板块列表被错误解析产生的垃圾数据）

用法:
    python scripts/cleanup_sector_data.py

需求: 18.3, 18.4, 19.3, 19.4, 20.3, 20.4
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# 环境与数据库连接
# ---------------------------------------------------------------------------

# 加载 .env 文件（项目根目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _to_sync_url(async_url: str) -> str:
    """将 asyncpg 连接字符串转换为同步 psycopg2 连接字符串"""
    return async_url.replace("postgresql+asyncpg://", "postgresql://")


def _get_pg_engine():
    """获取 PostgreSQL（业务数据库）同步引擎"""
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5433/quant_db")
    return create_engine(_to_sync_url(url))


def _get_ts_engine():
    """获取 TimescaleDB（时序数据库）同步引擎"""
    url = os.getenv("TIMESCALE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/quant_ts")
    return create_engine(_to_sync_url(url))


# ---------------------------------------------------------------------------
# 清理函数
# ---------------------------------------------------------------------------


def cleanup_tdx_kline_without_suffix() -> int:
    """删除 sector_kline 表中 data_source='TDX' 且 sector_code 不以 '.TDX' 结尾的记录

    这些记录来自 TDX 历史行情 ZIP 解析时未补充 .TDX 后缀的旧数据。

    Returns:
        删除的记录数量
    """
    engine = _get_ts_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM sector_kline "
                "WHERE data_source = 'TDX' "
                "AND sector_code NOT LIKE '%.TDX'"
            )
        )
        deleted = result.rowcount
    engine.dispose()
    print(f"[TDX Kline 清理] 删除 sector_kline 中不带 .TDX 后缀的 TDX 记录: {deleted} 条")
    return deleted


def cleanup_dc_kline_without_suffix() -> int:
    """删除 sector_kline 表中 data_source='DC' 且 sector_code 不以 '.DC' 结尾的记录

    这些记录来自 DC 行业板块行情（格式 B）解析时未补充 .DC 后缀的旧数据。

    Returns:
        删除的记录数量
    """
    engine = _get_ts_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM sector_kline "
                "WHERE data_source = 'DC' "
                "AND sector_code NOT LIKE '%.DC'"
            )
        )
        deleted = result.rowcount
    engine.dispose()
    print(f"[DC Kline 清理] 删除 sector_kline 中不带 .DC 后缀的 DC 记录: {deleted} 条")
    return deleted


def cleanup_dc_info_garbage() -> int:
    """删除 sector_info 表中 data_source='DC' 且 sector_code 不以 'BK' 开头的记录

    这些记录来自 DC 简版板块列表被错误按 13 列格式解析产生的垃圾数据
    （日期被当作板块代码、价格被当作板块名称等）。

    Returns:
        删除的记录数量
    """
    engine = _get_pg_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM sector_info "
                "WHERE data_source = 'DC' "
                "AND sector_code NOT LIKE 'BK%'"
            )
        )
        deleted = result.rowcount
    engine.dispose()
    print(f"[DC Info 清理] 删除 sector_info 中非 BK 开头的 DC 垃圾记录: {deleted} 条")
    return deleted


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------


def main() -> None:
    """依次执行所有清理任务并输出汇总报告"""
    print("=" * 60)
    print("板块数据清理脚本")
    print("=" * 60)
    print()

    # 1. 清理 TDX 行情中不带后缀的记录
    print("[1/3] 清理 TDX 行情数据（sector_kline）...")
    tdx_deleted = cleanup_tdx_kline_without_suffix()
    print()

    # 2. 清理 DC 行情中不带后缀的记录
    print("[2/3] 清理 DC 行情数据（sector_kline）...")
    dc_kline_deleted = cleanup_dc_kline_without_suffix()
    print()

    # 3. 清理 DC 板块信息中的垃圾记录
    print("[3/3] 清理 DC 板块信息（sector_info）...")
    dc_info_deleted = cleanup_dc_info_garbage()
    print()

    # 汇总报告
    print("=" * 60)
    print("清理完成 — 汇总报告")
    print("=" * 60)
    print(f"  TDX sector_kline 不带后缀记录: 删除 {tdx_deleted} 条")
    print(f"  DC  sector_kline 不带后缀记录: 删除 {dc_kline_deleted} 条")
    print(f"  DC  sector_info  垃圾记录:     删除 {dc_info_deleted} 条")
    print(f"  合计删除: {tdx_deleted + dc_kline_deleted + dc_info_deleted} 条")
    print()
    if tdx_deleted > 0:
        print("提示: TDX 行情数据已清理，请清空 Redis 增量缓存后触发全量导入以重新导入 TDX 历史行情。")
    if dc_kline_deleted > 0:
        print("提示: DC 行情数据已清理，请清空 Redis 增量缓存后触发全量导入以重新导入 DC 行业板块行情。")
    if dc_info_deleted > 0:
        print("提示: DC 垃圾记录已清理，板块列表数据已恢复正常。")


if __name__ == "__main__":
    main()
