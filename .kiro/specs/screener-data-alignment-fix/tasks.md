# 任务列表：智能选股数据对齐与算法修复

## 阶段 1：股票代码格式对齐（需求 1, 2）— 最高优先级

- [ ] 1.1 新增 `_strip_market_suffix` 辅助方法
  - 在 `app/services/screener/screen_data_provider.py` 中新增静态方法
  - 实现 `ts_code.split(".")[0]` 逻辑，处理 `.SH`/`.SZ`/`.BJ` 后缀
  - 处理边界情况：无后缀的代码直接返回、空字符串保护

- [ ] 1.2 修复 `_enrich_stk_factor_factors` 代码格式匹配
  - 将 `row_map` 构建逻辑从 `{r.ts_code: r}` 改为 `{self._strip_market_suffix(r.ts_code): r}`
  - 添加匹配率 INFO 日志：`"stk_factor 匹配 %d/%d 只股票"`

- [ ] 1.3 修复 `_enrich_chip_factors` 代码格式匹配
  - 将 `row_map` 构建逻辑中 `CyqPerf.ts_code` 转换为纯数字格式

- [ ] 1.4 修复 `_enrich_margin_factors` 代码格式匹配
  - 将 `grouped` 分组键从 `r.ts_code` 改为 `self._strip_market_suffix(r.ts_code)`

- [ ] 1.5 修复 `_enrich_enhanced_money_flow_factors` 代码格式匹配
  - 将 `MoneyflowThs` 和 `MoneyflowDc` 的 `row_map` 键转换为纯数字格式

- [ ] 1.6 修复 `_enrich_board_hit_factors` 代码格式匹配
  - 将 `limit_grouped`、`step_map`、`top_grouped` 的键转换为纯数字格式
  - 注意 `LimitList.ts_code`、`LimitStep.ts_code`、`TopList.ts_code` 三处

- [ ] 1.7 修复 `_enrich_index_factors` 代码格式匹配
  - 将 `basic_map`、`tech_map` 键转换为纯数字格式
  - 将 `stock_index_map` 中 `con_code` 转换为纯数字格式
  - 注意 `_TARGET_INDICES` 中的指数代码（`"000300.SH"` 等）在查询 `IndexDailybasic`/`IndexTech` 时保持原格式（这些是查询条件，不是匹配键）

- [ ] 1.8 修复 KlineRepository 查询格式标准化
  - 在 `app/services/data_engine/kline_repository.py` 的 `query()` 方法开头添加 `symbol = symbol.split(".")[0] if "." in symbol else symbol`

- [ ] 1.9 修复 AdjFactorRepository 批量查询格式标准化
  - 在 `app/services/data_engine/adj_factor_repository.py` 的 `query_batch()` 方法中对 `symbols` 列表做格式标准化

- [ ] 1.10 编写代码格式对齐单元测试
  - 测试 `_strip_market_suffix` 各种输入格式
  - 测试 `_enrich_stk_factor_factors` 使用带后缀 ts_code 的 mock 数据能正确匹配纯数字 symbol
  - 测试 `KlineRepository.query()` 传入带后缀和不带后缀的 symbol 均能正确查询

---

## 阶段 2：StrategyEngine 加权得分归一化（需求 3）

- [ ] 2.1 扩展 FactorEvalResult 数据类
  - 在 `app/services/screener/strategy_engine.py` 的 `FactorEvalResult` 中新增 `normalized_score: float = 0.0` 字段

- [ ] 2.2 实现归一化计算逻辑
  - 在 `FactorEvaluator.evaluate()` 方法末尾，根据 `threshold_type` 计算 `normalized_score`
  - BOOLEAN：通过=100.0，未通过=0.0
  - ABSOLUTE：通过时映射到 [60, 100]，未通过时映射到 [0, 60)
  - PERCENTILE：直接使用百分位值
  - INDUSTRY_RELATIVE：相对值映射到 [0, 100]
  - RANGE：区间内=100.0，偏离时按距离衰减

- [ ] 2.3 修改 StrategyEngine.evaluate() 加权求和
  - 将 `weighted_sum += result.value * weight` 改为 `weighted_sum += result.normalized_score * weight`
  - 确保 `weighted_score = weighted_sum / total_weight` 结果在 [0, 100]

- [ ] 2.4 编写归一化单元测试
  - 测试各 ThresholdType 的归一化结果范围
  - 测试 BOOLEAN 因子：True → 100.0，False → 0.0
  - 测试 ABSOLUTE 因子：通过时 >= 60，未通过时 < 60
  - 测试 PERCENTILE 因子：直接使用百分位值
  - 测试混合因子策略的 weighted_score 在 [0, 100]

- [ ] 2.5 编写归一化属性测试（Hypothesis）
  - 属性：任意因子组合的 `normalized_score` 始终在 [0, 100]
  - 属性：任意因子组合的 `weighted_score` 始终在 [0, 100]

---

## 阶段 3：信号去重与风控修复（需求 4, 5）

- [ ] 3.1 实现信号去重逻辑
  - 在 `app/services/screener/screen_executor.py` 的 `_execute()` 方法中，信号构建完成后添加去重
  - 调整信号构建顺序：先构建非 factor_editor 路径信号，再处理 factor_editor 路径信号
  - 使用 `(category, label)` 元组作为去重键
  - 已存在的键跳过 factor_editor 路径的信号

- [ ] 3.2 计算 daily_change_pct 因子
  - 在 `app/services/screener/screen_data_provider.py` 的 `_build_factor_dict()` 中添加涨跌幅计算
  - `daily_change_pct = (latest_close - prev_close) / prev_close * 100`
  - 处理边界：K 线不足 2 条时设为 0.0，prev_close 为 0 时设为 0.0

- [ ] 3.3 计算 change_pct_3d 因子
  - 在 `_build_factor_dict()` 中添加近 3 日累计涨幅计算
  - `change_pct_3d = (latest_close - close_3d_ago) / close_3d_ago * 100`
  - 处理边界：K 线不足 4 条时设为 0.0

- [ ] 3.4 修复风控过滤逻辑
  - 在 `ScreenExecutor._apply_risk_filters_pure()` 中确认 `daily_change_pct` 过滤正常工作
  - 新增 `change_pct_3d > 20.0` 的过滤条件

- [ ] 3.5 编写信号去重和风控单元测试
  - 测试：启用 factor_editor + indicator_params 时，MACD 信号不重复
  - 测试：daily_change_pct > 9 的股票被正确剔除
  - 测试：change_pct_3d > 20 的股票被正确剔除
  - 测试：daily_change_pct 未设置时不影响正常选股

---

## 阶段 4：PSY/OBV 因子实现与 profit_growth/revenue_growth 数据接入（需求 6）

- [ ] 4.1 实现 PSY 计算函数
  - 在 `app/services/screener/indicators.py` 中新增 `calculate_psy(closes, period=12) -> float | None`
  - PSY = 最近 period 日中上涨天数 / period × 100
  - 数据不足时返回 None

- [ ] 4.2 实现 OBV 信号计算函数
  - 在 `app/services/screener/indicators.py` 中新增 `calculate_obv_signal(closes, volumes, short=5, long=20) -> bool | None`
  - 计算 OBV 序列，比较短期均值与长期均值
  - 数据不足时返回 None

- [ ] 4.3 集成 PSY/OBV 到 _build_factor_dict
  - 在 `screen_data_provider.py` 的 `_build_factor_dict()` 中调用 `calculate_psy` 和 `calculate_obv_signal`
  - 将结果写入 `stock_data["psy"]` 和 `stock_data["obv_signal"]`

- [ ] 4.4 修改 _enrich_stk_factor_factors 的 PSY/OBV 覆盖逻辑
  - 将 `fd["psy"] = None` 改为 `fd.setdefault("psy", None)`
  - 将 `fd["obv_signal"] = None` 改为 `fd.setdefault("obv_signal", None)`
  - 确保 `_build_factor_dict()` 中已计算的值不被覆盖

- [ ] 4.5 为 profit_growth 和 revenue_growth 因子接入数据
  - 在 `screen_data_provider.py` 中新增 `_enrich_financial_growth_factors()` 方法
  - 从 `financial_statement` 表查询最新报告期的净利润同比增长率和营收同比增长率
  - 写入 `factor_dict["profit_growth"]` 和 `factor_dict["revenue_growth"]`
  - 无数据时降级为 None，记录 WARNING 日志

- [ ] 4.6 编写 PSY/OBV 单元测试
  - 测试 `calculate_psy`：全涨=100，全跌=0，混合情况
  - 测试 `calculate_obv_signal`：放量上涨=True，缩量下跌=False
  - 测试边界：数据不足返回 None
  - 测试集成：`_build_factor_dict()` 输出包含非 None 的 psy 和 obv_signal

- [ ] 4.7 编写 PSY 属性测试（Hypothesis）
  - 属性：任意收盘价序列的 PSY 结果在 [0, 100] 或 None

---

## 阶段 5：StrategyConfig 去重与 indicator_params 数据契约修复（需求 7）

- [ ] 5.1 移除第一个 StrategyConfig 类定义
  - 删除 `app/core/schemas.py` 第 239-283 行附近的第一个 `StrategyConfig` 类（`indicator_params: dict` 版本）
  - 确认所有引用 `StrategyConfig` 的代码使用的是第二个完整版本
  - 运行全量测试确认无回归

- [ ] 5.2 修改 IndicatorParamsConfig.from_dict() 支持嵌套格式
  - 检测 `data` 中是否包含 `"macd"` 子字典来判断格式
  - 嵌套格式映射：`macd.fast_period` → `macd_fast`，`boll.period` → `boll_period` 等
  - 扁平格式保持原有逻辑不变
  - 两种格式均能正确解析为 `IndicatorParamsConfig` 实例

- [ ] 5.3 编写 indicator_params 解析单元测试
  - 测试扁平格式输入：`{"macd_fast": 10}` → `macd_fast=10`
  - 测试嵌套格式输入：`{"macd": {"fast_period": 10}}` → `macd_fast=10`
  - 测试空字典输入：使用默认值
  - 测试混合格式（部分嵌套部分扁平）：嵌套优先

---

## 阶段 6：large_order_ratio 量纲修复（需求 8）

- [ ] 6.1 修复 _enrich_money_flow_factors 中的量纲转换
  - 在 `screen_data_provider.py` 的 `_enrich_money_flow_factors()` 中
  - 将 `float(latest_row.large_order_ratio)` 改为 `float(latest_row.large_order_ratio) * 100.0`
  - 添加安全判断：`raw_ratio <= 1.0` 时乘以 100，否则直接使用（兼容两种存储格式）
  - 同时修改写入 Factor_Dict 的 `large_order_ratio` 原始数值也使用百分比格式

- [ ] 6.2 编写量纲转换单元测试
  - 测试：`large_order_ratio=0.35` → 传递给 `check_large_order_signal` 的值为 `35.0`
  - 测试：`large_order_ratio=35.0` → 直接使用 `35.0`（兼容百分比格式存储）
  - 测试：`large_order_ratio=None` → 降级为 `0.0`

---

## 阶段 7：假突破检测逻辑修复（需求 9）

- [ ] 7.1 修改 _detect_all_breakouts 数据窗口前移
  - 在 `screen_data_provider.py` 的 `_detect_all_breakouts()` 中
  - 将突破检测数据切片改为 `closes[:-1]`、`highs[:-1]`、`lows[:-1]`、`volumes[:-1]`
  - 将确认日收盘价改为 `closes[-1]`
  - 添加长度保护：`len(closes) < 2` 时返回空列表

- [ ] 7.2 修改三种突破检测的调用方式
  - `detect_box_breakout` 使用 `detect_closes, detect_highs, detect_lows, detect_volumes`
  - `detect_previous_high_breakout` 使用 `detect_closes, detect_volumes`
  - `detect_descending_trendline_breakout` 使用 `detect_closes, detect_highs, detect_volumes`
  - `check_false_breakout` 使用 `confirm_close`（即 `closes[-1]`）

- [ ] 7.3 编写假突破检测单元测试
  - 测试：突破日站稳但确认日跌回 → `is_false_breakout=True`
  - 测试：突破日和确认日均站稳 → `is_false_breakout=False`
  - 测试：数据不足（`len(closes) < 2`）→ 返回空列表
  - 测试：`confirm_days=0` 时跳过假突破检测

---

## 阶段 8：增量缓存序列化修复（需求 10）

- [ ] 8.1 修改 _serialize_factor_dict 的 Decimal 处理
  - 在 `app/tasks/screening.py` 中
  - 将 `Decimal` → `str` 改为 `Decimal` → `float`
  - 对列表中的 `Decimal` 元素同样转换为 `float`

- [ ] 8.2 编写序列化/反序列化单元测试
  - 测试：`Decimal("25.50")` 序列化后反序列化为 `25.5`（float）
  - 测试：`[Decimal("25.50"), Decimal("26.00")]` 序列化后反序列化为 `[25.5, 26.0]`
  - 测试：非 Decimal 值（int、float、str、bool）不受影响

---

## 阶段 9：前端 screener store 修复（需求 11）

- [ ] 9.1 修复 fetchResults 响应处理
  - 在 `frontend/src/stores/screener.ts` 的 `fetchResults()` 中
  - 处理分页包装响应：从 `res.data.items` 提取数组
  - 兼容直接数组响应：`Array.isArray(data) ? data : (data.items ?? [])`

- [ ] 9.2 修复 ScreenItem.signals 类型定义
  - 新增 `SignalDetail` 接口：`category`、`label`、`strength`、`description`、`freshness`、`is_fake_breakout`
  - 将 `ScreenItem.signals` 类型从 `Record<string, unknown>` 改为 `SignalDetail[]`

- [ ] 9.3 前端类型验证
  - 运行 `npm run type-check` 确认无类型错误
  - 检查 `ScreenerResultsView.vue` 等消费 `ScreenItem` 的组件是否兼容新类型

---

## 阶段 10：集成验证

- [ ] 10.1 端到端集成测试
  - 构造包含 Tushare 因子条件（如 `kdj_k > 50`、`chip_winner_rate > 60`）的策略
  - 使用 mock 数据执行完整选股流程
  - 验证因子数据非 None，策略评估正常工作

- [ ] 10.2 回归测试
  - 运行现有全部 screener 相关测试，确保无回归
  - 运行属性测试，确保不变量保持

- [ ] 10.3 日志验证
  - 检查 `_enrich_stk_factor_factors` 的匹配率日志
  - 确认匹配率从 0% 提升到预期水平（接近 100%）

- [ ] 10.4 前端验证
  - 运行 `npm run type-check` 和 `npm test` 确认前端无回归
  - 验证选股结果页面正确展示信号详情
