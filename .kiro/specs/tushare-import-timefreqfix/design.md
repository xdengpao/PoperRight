# Tushare 导入频率超限与数据截断修复 设计文档

## Overview

本修复针对 Tushare 数据导入系统的两个系统性缺陷：

1. **频率超限（Rate Limit Exceeded）**：当前 `RateLimitGroup` 仅有 4 个分组（KLINE/FUNDAMENTALS/MONEY_FLOW/LIMIT_UP），无法覆盖 Tushare 实际存在的多个频率层级（如 80次/min、60次/min、20次/min、10次/min 等），导致大量 API 接口被分配到调用间隔过短的分组，触发 `code=40203` 频率超限错误。

2. **数据截断（Data Truncation）**：多个按日期分批的接口 `date_chunk_days` 步长配置过大，单个子区间返回行数达到 `max_rows` 上限后被 Tushare 静默截断。现有截断检测机制仅记录警告日志，不会自动缩小步长重试，导致数据丢失。

修复策略：
- 扩展 `RateLimitGroup` 枚举，新增 TIER_80、TIER_60、TIER_20、TIER_10 等分组，并在 `config.py` 和 `.env` 中添加对应配置项
- 逐一审查 120+ API 注册表条目，将每个接口分配到与 Tushare 官方限制匹配的频率分组
- 审查并修正所有 `date_chunk_days` 配置，确保不会触发截断
- 在 `_process_batched_by_date` 中实现截断自动重试机制：检测到截断时自动将子区间拆分为更小的子区间重新请求

## Glossary

- **Bug_Condition (C)**：触发缺陷的条件——API 接口的 `rate_limit_group` 对应的调用间隔低于 Tushare 官方限制，或 `date_chunk_days` 步长过大导致单次返回行数达到 `max_rows` 上限
- **Property (P)**：修复后的期望行为——每个 API 的实际调用间隔不低于 Tushare 官方要求；截断发生时自动缩小步长重试，不丢失数据
- **Preservation**：不受修复影响的现有行为——已正确配置的接口继续正常工作；按代码分批逻辑、停止信号响应、错误重试策略、字段映射、代码转换、日志记录均保持不变
- **RateLimitGroup**：`tushare_registry.py` 中的枚举类型，定义频率限制分组，每个分组对应一个调用间隔（秒/次）
- **date_chunk_days**：`ApiEntry` 的属性，定义按日期分批时每个子区间的天数
- **max_rows**：Tushare 单次 API 调用返回的最大行数上限（通常 3000-5000），超出部分被静默截断
- **_build_rate_limit_map()**：`tushare_import.py` 中的函数，从 `settings` 构建 `RateLimitGroup → 调用间隔` 的映射字典

## Bug Details

### Bug Condition

缺陷在以下两种情况下触发：

**情况 A — 频率超限**：当一个 API 接口的 Tushare 官方频率限制低于其所属 `RateLimitGroup` 配置的调用频率时，系统以过高频率调用该接口。例如 `stk_auction` 限制 10次/min（需 ≥6.0s 间隔），但被分配到 FUNDAMENTALS 组（0.40s 间隔，即 150次/min）。

**情况 B — 数据截断**：当一个按日期分批的 API 接口的 `date_chunk_days` 步长过大，导致单个子区间返回行数达到 `max_rows` 上限时，超出部分被 Tushare 静默截断，且系统仅记录警告不自动重试。

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {api_entry: ApiEntry, rate_limit_map: dict, api_response_rows: int}
  OUTPUT: boolean

  // 情况 A：频率超限
  actual_interval = rate_limit_map[api_entry.rate_limit_group]
  official_min_interval = getTushareOfficialMinInterval(api_entry.api_name)
  rate_limit_bug = actual_interval < official_min_interval

  // 情况 B：数据截断未重试
  max_rows = api_entry.extra_config.get("max_rows", 3000)
  truncation_bug = (api_entry.batch_by_date
                    AND api_response_rows >= max_rows
                    AND NOT autoRetryWithSmallerChunk())

  RETURN rate_limit_bug OR truncation_bug
END FUNCTION
```

### Examples

- `stk_auction`（开盘竞价）：Tushare 限制 10次/min（需 ≥6.0s），当前分配 FUNDAMENTALS 组（0.40s），实际调用频率超限 15 倍 → 触发 `code=40203`
- `ths_daily`（同花顺行业指数行情）：`date_chunk_days=2`，全市场约 500+ 板块，2 天数据量可能达到 3000 行上限 → 数据被截断
- `sw_daily`（申万行业日行情）：`date_chunk_days=130`，130 天 × ~30 个行业 = ~3900 行，超过 `max_rows=4000` 的安全阈值 → 接近截断边界
- `limit_list_ths`（涨跌停榜单）：`date_chunk_days=15`，每日涨跌停股票数量波动大，极端行情下 15 天数据可能超过 3000 行 → 间歇性截断
- `daily`（日线行情）：使用 KLINE 组（0.18s），Tushare 限制 500次/min → 配置正确，不触发缺陷

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 已正确配置频率分组的接口（如 `daily` 使用 KLINE 组 0.18s）继续以原有频率正常导入
- 按代码分批（`batch_by_code=True`）的接口分批策略路由 `determine_batch_strategy()` 优先级不变
- 未截断的子区间（返回行数 < max_rows）正常写入数据库，不触发重试
- 停止信号响应机制不变：收到停止信号时中断导入并更新状态为 "stopped"
- 错误重试策略不变：网络超时重试 3 次，Token 无效直接终止，频率限制等待 60s 重试
- 字段映射（`_apply_field_mappings`）和代码格式转换（`_convert_codes`）逻辑不变
- 导入完成后 `tushare_import_log` 和 Redis 进度记录逻辑不变

**Scope:**
所有不涉及频率分组变更或 `date_chunk_days` 调整的接口和代码路径应完全不受本次修复影响。

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **RateLimitGroup 枚举值不足**：当前仅有 4 个分组（KLINE=500次/min, FUNDAMENTALS=200次/min, MONEY_FLOW=300次/min, LIMIT_UP=10次/min），但 Tushare 实际存在更多频率层级（如 80次/min、60次/min、20次/min），导致许多接口被迫使用不匹配的分组。例如限制 10次/min 的接口被分配到 FUNDAMENTALS（200次/min）。

2. **API 注册表条目频率分组分配错误**：120+ 个 API 条目中，大量接口的 `rate_limit_group` 未根据 Tushare 官方文档逐一核实，而是粗略归类。特别是打板专题数据中的部分接口（如 `stk_auction`、`ths_daily`）被错误分配。

3. **date_chunk_days 配置未考虑数据密度**：部分接口的步长配置基于经验估算而非实际数据密度计算。例如 `sw_daily` 的 `date_chunk_days=130` 在行业数量较多时可能接近 `max_rows=4000` 的上限。

4. **截断检测机制不完整**：`check_truncation()` 函数仅记录警告日志，`_process_batched_by_date` 中检测到截断后仅设置 `needs_smaller_chunk=True` 标志但不执行实际的步长缩小和重试操作。

5. **_build_rate_limit_map() 缺少新分组映射**：函数硬编码了 4 个分组的映射，新增的 `RateLimitGroup` 枚举值无法自动获得对应的配置值。

## Correctness Properties

Property 1: Bug Condition - 频率分组与 Tushare 官方限制匹配

_For any_ API entry in the registry where the Tushare official rate limit is known, the assigned `rate_limit_group`'s configured interval (seconds per call) SHALL be greater than or equal to the minimum interval required by Tushare's official limit (with safety margin), ensuring no API is called faster than its official limit allows.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition - date_chunk_days 不导致截断

_For any_ API entry in the registry where `batch_by_date=True` and `estimated_daily_rows` is configured in `extra_config`, the product `date_chunk_days × estimated_daily_rows` SHALL be strictly less than `max_rows`, ensuring no single date chunk can trigger silent data truncation.

**Validates: Requirements 2.3**

Property 3: Bug Condition - RateLimitGroup 枚举完整性

_For any_ `RateLimitGroup` enum value, `_build_rate_limit_map()` SHALL return a positive float interval, and `Settings` SHALL have a corresponding `rate_limit_*` configuration field, ensuring all rate limit tiers are configurable via `.env`.

**Validates: Requirements 2.2, 2.6**

Property 4: Preservation - 分批策略路由不变

_For any_ `(ApiEntry, params)` input pair, the fixed `determine_batch_strategy()` function SHALL return the same strategy string as the original function, preserving the batch routing priority logic.

**Validates: Requirements 3.1, 3.3**

Property 5: Preservation - 字段映射和代码转换不变

_For any_ `(rows, ApiEntry)` input pair, the fixed `_apply_field_mappings()` and `_convert_codes()` functions SHALL produce the same output as the original functions, preserving data transformation behavior.

**Validates: Requirements 3.6**

Property 6: Preservation - 截断检测函数行为不变（未截断场景）

_For any_ input where `row_count < max_rows`, the fixed `check_truncation()` function SHALL return `False`, same as the original function, preserving the non-truncation detection path.

**Validates: Requirements 3.2**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `app/services/data_engine/tushare_registry.py`

**Changes**:
1. **扩展 RateLimitGroup 枚举**：新增 TIER_80（80次/min, ~0.90s）、TIER_60（60次/min, ~1.20s）、TIER_20（20次/min, ~3.50s）等分组，覆盖 Tushare 所有实际频率层级
2. **修正 API 条目频率分组**：逐一审查 120+ 个 API 条目，将每个接口的 `rate_limit_group` 修正为与 Tushare 官方限制匹配的分组
3. **修正 date_chunk_days 配置**：对所有 `batch_by_date=True` 的接口，根据数据密度重新计算安全步长，确保 `date_chunk_days × estimated_daily_rows < max_rows`
4. **添加 estimated_daily_rows 到 extra_config**：为关键接口添加预估每日行数，支持预检查

**File**: `app/core/config.py`

**Changes**:
1. **添加新频率分组配置项**：在 `Settings` 类中添加 `rate_limit_tier_80`、`rate_limit_tier_60`、`rate_limit_tier_20` 等字段

**File**: `app/tasks/tushare_import.py`

**Changes**:
1. **更新 _build_rate_limit_map()**：添加新 `RateLimitGroup` 枚举值到映射字典
2. **实现截断自动重试**：在 `_process_batched_by_date` 中，当 `check_truncation()` 返回 `True` 时，自动将当前子区间拆分为更小的子区间（步长减半）并重新请求数据
3. **连续截断自动缩小后续步长**：当连续截断计数达到阈值时，自动缩小后续所有子区间的步长

**File**: `.env` / `.env.example`

**Changes**:
1. **添加新频率分组环境变量**：`RATE_LIMIT_TIER_80=0.90`、`RATE_LIMIT_TIER_60=1.20`、`RATE_LIMIT_TIER_20=3.50` 等

## Testing Strategy

### Validation Approach

测试策略分两阶段：首先在未修复代码上运行探索性测试确认缺陷存在，然后在修复后验证正确性并确保不引入回归。

### Exploratory Bug Condition Checking

**Goal**: 在实施修复前，通过测试确认缺陷的存在和根因。

**Test Plan**: 编写测试遍历注册表中所有 API 条目，检查其 `rate_limit_group` 对应的调用间隔是否满足 Tushare 官方限制。在未修复代码上运行，预期会发现大量不匹配的条目。

**Test Cases**:
1. **频率分组匹配测试**：遍历所有 API 条目，检查 rate_limit_group 间隔 vs Tushare 官方限制（will fail on unfixed code）
2. **RateLimitGroup 完整性测试**：检查 _build_rate_limit_map() 是否覆盖所有枚举值（will fail on unfixed code）
3. **date_chunk_days 安全性测试**：检查所有 batch_by_date 接口的步长配置（will fail on unfixed code）
4. **截断重试机制测试**：模拟截断场景，验证是否自动重试（will fail on unfixed code）

**Expected Counterexamples**:
- 多个 API 条目的 rate_limit_group 间隔远低于 Tushare 官方限制
- _build_rate_limit_map() 缺少新增枚举值的映射
- 部分接口的 date_chunk_days × estimated_daily_rows >= max_rows

### Fix Checking

**Goal**: 验证修复后，所有触发缺陷条件的输入都能产生正确行为。

**Pseudocode:**
```
FOR ALL api_entry IN TUSHARE_API_REGISTRY DO
  rate_delay = _build_rate_limit_map()[api_entry.rate_limit_group]
  official_min = getTushareOfficialMinInterval(api_entry.api_name)
  ASSERT rate_delay >= official_min

  IF api_entry.batch_by_date AND api_entry.extra_config.get("estimated_daily_rows") THEN
    max_rows = api_entry.extra_config.get("max_rows", 3000)
    ASSERT api_entry.date_chunk_days * api_entry.extra_config["estimated_daily_rows"] < max_rows
  END IF
END FOR
```

### Preservation Checking

**Goal**: 验证修复不影响非缺陷路径的现有行为。

**Pseudocode:**
```
FOR ALL (entry, params) WHERE NOT isBugCondition(entry, params) DO
  ASSERT determine_batch_strategy_original(entry, params) = determine_batch_strategy_fixed(entry, params)
  ASSERT _apply_field_mappings_original(rows, entry) = _apply_field_mappings_fixed(rows, entry)
  ASSERT _convert_codes_original(rows, entry) = _convert_codes_fixed(rows, entry)
  ASSERT check_truncation_original(row_count < max_rows, ...) = check_truncation_fixed(row_count < max_rows, ...)
END FOR
```

**Testing Approach**: 使用 Hypothesis 属性测试框架生成随机输入，验证修复前后行为一致性。属性测试特别适合保全检查，因为它能自动生成大量测试用例覆盖边界情况。

**Test Cases**:
1. **分批策略路由保全**：生成随机 ApiEntry 和 params，验证 determine_batch_strategy() 返回值不变
2. **字段映射保全**：生成随机行数据和 ApiEntry，验证 _apply_field_mappings() 输出不变
3. **代码转换保全**：生成随机行数据和 ApiEntry，验证 _convert_codes() 输出不变
4. **未截断检测保全**：生成 row_count < max_rows 的输入，验证 check_truncation() 返回 False

### Unit Tests

- 测试新增 RateLimitGroup 枚举值的完整性
- 测试 _build_rate_limit_map() 覆盖所有枚举值
- 测试 Settings 中新增配置项的默认值和 .env 覆盖
- 测试截断自动重试逻辑：模拟返回 max_rows 行，验证自动拆分子区间
- 测试连续截断步长缩小：模拟连续 3 个截断子区间，验证后续步长减半
- 测试 check_chunk_config() 预检查逻辑

### Property-Based Tests

- 生成随机 API 注册表条目，验证频率分组间隔 >= Tushare 官方限制
- 生成随机 batch_by_date 配置，验证 date_chunk_days × estimated_daily_rows < max_rows
- 生成随机 (ApiEntry, params) 对，验证 determine_batch_strategy() 保全
- 生成随机行数据，验证 _apply_field_mappings() 和 _convert_codes() 保全
- 生成随机 row_count < max_rows 输入，验证 check_truncation() 返回 False

### Integration Tests

- 端到端测试：模拟完整导入流程，验证频率限制正确应用
- 截断重试集成测试：模拟 API 返回截断数据，验证自动重试后数据完整
- 停止信号测试：验证截断重试过程中收到停止信号能正确中断
