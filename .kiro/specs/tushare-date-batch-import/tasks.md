# 实现计划：Tushare 日期分批导入优化

## 概述

本实现计划将 Tushare 日期分批导入优化功能分解为可增量执行的编码任务。采用自底向上的构建顺序：先扩展注册表元数据 → 创建独立的日期拆分器（含属性测试） → 增强导入引擎路由和日期分批处理 → 截断检测 → 进度报告增强 → 日志持久化增强 → 集成测试。每个任务构建在前一个任务之上，确保无孤立代码。

## Tasks

- [x] 1. 注册表元数据扩展
  - [x] 1.1 在 ApiEntry 数据类中新增 `batch_by_date` 和 `date_chunk_days` 字段
    - 在 `app/services/data_engine/tushare_registry.py` 的 `ApiEntry` 数据类中新增 `batch_by_date: bool = False` 和 `date_chunk_days: int = 30` 两个字段
    - 默认值确保向后兼容，现有 127 个接口的 `register()` 调用无需修改即可正常工作
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 为第一类接口（required DATE_RANGE）配置日期分批参数
    - 为需求文档接口分析表第一类中列出的全部 required DATE_RANGE 接口的 `register()` 调用添加 `batch_by_date=True` 和对应的 `date_chunk_days` 值
    - 包括：stk_premarket(1), st(60), daily_basic(1), stk_limit(1), suspend_d(150), hsgt_top10(150), ggt_top10(150), ggt_daily(365), stk_shock(300), stk_high_shock(365), stk_alert(300), cyq_perf(1), cyq_chips(1), stk_factor_pro(1), ccass_hold(15), ccass_hold_detail(15), hk_hold(1), stk_auction_o(1), stk_auction_c(1), stk_nineturn(60), stk_ah_comparison(30), margin(365), margin_detail(1), slb_len(365), moneyflow_cnt_ths(10), moneyflow_ind_ths(100), moneyflow_ind_dc(100), moneyflow_mkt_dc(365), moneyflow_hsgt(365), limit_list_ths(15), limit_list_d(15), limit_step(100), limit_cpt_list(150), ths_daily(6), dc_daily(6), stk_auction(1), hm_detail(30), ths_hot(30), dc_hot(30), tdx_daily(6), kpl_list(30), index_dailybasic(60), idx_factor_pro(160), daily_info(365), sz_daily_info(365), index_global(130), sw_daily(130), ci_daily(130), bak_daily(1), rt_k(1), rt_min(1), rt_min_daily(1)
    - 确保每个接口的 `date_chunk_days x 每日预估行数 < max_rows` 约束成立
    - _Requirements: 1.3, 1.4, 1.7_

  - [x] 1.3 为第二类接口（optional DATE_RANGE）配置日期分批参数
    - 为需求文档接口分析表第二类中列出的全部 optional DATE_RANGE 接口的 `register()` 调用添加 `batch_by_date=True` 和对应的 `date_chunk_days` 值
    - 包括：pledge_stat(6), pledge_detail(15), repurchase(60), share_float(60), block_trade(30), stk_holdernumber(15), report_rc(30), stk_surv(60)
    - _Requirements: 1.3, 1.5, 1.7_

  - [x] 1.4 为第三类接口（use_trade_date_loop）配置日期分批参数
    - 为 `top_list` 和 `top_inst` 的 `register()` 调用添加 `batch_by_date=True` 和 `date_chunk_days=1`
    - 这两个接口使用 `trade_date` 单日参数，与 `use_trade_date_loop=True` 配合逐日调用
    - _Requirements: 1.6_

  - [x] 1.5 为 stk_mins 配置双重分批参数
    - 为 `stk_mins` 的 `register()` 调用添加 `batch_by_date=True` 和 `date_chunk_days=12`（单只股票 1 分钟频率每日约 240 行，12x240=2880 < 3000）
    - 该接口已有 `batch_by_code=True`，同时标记 `batch_by_date=True` 将触发双重分批
    - _Requirements: 1.8_

- [x] 2. 日期分批拆分器
  - [x] 2.1 创建 DateBatchSplitter 工具类
    - 新建 `app/services/data_engine/date_batch_splitter.py`
    - 实现 `DateBatchSplitter` 类，包含静态方法 `split(start_date, end_date, chunk_days) -> list[tuple[str, str]]`
    - 输入：start_date/end_date 为 YYYYMMDD 格式字符串，chunk_days 为正整数
    - 输出：连续无重叠的 (chunk_start, chunk_end) 元组列表
    - 参数验证：start_date > end_date 或 chunk_days <= 0 时抛出 ValueError
    - 边界处理：start_date == end_date 返回单元素列表；范围 < chunk_days 返回单元素列表
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 2.2 编写 DateBatchSplitter 属性测试 — Property 1: 子区间跨度上界
    - **Property 1: 子区间跨度上界**
    - 在 `tests/properties/test_date_batch_splitter_properties.py` 中使用 Hypothesis 编写属性测试
    - 生成器：`st.dates(min_value=date(2000,1,1), max_value=date(2030,12,31))` 生成 start/end，`st.integers(min_value=1, max_value=3650)` 生成 chunk_days，`assume(start <= end)`
    - 断言：每个子区间 (chunk_end - chunk_start + 1 天) <= chunk_days
    - 最少 100 次迭代
    - **Validates: Requirements 2.2**

  - [x] 2.3 编写 DateBatchSplitter 属性测试 — Property 2: 连续无重叠边界对齐
    - **Property 2: 子区间连续无重叠且边界对齐**
    - 断言：第一个子区间 chunk_start == start_date，最后一个子区间 chunk_end == end_date，相邻子区间 chunk_end + 1天 == 下一个 chunk_start
    - **Validates: Requirements 2.3, 2.7**

  - [x] 2.4 编写 DateBatchSplitter 属性测试 — Property 3: 日期覆盖 Round-Trip
    - **Property 3: 日期覆盖 Round-Trip**
    - 断言：所有子区间展开的日期集合并集恰好等于 start_date 到 end_date 的完整日期集合
    - **Validates: Requirements 2.6**

  - [x] 2.5 编写 DateBatchSplitter 单元测试
    - 在 `tests/services/test_date_batch_splitter.py` 中编写单元测试
    - 测试场景：基本拆分（30天/10天步长→3个子区间）、单日范围、范围小于步长、步长为1逐日拆分、跨月跨年、无效输入（start > end → ValueError、chunk_days <= 0 → ValueError）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. 检查点 — 确保日期拆分器测试全部通过
  - 运行 `pytest tests/services/test_date_batch_splitter.py tests/properties/test_date_batch_splitter_properties.py`，确保所有测试通过，如有问题请询问用户。

- [x] 4. 导入引擎重构 — 分批策略路由与日期分批增强
  - [x] 4.1 重构 `_process_import` 分批策略路由逻辑
    - 在 `app/tasks/tushare_import.py` 中重构 `_process_import` 函数的分批策略选择逻辑
    - 实现优先级路由：(1) batch_by_code → _process_batched（若同时 batch_by_date 且有日期范围则双重分批）；(2) INDEX_CODE 且未指定 ts_code → _process_batched_index；(3) batch_by_date 且有日期范围 → _process_batched_by_date；(4) 兜底：未声明 batch_by_date 但运行时检测到 DATE_RANGE 参数且有日期范围 → 兜底日期分批 + WARNING 日志；(5) 以上均不满足 → _process_single
    - 将 `_RATE_LIMIT_MAP` 硬编码改为从 `app.core.config.settings` 读取（`rate_limit_kline`、`rate_limit_fundamentals`、`rate_limit_money_flow`）
    - _Requirements: 4.1, 4.2, 5.3_

  - [x] 4.2 增强 `_process_batched_by_date` 使用 DateBatchSplitter 和注册表配置
    - 将 `_process_batched_by_date` 中的内联 `_generate_date_chunks` 替换为 `DateBatchSplitter.split()`
    - 使用注册表的 `entry.date_chunk_days` 替代硬编码的 `_DATE_BATCH_DAYS = 30`
    - 使用注册表 `entry.extra_config.get("max_rows", 3000)` 替代硬编码的 `_TUSHARE_MAX_ROWS = 3000`
    - 保留 `_generate_date_chunks` 函数但标记为 deprecated，内部调用 `DateBatchSplitter.split()`
    - 处理 `use_trade_date_loop` 模式：将每个子区间的 start_date 转为 trade_date 参数
    - _Requirements: 3.1, 3.2, 4.3, 4.4_

  - [x] 4.3 实现 `_process_batched` 中的双重分批支持
    - 在 `_process_batched` 的代码分批循环内部，对于同时标记 `batch_by_date=True` 且用户提供了日期范围的接口，在每个 ts_code 的调用中额外按日期分批
    - 使用 `DateBatchSplitter.split()` 拆分日期范围，对每个 (ts_code, date_chunk) 组合逐批调用 API
    - _Requirements: 1.8, 4.1_

  - [x] 4.4 实现截断检测逻辑
    - 在 `app/tasks/tushare_import.py` 中新增 `check_chunk_config()` 预检查函数和 `check_truncation()` 运行时检测函数
    - 预检查：导入开始前验证 `date_chunk_days` 配置合理性，不合理时记录 WARNING 日志
    - 运行时检测：每个子区间 API 返回行数 >= max_rows 时记录 WARNING 日志
    - 连续截断检测：连续 3 个子区间截断时记录 ERROR 日志，建议减小步长
    - 在 `_process_batched_by_date` 中集成预检查和运行时截断检测
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 4.5 增强进度报告
    - 扩展 `_update_progress` 函数签名，新增 `batch_mode`、`truncation_warnings`、`needs_smaller_chunk` 参数
    - 在 `_process_batched_by_date` 中设置 `batch_mode="by_date"`，在 `_process_batched` 中设置 `batch_mode="by_code"` 或 `"by_code_and_date"`（双重分批时），在 `_process_batched_index` 中设置 `batch_mode="by_index"`，在 `_process_single` 中设置 `batch_mode="single"`
    - 截断时将截断信息追加到 `truncation_warnings` 列表
    - 连续截断时设置 `needs_smaller_chunk=true`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 4.6 编写属性测试 — Property 4: 分批策略路由优先级
    - **Property 4: 分批策略路由优先级**
    - 在 `tests/properties/test_date_batch_splitter_properties.py` 中使用 Hypothesis 编写属性测试
    - 生成器：自定义 `st.builds(ApiEntry, ...)` 生成随机 ApiEntry 配置（组合 batch_by_code、batch_by_date、required_params、optional_params），`st.fixed_dictionaries()` 生成用户参数
    - 断言：路由选择严格遵循优先级（代码分批 > 指数分批 > 日期分批 > 单次调用）
    - 提取路由判断逻辑为纯函数 `determine_batch_strategy()` 以便属性测试
    - **Validates: Requirements 4.1**

- [x] 5. 检查点 — 确保导入引擎重构测试通过
  - 运行 `pytest tests/tasks/test_tushare_import_date_batch.py tests/properties/test_date_batch_splitter_properties.py`，确保所有测试通过，如有问题请询问用户。

- [x] 6. 导入日志持久化增强与数据库迁移
  - [x] 6.1 在 TushareImportLog ORM 模型中新增 `extra_info` 列
    - 在 `app/models/tushare_import.py` 的 `TushareImportLog` 类中新增 `extra_info: Mapped[str | None] = mapped_column(String(2000), nullable=True)` 列
    - 用于存储 JSON 格式的分批统计信息（batch_mode、total_chunks、success_chunks、truncation_count、truncation_details）
    - _Requirements: 8.1_

  - [x] 6.2 创建 Alembic 迁移脚本
    - 运行 `alembic revision --autogenerate -m "add extra_info to tushare_import_log"` 生成迁移脚本
    - 验证迁移脚本内容正确（仅新增 extra_info 列）
    - _Requirements: 8.1_

  - [x] 6.3 增强 `_finalize_log` 函数支持分批统计
    - 扩展 `_finalize_log` 函数签名，新增 `batch_stats: dict | None = None` 参数
    - 将 batch_stats 序列化为 JSON 存入 `extra_info` 列
    - 在 `_process_batched_by_date` 完成时调用 `_finalize_log` 传入分批统计
    - 截断警告信息记录到 `error_message` 字段（最多前 10 个截断子区间）
    - _Requirements: 8.1, 8.2_

  - [x] 6.4 增强 `get_import_history` 返回分批统计信息
    - 在 `app/services/data_engine/tushare_import_service.py` 的 `get_import_history` 方法中，返回结果新增 `extra_info` 字段（解析 JSON）
    - _Requirements: 8.3_

- [x] 7. 导入引擎单元测试
  - [x] 7.1 编写日期分批路由和处理的单元测试
    - 在 `tests/tasks/test_tushare_import_date_batch.py` 中编写测试
    - 测试场景：日期分批路由（batch_by_date=True + 日期参数 → _process_batched_by_date）、兜底路由（未声明 batch_by_date 但有 DATE_RANGE → 兜底分批 + WARNING）、双重分批（batch_by_code + batch_by_date → 代码外层 + 日期内层）、use_trade_date_loop 参数转换
    - 使用 mock TushareAdapter 和 mock Redis
    - _Requirements: 3.1, 4.1, 4.2, 4.3_

  - [x] 7.2 编写截断检测和进度报告的单元测试
    - 测试场景：截断检测（返回 max_rows 行 → WARNING 日志）、连续截断（3 个子区间截断 → ERROR 日志 + needs_smaller_chunk）、停止信号（中途停止 → 返回已导入记录数）、Token 无效（-2001 → 立即终止）、进度更新（每个子区间后 Redis 进度正确更新）、频率限制从配置读取
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 5.1, 5.3, 6.1, 6.2, 6.3, 6.4_

- [x] 8. 最终检查点 — 确保所有测试通过
  - 运行 `pytest tests/services/test_date_batch_splitter.py tests/properties/test_date_batch_splitter_properties.py tests/tasks/test_tushare_import_date_batch.py`，确保所有测试通过，如有问题请询问用户。

## Notes

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保可追溯性
- 检查点任务确保增量验证，及时发现问题
- 属性测试验证核心纯函数（DateBatchSplitter）的通用正确性
- 单元测试验证具体场景和边界条件
- 注册表扩展涉及 60+ 个接口的 `register()` 调用修改，需仔细核对步长配置
