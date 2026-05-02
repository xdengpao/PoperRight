# K 线辅助字段回填可靠性修复任务

## 阶段 1：回填服务串行化与重试

- [x] 1. 扩展 `BackfillStats` 统计字段
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 增加 `retry_count`、`failed_batches` 字段，默认值为 0。
  - 确保现有调用方和测试可向后兼容。
  - 验证：现有回填测试仍可构造并读取统计对象。

- [x] 2. 增加 K 线辅助字段回填 advisory transaction lock
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 增加 `_KLINE_AUX_BACKFILL_LOCK_KEY` 常量。
  - 增加 `_acquire_backfill_lock(session)`，执行 `SELECT pg_advisory_xact_lock(:lock_key)`。
  - 在每个回填 batch 执行 UPDATE 前获取锁。
  - 验证：单元测试断言一次 batch 至少执行 lock SQL 和 update SQL。

- [x] 3. 增加 batch 级瞬时数据库异常重试
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 增加 `_BACKFILL_MAX_RETRIES`、`_BACKFILL_RETRY_BASE_DELAY`。
  - 增加 `_is_transient_db_error(exc)`。
  - 将 `_execute_stats_sql` 拆成 retry wrapper 与 single-attempt 执行函数。
  - 异常时 rollback；可重试异常退避后重试；不可重试异常直接抛出。
  - 验证：测试覆盖第一次 deadlock、第二次成功，并累加 `retry_count`。

- [x] 4. 保持回填幂等与空值保护
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 保留 `COALESCE` 与 `IS DISTINCT FROM` 更新条件。
  - 确认新增锁和重试不改变重复回填语义。
  - 验证：现有幂等测试通过。

## 阶段 2：导入 hook 可观测性增强

- [x] 5. 增加紧凑回填错误摘要
  - 文件：`app/tasks/tushare_import.py`
  - 增加 `_compact_backfill_error(exc)`。
  - 对 deadlock、connection closed 等常见异常输出短错误类型。
  - 其他异常仅保留首行和有限长度。
  - 验证：测试确认摘要不包含完整 SQL 或大段参数。

- [x] 6. 优化 `_run_post_write_hooks` 失败记录
  - 文件：`app/tasks/tushare_import.py`
  - hook 失败时继续 `logger.warning(..., exc_info=True)`。
  - `_record_backfill_hook_info` 只写入 `source_table`、日期范围、`source_rows`、`backfill_error` 等紧凑字段。
  - 主导入任务仍不因 hook 失败而失败。
  - 验证：失败 hook 测试仍确认不抛出异常。

- [x] 7. 增加 `kline_aux_backfill_summary`
  - 文件：`app/tasks/tushare_import.py`
  - 在 `_merge_backfill_hook_info` 中汇总 items、errors、matched_rows、updated_rows、retry_count、failed_batches。
  - 保留原 `kline_aux_backfill` 明细列表，保证兼容。
  - 验证：测试确认 summary 字段存在且统计正确。

## 阶段 3：测试与验证

- [x] 8. 更新服务单元测试
  - 文件：`tests/services/test_kline_aux_field_backfill.py`
  - 更新已有测试，适配 lock SQL 额外执行。
  - 新增 transient error retry 成功测试。
  - 新增不可重试异常直接失败测试。
  - 验证：该测试文件全部通过。

- [x] 9. 更新导入 hook 单元测试
  - 文件：`tests/tasks/test_tushare_import_kline_aux_backfill.py`
  - 更新 `_Stats` dataclass 字段。
  - 新增 compact error 测试。
  - 新增 summary 汇总测试。
  - 验证：该测试文件全部通过。

- [x] 10. 运行相关测试
  - 命令：
    ```bash
    /Users/poper/ContestTrade/yes/bin/pytest \
      tests/services/test_kline_aux_field_backfill.py \
      tests/tasks/test_tushare_import_kline_aux_backfill.py
    ```
  - 视情况补跑：
    ```bash
    /Users/poper/ContestTrade/yes/bin/pytest \
      tests/tasks/test_tushare_import_by_trade_date.py \
      tests/integration/test_tushare_truncation_retry.py
    ```
  - 验证：测试通过或记录失败原因。

- [x] 11. 执行代码质量自检
  - 文件：`.kiro/hooks/code-quality-review.kiro.hook`
  - 按 hook 检查新增逻辑是否有复杂度、重复、命名和可维护性问题。
  - 验证：自检通过；如发现问题，修复后再检查。

## 阶段 4：运行后确认

- [x] 12. 重启服务并提示补跑回填/导入策略
  - 重启 Celery worker 使回填锁和重试逻辑生效。
  - 建议后续等待 `daily_basic` 当前导入完成；如仍有缺口，再按需补跑 `stk_limit` 或小范围重导 `daily_basic`。
  - 验证：Backend `/health` 返回 `{"status":"ok","env":"development"}`；前端返回 HTTP 200；Celery worker 日志显示 `celery@bogon ready.`。

- [x] 13. 提供验证 SQL
  - 提供按个股日 K 统计 `turnover/vol_ratio/limit_up/limit_down` 覆盖率的 SQL。
  - 明确指数/非个股 K 线辅助字段为空属于正常情况。
  - 验证：用户可用以下 SQL 判断补齐效果。

```sql
select time::date as trade_date,
       count(*) as stock_kline_rows,
       count(turnover) as turnover_rows,
       count(vol_ratio) as vol_ratio_rows,
       count(limit_up) as limit_up_rows,
       count(limit_down) as limit_down_rows
from kline
where freq = '1d'
  and adj_type = 0
  and time >= timestamp '2026-04-20'
  and time < timestamp '2026-05-01'
  and (
    symbol like '000%.SZ' or symbol like '001%.SZ' or symbol like '002%.SZ' or
    symbol like '003%.SZ' or symbol like '300%.SZ' or symbol like '301%.SZ' or
    symbol like '600%.SH' or symbol like '601%.SH' or symbol like '603%.SH' or
    symbol like '605%.SH' or symbol like '688%.SH'
  )
group by time::date
order by trade_date desc;
```
