#!/usr/bin/env python3
"""
批量清理 K 线数据中的重复记录（按月处理）

使用方式：
    python scripts/batch_cleanup_kline.py --start-year 2024 --end-year 2024
    python scripts/batch_cleanup_kline.py --start-year 2023 --end-year 2024
"""

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_cleanup(start_date: str, end_date: str) -> tuple[bool, dict]:
    """运行单月清理脚本"""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "cleanup_duplicate_kline.py"),
        "--execute",
        "--start-date", start_date,
        "--end-date", end_date,
    ]
    
    print(f"\n{'='*80}")
    print(f"处理: {start_date} 到 {end_date}")
    print(f"{'='*80}")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量清理 K 线重复数据（按月）")
    parser.add_argument("--start-year", type=int, required=True, help="开始年份")
    parser.add_argument("--end-year", type=int, required=True, help="结束年份")
    parser.add_argument("--start-month", type=int, default=1, help="开始月份（默认1月）")
    parser.add_argument("--end-month", type=int, default=12, help="结束月份（默认12月）")
    args = parser.parse_args()
    
    total_deleted = 0
    total_updated = 0
    failed_months = []
    
    for year in range(args.start_year, args.end_year + 1):
        start_month = args.start_month if year == args.start_year else 1
        end_month = args.end_month if year == args.end_year else 12
        
        for month in range(start_month, end_month + 1):
            start_date = f"{year}-{month:02d}-01"
            # 计算下个月的第一天
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            
            success = run_cleanup(start_date, end_date)
            if not success:
                failed_months.append(f"{year}-{month:02d}")
    
    print("\n" + "=" * 80)
    print("批量清理完成")
    print("=" * 80)
    if failed_months:
        print(f"失败的月份: {', '.join(failed_months)}")
    else:
        print("所有月份处理成功！")


if __name__ == "__main__":
    main()
