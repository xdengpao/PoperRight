# 实现计划

- [x] 1. 编写 Bug Condition 探索性测试（修复前）
  - **Property 1: Bug Condition** - 非 factor_editor 路径下 trend_score 未使用 ma_trend 评分
  - **CRITICAL**: 此测试必须在未修复代码上失败 — 失败即确认缺陷存在
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: 此测试编码了期望行为 — 修复后通过即验证修复正确性
  - **GOAL**: 产生反例证明缺陷存在
  - **Scoped PBT Approach**: 针对确定性缺陷，将属性范围限定到 `enabled_modules=["ma_trend"]`、`factors=[]`、`stock_data["ma_trend"] > 0` 的场景
  - 测试文件：`tests/properties/test_trend_score_bug_condition.py`
  - 使用 Hypothesis 生成随机 `ma_trend` 评分（范围 1.0-100.0）和随机 `stock_data`（包含 `close`、`ma_trend` 等字段）
  - 构造 `StrategyConfig(factors=[])`，`enabled_modules=["ma_trend"]`
  - 调用 `ScreenExecutor(strategy_config, enabled_modules=["ma_trend"]).run_eod_screen(stocks_data)` 获取选股结果
  - 断言：对每个 `ScreenItem`，`item.trend_score` 应等于对应 `stock_data["ma_trend"]` 的值（而非 0.0）
  - 断言：`item.risk_level` 应等于 `_classify_risk(item.trend_score)` 的正确结果
  - 在未修复代码上运行测试
  - **EXPECTED OUTCOME**: 测试失败（这是正确的 — 证明缺陷存在）
  - 记录反例：`trend_score` 始终为 0.0，与 `stock_data["ma_trend"]` 的实际值无关；`risk_level` 始终为 HIGH
  - 任务完成条件：测试已编写、已运行、失败已记录
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

- [x] 2. 编写 Preservation 属性测试（修复前）
  - **Property 2: Preservation** - factor_editor 路径及 ma_trend 未启用路径行为不变
  - **IMPORTANT**: 遵循观察优先方法论
  - 测试文件：`tests/properties/test_trend_score_preservation.py`
  - 观察：在未修复代码上，对以下非 bug 条件场景记录行为：
    - `factor_editor` 启用且 `factors` 非空时，`trend_score` 等于 `eval_result.weighted_score`
    - `ma_trend` 模块未启用时（如 `enabled_modules=["indicator_params"]`），`trend_score` 等于 `eval_result.weighted_score`（即 0.0）
    - `enabled_modules` 为空集时，返回空 `ScreenResult`
  - 使用 Hypothesis 生成随机 `StrategyConfig`（含非空 `factors`）和随机 `stock_data`
  - 编写属性测试 1：`enabled_modules` 包含 `"factor_editor"` 且 `factors` 非空时，`trend_score` 等于 `StrategyEngine.evaluate()` 的 `weighted_score`（clamp 到 [0, 100]）
  - 编写属性测试 2：`ma_trend` 模块未启用时（`enabled_modules` 不含 `"ma_trend"`），`trend_score` 等于 `eval_result.weighted_score`
  - 编写属性测试 3：`enabled_modules=[]` 时，`ScreenResult.items` 为空列表
  - 编写属性测试 4：对任意 `score ∈ [0, 100]`，`_classify_risk(score)` 遵循 >=80→LOW、>=50→MEDIUM、<50→HIGH 规则
  - 在未修复代码上运行测试
  - **EXPECTED OUTCOME**: 测试通过（确认基线行为需要保持）
  - 任务完成条件：测试已编写、已运行、在未修复代码上通过
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. 修复 trend_score 取值逻辑

  - [x] 3.1 在 `_execute()` 中增加 ma_trend 评分回退逻辑
    - 文件：`app/services/screener/screen_executor.py`
    - 在 `_execute()` 方法的 `for symbol, eval_result in passed:` 循环内
    - 当前代码：`trend_score = eval_result.weighted_score`
    - 修改为：在 `trend_score = eval_result.weighted_score` 之后，增加判断：
      ```python
      if self._is_module_enabled("ma_trend"):
          ma_trend_score = float(stock_data.get("ma_trend", 0.0))
          trend_score = max(trend_score, ma_trend_score)
      ```
    - 当 `ma_trend` 模块启用时，从 `stock_data["ma_trend"]` 读取已计算的均线趋势评分，与 `weighted_score` 取较大值
    - 无需修改 `StrategyEngine.evaluate()`（`factors` 为空时返回 0.0 是正确行为）
    - 无需修改 `_classify_risk()`（风险等级分类逻辑本身正确）
    - 无需修改 `ScreenDataProvider._build_factor_dict()`（已正确计算 `ma_trend` 评分）
    - _Bug_Condition: isBugCondition(config, enabled_modules, stock_data) where factor_editor NOT IN enabled_modules AND len(config.factors) == 0 AND "ma_trend" IN enabled_modules AND stock_data["ma_trend"] > 0_
    - _Expected_Behavior: trend_score = max(eval_result.weighted_score, stock_data["ma_trend"])_
    - _Preservation: factor_editor 启用且 factors 非空时，weighted_score 仍参与 trend_score 计算；_classify_risk() 阈值不变_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

  - [x] 3.2 验证 Bug Condition 探索性测试现在通过
    - **Property 1: Expected Behavior** - trend_score 正确反映 ma_trend 评分
    - **IMPORTANT**: 重新运行任务 1 中的同一测试 — 不要编写新测试
    - 任务 1 中的测试编码了期望行为
    - 当此测试通过时，确认期望行为已满足
    - 运行 `pytest tests/properties/test_trend_score_bug_condition.py -v`
    - **EXPECTED OUTCOME**: 测试通过（确认缺陷已修复）
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 验证 Preservation 属性测试仍然通过
    - **Property 2: Preservation** - factor_editor 路径及 ma_trend 未启用路径行为不变
    - **IMPORTANT**: 重新运行任务 2 中的同一测试 — 不要编写新测试
    - 运行 `pytest tests/properties/test_trend_score_preservation.py -v`
    - **EXPECTED OUTCOME**: 测试通过（确认无回归）
    - 确认修复后所有保持性测试仍然通过（无回归）
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - 确保所有测试通过
  - 运行 `pytest tests/properties/test_trend_score_bug_condition.py tests/properties/test_trend_score_preservation.py -v`
  - 确保所有测试通过，如有问题请询问用户。
