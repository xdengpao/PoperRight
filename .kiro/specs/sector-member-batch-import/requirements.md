# 需求文档：板块成分数据全量导入（按板块代码遍历）

## 简介

当前系统导入板块成分数据时存在两个问题：

### 问题一：板块覆盖率低

因为没有遍历所有板块代码，导致五个数据源的成分股覆盖率极低：

| 数据源 | 板块总数 | 有成分股的板块 | 覆盖股票数 |
|--------|---------|--------------|-----------|
| DC（东方财富） | 1020 | 1 | 449 |
| THS（同花顺） | 1724 | 2 | 5469 |
| TDX（通达信） | 481 | 20 | 3000 |
| TI（申万行业） | 359 | 27 | 3 |
| CI（中信行业） | 0 | 0 | 0 |

根本原因：`ths_member`、`dc_member`、`tdx_member` 三个接口需要传入具体的板块代码（`ts_code`）才能返回该板块的成分股，不传时 Tushare 只返回默认的极少数板块。

### 问题二：trade_date 字段处理错误导致数据去重

导入显示成功 1,430,805 条，但数据库实际只存储 78,657 条。经分析：

| 数据源 | API 返回 trade_date | 注册表配置 | 问题 |
|--------|---------------------|------------|------|
| TDX | ✅ 有（如 `20250328`） | 硬编码 `19000101` | 未映射 API 返回的日期字段 |
| DC | ✅ 有（如 `20260425`） | 硬编码 `19000101` | 未映射 API 返回的日期字段 |
| THS | ❌ 无 | 硬编码 `19000101` | API 无日期，需使用快照日期 |

由于 `sector_constituent` 表有唯一约束 `UNIQUE(trade_date, sector_code, data_source, symbol)`，当 trade_date 都被硬编码为 `1900-01-01` 时，同一板块的同一股票多次导入会被去重，导致大量数据丢失。

### 问题三：TI/CI 的 trade_date 字段语义需统一

经进一步分析，TI（申万行业）和 CI（中信行业）的 `in_date` 字段含义清晰，应保留：

| 数据源 | API 字段 | 含义 | 建议处理 |
|--------|----------|------|----------|
| TI | `in_date` | 股票纳入该行业的日期 | 保留，映射到 `trade_date` |
| CI | `in_date` | 股票纳入该行业的日期 | 保留，映射到 `trade_date` |
| TDX | `trade_date` | 股票调入板块的日期 | 保留，映射到 `trade_date` |
| DC | `trade_date` | 股票调入板块的日期 | 保留，映射到 `trade_date` |
| THS | 无 | API 不返回日期 | 使用导入当天日期作为纳入日期 |

**设计决策**：
- `trade_date` 字段语义统一为"纳入日期"（股票加入板块的日期）
- 不引入"快照日期"概念，减少数据冗余
- THS 因 API 不返回日期，使用导入当天日期作为纳入日期

### 问题四：TI 板块覆盖率低

TI（申万行业）有 359 个板块，但只有 27 个有成分股数据。原因：
- `index_member_all` 接口没有配置 `batch_by_sector=True`
- `max_rows=2000` 可能导致数据截断
- 没有按板块遍历，无法确保所有板块都被覆盖

本需求定义新增"按板块代码遍历"导入模式，并统一 trade_date 字段语义，使五个数据源均能获取完整的板块成分数据。

## 术语表

- **sector_info**：板块信息表，存储板块代码、名称、类型、数据来源
- **sector_constituent**：板块成分表，存储板块代码与股票代码的映射关系
- **batch_by_sector**：按板块代码遍历的新分批模式，区别于现有的 `batch_by_code`（按股票代码）和 `batch_by_date`（按日期）
- **成分股覆盖率**：有成分股数据的板块数 / 板块总数

## 需求

---

### 需求 1：新增 batch_by_sector 分批模式

**用户故事：** 作为量化交易者，我希望导入系统能够自动遍历 `sector_info` 表中所有板块代码，逐个调用 Tushare 成分股接口，以便获取完整的板块成分数据。

#### 验收标准

1. THE `ApiEntry` 数据类 SHALL 新增 `batch_by_sector: bool = False` 字段，标识该接口是否需要按板块代码遍历导入
2. WHEN `batch_by_sector=True` 时，THE 导入任务 SHALL 在执行前先查询 `sector_info` 表，获取该接口对应 `data_source` 下的所有板块代码列表
3. THE 导入任务 SHALL 对每个板块代码逐一调用 Tushare API，将 `ts_code` 参数设为当前板块代码
4. WHEN 某个板块代码调用失败时，THE 导入任务 SHALL 记录 WARNING 日志并继续处理下一个板块，不中断整体导入
5. THE 导入任务 SHALL 在每个板块代码调用之间遵守该接口的频率限制（`rate_limit_group`）
6. THE 导入进度 SHALL 实时更新，格式为"正在导入板块 {当前序号}/{总数}: {板块代码} ({板块名称})"
7. THE 导入任务 SHALL 支持停止信号，收到停止信号后在当前板块处理完成后退出，不强制中断

---

### 需求 2：ths_member 启用 batch_by_sector 模式

**用户故事：** 作为量化交易者，我希望同花顺 THS 的 1724 个板块全部导入成分股数据，以便板块因子能够覆盖全市场股票。

#### 验收标准

1. THE `ths_member` 接口注册配置 SHALL 设置 `batch_by_sector=True`
2. WHEN 导入 `ths_member` 时，THE 导入任务 SHALL 查询 `sector_info WHERE data_source='THS'` 获取所有 THS 板块代码
3. THE 导入任务 SHALL 对每个 THS 板块代码调用 `ths_member` 接口，传入 `ts_code` 参数
4. WHEN 导入完成后，THE `sector_constituent` 表中 `data_source='THS'` 的板块数 SHALL 接近 1724（允许部分板块无成分股数据）
5. THE 导入任务 SHALL 使用 `inject_fields={'data_source': 'THS'}` 注入数据来源字段
6. WHEN API 未返回 `trade_date` 字段时，THE 导入任务 SHALL 使用当前日期作为纳入日期（`date.today()`）

---

### 需求 3：dc_member 启用 batch_by_sector 模式并修复 trade_date 映射

**用户故事：** 作为量化交易者，我希望东方财富 DC 的 1020 个板块全部导入成分股数据，且 trade_date 使用 API 返回的真实日期。

#### 验收标准

1. THE `dc_member` 接口注册配置 SHALL 设置 `batch_by_sector=True`
2. WHEN 导入 `dc_member` 时，THE 导入任务 SHALL 查询 `sector_info WHERE data_source='DC'` 获取所有 DC 板块代码
3. THE 导入任务 SHALL 对每个 DC 板块代码调用 `dc_member` 接口，传入 `ts_code` 参数
4. WHEN 导入完成后，THE `sector_constituent` 表中 `data_source='DC'` 的板块数 SHALL 接近 1020
5. THE 注册表配置 SHALL 添加字段映射 `FieldMapping(source="trade_date", target="trade_date")`，使用 API 返回的日期
6. THE `inject_fields` SHALL 移除硬编码的 `trade_date` 字段，仅保留 `{"data_source": "DC"}`

---

### 需求 4：tdx_member 启用 batch_by_sector 模式并修复 trade_date 映射

**用户故事：** 作为量化交易者，我希望通达信 TDX 的 481 个板块全部导入成分股数据，且 trade_date 使用 API 返回的真实日期。

#### 验收标准

1. THE `tdx_member` 接口注册配置 SHALL 设置 `batch_by_sector=True`
2. WHEN 导入 `tdx_member` 时，THE 导入任务 SHALL 查询 `sector_info WHERE data_source='TDX'` 获取所有 TDX 板块代码
3. THE 导入任务 SHALL 对每个 TDX 板块代码调用 `tdx_member` 接口，传入 `ts_code` 参数
4. WHEN 导入完成后，THE `sector_constituent` 表中 `data_source='TDX'` 的板块数 SHALL 接近 481
5. THE 注册表配置 SHALL 添加字段映射 `FieldMapping(source="trade_date", target="trade_date")`，使用 API 返回的日期
6. THE `inject_fields` SHALL 移除硬编码的 `trade_date` 字段，仅保留 `{"data_source": "TDX"}`

---

### 需求 5：index_member_all（TI）启用 batch_by_sector 模式

**优先级：高**

**用户故事：** 作为量化交易者，我希望申万行业 TI 的 359 个板块全部导入成分股数据，且 trade_date 保留 API 返回的纳入日期。

#### 验收标准

1. THE `index_member_all` 接口注册配置 SHALL 设置 `batch_by_sector=True`
2. WHEN 导入 `index_member_all` 时，THE 导入任务 SHALL 查询 `sector_info WHERE data_source='TI'` 获取所有 TI 板块代码
3. THE 导入任务 SHALL 对每个 TI 板块代码调用 `index_member_all` 接口，传入 `ts_code` 参数
4. WHEN 导入完成后，THE `sector_constituent` 表中 `data_source='TI'` 的板块数 SHALL 接近 359（允许部分板块无成分股数据）
5. THE 注册表配置 SHALL 保留 `in_date` → `trade_date` 的字段映射，使用 API 返回的纳入日期
6. THE `max_rows` 配置 SHALL 提高到 5000 或更高，避免截断

---

### 需求 6：ci_index_member（CI）保留纳入日期

**优先级：高**

**用户故事：** 作为量化交易者，我希望中信行业 CI 的成分股数据保留 API 返回的纳入日期。

#### 验收标准

1. THE 注册表配置 SHALL 保留 `in_date` → `trade_date` 的字段映射，使用 API 返回的纳入日期
2. WHEN 重新导入 `ci_index_member` 后，THE `sector_constituent` 表中 `data_source='CI'` 的记录数 SHALL 大于 3000
3. THE `ci_index_member` 接口 SHALL 保持 `inject_fields={'data_source': 'CI'}` 注入数据来源字段

---

### 需求 7：ths_member 使用导入日期作为纳入日期

**优先级：高**

**用户故事：** 作为量化交易者，我希望同花顺 THS 的成分股数据使用导入当天日期作为纳入日期，因为 API 不返回日期字段。

#### 验收标准

1. THE `ths_member` 接口注册配置 SHALL 设置 `batch_by_sector=True`
2. WHEN API 未返回 `trade_date` 字段时，THE 导入任务 SHALL 使用当前日期作为纳入日期（`date.today()`）
3. THE 注册表配置 SHALL 不包含 `trade_date` 的字段映射，由导入逻辑动态注入当前日期

---

### 需求 8：TDX/DC 保留调入日期

**优先级：中**

**用户故事：** 作为量化交易者，我希望通达信 TDX 和东方财富 DC 的成分股数据保留 API 返回的调入日期。

#### 验收标准

1. THE 注册表配置 SHALL 保留 `trade_date` 字段映射，使用 API 返回的调入日期
2. THE `inject_fields` SHALL 移除硬编码的 `trade_date` 字段，仅保留 `{"data_source": "TDX/DC"}`

---

### 需求 9：导入进度与错误处理

**用户故事：** 作为量化交易者，我希望在导入大量板块成分数据时能够看到实时进度，并且单个板块失败不影响整体导入。

#### 验收标准

1. THE 导入进度 SHALL 通过 Redis 实时更新，包含：当前板块序号、总板块数、当前板块代码、当前板块名称、已成功写入记录数、失败板块数
2. WHEN 某个板块的 Tushare API 返回空数据时，THE 导入任务 SHALL 跳过该板块并继续，不计为失败
3. WHEN 某个板块的 Tushare API 返回错误（非空数据但 code != 0）时，THE 导入任务 SHALL 记录 WARNING 日志，将该板块计为失败，并继续处理下一个板块
4. THE 导入完成后，THE 导入日志 SHALL 记录：总板块数、成功板块数、失败板块数、总写入记录数
5. THE 前端导入进度显示 SHALL 展示"正在导入板块 {n}/{total}: {sector_code}"格式的当前状态

---

### 需求 10：正确性属性

**用户故事：** 作为量化交易者，我希望导入的成分股数据满足基本的正确性约束，确保数据质量。

#### 验收标准

1. THE `sector_constituent` 表中每条记录的 `(trade_date, sector_code, data_source, symbol)` 组合 SHALL 唯一（ON CONFLICT DO NOTHING 保证）
2. THE 导入的 `sector_code` SHALL 来自 `sector_info` 表中已存在的板块代码，不应写入不存在的板块代码
3. THE 导入的 `symbol` SHALL 为 6 位数字格式（经过代码格式转换）
4. WHEN `batch_by_sector` 模式下某板块返回的成分股数量达到 `max_rows` 上限时，THE 导入任务 SHALL 记录 WARNING 日志提示数据可能被截断
5. THE `trade_date` 字段语义 SHALL 统一为"纳入日期"（股票加入板块的日期）：
   - TI/CI：使用 API 返回的 `in_date`
   - TDX/DC：使用 API 返回的 `trade_date`
   - THS：使用导入当天日期（因 API 不返回日期）
