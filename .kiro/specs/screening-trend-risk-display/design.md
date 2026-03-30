# 选股趋势评分与风险等级显示修复 设计文档

## 概述

`ScreenExecutor._execute()` 在非 `factor_editor` 路径下，对每只股票调用 `StrategyEngine.evaluate(config, data)` 获取 `eval_result.weighted_score` 作为 `trend_score`。但当 `config.factors` 为空列表时（如内置"均线趋势选股"策略），`StrategyEngine.evaluate()` 直接返回 `weighted_score=0.0`，导致所有股票的趋势评分为 0、风险等级全部为 HIGH。

修复方案：在 `_execute()` 中，当 `ma_trend` 模块启用时，从 `stock_data["ma_trend"]` 读取已计算的均线趋势评分，与 `eval_result.weighted_score` 取较大值作为最终 `trend_score`。

## 术语表

- **Bug_Condition (C)**：触发 bug 的条件 — `factor_editor` 未启用且 `config.factors` 为空，同时 `ma_trend` 模块已启用
- **Property (P)**：期望行为 — `trend_score` 应反映 `stock_data["ma_trend"]` 中的实际均线趋势评分
- **Preservation**：不变行为 — `factor_editor` 启用且 `config.factors` 非空时，`weighted_score` 仍参与 `trend_score` 计算
- **`ScreenExecutor._execute()`**：`app/services/screener/screen_executor.py` 中的核心选股执行方法，遍历股票数据并构建 `ScreenItem` 列表
- **`StrategyEngine.evaluate()`**：`app/services/screener/strategy_engine.py` 中的多因子评估方法，当 `factors` 为空时返回 `weighted_score=0.0`
- **`_classify_risk()`**：根据 `trend_score` 划分风险等级的辅助函数（>=80→LOW, >=50→MEDIUM, <50→HIGH）
- **`stock_data["ma_trend"]`**：由 `ScreenDataProvider._build_factor_dict()` 调用 `score_ma_trend()` 计算的均线趋势评分（0-100）

## Bug 详情

### Bug 条件

当用户使用非 `factor_editor` 策略（如内置"均线趋势选股"）执行选股时，`_execute()` 对每只股票调用 `StrategyEngine.evaluate()`。由于 `config.factors` 为空列表，`evaluate()` 进入 `if not config.factors` 分支直接返回 `weighted_score=0.0`。随后 `_execute()` 将此 0.0 赋值给 `trend_score`，`_classify_risk(0.0)` 判定为 HIGH。

**形式化规约：**
```
FUNCTION isBugCondition(config, enabled_modules, stock_data)
  INPUT: config of type StrategyConfig,
         enabled_modules of type set[str] | None,
         stock_data of type dict[str, Any]
  OUTPUT: boolean

  factor_editor_disabled := enabled_modules IS NOT None
                            AND "factor_editor" NOT IN enabled_modules
  factors_empty := len(config.factors) == 0
  ma_trend_enabled := enabled_modules IS None
                      OR "ma_trend" IN enabled_modules
  has_valid_ma_trend := stock_data.get("ma_trend", 0) > 0

  RETURN factor_editor_disabled
         AND factors_empty
         AND ma_trend_enabled
         AND has_valid_ma_trend
END FUNCTION
```

### 示例

- 内置策略"均线趋势选股"（`enabled_modules=["ma_trend"]`, `factors=[]`），某股票 `stock_data["ma_trend"]=85.0`：期望 `trend_score=85.0`, `risk_level=LOW`；实际 `trend_score=0.0`, `risk_level=HIGH`
- 内置策略"MACD+RSI 技术信号"（`enabled_modules=["indicator_params"]`, `factors=[]`），某股票 `stock_data["ma_trend"]=72.0`：期望 `trend_score=0.0`（ma_trend 模块未启用）；实际 `trend_score=0.0` — 此场景不受 bug 影响
- 内置策略"多模块联合选股"（`enabled_modules=["ma_trend", "indicator_params", "breakout"]`, `factors=[]`），某股票 `stock_data["ma_trend"]=60.0`：期望 `trend_score=60.0`, `risk_level=MEDIUM`；实际 `trend_score=0.0`, `risk_level=HIGH`
- 内置策略"价值成长+趋势"（`enabled_modules=["factor_editor", "ma_trend"]`, `factors=[...]`），某股票 `weighted_score=45.0`, `stock_data["ma_trend"]=90.0`：期望 `trend_score=90.0`（取较大值）；实际 `trend_score=45.0`

## 期望行为

### 保持不变的行为

**不变行为：**
- 当 `factor_editor` 启用且 `config.factors` 非空时，`StrategyEngine.evaluate()` 的 `weighted_score` 仍参与 `trend_score` 计算
- `_classify_risk()` 的阈值逻辑不变：>=80→LOW, >=50→MEDIUM, <50→HIGH
- 当 `stock_data["ma_trend"]` 计算失败回退为 0.0 时，该股票趋势评分仍为 0，风险等级为 HIGH
- 当 `enabled_modules` 为空集时，仍返回空选股结果
- 前端渲染趋势评分进度条和风险等级徽章的逻辑不变
- 鼠标点击、排序、导出等前端交互不受影响

**范围：**
所有不满足 bug 条件的输入应完全不受此修复影响，包括：
- `factor_editor` 启用且 `factors` 非空的策略
- `ma_trend` 模块未启用的策略
- `enabled_modules` 为 None（全部启用）的临时策略

## 假设根因

基于代码分析，根因明确：

1. **`StrategyEngine.evaluate()` 在 `factors` 为空时返回 `weighted_score=0.0`**：这是设计正确的行为 — 无因子可评估时加权得分为 0。问题不在 `StrategyEngine`，而在调用方。

2. **`_execute()` 未区分 `weighted_score` 的来源**：在非 `factor_editor` 路径下，`_execute()` 仍然对每只股票调用 `StrategyEngine.evaluate()` 并使用其 `weighted_score`，但此时 `weighted_score` 无意义（因为 `factors` 为空）。

3. **`_execute()` 未利用已计算的 `stock_data["ma_trend"]`**：`ScreenDataProvider._build_factor_dict()` 已通过 `score_ma_trend()` 计算了均线趋势评分并存入 `stock_data["ma_trend"]`，但 `_execute()` 在构建 `ScreenItem` 时完全忽略了这个值。

根因总结：`_execute()` 中 `trend_score` 的取值逻辑缺少对 `ma_trend` 模块派生评分的回退机制。

## 正确性属性

Property 1: Bug Condition - 非 factor_editor 路径下 trend_score 应使用 ma_trend 评分

_For any_ 输入满足 bug 条件（`factor_editor` 未启用、`factors` 为空、`ma_trend` 模块已启用），修复后的 `_execute()` SHALL 使用 `stock_data["ma_trend"]` 的值作为 `trend_score`，且 `_classify_risk(trend_score)` 应返回与该评分对应的正确风险等级。

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - factor_editor 路径行为不变

_For any_ 输入不满足 bug 条件（`factor_editor` 已启用且 `factors` 非空，或 `ma_trend` 模块未启用），修复后的 `_execute()` SHALL 产生与修复前完全相同的 `trend_score` 和 `risk_level`，保持原有的因子加权评分逻辑不变。

**Validates: Requirements 3.1, 3.2, 3.3**

## 修复实现

### 需要的变更

假设根因分析正确：

**文件**：`app/services/screener/screen_executor.py`

**函数**：`_execute()`

**具体变更**：

1. **在 `trend_score` 赋值处增加 `ma_trend` 回退逻辑**：在 `for symbol, eval_result in passed:` 循环内，当 `ma_trend` 模块启用时，从 `stock_data` 读取 `ma_trend` 值，与 `eval_result.weighted_score` 取较大值作为 `trend_score`。

   当前代码（约第 130 行）：
   ```python
   trend_score = eval_result.weighted_score
   ```

   修改为：
   ```python
   trend_score = eval_result.weighted_score
   if self._is_module_enabled("ma_trend"):
       ma_trend_score = float(stock_data.get("ma_trend", 0.0))
       trend_score = max(trend_score, ma_trend_score)
   ```

2. **无需修改 `StrategyEngine`**：`evaluate()` 在 `factors` 为空时返回 `weighted_score=0.0` 是正确行为，不应改动。

3. **无需修改 `_classify_risk()`**：风险等级分类逻辑本身正确，问题仅在输入值。

4. **无需修改 `ScreenDataProvider`**：`_build_factor_dict()` 已正确计算 `ma_trend` 评分。

5. **无需修改前端**：前端已正确渲染 `trend_score` 和 `risk_level`，只是后端传入的值不正确。

## 测试策略

### 验证方法

测试策略分两阶段：先在未修复代码上复现 bug（探索性测试），再验证修复后的正确性和保持性。

### 探索性 Bug 条件检查

**目标**：在实施修复前，用反例证明 bug 存在，确认或否定根因分析。如果否定，需重新假设根因。

**测试计划**：构造 `enabled_modules=["ma_trend"]`、`factors=[]` 的策略配置，传入包含有效 `ma_trend` 评分的 `stock_data`，断言 `trend_score` 应大于 0。在未修复代码上运行，观察失败。

**测试用例**：
1. **均线趋势策略测试**：`enabled_modules=["ma_trend"]`, `factors=[]`, `stock_data["ma_trend"]=85.0` → 期望 `trend_score=85.0`（未修复代码将失败）
2. **多模块联合策略测试**：`enabled_modules=["ma_trend", "indicator_params"]`, `factors=[]`, `stock_data["ma_trend"]=60.0` → 期望 `trend_score=60.0`（未修复代码将失败）
3. **风险等级联动测试**：`trend_score=85.0` → 期望 `risk_level=LOW`（未修复代码将返回 HIGH）
4. **ma_trend 为 0 的边界测试**：`stock_data["ma_trend"]=0.0` → 期望 `trend_score=0.0`, `risk_level=HIGH`（未修复代码可能通过）

**预期反例**：
- `trend_score` 始终为 0.0，与 `stock_data["ma_trend"]` 的实际值无关
- 可能原因：`_execute()` 仅使用 `eval_result.weighted_score`，未读取 `stock_data["ma_trend"]`

### 修复检查

**目标**：验证对所有满足 bug 条件的输入，修复后的函数产生期望行为。

**伪代码：**
```
FOR ALL (config, enabled_modules, stock_data) WHERE isBugCondition(config, enabled_modules, stock_data) DO
  result := _execute_fixed(stocks_data, screen_type)
  FOR EACH item IN result.items DO
    ASSERT item.trend_score == stock_data[item.symbol]["ma_trend"]
    ASSERT item.risk_level == _classify_risk(item.trend_score)
  END FOR
END FOR
```

### 保持性检查

**目标**：验证对所有不满足 bug 条件的输入，修复后的函数与原函数产生相同结果。

**伪代码：**
```
FOR ALL (config, enabled_modules, stock_data) WHERE NOT isBugCondition(config, enabled_modules, stock_data) DO
  ASSERT _execute_original(stocks_data) == _execute_fixed(stocks_data)
END FOR
```

**测试方法**：推荐使用基于属性的测试（Property-Based Testing），因为：
- 自动生成大量测试用例覆盖输入域
- 捕获手动单元测试可能遗漏的边界情况
- 对非 bug 输入的行为不变性提供强保证

**测试计划**：先在未修复代码上观察 `factor_editor` 路径的行为，然后编写基于属性的测试捕获该行为。

**测试用例**：
1. **factor_editor 路径保持**：`enabled_modules=["factor_editor"]`, `factors=[...]` → 验证 `trend_score` 仍等于 `weighted_score`
2. **ma_trend 未启用保持**：`enabled_modules=["indicator_params"]`, `factors=[]` → 验证 `trend_score` 仍为 `weighted_score`（即 0.0）
3. **空模块集保持**：`enabled_modules=[]` → 验证返回空结果
4. **_classify_risk 保持**：对任意 score ∈ [0, 100]，验证风险等级分类规则不变

### 单元测试

- 测试 `_execute()` 在不同 `enabled_modules` 组合下的 `trend_score` 取值
- 测试 `_classify_risk()` 的边界值（0, 49.9, 50, 79.9, 80, 100）
- 测试 `stock_data["ma_trend"]` 缺失或为 0 时的回退行为

### 基于属性的测试

- 生成随机 `StrategyConfig`（`factors` 为空或非空）和随机 `enabled_modules` 组合，验证 `trend_score` 取值逻辑正确
- 生成随机 `stock_data`（`ma_trend` 在 0-100 范围内），验证 `risk_level` 与 `trend_score` 的对应关系
- 生成不满足 bug 条件的随机输入，验证修复前后行为一致

### 集成测试

- 端到端测试：使用内置"均线趋势选股"策略执行选股，验证返回结果中 `trend_score` 和 `risk_level` 正确
- 测试多模块联合策略（如"价值成长+趋势"）中 `trend_score` 取 `weighted_score` 和 `ma_trend` 的较大值
- 测试 API 响应中 `trend_score` 和 `risk_level` 字段值正确传递到前端
