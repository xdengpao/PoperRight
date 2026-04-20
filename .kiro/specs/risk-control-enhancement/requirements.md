# 需求文档：风控系统增强

## 简介

对 A 股量化交易平台的风险控制系统进行全面增强。当前风控模块存在多项关键缺陷：交易执行链路未强制调用风控校验、止损预警仅支持被动拉取而非实时推送、黑白名单管理器使用内存存储导致重启丢失数据、止损参数为全局配置无法适配不同波动率的个股、缺少总仓位控制、板块仓位使用交易所板块而非真实行业分类、破位检测条件过于严格、策略健康仅检查历史回测而非实盘表现、大盘风控仅监控两个指数、无风控事件历史日志、大盘风控缺少趋势可视化、持仓预警表缺少关键决策信息。本需求覆盖 P0 至 P3 共 12 项优化，按优先级分阶段实施。

## 术语表

- **Trade_Executor（交易执行器）**：负责委托提交的服务组件，位于 `app/services/trade_executor.py`
- **Risk_Controller（风控控制器）**：风控校验核心模块，位于 `app/services/risk_controller.py`，包含 MarketRiskChecker、StockRiskFilter、BlackWhiteListManager、PositionRiskChecker、StopLossChecker、SectorConcentrationChecker
- **Risk_Gateway（风控网关）**：在交易执行链路中强制执行风控校验的拦截层
- **Risk_API（风控 API）**：风控相关的 REST 端点，位于 `app/api/v1/risk.py`
- **BlackWhiteList_Manager（黑白名单管理器）**：管理个股黑名单和白名单的组件
- **Stop_Loss_Checker（止损检测器）**：检测固定止损、移动止损、趋势止损的组件
- **Position_Risk_Checker（仓位风控检测器）**：检测单股仓位、板块仓位、破位预警的组件
- **Market_Risk_Checker（大盘风控检测器）**：根据指数均线判定大盘风险等级的组件
- **ATR（Average True Range，平均真实波幅）**：衡量个股波动率的技术指标，用于自适应止损参数计算
- **WebSocket_Manager（WebSocket 管理器）**：管理 WebSocket 连接和消息推送的组件
- **Risk_Event_Log（风控事件日志）**：记录风控规则触发历史的持久化日志
- **Total_Position（总仓位）**：所有持仓市值占总资产（持仓市值 + 可用现金）的比例
- **Industry_Classification（行业分类）**：基于申万行业分类标准的真实行业划分，如银行、半导体、医药等
- **Strategy_Health_Monitor（策略健康监控器）**：监控策略实盘运行表现的组件，区别于仅检查历史回测的现有逻辑

## 需求

### 需求 1：交易执行链路强制风控校验（P0）

**用户故事：** 作为量化交易员，我希望所有交易委托在提交前自动经过风控校验，以防止任何绕过风控的交易行为。

#### 验收标准

1. WHEN Trade_Executor 收到委托请求, THE Risk_Gateway SHALL 在委托提交至券商之前执行完整的风控校验链（黑名单检查 → 涨幅检查 → 单股仓位检查 → 板块仓位检查）
2. IF 风控校验链中任一检查未通过, THEN THE Risk_Gateway SHALL 拒绝该委托并返回包含拒绝原因的 OrderResponse（status=REJECTED）
3. THE Risk_Gateway SHALL 对卖出方向（SELL）的委托跳过买入相关的风控检查（黑名单、涨幅、仓位上限），仅执行卖出相关校验
4. WHEN 风控校验通过, THE Risk_Gateway SHALL 将委托传递给底层 BrokerClient 执行提交
5. THE Risk_Gateway SHALL 确保 Celery 异步任务和直接代码调用 Trade_Executor 时均经过相同的风控校验链
6. IF 风控校验过程中发生异常, THEN THE Risk_Gateway SHALL 拒绝该委托并记录异常日志，返回 REJECTED 状态及异常描述
7. THE Risk_Gateway SHALL 提供纯函数版本的风控校验方法（不依赖数据库），接受持仓数据和行情数据作为参数，便于属性测试

### 需求 2：止损预警实时 WebSocket 推送（P0）

**用户故事：** 作为量化交易员，我希望在止损条件触发时立即收到实时推送通知，以便在快速下跌的行情中及时做出止损决策。

#### 验收标准

1. WHEN 止损条件（固定止损、移动止损、趋势止损）被触发, THE WebSocket_Manager SHALL 在 2 秒内通过 WebSocket 连接向前端推送止损预警消息
2. THE 止损预警消息 SHALL 包含以下字段：股票代码、预警类型、当前价格、触发阈值、预警级别（danger/warning）、触发时间
3. THE 前端风控页面 SHALL 建立 WebSocket 连接，实时接收并展示止损预警消息，无需手动刷新
4. WHEN 前端收到止损预警消息, THE 前端 SHALL 在仓位风控预警表格中实时插入新的预警行，并以视觉高亮（闪烁动画）提示用户
5. IF WebSocket 连接断开, THEN THE 前端 SHALL 自动尝试重连（最多 5 次，间隔递增），重连期间显示连接状态提示
6. THE 后端 SHALL 通过 Redis Pub/Sub 将止损预警事件发布到风控预警频道，由 WebSocket_Manager 中继推送至前端
7. WHILE 处于非交易时段（15:00 至次日 9:25）, THE 止损预警推送 SHALL 暂停，避免无效推送

### 需求 3：黑白名单持久化存储（P1）

**用户故事：** 作为量化交易员，我希望黑白名单数据在服务重启后仍然保留，以确保风控规则的持续有效性。

#### 验收标准

1. THE BlackWhiteList_Manager SHALL 在启动时从 PostgreSQL 数据库的 StockList 表加载黑白名单数据到内存缓存
2. WHEN 用户通过 API 添加股票到黑名单或白名单, THE BlackWhiteList_Manager SHALL 同时更新内存缓存和数据库记录
3. WHEN 用户通过 API 从黑名单或白名单移除股票, THE BlackWhiteList_Manager SHALL 同时从内存缓存和数据库中删除对应记录
4. IF 数据库写入失败, THEN THE BlackWhiteList_Manager SHALL 回滚内存缓存的变更并返回错误信息
5. THE BlackWhiteList_Manager SHALL 在风控校验时使用内存缓存进行查询，确保查询性能不受数据库延迟影响
6. THE BlackWhiteList_Manager SHALL 提供纯函数版本的黑白名单查询方法，接受名单集合作为参数，便于属性测试
7. FOR ALL 黑白名单操作序列（添加、删除、查询的任意组合），执行操作后内存缓存的状态 SHALL 与数据库中的状态保持一致（一致性不变量）

### 需求 4：个股自适应止损参数（P1）

**用户故事：** 作为量化交易员，我希望止损参数能根据个股波动率自动调整，以避免高波动股票频繁触发止损或低波动股票止损过宽。

#### 验收标准

1. THE Stop_Loss_Checker SHALL 支持基于 ATR 的自适应止损模式，使用 14 日 ATR 值动态计算止损阈值
2. WHEN 自适应止损模式启用时, THE Stop_Loss_Checker SHALL 按照公式「止损价 = 成本价 - ATR × 倍数」计算固定止损触发价，默认 ATR 倍数为 2.0
3. WHEN 自适应止损模式启用时, THE Stop_Loss_Checker SHALL 按照公式「移动止损回撤幅度 = ATR × 倍数 / 最高价」计算移动止损回撤比例，默认 ATR 倍数为 1.5
4. THE 前端止损配置区域 SHALL 增加止损模式切换控件，支持「固定比例」和「ATR 自适应」两种模式
5. WHEN 用户选择 ATR 自适应模式, THE 前端 SHALL 显示 ATR 倍数输入框（固定止损倍数默认 2.0，移动止损倍数默认 1.5），隐藏固定比例输入框
6. THE 止损配置 SHALL 持久化到 Redis，包含止损模式（fixed/atr_adaptive）和对应参数
7. THE Stop_Loss_Checker SHALL 提供纯函数版本的 ATR 自适应止损计算方法，接受 ATR 值、成本价、当前价、最高价和倍数作为参数，便于属性测试
8. FOR ALL 有效的 ATR 值（ATR > 0）和有效的价格数据（成本价 > 0），ATR 自适应止损计算 SHALL 产生大于 0 且小于成本价的止损触发价（止损价有效性不变量）

### 需求 5：总仓位控制（P1）

**用户故事：** 作为量化交易员，我希望系统能监控和控制总仓位水平，以便在系统性风险升高时自动限制仓位上限。

#### 验收标准

1. THE Position_Risk_Checker SHALL 提供总仓位计算方法，总仓位比例 = 持仓总市值 /（持仓总市值 + 可用现金）× 100%
2. THE Risk_API SHALL 新增 GET /risk/total-position 端点，返回当前总仓位比例、持仓总市值、可用现金和仓位上限
3. WHEN 大盘风险等级为 NORMAL, THE Position_Risk_Checker SHALL 使用默认总仓位上限 80%
4. WHEN 大盘风险等级为 CAUTION, THE Position_Risk_Checker SHALL 自动将总仓位上限降低至 60%
5. WHEN 大盘风险等级为 DANGER, THE Position_Risk_Checker SHALL 自动将总仓位上限降低至 30%
6. IF 当前总仓位已超过对应风险等级的仓位上限, THEN THE Risk_Gateway SHALL 拒绝新的买入委托并返回「总仓位超过上限」的拒绝原因
7. THE 前端风控页面 SHALL 在大盘风控状态卡片下方新增总仓位状态区域，显示当前总仓位比例（含进度条）、仓位上限和可用现金
8. THE Position_Risk_Checker SHALL 提供纯函数版本的总仓位检查方法，接受持仓市值、可用现金和仓位上限作为参数，便于属性测试
9. FOR ALL 有效的持仓市值（≥ 0）和可用现金（≥ 0），总仓位比例计算结果 SHALL 在 0% 至 100% 之间（仓位比例范围不变量）

### 需求 6：板块仓位使用真实行业分类（P2）

**用户故事：** 作为量化交易员，我希望板块仓位控制基于真实行业分类（如银行、半导体）而非交易所板块（主板/创业板/科创板），以实现有意义的行业集中度控制。

#### 验收标准

1. THE Position_Risk_Checker SHALL 使用申万行业分类（一级行业）替代 StockInfo.board 字段进行板块仓位计算
2. THE Risk_API 的板块仓位检查 SHALL 查询股票所属的申万一级行业代码，将同行业持仓市值汇总后计算行业仓位占比
3. IF 股票的行业分类数据不可用, THEN THE Position_Risk_Checker SHALL 将该股票归入「未分类」行业，并在预警信息中标注
4. THE 前端仓位风控预警表格中的「板块仓位超限」预警 SHALL 显示具体行业名称（如「银行行业仓位超限」），替代当前的「板块仓位超限」
5. THE Position_Risk_Checker SHALL 提供纯函数版本的行业仓位计算方法，接受持仓列表和行业分类映射作为参数，便于属性测试
6. FOR ALL 持仓列表，各行业仓位占比之和 SHALL 等于总仓位占比（行业仓位加和不变量）

### 需求 7：破位检测条件优化（P2）

**用户故事：** 作为量化交易员，我希望破位检测能识别缓慢阴跌模式，以便在股票持续小幅下跌时也能收到预警。

#### 验收标准

1. THE Position_Risk_Checker SHALL 新增连续阴跌检测模式：当股票连续 N 个交易日下跌（收盘价低于前一日收盘价）且累计跌幅超过阈值时触发预警
2. THE 连续阴跌检测 SHALL 使用默认参数：连续下跌天数 N = 3，累计跌幅阈值 = 8%
3. THE Position_Risk_Checker SHALL 将现有破位检测条件从「三个条件全部满足」改为「三个条件满足其中两个」即触发预警
4. THE 前端仓位风控预警表格 SHALL 区分显示「急跌破位预警」（原有三条件检测）和「阴跌破位预警」（连续阴跌检测）两种预警类型
5. THE Position_Risk_Checker SHALL 提供纯函数版本的连续阴跌检测方法，接受收盘价序列和参数作为输入，便于属性测试
6. FOR ALL 长度为 N 的收盘价序列，连续阴跌检测结果 SHALL 仅依赖最近 N+1 个收盘价数据（局部性不变量）

### 需求 8：策略实盘健康监控（P2）

**用户故事：** 作为量化交易员，我希望系统能监控策略的实盘运行表现，而非仅依赖历史回测结果，以便及时发现策略在实盘中的退化。

#### 验收标准

1. THE Strategy_Health_Monitor SHALL 基于最近 N 笔实盘交易记录（默认 N = 20）计算实盘胜率和实盘最大回撤
2. WHEN 实盘胜率低于 40% 或实盘最大回撤超过 20%, THE Strategy_Health_Monitor SHALL 判定策略实盘表现不健康
3. THE Risk_API 的 GET /risk/strategy-health 端点 SHALL 同时返回历史回测指标和实盘运行指标，并分别标注数据来源
4. THE 前端 SHALL 在策略健康状态区域分两栏展示「回测表现」和「实盘表现」，各自显示胜率和最大回撤
5. IF 实盘交易记录不足 N 笔, THEN THE Strategy_Health_Monitor SHALL 在返回结果中标注「实盘数据不足，仅供参考」
6. THE Strategy_Health_Monitor SHALL 提供纯函数版本的实盘健康计算方法，接受交易记录列表作为参数，便于属性测试

### 需求 9：扩展大盘风控监控指数（P3）

**用户故事：** 作为量化交易员，我希望大盘风控能监控更多宽基指数，以获得更全面的市场风险评估。

#### 验收标准

1. THE Market_Risk_Checker SHALL 支持监控以下指数：上证指数（000001.SH）、创业板指（399006.SZ）、沪深 300（000300.SH）、中证 500（000905.SH）
2. THE Risk_API 的 GET /risk/overview 端点 SHALL 返回所有监控指数的均线状态（MA20/MA60 站上或跌破）
3. THE Market_Risk_Checker SHALL 取所有监控指数中最严重的风险等级作为综合大盘风险等级
4. THE 前端大盘风控状态卡片 SHALL 展示所有监控指数的均线状态，每个指数一行，显示指数名称和 MA20/MA60 状态
5. WHEN 新增指数的 K 线数据不可用, THE Market_Risk_Checker SHALL 跳过该指数并在日志中记录，不影响其他指数的风控判定

### 需求 10：风控事件历史日志（P3）

**用户故事：** 作为量化交易员，我希望查看风控规则的历史触发记录，以便分析风控策略的有效性并进行优化。

#### 验收标准

1. WHEN 任一风控规则被触发（委托拒绝、止损预警、仓位超限、破位预警）, THE Risk_Event_Log SHALL 将事件记录持久化到 PostgreSQL 数据库
2. THE 风控事件记录 SHALL 包含以下字段：事件类型、股票代码、触发规则名称、触发值、阈值、处理结果（拒绝/预警）、触发时间
3. THE Risk_API SHALL 新增 GET /risk/event-log 端点，支持按时间范围、事件类型和股票代码筛选查询，返回分页结果
4. THE 前端风控页面 SHALL 新增「风控日志」区域，以表格形式展示风控事件历史记录，支持按时间范围筛选
5. THE Risk_Event_Log SHALL 自动清理超过 90 天的历史记录，避免数据无限增长

### 需求 11：大盘风控趋势可视化（P3）

**用户故事：** 作为量化交易员，我希望在风控页面直观看到指数的 K 线走势和均线位置，以便快速判断市场趋势方向和距离均线的距离。

#### 验收标准

1. THE 前端大盘风控状态卡片 SHALL 新增指数 K 线迷你图区域，展示上证指数和创业板指最近 60 个交易日的日 K 线
2. THE 指数 K 线迷你图 SHALL 叠加显示 MA20 和 MA60 均线，均线颜色与风控状态对应（站上为绿色，跌破为红色）
3. THE Risk_API SHALL 新增 GET /risk/index-kline 端点，返回指定指数最近 60 个交易日的 OHLC 数据
4. WHEN 用户悬停在 K 线迷你图上, THE 前端 SHALL 显示该交易日的日期、开盘价、最高价、最低价、收盘价和 MA20/MA60 值
5. THE 指数 K 线迷你图 SHALL 使用 ECharts 组件渲染，复用项目已有的图表基础设施

### 需求 12：持仓预警表信息增强（P3）

**用户故事：** 作为量化交易员，我希望在持仓预警表中直接看到成本价、盈亏比例和建议操作，以便无需切换页面即可做出交易决策。

#### 验收标准

1. THE Risk_API 的 GET /risk/position-warnings 端点返回的预警条目 SHALL 新增以下字段：成本价（cost_price）、当前价（current_price）、盈亏比例（pnl_pct）、建议操作（suggested_action）
2. THE 建议操作字段 SHALL 根据预警类型生成：固定止损触发 → 「建议止损卖出」、移动止损触发 → 「建议减仓」、破位预警 → 「建议关注，考虑减仓」、仓位超限 → 「建议不再加仓」
3. THE 前端仓位风控预警表格 SHALL 新增「成本价」「盈亏」「建议操作」三列
4. THE 前端预警表格的「盈亏」列 SHALL 以百分比形式显示，盈利为绿色，亏损为红色
5. THE 前端预警表格的「建议操作」列 SHALL 以标签形式显示，不同操作类型使用不同颜色区分
