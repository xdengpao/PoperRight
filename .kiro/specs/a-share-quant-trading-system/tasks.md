# 任务列表：A股右侧股票交易量化选股系统

## 阶段 1：项目基础架构搭建

- [x] 1.1 初始化后端项目结构（FastAPI + Python）
  - 创建项目目录结构：`app/`（api、services、models、core）
  - 配置 `pyproject.toml`，添加依赖：fastapi、uvicorn、sqlalchemy、asyncpg、redis、celery、hypothesis、pytest
  - 配置环境变量管理（`.env` + pydantic-settings）

- [x] 1.2 初始化前端项目结构（Vue 3 + TypeScript）
  - 使用 Vite 创建 Vue 3 + TypeScript 项目
  - 配置 Vue Router、Pinia 状态管理、Axios、ECharts
  - 配置 Vitest 测试框架

- [x] 1.3 配置数据库
  - 部署 TimescaleDB（行情时序数据）
  - 部署 PostgreSQL（业务数据）
  - 部署 Redis（缓存 + 消息队列）
  - 编写数据库初始化迁移脚本（Alembic）

- [x] 1.4 配置 Celery 异步任务队列
  - 配置 Celery + Redis Broker
  - 配置 Celery Beat 定时任务调度器
  - 创建任务基类和错误处理中间件

- [x] 1.5 配置 WebSocket 服务
  - 实现 FastAPI WebSocket 连接管理器
  - 实现 Redis Pub/Sub 到 WebSocket 的消息转发

---

## 阶段 2：数据模型与数据库表

- [x] 2.1 创建行情数据表（TimescaleDB）
  - 创建 `kline` 超表，配置时间分区和索引
  - 编写 KlineBar 数据类和 ORM 模型

- [x] 2.2 创建业务数据表（PostgreSQL）
  - 创建 `stock_info`、`permanent_exclusion`、`stock_list` 表
  - 创建 `strategy_template`、`screen_result` 表
  - 创建 `backtest_run`、`trade_order`、`position` 表
  - 创建 `app_user`、`audit_log` 表
  - 编写对应 SQLAlchemy ORM 模型

- [x] 2.3 编写核心 Python 数据类
  - 实现 `KlineBar`、`ScreenResult`、`ScreenItem` 数据类
  - 实现 `BacktestResult`、`RiskCheckResult`、`Position`、`OrderRequest` 数据类
  - 实现 `StrategyConfig`、`FactorCondition`、`AlertConfig` 数据类

---

## 阶段 3：数据接入与清洗模块（DataEngine）

- [x] 3.1 实现行情数据适配器
  - 实现第三方行情 API 客户端（支持 1/5/15/30/60 分钟、日/周/月 K 线）
  - 实现数据解析与入库逻辑（TimescaleDB 批量写入）
  - 实现实时行情订阅（WebSocket/轮询）

- [x] 3.2 实现基本面与资金数据适配器
  - 实现财务报表、业绩预告、股东数据同步
  - 实现主力资金、北向资金、龙虎榜数据同步
  - 实现大盘指数、板块数据同步

- [x] 3.3 实现数据清洗引擎（StockFilter）
  - 实现 ST/退市/次新股/停牌/高质押/业绩暴雷过滤逻辑
  - 实现永久剔除名单管理（不可解禁）
  - 实现除权除息处理（前复权/后复权/不复权）
  - 实现缺失值线性插值补全
  - 实现异常极值检测与剔除
  - 实现因子数据归一化处理

- [x] 3.4 编写 DataEngine 属性测试
  - 属性 1：数据清洗过滤不变量测试（Hypothesis）
  - 属性 2：复权处理连续性测试（Hypothesis）
  - 属性 3：缺失值插值完整性测试（Hypothesis）
  - 属性 4：归一化范围不变量测试（Hypothesis）

- [x] 3.5 配置数据同步定时任务
  - 配置盘中实时行情同步任务（Celery）
  - 配置盘后基本面/资金数据日更任务（Celery Beat）

---

## 阶段 4：核心选股引擎（StockScreener）

- [x] 4.1 实现均线计算与趋势打分
  - 实现可配置周期的 MA 计算（默认 5/10/20/60/120 日）
  - 实现多头排列识别（短期 MA > 长期 MA 且斜率 > 0）
  - 实现趋势打分算法（0-100 分，基于排列程度、斜率、距离）
  - 实现均线支撑形态识别（回调至均线企稳反弹）

- [x] 4.2 实现技术指标计算
  - 实现 MACD 指标计算与金叉信号识别
  - 实现 BOLL 指标计算与突破信号识别
  - 实现 RSI 指标计算与强势信号识别
  - 实现 DMA 指标计算
  - 支持所有指标参数自定义配置

- [x] 4.3 实现形态突破识别
  - 实现箱体突破识别算法
  - 实现前期高点突破识别算法
  - 实现下降趋势线突破识别算法
  - 实现有效突破判定（收盘价突破 + 成交量 ≥ 近 20 日均量 1.5 倍）
  - 实现假突破撤销逻辑（突破后未站稳 1 个交易日）

- [x] 4.4 实现量价资金筛选
  - 实现换手率区间筛选（3%-15%）
  - 实现量价背离检测与过滤
  - 实现日均成交额过滤（< 5000 万自动剔除）
  - 实现主力资金净流入信号生成（≥ 1000 万且连续 2 日）
  - 实现大单成交占比信号生成（> 30%）
  - 实现板块共振筛选（板块涨幅前 30 且多头趋势）

- [x] 4.5 实现多因子策略引擎
  - 实现四类因子（技术/资金/基本面/板块）自由组合
  - 实现 AND/OR 逻辑运算
  - 实现因子权重自定义配置
  - 实现策略模板 CRUD（保存/编辑/删除/导入/导出）
  - 实现单用户最多 20 套策略的上限约束
  - 实现一键切换策略模板

- [x] 4.6 实现选股执行调度
  - 实现盘后固定选股（每日 15:30 自动执行，Celery Beat）
  - 实现盘中实时选股（9:30-15:00，每 10 秒刷新，Celery）
  - 实现选股结果生成标的池（含买入参考价、趋势强度、风险等级）
  - 实现选股结果 Excel 导出

- [x] 4.7 编写 StockScreener 属性测试
  - 属性 5：均线计算正确性测试（Hypothesis）
  - 属性 6：趋势打分范围与阈值不变量测试（Hypothesis）
  - 属性 7：技术指标信号生成正确性测试（Hypothesis）
  - 属性 8：多因子逻辑运算正确性测试（Hypothesis）
  - 属性 9：突破有效性判定测试（Hypothesis）
  - 属性 10：量价资金筛选不变量测试（Hypothesis）
  - 属性 11：资金信号生成正确性测试（Hypothesis）
  - 属性 12：选股结果字段完整性测试（Hypothesis）
  - 属性 13：策略模板数量上限与序列化 round-trip 测试（Hypothesis）

---

## 阶段 5：预警推送服务（AlertService）

- [x] 5.1 实现预警推送核心逻辑
  - 实现用户自定义预警阈值配置（趋势打分/资金流入/突破幅度）
  - 实现盘中选股条件触发时的实时预警生成
  - 实现非交易时段预警停止逻辑

- [x] 5.2 实现预警推送通道
  - 实现 WebSocket 弹窗预警推送
  - 实现站内消息通知存储与查询

- [x] 5.3 编写 AlertService 属性测试
  - 属性 14：预警触发正确性测试（Hypothesis）

---

## 阶段 6：风险控制模块（RiskController）

- [x] 6.1 实现事前风控
  - 实现大盘指数跌破 20 日均线时自动提升阈值至 90 分
  - 实现大盘指数跌破 60 日均线时暂停所有买入信号
  - 实现个股单日涨幅 > 9% 自动剔除
  - 实现个股连续 3 日累计涨幅 > 20% 自动剔除
  - 实现个股黑名单/白名单手动维护接口

- [x] 6.2 实现事中风控
  - 实现单只个股仓位上限校验（≤ 15%）
  - 实现单一板块仓位上限校验（≤ 30%）
  - 实现持仓个股跌破 20 日均线且放量下跌 > 5% 的减仓预警

- [x] 6.3 实现事后止损止盈
  - 实现固定比例止损（5%/8%/10% 三档）
  - 实现移动止损（跟踪最高价回撤 3%/5%）
  - 实现趋势止损（跌破关键均线）
  - 实现策略胜率 < 50% 或最大回撤 > 15% 的策略风险预警

- [x] 6.4 编写 RiskController 属性测试
  - 属性 15：大盘风控状态转换测试（Hypothesis）
  - 属性 16：个股风控过滤正确性测试（Hypothesis）
  - 属性 17：黑名单不变量测试（Hypothesis）
  - 属性 18：仓位限制不变量测试（Hypothesis）
  - 属性 19：止损触发正确性测试（Hypothesis）

---

## 阶段 7：策略回测与优化引擎（BacktestEngine）

- [x] 7.1 实现历史回测核心引擎
  - 实现回测参数配置（起止日期/初始资金/手续费/滑点）
  - 实现 A 股 T+1 规则约束
  - 实现 9 项绩效指标计算（年化收益/累计收益/胜率/盈亏比/最大回撤/夏普/卡玛/交易次数/持仓天数）
  - 实现收益曲线、最大回撤曲线数据生成
  - 实现持仓明细和交易流水记录
  - 实现回测结果数据导出

- [x] 7.2 实现分段回测
  - 实现牛市/熊市/震荡市市场环境识别
  - 实现按市场环境分段执行回测并分别输出绩效指标

- [x] 7.3 实现参数优化
  - 实现遍历算法（网格搜索）参数优化
  - 实现遗传算法参数优化（最大迭代次数 1000 次）
  - 实现训练集（前 70%）/ 测试集（后 30%）数据划分
  - 实现过拟合检测（测试集与训练集收益偏差 > 20% 判定过拟合）

- [x] 7.4 编写 BacktestEngine 属性测试
  - 属性 20：回测 T+1 规则不变量测试（Hypothesis）
  - 属性 21：回测绩效指标完整性测试（Hypothesis）
  - 属性 22：回测手续费计算正确性测试（Hypothesis）
  - 属性 23：数据集划分比例测试（Hypothesis）
  - 属性 24：过拟合检测正确性测试（Hypothesis）

---

## 阶段 8：交易执行与持仓管理（TradeExecutor）

- [x] 8.1 实现券商接口对接
  - 实现券商交易 API 客户端（委托/撤单/查询）
  - 实现实盘/模拟盘模式切换
  - 实现交易指令加密传输（SSL）
  - 实现非交易时段委托拒绝逻辑

- [x] 8.2 实现手动交易功能
  - 实现选股池标的一键下单（限价/市价委托）
  - 实现下单界面自动带入参考买入价/止损价/止盈价

- [x] 8.3 实现条件单功能
  - 实现突破买入条件单
  - 实现止损卖出条件单
  - 实现止盈卖出条件单
  - 实现移动止盈条件单
  - 实现条件单监控服务（实时价格监控 + 自动触发委托）

- [x] 8.4 实现持仓管理
  - 实现持仓数据实时同步（持仓股数/成本价/市值/盈亏/仓位占比）
  - 实现持仓个股趋势破位实时预警
  - 实现委托/成交/撤单记录存储与查询导出

- [x] 8.5 编写 TradeExecutor 属性测试
  - 属性 25：条件单触发正确性测试（Hypothesis）
  - 属性 26：非交易时段委托拒绝测试（Hypothesis）
  - 属性 27：持仓盈亏计算正确性测试（Hypothesis）
  - 属性 28：交易记录 round-trip 测试（Hypothesis）

---

## 阶段 9：复盘分析模块（ReviewAnalyzer）

- [x] 9.1 实现每日复盘报告生成
  - 实现收盘后自动触发复盘任务（Celery Beat）
  - 实现选股胜率、盈亏统计计算
  - 实现成功/失败交易案例分析

- [x] 9.2 实现策略绩效报表
  - 实现日/周/月策略收益报表生成
  - 实现风险指标报表生成
  - 实现多策略并排对比分析

- [x] 9.3 实现市场复盘分析
  - 实现板块轮动分析
  - 实现趋势行情分布图数据生成
  - 实现资金流向分析报告

- [x] 9.4 实现报表导出功能
  - 实现所有报表的 Excel/CSV 导出
  - 实现图表数据的 JSON 导出（供前端 ECharts 渲染）

---

## 阶段 10：系统管理模块（AdminModule）

- [x] 10.1 实现用户权限管理
  - 实现用户账号新增/删除/权限分配
  - 实现三种角色（量化交易员/系统管理员/只读观察员）权限配置
  - 实现基于角色的 API 访问控制（RBAC）中间件

- [x] 10.2 实现系统监控与告警
  - 实现数据接口连接状态实时监控
  - 实现系统各模块运行状态监控
  - 实现异常自动触发告警通知

- [x] 10.3 实现数据管理功能
  - 实现数据备份与恢复功能
  - 实现策略模板统一管理
  - 实现系统参数配置管理

- [x] 10.4 实现全流程日志记录
  - 实现操作日志记录（操作人/时间/类型/对象）
  - 实现日志保留策略（≥ 1 年）
  - 实现日志查询接口

- [x] 10.5 编写 AdminModule 属性测试
  - 属性 29：角色权限不变量测试（Hypothesis）
  - 属性 30：操作日志 round-trip 测试（Hypothesis）
  - 属性 31：数据备份恢复 round-trip 测试（Hypothesis）

---

## 阶段 11：安全性实现

- [x] 11.1 实现传输安全
  - 配置 Nginx SSL/TLS 证书
  - 确保所有 API 端点强制 HTTPS

- [x] 11.2 实现存储安全
  - 实现用户策略数据和交易数据加密存储（AES-256）
  - 实现密码哈希存储（bcrypt）

- [x] 11.3 实现访问安全
  - 实现 JWT 身份认证
  - 实现核心交易操作二次身份验证（TOTP/短信验证码）
  - 实现 API 请求频率限制（防暴力破解）

---

## 阶段 12：前端界面开发

- [x] 12.1 实现数据展示页面
  - 实现 K 线图组件（ECharts）
  - 实现行情数据实时刷新（WebSocket）
  - 实现板块/个股数据展示

- [x] 12.2 实现选股功能页面
  - 实现策略配置界面（因子组合/权重/参数）
  - 实现选股结果标的池展示
  - 实现实时预警弹窗组件
  - 实现选股结果 Excel 导出按钮

- [x] 12.3 实现风控配置页面
  - 实现止损止盈参数配置界面
  - 实现黑白名单管理界面
  - 实现仓位限制配置界面

- [x] 12.4 实现回测功能页面
  - 实现回测参数配置表单
  - 实现收益曲线/最大回撤图表（ECharts）
  - 实现绩效指标展示卡片
  - 实现参数优化结果展示

- [x] 12.5 实现交易功能页面
  - 实现一键下单界面
  - 实现条件单配置界面
  - 实现持仓管理表格（实时盈亏）
  - 实现交易流水查询界面

- [x] 12.6 实现复盘分析页面
  - 实现每日复盘报告展示
  - 实现策略绩效图表（柱状图/折线图/饼图）
  - 实现多策略对比分析界面

- [x] 12.7 实现系统管理页面
  - 实现用户管理界面（仅管理员可见）
  - 实现系统监控状态面板
  - 实现日志查询界面

---

## 阶段 13：API 接口层

- [x] 13.1 实现数据查询 API
  - `GET /api/v1/kline/{symbol}` - 查询 K 线数据
  - `GET /api/v1/stocks` - 查询股票列表（含过滤）
  - `GET /api/v1/market/overview` - 查询大盘概况

- [x] 13.2 实现选股 API
  - `POST /api/v1/screen/run` - 执行选股
  - `GET /api/v1/screen/results` - 查询选股结果
  - `CRUD /api/v1/strategies` - 策略模板管理
  - `GET /api/v1/screen/export` - 导出选股结果

- [x] 13.3 实现风控 API
  - `POST /api/v1/risk/check` - 风控校验
  - `CRUD /api/v1/blacklist` - 黑名单管理
  - `CRUD /api/v1/whitelist` - 白名单管理
  - `GET /api/v1/risk/strategy-health` - 策略健康状态

- [x] 13.4 实现回测 API
  - `POST /api/v1/backtest/run` - 启动回测
  - `GET /api/v1/backtest/{id}/result` - 查询回测结果
  - `POST /api/v1/backtest/optimize` - 启动参数优化

- [x] 13.5 实现交易 API
  - `POST /api/v1/trade/order` - 提交委托
  - `DELETE /api/v1/trade/order/{id}` - 撤单
  - `GET /api/v1/trade/positions` - 查询持仓
  - `GET /api/v1/trade/orders` - 查询委托/成交记录
  - `CRUD /api/v1/trade/conditions` - 条件单管理

- [x] 13.6 实现复盘与管理 API
  - `GET /api/v1/review/daily` - 每日复盘报告
  - `GET /api/v1/review/strategy-report` - 策略绩效报表
  - `CRUD /api/v1/admin/users` - 用户管理
  - `GET /api/v1/admin/system-health` - 系统健康状态
  - `GET /api/v1/admin/logs` - 日志查询

---

## 阶段 14：集成测试与性能测试

- [x] 14.1 编写全链路集成测试
  - 数据接入 → 清洗 → 选股 → 风控 → 预警全链路测试
  - 选股 → 下单 → 持仓同步 → 止损触发全链路测试
  - 回测 → 参数优化 → 过拟合检测全链路测试

- [x] 14.2 编写性能测试（Locust）
  - 模拟 50 并发用户，验证盘后选股 ≤ 3 秒
  - 验证实时选股刷新 ≤ 1 秒
  - 验证页面操作响应 ≤ 500ms

- [x] 14.3 编写安全测试
  - 验证角色权限隔离（越权访问应返回 403）
  - 验证二次验证拦截（未验证的核心操作应被拒绝）
  - 验证非交易时段委托拒绝

---

## 阶段 15：部署与运维

- [x] 15.1 编写 Docker Compose 部署配置
  - 配置 FastAPI 应用容器
  - 配置 TimescaleDB、PostgreSQL、Redis 容器
  - 配置 Celery Worker 和 Celery Beat 容器
  - 配置 Nginx 反向代理容器

- [x] 15.2 配置系统监控
  - 配置应用健康检查端点
  - 配置数据库连接池监控
  - 配置 Celery 任务队列监控

- [x] 15.3 编写部署文档
  - Windows/Linux 服务器部署步骤
  - 环境变量配置说明
  - 数据库初始化步骤


---

## 阶段 16：前端登录与交互界面完整实现（需求 21）

- [x] 16.1 实现后端认证 API 端点
  - 实现 `POST /api/v1/auth/login` 登录接口（返回 access_token 和用户信息）
  - 实现 `POST /api/v1/auth/register` 注册接口（用户名唯一性校验 + 密码强度校验）
  - 实现 `GET /api/v1/auth/check-username` 用户名唯一性实时校验接口
  - 实现 `GET /api/v1/auth/me` 获取当前用户信息接口
  - _需求：21.1, 21.2, 21.3_

- [x] 16.2 实现登录页面（LoginView）
  - 实现用户名密码登录表单，调用 `POST /api/v1/auth/login`
  - 登录成功后存储 token 至 localStorage，跳转至系统主页面
  - 登录失败时在表单下方显示明确错误提示信息（如"用户名或密码错误"）
  - 清空密码输入框（登录失败时）
  - _需求：21.1_

- [x] 16.3 实现注册页面（RegisterView）
  - 创建 `RegisterView.vue` 页面组件
  - 实现用户名输入时实时调用 `GET /api/v1/auth/check-username` 校验唯一性
  - 实现密码强度实时校验并显示校验结果（✓/✗ 标记：≥8位、大写字母、小写字母、数字）
  - 提交调用 `POST /api/v1/auth/register`，成功后跳转至登录页
  - 在路由中注册 `/register` 路径（无需认证）
  - _需求：21.2_

- [x] 16.4 完善路由守卫与 Token 过期处理
  - 完善路由守卫：未持有有效 token 或 token 过期时自动重定向至登录页
  - 确保 Axios 拦截器在 401 响应时清除 token 并跳转登录页
  - 确保未认证用户无法访问任何功能页面
  - _需求：21.3_

- [x] 16.5 重构主布局框架（MainLayout）
  - 实现顶部导航栏：显示系统名称、预警通知铃铛（含未读数 badge）、用户信息和退出按钮
  - 重构侧边菜单栏：按功能模块分组（数据、选股、风控、交易、分析、系统）展示菜单项
  - 根据当前用户角色动态过滤菜单项（READONLY 不显示交易/持仓，TRADER 不显示系统管理）
  - 预警通知铃铛点击展开通知面板，显示最近预警列表
  - 主内容区域通过 `<router-view />` 渲染子路由页面
  - _需求：21.4, 21.14_

- [x] 16.6 实现数据管理页面（DataManageView）
  - 创建 `DataManageView.vue` 页面组件
  - 展示各数据源同步状态表格（行情、基本面、资金流向，含最后同步时间和状态）
  - 实现手动触发数据同步按钮（调用 `POST /api/v1/data/sync`）
  - 展示数据清洗结果统计和永久剔除名单列表
  - 在路由中注册 `/data` 路径
  - _需求：21.5_

- [x] 16.7 补充选股策略页面基础功能（ScreenerView）
  - 实现策略模板导入功能（上传 JSON 文件解析并保存）
  - 实现策略模板导出功能（下载 JSON 文件）
  - 实现策略删除确认对话框
  - 实现因子条件组合可视化编辑器（支持 AND/OR 逻辑切换、权重调整）
  - 实现一键执行选股后自动跳转至选股结果页面
  - _需求：21.6_

- [x] 16.8 完善选股结果页面（ScreenerResultsView）
  - 实现表格展示选股结果：股票代码、名称、买入参考价、趋势强度评分、风险等级、触发信号
  - 支持按趋势评分、风险等级排序
  - 实现导出为 Excel 文件按钮
  - 点击行可展开信号详情
  - _需求：21.7_

- [x] 16.9 完善风险控制页面（RiskView）
  - 实现大盘风控状态卡片（显示指数与均线关系、当前阈值、风控级别）
  - 实现止损止盈参数配置表单
  - 实现黑名单/白名单管理（增删查）
  - 实现仓位风控预警信息列表
  - _需求：21.16_

- [x] 16.10 完善回测分析页面（BacktestView）
  - 实现回测参数配置表单（起止日期选择器、初始资金、手续费率、滑点输入）
  - 实现执行回测按钮，运行中显示进度状态
  - 实现 ECharts 图表展示收益曲线和最大回撤曲线
  - 实现 9 项绩效指标卡片展示
  - 实现交易流水明细表格
  - _需求：21.17_

- [x] 16.11 完善交易执行页面（TradeView）
  - 实现选股池标的列表，点击快速填充下单表单（自动带入参考买入价、止损价、止盈价）
  - 实现限价委托/市价委托下单表单
  - 实现条件单配置面板（突破买入/止损卖出/止盈卖出/移动止盈）
  - 实现实盘/模拟盘模式切换开关
  - 实现委托记录和成交记录查询表格
  - _需求：21.18_

- [x] 16.12 完善持仓管理页面（PositionsView）
  - 实现实时持仓表格（持仓股数、成本价、当前市值、盈亏金额、盈亏比例、仓位占比）
  - 通过 WebSocket 实时更新当前价格和盈亏数据
  - 实现持仓破位预警信息高亮显示
  - 实现仓位占比饼图（ECharts）
  - _需求：21.19_

- [x] 16.13 完善复盘分析页面（ReviewView）
  - 实现日度/周度/月度报告切换标签
  - 实现策略收益柱状图、折线图（ECharts）
  - 实现风险指标饼图
  - 实现多策略对比分析（选择多个策略并排展示）
  - 实现报表导出按钮
  - _需求：21.20_

- [x] 16.14 完善系统管理页面（AdminView）
  - 实现用户账号管理表格（新增、删除、角色分配）
  - 实现操作日志查询（按时间范围、操作类型筛选）
  - 实现系统运行状态监控面板
  - 实现数据备份与恢复操作按钮
  - _需求：21.21_

- [x] 16.15 实现预警通知组件（AlertNotification）
  - 创建 `AlertNotification.vue` 全局通知组件
  - WebSocket 收到预警消息后在页面右上角弹出通知卡片
  - 卡片显示预警类型图标、股票代码、触发原因
  - 卡片自动 5 秒后消失，支持手动关闭
  - 点击卡片跳转至对应详情页面
  - 在 MainLayout 中集成通知组件
  - _需求：21.24_

- [x] 16.16 实现 WebSocket 客户端管理
  - 创建 `WsClient` 类（连接、断开、消息处理、自动重连）
  - 实现指数退避重连策略（1s → 2s → 4s → 8s → 最大 30s）
  - 用户登录成功后自动建立 WebSocket 连接，退出时断开
  - 收到 `alert` 消息时触发 AlertStore 和通知弹窗
  - 收到 `position_update` 消息时更新持仓 Store
  - 完善 AlertStore：补充 `type`、`link_to` 字段支持
  - _需求：21.16_

- [x] 16.17 实现全局加载状态与错误处理
  - 实现通用 `PageState<T>` 状态管理模式（loading / error / data）
  - 实现 `LoadingSpinner` 组件，所有数据加载过程中显示
  - 实现 `ErrorBanner` 组件（显示错误信息 + 重试按钮）
  - 网络断开时显示全局离线提示条
  - _需求：21.25_

- [x] 16.18 实现角色权限动态渲染
  - 只读观察员不显示交易相关操作按钮（下单、条件单等）
  - 量化交易员不显示系统管理菜单入口
  - 路由级别角色校验（已有基础，确保覆盖所有路由）
  - 页面内操作按钮级别角色校验
  - _需求：21.22_

- [x] 16.19 实现响应式布局
  - 确保最小支持分辨率 1280px 宽度下所有功能正常显示
  - 侧边菜单固定宽度 200px，主内容区域自适应剩余宽度
  - 数据表格内容溢出时启用水平滚动
  - 卡片网格使用 CSS Grid `repeat(auto-fill, minmax(280px, 1fr))` 自适应列数
  - 图表组件监听容器 resize 事件自动调整尺寸
  - _需求：21.23_

- [x] 16.20 检查点 - 确保所有页面功能正常
  - 确保所有页面可正常渲染，路由跳转无误，角色权限过滤正确，ask the user if questions arise.

- [x] 16.21 编写前端属性测试（Vitest + fast-check）
  - [x] 16.21.1 编写属性 32 测试：登录响应正确性
    - **属性 32：登录响应正确性**
    - 验证有效凭证返回 token 和用户对象，无效凭证返回错误且不返回 token
    - **验证需求：21.1**

  - [x] 16.21.2 编写属性 33 测试：注册校验正确性
    - **属性 33：注册校验正确性**
    - 验证用户名重复拒绝、密码强度不足拒绝、仅当用户名唯一且密码满足全部强度要求时注册成功
    - **验证需求：21.2**

  - [x] 16.21.3 编写属性 34 测试：路由守卫认证拦截
    - **属性 34：路由守卫认证拦截**
    - 验证未持有有效 token 或 token 过期时重定向至登录页
    - **验证需求：21.3**

  - [x] 16.21.4 编写属性 35 测试：前端数据渲染字段完整性
    - **属性 35：前端数据渲染字段完整性**
    - 验证选股结果项和持仓项渲染后所有必要字段均不为空
    - **验证需求：21.7, 21.19**

  - [x] 16.21.5 编写属性 36 测试：角色菜单动态渲染正确性
    - **属性 36：角色菜单动态渲染正确性**
    - 验证 READONLY 不含交易/持仓菜单，TRADER 不含系统管理菜单，ADMIN 包含全部菜单
    - **验证需求：21.22**

  - [x] 16.21.6 编写属性 37 测试：预警通知渲染完整性
    - **属性 37：预警通知渲染完整性**
    - 验证通知卡片包含预警类型、股票代码、触发原因且均不为空，携带正确跳转链接
    - **验证需求：21.24**

  - [x] 16.21.7 编写属性 38 测试：API 错误状态管理正确性
    - **属性 38：API 错误状态管理正确性**
    - 验证失败请求后 loading→error 状态转换、error 包含非空提示、重试后重新进入 loading
    - **验证需求：21.25**

- [x] 16.22 编写前端集成测试
  - [x] 16.22.1 登录 → 路由守卫 → 角色菜单渲染 → 页面访问全链路测试
  - [x] 16.22.2 WebSocket 连接 → 预警推送 → 通知弹窗 → 跳转详情全链路测试

- [x] 16.23 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

---

## 阶段 17：选股策略参数面板增强与信号分类展示（需求 21.8–21.15）

- [x] 17.1 扩展后端策略配置数据结构
  - 在 `app/core/schemas.py` 中新增 `MaTrendConfig`、`IndicatorParamsConfig`、`BreakoutConfig`、`VolumePriceConfig` 数据类
  - 扩展 `StrategyConfig` 数据类，新增 `ma_trend`、`indicator_params`（替换原 dict）、`breakout`、`volume_price` 字段
  - 确保 `strategy_template.config` JSONB 字段兼容新结构（向后兼容旧配置）
  - _需求：21.8, 21.9, 21.10, 21.11_

- [x] 17.2 扩展后端选股结果信号分类
  - 在 `app/core/schemas.py` 中新增 `SignalCategory` 枚举（MA_TREND / MACD / BOLL / RSI / DMA / BREAKOUT / CAPITAL_INFLOW / LARGE_ORDER / MA_SUPPORT / SECTOR_STRONG）
  - 新增 `SignalDetail` 数据类（category、label、is_fake_breakout）
  - 更新 `ScreenItem` 数据类：`signals` 字段改为 `list[SignalDetail]`，新增 `has_fake_breakout` 字段
  - 更新选股引擎各子模块，在生成信号时填充 `SignalDetail.category` 分类标签
  - _需求：21.15_

- [x] 17.3 实现盘后选股调度状态 API
  - 实现 `GET /api/v1/screen/schedule` 接口，返回 `EodScheduleStatus`（next_run_at、last_run_at、last_run_duration_ms、last_run_result_count）
  - 从 Celery Beat 调度配置和 Redis 缓存中读取调度状态数据
  - _需求：21.14_

- [x] 17.4 实现均线趋势参数配置面板（ScreenerView）
  - 在 ScreenerView 中新增"均线趋势配置"折叠面板区块
  - 实现均线周期组合多选标签输入（支持添加/删除自定义周期值，默认预填 5/10/20/60/120）
  - 实现多头排列斜率阈值数值输入框（步长 0.01，默认 0）
  - 实现趋势打分阈值滑块控件（0-100，默认 80，实时显示当前值）
  - 实现均线支撑回调均线复选框组（20 日 / 60 日，默认全选）
  - 将配置数据绑定至 `config.ma_trend` 并纳入 `buildStrategyConfig()` 输出
  - _需求：21.8_

- [x] 17.5 实现技术指标参数配置面板（ScreenerView）
  - 在 ScreenerView 中新增"技术指标配置"折叠面板区块，按指标分组（Accordion）
  - MACD 面板：快线周期（默认 12）、慢线周期（默认 26）、信号线周期（默认 9）三个数值输入框
  - BOLL 面板：周期（默认 20）和标准差倍数（默认 2）两个数值输入框
  - RSI 面板：周期（默认 14）+ 强势区间双端滑块（下限默认 50 / 上限默认 80）
  - DMA 面板：短期周期（默认 10）和长期周期（默认 50）两个数值输入框
  - 每个参数旁显示默认值提示，支持一键恢复默认值按钮
  - 将配置数据绑定至 `config.indicator_params` 并纳入 `buildStrategyConfig()` 输出
  - _需求：21.9_

- [x] 17.6 实现形态突破配置面板（ScreenerView）
  - 在 ScreenerView 中新增"形态突破配置"折叠面板区块
  - 实现三种突破形态开关复选框（箱体突破 / 前期高点突破 / 下降趋势线突破，默认全部启用）
  - 实现量比倍数阈值数值输入框（步长 0.1，默认 1.5，标注"倍近 20 日均量"）
  - 实现站稳确认天数数值输入框（步长 1，最小值 1，默认 1）
  - 将配置数据绑定至 `config.breakout` 并纳入 `buildStrategyConfig()` 输出
  - _需求：21.10_

- [x] 17.7 实现量价资金筛选配置面板（ScreenerView）
  - 在 ScreenerView 中新增"量价资金筛选"折叠面板区块
  - 实现换手率区间双端滑块或两个数值输入框（下限默认 3% / 上限默认 15%）
  - 实现主力资金净流入阈值数值输入框（单位万元，默认 1000）
  - 实现连续净流入天数数值输入框（步长 1，默认 2）
  - 实现大单成交占比阈值数值输入框（单位 %，默认 30）
  - 实现日均成交额下限数值输入框（单位万元，默认 5000）
  - 实现板块涨幅排名范围数值输入框（默认前 30）
  - 将配置数据绑定至 `config.volume_price` 并纳入 `buildStrategyConfig()` 输出
  - _需求：21.11_

- [x] 17.8 实现策略数量上限前端校验（ScreenerView）
  - 页面加载策略列表后检查当前策略数量是否达到 20 套上限
  - 达到上限时：新建策略按钮置灰（disabled），按钮旁显示"已达策略上限（20 套）"提示文字
  - 导入策略时同样校验上限，达到上限时拒绝导入并提示
  - _需求：21.12_

- [x] 17.9 实现实时选股开关与状态（ScreenerView）
  - 在执行选股区块中新增实时选股 Toggle Switch 控件（默认关闭）
  - 实现交易时段判断逻辑（9:30-15:00 CST）
  - 开启且在交易时段内：启动 10 秒定时器自动调用 `POST /api/v1/screen/run`（screen_type: REALTIME），页面显示倒计时和最近刷新时间
  - 非交易时段：开关自动禁用，显示"非交易时段"灰色状态提示
  - 关闭开关时清除定时器停止自动刷新
  - 组件卸载时清除定时器
  - _需求：21.13_

- [x] 17.10 实现盘后自动选股调度状态展示（ScreenerView）
  - 在选股策略页面新增盘后选股调度信息卡片
  - 调用 `GET /api/v1/screen/schedule` 获取调度状态数据
  - 显示下一次盘后选股的预计执行时间（每个交易日 15:30）
  - 显示最近一次盘后选股的执行时间、耗时和选出股票数量
  - _需求：21.14_

- [x] 17.11 实现选股结果信号分类展示（ScreenerResultsView）
  - 更新 `ScreenResultRow` 类型：`signals` 改为 `SignalDetail[]` 结构，新增 `has_fake_breakout` 字段
  - 展开详情行中按信号类型分类展示，每种类型使用不同颜色标签：
    - 均线趋势信号（蓝色）、MACD（青色）、BOLL（青色）、RSI（青色）、DMA（青色）
    - 形态突破信号（绿色）、资金流入信号（橙色）、大单活跃信号（黄色）
    - 均线支撑信号（紫色）、板块强势信号（品红色）
  - 假突破标记：当信号中存在 `is_fake_breakout: true` 时，在该信号标签旁以红色醒目样式标注"假突破"警告标签
  - 主行触发信号列显示信号数量和类型摘要（如"3 个信号：均线趋势 / MACD / 资金流入"）
  - _需求：21.15_

- [x] 17.12 编写选股增强功能属性测试（Vitest + fast-check）
  - [x] 17.12.1 编写属性 39 测试：均线趋势参数配置面板完整性
    - **属性 39：均线趋势参数配置面板完整性**
    - 验证面板支持均线周期组合、斜率阈值、打分阈值、支撑均线配置，保存后再加载参数一致
    - **验证需求：21.8**

  - [x] 17.12.2 编写属性 40 测试：技术指标参数配置面板完整性
    - **属性 40：技术指标参数配置面板完整性**
    - 验证 MACD/BOLL/RSI/DMA 各指标参数有默认值，保存后再加载参数一致
    - **验证需求：21.9**

  - [x] 17.12.3 编写属性 41 测试：形态突破配置面板完整性
    - **属性 41：形态突破配置面板完整性**
    - 验证三种突破形态独立启用/禁用，量比阈值和站稳天数配置，保存后再加载参数一致
    - **验证需求：21.10**

  - [x] 17.12.4 编写属性 42 测试：量价资金筛选配置面板完整性
    - **属性 42：量价资金筛选配置面板完整性**
    - 验证换手率区间、资金阈值、大单占比、成交额下限、板块排名配置，保存后再加载参数一致
    - **验证需求：21.11**

  - [x] 17.12.5 编写属性 43 测试：策略数量上限前端校验
    - **属性 43：策略数量上限前端校验**
    - 验证策略数量达到 20 套时新建按钮禁用且显示上限提示，小于 20 时按钮可用
    - **验证需求：21.12**

  - [x] 17.12.6 编写属性 44 测试：实时选股开关交易时段联动
    - **属性 44：实时选股开关交易时段联动**
    - 验证交易时段内开启后每 10 秒刷新并显示倒计时，非交易时段自动禁用并显示提示
    - **验证需求：21.13**

  - [x] 17.12.7 编写属性 45 测试：选股结果信号分类展示正确性
    - **属性 45：选股结果信号分类展示正确性**
    - 验证信号按类型分类展示，假突破标记以红色醒目样式标注
    - **验证需求：21.15**

- [x] 17.13 编写选股增强集成测试
  - [x] 17.13.1 选股策略配置（均线/指标/突破/量价面板）→ 保存策略 → 执行选股 → 结果信号分类展示全链路测试
  - [x] 17.13.2 实时选股开关开启 → 交易时段自动刷新 → 非交易时段自动禁用全链路测试

- [x] 17.14 检查点 - 确保阶段 17 所有功能和测试通过
  - 确保所有新增参数面板正常渲染和交互
  - 确保策略配置保存/加载包含所有新增子配置
  - 确保选股结果信号分类展示和假突破标记正常
  - 确保所有新增属性测试和集成测试通过

---

## 阶段 18：策略模板编辑与激活交互完善（需求 22）

- [x] 18.1 实现策略选中后配置回显（ScreenerView）
  - 重构 `selectStrategy()` 函数：选中策略时调用 `GET /api/v1/strategies/{id}` 获取完整配置
  - 将返回的 `config` 解析并回填至因子条件编辑器（`config.logic`、`config.factors`、权重）
  - 回填均线趋势配置面板（`maTrend` reactive 对象）
  - 回填技术指标配置面板（`indicatorParams` reactive 对象，含 MACD/BOLL/RSI/DMA）
  - 回填形态突破配置面板（`breakoutConfig` reactive 对象）
  - 回填量价资金筛选配置面板（`volumePriceConfig` reactive 对象）
  - 取消选中时恢复所有面板为默认值
  - _需求：22.1_

- [x] 18.2 实现策略激活切换（ScreenerView）
  - 选中策略时调用 `POST /api/v1/strategies/{id}/activate` 将该策略设为服务端活跃策略
  - 激活成功后刷新策略列表以更新各策略的 `is_active` 状态显示
  - 页面加载时（`onMounted`）从策略列表中识别 `is_active=true` 的策略并自动选中和回显其配置
  - _需求：22.3_

- [x] 18.3 实现策略保存修改功能（ScreenerView）
  - 在因子编辑器区块底部新增"💾 保存修改"按钮，仅当有策略选中时显示
  - 点击"保存修改"时调用 `PUT /api/v1/strategies/{activeStrategyId}` 提交 `{ config: buildStrategyConfig() }`
  - 保存成功后刷新策略列表并显示成功提示（如短暂的绿色提示文字）
  - 保存失败时在 `pageError` 中显示错误信息
  - _需求：22.2_

- [x] 18.4 实现策略重命名功能（ScreenerView）
  - 在策略列表每项的操作按钮区域新增"✏️ 重命名"按钮
  - 点击后弹出重命名对话框（复用现有 dialog 样式），预填当前策略名称
  - 确认后调用 `PUT /api/v1/strategies/{id}` 提交 `{ name: newName }`
  - 更新成功后刷新策略列表
  - _需求：22.5_

- [x] 18.5 实现导入策略前端上限校验（ScreenerView）
  - 在 `onImportFile()` 函数中，解析 JSON 文件前先检查 `strategies.value.length >= MAX_STRATEGIES`
  - 达到上限时设置 `pageError.value = '已达策略上限（20 套），请删除旧策略后再导入'` 并 return
  - 重置 file input 以允许用户删除策略后重新导入
  - _需求：22.4_

- [x] 18.6 编写策略编辑与激活属性测试（Vitest + fast-check）
  - [x] 18.6.1 编写属性 46 测试：策略配置回显 round-trip 正确性
    - **属性 46：策略配置回显 round-trip 正确性**
    - 验证任意策略配置保存后再选中加载，各面板回显参数与保存时完全一致
    - **验证需求：22.1, 22.2**

  - [x] 18.6.2 编写属性 47 测试：策略激活状态服务端同步正确性
    - **属性 47：策略激活状态服务端同步正确性**
    - 验证选中策略后服务端 is_active 状态正确，刷新页面后活跃策略与服务端一致
    - **验证需求：22.3**

  - [x] 18.6.3 编写属性 48 测试：导入策略前端上限校验正确性
    - **属性 48：导入策略前端上限校验正确性**
    - 验证策略数量达到 20 套时导入被前端拦截并显示上限提示，不发起后端请求
    - **验证需求：22.4**

- [x] 18.7 编写策略编辑与激活集成测试
  - [x] 18.7.1 选中策略 → 配置回显 → 修改参数 → 保存修改 → 重新选中验证回显一致性全链路测试
  - [x] 18.7.2 选中策略 A → 切换选中策略 B → 验证激活状态切换 → 刷新页面验证持久化全链路测试

- [x] 18.8 检查点 - 确保阶段 18 所有功能和测试通过
  - 确保选中策略后各配置面板正确回显参数
  - 确保保存修改功能调用 `PUT /strategies/{id}` 并正确更新
  - 确保策略激活调用 `POST /strategies/{id}/activate` 并同步服务端状态
  - 确保重命名功能正常工作
  - 确保导入策略前端上限校验生效
  - 确保所有新增属性测试和集成测试通过

---

## 阶段 19：因子条件编辑器交互优化与配置数据源统一（需求 23）

- [x] 19.1 消除配置参数双数据源问题
  - 移除因子编辑器区块中独立的"趋势打分阈值"数值输入框（`config.trendThreshold`），统一使用均线趋势配置面板的滑块（`maTrend.trend_score_threshold`）
  - 移除因子编辑器区块中独立的"均线周期"文本输入框（`config.maPeriods`），`buildStrategyConfig()` 的 `ma_periods` 改为直接读取 `maTrend.ma_periods`
  - 从 `config` reactive 对象中移除 `trendThreshold` 和 `maPeriods` 字段
  - 更新 `resetToDefaults()` 移除对已删除字段的重置
  - _需求：23.6_

- [x] 19.2 实现因子名称枚举下拉选择
  - 定义 `factorNameOptions` 常量：按四类因子类型（技术面/资金面/基本面/板块面）分组，每类包含预定义的因子名称枚举（value + 中文 label）
  - 将因子名称输入控件从 `<input>` 改为 `<select>`，选项根据当前因子类型动态过滤
  - 切换因子类型时自动重置因子名称为该类型的第一个选项（`@change` 事件处理）
  - 更新 `addFactor()` 函数：新增因子时默认选中对应类型的第一个因子名称
  - _需求：23.1, 23.2, 23.3, 23.4_

- [x] 19.3 实现因子类型持久化与向后兼容
  - 修改 `buildStrategyConfig()`：保存时保留因子的 `type` 字段（不再剥离）
  - 实现 `inferFactorType(name)` 辅助函数：遍历 `factorNameOptions` 根据因子名称反查所属类型
  - 修改 `selectStrategy()` 回填逻辑：优先使用存储的 `type` 字段，缺失时调用 `inferFactorType()` 推断
  - _需求：23.5_

- [x] 19.4 修复后端策略 API 兼容性问题
  - 将 `IndicatorParamsConfigIn` 从扁平结构改为嵌套子模型结构（`MacdParamsIn`/`BollParamsIn`/`RsiParamsIn`/`DmaParamsIn`），匹配前端发送的 JSON 格式
  - 策略 CRUD 端点改为内存存储（`_strategies` dict），使创建的策略能被列表和详情接口正确返回
  - _需求：23（后端支撑）_

- [x] 19.5 编写智能选股页面多模板参数可调性集成测试
  - 创建三种不同风格的策略模板（均线趋势型、量价突破型、保守防御型）并验证服务端存储
  - 验证均线趋势配置面板所有参数可调（周期组合、斜率阈值、打分阈值、支撑均线）
  - 验证技术指标配置面板所有参数可调（MACD/BOLL/RSI/DMA 各参数）
  - 验证形态突破配置面板所有参数可调（三种形态开关、量比阈值、确认天数）
  - 验证量价资金筛选配置面板所有参数可调（换手率区间、资金阈值、大单占比、成交额、板块排名）
  - 验证因子条件编辑器参数可调（AND/OR 逻辑、因子增删、权重调整、运算符和阈值）
  - 验证策略切换时参数正确回显、修改后持久化
  - 验证策略管理操作（重命名、删除、激活切换）
  - 全链路测试：创建 → 配置 → 保存 → 切换 → 验证回显
  - _需求：23_

---

## 阶段 20：Tushare/AkShare 双数据源接入与故障转移（需求 1.7–1.11）

- [x] 20.1 扩展 `app/core/config.py` 新增数据源配置字段
  - 新增 `tushare_api_token: str = ""`（Tushare API Token）
  - 新增 `tushare_api_url: str = "http://api.tushare.pro"`（Tushare API 地址）
  - 新增 `akshare_request_timeout: float = 30.0`（AkShare 请求超时时间）
  - 新增 `akshare_max_retries: int = 3`（AkShare 最大重试次数）
  - 更新 `.env.example` 添加对应环境变量注释和默认值
  - _需求：1.7, 1.8_

- [x] 20.2 实现 `BaseDataSourceAdapter` 抽象基类
  - [x] 20.2.1 创建 `app/services/data_engine/base_adapter.py`
    - 定义 `BaseDataSourceAdapter(ABC)` 抽象类
    - 声明抽象方法：`fetch_kline`、`fetch_fundamentals`、`fetch_money_flow`、`fetch_market_overview`、`health_check`
    - 定义 `DataSourceUnavailableError` 异常类
    - _需求：1.1, 1.9_

- [x] 20.3 实现 `TushareAdapter` 主数据源适配器
  - [x] 20.3.1 创建 `app/services/data_engine/tushare_adapter.py`
    - 继承 `BaseDataSourceAdapter`
    - 从 `settings.tushare_api_token` 和 `settings.tushare_api_url` 读取配置（不硬编码）
    - 实现 `_call_api()` 方法通过 HTTP POST + Token 认证调用 Tushare API
    - 实现 `fetch_kline()`：调用 Tushare `daily` 接口获取 K 线数据
    - 实现 `fetch_fundamentals()`：调用 Tushare `fina_indicator` 接口获取财务数据
    - 实现 `fetch_money_flow()`：调用 Tushare `moneyflow` 接口获取资金流向
    - 实现 `fetch_market_overview()`：调用 Tushare `index_daily` 接口获取大盘数据
    - 实现 `health_check()`：调用 Tushare `trade_cal` 接口验证连通性
    - _需求：1.1, 1.3, 1.4, 1.7_

- [x] 20.4 实现 `AkShareAdapter` 备用数据源适配器
  - [x] 20.4.1 创建 `app/services/data_engine/akshare_adapter.py`
    - 继承 `BaseDataSourceAdapter`
    - 从 `settings.akshare_request_timeout` 读取超时配置（不硬编码）
    - 通过 `asyncio.to_thread()` 在线程池中执行同步 akshare SDK 调用
    - 实现 `fetch_kline()`：调用 `ak.stock_zh_a_hist()` 获取 K 线数据
    - 实现 `fetch_fundamentals()`：调用 `ak.stock_financial_analysis_indicator()` 获取财务数据
    - 实现 `fetch_money_flow()`：调用 `ak.stock_individual_fund_flow()` 获取资金流向
    - 实现 `fetch_market_overview()`：调用 `ak.stock_zh_index_daily()` 获取大盘数据
    - 实现 `health_check()`：调用 `ak.stock_zh_a_spot_em()` 验证连通性
    - _需求：1.1, 1.4, 1.5, 1.8_

- [x] 20.5 实现 `TushareFormatConverter` 和 `AkShareFormatConverter` 格式转换器
  - [x] 20.5.1 创建 `app/services/data_engine/format_converter.py`
    - 实现 `TushareFormatConverter` 类：将 Tushare 返回的 dict（fields + items）映射为 `KlineBar`、`FundamentalsData`、`MoneyFlowData`、`MarketOverview`
    - 实现 `AkShareFormatConverter` 类：将 AkShare 返回的 pandas DataFrame（中文列名）映射为 `KlineBar`、`FundamentalsData`、`MoneyFlowData`、`MarketOverview`
    - 确保两个转换器输出的 `KlineBar` 结构完全一致（统一字段名、数据类型、单位）
    - _需求：1.11_

- [x] 20.6 实现 `DataSourceRouter` 数据源路由与故障转移管理器
  - [x] 20.6.1 创建 `app/services/data_engine/data_source_router.py`
    - 实现 `DataSourceRouter` 类，注入 `TushareAdapter`（主）和 `AkShareAdapter`（备）
    - 实现 `fetch_with_fallback()` 核心方法：优先调用 Tushare，失败时自动切换 AkShare
    - Tushare 失败时记录 warning 日志并切换
    - 两个数据源均失败时：记录 error 日志、推送 DANGER 级别告警通知、抛出 `DataSourceUnavailableError`
    - 实现 `fetch_kline()`、`fetch_fundamentals()`、`fetch_money_flow()`、`fetch_market_overview()` 代理方法
    - _需求：1.9, 1.10_

- [x] 20.7 检查点 - 确保核心组件实现完整
  - 确保所有新增模块可正常导入，无语法错误
  - 确保 `DataSourceRouter` 故障转移逻辑正确
  - 确保所有测试通过，ask the user if questions arise.

- [x] 20.8 重构现有 DataEngine 集成 DataSourceRouter
  - [x] 20.8.1 更新 `app/services/data_engine/__init__.py`
    - 导出新增模块：`BaseDataSourceAdapter`、`TushareAdapter`、`AkShareAdapter`、`DataSourceRouter`、`TushareFormatConverter`、`AkShareFormatConverter`、`DataSourceUnavailableError`
    - _需求：1.1_

  - [x] 20.8.2 更新数据同步任务使用 DataSourceRouter
    - 修改 `app/tasks/data_sync.py` 中的数据同步任务，通过 `DataSourceRouter` 获取数据（替代直接调用 `MarketDataClient`）
    - 确保故障转移逻辑在定时任务中生效
    - _需求：1.9, 1.10_

- [x] 20.9 更新 `.env.example` 新增数据源配置说明
  - 添加 `TUSHARE_API_TOKEN`、`TUSHARE_API_URL`、`AKSHARE_REQUEST_TIMEOUT`、`AKSHARE_MAX_RETRIES` 环境变量及注释
  - _需求：1.7, 1.8_

- [x] 20.10 编写数据源集成属性测试（Hypothesis）
  - [x] 20.10.1 编写属性 49 测试：数据源配置驱动初始化
    - **属性 49：数据源配置驱动初始化**
    - 验证 TushareAdapter 使用 Settings 中的 `tushare_api_token` 和 `tushare_api_url` 初始化，AkShareAdapter 使用 `akshare_request_timeout` 初始化，不包含硬编码凭证
    - **验证需求：1.7, 1.8**

  - [x] 20.10.2 编写属性 50 测试：Tushare 失败自动切换 AkShare
    - **属性 50：Tushare 失败自动切换 AkShare**
    - 验证对任意数据请求类型和参数，当 Tushare 调用失败时 DataSourceRouter 自动切换至 AkShare，若 AkShare 返回有效数据则整体请求成功
    - **验证需求：1.9**

  - [x] 20.10.3 编写属性 51 测试：双数据源均不可用时的错误处理
    - **属性 51：双数据源均不可用时的错误处理**
    - 验证当 Tushare 和 AkShare 均不可用时，DataSourceRouter 抛出 DataSourceUnavailableError，且记录包含两个数据源错误信息的日志，并推送 DANGER 级别告警
    - **验证需求：1.10**

  - [x] 20.10.4 编写属性 52 测试：统一格式转换不变量
    - **属性 52：统一格式转换不变量**
    - 验证对任意有效的 Tushare 或 AkShare 原始数据，经 FormatConverter 转换后 KlineBar 所有必填字段不为 None，high ≥ low，open/high/low/close 均为正数，两个数据源转换后结构一致
    - **验证需求：1.11**

- [x] 20.11 编写数据源故障转移集成测试
  - [x] 20.11.1 Tushare 正常 → 直接返回数据 → 不调用 AkShare 全链路测试
    - 验证主数据源正常时不触发备用数据源
    - _需求：1.1, 1.9_

  - [x] 20.11.2 Tushare 失败 → 自动切换 AkShare → 返回数据全链路测试
    - 验证主数据源失败时自动切换备用数据源并返回正确数据
    - _需求：1.9_

  - [x] 20.11.3 Tushare 和 AkShare 均失败 → 抛出异常 → 推送告警全链路测试
    - 验证双源不可用时抛出 DataSourceUnavailableError 并推送告警
    - _需求：1.10_

- [x] 20.12 最终检查点 - 确保阶段 20 所有功能和测试通过
  - 确保 `app/core/config.py` 包含所有新增配置字段
  - 确保 `TushareAdapter` 和 `AkShareAdapter` 正确实现 `BaseDataSourceAdapter` 接口
  - 确保 `DataSourceRouter` 故障转移逻辑正确（Tushare → AkShare → 异常 + 告警）
  - 确保格式转换器输出统一的 `KlineBar` 结构
  - 确保所有新增属性测试和集成测试通过
  - 确保所有测试通过，ask the user if questions arise.

---

## 阶段 21：数据管理页面与双数据源服务适配完善（需求 24）

- [x] 21.1 实现 `GET /data/sources/health` 健康检查端点
  - [x] 21.1.1 在 `app/api/v1/data.py` 中新增 `DataSourceStatus`、`DataSourceHealthResponse` Pydantic 响应模型
    - `DataSourceStatus`：name（str）、status（"connected" | "disconnected"）、checked_at（str ISO 8601）
    - `DataSourceHealthResponse`：sources（list[DataSourceStatus]）
    - _需求：24.1_

  - [x] 21.1.2 实现 `get_sources_health()` 端点
    - 分别实例化 `TushareAdapter` 和 `AkShareAdapter`，调用各自的 `health_check()` 方法
    - 外层 try/except 捕获所有异常，异常时将该数据源状态标记为 "disconnected"（需求 24.9）
    - 返回恰好 2 个数据源的健康状态
    - _需求：24.1, 24.9_

  - [x] 21.1.3 编写属性 53 测试：健康检查端点返回正确状态
    - **属性 53：健康检查端点返回正确状态**
    - 测试文件：`tests/properties/test_data_health_properties.py`
    - 对任意 health_check() 结果组合（True/False/异常），验证响应包含恰好 2 个数据源，status 字段正确映射，checked_at 不为空
    - **验证需求：24.1, 24.9**

- [x] 21.2 扩展 `DataSourceRouter` 新增 `fetch_with_fallback_info()` 方法
  - 在 `app/services/data_engine/data_source_router.py` 中新增 `fetch_with_fallback_info()` 方法
  - 返回三元组 `(data, data_source_name, is_fallback)`：主数据源成功返回 `("Tushare", False)`，回退成功返回 `("AkShare", True)`
  - 保持原 `fetch_with_fallback()` 不变（向后兼容）
  - _需求：24.3_

- [x] 21.3 更新 Celery 同步任务写入同步状态至 Redis
  - [x] 21.3.1 在 `app/tasks/data_sync.py` 中新增 `_update_sync_status()` 辅助函数
    - 接受参数：data_type、source_label、status、record_count、data_source、is_fallback
    - 通过 `cache_set()` 将 JSON 写入 Redis 键 `sync:status:{data_type}`，过期时间 24 小时
    - _需求：24.3_

  - [x] 21.3.2 更新 `sync_fundamentals` 任务使用 `fetch_with_fallback_info()` 并写入同步状态
    - 调用 `router.fetch_with_fallback_info()` 获取数据源标识
    - 任务完成后调用 `_update_sync_status("fundamentals", ...)` 写入 Redis
    - _需求：24.3_

  - [x] 21.3.3 更新 `sync_money_flow` 任务使用 `fetch_with_fallback_info()` 并写入同步状态
    - 同上逻辑，写入 `sync:status:money_flow`
    - _需求：24.3_

  - [x] 21.3.4 更新 `sync_realtime_market` 任务写入同步状态
    - 任务完成后调用 `_update_sync_status("kline", ...)` 写入 Redis
    - 实时行情不经过 DataSourceRouter，data_source 固定为 "MarketDataClient"，is_fallback 为 false
    - _需求：24.3_

- [x] 21.4 更新 `GET /data/sync/status` 端点从 Redis 读取同步状态
  - 在 `app/api/v1/data.py` 中新增 `SyncStatusItem`、`SyncStatusResponse` Pydantic 模型（含 data_source、is_fallback 字段）
  - 重写 `get_sync_status()` 端点：从 Redis 读取 `sync:status:kline`、`sync:status:fundamentals`、`sync:status:money_flow` 三个键
  - Redis 无缓存时返回默认值：status="UNKNOWN"、data_source="N/A"、is_fallback=false
  - _需求：24.3_

  - [x] 21.4.1 编写属性 54 测试：同步状态响应包含数据源和故障转移字段
    - **属性 54：同步状态响应包含数据源和故障转移字段**
    - 测试文件：`tests/properties/test_data_sync_status_properties.py`
    - 验证每条 SyncStatusItem 包含 data_source（"Tushare"/"AkShare"/"N/A"）和 is_fallback 布尔字段
    - **验证需求：24.3**

- [x] 21.5 更新 `POST /data/sync` 端点支持 sync_type 参数分发 Celery 任务
  - 在 `app/api/v1/data.py` 中新增 `SyncRequest`（sync_type 可选）和 `SyncResponse`（message + task_ids）Pydantic 模型
  - 重写 `trigger_sync()` 端点：根据 sync_type 分发对应 Celery 任务
    - `"kline"` → `sync_realtime_market.delay()`
    - `"fundamentals"` → `sync_fundamentals.delay()`
    - `"money_flow"` → `sync_money_flow.delay()`
    - `"all"` 或缺省 → 触发全部三个任务
    - 无效 sync_type → 返回错误提示，不触发任务
  - 返回 task_ids 列表，数量与触发的任务数一致
  - _需求：24.5_

  - [x] 21.5.1 编写属性 55 测试：手动同步按类型分发正确的 Celery 任务
    - **属性 55：手动同步按类型分发正确的 Celery 任务**
    - 测试文件：`tests/properties/test_data_sync_dispatch_properties.py`
    - 对任意有效 sync_type，验证分发的任务类型和 task_ids 数量正确
    - **验证需求：24.5**

- [x] 21.6 检查点 - 确保后端 API 端点实现完整
  - 确保 `GET /data/sources/health`、`GET /data/sync/status`、`POST /data/sync` 端点正常工作
  - 确保 DataSourceRouter.fetch_with_fallback_info() 返回正确三元组
  - 确保 Celery 任务写入 Redis 同步状态
  - 确保所有测试通过，ask the user if questions arise.

- [x] 21.7 实现 `GET /data/cleaning/stats` 清洗统计端点
  - 在 `app/api/v1/data.py` 中新增 `CleaningStatsResponse` Pydantic 模型（total_stocks、valid_stocks、st_delisted_count、new_stock_count、suspended_count、high_pledge_count）
  - 实现 `get_cleaning_stats()` 端点：通过 `AsyncSessionPG` 查询 `stock_info` 和 `permanent_exclusion` 表
    - total_stocks = `SELECT COUNT(*) FROM stock_info`
    - st_delisted_count = `is_st=True OR is_delisted=True` 的行数
    - new_stock_count = `permanent_exclusion` 中 `reason='NEW_STOCK'` 的行数
    - suspended_count = `permanent_exclusion` 中 `reason='SUSPENDED'` 的行数
    - high_pledge_count = `stock_info` 中 `pledge_ratio > 70` 的行数
    - valid_stocks = `max(total - st_delisted - new_stock - suspended - high_pledge, 0)`
  - _需求：24.7_

  - [x] 21.7.1 编写属性 56 测试：清洗统计数据库查询正确性
    - **属性 56：清洗统计数据库查询正确性**
    - 测试文件：`tests/properties/test_cleaning_stats_properties.py`
    - 对任意 stock_info 和 permanent_exclusion 表数据状态，验证各统计字段与数据库查询结果一致，valid_stocks 下限为 0
    - **验证需求：24.7**

- [x] 21.8 实现前端健康状态卡片和同步类型选择器（DataManageView）
  - [x] 21.8.1 新增 TypeScript 接口定义
    - 新增 `DataSourceStatus`、`DataSourceHealthResponse`、`CleaningStatsResponse` 接口
    - 更新 `SyncStatus` 接口新增 `data_source: string` 和 `is_fallback: boolean` 字段
    - _需求：24.1, 24.3, 24.7_

  - [x] 21.8.2 实现数据源健康状态卡片区域
    - 在 DataManageView 页面顶部（同步状态表格之前）新增健康状态卡片区域
    - 调用 `GET /data/sources/health` 获取数据，使用 `usePageState` 管理加载/错误状态
    - 连通（connected）显示绿色"✅ 已连接"卡片，断开（disconnected）显示红色"❌ 已断开"卡片
    - 页面加载时（`onMounted`）调用 `fetchHealth()`
    - _需求：24.2_

  - [x] 21.8.3 实现同步类型选择器下拉框
    - 在手动同步按钮前新增 `<select>` 下拉选择框，选项：全部同步 / 行情数据 / 基本面数据 / 资金流向
    - 绑定 `syncType` ref，`triggerSync()` 传递 `{ sync_type: syncType.value }` 至 `POST /data/sync`
    - _需求：24.6_

  - [x] 21.8.4 同步状态表格新增"数据源"列
    - 在同步状态表格中新增"数据源"列，显示 `item.data_source`
    - 当 `item.is_fallback` 为 true 时，在数据源名称后追加黄色"（故障转移）"标注
    - _需求：24.4_

  - [x] 21.8.5 编写属性 57 测试：数据源状态 UI 渲染正确性
    - **属性 57：数据源状态 UI 渲染正确性**
    - 测试文件：`frontend/src/views/__tests__/data-source-status.property.test.ts`
    - 对任意健康检查响应和同步状态响应组合，验证卡片颜色映射正确、故障转移标注正确
    - **验证需求：24.2, 24.4**

- [x] 21.9 实现前端 API 驱动的清洗统计（DataManageView）
  - 替换数据清洗统计区域的硬编码静态数值
  - 新增 `cleaningState` 使用 `usePageState<CleaningStatsResponse>` 管理状态
  - 调用 `GET /data/cleaning/stats` 获取实时统计数据
  - 加载中显示 `LoadingSpinner`，失败时显示 `ErrorBanner` 并提供重试按钮（需求 24.10）
  - 统计卡片展示：总股票数、有效标的、ST/退市剔除、新股剔除、停牌剔除、高质押剔除
  - 页面加载时（`onMounted`）调用 `fetchCleaningStats()`
  - _需求：24.8, 24.10_

  - [x] 21.9.1 编写属性 58 测试：清洗统计 UI 展示 API 数据正确性
    - **属性 58：清洗统计 UI 展示 API 数据正确性**
    - 测试文件：`frontend/src/views/__tests__/cleaning-stats.property.test.ts`
    - 对任意有效 CleaningStatsResponse 数据，验证页面展示数值与 API 返回一致，无硬编码静态数值
    - **验证需求：24.8**

- [x] 21.10 编写数据管理页面集成测试
  - [x] 21.10.1 健康检查 → 状态卡片渲染 → 手动同步（指定类型）→ 同步状态刷新（含数据源列）全链路测试
    - 测试文件：`tests/integration/test_data_manage_dual_source_integration.py`
    - 验证健康检查端点返回正确状态 → 前端卡片渲染 → 按类型触发同步 → 同步状态含 data_source 和 is_fallback 字段
    - _需求：24.1, 24.2, 24.3, 24.4, 24.5, 24.6_

  - [x] 21.10.2 数据库写入测试数据 → 清洗统计 API 查询 → 前端展示验证全链路测试
    - 测试文件：`tests/integration/test_data_manage_dual_source_integration.py`（同文件）
    - 向 stock_info 和 permanent_exclusion 表写入测试数据，验证 GET /data/cleaning/stats 返回正确统计
    - _需求：24.7, 24.8_

- [x] 21.11 最终检查点 - 确保阶段 21 所有功能和测试通过
  - 确保 `GET /data/sources/health` 正确返回两个数据源健康状态，异常时标记为 disconnected
  - 确保 `GET /data/sync/status` 从 Redis 读取并包含 data_source 和 is_fallback 字段
  - 确保 `POST /data/sync` 按 sync_type 分发正确的 Celery 任务
  - 确保 `GET /data/cleaning/stats` 从数据库查询实时清洗统计
  - 确保 DataManageView 健康状态卡片、同步类型选择器、数据源列、清洗统计均正常渲染
  - 确保所有新增属性测试和集成测试通过
  - 确保所有测试通过，ask the user if questions arise.

---

## 阶段 22：历史数据批量回填（需求 25）

### 概述

实现历史数据批量回填功能，支持 K 线行情、基本面、资金流向三种数据类型的批量回填，包含后端 BackfillService 编排层、三个 Celery 异步回填任务、每日增量同步定时任务、两个 API 端点、Redis 进度追踪，以及前端 DataManageView 回填控件与进度展示。

### 任务

- [x] 22.1 实现 BackfillService 编排层
  - [x] 22.1.1 创建 `app/services/data_engine/backfill_service.py`，实现 `BackfillService` 类
    - 常量：`BATCH_SIZE=50`、`BATCH_DELAY=1.0`、`REDIS_KEY="backfill:progress"`、`PROGRESS_TTL=86400`
    - `start_backfill(data_types, symbols, start_date, end_date, freq)` 方法：检查 Redis 并发保护（status=running 时拒绝）、填充默认参数、初始化 Redis 进度为 pending、按 data_types 分发对应 Celery 任务
    - `get_progress()` 方法：从 Redis 读取 `backfill:progress` 键，无数据时返回 `status="idle"` 默认值
    - `_resolve_symbols(symbols)` 方法：symbols 为空时查询 StockInfo 表中 `is_st=False AND is_delisted=False` 的全市场有效股票
    - `_resolve_start_date(start_date)` 方法：未传入时使用 `today - settings.kline_history_years`（默认 10 年）
    - _需求：25.1, 25.2, 25.3, 25.12_

  - [x] 22.1.2 编写属性 60 测试：回填参数默认值填充正确性
    - **属性 60：回填参数默认值填充正确性**
    - 测试文件：`tests/properties/test_backfill_defaults_properties.py`
    - 对任意缺省 symbols 和/或缺省 start_date 的回填请求，验证 symbols 填充为 StockInfo 全市场有效股票、start_date 填充为 `today - kline_history_years`
    - **验证需求：25.2, 25.3**

- [x] 22.2 实现三个 Celery 异步回填任务
  - [x] 22.2.1 在 `app/tasks/data_sync.py` 中新增 `sync_historical_kline` 任务
    - 接受参数：`symbols`、`start_date`、`end_date`、`freq`（默认 "1d"，支持 "1d"/"1w"/"1M"）
    - 按 BATCH_SIZE=50 分批处理，批间 `asyncio.sleep(1)` 延迟
    - 通过 `DataSourceRouter.fetch_kline()` 获取数据，通过 `KlineRepository.bulk_insert()` 写入（ON CONFLICT DO NOTHING 幂等）
    - 每完成一只股票更新 Redis `backfill:progress` 进度（completed++、current_symbol）
    - 单只股票 DataSourceRouter 双源失败时记录错误、failed++、继续下一只
    - 全部处理完毕后更新 status 为 completed
    - _需求：25.4, 25.7, 25.8, 25.10, 25.11_

  - [x] 22.2.2 在 `app/tasks/data_sync.py` 中新增 `sync_historical_fundamentals` 任务
    - 接受参数：`symbols`、`start_date`、`end_date`
    - 同样分批处理（BATCH_SIZE=50，批间 1s 延迟）、Redis 进度追踪、容错继续
    - 通过 `DataSourceRouter.fetch_fundamentals()` 获取数据，写入 PostgreSQL（唯一约束去重）
    - _需求：25.5, 25.7, 25.8, 25.10, 25.11_

  - [x] 22.2.3 在 `app/tasks/data_sync.py` 中新增 `sync_historical_money_flow` 任务
    - 接受参数：`symbols`、`start_date`、`end_date`
    - 同样分批处理（BATCH_SIZE=50，批间 1s 延迟）、Redis 进度追踪、容错继续
    - 通过 `DataSourceRouter.fetch_money_flow()` 获取数据，写入 PostgreSQL（唯一约束去重）
    - _需求：25.6, 25.7, 25.8, 25.10, 25.11_

  - [x] 22.2.4 编写属性 61 测试：回填任务数据流正确性
    - **属性 61：回填任务通过 DataSourceRouter 获取数据并写入正确存储**
    - 测试文件：`tests/properties/test_backfill_task_properties.py`
    - 对任意数据类型和非空股票列表，验证回填任务调用 DataSourceRouter 对应方法并写入正确存储
    - **验证需求：25.4, 25.5, 25.6**

  - [x] 22.2.5 编写属性 62 测试：批次大小与延迟
    - **属性 62：批次大小不超过 50 且批间延迟 ≥ 1 秒**
    - 测试文件：`tests/properties/test_backfill_batching_properties.py`
    - 对任意长度 N 的股票列表，验证分为 ⌈N/50⌉ 个批次，每批不超过 50 只，批间间隔 ≥ 1 秒
    - **验证需求：25.7**

  - [x] 22.2.6 编写属性 63 测试：回填操作幂等性
    - **属性 63：回填操作幂等性**
    - 测试文件：`tests/properties/test_backfill_idempotent_properties.py`
    - 对任意股票列表和日期范围，验证两次回填后数据库状态与一次回填完全相同
    - **验证需求：25.8**

  - [x] 22.2.7 编写属性 65 测试：单只股票失败不中断任务且 failed 计数正确
    - **属性 65：单只股票失败不中断任务且 failed 计数正确**
    - 测试文件：`tests/properties/test_backfill_fault_tolerance_properties.py`
    - 对任意长度 N 的股票列表（其中 K 只失败），验证 completed + failed = N 且 failed = K
    - **验证需求：25.11**

- [x] 22.3 检查点 - 确保回填任务核心逻辑正确
  - 确保 BackfillService 参数填充、并发保护、任务分发逻辑正确
  - 确保三个回填任务的分批处理、进度追踪、容错继续逻辑正确
  - 确保所有测试通过，ask the user if questions arise.

- [x] 22.4 实现 Celery Beat 每日增量同步任务
  - [x] 22.4.1 在 `app/tasks/data_sync.py` 中新增 `sync_daily_kline` 任务
    - 查询 StockInfo 全市场有效股票
    - 计算前一个交易日日期
    - 复用 `sync_historical_kline` 核心逻辑回填前一个交易日日 K 线数据
    - _需求：25.13_

  - [x] 22.4.2 在 `app/core/celery_app.py` 的 `beat_schedule` 中注册 `sync_daily_kline`
    - 调度配置：`crontab(hour=16, minute=0, day_of_week="1-5")`，队列 `data_sync`
    - 键名：`"daily-kline-sync-1600"`
    - _需求：25.13_

- [x] 22.5 实现两个 API 端点
  - [x] 22.5.1 在 `app/api/v1/data.py` 中新增 `POST /data/backfill` 端点
    - 请求模型 `BackfillRequest`：`data_types`（默认全部三种）、`symbols`（留空=全市场）、`start_date`、`end_date`、`freq`（默认 "1d"）
    - 响应模型 `BackfillResponse`：`message`、`task_ids`
    - 调用 `BackfillService.start_backfill()` 编排回填流程
    - 已有任务运行中（Redis status=running）时返回 HTTP 409
    - Pydantic 校验 freq 取值（"1d"/"1w"/"1M"）和 start_date ≤ end_date
    - _需求：25.1, 25.2, 25.3, 25.12_

  - [x] 22.5.2 在 `app/api/v1/data.py` 中新增 `GET /data/backfill/status` 端点
    - 响应模型 `BackfillStatusResponse`：`total`、`completed`、`failed`、`current_symbol`、`status`、`data_types`
    - 调用 `BackfillService.get_progress()` 从 Redis 读取进度
    - Redis 无数据时返回 `status="idle"` 默认值
    - _需求：25.9, 25.10_

  - [x] 22.5.3 编写属性 59 测试：回填 API 按数据类型分发任务
    - **属性 59：回填 API 按数据类型分发对应 Celery 任务**
    - 测试文件：`tests/properties/test_backfill_dispatch_properties.py`
    - 对任意合法 data_types 子集，验证分发的 Celery 任务集合与请求的 data_types 一一对应
    - **验证需求：25.1**

  - [x] 22.5.4 编写属性 64 测试：进度追踪 Redis 读写一致性
    - **属性 64：进度追踪 Redis 读写一致性**
    - 测试文件：`tests/properties/test_backfill_progress_properties.py`
    - 对任意回填进度状态，验证写入 Redis 后通过 GET /backfill/status 读取的各字段值与写入值一致
    - **验证需求：25.9, 25.10**

  - [x] 22.5.5 编写属性 66 测试：并发保护拒绝新请求
    - **属性 66：并发保护——运行中拒绝新请求**
    - 测试文件：`tests/properties/test_backfill_concurrency_properties.py`
    - 对任意 Redis 中 status 为 running 的状态，验证 POST /backfill 返回 HTTP 409 且不分发新任务
    - **验证需求：25.12**

- [x] 22.6 检查点 - 确保 API 端点和定时任务正确
  - 确保 `POST /data/backfill` 正确分发任务、并发保护生效、参数校验正确
  - 确保 `GET /data/backfill/status` 正确读取 Redis 进度
  - 确保 `sync_daily_kline` Celery Beat 调度配置正确（16:00 工作日）
  - 确保所有测试通过，ask the user if questions arise.

- [x] 22.7 实现前端回填控件与进度展示（DataManageView）
  - [x] 22.7.1 在 DataManageView.vue 中新增回填相关 TypeScript 类型定义
    - `BackfillRequest` 接口：`data_types`、`symbols`、`start_date`、`end_date`、`freq`
    - `BackfillProgress` 接口：`total`、`completed`、`failed`、`current_symbol`、`status`、`data_types`
    - _需求：25.14, 25.15_

  - [x] 22.7.2 在 DataManageView.vue 中新增"历史数据回填"区域（数据清洗统计之后、永久剔除名单之前）
    - 数据类型多选复选框：行情数据 / 基本面数据 / 资金流向（默认全选）
    - 股票代码输入框：支持逗号分隔多个代码，placeholder="留空表示全市场"
    - 起止日期选择器：`<input type="date">`
    - K 线频率选择控件：日线 / 周线 / 月线（仅当"行情数据"被勾选时显示）
    - "开始回填"按钮：点击调用 `POST /api/v1/data/backfill`
    - _需求：25.14_

  - [x] 22.7.3 实现回填进度展示区域
    - 进度条：`completed / total`（百分比）
    - 当前处理股票代码：`current_symbol`
    - 正在回填的数据类型标签：`data_types`
    - 失败数量：`failed`
    - 任务状态徽章：`status`（idle/pending/running/completed/failed）
    - 轮询逻辑：任务 running/pending 时每 3 秒调用 `GET /api/v1/data/backfill/status`，completed/failed 后停止轮询
    - 已有任务运行中时显示拒绝提示信息
    - _需求：25.15_

  - [x] 22.7.4 编写属性 67 测试：频率选择器动态显隐
    - **属性 67：前端回填控件根据数据类型选择动态显示频率选择器**
    - 测试文件：`frontend/src/views/__tests__/backfill-freq-toggle.property.test.ts`
    - 对任意数据类型复选框选择状态，验证频率选择器仅在"行情数据"被勾选时可见
    - **验证需求：25.14**

  - [x] 22.7.5 编写属性 68 测试：进度展示字段完整性
    - **属性 68：前端进度展示包含所有必要字段**
    - 测试文件：`frontend/src/views/__tests__/backfill-progress-display.property.test.ts`
    - 对任意合法 BackfillProgress 状态对象，验证渲染后包含进度条、当前股票代码、数据类型标签、失败数量和状态徽章
    - **验证需求：25.15**

- [x] 22.8 编写集成测试
  - [x] 22.8.1 触发回填 → Celery 任务执行 → Redis 进度更新 → 状态 API 查询全链路测试
    - 测试文件：`tests/integration/test_backfill_integration.py`
    - 验证 POST /data/backfill 触发任务 → 任务执行中 Redis 进度正确更新 → GET /data/backfill/status 返回正确进度
    - _需求：25.1, 25.4, 25.9, 25.10_

  - [x] 22.8.2 重复回填同一数据 → 验证数据库无重复记录（幂等性）全链路测试
    - 测试文件：`tests/integration/test_backfill_integration.py`（同文件）
    - 对同一股票和日期范围执行两次回填，验证数据库记录数与一次回填相同
    - _需求：25.8_

- [x] 22.9 最终检查点 - 确保阶段 22 所有功能和测试通过
  - 确保 `BackfillService` 参数填充、并发保护、任务分发逻辑正确
  - 确保 `sync_historical_kline`、`sync_historical_fundamentals`、`sync_historical_money_flow` 三个回填任务分批处理、进度追踪、容错继续均正常
  - 确保 `sync_daily_kline` Celery Beat 定时任务在 16:00 工作日正确调度
  - 确保 `POST /data/backfill` 正确分发任务、并发保护生效（running 时返回 409）
  - 确保 `GET /data/backfill/status` 正确从 Redis 读取进度、无数据时返回 idle
  - 确保 DataManageView 回填区域控件渲染正确：数据类型复选框、股票代码输入、日期选择器、频率选择器动态显隐、进度展示
  - 确保所有新增属性测试（属性 59-68）和集成测试通过
  - 确保所有测试通过，ask the user if questions arise.

---

## 阶段 23：回填任务停止功能（需求 25.16–25.17）

- [x] 23.1 实现后端停止回填功能
  - [x] 23.1.1 在 `BackfillService` 中新增 `stop_backfill()` 方法
    - 从 Redis 读取 `backfill:progress`，检查 `status` 是否为 `running` 或 `pending`
    - 是 → 将 `status` 设为 `"stopping"` 并写回 Redis，返回成功
    - 否 → 返回提示"当前没有正在执行的回填任务"
    - _需求：25.16_

  - [x] 23.1.2 在 `app/api/v1/data.py` 中新增 `POST /data/backfill/stop` 端点
    - 调用 `BackfillService.stop_backfill()`
    - 返回 `{message: str}`
    - _需求：25.16_

  - [x] 23.1.3 在三个历史回填任务中添加停止检测逻辑
    - 在 `_sync_historical_kline`、`_sync_historical_fundamentals`、`_sync_historical_money_flow` 的每只股票处理循环开头，读取 Redis `backfill:progress` 的 `status`
    - 检测到 `"stopping"` 时：将 `status` 更新为 `"stopped"`，记录日志，立即返回当前进度
    - 已写入数据库的数据保留不回滚
    - _需求：25.16_

- [x] 23.2 实现前端停止回填按钮
  - [x] 23.2.1 在 DataManageView.vue 回填区域新增"停止回填"按钮
    - 仅当 `backfillProgress.status` 为 `running` 或 `pending` 时显示
    - 点击调用 `POST /api/v1/data/backfill/stop`
    - 请求期间按钮显示"停止中..."并禁用
    - 任务状态变为 `stopped`/`completed`/`failed`/`idle` 后按钮隐藏
    - _需求：25.17_

  - [x] 23.2.2 更新 `BackfillProgress` 类型定义
    - `status` 字段新增 `'stopping'` 和 `'stopped'` 取值
    - 更新 `backfillStatusLabel()` 和 `backfillStatusClass()` 函数支持新状态
    - _需求：25.17_

- [x] 23.3 检查点 - 确保停止回填功能正常
  - 确保 `POST /data/backfill/stop` 正确发送停止信号
  - 确保三个回填任务检测到停止信号后立即终止
  - 确保前端停止按钮在正确时机显示/隐藏
  - 确保已写入的数据保留不丢失

---

## 阶段 24：大盘概况页面基本面数据与资金流向展示（需求 26）

- [x] 24.1 实现后端基本面与资金流向 API 端点
  - [x] 24.1.1 在 `app/api/v1/data.py` 中新增 Pydantic 响应模型
    - 定义 `StockFundamentalsResponse`：包含 `symbol`、`name`、`pe_ttm`、`pb`、`roe`、`market_cap`、`revenue_growth`、`net_profit_growth`、`report_period`、`updated_at` 字段
    - 定义 `MoneyFlowDailyRecord`：包含 `trade_date`、`main_net_inflow`、`north_net_inflow`、`large_order_ratio`、`super_large_inflow`、`large_inflow` 字段
    - 定义 `StockMoneyFlowResponse`：包含 `symbol`、`name`、`days`、`records: list[MoneyFlowDailyRecord]` 字段
    - `FundamentalsData.revenue_yoy` 映射为 `revenue_growth`，`net_profit_yoy` 映射为 `net_profit_growth`
    - _需求：26.6, 26.7_

  - [x] 24.1.2 实现 `GET /api/v1/data/stock/{symbol}/fundamentals` 端点
    - 调用 `DataSourceRouter.fetch_fundamentals(symbol)` 获取数据
    - 将 `FundamentalsData` 映射为 `StockFundamentalsResponse` 返回
    - 股票不存在或无数据 → 返回 HTTP 404，消息"未找到该股票的基本面数据"
    - `DataSourceUnavailableError` → 返回 HTTP 503，消息"数据源暂时不可用，请稍后重试"
    - _需求：26.6, 26.8_

  - [x] 24.1.3 实现 `GET /api/v1/data/stock/{symbol}/money-flow` 端点
    - 接受 `days` 查询参数（默认 20，范围 1–60）
    - 调用 `DataSourceRouter.fetch_money_flow()` 获取近 `days` 个交易日数据
    - 聚合为 `StockMoneyFlowResponse` 返回，`records` 按日期升序排列
    - 股票不存在或无数据 → 返回 HTTP 404，消息"未找到该股票的资金流向数据"
    - `DataSourceUnavailableError` → 返回 HTTP 503
    - _需求：26.7, 26.9_

  - [x] 24.1.4 编写属性测试：基本面 API 响应字段完整性
    - **属性 69：基本面 API 响应包含全部必需字段**
    - 测试文件：`tests/properties/test_stock_fundamentals_api_properties.py`
    - *For any* 合法的 `FundamentalsData`，响应 JSON 应包含全部 8 个必需字段
    - **验证：需求 26.6**

  - [x] 24.1.5 编写属性测试：资金流向 API 记录数与字段完整性
    - **属性 70：资金流向 API 返回记录数不超过 days 参数**
    - 测试文件：`tests/properties/test_stock_money_flow_api_properties.py`
    - *For any* 合法的 `days`（1–60），返回 `records` 长度 ≤ `days`，每条记录包含全部 6 个字段
    - **验证：需求 26.7**

  - [x] 24.1.6 编写属性测试：资金流向汇总计算正确性
    - **属性 75：资金流向汇总卡片计算正确性**
    - 测试文件：`tests/properties/test_money_flow_summary_properties.py`
    - *For any* 长度 ≥ 5 的记录列表，近5日累计 = 最近5条 `main_net_inflow` 之和，当日 = 最新一条
    - **验证：需求 26.3**

- [x] 24.2 实现前端 DashboardView 标签页结构
  - [x] 24.2.1 在 DashboardView.vue 中新增标签页导航
    - 在 `chart-section` 区域新增标签页容器，包含"K线图"、"基本面"、"资金流向"三个标签按钮
    - 使用 `role="tablist"` / `role="tab"` / `role="tabpanel"` 确保无障碍访问
    - 定义 `activeTab` 响应式变量（类型 `'kline' | 'fundamentals' | 'moneyFlow'`，默认 `'kline'`）
    - 将现有 K 线图内容包裹在 `v-show="activeTab === 'kline'"` 面板中
    - _需求：26.1_

  - [x] 24.2.2 定义前端 TypeScript 接口
    - 定义 `StockFundamentalsResponse`、`MoneyFlowDailyRecord`、`StockMoneyFlowResponse`、`ChartTab` 类型
    - 新增 `fundamentals`、`fundamentalsLoading`、`fundamentalsError`、`moneyFlow`、`moneyFlowLoading`、`moneyFlowError` 响应式状态
    - _需求：26.2, 26.3_

  - [x] 24.2.3 实现标签页切换与数据加载逻辑
    - `switchTab(tab)` 方法：切换 `activeTab`，首次切换到非 K 线标签页时自动调用对应加载函数
    - `loadFundamentals()`：调用 `GET /api/v1/data/stock/{symbol}/fundamentals`，管理 loading/error 状态
    - `loadMoneyFlow()`：调用 `GET /api/v1/data/stock/{symbol}/money-flow`，管理 loading/error 状态
    - 使用 AbortController 取消旧请求，避免切换股票时数据错乱
    - _需求：26.2, 26.3, 26.10_

  - [x] 24.2.4 编写属性测试：标签页切换仅显示当前激活面板
    - **属性 71：标签页切换仅显示当前激活面板**
    - 测试文件：`frontend/src/views/__tests__/dashboard-tabs.property.test.ts`
    - *For any* 标签页状态，仅当前激活面板可见，其余隐藏
    - **验证：需求 26.1**

- [x] 24.3 实现基本面数据卡片与颜色编码
  - [x] 24.3.1 实现基本面数据卡片渲染
    - 在"基本面"面板中以数据卡片形式展示：PE TTM、PB、ROE、总市值、营收同比增长率、净利润同比增长率
    - 底部显示报告期（`report_period`）和更新时间（`updated_at`）
    - 加载中显示 loading 指示器，请求失败显示错误提示和重试按钮
    - _需求：26.2, 26.10, 26.11_

  - [x] 24.3.2 实现 `getFundamentalColorClass` 颜色编码纯函数
    - PE TTM：低于行业均值 → `color-green`，高于行业均值 → `color-red`
    - ROE：> 15% → `color-green`，< 8% → `color-red`，8%–15% → 无色
    - 营收/净利润增长率：> 0 → `color-red`（增长），< 0 → `color-green`（下降），= 0 → 无色
    - _需求：26.5_

  - [x] 24.3.3 编写属性测试：基本面数据卡片渲染完整性
    - **属性 72：基本面数据卡片渲染全部指标及元数据**
    - 测试文件：`frontend/src/views/__tests__/dashboard-fundamentals-cards.property.test.ts`
    - *For any* 合法的 `StockFundamentalsResponse`（数值字段非 null），渲染应包含六个指标值及报告期和更新时间
    - **验证：需求 26.2, 26.11**

  - [x] 24.3.4 编写属性测试：基本面颜色编码正确性
    - **属性 73：基本面指标颜色编码正确性**
    - 测试文件：`frontend/src/views/__tests__/dashboard-fundamentals-color.property.test.ts`
    - *For any* PE/ROE/增长率值，`getFundamentalColorClass` 返回值应符合颜色规则
    - **验证：需求 26.5**

- [x] 24.4 实现资金流向柱状图与汇总卡片
  - [x] 24.4.1 实现资金流向 ECharts 柱状图
    - 使用 ECharts 渲染近 20 个交易日的每日主力资金净流入柱状图
    - 正值柱体颜色 `#f85149`（红色），负值柱体颜色 `#3fb950`（绿色）
    - X 轴为交易日期，Y 轴为金额（万元），含 tooltip 显示具体数值
    - _需求：26.4_

  - [x] 24.4.2 实现资金流向汇总数据卡片
    - 展示：当日主力资金净流入金额、近5日主力资金净流入累计金额、北向资金持仓变动、大单成交占比
    - 当日净流入 = 最新一条记录的 `main_net_inflow`
    - 近5日累计 = 最近5条记录的 `main_net_inflow` 之和
    - 加载中显示 loading 指示器，请求失败显示错误提示和重试按钮
    - _需求：26.3, 26.10_

  - [x] 24.4.3 编写属性测试：资金流向柱状图颜色映射
    - **属性 74：资金流向柱状图颜色映射**
    - 测试文件：`frontend/src/views/__tests__/dashboard-money-flow-color.property.test.ts`
    - *For any* 每日记录列表，`main_net_inflow ≥ 0` → `#f85149`，`< 0` → `#3fb950`
    - **验证：需求 26.4**

- [x] 24.5 实现加载/错误状态与股票切换重置
  - [x] 24.5.1 实现统一加载与错误状态处理
    - 基本面和资金流向标签页：loading 时显示加载指示器，error 时显示错误信息和重试按钮
    - 重试按钮点击后重新调用对应加载函数
    - _需求：26.10_

  - [x] 24.5.2 实现 `resetTabData()` 股票切换数据重置
    - 切换股票查询时清除 `fundamentals`、`moneyFlow` 数据及 loading/error 状态
    - 如果当前在非 K 线标签页，自动加载对应数据
    - _需求：26.12_

  - [x] 24.5.3 编写属性测试：加载与错误状态渲染
    - **属性 76：加载与错误状态渲染**
    - 测试文件：`frontend/src/views/__tests__/dashboard-loading-error.property.test.ts`
    - *For any* loading/error 状态组合，渲染结果应符合：loading=true → 加载指示器，error 非空 → 错误信息+重试按钮
    - **验证：需求 26.10**

  - [x] 24.5.4 编写属性测试：切换股票数据状态重置
    - **属性 77：切换股票查询时数据状态重置**
    - 测试文件：`frontend/src/views/__tests__/dashboard-stock-switch-reset.property.test.ts`
    - *For any* 两个不同股票代码，切换后基本面和资金流向的数据、loading、error 状态应全部重置
    - **验证：需求 26.12**

- [x] 24.6 检查点 - 确保基本面与资金流向功能正常
  - 确保 `GET /data/stock/{symbol}/fundamentals` 正确返回基本面数据，无数据时返回 404
  - 确保 `GET /data/stock/{symbol}/money-flow` 正确返回资金流向数据，`records` 按日期升序且长度 ≤ days
  - 确保 DashboardView 三个标签页切换正常，仅当前面板可见
  - 确保基本面数据卡片渲染六个指标值、颜色编码正确、底部显示报告期和更新时间
  - 确保资金流向柱状图红绿颜色映射正确，汇总卡片计算准确
  - 确保切换股票时数据状态正确重置
  - 确保所有新增属性测试（属性 69-77）通过
  - 确保所有测试通过，ask the user if questions arise.

---

## 备注

- 标记 `*` 的子任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点任务确保增量验证
- 属性测试验证普遍正确性属性（使用 Hypothesis）
- 单元测试验证具体示例和边界条件
