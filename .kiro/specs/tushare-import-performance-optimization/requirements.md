# 需求文档

## 简介

Tushare 数据导入功能是 PoperRight 量化交易系统的核心数据基础设施，负责从 Tushare Pro API 获取 120+ 种 A 股市场数据并写入 PostgreSQL / TimescaleDB。当前实现在功能上已较为完善（支持 6 种分批策略、截断检测重试、4 级 Token 路由等），但在性能、可靠性和运维效率方面存在多个可优化点。

本次优化聚焦于：数据库写入性能、HTTP 连接复用、asyncio 事件循环阻塞、增量导入智能调度、数据完整性校验、以及若干代码健壮性改进。目标是在不改变现有架构和 API 接口的前提下，显著提升导入效率和数据可靠性。

## 术语表

- **逐行 INSERT**：当前 `_write_to_postgresql` 和 `_write_to_kline` 中对每条记录单独执行一次 `session.execute(stmt, row)` 的写入方式
- **批量 INSERT**：将多条记录合并为一次数据库操作（如 `executemany` 或多值 VALUES 语法）
- **连接池复用**：在多次 HTTP 请求间复用同一个 TCP 连接，避免重复建立/销毁连接的开销
- **event loop 阻塞**：在 async 函数中调用 `time.sleep()` 等同步阻塞操作，导致整个 asyncio 事件循环暂停
- **增量导入**：基于上次成功导入的截止日期，自动计算本次导入的起始日期，避免重复拉取已有数据
- **数据完整性校验**：导入完成后验证实际写入的数据量是否符合预期（如交易日数量 × 股票数量）

## 需求

### 需求 1: 数据库批量写入优化

**用户故事：** 作为系统运维人员，我希望大批量数据导入时数据库写入速度显著提升，以便缩短全市场数据同步的等待时间。

#### 验收标准

1.1 WHEN 调用 `_write_to_postgresql` 写入数据 THEN 系统 SHALL 使用批量 INSERT（`executemany` 或等效方式）替代逐行 INSERT，单批最大 1000 行。

1.2 WHEN 调用 `_write_to_kline`、`_write_to_adjustment_factor`、`_write_to_sector_kline` 写入 TimescaleDB 数据 THEN 系统 SHALL 使用批量 INSERT 替代逐行 INSERT。

1.3 WHEN 批量 INSERT 中某行因数据类型错误导致整批失败 THEN 系统 SHALL 回退到逐行 INSERT 模式处理该批次，确保有效数据不丢失。

1.4 WHEN 批量写入完成 THEN 系统 SHALL 保持现有的 ON CONFLICT 去重策略（DO NOTHING / DO UPDATE）不变。

### 需求 2: HTTP 连接池复用

**用户故事：** 作为系统运维人员，我希望 Tushare API 调用时复用 HTTP 连接，以便减少 TCP 连接建立开销，提升 batch_by_code 模式下 5000+ 次 API 调用的整体效率。

#### 验收标准

2.1 WHEN 创建 TushareAdapter 实例 THEN 系统 SHALL 内部持有一个可复用的 `httpx.AsyncClient` 实例（带连接池），而非每次 `_call_api` 都新建 client。

2.2 WHEN 导入任务结束（正常完成、失败或被停止） THEN 系统 SHALL 确保 `httpx.AsyncClient` 被正确关闭，释放底层连接资源。

2.3 WHEN 使用连接池复用后 THEN 系统 SHALL 保持现有的超时配置（默认 30s）和错误处理逻辑不变。

### 需求 3: 消除 event loop 阻塞

**用户故事：** 作为开发人员，我希望 async 函数中的频率限制等待不阻塞 asyncio 事件循环，以便 Redis 进度更新等 IO 操作能正常执行，避免潜在的超时问题。

#### 验收标准

3.1 WHEN async 函数中需要进行频率限制等待 THEN 系统 SHALL 使用 `await asyncio.sleep(delay)` 替代 `time.sleep(delay)`。

3.2 WHEN 替换为 `asyncio.sleep` 后 THEN 系统 SHALL 保持现有的频率限制间隔配置不变（各 RateLimitGroup 的延迟值不变）。

### 需求 4: 增量导入智能调度

**用户故事：** 作为量化交易员，我希望系统能自动判断上次导入到哪天并从断点续接，以便我不需要每次手动查找和输入日期范围，同时节省 Tushare API 配额。

#### 验收标准

4.1 WHEN 用户发起导入请求且未指定 start_date THEN 系统 SHALL 自动查询 `tushare_import_log` 获取该接口最后一次成功导入的 end_date，将 start_date 设为 end_date 的下一个交易日。

4.2 WHEN 用户发起导入请求且未指定 end_date THEN 系统 SHALL 自动将 end_date 设为当前日期（或最近交易日）。

4.3 WHEN 该接口从未成功导入过（无历史记录） THEN 系统 SHALL 使用合理的默认起始日期（如 20100101）或提示用户手动指定。

4.4 WHEN 用户显式指定了 start_date 和 end_date THEN 系统 SHALL 优先使用用户指定的日期范围，不进行自动推断。

4.5 WHEN 增量导入的 start_date 计算结果晚于 end_date THEN 系统 SHALL 返回提示"数据已是最新，无需导入"，不发起 Celery 任务。

### 需求 5: 数据完整性校验

**用户故事：** 作为量化交易员，我希望导入完成后系统能告诉我数据是否完整，以便我能及时发现因网络错误或截断导致的数据缺失。

#### 验收标准

5.1 WHEN batch_by_code 模式导入完成 THEN 系统 SHALL 在 batch_stats 中记录失败的 ts_code 列表（最多 100 个），并在 tushare_import_log 的 extra_info 中持久化。

5.2 WHEN batch_by_date 模式导入完成 THEN 系统 SHALL 在 batch_stats 中记录失败的日期子区间列表。

5.3 WHEN 导入完成且存在失败项 THEN 系统 SHALL 在 Redis 进度信息中包含 `failed_items` 字段，前端可据此展示失败详情。

### 需求 6: 股票代码后缀推断优化

**用户故事：** 作为开发人员，我希望股票代码到 Tushare ts_code 的转换逻辑更加健壮，以便避免因代码前缀推断错误导致 API 调用失败。

#### 验收标准

6.1 WHEN `_get_stock_list` 从 stock_info 表获取股票列表 THEN 系统 SHALL 优先使用 stock_info 表中已有的 exchange 字段（如有）来确定后缀，而非仅依赖代码前缀推断。

6.2 IF stock_info 表中无 exchange 字段或值为空 THEN 系统 SHALL 回退到现有的前缀推断逻辑，但对无法识别的前缀记录 WARNING 日志而非静默归类为深圳。

### 需求 7: 频率限制配置热更新

**用户故事：** 作为系统运维人员，我希望修改频率限制配置后无需重启 Celery worker 即可生效，以便在遇到频率限制问题时能快速调整。

#### 验收标准

7.1 WHEN 导入任务开始执行 THEN 系统 SHALL 在任务级别重新读取频率限制配置（从 settings），而非使用模块加载时的缓存值。

7.2 WHEN 频率限制配置更新后 THEN 新启动的导入任务 SHALL 使用最新的配置值，已运行中的任务不受影响。

### 需求 8: sector 成分导入 trade_date 逻辑优化

**用户故事：** 作为量化交易员，我希望板块成分数据能正确追踪成分变化，以便我的板块分析基于准确的成分股列表。

#### 验收标准

8.1 WHEN ths_member/dc_member/tdx_member API 不返回 trade_date 字段 THEN 系统 SHALL 注入当前日期作为 trade_date，这一行为与现有逻辑一致。

8.2 WHEN 同一板块的成分股发生变化（新增或移除成分股） THEN 系统 SHALL 能够记录新的成分关系，不因 ON CONFLICT DO NOTHING 而丢失变更。

8.3 WHEN sector_constituent 表中已存在相同 (sector_code, data_source, symbol) 的记录但 trade_date 不同 THEN 系统 SHALL 保留历史记录，新记录正常插入（当前冲突键包含 trade_date，已满足此需求）。
