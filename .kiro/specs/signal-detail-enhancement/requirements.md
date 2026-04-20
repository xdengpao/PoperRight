# Requirements Document

## Introduction

智能选股结果中展示的触发信号详情不够详细，用户无法分辨触发信号具体来源于哪个因子条件，也没有信号强度颜色编码的说明。本需求旨在增强信号详情的展示，使每条信号包含具体的因子条件描述和量化数值，并通过颜色编码直观表达信号强度等级，同时提供图例说明。

### 现状分析

- 后端 `SignalDetail` 已包含 `strength`（STRONG/MEDIUM/WEAK）和 `freshness`（NEW/CONTINUING）字段，但 API 响应未序列化这两个字段
- 前端信号标签仅显示分类名和原始因子名（如"均线趋势：ma_trend"），缺乏人类可读的因子条件描述
- 前端无信号强度颜色编码，也无图例说明

## Glossary

- **Signal_Detail_API**: 选股 API（`/api/v1/screen/run` 和 `/api/v1/screen/results`）中返回的信号详情 JSON 对象
- **Signal_Tag**: 前端选股结果展开详情面板中用于展示单条信号的标签组件
- **Signal_Strength_Indicator**: 前端用于以颜色编码表达信号强度等级（STRONG/MEDIUM/WEAK）的视觉元素
- **Signal_Strength_Legend**: 前端用于解释信号强度颜色含义的图例组件
- **Factor_Description**: 信号中包含的人类可读因子条件描述文本，说明具体触发条件和量化数值
- **Screen_Executor**: 后端选股执行器（`app/services/screener/screen_executor.py`），负责生成 `ScreenItem` 和 `SignalDetail`
- **ScreenerResultsView**: 前端选股结果页面（`frontend/src/views/ScreenerResultsView.vue`）
- **Signal_Dimension**: 信号维度分类，将 10 种 `SignalCategory` 归类为四个分析维度——技术面（Technical）、资金面（Capital Flow）、基本面（Fundamental）、板块面（Sector），用于在前端按维度分组展示触发信号

## Requirements

### Requirement 1: 信号详情 API 响应增强

**User Story:** As a 量化交易用户, I want 选股 API 返回完整的信号详情字段, so that 前端可以展示信号强度、新鲜度和因子描述信息。

#### Acceptance Criteria

1. WHEN 选股执行完成, THE Signal_Detail_API SHALL 在每条信号对象中包含 `strength` 字段，值为 `STRONG`、`MEDIUM` 或 `WEAK` 之一
2. WHEN 选股执行完成, THE Signal_Detail_API SHALL 在每条信号对象中包含 `freshness` 字段，值为 `NEW` 或 `CONTINUING` 之一
3. WHEN 选股执行完成, THE Signal_Detail_API SHALL 在每条信号对象中包含 `description` 字段，值为人类可读的因子条件描述文本
4. WHEN 选股结果从缓存中读取, THE Signal_Detail_API SHALL 保留完整的信号详情字段（包括 `strength`、`freshness`、`description`）

### Requirement 2: 因子条件描述文本生成

**User Story:** As a 量化交易用户, I want 每条信号包含具体的因子条件描述, so that 我能清楚知道触发信号来源于哪个因子条件及其量化数值。

#### Acceptance Criteria

1. WHEN 均线趋势信号（MA_TREND）触发, THE Screen_Executor SHALL 生成包含均线周期和趋势评分的描述文本（例如"5日/10日/20日均线多头排列, 趋势评分 85"）
2. WHEN MACD 信号触发, THE Screen_Executor SHALL 生成包含 MACD 指标状态的描述文本（例如"MACD 金叉, DIF 上穿 DEA"）
3. WHEN 布林带信号（BOLL）触发, THE Screen_Executor SHALL 生成包含布林带位置关系的描述文本（例如"价格突破布林带上轨"）
4. WHEN RSI 信号触发, THE Screen_Executor SHALL 生成包含 RSI 数值的描述文本（例如"RSI(14) = 65, 处于强势区间"）
5. WHEN DMA 信号触发, THE Screen_Executor SHALL 生成包含 DMA 与 AMA 关系的描述文本（例如"DMA 上穿 AMA, DMA=0.52"）
6. WHEN 形态突破信号（BREAKOUT）触发, THE Screen_Executor SHALL 生成包含突破类型和量比的描述文本（例如"箱体突破, 量比 2.3 倍"）
7. WHEN 资金流入信号（CAPITAL_INFLOW）触发, THE Screen_Executor SHALL 生成包含资金流向的描述文本（例如"主力资金净流入"）
8. WHEN 大单活跃信号（LARGE_ORDER）触发, THE Screen_Executor SHALL 生成包含大单状态的描述文本（例如"大单成交活跃"）
9. WHEN 均线支撑信号（MA_SUPPORT）触发, THE Screen_Executor SHALL 生成包含支撑均线的描述文本（例如"回调至 20 日均线获支撑"）
10. WHEN 板块强势信号（SECTOR_STRONG）触发, THE Screen_Executor SHALL 生成包含具体触发板块名称的描述文本（例如"所属板块【半导体】涨幅排名前列"），使用户能明确知道因哪个板块而被选中
11. THE Screen_Executor SHALL 将生成的描述文本存储在 SignalDetail 的 `description` 字段中

### Requirement 3: 前端信号标签增强展示

**User Story:** As a 量化交易用户, I want 选股结果中的信号标签展示具体的因子条件描述, so that 我能直观了解每条信号的触发原因。

#### Acceptance Criteria

1. WHEN 选股结果展开详情面板显示信号标签, THE Signal_Tag SHALL 展示信号的 `description` 文本替代原始的 `label` 字段
2. WHEN 信号包含 `description` 字段, THE Signal_Tag SHALL 以"分类名：描述文本"的格式展示（例如"均线趋势：5日/10日/20日均线多头排列, 趋势评分 85"）
3. IF 信号的 `description` 字段为空或缺失, THEN THE Signal_Tag SHALL 回退显示原始的 `label` 字段以保持向后兼容

### Requirement 4: 信号强度颜色编码

**User Story:** As a 量化交易用户, I want 信号标签通过颜色编码表达强度等级, so that 我能快速识别强信号和弱信号。

#### Acceptance Criteria

1. WHEN 信号强度为 STRONG, THE Signal_Strength_Indicator SHALL 在信号标签上显示醒目的强信号视觉样式（如红色/绿色高亮边框或背景色）
2. WHEN 信号强度为 MEDIUM, THE Signal_Strength_Indicator SHALL 在信号标签上显示中等强度的视觉样式（如橙色/黄色边框或背景色）
3. WHEN 信号强度为 WEAK, THE Signal_Strength_Indicator SHALL 在信号标签上显示低调的弱信号视觉样式（如灰色边框或背景色）
4. THE Signal_Strength_Indicator SHALL 在信号标签内以文字形式标注强度等级（如"强"、"中"、"弱"）
5. IF 信号的 `strength` 字段缺失, THEN THE Signal_Strength_Indicator SHALL 默认使用 MEDIUM 的视觉样式

### Requirement 5: 信号强度图例说明

**User Story:** As a 量化交易用户, I want 选股结果页面提供信号强度颜色的图例说明, so that 我能理解不同颜色代表的含义。

#### Acceptance Criteria

1. THE Signal_Strength_Legend SHALL 在选股结果页面的信号详情区域上方展示
2. THE Signal_Strength_Legend SHALL 包含三个强度等级（STRONG、MEDIUM、WEAK）对应的颜色样本和中文标签
3. THE Signal_Strength_Legend SHALL 对每个强度等级提供简短的含义说明（例如"强：多个因子共振确认"、"中：部分因子确认"、"弱：单一因子触发"）
4. WHEN 选股结果列表为空, THE Signal_Strength_Legend SHALL 不显示

### Requirement 6: 信号新鲜度标记展示

**User Story:** As a 量化交易用户, I want 信号标签展示新鲜度标记, so that 我能区分新出现的信号和持续存在的信号。

#### Acceptance Criteria

1. WHEN 信号新鲜度为 NEW, THE Signal_Tag SHALL 在标签上显示"新"标记徽章
2. WHEN 信号新鲜度为 CONTINUING, THE Signal_Tag SHALL 不显示额外的新鲜度标记
3. IF 信号的 `freshness` 字段缺失, THEN THE Signal_Tag SHALL 不显示新鲜度标记

### Requirement 7: 信号摘要增强

**User Story:** As a 量化交易用户, I want 选股结果主行的信号摘要包含强度信息, so that 我无需展开详情即可了解信号强度分布。

#### Acceptance Criteria

1. WHEN 选股结果主行显示信号摘要, THE ScreenerResultsView SHALL 在信号数量旁展示强信号的数量（例如"5 个信号（3 强）"）
2. IF 所有信号均非 STRONG, THEN THE ScreenerResultsView SHALL 仅显示信号总数（例如"5 个信号"）

### Requirement 8: SignalDetail 数据模型扩展

**User Story:** As a 开发者, I want SignalDetail 数据类包含 description 字段, so that 因子条件描述可以在系统各层之间传递。

#### Acceptance Criteria

1. THE SignalDetail SHALL 包含 `description` 字段，类型为 `str`，默认值为空字符串
2. THE SignalDetail SHALL 保持与现有字段（`category`、`label`、`is_fake_breakout`、`breakout_type`、`strength`、`freshness`）的向后兼容
3. FOR ALL valid SignalDetail objects, 序列化为 JSON 再反序列化 SHALL 产生等价的对象（round-trip property）

### Requirement 9: 选股结果板块分类展示

**User Story:** As a 量化交易员, I want 选股结果中展示每只股票在东方财富、同花顺、通达信三个数据源的所属板块, so that 我能快速了解股票的板块归属并进行跨数据源对比。

#### Acceptance Criteria

1. WHEN 选股执行完成, THE Signal_Detail_API SHALL 在每条选股结果中包含 `sector_classifications` 字段，值为包含三个数据源板块信息的对象
2. THE Signal_Detail_API SHALL 在 `sector_classifications` 对象中包含 `eastmoney` 字段（东方财富板块列表）、`tonghuashun` 字段（同花顺板块列表）和 `tongdaxin` 字段（通达信板块列表），每个字段值为该数据源下该股票所属板块名称的字符串数组
3. IF 某数据源下该股票无板块数据, THEN THE Signal_Detail_API SHALL 返回该数据源字段为空数组
4. WHEN 选股结果展开详情面板, THE ScreenerResultsView SHALL 在信号详情区域下方展示板块分类信息，以三列布局分别显示东方财富、同花顺、通达信的板块名称
5. THE ScreenerResultsView SHALL 为每列显示数据源中文标题（"东方财富"、"同花顺"、"通达信"）
6. IF 某数据源的板块列表为空, THEN THE ScreenerResultsView SHALL 在对应列中显示"暂无数据"占位文本
7. WHEN 选股结果从缓存中读取, THE Signal_Detail_API SHALL 保留完整的 `sector_classifications` 字段
8. THE ScreenerResultsView SHALL 将板块分类区域嵌套在信号详情区域（`detail-signals`）内部、信号标签列表下方，而非作为与信号详情和K线图表并列的独立 flex 子项，以避免挤占K线图表的水平空间导致图表无法正常显示


### Requirement 10: 信号维度分类展示

**User Story:** As a 量化交易员, I want 在触发信号详情中知道具体是技术面、资金面、基本面还是板块面中哪个因子触发了, so that 我能从多维度视角快速理解信号来源并做出更全面的交易决策。

#### Acceptance Criteria

1. THE Signal_Detail_API SHALL 定义一个从 `SignalCategory` 到 Signal_Dimension 的静态映射，其中：技术面包含 MA_TREND、MACD、BOLL、RSI、DMA、BREAKOUT、MA_SUPPORT；资金面包含 CAPITAL_INFLOW、LARGE_ORDER；基本面暂无对应分类（预留扩展）；板块面包含 SECTOR_STRONG
2. WHEN 选股执行完成, THE Signal_Detail_API SHALL 在每条信号对象中包含 `dimension` 字段，值为该信号所属维度的中文名称（"技术面"、"资金面"、"基本面"或"板块面"）
3. WHEN 选股结果展开详情面板, THE ScreenerResultsView SHALL 将信号标签按 Signal_Dimension 分组展示，每组以维度中文名称作为分组标题
4. THE ScreenerResultsView SHALL 按固定顺序展示维度分组：技术面 → 板块面 → 资金面 → 基本面，跳过无信号的维度分组
5. IF 信号的 `dimension` 字段缺失, THEN THE ScreenerResultsView SHALL 将该信号归入默认分组"其他"以保持向后兼容
6. WHEN 选股结果从缓存中读取, THE Signal_Detail_API SHALL 保留完整的 `dimension` 字段
7. WHEN 板块面维度的信号（SECTOR_STRONG）展示时, THE ScreenerResultsView SHALL 在信号描述中包含具体触发板块名称，使用户能明确知道该股票因属于哪个板块而被选中

### Requirement 11: 因子条件编辑器板块面信号生成修复

**User Story:** As a 量化交易员, I want 通过因子条件编辑器配置的板块面因子（板块涨幅排名、板块趋势）在选股执行后能正确生成 SECTOR_STRONG 信号, so that 选股结果中能展示板块面维度的触发信号而非仅有技术面信号。

#### Acceptance Criteria

1. WHEN 用户在因子条件编辑器中配置了板块面因子（`sector_rank` 或 `sector_trend`）且因子评估通过, THE Screen_Executor SHALL 生成对应的 `SECTOR_STRONG` 类别信号，不受 `volume_price` 模块启用状态的限制
2. THE Screen_Executor 的 `_FACTOR_MODULE` 映射 SHALL NOT 将 `sector_rank` 和 `sector_trend` 映射到 `"volume_price"` 模块，以避免因子条件编辑器路径中板块面因子被错误地按模块启用状态过滤
3. WHEN 因子条件编辑器路径中某因子不在 `_FACTOR_MODULE` 映射中, THE Screen_Executor SHALL 跳过模块启用检查，直接根据因子评估结果生成信号
4. THE Screen_Executor SHALL 保持非因子条件编辑器路径（独立模块路径）中板块面信号的生成逻辑不变
