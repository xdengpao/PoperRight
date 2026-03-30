# 选股模块孤立代码缺陷修复设计

## 概述

智能选股系统的五个选股模块（`ma_trend`、`indicator_params`、`breakout`、`volume_price`、`factor_editor`）的核心算法函数从未被选股流水线调用。`ScreenDataProvider._build_factor_dict()` 仅提供原始 K 线行情数据和基本面数据，但不调用任何模块的计算函数来生成派生因子值（如 `ma_trend`、`macd`、`breakout`、`money_flow` 等）。

修复策略：在 `ScreenDataProvider._build_factor_dict()` 中增加对各模块计算函数的调用，将派生因子值填充到 `stock_data` 字典中；同时修改 `ScreenExecutor._execute()` 使其在仅启用非 `factor_editor` 模块时，直接调用对应模块的检测逻辑进行筛选并生成信号。

## 术语表

- **Bug_Condition (C)**：选股流水线中 `_build_factor_dict()` 未调用模块计算函数，导致 `stock_data` 中派生因子键缺失（值为 `None`），`FactorEvaluator.evaluate()` 始终返回 `passed=False`
- **Property (P)**：修复后，`_build_factor_dict()` 应调用各模块计算函数，`stock_data` 中应包含所有已启用模块的派生因子值；`ScreenExecutor._execute()` 应能基于这些值正确生成选股信号
- **Preservation**：原始行情数据（`close`、`open`、`high`、`low`、`volume`、`closes`、`highs` 等）和基本面数据（`pe_ttm`、`pb`、`roe`、`market_cap`）的值和格式不变；`enabled_modules` 为空集时返回空结果的行为不变；CSV 导出功能不变
- **`_build_factor_dict()`**：`ScreenDataProvider` 中的静态方法，位于 `app/services/screener/screen_data_provider.py`，负责将 `StockInfo` + `KlineBar` 列表转换为因子字典
- **`_execute()`**：`ScreenExecutor` 中的核心方法，位于 `app/services/screener/screen_executor.py`，负责执行选股逻辑并生成 `ScreenResult`
- **`StrategyEngine`**：多因子策略引擎，位于 `app/services/screener/strategy_engine.py`，通过 `FactorEvaluator` 评估 `stock_data` 中的因子值
- **`enabled_modules`**：策略配置中的模块启用列表，`None` 表示全部启用（向后兼容），空集表示跳过所有筛选

## 缺陷详情

### Bug Condition

缺陷在以下条件下触发：用户启用任意选股模块（`ma_trend`、`indicator_params`、`breakout`、`volume_price`、`factor_editor`）并执行选股时，`_build_factor_dict()` 仅返回原始行情和基本面数据，不包含任何派生因子键。`StrategyEngine` / `FactorEvaluator` 从 `stock_data` 中读取因子值时得到 `None`，始终返回 `passed=False`。

**形式化规约：**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ScreenExecutionContext
    - input.enabled_modules: set[str] | None  # 启用的模块集合
    - input.stocks_data: dict[str, dict[str, Any]]  # 全市场股票因子数据
    - input.strategy_config: StrategyConfig  # 策略配置
  OUTPUT: boolean

  # 至少有一个非空的模块被启用
  LET active_modules = input.enabled_modules IF input.enabled_modules IS NOT None
                       ELSE {"ma_trend", "indicator_params", "breakout", "volume_price", "factor_editor"}

  # 存在至少一只股票有足够的 K 线数据
  LET has_valid_stock = EXISTS stock IN input.stocks_data.values()
    WHERE len(stock["closes"]) >= 26  # 至少满足 MACD slow period

  # 存在至少一个需要派生因子的模块被启用
  LET has_derived_module = active_modules INTERSECT {"ma_trend", "indicator_params", "breakout", "volume_price"} != EMPTY
    OR ("factor_editor" IN active_modules
        AND EXISTS factor IN input.strategy_config.factors
        WHERE factor.factor_name IN ["ma_trend", "macd", "boll", "rsi", "dma", "breakout", "money_flow", "large_order", "volume_price"])

  RETURN has_valid_stock AND has_derived_module
END FUNCTION
```

### 示例

- **示例 1（ma_trend）**：用户启用 `ma_trend` 模块，股票 600000 有 250 天 K 线数据且处于多头排列状态。期望 `stock_data["ma_trend"]` 为 85.0（趋势打分），实际为 `None`，因子评估不通过。
- **示例 2（indicator_params）**：用户启用 `indicator_params` 模块，股票 000001 的 MACD 出现金叉信号。期望 `stock_data["macd"]` 为 `True`，实际为 `None`，信号丢失。
- **示例 3（breakout）**：用户启用 `breakout` 模块，股票 002415 突破箱体上沿且放量 2 倍。期望 `stock_data["breakout"]` 包含 `BreakoutSignal` 信息，实际为 `None`，突破信号未被识别。
- **示例 4（volume_price）**：用户启用 `volume_price` 模块，股票 300750 主力资金连续 3 日净流入超 1000 万。期望 `stock_data["money_flow"]` 为 `True`，实际为 `None`。
- **示例 5（factor_editor + 派生因子）**：用户启用 `factor_editor` 并配置 `ma_trend >= 80 AND macd == True`。期望通过筛选的股票列表非空，实际所有股票因子值为 `None`，无股票通过。
- **边界情况**：股票仅有 10 天 K 线数据，不足以计算 MA20。期望 `stock_data["ma_trend"]` 为安全默认值（0.0 或 `None`），不应抛出异常。

## 期望行为

### Preservation Requirements

**不变行为：**
- 原始行情数据字段（`close`、`open`、`high`、`low`、`volume`、`amount`、`turnover`、`vol_ratio`、`closes`、`highs`、`lows`、`volumes`、`amounts`、`turnovers`）的值和类型不变
- 基本面因子字段（`pe_ttm`、`pb`、`roe`、`market_cap`）的值和类型不变
- `enabled_modules` 为空集（`set()`）时返回空 `ScreenResult`（需求 27.8）
- `enabled_modules` 为 `None` 时全部模块启用（向后兼容）
- `export_screen_result_to_csv()` 函数的输入输出格式不变
- 仅包含基本面因子（`pe`、`pb`、`roe`、`market_cap`）的 `factor_editor` 策略不受影响

**范围：**
所有不涉及派生因子计算的输入路径应完全不受本次修复影响，包括：
- 仅使用基本面因子的多因子策略
- `enabled_modules` 为空集的选股请求
- CSV 导出功能
- 原始行情数据的读取和序列化

## 假设根因分析

基于代码分析，最可能的根因如下：

1. **`_build_factor_dict()` 缺少模块计算调用**：该方法仅从 `KlineBar` 和 `StockInfo` 中提取原始数据字段，从未 import 或调用 `ma_trend.score_ma_trend()`、`indicators.detect_macd_signal()` 等函数。这是核心根因——数据提供层与算法层之间的"断路"。

2. **`ScreenExecutor._execute()` 信号构建逻辑不完整**：当仅启用非 `factor_editor` 模块时，`_execute()` 跳过 `StrategyEngine.screen_stocks()`，所有股票"初始通过"。但信号构建阶段仅从 `eval_result.factor_results` 中提取已通过的因子，由于 `stock_data` 中无派生因子值，`factor_results` 中所有因子均为 `passed=False`，信号列表为空。

3. **模块间缺少集成层**：五个选股模块（`ma_trend.py`、`indicators.py`、`breakout.py`、`volume_price.py`）各自实现了完整的算法逻辑，但缺少一个"编排层"将它们的计算结果汇总到 `stock_data` 字典中。

4. **`ScreenExecutor` 缺少模块级筛选逻辑**：当仅启用 `breakout` 或 `ma_trend` 等模块时，`_execute()` 应直接调用对应模块的检测函数对股票进行筛选，而非依赖 `FactorEvaluator` 从 `stock_data` 中读取预计算值。

## 正确性属性

Property 1: Bug Condition - 派生因子值正确计算并填充

_For any_ 包含足够 K 线数据的股票（`len(closes) >= 26`），修复后的 `_build_factor_dict()` 应调用各模块计算函数，`stock_data` 中应包含 `ma_trend`（float）、`macd`（bool）、`boll`（bool）、`rsi`（bool）、`dma`（dict）、`breakout`（dict|None）等派生因子键，且值类型正确、非全部为 `None`。

**Validates: Requirements 2.1, 2.3, 2.7, 2.11**

Property 2: Preservation - 原始行情与基本面数据不变

_For any_ 输入的 `StockInfo` + `KlineBar` 列表，修复后的 `_build_factor_dict()` 返回的因子字典中，原始行情字段（`close`、`open`、`high`、`low`、`volume`、`amount`、`turnover`、`vol_ratio`、`closes`、`highs`、`lows`、`volumes`、`amounts`、`turnovers`）和基本面字段（`pe_ttm`、`pb`、`roe`、`market_cap`）的值应与修复前的 `_build_factor_dict()` 返回值完全一致。

**Validates: Requirements 3.1, 3.6**

## 修复实现

### 所需变更

假设根因分析正确：

**文件**: `app/services/screener/screen_data_provider.py`

**方法**: `_build_factor_dict()`

**具体变更**:
1. **导入模块计算函数**：在文件顶部导入 `ma_trend.score_ma_trend`、`ma_trend.detect_ma_support`、`indicators.detect_macd_signal`、`indicators.detect_boll_signal`、`indicators.detect_rsi_signal`、`indicators.calculate_dma`、`breakout.detect_box_breakout`、`breakout.detect_previous_high_breakout`、`breakout.detect_descending_trendline_breakout`、`volume_price.check_turnover_rate`、`volume_price.check_money_flow_signal`、`volume_price.check_large_order_signal`

2. **在 `_build_factor_dict()` 中调用 ma_trend 模块**：
   - 将 `closes` 序列转为 `list[float]`，调用 `score_ma_trend(closes)` 获取趋势打分，存入 `stock_data["ma_trend"]`
   - 调用 `detect_ma_support(closes)` 获取均线支撑信号，存入 `stock_data["ma_support"]`

3. **在 `_build_factor_dict()` 中调用 indicator_params 模块**：
   - 调用 `detect_macd_signal(closes)` 获取 MACD 信号，存入 `stock_data["macd"]`（bool）
   - 调用 `detect_boll_signal(closes)` 获取 BOLL 信号，存入 `stock_data["boll"]`（bool）
   - 调用 `detect_rsi_signal(closes)` 获取 RSI 信号，存入 `stock_data["rsi"]`（bool）
   - 调用 `calculate_dma(closes)` 获取 DMA 结果，存入 `stock_data["dma"]`

4. **在 `_build_factor_dict()` 中调用 breakout 模块**：
   - 调用 `detect_box_breakout(closes, highs, lows, volumes)` 获取箱体突破信号
   - 调用 `detect_previous_high_breakout(closes, volumes)` 获取前高突破信号
   - 调用 `detect_descending_trendline_breakout(closes, highs, volumes)` 获取趋势线突破信号
   - 将检测到的突破信号汇总存入 `stock_data["breakout"]`

5. **在 `_build_factor_dict()` 中调用 volume_price 模块**：
   - 调用 `check_turnover_rate(turnover)` 存入 `stock_data["turnover_check"]`
   - 调用 `check_money_flow_signal(daily_inflows)` 存入 `stock_data["money_flow"]`（bool）
   - 调用 `check_large_order_signal(large_order_ratio)` 存入 `stock_data["large_order"]`（bool）
   - 注意：`money_flow` 和 `large_order` 数据可能需要从额外数据源获取（money_flow 表），当数据不可用时使用安全默认值 `False`

6. **异常处理**：每个模块的计算调用应包裹在 `try/except` 中，单个模块计算失败不影响其他模块，失败时使用安全默认值

**文件**: `app/services/screener/screen_executor.py`

**方法**: `_execute()`

**具体变更**:
1. **增强信号构建逻辑**：当仅启用非 `factor_editor` 模块时，`_execute()` 应从 `stock_data` 中读取各模块的派生因子值，直接构建 `SignalDetail` 列表，而非仅依赖 `eval_result.factor_results`
2. **模块级筛选**：对于 `ma_trend` 模块，检查 `stock_data["ma_trend"] >= 80`；对于 `breakout` 模块，检查 `stock_data["breakout"]` 是否包含有效突破信号；对于 `volume_price` 模块，检查 `stock_data["money_flow"]` 或 `stock_data["large_order"]` 是否为 `True`
3. **假突破标记**：从 `stock_data["breakout"]` 中读取 `is_fake_breakout` 标记，设置到 `SignalDetail` 和 `ScreenItem` 中

## 测试策略

### 验证方法

测试策略分两阶段：首先在未修复代码上运行探索性测试以确认缺陷存在并验证根因假设，然后在修复后验证正确性和行为保持。

### 探索性 Bug Condition 检查

**目标**：在实施修复前，通过测试确认缺陷存在，验证或推翻根因分析。如果推翻，需要重新假设根因。

**测试计划**：构造包含足够 K 线数据的 `StockInfo` + `KlineBar` 列表，调用 `_build_factor_dict()` 并检查返回的因子字典中是否缺少派生因子键。在未修复代码上运行这些测试应观察到失败。

**测试用例**:
1. **ma_trend 因子缺失测试**：构造 250 天 K 线数据，调用 `_build_factor_dict()`，断言 `stock_data["ma_trend"]` 存在且为数值（在未修复代码上将失败，因为该键不存在）
2. **MACD 因子缺失测试**：构造 60 天 K 线数据，调用 `_build_factor_dict()`，断言 `stock_data["macd"]` 存在（在未修复代码上将失败）
3. **breakout 因子缺失测试**：构造突破形态的 K 线数据，调用 `_build_factor_dict()`，断言 `stock_data["breakout"]` 存在（在未修复代码上将失败）
4. **ScreenExecutor 空信号测试**：构造启用 `breakout` 模块的 `ScreenExecutor`，传入包含突破形态的股票数据，断言结果中 `signals` 列表非空（在未修复代码上将失败）

**预期反例**:
- `_build_factor_dict()` 返回的字典中不包含 `ma_trend`、`macd`、`boll`、`rsi`、`breakout`、`money_flow` 等键
- 根因确认：`_build_factor_dict()` 方法体中无任何对 `ma_trend.py`、`indicators.py`、`breakout.py`、`volume_price.py` 的函数调用

### Fix Checking

**目标**：验证对于所有满足 bug condition 的输入，修复后的函数产生期望行为。

**伪代码：**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := _build_factor_dict_fixed(input.stock, input.bars)
  ASSERT result["ma_trend"] IS NOT None  # float 趋势打分
  ASSERT result["macd"] IS NOT None      # bool MACD 信号
  ASSERT result["boll"] IS NOT None      # bool BOLL 信号
  ASSERT result["rsi"] IS NOT None       # bool RSI 信号
  ASSERT result["breakout"] IS NOT None OR no_breakout_detected  # dict|None
  
  screen_result := ScreenExecutor_fixed.run_eod_screen(stocks_data)
  FOR item IN screen_result.items DO
    ASSERT len(item.signals) > 0 OR stock_has_no_signals
  END FOR
END FOR
```

### Preservation Checking

**目标**：验证对于所有不满足 bug condition 的输入，修复后的函数与原始函数产生相同结果。

**伪代码：**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT _build_factor_dict_original(input) == _build_factor_dict_fixed(input)
    ON KEYS ["close", "open", "high", "low", "volume", "amount", "turnover",
             "vol_ratio", "closes", "highs", "lows", "volumes", "amounts",
             "turnovers", "pe_ttm", "pb", "roe", "market_cap"]
END FOR
```

**测试方法**：推荐使用 property-based testing 进行 preservation checking，因为：
- 可以自动生成大量测试用例覆盖输入域
- 能捕获手动单元测试可能遗漏的边界情况
- 对"行为不变"提供强保证

**测试计划**：先在未修复代码上观察原始行情数据和基本面数据的行为，然后编写 property-based 测试验证修复后这些字段不变。

**测试用例**:
1. **原始行情数据保持测试**：生成随机 K 线数据，验证修复后 `_build_factor_dict()` 返回的 `close`、`closes`、`volumes` 等字段与修复前一致
2. **基本面数据保持测试**：生成随机 `StockInfo`，验证修复后 `pe_ttm`、`pb`、`roe`、`market_cap` 字段不变
3. **空模块集行为保持测试**：验证 `enabled_modules=set()` 时 `ScreenExecutor` 仍返回空结果
4. **仅基本面因子策略保持测试**：验证仅包含 `pe >= 0` 等基本面因子的策略在修复前后行为一致

### 单元测试

- 测试 `_build_factor_dict()` 对每个模块的计算调用和结果填充
- 测试数据不足时的安全默认值（如 K 线少于 26 天时 MACD 应为安全默认值）
- 测试单个模块计算异常时不影响其他模块
- 测试 `ScreenExecutor._execute()` 在各种 `enabled_modules` 组合下的信号构建

### Property-Based Tests

- 生成随机 K 线序列，验证 `_build_factor_dict()` 返回的派生因子键存在且类型正确
- 生成随机 K 线序列，验证修复后原始行情字段和基本面字段与修复前完全一致（preservation property）
- 生成随机 `enabled_modules` 组合和股票数据，验证 `ScreenExecutor` 的信号生成逻辑正确

### 集成测试

- 端到端测试：从 `ScreenDataProvider.load_screen_data()` 到 `ScreenExecutor.run_eod_screen()` 的完整流程
- 多模块组合测试：同时启用 `ma_trend` + `breakout` + `factor_editor`，验证各模块信号正确汇总
- CSV 导出测试：验证修复后的选股结果能正确导出为 CSV
