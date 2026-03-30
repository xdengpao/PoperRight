# Bugfix 需求文档

## 简介

选股结果中所有股票的趋势评分（trend_score）始终显示为 0，风险等级（risk_level）始终显示为 HIGH。根因是 `ScreenExecutor._execute()` 在非 `factor_editor` 路径下，使用 `StrategyEngine.evaluate()` 返回的 `weighted_score` 作为 `trend_score`，但当策略配置中 `factors` 为空时（如"均线趋势选股"等非因子编辑器策略），`weighted_score` 始终为 0.0。而 `_classify_risk(0)` 将 score < 50 分类为 HIGH，导致风险等级全部为高风险。

实际的趋势评分已由 `_build_factor_dict()` 正确计算并存储在 `stock_data["ma_trend"]` 中，但 `_execute()` 未使用该值。

## Bug 分析

### 当前行为（缺陷）

1.1 WHEN 选股策略未启用 `factor_editor` 模块且 `config.factors` 为空时，`ScreenExecutor._execute()` 调用 `StrategyEngine.evaluate()` 获取 `eval_result.weighted_score`，由于无因子可评估，`weighted_score` 始终为 0.0，THEN 系统将所有股票的 `trend_score` 设置为 0

1.2 WHEN `trend_score` 为 0 时，`_classify_risk(0)` 判定 0 < 50，THEN 系统将所有股票的 `risk_level` 设置为 HIGH

1.3 WHEN 选股策略仅启用 `ma_trend` 模块（如内置"均线趋势选股"策略）时，`stock_data["ma_trend"]` 中已有正确的趋势评分（0-100），但 `_execute()` 未读取该值，THEN 系统忽略了已计算的均线趋势评分

### 期望行为（正确）

2.1 WHEN 选股策略未启用 `factor_editor` 模块且 `config.factors` 为空，但 `ma_trend` 模块已启用时，THEN 系统 SHALL 使用 `stock_data["ma_trend"]` 中的均线趋势评分作为 `trend_score`

2.2 WHEN `trend_score` 基于正确的均线趋势评分计算时，THEN 系统 SHALL 根据实际评分正确分类风险等级：评分 >= 80 为 LOW，评分 >= 50 为 MEDIUM，评分 < 50 为 HIGH

2.3 WHEN 选股策略同时启用 `factor_editor` 和 `ma_trend` 模块，且 `config.factors` 非空时，THEN 系统 SHALL 综合考虑因子加权得分和均线趋势评分来确定 `trend_score`（取两者中的较大值或加权组合）

### 不变行为（回归防护）

3.1 WHEN 选股策略启用 `factor_editor` 模块且 `config.factors` 非空时，THEN 系统 SHALL CONTINUE TO 使用 `StrategyEngine.evaluate()` 的 `weighted_score` 参与 `trend_score` 计算

3.2 WHEN `trend_score` 为有效值（0-100 范围内）时，`_classify_risk()` THEN 系统 SHALL CONTINUE TO 按照 >= 80 → LOW、>= 50 → MEDIUM、< 50 → HIGH 的规则分类风险等级

3.3 WHEN `stock_data["ma_trend"]` 计算失败回退为 0.0 时，THEN 系统 SHALL CONTINUE TO 将该股票的趋势评分视为 0，风险等级为 HIGH

3.4 WHEN `enabled_modules` 为空集（非 None）时，THEN 系统 SHALL CONTINUE TO 返回空的选股结果

3.5 WHEN 前端接收到 API 返回的 `trend_score` 和 `risk_level` 时，THEN 系统 SHALL CONTINUE TO 正确渲染趋势评分进度条和风险等级徽章
