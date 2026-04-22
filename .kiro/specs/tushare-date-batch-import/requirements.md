# 需求文档：Tushare 日期分批导入优化

## 简介

对现有 Tushare 数据导入系统进行优化，为所有基于时间段的数据导入接口实现自动日期分批机制。Tushare API 单次调用存在行数上限（约 3000-5000 条，部分接口可达 8000 条），当用户请求大日期范围的数据时，系统需要自动将日期范围拆分为多个子区间逐批调用，确保数据完整性。同时，整体调用频率需严格遵守 Tushare API 的频率限制要求（kline: 0.18s, fundamentals: 0.40s, money_flow: 0.30s）。

当前系统已有按股票代码分批（`batch_by_code`）和按指数代码分批的逻辑，以及一个临时的 `_process_batched_by_date` 实现。本需求旨在系统化地分析全部 100+ 个接口，在注册表中声明式标注每个接口的日期分批配置，并在导入引擎中实现通用的日期分批处理机制。

## 术语表

- **Date_Batch_Splitter**：日期分批拆分器，负责将大日期范围按配置的步长拆分为多个子区间
- **API_Registry**：Tushare API 接口注册表（`tushare_registry.py`），以声明式方式定义每个接口的元数据
- **ApiEntry**：注册表中单个接口的注册信息数据类
- **Import_Task**：Celery 异步导入任务（`tushare_import.py`），执行实际的 API 调用和数据写入
- **Import_Service**：导入编排服务（`tushare_import_service.py`），负责参数校验、Token 路由和任务分发
- **Rate_Limiter**：API 调用频率限制器，按 RateLimitGroup 分组控制调用间隔
- **RateLimitGroup**：频率限制分组枚举，包含 kline（0.18s）、fundamentals（0.40s）、money_flow（0.30s）三组
- **Tushare_Row_Limit**：Tushare 单次 API 调用返回的最大行数上限，默认 3000 条，部分接口可通过 `max_rows` 自定义（如 index_daily: 8000, sw_daily: 4000, sz_daily_info: 2000）
- **Date_Chunk**：日期子区间，由 (chunk_start, chunk_end) 组成的 YYYYMMDD 格式日期对
- **Chunk_Days**：每个日期子区间的天数步长，不同接口根据数据密度配置不同步长，需满足约束：`chunk_days x 每日预估行数 < max_rows`
- **Truncation_Warning**：截断警告，当单个子区间返回行数达到 Tushare 行数上限时发出的日志警告
- **batch_by_date**：注册表中新增的布尔标志，标识该接口是否需要按日期自动分批
- **date_chunk_days**：注册表中新增的整数配置，指定接口的日期分批步长（天数）
- **ParamType.DATE_RANGE**：注册表中的参数类型枚举值，标识接口支持 start_date/end_date 日期范围参数
- **use_trade_date_loop**：注册表 extra_config 中的特殊标志，标识接口使用 trade_date 单日循环而非 start_date/end_date 范围查询
- **max_rows**：注册表 extra_config 中的可选字段，自定义该接口的单次返回行数上限阈值（覆盖默认的 3000）

## 接口分析

### 步长配置约束

所有接口的 `date_chunk_days` 配置必须满足以下约束：

```
date_chunk_days x 每日预估行数 < max_rows（默认 3000）
```

例如：每日约 5000 行的接口，单日数据就可能超过 3000 行上限，必须配置 `date_chunk_days=1`（按单日查询）或使用 `batch_by_code` 按个股分批。

### 已有 max_rows 自定义配置的接口

以下接口在注册表 extra_config 中已配置了自定义 max_rows，截断检测应使用对应阈值：

| 接口名 | max_rows | 说明 |
|---------|----------|------|
| index_daily | 8000 | 指数日线行情（batch_by_code） |
| index_weekly | 8000 | 指数周线行情 |
| index_monthly | 8000 | 指数月线行情 |
| idx_mins | 8000 | 指数分钟行情 |
| idx_factor_pro | 8000 | 指数技术面因子 |
| sw_daily | 4000 | 申万行业指数日行情 |
| ci_daily | 4000 | 中信行业指数日行情 |
| daily_info | 4000 | 沪深市场每日交易统计 |
| index_global | 4000 | 国际主要指数 |
| sz_daily_info | 2000 | 深圳市场每日交易情况 |
| index_member_all | 2000 | 申万行业成分 |
| ci_index_member | 5000 | 中信行业成分 |

### 需要日期分批的接口分类

经过对注册表中全部接口的系统分析，以下接口需要启用日期分批机制：

**第一类：required DATE_RANGE — 纯日期范围查询（使用 start_date/end_date）**

| 接口名 | 中文说明 | 频率组 | 每日预估行数 | max_rows | 建议步长(天) | 步长依据 |
|---------|----------|--------|-------------|----------|-------------|---------|
| stk_premarket | 每日股本盘前 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限，需逐日查询 |
| st | ST风险警示板 | fundamentals | ~50 | 3000 | 60 | 60x50=3000 |
| daily_basic | 每日指标 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限，需逐日查询 |
| stk_limit | 每日涨跌停价格 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限，需逐日查询 |
| suspend_d | 每日停复牌信息 | fundamentals | ~20 | 3000 | 150 | 150x20=3000 |
| hsgt_top10 | 沪深股通十大成交股 | fundamentals | ~20 | 3000 | 150 | 150x20=3000 |
| ggt_top10 | 港股通十大成交股 | fundamentals | ~20 | 3000 | 150 | 150x20=3000 |
| ggt_daily | 港股通每日成交统计 | fundamentals | ~1 | 3000 | 365 | 365x1=365 |
| stk_shock | 个股异常波动 | fundamentals | ~10 | 3000 | 300 | 300x10=3000 |
| stk_high_shock | 个股严重异常波动 | fundamentals | ~5 | 3000 | 365 | 365x5=1825 |
| stk_alert | 交易所重点提示证券 | fundamentals | ~10 | 3000 | 300 | 300x10=3000 |
| cyq_perf | 每日筹码及胜率 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限，需逐日查询 |
| cyq_chips | 每日筹码分布 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限，需逐日查询 |
| stk_factor_pro | 股票技术面因子 | kline | ~5000 | 3000 | 1 | 单日即可能超限，需逐日查询 |
| ccass_hold | 中央结算系统持股统计 | fundamentals | ~200 | 3000 | 15 | 15x200=3000 |
| ccass_hold_detail | 中央结算系统持股明细 | fundamentals | ~200 | 3000 | 15 | 15x200=3000 |
| hk_hold | 沪深股通持股明细 | fundamentals | ~3000 | 3000 | 1 | 单日即达上限 |
| stk_auction_o | 股票开盘集合竞价 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限 |
| stk_auction_c | 股票收盘集合竞价 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限 |
| stk_nineturn | 神奇九转指标 | fundamentals | ~50 | 3000 | 60 | 60x50=3000 |
| stk_ah_comparison | AH股比价 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| margin | 融资融券汇总 | money_flow | ~2 | 3000 | 365 | 365x2=730 |
| margin_detail | 融资融券交易明细 | money_flow | ~2000 | 3000 | 1 | 单日即接近上限 |
| slb_len | 转融资交易汇总 | money_flow | ~5 | 3000 | 365 | 365x5=1825 |
| moneyflow_cnt_ths | 板块资金流向THS | money_flow | ~300 | 3000 | 10 | 10x300=3000 |
| moneyflow_ind_ths | 行业资金流向THS | money_flow | ~30 | 3000 | 100 | 100x30=3000 |
| moneyflow_ind_dc | 板块资金流向DC | money_flow | ~30 | 3000 | 100 | 100x30=3000 |
| moneyflow_mkt_dc | 大盘资金流向DC | money_flow | ~1 | 3000 | 365 | 365x1=365 |
| moneyflow_hsgt | 沪港通资金流向 | money_flow | ~1 | 3000 | 365 | 365x1=365 |
| limit_list_ths | 同花顺涨跌停榜单 | fundamentals | ~200 | 3000 | 15 | 15x200=3000 |
| limit_list_d | 涨跌停和炸板数据 | fundamentals | ~200 | 3000 | 15 | 15x200=3000 |
| limit_step | 涨停股票连板天梯 | fundamentals | ~30 | 3000 | 100 | 100x30=3000 |
| limit_cpt_list | 涨停最强板块统计 | fundamentals | ~20 | 3000 | 150 | 150x20=3000 |
| ths_daily | 同花顺行业概念指数行情 | kline | ~500 | 3000 | 6 | 6x500=3000 |
| dc_daily | 东方财富概念板块行情 | kline | ~500 | 3000 | 6 | 6x500=3000 |
| stk_auction | 开盘竞价成交当日 | fundamentals | ~5000 | 3000 | 1 | 单日即可能超限 |
| hm_detail | 游资交易每日明细 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| ths_hot | 同花顺热榜 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| dc_hot | 东方财富热榜 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| tdx_daily | 通达信板块行情 | kline | ~500 | 3000 | 6 | 6x500=3000 |
| kpl_list | 开盘啦榜单数据 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| index_dailybasic | 大盘指数每日指标 | fundamentals | ~50 | 3000 | 60 | 60x50=3000 |
| idx_factor_pro | 指数技术面因子 | kline | ~50 | 8000 | 160 | 160x50=8000 |
| daily_info | 沪深市场每日交易统计 | kline | ~10 | 4000 | 365 | 365x10=3650 |
| sz_daily_info | 深圳市场每日交易情况 | kline | ~5 | 2000 | 365 | 365x5=1825 |
| index_global | 国际主要指数 | kline | ~30 | 4000 | 130 | 130x30=3900 |
| sw_daily | 申万行业指数日行情 | kline | ~30 | 4000 | 130 | 130x30=3900 |
| ci_daily | 中信行业指数日行情 | kline | ~30 | 4000 | 130 | 130x30=3900 |
| bak_daily | 备用行情 | kline | ~5000 | 3000 | 1 | 单日即可能超限 |
| rt_k | 实时日线 | kline | ~5000 | 3000 | 1 | 单日即可能超限 |
| rt_min | 实时分钟 | kline | ~50000 | 3000 | 1 | 分钟级数据量极大 |
| rt_min_daily | 实时分钟日累计 | kline | ~50000 | 3000 | 1 | 分钟级数据量极大 |

**第二类：optional DATE_RANGE — 可选日期范围查询（用户不指定 ts_code 时全市场查询）**

以下接口的 DATE_RANGE 在 `optional_params` 中。当用户不指定 `ts_code` 而只传日期范围时，会返回全市场数据，同样面临截断风险：

| 接口名 | 中文说明 | 频率组 | 每日预估行数 | max_rows | 建议步长(天) | 步长依据 |
|---------|----------|--------|-------------|----------|-------------|---------|
| pledge_stat | 股权质押统计 | fundamentals | ~500 | 3000 | 6 | 6x500=3000 |
| pledge_detail | 股权质押明细 | fundamentals | ~200 | 3000 | 15 | 15x200=3000 |
| repurchase | 股票回购 | fundamentals | ~50 | 3000 | 60 | 60x50=3000 |
| share_float | 限售股解禁 | fundamentals | ~50 | 3000 | 60 | 60x50=3000 |
| block_trade | 大宗交易 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| stk_holdernumber | 股东人数 | fundamentals | ~200 | 3000 | 15 | 15x200=3000 |
| report_rc | 券商盈利预测 | fundamentals | ~100 | 3000 | 30 | 30x100=3000 |
| stk_surv | 机构调研数据 | fundamentals | ~50 | 3000 | 60 | 60x50=3000 |

**第三类：使用 trade_date 单日循环的接口（use_trade_date_loop=True）**

以下接口使用 `trade_date` 单日参数而非 `start_date/end_date` 范围查询。当用户传入日期范围时，需要按每个交易日逐日调用，本质上是 `date_chunk_days=1` 的日期分批：

| 接口名 | 中文说明 | 频率组 | 建议步长(天) | 说明 |
|---------|----------|--------|-------------|------|
| top_list | 龙虎榜每日统计单 | fundamentals | 1 | use_trade_date_loop=True，每次只查一天 |
| top_inst | 龙虎榜机构交易单 | fundamentals | 1 | use_trade_date_loop=True，每次只查一天 |

**不需要日期分批的接口（已有其他分批机制或无日期参数）：**

- `batch_by_code=True` 的接口（daily, weekly, monthly, stk_weekly_monthly, adj_factor, stk_mins, moneyflow, moneyflow_ths, moneyflow_dc, index_daily）：已按股票/指数代码分批
- 无 DATE_RANGE 参数的接口（stock_basic, trade_cal, stock_st, stock_hsgt, namechange, stock_company, stk_managers, stk_rewards, bse_mapping, new_share, bak_basic, margin_secs, dividend, ths_index, dc_index, ths_member, dc_member, tdx_index, tdx_member, hm_list, kpl_concept_cons, dc_concept, dc_concept_cons, index_basic, index_classify, index_member_all, ci_index_member, broker_recommend, ggt_monthly, stk_holdertrade 等）：一次调用即可获取全部数据
- 财务数据接口（income, balancesheet, cashflow, fina_indicator, forecast, express, fina_mainbz, disclosure_date 及其 VIP 变体）：使用 REPORT_PERIOD 参数，按季度查询，单次数据量可控
- 实时快照接口（rt_idx_k, rt_idx_min, rt_idx_min_daily, rt_sw_k）：获取当前快照，无日期范围

### batch_by_code + 大日期范围的双重分批场景

以下 `batch_by_code=True` 的接口，当单只股票/指数请求超长日期范围时，也可能触及行数上限：

| 接口名 | 中文说明 | 单只代码每日行数 | 超限风险日期范围 |
|---------|----------|----------------|----------------|
| index_daily | 指数日线行情 | 1 | >8000天（~32年），风险极低 |
| stk_mins | 历史分钟行情 | ~240（1分钟频率） | >12天，风险较高 |

对于 `stk_mins` 等分钟级接口，当单只股票的日期范围较大时，需要在按代码分批的基础上，对每个代码内部再按日期分批（双重分批）。


## 需求

### 需求 1：注册表扩展 — 日期分批元数据声明

**用户故事：** 作为量化交易员，我希望每个 Tushare 接口的日期分批配置在注册表中声明式定义，以便新增接口时只需修改注册表元数据，无需改动核心导入逻辑。

#### 验收标准

1. THE ApiEntry SHALL 新增 `batch_by_date` 布尔字段（默认 False），标识该接口是否需要按日期自动分批
2. THE ApiEntry SHALL 新增 `date_chunk_days` 整数字段（默认 30），指定日期分批的步长天数
3. FOR ALL 注册表中标记 `batch_by_date=True` 的接口，`date_chunk_days` 的配置 SHALL 满足约束：`date_chunk_days x 每日预估行数 < max_rows`（max_rows 默认 3000，可通过 extra_config 自定义）
4. THE API_Registry SHALL 为接口分析表第一类中列出的全部 required DATE_RANGE 接口设置 `batch_by_date=True`，并根据步长依据列配置对应的 `date_chunk_days` 值
5. THE API_Registry SHALL 为接口分析表第二类中列出的全部 optional DATE_RANGE 接口设置 `batch_by_date=True`，并根据步长依据列配置对应的 `date_chunk_days` 值
6. THE API_Registry SHALL 为接口分析表第三类中的 `top_list` 和 `top_inst` 设置 `batch_by_date=True` 和 `date_chunk_days=1`（与 use_trade_date_loop 配合，逐日调用）
7. FOR ALL 注册表中标记 `batch_by_date=True` 的接口，THE ApiEntry 的 `required_params` 或 `optional_params` SHALL 包含 `ParamType.DATE_RANGE`（日期分批的前提条件）
8. WHEN 接口同时标记 `batch_by_code=True` 和 `batch_by_date=True`，THE Import_Task SHALL 优先按代码分批；对于分钟级接口（如 stk_mins），在每个代码的调用中 SHALL 额外按日期分批（双重分批），以避免单只股票长日期范围数据截断

### 需求 2：日期分批拆分器

**用户故事：** 作为量化交易员，我希望系统能将大日期范围自动拆分为多个子区间，以便每次 API 调用的数据量不超过 Tushare 的行数上限。

#### 验收标准

1. THE Date_Batch_Splitter SHALL 接受 start_date（YYYYMMDD）、end_date（YYYYMMDD）和 chunk_days（正整数）三个参数
2. WHEN start_date 和 end_date 有效且 start_date <= end_date，THE Date_Batch_Splitter SHALL 返回一个 (chunk_start, chunk_end) 元组列表，每个子区间跨度不超过 chunk_days 天
3. THE Date_Batch_Splitter SHALL 确保所有子区间连续且无重叠，第一个子区间的 chunk_start 等于 start_date，最后一个子区间的 chunk_end 等于 end_date
4. WHEN start_date 等于 end_date，THE Date_Batch_Splitter SHALL 返回包含单个子区间 [(start_date, end_date)] 的列表
5. WHEN 日期范围小于 chunk_days，THE Date_Batch_Splitter SHALL 返回包含单个子区间的列表
6. FOR ALL 由 Date_Batch_Splitter 生成的子区间列表，拆分后再合并 SHALL 覆盖原始日期范围内的每一天（round-trip 属性）
7. FOR ALL 由 Date_Batch_Splitter 生成的子区间列表，相邻子区间的 chunk_end 与下一个 chunk_start 之间 SHALL 恰好相差 1 天（无间隙无重叠属性）

### 需求 3：导入引擎日期分批处理

**用户故事：** 作为量化交易员，我希望导入引擎在检测到接口需要日期分批时，自动按配置的步长拆分日期范围并逐批调用 API，以便大日期范围的数据能完整导入而不被截断。

#### 验收标准

1. WHEN Import_Task 处理一个 `batch_by_date=True` 的接口且用户提供了 start_date 和 end_date 参数，THE Import_Task SHALL 使用 Date_Batch_Splitter 将日期范围拆分为子区间，并按子区间逐批调用 Tushare API
2. WHEN Import_Task 处理一个 `batch_by_date=True` 的接口但用户未提供 start_date 或 end_date，THE Import_Task SHALL 退回到单次调用模式（_process_single）
3. WHEN 处理每个日期子区间时，THE Import_Task SHALL 在调用 API 前检查 Redis 停止信号，收到停止信号时立即终止并返回已导入的记录数
4. WHEN 处理每个日期子区间时，THE Import_Task SHALL 在每次 API 调用后按接口所属 RateLimitGroup 的频率限制等待相应时间（kline: 0.18s, fundamentals: 0.40s, money_flow: 0.30s）
5. WHEN 单个日期子区间的 API 返回行数达到该接口的 max_rows 阈值（默认 3000，可通过 extra_config 自定义），THE Import_Task SHALL 记录 WARNING 级别日志，提示该子区间数据可能被截断，并包含接口名、子区间起止日期、返回行数和 max_rows 阈值
6. WHEN 某个日期子区间的 API 调用失败（非 Token 无效错误），THE Import_Task SHALL 记录错误日志并继续处理下一个子区间，不终止整个导入任务
7. IF 某个日期子区间的 API 调用返回 Token 无效错误（code=-2001），THEN THE Import_Task SHALL 立即终止整个导入任务并抛出异常
8. THE Import_Task SHALL 在处理过程中通过 Redis 实时更新进度信息，包含总子区间数（total）、已完成子区间数（completed）和当前处理的子区间标识（current_item）
9. WHEN 所有日期子区间处理完成，THE Import_Task SHALL 汇总全部子区间的记录数作为总导入记录数返回

### 需求 4：导入引擎分批策略路由

**用户故事：** 作为量化交易员，我希望导入引擎能根据注册表配置自动选择正确的分批策略（按代码分批、按指数分批、按日期分批或单次调用），以便不同类型的接口都能以最优方式导入数据。

#### 验收标准

1. WHEN Import_Task 接收到导入请求，THE Import_Task SHALL 按以下优先级选择分批策略：
   - 优先级 1：`batch_by_code=True` → 按股票代码分批（_process_batched）；若同时 `batch_by_date=True`，则在每个代码内部额外按日期分批（双重分批）
   - 优先级 2：接口支持 INDEX_CODE 参数且用户未指定 ts_code → 按指数代码分批（_process_batched_index）
   - 优先级 3：`batch_by_date=True` 且用户提供了 start_date 和 end_date → 按日期分批（_process_batched_by_date）
   - 优先级 4：以上均不满足 → 单次调用（_process_single）
2. THE Import_Task SHALL 将当前基于运行时推断的隐式日期分批逻辑（`has_date_range and has_date_params` 的动态判断）改为兜底机制：优先使用注册表的 `batch_by_date` 声明，若接口未声明 `batch_by_date=True` 但运行时检测到有 DATE_RANGE 参数且用户提供了日期范围，THE Import_Task SHALL 记录 WARNING 日志（提示该接口缺少 batch_by_date 声明）并仍然按日期分批处理，使用默认步长 30 天
3. WHEN 接口标记 `batch_by_date=True` 且 extra_config 中包含 `use_trade_date_loop=True`，THE Import_Task SHALL 在日期分批处理中将每个子区间的 start_date 转为 trade_date 参数，并移除 end_date 参数
4. THE Import_Task SHALL 使用注册表中配置的 `date_chunk_days` 值作为 Date_Batch_Splitter 的步长参数，而非硬编码的默认值

### 需求 5：频率限制合规

**用户故事：** 作为量化交易员，我希望系统在日期分批导入过程中严格遵守 Tushare API 的频率限制，以避免因调用过快被 Tushare 封禁 Token。

#### 验收标准

1. THE Import_Task SHALL 在每次 Tushare API 调用之间按 RateLimitGroup 等待相应时间：kline 组 0.18 秒、fundamentals 组 0.40 秒、money_flow 组 0.30 秒
2. WHEN Tushare API 返回频率限制错误（code=-2002），THE Import_Task SHALL 等待 60 秒后重试当前请求，最多重试 3 次
3. THE Import_Task SHALL 从环境变量读取频率限制配置（RATE_LIMIT_KLINE、RATE_LIMIT_FUNDAMENTALS、RATE_LIMIT_MONEY_FLOW），支持运行时调整
4. WHILE 日期分批导入正在进行，THE Import_Task SHALL 确保同一 RateLimitGroup 内的连续 API 调用间隔不小于配置的最小间隔时间
5. WHEN 某次 API 调用的实际间隔时间低于配置的最小间隔时间，THE Import_Task SHALL 记录 WARNING 级别日志（仅记录违规情况，避免正常调用产生日志噪音）

### 需求 6：截断检测与预检查

**用户故事：** 作为量化交易员，我希望系统能检测到数据被截断的情况并发出警告，以便我知道需要缩小日期范围重新导入。

#### 验收标准

1. WHEN 日期分批导入开始前，THE Import_Task SHALL 执行预检查：根据接口的 `date_chunk_days` 和 `max_rows` 配置，验证步长配置的合理性；如果 `date_chunk_days` 值大于 `max_rows / 预估每日行数`（从 extra_config 的 `estimated_daily_rows` 字段读取，默认 3000），THE Import_Task SHALL 记录 WARNING 日志提示步长可能过大
2. WHEN 单个日期子区间的 API 返回行数达到或超过该接口的 max_rows 阈值（默认 3000，可通过 extra_config 自定义），THE Import_Task SHALL 在日志中记录 WARNING 级别消息，包含接口名称、子区间起止日期、返回行数和 max_rows 阈值
3. WHEN 检测到截断时，THE Import_Task SHALL 在 Redis 进度信息中记录截断警告列表，包含被截断的子区间信息
4. IF 连续 3 个或以上子区间均检测到截断，THEN THE Import_Task SHALL 在日志中记录 ERROR 级别消息，建议用户减小该接口的 `date_chunk_days` 配置，并在 Redis 进度信息中标记 `needs_smaller_chunk=true`

### 需求 7：进度报告增强

**用户故事：** 作为量化交易员，我希望在日期分批导入过程中能看到详细的进度信息，以便了解导入的整体进展和预计完成时间。

#### 验收标准

1. WHEN 日期分批导入开始时，THE Import_Task SHALL 在 Redis 进度信息中设置 total 为日期子区间总数
2. WHEN 每个日期子区间处理完成后，THE Import_Task SHALL 更新 Redis 进度信息中的 completed 计数和 current_item（格式为 "YYYYMMDD-YYYYMMDD"）
3. THE Import_Task SHALL 在 Redis 进度信息中新增 `truncation_warnings` 列表字段，记录所有检测到截断的子区间信息
4. THE Import_Task SHALL 在 Redis 进度信息中新增 `batch_mode` 字段（值为 "by_date"、"by_code"、"by_index"、"by_code_and_date" 或 "single"），标识当前使用的分批策略
5. WHEN 导入完成时，THE Import_Task SHALL 在最终结果中包含总记录数、总子区间数、成功子区间数和截断警告数

### 需求 8：导入日志持久化增强

**用户故事：** 作为量化交易员，我希望导入历史记录中能看到日期分批的详细信息，以便回溯和排查数据完整性问题。

#### 验收标准

1. WHEN 日期分批导入完成时，THE Import_Task SHALL 在 tushare_import_log 记录中保存分批统计信息，包含总子区间数、成功子区间数和截断警告数
2. IF 导入过程中存在截断警告，THEN THE Import_Task SHALL 在 tushare_import_log 的 error_message 字段中记录截断的子区间列表（最多前 10 个）
3. THE Import_Service SHALL 在查询导入历史时返回分批统计信息，便于前端展示