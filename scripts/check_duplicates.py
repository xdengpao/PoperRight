#!/usr/bin/env python3
"""
检查数据库中的重复数据

检查以下表的重复情况：
1. K线数据 (kline) - TimescaleDB
2. 板块K线 (sector_kline) - TimescaleDB
3. Tushare 导入数据表 - PostgreSQL
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import AsyncSessionPG, AsyncSessionTS


async def check_pg_duplicates():
    """检查 PostgreSQL 业务数据表中的重复数据"""
    print("\n" + "=" * 80)
    print("PostgreSQL 业务数据表重复检查")
    print("=" * 80)
    
    # 定义要检查的表和唯一键列
    tables_to_check = [
        # (表名, 唯一键列列表, 唯一约束名)
        ("stock_st", ["ts_code", "trade_date"], "uq_stock_st_ts_code_trade_date"),
        ("st_warning", ["ts_code", "imp_date"], "uq_st_warning_ts_code_imp_date"),
        ("stk_limit", ["ts_code", "trade_date"], "uq_stk_limit_ts_code_trade_date"),
        ("hsgt_top10", ["trade_date", "ts_code", "market_type"], "uq_hsgt_top10_trade_date_ts_code_market_type"),
        ("ggt_top10", ["trade_date", "ts_code", "market_type"], "uq_ggt_top10_trade_date_ts_code_market_type"),
        ("ggt_daily", ["trade_date"], "uq_ggt_daily_trade_date"),
        ("financial_statement", ["ts_code", "end_date", "report_type"], "uq_financial_statement_ts_code_end_date_report_type"),
        ("forecast", ["ts_code", "end_date"], "uq_forecast_ts_code_end_date"),
        ("express", ["ts_code", "end_date"], "uq_express_ts_code_end_date"),
        ("disclosure_date", ["ts_code", "end_date"], "uq_disclosure_date_ts_code_end_date"),
        ("top_holders", ["ts_code", "end_date", "holder_name", "holder_type"], "uq_top_holders_ts_code_end_date_holder_name_holder_type"),
        ("pledge_stat", ["ts_code", "end_date"], "uq_pledge_stat_ts_code_end_date"),
        ("block_trade", ["ts_code", "trade_date", "buyer", "seller"], "uq_block_trade_ts_code_trade_date_buyer_seller"),
        ("stk_factor", ["ts_code", "trade_date"], "uq_stk_factor_ts_code_trade_date"),
        ("margin_data", ["trade_date", "exchange_id"], "uq_margin_data_trade_date_exchange_id"),
        ("margin_detail", ["ts_code", "trade_date"], "uq_margin_detail_ts_code_trade_date"),
        ("tushare_moneyflow", ["ts_code", "trade_date"], "uq_tushare_moneyflow_ts_code_trade_date"),
        ("moneyflow_ths", ["ts_code", "trade_date"], "uq_moneyflow_ths_ts_code_trade_date"),
        ("moneyflow_dc", ["ts_code", "trade_date"], "uq_moneyflow_dc_ts_code_trade_date"),
        ("moneyflow_hsgt", ["trade_date"], "uq_moneyflow_hsgt_trade_date"),
        ("moneyflow_mkt_dc", ["trade_date"], "uq_moneyflow_mkt_dc_trade_date"),
        ("top_list", ["trade_date", "ts_code", "reason"], "uq_top_list_trade_date_ts_code_reason"),
        ("top_inst", ["trade_date", "ts_code", "exalter"], "uq_top_inst_trade_date_ts_code_exalter"),
        # limit_list_ths 和 limit_list 的 limit 列是保留字，需要特殊处理
        ("limit_list_ths", ["ts_code", "trade_date", '"limit"'], "uq_limit_list_ths_ts_code_trade_date_limit"),
        ("limit_list", ["ts_code", "trade_date", '"limit"'], "uq_limit_list_ts_code_trade_date_limit"),
        ("limit_step", ["ts_code", "trade_date"], "uq_limit_step_ts_code_trade_date"),
        ("stk_auction", ["ts_code", "trade_date"], "uq_stk_auction_ts_code_trade_date"),
        ("index_weight", ["index_code", "con_code", "trade_date"], "uq_index_weight_index_code_con_code_trade_date"),
        ("index_dailybasic", ["ts_code", "trade_date"], "uq_index_dailybasic_ts_code_trade_date"),
        ("index_tech", ["ts_code", "trade_date"], "uq_index_tech_ts_code_trade_date"),
        ("index_global", ["ts_code", "trade_date"], "uq_index_global_ts_code_trade_date"),
        # 迁移文件中添加的约束
        ("suspend_info", ["ts_code", "suspend_date"], "uq_suspend_info"),
        ("dividend", ["ts_code", "end_date", "div_proc"], "uq_dividend"),
        ("stock_namechange", ["ts_code", "start_date"], "uq_stock_namechange"),
        ("stk_rewards", ["ts_code", "ann_date", "name"], "uq_stk_rewards"),
        ("stk_managers", ["ts_code", "name", "begin_date"], "uq_stk_managers"),
        ("stk_holdernumber", ["ts_code", "end_date"], "uq_stk_holdernumber"),
        ("stk_holdertrade", ["ts_code", "ann_date", "holder_name"], "uq_stk_holdertrade"),
        ("slb_len", ["ts_code", "trade_date"], "uq_slb_len"),
        ("hm_detail", ["trade_date", "ts_code", "hm_name"], "uq_hm_detail"),
        ("dc_hot", ["trade_date", "ts_code"], "uq_dc_hot"),
        ("ths_hot", ["trade_date", "ts_code"], "uq_ths_hot"),
        ("kpl_list", ["trade_date", "ts_code"], "uq_kpl_list"),
        ("moneyflow_ind", ["trade_date", "industry_name", "data_source"], "uq_moneyflow_ind"),
    ]
    
    duplicate_tables = []
    
    async with AsyncSessionPG() as session:
        for table_name, unique_cols, constraint_name in tables_to_check:
            try:
                # 检查表是否存在
                check_table = text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = :table_name
                    )
                """)
                result = await session.execute(check_table, {"table_name": table_name})
                if not result.scalar():
                    continue
                
                # 检查唯一约束是否存在
                check_constraint = text(f"""
                    SELECT COUNT(*) 
                    FROM pg_constraint 
                    WHERE conname = :constraint_name 
                    AND contype = 'u'
                """)
                result = await session.execute(check_constraint, {"constraint_name": constraint_name})
                constraint_exists = result.scalar() > 0
                
                # 检查重复数据
                cols_str = ", ".join(unique_cols)
                check_dup = text(f"""
                    SELECT {cols_str}, COUNT(*) as dup_count
                    FROM {table_name}
                    GROUP BY {cols_str}
                    HAVING COUNT(*) > 1
                    ORDER BY dup_count DESC
                    LIMIT 5
                """)
                result = await session.execute(check_dup)
                duplicates = result.fetchall()
                
                if duplicates:
                    print(f"\n  表 {table_name}:")
                    print(f"    唯一约束 '{constraint_name}': {'存在' if constraint_exists else '不存在'}")
                    print(f"    发现重复数据 (前5条):")
                    for row in duplicates:
                        print(f"      {row}")
                    duplicate_tables.append((table_name, len(duplicates)))
            except Exception as e:
                print(f"  表 {table_name}: 检查失败 - {e}")
                await session.rollback()
    
    return duplicate_tables


async def check_ts_duplicates():
    """检查 TimescaleDB 时序数据表中的重复数据"""
    print("\n" + "=" * 80)
    print("TimescaleDB 时序数据表重复检查")
    print("=" * 80)
    
    # K线数据表
    tables_to_check = [
        # (表名, 唯一键列列表, 唯一约束名)
        ("kline", ["time", "symbol", "freq", "adj_type"], "uq_kline_time_symbol_freq_adj"),
        ("sector_kline", ["time", "sector_code", "data_source", "freq"], "uq_sector_kline_time_code_source_freq"),
    ]
    
    duplicate_tables = []
    
    async with AsyncSessionTS() as session:
        for table_name, unique_cols, constraint_name in tables_to_check:
            try:
                # 检查表是否存在
                check_table = text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = :table_name
                    )
                """)
                result = await session.execute(check_table, {"table_name": table_name})
                if not result.scalar():
                    print(f"  表 {table_name}: 不存在，跳过")
                    continue
                
                # 检查唯一约束是否存在
                check_constraint = text(f"""
                    SELECT COUNT(*) 
                    FROM pg_constraint 
                    WHERE conname = :constraint_name 
                    AND contype = 'u'
                """)
                result = await session.execute(check_constraint, {"constraint_name": constraint_name})
                constraint_exists = result.scalar() > 0
                
                # 先检查总记录数
                count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                total_count = count_result.scalar()
                print(f"  表 {table_name}: 共 {total_count} 条记录")
                
                if total_count == 0:
                    continue
                
                # 检查重复数据 - 使用更高效的查询
                cols_str = ", ".join(unique_cols)
                check_dup = text(f"""
                    SELECT {cols_str}, COUNT(*) as dup_count
                    FROM {table_name}
                    GROUP BY {cols_str}
                    HAVING COUNT(*) > 1
                    ORDER BY dup_count DESC
                    LIMIT 10
                """)
                result = await session.execute(check_dup)
                duplicates = result.fetchall()
                
                if duplicates:
                    print(f"\n  表 {table_name}:")
                    print(f"    唯一约束 '{constraint_name}': {'存在' if constraint_exists else '不存在'}")
                    print(f"    发现重复数据 (前10条):")
                    for row in duplicates:
                        print(f"      {row}")
                    duplicate_tables.append((table_name, len(duplicates)))
            except Exception as e:
                print(f"  表 {table_name}: 检查失败 - {e}")
    
    return duplicate_tables


async def check_missing_constraints():
    """检查缺失的唯一约束"""
    print("\n" + "=" * 80)
    print("检查 ORM 模型定义了但数据库中缺失的唯一约束")
    print("=" * 80)
    
    # 从迁移文件中提取的约束
    migration_constraints = [
        ("stock_st", "uq_stock_st"),
        ("suspend_info", "uq_suspend_info"),
        ("dividend", "uq_dividend"),
        ("stock_namechange", "uq_stock_namechange"),
        ("hs_constituent", "uq_hs_constituent"),
        ("stk_rewards", "uq_stk_rewards"),
        ("stk_managers", "uq_stk_managers"),
        ("stk_holdernumber", "uq_stk_holdernumber"),
        ("stk_holdertrade", "uq_stk_holdertrade"),
        ("stk_account", "uq_stk_account"),
        ("margin_target", "uq_margin_target"),
        ("slb_len", "uq_slb_len"),
        ("slb_sec", "uq_slb_sec"),
        ("hm_list", "uq_hm_list"),
        ("hm_detail", "uq_hm_detail"),
        ("dc_hot", "uq_dc_hot"),
        ("ths_hot", "uq_ths_hot"),
        ("kpl_list", "uq_kpl_list"),
        ("moneyflow_ind", "uq_moneyflow_ind"),
    ]
    
    missing_constraints = []
    
    async with AsyncSessionPG() as session:
        for table_name, constraint_name in migration_constraints:
            try:
                # 检查表是否存在
                check_table = text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = :table_name
                    )
                """)
                result = await session.execute(check_table, {"table_name": table_name})
                if not result.scalar():
                    continue
                
                # 检查约束是否存在
                check_constraint = text(f"""
                    SELECT COUNT(*) 
                    FROM pg_constraint 
                    WHERE conname = :constraint_name 
                    AND contype = 'u'
                """)
                result = await session.execute(check_constraint, {"constraint_name": constraint_name})
                if result.scalar() == 0:
                    print(f"  表 {table_name}: 缺失约束 '{constraint_name}'")
                    missing_constraints.append((table_name, constraint_name))
            except Exception as e:
                print(f"  表 {table_name}: 检查失败 - {e}")
                await session.rollback()
    
    return missing_constraints


async def main():
    """主函数"""
    print("=" * 80)
    print("数据库重复数据检查脚本")
    print("=" * 80)
    
    pg_duplicates = await check_pg_duplicates()
    ts_duplicates = await check_ts_duplicates()
    missing_constraints = await check_missing_constraints()
    
    print("\n" + "=" * 80)
    print("检查结果汇总")
    print("=" * 80)
    
    if pg_duplicates:
        print(f"\nPostgreSQL 发现重复数据的表: {len(pg_duplicates)} 个")
        for table, count in pg_duplicates:
            print(f"  - {table}: {count} 组重复")
    else:
        print("\nPostgreSQL: 未发现重复数据")
    
    if ts_duplicates:
        print(f"\nTimescaleDB 发现重复数据的表: {len(ts_duplicates)} 个")
        for table, count in ts_duplicates:
            print(f"  - {table}: {count} 组重复")
    else:
        print("\nTimescaleDB: 未发现重复数据")
    
    if missing_constraints:
        print(f"\n缺失唯一约束的表: {len(missing_constraints)} 个")
        for table, constraint in missing_constraints:
            print(f"  - {table}: {constraint}")
    else:
        print("\n所有唯一约束均已创建")
    
    print("\n" + "=" * 80)
    print("检查完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
