# 智能选股 Tushare 一键数据导入工作流 Requirements

## 背景

智能选股当前包含 28 个内置/示例策略，启用模块覆盖：

- `ma_trend`：18 个策略使用；
- `volume_price`：14 个策略使用；
- `indicator_params`：12 个策略使用；
- `breakout`：7 个策略使用；
- `factor_editor`：2 个策略显式使用。

策略实际使用的因子共 33 个，覆盖技术面、量价资金、板块面、筹码面、两融面、打板面、指数专题和基本面。若 Tushare 数据导入顺序不正确，常见问题包括：

- 选股能加载 K 线，但 `money_flow_pctl`、`stk_factor`、`sector_rank` 等专题因子缺失；
- 当天尚未有某些专题表数据时，筛选回退不一致；
- 板块数据、指数专题和股票行情不同步，导致组合策略交集为空；
- 用户需要手动展开多个接口分类逐个选择，容易漏导关键接口。

因此需要在 Tushare 数据导入页面增加“智能选股一键导入”工作流。入口可放在连接状态栏，与“重新检测”并列；一键导入按钮左侧提供数据起始日期和结束日期设置。工作流应按智能选股依赖顺序自动执行一组 Tushare API 导入任务，并将用户选择的时间段自动同步给所有需要日期范围的导入任务，同时提供进度、失败恢复和数据完整性检查。

## 智能选股因子到数据源映射

### 技术面与量价行情

| 因子 | 来源 | 需要的 Tushare/API 数据 |
|------|------|-------------------------|
| `ma_trend` | K 线计算 | `stock_basic`、`trade_cal`、`daily`、`adj_factor` |
| `ma_support` | K 线计算 | `daily`、`adj_factor` |
| `breakout` | K 线成交量和价格形态 | `daily`、`adj_factor` |
| `macd` | K 线计算 | `daily`、`adj_factor` |
| `boll` | K 线计算 | `daily`、`adj_factor` |
| `rsi` | K 线计算 | `daily`、`adj_factor` |
| `dma` | K 线计算 | `daily`、`adj_factor` |
| `turnover` | K 线辅助字段 | `daily_basic` 回填到 K 线，必要时依赖 `daily` |
| `volume_price` | 近 20 日成交额百分位 | `daily` |

### 技术专题因子

| 因子 | 来源 | 需要的 Tushare/API 数据 |
|------|------|-------------------------|
| `kdj_k`、`kdj_d` | `stk_factor` | `stk_factor_pro` |

### 基本面因子

| 因子 | 来源 | 需要的 Tushare/API 数据 |
|------|------|-------------------------|
| `roe`、`profit_growth`、`market_cap`、`pe` | `stock_info` 派生或基础表 | `daily_basic`、财务指标类接口；当前最小链路优先保证 `daily_basic` |
| `pe_ttm` | 旧内置策略配置字段 | 应识别为兼容风险，后续应统一到 `pe` 或保证 `pe_ttm` 字段可评估 |

### 资金流因子

| 因子 | 来源 | 需要的 Tushare/API 数据 |
|------|------|-------------------------|
| `money_flow` | `money_flow_value -> money_flow_pctl` | 推荐 `moneyflow_dc`，备选 `moneyflow_ths` |
| `large_order` | 大单/超大单金额占比 | `moneyflow_dc` 或 `moneyflow_ths` |
| `super_large_net_inflow` | 超大单净流入百分位 | `moneyflow_dc` 或 `moneyflow_ths` |
| `large_net_inflow` | 大单净流入百分位 | `moneyflow_dc` 或 `moneyflow_ths` |
| `small_net_outflow` | 小单净流出 | `moneyflow_dc` 或 `moneyflow_ths` |
| `money_flow_strength` | 资金流强度综合评分 | `moneyflow_dc` 或 `moneyflow_ths` |

### 板块面与指数专题

| 因子 | 来源 | 需要的 Tushare/API 数据 |
|------|------|-------------------------|
| `sector_rank`、`sector_trend` | 板块行情、板块成分映射 | `ths_index`/`dc_index` 等板块基础信息、`ths_member`/`dc_member` 等成分、`ths_daily`/`dc_daily` 等板块行情；默认优先 DC |
| `index_ma_trend` | 指数专题/K 线 | `index_basic`、`index_daily`、`idx_factor_pro` |

### 筹码、两融、打板

| 因子 | 来源 | 需要的 Tushare/API 数据 |
|------|------|-------------------------|
| `chip_winner_rate`、`chip_concentration` | 筹码专题 | `cyq_perf` |
| `margin_net_buy`、`rzrq_balance_trend` | 两融专题 | `margin_detail` |
| `limit_up_open_pct`、`limit_up_streak`、`first_limit_up` | 打板专题 | `limit_list_d`、`limit_step` |
| `dragon_tiger_net_buy` | 龙虎榜 | `top_list` |

## 推荐导入顺序

一键工作流 SHALL 按以下阶段顺序执行，避免下游依赖先于上游数据：

1. **基础证券和交易日历**
   - `stock_basic`
   - `trade_cal`

2. **股票日线主行情和复权因子**
   - `daily`
   - `adj_factor`

3. **日指标和 K 线辅助字段**
   - `daily_basic`
   - 该阶段完成后 SHOULD 触发已有 K 线辅助字段回填，保证 `turnover` 等字段可用。

4. **技术专题指标**
   - `stk_factor_pro`

5. **资金流专题**
   - 默认 `moneyflow_dc`
   - 可配置同时导入 `moneyflow_ths`
   - 旧 `moneyflow` 不作为默认工作流依赖。

6. **板块数据**
   - 默认 DC 数据源：板块基础信息、板块成分、`dc_daily`
   - 可选 THS/TDX/TI/CI 数据源导入；
   - 一键默认至少保证 `sector_rank/sector_trend` 使用的默认 DC 链路完整。

7. **指数专题**
   - `index_basic`
   - `index_daily`
   - `index_weight`
   - `index_dailybasic`
   - `idx_factor_pro`

8. **扩展专题因子**
   - `cyq_perf`
   - `margin_detail`
   - `limit_list_d`
   - `limit_step`
   - `top_list`

9. **完整性检查**
   - 检查最近交易日 K 线覆盖股票数；
   - 检查 `daily_basic` 对 K 线辅助字段的覆盖；
   - 检查 `moneyflow_dc` 最近可用日期和覆盖股票数；
   - 检查 `stk_factor` 最近可用日期和覆盖股票数；
   - 检查默认 DC 板块行情和成分映射覆盖；
   - 检查指数专题最近可用日期。

## Requirements

### Requirement 1：提供智能选股数据依赖清单

**User Story:** 作为量化交易员，我希望系统能明确告诉我智能选股策略依赖哪些行情和专题数据，这样我能判断 0 结果是策略逻辑过严还是数据缺失。

#### Acceptance Criteria

1. WHEN 用户查看智能选股一键导入工作流 THEN 系统 SHALL 展示工作流包含的阶段、接口列表和每个阶段服务的因子类别。
2. WHEN 系统生成工作流 THEN SHALL 覆盖当前内置/示例策略中使用到的技术、量价资金、板块、筹码、两融、打板、指数专题和基本面因子。
3. WHEN 存在旧策略字段如 `pe_ttm` 不在因子注册表中 THEN 系统 SHALL 在完整性检查或工作流说明中标记为兼容风险。
4. WHEN 后续新增策略或因子 THEN 工作流 SHOULD 能从因子注册表和策略示例自动推导依赖，避免硬编码遗漏。

### Requirement 2：连接状态栏增加日期范围和一键导入控制区

**User Story:** 作为量化交易员，我希望在 Tushare 数据导入页连接状态栏设置数据起止日期，并通过一组快捷按钮导入、暂停、恢复或停止工作流，这样每天 18:00 后可以一次性导入当天智能选股所需数据，也能安全中断长任务。

#### Acceptance Criteria

1. WHEN 用户进入 Tushare 数据导入页 THEN 连接状态栏 SHALL 展示数据起始日期、数据结束日期和工作流快捷按钮区，日期设置位于按钮区左侧。
2. WHEN 页面初始化 THEN 日期范围 SHALL 默认设置为最近一天，即 `start_date = end_date = 当前日期`（系统时区 Asia/Shanghai）。
3. WHEN 当前时间早于 18:00 且默认结束日期为当前日期 THEN 系统 SHOULD 提示当天 Tushare 数据可能尚未完整。
4. WHEN 用户查看工作流快捷按钮区 THEN 系统 SHALL 上下两排放置四个小按钮：一键导入、一键暂停、一键恢复、一键停止，每排两个按钮。
5. WHEN Tushare 未连接或必要 Token 缺失 THEN “一键导入” SHALL 禁用或提示缺失的 Token 等级。
6. WHEN 用户点击“一键导入” THEN 系统 SHALL 打开确认面板或弹窗，展示默认导入阶段、用户选择的数据范围和风险提示。
7. WHEN 用户确认执行 THEN 前端 SHALL 调用后端工作流启动接口，而不是在前端串行拼接多个单接口导入请求。
8. WHEN 工作流生成需要日期范围的导入步骤 THEN 系统 SHALL 将用户选择的 `start_date` 和 `end_date` 自动同步到该步骤参数。
9. WHEN 工作流生成不需要日期范围的导入步骤 THEN 系统 SHALL 不向该步骤强行注入日期参数。
10. WHEN 工作流处于运行中或排队中 THEN “一键暂停”和“一键停止” SHALL 可用。
11. WHEN 用户点击“一键暂停” THEN 系统 SHALL 停止当前子接口导入并阻止后续步骤启动，同时将工作流置为可恢复的 `paused` 状态。
12. WHEN 工作流处于 `paused` 或 `failed` 状态 THEN “一键恢复” SHALL 可用，并从未完成步骤继续。
13. WHEN 用户点击“一键停止” THEN 系统 SHALL 停止当前子接口导入并将工作流置为终止态 `stopped`，不再作为可恢复暂停状态处理。

### Requirement 3：后端提供工作流定义和执行接口

**User Story:** 作为系统维护者，我希望一键导入由后端统一编排，这样导入顺序、重试、停止和状态恢复都一致可靠。

#### Acceptance Criteria

1. WHEN 前端请求工作流定义 THEN 后端 SHALL 返回阶段列表、接口列表、默认参数、Token 要求和说明。
2. WHEN 前端启动工作流 THEN 后端 SHALL 创建一个工作流任务 ID，并按阶段顺序提交或执行接口导入。
3. WHEN 某一阶段包含多个互不依赖接口 THEN 后端 MAY 支持串行执行优先；未来可扩展安全并行。
4. WHEN 任一接口导入失败 THEN 工作流 SHALL 记录失败阶段、失败接口和错误信息，并根据策略决定继续或中止。
5. WHEN 用户停止工作流 THEN 系统 SHALL 停止尚未启动的后续阶段，并向正在运行的导入任务发送停止信号。
6. WHEN 用户暂停工作流 THEN 系统 SHALL 停止尚未启动的后续阶段，并向正在运行的导入任务发送停止信号，但保留恢复执行所需状态。

### Requirement 4：默认参数适合智能选股

**User Story:** 作为量化交易员，我希望默认导入参数能覆盖日常智能选股，而不是一次性导入过大的无关数据。

#### Acceptance Criteria

1. WHEN 用户执行日常增量一键导入 THEN 默认日期范围 SHALL 为最近一天，满足每天 18:00 后导入当天数据的常规流程。
2. WHEN 用户需要补导节假日或历史缺口 THEN 用户 SHALL 能手动调整起始日期和结束日期，系统 SHALL 将该范围同步到所有需要日期范围的导入步骤。
3. WHEN 用户执行首次初始化一键导入 THEN 系统 SHOULD 提供近 1 年快捷范围或初始化模式，满足 MA250、突破和回测预览需要。
4. WHEN 导入 `daily`、`adj_factor`、`daily_basic`、`stk_factor_pro`、`moneyflow_dc` 等全市场接口 THEN 系统 SHALL 使用已有分批策略，避免触发 Tushare 行数截断。
5. WHEN 导入指数专题 THEN 系统 SHALL 使用默认核心指数集合或全量指数策略，并能处理 `index_weight` 这类按指数分批接口。
6. WHEN 导入板块数据 THEN 默认 SHALL 优先导入 DC 链路；若用户策略选择 THS/TDX/TI/CI，工作流 SHOULD 提供可选扩展阶段。

### Requirement 5：可观测进度和完整性校验

**User Story:** 作为量化交易员，我希望一键导入过程中看到当前阶段、当前接口、完成数量和完整性结果，这样能判断是否可以执行智能选股。

#### Acceptance Criteria

1. WHEN 工作流运行中 THEN 前端 SHALL 展示整体进度、当前阶段、当前接口、已完成接口数、失败接口数。
2. WHEN 单个接口正在导入 THEN 前端 SHALL 能跳转或展开查看该接口原有导入任务状态。
3. WHEN 工作流完成 THEN 系统 SHALL 展示智能选股完整性摘要，包括 K 线、资金流、技术专题、板块、指数专题的最近日期和覆盖数。
4. WHEN 完整性检查发现关键数据缺失 THEN 系统 SHALL 给出具体缺失接口和建议重新导入阶段。
5. WHEN 工作流失败或暂停 THEN 用户 SHALL 能从失败或暂停阶段继续执行，而不是必须从第一阶段重来。

### Requirement 6：与现有导入系统兼容

**User Story:** 作为开发者，我希望一键导入复用现有 Tushare 注册表和 Celery 导入能力，避免维护两套导入逻辑。

#### Acceptance Criteria

1. WHEN 工作流执行单个 API 导入 THEN SHALL 复用现有 `/data/tushare/import` 背后的 `run_import` 能力或同等服务层逻辑。
2. WHEN 工作流查询 Token 和接口元数据 THEN SHALL 复用现有 Tushare registry、Token tier 和 health 检查。
3. WHEN 工作流写入导入历史 THEN SHALL 保留每个子任务原有 `tushare_import_log`，并新增工作流层级状态记录。
4. WHEN 现有单接口导入、批量导入和历史记录功能使用时 THEN SHALL 不受一键工作流影响。
5. WHEN 前端刷新页面 THEN SHALL 能恢复正在运行的工作流状态。

### Requirement 7：测试覆盖

**User Story:** 作为开发者，我希望工作流的阶段顺序、默认参数和前端入口都有测试覆盖，避免后续新增接口时破坏智能选股数据准备。

#### Acceptance Criteria

1. WHEN 运行后端测试 THEN SHALL 验证工作流定义包含关键接口：`stock_basic`、`trade_cal`、`daily`、`adj_factor`、`daily_basic`、`stk_factor_pro`、`moneyflow_dc`、板块 DC 链路、`index_daily`、`index_dailybasic`、`idx_factor_pro`、`cyq_perf`、`margin_detail`、`limit_list_d`、`limit_step`、`top_list`。
2. WHEN 运行后端测试 THEN SHALL 验证工作流阶段顺序满足依赖关系。
3. WHEN 运行后端测试 THEN SHALL 验证工作流启动、停止、失败记录和状态恢复。
4. WHEN 运行前端测试 THEN SHALL 验证连接状态栏展示一键导入、一键暂停、一键恢复、一键停止四个按钮。
5. WHEN 运行前端测试 THEN SHALL 验证连接状态栏展示数据起始日期和结束日期，并默认最近一天。
6. WHEN 运行前端测试 THEN SHALL 验证 Token 不满足时按钮禁用或提示。
7. WHEN 运行前端测试 THEN SHALL 验证用户确认后一键导入调用工作流启动接口并携带所选日期范围。
8. WHEN 运行前端测试 THEN SHALL 验证暂停、恢复、停止按钮按工作流状态启禁并调用对应接口。

### Requirement 8：后续优化观察池

**User Story:** 作为量化交易员，我希望工作流运行中的子接口进度展示能反映真实导入进展，而不是只显示最终落账行数，这样我能判断长时间运行的接口是否正常推进。

#### Acceptance Criteria

1. WHEN 工作流子接口处于 `running` 状态 THEN 前端 SHOULD 展示该子接口实时进度，例如 `completed / total`、失败数和当前处理对象。
2. WHEN 工作流状态接口返回子任务列表 THEN 后端 SHOULD 将运行中子任务的单接口 Redis 进度合并到 `child_tasks`，避免前端额外逐个请求。
3. WHEN 子接口尚未完成且 `record_count` 仍为 0 THEN 前端 SHOULD 避免仅展示 `0 行` 造成“没有导入”的误解。
4. WHEN 子接口完成 THEN 前端 SHALL 继续展示最终 `record_count`，并与现有导入历史保持一致。
5. WHEN 后续观察到其他一键导入可观测性问题 THEN SHOULD 追加到本需求下统一处理。
