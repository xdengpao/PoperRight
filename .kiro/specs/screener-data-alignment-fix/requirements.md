# 需求文档：智能选股数据对齐与算法修复

## 简介

本需求文档定义了对现有智能选股系统（`app/services/screener/`）的数据对齐修复与算法优化计划。

经过对选股全链路的深入分析，发现以下核心问题导致选股结果严重失真：

1. **股票代码格式不一致**：`stock_info` 表使用纯数字格式（`"000001"`），Tushare 导入表使用带后缀格式（`"000001.SZ"`），导致约 30 个因子数据匹配失败，全部降级为 None
2. **StrategyEngine 加权得分计算缺陷**：不同量纲的因子原始值直接加权求和，结果无实际意义
3. **信号重复构建**：`factor_editor` 路径与模块路径同时执行时产生重复信号
4. **涨停股过滤失效**：`daily_change_pct` 因子未计算，风控过滤永远不生效
5. **PSY/OBV 因子空壳**：注册但无数据来源，用户配置后不生效
6. **StrategyConfig 重复定义**：`schemas.py` 中存在两个 `StrategyConfig` 类定义，第一个被静默覆盖
7. **前端 indicator_params 嵌套结构与后端 from_dict 不匹配**：用户自定义技术指标参数被静默忽略
8. **large_order_ratio 量纲不匹配**：数据库存储比率格式（0.30），阈值使用百分比格式（30.0），大单信号永远为 False
9. **profit_growth/revenue_growth 因子无数据来源**：注册并参与百分位排名但从未写入 Factor_Dict
10. **假突破检测使用错误日期**：突破检测和假突破验证使用同一份数据切片，无法获取"次日"数据
11. **实时选股增量缓存 Decimal 序列化问题**：Decimal 序列化为字符串后反序列化不还原为数值类型
12. **前端 screener store 响应类型不匹配**：`fetchResults` 期望数组但后端返回分页包装对象

## 术语表

- **ScreenDataProvider**：选股数据提供服务，位于 `app/services/screener/screen_data_provider.py`，负责从数据库加载股票数据并计算派生因子
- **ScreenExecutor**：选股执行器，位于 `app/services/screener/screen_executor.py`，封装盘后与盘中选股核心逻辑
- **StrategyEngine**：多因子策略引擎，位于 `app/services/screener/strategy_engine.py`，执行 AND/OR 逻辑评估与加权评分
- **Factor_Dict**：因子字典，`ScreenDataProvider._build_factor_dict()` 为每只股票生成的 `{factor_name: value}` 字典
- **ts_code**：Tushare 数据接口使用的股票代码格式，带市场后缀，如 `"000001.SZ"`、`"600000.SH"`
- **symbol**：系统内部业务表使用的股票代码格式，纯 6 位数字，如 `"000001"`、`"600000"`
- **KlineRepository**：K 线数据仓储层，位于 `app/services/data_engine/kline_repository.py`
- **stk_factor**：Tushare 导入的股票技术面因子表，使用 `ts_code` 字段（带后缀格式）
- **cyq_perf**：Tushare 导入的每日筹码及胜率表，使用 `ts_code` 字段（带后缀格式）
- **margin_detail**：Tushare 导入的融资融券交易明细表，使用 `ts_code` 字段（带后缀格式）
- **moneyflow_ths/dc**：Tushare 导入的个股资金流向表，使用 `ts_code` 字段（带后缀格式）
- **limit_list/step**：Tushare 导入的涨跌停数据表，使用 `ts_code` 字段（带后缀格式）
- **top_list**：Tushare 导入的龙虎榜数据表，使用 `ts_code` 字段（带后缀格式）
- **index_weight**：Tushare 导入的指数成分权重表，使用 `con_code` 字段（带后缀格式）
- **weighted_score**：StrategyEngine 计算的加权得分，用于因子评估结果的综合评分
- **IndicatorParamsConfig**：技术指标参数配置数据类，位于 `app/core/schemas.py`，使用扁平键（`macd_fast`、`boll_period` 等）
- **IndicatorParamsConfigIn**：API 层技术指标参数输入模型，位于 `app/api/v1/screen.py`，使用嵌套结构（`macd.fast_period`、`boll.period` 等）
- **check_false_breakout**：假突破检测函数，位于 `app/services/screener/breakout.py`，检查突破后次日收盘价是否跌回压力位以下
- **Redis_Factor_Cache**：Redis 因子缓存，用于存储盘中增量计算的中间因子数据

## 需求

---

### 需求 1：Tushare 因子数据股票代码格式对齐

**用户故事：** 作为量化交易员，我希望选股系统能正确匹配 Tushare 导入的因子数据（技术面、筹码、两融、资金流、打板、指数），以便这些因子能真正参与选股评估而非全部降级为 None。

#### 验收标准

1. WHEN `_enrich_stk_factor_factors()` 构建 `row_map` 时，THE ScreenDataProvider SHALL 将 `StkFactor.ts_code` 转换为纯数字格式（去除 `.SH`/`.SZ`/`.BJ` 后缀）作为映射键，确保与 `stocks_data` 的 symbol 键（纯数字格式）正确匹配。
2. WHEN `_enrich_chip_factors()` 构建 `row_map` 时，THE ScreenDataProvider SHALL 将 `CyqPerf.ts_code` 转换为纯数字格式作为映射键。
3. WHEN `_enrich_margin_factors()` 按 `ts_code` 分组时，THE ScreenDataProvider SHALL 将 `MarginDetail.ts_code` 转换为纯数字格式作为分组键。
4. WHEN `_enrich_enhanced_money_flow_factors()` 构建 `row_map` 时，THE ScreenDataProvider SHALL 将 `MoneyflowThs.ts_code` 和 `MoneyflowDc.ts_code` 转换为纯数字格式作为映射键。
5. WHEN `_enrich_board_hit_factors()` 按 `ts_code` 分组时，THE ScreenDataProvider SHALL 将 `LimitList.ts_code`、`LimitStep.ts_code`、`TopList.ts_code` 转换为纯数字格式作为分组键和映射键。
6. WHEN `_enrich_index_factors()` 构建 `stock_index_map` 时，THE ScreenDataProvider SHALL 将 `IndexWeight.con_code` 转换为纯数字格式作为映射键。
7. THE ScreenDataProvider SHALL 提供统一的代码格式转换辅助方法 `_strip_market_suffix(ts_code: str) -> str`，实现 `ts_code.split(".")[0]` 逻辑，所有 `_enrich_*` 方法统一调用该方法。
8. WHEN 转换后的纯数字代码在 `stocks_data` 中存在对应记录时，THE ScreenDataProvider SHALL 将因子数据正确写入该股票的 Factor_Dict，不再降级为 None。
9. THE ScreenDataProvider SHALL 在 `_enrich_stk_factor_factors()` 执行完成后记录 INFO 级别日志，包含成功匹配的股票数量和总查询数量，便于验证匹配率。

---

### 需求 2：KlineRepository 查询与存储的代码格式统一

**用户故事：** 作为量化交易员，我希望 K 线数据的存储和查询使用一致的股票代码格式，以便选股数据加载不会因格式不匹配而查询到空结果。

#### 验收标准

1. THE KlineRepository `query()` 方法 SHALL 在执行查询前对传入的 `symbol` 参数进行格式标准化：若 symbol 包含 `.` 后缀则去除后缀，确保与 `bulk_insert()` 存储的纯数字格式一致。
2. THE KlineRepository `bulk_insert()` 方法 SHALL 保持现有的 `symbol.split(".")[0]` 去后缀逻辑不变。
3. WHEN `ScreenDataProvider.load_screen_data()` 调用 `kline_repo.query(symbol=stock.symbol)` 时，THE KlineRepository SHALL 能正确查询到该股票的 K 线数据，无论传入的 symbol 是纯数字格式还是带后缀格式。
4. THE AdjFactorRepository `query_batch()` 方法 SHALL 对传入的 `symbols` 列表中的每个代码进行同样的格式标准化处理。

---

### 需求 3：StrategyEngine 加权得分归一化修复

**用户故事：** 作为量化交易员，我希望多因子策略的加权得分能正确反映各因子的综合评估结果，以便策略筛选排序有实际参考价值。

#### 验收标准

1. THE StrategyEngine `evaluate()` 方法 SHALL 对每个因子的评估结果进行归一化处理后再加权求和，而非直接使用因子原始值。
2. FOR BOOLEAN 类型因子（如 `macd`、`boll`、`rsi`、`ma_support`、`breakout`、`trix`、`sector_trend`、`dragon_tiger_net_buy`、`first_limit_up`、`small_net_outflow`、`obv_signal`），THE StrategyEngine SHALL 将通过的因子归一化为 100.0，未通过的归一化为 0.0。
3. FOR ABSOLUTE 类型因子（如 `ma_trend`、`rsi_current`、`kdj_k`、`kdj_d`、`kdj_j`、`cci`、`wr`、`bias`、`psy`），THE StrategyEngine SHALL 根据因子的阈值和实际值计算归一化分数：当因子通过条件时，基于实际值相对阈值的距离映射到 [60, 100] 区间；未通过时映射到 [0, 60) 区间。
4. FOR PERCENTILE 类型因子，THE StrategyEngine SHALL 直接使用百分位值（已在 0-100 范围内）作为归一化分数。
5. FOR INDUSTRY_RELATIVE 类型因子，THE StrategyEngine SHALL 将行业相对值映射到 [0, 100] 区间：相对值 1.0 映射为 50 分，低于行业中位数映射到 [0, 50)，高于行业中位数映射到 (50, 100]。
6. FOR RANGE 类型因子，THE StrategyEngine SHALL 当值在区间内时归一化为 100.0，不在区间内时根据偏离程度映射到 [0, 100) 区间。
7. THE StrategyEngine `evaluate()` 方法 SHALL 使用归一化后的分数替代原始值计算 `weighted_score`，公式为：`weighted_score = Σ(normalized_score × weight) / Σ(weight)`，结果保证在 [0, 100] 闭区间内。

---

### 需求 4：选股信号去重

**用户故事：** 作为量化交易员，我希望选股结果中每个因子只产生一个信号，以便信号列表清晰准确、不产生误导。

#### 验收标准

1. WHEN `factor_editor` 模块启用时，THE ScreenExecutor `_execute()` 方法 SHALL 在构建信号列表时对 `(category, label)` 元组进行去重，同一因子不产生重复的 SignalDetail。
2. THE ScreenExecutor SHALL 优先保留非 `factor_editor` 路径生成的信号（因其包含更丰富的上下文信息如 `strength`、`signal_type`），当 `factor_editor` 路径产生相同 `(category, label)` 的信号时跳过。
3. WHEN 去重后信号列表为空且 `factor_editor` 未启用时，THE ScreenExecutor SHALL 跳过该股票，不生成 ScreenItem。

---

### 需求 5：涨跌幅因子计算与风控过滤修复

**用户故事：** 作为量化交易员，我希望选股结果能正确过滤涨停股和连续大涨股，以便避免追高买入。

#### 验收标准

1. THE ScreenDataProvider `_build_factor_dict()` 方法 SHALL 计算 `daily_change_pct` 因子：当 K 线序列长度 >= 2 时，`daily_change_pct = (latest_close - prev_close) / prev_close * 100`；长度不足时设为 0.0。
2. THE ScreenDataProvider `_build_factor_dict()` 方法 SHALL 将 `daily_change_pct` 写入 Factor_Dict，供 ScreenExecutor 风控过滤使用。
3. WHEN `daily_change_pct > 9.0` 时，THE ScreenExecutor 风控过滤 SHALL 将该股票从选股结果中剔除。
4. THE ScreenDataProvider `_build_factor_dict()` 方法 SHALL 同时计算 `change_pct_3d` 因子（近 3 个交易日累计涨幅），当 K 线序列长度 >= 4 时，`change_pct_3d = (latest_close - close_3d_ago) / close_3d_ago * 100`；长度不足时设为 0.0。
5. WHEN `change_pct_3d > 20.0` 时，THE ScreenExecutor 风控过滤 SHALL 将该股票从选股结果中剔除（对应需求 9.4：连续 3 个交易日累计涨幅超过 20%）。

---

### 需求 6：PSY 和 OBV 因子本地计算实现

**用户故事：** 作为量化交易员，我希望 PSY（心理线）和 OBV（能量潮）因子能基于本地 K 线数据计算得出，以便这两个已注册的因子能真正参与选股评估。

#### 验收标准

1. THE ScreenDataProvider SHALL 在 `_build_factor_dict()` 中基于 K 线收盘价序列计算 PSY 因子：`PSY = 最近 N 日中上涨天数 / N × 100`，默认 N=12，结果范围 [0, 100]。
2. THE ScreenDataProvider SHALL 在 `_build_factor_dict()` 中基于 K 线收盘价和成交量序列计算 OBV 信号因子：当 OBV 最近 5 日均值 > OBV 最近 20 日均值时，`obv_signal = True`，否则为 `False`。
3. WHEN K 线序列长度不足以计算 PSY 或 OBV 时，THE ScreenDataProvider SHALL 将对应因子设为 None，不抛出异常。
4. THE ScreenDataProvider SHALL 移除 `_enrich_stk_factor_factors()` 中 `fd["psy"] = None` 和 `fd["obv_signal"] = None` 的硬编码降级逻辑，改为使用 `_build_factor_dict()` 中计算的值。
5. THE ScreenDataProvider SHALL 在 `_build_factor_dict()` 中同时为 `profit_growth` 和 `revenue_growth` 因子提供数据来源：从 Tushare 导入的财务数据表中查询净利润同比增长率和营收同比增长率，或在无数据时显式设为 None，确保因子注册表中的因子定义与实际数据供给一致。

---

### 需求 7：StrategyConfig 重复定义清理与 indicator_params 前后端数据契约修复

**用户故事：** 作为量化交易员，我希望在选股策略页面自定义的技术指标参数（MACD 快慢线周期、BOLL 标准差倍数、RSI 区间等）能被后端正确接收和使用，以便策略参数调优有实际效果。

#### 验收标准

1. THE `app/core/schemas.py` SHALL 移除第一个 `StrategyConfig` 类定义（第 239 行附近，`indicator_params: dict` 版本），仅保留第二个完整版本（第 497 行附近，`indicator_params: IndicatorParamsConfig` 版本），消除类重复定义的隐患。
2. THE `IndicatorParamsConfig.from_dict()` 方法 SHALL 同时支持扁平键格式（`{"macd_fast": 12, "boll_period": 20}`）和嵌套键格式（`{"macd": {"fast_period": 12}, "boll": {"period": 20}}`），当检测到嵌套结构时自动展开为扁平键。
3. WHEN 前端通过 `POST /api/v1/screen/run` 或 `PUT /api/v1/strategies/{id}` 提交包含嵌套 `indicator_params` 的策略配置时，THE StrategyConfig SHALL 正确解析用户自定义的 MACD、BOLL、RSI、DMA 参数，不再静默回退为默认值。
4. THE `IndicatorParamsConfig.from_dict()` SHALL 在解析嵌套格式时按以下映射规则展开：`macd.fast_period` → `macd_fast`，`macd.slow_period` → `macd_slow`，`macd.signal_period` → `macd_signal`，`boll.period` → `boll_period`，`boll.std_dev` → `boll_std_dev`，`rsi.period` → `rsi_period`，`rsi.lower_bound` → `rsi_lower`，`rsi.upper_bound` → `rsi_upper`，`dma.short_period` → `dma_short`，`dma.long_period` → `dma_long`。

---

### 需求 8：large_order_ratio 量纲统一

**用户故事：** 作为量化交易员，我希望大单成交占比信号能正确触发，以便资金面筛选能识别出大单活跃的个股。

#### 验收标准

1. THE ScreenDataProvider `_enrich_money_flow_factors()` 方法 SHALL 在将 `MoneyFlow.large_order_ratio` 传递给 `check_large_order_signal()` 之前，将比率格式（0-1 范围，如 `0.30`）转换为百分比格式（0-100 范围，如 `30.0`），与 `DEFAULT_LARGE_ORDER_RATIO_THRESHOLD = 30.0` 的量纲一致。
2. WHEN `MoneyFlow.large_order_ratio` 值为 `0.35`（表示 35%）时，THE ScreenDataProvider SHALL 将其转换为 `35.0` 后传递给 `check_large_order_signal()`，使其正确超过 30.0 阈值并触发大单活跃信号。
3. THE ScreenDataProvider SHALL 同时将写入 Factor_Dict 的 `large_order_ratio` 原始数值也转换为百分比格式，确保百分位排名计算和因子条件评估使用统一量纲。

---

### 需求 9：假突破检测逻辑修复

**用户故事：** 作为量化交易员，我希望假突破检测能正确识别突破后未能站稳的情况，以便过滤掉无效的突破信号、避免追高买入。

#### 验收标准

1. THE ScreenDataProvider `_detect_all_breakouts()` 方法 SHALL 采用数据窗口前移方式实现假突破检测：使用 `closes[:-1]`（去掉最后一天）作为突破检测的数据切片，使用 `closes[-1]`（最后一天）作为突破后的确认日收盘价。
2. WHEN 突破检测函数（`detect_box_breakout`、`detect_previous_high_breakout`、`detect_descending_trendline_breakout`）在 `closes[:-1]` 切片上检测到突破信号时，THE ScreenDataProvider SHALL 将 `closes[-1]`（确认日收盘价）传递给 `check_false_breakout()` 作为 `next_day_close` 参数。
3. WHEN 确认日收盘价 `closes[-1]` 低于突破压力位时，THE `check_false_breakout()` SHALL 将该信号标记为假突破（`is_false_breakout=True`），并将 `generates_buy_signal` 设为 False。
4. WHEN K 线序列长度不足以同时提供突破检测窗口和确认日数据时（即 `len(closes) < 2`），THE ScreenDataProvider SHALL 跳过假突破检测，直接使用原始突破信号。
5. THE `_detect_all_breakouts()` 方法 SHALL 同步调整 `highs`、`lows`、`volumes` 切片与 `closes` 切片保持一致（均使用 `[:-1]`），确保突破检测函数接收的数据维度对齐。

---

### 需求 10：实时选股增量缓存序列化修复

**用户故事：** 作为量化交易员，我希望盘中实时选股的增量缓存机制能正确保存和恢复因子数据的数值类型，以便增量更新后的技术指标计算结果准确。

#### 验收标准

1. THE `_serialize_factor_dict()` 函数 SHALL 将 `Decimal` 类型值转换为 `float`（而非 `str`）后再进行 JSON 序列化，确保从 Redis 反序列化后的数据保持数值类型。
2. THE `_serialize_factor_dict()` 函数 SHALL 对列表类型值（如 `closes`、`highs`、`lows`、`volumes`、`amounts`、`turnovers`）中的 `Decimal` 元素同样转换为 `float`。
3. WHEN 从 Redis 反序列化因子缓存数据时，THE `_incremental_update()` 函数 SHALL 确保合并后的因子字典中所有数值型字段为 `float` 或 `int` 类型，不包含字符串类型的数值。
4. THE 序列化/反序列化过程 SHALL 保持数值精度损失在可接受范围内（`Decimal` → `float` 的精度损失对选股计算无实质影响）。

---

### 需求 11：前端 screener store 响应类型修复

**用户故事：** 作为量化交易员，我希望选股结果页面能正确加载和展示选股数据，以便查看和分析选股结果。

#### 验收标准

1. THE `frontend/src/stores/screener.ts` 的 `fetchResults()` 方法 SHALL 正确处理后端 `GET /screen/results` 返回的分页包装响应（`{ total, page, page_size, items }`），从 `items` 字段提取选股结果数组。
2. THE `frontend/src/stores/screener.ts` 的 `ScreenItem` 接口 SHALL 将 `signals` 字段类型从 `Record<string, unknown>` 修正为 `SignalDetail[]`（信号详情数组），与后端实际返回的数据结构一致。
3. THE `frontend/src/stores/screener.ts` SHALL 新增 `SignalDetail` 接口定义，包含 `category`、`label`、`strength`、`description`、`freshness`、`is_fake_breakout` 字段，与后端 `SignalDetail` 数据类的序列化输出一致。
