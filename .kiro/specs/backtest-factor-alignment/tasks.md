# 任务列表：回测引擎因子对齐优化

## 阶段 1：BacktestConfig 扩展与基础数据加载（需求 1, 2, 8, 11）

- [ ] 1.1 扩展 BacktestConfig 数据类
  - 在 `app/core/schemas.py` 的 `BacktestConfig` 中新增三个布尔字段
  - `enable_fundamental_data: bool = False`
  - `enable_money_flow_data: bool = False`
  - `enable_tushare_factors: bool = False`
  - 更新 `to_dict()` / `from_dict()` 方法，向后兼容旧配置

- [ ] 1.2 扩展 BacktestTask 基本面数据加载
  - 在 `app/tasks/backtest.py` 中，当 `enable_fundamental_data=True` 时
  - 从 `stock_info` 表批量查询 pe_ttm/pb/roe/market_cap
  - 构建 `{symbol: {pe_ttm, pb, roe, market_cap}}` 映射字典
  - 加载失败时记录 WARNING 日志，使用 None 继续

- [ ] 1.3 扩展 BacktestTask 资金流向数据加载
  - 当 `enable_money_flow_data=True` 时
  - 从 `money_flow` 表批量查询回测日期范围内的数据
  - 构建 `{symbol: {date_str: {main_net_inflow, large_order_ratio}}}` 嵌套映射
  - 注意 `large_order_ratio` 量纲转换（比率→百分比）

- [ ] 1.4 扩展 BacktestTask Tushare 因子数据加载
  - 当 `enable_tushare_factors=True` 时，批量查询以下表：
  - `stk_factor`：KDJ/CCI/WR/TRIX/BIAS，使用 `_strip_market_suffix()` 转换 ts_code
  - `cyq_perf`：筹码数据
  - `margin_detail`：两融数据
  - `moneyflow_ths`/`moneyflow_dc`：增强资金流数据（优先 THS，回退 DC）
  - `limit_list`/`limit_step`/`top_list`：打板数据
  - `index_dailybasic`/`index_tech`/`index_weight`：指数数据
  - 所有数据按 `{symbol: {date_str: record}}` 格式组织

- [ ] 1.5 扩展 BacktestTask 板块数据加载（始终加载）
  - 从 `sector_kline` 表查询板块行情数据
  - 从 `sector_constituent` 表查询板块成分股映射
  - 从 `sector_info` 表查询板块名称映射
  - 当 `enable_fundamental_data=True` 时额外查询行业映射

- [ ] 1.6 扩展 BacktestEngine.run_backtest 方法签名
  - 新增参数：fundamental_data, money_flow_data, tushare_factor_data, sector_kline_data, stock_sector_map, industry_map, sector_info_map
  - 所有新增参数默认 None，向后兼容
  - 在 `_run_backtest_strategy_driven` 中存储为实例属性

---

## 阶段 2：BacktestFactorProvider 新模块（需求 3, 4, 5, 6, 11, 12）

- [ ] 2.1 创建 BacktestFactorProvider 模块
  - 新建 `app/services/backtest_factor_provider.py`
  - 实现 `enrich_factor_dicts()` 主入口函数
  - 所有方法为纯函数/静态方法，不依赖数据库会话

- [ ] 2.2 实现基本面因子填充
  - `_fill_fundamental_fields()`：从 fundamental_data 映射填充 pe_ttm/pb/roe/market_cap
  - 禁用时设为 None，缺失数据时设为 None

- [ ] 2.3 实现资金面因子填充
  - `_fill_money_flow_fields()`：从 money_flow_data 映射按交易日填充
  - 禁用时设为 None，缺失数据时设为 None

- [ ] 2.4 实现 Tushare 因子填充
  - `_fill_tushare_factor_fields()`：从 tushare_factor_data 映射按交易日填充
  - 包含 stk_factor/cyq_perf/margin_detail/moneyflow/limit/index 全部因子
  - 禁用时设为 None/默认值

- [ ] 2.5 实现 PSY/OBV 因子计算
  - 在 `enrich_factor_dicts()` 中调用 `calculate_psy()` 和 `calculate_obv_signal()`
  - 基于 K 线数据本地计算，不依赖 Tushare 数据，始终计算

- [ ] 2.6 实现 volume_price 计算
  - `_compute_volume_price()`：基于 amounts 序列计算近 20 日日均成交额
  - 始终计算，不依赖可选开关

- [ ] 2.7 实现板块强势计算
  - `_compute_sector_strength()`：复用 SectorStrengthFilter 纯函数
  - 始终计算，板块数据不可用时降级为默认值

- [ ] 2.8 实现百分位排名条件计算
  - `_compute_conditional_percentile_ranks()`：根据开关条件选择性计算
  - 复用 ScreenDataProvider._compute_percentile_ranks 静态方法

- [ ] 2.9 实现行业相对值条件计算
  - `_compute_conditional_industry_relative()`：根据开关条件选择性计算
  - 复用 ScreenDataProvider._compute_industry_relative_values 静态方法

---

## 阶段 3：BacktestEngine 因子字典对齐（需求 6, 12）

- [ ] 3.1 更新 _generate_buy_signals 因子字典
  - 移除硬编码的 `pe_ttm: None, pb: None, roe: None, market_cap: None`
  - 移除硬编码的 `money_flow: False, large_order: False`
  - 初始化所有新增字段为 None/默认值
  - 添加信号增强字段：macd_strength, macd_signal_type, boll_near_upper_band, boll_hold_days, rsi_current, rsi_consecutive_rising
  - 添加 daily_change_pct, change_pct_3d 计算
  - 添加 breakout_list 字段（使用数据窗口前移方式）
  - 构建完成后调用 `enrich_factor_dicts()`

- [ ] 3.2 更新 _generate_buy_signals_optimized 因子字典
  - 与 3.1 相同的修改，确保两条路径一致
  - 优化路径从 IndicatorCache 读取信号增强字段

- [ ] 3.3 更新 _precompute_indicators 缓存信号增强字段
  - 在预计算阶段缓存 macd_strength, macd_signal_type 等字段
  - 确保优化路径能从缓存中读取这些字段

---

## 阶段 4：涨跌停价格修正（需求 13）

- [ ] 4.1 修改 _calc_limit_prices 方法
  - 新增 `symbol` 参数
  - 根据股票代码前缀判断涨跌停幅度：300/688→20%，8/4→30%，其他→10%

- [ ] 4.2 更新所有调用点
  - 买入判断（`open_price >= limit_up`）：传入 symbol
  - 卖出判断（`open_price <= limit_down`）：传入 symbol
  - 最高价跟踪（`close < limit_up`）：传入 symbol

- [ ] 4.3 编写涨跌停修正单元测试
  - 测试主板股票（600xxx）：±10%
  - 测试创业板股票（300xxx）：±20%
  - 测试科创板股票（688xxx）：±20%
  - 测试北交所股票（8xxxxx）：±30%

---

## 阶段 5：持仓天数修正（需求 14）

- [ ] 5.1 修正 buy_trade_day_index 赋值
  - 将 `buy_trade_day_index=state.trade_day_index` 改为 `state.trade_day_index + 1`
  - 同步修正 `HoldingContext.entry_bar_index`

- [ ] 5.2 编写持仓天数修正单元测试
  - 测试 max_holding_days=5 时，实际持仓恰好 5 个交易日后触发强制卖出
  - 测试边界：买入当日不计入持仓天数

---

## 阶段 6：DANGER 风控对齐（需求 15）

- [ ] 6.1 移除 DANGER 完全阻断逻辑
  - 删除 `_generate_buy_signals` 中的 `if market_risk_state == "DANGER": return []`
  - 删除 `_generate_buy_signals_optimized` 中的同样逻辑

- [ ] 6.2 传递 index_closes 给 ScreenExecutor
  - 在调用 `ScreenExecutor.run_eod_screen()` 时传入 `index_closes` 参数
  - 由 ScreenExecutor 内部按 `trend_score >= 95` 过滤 DANGER 状态

- [ ] 6.3 编写 DANGER 风控对齐测试
  - 测试 DANGER 状态下 trend_score >= 95 的股票能通过
  - 测试 DANGER 状态下 trend_score < 95 的股票被过滤
  - 对比回测与实时选股在 DANGER 状态下的行为一致性

---

## 阶段 7：优化路径趋势评分算法修正（需求 16）— 最高优先级

- [ ] 7.1 替换 _precompute_indicators 中的趋势评分逻辑
  - 移除内联的距离评分公式（`50 + pct_above * 10`）
  - 移除内联的斜率评分逻辑（等权平均、无 slope_threshold）
  - 改为对每个 bar 位置调用 `score_ma_trend(closes[:i+1], periods, slope_threshold=slope_threshold)`
  - 从 `strategy_config.ma_trend.slope_threshold` 读取 slope_threshold 参数

- [ ] 7.2 验证两条路径评分一致性
  - 构造测试数据，分别通过优化路径和非优化路径计算 ma_trend 评分
  - 验证两条路径在相同输入下产生完全一致的评分（误差 < 0.01）
  - 覆盖边界情况：全部上涨、全部下跌、横盘震荡

- [ ] 7.3 性能验证
  - 对比修改前后 _precompute_indicators 的执行时间
  - 确保 3000 只股票 × 250 个交易日的场景下性能可接受
  - 如有性能问题，考虑预计算 MA 序列后传入 score_ma_trend 的 ma_dict 参数

---

## 阶段 8：实时选股指标参数一致性修复（需求 17）

- [ ] 8.1 修改 ScreenDataProvider._build_factor_dict 传递自定义指标参数
  - 从 `strategy_config` 中提取 `indicator_params` 配置
  - 将 macd_fast/macd_slow/macd_signal 传递给 `detect_macd_signal()`
  - 将 boll_period/boll_std_dev 传递给 `detect_boll_signal()`
  - 将 rsi_period/rsi_lower/rsi_upper 传递给 `detect_rsi_signal()`
  - 将 dma_short/dma_long 传递给 `calculate_dma()`
  - 兼容 IndicatorParamsConfig 对象和 dict 两种格式

- [ ] 8.2 修复非优化路径 slope_threshold 传递
  - 在 `_generate_buy_signals` 中将 `slope_threshold` 传递给 `score_ma_trend()`
  - 从 `config.strategy_config.ma_trend.slope_threshold` 读取

- [ ] 8.3 编写指标参数一致性测试
  - 测试自定义 macd_fast=8 时，ScreenDataProvider 和 BacktestEngine 产生相同的 MACD 信号
  - 测试默认参数时行为不变

---

## 阶段 9：回测 API 层扩展（需求 18）

- [ ] 9.1 扩展 BacktestRunRequest 模型
  - 新增 enable_fundamental_data、enable_money_flow_data、enable_tushare_factors 字段
  - 默认值均为 False

- [ ] 9.2 修改 run_backtest 端点传递新参数
  - 将三个开关字段传递给 Celery 任务

- [ ] 9.3 前端 BacktestView 新增数据源选项
  - 新增折叠面板，包含三个开关控件
  - 添加提示文本说明各数据源用途
  - 将开关值包含在回测请求参数中

---

## 阶段 10：向后兼容性保障（需求 9）

- [ ] 10.1 编写向后兼容性测试
  - 测试不传新参数时 run_backtest 正常工作
  - 测试旧版 BacktestConfig（无新字段）正确使用默认值
  - 测试旧版 StrategyConfig（无 sector_config）使用默认 SectorScreenConfig
  - 测试仅使用技术面因子的策略回测结果与优化前一致

---

## 阶段 11：属性测试与集成验证

- [ ] 11.1 编写 BacktestFactorProvider 属性测试
  - Property 1：禁用开关时因子字段全部为 None
  - Property 2：启用开关时因子字段从数据映射正确填充
  - Property 3：volume_price 计算正确性
  - Property 4：百分位排名条件计算
  - Property 5：因子字典结构完整性
  - Property 6：向后兼容性
  - Property 7：优化路径与非优化路径趋势评分一致性

- [ ] 11.2 编写 BacktestFactorProvider 单元测试
  - 测试各 _fill_* 方法的正常和异常路径
  - 测试 _compute_* 方法的边界条件
  - 测试 enrich_factor_dicts 完整流水线

- [ ] 11.3 编写 BacktestTask 数据加载测试
  - 测试各开关启用/禁用时的数据加载行为
  - 测试数据库查询失败时的优雅降级
  - 测试 Tushare 因子数据的 ts_code 格式转换

- [ ] 11.4 端到端集成测试
  - 使用包含 Tushare 因子条件的策略执行回测
  - 验证因子数据非 None，策略评估正常工作
  - 对比两条路径（普通/优化）产生相同的趋势评分和因子字典结构
  - 验证涨跌停修正对创业板/科创板股票的影响
  - 验证自定义指标参数在实时选股和回测中产生一致的信号
