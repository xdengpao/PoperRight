# Requirements Document

## Introduction

本需求文档定义了智能选股管线（Screening Pipeline）的参数优化与新功能需求。基于对现有选股系统 10 个已识别问题的分析，对 MACD、BOLL、RSI、MA 趋势、模块评分、资金流、突破信号、市场风控、板块数据新鲜度、趋势评分阈值等核心模块进行参数与逻辑优化。同时新增因子指标使用说明展示功能，帮助量化交易员在配置因子条件时理解各指标的含义与推荐阈值。

## Glossary

- **Screening_Pipeline**: 智能选股管线，从数据加载到信号生成的完整选股流程
- **MACD_Detector**: MACD 多头信号检测器，位于 `app/services/screener/indicators.py` 中的 `detect_macd_signal` 函数
- **BOLL_Detector**: 布林带信号检测器，位于 `app/services/screener/indicators.py` 中的 `detect_boll_signal` 函数
- **RSI_Detector**: RSI 强势信号检测器，位于 `app/services/screener/indicators.py` 中的 `detect_rsi_signal` 函数
- **MA_Trend_Scorer**: 均线趋势打分器，位于 `app/services/screener/ma_trend.py` 中的 `score_ma_trend` 函数
- **Screen_Executor**: 选股执行器，位于 `app/services/screener/screen_executor.py` 中的 `ScreenExecutor` 类
- **Money_Flow_Checker**: 资金流信号检测器，位于 `app/services/screener/volume_price.py` 中的 `check_money_flow_signal` 函数
- **Breakout_Detector**: 形态突破检测器，位于 `app/services/screener/breakout.py` 中的突破检测函数集合
- **Market_Risk_Checker**: 大盘风控检测器，位于 `app/services/risk_controller.py` 中的 `MarketRiskChecker` 类
- **Sector_Strength_Filter**: 板块强势筛选器，位于 `app/services/screener/sector_strength.py` 中的 `SectorStrengthFilter` 类
- **Factor_Registry**: 因子元数据注册表，位于 `app/services/screener/factor_registry.py` 中的 `FACTOR_REGISTRY` 字典
- **Signal_Strength**: 信号强度等级枚举（STRONG / MEDIUM / WEAK），定义于 `app/core/schemas.py`
- **Golden_Cross**: MACD 金叉，DIF 线上穿 DEA 线的技术形态
- **Zero_Axis**: MACD 零轴，DIF 和 DEA 值为 0 的水平线
- **Bell_Curve_Score**: 钟形曲线评分函数，在最优区间给满分，偏离越远扣分越多
- **Resonance_Bonus**: 共振加分，多个技术指标同时触发时给予的额外评分奖励
- **Market_Breadth**: 市场广度指标，衡量上涨股票数与下跌股票数的比率
- **Factor_Usage_Panel**: 因子使用说明面板，在因子条件编辑器中展示因子描述、示例和推荐阈值的 UI 组件

## Requirements

### Requirement 1: MACD 信号条件放宽

**User Story:** As a 量化交易员, I want MACD 信号检测支持零轴下方二次金叉作为不同强度的信号，并移除 DEA 趋势向上的硬性要求, so that 系统不会遗漏零轴下方的有效金叉机会，提高信号捕获率。

#### Acceptance Criteria

1. WHEN DIF 上穿 DEA 且 DIF > 0 且 DEA > 0 且 MACD 红柱放大, THE MACD_Detector SHALL 生成 STRONG 强度的 MACD 信号（零轴上方金叉）
2. WHEN DIF 在零轴下方第二次上穿 DEA（前 60 个交易日内存在一次零轴下方金叉后死叉）, THE MACD_Detector SHALL 生成 WEAK 强度的 MACD 信号（零轴下方二次金叉）
3. WHEN DEA 趋势向上（当日 DEA > 前一日 DEA）, THE MACD_Detector SHALL 将信号强度提升一级（WEAK → MEDIUM, MEDIUM → STRONG），而非将其作为信号触发的必要条件
4. THE MACD_Detector SHALL 返回包含 signal（bool）、strength（SignalStrength）和 signal_type（str: "above_zero" | "below_zero_second"）的结构化结果
5. WHEN 仅发生零轴下方首次金叉（非二次金叉）, THE MACD_Detector SHALL 不生成信号（signal=False）

### Requirement 2: BOLL 信号逻辑修正

**User Story:** As a 量化交易员, I want 布林带信号以"突破中轨并站稳"为主信号，将"接近上轨"改为风险提示, so that 系统不再在接近上轨时发出追高买入信号，降低追高风险。

#### Acceptance Criteria

1. WHEN 当日收盘价突破布林带中轨且连续 2 个交易日收盘价均高于中轨, THE BOLL_Detector SHALL 生成 BOLL 突破信号（signal=True）
2. WHEN 当日收盘价 >= 上轨 × 0.98, THE BOLL_Detector SHALL 在信号结果中标记 near_upper_band=True 作为风险提示，而非将其作为买入信号条件
3. WHEN 收盘价突破中轨但未满足连续 2 日站稳条件, THE BOLL_Detector SHALL 不生成信号（signal=False）
4. THE BOLL_Detector SHALL 返回包含 signal（bool）、near_upper_band（bool）和 hold_days（int: 站稳天数）的结构化结果

### Requirement 3: RSI 区间收窄与趋势方向检查

**User Story:** As a 量化交易员, I want RSI 默认强势区间从 [50, 80] 收窄至 [55, 75]，并增加 RSI 连续上升趋势检查, so that RSI 信号过滤更精准，减少正常波动中的误触发。

#### Acceptance Criteria

1. THE RSI_Detector SHALL 使用 [55, 75] 作为默认强势区间（替代原 [50, 80]）
2. WHEN RSI 值处于强势区间内且 RSI 连续 3 个交易日上升（每日 RSI > 前一日 RSI）, THE RSI_Detector SHALL 生成 RSI 强势信号（signal=True）
3. WHEN RSI 值处于强势区间内但 RSI 未连续 3 个交易日上升, THE RSI_Detector SHALL 不生成信号（signal=False）
4. THE RSI_Detector SHALL 支持通过参数自定义连续上升天数（默认 3 天）和强势区间上下限
5. IF RSI 数据不足以判断连续上升趋势（可用交易日 < 连续上升天数 + RSI 周期）, THEN THE RSI_Detector SHALL 不生成信号并保持 signal=False

### Requirement 4: MA 趋势评分权重优化

**User Story:** As a 量化交易员, I want MA 趋势评分中距离分使用钟形曲线（0-3% 最优，>5% 开始扣分），并提高短期均线斜率权重, so that 评分不再对远离均线的追高股票给满分，同时更重视短期趋势变化。

#### Acceptance Criteria

1. THE MA_Trend_Scorer SHALL 使用钟形曲线计算距离分：价格在均线上方 0%-3% 时得满分（100 分），3%-5% 时线性递减，>5% 时从 100 分开始扣分（距离越远分数越低）
2. THE MA_Trend_Scorer SHALL 对短期均线（5 日、10 日）的斜率赋予更高权重：短期均线斜率权重为长期均线（60 日、120 日）斜率权重的 2 倍
3. THE MA_Trend_Scorer SHALL 保持总评分在 [0, 100] 闭区间内
4. WHEN 价格在均线上方超过 5%, THE MA_Trend_Scorer SHALL 使距离分低于价格在均线上方 3% 时的距离分
5. FOR ALL 有效收盘价序列, 解析后打分再解析 SHALL 产生等价的评分结果（幂等性：对同一输入多次调用 score_ma_trend 返回相同结果）

### Requirement 5: 模块评分权重差异化与共振加分

**User Story:** As a 量化交易员, I want 技术指标模块按可靠性差异化加权（MACD 35, RSI 25, BOLL 20, DMA 20），并在 2 个以上指标同时触发时给予共振加分, so that 评分更能反映各指标的实际可靠性，多指标共振时给出更强的信号。

#### Acceptance Criteria

1. THE Screen_Executor SHALL 使用差异化权重计算 indicator_params 模块评分：MACD 触发得 35 分, RSI 触发得 25 分, BOLL 触发得 20 分, DMA 触发得 20 分（满分 100 分）
2. WHEN 2 个技术指标同时触发, THE Screen_Executor SHALL 在 indicator_params 模块基础评分上额外加 10 分共振奖励
3. WHEN 3 个或以上技术指标同时触发, THE Screen_Executor SHALL 在 indicator_params 模块基础评分上额外加 20 分共振奖励
4. THE Screen_Executor SHALL 保证 indicator_params 模块评分不超过 100 分（含共振加分后取 min(score, 100)）
5. WHEN 仅 1 个技术指标触发, THE Screen_Executor SHALL 不给予共振加分

### Requirement 6: 资金流信号阈值相对化

**User Story:** As a 量化交易员, I want 资金流信号使用相对阈值（净流入 / 日均成交额 ≥ 5%）替代固定 1000 万元阈值, so that 信号对大盘股和小盘股同样有效，不因股票市值差异导致信号偏差。

#### Acceptance Criteria

1. THE Money_Flow_Checker SHALL 使用相对阈值判断资金流入信号：net_inflow / daily_avg_amount ≥ 5%（默认阈值）
2. WHEN 股票的日均成交额数据可用, THE Money_Flow_Checker SHALL 计算最近 20 个交易日的日均成交额作为基准
3. WHEN 相对净流入比例连续 2 个交易日 ≥ 阈值, THE Money_Flow_Checker SHALL 生成资金流入信号（signal=True）
4. THE Money_Flow_Checker SHALL 支持通过参数自定义相对阈值百分比（默认 5%）和连续天数（默认 2 天）
5. IF 日均成交额为 0 或数据不可用, THEN THE Money_Flow_Checker SHALL 回退到使用已有的 money_flow_pctl 百分位排名（≥ 80 百分位触发信号）
6. THE Money_Flow_Checker SHALL 保持向后兼容，支持通过配置参数选择绝对阈值模式或相对阈值模式

### Requirement 7: 突破信号成交量持续性验证

**User Story:** As a 量化交易员, I want 突破信号增加突破后 2-3 日的成交量持续性验证，并对突破前横盘整理时间较长的突破给予加分, so that 系统能过滤掉突破后立即缩量的假突破，并识别更可靠的长期整理后突破。

#### Acceptance Criteria

1. WHEN 突破信号触发后连续 2 个交易日成交量均 ≥ 突破日成交量的 70%, THE Breakout_Detector SHALL 标记该突破为 volume_sustained=True
2. WHEN 突破信号触发后任一交易日成交量 < 突破日成交量的 50%, THE Breakout_Detector SHALL 标记该突破为 volume_sustained=False
3. WHEN 箱体突破前的横盘整理期 ≥ 30 个交易日, THE Breakout_Detector SHALL 在突破信号中附加 consolidation_bonus=True 标记
4. THE Breakout_Detector SHALL 返回包含 volume_sustained（bool）和 consolidation_bonus（bool）字段的突破信号结构
5. WHILE 成交量持续性验证数据不足（突破后交易日不足 2 天）, THE Breakout_Detector SHALL 将 volume_sustained 设为 None（待确认状态）

### Requirement 8: 市场风控多维度增强

**User Story:** As a 量化交易员, I want 市场风控增加市场广度指标（涨跌比）和成交量变化率，并在 DANGER 模式下允许强势股通过而非完全暂停买入, so that 风控判断更全面，极端行情下不会错过真正的强势股机会。

#### Acceptance Criteria

1. THE Market_Risk_Checker SHALL 在判定大盘风险等级时综合考虑三个维度：指数均线位置（现有）、市场广度（涨跌比）、成交量变化率
2. WHEN 市场广度数据可用且上涨股票数 / 下跌股票数 < 0.5, THE Market_Risk_Checker SHALL 将风险等级提升一级（NORMAL → CAUTION 或 CAUTION → DANGER）
3. WHEN 大盘风险等级为 DANGER, THE Screen_Executor SHALL 仅允许趋势评分 ≥ 95 的强势股通过（替代原有的完全暂停买入逻辑）
4. THE Market_Risk_Checker SHALL 支持通过参数配置市场广度阈值（默认 0.5）和 DANGER 模式下的强势股趋势评分阈值（默认 95）
5. IF 市场广度数据不可用, THEN THE Market_Risk_Checker SHALL 仅使用指数均线位置判定风险等级（降级为现有逻辑）

### Requirement 9: 板块数据新鲜度检测

**User Story:** As a 量化交易员, I want 系统在板块数据超过 2 个交易日未更新时记录 WARNING 日志，超过 5 个交易日时自动降级为不使用板块因子, so that 系统不会静默使用过期的板块数据导致错误的选股结果。

#### Acceptance Criteria

1. WHEN 板块 K 线数据的最新交易日距当前日期超过 2 个交易日, THE Sector_Strength_Filter SHALL 记录 WARNING 级别日志，包含数据源名称和最新数据日期
2. WHEN 板块 K 线数据的最新交易日距当前日期超过 5 个交易日, THE Sector_Strength_Filter SHALL 返回空排名列表并记录 WARNING 日志，使板块因子降级为默认值（sector_rank=None, sector_trend=False）
3. THE Sector_Strength_Filter SHALL 在 compute_sector_ranks 方法中执行数据新鲜度检查，在查询到最新交易日后立即判断
4. THE Sector_Strength_Filter SHALL 支持通过参数配置 WARNING 阈值（默认 2 个交易日）和降级阈值（默认 5 个交易日）
5. WHILE 板块数据处于 WARNING 状态（2-5 个交易日未更新）, THE Sector_Strength_Filter SHALL 继续使用现有数据计算排名，但在日志中标注数据延迟天数

### Requirement 10: 趋势评分阈值降低与趋势加速信号

**User Story:** As a 量化交易员, I want MA_TREND 信号的默认趋势评分阈值从 80 降低至 65-70，并新增"趋势加速"信号（评分从 <60 快速上升至 >70）, so that 系统能在趋势早期阶段就捕获信号，不再因阈值过高而错过初始上涨。

#### Acceptance Criteria

1. THE Screen_Executor SHALL 使用 68 作为 MA_TREND 信号的默认趋势评分阈值（替代原 80）
2. WHEN 当前趋势评分 ≥ 70 且前一轮趋势评分 < 60（评分在短期内从低位快速上升）, THE Screen_Executor SHALL 生成"趋势加速"信号（SignalCategory.MA_TREND, label="ma_trend_acceleration"）
3. THE Screen_Executor SHALL 支持通过 MaTrendConfig.trend_score_threshold 参数自定义阈值（默认值更新为 68）
4. WHEN "趋势加速"信号触发, THE Screen_Executor SHALL 将该信号的强度设为 STRONG
5. IF 前一轮趋势评分数据不可用（首次选股或无历史数据）, THEN THE Screen_Executor SHALL 不生成"趋势加速"信号，仅使用常规阈值判断

### Requirement 11: 因子指标使用说明展示

**User Story:** As a 量化交易员, I want 在因子条件编辑器中选择或悬停某个因子时，看到该因子的使用说明（描述、示例、推荐阈值范围）, so that 我能快速理解每个因子的含义并设置合理的阈值，无需查阅外部文档。

#### Acceptance Criteria

1. THE Factor_Registry SHALL 为每个因子提供完整的元数据，包含 description（描述文本）、examples（配置示例列表）和 default_threshold 或 default_range（推荐阈值）
2. WHEN 用户在因子条件编辑器中选择一个因子, THE Factor_Usage_Panel SHALL 展示该因子的 description、examples 和推荐阈值范围
3. THE Factor_Usage_Panel SHALL 通过 API 端点 GET /api/v1/screen/factors/{factor_name}/usage 获取因子使用说明数据
4. THE Factor_Usage_Panel SHALL 通过 API 端点 GET /api/v1/screen/factors 获取所有因子的元数据列表（含 category 分组）
5. IF 请求的因子名称在 Factor_Registry 中不存在, THEN THE API SHALL 返回 HTTP 404 状态码和描述性错误信息
6. THE Factor_Registry SHALL 确保所有 19 个已注册因子均包含非空的 description 字段
