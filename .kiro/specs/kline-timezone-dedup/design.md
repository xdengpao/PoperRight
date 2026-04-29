# K线数据时区处理与重复数据清理设计文档

## Overview

修复 K 线数据导入时因时区处理不一致导致的重复存储问题。问题根源在于 `_parse_datetime`（本地 CSV 导入）和 `_parse_trade_date`（Tushare API 导入）函数创建 naive datetime 对象，存入 TimescaleDB 时被解释为 UTC 时间，但不同数据源对日期字符串的时区假设不同，导致同一交易日产生 `00:00:00 UTC` 和 `16:00:00 UTC` 两个时间戳。

修复策略：
1. 统一时区处理：所有日线数据使用 `00:00:00 UTC` 时间戳
2. 清理历史重复数据：删除 `16:00:00 UTC` 时间戳的记录
3. 标准化导入流程：修改日期解析函数，明确使用 UTC 时区

## Glossary

- **Bug_Condition (C)**: K 线数据导入时，同一交易日因时区处理不一致被存储为两个不同的时间戳（`00:00:00 UTC` 和 `16:00:00 UTC`）
- **Property (P)**: 日线数据统一使用 `00:00:00 UTC` 时间戳存储，确保唯一约束正确生效
- **Preservation**: 现有查询、批量写入、分钟级数据处理功能保持不变
- **KlineBar**: K 线数据传输对象，包含 time、symbol、freq、OHLCV 等字段
- **TimescaleDB**: 时序数据库，存储 K 线超表，使用 TIMESTAMPTZ 类型
- **Naive datetime**: 无时区信息的 datetime 对象，存入数据库时被解释为 UTC

## Bug Details

### Bug Condition

K 线数据导入时，`_parse_datetime` 和 `_parse_trade_date` 函数解析日期字符串创建 naive datetime 对象。由于不同数据源对日期的时区假设不同：
- 本地 CSV 导入：日期字符串如 `2024-01-15` 被解析为 `datetime(2024, 1, 15, 0, 0, 0)`，存入数据库后为 `2024-01-15 00:00:00 UTC`
- Tushare API 导入：交易日期 `20240115` 被解析为 `datetime(2024, 1, 15, 0, 0, 0)`，但部分历史数据可能被错误地存储为 `2024-01-15 16:00:00 UTC`（对应北京时间 2024-01-16 00:00:00）

**Formal Specification:**
```
FUNCTION isBugCondition(record)
  INPUT: record of type Kline
  OUTPUT: boolean
  
  RETURN record.time.hour = 16
         AND record.time.minute = 0
         AND record.time.second = 0
         AND record.freq = '1d'
         AND EXISTS another record with same (symbol, freq, adj_type)
              AND another.time = record.time - 16 hours (i.e., 00:00:00 UTC same day)
END FUNCTION
```

### Examples

- **示例 1**: 股票 `000001.SZ` 在 `2024-01-15` 有两条日线记录：
  - `time = 2024-01-15 00:00:00 UTC`，close = 10.50
  - `time = 2024-01-15 16:00:00 UTC`，close = 10.50
  - 前端查询时显示两条重复记录

- **示例 2**: 股票 `600000.SH` 在 `2024-01-15` 仅有一条记录：
  - `time = 2024-01-15 00:00:00 UTC`，close = 12.30
  - 正常情况，无重复

- **示例 3**: 分钟级 K 线数据 `000001.SZ` 频率 `5m`：
  - `time = 2024-01-15 09:30:00 UTC`，包含完整时间戳
  - 分钟数据不受此 bug 影响，因为时间戳已包含具体时间

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 查询 K 线数据时，按时间范围、股票代码、频率、复权类型正确返回数据
- 批量写入 K 线数据时，使用 `ON CONFLICT DO NOTHING` 保证幂等性
- 分钟级 K 线数据导入时，正确处理带时间戳的分钟数据
- 前端展示 K 线图表时，按交易日正确渲染

**Scope:**
所有非日线数据（分钟级 K 线）和已正确存储的日线数据（`00:00:00 UTC` 时间戳）不受影响。修复仅针对：
- 新导入的日线数据，确保时间戳标准化
- 历史重复数据，清理 `16:00:00 UTC` 时间戳的记录

## Hypothesized Root Cause

基于代码分析和数据检查，问题根源如下：

1. **Naive datetime 时区歧义**:
   - `_parse_datetime` 函数（`local_kline_import.py` 第 587-605 行）解析日期字符串时创建 naive datetime
   - `_parse_trade_date` 函数（`tushare_adapter.py` 第 187-196 行）同样创建 naive datetime
   - 存入 TimescaleDB 时，naive datetime 被解释为 UTC 时间

2. **历史数据导入时区假设不一致**:
   - 部分数据源可能将日期字符串解释为北京时间（UTC+8），导致 `2024-01-15` 被存储为 `2024-01-15 16:00:00 UTC`（对应北京时间 2024-01-16 00:00:00）
   - 其他数据源将日期字符串解释为 UTC，存储为 `2024-01-15 00:00:00 UTC`

3. **唯一约束未覆盖时间戳差异**:
   - 唯一约束 `uq_kline_time_symbol_freq_adj` 基于 `(time, symbol, freq, adj_type)`
   - 时间戳差异导致同一交易日数据被存储为两条记录

## Correctness Properties

Property 1: Bug Condition - 日线数据时间戳标准化

_For any_ 日线 K 线数据导入操作，系统 SHALL 将日期字符串解析为 `00:00:00 UTC` 时间戳，确保同一交易日数据在唯一约束下正确去重。

**Validates: Requirements 2.1, 2.3, 2.4**

Property 2: Preservation - 非日线数据保持不变

_For any_ 分钟级 K 线数据导入操作，系统 SHALL 保持原有时间戳处理逻辑不变，确保分钟级数据的时间精度不受影响。

**Validates: Requirements 3.3**

Property 3: Preservation - 查询和写入功能保持不变

_For any_ K 线数据查询和批量写入操作，系统 SHALL 保持现有行为不变，包括查询条件、排序、`ON CONFLICT DO NOTHING` 幂等性保证。

**Validates: Requirements 3.1, 3.2**

## Fix Implementation

### Changes Required

**文件 1**: `app/services/data_engine/local_kline_import.py`

**函数**: `_parse_datetime`（静态方法）

**修改内容**:
```python
# 修改前（第 587-605 行）
@staticmethod
def _parse_datetime(time_str: str) -> datetime:
    """尝试多种格式解析时间字符串。"""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y%m%d %H:%M:%S",
        "%Y%m%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间: {time_str}")

# 修改后
@staticmethod
def _parse_datetime(time_str: str) -> datetime:
    """尝试多种格式解析时间字符串，返回 UTC 时区的 datetime 对象。
    
    对于日线数据（仅日期格式），统一使用 00:00:00 UTC 时间戳。
    对于分钟级数据（带时间格式），保持原有时间戳，但明确标记为 UTC。
    """
    from datetime import timezone
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y%m%d %H:%M:%S",
        "%Y%m%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            # 明确标记为 UTC 时区
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间: {time_str}")
```

**文件 2**: `app/services/data_engine/tushare_adapter.py`

**函数**: `_parse_trade_date`（静态方法）

**修改内容**:
```python
# 修改前（第 187-196 行）
@staticmethod
def _parse_trade_date(value: Any) -> datetime:
    """解析 Tushare 日期字符串 (YYYYMMDD) 为 datetime。"""
    if value is None:
        return datetime.utcnow()
    s = str(value).strip()
    try:
        return datetime.strptime(s[:8], "%Y%m%d")
    except ValueError:
        return datetime.utcnow()

# 修改后
@staticmethod
def _parse_trade_date(value: Any) -> datetime:
    """解析 Tushare 日期字符串 (YYYYMMDD) 为 UTC 时区的 datetime。
    
    日线数据统一使用 00:00:00 UTC 时间戳存储。
    """
    from datetime import timezone
    
    if value is None:
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    s = str(value).strip()
    try:
        dt = datetime.strptime(s[:8], "%Y%m%d")
        # 明确标记为 UTC 时区，时间设为 00:00:00
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
```

**文件 3**: `app/services/data_engine/market_adapter.py`

**函数**: `_parse_kline_response`（静态方法）

**修改内容**:
```python
# 修改前（第 125-133 行）
# 时间字段：支持 ISO 字符串或 Unix 时间戳（毫秒）
raw_time = item.get("time") or item.get("datetime") or item.get("ts")
if isinstance(raw_time, (int, float)):
    ts = raw_time / 1000 if raw_time > 1e10 else raw_time
    bar_time = datetime.utcfromtimestamp(ts)
else:
    bar_time = datetime.fromisoformat(str(raw_time))

# 修改后
from datetime import timezone

# 时间字段：支持 ISO 字符串或 Unix 时间戳（毫秒）
raw_time = item.get("time") or item.get("datetime") or item.get("ts")
if isinstance(raw_time, (int, float)):
    ts = raw_time / 1000 if raw_time > 1e10 else raw_time
    bar_time = datetime.fromtimestamp(ts, tz=timezone.utc)
else:
    bar_time = datetime.fromisoformat(str(raw_time))
    # 如果解析结果无时区信息，假设为 UTC
    if bar_time.tzinfo is None:
        bar_time = bar_time.replace(tzinfo=timezone.utc)
```

### 数据清理脚本

创建独立的清理脚本 `scripts/cleanup_duplicate_kline.py`，用于删除历史重复数据：

```python
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
"""

import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionTS
from app.models.kline import Kline


async def find_duplicates(session: AsyncSession, batch_size: int = 10000) -> list[dict]:
    """查找所有 16:00:00 UTC 时间戳的日线记录。"""
    # 查询 time.hour = 16 且 freq = '1d' 的记录
    stmt = select(Kline).where(
        and_(
            Kline.freq == '1d',
            # 使用 PostgreSQL 的 EXTRACT 函数筛选 hour = 16
            # 这里需要原生 SQL，暂用时间范围筛选
        )
    )
    # 实际实现需要使用原生 SQL 或 SQLAlchemy 的 func.extract
    pass


async def cleanup_duplicates(dry_run: bool = True, batch_size: int = 10000) -> dict:
    """清理重复的 K 线数据。"""
    pass


async def main():
    parser = argparse.ArgumentParser(description="清理 K 线重复数据")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际删除")
    parser.add_argument("--execute", action="store_true", help="执行清理")
    parser.add_argument("--batch-size", type=int, default=10000, help="批处理大小")
    args = parser.parse_args()
    
    if args.execute:
        result = await cleanup_duplicates(dry_run=False, batch_size=args.batch_size)
    else:
        result = await cleanup_duplicates(dry_run=True, batch_size=args.batch_size)
    
    print(f"清理结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 数据清理 SQL 策略

由于数据量较大（4.5 亿条记录，396,675 组重复），建议使用原生 SQL 分批处理：

```sql
-- 步骤 1：创建临时表存储需要删除的记录 ID
CREATE TEMP TABLE duplicate_kline_ids AS
SELECT time, symbol, freq, adj_type
FROM kline
WHERE freq = '1d'
  AND EXTRACT(HOUR FROM time) = 16
  AND EXISTS (
    SELECT 1 FROM kline k2
    WHERE k2.symbol = kline.symbol
      AND k2.freq = kline.freq
      AND k2.adj_type = kline.adj_type
      AND k2.time = kline.time - INTERVAL '16 hours'
  );

-- 步骤 2：分批删除（每批 10,000 条）
DELETE FROM kline
WHERE (time, symbol, freq, adj_type) IN (
  SELECT time, symbol, freq, adj_type FROM duplicate_kline_ids LIMIT 10000
);

-- 步骤 3：更新无对应记录的 16:00:00 UTC 时间戳为 00:00:00 UTC
UPDATE kline
SET time = time - INTERVAL '16 hours'
WHERE freq = '1d'
  AND EXTRACT(HOUR FROM time) = 16
  AND NOT EXISTS (
    SELECT 1 FROM kline k2
    WHERE k2.symbol = kline.symbol
      AND k2.freq = kline.freq
      AND k2.adj_type = kline.adj_type
      AND k2.time = kline.time - INTERVAL '16 hours'
  );
```

## Testing Strategy

### Validation Approach

测试策略分为三个阶段：
1. **探索性测试**：在修复前验证 bug 存在，确认根因分析正确
2. **修复验证**：验证修复后日线数据时间戳标准化为 `00:00:00 UTC`
3. **保留性测试**：验证非日线数据和现有功能不受影响

### Exploratory Bug Condition Checking

**Goal**: 在修复前验证 bug 存在，确认根因分析正确。

**Test Plan**: 编写测试用例，模拟不同数据源导入日线数据，检查时间戳是否一致。

**Test Cases**:
1. **本地 CSV 导入测试**: 解析日期字符串 `2024-01-15`，验证返回的 datetime 对象是否为 `2024-01-15 00:00:00 UTC`
2. **Tushare API 导入测试**: 解析交易日期 `20240115`，验证返回的 datetime 对象是否为 `2024-01-15 00:00:00 UTC`
3. **数据库查询测试**: 查询存在重复的股票代码，验证返回两条记录
4. **时间戳差异测试**: 验证两条记录的时间戳差异为 16 小时

**Expected Counterexamples**:
- 修复前，`_parse_datetime("2024-01-15")` 返回 naive datetime，存入数据库后被解释为 UTC
- 修复前，数据库中存在 `time.hour = 16` 的日线记录

### Fix Checking

**Goal**: 验证修复后日线数据时间戳标准化为 `00:00:00 UTC`。

**Pseudocode:**
```
FOR ALL input WHERE isDailyKline(input) DO
  result := _parse_datetime(input.date_string)
  ASSERT result.hour = 0
  ASSERT result.minute = 0
  ASSERT result.second = 0
  ASSERT result.tzinfo = timezone.utc
END FOR
```

**Test Cases**:
1. **本地 CSV 导入修复验证**: 调用修改后的 `_parse_datetime`，验证返回的 datetime 对象包含 UTC 时区信息
2. **Tushare API 导入修复验证**: 调用修改后的 `_parse_trade_date`，验证返回的 datetime 对象包含 UTC 时区信息
3. **Market Adapter 修复验证**: 调用修改后的 `_parse_kline_response`，验证返回的 KlineBar 时间戳包含 UTC 时区信息
4. **数据库写入验证**: 导入日线数据后，查询数据库验证时间戳为 `00:00:00 UTC`

### Preservation Checking

**Goal**: 验证非日线数据和现有功能不受影响。

**Pseudocode:**
```
FOR ALL input WHERE NOT isDailyKline(input) DO
  result_fixed := _parse_datetime_fixed(input.time_string)
  result_original := _parse_datetime_original(input.time_string)
  ASSERT result_fixed.time = result_original.time
END FOR
```

**Testing Approach**: 使用属性测试（Hypothesis）生成随机分钟级时间字符串，验证修复前后解析结果一致。

**Test Cases**:
1. **分钟级数据保留测试**: 解析 `2024-01-15 09:30:00` 格式字符串，验证时间戳保持不变
2. **查询功能保留测试**: 查询 K 线数据，验证返回结果与修复前一致
3. **批量写入保留测试**: 批量写入 K 线数据，验证 `ON CONFLICT DO NOTHING` 仍然生效
4. **前端显示保留测试**: 验证前端 K 线图表正确渲染，无重复显示

### Unit Tests

- 测试 `_parse_datetime` 函数解析各种日期格式，验证返回 UTC 时区的 datetime
- 测试 `_parse_trade_date` 函数解析 Tushare 日期格式，验证返回 UTC 时区的 datetime
- 测试 `_parse_kline_response` 函数解析行情 API 响应，验证时间戳处理正确
- 测试数据清理脚本，验证删除逻辑正确

### Property-Based Tests

- 生成随机日期字符串，验证 `_parse_datetime` 始终返回 `00:00:00 UTC` 时间戳
- 生成随机分钟级时间字符串，验证时间戳保持原有精度
- 生成随机 K 线数据，验证批量写入幂等性

### Integration Tests

- 测试完整的本地 CSV 导入流程，验证日线数据正确存储
- 测试完整的 Tushare API 导入流程，验证日线数据正确存储
- 测试数据清理脚本执行，验证重复数据被正确删除
- 测试前端 K 线图表显示，验证无重复记录
