# Tushare 每日智能选股快速导入工作流 Design

## 概览

本设计在现有“智能选股一键导入完整链路”之外，新增一个每日选股场景优先的快速导入方案。核心思想是把数据导入拆成四类：

1. **每日快速链路**：每天 18:00 后执行，只导入今日/最近交易日选股必要数据。
2. **缺口补导链路**：发现某接口缺少最近交易日时，只补缺口日期。
3. **周维护链路**：每周或手动执行低频基础数据和板块/指数成分。
4. **完整初始化链路**：保留现有完整工作流，用于首次初始化、历史修复和大范围补数。

该方案的目标不是减少数据完整性，而是把“当天必须更新”和“低频可维护”拆开，缩短每天等待选股的时间。

## 当前耗时评估

从 2026-04-30 晚间执行 `20260410` 至 `20260430` 的完整链路观察，主要耗时来自低频全量接口和多源扩展：

| 类型 | 代表接口 | 观察耗时 | 每日必要性评估 |
|------|----------|----------|----------------|
| 板块成分全量 | `dc_member` | 约 124.5 分钟 | 不应每日跑 |
| 板块成分全量 | `tdx_member` | 约 58.4 分钟 | 不应每日跑 |
| 行业成分全量 | `ci_index_member` | 约 47.3 分钟 | 不应每日跑 |
| 行业成分全量 | `index_member_all` | 约 46.8 分钟 | 不应每日跑 |
| 板块成分全量 | `ths_member` | 约 37.8 分钟 | 不应每日跑 |
| 资金流 | `moneyflow_dc` / `moneyflow_ths` | 各约 35.6 分钟（20 天） | 每日只跑必要源和缺口 |
| 日频行情 | `daily` / `adj_factor` / `daily_basic` | 各约 21-24 分钟（20 天） | 每日只跑最近交易日或缺口 |

关键判断：

- `dc_member` 等成分表是主要耗时源，但成分关系不需要每天完整刷新。
- `moneyflow_ths` 与 `moneyflow_dc` 同时跑会明显拉长日常链路，应默认只跑当前策略使用的数据源。
- `index_daily` 当前按全量指数推进，日常选股大多只需要核心指数和策略明确引用的指数集合。
- 当前完整工作流适合“补 20 天数据”，不适合作为每天默认路径。

## 推荐方案

### 方案 A：每日快速链路（默认推荐）

适用场景：每天 18:00 后准备当天智能选股。

默认执行：

| 阶段 | 接口 | 说明 |
|------|------|------|
| 交易日解析 | `trade_cal` 本地读取/必要时刷新 | 解析目标交易日，不默认全量导入 |
| 股票日频核心 | `daily` | 当日或缺口交易日 |
| 复权因子 | `adj_factor` | 当日或缺口交易日 |
| 日指标 | `daily_basic` | 当日或缺口交易日，并更新 `stock_info` 快照 |
| 技术专题 | `stk_factor_pro` | 当日或缺口交易日 |
| 资金流 | `moneyflow_dc` | 默认资金流来源；`moneyflow_ths` 默认关闭 |
| 默认板块行情 | `dc_daily` | 复用已有 `dc_member` 成分映射 |
| 核心指数 | `index_daily`、`index_dailybasic`、`idx_factor_pro` | 默认核心指数集合，不跑全量 8000 指数 |
| 完整性检查 | 无导入接口 | 检查关键表最新日期和覆盖数 |

按策略可选：

- 打板策略启用：追加 `limit_list_d`、`limit_step`。
- 龙虎榜策略启用：追加 `top_list`。
- 两融策略启用：追加 `margin_detail`。
- 筹码策略启用：追加 `cyq_perf`。
- THS 资金流策略启用：追加 `moneyflow_ths`。

默认跳过：

- `stock_basic`、`index_basic`、`dc_index` 等低频基础表；
- `dc_member`、`ths_member`、`tdx_member`、`index_member_all`、`ci_index_member` 等成分全量接口；
- 非当前策略数据源的板块/资金流扩展；
- 全量指数导入。

预期收益：

- 单日导入时，`daily/adj_factor/daily_basic/moneyflow` 的数据量约为 20 日补数的 1/10 到 1/20。
- 跳过 `dc_member`、`tdx_member`、`ci_index_member`、`index_member_all`、`ths_member` 可直接避免约 5 小时以上等待。
- 默认只保留 DC 资金流和 DC 板块行情，可避免重复专题源下载。

### 方案 B：缺口补导链路

适用场景：昨日导入失败、节假日前后漏导、服务中断后恢复。

执行逻辑：

1. 根据 `trade_cal` 解析目标交易日集合。
2. 对每个日频接口查询最近成功覆盖日期。
3. 若目标交易日已覆盖，则跳过。
4. 若缺口存在，则按缺失交易日生成最小日期范围。
5. 执行后再跑完整性检查。

示例：

- 当前日期为 2026-05-01，但 A 股休市；
- 最近交易日为 2026-04-30；
- `daily` 已覆盖 2026-04-30，`moneyflow_dc` 只覆盖到 2026-04-29；
- 本次只补 `moneyflow_dc` 的 2026-04-30，其他接口跳过。

### 方案 C：周维护链路

适用场景：周末、盘后空闲时段、发现静态数据过期。

建议执行：

| 类别 | 接口 |
|------|------|
| 基础证券 | `stock_basic`、`trade_cal` |
| 指数基础 | `index_basic` |
| DC 板块 | `dc_index`、`dc_member` |
| 可选 THS | `ths_index`、`ths_member` |
| 可选 TDX | `tdx_index`、`tdx_member` |
| 可选申万 | `index_classify`、`index_member_all` |
| 可选中信 | `ci_index_member` |

静态 TTL 建议：

- `stock_basic`：1 天到 7 天，可按是否出现新股/退市调整。
- `trade_cal`：30 天或每周维护。
- 板块/行业成分：7 天，或检测成分覆盖异常时提示。
- `index_basic`：7 天到 30 天。

### 方案 D：完整初始化链路

保留现有 `smart-screening` 完整工作流，适用：

- 首次初始化；
- 手动选择长日期范围补数；
- 更换数据源或新启用大量因子；
- 数据一致性修复；
- 周期性全链路审计。

## 后端设计建议

### 新增计划生成器

建议新增或扩展服务层计划生成能力：

```python
class TushareImportPlanMode(str, Enum):
    DAILY_FAST = "daily_fast"
    GAP_REPAIR = "gap_repair"
    WEEKLY_MAINTENANCE = "weekly_maintenance"
    FULL_INITIALIZE = "full_initialize"
```

计划生成器职责：

- 输入：目标日期、模式、启用策略/因子、数据源选项、强制刷新选项。
- 输出：`target_trade_date`、`execute_steps`、`skip_steps`、`maintenance_suggestions`、`estimated_cost`、`next_actions`。
- 每个 step 标记：
  - `api_name`
  - `reason`
  - `params`
  - `priority`
  - `estimated_rows`
  - `estimated_duration`
  - `skip_reason`

### 数据新鲜度检查

新增 freshness 检查：

| 数据类型 | 检查方式 |
|----------|----------|
| K 线/日频表 | 最近 `trade_date/time` 是否覆盖目标交易日 |
| 资金流 | 最近 `trade_date` 是否覆盖目标交易日，允许可配置回退 |
| 板块行情 | 最近行情日期是否覆盖目标交易日 |
| 板块成分 | `updated_at` 或最近导入日志是否在 TTL 内 |
| 基础表 | 最近成功导入日志是否在 TTL 内 |

### 核心指数集合

每日快速链路默认只导核心指数：

- `000001.SH`
- `399001.SZ`
- `399006.SZ`
- `000300.SH`
- `000905.SH`
- `000852.SH`

若策略或用户配置需要全量指数，再切换为扩展指数导入。

### 策略感知依赖

优先级建议：

1. 当前用户即将执行的策略；
2. 用户选中的策略模板集合；
3. 系统默认智能选股策略集合；
4. 全部内置策略。

这样每日快速导入可以避免为未使用因子下载 `cyq_perf`、`margin_detail`、`top_list` 等扩展数据。

## 前端设计建议

在 Tushare 导入页的一键导入区提供链路模式下拉框，放在日期范围和“一键导入”按钮附近。下拉框选项：

- `每日快速`
- `缺口补导`
- `周维护`
- `完整初始化`

默认值为 `每日快速`。用户点击“一键导入”时，系统按当前下拉框选择的链路生成计划并打开确认面板。

建议连接栏控件顺序：

1. 起始日期；
2. 结束日期；
3. 链路模式下拉框，默认“每日快速”；
4. 一键导入、一键暂停、一键恢复、一键停止按钮组。

确认面板展示三类列表：

1. **本次执行**：接口、日期范围、原因、预计耗时。
2. **本次跳过**：接口、跳过原因，例如“今日已覆盖”“静态数据未过期”“当前策略未使用”。
3. **建议维护**：低频数据过期、可选数据源未更新、完整性风险。

链路选择行为：

- `每日快速`：默认链路，每天 18:00 后用于当天或最近交易日选股数据更新。
- `缺口补导`：根据完整性检查或最近成功日期生成最小补导计划；若用户从每日快速的失败/不完整结果进入，应自动带入缺失接口和日期范围。
- `周维护`：刷新低频基础表、板块成分、行业成分和可选扩展成分。
- `完整初始化`：执行完整链路，用于首次初始化、历史区间补导或大型修复。

每日快速模式默认选项：

- 日期：最近交易日或用户选择日期。
- 资金流：默认 DC，可选 THS。
- 板块源：默认 DC，可选 THS/TDX/TI/CI，但默认不刷新成分。
- 扩展专题：按策略自动勾选，可手动覆盖。
- 静态刷新：默认关闭。

### 每日快速后的补导闭环

每日快速链路完成后必须执行完整性检查，并把结果直接转化为下一步动作建议：

| 完整性结果 | 推荐动作 |
|------------|----------|
| 关键日频数据完整 | 展示“每日选股数据已就绪” |
| 日频接口缺少目标交易日 | 建议切换到“缺口补导”，并自动带入缺失接口和日期 |
| 资金流缺少目标交易日 | 建议切换到“缺口补导”，默认补 `moneyflow_dc` 或当前策略资金流源 |
| 板块行情缺少目标交易日 | 建议切换到“缺口补导”，补默认板块行情 |
| 成分/基础表过期 | 建议切换到“周维护” |
| 多类数据大范围缺失 | 建议切换到“完整初始化”或提示用户缩小补导范围 |

用户从完整性结果进入缺口补导时，确认面板应显示“来自上一轮每日快速检查”的缺口来源，避免用户误以为重新跑全链路。

## API 设计建议

可新增或扩展现有工作流 API：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/data/tushare/workflows/smart-screening/plan` | 生成导入计划，不启动 |
| POST | `/data/tushare/workflows/smart-screening/start` | 增加 `mode=daily_fast/gap_repair/weekly_maintenance/full_initialize` |
| GET | `/data/tushare/workflows/status/{workflow_task_id}` | 返回执行、跳过、建议维护和耗时统计 |

计划请求示例：

```json
{
  "mode": "daily_fast",
  "target_date": "20260430",
  "strategy_scope": {
    "type": "selected_strategies",
    "strategy_ids": ["right-side-breakout"]
  },
  "options": {
    "moneyflow_source": "DC",
    "sector_sources": ["DC"],
    "include_static_refresh": false,
    "include_extended_topics": "strategy_aware"
  }
}
```

缺口补导请求可由每日快速结果自动生成：

```json
{
  "mode": "gap_repair",
  "target_date": "20260430",
  "repair_source_workflow_id": "previous-workflow-id",
  "repair_plan": {
    "missing_steps": [
      {"api_name": "moneyflow_dc", "start_date": "20260430", "end_date": "20260430"}
    ]
  }
}
```

计划响应示例：

```json
{
  "mode": "daily_fast",
  "target_trade_date": "20260430",
  "execute_steps": [
    {"api_name": "daily", "params": {"start_date": "20260430", "end_date": "20260430"}, "reason": "K线因子需要"},
    {"api_name": "daily_basic", "params": {"start_date": "20260430", "end_date": "20260430"}, "reason": "换手率/市值/估值需要"},
    {"api_name": "moneyflow_dc", "params": {"start_date": "20260430", "end_date": "20260430"}, "reason": "资金流因子需要"}
  ],
  "skip_steps": [
    {"api_name": "dc_member", "reason": "静态成分数据未过期"},
    {"api_name": "moneyflow_ths", "reason": "当前策略未选择 THS 资金流"}
  ],
  "maintenance_suggestions": [],
  "next_actions": [
    {"mode": "gap_repair", "label": "补齐缺口", "enabled": false},
    {"mode": "weekly_maintenance", "label": "执行周维护", "enabled": false}
  ]
}
```

## 风险与边界

| 风险 | 缓解 |
|------|------|
| 跳过静态成分导致板块映射过旧 | 增加 TTL 和完整性提醒，周维护补齐 |
| 策略感知依赖漏判 | 默认策略集保守覆盖，完整性检查兜底提示 |
| Tushare 当日数据未发布完整 | 18:00 前提示风险，支持稍后重新补导缺口 |
| 单日资金流仍较慢 | 默认只跑 DC，THS 后台可选或延后 |
| 指数全量导入拖慢 | 默认核心指数，策略需要时再扩展 |
| 用户手动选择长日期范围 | 自动切换到缺口补导或完整链路，并提示预计耗时 |

## 推荐结论

推荐新增“每日快速”作为连接栏一键导入的默认模式，完整链路降级为“完整初始化/修复”模式。

每日快速默认链路应满足绝大部分日常右侧选股：

1. `daily`
2. `adj_factor`
3. `daily_basic`
4. `stk_factor_pro`
5. `moneyflow_dc`
6. `dc_daily`
7. 核心指数 `index_daily` / `index_dailybasic` / `idx_factor_pro`
8. 按策略追加扩展专题

低频全量接口进入周维护，尤其是 `dc_member`、`tdx_member`、`ci_index_member`、`index_member_all`、`ths_member`。这是当前最有确定性的提速点。
