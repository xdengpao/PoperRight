#!/usr/bin/env python3
"""
分析数据库中的重复数据详情
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import AsyncSessionPG, AsyncSessionTS


async def analyze_suspend_info():
    """分析 suspend_info 表的重复数据"""
    print("\n" + "=" * 80)
    print("分析 suspend_info 表（停复牌信息）的重复数据")
    print("=" * 80)
    
    async with AsyncSessionPG() as session:
        # 检查唯一约束定义
        check_constraint = text("""
            SELECT pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conname = 'uq_suspend_info' AND contype = 'u'
        """)
        result = await session.execute(check_constraint)
        constraint_def = result.scalar()
        print(f"\n唯一约束定义: {constraint_def}")
        
        # 检查重复数据的详细情况
        check_dup = text("""
            SELECT ts_code, suspend_date, COUNT(*) as dup_count
            FROM suspend_info
            GROUP BY ts_code, suspend_date
            HAVING COUNT(*) > 1
            ORDER BY dup_count DESC
            LIMIT 20
        """)
        result = await session.execute(check_dup)
        duplicates = result.fetchall()
        
        print(f"\n发现 {len(duplicates)} 组重复数据 (前20组):")
        for row in duplicates:
            print(f"  ts_code={row[0]}, suspend_date={row[1]}, 重复次数={row[2]}")
        
        # 查看具体的重复记录示例
        if duplicates:
            example_ts_code = duplicates[0][0]
            example_suspend_date = duplicates[0][1]
            
            print(f"\n示例: ts_code={example_ts_code}, suspend_date={example_suspend_date} 的重复记录:")
            check_example = text("""
                SELECT *
                FROM suspend_info
                WHERE ts_code = :ts_code
                ORDER BY id
                LIMIT 10
            """)
            result = await session.execute(check_example, {"ts_code": example_ts_code})
            examples = result.fetchall()
            for row in examples:
                print(f"  {row}")
        
        # 统计总重复记录数
        count_dup = text("""
            SELECT SUM(dup_count - 1) as extra_records
            FROM (
                SELECT COUNT(*) as dup_count
                FROM suspend_info
                GROUP BY ts_code, suspend_date
                HAVING COUNT(*) > 1
            ) subq
        """)
        result = await session.execute(count_dup)
        extra_records = result.scalar()
        print(f"\n总重复记录数（需要删除）: {extra_records}")


async def analyze_stk_managers():
    """分析 stk_managers 表的重复数据"""
    print("\n" + "=" * 80)
    print("分析 stk_managers 表（上市公司管理层）的重复数据")
    print("=" * 80)
    
    async with AsyncSessionPG() as session:
        # 检查唯一约束定义
        check_constraint = text("""
            SELECT pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conname = 'uq_stk_managers' AND contype = 'u'
        """)
        result = await session.execute(check_constraint)
        constraint_def = result.scalar()
        print(f"\n唯一约束定义: {constraint_def}")
        
        # 检查重复数据的详细情况
        check_dup = text("""
            SELECT ts_code, name, begin_date, COUNT(*) as dup_count
            FROM stk_managers
            GROUP BY ts_code, name, begin_date
            HAVING COUNT(*) > 1
            ORDER BY dup_count DESC
            LIMIT 20
        """)
        result = await session.execute(check_dup)
        duplicates = result.fetchall()
        
        print(f"\n发现 {len(duplicates)} 组重复数据 (前20组):")
        for row in duplicates:
            print(f"  ts_code={row[0]}, name={row[1]}, begin_date={row[2]}, 重复次数={row[3]}")
        
        # 查看具体的重复记录示例
        if duplicates:
            example_ts_code = duplicates[0][0]
            example_name = duplicates[0][1]
            example_begin_date = duplicates[0][2]
            
            print(f"\n示例: ts_code={example_ts_code}, name={example_name}, begin_date={example_begin_date} 的重复记录:")
            check_example = text("""
                SELECT *
                FROM stk_managers
                WHERE ts_code = :ts_code AND name = :name AND begin_date = :begin_date
                ORDER BY id
            """)
            result = await session.execute(check_example, {
                "ts_code": example_ts_code,
                "name": example_name,
                "begin_date": example_begin_date
            })
            examples = result.fetchall()
            for row in examples:
                print(f"  {row}")
        
        # 统计总重复记录数
        count_dup = text("""
            SELECT SUM(dup_count - 1) as extra_records
            FROM (
                SELECT COUNT(*) as dup_count
                FROM stk_managers
                GROUP BY ts_code, name, begin_date
                HAVING COUNT(*) > 1
            ) subq
        """)
        result = await session.execute(count_dup)
        extra_records = result.scalar()
        print(f"\n总重复记录数（需要删除）: {extra_records}")


async def analyze_kline_sample():
    """抽样分析 kline 表的重复数据"""
    print("\n" + "=" * 80)
    print("抽样分析 kline 表（K线数据）的重复数据")
    print("=" * 80)
    
    async with AsyncSessionTS() as session:
        # 检查唯一约束定义
        check_constraint = text("""
            SELECT pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conname = 'uq_kline_time_symbol_freq_adj' AND contype = 'u'
        """)
        result = await session.execute(check_constraint)
        constraint_def = result.scalar()
        print(f"\n唯一约束定义: {constraint_def}")
        
        # 抽样检查 - 随机选择几个股票代码
        print("\n抽样检查几个股票的重复情况...")
        
        # 获取几个常见的股票代码
        get_symbols = text("""
            SELECT DISTINCT symbol 
            FROM kline 
            WHERE freq = '1d' 
            LIMIT 10
        """)
        result = await session.execute(get_symbols)
        symbols = [row[0] for row in result.fetchall()]
        
        for symbol in symbols:
            check_dup = text(f"""
                SELECT time, symbol, freq, adj_type, COUNT(*) as dup_count
                FROM kline
                WHERE symbol = :symbol
                GROUP BY time, symbol, freq, adj_type
                HAVING COUNT(*) > 1
                LIMIT 5
            """)
            result = await session.execute(check_dup, {"symbol": symbol})
            duplicates = result.fetchall()
            
            if duplicates:
                print(f"\n  股票 {symbol} 发现重复:")
                for row in duplicates:
                    print(f"    time={row[0]}, freq={row[2]}, adj_type={row[3]}, 重复次数={row[4]}")
            else:
                print(f"  股票 {symbol}: 无重复")


async def check_constraint_vs_model():
    """检查 ORM 模型定义与数据库约束的一致性"""
    print("\n" + "=" * 80)
    print("检查 ORM 模型定义与数据库约束的一致性")
    print("=" * 80)
    
    # suspend_info 表的 ORM 定义
    print("\nsuspend_info 表:")
    print("  ORM 模型定义: 无 UniqueConstraint（只有 id 自增主键）")
    print("  数据库约束: uq_suspend_info (ts_code, suspend_date)")
    print("  问题: 迁移文件添加了约束，但 ORM 模型未定义")
    
    print("\nstk_managers 表:")
    print("  ORM 模型定义: 无 UniqueConstraint（只有 id 自增主键）")
    print("  数据库约束: uq_stk_managers (ts_code, name, begin_date)")
    print("  问题: 迁移文件添加了约束，但 ORM 模型未定义")


async def main():
    """主函数"""
    print("=" * 80)
    print("数据库重复数据详细分析脚本")
    print("=" * 80)
    
    await analyze_suspend_info()
    await analyze_stk_managers()
    await analyze_kline_sample()
    await check_constraint_vs_model()
    
    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
