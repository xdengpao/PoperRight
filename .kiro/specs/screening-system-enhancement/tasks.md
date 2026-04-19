# 任务清单：智能选股系统增强

## 阶段一：修复断裂链路

- [x] 1. 资金流因子数据接入（需求 1）
  - [x] 1.1 在 `app/models/` 中创建 `money_flow.py` ORM 模型，映射 `money_flow` 表的 `symbol`、`trade_date`、`main_net_inflow`、`large_order_ratio` 等字段
  - [x] 1.2 在 `ScreenDataProvider.load_screen_data()` 主循环中，为每只股票查询 `money_flow` 表最近 N 日数据，调用 `check_money_flow_signal()` 和 `check_large_order_signal()` 计算因子值，替代当前硬编码的 `False`
  - [x] 1.3 将 `money_flow` 和 `large_order` 的原始数值（`main_net_inflow` 浮点值、`large_order_ratio` 浮点值）同时写入 Factor_Dict，确保百分位排名计算能正确处理
  - [x] 1.4 添加缺失数据降级逻辑：当 `money_flow` 表无该股票记录时，设 `money_flow=False`、`large_order=False`，记录 WARNING 日志
  - [x] 1.5 编写单元测试 `tests/services/test_screen_data_provider_money_flow.py`，覆盖正常加载、缺失数据、异常处理场景

- [x] 2. Celery 选股任务接入数据管线（需求 2）
  - [x] 2.1 在 `app/tasks/screening.py` 中实现 `_load_market_data_async()`，通过 `ScreenDataProvider` 异步加载全市场股票因子数据，替代返回空字典的占位实现
  - [x] 2.2 在 `app/tasks/screening.py` 中实现 `_load_active_strategy_async()`，从 `strategy_template` 表查询 `is_active=True` 的策略模板，替代返回空配置的占位实现
  - [x] 2.3 在 `run_eod_screening` 任务完成后，将选股结果写入 Redis 缓存（key `screen:results:{strategy_id}`），并记录执行耗时和选出股票数量到 Redis（key `screen:eod:last_run`）
  - [x] 2.4 添加数据库连接失败时的 Celery 重试逻辑（最多 3 次，指数退避），记录 ERROR 日志
  - [x] 2.5 编写单元测试 `tests/tasks/test_screening_pipeline.py`，覆盖正常执行、策略加载、Redis 缓存写入、重试场景

- [x] 3. 板块因子接入主选股管线（需求 3）
  - [x] 3.1 修复 `ScreenDataProvider.load_screen_data()` 中板块数据写入路径，确保 `sector_rank`（int|None）和 `sector_trend`（bool）写入每只股票的 Factor_Dict 内部
  - [x] 3.2 添加板块数据加载失败时的降级逻辑：`sector_rank=None`、`sector_trend=False`，选股流程不中断
  - [x] 3.3 编写属性测试 `tests/properties/test_sector_factor_type_properties.py`，验证 Property 1（板块因子类型不变量）

- [x] 4. 风控集成到选股执行器（需求 4）
  - [x] 4.1 在 `ScreenExecutor` 中新增 `_apply_risk_filters()` 方法，接受候选股票列表、stocks_data、指数收盘价序列，返回过滤后的列表和大盘风险等级
  - [x] 4.2 在 `_apply_risk_filters()` 中集成 `MarketRiskChecker.check_market_risk()`：DANGER 返回空列表，CAUTION 提升阈值至 90
  - [x] 4.3 在 `_apply_risk_filters()` 中集成 `StockRiskFilter.check_daily_gain()` 剔除单日涨幅 > 9% 的股票
  - [x] 4.4 在 `_apply_risk_filters()` 中集成 `BlackWhiteListManager.is_blacklisted()` 剔除黑名单股票
  - [x] 4.5 在 `ScreenItem` 和 `ScreenResult` 中新增风控信息字段（`market_risk_level`、`risk_filter_info`）
  - [x] 4.6 在 `_execute()` 方法中调用 `_apply_risk_filters()`，将风控作为选股后处理步骤
  - [x] 4.7 编写属性测试 `tests/properties/test_risk_filter_properties.py`，验证 Property 2（DANGER 清空）、Property 3（CAUTION 阈值）、Property 4（风控排除规则）

## 阶段二：重构评分与信号体系

- [x] 5. 重构趋势评分为加权求和（需求 5）
  - [x] 5.1 在 `app/core/schemas.py` 中定义 `DEFAULT_MODULE_WEIGHTS` 常量字典
  - [x] 5.2 在 `ScreenExecutor` 中新增 `_compute_weighted_score(module_scores: dict[str, float]) -> float` 纯函数，实现加权求和公式，排除 score=0 的模块，确保结果在 [0, 100]
  - [x] 5.3 重构 `_execute()` 方法中的趋势评分逻辑，将各模块评分收集到 `module_scores` 字典，调用 `_compute_weighted_score()` 替代 `max()` 竞争
  - [x] 5.4 编写属性测试 `tests/properties/test_weighted_score_properties.py`，验证 Property 5（加权求和公式与范围）

- [x] 6. 支持多重突破信号并发（需求 6）
  - [x] 6.1 修改 `ScreenDataProvider._build_factor_dict()` 中的突破检测逻辑，对所有启用的突破类型逐一检测，将结果存储为 `breakout_list: list[dict]`
  - [x] 6.2 保持向后兼容：`breakout` 字段保留第一个信号（或 None），新增 `breakout_list` 字段
  - [x] 6.3 修改 `ScreenExecutor._execute()` 中的突破信号处理逻辑，从 `breakout_list` 为每种有效突破类型生成独立的 `SignalDetail`
  - [x] 6.4 添加向后兼容处理：当 `breakout` 为单个字典（旧格式）时仍能正确处理
  - [x] 6.5 编写属性测试 `tests/properties/test_breakout_multi_properties.py`，验证 Property 6（完整检测）和 Property 7（信号映射）

- [x] 7. 信号强度分级（需求 7）
  - [x] 7.1 在 `app/core/schemas.py` 中新增 `SignalStrength` 枚举（STRONG/MEDIUM/WEAK），在 `SignalDetail` 中新增 `strength` 字段
  - [x] 7.2 在 `ScreenExecutor` 中新增 `_compute_signal_strength()` 纯函数，根据信号类别和上下文数据计算强度等级
  - [x] 7.3 在 `_execute()` 方法中为每个生成的 `SignalDetail` 调用 `_compute_signal_strength()` 设置强度
  - [x] 7.4 编写属性测试 `tests/properties/test_signal_strength_properties.py`，验证 Property 8（信号强度分级映射）

- [x] 8. 信号新鲜度标记（需求 8）
  - [x] 8.1 在 `app/core/schemas.py` 中新增 `SignalFreshness` 枚举（NEW/CONTINUING），在 `SignalDetail` 中新增 `freshness` 字段，在 `ScreenItem` 中新增 `has_new_signal` 字段
  - [x] 8.2 在 `ScreenExecutor` 中新增 `_mark_signal_freshness()` 纯函数，接受当前信号列表和上一轮信号列表，返回标记了新鲜度的信号列表
  - [x] 8.3 在 `_execute()` 方法中从 Redis 读取上一轮结果，调用 `_mark_signal_freshness()` 标记新鲜度，设置 `has_new_signal`
  - [x] 8.4 编写属性测试 `tests/properties/test_signal_freshness_properties.py`，验证 Property 9（新鲜度标记）和 Property 10（has_new_signal 一致性）

## 阶段三：性能与架构优化

- [x] 9. 实时选股增量计算架构（需求 9）
  - [x] 9.1 在 `app/tasks/screening.py` 中实现 `_warmup_factor_cache()` 函数，交易日首次执行时全量预热因子数据到 Redis，缓存有效期 6 小时
  - [x] 9.2 在 `app/tasks/screening.py` 中实现 `_incremental_update()` 函数，从 Redis 读取缓存因子，仅重新计算受实时数据影响的因子（均线、技术指标），基本面和板块因子使用缓存值
  - [x] 9.3 修改 `run_realtime_screening` 任务，首次执行时调用预热，后续执行使用增量模式
  - [x] 9.4 在每轮实时选股完成后记录执行耗时，超过 8 秒记录 WARNING 日志
  - [x] 9.5 编写单元测试 `tests/tasks/test_realtime_incremental.py`，覆盖预热、增量更新、超时告警场景

- [x] 10. 选股结果去重与变化检测（需求 10）
  - [x] 10.1 在 `app/core/schemas.py` 中新增 `ChangeType` 枚举和 `ScreenChange` 数据类，在 `ScreenResult` 中新增 `changes` 字段
  - [x] 10.2 在 `ScreenExecutor` 中新增 `_compute_result_diff()` 纯函数，接受当前结果和上一轮结果，返回 `list[ScreenChange]`
  - [x] 10.3 在 `_execute()` 方法中调用 `_compute_result_diff()`，将变化列表写入 `ScreenResult.changes`
  - [x] 10.4 编写属性测试 `tests/properties/test_result_diff_properties.py`，验证 Property 11（变化检测完备性）

- [x] 11. 选股结果到回测的闭环验证（需求 11）
  - [x] 11.1 在 `app/api/v1/screen.py` 中新增 `POST /screen/backtest` 端点，接受选股结果 ID 和回测参数
  - [x] 11.2 实现从选股结果中提取策略配置、股票列表、选股时间，构造 `BacktestConfig` 并提交回测任务
  - [x] 11.3 处理选股结果 ID 不存在或已过期的情况，返回 404 错误
  - [x] 11.4 编写 API 测试 `tests/api/test_screen_backtest.py`，覆盖正常提交、结果不存在、参数校验场景
