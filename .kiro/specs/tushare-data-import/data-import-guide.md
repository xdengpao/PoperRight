# Tushare 数据导入说明

## 一、需求校验结果：缺失接口清单

基于 Tushare 官方 Skills 文档（220+ 接口）与当前需求文档逐项比对，以下接口在当前需求中**缺失**：

### 1.1 基础数据（需求 3）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `new_share` | IPO新股上市 | ✅ 已补充 |
| `stock_st` / `st` | ST股票列表 | ✅ 已补充 |
| `bak_basic` | 备用基础信息 | ✅ 已补充 |
| `stk_delist` | 股票历史列表（含退市） | ✅ 已补充 |
| `daily_share` | 每日股本（盘前） | ✅ 已补充 |

### 1.2 行情数据（需求 4/4a）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `pro_bar` | 通用行情接口（含复权） | 可选，daily/weekly/monthly 已覆盖核心功能 |
| `bak_daily` | 备用行情 | 可选，低优先级 |
| `hsgt_top10` | 沪深股通十大成交股 | 建议纳入需求 4 行情数据 |
| `ggt_top10` | 港股通十大成交股 | 建议纳入需求 4 行情数据 |
| `ggt_daily` | 港股通每日成交统计 | 建议纳入需求 4 行情数据 |
| `ggt_monthly` | 港股通每月成交统计 | 建议纳入需求 4 行情数据 |
| `rt_k` | 实时日线 | 可选，实时数据非批量导入场景 |
| `rt_min` | 实时分钟 | 可选，实时数据非批量导入场景 |

### 1.3 财务数据（需求 5）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `forecast` | 业绩预告 | ✅ 已补充 |
| `express` | 业绩快报 | ✅ 已补充 |
| `fina_audit` | 财务审计意见 | 暂不纳入 |
| `fina_mainbz` | 主营业务构成 | 暂不纳入 |
| `disclosure_date` | 财报披露日期表 | 暂不纳入 |

### 1.4 参考数据（需求 6/7）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `share_float` | 限售股解禁 | **建议纳入**，对股价有直接影响 |
| `pledge_detail` | 股权质押明细数据 | 建议纳入，系统已有 pledge_ratio 字段 |
| `pledge_stat` | 股权质押统计数据 | 建议纳入 |
| `repurchase` | 股票回购 | 建议纳入 |

### 1.5 特色数据（需求 7）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `stk_factor` | 股票技术面因子 | ✅ 已补充（需求 7a） |
| `stk_factor_pro` | 股票技术面因子(专业版) | ✅ 已补充（需求 7a，special 权限） |
| `ccass_hold` | 中央结算系统持股统计 | 暂不纳入 |
| `ccass_hold_detail` | 中央结算系统持股明细 | 暂不纳入 |
| `report_rc` | 券商盈利预测数据 | 暂不纳入 |
| `stk_surv` | 机构调研数据 | 暂不纳入 |
| `cyq_perf` | 每日筹码分布 | 暂不纳入 |
| `cyq_chips` | 每日筹码及胜率 | 暂不纳入 |

### 1.6 打板专题数据（需求 10）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `limit_step` | 涨停股票连板天梯 | ✅ 已补充 |
| `ths_limit` | 同花顺涨跌停榜单 | ✅ 已补充 |
| `dc_hot` | 东方财富App热榜 | ✅ 已补充 |
| `ths_hot` | 同花顺App热榜 | ✅ 已补充 |
| `kpl_list` | 榜单数据（开盘啦） | ✅ 已补充 |
| `ths_index` | 同花顺行业概念板块 | ✅ 已补充 |
| `ths_member` | 同花顺行业概念成分 | ✅ 已补充 |
| `dc_index` | 东方财富概念板块 | ✅ 已补充 |
| `dc_member` | 东方财富概念成分 | ✅ 已补充 |

### 1.7 资金流向数据（需求 9）缺失

| 接口名 | 中文说明 | 建议 |
|--------|---------|------|
| `moneyflow_mkt_dc` | 大盘资金流向（DC） | ✅ 已补充 |
| `moneyflow_dc` | 个股资金流向（DC） | 暂不纳入，moneyflow 已覆盖 |
| `moneyflow_ths` | 个股资金流向（THS） | 暂不纳入，moneyflow 已覆盖 |

### 1.8 已覆盖接口汇总（无需修改）

当前需求已完整覆盖的接口：stock_basic, trade_cal, daily, weekly, monthly, stk_mins, adj_factor, daily_basic, suspend_d, income, balancesheet, cashflow, fina_indicator, dividend, stock_company, namechange, hs_const, stk_rewards, stk_managers, top10_holders, top10_floatholders, stk_holdernumber, stk_holdertrade, block_trade, stk_account, stk_limit, margin, margin_detail, margin_target, slb_len, slb_sec, moneyflow, moneyflow_hsgt, moneyflow_ind_dc, moneyflow_ind_ths, limit_list_d, hm_list, hm_detail, top_list, top_inst, index_basic, index_daily, index_weekly, index_monthly, index_min, index_1min_realtime, index_weight, index_classify, sw_daily, ci_daily, index_dailybasic, index_tech, daily_info, sz_daily_info, index_global

---

## 二、数据导入说明

### 2.1 总体架构

```
用户(前端) → TushareImportView → REST API → Import_Service → Celery Task → Tushare API → 数据库
                                                  ↓
                                          三级Token自动选择
                                     basic / advanced / special
```

### 2.2 股票数据导入清单

#### 2.2.1 基础数据（无需日期参数，全量导入）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 1 | `stock_basic` | 股票基础列表 | 静态元数据 | 全量拉取，ON CONFLICT 更新 | stock_info (PG) | basic |
| 2 | `trade_cal` | 交易日历 | 静态元数据 | 按交易所全量拉取 | trade_calendar (PG) | basic |
| 3 | `stock_company` | 上市公司基本信息 | 静态元数据 | 全量拉取，ON CONFLICT 更新 | stock_company (PG) | basic |
| 4 | `namechange` | 股票曾用名 | 静态元数据 | 全量拉取 | stock_namechange (PG) | basic |
| 5 | `hs_const` | 沪深股通成份股 | 静态元数据 | 按类型(SH/SZ)拉取 | hs_constituent (PG) | basic |
| 6 | `stk_rewards` | 管理层薪酬和持股 | 静态元数据 | 按股票代码拉取 | stk_rewards (PG) | basic |
| 7 | `stk_managers` | 上市公司管理层 | 静态元数据 | 按股票代码拉取 | stk_managers (PG) | basic |

#### 2.2.2 低频行情数据（需日期范围，按日/周/月导入）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 8 | `daily` | 日线行情 | 时序OHLCV | 按日期+代码批量拉取，写入kline超表 freq="1d" | kline (TS) | basic |
| 9 | `weekly` | 周线行情 | 时序OHLCV | 按日期+代码批量拉取，写入kline超表 freq="1w" | kline (TS) | basic |
| 10 | `monthly` | 月线行情 | 时序OHLCV | 按日期+代码批量拉取，写入kline超表 freq="1M" | kline (TS) | basic |
| 11 | `adj_factor` | 复权因子 | 时序因子 | 按日期+代码拉取 | adjustment_factor (PG) | basic |
| 12 | `daily_basic` | 每日指标 | 时序指标 | 按日期拉取（换手率/PE/PB/总市值等） | stock_info (PG) 更新 | basic |
| 13 | `suspend_d` | 每日停复牌信息 | 事件数据 | 按日期拉取 | suspend_info (PG) | basic |

#### 2.2.3 中频行情数据（需日期范围+频率，分钟级导入）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 14 | `stk_mins` | 历史分钟行情 | 时序OHLCV | 按代码+日期+频率拉取，建议单只股票短日期范围 | kline (TS) freq="1m/5m/15m/30m/60m" | advanced |

#### 2.2.4 财务数据（需报告期参数）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 15 | `income` | 利润表 | 财报JSONB | 按报告期+代码拉取，ON CONFLICT 去重 | financial_statement (PG) report_type="income" | basic |
| 16 | `balancesheet` | 资产负债表 | 财报JSONB | 按报告期+代码拉取 | financial_statement (PG) report_type="balance" | basic |
| 17 | `cashflow` | 现金流量表 | 财报JSONB | 按报告期+代码拉取 | financial_statement (PG) report_type="cashflow" | basic |
| 18 | `fina_indicator` | 财务指标数据 | 财务指标 | 按报告期+代码拉取，更新stock_info | stock_info (PG) pe_ttm/pb/roe | basic |
| 19 | `dividend` | 分红送股数据 | 事件数据 | 按代码拉取 | dividend (PG) | basic |

#### 2.2.5 参考数据（按代码或日期拉取）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 20 | `top10_holders` | 前十大股东 | 报告期快照 | 按代码+报告期拉取 | top_holders (PG) holder_type="top10" | basic |
| 21 | `top10_floatholders` | 前十大流通股东 | 报告期快照 | 按代码+报告期拉取 | top_holders (PG) holder_type="float" | basic |
| 22 | `stk_holdernumber` | 股东人数 | 报告期快照 | 按代码+日期拉取 | stk_holdernumber (PG) | basic |
| 23 | `stk_holdertrade` | 股东增减持 | 事件数据 | 按代码拉取 | stk_holdertrade (PG) | basic |
| 24 | `block_trade` | 大宗交易 | 事件数据 | 按日期拉取 | block_trade (PG) | basic |
| 25 | `stk_account` | 股票开户数据 | 统计数据 | 按日期拉取 | stk_account (PG) | basic |
| 26 | `stk_limit` | 每日涨跌停价格 | 时序数据 | 按日期拉取 | stk_limit (PG) | basic |

#### 2.2.6 两融及转融通数据

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 27 | `margin` | 融资融券交易汇总 | 时序数据 | 按日期拉取 | margin_data (PG) | basic |
| 28 | `margin_detail` | 融资融券交易明细 | 时序数据 | 按日期+代码拉取 | margin_detail (PG) | basic |
| 29 | `margin_target` | 融资融券标的(盘前) | 静态数据 | 全量拉取 | margin_target (PG) | basic |
| 30 | `slb_len` | 转融资交易汇总 | 时序数据 | 按日期拉取 | slb_len (PG) | basic |
| 31 | `slb_sec` | 转融券交易汇总 | 时序数据 | 按日期拉取 | slb_sec (PG) | basic |

#### 2.2.7 资金流向数据

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 32 | `moneyflow` | 个股资金流向 | 时序数据 | 按日期+代码拉取 | money_flow (PG) | basic |
| 33 | `moneyflow_hsgt` | 沪深港通资金流向 | 时序数据 | 按日期拉取 | moneyflow_hsgt (PG) | basic |
| 34 | `moneyflow_ind_dc` | 行业资金流向(东财) | 时序数据 | 按日期拉取 | moneyflow_ind (PG) data_source="DC" | basic |
| 35 | `moneyflow_ind_ths` | 行业资金流向(同花顺) | 时序数据 | 按日期拉取 | moneyflow_ind (PG) data_source="THS" | basic |
| 36 | `moneyflow_mkt_dc` | 大盘资金流向(东财) | 时序数据 | 按日期拉取 | moneyflow_mkt_dc (PG) | basic |

#### 2.2.8 打板专题数据

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 36 | `limit_list_d` | 涨跌停和炸板数据 | 时序数据 | 按日期拉取 | limit_list (PG) | advanced |
| 37 | `top_list` | 龙虎榜每日统计单 | 时序数据 | 按日期拉取 | top_list (PG) | basic |
| 38 | `top_inst` | 龙虎榜机构交易单 | 时序数据 | 按日期拉取 | top_inst (PG) | basic |
| 39 | `hm_list` | 市场游资最全名录 | 静态数据 | 全量拉取 | hm_list (PG) | advanced |
| 40 | `hm_detail` | 游资交易每日明细 | 时序数据 | 按日期拉取 | hm_detail (PG) | advanced |

### 2.3 指数专题数据导入清单

#### 2.3.1 指数基础信息

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 41 | `index_basic` | 指数基本信息 | 静态元数据 | 按市场(SSE/SZSE/CSI)拉取 | index_info (PG) | basic |

#### 2.3.2 指数低频行情

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 42 | `index_daily` | 指数日线行情 | 时序OHLCV | 按日期+指数代码拉取 | kline (TS) freq="1d" | basic |
| 43 | `index_weekly` | 指数周线行情 | 时序OHLCV | 按日期+指数代码拉取 | kline (TS) freq="1w" | basic |
| 44 | `index_monthly` | 指数月线行情 | 时序OHLCV | 按日期+指数代码拉取 | kline (TS) freq="1M" | basic |

#### 2.3.3 指数中频行情

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 45 | `index_min` | 指数历史分钟行情 | 时序OHLCV | 按代码+日期+频率拉取 | kline (TS) freq="1m/5m/15m/30m/60m" | advanced |
| 46 | `index_1min_realtime` | 指数实时分钟行情 | 时序OHLCV | 按代码拉取 | kline (TS) freq="1m" | advanced |

#### 2.3.4 指数成分与行业

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 47 | `index_weight` | 指数成分和权重 | 快照数据 | 按指数代码+日期拉取 | index_weight (PG) | basic |
| 48 | `index_classify` | 申万行业分类 | 静态元数据 | 全量拉取 | sector_info (PG) | basic |
| 49 | `sw_daily` | 申万行业指数日行情 | 时序OHLCV | 按日期拉取 | sector_kline (TS) | basic |
| 50 | `ci_daily` | 中信行业指数日行情 | 时序OHLCV | 按日期拉取 | sector_kline (TS) | basic |

#### 2.3.5 指数指标与统计

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 51 | `index_dailybasic` | 大盘指数每日指标 | 时序指标 | 按日期拉取 | index_dailybasic (PG) | advanced |
| 52 | `index_tech` | 指数技术面因子(专业版) | 时序指标 | 按代码+日期拉取 | index_tech (PG) | special |
| 53 | `daily_info` | 沪深市场每日交易统计 | 统计数据 | 按日期拉取 | market_daily_info (PG) | basic |
| 54 | `sz_daily_info` | 深圳市场每日交易情况 | 统计数据 | 按日期拉取 | sz_daily_info (PG) | basic |
| 55 | `index_global` | 国际主要指数 | 时序OHLCV | 按日期拉取 | index_global (PG) | basic |

### 2.4 导入方法说明

#### 2.4.1 导入模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **全量导入** | 不需要日期参数，一次拉取全部数据 | 基础元数据（stock_basic、trade_cal、index_basic 等） |
| **增量导入（按日期范围）** | 用户指定 start_date/end_date | 行情数据、财务数据、资金流向等时序数据 |
| **增量导入（按报告期）** | 用户指定年份+季度 | 财务报表（income、balancesheet、cashflow） |
| **按代码导入** | 用户指定 ts_code 列表 | 单只或多只股票的特定数据 |

#### 2.4.2 数据存储分类

| 存储引擎 | 用途 | 表前缀/标识 |
|---------|------|------------|
| **TimescaleDB (TS)** | 时序行情数据（OHLCV） | kline 超表、sector_kline 超表 |
| **PostgreSQL (PG)** | 业务数据、元数据、财务数据 | 所有其他表 |

#### 2.4.3 去重策略

所有导入均使用 `INSERT ... ON CONFLICT DO NOTHING` 或 `ON CONFLICT DO UPDATE` 策略：
- **DO NOTHING**：行情数据、财务报表等历史数据不变的场景
- **DO UPDATE**：基础信息（stock_basic → stock_info）等需要更新最新状态的场景

#### 2.4.4 频率限制

| 数据类型 | 配置项 | 间隔 | 说明 |
|---------|--------|------|------|
| 行情数据 | `rate_limit_kline` | 0.18s | 500次/min |
| 财务数据 | `rate_limit_fundamentals` | 0.40s | 200次/min |
| 资金流向 | `rate_limit_money_flow` | 0.30s | 300次/min |

#### 2.4.5 三级 Token 权限

| 级别 | 配置项 | 积分要求 | 典型接口 |
|------|--------|---------|---------|
| basic | `TUSHARE_TOKEN_BASIC` | ≤6000 | stock_basic, daily, income, moneyflow, index_daily 等大部分接口 |
| advanced | `TUSHARE_TOKEN_ADVANCED` | >6000 | stk_mins, limit_list_d, hm_list, hm_detail, index_dailybasic 等 |
| special | `TUSHARE_TOKEN_SPECIAL` | 单独开通 | index_tech, stk_factor_pro, cyq_perf, cyq_chips 等专业版接口 |

#### 2.4.6 批量处理策略

- **BATCH_SIZE = 50**：按股票列表分批，每批 50 只股票
- **Celery 异步队列**：所有导入任务分发到 `data_sync` 队列
- **Redis 进度追踪**：键格式 `tushare:import:{task_id}`，每 3 秒前端轮询
- **停止信号**：Redis 键 `tushare:import:stop:{task_id}`，任务每批检查

### 2.5 ts_code 格式转换规则

| 场景 | 输入格式 | 存储格式 | 示例 |
|------|---------|---------|------|
| 股票数据写入 stock_info/kline | 600000.SH | 600000（纯6位） | ts_code.split(".")[0] |
| 指数数据写入 index_info/kline | 000001.SH | 000001.SH（保留后缀） | 原样存储 |
| 用户输入补全 | 600000 | 600000.SH | 6开头→.SH，0/3开头→.SZ |
