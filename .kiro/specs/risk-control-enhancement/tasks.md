# 任务清单：风控系统增强

## 阶段一：P0 — 交易执行链路强制风控 + 止损实时推送

- [x] 1. RiskGateway 风控网关实现（需求 1）
  - [x] 1.1 在 `app/services/risk_controller.py` 中新增 `RiskGateway` 类，实现 `check_order_risk_pure()` 静态方法：接受委托请求、持仓列表、黑名单集合、涨幅、行业映射、总市值、可用现金、仓位上限等参数，按顺序执行黑名单检查 → 涨幅检查 → 单股仓位检查 → 板块仓位检查 → 总仓位检查（短路求值），卖出委托直接返回 passed=True
  - [x] 1.2 在 `RiskGateway` 中实现 `check_and_submit()` 方法：对买入委托调用风控校验链，通过则提交至 BrokerClient，未通过则返回 REJECTED 状态的 OrderResponse（含拒绝原因），异常时捕获并返回 REJECTED + 异常描述
  - [x] 1.3 修改 `app/services/trade_executor.py` 中 `TradeExecutor.submit_order()` 方法，在调用 `broker.submit_order()` 之前插入 `RiskGateway.check_and_submit()` 调用，确保所有委托路径（直接调用和 Celery 任务）均经过风控网关
  - [x] 1.4 编写属性测试 `tests/properties/test_risk_gateway_properties.py`，验证 Property 1（风控网关校验正确性）和 Property 2（卖出委托跳过买入风控）
  - [x] 1.5 编写单元测试 `tests/services/test_risk_gateway.py`，覆盖异常处理路径、边界条件（空持仓、零仓位）

- [x] 2. 止损预警实时 WebSocket 推送（需求 2）
  - [x] 2.1 在 `app/core/pubsub_relay.py` 的 `USER_CHANNEL_PREFIXES` 列表中新增 `"risk:alert:"` 前缀，使风控预警消息能通过现有 PubSubRelay 转发到 WebSocket
  - [x] 2.2 在 `app/services/risk_controller.py` 中新增 `build_stop_loss_alert_message()` 静态方法，接受股票代码、预警类型、当前价格、触发阈值、预警级别、触发时间，返回 JSON 格式的预警消息字符串
  - [x] 2.3 在 `app/api/v1/risk.py` 的 `position_warnings` 端点中，当检测到止损预警时，通过 Redis `PUBLISH risk:alert:{user_id}` 发布预警消息
  - [x] 2.4 在 `app/services/risk_controller.py` 中新增交易时段判断方法 `is_risk_alert_active(now: datetime) -> bool`，非交易时段（15:00 至次日 9:25）返回 False，用于抑制无效推送
  - [x] 2.5 在 `frontend/src/views/RiskView.vue` 中建立 WebSocket 连接，监听 `risk:alert` 频道消息，收到止损预警时在仓位风控预警表格中实时插入新行并添加闪烁动画（CSS `@keyframes flash`），实现自动重连逻辑（最多 5 次，间隔递增）
  - [x] 2.6 编写属性测试（追加到 `tests/properties/test_risk_gateway_properties.py`），验证 Property 13（止损预警消息完整性）和 Property 14（非交易时段预警抑制）

## 阶段二：P1 — 黑白名单持久化 + ATR 止损 + 总仓位控制

- [x] 3. 黑白名单持久化存储（需求 3）
  - [x] 3.1 修改 `app/services/risk_controller.py` 中 `BlackWhiteListManager`，新增 `_cache` 属性（dict[str, set[str]]）和 `load_from_db()` 异步方法，启动时从 `stock_list` 表加载数据到内存缓存
  - [x] 3.2 修改 `BlackWhiteListManager` 的 `add_to_blacklist()`/`add_to_whitelist()` 方法为异步方法，同时写入内存缓存和数据库，数据库写入失败时回滚内存变更
  - [x] 3.3 修改 `BlackWhiteListManager` 的 `remove_from_blacklist()`/`remove_from_whitelist()` 方法为异步方法，同时从内存缓存和数据库删除，数据库删除失败时回滚内存变更
  - [x] 3.4 新增 `is_blacklisted_pure(symbol, blacklist_set)` 和 `is_whitelisted_pure(symbol, whitelist_set)` 静态方法，用于属性测试
  - [x] 3.5 修改 `app/api/v1/risk.py` 中黑白名单 CRUD 端点，调用 `BlackWhiteListManager` 的异步方法替代直接数据库操作
  - [x] 3.6 编写属性测试 `tests/properties/test_blackwhitelist_persistence_properties.py`，验证 Property 12（黑白名单操作序列一致性）

- [x] 4. 个股 ATR 自适应止损参数（需求 4）
  - [x] 4.1 在 `app/core/schemas.py` 中新增 `StopLossMode` 枚举（FIXED/ATR_ADAPTIVE），扩展止损配置数据类新增 `mode`、`atr_fixed_multiplier`、`atr_trailing_multiplier` 字段
  - [x] 4.2 在 `app/services/risk_controller.py` 的 `StopLossChecker` 中新增 `compute_atr_fixed_stop_price(cost_price, atr, multiplier)` 和 `compute_atr_trailing_retrace_pct(atr, peak_price, multiplier)` 静态方法
  - [x] 4.3 新增 `compute_atr_stop_loss_pure(cost_price, current_price, peak_price, atr, fixed_multiplier, trailing_multiplier)` 纯函数，同时计算固定止损和移动止损触发状态
  - [x] 4.4 修改 `app/api/v1/risk.py` 中 `StopConfigRequest`/`StopConfigResponse` Pydantic 模型，新增 `mode`、`atr_fixed_multiplier`、`atr_trailing_multiplier` 字段，保持向后兼容
  - [x] 4.5 修改 `position_warnings` 端点中的止损检测逻辑，当配置为 ATR 模式时使用 ATR 计算方法替代固定比例
  - [x] 4.6 在 `frontend/src/views/RiskView.vue` 止损配置区域新增止损模式切换控件（固定比例/ATR 自适应），ATR 模式下显示倍数输入框并隐藏固定比例输入框
  - [x] 4.7 编写属性测试 `tests/properties/test_atr_stop_loss_properties.py`，验证 Property 3（ATR 自适应止损计算正确性与范围不变量）

- [x] 5. 总仓位控制（需求 5）
  - [x] 5.1 在 `app/services/risk_controller.py` 的 `PositionRiskChecker` 中新增 `compute_total_position_pct(total_market_value, available_cash)` 静态方法，实现总仓位比例计算公式
  - [x] 5.2 新增 `check_total_position_limit(total_market_value, available_cash, limit_pct)` 静态方法，返回 `RiskCheckResult`
  - [x] 5.3 新增 `get_total_position_limit_by_risk_level(risk_level)` 静态方法，实现 NORMAL→80%、CAUTION→60%、DANGER→30% 映射
  - [x] 5.4 在 `RiskGateway.check_order_risk_pure()` 的校验链中新增总仓位检查步骤
  - [x] 5.5 在 `app/api/v1/risk.py` 中新增 `GET /risk/total-position` 端点，返回当前总仓位比例、持仓总市值、可用现金和仓位上限
  - [x] 5.6 在 `frontend/src/views/RiskView.vue` 大盘风控状态卡片下方新增总仓位状态区域，显示仓位比例进度条、仓位上限和可用现金
  - [x] 5.7 编写属性测试 `tests/properties/test_total_position_properties.py`，验证 Property 4（总仓位比例范围不变量）和 Property 5（大盘风险等级与总仓位上限映射）

## 阶段三：P2 — 行业分类 + 破位优化 + 策略实盘监控

- [x] 6. 板块仓位使用真实行业分类（需求 6）
  - [x] 6.1 在 `app/models/stock.py` 的 `StockInfo` 模型中新增 `industry_code`（String(10)）和 `industry_name`（String(50)）字段，创建 Alembic 迁移脚本
  - [x] 6.2 在 `app/services/risk_controller.py` 的 `PositionRiskChecker` 中新增 `compute_industry_positions_pure(positions, industry_map)` 静态方法，按申万一级行业汇总持仓市值并计算各行业仓位占比，缺失行业数据的股票归入「未分类」
  - [x] 6.3 修改 `app/api/v1/risk.py` 中 `risk_check` 和 `position_warnings` 端点的板块仓位检查逻辑，从查询 `StockInfo.board` 改为查询 `StockInfo.industry_code`
  - [x] 6.4 修改前端预警表格中「板块仓位超限」的显示文案，从「板块仓位超限」改为显示具体行业名称（如「银行行业仓位超限」）
  - [x] 6.5 编写属性测试 `tests/properties/test_industry_position_properties.py`，验证 Property 6（行业仓位加和不变量）

- [x] 7. 破位检测条件优化（需求 7）
  - [x] 7.1 在 `app/services/risk_controller.py` 的 `PositionRiskChecker` 中新增 `check_position_breakdown_relaxed(current_price, ma20, daily_change_pct, volume_ratio)` 静态方法，实现三个条件满足其中两个即触发的放宽逻辑
  - [x] 7.2 新增 `check_consecutive_decline_pure(closes, n_days=3, threshold_pct=8.0)` 静态方法，检测连续 N 个交易日下跌且累计跌幅超过阈值
  - [x] 7.3 修改 `position_warnings` 端点中的破位检测调用，使用 `check_position_breakdown_relaxed()` 替代原有 `check_position_breakdown()`，并新增连续阴跌检测调用
  - [x] 7.4 修改前端预警表格，区分显示「急跌破位预警」和「阴跌破位预警」两种预警类型
  - [x] 7.5 编写属性测试 `tests/properties/test_breakdown_properties.py`，验证 Property 7（放宽版破位检测三满足二）和 Property 8（连续阴跌检测局部性不变量）

- [x] 8. 策略实盘健康监控（需求 8）
  - [x] 8.1 在 `app/services/risk_controller.py` 中新增 `StrategyHealthMonitor` 类，实现 `compute_live_health_pure(trade_records, n=20)` 静态方法：取最近 N 笔交易计算胜率（盈利笔数/总笔数）和最大回撤，胜率 < 40% 或回撤 > 20% 判定为不健康，记录不足 N 笔时标注 data_sufficient=False
  - [x] 8.2 修改 `app/api/v1/risk.py` 中 `strategy_health` 端点，新增实盘交易记录查询（从 `trade_order` 表查询 status=FILLED 的记录），调用 `compute_live_health_pure()` 计算实盘指标，在响应中同时返回回测指标和实盘指标
  - [x] 8.3 修改 `StrategyHealthResponse` Pydantic 模型，新增 `live_win_rate`、`live_max_drawdown`、`live_is_healthy`、`live_data_sufficient` 字段
  - [x] 8.4 在 `frontend/src/views/RiskView.vue` 中新增策略健康状态区域（如果尚未存在），分两栏展示「回测表现」和「实盘表现」，各自显示胜率和最大回撤
  - [x] 8.5 编写属性测试 `tests/properties/test_strategy_health_properties.py`，验证 Property 9（策略实盘健康计算正确性）

## 阶段四：P3 — 扩展监控 + 事件日志 + 可视化 + 预警增强

- [x] 9. 扩展大盘风控监控指数（需求 9）
  - [x] 9.1 在 `app/services/risk_controller.py` 的 `MarketRiskChecker` 中新增 `check_multi_index_risk(index_data)` 方法，接受 `dict[str, list[float]]`（指数代码→收盘价序列），对每个指数调用 `check_market_risk()`，取最严重等级作为综合风险等级，空数据的指数跳过
  - [x] 9.2 修改 `app/api/v1/risk.py` 中 `risk_overview` 端点，查询 4 个指数（000001.SH、399006.SZ、000300.SH、000905.SH）的 K 线数据，调用 `check_multi_index_risk()`，在响应中返回所有指数的均线状态
  - [x] 9.3 扩展 `RiskOverviewResponse` Pydantic 模型，新增 `indices` 列表字段（每个元素包含 index_code、index_name、above_ma20、above_ma60、risk_level）
  - [x] 9.4 修改 `frontend/src/views/RiskView.vue` 大盘风控状态卡片，展示所有监控指数的均线状态（每个指数一行）
  - [x] 9.5 编写属性测试 `tests/properties/test_multi_index_risk_properties.py`，验证 Property 10（多指数风控最严重等级聚合）

- [x] 10. 风控事件历史日志（需求 10）
  - [x] 10.1 在 `app/models/` 中新增 `risk_event.py`，定义 `RiskEventLog` ORM 模型（id、user_id、event_type、symbol、rule_name、trigger_value、threshold、result、triggered_at、created_at），创建 Alembic 迁移脚本
  - [x] 10.2 在 `app/services/risk_controller.py` 中新增 `RiskEventLogger` 类，实现 `build_event_record()` 静态方法构建事件记录字典，实现 `log_event()` 异步方法将事件写入数据库
  - [x] 10.3 在 `RiskGateway.check_and_submit()` 中，当委托被拒绝时调用 `RiskEventLogger.log_event()` 记录拒绝事件；在 `position_warnings` 端点中，当检测到预警时记录预警事件
  - [x] 10.4 在 `app/api/v1/risk.py` 中新增 `GET /risk/event-log` 端点，支持按时间范围（start_date/end_date）、事件类型（event_type）和股票代码（symbol）筛选查询，返回分页结果
  - [x] 10.5 在 `frontend/src/views/RiskView.vue` 中新增「风控日志」区域，以表格形式展示风控事件历史记录，支持按时间范围筛选
  - [x] 10.6 实现 90 天数据自动清理：在 Celery Beat 中新增每日清理任务，删除 `triggered_at` 超过 90 天的记录
  - [x] 10.7 编写属性测试（追加到 `tests/properties/test_risk_gateway_properties.py`），验证 Property 15（风控事件记录完整性）

- [x] 11. 大盘风控趋势可视化（需求 11）
  - [x] 11.1 在 `app/api/v1/risk.py` 中新增 `GET /risk/index-kline` 端点，接受 `symbol` 查询参数，返回指定指数最近 60 个交易日的 OHLC 数据（time、open、high、low、close）以及 MA20/MA60 值
  - [x] 11.2 在 `frontend/src/views/RiskView.vue` 大盘风控状态卡片中新增指数 K 线迷你图区域，使用 ECharts 渲染上证指数和创业板指的日 K 线，叠加 MA20（绿色/红色随站上/跌破变化）和 MA60 均线
  - [x] 11.3 实现 K 线迷你图的悬停交互：显示该交易日的日期、OHLC 和 MA20/MA60 值

- [x] 12. 持仓预警表信息增强（需求 12）
  - [x] 12.1 修改 `app/api/v1/risk.py` 中 `PositionWarningItem` Pydantic 模型，新增 `cost_price`、`current_price`、`pnl_pct`、`suggested_action` 字段
  - [x] 12.2 在 `app/services/risk_controller.py` 中新增 `get_suggested_action(warning_type)` 静态方法，实现预警类型到建议操作的映射：固定止损触发→「建议止损卖出」、移动止损触发→「建议减仓」、破位预警→「建议关注，考虑减仓」、仓位超限→「建议不再加仓」
  - [x] 12.3 修改 `position_warnings` 端点，在每个预警条目中填充 cost_price、current_price、pnl_pct（盈亏比例）和 suggested_action
  - [x] 12.4 修改 `frontend/src/views/RiskView.vue` 仓位风控预警表格，新增「成本价」「盈亏」「建议操作」三列，盈亏列以百分比显示（盈利绿色/亏损红色），建议操作列以彩色标签显示
  - [x] 12.5 编写属性测试 `tests/properties/test_suggested_action_properties.py`，验证 Property 11（预警建议操作映射正确性）
