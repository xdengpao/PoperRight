# Tushare 导入数据与平台现有数据存储差异评估

## 一、行情数据

### 现有存储

| 表名 | 引擎 | 字段 | 数据来源 |
|------|------|------|---------|
| `kline` | TimescaleDB | time, symbol(纯6位), freq, OHLCV, turnover, vol_ratio, limit_up, limit_down, adj_type | Tushare daily + AkShare + 本地CSV |
| `adjustment_factor` | TimescaleDB | symbol, trade_date, adj_type, adj_factor | Tushare adj_factor |

### Tushare 导入数据

| 接口 | 字段 | 差异分析 |
|------|------|---------|
| `daily` | ts_code, trade_date, open/high/low/close, vol, amount, pct_chg, change, pre_close | 核心 OHLCV 完全匹配，Tushare 多了 pct_chg/change/pre_close |
| `weekly/monthly` | 同 daily | 完全匹配，freq 不同 |
| `stk_mins` | ts_code, trade_date, open/high/low/close, vol, amount | 完全匹配 |
| `adj_factor` | ts_code, trade_date, adj_factor | 完全匹配 |
| `daily_basic` | ts_code, trade_date, turnover_rate, pe_ttm, pb, ps_ttm, dv_ttm, total_mv, circ_mv | 部分字段(turnover)可写入 kline，估值字段写入 stock_info |

### 评估结论：✅ 可统一存储

- **股票 K 线**：Tushare daily/weekly/monthly/stk_mins → 直接写入现有 `kline` 超表，字段完全兼容。symbol 需从 ts_code 转为纯 6 位。
- **指数 K 线**：Tushare index_daily/index_weekly/index_monthly/index_min → 直接写入现有 `kline` 超表，symbol 保留 ts_code 格式（如 000001.SH）。当前系统已在 `fetch_market_overview` 中用此格式查询指数。
- **复权因子**：Tushare adj_factor → 直接写入现有 `adjustment_factor` 表，完全兼容。
- **daily_basic 估值字段**：turnover_rate 写入 kline.turnover，pe_ttm/pb/total_mv 更新 stock_info 对应字段。
- **无需新建行情表**。

---

## 二、板块数据

### 现有存储

| 表名 | 引擎 | 字段 | 数据来源 |
|------|------|------|---------|
| `sector_info` | PostgreSQL | sector_code, name, sector_type(CONCEPT/INDUSTRY/REGION/STYLE), data_source(DC/TI/TDX), list_date, constituent_count | AkShare 东方财富 |
| `sector_constituent` | PostgreSQL | trade_date, sector_code, data_source, symbol, stock_name | AkShare 东方财富 |
| `sector_kline` | TimescaleDB | time, sector_code, data_source, freq, OHLCV, turnover, change_pct | AkShare 东方财富 |

### Tushare 导入数据

| 接口 | 对应现有表 | 差异分析 |
|------|-----------|---------|
| `index_classify`（申万行业分类） | sector_info | ✅ 可复用。sector_type="INDUSTRY", data_source="TI" |
| `sw_daily`（申万行业日行情） | sector_kline | ✅ 可复用。data_source="TI" |
| `ci_daily`（中信行业日行情） | sector_kline | ✅ 可复用。data_source="CI"（需在 DataSource 枚举中新增 "CI"） |
| `ths_index`（同花顺概念/行业板块） | sector_info | ✅ 可复用。data_source="THS"（需新增枚举值） |
| `ths_member`（同花顺成分股） | sector_constituent | ✅ 可复用。data_source="THS" |
| `dc_index`（东财概念板块） | sector_info | ✅ 可复用。data_source="DC"（已有枚举值） |
| `dc_member`（东财概念成分） | sector_constituent | ✅ 可复用。data_source="DC" |
| `index_weight`（指数成分权重） | — | ❌ 不可复用。sector_constituent 无 weight 字段，且 index_weight 是指数成分而非板块成分，语义不同 |

### 评估结论：✅ 大部分可统一存储

- **申万/中信行业分类** → 写入现有 `sector_info`，通过 data_source 区分来源。
- **申万/中信行业行情** → 写入现有 `sector_kline`，通过 data_source 区分。
- **同花顺/东财概念板块** → 写入现有 `sector_info` + `sector_constituent`，通过 data_source 区分。
- **需要的改动**：DataSource 枚举新增 `CI = "CI"`（中信）和 `THS = "THS"`（同花顺）。
- **index_weight 需独立表**：指数成分权重有 weight 字段且语义不同于板块成分，保留独立的 `index_weight` 表。
- **ths_index/dc_index 可选方案**：需求中设计了独立的 ths_index/dc_index 表，但实际上可以复用 sector_info（data_source 区分）。**建议统一到 sector_info**，减少表数量。同理 ths_member/dc_member 可统一到 sector_constituent。

---

## 三、基本面数据

### 现有存储

| 表名 | 引擎 | 字段 | 数据来源 |
|------|------|------|---------|
| `stock_info` | PostgreSQL | symbol, name, market, board, list_date, is_st, is_delisted, pledge_ratio, pe_ttm, pb, roe, market_cap, industry_code, industry_name, updated_at | Tushare stock_basic + FundamentalAdapter |

### Tushare 导入数据

| 接口 | 对应现有表 | 差异分析 |
|------|-----------|---------|
| `stock_basic` | stock_info | ✅ 可复用。ts_code→symbol 转换后直接 upsert |
| `stock_company` | — | ❌ 新增。stock_info 无 chairman/secretary/reg_capital 等公司治理字段，字段差异大，建议独立表 |
| `fina_indicator` | stock_info | ✅ 部分复用。pe_ttm/pb/roe 更新到 stock_info |
| `income/balancesheet/cashflow` | — | ❌ 新增。完整财报数据量大、字段多，stock_info 无法承载，需 financial_statement 表（JSONB 存储） |
| `forecast` | — | ❌ 新增。业绩预告有独立的 type/p_change_min/max 等字段 |
| `express` | — | ❌ 新增。业绩快报有独立的 revenue/n_income 等字段 |
| `dividend` | — | ❌ 新增。分红送股有独立的 stk_div/cash_div 等字段 |
| `daily_basic` | stock_info | ✅ 部分复用。pe_ttm/pb/total_mv 更新到 stock_info |

### 评估结论：⚠️ 部分可统一，部分需新建

- **stock_basic / fina_indicator / daily_basic** → 估值摘要字段（pe_ttm, pb, roe, market_cap）更新到现有 `stock_info`，**可统一**。
- **income / balancesheet / cashflow** → 完整财报数据字段极多（利润表 50+ 字段），不适合塞入 stock_info。**需新建 financial_statement 表**，用 JSONB 存储原始数据，report_type 区分三表。
- **forecast / express / dividend / stock_company** → 各有独立语义和字段结构，**需独立新建表**。
- **FundamentalsData dataclass** 中的 forecast_type/forecast_net_profit 等字段目前只是内存传输用，未持久化到数据库。Tushare 导入后这些数据将有独立的持久化表。

---

## 四、资金面数据

### 现有存储

| 存储位置 | 字段 | 数据来源 |
|---------|------|---------|
| `MoneyFlowData` (内存 dataclass) | symbol, trade_date, main_net_inflow, main_inflow, main_outflow, large_order_net, north_net_inflow, dragon_tiger_net, block_trade_amount 等 | Tushare moneyflow + AkShare |
| 无持久化表 | — | 当前资金流向数据仅在 API 请求时实时拉取，**未持久化到数据库** |

### Tushare 导入数据

| 接口 | 对应现有存储 | 差异分析 |
|------|------------|---------|
| `moneyflow` | MoneyFlowData (内存) | 字段基本匹配，但当前无持久化表 |
| `moneyflow_hsgt` | 无 | 沪深港通资金流向，当前无持久化 |
| `moneyflow_ind_dc/ths` | 无 | 行业资金流向，当前无持久化 |
| `moneyflow_mkt_dc` | 无 | 大盘资金流向，当前无持久化 |

### 评估结论：❌ 需全部新建

- **当前系统资金流向数据完全没有持久化**，仅在 API 请求时通过 DataSourceRouter 实时拉取 Tushare/AkShare 数据返回给前端。
- Tushare 导入需要新建所有资金流向相关表：`money_flow`、`moneyflow_hsgt`、`moneyflow_ind`、`moneyflow_mkt_dc`。
- 导入后，现有的 `DataSourceRouter.fetch_money_flow()` 可以优先从本地 money_flow 表查询，无数据时再回退到实时 API，与 kline 的查询逻辑一致。

---

## 五、汇总建议

### 可统一存储（复用现有表）

| Tushare 数据 | 复用表 | 说明 |
|-------------|--------|------|
| daily/weekly/monthly/stk_mins | `kline` (TS) | OHLCV 完全兼容，symbol 格式转换即可 |
| index_daily/weekly/monthly/min | `kline` (TS) | symbol 保留 ts_code 格式 |
| adj_factor | `adjustment_factor` (TS) | 完全兼容 |
| stock_basic | `stock_info` (PG) | ts_code→symbol 转换后 upsert |
| fina_indicator / daily_basic | `stock_info` (PG) | 更新 pe_ttm/pb/roe/market_cap 字段 |
| index_classify / ths_index / dc_index | `sector_info` (PG) | 通过 data_source 区分来源 |
| sw_daily / ci_daily | `sector_kline` (TS) | 通过 data_source 区分来源 |
| ths_member / dc_member | `sector_constituent` (PG) | 通过 data_source 区分来源 |

### 需新建表（无法复用）

| Tushare 数据 | 新建表 | 原因 |
|-------------|--------|------|
| income/balancesheet/cashflow | `financial_statement` | 财报字段极多，JSONB 存储 |
| forecast | `forecast` | 独立语义（业绩预告类型/预测范围） |
| express | `express` | 独立语义（业绩快报摘要） |
| dividend | `dividend` | 独立语义（分红送股明细） |
| stock_company | `stock_company` | 公司治理字段与 stock_info 差异大 |
| moneyflow | `money_flow` | 当前无持久化表 |
| moneyflow_hsgt | `moneyflow_hsgt` | 当前无持久化表 |
| moneyflow_ind_dc/ths | `moneyflow_ind` | 当前无持久化表 |
| moneyflow_mkt_dc | `moneyflow_mkt_dc` | 当前无持久化表 |
| index_weight | `index_weight` | 指数成分权重，与板块成分语义不同 |
| 打板专题全部接口 | 各独立表 | 全新数据类型 |
| 其他基础/参考数据 | 各独立表 | 全新数据类型 |

### 需要的代码改动

1. **DataSource 枚举**（`app/models/sector.py`）：新增 `CI = "CI"` 和 `THS = "THS"`
2. **需求文档调整建议**：将 ths_index/dc_index/ths_member/dc_member 改为复用 sector_info/sector_constituent，减少 4 个新表
3. **DataSourceRouter 优化**：资金流向查询可增加"先查本地 money_flow 表，无数据再实时拉取"的逻辑
