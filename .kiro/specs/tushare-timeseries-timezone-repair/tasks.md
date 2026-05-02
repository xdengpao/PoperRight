# Tushare 时序数据日期时区修复 Tasks

## 阶段 1：入口修复

- [x] 1. 增加统一 Tushare 交易日 UTC 解析函数
  - 文件：`app/tasks/tushare_import.py`
  - 新增 `_parse_tushare_trade_date_utc(value)`。
  - 新增 `_parse_tushare_datetime_utc(value)` 与 `_normalize_tushare_timeseries_time(row, freq)`。
  - 支持 `YYYYMMDD`、`YYYY-MM-DD`、`date`、aware/naive `datetime`。
  - 分钟级优先解析 `trade_time/time/datetime/trade_datetime` 等具体时间字段。
  - 无效值返回 `None`，不抛出到导入主流程。
  - 验证：单元测试断言 `20260429 -> 2026-04-29T00:00:00+00:00`。
  - 需求：1.1、1.3、1.4、5.1。

- [x] 2. 增加日级/分钟级频率判断与运行时 `freq` 传递
  - 文件：`app/tasks/tushare_import.py`
  - 新增 `_is_intraday_freq(freq)` 或等价纯函数。
  - 明确 `1d/1w/1M` 为日级，分钟频率不进入历史日级偏移校正。
  - 给 `WriteContext` 增加 `runtime_freq`，并从 `params/call_params` 透传到 `_write_to_timescaledb`。
  - `_write_to_timescaledb` 频率优先级：运行时 `freq` > `entry.extra_config.freq` > `1d`。
  - 验证：覆盖典型日级/分钟级频率测试，并断言分钟接口不会默认写成 `1d`。
  - 需求：1.3、2.1、3.5、5.5。

- [x] 3. 修复 `_write_to_kline` 的 naive datetime 写入
  - 文件：`app/tasks/tushare_import.py`
  - 将内联 `datetime.strptime(..., "%Y%m%d")` 替换为 `_normalize_tushare_timeseries_time(row, freq)`。
  - 保持现有字段映射、代码转换、批量写入、逐行降级、`ON CONFLICT DO UPDATE` 语义不变。
  - 验证：mock `AsyncSessionTS.execute`，断言写入参数 `time.tzinfo` 为 UTC。
  - 需求：1.1、2.1、5.1。

- [x] 4. 修复 `_write_to_sector_kline` 的 naive datetime 写入
  - 文件：`app/tasks/tushare_import.py`
  - 复用 `_normalize_tushare_timeseries_time(row, freq)`。
  - 保持 `sector_code/data_source/freq/time` 唯一键和字段更新语义不变。
  - 验证：mock `AsyncSessionTS.execute`，断言板块 K 线写入参数为 UTC aware datetime。
  - 需求：1.2、2.2、5.2。

- [x] 5. 明确 `adjustment_factor` 不做 datetime 转换
  - 文件：`app/tasks/tushare_import.py`
  - 保持 `_write_to_adjustment_factor` 使用 Python `date`。
  - 补测试锁定该行为。
  - 验证：测试断言 `trade_date` 参数是 `date` 对象，不是 `datetime`。
  - 需求：2.3、5.3。

## 阶段 2：历史校正工具

- [x] 6. 新增历史时区偏移修复脚本框架
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 支持 CLI 参数：`--table`、`--start-date`、`--end-date`、`--freq`、`--batch-days`、`--dry-run`、`--execute`。
  - 默认 dry-run，未传 `--execute` 不写库。
  - 验证：参数解析测试或脚本 `--help` 正常。
  - 需求：6.1、6.2。

- [x] 7. 实现日期范围与批次拆分
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 支持 `YYYYMMDD` 与 `YYYY-MM-DD`。
  - 将闭区间按 `--batch-days` 拆成小批次。
  - 非法范围直接退出并给出清晰错误。
  - 验证：单元测试覆盖正常范围、反向范围、非法日期。
  - 需求：6.2、6.3。

- [x] 8. 实现 `kline` dry-run 诊断 SQL
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 统计候选偏移行数、冲突行数、可移动行数、样例记录。
  - `kline.time` 是 `TIMESTAMPTZ`，小时判断使用 `extract(hour from time at time zone 'UTC')`。
  - SQL 必须带日期范围与频率条件，避免全表聚合。
  - 验证：dry-run 不执行 `UPDATE/DELETE`，输出包含候选/冲突/样例。
  - 需求：3.1、5.4、6.1。

- [x] 9. 实现 `sector_kline` dry-run 诊断 SQL
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 使用 `sector_code/data_source/freq/time` 判断冲突。
  - `sector_kline.time` 当前是 `timestamp without time zone`，小时判断使用 `extract(hour from time)`。
  - SQL 必须带日期范围与频率条件。
  - 验证：dry-run 不执行 `UPDATE/DELETE`，输出板块样例。
  - 需求：3.4、5.4、6.1。

- [x] 10. 实现 `kline` 执行校正
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 对目标主键不存在的偏移记录执行 `time = time + interval '8 hours'`。
  - 对目标主键已存在的冲突记录，保留目标非空字段，仅用偏移记录非空字段补齐目标空值，再删除偏移记录。
  - 每批独立事务，失败回滚当前批。
  - 验证：脚本测试或测试库样例确认冲突/非冲突路径均正确。
  - 需求：3.1、3.2、6.3。

- [x] 11. 实现 `sector_kline` 执行校正
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 对目标主键不存在的偏移记录移动时间。
  - 对冲突记录保留目标非空字段，仅用偏移记录补齐 `open/high/low/close/volume/amount/turnover/change_pct` 空值。
  - 每批独立事务，失败回滚当前批。
  - 验证：测试库样例确认冲突/非冲突路径均正确。
  - 需求：3.4、6.3。

- [x] 12. 增加校正后验证输出
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 输出校正前后剩余偏移候选数。
  - 输出目标交易日覆盖率 SQL 或覆盖率统计。
  - 对 `kline` 输出辅助字段补跑建议。
  - 验证：执行 dry-run 和 execute 后均有清晰报告。
  - 需求：4.2、4.3、6.4。

## 阶段 3：辅助字段回填与验证

- [x] 13. 校正后复用现有 `stk_limit` 历史回填
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 确认 `backfill_stk_limit_table(start_date, end_date)` 可用于校正后补跑。
  - 如发现日期格式不兼容，仅做最小修正。
  - 验证：相关现有测试通过。
  - 需求：3.3、4.1。

- [x] 14. 明确 `daily_basic` 补跑策略
  - 文件：`.kiro/specs/tushare-timeseries-timezone-repair/design.md` 或运维输出。
  - 由于 `daily_basic` 历史主表当前不完整持久化，校正后通过重跑指定日期范围触发 hook 回填。
  - 在最终运行手册中写明推荐命令或前端操作顺序。
  - 验证：2026-04-29 重跑后 `matched_rows > 0`。
  - 需求：3.3、4.1、4.3。

- [x] 15. 提供并验证 2026-04-29 覆盖率 SQL
  - 文件：`.kiro/specs/tushare-timeseries-timezone-repair/tasks.md` 或最终报告。
  - SQL 统计个股 `daily` K 线行数与 `turnover/vol_ratio/limit_up/limit_down` 覆盖行数。
  - 验证：修复后 2026-04-29 覆盖率与 2026-04-28 同量级。
  - 需求：4.3、5.4。

## 阶段 4：测试

- [x] 16. 新增/更新 Tushare 时区单元测试
  - 文件：`tests/tasks/test_tushare_import_timezone.py` 或现有 `tests/tasks/test_tushare_import_timefreqfix.py`。
  - 覆盖 `_parse_tushare_trade_date_utc`、`_parse_tushare_datetime_utc`、`_normalize_tushare_timeseries_time`、运行时 `freq` 透传、`_write_to_kline`、`_write_to_sector_kline`、`_write_to_adjustment_factor`。
  - 验证：测试文件全部通过。
  - 需求：1.3、5.1、5.2、5.3。

- [x] 17. 新增历史修复脚本测试
  - 文件：`tests/scripts/test_repair_tushare_timeseries_timezone.py`。
  - 覆盖 dry-run、execute=false、日期解析、批次拆分、SQL 参数。
  - 验证：脚本测试通过，且不会连接真实生产库。
  - 需求：5.4、6.1、6.2、6.3。

- [x] 18. 跑 Tushare 导入相关回归测试
  - 命令：
    ```bash
    /Users/poper/ContestTrade/yes/bin/pytest \
      tests/tasks/test_tushare_import_timezone.py \
      tests/tasks/test_tushare_import_timefreqfix.py \
      tests/tasks/test_tushare_import_by_trade_date.py \
      tests/tasks/test_tushare_import_kline_aux_backfill.py
    ```
  - 如新增测试文件，追加到命令。
  - 验证：全部通过；如有既有失败，记录与本次变更关系。
  - 需求：5.5。

- [x] 19. 执行代码质量自检
  - 文件：`.kiro/hooks/code-quality-review.kiro.hook`
  - 检查是否存在重复日期解析逻辑、隐藏 naive datetime、过重 SQL、事务风险。
  - 验证：自检通过或记录修复项。
  - 需求：5.5、6.3。

## 阶段 5：运行与修复数据

- [x] 20. 部署入口修复并重启服务
  - 重启 Celery worker，使 Tushare 新写入逻辑生效。
  - 验证：worker ready；backend health 正常。
  - 已执行：backend、celery-worker、celery-beat、frontend 均已重启；Tushare health 返回 connected=true。
  - 需求：1、2。

- [x] 21. 执行 `kline` dry-run
  - 示例：
    ```bash
    /Users/poper/ContestTrade/yes/bin/python scripts/repair_tushare_timeseries_timezone.py \
      --table kline \
      --start-date 2026-04-01 \
      --end-date 2026-04-30 \
      --freq 1d \
      --dry-run
    ```
  - 验证：输出候选、冲突、可移动行数和样例。
  - 已执行：2026-04-29 dry-run，候选 5462、冲突 0、可移动 5462。
  - 需求：6.1。

- [x] 22. 执行 `kline` 历史校正
  - dry-run 确认后执行 `--execute`。
  - 按小日期范围分批，避免长事务。
  - 验证：2026-04-29 个股 `daily` K 线行数正常。
  - 已执行：2026-04-29 候选 5462、冲突 0、移动 5462、剩余偏移候选 0。
  - 需求：3.1、3.2、6.3。

- [x] 23. 视诊断结果执行 `sector_kline` dry-run 与校正
  - 若 dry-run 无候选，可记录无需执行。
  - 若存在候选，按同样流程执行。
  - 验证：板块日 K 不再存在目标范围内的日级偏移候选。
  - 已执行：2026-04-29 sector_kline dry-run，候选 0、冲突 0、可移动 0，无需校正。
  - 需求：3.4、6.1、6.3。

- [x] 24. 补跑 `daily_basic/stk_limit` 或回填
  - 推荐先补跑 `daily_basic` 20260429，触发 hook 回填 `turnover/vol_ratio`。
  - 再补跑 `stk_limit` 20260429，或调用 `backfill_stk_limit_table` 补 `limit_up/limit_down`。
  - 验证：回填日志 `matched_rows > 0`，无 deadlock/lock timeout。
  - 已执行：daily_basic log_id=615，source_rows=5462、matched_rows=5462、updated_rows=5462；stk_limit log_id=616，source_rows=7568、matched_rows=5462、updated_rows=5348。
  - 需求：3.3、4.1、4.3。

- [x] 25. 最终覆盖率与预览验证
  - 运行 2026-04-29 覆盖率 SQL。
  - 打开 Tushare 预览 `daily`，确认 2026-04-29 个股行显示在正确日期且辅助字段不为空。
  - 验证：前端展示和 SQL 一致。
  - 已验证：2026-04-29 个股日 K 5460 行，turnover 5460、vol_ratio 5456、limit_up 5460、limit_down 5460；预览接口返回 `2026-04-29T00:00:00+00:00` 且辅助字段有值。
  - 需求：4.3、6.4。

## 阶段 6：补充清理 16:00 UTC 残留重复日线

- [x] 26. 确认 `2026-04-27 16:00:00+00` 来源
  - 查询样例股票 `000001.SZ` 最近日线，确认 `2026-04-27 16:00:00+00` 与 `2026-04-28 00:00:00+00` 映射到同一本地交易日。
  - 结合当前 `_normalize_tushare_timeseries_time()` 入口修复，确认残留来自旧 naive datetime 写入路径，而非新写入路径。
  - 验证：已输出 `000001.SZ` 样例；`2026-04-27 16:00:00+00` 与 `2026-04-28 00:00:00+00` 均映射到 Asia/Shanghai 本地交易日 `2026-04-28`；当前 `_normalize_tushare_timeseries_time()` 已返回 UTC aware 零点，确认残留来自旧 naive datetime 写入路径。
  - 需求：7。

- [x] 27. 增强历史修复脚本 dry-run 诊断
  - 文件：`scripts/repair_tushare_timeseries_timezone.py`
  - 增加按目标交易日分布统计。
  - 增加同一本地交易日重复统计 SQL。
  - 增加冲突记录 OHLCV 差异计数和样例输出。
  - 保持默认 dry-run 不写库。
  - 验证：已增加候选、冲突、可移动、目标交易日分布、本地交易日重复、OHLCV 差异 dry-run 输出。
  - 需求：7.1、7.5、7.7。

- [x] 28. 更新脚本测试
  - 文件：`tests/scripts/test_repair_tushare_timeseries_timezone.py`
  - 覆盖新增 SQL 构建函数或输出函数。
  - 断言重复验证 SQL 使用 `date(time at time zone 'Asia/Shanghai')`。
  - 断言 OHLCV 差异诊断不包含 UPDATE/DELETE。
  - 验证：`/Users/poper/ContestTrade/yes/bin/pytest tests/scripts/test_repair_tushare_timeseries_timezone.py` 通过，10 passed。
  - 需求：5.4、7.5、7.7。

- [x] 29. 执行 2026-04 残留 dry-run
  - 命令：
    ```bash
    /Users/poper/ContestTrade/yes/bin/python scripts/repair_tushare_timeseries_timezone.py \
      --table kline \
      --start-date 2026-04-01 \
      --end-date 2026-04-30 \
      --freq 1d \
      --dry-run
    ```
  - 验证：全月轻量 dry-run 候选 104335、冲突 104335、可移动 0；增强 dry-run 首批 2026-04-01~2026-04-05 候选 16450、本地重复 16450、OHLCV 差异 378，execute 将保留规范记录并仅补空字段。
  - 需求：6.1、7.1、7.5。

- [x] 30. 执行 2026-04 `kline` 去重
  - dry-run 确认后执行 `--execute`。
  - 对冲突记录只补空字段并删除 16:00 残留；对无冲突记录移动到 `time + 8 hours`。
  - 验证：按 1 天批次成功执行；2026-04 共删除 104335 条 16:00 UTC 冲突残留，merged=0、moved=0，每批 remaining_candidates=0。
  - 需求：7.2、7.3、7.4。

- [x] 31. 验证去重结果
  - 运行同一本地交易日重复验证 SQL。
  - 抽样检查 `000001.SZ` 等股票最近日线不再存在 `16:00 UTC` 与 `00:00 UTC` 双记录。
  - 验证：2026-04 范围 `remaining_16h=0`、本地交易日重复组 `duplicate_groups=0`；`000001.SZ` 4/26~4/29 每个本地交易日仅一条 UTC 零点日线。
  - 需求：7.5。

- [x] 32. 验证策略指标恢复
  - 复跑全市场或 SQL 批量诊断的 `ma_trend + breakout` 统计。
  - 对比去重前异常值：原始重复数据上 `breakout_any=2`、`ma_trend+breakout=0`。
  - 验证：去重后全市场 5331 只中 `breakout_any=1090`、`ma_trend>=75=262`、`ma_trend+breakout=122`、有效买入突破交集 47；相对去重前 `breakout_any=2`、`ma_trend+breakout=0` 已恢复。
  - 需求：7.6。

- [x] 33. 执行代码质量自检与回归测试
  - 运行脚本测试和相关 Tushare 时区测试。
  - 按 `.kiro/hooks/code-quality-review.kiro.hook` 自检修改文件。
  - 验证：`PYTHONPATH=. /Users/poper/ContestTrade/yes/bin/pytest tests/scripts/test_repair_tushare_timeseries_timezone.py tests/tasks/test_tushare_import_timezone.py tests/tasks/test_tushare_import_timefreqfix.py` 通过，39 passed；`python -m py_compile scripts/repair_tushare_timeseries_timezone.py` 通过。未带 `PYTHONPATH=.` 时虚拟环境会导入旧包导致 timezone 测试失败，已记录为环境路径问题。
  - 需求：5.5、7。
