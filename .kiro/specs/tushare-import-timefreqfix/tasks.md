# Tasks — Tushare 导入频率超限与数据截断修复

## Task 1: 扩展 RateLimitGroup 枚举和配置

- [x] 1.1 在 `app/services/data_engine/tushare_registry.py` 的 `RateLimitGroup` 枚举中新增频率层级：TIER_80（80次/min）、TIER_60（60次/min）、TIER_20（20次/min）、TIER_10（10次/min，替代原 LIMIT_UP 语义）。保留原有 KLINE、FUNDAMENTALS、MONEY_FLOW、LIMIT_UP 枚举值以保持向后兼容
- [x] 1.2 在 `app/core/config.py` 的 `Settings` 类中添加新频率分组配置项：`rate_limit_tier_80: float = 0.90`、`rate_limit_tier_60: float = 1.20`、`rate_limit_tier_20: float = 3.50`、`rate_limit_tier_10: float = 7.0`
- [x] 1.3 更新 `app/tasks/tushare_import.py` 中的 `_build_rate_limit_map()` 函数，添加新 `RateLimitGroup` 枚举值到映射字典，从 `settings` 读取对应配置值
- [x] 1.4 更新 `.env.example` 添加新频率分组环境变量及注释说明（`RATE_LIMIT_TIER_80=0.90` 等）
- [x] 1.5 更新 `.env` 添加新频率分组环境变量

## Task 2: 修正 API 注册表频率分组

- [x] 2.1 审查并修正 `tushare_registry.py` 中所有 API 条目的 `rate_limit_group`，将每个接口分配到与 Tushare 官方频率限制匹配的分组。重点关注：打板专题数据接口（`stk_auction`、`ths_daily`、`dc_daily` 等）、特色数据接口（`stk_auction_o`、`stk_auction_c` 等）、参考数据接口
- [x] 2.2 为关键的 `batch_by_date=True` 接口在 `extra_config` 中添加 `estimated_daily_rows` 字段，用于预检查步长配置合理性

## Task 3: 修正 date_chunk_days 配置

- [x] 3.1 审查并修正所有 `batch_by_date=True` 接口的 `date_chunk_days` 配置，确保 `date_chunk_days × estimated_daily_rows < max_rows`（含安全余量）。重点关注：`sw_daily`（当前 130 天）、`ci_daily`（当前 130 天）、`limit_list_ths`（当前 15 天）、`limit_step`（当前 100 天）、`moneyflow_ind_ths`（当前 100 天）等

## Task 4: 实现截断自动重试机制

- [x] 4.1 在 `app/tasks/tushare_import.py` 的 `_process_batched_by_date` 函数中实现截断自动重试：当 `check_truncation()` 返回 `True` 时，自动将当前子区间拆分为更小的子区间（步长减半）并重新请求数据，替代当前仅记录警告的行为
- [x] 4.2 实现连续截断自动缩小后续步长：当连续截断计数达到阈值时，自动缩小后续所有子区间的步长（减半），并在 `batch_stats` 中记录截断自动恢复的详细信息
- [x] 4.3 为截断重试设置最大重试深度（如 3 层），防止无限递归拆分；当达到最大深度时记录 ERROR 日志并继续处理下一个子区间

## Task 5: 编写属性测试（Property-Based Tests）

- [x] 5.1 [PBT-exploration] 编写探索性测试：遍历注册表所有 API 条目，验证 `rate_limit_group` 对应的调用间隔 >= Tushare 官方最小间隔。在未修复代码上运行预期失败，修复后通过
- [x] 5.2 [PBT-exploration] 编写探索性测试：验证所有 `batch_by_date=True` 且配置了 `estimated_daily_rows` 的接口，`date_chunk_days × estimated_daily_rows < max_rows`。在未修复代码上运行预期失败，修复后通过
- [x] 5.3 [PBT-exploration] 编写探索性测试：验证 `_build_rate_limit_map()` 返回的映射覆盖所有 `RateLimitGroup` 枚举值。在未修复代码上运行预期失败，修复后通过
- [x] 5.4 [PBT-preservation] 编写保全测试：生成随机 `(ApiEntry, params)` 对，验证 `determine_batch_strategy()` 返回值在修复前后不变
- [x] 5.5 [PBT-preservation] 编写保全测试：生成随机 `(rows, ApiEntry)` 对，验证 `_apply_field_mappings()` 和 `_convert_codes()` 输出在修复前后不变
- [x] 5.6 [PBT-preservation] 编写保全测试：生成 `row_count < max_rows` 的随机输入，验证 `check_truncation()` 始终返回 `False`

## Task 6: 编写单元测试和集成测试

- [x] 6.1 编写单元测试：验证新增 `RateLimitGroup` 枚举值的完整性和 `_build_rate_limit_map()` 覆盖所有枚举值
- [x] 6.2 编写单元测试：验证截断自动重试逻辑——模拟 API 返回 `max_rows` 行，验证自动拆分子区间并重新请求
- [x] 6.3 编写单元测试：验证连续截断步长缩小——模拟连续 3 个截断子区间，验证后续步长减半
- [x] 6.4 编写集成测试：模拟完整导入流程，验证截断重试后数据完整且 `batch_stats` 记录正确

## Task 7: 验证和清理

- [x] 7.1 运行全部测试套件（`pytest`），确保所有测试通过且无回归
- [x] 7.2 运行属性测试（`pytest tests/properties/`），确保所有属性测试通过
