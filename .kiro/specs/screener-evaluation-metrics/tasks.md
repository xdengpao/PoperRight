# 任务文档：智能选股功能评价指标与业务逻辑评估

## 阶段一：基础设施搭建

- [ ] 1.1 创建评估子模块目录结构 `app/services/screener/evaluation/__init__.py` 和 `reports/.gitkeep`
- [ ] 1.2 实现 `HistoricalDataPreparer` 类：`get_trading_dates()`、`load_daily_snapshot()`、`load_index_data()`、`load_stock_info()` 方法，复用 `ScreenDataProvider._build_factor_dict` 逻辑按指定日期加载因子快照
- [ ] 1.3 实现 `ForwardReturnCalculator` 类：`calculate()` 方法计算 T+1/3/5/10/20 持有期收益，`_check_can_buy()` 判断停牌/涨停，计算参考价偏离度和超额收益
- [ ] 1.4 实现 `ScreeningSimulator` 类：`simulate_single_day()` 调用 `ScreenExecutor` 纯函数方法模拟单日选股，`simulate_period()` 遍历评估期每个交易日

## 阶段二：指标计算器实现

- [ ] 2.1 实现 `ReturnMetricsCalculator`：按持有期计算命中率、平均/中位数/最大/最小收益率、超额收益、无法买入比例、参考价偏离度统计
- [ ] 2.2 实现 `SignalMetricsCalculator`：按 10 种信号类别计算命中率和平均收益，计算信号共振效果（双信号/三信号组合矩阵），按强度和新鲜度分组统计
- [ ] 2.3 实现 `FactorMetricsCalculator`：计算横截面 Spearman IC、IR、IC 正比例和因子换手率（factor_turnover），识别有效因子（|IC|>0.05）和无效因子（|IC|<0.02），计算因子间相关性矩阵和冗余因子对
- [ ] 2.4 实现 `ScoreMetricsCalculator`：按 5 档趋势评分计算收益和命中率，验证评分单调性，评估 4 条风控规则的有效性（被过滤 vs 保留股票的收益对比），计算各模块评分与收益的相关性和最优权重
- [ ] 2.5 实现 `StrategyMetricsCalculator`：对每个策略模板计算命中率/平均收益/夏普/最大回撤/换手率/综合得分，按市场环境（上涨/震荡/下跌）分组评估，生成策略排名和末位策略清单

## 阶段三：改进方案生成器实现

- [ ] 3.1 实现 `FactorWeightOptimizer`：基于 IC/IR 生成无效因子清单（降权/移除建议）、高效因子清单（提权建议）、冗余因子合并方案，输出优化后的 `DEFAULT_MODULE_WEIGHTS` 具体值和涉及的文件路径/代码位置
- [ ] 3.2 实现 `RiskRuleOptimizer`：对单日涨幅/累计涨幅/DANGER/CAUTION 四条规则，基于被过滤股票的实际收益给出阈值调整建议，附带放宽后的预期选股数量变化、命中率变化和最坏情况损失评估
- [ ] 3.3 实现 `SignalSystemOptimizer`：对有效信号给出权重提升建议，对低效信号给出参数收紧/降权/移除三选一建议（含具体参数值），输出 Top 5 双信号和 Top 3 三信号高效组合推荐
- [ ] 3.4 实现 `StrategyTemplateOptimizer`：生成末位策略淘汰建议、中间策略参数优化建议（含具体配置修改）、2-3 个新增高效策略的完整 StrategyConfig，按市场环境给出 Top 3 策略推荐
- [ ] 3.5 实现 `RefPriceOptimizer`：分析参考价偏离度分布，按市值/涨跌幅/信号强度分组分析，给出参考价计算逻辑的具体修改方案（含代码片段）
- [ ] 3.6 实现 `ImprovementPrioritizer`：汇总所有改进建议，按 `预期效果×0.6 + (1-难度)×0.4` 计算优先级得分，分为三个实施阶段（快速见效/核心优化/深度重构），计算各阶段完成后的预期整体效果

## 阶段四：报告生成与脚本集成

- [ ] 4.1 实现 `ReportGenerator`：`generate_json()` 输出结构化 JSON 报告（含 summary/return_metrics/signal_metrics/factor_metrics/score_metrics/strategy_metrics/improvements 章节），`generate_markdown()` 输出人类可读报告（含表格和关键指标），`generate_improvement_reports()` 输出 6 份独立改进方案 Markdown 文件
- [ ] 4.2 实现 `scripts/evaluate_screener.py` 入口脚本：解析命令行参数（--start-date/--end-date/--strategies/--output/--format），串联数据准备→选股模拟→收益计算→指标计算→改进方案→报告输出的完整流程，显示进度信息和最终摘要

## 阶段五：业务逻辑测试

- [ ] 5.1 编写 `test_evaluation_data_integrity.py`：验证 factor_dict 包含 52 个因子键、各因子覆盖率 >= 50%、百分位值在 [0,100]、行业相对值为正、数据时效性检查
- [ ] 5.2 编写 `test_evaluation_factor_correctness.py`：使用已知历史数据验证 MA/MACD/RSI/BOLL/KDJ 计算精度（偏差 < 0.01%），验证均线趋势评分边界条件（多头>=80/空头<=20），验证三种突破检测和假突破标记，验证信号强度排序一致性
- [ ] 5.3 编写 `test_evaluation_strategy_engine.py`：验证 AND/OR 逻辑正确性，验证加权评分公式和未启用模块排除，验证 6 种阈值类型判断逻辑，验证 StrategyConfig 序列化往返一致性
- [ ] 5.4 编写 `test_evaluation_risk_filters.py`：验证 NORMAL/CAUTION/DANGER 三级响应，验证单日涨幅 9% 和累计涨幅 20% 的边界值过滤，验证黑名单过滤和过滤顺序幂等性
- [ ] 5.5 编写 `test_evaluation_consistency.py`：验证相同输入产生相同输出（确定性），验证选股与回测的 MACD/RSI/BOLL/MA 信号一致性，验证 NEW/UPDATED/REMOVED 变化检测正确性，验证 Redis 缓存与数据库持久化结果一致

## 阶段六：集成验证

- [ ] 6.1 端到端运行评估脚本，使用真实数据库中最近 20 个交易日的数据验证完整流程，确认 JSON 和 Markdown 报告正确生成，6 份改进方案报告内容完整
- [ ] 6.2 审查改进方案的可执行性：验证每条建议引用的文件路径存在、代码位置准确、参数值合理，确认改进建议的优先级排序和阶段划分合理
