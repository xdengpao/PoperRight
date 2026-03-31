# 需求文档

## 简介

A股右侧股票交易量化选股系统，专为A股市场设计，聚焦趋势确立后的波段/短线交易机会。系统遵循右侧交易准则：大盘趋势向好→板块强势共振→个股趋势突破→量价资金配合→风控校验放行，实现数据自动化处理-多因子智能选股-全流程风险控制-策略回测优化-实盘交易执行-交易复盘迭代闭环。

## 术语表

- **System**：A股右侧量化选股系统整体
- **DataEngine**：数据接入与清洗引擎
- **StockScreener**：核心选股模块
- **RiskController**：风险控制模块
- **BacktestEngine**：策略回测与优化引擎
- **TradeExecutor**：交易执行与持仓管理模块
- **ReviewAnalyzer**：复盘分析模块
- **AdminModule**：系统管理模块
- **AlertService**：预警推送服务
- **MA**：移动平均线（Moving Average）
- **MACD**：指数平滑异同移动平均线
- **BOLL**：布林带指标
- **RSI**：相对强弱指数
- **DMA**：平行线差指标
- **WebUI**：系统前端Web交互界面，基于Vue 3构建的单页应用
- **右侧交易**：趋势确立后顺势入场，不抄底、不摸顶
- **多头排列**：短期均线在上、长期均线在下、均线向上发散的形态
- **量价配合**：成交量与价格走势相互印证的健康形态
- **初选池**：通过初步筛选条件的候选股票集合
- **黑名单**：手动屏蔽、永久剔除的股票列表
- **白名单**：手动指定、强制保留的股票列表
- **训练集**：用于策略参数优化的历史数据集（70%）
- **测试集**：用于验证策略样本外表现的历史数据集（30%）
- **Tushare**：第三方A股金融数据接口平台，提供K线行情、财务报表、资金流向等数据，通过HTTP API + Token认证方式访问
- **AkShare**：开源A股金融数据接口库，提供行情数据、板块数据、市场情绪等数据，通过Python SDK方式调用
- **DataSourceConfig**：数据源配置模块，管理Tushare和AkShare的API访问地址与认证凭证
- **StrategyModuleSelector**：策略模板模块选择器，用于新建策略模板时选择需要启用的可选配置模块

---

## 需求

### 需求 1：行情与基础数据接入

**用户故事：** 作为量化交易员，我希望系统能通过Tushare和AkShare两个第三方数据接口自动接入A股全市场实时与历史行情数据，以便选股计算和回测分析有准确的数据基础。

#### 验收标准

1. THE DataEngine SHALL 对接Tushare数据接口和AkShare数据接口，获取A股全市场（主板/创业板/科创板/北交所）1分钟、5分钟、15分钟、30分钟、60分钟、日、周、月K线数据，包含成交量、成交额、换手率、量比、涨跌停价。
2. WHEN 行情数据到达时，THE DataEngine SHALL 在500ms内完成数据接收与入库。
3. THE DataEngine SHALL 通过Tushare接口每日更新个股财务报表（季度/年度）、业绩预告、违规处罚、股东减持、质押率、市值、PE/PB/ROE估值数据。
4. THE DataEngine SHALL 通过Tushare接口和AkShare接口实时同步主力资金流向、北向资金、龙虎榜、大宗交易、盘口委比/内外盘数据。
5. THE DataEngine SHALL 通过AkShare接口实时同步大盘指数、行业/概念板块、涨跌家数、涨跌停数量、市场情绪指标数据。
6. THE DataEngine SHALL 采用时序数据库存储行情数据，历史数据保留不少于10年，支持按股票代码、时间范围快速查询。
7. THE DataEngine SHALL 从配置文件（pydantic-settings / .env）中读取Tushare API Token（`tushare_api_token`）和Tushare API地址（`tushare_api_url`），代码中不得硬编码任何API访问凭证或地址。
8. THE DataEngine SHALL 从配置文件（pydantic-settings / .env）中读取AkShare请求超时时间（`akshare_request_timeout`）等运行参数，代码中不得硬编码AkShare的运行配置参数。
9. WHEN Tushare接口调用失败或返回错误时，THE DataEngine SHALL 自动切换至AkShare接口获取同类数据，确保数据获取的连续性。
10. WHEN Tushare接口和AkShare接口均不可用时，THE DataEngine SHALL 记录错误日志并推送数据源异常告警通知，停止对应数据类型的同步任务直至数据源恢复。
11. THE DataEngine SHALL 对Tushare和AkShare返回的数据进行统一格式转换，将不同数据源的字段名称和数据类型映射为系统内部统一的KlineBar数据结构。

### 需求 2：数据清洗与预处理

**用户故事：** 作为量化交易员，我希望系统自动过滤不合规标的并处理数据质量问题，以便选股结果不受脏数据干扰。

#### 验收标准

1. THE DataEngine SHALL 自动从候选股票池中剔除ST股、*ST股、退市整理股、停牌股、上市未满20个交易日的次新股、质押率超过70%的个股、净利润同比亏损超过50%的个股。
2. THE DataEngine SHALL 对历史行情数据自动完成除权除息处理，支持前复权、后复权、不复权三种模式切换。
3. WHEN 行情数据存在缺失值时，THE DataEngine SHALL 采用线性插值方法补全缺失数据。
4. WHEN 行情数据存在异常极值时，THE DataEngine SHALL 自动识别并剔除该异常数据点。
5. THE DataEngine SHALL 对因子计算所需数据进行归一化处理，使各因子数值处于统一量纲范围内。
6. THE DataEngine SHALL 将新股、ST股、退市股永久纳入剔除名单，该名单不可通过用户操作解禁。

### 需求 3：均线趋势选股

**用户故事：** 作为量化交易员，我希望系统能自动识别多头排列形态并打分，以便快速筛选出处于上升趋势的个股。

#### 验收标准

1. THE StockScreener SHALL 支持用户自定义均线周期，默认计算5日、10日、20日、60日、120日移动平均线。
2. THE StockScreener SHALL 自动识别多头排列形态，判定条件为：短期均线数值大于长期均线数值，且各均线斜率均大于0。
3. THE StockScreener SHALL 对每只股票生成0到100分的趋势打分，打分基于均线排列程度、均线斜率、股价与均线距离综合计算。
4. WHEN 个股趋势打分大于等于80分时，THE StockScreener SHALL 将该个股纳入初选池。
5. THE StockScreener SHALL 识别股价回调至20日或60日均线后企稳反弹的形态，并将符合条件的个股标记为均线支撑信号。

### 需求 4：技术指标趋势选股

**用户故事：** 作为量化交易员，我希望系统集成主流技术指标并支持参数自定义，以便通过多指标共振提高选股精度。

#### 验收标准

1. THE StockScreener SHALL 集成MACD、BOLL、RSI、DMA四种技术指标，所有指标参数支持用户自定义配置。
2. WHEN MACD指标满足DIF与DEA均在零轴上方、DIF上穿DEA形成金叉、红柱持续放大、DEA向上运行时，THE StockScreener SHALL 生成MACD多头信号。
3. WHEN BOLL指标满足股价站稳中轨、向上触碰上轨、布林带开口向上时，THE StockScreener SHALL 生成BOLL突破信号。
4. WHEN RSI数值处于50到80区间且无超买背离时，THE StockScreener SHALL 生成RSI强势信号。
5. THE StockScreener SHALL 支持用户配置多指标组合条件，通过AND/OR逻辑运算生成综合技术信号。

### 需求 5：形态突破选股

**用户故事：** 作为量化交易员，我希望系统能自动识别有效突破形态并过滤假突破，以便捕捉真实的趋势启动信号。

#### 验收标准

1. THE StockScreener SHALL 自动识别箱体突破、前期高点突破、下降趋势线突破三种形态。
2. WHEN 个股收盘价突破压力位且当日成交量大于等于近20日均量的1.5倍时，THE StockScreener SHALL 判定为有效突破信号。
3. WHEN 个股突破后收盘价未能站稳突破位满1个交易日时，THE StockScreener SHALL 撤销该突破信号并标记为假突破。
4. THE StockScreener SHALL 过滤无量突破信号，即成交量低于近20日均量1.5倍的突破不生成买入信号。

### 需求 6：量价资金筛选

**用户故事：** 作为量化交易员，我希望系统通过量价关系和资金流向进行二次筛选，以便确保选出的个股有主力资金支撑。

#### 验收标准

1. THE StockScreener SHALL 筛选换手率处于3%到15%区间的个股，剔除换手率过低（流动性不足）或过高（异常炒作）的标的。
2. THE StockScreener SHALL 剔除量价背离（价涨量缩或价跌量增异常）和高位放量滞涨的个股。
3. WHEN 个股主力资金单日净流入大于等于1000万且连续2日净流入时，THE StockScreener SHALL 生成资金流入信号。
4. WHEN 个股大单成交占比大于30%时，THE StockScreener SHALL 标记为大单活跃信号。
5. THE StockScreener SHALL 优先选择所属行业或概念板块涨幅排名前30且处于多头趋势的个股，弱势板块个股直接剔除。
6. WHEN 个股近20日日均成交额低于5000万时，THE StockScreener SHALL 自动将该个股从选股池中剔除。

### 需求 7：多因子自定义选股策略

**用户故事：** 作为量化交易员，我希望能自由组合技术面、资金面、基本面、板块面因子并保存策略模板，以便灵活应对不同市场环境。

#### 验收标准

1. THE StockScreener SHALL 支持技术面、资金面、基本面、板块面四类因子的自由组合，支持AND/OR逻辑运算，支持因子权重自定义配置。
2. THE StockScreener SHALL 支持策略模板的保存、编辑、删除、导入、导出操作，单用户最多保存20套选股策略。
3. THE StockScreener SHALL 支持一键切换已保存的策略模板，切换后立即以新策略重新执行选股。
4. THE StockScreener SHALL 在每个交易日15:30自动执行盘后选股，生成当日选股结果。
5. WHILE 交易时段（9:30至15:00）内，THE StockScreener SHALL 每10秒刷新一次实时选股结果。
6. THE StockScreener SHALL 将选股结果自动生成标的池，每条结果标注买入参考价、趋势强度评分、风险等级，支持导出为Excel文件。

### 需求 8：选股预警推送

**用户故事：** 作为量化交易员，我希望盘中触发选股条件时能立即收到预警通知，以便及时把握交易机会。

#### 验收标准

1. WHEN 盘中个股触发用户配置的选股条件时，THE AlertService SHALL 实时推送弹窗预警和站内消息通知。
2. THE AlertService SHALL 支持用户自定义预警阈值，包括趋势打分阈值、资金流入金额阈值、突破幅度阈值。
3. WHILE 非交易时段（15:00至次日9:25），THE AlertService SHALL 停止实时选股预警推送，仅保留盘后选股结果通知。

### 需求 9：事前风险控制

**用户故事：** 作为量化交易员，我希望系统在大盘趋势恶化时自动收紧或暂停选股信号，以便避免在熊市中频繁买入亏损。

#### 验收标准

1. WHEN 上证指数或创业板指跌破20日均线时，THE RiskController SHALL 自动将趋势打分纳入初选池的阈值从80分提升至90分。
2. WHEN 上证指数或创业板指跌破60日均线时，THE RiskController SHALL 暂停所有买入选股信号的生成，直至指数重新站上60日均线。
3. WHEN 个股单日涨幅超过9%时，THE RiskController SHALL 将该个股从当日选股池中剔除。
4. WHEN 个股连续3个交易日累计涨幅超过20%时，THE RiskController SHALL 将该个股从选股池中剔除。
5. THE RiskController SHALL 支持用户手动维护个股黑名单和白名单，黑名单中的个股不出现在任何选股结果中。

### 需求 10：事中风险控制

**用户故事：** 作为量化交易员，我希望系统对持仓仓位进行实时监控并在破位时预警，以便控制单一标的和板块的集中风险。

#### 验收标准

1. THE RiskController SHALL 限制单只个股持仓仓位不超过总资产的15%，超出时拒绝新增买入委托并推送预警。
2. THE RiskController SHALL 限制单一板块持仓仓位不超过总资产的30%，超出时拒绝该板块新增买入委托并推送预警。
3. WHEN 持仓个股跌破20日均线且当日放量下跌超过5%时，THE RiskController SHALL 实时推送减仓或平仓预警通知。

### 需求 11：事后止损止盈控制

**用户故事：** 作为量化交易员，我希望系统支持多种止损止盈方式并自动监控触发条件，以便保护已有盈利并控制最大亏损。

#### 验收标准

1. THE RiskController SHALL 支持固定比例止损，可选5%、8%、10%三档，当持仓亏损达到设定比例时自动触发止损预警。
2. THE RiskController SHALL 支持移动止损，跟踪持仓期间最高价，当价格从最高价回撤3%或5%（用户可选）时触发止损预警。
3. THE RiskController SHALL 支持趋势止损，当持仓个股收盘价跌破用户指定的关键均线时触发止损预警。
4. WHEN 选股策略的实时胜率低于50%或最大回撤超过15%时，THE RiskController SHALL 自动推送策略风险预警通知。

### 需求 12：策略历史回测

**用户故事：** 作为量化交易员，我希望能对选股策略进行历史回测并获得完整的绩效指标，以便在实盘前验证策略有效性。

#### 验收标准

##### 基础参数与输出

1. THE BacktestEngine SHALL 支持用户自定义回测起止日期、初始资金金额、买入手续费率（默认0.03%）、卖出手续费率（默认0.13%加0.1%印花税）、滑点比例（默认0.1%）。
2. THE BacktestEngine SHALL 输出年化收益率、累计收益率、胜率、盈亏比、最大回撤、夏普比率、卡玛比率、总交易次数、平均持仓天数共9项绩效指标。
3. THE BacktestEngine SHALL 以图表形式展示收益曲线、最大回撤曲线、持仓明细列表、交易流水记录，并支持导出为数据文件。
4. THE BacktestEngine SHALL 支持按牛市、熊市、震荡市三种市场环境分段执行回测，分别输出各阶段绩效指标。

##### 信号生成规则

5. THE BacktestEngine SHALL 在回测区间内逐交易日执行策略驱动选股：每个交易日收盘后，使用当日及之前的历史K线数据调用 ScreenExecutor 按策略配置（StrategyConfig）执行选股，自动生成买入候选信号。
6. THE BacktestEngine SHALL 仅采用日频盘后选股模式生成信号，与需求7验收标准4的盘后选股逻辑一致，不模拟盘中实时选股。
7. THE BacktestEngine SHALL 在每个交易日收盘后同时检查已持仓标的是否触发卖出条件（止损、移动止盈、趋势破位、持仓超期），生成卖出信号。

##### 买入执行规则

8. WHEN 选股信号于交易日T收盘后生成时，THE BacktestEngine SHALL 在T+1日以开盘价执行买入委托。
9. WHEN T+1日该股开盘价等于涨停价时，THE BacktestEngine SHALL 视为无法买入，跳过该买入信号。
10. THE BacktestEngine SHALL 支持用户配置最大同时持仓数量（`max_holdings`，默认10只），WHEN 当前持仓数量已达上限时，不执行新的买入信号。
11. THE BacktestEngine SHALL 采用等权资金分配策略，单笔买入金额 = 当前可用资金 / （最大持仓数量 - 当前持仓数量），同时支持可选的评分加权分配模式（`allocation_mode`，取值 "equal" 或 "score_weighted"，默认 "equal"）。
12. WHEN 采用评分加权分配模式时，THE BacktestEngine SHALL 按各候选标的的趋势评分占比分配买入资金，评分高的标的获得更多资金。
13. THE BacktestEngine SHALL 限制单股买入后仓位不超过总资产的 `max_position_pct`（默认15%），WHEN 计算买入金额超过该上限时，缩减买入数量至仓位上限以内。
14. THE BacktestEngine SHALL 将买入数量向下取整为100股（1手）的整数倍，WHEN 取整后买入数量不足100股时，放弃该笔买入。
15. WHEN 选股结果中包含已持仓的标的时，THE BacktestEngine SHALL 跳过该标的，不重复买入。
16. WHEN 同一交易日的买入候选标的数量超过剩余持仓空位数时，THE BacktestEngine SHALL 按以下优先级排序后取前N只（N=剩余空位数）：趋势评分从高到低 → 风险等级从低到高（LOW > MEDIUM > HIGH）→ 触发信号数量从多到少 → 趋势强度从强到弱。

##### 卖出执行规则

17. THE BacktestEngine SHALL 支持以下四种卖出条件，按优先级从高到低依次为：固定止损、趋势破位、移动止盈、持仓超期。
18. WHEN 持仓个股收盘价相对买入成本价的亏损比例达到固定止损阈值（`stop_loss_pct`，默认8%，可配置）时，THE BacktestEngine SHALL 在T+1日以开盘价执行止损卖出。
19. WHEN 持仓个股收盘价跌破用户指定的关键均线（默认20日均线）时，THE BacktestEngine SHALL 在T+1日以开盘价执行趋势破位卖出，复用 RiskController 的趋势止损逻辑。
20. THE BacktestEngine SHALL 跟踪每只持仓个股持仓期间的最高收盘价，WHEN 收盘价从最高价回撤达到移动止盈阈值（`trailing_stop_pct`，默认5%，可配置）时，在T+1日以开盘价执行移动止盈卖出。
21. WHEN 持仓个股涨停时（收盘价等于涨停价），THE BacktestEngine SHALL 不将该日计入移动止盈的回撤判断。
22. WHEN 持仓天数超过最大持仓天数（`max_holding_days`，默认20个交易日，可配置）且未触发其他卖出条件时，THE BacktestEngine SHALL 在超期次日以开盘价执行强制卖出。
23. WHEN 卖出执行日该股开盘价等于跌停价时，THE BacktestEngine SHALL 视为无法卖出，延迟至下一个非跌停交易日以开盘价执行卖出。

##### 仓位管理规则

24. THE BacktestEngine SHALL 将卖出回收的资金标记为当日不可用，次日起方可用于新的买入委托，模拟A股资金T+1可用规则。
25. WHEN 某交易日无选股结果且无持仓时，THE BacktestEngine SHALL 保持资金闲置，不强制买入，空仓期间资金不计算额外收益。

##### 风控集成规则

26. THE BacktestEngine SHALL 默认启用大盘风控模拟（`enable_market_risk`，默认True，可配置关闭），回测期间同步计算上证指数和创业板指的均线状态：指数跌破20日均线时将趋势打分纳入初选池的阈值从80分提升至90分（需求9.1），指数跌破60日均线时暂停所有买入信号直至指数重新站上60日均线（需求9.2）。
27. THE BacktestEngine SHALL 在买入时检查板块仓位上限（`max_sector_pct`，默认30%），WHEN 买入后该板块总仓位超过总资产的30%时，跳过该标的。
28. THE BacktestEngine SHALL 在选股阶段过滤当日涨幅超过9%的个股（需求9.3）和连续3个交易日累计涨幅超过20%的个股（需求9.4），不生成买入信号。
29. THE BacktestEngine SHALL 在回测中不模拟黑白名单过滤，以确保回测结果反映策略本身的表现，不受人工干预影响。

##### A股特殊交易规则

30. FOR ALL 回测结果，THE BacktestEngine SHALL 严格按照A股T+1交易规则计算，不允许当日买入当日卖出同一标的。
31. THE BacktestEngine SHALL 使用前复权价格进行回测计算（与需求2验收标准2一致），确保历史价格可比。
32. WHEN 持仓标的停牌（无K线数据）时，THE BacktestEngine SHALL 暂停该标的的止损、止盈、趋势破位检测，复牌后继续检测，WHEN 复牌首日触发止损条件时在T+1日执行卖出。
33. THE BacktestEngine SHALL 使用前一交易日收盘价乘以（1±10%）计算涨跌停价格（主板与创业板统一按10%简化处理），用于判定涨停无法买入和跌停无法卖出。

### 需求 13：策略参数优化与过拟合检测

**用户故事：** 作为量化交易员，我希望系统能自动寻找最优参数组合并检测过拟合风险，以便提升策略的实盘适应性。

#### 验收标准

1. THE BacktestEngine SHALL 支持遍历算法对选股因子参数进行网格搜索，输出各参数组合对应的绩效指标排名。
2. THE BacktestEngine SHALL 支持遗传算法对选股因子参数进行智能优化，自动输出最优参数组合。
3. THE BacktestEngine SHALL 将历史数据按时间顺序划分为训练集（前70%）和测试集（后30%），分别在两个数据集上执行回测。
4. WHEN 策略在测试集上的收益率与训练集收益率偏差超过20%时，THE BacktestEngine SHALL 判定该策略存在过拟合风险并输出警告。

### 需求 14：交易执行

**用户故事：** 作为量化交易员，我希望能从选股池直接下单并支持条件单，以便快速执行交易决策。

#### 验收标准

1. THE TradeExecutor SHALL 支持对选股池中的标的一键发起限价委托或市价委托，下单界面自动带入系统计算的参考买入价、止损价、止盈价。
2. THE TradeExecutor SHALL 支持突破买入条件单、止损卖出条件单、止盈卖出条件单、移动止盈条件单四种条件单类型，条件触发后自动提交委托。
3. THE TradeExecutor SHALL 对接主流券商交易API，支持实盘模式与模拟盘模式切换，两种模式下交易流程完全一致。
4. THE TradeExecutor SHALL 对所有交易指令进行加密传输，通过券商合规接口提交委托。
5. IF 当前时间不在交易时段（9:25至15:00）内，THEN THE TradeExecutor SHALL 拒绝实时委托提交并提示用户当前为非交易时段。

### 需求 15：持仓管理

**用户故事：** 作为量化交易员，我希望实时查看持仓状态并监控趋势是否维持，以便及时做出调仓决策。

#### 验收标准

1. THE TradeExecutor SHALL 实时同步并展示每只持仓股票的持仓股数、成本价、当前市值、盈亏金额、盈亏比例、仓位占比。
2. WHEN 持仓个股不再满足右侧趋势判断条件时，THE TradeExecutor SHALL 实时推送持仓破位预警通知。
3. THE TradeExecutor SHALL 记录所有委托记录、成交记录、撤单记录，支持按时间范围查询和导出交易流水。

### 需求 16：复盘分析

**用户故事：** 作为量化交易员，我希望每日自动生成复盘报告并支持多策略对比，以便持续迭代优化交易策略。

#### 验收标准

1. THE ReviewAnalyzer SHALL 每个交易日收盘后自动生成当日复盘报告，包含选股胜率、盈亏统计、成功交易案例分析、失败交易案例分析。
2. THE ReviewAnalyzer SHALL 生成日度、周度、月度策略收益报表和风险指标报表，支持多套策略并排对比分析。
3. THE ReviewAnalyzer SHALL 生成板块轮动分析、趋势行情分布图、资金流向分析报告，辅助用户判断市场结构。
4. THE ReviewAnalyzer SHALL 以柱状图、折线图、饼图等多种图表形式展示复盘数据，所有报表支持导出功能。

### 需求 17：系统管理

**用户故事：** 作为系统管理员，我希望能管理用户权限、监控系统状态并维护日志，以便保障系统安全稳定运行。

#### 验收标准

1. THE AdminModule SHALL 支持用户账号的新增、删除、权限分配操作，支持量化交易员、系统管理员、只读观察员三种角色的权限自定义配置。
2. THE AdminModule SHALL 记录所有用户操作日志，日志内容包含操作人、操作时间、操作类型、操作对象，日志保留时间不少于1年。
3. THE AdminModule SHALL 实时监控数据接口连接状态和系统各模块运行状态，WHEN 任意接口或模块出现异常时，THE AdminModule SHALL 自动触发报警通知。
4. THE AdminModule SHALL 支持数据备份与恢复、策略模板统一管理、系统参数配置功能。
5. THE AdminModule SHALL 记录选股、交易、回测、用户操作全流程日志，日志保留时间不少于1年。

### 需求 18：性能与可用性

**用户故事：** 作为量化交易员，我希望系统在高并发场景下保持快速响应和稳定运行，以便在交易时段不错过任何信号。

#### 验收标准

1. THE System SHALL 在全市场盘后选股场景下，从触发执行到输出完整选股结果的耗时不超过3秒。
2. WHILE 盘中实时选股运行时，THE System SHALL 每次刷新选股结果的耗时不超过1秒。
3. THE System SHALL 在不少于50个用户同时在线操作时，页面操作响应时间不超过500ms，无卡顿或宕机。
4. THE System SHALL 实现7×24小时不间断运行，系统可用性不低于99.9%。
5. THE System SHALL 保证数据计算误差不超过0.01%，选股信号无漏报、误报。

### 需求 19：安全性

**用户故事：** 作为系统管理员，我希望系统对数据传输、权限访问、交易指令进行全面安全防护，以便保障用户资产和数据安全。

#### 验收标准

1. THE System SHALL 对所有前后端数据传输采用SSL加密，防止数据在传输过程中被截获或篡改。
2. THE System SHALL 对用户策略数据和交易数据进行加密存储，防止数据库泄露导致敏感信息暴露。
3. THE System SHALL 对核心交易操作（下单、撤单、策略删除）执行二次身份验证，防止越权操作。
4. THE System SHALL 按角色实施分级权限管控，只读观察员不可访问交易功能，量化交易员不可访问系统管理功能。

### 需求 20：兼容性

**用户故事：** 作为量化交易员，我希望系统能在主流浏览器和操作系统上正常运行，以便在不同工作环境中使用。

#### 验收标准

1. THE System SHALL 支持在Chrome、Firefox、Edge三种主流浏览器上完整运行所有功能，无功能缺失或显示异常。
2. THE System SHALL 支持在Windows和Linux操作系统上完成服务端部署，兼容主流券商交易接口和第三方行情数据接口。

### 需求 21：登录与交互界面

**用户故事：** 作为量化交易员，我希望系统提供完整的登录认证界面和覆盖所有服务端功能的交互界面，以便通过浏览器高效操作系统的全部功能模块。

#### 验收标准

1. THE WebUI SHALL 提供用户登录页面，支持用户名密码登录，登录成功后跳转至系统主页面，登录失败时显示明确的错误提示信息。
2. THE WebUI SHALL 提供用户注册页面，支持新用户填写用户名和密码完成注册，注册时对用户名唯一性和密码强度进行校验并实时反馈校验结果。
3. WHEN 用户登录凭证过期或未登录时，THE WebUI SHALL 自动跳转至登录页面，阻止未认证用户访问系统功能页面。
4. THE WebUI SHALL 提供统一的主布局框架，包含顶部导航栏、侧边菜单栏和主内容区域，侧边菜单栏按功能模块分组展示所有可用页面入口。
5. THE WebUI SHALL 提供数据管理页面，支持查看行情数据同步状态、手动触发数据同步、查看数据清洗结果和剔除名单，对应DataEngine的全部服务端功能。
6. THE WebUI SHALL 提供选股策略页面，支持策略模板的创建、编辑、删除、导入、导出操作，支持因子条件组合配置、权重调整、逻辑运算符选择，支持一键执行选股并展示选股结果列表，对应StockScreener的全部服务端功能。
7. THE WebUI SHALL 提供选股结果页面，以表格形式展示选股结果，每条结果显示股票代码、名称、买入参考价、趋势强度评分、风险等级、触发信号，支持结果导出为Excel文件。
8. THE WebUI 选股策略页面 SHALL 提供均线趋势参数配置面板，支持用户自定义均线周期组合（默认5/10/20/60/120日），支持配置多头排列判定的斜率阈值，支持配置趋势打分纳入初选池的分数阈值（默认80分），支持配置均线支撑信号的回调均线选择（20日/60日），对应需求3均线趋势选股的全部参数配置需求。
9. THE WebUI 选股策略页面 SHALL 提供技术指标参数配置面板，针对MACD指标支持配置快线周期、慢线周期、信号线周期参数，针对BOLL指标支持配置周期和标准差倍数参数，针对RSI指标支持配置周期和强势区间上下限参数，针对DMA指标支持配置短期和长期周期参数，所有指标参数均提供默认值且支持用户自定义修改，对应需求4技术指标趋势选股的全部参数配置需求。
10. THE WebUI 选股策略页面 SHALL 提供形态突破配置面板，支持用户勾选启用箱体突破、前期高点突破、下降趋势线突破三种形态识别，支持配置有效突破的量比倍数阈值（默认1.5倍近20日均量），支持配置突破站稳确认天数（默认1个交易日），对应需求5形态突破选股的全部参数配置需求。
11. THE WebUI 选股策略页面 SHALL 提供量价资金筛选配置面板，支持配置换手率区间上下限（默认3%至15%），支持配置主力资金净流入金额阈值（默认1000万）和连续净流入天数（默认2日），支持配置大单成交占比阈值（默认30%），支持配置日均成交额下限（默认5000万），支持配置板块涨幅排名筛选范围（默认前30），对应需求6量价资金筛选的全部参数配置需求。
12. THE WebUI 选股策略页面 SHALL 在用户已保存策略数量达到20套上限时，禁用新建策略按钮并显示"已达策略上限（20套）"提示信息，对应需求7验收标准2的策略数量限制。
13. THE WebUI 选股策略页面 SHALL 提供实时选股开关控件，开启后在交易时段（9:30至15:00）内每10秒自动刷新选股结果并在页面展示倒计时和最近刷新时间，非交易时段自动禁用实时选股并显示"非交易时段"状态提示，对应需求7验收标准5的盘中实时选股需求。
14. THE WebUI 选股策略页面 SHALL 展示盘后自动选股调度状态，显示下一次盘后选股的预计执行时间（每个交易日15:30），支持查看最近一次盘后选股的执行结果和耗时，对应需求7验收标准4的盘后自动选股需求。
15. THE WebUI 选股结果页面 SHALL 对每条选股结果的触发信号按信号类型分类展示，区分均线趋势信号、技术指标信号（MACD/BOLL/RSI/DMA）、形态突破信号、资金流入信号、大单活跃信号、均线支撑信号、板块强势信号，WHEN 个股存在假突破标记时以醒目样式标注"假突破"警告标签，对应需求3至需求6产生的各类选股信号的完整展示需求。
16. THE WebUI SHALL 提供风险控制页面，支持查看当前大盘风控状态、配置止损止盈参数、管理个股黑名单和白名单、查看仓位风控预警信息，对应RiskController的全部服务端功能。
17. THE WebUI SHALL 提供回测分析页面，支持配置回测参数（起止日期、初始资金、手续费率、滑点）、执行回测任务、以图表形式展示收益曲线和最大回撤曲线、展示9项绩效指标、查看交易流水明细，对应BacktestEngine的全部服务端功能。
18. THE WebUI SHALL 提供交易执行页面，支持对选股池标的发起限价委托和市价委托、配置条件单、切换实盘与模拟盘模式、查看委托记录和成交记录，对应TradeExecutor的全部服务端功能。
19. THE WebUI SHALL 提供持仓管理页面，实时展示每只持仓股票的持仓股数、成本价、当前市值、盈亏金额、盈亏比例、仓位占比，支持查看持仓破位预警信息。
20. THE WebUI SHALL 提供复盘分析页面，支持查看日度、周度、月度复盘报告，以柱状图、折线图、饼图展示策略收益和风险指标，支持多策略对比分析和报表导出，对应ReviewAnalyzer的全部服务端功能。
21. THE WebUI SHALL 提供系统管理页面，支持用户账号管理（新增、删除、角色分配）、操作日志查询、系统运行状态监控、数据备份与恢复操作，对应AdminModule的全部服务端功能。
22. THE WebUI SHALL 根据当前登录用户的角色动态渲染菜单和页面内容，只读观察员不显示交易相关操作按钮，量化交易员不显示系统管理菜单入口。
23. THE WebUI SHALL 采用响应式布局，在1280px及以上分辨率的桌面浏览器中正常显示所有功能，无内容截断或布局错乱。
24. WHEN 服务端通过WebSocket推送预警消息时，THE WebUI SHALL 在页面右上角实时弹出预警通知卡片，显示预警类型、股票代码和触发原因，支持点击跳转至对应详情页面。
25. THE WebUI SHALL 在所有数据加载过程中显示加载状态指示器，WHEN 接口请求失败时显示明确的错误提示信息并提供重试操作入口。

### 需求 22：选股策略模板编辑与激活交互完善

**用户故事：** 作为量化交易员，我希望在选股策略页面选中已有策略后能查看和修改其配置参数，并通过一键切换将策略设为服务端活跃策略，以便持续优化策略参数并确保盘后自动选股使用正确的策略。

#### 验收标准

1. WHEN 用户在选股策略页面点击选中一个已保存的策略模板时，THE WebUI SHALL 调用 `GET /api/v1/strategies/{id}` 获取该策略的完整配置，并将配置参数回填至因子条件编辑器、均线趋势配置面板、技术指标配置面板、形态突破配置面板、量价资金筛选配置面板，使用户能直观查看当前策略的全部参数设置。
2. THE WebUI 选股策略页面 SHALL 在策略模板列表区域或因子编辑器区域提供"保存修改"按钮，WHEN 用户修改了已选中策略的配置参数并点击"保存修改"时，THE WebUI SHALL 调用 `PUT /api/v1/strategies/{id}` 将当前编辑面板中的全部配置参数（因子条件、均线趋势、技术指标、形态突破、量价资金）提交至后端更新该策略模板，更新成功后刷新策略列表并显示成功提示。
3. WHEN 用户在选股策略页面点击选中一个策略模板时，THE WebUI SHALL 调用 `POST /api/v1/strategies/{id}/activate` 将该策略设为服务端活跃策略（其余策略自动取消激活），确保盘后自动选股任务和盘中实时选股使用该活跃策略执行，对应需求7验收标准3的一键切换功能。
4. WHEN 用户在选股策略页面通过导入功能上传策略JSON文件时，THE WebUI SHALL 在调用创建接口前检查当前策略数量是否已达20套上限，达到上限时拒绝导入并显示"已达策略上限（20套），请删除旧策略后再导入"提示信息，对应需求7验收标准2和需求21验收标准12的策略数量限制。
5. THE WebUI 选股策略页面 SHALL 支持对已保存策略模板的名称进行修改，修改后调用 `PUT /api/v1/strategies/{id}` 更新策略名称。

### 需求 23：因子条件编辑器交互优化与配置数据源统一

**用户故事：** 作为量化交易员，我希望因子条件编辑器中的因子名称以预定义枚举下拉选择的方式呈现（而非自由文本输入），并且各配置面板的参数保持单一数据源，以便减少输入错误、消除参数回显不一致问题、提升策略配置效率。

#### 验收标准

1. THE WebUI 因子条件编辑器 SHALL 为每个因子类型（技术面、资金面、基本面、板块面）预定义因子名称枚举列表，因子名称输入控件从自由文本输入框改为下拉选择框（`<select>`），用户只能从预定义列表中选择因子名称。
2. THE WebUI 因子条件编辑器 SHALL 预定义以下因子名称枚举：
   - 技术面：均线趋势评分（ma_trend）、MACD 多头信号（macd_signal）、BOLL 突破信号（boll_breakout）、RSI 强势信号（rsi_strength）、DMA 信号（dma_signal）、均线支撑信号（ma_support）、箱体突破（box_breakout）、前高突破（high_breakout）、趋势线突破（trendline_breakout）、突破综合评分（breakout_score）
   - 资金面：主力资金净流入（capital_inflow）、大单成交占比（large_order_ratio）、北向资金流入（north_inflow）、成交量放大倍数（volume_surge）、换手率（turnover_rate）
   - 基本面：PE TTM（pe_ttm）、PB（pb）、ROE（roe）、净利润同比增长率（net_profit_growth）、营收同比增长率（revenue_growth）、总市值（market_cap）
   - 板块面：板块涨幅排名（sector_rank）、板块趋势强度（sector_trend）、板块资金流入（sector_inflow）、板块涨停家数（sector_count）
3. WHEN 用户切换因子类型时，THE WebUI SHALL 自动将因子名称重置为该类型下的第一个枚举选项。
4. WHEN 用户点击"添加因子"按钮时，THE WebUI SHALL 自动为新增因子选中对应类型的第一个枚举因子名称。
5. THE WebUI SHALL 在保存策略配置时将因子的 `type` 字段一并持久化至服务端，加载策略时优先使用存储的 `type` 字段，缺失时根据因子名称自动推断所属类型（向后兼容旧数据）。
6. THE WebUI 选股策略页面 SHALL 消除配置参数的双数据源问题：策略顶层的 `ma_periods` 字段统一从均线趋势配置面板的 `maTrend.ma_periods` 读取（移除因子编辑器区块中独立的均线周期文本输入框），趋势打分阈值统一从均线趋势配置面板的 `maTrend.trend_score_threshold` 读取（移除因子编辑器区块中独立的趋势打分阈值输入框），确保保存和回显使用同一数据源，消除切换策略时参数不一致的问题。


### 需求 24：数据管理页面与双数据源服务适配完善

**用户故事：** 作为量化交易员，我希望数据管理页面能展示Tushare和AkShare两个数据源的实时健康状态、显示每种数据同步实际使用的数据源、支持按数据类型单独触发同步任务、并用真实的数据清洗统计替换硬编码数值，以便全面掌握双数据源运行状况并灵活管理数据同步流程。

#### 验收标准

1. THE DataEngine SHALL 提供 `GET /api/v1/data/sources/health` 接口，该接口分别调用 TushareAdapter 和 AkShareAdapter 的 `health_check()` 方法，返回每个数据源的名称、连通状态（connected 或 disconnected）和检测时间戳。
2. WHEN 用户打开数据管理页面时，THE WebUI SHALL 调用 `GET /api/v1/data/sources/health` 接口，以状态卡片形式展示 Tushare 和 AkShare 各自的健康状态，连通时卡片显示绿色"已连接"标识，不可用时卡片显示红色"已断开"标识。
3. THE DataEngine SHALL 更新 `GET /api/v1/data/sync/status` 接口的返回数据，在每条同步状态记录中新增 `data_source` 字段（取值为 "Tushare" 或 "AkShare"）和 `is_fallback` 布尔字段，标识该类型数据最近一次同步实际使用的数据源以及是否触发了故障转移。
4. THE WebUI 数据管理页面同步状态表格 SHALL 新增"数据源"列，显示每条同步记录实际使用的数据源名称，WHEN `is_fallback` 为 true 时在数据源名称后追加"（故障转移）"标注。
5. THE DataEngine SHALL 更新 `POST /api/v1/data/sync` 接口，接受可选的 `sync_type` 参数（取值为 "kline"、"fundamentals"、"money_flow" 或 "all"），根据参数值分别调用对应的 Celery 异步任务，`sync_type` 缺省时默认触发全部三种同步任务。
6. THE WebUI 数据管理页面 SHALL 在手动同步按钮前提供同步类型选择控件，选项包括"全部同步"、"行情数据"、"基本面数据"、"资金流向"，用户选择后点击同步按钮时将对应的 `sync_type` 参数传递至 `POST /api/v1/data/sync` 接口。
7. THE DataEngine SHALL 提供 `GET /api/v1/data/cleaning/stats` 接口，从数据库中查询并返回实时数据清洗统计信息，包含总股票数、有效标的数、ST/退市剔除数、新股剔除数、停牌剔除数和高质押剔除数。
8. WHEN 用户打开数据管理页面时，THE WebUI SHALL 调用 `GET /api/v1/data/cleaning/stats` 接口获取实时数据清洗统计，替换当前硬编码的静态数值，在统计卡片中展示从接口返回的各项数据。
9. IF `GET /api/v1/data/sources/health` 接口调用 `health_check()` 方法时发生异常，THEN THE DataEngine SHALL 捕获该异常并将对应数据源状态标记为 disconnected，接口正常返回结果而非抛出错误。
10. IF `GET /api/v1/data/cleaning/stats` 接口查询数据库失败，THEN THE WebUI SHALL 在数据清洗统计区域显示错误提示信息并提供重试操作入口。

### 需求 25：历史数据批量回填（行情、基本面、资金流向）

**用户故事：** 作为量化交易员，我希望系统能批量回填指定股票或全市场的历史K线行情数据、基本面数据和资金流向数据，并支持每日自动增量同步，以便回测引擎和选股计算拥有完整的历史数据基础。

#### 验收标准

1. THE DataEngine SHALL 提供 `POST /api/v1/data/backfill` 接口，接受以下参数：`data_types`（数据类型列表，取值为 "kline"、"fundamentals"、"money_flow" 的任意组合，默认全部三种）、`symbols`（股票代码列表，留空表示全市场）、`start_date`（起始日期）、`end_date`（结束日期）、`freq`（K线频率，仅 kline 类型有效，取值为 "1d"、"1w"、"1M"，默认 "1d"），调用对应的 Celery 异步回填任务，返回任务ID。
2. WHEN `POST /api/v1/data/backfill` 接口未传入 `symbols` 参数或 `symbols` 为空列表时，THE DataEngine SHALL 从数据库 StockInfo 表查询全市场有效股票代码列表作为默认回填范围。
3. WHEN `POST /api/v1/data/backfill` 接口未传入 `start_date` 参数时，THE DataEngine SHALL 使用当前日期往前推 `kline_history_years`（配置默认值10年）作为默认起始日期。
4. THE DataEngine SHALL 提供 Celery 异步任务 `sync_historical_kline`，该任务通过 DataSourceRouter（Tushare 主数据源、AkShare 备用数据源故障转移）获取指定股票列表在指定日期范围内的历史K线数据，并通过 KlineRepository 批量写入 TimescaleDB，支持 "1d"（日线）、"1w"（周线）、"1M"（月线）三种K线频率。
5. THE DataEngine SHALL 提供 Celery 异步任务 `sync_historical_fundamentals`，该任务通过 DataSourceRouter 获取指定股票列表的历史基本面数据（财务报表、估值指标），并写入 PostgreSQL 业务数据库。
6. THE DataEngine SHALL 提供 Celery 异步任务 `sync_historical_money_flow`，该任务通过 DataSourceRouter 获取指定股票列表在指定日期范围内的历史资金流向数据（主力资金、北向资金），并写入 PostgreSQL 业务数据库。
7. THE DataEngine 所有历史回填任务 SHALL 将股票列表按每批不超过50只的批次进行处理，每批次之间等待至少1秒间隔，避免触发 Tushare 和 AkShare 的 API 频率限制。
8. THE DataEngine 所有历史回填任务 SHALL 确保回填操作幂等，对已存在的数据跳过写入（K线数据利用 ON CONFLICT DO NOTHING 机制，基本面和资金流向数据通过主键或唯一约束去重），重复执行不产生重复数据。
9. THE DataEngine SHALL 提供 `GET /api/v1/data/backfill/status` 接口，从 Redis 中读取回填进度信息，返回 `total`（总股票数）、`completed`（已完成数）、`failed`（失败数）、`current_symbol`（当前正在处理的股票代码）、`status`（任务状态：pending、running、completed、failed）、`data_types`（正在回填的数据类型列表）字段。
10. WHEN 回填任务执行时，THE DataEngine SHALL 将回填进度信息实时写入 Redis，每完成一只股票的回填后更新一次进度。
11. IF 回填任务在处理某只股票时 DataSourceRouter 的 Tushare 和 AkShare 均调用失败，THEN THE DataEngine SHALL 记录该股票的错误信息，将 failed 计数加1，继续处理下一只股票，任务不因单只股票失败而中断。
12. WHEN 已有回填任务正在执行时（status 为 running），THE DataEngine `POST /api/v1/data/backfill` 接口 SHALL 拒绝新的回填请求并返回提示信息"已有回填任务正在执行，请等待完成后再试"。
13. THE DataEngine SHALL 在 Celery Beat 调度计划中注册 `sync_daily_kline` 定时任务，每个交易日（周一至周五）16:00 自动执行，回填前一个交易日全市场有效股票的日K线数据，实现历史K线数据的每日增量同步。
14. THE WebUI 数据管理页面 SHALL 新增"历史数据回填"区域，提供以下控件：数据类型多选复选框（行情数据/基本面数据/资金流向，默认全选）、股票代码输入框（支持多个代码逗号分隔，留空表示全市场）、起止日期选择器、K线频率选择控件（日线/周线/月线，仅当选中行情数据时显示）和"开始回填"按钮，点击后调用 `POST /api/v1/data/backfill` 接口触发回填任务。
15. THE WebUI 数据管理页面历史数据回填区域 SHALL 展示回填进度信息，包含进度条（已完成数/总数）、当前处理股票代码、正在回填的数据类型、失败数量和任务状态，通过定时轮询 `GET /api/v1/data/backfill/status` 接口（每3秒一次）更新进度显示，任务完成或失败后停止轮询。

### 需求 26：大盘概况页面股票K线图扩展基本面数据与资金流向展示

**用户故事：** 作为量化交易员，我希望在大盘概况页面查询个股K线图时，能同时查看该股票的基本面核心指标和资金流向数据，以便在分析技术走势的同时快速评估个股的基本面质量和主力资金动向，辅助交易决策。

#### 验收标准

1. THE WebUI 大盘概况页面 SHALL 在股票查询K线展示图区域新增"基本面"和"资金流向"两个数据标签页，与现有"K线图"标签页并列展示，用户可通过点击标签页在三个视图之间自由切换。
2. WHEN 用户在大盘概况页面输入股票代码并查询后切换至"基本面"标签页时，THE WebUI SHALL 调用 `GET /api/v1/data/stock/{symbol}/fundamentals` 接口获取该股票的基本面数据，并以数据卡片形式展示以下核心指标：市盈率（PE TTM）、市净率（PB）、净资产收益率（ROE）、总市值、营收同比增长率、净利润同比增长率。
3. WHEN 用户在大盘概况页面输入股票代码并查询后切换至"资金流向"标签页时，THE WebUI SHALL 调用 `GET /api/v1/data/stock/{symbol}/money-flow` 接口获取该股票的资金流向数据，并以图表和数据卡片组合形式展示以下核心指标：当日主力资金净流入金额、近5日主力资金净流入累计金额、北向资金持仓变动、大单成交占比。
4. THE WebUI 大盘概况页面"资金流向"标签页 SHALL 以柱状图形式展示该股票近20个交易日的每日主力资金净流入金额趋势，正值显示为红色柱体，负值显示为绿色柱体。
5. THE WebUI 大盘概况页面"基本面"标签页 SHALL 对各指标数值进行颜色标注：PE TTM 低于行业均值时标注为绿色（低估）、高于行业均值时标注为红色（高估）；ROE 大于15%时标注为绿色（优质）、低于8%时标注为红色（较差）；营收和净利润同比增长率为正值时标注为红色（增长）、为负值时标注为绿色（下降）。
6. THE DataEngine SHALL 提供 `GET /api/v1/data/stock/{symbol}/fundamentals` 接口，通过 DataSourceRouter 获取指定股票的最新基本面数据，返回字段包含：`pe_ttm`（市盈率TTM）、`pb`（市净率）、`roe`（净资产收益率）、`market_cap`（总市值，单位：亿元）、`revenue_growth`（营收同比增长率，单位：%）、`net_profit_growth`（净利润同比增长率，单位：%）、`report_period`（报告期）、`updated_at`（数据更新时间）。
7. THE DataEngine SHALL 提供 `GET /api/v1/data/stock/{symbol}/money-flow` 接口，接受可选的 `days` 查询参数（默认值20），通过 DataSourceRouter 获取指定股票近 `days` 个交易日的资金流向数据，返回字段包含每日记录列表，每条记录包含：`trade_date`（交易日期）、`main_net_inflow`（主力资金净流入，单位：万元）、`north_net_inflow`（北向资金净流入，单位：万元）、`large_order_ratio`（大单成交占比，单位：%）、`super_large_inflow`（超大单净流入，单位：万元）、`large_inflow`（大单净流入，单位：万元）。
8. IF `GET /api/v1/data/stock/{symbol}/fundamentals` 接口查询的股票代码不存在或无基本面数据，THEN THE DataEngine SHALL 返回 404 状态码和明确的错误提示信息"未找到该股票的基本面数据"。
9. IF `GET /api/v1/data/stock/{symbol}/money-flow` 接口查询的股票代码不存在或无资金流向数据，THEN THE DataEngine SHALL 返回 404 状态码和明确的错误提示信息"未找到该股票的资金流向数据"。
10. WHEN 用户在"基本面"或"资金流向"标签页时，THE WebUI SHALL 在数据加载过程中显示加载状态指示器，WHEN 接口请求失败时显示明确的错误提示信息并提供重试操作入口，对应需求21验收标准25的统一加载与错误处理规范。
11. THE WebUI 大盘概况页面 SHALL 在"基本面"标签页底部显示数据报告期和更新时间，使用户了解基本面数据的时效性。
12. THE WebUI 大盘概况页面 SHALL 在切换股票查询时自动重置"基本面"和"资金流向"标签页的数据状态，重新加载新股票的对应数据。

### 需求 27：策略模板新建时可选配置模块多选

**用户故事：** 作为量化交易员，我希望在智能选股页面新建策略模板时，能够以多选方式自由选择需要启用的配置模块（因子条件编辑器、均线趋势配置、技术指标配置、形态突破配置、量价资金筛选），这些模块均为可选项而非必选项，以便根据不同的交易策略风格灵活组合所需的配置模块，避免不必要的配置项干扰。

#### 验收标准

1. WHEN 用户在选股策略页面点击"新建策略"时，THE WebUI SHALL 展示策略模板创建表单，表单中包含策略名称输入框和配置模块多选区域，配置模块多选区域以复选框形式列出以下五个可选模块：因子条件编辑器、均线趋势配置、技术指标配置、形态突破配置、量价资金筛选，所有模块默认未勾选。
2. THE WebUI 策略模板创建表单 SHALL 允许用户勾选零个或多个配置模块，不强制要求勾选任何模块，用户可以仅填写策略名称后直接创建空策略模板。
3. WHEN 用户完成模块勾选并确认创建策略模板后，THE WebUI SHALL 仅在选股策略页面展示用户所勾选的配置模块面板，未勾选的模块面板隐藏不显示。
4. THE WebUI SHALL 在已创建的策略模板配置中持久化用户选择的模块列表（`enabled_modules` 字段，取值为 "factor_editor"、"ma_trend"、"indicator_params"、"breakout"、"volume_price" 的任意子集），调用 `POST /api/v1/strategies` 创建策略时将 `enabled_modules` 字段包含在请求体中。
5. WHEN 用户选中一个已保存的策略模板时，THE WebUI SHALL 根据该策略的 `enabled_modules` 字段动态显示对应的配置模块面板，未启用的模块面板隐藏不显示，对应需求22验收标准1的配置回显逻辑。
6. THE WebUI 选股策略页面 SHALL 在已选中策略的配置区域提供"管理模块"按钮，WHEN 用户点击"管理模块"时弹出模块选择对话框，允许用户修改当前策略已启用的配置模块，修改后调用 `PUT /api/v1/strategies/{id}` 更新 `enabled_modules` 字段，页面立即刷新显示或隐藏对应的配置面板。
7. THE StockScreener SHALL 在执行选股时仅应用策略模板中 `enabled_modules` 所列模块对应的筛选逻辑，未启用的模块对应的筛选条件不参与选股计算。
8. WHEN 策略模板的 `enabled_modules` 为空列表时，THE StockScreener SHALL 跳过所有模块筛选逻辑，返回空的选股结果集。
9. WHEN 用户通过 `POST /api/v1/screen/run` 接口执行选股时，THE StockScreener SHALL 完成以下完整执行流程：若请求中包含 `strategy_id`，从策略存储中加载该策略的完整配置（含 `config` 和 `enabled_modules`）；若请求中包含 `strategy_config` 而无 `strategy_id`，使用请求中的配置并将 `enabled_modules` 视为全部启用；从本地数据库（TimescaleDB kline 表和 PostgreSQL 业务表）查询全市场有效股票的最新行情数据和因子数据作为选股输入；使用加载的策略配置和 `enabled_modules` 实例化 `ScreenExecutor` 并执行选股；返回包含实际选股结果的 `ScreenResult`（含 `items` 列表、每条结果的 `symbol`、`ref_buy_price`、`trend_score`、`risk_level`、`signals`）。
10. THE StockScreener `POST /api/v1/screen/run` 接口 SHALL 从本地数据库获取选股所需的股票数据，不直接调用外部数据源接口，具体包括：从 TimescaleDB `kline` 表查询各股票最近 N 个交易日的日 K 线数据（用于均线计算、形态识别、量价分析），从 PostgreSQL `stock_info` 表查询股票基本面数据（PE/PB/ROE/市值等），从 PostgreSQL 资金流向相关表查询主力资金和北向资金数据。
11. IF `POST /api/v1/screen/run` 接口传入的 `strategy_id` 在策略存储中不存在，THEN THE StockScreener SHALL 返回 HTTP 404 状态码和明确的错误提示信息"策略不存在"。
12. IF `POST /api/v1/screen/run` 接口执行选股时本地数据库中无可用的行情数据，THEN THE StockScreener SHALL 返回空的选股结果集（`items` 为空列表）并在响应中标注 `is_complete: true`，不抛出异常。

### 需求 28：风险控制页面 API 实装与数据持久化

**用户故事：** 作为量化交易员，我希望风险控制页面展示的大盘风控状态、止损止盈配置、黑白名单和仓位预警信息均来自真实的服务端计算和数据库存储，而非硬编码的占位数据，以便在实盘交易中依赖风控系统做出准确的风险管理决策。

#### 验收标准

##### 大盘风控状态实时计算

1. THE RiskController SHALL 提供 `GET /api/v1/risk/overview` 接口，该接口从 TimescaleDB kline 表查询上证指数（000001.SH）和创业板指（399006.SZ）最近 60 个交易日的日 K 线收盘价，调用 `MarketRiskChecker.check_market_risk()` 分别计算两个指数的风险等级，返回包含以下字段的响应：`market_risk_level`（NORMAL / CAUTION / DANGER，取两个指数中更严重的等级）、`sh_above_ma20`（布尔值）、`sh_above_ma60`（布尔值）、`cyb_above_ma20`（布尔值）、`cyb_above_ma60`（布尔值）、`current_threshold`（当前趋势打分阈值，NORMAL 时为 80，CAUTION/DANGER 时为 90）。
2. IF `GET /api/v1/risk/overview` 接口查询指数 K 线数据失败或数据不足，THEN THE RiskController SHALL 返回 `market_risk_level: "NORMAL"` 的保守默认值，不抛出异常，并在响应中标注 `data_insufficient: true`。

##### 委托风控校验实装

3. THE RiskController SHALL 更新 `POST /api/v1/risk/check` 接口，接受委托请求参数（symbol、direction、quantity、price），依次调用以下风控检查并返回综合校验结果：
   - 调用 `BlackWhiteListManager.is_blacklisted(symbol)` 检查黑名单，命中时返回 `passed: false, reason: "该股票在黑名单中"`
   - 调用 `StockRiskFilter.check_daily_gain()` 检查当日涨幅，超过 9% 时返回 `passed: false, reason: "个股单日涨幅超过9%"`
   - 调用 `PositionRiskChecker.check_stock_position_limit()` 检查单股仓位上限，超过 15% 时返回 `passed: false, reason: "单股仓位超过15%上限"`
   - 调用 `PositionRiskChecker.check_sector_position_limit()` 检查板块仓位上限，超过 30% 时返回 `passed: false, reason: "板块仓位超过30%上限"`
   - 所有检查通过时返回 `passed: true`
4. THE RiskController `POST /api/v1/risk/check` 接口 SHALL 按以上顺序依次执行风控检查，遇到第一个不通过的检查即返回失败结果，不继续执行后续检查。

##### 止损止盈配置持久化

5. THE RiskController SHALL 提供 `POST /api/v1/risk/stop-config` 接口，接受止损止盈配置参数（`fixed_stop_loss`: 固定止损比例，`trailing_stop`: 移动止损回撤比例，`trend_stop_ma`: 趋势止损均线周期），将配置持久化至 Redis（键名 `risk:stop_config:{user_id}`，过期时间 30 天），返回保存成功确认。
6. THE RiskController SHALL 提供 `GET /api/v1/risk/stop-config` 接口，从 Redis 读取当前用户的止损止盈配置，Redis 无数据时返回默认值（`fixed_stop_loss: 8`, `trailing_stop: 5`, `trend_stop_ma: 20`）。
7. WHEN 用户打开风险控制页面时，THE WebUI SHALL 调用 `GET /api/v1/risk/stop-config` 接口加载已保存的止损止盈配置并回填至配置表单，替代当前的前端硬编码默认值。

##### 持仓预警实时检测

8. THE RiskController SHALL 提供 `GET /api/v1/risk/position-warnings` 接口，该接口从数据库查询当前用户的所有持仓记录，对每只持仓标的执行以下检测并返回预警列表：
   - 调用 `PositionRiskChecker.check_stock_position_limit()` 检测单股仓位是否超过 15%，超过时生成 `danger` 级别预警
   - 调用 `PositionRiskChecker.check_sector_position_limit()` 检测板块仓位是否超过 30%，超过时生成 `warning` 级别预警
   - 调用 `PositionRiskChecker.check_position_breakdown()` 检测是否触发破位预警（跌破 MA20 + 放量下跌 > 5%），触发时生成 `danger` 级别预警
   - 调用 `StopLossChecker.check_fixed_stop_loss()` 检测是否触发固定止损，触发时生成 `danger` 级别预警
   - 调用 `StopLossChecker.check_trailing_stop_loss()` 检测是否触发移动止损，触发时生成 `warning` 级别预警
   - 调用 `StopLossChecker.check_trend_stop_loss()` 检测是否触发趋势止损，触发时生成 `warning` 级别预警
9. THE RiskController `GET /api/v1/risk/position-warnings` 接口返回的每条预警记录 SHALL 包含以下字段：`symbol`（股票代码）、`type`（预警类型描述）、`level`（"danger" | "warning" | "info"）、`current_value`（当前值）、`threshold`（阈值）、`time`（检测时间）。
10. IF 当前用户无持仓记录，THEN `GET /api/v1/risk/position-warnings` 接口 SHALL 返回空列表，不抛出异常。

##### 黑白名单数据库持久化

11. THE RiskController SHALL 更新黑名单 CRUD 接口（`GET /api/v1/blacklist`、`POST /api/v1/blacklist`、`DELETE /api/v1/blacklist/{symbol}`），连接 PostgreSQL `stock_list` 表（`list_type='BLACK'`）进行真实的数据库读写操作，替代当前的 stub 实现。
12. THE RiskController SHALL 更新白名单 CRUD 接口（`GET /api/v1/whitelist`、`POST /api/v1/whitelist`、`DELETE /api/v1/whitelist/{symbol}`），连接 PostgreSQL `stock_list` 表（`list_type='WHITE'`）进行真实的数据库读写操作，替代当前的 stub 实现。
13. THE RiskController 黑白名单 `GET` 接口 SHALL 支持分页查询（`page` 和 `page_size` 参数），返回 `total`（总数）、`items`（当前页数据列表）字段。
14. WHEN 用户通过 `POST /api/v1/blacklist` 添加已存在于黑名单中的股票代码时，THE RiskController SHALL 返回 HTTP 409 状态码和提示信息"该股票已在黑名单中"，不产生重复记录。

##### 策略健康状态实时计算

15. THE RiskController SHALL 更新 `GET /api/v1/risk/strategy-health` 接口，接受可选的 `strategy_id` 查询参数，从数据库查询该策略关联的回测结果或交易记录，计算实时胜率和最大回撤，调用 `StopLossChecker.check_strategy_health()` 判定策略是否健康，返回 `strategy_id`、`win_rate`、`max_drawdown`、`is_healthy`（布尔值）、`warnings`（预警信息列表）字段。
16. IF `GET /api/v1/risk/strategy-health` 接口未传入 `strategy_id` 或该策略无交易记录，THEN THE RiskController SHALL 返回 `is_healthy: true`、`win_rate: 0`、`max_drawdown: 0`、`warnings: []` 的默认值。

### 需求 29：复盘分析页面 API 实装与数据持久化

**用户故事：** 作为量化交易员，我希望复盘分析页面展示的每日复盘报告、策略绩效报表、市场复盘分析和报表导出功能均来自真实的服务端计算和数据库查询，而非硬编码的占位数据，以便在每个交易日收盘后通过复盘数据持续优化交易策略。

#### 验收标准

##### 每日复盘报告 API 实装

1. THE ReviewAnalyzer SHALL 更新 `GET /api/v1/review/daily` 接口，接受可选的 `date` 查询参数（默认最近交易日），从 PostgreSQL `trade_order` 表查询该日期所有已成交（status='FILLED'）的交易记录，从 `screen_result` 表查询该日期的选股结果，调用 `ReviewAnalyzer.generate_daily_review()` 生成真实的复盘报告，返回包含以下字段的响应：`date`（复盘日期）、`win_rate`（胜率）、`total_pnl`（总盈亏）、`trade_count`（交易笔数）、`success_cases`（成功案例列表，每条含 symbol、pnl、reason）、`failure_cases`（失败案例列表，每条含 symbol、pnl、reason）。
2. IF `GET /api/v1/review/daily` 接口查询的日期无交易记录，THEN THE ReviewAnalyzer SHALL 返回 `win_rate: 0`、`total_pnl: 0`、`trade_count: 0`、`success_cases: []`、`failure_cases: []` 的默认值，不抛出异常。
3. THE ReviewAnalyzer SHALL 将生成的每日复盘报告以 JSON 格式缓存至 Redis（键名 `review:daily:{date}`，过期时间 7 天），后续相同日期的请求直接从缓存读取，避免重复计算。

##### 策略绩效报表 API 实装

4. THE ReviewAnalyzer SHALL 更新 `GET /api/v1/review/strategy-report` 接口，接受 `strategy_id`（必填）、`period`（"daily" / "weekly" / "monthly"，默认 "daily"）查询参数，从 PostgreSQL `trade_order` 表查询该策略关联的交易记录，调用 `StrategyReportGenerator.generate_period_report()` 生成绩效报表，返回包含以下字段的响应：`strategy_id`、`strategy_name`、`period`、`returns`（日期-收益率序列，供前端 ECharts 渲染折线图和柱状图）、`risk_metrics`（含 `max_drawdown`、`sharpe_ratio`、`win_rate`、`calmar_ratio`）。
5. IF `GET /api/v1/review/strategy-report` 接口未传入 `strategy_id`，THEN THE ReviewAnalyzer SHALL 返回 HTTP 400 状态码和提示信息"请指定策略ID"。
6. IF `GET /api/v1/review/strategy-report` 接口传入的 `strategy_id` 无关联交易记录，THEN THE ReviewAnalyzer SHALL 返回空的 `returns` 列表和全零的 `risk_metrics`，不抛出异常。

##### 市场复盘分析 API 新增

7. THE ReviewAnalyzer SHALL 提供 `GET /api/v1/review/market` 接口，接受可选的 `date` 查询参数（默认最近交易日），调用 `MarketReviewAnalyzer` 的三个分析方法，返回包含以下字段的响应：`sector_rotation`（板块轮动分析，含 `top_sectors`、`bottom_sectors`、`rotation_summary`）、`trend_distribution`（趋势行情分布，含 `bins` 和 `counts`）、`money_flow`（资金流向分析，含 `net_inflow_total`、`top_inflow_sectors`、`top_outflow_sectors`）。
8. THE ReviewAnalyzer `GET /api/v1/review/market` 接口 SHALL 从本地数据库获取板块数据（板块涨跌幅）、个股趋势评分和资金流向数据，不直接调用外部数据源接口。
9. IF `GET /api/v1/review/market` 接口查询的日期无市场数据，THEN THE ReviewAnalyzer SHALL 返回各字段的空默认值（空列表和零值），不抛出异常。

##### 报表导出 API 实装

10. THE ReviewAnalyzer SHALL 提供 `GET /api/v1/review/export` 接口，接受 `period`（"daily" / "weekly" / "monthly"）和可选的 `strategy_id`、`format`（"csv" / "json"，默认 "csv"）查询参数，调用 `ReportExporter` 生成对应格式的报表文件，以文件下载流形式返回（Content-Disposition: attachment）。
11. WHEN `format` 为 "csv" 时，THE ReviewAnalyzer `GET /api/v1/review/export` 接口 SHALL 返回 UTF-8 编码（含 BOM）的 CSV 文件，Content-Type 为 `text/csv; charset=utf-8`。
12. WHEN `format` 为 "json" 时，THE ReviewAnalyzer `GET /api/v1/review/export` 接口 SHALL 返回 JSON 文件，Content-Type 为 `application/json`。

##### Celery 任务数据加载实装

13. THE ReviewAnalyzer SHALL 更新 Celery 任务 `generate_daily_review` 中的 `_load_trade_records()` 函数，从 PostgreSQL `trade_order` 表查询指定日期所有已成交的交易记录（status='FILLED'），返回包含 symbol、profit、direction、price、quantity 字段的字典列表。
14. THE ReviewAnalyzer SHALL 更新 Celery 任务 `generate_daily_review` 中的 `_load_screen_results()` 函数，从 PostgreSQL `screen_result` 表查询指定日期的盘后选股结果（screen_type='EOD'），返回包含 symbol、trend_score、risk_level、signals 字段的字典列表。
15. THE ReviewAnalyzer Celery 任务 `generate_daily_review` SHALL 在生成复盘报告后将结果缓存至 Redis（键名 `review:daily:{date}`，过期时间 7 天），供 `GET /api/v1/review/daily` 接口直接读取。

##### 多策略对比 API 支持

16. THE ReviewAnalyzer SHALL 提供 `POST /api/v1/review/compare` 接口，接受 `strategy_ids`（策略ID列表，至少2个）和 `period` 参数，对每个策略调用 `StrategyReportGenerator.generate_period_report()` 生成报表，再调用 `StrategyReportGenerator.compare_strategies()` 生成对比分析结果，返回包含各策略绩效摘要和最佳策略标识的响应。
17. IF `POST /api/v1/review/compare` 接口传入的 `strategy_ids` 少于 2 个，THEN THE ReviewAnalyzer SHALL 返回 HTTP 400 状态码和提示信息"请至少选择2个策略进行对比"。
