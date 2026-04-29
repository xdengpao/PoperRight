# 交叉验证报告

## 验证日期
2026-04-29

## 验证范围
- bugfix.md（需求文档）
- design.md（设计文档）
- tasks.md（任务列表）
- 源码文件：
  - `app/services/data_engine/local_kline_import.py`
  - `app/services/data_engine/tushare_adapter.py`
  - `app/services/data_engine/market_adapter.py`

---

## 1. 源码验证

### 1.1 `_parse_datetime` 函数（local_kline_import.py）

**设计文档描述**：
- 位置：第 680-695 行
- 问题：创建 naive datetime 对象

**实际源码**：
```python
# 位置：第 587-605 行（实际行号与设计文档有偏差）
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
```

**验证结果**：✅ 确认问题存在
- 函数返回 naive datetime（无 `tzinfo` 参数）
- 设计文档行号有偏差（实际 587-605 行，设计文档写 680-695 行）

**修复建议**：更新设计文档行号

---

### 1.2 `_parse_trade_date` 函数（tushare_adapter.py）

**设计文档描述**：
- 位置：第 150-157 行
- 问题：创建 naive datetime 对象

**实际源码**：
```python
# 位置：第 187-196 行（实际行号与设计文档有偏差）
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
```

**验证结果**：✅ 确认问题存在
- 函数返回 naive datetime
- `datetime.utcnow()` 也返回 naive datetime
- 设计文档行号有偏差（实际 187-196 行，设计文档写 150-157 行）

**修复建议**：更新设计文档行号

---

### 1.3 `_parse_kline_response` 函数（market_adapter.py）

**设计文档描述**：
- 位置：第 95-100 行
- 问题：使用 `datetime.utcfromtimestamp(ts)` 返回 naive datetime

**实际源码**：
```python
# 位置：第 125-133 行（实际行号与设计文档有偏差）
# 时间字段：支持 ISO 字符串或 Unix 时间戳（毫秒）
raw_time = item.get("time") or item.get("datetime") or item.get("ts")
if isinstance(raw_time, (int, float)):
    ts = raw_time / 1000 if raw_time > 1e10 else raw_time
    bar_time = datetime.utcfromtimestamp(ts)
else:
    bar_time = datetime.fromisoformat(str(raw_time))
```

**验证结果**：✅ 确认问题存在
- `datetime.utcfromtimestamp(ts)` 返回 naive datetime
- `datetime.fromisoformat()` 也可能返回 naive datetime
- 设计文档行号有偏差（实际 125-133 行，设计文档写 95-100 行）

**修复建议**：更新设计文档行号

---

## 2. 需求文档验证

### 2.1 Current Behavior（缺陷行为）

| 需求 ID | 描述 | 源码验证 | 状态 |
|---------|------|----------|------|
| 1.1 | K线数据导入时使用不同的时区假设 | ✅ 确认：naive datetime 存入数据库被解释为 UTC | 通过 |
| 1.2 | 前端查询返回同一交易日的两条记录 | ✅ 确认：数据库中存在 00:00:00 和 16:00:00 两个时间戳 | 通过 |
| 1.3 | `_parse_datetime` 创建 naive datetime | ✅ 确认：函数无 tzinfo 参数 | 通过 |
| 1.4 | `_parse_trade_date` 创建 naive datetime | ✅ 确认：函数无 tzinfo 参数 | 通过 |

### 2.2 Expected Behavior（期望行为）

| 需求 ID | 描述 | 设计文档覆盖 | 状态 |
|---------|------|--------------|------|
| 2.1 | 统一使用 00:00:00 UTC 时间戳 | ✅ Property 1 | 通过 |
| 2.2 | 删除 16:00:00 UTC 记录 | ✅ 数据清理脚本 | 通过 |
| 2.3 | 标准化时间戳 | ✅ 修复方案 | 通过 |
| 2.4 | 明确使用 UTC 时区 | ✅ 修复方案 | 通过 |

### 2.3 Unchanged Behavior（保留行为）

| 需求 ID | 描述 | 设计文档覆盖 | 状态 |
|---------|------|--------------|------|
| 3.1 | 查询功能保持不变 | ✅ Property 3 | 通过 |
| 3.2 | 批量写入幂等性保持不变 | ✅ Property 3 | 通过 |
| 3.3 | 分钟级数据处理保持不变 | ✅ Property 2 | 通过 |
| 3.4 | 前端显示保持不变 | ✅ Preservation Requirements | 通过 |

---

## 3. 设计文档验证

### 3.1 修复方案验证

| 文件 | 函数 | 设计文档修复方案 | 源码实际情况 | 状态 |
|------|------|------------------|--------------|------|
| local_kline_import.py | `_parse_datetime` | 添加 `tzinfo=timezone.utc` | 需要修改 | ✅ 可行 |
| tushare_adapter.py | `_parse_trade_date` | 添加 `tzinfo=timezone.utc` | 需要修改 | ✅ 可行 |
| market_adapter.py | `_parse_kline_response` | 使用 `datetime.fromtimestamp(ts, tz=timezone.utc)` | 需要修改 | ✅ 可行 |

### 3.2 数据清理策略验证

**设计文档策略**：
1. 删除存在对应 00:00:00 UTC 记录的 16:00:00 UTC 记录
2. 更新不存在对应记录的 16:00:00 UTC 时间戳为 00:00:00 UTC

**数据库验证**：
```sql
-- 验证查询
SELECT symbol, DATE(time) as trade_date, COUNT(*) as record_count
FROM kline
WHERE symbol = '000001.SZ' AND freq = '1d'
GROUP BY symbol, DATE(time)
HAVING COUNT(*) > 1
ORDER BY trade_date DESC
LIMIT 20;
```

**验证结果**：✅ 策略可行
- 确认存在同一交易日两条记录的情况
- 确认时间戳差异为 16 小时

---

## 4. 任务列表验证

### 4.1 任务完整性

| Phase | 任务 | 需求覆盖 | 设计覆盖 | 状态 |
|-------|------|----------|----------|------|
| Phase 1 | Bug condition 探索测试 | 1.1-1.4 | Bug Condition | ✅ |
| Phase 1 | Preservation 属性测试 | 3.3 | Property 2 | ✅ |
| Phase 2 | 数据清理脚本 | 2.2 | 数据清理策略 | ✅ |
| Phase 2 | 测试清理脚本 | 2.2 | 数据清理策略 | ✅ |
| Phase 2 | 执行数据清理 | 2.2 | 数据清理策略 | ✅ |
| Phase 3 | 修复 `_parse_datetime` | 2.1, 2.3, 2.4 | Fix Implementation | ✅ |
| Phase 3 | 修复 `_parse_trade_date` | 2.1, 2.4 | Fix Implementation | ✅ |
| Phase 3 | 修复 `_parse_kline_response` | 2.1 | Fix Implementation | ✅ |
| Phase 3 | 验证探索测试通过 | 2.1, 2.4 | Fix Checking | ✅ |
| Phase 3 | 验证保留测试通过 | 3.3 | Preservation Checking | ✅ |
| Phase 4 | 集成测试 | 2.1, 3.1-3.4 | Integration Tests | ✅ |
| Phase 4 | 完整测试套件 | 3.1-3.4 | Testing Strategy | ✅ |
| Phase 5 | Checkpoint | 全部 | 全部 | ✅ |

### 4.2 任务依赖关系

```
Phase 1 (探索测试)
    ↓
Phase 3 (代码修复) ← 依赖 Phase 1 的测试用例
    ↓
Phase 2 (数据清理) ← 可并行执行，但建议在修复后执行
    ↓
Phase 4 (集成测试)
    ↓
Phase 5 (Checkpoint)
```

**验证结果**：✅ 任务依赖关系合理

---

## 5. 发现的问题

### 5.1 设计文档行号偏差

| 文件 | 设计文档行号 | 实际行号 | 偏差 |
|------|--------------|----------|------|
| local_kline_import.py | 680-695 | 587-605 | -93 行 |
| tushare_adapter.py | 150-157 | 187-196 | +37 行 |
| market_adapter.py | 95-100 | 125-133 | +30 行 |

**建议**：更新设计文档中的行号，或删除具体行号引用（因为代码会变化）

### 5.2 缺失的验证点

设计文档未提及以下验证点：
1. `sector_kline` 表是否也存在同样问题
2. 其他使用 naive datetime 的地方（如 `adj_factor_repository.py`）

**建议**：在任务中添加对 `sector_kline` 表的检查

---

## 6. 验证结论

### 6.1 总体评估

| 项目 | 状态 | 说明 |
|------|------|------|
| 需求文档 | ✅ 通过 | 完整描述了问题和期望行为 |
| 设计文档 | ⚠️ 需更新 | 行号偏差，修复方案可行 |
| 任务列表 | ✅ 通过 | 完整覆盖需求和设计 |
| 源码验证 | ✅ 通过 | 确认问题存在，修复方案可行 |

### 6.2 建议的更新

1. **更新设计文档行号**：将具体行号改为"约第 X 行"或删除行号引用
2. **添加 sector_kline 检查**：在任务中添加对板块 K 线表的检查
3. **添加其他文件检查**：检查是否有其他文件使用 naive datetime

### 6.3 可执行性评估

**结论**：✅ Spec 可直接执行

- 需求清晰，设计可行
- 任务列表完整，依赖关系合理
- 源码问题确认，修复方案明确
