# 需求文档：Tushare 导入超时优化

## 简介

当前系统中多个 Tushare 数据导入任务因 `SoftTimeLimitExceeded` 超时失败，运行时间长达 120-168 分钟。这些接口配置了 `batch_by_date=True`，但数据特点是每只股票独立，按日期分批会导致每个日期批次都要遍历全市场 5000+ 只股票，造成 API 调用次数爆炸。

**问题接口（共 15 个）：**

**第一批（已分析）：**
| 接口名 | 运行时间 | 超时限制 | date_chunk_days |
|--------|---------|---------|-----------------|
| stk_holdernumber | 168m14s | 120m | 10 |
| block_trade | 168m14s | 120m | 30 |
| share_float | 120m0s | 120m | 60 |
| repurchase | 120m0s | 120m | 60 |
| pledge_detail | 120m0s | 120m | 15 |
| pledge_stat | 120m0s | 120m | 4 |

**第二批（新增）：**
| 接口名 | 完成进度 | 已完成/总数 | date_chunk_days | 问题类型 |
|--------|---------|------------|-----------------|---------|
| daily_basic | 1% | 24633/2019222 | 1 | 日期分批过多 |
| bak_daily | 1% | 24419/2019222 | ? | 日期分批过多 |
| report_rc | 0% | 205/71721 | 30 | 双重分批 |
| stk_factor_pro | 1% | 21235/2019222 | 1 | 日期分批过多 |
| ccass_hold_detail | 10% | 13718/137925 | 15 | 双重分批 |
| hk_hold | 1% | 13730/2019222 | 1 | 日期分批过多 |
| stk_nineturn | 36% | 13718/38619 | 60 | 双重分批 |
| stk_ah_comparison | 19% | 13714/71721 | 30 | 双重分批 |
| stk_surv | 18% | 6866/38619 | 60 | 双重分批 |

**根本原因：**
- 这些接口支持 `ParamType.STOCK_CODE`，当不传 `ts_code` 时会自动按全市场股票遍历
- `batch_by_date=True` 导致日期分批 × 股票代码分批 = 数万次 API 调用
- Celery 任务超时设置为 `soft_time_limit=7200`（2小时），不足以完成全量导入

本需求通过优化分批策略和增加超时时间，解决导入任务超时问题。

## 术语表

- **batch_by_code**：按股票代码分批模式，每次 API 调用传入一只股票代码
- **batch_by_date**：按日期分批模式，每次 API 调用传入一个日期范围
- **soft_time_limit**：Celery 任务软超时，超时后抛出 `SoftTimeLimitExceeded` 异常
- **time_limit**：Celery 任务硬超时，超时后强制终止任务

## 需求

---

### 需求 1：优化分批策略配置（第一批接口）

**用户故事：** 作为量化交易者，我希望 Tushare 导入任务能够合理分批，避免因 API 调用次数过多导致超时。

#### 验收标准

1. THE `stk_holdernumber` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
2. THE `block_trade` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
3. THE `share_float` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
4. THE `repurchase` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
5. THE `pledge_detail` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
6. THE `pledge_stat` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
7. THE 修改后的接口 SHALL 移除 `date_chunk_days` 配置（不再需要日期分批）
8. THE 修改后的接口 SHALL 保留 `optional_params` 中的 `ParamType.STOCK_CODE` 和 `ParamType.DATE_RANGE`

---

### 需求 1B：优化分批策略配置（第二批接口 - 双重分批问题）

**用户故事：** 作为量化交易者，我希望支持股票代码参数的接口能够按股票代码分批，而不是按日期分批后再遍历股票。

#### 验收标准

1. THE `report_rc` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
2. THE `ccass_hold_detail` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
3. THE `stk_nineturn` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
4. THE `stk_ah_comparison` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
5. THE `stk_surv` 接口 SHALL 将 `batch_by_date=True` 改为 `batch_by_code=True`
6. THE 修改后的接口 SHALL 移除 `date_chunk_days` 配置
7. THE 修改后的接口 SHALL 保留 `optional_params` 中的 `ParamType.STOCK_CODE` 和 `ParamType.DATE_RANGE`

---

### 需求 1C：优化分批策略配置（第二批接口 - 日期分批过多问题）

**用户故事：** 作为量化交易者，我希望日期分批的接口能够使用更大的日期区间，减少 API 调用次数。

#### 验收标准

1. THE `daily_basic` 接口 SHALL 将 `date_chunk_days` 从 1 增加到 30
2. THE `bak_daily` 接口 SHALL 设置 `date_chunk_days=30`（如果未设置）
3. THE `stk_factor_pro` 接口 SHALL 将 `date_chunk_days` 从 1 增加到 30
4. THE `hk_hold` 接口 SHALL 将 `date_chunk_days` 从 1 增加到 30
5. THE 这些接口 SHALL 保持 `batch_by_date=True`（因为它们不支持按股票代码分批）

---

### 需求 2：增加 Celery 任务超时时间

**用户故事：** 作为量化交易者，我希望导入任务有足够的执行时间，避免因超时中断导致数据不完整。

#### 验收标准

1. THE `tushare_import` Celery 任务 SHALL 将 `soft_time_limit` 从 7200 秒（2小时）增加到 14400 秒（4小时）
2. THE `tushare_import` Celery 任务 SHALL 将 `time_limit` 从 10800 秒（3小时）增加到 18000 秒（5小时）
3. THE 超时时间设置 SHALL 在 `app/tasks/tushare_import.py` 的 `@app.task` 装饰器中配置

---

### 需求 3：进度显示优化

**用户故事：** 作为量化交易者，我希望在导入大量股票数据时能够看到实时进度，了解当前处理到哪只股票。

#### 验收标准

1. THE `batch_by_code` 模式下的进度显示 SHALL 包含：当前股票序号、总股票数、当前股票代码
2. THE 进度格式 SHALL 为"正在导入股票 {当前序号}/{总数}: {股票代码}"
3. THE 进度更新 SHALL 通过 Redis 实时推送，前端可实时展示

---

### 需求 4：正确性属性

**用户故事：** 作为量化交易者，我希望导入的数据完整准确，不因超时或错误导致数据丢失。

#### 验收标准

1. THE 导入任务 SHALL 在超时前优雅退出，记录已完成的股票代码
2. THE 导入任务 SHALL 支持断点续传，下次导入时跳过已完成的股票
3. THE 单只股票导入失败 SHALL 不影响其他股票的导入
4. THE 导入完成后 SHALL 记录：总股票数、成功股票数、失败股票数、总写入记录数

---

### 需求 5：向后兼容性

**用户故事：** 作为系统管理员，我希望修改后的配置不影响现有导入功能，已导入的数据不受影响。

#### 验收标准

1. THE 修改后的接口 SHALL 保持 `target_table`、`conflict_columns`、`conflict_action` 不变
2. THE 修改后的接口 SHALL 保持 `rate_limit_group` 不变
3. THE 已导入的数据 SHALL 不受影响，新导入的数据 SHALL 正常写入
4. THE 前端导入界面 SHALL 无需修改，自动适配新的分批策略
