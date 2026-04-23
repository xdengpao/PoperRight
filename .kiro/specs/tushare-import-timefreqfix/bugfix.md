# Bugfix Requirements Document

## Introduction

Tushare 数据导入系统存在两个系统性缺陷，影响全部 120+ API 接口的数据完整性和可靠性：

1. **频率超限（Rate Limit Exceeded）**：多个 API 被分配到错误的频率限制分组，导致实际调用频率远超 Tushare 官方限制，触发 `code=40203` 错误。当前系统仅有 4 个频率分组（KLINE=0.18s, FUNDAMENTALS=0.40s, MONEY_FLOW=0.30s, LIMIT_UP=7.0s），但 Tushare 实际存在更多频率层级（如某些接口限制 60次/min、80次/min、20次/min 等），导致大量接口的频率配置与 Tushare 官方限制不匹配。

2. **数据截断（Data Truncation）**：API 单次返回行数有上限（通常 3000-5000 行），但许多接口的 `date_chunk_days` 步长配置过大，导致单次查询返回的数据量达到上限后被静默截断。现有截断检测机制（`check_truncation`）仅记录警告日志，不会阻止数据丢失或自动缩小步长重试。

这两个问题导致：频率超限时导入任务失败或被 Tushare 封禁；数据截断时部分交易日数据丢失，影响后续量化分析的准确性。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 一个 API 接口的 Tushare 官方频率限制低于其所属 `RateLimitGroup` 配置的调用频率（例如 `stk_auction` 限制 10次/min 但被分配到 FUNDAMENTALS 组 150次/min）THEN 系统以远超官方限制的频率调用该接口，触发 Tushare `code=40203` 频率超限错误，导致导入任务失败

1.2 WHEN 系统仅有 4 个频率分组（KLINE/FUNDAMENTALS/MONEY_FLOW/LIMIT_UP）但 Tushare 实际存在更多频率层级（如 60次/min、80次/min、20次/min 等）THEN 无法为每个频率层级的接口分配正确的调用间隔，大量接口被迫使用不匹配的频率分组

1.3 WHEN 一个按日期分批的 API 接口的 `date_chunk_days` 步长过大，导致单个子区间返回的行数达到 `max_rows` 上限（如 `ths_daily` 的 `date_chunk_days=6` 返回恰好 3000 行）THEN 超出上限的数据被 Tushare 静默截断，系统丢失部分交易日数据而不报错

1.4 WHEN 截断检测函数 `check_truncation()` 检测到某个子区间返回行数达到 `max_rows` 上限 THEN 系统仅记录 WARNING 级别日志，继续处理下一个子区间，不会自动缩小步长重试或将该子区间标记为数据不完整

1.5 WHEN 连续多个子区间均被截断（连续截断计数达到阈值 `_CONSECUTIVE_TRUNCATION_THRESHOLD=3`）THEN 系统仅记录 ERROR 级别日志并设置 `needs_smaller_chunk=True` 标志，但不会实际执行步长缩小或重试操作，截断数据仍被写入数据库

1.6 WHEN `_build_rate_limit_map()` 构建频率限制映射时 THEN 映射表中缺少部分 Tushare 频率层级对应的分组，新增的频率层级无法通过配置文件灵活调整

### Expected Behavior (Correct)

2.1 WHEN 一个 API 接口在 Tushare 官方有明确的频率限制 THEN 系统 SHALL 为该接口分配与其官方限制匹配的 `RateLimitGroup`，确保实际调用间隔不低于 Tushare 要求的最小间隔（含安全余量）

2.2 WHEN Tushare 存在多个不同的频率层级 THEN 系统 SHALL 提供足够数量的 `RateLimitGroup` 枚举值和对应的配置项，覆盖所有实际使用的频率层级（如 TIER_500=0.18s, TIER_200=0.40s, TIER_80=1.0s, TIER_60=1.2s, TIER_20=3.5s, TIER_10=7.0s 等）

2.3 WHEN 一个按日期分批的 API 接口配置了 `date_chunk_days` 步长 THEN 系统 SHALL 确保该步长在正常数据密度下不会导致单个子区间返回行数达到 `max_rows` 上限，即 `date_chunk_days × estimated_daily_rows < max_rows`

2.4 WHEN 截断检测函数 `check_truncation()` 检测到某个子区间返回行数达到 `max_rows` 上限 THEN 系统 SHALL 自动将该子区间拆分为更小的子区间并重新请求数据，确保不丢失任何数据行

2.5 WHEN 连续多个子区间均被截断 THEN 系统 SHALL 自动将后续子区间的步长缩小（例如减半），并在导入完成后的 `batch_stats` 中记录截断自动恢复的详细信息

2.6 WHEN 新增或调整频率限制分组时 THEN 系统 SHALL 支持通过 `.env` 环境变量配置每个分组的调用间隔，`_build_rate_limit_map()` 能正确读取所有分组的配置值

### Unchanged Behavior (Regression Prevention)

3.1 WHEN API 接口的频率分组和步长配置本身已经正确（如 `daily` 接口使用 KLINE 组 0.18s 间隔，按代码分批无日期截断风险）THEN 系统 SHALL CONTINUE TO 以原有频率和步长正常导入数据，不受本次修复影响

3.2 WHEN 截断检测函数 `check_truncation()` 判定某个子区间未被截断（返回行数 < max_rows）THEN 系统 SHALL CONTINUE TO 正常写入数据并继续处理下一个子区间，不触发任何重试或步长调整逻辑

3.3 WHEN 按代码分批（`batch_by_code=True`）的接口执行导入 THEN 系统 SHALL CONTINUE TO 按原有的股票代码列表分批逻辑正常运行，分批策略路由 `determine_batch_strategy()` 的优先级不变

3.4 WHEN 导入任务收到停止信号 THEN 系统 SHALL CONTINUE TO 正确响应停止信号，中断导入并更新状态为 "stopped"

3.5 WHEN API 调用遇到网络超时或 Token 无效错误 THEN 系统 SHALL CONTINUE TO 按现有重试策略处理（网络超时重试 3 次，Token 无效直接终止，频率限制等待 60s 重试）

3.6 WHEN 字段映射（`_apply_field_mappings`）和代码格式转换（`_convert_codes`）处理数据 THEN 系统 SHALL CONTINUE TO 按注册表配置正确转换字段名和代码格式，不受频率或步长修复影响

3.7 WHEN 导入完成后更新 `tushare_import_log` 和 Redis 进度 THEN 系统 SHALL CONTINUE TO 正确记录导入状态、记录数和分批统计信息
