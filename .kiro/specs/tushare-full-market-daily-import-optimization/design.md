# 设计文档：Tushare 日级全市场导入性能优化

## 概览

本设计为 `stk_factor_pro`、`daily_basic`、`stk_limit` 增加“按交易日全市场导入”路径，解决当前通用路由把它们误判成 `by_code_and_date` 的性能问题。

核心思路：

1. 在 Tushare registry 中用显式配置标记“日级全市场接口”。
2. 在分批路由中优先识别该配置：未传 `ts_code` 且有日期范围时返回 `by_trade_date`。
3. `by_trade_date` 使用 `trade_calendar` 解析真实交易日，逐交易日全市场调用 Tushare。
4. `daily_basic` 通过写入策略保护 `stock_info`：历史日期只用于 Kline 辅助字段回填，只有市场最近可用交易日或用户显式开关才更新当前指标。
5. 复用已有 `KlineAuxFieldBackfillService`，确保 `daily_basic` / `stk_limit` 的导入 hook 行为不丢失。

本设计不重做整个 Tushare 导入框架，仍保留注册表驱动、Celery 任务、Redis 进度、批量写库、post-write hook 的现有架构。

## 当前问题定位

### 路由误判

当前 `determine_batch_strategy()` 的关键逻辑是：

- 如果接口支持 `STOCK_CODE` 且用户未传 `ts_code`，则自动启用 `batch_by_code`
- 如果同时 `batch_by_date=True` 且有 `start_date/end_date`，则返回 `by_code_and_date`

`stk_factor_pro`、`daily_basic`、`stk_limit` 都符合：

- `optional_params=[ParamType.STOCK_CODE]`
- `batch_by_date=True`
- `date_chunk_days=1`

因此全市场历史导入变成：

```text
股票数 × 日期数
```

而这三类接口实际更适合：

```text
交易日数
```

### `daily_basic` 语义问题

`daily_basic` 当前写入 `stock_info`，冲突键是 `symbol`，更新字段是 `pe_ttm`、`pb`、`market_cap`、`updated_at`。这适合保存“当前指标快照”，但不适合大范围历史导入：

- 导入历史旧日期时，会用旧指标覆盖当前指标
- 历史数据没有独立明细表可查询
- 但导入 rows 又是回填 `kline.turnover` / `kline.vol_ratio` 的必要来源

因此本设计短期采用“rows 回填 + 当前指标保护”，长期预留 `daily_basic_history`。

## 架构图

```mermaid
flowchart TD
    UI[TushareImportView] --> API[/api/v1/data/tushare/import]
    API --> SVC[TushareImportService.start_import]
    SVC --> CELERY[Celery data_sync queue]
    CELERY --> TASK[run_import/_process_import]

    TASK --> ROUTE[determine_batch_strategy]
    ROUTE --> BTD[by_trade_date]
    ROUTE --> OLD[existing by_code/by_date/by_code_and_date]

    BTD --> CAL[TradeDateResolver]
    CAL --> TC[(PostgreSQL.trade_calendar)]
    CAL --> DATES[交易日列表]
    DATES --> CALL[Tushare API 每交易日一次]
    CALL --> MAP[字段映射/代码转换]
    MAP --> POLICY[写入策略]

    POLICY --> STKF[(PostgreSQL.stk_factor)]
    POLICY --> SLIM[(PostgreSQL.stk_limit)]
    POLICY --> SINFO[(PostgreSQL.stock_info 当前指标)]

    CALL --> HOOK[post-write hooks]
    HOOK --> BACKFILL[KlineAuxFieldBackfillService]
    BACKFILL --> KLINE[(TimescaleDB.kline)]

    TASK --> REDIS[(Redis progress)]
    TASK --> LOG[(tushare_import_log.extra_info)]
```

## Registry 设计

文件：`app/services/data_engine/tushare_registry.py`

### ApiEntry 扩展方式

优先使用现有 `extra_config`，避免扩大 dataclass 字段面：

```python
extra_config={
    "full_market_by_trade_date": True,
    "date_param": "trade_date",
    "max_rows": 10000,
    "estimated_daily_rows": 5500,
}
```

字段含义：

| key | 含义 |
| --- | --- |
| `full_market_by_trade_date` | 未传 `ts_code` 时优先按交易日全市场导入 |
| `date_param` | 单日调用使用的日期参数名，默认 `trade_date` |
| `max_rows` | 单次返回行数上限，用于截断风险判断 |
| `estimated_daily_rows` | 每日预估行数，用于配置预检查和日志 |
| `primary_write_policy` | 主表写入策略，`daily_basic` 使用 `latest_market_trade_date_only` |
| `update_current_snapshot_param` | 允许用户显式更新当前快照的参数名，默认 `update_current_snapshot` |

### 目标接口配置

`stk_factor_pro`：

```python
extra_config={
    "full_market_by_trade_date": True,
    "date_param": "trade_date",
    "max_rows": 10000,
    "estimated_daily_rows": 5500,
}
```

同时补齐 `update_columns`：

```python
["wr", "dmi", "trix", "bias"]
```

`stk_limit`：

```python
extra_config={
    "full_market_by_trade_date": True,
    "date_param": "trade_date",
    "max_rows": 10000,
    "estimated_daily_rows": 5500,
}
```

`daily_basic`：

```python
extra_config={
    "full_market_by_trade_date": True,
    "date_param": "trade_date",
    "max_rows": 10000,
    "estimated_daily_rows": 5500,
    "primary_write_policy": "latest_market_trade_date_only",
    "update_current_snapshot_param": "update_current_snapshot",
}
```

说明：

- `daily_basic` 的 post-write hook 仍对每个交易日 rows 执行，用于回填 Kline。
- `stock_info` 主表更新只在当前交易日等于市场最近可用交易日，或用户显式传入 `update_current_snapshot=true` 时执行，避免旧历史区间最后一天覆盖当前指标。

## 分批路由设计

文件：`app/tasks/tushare_import.py`

### 策略新增

新增策略名：

```python
"by_trade_date"
```

### 路由优先级

在当前 `batch_by_code` 自动推断之前插入：

```python
if (
    entry.extra_config.get("full_market_by_trade_date")
    and has_date_params
    and not has_ts_code
):
    return "by_trade_date"
```

保留兼容：

- 用户显式传 `ts_code`：继续走现有 `by_date` 或单代码导入路径
- 未配置 `full_market_by_trade_date` 的接口：不改变现有策略
- 已有 `by_sector` 仍保持最高优先级

### `_process_import` 分发

新增分支：

```python
elif strategy == "by_trade_date":
    result = await _process_batched_by_trade_date(
        entry, adapter, params, task_id, log_id, rate_delay
    )
```

## 交易日解析设计

新增辅助函数，文件可放在 `app/tasks/tushare_import.py`，后续若复用扩大再抽到 `app/services/data_engine/trade_date_resolver.py`。

```python
async def _resolve_trade_dates(start_date: str, end_date: str) -> tuple[list[str], bool]:
    ...
```

返回：

- `trade_dates`: `YYYYMMDD` 字符串列表，升序
- `used_calendar`: 是否使用了 `trade_calendar`

查询逻辑：

```sql
SELECT cal_date
FROM trade_calendar
WHERE exchange IN ('SSE', 'SZSE', '')
  AND is_open = true
  AND cal_date >= :start
  AND cal_date <= :end
ORDER BY cal_date
```

去重：

- 如果 SSE/SZSE 都有同一交易日，只保留一个日期

兜底逻辑：

- 如果查询不到交易日历，生成 `start_date~end_date` 的自然日列表
- 记录 warning：交易日历缺失，使用自然日兜底，可能产生空请求

选择自然日兜底而不是工作日兜底的原因：

- 避免漏掉特殊调休交易日
- 空请求比漏数据更可接受

## `by_trade_date` 执行流程

新增函数：

```python
async def _process_batched_by_trade_date(
    entry: ApiEntry,
    adapter: TushareAdapter,
    params: dict,
    task_id: str,
    log_id: int,
    rate_delay: float,
) -> dict:
    ...
```

流程：

1. 读取 `start_date/end_date`
2. 调用 `_resolve_trade_dates()`
3. 初始化 Redis 进度：
   - `batch_mode="by_trade_date"`
   - `total=len(trade_dates)`
   - `completed=0`
4. 逐交易日执行：
   - 检查停止信号
   - 构造 API 参数
   - 调用 Tushare API
   - rows 非空时字段映射、代码转换、写库
   - 执行或复用 post-write hook
   - 更新统计与 Redis 进度
   - sleep `rate_delay`
5. 返回 `batch_stats`

单日 API 参数：

```python
call_params = {
    **entry.extra_config.get("default_params", {}),
    **params_without_date_range,
    date_param: trade_date,
}
```

其中 `params_without_date_range` 移除：

- `start_date`
- `end_date`

避免同时传 `trade_date` 和日期范围造成 Tushare 行为不明确。

统计字段：

```python
{
    "batch_mode": "by_trade_date",
    "planned_trade_dates": len(trade_dates),
    "success_trade_dates": success_count,
    "empty_trade_dates": empty_count,
    "failed_trade_dates": failed_count,
    "used_trade_calendar": used_calendar,
    "record_count": total_records,
    "api_rows": total_api_rows,
    "primary_written_rows": primary_written_rows,
    "truncation_count": len(truncation_warnings),
    "failed_dates": failed_dates[:100],
}
```

统计口径：

- `record_count` / `api_rows`：Tushare 返回的有效 rows 数，用于衡量本次接口拉取规模
- `primary_written_rows`：实际写入主表的 rows 数；`daily_basic` 历史日期可能为 0
- `kline_aux_backfill`：由现有 hook 记录 Kline 回填统计，与主表写入统计分开

## 写入策略设计

### 统一写入上下文

新增轻量上下文：

```python
@dataclass
class WriteContext:
    batch_mode: str
    current_trade_date: str | None = None
    latest_trade_date: str | None = None
```

新增统一入口：

```python
async def _write_rows_with_policy(
    raw_rows: list[dict],
    entry: ApiEntry,
    context: WriteContext,
) -> int:
    ...
```

职责：

1. 执行 `inject_fields`
2. 执行字段映射、展开、代码转换
3. 根据 `entry.extra_config.primary_write_policy` 决定是否写主表
4. 确保 `daily_basic` / `stk_limit` hook 行为符合预期

### `primary_write_policy`

默认：

```python
"always"
```

`daily_basic`：

```python
"latest_market_trade_date_only"
```

判断：

```python
should_write_primary = (
    policy != "latest_market_trade_date_only"
    or context.current_trade_date == context.latest_market_trade_date
    or context.update_current_snapshot is True
)
```

hook 策略：

- `daily_basic`：无论是否写 `stock_info`，都要用 raw rows 回填 `kline.turnover/vol_ratio`
- `stk_limit`：主表写入后复用现有 `_write_to_postgresql()` 内部 hook；如果未来跳过主表，也需要直接调用 hook
- `stk_factor_pro`：无 hook，只写 `stk_factor`

### 避免 hook 重复执行

当前 `_write_to_postgresql()` 会在 commit 后调用 `_run_post_write_hooks(rows, entry)`。为避免 `by_trade_date` 路径重复 hook，设计两种可选实现：

优先实现：

```python
async def _write_to_postgresql(rows, entry, run_post_hooks: bool = True)
```

默认 `True` 保持兼容；新统一入口可控制：

- 主表写入且需要 hook：`run_post_hooks=True`
- 主表跳过但需要 hook：直接调用 `_run_post_write_hooks(raw_rows, entry)`
- 已手动 hook：`run_post_hooks=False`

## `daily_basic` 历史语义设计

### 本次实施范围

本次实施不强制新增 `daily_basic_history` 表，先完成：

1. 全市场按交易日导入
2. 每个交易日 rows 回填 `kline.turnover/vol_ratio`
3. 只有市场最近可用交易日，或用户显式传入 `update_current_snapshot=true` 时，才更新 `stock_info` 当前指标

示例：

导入 `20260101~20260429`：

- `20260102` 等历史交易日：只回填 Kline，不更新 `stock_info.pe_ttm/pb/market_cap`
- 如果 `20260429` 是市场最近可用交易日：回填 Kline，并更新 `stock_info` 当前指标
- 如果 `20260429` 不是市场最近可用交易日：只回填 Kline，不更新 `stock_info`

如果用户导入旧区间 `20240101~20240131`：

- 默认所有交易日都不更新 `stock_info`，只回填 Kline
- 若用户明确希望用旧区间最后一天覆盖当前快照，可传入显式开关：

```python
params["update_current_snapshot"] = True
```

系统识别市场最近可用交易日的方式：

- 优先使用 `trade_calendar` 中不晚于当前日期且 `is_open=true` 的最大日期
- 如果交易日历缺失，则使用本次计划交易日列表的最大日期，但记录 warning；这种兜底只影响是否更新当前快照，不影响 Kline 回填

### 后续历史表方案

后续可新增：

```text
daily_basic_history
```

建议字段：

- `id`
- `ts_code`
- `trade_date`
- `turnover_rate`
- `volume_ratio`
- `pe`
- `pe_ttm`
- `pb`
- `ps`
- `ps_ttm`
- `dv_ratio`
- `dv_ttm`
- `total_share`
- `float_share`
- `free_share`
- `total_mv`
- `circ_mv`

唯一约束：

```sql
UNIQUE (ts_code, trade_date)
```

迁移策略：

- 将 `daily_basic` registry 的 `target_table` 改为 `daily_basic_history`
- 增加独立 hook 或后置同步，只把最新交易日快照同步到 `stock_info`
- `TusharePreviewService` 可直接预览历史每日指标

## 截断检测设计

现有 `_TUSHARE_MAX_ROWS=3000` 是通用默认值，不适合 `stk_factor_pro` 这类全市场接口。

`by_trade_date` 使用：

```python
max_rows = entry.extra_config.get("max_rows", _TUSHARE_MAX_ROWS)
```

当 `len(rows) >= max_rows`：

- 记录 warning
- `truncation_warnings.append({"trade_date": trade_date, "rows": len(rows), "max_rows": max_rows})`
- 不自动按股票拆分，避免又退回超高请求量

后续如需二级拆分，可增加：

```python
extra_config["truncate_split_by"] = "exchange"
```

但本次不实现。

## 进度与日志设计

Redis 进度新增/复用字段：

```json
{
  "status": "running",
  "total": 80,
  "completed": 12,
  "current_item": "20260120",
  "batch_mode": "by_trade_date"
}
```

任务开始日志：

```text
Tushare 导入开始 api=stk_factor_pro batch_mode=by_trade_date dates=80 range=20260101~20260429 used_calendar=true
```

导入完成 `extra_info`：

```json
{
  "batch_mode": "by_trade_date",
  "planned_trade_dates": 80,
  "success_trade_dates": 78,
  "empty_trade_dates": 2,
  "failed_trade_dates": 0,
  "used_trade_calendar": true,
  "record_count": 438000,
  "api_rows": 438000,
  "primary_written_rows": 5531,
  "kline_aux_backfill": [...]
}
```

## 测试设计

### 单元测试

文件：`tests/tasks/test_tushare_import_strategy.py` 或现有相关测试文件

覆盖：

- `stk_factor_pro` 未传 `ts_code`：返回 `by_trade_date`
- `daily_basic` 未传 `ts_code`：返回 `by_trade_date`
- `stk_limit` 未传 `ts_code`：返回 `by_trade_date`
- 显式传 `ts_code`：不返回 `by_trade_date`
- 未配置 `full_market_by_trade_date` 的接口：保持现有策略

文件：`tests/tasks/test_tushare_import_trade_dates.py`

覆盖：

- 有 `trade_calendar` 数据时只返回 `is_open=True` 日期
- SSE/SZSE 重复日期去重
- 无日历数据时返回自然日兜底并记录 warning
- 日期升序

文件：`tests/tasks/test_tushare_import_by_trade_date.py`

覆盖：

- 三个交易日只调用三次 API
- 每次调用参数使用 `trade_date`
- 不传 `start_date/end_date` 到单日 API
- Redis 进度 total 等于交易日数量
- 空 rows 计入 `empty_trade_dates`
- API 异常计入 `failed_trade_dates` 并继续后续日期

文件：`tests/tasks/test_tushare_import_daily_basic_policy.py`

覆盖：

- `daily_basic` 历史交易日不写 `stock_info`
- `daily_basic` 市场最近可用交易日写 `stock_info`
- `daily_basic` 旧区间最后一天不写 `stock_info`
- `daily_basic` 显式 `update_current_snapshot=true` 时允许写 `stock_info`
- 历史交易日仍调用 `backfill_daily_basic_rows`
- hook 失败不影响主流程

### 回归测试

扩展现有：

- `tests/tasks/test_tushare_import_kline_aux_backfill.py`
- `tests/tasks/test_truncation_detection.py`

新增断言：

- `stk_factor_pro.update_columns` 包含 `wr/dmi/trix/bias`
- `extra_config.max_rows` 被读取，而不是固定 3000

### 验证命令

定向后端测试：

```bash
pytest tests/tasks/test_tushare_import_strategy.py \
       tests/tasks/test_tushare_import_trade_dates.py \
       tests/tasks/test_tushare_import_by_trade_date.py \
       tests/tasks/test_tushare_import_daily_basic_policy.py
```

真实库 dry-run 或小范围导入验证：

```text
范围：最近 3 个交易日
接口：stk_factor_pro / daily_basic / stk_limit
期望：计划请求数 = 3，而不是 5531 × 3
```

数据库覆盖率验证：

```sql
SELECT trade_date, COUNT(*) FROM stk_factor GROUP BY trade_date ORDER BY trade_date DESC LIMIT 5;
```

```sql
SELECT
  COUNT(*) AS rows,
  COUNT(turnover) AS turnover_non_null,
  COUNT(vol_ratio) AS vol_ratio_non_null,
  COUNT(limit_up) AS limit_up_non_null,
  COUNT(limit_down) AS limit_down_non_null
FROM kline
WHERE freq='1d'
  AND adj_type=0
  AND time >= :latest_trade_date
  AND time < :latest_trade_date + INTERVAL '1 day';
```

## 向后兼容

- 未配置 `full_market_by_trade_date` 的接口不受影响。
- 显式传 `ts_code` 的导入请求仍走原有路径。
- `_write_to_postgresql()` 默认行为保持执行 post-write hook，避免旧调用方漏 hook。
- `daily_basic` 当前仍可更新 `stock_info`，但新全市场历史路径会限制更新时机。
- 前端无需立即调整；`batch_mode` 只是新增可观测值。

## 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Tushare 某接口单日全市场返回超过上限 | 单日数据可能截断 | 配置 `max_rows`，记录截断 warning；后续再加二级拆分 |
| `trade_calendar` 缺失 | 可能产生自然日空请求 | warning + 自然日兜底，不漏数据 |
| `daily_basic` 旧区间更新 `stock_info` | 当前指标回退 | `primary_write_policy` 限制为市场最近可用交易日；显式开关才允许覆盖 |
| hook 执行耗时 | 单日导入变慢 | 保持批量 SQL；hook 失败不回滚主导入 |
| 任务队列已有长任务阻塞 | 新任务 pending 看似卡住 | 保持 pending/running 可观测，日志输出任务开始信息 |
