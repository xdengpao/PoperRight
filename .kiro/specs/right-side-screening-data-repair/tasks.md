# 任务清单：右侧趋势突破选股数据消缺

## 阶段 1：因子评估口径修复

- [x] 1.1 在 `FactorEvaluator` 中抽取字段解析逻辑
  - 文件：`app/services/screener/strategy_engine.py`
  - 新增 `resolve_field_name()` 或等价静态方法
  - 保持 PERCENTILE、INDUSTRY_RELATIVE 现有字段规则

- [x] 1.2 修复 `rsi` RANGE 读取 `rsi_current`
  - 文件：`app/services/screener/strategy_engine.py`
  - `factor_name="rsi"` 且 `ThresholdType.RANGE` 时读取 `rsi_current`
  - 缺失 `rsi_current` 时不通过

- [x] 1.3 补充 RSI 评估测试
  - 文件：`tests/services/test_factor_evaluator_enhanced.py`
  - 覆盖 `rsi=True/False` 但 `rsi_current=60` 时通过
  - 覆盖 `rsi=True` 但缺失 `rsi_current` 时不通过
  - 覆盖 `rsi_current` 超出区间时不通过

## 阶段 2：策略配置支持资金流数据源

- [x] 2.1 扩展后端 `VolumePriceConfig`
  - 文件：`app/core/schemas.py`、`app/api/v1/screen.py`
  - 新增 `money_flow_source: str = "money_flow"`
  - `to_dict()` / `from_dict()` 支持该字段
  - `VolumePriceConfigIn` 支持该字段，避免 API `model_dump()` 丢弃前端配置
  - 非法值归一化为 `"money_flow"`

- [x] 2.2 补充配置序列化测试
  - 文件：`tests/core/test_schemas_param_optimization.py`
  - 覆盖默认值、三种合法值、非法值兼容、往返序列化

- [x] 2.3 扩展前端量价资金配置类型和默认值
  - 文件：`frontend/src/views/ScreenerView.vue`
  - `VolumePriceConfig` 新增 `money_flow_source`
  - `VOLUME_PRICE_DEFAULTS` 新增默认值
  - 策略加载时回填该字段
  - 策略保存/运行时写入配置

- [x] 2.4 增加前端资金流数据源下拉框
  - 文件：`frontend/src/views/ScreenerView.vue`
  - 选项：`money_flow`、`moneyflow_ths`、`moneyflow_dc`
  - 使用单选 select
  - 保持量价资金面板现有布局风格

- [x] 2.5 补充前端配置测试
  - 文件：优先扩展 `frontend/src/views/__tests__/ScreenerView.property.test.ts` 或相关策略编辑测试
  - 覆盖保存和加载 `money_flow_source`
  - 覆盖缺失字段时默认 `money_flow`

## 阶段 3：资金流因子三选一接入

- [x] 3.1 重命名或隔离旧资金流 enrich 方法
  - 文件：`app/services/screener/screen_data_provider.py`
  - 将现有 `_enrich_money_flow_factors()` 保留为旧 `money_flow` 数据源路径
  - 避免 THS/DC 选择时逐股票查询旧表

- [x] 3.2 新增资金流源解析方法
  - 文件：`app/services/screener/screen_data_provider.py`
  - 从 `strategy_config["volume_price"]["money_flow_source"]` 读取
  - 缺失或非法时默认 `money_flow`

- [x] 3.3 新增 THS/DC 选择式批量 enrich
  - 文件：`app/services/screener/screen_data_provider.py`
  - `moneyflow_ths` 只查询 `moneyflow_ths`
  - `moneyflow_dc` 只查询 `moneyflow_dc`
  - 不自动回退
  - 写入 `money_flow`、`money_flow_value`、`main_net_inflow`、`large_order`、`large_order_ratio`

- [x] 3.4 调整旧 money_flow 路径写入百分位原始值
  - 文件：`app/services/screener/screen_data_provider.py`
  - 旧表路径额外写入 `money_flow_value`
  - 缺失数据时 `money_flow_value=None`

- [x] 3.5 调整百分位计算流程
  - 文件：`app/services/screener/screen_data_provider.py`
  - 使用 `money_flow_value` 计算资金流百分位
  - 将结果写入/别名为 `money_flow_pctl`
  - 保持 `money_flow` 布尔字段供模块评分和展示使用

- [x] 3.6 补充资金流选择测试
  - 文件：`tests/services/test_screen_data_provider_money_flow.py`
  - 覆盖三种数据源
  - 覆盖 THS/DC 不自动回退
  - 覆盖 `money_flow_pctl` 基于 `money_flow_value`

## 阶段 4：Kline 辅助字段回填

- [x] 4.1 新增 Kline 辅助字段回填服务
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 定义 `BackfillStats`
  - 实现 rows-based `backfill_daily_basic_rows()`
  - 实现 rows-based `backfill_stk_limit_rows()`

- [x] 4.2 实现 `daily_basic` rows 回填 SQL
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - `turnover <- turnover_rate`
  - `vol_ratio <- volume_ratio`
  - 匹配 `(symbol, trade_date, freq='1d', adj_type=0)`
  - None 不覆盖已有值

- [x] 4.3 实现 `stk_limit` rows 回填 SQL
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - `limit_up <- up_limit`
  - `limit_down <- down_limit`
  - 匹配 `(symbol, trade_date, freq='1d', adj_type=0)`
  - None 不覆盖已有值

- [x] 4.4 提供历史 `stk_limit` 表补跑方法
  - 文件：`app/services/data_engine/kline_aux_field_backfill.py`
  - 方法名：`backfill_stk_limit_table()`
  - 支持 `start_date` / `end_date`
  - 从 PostgreSQL `stk_limit` 读取，再批量更新 TimescaleDB `kline`

- [x] 4.5 接入 Tushare 导入后置 hook
  - 文件：`app/tasks/tushare_import.py`
  - `daily_basic` 主写入后触发 `backfill_daily_basic_rows`
  - `stk_limit` 主写入后触发 `backfill_stk_limit_rows`
  - hook 失败记录 warning，不回滚主表导入
  - 导入任务结果 `extra_info` 附加 `backfill_error` 或等价回填失败摘要

- [x] 4.6 补充回填服务测试
  - 文件：新增 `tests/services/test_kline_aux_field_backfill.py`
  - 覆盖匹配更新、无匹配跳过、None 不覆盖、幂等重复执行

- [x] 4.7 补充 Tushare hook 测试
  - 文件：新增或扩展 `tests/tasks/test_tushare_import_kline_aux_backfill.py`
  - 模拟 `daily_basic` / `stk_limit` 导入 rows 后触发回填

## 阶段 5：stk_factor 最近可用日期回退

- [x] 5.1 新增最近可用日期解析方法
  - 文件：`app/services/screener/screen_data_provider.py`
  - 查询 `stk_factor.trade_date <= target`
  - 默认 10 自然日窗口

- [x] 5.2 改造 `_enrich_stk_factor_factors`
  - 文件：`app/services/screener/screen_data_provider.py`
  - 目标日无 rows 时使用最近可用日期
  - 超窗则保持 None 降级
  - 日志输出 target、actual、fallback_days、matched

- [x] 5.3 补充 stk_factor 回退测试
  - 文件：新增 `tests/services/test_screen_data_provider_stk_factor.py`
  - 覆盖目标日命中、最近日期回退、超窗降级

## 阶段 6：0 入选可解释日志

- [x] 6.1 新增因子失败统计纯函数
  - 文件：`app/services/screener/strategy_engine.py` 或新建辅助模块
  - 输出每个因子的 `passed/missing/failed`
  - 复用 `FactorEvaluator` 字段解析逻辑

- [x] 6.2 手动选股 0 入选时输出统计日志
  - 文件：`app/tasks/screening.py`
  - 仅当 `len(result.items) == 0` 时输出
  - 不改变 API 响应结构

- [x] 6.3 补充统计测试
  - 文件：新增 `tests/services/test_screening_factor_summary.py`
  - 覆盖缺失、失败、通过三类计数

## 阶段 7：数据补跑与验证

- [!] 7.1 执行历史 `stk_limit` 到 `kline` 回填
  - 通过服务函数或临时脚本调用 `backfill_stk_limit_table`
  - 记录处理行数、匹配行数、更新行数
  - 失败原因：已尝试全历史补跑；3000 行批次暴露 SQL 类型问题并已修复，200 行批次运行数分钟后仍未返回统计，为避免长事务继续占用，已中断。建议后续按日期范围分段补跑。

- [!] 7.2 重新导入或补跑 `daily_basic` 以补齐 turnover/vol_ratio
  - 使用 Tushare 导入流程触发 hook
  - 或在确认有历史明细来源后通过回填服务补跑
  - 失败原因：当前 spec 不新增 `daily_basic` 历史明细表，本轮未执行 Tushare 重新导入；后续导入会自动触发 rows 回填。

- [x] 7.3 执行数据库覆盖率验证
  - 查询最近 10 个交易日 `kline.turnover`、`vol_ratio`、`limit_up`、`limit_down` 非空覆盖率
  - 保存关键输出到最终报告

- [!] 7.4 运行右侧趋势突破综合策略验证
  - 手动触发选股或执行等价服务级运行
  - 检查不再因 RSI 口径、turnover 缺失、money_flow 源缺失导致必然 0 入选
  - 若仍为 0，依据因子失败统计解释主要约束
  - 失败原因：已通过 API 触发右侧趋势突破综合策略，筛选 5331 只、入选 0 只；当前运行中的 Celery worker 未重启，未加载本次新增的 0 入选因子统计代码。日志仍显示最新日期 `turnover` 大量为 NULL、旧 `money_flow` 表缺失、`stk_factor` 仅匹配 80/5331。

## 阶段 8：测试与质量审查

- [x] 8.1 运行后端定向测试
  - `pytest tests/services/test_factor_evaluator_enhanced.py`
  - `pytest tests/core/test_schemas_param_optimization.py`
  - `pytest tests/services/test_screen_data_provider_money_flow.py`
  - 新增测试文件逐一运行

- [x] 8.2 运行前端定向测试或类型检查
  - `cd frontend && npm run type-check`
  - 如新增/修改前端测试，运行对应 Vitest

- [x] 8.3 运行代码质量自审
  - 按 `.kiro/hooks/code-quality-review.kiro.hook` 检查
  - 修复异味、重复逻辑、边界缺失和性能风险

- [x] 8.4 更新任务状态与最终说明
  - 执行完成的任务标记为 `[x]`
  - 若某项无法完成，标记 `[!]` 并说明原因
  - 最终报告包含测试命令、数据验证结果和剩余风险
