#!/usr/bin/env python3
"""
清理 K 线数据中的重复记录（16:00:00 UTC 时间戳）

执行步骤：
1. 查询所有 time.hour = 16 的日线记录
2. 检查是否存在对应的 00:00:00 UTC 记录
3. 如果存在，删除 16:00:00 UTC 记录
4. 如果不存在，将 16:00:00 UTC 记录的时间戳更新为 00:00:00 UTC

使用方式：
    python scripts/cleanup_duplicate_kline.py --dry-run  # 预览模式
    python scripts/cleanup_duplicate_kline.py --execute  # 执行清理

需求: 2.2
"""

import asyncio
import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionTS


async def find_duplicates(
    session: AsyncSession, 
    batch_size: int = 10000,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    查找所有 16:00:00 UTC 时间戳的日线记录。
    
    返回统计信息：
    - total_16h_records: 16:00:00 UTC 日线记录总数
    - to_delete: 有对应 00:00:00 UTC 记录的数量（需要删除）
    - to_update: 无对应 00:00:00 UTC 记录的数量（需要更新时间戳）
    
    Args:
        session: TimescaleDB 异步会话
        batch_size: 批处理大小（用于统计）
        start_date: 开始日期 (YYYY-MM-DD)，用于分批处理
        end_date: 结束日期 (YYYY-MM-DD)，用于分批处理
    
    Returns:
        包含统计信息的字典
    """
    print("\n" + "=" * 80)
    print("查找重复数据...")
    if start_date or end_date:
        print(f"日期范围: {start_date or '最早'} 到 {end_date or '最新'}")
    print("=" * 80)
    
    # 构建日期范围条件
    date_condition = ""
    params = {}
    if start_date:
        date_condition += " AND time >= :start_date"
        params["start_date"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_date:
        date_condition += " AND time < :end_date"
        params["end_date"] = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    # 统计 16:00:00 UTC 日线记录总数
    count_total_sql = text(f"""
        SELECT COUNT(*) as total
        FROM kline
        WHERE freq = '1d'
          AND EXTRACT(HOUR FROM time) = 16
          AND EXTRACT(MINUTE FROM time) = 0
          AND EXTRACT(SECOND FROM time) = 0
          {date_condition}
    """)
    result = await session.execute(count_total_sql, params)
    total_16h_records = result.scalar() or 0
    print(f"\n16:00:00 UTC 日线记录总数: {total_16h_records:,}")
    
    if total_16h_records == 0:
        print("未发现重复数据，无需清理。")
        return {
            "total_16h_records": 0,
            "to_delete": 0,
            "to_update": 0,
        }
    
    # 统计需要删除的记录（有对应的 00:00:00 UTC 记录）
    count_delete_sql = text(f"""
        SELECT COUNT(*) as total
        FROM kline k1
        WHERE k1.freq = '1d'
          AND EXTRACT(HOUR FROM k1.time) = 16
          AND EXTRACT(MINUTE FROM k1.time) = 0
          AND EXTRACT(SECOND FROM k1.time) = 0
          {date_condition}
          AND EXISTS (
            SELECT 1
            FROM kline k2
            WHERE k2.symbol = k1.symbol
              AND k2.freq = k1.freq
              AND k2.adj_type = k1.adj_type
              AND k2.time = k1.time - INTERVAL '16 hours'
          )
    """)
    result = await session.execute(count_delete_sql, params)
    to_delete = result.scalar() or 0
    print(f"需要删除的记录（有对应 00:00:00 UTC）: {to_delete:,}")
    
    # 统计需要更新的记录（无对应的 00:00:00 UTC 记录）
    count_update_sql = text(f"""
        SELECT COUNT(*) as total
        FROM kline k1
        WHERE k1.freq = '1d'
          AND EXTRACT(HOUR FROM k1.time) = 16
          AND EXTRACT(MINUTE FROM k1.time) = 0
          AND EXTRACT(SECOND FROM k1.time) = 0
          {date_condition}
          AND NOT EXISTS (
            SELECT 1
            FROM kline k2
            WHERE k2.symbol = k1.symbol
              AND k2.freq = k1.freq
              AND k2.adj_type = k1.adj_type
              AND k2.time = k1.time - INTERVAL '16 hours'
          )
    """)
    result = await session.execute(count_update_sql, params)
    to_update = result.scalar() or 0
    print(f"需要更新的记录（无对应 00:00:00 UTC）: {to_update:,}")
    
    # 抽样显示重复数据示例
    print("\n重复数据示例（前 10 条）:")
    sample_date_condition = ""
    sample_params = {}
    if start_date:
        sample_date_condition += " AND k1.time >= :start_date"
        sample_params["start_date"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_date:
        sample_date_condition += " AND k1.time < :end_date"
        sample_params["end_date"] = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    sample_sql = text(f"""
        SELECT k1.time, k1.symbol, k1.freq, k1.adj_type, k1.close,
               k2.time as correct_time, k2.close as correct_close
        FROM kline k1
        LEFT JOIN kline k2
          ON k2.symbol = k1.symbol
          AND k2.freq = k1.freq
          AND k2.adj_type = k1.adj_type
          AND k2.time = k1.time - INTERVAL '16 hours'
        WHERE k1.freq = '1d'
          AND EXTRACT(HOUR FROM k1.time) = 16
          AND EXTRACT(MINUTE FROM k1.time) = 0
          AND EXTRACT(SECOND FROM k1.time) = 0
          {sample_date_condition}
        LIMIT 10
    """)
    result = await session.execute(sample_sql, sample_params)
    samples = result.fetchall()
    
    for row in samples:
        time_16h, symbol, freq, adj_type, close_16h, correct_time, correct_close = row
        if correct_time:
            print(f"  {symbol} {freq} adj={adj_type}: {time_16h} (close={close_16h}) -> 存在正确记录 {correct_time}")
        else:
            print(f"  {symbol} {freq} adj={adj_type}: {time_16h} (close={close_16h}) -> 需要更新时间戳")
    
    return {
        "total_16h_records": total_16h_records,
        "to_delete": to_delete,
        "to_update": to_update,
    }


async def cleanup_duplicates(
    dry_run: bool = True,
    batch_size: int = 10000,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """
    清理重复的 K 线数据。
    
    Args:
        dry_run: 预览模式，不实际执行删除/更新
        batch_size: 批处理大小
        start_date: 开始日期 (YYYY-MM-DD)，用于分批处理
        end_date: 结束日期 (YYYY-MM-DD)，用于分批处理
    
    Returns:
        包含清理结果的字典
    """
    start_time = datetime.now()
    
    print("\n" + "=" * 80)
    print(f"K 线数据重复清理脚本 - {'预览模式' if dry_run else '执行模式'}")
    if start_date or end_date:
        print(f"日期范围: {start_date or '最早'} 到 {end_date or '最新'}")
    print("=" * 80)
    print(f"批处理大小: {batch_size:,}")
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with AsyncSessionTS() as session:
        # 步骤 1: 查找重复数据
        stats = await find_duplicates(session, batch_size, start_date, end_date)
        
        if stats["total_16h_records"] == 0:
            return {
                "status": "success",
                "dry_run": dry_run,
                "stats": stats,
                "deleted": 0,
                "updated": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }
        
        if dry_run:
            print("\n" + "-" * 80)
            print("预览模式 - 不执行实际操作")
            print("-" * 80)
            print(f"\n计划操作:")
            print(f"  - 删除记录: {stats['to_delete']:,} 条")
            print(f"  - 更新记录: {stats['to_update']:,} 条")
            print(f"\n要执行清理，请运行:")
            print(f"  python scripts/cleanup_duplicate_kline.py --execute")
            
            return {
                "status": "dry_run",
                "dry_run": True,
                "stats": stats,
                "deleted": 0,
                "updated": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }
        
        # 步骤 2: 执行删除操作（分批处理）
        print("\n" + "-" * 80)
        print("执行删除操作...")
        print("-" * 80)
        
        # 构建日期范围条件
        date_condition = ""
        params = {}
        if start_date:
            date_condition += " AND k1.time >= :start_date"
            params["start_date"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_date:
            date_condition += " AND k1.time < :end_date"
            params["end_date"] = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        deleted_total = 0
        batch_num = 0
        
        while True:
            batch_num += 1
            # 使用 CTE 和 DELETE ... USING 语法进行批量删除
            delete_sql = text(f"""
                WITH to_delete AS (
                    SELECT k1.time, k1.symbol, k1.freq, k1.adj_type
                    FROM kline k1
                    WHERE k1.freq = '1d'
                      AND EXTRACT(HOUR FROM k1.time) = 16
                      AND EXTRACT(MINUTE FROM k1.time) = 0
                      AND EXTRACT(SECOND FROM k1.time) = 0
                      {date_condition}
                      AND EXISTS (
                        SELECT 1
                        FROM kline k2
                        WHERE k2.symbol = k1.symbol
                          AND k2.freq = k1.freq
                          AND k2.adj_type = k1.adj_type
                          AND k2.time = k1.time - INTERVAL '16 hours'
                      )
                    LIMIT {batch_size}
                )
                DELETE FROM kline
                WHERE (time, symbol, freq, adj_type) IN (SELECT time, symbol, freq, adj_type FROM to_delete)
            """)
            
            result = await session.execute(delete_sql, params)
            deleted_count = result.rowcount
            deleted_total += deleted_count
            
            if deleted_count > 0:
                await session.commit()
                print(f"  批次 {batch_num}: 删除 {deleted_count:,} 条记录，累计 {deleted_total:,} 条")
            
            # 如果删除数量小于批处理大小，说明已经处理完毕
            if deleted_count < batch_size:
                break
        
        print(f"\n删除完成: 共删除 {deleted_total:,} 条记录")
        
        # 步骤 3: 执行更新操作（分批处理）
        print("\n" + "-" * 80)
        print("执行更新操作...")
        print("-" * 80)
        
        updated_total = 0
        batch_num = 0
        
        while True:
            batch_num += 1
            # 更新无对应记录的 16:00:00 UTC 时间戳为 00:00:00 UTC
            update_sql = text(f"""
                WITH to_update AS (
                    SELECT k1.time, k1.symbol, k1.freq, k1.adj_type
                    FROM kline k1
                    WHERE k1.freq = '1d'
                      AND EXTRACT(HOUR FROM k1.time) = 16
                      AND EXTRACT(MINUTE FROM k1.time) = 0
                      AND EXTRACT(SECOND FROM k1.time) = 0
                      {date_condition}
                      AND NOT EXISTS (
                        SELECT 1
                        FROM kline k2
                        WHERE k2.symbol = k1.symbol
                          AND k2.freq = k1.freq
                          AND k2.adj_type = k1.adj_type
                          AND k2.time = k1.time - INTERVAL '16 hours'
                      )
                    LIMIT {batch_size}
                )
                UPDATE kline
                SET time = time - INTERVAL '16 hours'
                WHERE (time, symbol, freq, adj_type) IN (SELECT time, symbol, freq, adj_type FROM to_update)
            """)
            
            result = await session.execute(update_sql, params)
            updated_count = result.rowcount
            updated_total += updated_count
            
            if updated_count > 0:
                await session.commit()
                print(f"  批次 {batch_num}: 更新 {updated_count:,} 条记录，累计 {updated_total:,} 条")
            
            # 如果更新数量小于批处理大小，说明已经处理完毕
            if updated_count < batch_size:
                break
        
        print(f"\n更新完成: 共更新 {updated_total:,} 条记录")
        
        # 步骤 4: 验证清理结果
        print("\n" + "-" * 80)
        print("验证清理结果...")
        print("-" * 80)
        
        verify_date_condition = ""
        verify_params = {}
        if start_date:
            verify_date_condition += " AND time >= :start_date"
            verify_params["start_date"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_date:
            verify_date_condition += " AND time < :end_date"
            verify_params["end_date"] = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        verify_sql = text(f"""
            SELECT COUNT(*) as remaining
            FROM kline
            WHERE freq = '1d'
              AND EXTRACT(HOUR FROM time) = 16
              AND EXTRACT(MINUTE FROM time) = 0
              AND EXTRACT(SECOND FROM time) = 0
              {verify_date_condition}
        """)
        result = await session.execute(verify_sql, verify_params)
        remaining = result.scalar() or 0
        
        if remaining == 0:
            print("验证通过: 所有 16:00:00 UTC 日线记录已清理完毕")
        else:
            print(f"警告: 仍有 {remaining:,} 条 16:00:00 UTC 日线记录未清理")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 打印摘要报告
        print("\n" + "=" * 80)
        print("清理摘要报告")
        print("=" * 80)
        print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"耗时: {duration:.2f} 秒")
        print(f"\n原始统计:")
        print(f"  - 16:00:00 UTC 日线记录: {stats['total_16h_records']:,} 条")
        print(f"  - 需要删除: {stats['to_delete']:,} 条")
        print(f"  - 需要更新: {stats['to_update']:,} 条")
        print(f"\n实际操作:")
        print(f"  - 已删除: {deleted_total:,} 条")
        print(f"  - 已更新: {updated_total:,} 条")
        print(f"  - 剩余未清理: {remaining:,} 条")
        print("=" * 80)
        
        return {
            "status": "success",
            "dry_run": False,
            "stats": stats,
            "deleted": deleted_total,
            "updated": updated_total,
            "remaining": remaining,
            "duration_seconds": duration,
        }


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="清理 K 线重复数据（16:00:00 UTC 时间戳）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/cleanup_duplicate_kline.py --dry-run     # 预览模式，查看将要清理的数据
  python scripts/cleanup_duplicate_kline.py --execute     # 执行清理
  python scripts/cleanup_duplicate_kline.py --dry-run --start-date 2024-01-01 --end-date 2024-02-01  # 指定日期范围
  python scripts/cleanup_duplicate_kline.py --execute --batch-size 5000  # 自定义批处理大小
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="预览模式，不实际删除或更新数据（默认）",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行清理（覆盖 --dry-run）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="批处理大小，默认 10000",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="开始日期 (YYYY-MM-DD)，用于分批处理",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="结束日期 (YYYY-MM-DD)，用于分批处理",
    )
    args = parser.parse_args()
    
    # 如果指定 --execute，则关闭 dry_run
    dry_run = not args.execute
    
    try:
        result = await cleanup_duplicates(
            dry_run=dry_run, 
            batch_size=args.batch_size,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        
        if result["status"] == "success":
            print("\n清理完成！")
        elif result["status"] == "dry_run":
            print("\n预览完成！使用 --execute 参数执行实际清理。")
        
        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
