# Implementation Plan: Tushare 数据在线导入

## Overview

本实现计划将 Tushare 数据在线导入功能分解为可增量执行的编码任务。采用自底向上的构建顺序：先扩展配置和枚举 → 创建数据模型（85张表） → 数据库迁移 → 核心服务层（Registry 120+ 接口 → Import Service 四级Token → Import Task） → REST API → 前端组件（四级Token状态） → 路由/菜单集成。每个任务构建在前一个任务之上，确保无孤立代码。

## Tasks

- [x] 1. 配置扩展与枚举更新
  - [x] 1.1 扩展 Settings 添加四级 Token 配置
    - 在 `app/core/config.py` 的 `Settings` 类中新增 `tushare_token_basic`、`tushare_token_advanced`、`tushare_token_premium`、`tushare_token_special` 四个字符串配置项，默认值为空字符串
    - 在 `.env.example` 中添加对应的环境变量示例：`TUSHARE_TOKEN_BASIC`、`TUSHARE_TOKEN_ADVANCED`、`TUSHARE_TOKEN_PREMIUM`、`TUSHARE_TOKEN_SPECIAL`
    - _Requirements: 22a.1, 22a.7_

  - [x] 1.2 扩展 DataSource 枚举
    - 在 `app/models/sector.py` 的 `DataSource` 枚举中新增 `CI = "CI"`（中信行业）和 `THS = "THS"`（同花顺概念/行业板块）
    - _Requirements: 25.47, 25.48_

- [x] 2. 数据模型定义（新建表 ORM 模型）
  - [x] 2.1 创建导入日志和基础数据模型
    - 新建 `app/models/tushare_import.py`，定义以下 ORM 模型（继承 PGBase，使用 Mapped[] + mapped_column() 声明式风格）：
      - `TushareImportLog`：导入日志表（id, api_name, params_json/JSONB, status, record_count, error_message, celery_task_id, started_at, finished_at）
      - `TradeCalendar`：交易日历表（exchange+cal_date 复合主键, is_open）
      - `NewShare`：IPO 新股表（ts_code 主键, sub_code, name, ipo_date, issue_date, amount, market_amount, price, pe, limit_amount, funds, ballot）
      - `StockST`：ST 股票表（ts_code, name, is_st, st_date, st_type）
      - `StWarning`：ST 风险警示板表（ts_code, trade_date, name, close, pct_chg, vol, amount，唯一约束 ts_code+trade_date）
      - `StkPremarket`：每日股本盘前表（ts_code, trade_date, total_share, float_share, free_share, total_mv, float_mv, up_limit, down_limit，唯一约束 ts_code+trade_date）
      - `StockHsgt`：沪深港通股票列表表（ts_code, hs_type, in_date, out_date, is_new）
      - `StockNamechange`：股票曾用名表（ts_code, name, start_date, end_date, change_reason）
      - `StockCompany`：上市公司基本信息表（ts_code 主键, chairman, manager, secretary, reg_capital, setup_date, province, city, website）
      - `StkManagers`：上市公司管理层表（ts_code, ann_date, name, gender, lev, title, edu, national, birthday, begin_date, end_date）
      - `StkRewards`：管理层薪酬和持股表（ts_code, ann_date, name, title, reward, hold_vol）
      - `BseMapping`：北交所新旧代码对照表（old_code, new_code, name, list_date）
      - `SuspendInfo`：停复牌信息表（ts_code, suspend_date, resume_date, suspend_type）
    - _Requirements: 25.9, 25.1, 25.35, 25.36, 25.49, 25.37, 25.20, 25.19, 25.18, 25.22, 25.21, 25.50, 25.8, 3.2-3.16_

  - [x] 2.2 创建行情数据相关模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `StkLimit`：每日涨跌停价格表（ts_code, trade_date, up_limit, down_limit，唯一约束 ts_code+trade_date）
      - `HsgtTop10`：沪深股通十大成交股表（trade_date, ts_code, name, close, change, rank, market_type, amount, net_amount, buy, sell，唯一约束 trade_date+ts_code+market_type）
      - `GgtTop10`：港股通十大成交股表（trade_date, ts_code, name, close, p_change, rank, market_type, amount, net_amount, buy, sell，唯一约束 trade_date+ts_code+market_type）
      - `GgtDaily`：港股通每日成交统计表（trade_date, buy_amount, buy_volume, sell_amount, sell_volume，唯一约束 trade_date）
      - `GgtMonthly`：港股通每月成交统计表（month, buy_amount, buy_volume, sell_amount, sell_volume，唯一约束 month）
    - _Requirements: 25.25, 25.51, 25.52, 25.53, 25.54, 4.8-4.14_

  - [x] 2.3 创建财务数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `FinancialStatement`：财务报表表（ts_code, ann_date, end_date, report_type, data_json/JSONB，唯一约束 ts_code+end_date+report_type）
      - `Dividend`：分红送股表（ts_code, ann_date, end_date, div_proc, stk_div, cash_div）
      - `Forecast`：业绩预告表（ts_code, ann_date, end_date, type, p_change_min/max, net_profit_min/max, summary，唯一约束 ts_code+end_date）
      - `Express`：业绩快报表（ts_code, ann_date, end_date, revenue, operate_profit, total_profit, n_income, total_assets, total_hldr_eqy_exc_min_int, diluted_eps, yoy_net_profit, bps, perf_summary，唯一约束 ts_code+end_date）
      - `FinaMainbz`：主营业务构成表（ts_code, end_date, bz_item, bz_sales, bz_profit, bz_cost, curr_type，唯一约束 ts_code+end_date+bz_item）
      - `DisclosureDate`：财报披露日期表（ts_code, ann_date, end_date, pre_date, actual_date，唯一约束 ts_code+end_date）
    - _Requirements: 25.2, 25.3, 25.38, 25.39, 25.55, 25.56, 5.3-5.9_

  - [x] 2.4 创建参考数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `StkShock`：个股异常波动表（ts_code, trade_date, shock_type, pct_chg, vol, amount，唯一约束 ts_code+trade_date+shock_type）
      - `StkHighShock`：个股严重异常波动表（ts_code, trade_date, shock_type, pct_chg, vol, amount，唯一约束 ts_code+trade_date+shock_type）
      - `StkAlert`：交易所重点提示证券表（ts_code, trade_date, alert_type, alert_desc）
      - `TopHolders`：前十大股东表（ts_code, ann_date, end_date, holder_name, hold_amount, hold_ratio, holder_type，唯一约束 ts_code+end_date+holder_name+holder_type）
      - `PledgeStat`：股权质押统计表（ts_code, end_date, pledge_count, unrest_pledge, rest_pledge, total_share, pledge_ratio，唯一约束 ts_code+end_date）
      - `PledgeDetail`：股权质押明细表（ts_code, ann_date, holder_name, pledge_amount, start_date, end_date, is_release）
      - `Repurchase`：股票回购表（ts_code, ann_date, end_date, proc, exp_date, vol, amount, high_limit, low_limit）
      - `ShareFloat`：限售股解禁表（ts_code, ann_date, float_date, float_share, float_ratio, holder_name, share_type）
      - `BlockTrade`：大宗交易表（ts_code, trade_date, price, vol, amount, buyer, seller，唯一约束 ts_code+trade_date+buyer+seller）
      - `StkHoldernumber`：股东人数表（ts_code, ann_date, end_date, holder_num, holder_num_change）
      - `StkHoldertrade`：股东增减持表（ts_code, ann_date, holder_name, change_vol, change_ratio, after_vol, after_ratio, in_de）
    - _Requirements: 25.57, 25.58, 25.59, 25.14, 25.60, 25.61, 25.62, 25.63, 25.13, 25.23, 25.24, 6.1-6.12_

  - [x] 2.5 创建特色数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `ReportRc`：券商盈利预测表（ts_code, report_date, broker_name, analyst_name, target_price, rating, eps_est）
      - `CyqPerf`：每日筹码及胜率表（ts_code, trade_date, his_low, his_high, cost_5pct, cost_15pct, cost_50pct, cost_85pct, cost_95pct, weight_avg, winner_rate，唯一约束 ts_code+trade_date）
      - `CyqChips`：每日筹码分布表（ts_code, trade_date, price, percent）
      - `StkFactor`：股票技术面因子表（ts_code, trade_date, close, macd_dif, macd_dea, macd, kdj_k, kdj_d, kdj_j, rsi_6, rsi_12, rsi_24, boll_upper, boll_mid, boll_lower, cci, wr, dmi, trix, bias，唯一约束 ts_code+trade_date）
      - `CcassHold`：中央结算系统持股统计表（ts_code, trade_date, participant_id, participant_name, hold_amount, hold_ratio）
      - `CcassHoldDetail`：中央结算系统持股明细表（ts_code, trade_date, participant_id, participant_name, hold_amount, hold_ratio）
      - `HkHold`：沪深股通持股明细表（ts_code, trade_date, code, vol, ratio, exchange，唯一约束 ts_code+trade_date+exchange）
      - `StkAuctionO`：股票开盘集合竞价表（ts_code, trade_date, open, vol, amount，唯一约束 ts_code+trade_date）
      - `StkAuctionC`：股票收盘集合竞价表（ts_code, trade_date, close, vol, amount，唯一约束 ts_code+trade_date）
      - `StkNineturn`：神奇九转指标表（ts_code, trade_date, turn_type, turn_number，唯一约束 ts_code+trade_date+turn_type）
      - `StkAhComparison`：AH股比价表（ts_code, trade_date, a_close, h_close, ah_ratio，唯一约束 ts_code+trade_date）
      - `StkSurv`：机构调研数据表（ts_code, surv_date, fund_name, surv_type, participants）
      - `BrokerRecommend`：券商每月金股表（month, broker, ts_code, name, rating）
    - _Requirements: 25.64-25.75, 7.1-7.13_

  - [x] 2.6 创建两融及转融通数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `MarginData`：融资融券汇总表（trade_date, exchange_id, rzye, rzmre, rzche, rqye, rqmcl, rzrqye，唯一约束 trade_date+exchange_id）
      - `MarginDetail`：融资融券交易明细表（ts_code, trade_date, rzye, rzmre, rzche, rqye, rqmcl, rqyl，唯一约束 ts_code+trade_date）
      - `MarginSecs`：融资融券标的盘前表（ts_code, trade_date, mg_type, is_new）
      - `SlbLen`：转融资交易汇总表（ts_code, trade_date, len_rate, len_amt）
    - _Requirements: 25.10, 25.11, 25.12, 25.26, 8.1-8.4_

  - [x] 2.7 创建资金流向数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `MoneyFlow`：个股资金流向表（ts_code, trade_date, buy_sm/md/lg/elg_amount, sell_sm/md/lg/elg_amount, net_mf_amount，唯一约束 ts_code+trade_date）
      - `MoneyflowThs`：个股资金流向THS表（ts_code, trade_date, buy_sm_amount, sell_sm_amount, buy_md_amount, sell_md_amount, buy_lg_amount, sell_lg_amount, buy_elg_amount, sell_elg_amount, net_mf_amount，唯一约束 ts_code+trade_date）
      - `MoneyflowDc`：个股资金流向DC表（ts_code, trade_date, buy_sm_amount, sell_sm_amount, buy_md_amount, sell_md_amount, buy_lg_amount, sell_lg_amount, buy_elg_amount, sell_elg_amount, net_mf_amount，唯一约束 ts_code+trade_date）
      - `MoneyflowCntThs`：板块资金流向THS表（trade_date, ts_code, name, buy_amount, sell_amount, net_amount）
      - `MoneyflowInd`：行业资金流向表（trade_date, industry_name, data_source, buy_amount, sell_amount, net_amount）
      - `MoneyflowHsgt`：沪深港通资金流向表（trade_date, ggt_ss, ggt_sz, hgt, sgt, north_money, south_money，唯一约束 trade_date）
      - `MoneyflowMktDc`：大盘资金流向表（trade_date, close, change, pct_change, net_mf_amount, net_mf_amount_rate, buy/sell_elg/lg/md/sm_amount，唯一约束 trade_date）
    - _Requirements: 25.7, 25.76, 25.77, 25.78, 25.28, 25.27, 25.46, 9.2-9.9_

  - [x] 2.8 创建打板专题数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `TopList`：龙虎榜每日统计单表（trade_date, ts_code, name, close, pct_change, turnover_rate, amount, l_sell, l_buy, l_amount, net_amount, net_rate, amount_rate, float_values, reason，唯一约束 trade_date+ts_code+reason）
      - `TopInst`：龙虎榜机构交易单表（trade_date, ts_code, exalter, buy, buy_rate, sell, sell_rate, net_buy，唯一约束 trade_date+ts_code+exalter）
      - `LimitListThs`：同花顺涨跌停榜单表（trade_date, ts_code, name, close, pct_chg, fd_amount, first_time, last_time, open_times, limit，唯一约束 ts_code+trade_date+limit）
      - `LimitList`：涨跌停和炸板数据表（ts_code, trade_date, industry, close, pct_chg, amount, limit_amount, float_mv, total_mv, turnover_ratio, fd_amount, first_time, last_time, open_times, up_stat, limit_times, limit，唯一约束 ts_code+trade_date+limit）
      - `LimitStep`：涨停股票连板天梯表（ts_code, trade_date, name, close, pct_chg, step, limit_order, amount, turnover_ratio, fd_amount, first_time, last_time, open_times，唯一约束 ts_code+trade_date）
      - `LimitCptList`：涨停最强板块统计表（trade_date, concept_name, limit_count, up_count, down_count, amount）
      - `StkAuction`：开盘竞价成交当日表（ts_code, trade_date, open, vol, amount, bid_price, bid_vol，唯一约束 ts_code+trade_date）
      - `HmList`：游资名录表（hm_name, hm_code, market, desc）
      - `HmDetail`：游资每日明细表（trade_date, ts_code, hm_name, buy_amount, sell_amount, net_amount）
      - `ThsHot`：同花顺热榜表（trade_date, ts_code, name, rank, pct_chg, hot_value）
      - `DcHot`：东方财富热榜表（trade_date, ts_code, name, rank, pct_chg, hot_value）
      - `KplList`：开盘啦榜单表（trade_date, ts_code, name, close, pct_chg, tag）
      - `KplConceptCons`：开盘啦题材成分表（concept_code, ts_code, name）
      - `DcConcept`：东方财富题材库表（concept_code, concept_name, src）
      - `DcConceptCons`：东方财富题材成分表（concept_code, ts_code, name）
    - _Requirements: 25.33, 25.34, 25.42, 25.15, 25.41, 25.79, 25.80, 25.29, 25.30, 25.44, 25.43, 25.45, 25.81, 25.82, 25.83, 10.1-10.24_

  - [x] 2.9 创建指数专题数据模型
    - 在 `app/models/tushare_import.py` 中新增以下 ORM 模型：
      - `IndexInfo`：指数基本信息表（ts_code 主键, name, market, publisher, category, base_date, base_point, list_date）
      - `IndexWeight`：指数成分权重表（index_code, con_code, trade_date, weight，唯一约束 index_code+con_code+trade_date）
      - `IndexDailybasic`：大盘指数每日指标表（ts_code, trade_date, pe, pb, turnover_rate, total_mv, float_mv，唯一约束 ts_code+trade_date）
      - `IndexTech`：指数技术面因子表（ts_code, trade_date, close, macd_dif, macd_dea, macd, kdj_k, kdj_d, kdj_j, rsi_6, rsi_12, boll_upper, boll_mid, boll_lower，唯一约束 ts_code+trade_date）
      - `IndexGlobal`：国际主要指数表（ts_code, trade_date, open, close, high, low, pre_close, change, pct_chg, vol, amount，唯一约束 ts_code+trade_date）
      - `MarketDailyInfo`：沪深市场每日交易统计表（trade_date, exchange, ts_code, ts_name, com_count, total_share, float_share, total_mv, float_mv, amount, vol, trans_count，唯一约束 trade_date+exchange+ts_code）
      - `SzDailyInfo`：深圳市场每日交易情况表（trade_date, ts_code, count, amount, vol, total_share, total_mv, float_share, float_mv，唯一约束 trade_date+ts_code）
    - _Requirements: 25.4, 25.5, 25.6, 25.17, 25.16, 25.31, 25.32, 11.3, 13.2, 16.2, 17.2, 18.1, 18.2, 19.2_

- [x] 3. 数据库迁移
  - [x] 3.1 创建 Alembic 迁移脚本
    - 运行 `alembic revision --autogenerate -m "add tushare import tables v2"` 生成迁移脚本
    - 在迁移脚本中添加 DataSource 枚举扩展的 `ALTER TYPE` 语句（新增 CI、THS 值）
    - 运行 `alembic upgrade head` 验证迁移成功
    - _Requirements: 25.84_

- [x] 4. Checkpoint - 确保数据模型和迁移正确
  - 确保所有模型定义无语法错误，Alembic 迁移脚本可正常执行。如有问题请向用户确认。

- [x] 5. API_Registry 接口注册表
  - [x] 5.1 创建注册表核心框架
    - 新建 `app/services/data_engine/tushare_registry.py`
    - 实现 `TokenTier`（含 BASIC/ADVANCED/PREMIUM/SPECIAL 四级）、`CodeFormat`、`StorageEngine`、`ParamType`（含 DATE_RANGE/STOCK_CODE/INDEX_CODE/MARKET/REPORT_PERIOD/FREQ/HS_TYPE/SECTOR_CODE/MONTH_RANGE/CONCEPT_CODE）、`RateLimitGroup` 枚举
    - 实现 `FieldMapping`、`ApiEntry`（含 vip_variant 字段）数据类
    - 实现 `TUSHARE_API_REGISTRY` 全局字典和 `register()`、`get_entry()`、`get_all_entries()`、`get_entries_by_category()`、`get_entries_by_subcategory()` 函数
    - _Requirements: 22a.2, 26.4_

  - [x] 5.2 注册基础数据接口（13个）
    - 在 `tushare_registry.py` 中注册以下接口的 ApiEntry：
      - stock_basic、stk_premarket、trade_cal、stock_st、st、stock_hsgt、namechange、stock_company、stk_managers、stk_rewards、bse_mapping、new_share、bak_basic
    - 每个 ApiEntry 包含完整的 api_name、label、category、subcategory、token_tier、target_table、storage_engine、code_format、conflict_columns、conflict_action、field_mappings、required_params、optional_params、rate_limit_group、batch_by_code 配置
    - _Requirements: 3.1-3.16_

  - [x] 5.3 注册行情数据低频接口（13个）
    - 注册以下接口：daily、weekly、monthly、stk_weekly_monthly、adj_factor、daily_basic、stk_limit、suspend_d、hsgt_top10、ggt_top10、ggt_daily、ggt_monthly、bak_daily
    - _Requirements: 4.1-4.15_

  - [x] 5.4 注册行情数据中频接口（4个）
    - 注册以下接口：stk_mins、rt_k、rt_min、rt_min_daily
    - _Requirements: 4a.1-4a.9_

  - [x] 5.5 注册财务数据接口（9个 + VIP 变体）
    - 注册以下接口：income、balancesheet、cashflow、fina_indicator、dividend、forecast、express、fina_mainbz、disclosure_date
    - 为 income/balancesheet/cashflow/forecast/express/fina_indicator/fina_mainbz 标注 vip_variant 字段（如 income_vip），VIP 接口使用 advanced 权限级别
    - _Requirements: 5.1-5.11_

  - [x] 5.6 注册参考数据接口（12个）
    - 注册以下接口：stk_shock、stk_high_shock、stk_alert、top10_holders、top10_floatholders、pledge_stat、pledge_detail、repurchase、share_float、block_trade、stk_holdernumber、stk_holdertrade
    - _Requirements: 6.1-6.13_

  - [x] 5.7 注册特色数据接口（13个）
    - 注册以下接口：report_rc、cyq_perf、cyq_chips、stk_factor_pro、ccass_hold、ccass_hold_detail、hk_hold、stk_auction_o、stk_auction_c、stk_nineturn、stk_ah_comparison、stk_surv、broker_recommend
    - 标注权限级别：stk_factor_pro=advanced、stk_auction_o/stk_auction_c=special、report_rc=premium、ccass_hold_detail=premium
    - _Requirements: 7.1-7.15_

  - [x] 5.8 注册两融及转融通接口（4个）
    - 注册以下接口：margin、margin_detail、margin_secs、slb_len
    - _Requirements: 8.1-8.6_

  - [x] 5.9 注册资金流向数据接口（8个）
    - 注册以下接口：moneyflow、moneyflow_ths、moneyflow_dc、moneyflow_cnt_ths、moneyflow_ind_ths、moneyflow_ind_dc、moneyflow_mkt_dc、moneyflow_hsgt
    - _Requirements: 9.1-9.10_

  - [x] 5.10 注册打板专题数据接口（24个）
    - 注册以下接口：top_list、top_inst、limit_list_ths、limit_list_d、limit_step、limit_cpt_list、ths_index、ths_daily、ths_member、dc_index、dc_member、dc_daily、stk_auction、hm_list、hm_detail、ths_hot、dc_hot、tdx_index、tdx_member、tdx_daily、kpl_list、kpl_concept_cons、dc_concept、dc_concept_cons
    - 板块类接口（ths_index/dc_index/tdx_index）target_table 设为 sector_info，成分类（ths_member/dc_member/tdx_member）设为 sector_constituent，行情类（ths_daily/dc_daily/tdx_daily）设为 sector_kline
    - _Requirements: 10.1-10.25_

  - [x] 5.11 注册指数专题类接口（20个）
    - 注册以下接口：
      - 指数基本信息：index_basic（basic）
      - 指数低频行情：index_daily（advanced，2000积分）、index_weekly（basic，600积分）、index_monthly（basic，600积分）
      - 指数中频行情：rt_idx_k（special，指数实时日线）、rt_idx_min（special，指数实时分钟）、rt_idx_min_daily（special，指数实时分钟日累计）、idx_mins（special，指数历史分钟）
      - 指数成分和权重：index_weight（advanced，2000积分）
      - 申万行业：index_classify（advanced，2000积分）、index_member_all（advanced，2000积分，申万行业成分分级）、sw_daily（advanced，5000积分）、rt_sw_k（special，申万实时行情）
      - 中信行业：ci_index_member（advanced，5000积分，中信行业成分）、ci_daily（advanced，5000积分）
      - 大盘指数每日指标：index_dailybasic（basic，400积分）
      - 指数技术面因子：idx_factor_pro（advanced，5000积分，表名 index_tech）
      - 沪深市场每日交易统计：daily_info（basic，600积分）、sz_daily_info（advanced，2000积分）
      - 国际主要指数：index_global（advanced，6000积分）
    - 指数中频行情接口（rt_idx_k/rt_idx_min/rt_idx_min_daily/idx_mins）和申万实时行情（rt_sw_k）均复用 kline/sector_kline 超表
    - 申万行业成分（index_member_all）和中信行业成分（ci_index_member）复用 sector_constituent 表，通过 data_source="TI"/"CI" 区分
    - _Requirements: 11.1-11.6, 12.1-12.7, 12a.1-12a.10, 13.1-13.5, 14.1-14.7, 15.1-15.5, 16.1-16.5, 17.1-17.5, 18.1-18.4, 19.1-19.4_

  - [x] 5.12 编写 API_Registry 属性测试
    - **Property 5: API_Registry 条目完整性**
    - 在 `tests/properties/test_tushare_import_properties.py` 中编写属性测试，验证所有注册的 ApiEntry（120+ 个）的 token_tier 为 {BASIC, ADVANCED, PREMIUM, SPECIAL} 之一，code_format 为 {STOCK_SYMBOL, INDEX_CODE, NONE} 之一，storage_engine 为 {PG, TS} 之一，且 target_table 不为空
    - **Validates: Requirements 22a.2, 26.4**

- [x] 6. Import_Service 导入编排服务
  - [x] 6.1 创建 TushareImportService 核心框架
    - 新建 `app/services/data_engine/tushare_import_service.py`
    - 实现 `TushareImportService` 类，包含以下方法：
      - `_resolve_token(tier: TokenTier) -> str`：根据权限级别选择 Token（四级路由），优先对应级别 Token（basic→tushare_token_basic, advanced→tushare_token_advanced, premium→tushare_token_premium, special→tushare_token_special），未配置则回退到 `tushare_api_token`，两者均空则抛出错误
      - `_validate_params(entry: ApiEntry, params: dict) -> dict`：校验必填参数、日期格式、代码格式
      - `check_health() -> dict`：检查 Tushare 连通性（调用 TushareAdapter.health_check）和四级 Token 配置状态（basic/advanced/premium/special 各自是否已配置）
    - _Requirements: 22.1, 22a.3, 22a.4, 23.4_

  - [x] 6.2 实现导入任务启动和控制
    - 在 `TushareImportService` 中实现：
      - `start_import(api_name, params) -> dict`：从 Registry 获取元数据 → 参数校验 → Token 路由（四级） → 在 tushare_import_log 创建记录 → 初始化 Redis 进度（键 `tushare:import:{task_id}`） → 分发 Celery 任务 → 返回 task_id
      - `stop_import(task_id) -> dict`：在 Redis 设置停止信号 `tushare:import:stop:{task_id}` → 更新进度状态 → 撤销 Celery 任务
      - `get_import_status(task_id) -> dict`：从 Redis 读取进度数据
      - `get_import_history(limit=20) -> list[dict]`：从 tushare_import_log 表查询最近记录
    - 实现并发保护：同一 api_name 同时只允许一个导入任务运行
    - _Requirements: 20.1, 20.4, 21.2, 21.3, 24.3, 24.4, 24.5, 24.6_

  - [x] 6.3 编写 Token 路由属性测试
    - **Property 4: 四级 Token 路由与回退**
    - 在 `tests/properties/test_tushare_import_properties.py` 中编写属性测试，验证 `_resolve_token` 在各种 Token 配置组合下的行为：(a) 对应级别 Token 已配置时返回该 Token；(b) 对应级别 Token 为空但默认 Token 已配置时返回默认 Token；(c) 两者均为空时抛出错误。覆盖 BASIC/ADVANCED/PREMIUM/SPECIAL 四个级别
    - **Validates: Requirements 22a.3, 22a.4**

  - [x] 6.4 编写 Import_Service 单元测试
    - 在 `tests/services/test_tushare_import_service.py` 中编写单元测试，覆盖参数校验、四级 Token 路由、任务分发、并发保护、进度查询、历史记录查询
    - _Requirements: 20.1, 21.2, 22.1, 22a.3, 23.4, 24.5_

- [x] 7. Import_Task 异步导入任务
  - [x] 7.1 创建 Celery 导入任务核心框架
    - 新建 `app/tasks/tushare_import.py`
    - 实现 `run_import` Celery 任务（注册到 `data_sync` 队列），接收 api_name、params、token、log_id、task_id 参数
    - 实现核心处理逻辑 `_process_import`：
      - 从 API_Registry 获取接口元数据
      - 创建 TushareAdapter（使用指定 Token）
      - 调用 `_call_api` 获取数据
      - 应用字段映射（`_apply_field_mappings`）
      - 转换代码格式（`_convert_codes`：STOCK_SYMBOL 去后缀、INDEX_CODE 保留原样）
      - 写入目标表（ON CONFLICT 去重）
      - 更新 Redis 进度
    - _Requirements: 3.2, 4.4, 4.5, 12.3, 26.1, 26.2_

  - [x] 7.2 实现批处理和频率限制
    - 在 `_process_import` 中实现：
      - 按 BATCH_SIZE=50 分批处理（当 batch_by_code=True 时按代码分批）
      - 每批处理前检查 Redis 停止信号 `tushare:import:stop:{task_id}`
      - 按 rate_limit_group 控制 API 调用间隔（kline=0.18s, fundamentals=0.40s, money_flow=0.30s）
      - 每批完成后更新 Redis 进度（completed 单调递增）
      - 任务完成/失败/停止后更新 tushare_import_log 记录
    - 实现错误处理：HTTP 错误记录日志标记 failed、网络超时重试（最多 3 次）、Token 无效不重试、频率限制等待 60s 重试、数据库写入失败回滚当前批次继续下一批
    - _Requirements: 4.15, 20.2, 21.3, 3.16_

  - [x] 7.3 实现 PostgreSQL 和 TimescaleDB 写入函数
    - 实现 `_write_to_postgresql(rows, entry)`：根据 ApiEntry 的 conflict_columns 和 conflict_action 构建 INSERT ... ON CONFLICT SQL，使用 AsyncSessionPG 写入
    - 实现 `_write_to_timescaledb(rows, entry)`：构建 INSERT ... ON CONFLICT (time, symbol, freq, adj_type) DO NOTHING SQL，使用 AsyncSessionTS 写入 kline 超表
    - 两个函数均使用事务保证单批原子性
    - _Requirements: 4.4, 4.5, 5.3, 9.2, 12.3_

  - [x] 7.4 编写代码转换和批处理属性测试
    - **Property 1: ts_code 到 symbol 的转换正确性**
    - **Property 2: 纯数字代码到 ts_code 的补全正确性（Round-Trip）**
    - **Property 3: 指数代码保持不变**
    - **Property 6: 批处理分批数量**
    - 在 `tests/properties/test_tushare_import_properties.py` 中编写以上 4 个属性测试
    - **Validates: Requirements 3.2, 26.1, 26.2, 26.3, 4.15**

  - [x] 7.5 编写进度和终态属性测试
    - **Property 7: 导入进度单调递增**
    - **Property 8: 导入任务终态**
    - 在 `tests/properties/test_tushare_import_properties.py` 中编写以上 2 个属性测试
    - **Validates: Requirements 20.2, 3.16, 20.4, 21.3**

  - [x] 7.6 编写 Import_Task 单元测试
    - 在 `tests/tasks/test_tushare_import_task.py` 中编写单元测试，覆盖字段映射、代码转换、批处理逻辑、停止信号检测、错误处理
    - Mock TushareAdapter._call_api 返回 fixture 数据
    - _Requirements: 3.2, 4.4, 4.15, 21.3_

- [x] 8. Checkpoint - 确保后端核心服务层正确
  - 确保 API_Registry（120+ 接口）、Import_Service（四级Token）、Import_Task 所有测试通过。如有问题请向用户确认。

- [x] 9. REST API 端点
  - [x] 9.1 创建 Tushare API 路由模块
    - 新建 `app/api/v1/tushare.py`，创建 `router = APIRouter(prefix="/data/tushare", tags=["tushare"])`
    - 定义 Pydantic 请求/响应模型：`TushareImportRequest`、`TushareImportResponse`、`TushareImportStatusResponse`、`TushareImportStopResponse`、`TushareHealthResponse`（含四级 Token 状态：basic/advanced/premium/special）、`ApiRegistryItem`（含 token_tier、token_available、vip_variant 字段）、`TushareImportLogItem`
    - 实现 6 个端点：
      - `GET /health`：调用 Import_Service.check_health()，返回四级 Token 配置状态
      - `GET /registry`：调用 API_Registry.get_all_entries() 并转换为 ApiRegistryItem 列表（含 token_available 字段）
      - `POST /import`：调用 Import_Service.start_import()
      - `GET /import/status/{task_id}`：调用 Import_Service.get_import_status()
      - `POST /import/stop/{task_id}`：调用 Import_Service.stop_import()
      - `GET /import/history`：调用 Import_Service.get_import_history()
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 20.3, 21.1, 24.5_

  - [x] 9.2 注册路由到 API v1
    - 在 `app/api/v1/__init__.py` 中导入并注册 tushare router
    - _Requirements: 22.1_

  - [x] 9.3 编写 REST API 端点测试
    - 在 `tests/api/test_tushare_api.py` 中编写端点测试，覆盖健康检查（四级Token状态）、注册表查询（120+接口）、导入启动/状态/停止/历史
    - Mock Import_Service 方法
    - _Requirements: 22.1, 20.3, 21.1, 24.5_

- [x] 10. 前端 TushareImportView 组件
  - [x] 10.1 创建 TushareImportView 基础布局
    - 新建 `frontend/src/views/TushareImportView.vue`
    - 实现页面顶部 Tushare 连接状态指示器（绿色"已连接"/红色"未连接"）和四级 Token 配置状态显示（基础✅/高级✅/专业✅/特殊❌）
    - 实现"重新检测"按钮，调用 `GET /api/v1/data/tushare/health`
    - 页面加载时自动检查连通性
    - _Requirements: 2.1, 22.1, 22.2, 22.3, 22.4, 22a.5_

  - [x] 10.2 实现数据分类卡片和接口列表
    - 页面加载时调用 `GET /api/v1/data/tushare/registry` 获取接口列表
    - 按 category（stock_data/index_data）分为"股票数据"和"指数专题"两个卡片区域
    - 在每个卡片内按 subcategory 分组显示可折叠的子分类
    - "股票数据"下显示：基础数据（13个）、行情数据低频（13个）、行情数据中频（4个）、财务数据（9个+VIP）、参考数据（12个）、特色数据（13个）、两融及转融通（4个）、资金流向数据（8个）、打板专题数据（24个）
    - "指数专题"下显示：指数基本信息（1个）、指数行情低频（日线/周线/月线，3个）、指数行情中频（实时日线/实时分钟/历史分钟，4个）、指数成分和权重（1个）、申万行业数据（分类/成分/日线/实时，4个）、中信行业数据（成分/日线，2个）、大盘指数每日指标（1个）、指数技术面因子专业版（1个）、沪深市场每日交易统计（2个）、深圳市场每日交易情况、国际主要指数（1个）
    - 展开子分类后显示该分类下所有 API 接口，每个接口显示 api_name、label（中文说明）和 token_tier 权限标签（基础/高级/专业/特殊）
    - 若对应 Token 未配置（token_available=false），禁用该接口的导入按钮并提示"需配置对应权限 Token"
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 22a.5, 22a.6_

  - [x] 10.3 实现动态参数表单
    - 根据每个 ApiEntry 的 required_params 和 optional_params 动态渲染参数输入控件：
      - DATE_RANGE → 起止日期选择器（默认结束日期为当天）
      - STOCK_CODE → 股票代码输入框（支持逗号分隔，留空表示全市场）
      - INDEX_CODE → 指数代码输入框
      - MARKET → 市场下拉选择器（SSE/SZSE/CSI/全部）
      - REPORT_PERIOD → 报告期选择器（年份+季度）
      - FREQ → 频率选择器（1min/5min/15min/30min/60min）
      - HS_TYPE → 类型选择器（SH/SZ）
      - SECTOR_CODE → 板块代码输入框
      - MONTH_RANGE → 月份范围选择器
      - CONCEPT_CODE → 题材代码输入框
    - 必填参数未填写时禁用"开始导入"按钮并显示参数提示
    - 中频行情分组中显示提示"分钟级数据量较大，建议按单只股票或短日期范围分批导入"
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 4a.1, 4a.9, 12a.1, 12a.6_

  - [x] 10.4 实现导入控制和进度追踪
    - 点击"开始导入"时调用 `POST /api/v1/data/tushare/import`，获取 task_id
    - 在"活跃任务"区域显示正在运行的导入任务，包含进度条、百分比、已完成/失败数量、当前处理项
    - 每 3 秒轮询 `GET /api/v1/data/tushare/import/status/{task_id}` 更新进度
    - 任务运行中显示"停止导入"按钮，点击调用 `POST /api/v1/data/tushare/import/stop/{task_id}`
    - 任务完成/失败/停止后停止轮询并显示最终状态标签
    - _Requirements: 20.3, 20.5, 21.1, 21.2, 21.4_

  - [x] 10.5 实现导入历史记录
    - 页面加载时调用 `GET /api/v1/data/tushare/import/history` 获取最近 20 条导入记录
    - 在页面底部"导入历史"区域显示记录列表，每条记录包含：接口名称、导入时间、数据量、状态（成功✅/失败❌/已停止⏹）、耗时
    - 导入任务完成后自动刷新历史记录列表
    - _Requirements: 2.7, 24.1, 24.2, 24.5_

  - [x] 10.6 编写前端属性测试
    - 在 `frontend/src/views/__tests__/TushareImportView.property.test.ts` 中编写以下属性测试：
      - **Property 9: 动态表单参数渲染** — 验证参数表单根据 required_params/optional_params 正确渲染对应 UI 控件（含 MONTH_RANGE、CONCEPT_CODE 新增类型）
      - **Property 10: 必填参数校验** — 验证必填参数未填写时导入按钮禁用
      - **Property 11: Token 不可用时禁用导入** — 验证四级 Token 未配置时对应接口导入按钮禁用
      - **Property 12: 注册表驱动的接口列表渲染** — 验证子分类展开后显示的接口列表与 Registry 数据一致
      - **Property 13: 导入历史记录字段完整性** — 验证历史记录行包含所有必要字段
    - **Validates: Requirements 23.1-23.4, 22a.6, 2.5, 2.6, 24.2**

  - [x] 10.7 编写前端单元测试
    - 在 `frontend/src/views/__tests__/TushareImportView.test.ts` 中编写单元测试，覆盖组件渲染、连接状态检查（四级Token）、接口列表展示（120+接口）、参数表单交互、导入启动/停止、进度更新、历史记录显示
    - _Requirements: 2.1-2.7, 20.3, 21.1, 22.1-22.4, 23.1-23.4, 24.1-24.2_

- [x] 11. 路由和菜单集成
  - [x] 11.1 添加前端路由
    - 在 `frontend/src/router/index.ts` 的 MainLayout children 中新增路由：
      ```
      path: 'data/online/tushare', name: 'DataOnlineTushare',
      component: () => import('@/views/TushareImportView.vue'),
      meta: { title: 'Tushare 数据导入' }
      ```
    - _Requirements: 1.2_

  - [x] 11.2 修改侧边栏菜单结构
    - 在 `frontend/src/layouts/MainLayout.vue` 中将"在线数据"菜单项改为可展开的父菜单：
      - 父菜单：`{ path: '/data/online', label: '在线数据', icon: '🌐', children: [...] }`
      - 子菜单 1：`{ path: '/data/online', label: '数据总览', icon: '📊' }`
      - 子菜单 2：`{ path: '/data/online/tushare', label: 'tushare', icon: '📡' }`
    - 保持"本地数据"菜单项不变
    - 确保 `/data/online/tushare` 路由激活时高亮 tushare 子菜单项
    - 确保 expandedMenus 默认展开 `/data/online` 父菜单
    - _Requirements: 1.1, 1.3, 1.4, 1.5_

- [x] 12. Checkpoint - 确保前后端集成正确
  - 确保所有测试通过，前端页面可正常渲染，API 端点可正常响应。如有问题请向用户确认。

- [x] 13. 集成测试
  - [x] 13.1 编写完整导入流程集成测试
    - 在 `tests/integration/test_tushare_import_flow.py` 中编写集成测试：
      - Mock Tushare API 返回 fixture 数据
      - 验证完整流程：POST /import → Celery 任务执行 → 数据写入 DB → 进度更新 → 状态变为 completed → import_log 记录正确
    - _Requirements: 3.1-3.2, 4.3-4.5, 20.1-20.4, 24.3-24.6_

  - [x] 13.2 编写停止信号集成测试
    - 在 `tests/integration/test_tushare_import_stop.py` 中编写集成测试：
      - 验证停止信号传播：POST /import/stop → Redis 停止信号 → 任务检测信号 → 状态变为 stopped → import_log 更新
    - _Requirements: 21.2, 21.3, 21.4_

- [x] 14. Final checkpoint - 确保所有测试通过
  - 确保所有测试通过，包括属性测试、单元测试和集成测试。如有问题请向用户确认。

## Notes

- 标记 `*` 的子任务为可选，可跳过以加速 MVP 交付
- 每个任务引用具体需求编号以确保可追溯性
- Checkpoint 确保增量验证
- 属性测试验证设计文档中的 13 个正确性属性（Property 1-13）
- 单元测试验证具体示例和边界情况
- 实现顺序确保无孤立代码：配置 → 模型（85张表） → 迁移 → 注册表（120+接口） → 服务（四级Token） → 任务 → API → 前端 → 路由
- 所有新 Python 文件应包含中文 docstring 和模块级注释
- ORM 模型使用 SQLAlchemy 2.0 `Mapped[]` + `mapped_column()` 声明式风格，继承 `PGBase`
- Celery 任务是调用 services 的薄包装器，遵循 `app/tasks/` 中的现有模式
- 四级 Token 路由：basic（≤2000积分）→ advanced（2000-6000含6000）→ premium（>6000）→ special（单独开通）
- 板块数据复用现有 sector_info/sector_constituent/sector_kline 表，通过 data_source 枚举（THS/DC/CI/TDX/TI）区分来源，其中 index_member_all 使用 TI、ci_index_member 使用 CI
- VIP 批量接口（如 income_vip）通过 ApiEntry.vip_variant 字段关联，使用 advanced 权限级别 Token
