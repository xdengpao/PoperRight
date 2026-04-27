# 实现计划：Tushare 数据导入性能优化

## 概述

按优先级分 5 个阶段实施 8 项优化。阶段 1-2 为 P0 性能关键项（批量写入 + HTTP 连接池），阶段 3 为 P1 可靠性改进（asyncio + 增量调度），阶段 4 为 P2 完整性与健壮性，阶段 5 为验证检查点。

## Tasks

### 阶段 1：数据库批量写入优化（P0）

- [ ] 1.1 重构 `_write_to_postgresql` 为批量 INSERT
  - 将逐行 `session.execute(stmt, row)` 循环改为分批 `session.execute(stmt, batch)`（每批 1000 行）
  - 新增 try/except 包裹批量写入，失败时回退到逐行 INSERT 并记录 WARNING
  - 逐行回退模式下单行失败仅跳过该行，不中断整批
  - 保持现有 ON CONFLICT 策略和死锁重试逻辑不变
  - _Requirements: 1.1, 1.3, 1.4_

- [ ] 1.2 重构 `_write_to_kline` 为批量 INSERT
  - 将数据预处理（trade_date 解析、symbol 提取、无效行过滤）提取到参数列表构建阶段
  - 将逐行 execute 改为 `session.execute(sql, params_list)` 批量写入
  - 新增批量失败回退逻辑
  - _Requirements: 1.2, 1.3_

- [ ] 1.3 重构 `_write_to_adjustment_factor` 为批量 INSERT
  - 同 1.2 模式：预处理 + 批量 executemany + 回退
  - _Requirements: 1.2, 1.3_

- [ ] 1.4 重构 `_write_to_sector_kline` 为批量 INSERT
  - 同 1.2 模式：预处理 + 批量 executemany + 回退
  - _Requirements: 1.2, 1.3_

- [ ] 1.5 检查点 — 验证批量写入
  - 确认所有 4 个写入函数均已改为批量模式
  - 确认 ON CONFLICT 策略未被改变
  - 确认回退逻辑存在且有日志输出

### 阶段 2：HTTP 连接池复用（P0）

- [ ] 2.1 改造 `TushareAdapter` 支持持久 httpx.AsyncClient
  - 新增 `_client` 实例属性（初始为 None）
  - 新增 `_get_client()` 方法：延迟创建 client，检测 is_closed 自动重建
  - 新增 `close()` 方法：关闭 client 并置 None
  - 修改 `_call_api`：使用 `await self._get_client()` 替代 `async with httpx.AsyncClient()`
  - 保持 timeout 配置和错误处理逻辑不变
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 2.2 在 `_process_import` 中确保 adapter 资源释放
  - 在 finally 块中调用 `await adapter.close()`（在释放 Redis 锁之前）
  - _Requirements: 2.2_

- [ ] 2.3 检查点 — 验证连接池复用
  - 确认 `_call_api` 不再每次创建新 client
  - 确认 `_process_import` 的 finally 块包含 `adapter.close()`
  - 确认 `health_check` 等短生命周期调用仍能正常工作

### 阶段 3：asyncio 阻塞消除 + 增量导入（P1）

- [ ] 3.1 全局替换 `time.sleep` 为 `await asyncio.sleep`
  - 替换 `_process_chunk_with_retry` 中的 `time.sleep(rate_delay)`
  - 替换 `_process_batched_by_date` 中的 `time.sleep(rate_delay)`
  - 替换 `_process_batched` 中的两处 `time.sleep(rate_delay)`（双重分批和单次分批）
  - 替换 `_process_batched_index` 中的 `time.sleep(rate_delay)`
  - 替换 `_process_batched_by_sector` 中的 `time.sleep(rate_delay)`
  - 替换 `_call_api_with_retry` 中的 `time.sleep(_RATE_LIMIT_WAIT)` 和 `time.sleep(2 * (attempt + 1))`
  - 替换 `_write_to_postgresql` 死锁重试中的 `_time.sleep(wait)`
  - _Requirements: 3.1, 3.2_

- [ ] 3.2 实现增量导入日期推断
  - 在 `TushareImportService` 中新增 `_get_last_successful_end_date(api_name)` 方法
    - 查询 tushare_import_log 中 status='completed' 且 api_name 匹配的最新记录
    - 从 params_json 中提取 end_date，返回 YYYYMMDD 字符串或 None
  - 在 `TushareImportService` 中新增 `_resolve_incremental_dates(api_name, entry, params)` 方法
    - 仅对含 DATE_RANGE 参数的接口生效
    - 用户已指定 start_date + end_date 时直接返回
    - 否则自动推断：start_date = last_end_date + 1 天，end_date = 当前日期
    - 无历史记录时 start_date 默认 20100101
    - start_date > end_date 时抛出 ValueError("数据已是最新")
  - 在 `start_import` 方法中，参数校验之前调用 `_resolve_incremental_dates`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 3.3 检查点 — 验证阶段 3
  - 确认 tushare_import.py 中无残留的 `time.sleep` 调用（grep 验证）
  - 确认增量导入方法已集成到 start_import 流程

### 阶段 4：完整性校验 + 代码健壮性（P2）

- [ ] 4.1 在 `_process_batched` 中新增失败项追踪
  - 新增 `failed_codes: list[str]` 列表
  - 在 API 调用或 DB 写入异常时将 ts_code 追加到 failed_codes
  - 在返回的 batch_stats 中包含 `failed_codes`（截取前 100 个）
  - _Requirements: 5.1_

- [ ] 4.2 在 `_process_batched_by_date` 中新增失败区间追踪
  - 新增 `failed_chunks: list[str]` 列表
  - 在异常时将 `{chunk_start}-{chunk_end}` 追加到 failed_chunks
  - 在 batch_stats 中包含 `failed_chunks`（截取前 100 个）
  - _Requirements: 5.2_

- [ ] 4.3 在 `_update_progress` 中传递 failed_items
  - 新增 `failed_items` 可选参数
  - 在 Redis 进度 JSON 中包含 `failed_items` 字段
  - _Requirements: 5.3_

- [ ] 4.4 优化 `_get_stock_list` 代码后缀推断
  - 查询时新增 `StockInfo.market` 字段
  - 优先使用 market 字段（SH/SZ/BJ）确定后缀
  - market 为空时回退到前缀推断，未知前缀记录 WARNING
  - _Requirements: 6.1, 6.2_

- [ ] 4.5 频率限制配置热更新
  - 删除模块级 `_RATE_LIMIT_MAP` 变量
  - 在 `_process_import` 中改为 `rate_delay = _build_rate_limit_map().get(entry.rate_limit_group, 0.18)`
  - _Requirements: 7.1, 7.2_

- [ ] 4.6 sector 成分导入日志增强
  - 在 `_process_batched_by_sector` 的 batch_stats 中新增 `trade_date` 字段（记录注入的日期）
  - _Requirements: 8.1, 8.2, 8.3_

- [ ] 4.7 检查点 — 验证阶段 4
  - 确认 failed_codes / failed_chunks 在 batch_stats 中正确传递
  - 确认 _get_stock_list 使用 market 字段
  - 确认模块级 _RATE_LIMIT_MAP 已删除

### 阶段 5：最终验证

- [ ] 5.1 全局代码审查
  - 检查所有修改文件的 import 语句是否完整
  - 检查是否有遗漏的 time.sleep 调用
  - 检查 async/await 使用是否正确（无遗漏 await）
  - 检查日志级别是否合理（ERROR/WARNING/INFO/DEBUG）

- [ ] 5.2 向后兼容性验证
  - 确认 TushareAdapter 的公开接口签名未变
  - 确认 tushare_registry.py 未被修改
  - 确认 Redis 键格式和 TTL 未变
  - 确认 API 端点响应格式未变

## Notes

- 所有修改集中在 3 个文件：`tushare_import.py`、`tushare_adapter.py`、`tushare_import_service.py`
- 不涉及数据库 schema 变更，无需 Alembic 迁移
- 不涉及前端变更
- 批量写入的分批大小 1000 行是经验值，可通过常量调整
