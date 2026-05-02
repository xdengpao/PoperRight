# Tushare 每日智能选股快速导入工作流 Requirements

## 背景

当前“智能选股一键导入”以完整依赖覆盖为目标，适合首次初始化、历史缺口补导和全链路修复。但实际每日选股只需要更新“今天或最近交易日”的行情、指标和少量专题数据。2026-04-30 晚间执行 `20260410` 至 `20260430` 全链路导入时，已观察到以下耗时特征：

| 接口 | 数据特征 | 当前耗时观察 |
|------|----------|--------------|
| `dc_member` | 板块成分，全量/低频变化 | 约 124.5 分钟 |
| `tdx_member` | 板块成分，全量/低频变化 | 约 58.4 分钟 |
| `ci_index_member` | 行业成分，全量/低频变化 | 约 47.3 分钟 |
| `index_member_all` | 申万行业成分，全量/低频变化 | 约 46.8 分钟 |
| `ths_member` | 板块成分，全量/低频变化 | 约 37.8 分钟 |
| `moneyflow_dc` / `moneyflow_ths` | 日期范围全市场资金流 | 各约 35.6 分钟 |
| `daily` / `adj_factor` / `daily_basic` | 日期范围全市场日频行情和指标 | 各约 21-24 分钟 |

结论：每日导入如果继续执行完整链路，会把“静态/低频全量类数据”和“多数据源可选扩展链路”混入日常更新，导致每天 18:00 后到可选股之间等待时间过长。

## 目标

新增一个面向每日选股的快速导入方案。该方案不替代完整工作流，而是在现有完整链路之外增加“每日快速链路”，优先满足当天智能选股可用性：

- 在一键导入入口提供链路下拉框，可选择每日快速、缺口补导、周维护、完整初始化；
- 默认选择每日快速链路；
- 每日 18:00 后快速更新当日或最近交易日数据；
- 只执行当天选股所需的最小必要接口；
- 跳过或延后低频静态数据、全量板块成分和非启用数据源；
- 支持按当前启用策略/因子推导依赖，减少无关专题下载；
- 保留完整工作流用于初始化、周末维护、历史补洞和数据修复。
- 每日快速导入完成后执行完整性检查；若数据不完整，用户可再选择缺口补导链路补齐缺失数据。

## 工作流分层建议

### 1. 每日快速链路（Daily Fast）

每天 18:00 后默认执行，用于当天智能选股。

建议包含：

- `daily`
- `adj_factor`
- `daily_basic`
- `stk_factor_pro`
- `moneyflow_dc`（默认资金流来源）
- 默认板块行情：`dc_daily`
- 默认指数核心行情：核心指数集合的 `index_daily`、`index_dailybasic`、`idx_factor_pro`
- 按启用策略需要可选执行：`limit_list_d`、`limit_step`、`top_list`、`margin_detail`、`cyq_perf`

建议默认不包含：

- `dc_member`、`ths_member`、`tdx_member`、`index_member_all`、`ci_index_member`
- `stock_basic`、`trade_cal`、`index_basic` 等低频基础表，除非完整性检查发现过期；
- `moneyflow_ths` 和 THS/TDX/TI/CI 板块扩展链路，除非策略明确使用对应数据源。

### 2. 缺口补导链路（Gap Repair）

用于发现某接口最近成功日期早于目标交易日时，只补缺失交易日，不再重复下载已覆盖日期。

### 3. 周维护链路（Weekly Maintenance）

每周非交易时段执行，用于低频基础和成分数据：

- `stock_basic`
- `trade_cal`
- `index_basic`
- `dc_index`
- `dc_member`
- 可选：`ths_index`、`ths_member`、`tdx_index`、`tdx_member`、`index_classify`、`index_member_all`、`ci_index_member`

### 4. 完整初始化/修复链路（Full Initialize）

保留现有全链路能力，用于首次初始化、历史区间补导和大型数据修复。

## Requirements

### Requirement 1：提供每日快速导入模式

**User Story:** 作为量化交易员，我希望每天只下载今日选股真正需要的数据，这样 18:00 后可以更快进入智能选股。

#### Acceptance Criteria

1. WHEN 用户选择每日快速导入 THEN 系统 SHALL 只执行日频行情、日指标、技术专题、默认资金流、默认板块行情和核心指数数据。
2. WHEN 用户未显式启用扩展数据源 THEN 系统 SHALL 不默认执行 THS/TDX/TI/CI 全链路扩展导入。
3. WHEN 用户未显式启用静态数据刷新 THEN 系统 SHALL 不默认执行板块成员、指数成分、股票基础信息等低频全量接口。
4. WHEN 每日快速导入完成 THEN 系统 SHALL 能支持右侧趋势突破综合策略和现有智能选股默认策略的当天筛选。

### Requirement 2：按策略/因子推导每日依赖

**User Story:** 作为量化交易员，我希望系统根据当前要运行的策略判断需要哪些专题数据，这样不为未使用的因子下载数据。

#### Acceptance Criteria

1. WHEN 用户选择全部默认策略 THEN 系统 SHALL 使用默认每日快速依赖集。
2. WHEN 用户只选择部分策略或策略模板 THEN 系统 SHOULD 从因子注册表和策略配置推导需要的 API。
3. WHEN 策略未使用筹码、两融、打板或龙虎榜因子 THEN 每日快速导入 SHOULD 跳过对应扩展接口。
4. WHEN 策略使用 THS/TDX/TI/CI 板块源 THEN 每日快速导入 SHOULD 只启用对应数据源的行情接口，并仅在成分数据过期时提示执行维护链路。

### Requirement 3：跳过低频静态数据并提供过期检查

**User Story:** 作为量化交易员，我希望低频数据不要每天全量下载，但如果它过期或缺失，系统能提醒我维护。

#### Acceptance Criteria

1. WHEN `stock_basic`、`trade_cal`、`index_basic` 在有效期内 THEN 每日快速导入 SHALL 跳过这些接口。
2. WHEN 板块成分表在有效期内 THEN 每日快速导入 SHALL 跳过 `dc_member`、`ths_member`、`tdx_member`、`index_member_all`、`ci_index_member`。
3. WHEN 低频数据缺失或超过配置 TTL THEN 系统 SHALL 在确认面板或完整性摘要中提示执行周维护链路。
4. WHEN 用户强制刷新静态数据 THEN 系统 MAY 将低频接口追加到本次任务，但必须提示预计耗时明显增加。

### Requirement 4：按最近成功日期自动补缺口

**User Story:** 作为量化交易员，我希望系统自动识别缺了哪几天，而不是每天重复下载很长日期范围。

#### Acceptance Criteria

1. WHEN 用户选择“最近交易日”导入 THEN 系统 SHALL 根据交易日历解析目标交易日。
2. WHEN 某个日频接口最近成功日期早于目标交易日 THEN 系统 SHALL 自动生成缺口日期范围。
3. WHEN 某个日频接口已经覆盖目标交易日 THEN 系统 SHOULD 跳过该接口或标记为已就绪。
4. WHEN 用户手动选择日期范围 THEN 系统 SHALL 支持只补该范围内缺失交易日。

### Requirement 5：核心指数和板块默认最小化

**User Story:** 作为量化交易员，我希望大盘和板块数据足够支持选股判断，但不要默认下载无关全量指数。

#### Acceptance Criteria

1. WHEN 每日快速导入指数专题 THEN 系统 SHALL 默认只导入核心指数集合。
2. WHEN 策略需要全量指数或行业指数 THEN 系统 SHOULD 允许切换为扩展指数导入。
3. WHEN 每日快速导入板块数据 THEN 系统 SHALL 默认只导入默认数据源的板块行情，例如 DC 的 `dc_daily`。
4. WHEN 板块成分未过期 THEN 系统 SHALL 复用已有成分映射，不重复导入成分表。

### Requirement 6：提供耗时预估和链路选择

**User Story:** 作为量化交易员，我希望执行前知道本次会跑哪些接口、预计耗时和跳过原因。

#### Acceptance Criteria

1. WHEN 用户查看一键导入控制区 THEN 系统 SHALL 提供链路模式下拉框，选项包含“每日快速”“缺口补导”“周维护”“完整初始化”。
2. WHEN 页面初始化 THEN 链路模式 SHALL 默认选择“每日快速”。
3. WHEN 用户切换链路模式 THEN 系统 SHALL 根据所选链路重新生成导入计划和预计耗时。
4. WHEN 用户打开导入确认面板 THEN 系统 SHALL 展示本次计划执行、跳过、建议维护的接口列表。
5. WHEN 接口被跳过 THEN 系统 SHALL 展示跳过原因，例如“今日已覆盖”“静态数据未过期”“当前策略未使用”。
6. WHEN 用户启用慢速扩展项 THEN 系统 SHALL 提示预计耗时增加。
7. WHEN 工作流结束 THEN 系统 SHALL 展示实际耗时、接口耗时排名和可优化建议。

### Requirement 7：保留完整链路和现有行为

**User Story:** 作为开发者，我希望每日快速导入不破坏现有完整一键导入能力。

#### Acceptance Criteria

1. WHEN 用户选择完整初始化或历史补导 THEN 系统 SHALL 保留现有完整工作流。
2. WHEN 用户选择每日快速导入 THEN 系统 SHALL 使用新的快速计划，不影响现有单接口导入、批量导入和历史记录。
3. WHEN 快速链路发现关键依赖缺失 THEN 系统 SHALL 提示用户执行维护链路或完整链路，而不是静默选股。
4. WHEN 后续新增策略或因子 THEN 系统 SHOULD 能通过依赖推导将其纳入快速链路或维护链路。

### Requirement 8：每日快速后的完整性检查和补导闭环

**User Story:** 作为量化交易员，我希望每日快速导入后系统自动检查数据是否完整，如果不完整，我可以选择缺口补导继续补齐，而不是重新跑完整链路。

#### Acceptance Criteria

1. WHEN 每日快速导入完成 THEN 系统 SHALL 自动执行智能选股数据完整性检查。
2. WHEN 完整性检查通过 THEN 系统 SHALL 明确提示“每日选股数据已就绪”或等价状态。
3. WHEN 完整性检查发现缺失 THEN 系统 SHALL 展示缺失接口、缺失日期范围和建议使用的补导链路。
4. WHEN 用户从每日快速结果切换到缺口补导 THEN 系统 SHOULD 自动带入上一轮完整性检查发现的缺口范围和接口集合。
5. WHEN 缺口补导完成 THEN 系统 SHALL 再次执行完整性检查，直到数据就绪或明确展示剩余缺口原因。
6. WHEN 缺失项属于低频静态数据或成分数据过期 THEN 系统 SHOULD 建议“周维护”而不是“缺口补导”。

### Requirement 9：超时失败状态落账和恢复

**User Story:** 作为量化交易员，我希望一键导入任务超时或被 worker 中断后，系统能明确标记失败并允许从未完成步骤恢复，而不是一直显示运行中。

#### Acceptance Criteria

1. WHEN Celery 工作流任务触发 `SoftTimeLimitExceeded`、硬超时或 worker 异常退出 THEN 系统 SHALL 将 workflow 状态标记为 `failed`。
2. WHEN workflow 因超时失败且存在运行中的 child task THEN 系统 SHALL 将该 child task 状态标记为 `failed` 或 `stale_failed`，并写入明确错误信息。
3. WHEN workflow 超时失败 THEN 系统 SHALL 释放 running 键和当前子接口锁，避免后续一键导入被假运行状态阻塞。
4. WHEN 前端查询到超时失败状态 THEN SHALL 展示失败原因、最后运行接口、已完成步骤和可恢复入口。
5. WHEN 用户点击恢复 THEN 系统 SHALL 从未完成或失败步骤继续执行，并跳过已完成步骤。
6. WHEN 单接口导入日志仍停留在 `running` 但 Celery 已无 active/reserved/scheduled 任务 THEN 系统 SHOULD 将该日志识别为 stale 并允许用户修复状态或重新补导。
