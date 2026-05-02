#!/usr/bin/env python
"""K 线重复交易日专项审计入口。

复用 Tushare 时序偏移修复脚本的 dry-run 诊断，统一输出候选、
冲突、本地交易日重复和 OHLCV 差异样例。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.repair_tushare_timeseries_timezone import main as repair_main


if __name__ == "__main__":
    if "--table" not in sys.argv:
        sys.argv.extend(["--table", "kline"])
    if "--dry-run" not in sys.argv and "--execute" not in sys.argv:
        sys.argv.append("--dry-run")
    raise SystemExit(asyncio.run(repair_main()))
