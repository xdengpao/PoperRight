# Implementation Plan: Screening Parameter Optimization

## Overview

本实现计划将 11 项选股管线参数优化需求分解为可增量执行的编码任务。任务按依赖顺序排列：先修改数据模型与配置默认值，再实现各模块核心逻辑变更，然后集成到执行器层，最后添加 API 端点和前端展示。每个任务引用具体需求条款，属性测试引用设计文档中的正确性属性编号。

## Tasks

- [x] 1. 数据模型与配置默认值变更
  - [x] 1.1 修改 `app/core/schemas.py` 中的配置默认值
    - 将 `IndicatorParamsConfig.rsi_lower` 默认值从 50 改为 55
    - 将 `IndicatorParamsConfig.rsi_upper` 默认值从 80 改为 75
    - 将 `MaTrendConfig.trend_score_threshold` 默认值从 80 改为 68
    - 在 `VolumePriceConfig` 中新增 `money_flow_mode: str = "relative"` 和 `relative_threshold_pct: float = 5.0` 字段
    - 更新 `VolumePriceConfig.to_dict()` 和 `from_dict()` 以序列化/反序列化新字段（向后兼容）
    - _Requirements: 3.1, 6.6, 10.1, 10.3_

  - [x] 1.2 新增 MACD/BOLL/RSI 结构化结果数据类到 `app/services/screener/indicators.py`
    - 新增 `MACDSignalResult` dataclass（signal, strength, signal_type, dif, dea, macd）
    - 新增 `BOLLSignalResult` dataclass（signal, near_upper_band, hold_days, upper, middle, lower）
    - 新增 `RSISignalResult` dataclass（signal, current_rsi, consecutive_rising, values）
    - 导入 `SignalStrength` 枚举
    - _Requirements: 1.4, 2.4, 3.4_

  - [x] 1.3 扩展 `app/services/screener/breakout.py` 中 `BreakoutSignal` 数据类
    - 新增 `volume_sustained: bool | None = None` 字段
    - 新增 `consolidation_bonus: bool = False` 字段
    - _Requirements: 7.4_

  - [x] 1.4 为数据模型变更编写单元测试
    - 测试 `VolumePriceConfig.to_dict()` / `from_dict()` 新字段序列化与向后兼容
    - 测试 `MaTrendConfig` 默认值为 68
    - 测试 `IndicatorParamsConfig` RSI 默认区间为 [55, 75]
    - _Requirements: 3.1, 6.6, 10.3_

- [x] 2. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 3. MACD 信号条件放宽（Req 1）
  - [x] 3.1 实现 `_count_below_zero_golden_crosses` 辅助函数
    - 在 `app/services/screener/indicators.py` 中新增纯函数
    - 统计最近 lookback（默认 60）天内零轴下方金叉次数
    - 金叉定义：DIF[i-1] <= DEA[i-1] 且 DIF[i] > DEA[i] 且 DIF[i] < 0
    - _Requirements: 1.2, 1.5_

  - [x] 3.2 重构 `detect_macd_signal` 函数返回 `MACDSignalResult`
    - 零轴上方金叉：DIF > 0, DEA > 0, DIF 上穿 DEA, MACD 红柱放大 → signal=True, strength=STRONG, signal_type="above_zero"
    - 零轴下方二次金叉：调用 `_count_below_zero_golden_crosses` 判断是否为第二次 → signal=True, strength=WEAK, signal_type="below_zero_second"
    - 零轴下方首次金叉：signal=False
    - DEA 趋势向上作为强度修饰符：DEA[last] > DEA[prev] 时 strength 提升一级（WEAK→MEDIUM, MEDIUM→STRONG, STRONG 不变）
    - 移除 DEA 向上作为信号触发的硬性条件
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 3.3 编写 MACD 信号属性测试
    - **Property 1: MACD 信号类型与强度分类**
    - **Property 2: DEA 趋势向上提升信号强度**
    - 测试文件：`tests/properties/test_macd_signal_props.py`
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

  - [x] 3.4 编写 MACD 信号单元测试
    - 测试文件：`tests/services/test_indicators_macd.py`
    - 覆盖：零轴上方金叉、零轴下方二次金叉、首次金叉不触发、DEA 修饰符、数据不足
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 4. BOLL 信号逻辑修正（Req 2）
  - [x] 4.1 重构 `detect_boll_signal` 函数返回 `BOLLSignalResult`
    - 主信号条件：当日收盘价 > 中轨 AND 前一日收盘价 > 前一日中轨（连续 2 日站稳）→ signal=True
    - 风险提示：当日收盘价 >= 上轨 × 0.98 → near_upper_band=True（独立于 signal）
    - hold_days 计算：从最新一天向前扫描连续收盘价 > 中轨的天数
    - 移除原有"触碰上轨"作为买入条件的逻辑
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 4.2 编写 BOLL 信号属性测试
    - **Property 3: BOLL 信号需要连续 2 日站稳中轨**
    - **Property 4: BOLL 接近上轨风险标记**
    - 测试文件：`tests/properties/test_boll_signal_props.py`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [x] 4.3 编写 BOLL 信号单元测试
    - 测试文件：`tests/services/test_indicators_boll.py`
    - 覆盖：2 日站稳触发、1 日不触发、上轨风险标记独立性、数据不足
    - _Requirements: 2.1, 2.2, 2.3_

- [x] 5. RSI 区间收窄与趋势方向检查（Req 3）
  - [x] 5.1 修改 `detect_rsi_signal` 函数签名和逻辑，返回 `RSISignalResult`
    - 默认强势区间改为 [55, 75]（通过 `lower_bound` 和 `upper_bound` 参数）
    - 新增 `rising_days: int = 3` 参数
    - 信号条件：RSI 在 [lower, upper] 区间内 AND 最近 rising_days 天 RSI 严格递增 AND 无超买背离
    - 数据不足时（可用天数 < rising_days + period）返回 signal=False
    - 返回 `RSISignalResult`（含 current_rsi, consecutive_rising）
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 5.2 编写 RSI 信号属性测试
    - **Property 5: RSI 信号需要区间内且连续上升**
    - 测试文件：`tests/properties/test_rsi_signal_props.py`
    - **Validates: Requirements 3.2, 3.3, 3.5**

  - [x] 5.3 编写 RSI 信号单元测试
    - 测试文件：`tests/services/test_indicators_rsi.py`
    - 覆盖：[55,75] 区间、连续上升 3 天、自定义 rising_days、数据不足
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 7. MA 趋势评分权重优化（Req 4）
  - [x] 7.1 实现 `_bell_curve_distance_score` 纯函数
    - 在 `app/services/screener/ma_trend.py` 中新增
    - 钟形曲线规则：[0%, 3%] → 100 分，(3%, 5%] → 线性递减至 60，(5%, 10%] → 线性递减至 20，>10% → 20 分，<0% → 线性递减至 0（-5% 时为 0）
    - _Requirements: 4.1, 4.4_

  - [x] 7.2 修改 `score_ma_trend` 中的距离分和斜率权重计算
    - 距离分使用 `_bell_curve_distance_score` 替代原有线性映射
    - 斜率权重：短期均线（5 日、10 日）权重系数 2.0，中期（20 日）和长期（60 日、120 日）权重系数 1.0
    - 加权平均斜率 = Σ(slope_i × weight_i) / Σ(weight_i)
    - 保持总评分在 [0, 100] 闭区间
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 7.3 编写 MA 趋势评分属性测试
    - **Property 6: MA 趋势距离分钟形曲线形状**
    - **Property 7: MA 趋势短期均线斜率优先**
    - **Property 8: MA 趋势评分范围不变量与幂等性**
    - 测试文件：`tests/properties/test_ma_trend_props.py`
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [x] 7.4 编写 MA 趋势评分单元测试
    - 测试文件：`tests/services/test_ma_trend.py`
    - 覆盖：钟形曲线各区间边界值、短期斜率权重 2 倍验证、评分范围 [0, 100]
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 8. 模块评分权重差异化与共振加分（Req 5）
  - [x] 8.1 新增 `_compute_indicator_score` 静态纯函数到 `app/services/screener/screen_executor.py`
    - 差异化权重：MACD=35, RSI=25, BOLL=20, DMA=20
    - 共振加分：count < 2 → 0, count == 2 → +10, count >= 3 → +20
    - 返回 min(base_score + resonance_bonus, 100.0)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 8.2 修改 `_execute` 方法中 indicator_params 模块评分逻辑
    - 替换原有每个信号 +25 的逻辑，改为调用 `_compute_indicator_score`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 8.3 编写技术指标评分属性测试
    - **Property 9: 技术指标差异化权重与共振加分**
    - 测试文件：`tests/properties/test_indicator_score_props.py`
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

  - [x] 8.4 编写技术指标评分单元测试
    - 测试文件：`tests/services/test_screen_executor.py`（追加测试用例）
    - 覆盖：单指标无共振、2 指标 +10、3 指标 +20、4 指标 +20 且不超 100
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9. 资金流信号阈值相对化（Req 6）
  - [x] 9.1 新增 `check_money_flow_signal_relative` 纯函数到 `app/services/screener/volume_price.py`
    - 参数：daily_inflows, daily_amounts, relative_threshold_pct=5.0, consecutive=2, amount_period=20
    - 计算 avg_daily_amount = mean(daily_amounts[-amount_period:])
    - 信号条件：net_inflow / avg_daily_amount >= relative_threshold_pct% 连续 consecutive 天
    - avg_daily_amount <= 0 时返回 signal=False 并标记 fallback_needed
    - 保留原 `check_money_flow_signal` 函数不变（向后兼容）
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 9.2 编写相对资金流属性测试
    - **Property 10: 相对资金流信号**
    - 测试文件：`tests/properties/test_money_flow_props.py`
    - **Validates: Requirements 6.1, 6.3**

  - [x] 9.3 编写资金流信号单元测试
    - 测试文件：`tests/services/test_volume_price.py`（追加测试用例）
    - 覆盖：相对阈值触发、回退逻辑、向后兼容、数据不足
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 10. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 11. 突破信号成交量持续性验证（Req 7）
  - [x] 11.1 新增 `check_volume_sustainability` 和 `check_consolidation_bonus` 纯函数到 `app/services/screener/breakout.py`
    - `check_volume_sustainability`：连续 2 日 >= breakout_volume × 70% → True，任一日 < 50% → False，数据不足 → None
    - `check_consolidation_bonus`：box_period_days >= 30 → True
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [x] 11.2 编写突破成交量持续性属性测试
    - **Property 11: 突破成交量持续性分类**
    - **Property 12: 突破横盘整理加分**
    - 测试文件：`tests/properties/test_breakout_props.py`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.5**

  - [x] 11.3 编写突破信号单元测试
    - 测试文件：`tests/services/test_breakout.py`（追加测试用例）
    - 覆盖：成交量持续性三种状态、横盘加分边界值、突破日成交量为 0
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 12. 市场风控多维度增强（Req 8）
  - [x] 12.1 扩展 `MarketRiskChecker.check_market_risk` 方法签名和逻辑
    - 在 `app/services/risk_controller.py` 中修改
    - 新增参数：market_breadth (float | None), volume_change_rate (float | None), breadth_threshold (float = 0.5)
    - 先用现有均线逻辑计算基础风险等级
    - 若 market_breadth 可用且 < breadth_threshold，风险等级提升一级（NORMAL→CAUTION, CAUTION→DANGER）
    - market_breadth 为 None 时仅使用均线判定（降级为现有逻辑）
    - _Requirements: 8.1, 8.2, 8.5_

  - [x] 12.2 修改 `ScreenExecutor._apply_risk_filters_pure` 中 DANGER 分支逻辑
    - DANGER 模式下从返回空列表改为仅允许 trend_score >= 95 的强势股通过
    - 新增配置参数 `danger_strong_threshold: float = 95.0`
    - _Requirements: 8.3, 8.4_

  - [x] 12.3 编写多维度风控属性测试
    - **Property 13: 多维度市场风险评估**
    - **Property 14: DANGER 模式允许强势股通过**
    - 测试文件：`tests/properties/test_risk_props.py`
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.5**

  - [x] 12.4 编写风控单元测试
    - 测试文件：`tests/services/test_risk_controller.py`（追加测试用例）
    - 覆盖：多维度风控升级、DANGER 强势股通过、广度数据不可用降级
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 13. 板块数据新鲜度检测（Req 9）
  - [x] 13.1 新增 `check_data_freshness` 静态纯函数到 `app/services/screener/sector_strength.py`
    - 参数：latest_data_date, current_date, warning_threshold_days=2, degrade_threshold_days=5
    - 返回 (should_warn, should_degrade, stale_days)
    - 使用简化工作日计算（排除周末）
    - _Requirements: 9.1, 9.2, 9.4_

  - [x] 13.2 在 `compute_sector_ranks` 方法中集成数据新鲜度检查
    - 查询到最新交易日后立即调用 `check_data_freshness`
    - should_warn=True 时记录 WARNING 日志（含数据源名称和最新数据日期）
    - should_degrade=True 时返回空排名列表并记录 WARNING 日志
    - _Requirements: 9.1, 9.2, 9.3, 9.5_

  - [x] 13.3 编写板块数据新鲜度属性测试
    - **Property 15: 板块数据新鲜度降级**
    - 测试文件：`tests/properties/test_sector_freshness_props.py`
    - **Validates: Requirements 9.2, 9.5**

  - [x] 13.4 编写板块数据新鲜度单元测试
    - 测试文件：`tests/services/test_sector_strength.py`（追加测试用例）
    - 覆盖：WARNING 阈值（2 天）、降级阈值（5 天）、周末跳过、自定义阈值
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 14. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 15. 趋势评分阈值降低与趋势加速信号（Req 10）
  - [x] 15.1 新增 `_detect_trend_acceleration` 静态纯函数到 `app/services/screener/screen_executor.py`
    - 参数：current_score, previous_score (float | None), acceleration_high=70.0, acceleration_low=60.0
    - 条件：current_score >= acceleration_high AND previous_score is not None AND previous_score < acceleration_low
    - _Requirements: 10.2, 10.5_

  - [x] 15.2 在 `_execute` 方法中集成趋势加速信号和新默认阈值
    - MA_TREND 信号使用 `MaTrendConfig.trend_score_threshold`（默认 68）
    - 当趋势加速触发时生成 `SignalDetail(category=MA_TREND, label="ma_trend_acceleration", strength=STRONG)`
    - 从 `stock_data` 中读取 `previous_ma_trend_score` 作为前一轮评分
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 15.3 编写趋势加速属性测试
    - **Property 16: 趋势加速信号**
    - 测试文件：`tests/properties/test_trend_acceleration_props.py`
    - **Validates: Requirements 10.2, 10.4, 10.5**

  - [x] 15.4 编写趋势加速单元测试
    - 测试文件：`tests/services/test_screen_executor.py`（追加测试用例）
    - 覆盖：加速信号触发、阈值 68 生效、无历史数据不触发、强度为 STRONG
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 16. 信号检测调用方适配
  - [x] 16.1 更新 `ScreenDataProvider` 中对 MACD/BOLL/RSI 检测函数的调用
    - 适配 `detect_macd_signal` 返回 `MACDSignalResult`，将 signal、strength、signal_type 写入 stock_data
    - 适配 `detect_boll_signal` 返回 `BOLLSignalResult`，将 signal、near_upper_band、hold_days 写入 stock_data
    - 适配 `detect_rsi_signal` 返回 `RSISignalResult`，将 signal、current_rsi、consecutive_rising 写入 stock_data
    - _Requirements: 1.4, 2.4, 3.4_

  - [x] 16.2 更新 `ScreenExecutor._execute` 中信号构建逻辑
    - MACD 信号使用新的 strength 和 signal_type 字段
    - BOLL 信号在 near_upper_band=True 时附加风险提示到 description
    - RSI 信号使用新的 current_rsi 字段生成描述文本
    - 更新 `_generate_signal_description` 以支持新字段
    - _Requirements: 1.4, 2.2, 2.4, 3.4_

- [x] 17. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 18. 因子注册表完善与 API 端点（Req 11 后端）
  - [x] 18.1 完善 `app/services/screener/factor_registry.py` 中因子元数据
    - 确保所有 19 个因子的 description 字段非空
    - 补充缺失的 examples 列表（至少为每个因子提供 1 个配置示例）
    - _Requirements: 11.1, 11.6_

  - [x] 18.2 新增因子使用说明 API 端点到 `app/api/v1/screen.py`
    - `GET /api/v1/screen/factors` — 返回所有因子元数据（按 category 分组），复用现有 `get_factor_registry` 逻辑
    - `GET /api/v1/screen/factors/{factor_name}/usage` — 返回单个因子的使用说明（description, examples, 推荐阈值）
    - 因子不存在时返回 HTTP 404 + 描述性错误信息
    - _Requirements: 11.2, 11.3, 11.4, 11.5_

  - [x] 18.3 编写因子注册表完整性属性测试
    - **Property 17: 因子注册表完整性**
    - 测试文件：`tests/properties/test_factor_registry_props.py`
    - **Validates: Requirements 11.1, 11.6**

  - [x] 18.4 编写因子 API 单元测试
    - 测试文件：`tests/api/test_screen_factors.py`
    - 覆盖：因子列表返回、单因子使用说明、404 错误、category 筛选
    - _Requirements: 11.3, 11.4, 11.5_

- [x] 19. 因子使用说明前端面板（Req 11 前端）
  - [x] 19.1 在 `frontend/src/views/ScreenerView.vue` 中实现因子使用说明面板
    - 当用户在因子条件编辑器中选择一个因子时，调用 `GET /api/v1/screen/factors/{factor_name}/usage` 获取数据
    - 展示面板内容：description（描述文本）、examples（配置示例列表）、推荐阈值范围（default_threshold 或 default_range）
    - 面板在因子选择变化时自动更新
    - 处理加载状态和错误状态
    - _Requirements: 11.2, 11.3_

  - [x] 19.2 编写因子使用说明面板前端测试
    - 测试文件：`frontend/src/views/__tests__/FactorUsagePanel.test.ts`
    - 覆盖：面板展示、API 调用 mock、空状态、因子切换联动
    - _Requirements: 11.2, 11.3_

- [x] 20. Final checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.
  - 运行 `pytest` 验证后端全量测试
  - 运行 `npm test` 验证前端测试（在 frontend/ 目录下）

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation after logical groups of changes
- All comments and docstrings should be in Chinese (中文)
- Backend property tests use Hypothesis (`tests/properties/`), frontend uses fast-check
