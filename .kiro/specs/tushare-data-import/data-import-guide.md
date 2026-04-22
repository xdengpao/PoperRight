# Tushare 数据导入说明

## 一、接口覆盖总览

基于用户提供的 8 个 Tushare 数据文档及指数专题文档，当前需求已覆盖全部股票数据接口（102个）和指数专题接口（20个），合计 122 个接口。

### 1.1 股票数据接口分布

| 子分类 | 接口数 | 对应文档 | 对应需求 |
|--------|-------|---------|---------|
| 基础数据 | 13 | 文档1 | 需求 3 |
| 行情数据（低频） | 13 | 文档8 | 需求 4 |
| 行情数据（中频/实时） | 4 | 文档8 | 需求 4a |
| 财务数据 | 9 (+7 VIP变体) | 文档7 | 需求 5 |
| 参考数据 | 12 | 文档6 | 需求 6 |
| 特色数据 | 13 | 文档5 | 需求 7 |
| 两融及转融通 | 4 | 文档4 | 需求 8 |
| 资金流向数据 | 8 | 文档3 | 需求 9 |
| 打板专题数据 | 24 | 文档2 | 需求 10 |

### 1.2 指数专题接口分布

| 子分类 | 接口数 | 对应需求 |
|--------|-------|---------|
| 指数基本信息 | 1 | 需求 11 |
| 指数行情低频（日线/周线/月线） | 3 | 需求 12 |
| 指数行情中频（实时日线/实时分钟/历史分钟） | 4 | 需求 12a |
| 指数成分和权重 | 1 | 需求 13 |
| 申万行业数据（分类/成分/日线/实时） | 4 | 需求 14 |
| 中信行业数据（成分/日线） | 2 | 需求 15 |
| 大盘指数每日指标 | 1 | 需求 16 |
| 指数技术面因子（专业版） | 1 | 需求 17 |
| 沪深市场每日交易统计 | 2 | 需求 18 |
| 深圳市场每日交易情况 | — | 需求 18 |
| 国际主要指数 | 1 | 需求 19 |

> 指数专题合计 20 个接口（较旧版 15 个新增 5 个：rt_idx_k、rt_idx_min、rt_idx_min_daily、index_member_all、ci_index_member、rt_sw_k；替换 2 个：index_1min_realtime→rt_idx_min、index_min→idx_mins、index_tech→idx_factor_pro）

---

## 二、数据导入说明

### 2.1 总体架构

```
用户(前端) → TushareImportView → REST API → Import_Service → Celery Task → Tushare API → 数据库
                                                  ↓
                                          四级Token自动选择
                                   basic / advanced / premium / special
```

### 2.2 股票数据导入清单

#### 2.2.1 基础数据（文档1，13个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 1 | `stock_basic` | 股票基础列表 | 静态元数据 | 全量拉取，ON CONFLICT 更新 | stock_info (PG) | basic |
| 2 | `stk_premarket` | 每日股本盘前 | 时序数据 | 按日期拉取，含涨跌停价格 | stk_premarket (PG) | special |
| 3 | `trade_cal` | 交易日历 | 静态元数据 | 按交易所全量拉取 | trade_calendar (PG) | basic |
| 4 | `stock_st` | ST股票列表 | 事件数据 | 按日期拉取 | stock_st (PG) | advanced |
| 5 | `st` | ST风险警示板股票 | 时序数据 | 按日期拉取 | st_warning (PG) | advanced |
| 6 | `stock_hsgt` | 沪深港通股票列表 | 静态元数据 | 按类型(SH/SZ)拉取 | stock_hsgt (PG) | advanced |
| 7 | `namechange` | 股票曾用名 | 静态元数据 | 全量拉取 | stock_namechange (PG) | basic |
| 8 | `stock_company` | 上市公司基本信息 | 静态元数据 | 全量拉取，ON CONFLICT 更新 | stock_company (PG) | basic |
| 9 | `stk_managers` | 上市公司管理层 | 静态元数据 | 按股票代码拉取 | stk_managers (PG) | basic |
| 10 | `stk_rewards` | 管理层薪酬和持股 | 静态元数据 | 按股票代码拉取 | stk_rewards (PG) | basic |
| 11 | `bse_mapping` | 北交所新旧代码对照 | 静态元数据 | 全量拉取 | bse_mapping (PG) | basic |
| 12 | `new_share` | IPO新股上市 | 静态元数据 | 全量拉取 | new_share (PG) | basic |
| 13 | `bak_basic` | 备用基础信息 | 静态元数据 | 按日期拉取，补充stock_info | stock_info (PG) | advanced |

#### 2.2.2 低频行情数据（文档8，13个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 14 | `daily` | 日线行情 | 时序OHLCV | 按日期+代码批量拉取 freq="1d" | kline (TS) | basic |
| 15 | `weekly` | 周线行情 | 时序OHLCV | 按日期+代码批量拉取 freq="1w" | kline (TS) | basic |
| 16 | `monthly` | 月线行情 | 时序OHLCV | 按日期+代码批量拉取 freq="1M" | kline (TS) | basic |
| 17 | `stk_weekly_monthly` | 周/月行情每日更新 | 时序OHLCV | 按日期拉取，每日更新的周月线 | kline (TS) | basic |
| 18 | `adj_factor` | 复权因子 | 时序因子 | 按日期+代码拉取 | adjustment_factor (PG) | basic |
| 19 | `daily_basic` | 每日指标 | 时序指标 | 按日期拉取（换手率/PE/PB/总市值等） | stock_info (PG) 更新 | basic |
| 20 | `stk_limit` | 每日涨跌停价格 | 时序数据 | 按日期拉取 | stk_limit (PG) | basic |
| 21 | `suspend_d` | 每日停复牌信息 | 事件数据 | 按日期拉取 | suspend_info (PG) | basic |
| 22 | `hsgt_top10` | 沪深股通十大成交股 | 时序数据 | 按日期拉取 | hsgt_top10 (PG) | basic |
| 23 | `ggt_top10` | 港股通十大成交股 | 时序数据 | 按日期拉取 | ggt_top10 (PG) | basic |
| 24 | `ggt_daily` | 港股通每日成交统计 | 时序数据 | 按日期拉取 | ggt_daily (PG) | basic |
| 25 | `ggt_monthly` | 港股通每月成交统计 | 统计数据 | 按月份拉取 | ggt_monthly (PG) | advanced |
| 26 | `bak_daily` | 备用行情 | 时序OHLCV | 按日期拉取 | kline/bak_daily (TS/PG) | advanced |

#### 2.2.3 中频行情数据（文档8，4个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 27 | `stk_mins` | 历史分钟行情 | 时序OHLCV | 按代码+日期+频率拉取 | kline (TS) freq="1m/5m/15m/30m/60m" | special |
| 28 | `rt_k` | 实时日线 | 时序OHLCV | 按代码拉取实时数据 | kline (TS) freq="1d" | special |
| 29 | `rt_min` | 实时分钟 | 时序OHLCV | 按代码拉取实时数据 | kline (TS) | special |
| 30 | `rt_min_daily` | 实时分钟日累计 | 时序OHLCV | 按代码拉取当日累计 | kline (TS) | special |

#### 2.2.4 财务数据（文档7，9个接口 + 7个VIP变体）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 | VIP变体 |
|------|--------|---------|---------|---------|---------|---------|---------|
| 31 | `income` | 利润表 | 财报JSONB | 按报告期+代码拉取 | financial_statement (PG) | basic | income_vip |
| 32 | `balancesheet` | 资产负债表 | 财报JSONB | 按报告期+代码拉取 | financial_statement (PG) | basic | balancesheet_vip |
| 33 | `cashflow` | 现金流量表 | 财报JSONB | 按报告期+代码拉取 | financial_statement (PG) | basic | cashflow_vip |
| 34 | `forecast` | 业绩预告 | 财报数据 | 按报告期+代码拉取 | forecast (PG) | basic | forecast_vip |
| 35 | `express` | 业绩快报 | 财报数据 | 按报告期+代码拉取 | express (PG) | basic | express_vip |
| 36 | `dividend` | 分红送股数据 | 事件数据 | 按代码拉取 | dividend (PG) | basic | — |
| 37 | `fina_indicator` | 财务指标数据 | 财务指标 | 按报告期+代码拉取 | stock_info (PG) 更新 | basic | fina_indicator_vip |
| 38 | `fina_mainbz` | 主营业务构成 | 财务数据 | 按报告期+代码拉取 | fina_mainbz (PG) | basic | fina_mainbz_vip |
| 39 | `disclosure_date` | 财报披露日期表 | 静态数据 | 按报告期拉取 | disclosure_date (PG) | basic | — |

> VIP 批量接口（如 income_vip）使用 advanced 权限级别 Token（5000积分），支持按季度批量获取全市场数据。

#### 2.2.5 参考数据（文档6，12个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 40 | `stk_shock` | 个股异常波动 | 事件数据 | 按日期/代码拉取 | stk_shock (PG) | advanced |
| 41 | `stk_high_shock` | 个股严重异常波动 | 事件数据 | 按日期/代码拉取 | stk_high_shock (PG) | advanced |
| 42 | `stk_alert` | 交易所重点提示证券 | 事件数据 | 按日期/代码拉取 | stk_alert (PG) | advanced |
| 43 | `top10_holders` | 前十大股东 | 报告期快照 | 按代码+报告期拉取 | top_holders (PG) holder_type="top10" | basic |
| 44 | `top10_floatholders` | 前十大流通股东 | 报告期快照 | 按代码+报告期拉取 | top_holders (PG) holder_type="float" | basic |
| 45 | `pledge_stat` | 股权质押统计 | 时序数据 | 按日期拉取 | pledge_stat (PG) | basic |
| 46 | `pledge_detail` | 股权质押明细 | 事件数据 | 按代码拉取 | pledge_detail (PG) | basic |
| 47 | `repurchase` | 股票回购 | 事件数据 | 按代码拉取 | repurchase (PG) | basic |
| 48 | `share_float` | 限售股解禁 | 事件数据 | 按日期拉取 | share_float (PG) | basic |
| 49 | `block_trade` | 大宗交易 | 事件数据 | 按日期拉取 | block_trade (PG) | basic |
| 50 | `stk_holdernumber` | 股东人数 | 报告期快照 | 按代码+日期拉取 | stk_holdernumber (PG) | basic |
| 51 | `stk_holdertrade` | 股东增减持 | 事件数据 | 按代码拉取 | stk_holdertrade (PG) | basic |

#### 2.2.6 特色数据（文档5，13个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 52 | `report_rc` | 券商盈利预测 | 时序数据 | 按日期拉取 | report_rc (PG) | premium |
| 53 | `cyq_perf` | 每日筹码及胜率 | 时序数据 | 按代码+日期拉取 | cyq_perf (PG) | advanced |
| 54 | `cyq_chips` | 每日筹码分布 | 时序数据 | 按代码+日期拉取 | cyq_chips (PG) | advanced |
| 55 | `stk_factor_pro` | 股票技术面因子专业版 | 时序指标 | 按代码+日期拉取 | stk_factor (PG) | advanced |
| 56 | `ccass_hold` | 中央结算系统持股统计 | 时序数据 | 按日期拉取 | ccass_hold (PG) | advanced |
| 57 | `ccass_hold_detail` | 中央结算系统持股明细 | 时序数据 | 按代码+日期拉取 | ccass_hold_detail (PG) | premium |
| 58 | `hk_hold` | 沪深股通持股明细 | 时序数据 | 按日期拉取 | hk_hold (PG) | basic |
| 59 | `stk_auction_o` | 股票开盘集合竞价 | 时序数据 | 按日期拉取 | stk_auction_o (PG) | special |
| 60 | `stk_auction_c` | 股票收盘集合竞价 | 时序数据 | 按日期拉取 | stk_auction_c (PG) | special |
| 61 | `stk_nineturn` | 神奇九转指标 | 时序指标 | 按代码+日期拉取 | stk_nineturn (PG) | advanced |
| 62 | `stk_ah_comparison` | AH股比价 | 时序数据 | 按日期拉取 | stk_ah_comparison (PG) | advanced |
| 63 | `stk_surv` | 机构调研数据 | 事件数据 | 按代码拉取 | stk_surv (PG) | advanced |
| 64 | `broker_recommend` | 券商每月金股 | 月度数据 | 按月份拉取 | broker_recommend (PG) | advanced |

#### 2.2.7 两融及转融通数据（文档4，4个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 65 | `margin` | 融资融券交易汇总 | 时序数据 | 按日期拉取 | margin_data (PG) | basic |
| 66 | `margin_detail` | 融资融券交易明细 | 时序数据 | 按日期+代码拉取 | margin_detail (PG) | basic |
| 67 | `margin_secs` | 融资融券标的（盘前） | 时序数据 | 按日期拉取，每天盘前更新 | margin_secs (PG) | basic |
| 68 | `slb_len` | 转融资交易汇总 | 时序数据 | 按日期拉取 | slb_len (PG) | basic |

#### 2.2.8 资金流向数据（文档3，8个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 69 | `moneyflow` | 个股资金流向 | 时序数据 | 按日期+代码拉取 | money_flow (PG) | basic |
| 70 | `moneyflow_ths` | 个股资金流向（THS） | 时序数据 | 按日期+代码拉取 | moneyflow_ths (PG) | advanced |
| 71 | `moneyflow_dc` | 个股资金流向（DC） | 时序数据 | 按日期+代码拉取 | moneyflow_dc (PG) | advanced |
| 72 | `moneyflow_cnt_ths` | 板块资金流向（THS） | 时序数据 | 按日期拉取 | moneyflow_cnt_ths (PG) | advanced |
| 73 | `moneyflow_ind_ths` | 行业资金流向（THS） | 时序数据 | 按日期拉取 | moneyflow_ind (PG) data_source="THS" | advanced |
| 74 | `moneyflow_ind_dc` | 板块资金流向（DC） | 时序数据 | 按日期拉取 | moneyflow_ind (PG) data_source="DC" | advanced |
| 75 | `moneyflow_mkt_dc` | 大盘资金流向（DC） | 时序数据 | 按日期拉取 | moneyflow_mkt_dc (PG) | advanced |
| 76 | `moneyflow_hsgt` | 沪港通资金流向 | 时序数据 | 按日期拉取 | moneyflow_hsgt (PG) | basic |

#### 2.2.9 打板专题数据（文档2，24个接口）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 77 | `top_list` | 龙虎榜每日统计单 | 时序数据 | 按日期拉取 | top_list (PG) | basic |
| 78 | `top_inst` | 龙虎榜机构交易单 | 时序数据 | 按日期拉取 | top_inst (PG) | advanced |
| 79 | `limit_list_ths` | 同花顺涨跌停榜单 | 时序数据 | 按日期拉取 | limit_list_ths (PG) | premium |
| 80 | `limit_list_d` | 涨跌停和炸板数据 | 时序数据 | 按日期拉取 | limit_list (PG) | advanced |
| 81 | `limit_step` | 涨停股票连板天梯 | 时序数据 | 按日期拉取 | limit_step (PG) | premium |
| 82 | `limit_cpt_list` | 涨停最强板块统计 | 时序数据 | 按日期拉取 | limit_cpt_list (PG) | premium |
| 83 | `ths_index` | 同花顺行业概念板块 | 静态元数据 | 全量拉取 | sector_info (PG) data_source="THS" | advanced |
| 84 | `ths_daily` | 同花顺板块指数行情 | 时序OHLCV | 按代码+日期拉取 | sector_kline (TS) data_source="THS" | advanced |
| 85 | `ths_member` | 同花顺行业概念成分 | 静态元数据 | 按板块代码拉取 | sector_constituent (PG) data_source="THS" | advanced |
| 86 | `dc_index` | 东方财富概念板块 | 静态元数据 | 按日期拉取 | sector_info (PG) data_source="DC" | advanced |
| 87 | `dc_member` | 东方财富概念成分 | 静态元数据 | 按板块代码+日期拉取 | sector_constituent (PG) data_source="DC" | advanced |
| 88 | `dc_daily` | 东方财富概念板块行情 | 时序OHLCV | 按代码+日期拉取 | sector_kline (TS) data_source="DC" | advanced |
| 89 | `stk_auction` | 开盘竞价成交（当日） | 时序数据 | 按日期拉取 | stk_auction (PG) | special |
| 90 | `hm_list` | 市场游资名录 | 静态数据 | 全量拉取 | hm_list (PG) | advanced |
| 91 | `hm_detail` | 游资交易每日明细 | 时序数据 | 按日期拉取 | hm_detail (PG) | premium |
| 92 | `ths_hot` | 同花顺热榜 | 时序数据 | 按日期拉取 | ths_hot (PG) | advanced |
| 93 | `dc_hot` | 东方财富热榜 | 时序数据 | 按日期拉取 | dc_hot (PG) | premium |
| 94 | `tdx_index` | 通达信板块信息 | 静态元数据 | 全量拉取 | sector_info (PG) data_source="TDX" | advanced |
| 95 | `tdx_member` | 通达信板块成分 | 静态元数据 | 按板块代码拉取 | sector_constituent (PG) data_source="TDX" | advanced |
| 96 | `tdx_daily` | 通达信板块行情 | 时序OHLCV | 按代码+日期拉取 | sector_kline (TS) data_source="TDX" | advanced |
| 97 | `kpl_list` | 开盘啦榜单数据 | 时序数据 | 按日期拉取 | kpl_list (PG) | advanced |
| 98 | `kpl_concept_cons` | 开盘啦题材成分 | 静态数据 | 按题材代码拉取（暂无新增数据） | kpl_concept_cons (PG) | advanced |
| 99 | `dc_concept` | 东方财富题材库 | 静态数据 | 按日期拉取 | dc_concept (PG) | advanced |
| 100 | `dc_concept_cons` | 东方财富题材成分 | 静态数据 | 按题材代码+日期拉取 | dc_concept_cons (PG) | advanced |


### 2.3 指数专题数据导入清单

#### 2.3.1 指数基础信息

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 101 | `index_basic` | 指数基本信息 | 静态元数据 | 按市场(SSE/SZSE/CSI)拉取 | index_info (PG) | basic |

#### 2.3.2 指数低频行情（日线/周线/月线）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 102 | `index_daily` | 指数日线行情 | 时序OHLCV | 按日期+指数代码拉取，单次最大8000行 | kline (TS) freq="1d" | advanced（2000积分） |
| 103 | `index_weekly` | 指数周线行情 | 时序OHLCV | 按日期+指数代码拉取，单次最大1000行 | kline (TS) freq="1w" | basic（600积分） |
| 104 | `index_monthly` | 指数月线行情 | 时序OHLCV | 按日期+指数代码拉取，单次最大1000行 | kline (TS) freq="1M" | basic（600积分） |

#### 2.3.3 指数中频行情（实时日线/实时分钟/历史分钟）

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 105 | `rt_idx_k` | 指数实时日线 | 时序OHLCV | 按代码或通配符拉取全部交易所指数 | kline (TS) freq="1d" | special |
| 106 | `rt_idx_min` | 指数实时分钟 | 时序OHLCV | 按代码拉取，单次最大1000行，支持逗号分隔多代码 | kline (TS) | special |
| 107 | `rt_idx_min_daily` | 指数实时分钟日累计 | 时序OHLCV | 按单个指数代码拉取当日累计 | kline (TS) | special |
| 108 | `idx_mins` | 指数历史分钟 | 时序OHLCV | 按代码+日期+频率拉取，单次最大8000行，超10年历史 | kline (TS) freq="1m/5m/15m/30m/60m" | special |

#### 2.3.4 指数成分与行业

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 109 | `index_weight` | 指数成分和权重 | 快照数据 | 按指数代码+日期拉取（建议输入当月首末日） | index_weight (PG) | advanced（2000积分） |
| 110 | `index_classify` | 申万行业分类 | 静态元数据 | 全量拉取（2014版/2021版） | sector_info (PG) data_source="TI" | advanced（2000积分） |
| 111 | `index_member_all` | 申万行业成分（分级） | 静态元数据 | 按分类代码或股票代码拉取，单次最大2000行 | sector_constituent (PG) data_source="TI" | advanced（2000积分） |
| 112 | `sw_daily` | 申万行业指数日行情 | 时序OHLCV | 按日期拉取（默认2021版），单次最大4000行 | sector_kline (TS) data_source="TI" | advanced（5000积分） |
| 113 | `rt_sw_k` | 申万实时行情 | 时序OHLCV | 拉取最新截面数据 | sector_kline (TS) data_source="TI" | special |
| 114 | `ci_index_member` | 中信行业成分 | 静态元数据 | 按分类代码或股票代码拉取，单次最大5000行 | sector_constituent (PG) data_source="CI" | advanced（5000积分） |
| 115 | `ci_daily` | 中信行业指数日行情 | 时序OHLCV | 按日期拉取，单次最大4000条 | sector_kline (TS) data_source="CI" | advanced（5000积分） |

#### 2.3.5 指数指标与统计

| 序号 | 接口名 | 中文说明 | 数据类型 | 导入方法 | 存储目标 | 权限级别 |
|------|--------|---------|---------|---------|---------|---------|
| 116 | `index_dailybasic` | 大盘指数每日指标 | 时序指标 | 按日期拉取（仅6大指数，2004年起） | index_dailybasic (PG) | basic（400积分） |
| 117 | `idx_factor_pro` | 指数技术面因子(专业版) | 时序指标 | 按代码+日期拉取，单次最大8000行 | index_tech (PG) | advanced（5000积分） |
| 118 | `daily_info` | 沪深市场每日交易统计 | 统计数据 | 按日期拉取，单次最大4000行 | market_daily_info (PG) | basic（600积分） |
| 119 | `sz_daily_info` | 深圳市场每日交易情况 | 统计数据 | 按日期拉取，单次最大2000行 | sz_daily_info (PG) | advanced（2000积分） |
| 120 | `index_global` | 国际主要指数 | 时序OHLCV | 按日期拉取，单次最大4000行 | index_global (PG) | advanced（6000积分） |

---

## 三、导入方法说明

### 3.1 导入模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **全量导入** | 不需要日期参数，一次拉取全部数据 | 基础元数据（stock_basic、trade_cal、index_basic 等） |
| **增量导入（按日期范围）** | 用户指定 start_date/end_date | 行情数据、资金流向、打板专题等时序数据 |
| **增量导入（按报告期）** | 用户指定年份+季度 | 财务报表（income、balancesheet、cashflow 等） |
| **按代码导入** | 用户指定 ts_code 列表 | 单只或多只股票的特定数据 |
| **按月份导入** | 用户指定月份范围 | broker_recommend、ggt_monthly 等月度数据 |

### 3.2 数据存储分类

| 存储引擎 | 用途 | 表前缀/标识 |
|---------|------|------------|
| **TimescaleDB (TS)** | 时序行情数据（OHLCV） | kline 超表、sector_kline 超表 |
| **PostgreSQL (PG)** | 业务数据、元数据、财务数据 | 所有其他表 |

### 3.3 去重策略

所有导入均使用 `INSERT ... ON CONFLICT DO NOTHING` 或 `ON CONFLICT DO UPDATE` 策略：
- **DO NOTHING**：行情数据、财务报表等历史数据不变的场景
- **DO UPDATE**：基础信息（stock_basic → stock_info）等需要更新最新状态的场景

### 3.4 频率限制

| 数据类型 | 配置项 | 间隔 | 说明 |
|---------|--------|------|------|
| 行情数据 | `rate_limit_kline` | 0.18s | 约500次/min |
| 财务数据 | `rate_limit_fundamentals` | 0.40s | 约200次/min |
| 资金流向 | `rate_limit_money_flow` | 0.30s | 约300次/min |

### 3.5 四级 Token 权限

| 级别 | 配置项 | 积分范围 | 典型接口 |
|------|--------|---------|---------|
| **basic** | `TUSHARE_TOKEN_BASIC` | ≤2000 积分 | stock_basic, daily, weekly, monthly, adj_factor, daily_basic, income, balancesheet, cashflow, dividend, moneyflow, moneyflow_hsgt, margin, top10_holders, pledge_stat, block_trade, top_list, index_basic, index_weekly, index_monthly, index_dailybasic, daily_info 等 |
| **advanced** | `TUSHARE_TOKEN_ADVANCED` | 2000-6000 积分（含6000） | stock_st, stock_hsgt, bak_basic, ggt_monthly, bak_daily, limit_list_d, top_inst, hm_list, ths_index, ths_daily, ths_member, dc_index, dc_member, dc_daily, tdx_index, tdx_member, tdx_daily, ths_hot, kpl_list, dc_concept, stk_shock, stk_high_shock, stk_alert, cyq_perf, cyq_chips, stk_factor_pro, ccass_hold, stk_nineturn, stk_ah_comparison, stk_surv, broker_recommend, moneyflow_ths, moneyflow_dc, moneyflow_cnt_ths, moneyflow_ind_ths, moneyflow_ind_dc, moneyflow_mkt_dc, VIP批量接口, index_daily, index_weight, index_classify, index_member_all, sw_daily, ci_index_member, ci_daily, idx_factor_pro, sz_daily_info, index_global 等 |
| **premium** | `TUSHARE_TOKEN_PREMIUM` | >6000 积分 | limit_list_ths, limit_step, limit_cpt_list, report_rc, ccass_hold_detail, dc_hot, hm_detail 等 |
| **special** | `TUSHARE_TOKEN_SPECIAL` | 需单独开通 | stk_premarket, stk_mins, rt_k, rt_min, rt_min_daily, stk_auction, stk_auction_o, stk_auction_c, rt_idx_k, rt_idx_min, rt_idx_min_daily, idx_mins, rt_sw_k 等 |

> 原有 `TUSHARE_API_TOKEN` 作为默认 fallback，当对应级别 Token 未配置时自动回退使用。

### 3.6 批量处理策略

- **BATCH_SIZE = 50**：按股票列表分批，每批 50 只股票
- **Celery 异步队列**：所有导入任务分发到 `data_sync` 队列
- **Redis 进度追踪**：键格式 `tushare:import:{task_id}`，每 3 秒前端轮询
- **停止信号**：Redis 键 `tushare:import:stop:{task_id}`，任务每批检查

### 3.7 ts_code 格式转换规则

| 场景 | 输入格式 | 存储格式 | 示例 |
|------|---------|---------|------|
| 股票数据写入 stock_info/kline | 600000.SH | 600000（纯6位） | ts_code.split(".")[0] |
| 指数数据写入 index_info/kline | 000001.SH | 000001.SH（保留后缀） | 原样存储 |
| 用户输入补全 | 600000 | 600000.SH | 6开头→.SH，0/3开头→.SZ |

---

## 四、接口变更记录（相对旧版需求）

### 4.1 新增接口

| 子分类 | 新增接口 |
|--------|---------|
| 基础数据 | stk_premarket, st, stock_hsgt, bse_mapping |
| 行情数据 | rt_k, rt_min, rt_min_daily, stk_weekly_monthly, hsgt_top10, ggt_top10, ggt_daily, ggt_monthly, bak_daily |
| 财务数据 | fina_mainbz, disclosure_date (+7个VIP变体) |
| 参考数据 | stk_shock, stk_high_shock, stk_alert, pledge_stat, pledge_detail, repurchase, share_float |
| 特色数据 | report_rc, cyq_perf, cyq_chips, ccass_hold, ccass_hold_detail, hk_hold, stk_auction_o, stk_auction_c, stk_nineturn, stk_ah_comparison, stk_surv, broker_recommend |
| 资金流向 | moneyflow_ths, moneyflow_dc, moneyflow_cnt_ths |
| 打板专题 | limit_list_ths, limit_cpt_list, ths_daily, dc_daily, stk_auction, tdx_index, tdx_member, tdx_daily, kpl_concept_cons, dc_concept, dc_concept_cons |
| 指数专题 | rt_idx_k（指数实时日线）, rt_idx_min_daily（指数实时分钟日累计）, index_member_all（申万行业成分分级）, ci_index_member（中信行业成分）, rt_sw_k（申万实时行情） |

### 4.2 替换接口

| 旧接口 | 新接口 | 说明 |
|--------|--------|------|
| daily_share | stk_premarket | 新增涨跌停价格字段 |
| hs_const | stock_hsgt | 沪深港通股票列表 |
| margin_target | margin_secs | 融资融券标的（盘前），新增 trade_date |
| ths_limit | limit_list_ths | 同花顺涨跌停榜单 |
| stk_factor | stk_factor_pro | 仅保留专业版 |
| index_1min_realtime | rt_idx_min | 指数实时分钟，文档接口名更新 |
| index_min | idx_mins | 指数历史分钟，文档接口名更新 |
| index_tech | idx_factor_pro | 指数技术面因子专业版，文档接口名更新 |

### 4.3 移除接口

| 接口 | 说明 |
|------|------|
| stk_delist | 文档中未出现 |
| slb_sec | 文档中未出现 |
| stk_account | 文档中未出现 |

### 4.4 分类调整

| 接口 | 旧分类 | 新分类 |
|------|--------|--------|
| namechange, stock_company, stk_managers, stk_rewards | 参考数据 | 基础数据 |
| top10_holders, top10_floatholders, stk_holdernumber, stk_holdertrade, block_trade | 特色数据 | 参考数据 |
| stk_limit | 特色数据/打板专题 | 行情数据（低频） |

### 4.5 指数专题权限级别调整

| 接口 | 旧权限级别 | 新权限级别 | 依据 |
|------|-----------|-----------|------|
| index_daily | basic | advanced | 文档：2000积分可调取 |
| index_weekly | basic | basic | 文档：600积分可调取 |
| index_monthly | basic | basic | 文档：600积分可调取 |
| index_weight | basic | advanced | 文档：2000积分可调取 |
| index_classify | basic | advanced | 文档：2000积分可调取 |
| sw_daily | basic | advanced | 文档：5000积分可调取 |
| ci_daily | basic | advanced | 文档：5000积分可调取 |
| index_dailybasic | basic | basic | 文档：400积分可调取 |
| idx_factor_pro（原 index_tech） | special | advanced | 文档：5000积分可调取 |
| daily_info | basic | basic | 文档：600积分可调取 |
| sz_daily_info | basic | advanced | 文档：2000积分可调取 |
| index_global | basic | advanced | 文档：6000积分可调取（属于 advanced 范围） |
| rt_idx_k（新增） | — | special | 文档：需单独开权限 |
| rt_idx_min（替代 index_1min_realtime） | basic | special | 文档：需单独开权限 |
| rt_idx_min_daily（新增） | — | special | 文档：需单独开权限 |
| idx_mins（替代 index_min） | basic | special | 文档：需单独开权限 |
| index_member_all（新增） | — | advanced | 文档：2000积分可调取 |
| ci_index_member（新增） | — | advanced | 文档：5000积分可调取 |
| rt_sw_k（新增） | — | special | 文档：需单独开权限 |