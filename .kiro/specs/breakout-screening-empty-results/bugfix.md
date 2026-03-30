# 缺陷修复需求文档

## 简介

智能选股系统的所有五个选股模块（`ma_trend`、`indicator_params`、`breakout`、`volume_price`、`factor_editor`）均存在相同的系统性缺陷：`ScreenDataProvider._build_factor_dict()` 仅提供原始 K 线行情数据（收盘价、最高价、最低价、成交量等序列）和基本面数据（PE/PB/ROE/市值），但从未调用任何选股模块的计算函数来生成派生因子值。

这导致 `stock_data` 字典中不包含 `ma_trend`、`macd`、`boll`、`rsi`、`dma`、`breakout`、`money_flow`、`large_order`、`volume_price` 等因子键。`StrategyEngine.evaluate()` 仅从 `stock_data` 字典中按因子名称读取预计算值，不执行任何计算逻辑。当这些键不存在时，`FactorEvaluator.evaluate()` 因 `value is None` 始终返回 `passed=False`，导致所有模块的选股结果均为空或无信号。

该缺陷涉及两层问题：

1. **孤立代码问题（系统性）**：五个选股模块的核心算法函数从未被选股流水线调用：
   - `ma_trend.py`：`score_ma_trend()`、`detect_bullish_alignment()`、`detect_ma_support()` 从未被调用
   - `indicators.py`：`detect_macd_signal()`、`detect_boll_signal()`、`detect_rsi_signal()`、`calculate_dma()` 从未被调用
   - `breakout.py`：`detect_box_breakout()`、`detect_previous_high_breakout()`、`validate_breakout()` 从未被调用
   - `volume_price.py`：`check_turnover_rate()`、`detect_volume_price_divergence()`、`check_money_flow_signal()`、`check_large_order_signal()`、`check_sector_resonance()` 从未被调用
   - `factor_editor`（策略引擎）：`FactorEvaluator.evaluate()` 读取的因子值全部为 `None`，因为上游未计算

2. **enabled_modules 逻辑缺陷**：当用户仅启用非 `factor_editor` 模块时，`ScreenExecutor._execute()` 跳过 `StrategyEngine.screen_stocks()`，所有股票"初始通过"。但信号构建阶段仅从 `eval_result.factor_results` 中提取已通过的因子，由于所有因子数据缺失，信号列表为空，选股结果无实质内容。

## 缺陷分析

### 当前行为（缺陷）

**均线趋势模块（ma_trend）**

1.1 WHEN 用户启用 `ma_trend` 模块并执行选股 THEN `ScreenDataProvider._build_factor_dict()` 返回的因子字典中不包含 `ma_trend` 键，`score_ma_trend()`、`detect_bullish_alignment()`、`detect_ma_support()` 从未被调用，趋势打分和多头排列识别结果缺失

1.2 WHEN `StrategyEngine` 评估包含 `ma_trend` 因子条件的策略 THEN 由于 `stock_data["ma_trend"]` 为 `None`，`FactorEvaluator.evaluate()` 始终返回 `passed=False`，所有股票的均线趋势因子均不通过

**技术指标模块（indicator_params）**

1.3 WHEN 用户启用 `indicator_params` 模块并执行选股 THEN `ScreenDataProvider._build_factor_dict()` 返回的因子字典中不包含 `macd`、`boll`、`rsi`、`dma` 键，`detect_macd_signal()`、`detect_boll_signal()`、`detect_rsi_signal()`、`calculate_dma()` 从未被调用

1.4 WHEN `StrategyEngine` 评估包含 MACD/BOLL/RSI/DMA 因子条件的策略 THEN 由于 `stock_data["macd"]`、`stock_data["boll"]`、`stock_data["rsi"]`、`stock_data["dma"]` 均为 `None`，所有技术指标因子均不通过

**形态突破模块（breakout）**

1.5 WHEN 用户启用 `breakout` 模块并执行选股 THEN `ScreenDataProvider._build_factor_dict()` 返回的因子字典中不包含 `breakout` 键，`detect_box_breakout()`、`detect_previous_high_breakout()`、`detect_descending_trendline_breakout()` 从未被调用

1.6 WHEN `StrategyEngine` 评估包含 `breakout` 因子条件的策略 THEN 由于 `stock_data["breakout"]` 为 `None`，所有股票的突破因子均不通过

**量价资金模块（volume_price）**

1.7 WHEN 用户启用 `volume_price` 模块并执行选股 THEN `ScreenDataProvider._build_factor_dict()` 返回的因子字典中不包含 `money_flow`、`large_order`、`volume_price`、`turnover` 键，`check_turnover_rate()`、`detect_volume_price_divergence()`、`check_money_flow_signal()`、`check_large_order_signal()` 从未被调用

1.8 WHEN `StrategyEngine` 评估包含资金面因子条件（`money_flow`、`large_order`、`volume_price`）的策略 THEN 由于对应因子值均为 `None`，所有量价资金因子均不通过

**多因子编辑器模块（factor_editor）**

1.9 WHEN 用户启用 `factor_editor` 模块并配置包含技术面/资金面因子的策略 THEN `StrategyEngine.screen_stocks()` 对每只股票调用 `FactorEvaluator.evaluate()`，但所有派生因子值（`ma_trend`、`macd`、`breakout`、`money_flow` 等）均为 `None`，导致 AND 逻辑下无股票通过筛选

**跨模块通用问题**

1.10 WHEN 用户仅启用非 `factor_editor` 模块（如仅启用 `breakout` 或 `ma_trend`）执行选股 THEN `ScreenExecutor._execute()` 跳过多因子筛选，所有股票初始通过，但 `eval_result.factor_results` 中无任何模块的信号数据，最终选股结果的 `signals` 列表为空

1.11 WHEN 存在符合各模块选股条件的股票（如多头排列、MACD 金叉、箱体突破、主力资金净流入）THEN 选股结果返回空列表或无信号的结果项，用户无法获得任何有效选股信息

### 期望行为（正确）

**均线趋势模块（ma_trend）**

2.1 WHEN 用户启用 `ma_trend` 模块并执行选股 THEN 选股流水线应调用 `score_ma_trend()` 对每只股票计算趋势打分（0-100），并将打分结果存入 `stock_data["ma_trend"]`；同时调用 `detect_ma_support()` 检测均线支撑信号

2.2 WHEN 均线趋势打分 >= 80（需求 3.4）THEN 该股票的 `ma_trend` 因子应标记为通过，信号类别为 `SignalCategory.MA_TREND`

**技术指标模块（indicator_params）**

2.3 WHEN 用户启用 `indicator_params` 模块并执行选股 THEN 选股流水线应调用 `detect_macd_signal()` 检测 MACD 多头信号、`detect_boll_signal()` 检测 BOLL 突破信号、`detect_rsi_signal()` 检测 RSI 强势信号、`calculate_dma()` 计算 DMA 指标，并将结果分别存入 `stock_data["macd"]`、`stock_data["boll"]`、`stock_data["rsi"]`、`stock_data["dma"]`

2.4 WHEN MACD 检测到金叉信号（DIF/DEA 零轴上方 + DIF 上穿 DEA + 红柱放大 + DEA 向上，需求 4.2）THEN `stock_data["macd"]` 应为 `True`，因子评估通过

2.5 WHEN BOLL 检测到突破信号（站稳中轨 + 触碰上轨 + 开口向上，需求 4.3）THEN `stock_data["boll"]` 应为 `True`，因子评估通过

2.6 WHEN RSI 检测到强势信号（RSI 在 [50, 80] 且无超买背离，需求 4.4）THEN `stock_data["rsi"]` 应为 `True`，因子评估通过

**形态突破模块（breakout）**

2.7 WHEN 用户启用 `breakout` 模块并执行选股 THEN 选股流水线应调用 `breakout.py` 中的突破检测函数（`detect_box_breakout`、`detect_previous_high_breakout`、`detect_descending_trendline_breakout`）对每只股票进行突破分析

2.8 WHEN 突破检测函数识别到有效突破信号（收盘价突破压力位 AND 成交量 ≥ 近 20 日均量 1.5 倍，需求 5.2）THEN 该突破信号应包含在选股结果的 `signals` 列表中，信号类别为 `SignalCategory.BREAKOUT`

2.9 WHEN 突破检测发现无量突破（成交量 < 近 20 日均量 1.5 倍）THEN 该突破不生成买入信号，符合 `validate_breakout` 逻辑（需求 5.4）

2.10 WHEN 突破检测完成后进行假突破检查 THEN 应按照 `check_false_breakout` 逻辑标记假突破，并在结果中设置 `is_fake_breakout=True`（需求 5.3）

**量价资金模块（volume_price）**

2.11 WHEN 用户启用 `volume_price` 模块并执行选股 THEN 选股流水线应调用 `check_turnover_rate()` 筛选换手率（3%-15%，需求 6.1）、`detect_volume_price_divergence()` 检测量价背离（需求 6.2）、`check_money_flow_signal()` 检测主力资金净流入信号（需求 6.3）、`check_large_order_signal()` 检测大单活跃信号（需求 6.4）

2.12 WHEN 主力资金单日净流入 ≥ 1000 万且连续 2 日（需求 6.3）THEN `stock_data["money_flow"]` 应为 `True`，因子评估通过，信号类别为 `SignalCategory.CAPITAL_INFLOW`

2.13 WHEN 大单成交占比 > 30%（需求 6.4）THEN `stock_data["large_order"]` 应为 `True`，因子评估通过，信号类别为 `SignalCategory.LARGE_ORDER`

**多因子编辑器模块（factor_editor）**

2.14 WHEN 用户启用 `factor_editor` 模块并配置多因子策略 THEN `StrategyEngine.screen_stocks()` 应能从 `stock_data` 中读取到所有已计算的派生因子值，按 AND/OR 逻辑正确评估每只股票

**跨模块通用**

2.15 WHEN 用户仅启用非 `factor_editor` 模块执行选股 THEN `ScreenExecutor` 应直接调用对应模块的检测逻辑对所有股票进行筛选，仅返回检测到有效信号的股票

### 不变行为（回归防护）

3.1 WHEN 用户启用 `factor_editor` 模块执行多因子选股（不涉及其他模块）且因子条件仅包含基本面因子（`pe`、`pb`、`roe`、`market_cap`）THEN 系统应继续按照现有 `StrategyEngine.screen_stocks()` 逻辑正常筛选，基本面因子数据（已由 `_build_factor_dict` 提供）不受影响

3.2 WHEN 用户同时启用 `factor_editor` 和其他模块执行选股 THEN 多因子筛选逻辑应继续正常工作，各模块信号作为额外信号附加到结果中

3.3 WHEN `enabled_modules` 为空集（非 `None`）THEN 系统应继续返回空结果（需求 27.8），不受本次修复影响

3.4 WHEN `enabled_modules` 为 `None`（向后兼容模式，全部模块启用）THEN 系统应继续按照现有逻辑执行全模块选股

3.5 WHEN 选股结果导出为 CSV THEN `export_screen_result_to_csv` 函数应继续正常工作，各模块信号应正确序列化到导出文件中

3.6 WHEN `ScreenDataProvider._build_factor_dict()` 提供的原始行情数据（`close`、`open`、`high`、`low`、`volume`、`amount`、`closes`、`highs`、`lows`、`volumes` 等序列）和基本面数据（`pe_ttm`、`pb`、`roe`、`market_cap`）THEN 这些已有字段的值和格式应保持不变

3.7 WHEN 某只股票的 K 线数据不足以计算某个指标（如数据少于 MA250 所需天数）THEN 该指标应返回安全默认值（如 `None` 或 `False`），不应导致异常或影响其他股票的选股流程
