#!/usr/bin/env python
"""K 线重复交易日专项修复入口。

默认 dry-run；传入 --execute 后复用已验证的 16:00 UTC 残留归并逻辑。
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
    raise SystemExit(asyncio.run(repair_main()))
