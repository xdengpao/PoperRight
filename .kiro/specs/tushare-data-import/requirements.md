# 需求文档：Tushare 数据在线导入

## 简介

在数据管理模块的"在线数据"菜单下新增"tushare"子菜单，提供 Tushare 平台股票数据和指数专题数据的在线导入功能。用户可按数据分类选择导入内容、设置日期范围和参数，通过 Celery 异步任务执行导入，并实时查看导入进度。指数专题覆盖 20 个接口，包含指数基本信息、指数行情（低频/中频）、指数成分和权重、申万行业（分类/成分/日线/实时）、中信行业（成分/日线）、大盘指数每日指标、指数技术面因子（专业版）、沪深市场每日交易统计、深圳市场每日交易情况、国际主要指数。

## 术语表

- **Tushare_Adapter**：已有的 Tushare 数据源适配器（`app/services/data_engine/tushare_adapter.py`），通过 HTTP POST + Token 认证访问 Tushare API
- **Import_Service**：Tushare 数据导入编排服务，负责参数校验、任务分发和进度管理
- **Import_Task**：Celery 异步导入任务，执行实际的 API 调用和数据写入
- **TushareImportView**：前端 Tushare 数据导入页面组件
- **Stock_Data**：Tushare 股票数据大类，包含基础数据、行情数据、财务数据、参考数据、特色数据、两融及转融通、资金流向数据、打板专题数据等子分类
- **Index_Data**：Tushare 指数专题数据大类，包含指数基本信息、指数行情（低频：日线/周线/月线）、指数行情（中频：实时日线/实时分钟/历史分钟）、指数成分和权重、申万行业数据（分类/成分/日线行情/实时行情）、中信行业数据（成分/日线行情）、大盘指数每日指标、指数技术面因子（专业版）、沪深市场每日交易统计、深圳市场每日交易情况、国际主要指数等子分类
- **ts_code**：Tushare 股票/指数代码格式，如 600000.SH（上海）、000001.SZ（深圳）、000001.BJ（北京）
- **symbol**：系统内部使用的纯 6 位数字股票代码格式，如 600000、000001
- **API_Registry**：Tushare API 接口注册表，定义每个接口的名称、参数、字段映射和目标存储表
- **Rate_Limiter**：API 调用频率限制器，根据 Tushare 接口限制控制调用间隔
- **Import_Record**：导入历史记录，持久化存储在 PostgreSQL 的 tushare_import_log 表中，记录每次导入任务的元数据和执行结果
- **Basic_Data**：Tushare 基础数据子分类（文档1），包含股票基础信息（stock_basic）、每日股本盘前（stk_premarket）、交易日历（trade_cal）、ST股票列表（stock_st）、ST风险警示板（st）、沪深港通股票列表（stock_hsgt）、股票曾用名（namechange）、上市公司基本信息（stock_company）、上市公司管理层（stk_managers）、管理层薪酬（stk_rewards）、北交所新旧代码对照（bse_mapping）、IPO新股上市（new_share）、股票历史列表（bak_basic）
- **Quote_Data**：Tushare 行情数据子分类（文档8），包含历史日线（daily）、实时日线（rt_k）、历史分钟（stk_mins）、实时分钟（rt_min）、实时分钟日累计（rt_min_daily）、周线行情（weekly）、月线行情（monthly）、周/月行情每日更新（stk_weekly_monthly）、复权因子（adj_factor）、每日指标（daily_basic）、每日涨跌停价格（stk_limit）、每日停复牌信息（suspend_d）、沪深股通十大成交股（hsgt_top10）、港股通十大成交股（ggt_top10）、港股通每日成交统计（ggt_daily）、港股通每月成交统计（ggt_monthly）、备用行情（bak_daily）
- **Financial_Data**：Tushare 财务数据子分类（文档7），包含利润表（income/income_vip）、资产负债表（balancesheet/balancesheet_vip）、现金流量表（cashflow/cashflow_vip）、业绩预告（forecast/forecast_vip）、业绩快报（express/express_vip）、分红送股（dividend）、财务指标（fina_indicator/fina_indicator_vip）、主营业务构成（fina_mainbz/fina_mainbz_vip）、财报披露日期表（disclosure_date）
- **Reference_Data**：Tushare 参考数据子分类（文档6），包含个股异常波动（stk_shock）、个股严重异常波动（stk_high_shock）、交易所重点提示证券（stk_alert）、前十大股东（top10_holders）、前十大流通股东（top10_floatholders）、股权质押统计（pledge_stat）、股权质押明细（pledge_detail）、股票回购（repurchase）、限售股解禁（share_float）、大宗交易（block_trade）、股东人数（stk_holdernumber）、股东增减持（stk_holdertrade）
- **Special_Data**：Tushare 特色数据子分类（文档5），包含券商盈利预测（report_rc）、每日筹码及胜率（cyq_perf）、每日筹码分布（cyq_chips）、股票技术面因子专业版（stk_factor_pro）、中央结算系统持股统计（ccass_hold）、中央结算系统持股明细（ccass_hold_detail）、沪深股通持股明细（hk_hold）、股票开盘集合竞价（stk_auction_o）、股票收盘集合竞价（stk_auction_c）、神奇九转指标（stk_nineturn）、AH股比价（stk_ah_comparison）、机构调研数据（stk_surv）、券商每月金股（broker_recommend）
- **Margin_Data**：Tushare 两融及转融通子分类（文档4），包含融资融券汇总（margin）、融资融券交易明细（margin_detail）、融资融券标的盘前（margin_secs）、转融资交易汇总（slb_len）
- **MoneyFlow_Data**：Tushare 资金流向数据子分类（文档3），包含个股资金流向（moneyflow）、个股资金流向THS（moneyflow_ths）、个股资金流向DC（moneyflow_dc）、板块资金流向THS（moneyflow_cnt_ths）、行业资金流向THS（moneyflow_ind_ths）、板块资金流向DC（moneyflow_ind_dc）、大盘资金流向DC（moneyflow_mkt_dc）、沪港通资金流向（moneyflow_hsgt）
- **Limit_Up_Data**：Tushare 打板专题数据子分类（文档2），包含龙虎榜每日统计单（top_list）、龙虎榜机构交易单（top_inst）、同花顺涨跌停榜单（limit_list_ths）、涨跌停和炸板数据（limit_list_d）、涨停股票连板天梯（limit_step）、涨停最强板块统计（limit_cpt_list）、同花顺行业概念板块（ths_index）、同花顺行业概念指数行情（ths_daily）、同花顺行业概念成分（ths_member）、东方财富概念板块（dc_index）、东方财富概念成分（dc_member）、东方财富概念板块行情（dc_daily）、开盘竞价成交当日（stk_auction）、市场游资名录（hm_list）、游资交易每日明细（hm_detail）、同花顺热榜（ths_hot）、东方财富热榜（dc_hot）、通达信板块信息（tdx_index）、通达信板块成分（tdx_member）、通达信板块行情（tdx_daily）、开盘啦榜单数据（kpl_list）、开盘啦题材成分（kpl_concept_cons）、东方财富题材库（dc_concept）、东方财富题材成分（dc_concept_cons）
- **DataSource_Enum**：板块数据来源枚举（`app/models/sector.py`），现有值 DC（东方财富）、TI（申万行业）、TDX（通达信），需新增 CI（中信行业）和 THS（同花顺概念/行业板块）
- **Token_Tier**：Tushare API Token 权限级别，分为 basic（2000 积分及以下）、advanced（2000-6000 积分，包含6000积分）、premium（6000 积分以上）、special（需单独开通权限）四级，系统根据接口权限级别自动选择对应 Token
- **Low_Freq_Data**：低频行情数据，包含日K（daily/index_daily）、周K（weekly/index_weekly）、月K（monthly/index_monthly），与中频数据分开导入
- **Mid_Freq_Data**：中频行情数据，包含分钟级行情（stk_mins/idx_mins/rt_idx_min_daily）和实时行情（rt_k/rt_min/rt_min_daily/rt_idx_k/rt_idx_min/rt_sw_k），数据量较大，与低频数据分开导入 【调整：指数中频接口名更新为 idx_mins/rt_idx_k/rt_idx_min/rt_idx_min_daily，新增 rt_sw_k】

## 需求

### 需求 1：侧边栏菜单扩展

**用户故事：** 作为量化交易员，我希望在侧边栏"数据管理 > 在线数据"下看到"tushare"子菜单，以便快速访问 Tushare 数据导入功能。

#### 验收标准

1. WHEN 用户展开"数据管理"菜单，THE MainLayout SHALL 在"在线数据"子菜单下显示"tushare"子菜单项，图标使用 📡
2. WHEN 用户点击"tushare"子菜单项，THE Router SHALL 导航至 `/data/online/tushare` 路径并渲染 TushareImportView 组件
3. WHEN 当前路由为 `/data/online/tushare`，THE MainLayout SHALL 高亮"tushare"子菜单项为激活状态
4. THE MainLayout SHALL 保持"在线数据"和"本地数据"原有子菜单项不变
5. THE MainLayout SHALL 将"在线数据"菜单项改为可展开的父菜单，包含原有"在线数据"页面入口和新增的"tushare"子菜单项

### 需求 2：Tushare 导入页面布局

**用户故事：** 作为量化交易员，我希望 Tushare 导入页面按"股票数据"和"指数专题"两大分类组织，并覆盖 Tushare 平台全部可用数据子分类，以便快速定位需要导入的数据类型。

#### 验收标准

1. THE TushareImportView SHALL 在页面顶部显示 Tushare 连接状态指示器
2. THE TushareImportView SHALL 显示"股票数据"和"指数专题"两个独立的数据分类卡片区域
3. THE TushareImportView SHALL 在"股票数据"分类下显示以下子分类：基础数据、行情数据（低频：日K/周K/月K）、行情数据（中频：分钟级/实时）、财务数据、参考数据、特色数据、两融及转融通、资金流向数据、打板专题数据 【调整：子分类列表更新，行情数据中频分组增加"实时"标注】
4. THE TushareImportView SHALL 在"指数专题"分类下显示以下子分类：指数基本信息、指数行情数据（低频：日线/周线/月线）、指数行情数据（中频：实时日线/实时分钟/历史分钟）、指数成分和权重、申万行业数据（分类/成分/日线行情/实时行情）、中信行业数据（成分/日线行情）、大盘指数每日指标、指数技术面因子（专业版）、沪深市场每日交易统计、深圳市场每日交易情况、国际主要指数 【调整：中频新增实时日线；申万行业新增成分和实时行情；中信行业新增成分；指数技术面因子标注专业版；接口名称按文档更新】
5. WHEN 用户展开某个子分类，THE TushareImportView SHALL 显示该子分类下所有可导入的 Tushare API 接口列表
6. THE TushareImportView SHALL 为每个 API 接口显示接口名称（如 stock_basic）和中文说明（如"股票基础列表"）
7. THE TushareImportView SHALL 在页面底部显示导入历史记录区域

### 需求 3：股票基础数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 股票基础数据（stock_basic、stk_premarket、trade_cal、stock_st、st、stock_hsgt、namechange、stock_company、stk_managers、stk_rewards、bse_mapping、new_share、bak_basic），以便获取全市场股票列表、交易日历、IPO新股、ST列表、沪深港通股票、上市公司信息和管理层数据。

#### 验收标准

1. WHEN 用户选择 stock_basic 接口并点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("stock_basic")` 获取全市场股票列表
2. WHEN stock_basic 数据获取成功，THE Import_Task SHALL 将 ts_code 转换为纯 6 位 symbol 格式后写入 stock_info 表，使用 ON CONFLICT (symbol) 策略更新已有记录
3. WHEN 用户选择 stk_premarket 接口并设置日期范围，THE Import_Task SHALL 将每日股本（盘前）数据（含涨跌停价格）写入 stk_premarket 表（PostgreSQL），包含 ts_code、trade_date、total_share、float_share、free_share、total_mv、float_mv、up_limit、down_limit 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【调整：替代原 daily_share 接口，新增涨跌停价格字段】
4. WHEN 用户选择 trade_cal 接口并点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("trade_cal")` 获取交易日历数据
5. WHEN trade_cal 数据获取成功，THE Import_Task SHALL 将数据写入 trade_calendar 表（PostgreSQL），包含 exchange、cal_date、is_open 字段
6. WHEN 用户选择 stock_st 接口并点击"开始导入"，THE Import_Task SHALL 将 ST 股票列表数据写入 stock_st 表（PostgreSQL），包含 ts_code、name、is_st（Y/N）、st_date、st_type 字段
7. WHEN 用户选择 st 接口并设置日期范围，THE Import_Task SHALL 将 ST 风险警示板股票数据写入 st_warning 表（PostgreSQL），包含 ts_code、trade_date、name、close、pct_chg、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增：独立于 stock_st 的 ST 风险警示板数据】
8. WHEN 用户选择 stock_hsgt 接口并指定类型（SH/SZ），THE Import_Task SHALL 将沪深港通股票列表数据写入 stock_hsgt 表（PostgreSQL），包含 ts_code、hs_type、in_date、out_date、is_new 字段 【新增：替代原 hs_const 接口】
9. WHEN 用户选择 namechange 接口并点击"开始导入"，THE Import_Task SHALL 将股票曾用名数据写入 stock_namechange 表（PostgreSQL），包含 ts_code、name、start_date、end_date、change_reason 字段 【调整：从原参考数据移入基础数据】
10. WHEN 用户选择 stock_company 接口并点击"开始导入"，THE Import_Task SHALL 将上市公司基本信息写入 stock_company 表（PostgreSQL），包含 ts_code、chairman、manager、secretary、reg_capital、setup_date、province、city、website 字段，使用 ON CONFLICT (ts_code) 策略更新已有记录 【调整：从原参考数据移入基础数据】
11. WHEN 用户选择 stk_managers 接口，THE Import_Task SHALL 将上市公司管理层数据写入 stk_managers 表（PostgreSQL），包含 ts_code、ann_date、name、gender、lev、title、edu、national、birthday、begin_date、end_date 字段 【调整：从原参考数据移入基础数据】
12. WHEN 用户选择 stk_rewards 接口，THE Import_Task SHALL 将管理层薪酬和持股数据写入 stk_rewards 表（PostgreSQL），包含 ts_code、ann_date、name、title、reward、hold_vol 字段 【调整：从原参考数据移入基础数据】
13. WHEN 用户选择 bse_mapping 接口并点击"开始导入"，THE Import_Task SHALL 将北交所新旧代码对照数据写入 bse_mapping 表（PostgreSQL），包含 old_code、new_code、name、list_date 字段 【新增】
14. WHEN 用户选择 new_share 接口并点击"开始导入"，THE Import_Task SHALL 将 IPO 新股上市数据写入 new_share 表（PostgreSQL），包含 ts_code、sub_code、name、ipo_date、issue_date、amount、market_amount、price、pe、limit_amount、funds、ballot 字段，使用 ON CONFLICT (ts_code) 策略去重
15. WHEN 用户选择 bak_basic 接口并点击"开始导入"，THE Import_Task SHALL 将备用基础信息数据写入 stock_info 表，补充更新已有字段
16. IF Tushare API 调用失败，THEN THE Import_Task SHALL 记录错误日志并将任务状态标记为失败，同时更新 Import_Record
17. 【移除】原 stk_delist 接口（文档中未出现），原 daily_share 接口（被 stk_premarket 替代）

### 需求 4：股票低频行情数据导入（日K/周K/月K）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 股票低频行情数据（daily、weekly、monthly、stk_weekly_monthly、adj_factor、daily_basic、stk_limit、suspend_d、hsgt_top10、ggt_top10、ggt_daily、ggt_monthly、bak_daily），低频数据与中频数据分开导入，以便分别管理不同频率的数据导入任务。

#### 验收标准

1. THE TushareImportView SHALL 在"行情数据"子分类下将接口分为"低频行情（日K/周K/月K）"和"中频行情（分钟级/实时）"两个独立分组
2. WHEN 用户选择低频行情接口（daily/weekly/monthly）并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器和可选的股票代码输入框
3. WHEN 用户点击"开始导入"，THE Import_Service SHALL 通过 Celery 分发异步导入任务到 data_sync 队列
4. WHEN 导入 daily/weekly/monthly 数据时，THE Import_Task SHALL 将行情数据写入 TimescaleDB 的 kline 超表，freq 字段分别设为 "1d"/"1w"/"1M"，symbol 字段存储纯 6 位代码
5. WHEN 导入 stk_weekly_monthly 数据时，THE Import_Task SHALL 将每日更新的周/月行情数据写入 kline 超表，根据数据频率设置 freq 字段 【新增：每日更新的周月线接口】
6. WHEN 导入 adj_factor 数据时，THE Import_Task SHALL 将复权因子写入 adjustment_factor 表
7. WHEN 导入 daily_basic 数据时，THE Import_Task SHALL 将每日基本指标（换手率、市盈率、市净率、总市值等）更新到 stock_info 表对应字段
8. WHEN 导入 stk_limit 数据时，THE Import_Task SHALL 将每日涨跌停价格数据写入 stk_limit 表（PostgreSQL），包含 ts_code、trade_date、up_limit、down_limit 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【调整：从原特色数据/打板专题移入行情数据】
9. WHEN 导入 suspend_d 数据时，THE Import_Task SHALL 将停复牌信息写入 suspend_info 表（PostgreSQL），包含 ts_code、suspend_date、resume_date、suspend_type 字段
10. WHEN 导入 hsgt_top10 数据时，THE Import_Task SHALL 将沪深股通十大成交股数据写入 hsgt_top10 表（PostgreSQL），包含 trade_date、ts_code、name、close、change、rank、market_type、amount、net_amount、buy、sell 字段，使用 ON CONFLICT (trade_date, ts_code, market_type) 策略去重 【新增】
11. WHEN 导入 ggt_top10 数据时，THE Import_Task SHALL 将港股通十大成交股数据写入 ggt_top10 表（PostgreSQL），包含 trade_date、ts_code、name、close、p_change、rank、market_type、amount、net_amount、buy、sell 字段，使用 ON CONFLICT (trade_date, ts_code, market_type) 策略去重 【新增】
12. WHEN 导入 ggt_daily 数据时，THE Import_Task SHALL 将港股通每日成交统计数据写入 ggt_daily 表（PostgreSQL），包含 trade_date、buy_amount、buy_volume、sell_amount、sell_volume 字段，使用 ON CONFLICT (trade_date) 策略去重 【新增】
13. WHEN 导入 ggt_monthly 数据时，THE Import_Task SHALL 将港股通每月成交统计数据写入 ggt_monthly 表（PostgreSQL），包含 month、buy_amount、buy_volume、sell_amount、sell_volume 字段，使用 ON CONFLICT (month) 策略去重 【新增】
14. WHEN 导入 bak_daily 数据时，THE Import_Task SHALL 将备用行情数据写入 kline 超表或 bak_daily 表，作为主行情数据的补充 【新增】
15. THE Import_Task SHALL 按 BATCH_SIZE=50 分批处理股票列表，每次 API 调用间隔遵循 settings.rate_limit_kline（0.18 秒）频率限制

### 需求 4a：股票中频行情数据导入（分钟级/实时）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 股票分钟级和实时行情数据（stk_mins、rt_k、rt_min、rt_min_daily），中频数据与低频数据分开导入，以便独立控制分钟级和实时数据的导入范围和频率。

#### 验收标准

1. WHEN 用户选择中频行情接口（stk_mins）并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器、股票代码输入框和频率选择器（1min/5min/15min/30min/60min）
2. WHEN 用户点击"开始导入"，THE Import_Service SHALL 通过 Celery 分发异步导入任务到 data_sync 队列
3. WHEN 导入 stk_mins 数据时，THE Import_Task SHALL 将分钟行情数据写入 TimescaleDB 的 kline 超表，freq 字段根据用户选择设为 "1m"/"5m"/"15m"/"30m"/"60m"，symbol 字段存储纯 6 位代码
4. WHEN 导入 rt_k（实时日线）数据时，THE Import_Task SHALL 将实时日线行情数据写入 kline 超表，freq 字段设为 "1d"，标记为实时数据 【新增】
5. WHEN 导入 rt_min（实时分钟）数据时，THE Import_Task SHALL 将实时分钟行情数据写入 kline 超表，freq 字段根据频率设置 【新增】
6. WHEN 导入 rt_min_daily（实时分钟日累计）数据时，THE Import_Task SHALL 将实时分钟日累计行情数据写入 kline 超表 【新增】
7. THE Import_Task SHALL 使用 ON CONFLICT (time, symbol, freq, adj_type) 策略去重
8. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
9. THE TushareImportView SHALL 在中频行情分组中提示用户"分钟级数据量较大，建议按单只股票或短日期范围分批导入"

### 需求 5：股票财务数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 财务数据（income、balancesheet、cashflow、fina_indicator、dividend、forecast、express、fina_mainbz、disclosure_date），以便进行基本面分析和业绩预期跟踪。

#### 验收标准

1. WHEN 用户选择财务数据接口并设置报告期范围，THE TushareImportView SHALL 提供报告期选择器（年份+季度）
2. WHEN 用户点击"开始导入"，THE Import_Service SHALL 通过 Celery 分发异步导入任务
3. WHEN 导入 income/balancesheet/cashflow 数据时，THE Import_Task SHALL 将财务报表数据写入对应的 financial_statement 表（PostgreSQL），使用 ON CONFLICT (ts_code, end_date, report_type) 策略去重
4. WHEN 导入 fina_indicator 数据时，THE Import_Task SHALL 将财务指标数据更新到 stock_info 表的 pe_ttm、pb、roe 字段
5. WHEN 导入 dividend 数据时，THE Import_Task SHALL 将分红送股数据写入 dividend 表（PostgreSQL），包含 ts_code、ann_date、div_proc、stk_div、cash_div 字段
6. WHEN 导入 forecast 数据时，THE Import_Task SHALL 将业绩预告数据写入 forecast 表（PostgreSQL），包含 ts_code、ann_date、end_date、type（预增/预减/扭亏/首亏/续亏/续盈/略增/略减）、p_change_min、p_change_max、net_profit_min、net_profit_max、summary 字段，使用 ON CONFLICT (ts_code, end_date) 策略去重
7. WHEN 导入 express 数据时，THE Import_Task SHALL 将业绩快报数据写入 express 表（PostgreSQL），包含 ts_code、ann_date、end_date、revenue、operate_profit、total_profit、n_income、total_assets、total_hldr_eqy_exc_min_int、diluted_eps、yoy_net_profit、bps、perf_summary 字段，使用 ON CONFLICT (ts_code, end_date) 策略去重
8. WHEN 导入 fina_mainbz 数据时，THE Import_Task SHALL 将主营业务构成数据写入 fina_mainbz 表（PostgreSQL），包含 ts_code、end_date、bz_item（业务名称）、bz_sales（业务收入）、bz_profit（业务利润）、bz_cost（业务成本）、curr_type（币种）字段，使用 ON CONFLICT (ts_code, end_date, bz_item) 策略去重 【新增】
9. WHEN 导入 disclosure_date 数据时，THE Import_Task SHALL 将财报披露日期表数据写入 disclosure_date 表（PostgreSQL），包含 ts_code、ann_date、end_date、pre_date（预披露日期）、actual_date（实际披露日期）字段，使用 ON CONFLICT (ts_code, end_date) 策略去重 【新增】
10. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制
11. THE API_Registry SHALL 为 income/balancesheet/cashflow/forecast/express/fina_indicator/fina_mainbz 标注 VIP 批量接口变体（如 income_vip），VIP 接口使用 advanced 权限级别 Token 【新增：VIP 批量接口说明】

### 需求 6：参考数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 参考数据（stk_shock、stk_high_shock、stk_alert、top10_holders、top10_floatholders、pledge_stat、pledge_detail、repurchase、share_float、block_trade、stk_holdernumber、stk_holdertrade），以便分析个股异常波动、股东结构、股权质押、回购和大宗交易信息。

#### 验收标准

1. WHEN 用户选择 stk_shock 接口并设置日期范围，THE Import_Task SHALL 将个股异常波动数据写入 stk_shock 表（PostgreSQL），包含 ts_code、trade_date、shock_type、pct_chg、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date, shock_type) 策略去重 【新增】
2. WHEN 用户选择 stk_high_shock 接口并设置日期范围，THE Import_Task SHALL 将个股严重异常波动数据写入 stk_high_shock 表（PostgreSQL），包含 ts_code、trade_date、shock_type、pct_chg、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date, shock_type) 策略去重 【新增】
3. WHEN 用户选择 stk_alert 接口并设置日期范围，THE Import_Task SHALL 将交易所重点提示证券数据写入 stk_alert 表（PostgreSQL），包含 ts_code、trade_date、alert_type、alert_desc 字段 【新增】
4. WHEN 用户选择 top10_holders 或 top10_floatholders 接口并设置报告期，THE Import_Task SHALL 将前十大股东/流通股东数据写入 top_holders 表（PostgreSQL），包含 ts_code、ann_date、end_date、holder_name、hold_amount、hold_ratio、holder_type（top10/float）字段，使用 ON CONFLICT (ts_code, end_date, holder_name, holder_type) 策略去重 【调整：从原特色数据移入参考数据】
5. WHEN 用户选择 pledge_stat 接口并设置日期范围，THE Import_Task SHALL 将股权质押统计数据写入 pledge_stat 表（PostgreSQL），包含 ts_code、end_date、pledge_count（质押次数）、unrest_pledge（无限售股质押数量）、rest_pledge（限售股质押数量）、total_share、pledge_ratio（质押比例）字段，使用 ON CONFLICT (ts_code, end_date) 策略去重 【新增】
6. WHEN 用户选择 pledge_detail 接口并设置日期范围，THE Import_Task SHALL 将股权质押明细数据写入 pledge_detail 表（PostgreSQL），包含 ts_code、ann_date、holder_name、pledge_amount、start_date、end_date、is_release 字段 【新增】
7. WHEN 用户选择 repurchase 接口并设置日期范围，THE Import_Task SHALL 将股票回购数据写入 repurchase 表（PostgreSQL），包含 ts_code、ann_date、end_date、proc（进度）、exp_date（到期日）、vol（回购数量）、amount（回购金额）、high_limit、low_limit 字段 【新增】
8. WHEN 用户选择 share_float 接口并设置日期范围，THE Import_Task SHALL 将限售股解禁数据写入 share_float 表（PostgreSQL），包含 ts_code、ann_date、float_date（解禁日期）、float_share（解禁数量）、float_ratio（解禁比例）、holder_name、share_type 字段 【新增】
9. WHEN 用户选择 block_trade 接口并设置日期范围，THE Import_Task SHALL 将大宗交易数据写入 block_trade 表（PostgreSQL），包含 ts_code、trade_date、price、vol、amount、buyer、seller 字段，使用 ON CONFLICT (ts_code, trade_date, buyer, seller) 策略去重 【调整：从原特色数据移入参考数据】
10. WHEN 用户选择 stk_holdernumber 接口并设置日期范围，THE Import_Task SHALL 将股东人数数据写入 stk_holdernumber 表（PostgreSQL），包含 ts_code、ann_date、end_date、holder_num、holder_num_change 字段 【调整：从原特色数据移入参考数据】
11. WHEN 用户选择 stk_holdertrade 接口，THE Import_Task SHALL 将股东增减持数据写入 stk_holdertrade 表（PostgreSQL），包含 ts_code、ann_date、holder_name、change_vol、change_ratio、after_vol、after_ratio、in_de（增持/减持）字段 【调整：从原特色数据移入参考数据】
12. IF Tushare API 调用失败，THEN THE Import_Task SHALL 记录错误日志并将任务状态标记为失败，同时更新 Import_Record
13. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制
14. 【移除】原 stock_company、namechange、hs_const、stk_rewards、stk_managers 接口（已移至需求3基础数据）

### 需求 7：特色数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 特色数据（report_rc、cyq_perf、cyq_chips、stk_factor_pro、ccass_hold、ccass_hold_detail、hk_hold、stk_auction_o、stk_auction_c、stk_nineturn、stk_ah_comparison、stk_surv、broker_recommend），以便获取券商预测、筹码分布、中央结算持股、集合竞价、技术指标和机构调研等高级分析数据。

#### 验收标准

1. WHEN 用户选择 report_rc 接口并设置日期范围，THE Import_Task SHALL 将券商盈利预测数据写入 report_rc 表（PostgreSQL），包含 ts_code、report_date、broker_name、analyst_name、target_price、rating、eps_est 字段 【新增】
2. WHEN 用户选择 cyq_perf 接口并设置日期范围和股票代码，THE Import_Task SHALL 将每日筹码及胜率数据写入 cyq_perf 表（PostgreSQL），包含 ts_code、trade_date、his_low、his_high、cost_5pct、cost_15pct、cost_50pct、cost_85pct、cost_95pct、weight_avg、winner_rate 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
3. WHEN 用户选择 cyq_chips 接口并设置日期范围和股票代码，THE Import_Task SHALL 将每日筹码分布数据写入 cyq_chips 表（PostgreSQL），包含 ts_code、trade_date、price、percent 字段 【新增】
4. WHEN 用户选择 stk_factor_pro 接口（专业版）并设置日期范围和股票代码，THE Import_Task SHALL 将专业版技术面因子数据写入 stk_factor 表（PostgreSQL），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、rsi_24、boll_upper、boll_mid、boll_lower、cci、wr、dmi、trix、bias 等字段，使用 ON CONFLICT (ts_code, trade_date) 策略更新 【调整：仅保留 stk_factor_pro，移除原 stk_factor 非pro版】
5. WHEN 用户选择 ccass_hold 接口并设置日期范围，THE Import_Task SHALL 将中央结算系统持股统计数据写入 ccass_hold 表（PostgreSQL），包含 ts_code、trade_date、participant_id、participant_name、hold_amount、hold_ratio 字段 【新增】
6. WHEN 用户选择 ccass_hold_detail 接口并设置日期范围和股票代码，THE Import_Task SHALL 将中央结算系统持股明细数据写入 ccass_hold_detail 表（PostgreSQL），包含 ts_code、trade_date、participant_id、participant_name、hold_amount、hold_ratio 字段 【新增】
7. WHEN 用户选择 hk_hold 接口并设置日期范围，THE Import_Task SHALL 将沪深股通持股明细数据写入 hk_hold 表（PostgreSQL），包含 ts_code、trade_date、code（港交所代码）、vol（持股数量）、ratio（持股比例）、exchange 字段，使用 ON CONFLICT (ts_code, trade_date, exchange) 策略去重 【新增】
8. WHEN 用户选择 stk_auction_o 接口并设置日期范围，THE Import_Task SHALL 将股票开盘集合竞价数据写入 stk_auction_o 表（PostgreSQL），包含 ts_code、trade_date、open、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
9. WHEN 用户选择 stk_auction_c 接口并设置日期范围，THE Import_Task SHALL 将股票收盘集合竞价数据写入 stk_auction_c 表（PostgreSQL），包含 ts_code、trade_date、close、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
10. WHEN 用户选择 stk_nineturn 接口并设置日期范围和股票代码，THE Import_Task SHALL 将神奇九转指标数据写入 stk_nineturn 表（PostgreSQL），包含 ts_code、trade_date、turn_type（买入/卖出）、turn_number（九转序号1-9）字段，使用 ON CONFLICT (ts_code, trade_date, turn_type) 策略去重 【新增】
11. WHEN 用户选择 stk_ah_comparison 接口并设置日期范围，THE Import_Task SHALL 将 AH 股比价数据写入 stk_ah_comparison 表（PostgreSQL），包含 ts_code、trade_date、a_close、h_close、ah_ratio（AH比价）字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
12. WHEN 用户选择 stk_surv 接口并设置日期范围，THE Import_Task SHALL 将机构调研数据写入 stk_surv 表（PostgreSQL），包含 ts_code、surv_date、fund_name、surv_type、participants 字段 【新增】
13. WHEN 用户选择 broker_recommend 接口并设置月份范围，THE Import_Task SHALL 将券商每月金股数据写入 broker_recommend 表（PostgreSQL），包含 month、broker、ts_code、name、rating 字段 【新增】
14. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制
15. THE API_Registry SHALL 将 stk_factor_pro 标注为 advanced 权限级别，stk_auction_o/stk_auction_c 标注为 special 权限级别
16. 【移除】原 top10_holders、top10_floatholders、stk_holdernumber、stk_holdertrade、block_trade（已移至需求6参考数据）、stk_account（文档中未出现）、stk_limit（已移至需求4行情数据）、stk_factor 非pro版（文档中未出现）

### 需求 8：两融及转融通数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 两融及转融通数据（margin、margin_detail、margin_secs、slb_len），以便分析融资融券和转融通市场动态。

#### 验收标准

1. WHEN 用户选择 margin 接口并设置日期范围，THE Import_Task SHALL 将融资融券汇总数据写入 margin_data 表（PostgreSQL），包含 trade_date、exchange_id、rzye（融资余额）、rzmre（融资买入额）、rzche（融资偿还额）、rqye（融券余额）、rqmcl（融券卖出量）、rzrqye（融资融券余额）字段，使用 ON CONFLICT (trade_date, exchange_id) 策略去重
2. WHEN 用户选择 margin_detail 接口并设置日期范围和可选股票代码，THE Import_Task SHALL 将融资融券交易明细写入 margin_detail 表（PostgreSQL），包含 ts_code、trade_date、rzye、rzmre、rzche、rqye、rqmcl、rqyl 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. WHEN 用户选择 margin_secs 接口，THE Import_Task SHALL 将融资融券标的（盘前）数据写入 margin_secs 表（PostgreSQL），包含 ts_code、trade_date、mg_type（融资/融券）、is_new 字段 【调整：margin_target 替换为 margin_secs，新增 trade_date 字段】
4. WHEN 用户选择 slb_len 接口并设置日期范围，THE Import_Task SHALL 将转融资交易汇总数据写入 slb_len 表（PostgreSQL），包含 ts_code、trade_date、len_rate、len_amt 字段
5. THE Import_Task SHALL 遵循 settings.rate_limit_money_flow（0.30 秒）频率限制
6. 【移除】原 margin_target 接口（被 margin_secs 替代）、原 slb_sec 接口（文档中未出现）

### 需求 9：资金流向数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 资金流向数据（moneyflow、moneyflow_ths、moneyflow_dc、moneyflow_cnt_ths、moneyflow_ind_ths、moneyflow_ind_dc、moneyflow_mkt_dc、moneyflow_hsgt），以便分析主力资金动向、沪深港通资金、行业和板块资金流向。

#### 验收标准

1. WHEN 用户选择 moneyflow 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器和可选的股票代码输入框
2. WHEN 导入 moneyflow 数据时，THE Import_Task SHALL 将个股资金流向数据写入 money_flow 表（PostgreSQL），包含 ts_code、trade_date、主力净流入、大单净流入等字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. WHEN 导入 moneyflow_ths 数据时，THE Import_Task SHALL 将同花顺个股资金流向数据写入 moneyflow_ths 表（PostgreSQL），包含 ts_code、trade_date、buy_sm_amount、sell_sm_amount、buy_md_amount、sell_md_amount、buy_lg_amount、sell_lg_amount、buy_elg_amount、sell_elg_amount、net_mf_amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
4. WHEN 导入 moneyflow_dc 数据时，THE Import_Task SHALL 将东方财富个股资金流向数据写入 moneyflow_dc 表（PostgreSQL），包含 ts_code、trade_date、buy_sm_amount、sell_sm_amount、buy_md_amount、sell_md_amount、buy_lg_amount、sell_lg_amount、buy_elg_amount、sell_elg_amount、net_mf_amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
5. WHEN 导入 moneyflow_cnt_ths 数据时，THE Import_Task SHALL 将同花顺概念板块资金流向数据写入 moneyflow_cnt_ths 表（PostgreSQL），包含 trade_date、ts_code、name、buy_amount、sell_amount、net_amount 字段 【新增】
6. WHEN 用户选择 moneyflow_ind_ths 接口并设置日期范围，THE Import_Task SHALL 将同花顺行业资金流向数据写入 moneyflow_ind 表（PostgreSQL），data_source 设为 "THS"，包含 trade_date、industry_name、data_source、buy_amount、sell_amount、net_amount 字段
7. WHEN 用户选择 moneyflow_ind_dc 接口并设置日期范围，THE Import_Task SHALL 将东财板块资金流向数据写入 moneyflow_ind 表（PostgreSQL），data_source 设为 "DC"，包含 trade_date、industry_name、data_source、buy_amount、sell_amount、net_amount 字段
8. WHEN 用户选择 moneyflow_mkt_dc 接口并设置日期范围，THE Import_Task SHALL 将大盘资金流向（东财）数据写入 moneyflow_mkt_dc 表（PostgreSQL），包含 trade_date、close、change、pct_change、net_mf_amount、net_mf_amount_rate、buy_elg_amount、sell_elg_amount、buy_lg_amount、sell_lg_amount、buy_md_amount、sell_md_amount、buy_sm_amount、sell_sm_amount 字段，使用 ON CONFLICT (trade_date) 策略去重
9. WHEN 用户选择 moneyflow_hsgt 接口并设置日期范围，THE Import_Task SHALL 将沪深港通资金流向数据写入 moneyflow_hsgt 表（PostgreSQL），包含 trade_date、ggt_ss（港股通上海）、ggt_sz（港股通深圳）、hgt（沪股通）、sgt（深股通）、north_money（北向资金）、south_money（南向资金）字段，使用 ON CONFLICT (trade_date) 策略去重
10. THE Import_Task SHALL 遵循 settings.rate_limit_money_flow（0.30 秒）频率限制

### 需求 10：打板专题数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 打板专题完整数据（top_list、top_inst、limit_list_ths、limit_list_d、limit_step、limit_cpt_list、ths_index、ths_daily、ths_member、dc_index、dc_member、dc_daily、stk_auction、hm_list、hm_detail、ths_hot、dc_hot、tdx_index、tdx_member、tdx_daily、kpl_list、kpl_concept_cons、dc_concept、dc_concept_cons），以便全面分析涨跌停统计、连板天梯、龙虎榜、游资动向、热榜、概念板块和题材数据。

#### 验收标准

1. WHEN 用户选择 top_list 接口并设置日期范围，THE Import_Task SHALL 将龙虎榜每日统计单数据写入 top_list 表（PostgreSQL），包含 trade_date、ts_code、name、close、pct_change、turnover_rate、amount、l_sell、l_buy、l_amount、net_amount、net_rate、amount_rate、float_values、reason 字段，使用 ON CONFLICT (trade_date, ts_code, reason) 策略去重
2. WHEN 用户选择 top_inst 接口并设置日期范围，THE Import_Task SHALL 将龙虎榜机构交易单数据写入 top_inst 表（PostgreSQL），包含 trade_date、ts_code、exalter（营业部名称）、buy、buy_rate、sell、sell_rate、net_buy 字段，使用 ON CONFLICT (trade_date, ts_code, exalter) 策略去重
3. WHEN 用户选择 limit_list_ths 接口并设置日期范围，THE Import_Task SHALL 将同花顺涨跌停榜单数据写入 limit_list_ths 表（PostgreSQL），包含 trade_date、ts_code、name、close、pct_chg、fd_amount、first_time、last_time、open_times、limit（U/D）字段，使用 ON CONFLICT (ts_code, trade_date, limit) 策略去重 【调整：ths_limit 替换为 limit_list_ths】
4. WHEN 用户选择 limit_list_d 接口并设置日期范围，THE Import_Task SHALL 将涨跌停和炸板数据写入 limit_list 表（PostgreSQL），包含 ts_code、trade_date、industry、close、pct_chg、amount、limit_amount、float_mv、total_mv、turnover_ratio、fd_amount、first_time、last_time、open_times、up_stat、limit_times、limit（U涨停/D跌停）字段，使用 ON CONFLICT (ts_code, trade_date, limit) 策略去重
5. WHEN 用户选择 limit_step 接口并设置日期范围，THE Import_Task SHALL 将涨停股票连板天梯数据写入 limit_step 表（PostgreSQL），包含 ts_code、trade_date、name、close、pct_chg、step（连板天数）、limit_order（封板顺序）、amount、turnover_ratio、fd_amount、first_time、last_time、open_times 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
6. WHEN 用户选择 limit_cpt_list 接口并设置日期范围，THE Import_Task SHALL 将涨停最强板块统计数据写入 limit_cpt_list 表（PostgreSQL），包含 trade_date、concept_name、limit_count、up_count、down_count、amount 字段 【新增】
7. WHEN 用户选择 ths_index 接口，THE Import_Task SHALL 将同花顺行业概念板块列表写入现有 sector_info 表（PostgreSQL），将 ts_code 映射为 sector_code、type 映射为 sector_type（CONCEPT/INDUSTRY）、data_source 设为 "THS"，使用 ON CONFLICT (sector_code, data_source) 策略更新
8. WHEN 用户选择 ths_daily 接口并设置日期范围和板块代码，THE Import_Task SHALL 将同花顺行业概念指数行情数据写入 sector_kline 表，data_source 设为 "THS"，包含 ts_code、trade_date、open、close、high、low、vol、amount 字段 【新增】
9. WHEN 用户选择 ths_member 接口并指定板块代码，THE Import_Task SHALL 将同花顺行业概念成分股写入现有 sector_constituent 表（PostgreSQL），将 con_code 映射为 symbol、con_name 映射为 stock_name、data_source 设为 "THS"
10. WHEN 用户选择 dc_index 接口，THE Import_Task SHALL 将东方财富概念板块列表写入现有 sector_info 表（PostgreSQL），将 ts_code 映射为 sector_code、data_source 设为 "DC"，使用 ON CONFLICT (sector_code, data_source) 策略更新
11. WHEN 用户选择 dc_member 接口并指定板块代码，THE Import_Task SHALL 将东方财富概念成分股写入现有 sector_constituent 表（PostgreSQL），将 con_code 映射为 symbol、con_name 映射为 stock_name、data_source 设为 "DC"
12. WHEN 用户选择 dc_daily 接口并设置日期范围和板块代码，THE Import_Task SHALL 将东方财富概念板块行情数据写入 sector_kline 表，data_source 设为 "DC"，包含 ts_code、trade_date、open、close、high、low、vol、amount 字段 【新增】
13. WHEN 用户选择 stk_auction 接口并设置日期，THE Import_Task SHALL 将开盘竞价成交（当日）数据写入 stk_auction 表（PostgreSQL），包含 ts_code、trade_date、open、vol、amount、bid_price、bid_vol 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重 【新增】
14. WHEN 用户选择 hm_list 接口，THE Import_Task SHALL 将市场游资名录数据写入 hm_list 表（PostgreSQL），包含 hm_name、hm_code、market、desc 字段
15. WHEN 用户选择 hm_detail 接口并设置日期范围，THE Import_Task SHALL 将游资交易每日明细数据写入 hm_detail 表（PostgreSQL），包含 trade_date、ts_code、hm_name、buy_amount、sell_amount、net_amount 字段
16. WHEN 用户选择 ths_hot 接口并设置日期范围，THE Import_Task SHALL 将同花顺热榜数据写入 ths_hot 表（PostgreSQL），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
17. WHEN 用户选择 dc_hot 接口并设置日期范围，THE Import_Task SHALL 将东方财富热榜数据写入 dc_hot 表（PostgreSQL），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
18. WHEN 用户选择 tdx_index 接口，THE Import_Task SHALL 将通达信板块信息写入现有 sector_info 表（PostgreSQL），data_source 设为 "TDX"，使用 ON CONFLICT (sector_code, data_source) 策略更新 【新增】
19. WHEN 用户选择 tdx_member 接口并指定板块代码，THE Import_Task SHALL 将通达信板块成分股写入现有 sector_constituent 表（PostgreSQL），data_source 设为 "TDX" 【新增】
20. WHEN 用户选择 tdx_daily 接口并设置日期范围和板块代码，THE Import_Task SHALL 将通达信板块行情数据写入 sector_kline 表，data_source 设为 "TDX" 【新增】
21. WHEN 用户选择 kpl_list 接口并设置日期范围，THE Import_Task SHALL 将开盘啦榜单数据写入 kpl_list 表（PostgreSQL），包含 trade_date、ts_code、name、close、pct_chg、tag 字段
22. WHEN 用户选择 kpl_concept_cons 接口并指定题材代码，THE Import_Task SHALL 将开盘啦题材成分数据写入 kpl_concept_cons 表（PostgreSQL），包含 concept_code、ts_code、name 字段 【新增：注意该接口暂无新增数据】
23. WHEN 用户选择 dc_concept 接口，THE Import_Task SHALL 将东方财富题材库数据写入 dc_concept 表（PostgreSQL），包含 concept_code、concept_name、src 字段 【新增】
24. WHEN 用户选择 dc_concept_cons 接口并指定题材代码，THE Import_Task SHALL 将东方财富题材成分数据写入 dc_concept_cons 表（PostgreSQL），包含 concept_code、ts_code、name 字段 【新增】
25. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制
26. 【移除】原 stk_limit 接口（已移至需求4行情数据）、原 ths_limit 接口（被 limit_list_ths 替代）

### 需求 11：指数基本信息导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 指数基本信息（index_basic），以便获取指数元数据。

#### 验收标准

1. WHEN 用户选择 index_basic 接口并指定市场（SSE/SZSE/CSI/全部），THE TushareImportView SHALL 提供市场下拉选择器
2. WHEN 用户点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("index_basic")` 获取指数列表
3. WHEN index_basic 数据获取成功，THE Import_Task SHALL 将指数信息写入 index_info 表（PostgreSQL），包含 ts_code、name、market、publisher、category、list_date 字段
4. THE Import_Task SHALL 使用 ON CONFLICT (ts_code) 策略更新已有记录
5. IF Tushare API 返回错误码，THEN THE Import_Task SHALL 记录错误详情并将任务状态标记为失败
6. THE API_Registry SHALL 将 index_basic 标注为 basic 权限级别

### 需求 12：指数低频行情数据导入（日线/周线/月线）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 指数低频行情数据（index_daily、index_weekly、index_monthly），低频与中频分开导入，以便分别管理不同频率的指数数据。

#### 验收标准

1. THE TushareImportView SHALL 在"指数行情数据"子分类下将接口分为"低频行情（日线/周线/月线）"和"中频行情（实时日线/实时分钟/历史分钟）"两个独立分组 【调整：中频分组新增实时日线】
2. WHEN 用户选择指数低频行情接口并设置日期范围和指数代码，THE TushareImportView SHALL 提供起止日期选择器和指数代码输入框
3. WHEN 导入 index_daily/index_weekly/index_monthly 数据时，THE Import_Task SHALL 将指数行情写入 TimescaleDB 的 kline 超表，symbol 字段存储指数 ts_code（如 000001.SH），freq 字段分别对应 "1d"/"1w"/"1M"
4. THE Import_Task SHALL 使用 ON CONFLICT (time, symbol, freq, adj_type) 策略去重
5. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
6. THE API_Registry SHALL 将 index_daily 标注为 advanced 权限级别（2000积分），index_weekly 和 index_monthly 标注为 basic 权限级别（600积分） 【调整：根据文档积分要求更新权限级别，index_daily 需2000积分，index_weekly/index_monthly 需600积分】
7. THE TushareImportView SHALL 在 index_daily 接口说明中注明"深证成指（399001.SZ）仅包含500只成分股，如需深市全部A股成交数据请使用深证A指（399107.SZ）" 【新增：根据文档注意事项】

### 需求 12a：指数中频行情数据导入（实时日线/实时分钟/历史分钟）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 指数实时和分钟级行情数据（rt_idx_k、rt_idx_min、rt_idx_min_daily、idx_mins），中频与低频分开导入，以便独立控制实时和分钟级指数数据的导入。

#### 验收标准

1. WHEN 用户选择指数中频行情接口并设置日期范围和指数代码，THE TushareImportView SHALL 提供起止日期选择器、指数代码输入框和频率选择器（1min/5min/15min/30min/60min，仅 idx_mins 需要）
2. WHEN 导入 rt_idx_k（指数实时日线）数据时，THE Import_Task SHALL 将指数实时日线行情写入 kline 超表，freq 字段设为 "1d"，标记为实时数据，支持按代码或代码通配符一次性提取全部交易所指数 【新增：替代原概念，文档接口名为 rt_idx_k】
3. WHEN 导入 rt_idx_min（指数实时分钟）数据时，THE Import_Task SHALL 将指数实时分钟行情写入 kline 超表，freq 字段根据频率设置，单次最大1000行，支持逗号分隔多个代码同时提取 【调整：替代原 index_1min_realtime，文档接口名为 rt_idx_min】
4. WHEN 导入 rt_idx_min_daily（指数实时分钟日累计）数据时，THE Import_Task SHALL 将指数实时分钟日累计行情写入 kline 超表，仅支持单个指数提取 【新增：文档中注明的日累计接口】
5. WHEN 导入 idx_mins（指数历史分钟）数据时，THE Import_Task SHALL 将指数历史分钟行情写入 kline 超表，freq 字段根据用户选择的频率设置（"1m"/"5m"/"15m"/"30m"/"60m"），单次最大8000行，可提供超过10年历史分钟数据 【调整：替代原 index_min，文档接口名为 idx_mins】
6. THE Import_Task SHALL 使用 ON CONFLICT (time, symbol, freq, adj_type) 策略去重
7. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
8. THE TushareImportView SHALL 在中频行情分组中提示用户"分钟级数据量较大，建议按单只指数或短日期范围分批导入"
9. THE API_Registry SHALL 将 rt_idx_k、rt_idx_min、rt_idx_min_daily、idx_mins 均标注为 special 权限级别（需单独开通） 【调整：根据文档权限说明更新】
10. 【移除】原 index_1min_realtime 接口（被 rt_idx_min 替代）、原 index_min 接口（被 idx_mins 替代）

### 需求 13：指数成分和权重导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 指数成分和权重数据（index_weight），以便了解指数构成。

#### 验收标准

1. WHEN 用户选择 index_weight 接口并指定指数代码和日期，THE TushareImportView SHALL 提供指数代码输入框和日期选择器，建议输入当月第一天和最后一天的日期 【调整：根据文档建议补充日期输入提示】
2. WHEN 导入 index_weight 数据时，THE Import_Task SHALL 将成分权重数据写入 index_weight 表（PostgreSQL），包含 index_code、con_code、trade_date、weight 字段
3. THE Import_Task SHALL 使用 ON CONFLICT (index_code, con_code, trade_date) 策略去重
4. IF 指定日期无成分数据，THEN THE Import_Task SHALL 记录警告日志
5. THE API_Registry SHALL 将 index_weight 标注为 advanced 权限级别（2000积分） 【调整：根据文档积分要求更新】并返回空结果

### 需求 14：申万行业数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 申万行业分类、成分和行情数据（index_classify、index_member_all、sw_daily、rt_sw_k），以便进行全面的行业分析。

#### 验收标准

1. WHEN 用户选择 index_classify 接口，THE Import_Service SHALL 调用 Tushare_Adapter 获取申万行业分类数据，支持2014年版本（28个一级/104个二级/227个三级）和2021年版本（31个一级/134个二级/346个三级） 【调整：补充版本说明】
2. WHEN index_classify 数据获取成功，THE Import_Task SHALL 将行业分类写入 sector_info 表，sector_type 设为 "INDUSTRY"，data_source 设为 "TI"
3. WHEN 用户选择 index_member_all 接口并指定分类代码或股票代码，THE Import_Task SHALL 将申万行业成分（按三级分类）数据写入 sector_constituent 表（PostgreSQL），data_source 设为 "TI"，包含 sector_code、symbol、stock_name、level（分类级别）字段，单次最大2000行 【新增：申万行业成分分级接口】
4. WHEN 用户选择 sw_daily 接口并设置日期范围，THE Import_Task SHALL 将申万行业指数日行情（默认申万2021版）写入 sector_kline 表，data_source 设为 "TI"，单次最大4000行 【调整：补充版本和限量说明】
5. WHEN 用户选择 rt_sw_k 接口，THE Import_Task SHALL 将申万行业指数最新截面数据写入 sector_kline 表，data_source 设为 "TI"，标记为实时数据 【新增：申万实时行情接口】
6. THE Import_Task SHALL 使用 ON CONFLICT 策略去重
7. THE API_Registry SHALL 将 index_classify 标注为 advanced 权限级别（2000积分），index_member_all 标注为 advanced 权限级别（2000积分），sw_daily 标注为 advanced 权限级别（5000积分），rt_sw_k 标注为 special 权限级别（需单独开通） 【调整：根据文档积分要求更新权限级别】

### 需求 15：中信行业数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 中信行业成分和行情数据（ci_index_member、ci_daily），以便进行多维度行业对比。

#### 验收标准

1. WHEN 用户选择 ci_index_member 接口并指定分类代码或股票代码，THE Import_Task SHALL 将中信行业成分（按三级分类）数据写入 sector_constituent 表（PostgreSQL），data_source 设为 "CI"，包含 sector_code、symbol、stock_name、level（分类级别）字段，单次最大5000行 【新增：中信行业成分接口】
2. WHEN 用户选择 ci_daily 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器
3. WHEN 导入中信行业行情数据时，THE Import_Task SHALL 将数据写入 sector_kline 表，data_source 设为 "CI"，单次最大4000条，可循环提取
4. THE Import_Task SHALL 使用 ON CONFLICT 策略去重
5. THE API_Registry SHALL 将 ci_index_member 和 ci_daily 均标注为 advanced 权限级别（5000积分） 【调整：根据文档积分要求更新权限级别】

### 需求 16：大盘指数每日指标导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 大盘指数每日指标（index_dailybasic），以便获取指数估值和成交数据。

#### 验收标准

1. WHEN 用户选择 index_dailybasic 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器
2. WHEN 导入 index_dailybasic 数据时，THE Import_Task SHALL 将指数每日指标写入 index_dailybasic 表（PostgreSQL），包含 ts_code、trade_date、pe、pb、turnover_rate、total_mv 字段
3. THE Import_Task SHALL 使用 ON CONFLICT (ts_code, trade_date) 策略去重
4. THE TushareImportView SHALL 在 index_dailybasic 接口说明中注明"目前只提供上证综指、深证成指、上证50、中证500、中小板指、创业板指的每日指标数据，数据从2004年1月开始" 【新增：根据文档数据范围说明】
5. THE API_Registry SHALL 将 index_dailybasic 标注为 basic 权限级别（400积分） 【调整：根据文档积分要求更新】

### 需求 17：指数技术面因子导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 指数技术面因子数据（idx_factor_pro，专业版接口），以便获取指数技术分析指标，覆盖大盘指数、申万行业指数和中信指数。

#### 验收标准

1. WHEN 用户选择 idx_factor_pro 接口并设置日期范围和指数代码，THE TushareImportView SHALL 提供起止日期选择器和指数代码输入框
2. WHEN 导入 idx_factor_pro 数据时，THE Import_Task SHALL 将指数技术面因子数据写入 index_tech 表（PostgreSQL），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、boll_upper、boll_mid、boll_lower 字段（输出参数_bfq表示不复权），使用 ON CONFLICT (ts_code, trade_date) 策略去重 【调整：接口名从 index_tech 更新为 idx_factor_pro，补充不复权说明】
3. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔，单次最大8000行
4. THE API_Registry SHALL 将 idx_factor_pro 标注为 advanced 权限级别（5000积分，8000积分以上频次更高） 【调整：根据文档积分要求从 special 更新为 advanced】
5. 【移除】原 index_tech 接口名（被 idx_factor_pro 替代）

### 需求 18：沪深市场每日交易统计导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 沪深市场每日交易统计数据（daily_info、sz_daily_info），以便了解市场整体交易情况。

#### 验收标准

1. WHEN 用户选择 daily_info 接口并设置日期范围，THE Import_Task SHALL 将沪深市场每日交易统计数据写入 market_daily_info 表（PostgreSQL），包含 trade_date、exchange、ts_code、ts_name、com_count、total_share、float_share、total_mv、float_mv、amount、vol、trans_count 字段，使用 ON CONFLICT (trade_date, exchange, ts_code) 策略去重，单次最大4000行
2. WHEN 用户选择 sz_daily_info 接口并设置日期范围，THE Import_Task SHALL 将深圳市场每日交易情况数据写入 sz_daily_info 表（PostgreSQL），包含 trade_date、ts_code、count、amount、vol、total_share、total_mv、float_share、float_mv 字段，使用 ON CONFLICT (trade_date, ts_code) 策略去重，单次最大2000行
3. THE Import_Task SHALL 遵循 settings.rate_limit_kline（0.18 秒）频率限制
4. THE API_Registry SHALL 将 daily_info 标注为 basic 权限级别（600积分），sz_daily_info 标注为 advanced 权限级别（2000积分） 【调整：根据文档积分要求更新权限级别】

### 需求 19：国际主要指数导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 国际主要指数数据（index_global），以便跟踪全球市场走势。

#### 验收标准

1. WHEN 用户选择 index_global 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器和可选的指数代码输入框
2. WHEN 导入 index_global 数据时，THE Import_Task SHALL 将国际指数行情数据写入 index_global 表（PostgreSQL），包含 ts_code、trade_date、open、close、high、low、pre_close、change、pct_chg、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重，单次最大4000行
3. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
4. THE API_Registry SHALL 将 index_global 标注为 advanced 权限级别（6000积分） 【调整：根据文档积分要求从 basic 更新为 advanced，6000积分属于 advanced 范围（2000-6000含6000）】

### 需求 20：导入任务进度追踪

**用户故事：** 作为量化交易员，我希望实时查看每个导入任务的进度，以便了解导入状态和预估完成时间。

#### 验收标准

1. WHEN 导入任务开始执行，THE Import_Service SHALL 在 Redis 中初始化进度数据，键格式为 `tushare:import:{task_id}`，包含 total、completed、failed、status、current_item 字段
2. WHILE 导入任务运行中，THE Import_Task SHALL 每处理完一批记录后更新 Redis 中的进度数据
3. WHEN 前端轮询进度接口，THE TushareImportView SHALL 每 3 秒请求一次 `/data/tushare/import/status/{task_id}` 并更新进度条和状态文本
4. WHEN 导入任务完成或失败，THE Import_Service SHALL 将 Redis 中的状态更新为 "completed" 或 "failed"
5. THE TushareImportView SHALL 显示进度百分比、已完成数量、失败数量和当前处理项

### 需求 21：导入任务停止控制

**用户故事：** 作为量化交易员，我希望能够停止正在运行的导入任务，以便在发现问题时及时中断。

#### 验收标准

1. WHILE 导入任务状态为 "running" 或 "pending"，THE TushareImportView SHALL 显示"停止导入"按钮
2. WHEN 用户点击"停止导入"，THE Import_Service SHALL 在 Redis 中设置停止信号键 `tushare:import:stop:{task_id}`
3. WHILE 导入任务运行中，THE Import_Task SHALL 在每批记录处理前检查停止信号，检测到信号后将状态更新为 "stopped" 并终止执行
4. WHEN 导入任务停止后，THE TushareImportView SHALL 显示"已停止"状态标签

### 需求 22：API Token 验证

**用户故事：** 作为量化交易员，我希望在导入前验证 Tushare API Token 是否有效，以便避免因 Token 无效导致导入失败。

#### 验收标准

1. WHEN TushareImportView 页面加载时，THE TushareImportView SHALL 调用 `/data/tushare/health` 接口检查 Tushare 连通性
2. WHEN Tushare 连通性检查通过，THE TushareImportView SHALL 显示绿色"已连接"状态指示器
3. IF Tushare 连通性检查失败，THEN THE TushareImportView SHALL 显示红色"未连接"状态指示器并禁用所有导入按钮
4. THE TushareImportView SHALL 提供"重新检测"按钮，允许用户手动触发连通性检查

### 需求 22a：多级权限 Token 配置

**用户故事：** 作为量化交易员，我希望系统支持多种不同积分权限级别的 Tushare API Token 配置，以便根据接口权限要求自动选择对应的 Token 进行数据导入。

#### 验收标准

1. THE Settings SHALL 新增四个 Token 配置项：`tushare_token_basic`（2000 积分及以下权限接口）、`tushare_token_advanced`（2000-6000 积分权限接口，包含6000积分）、`tushare_token_premium`（6000 积分以上权限接口）、`tushare_token_special`（需单独开通权限的接口），原有 `tushare_api_token` 作为默认 fallback 【调整：从三级扩展为四级，新增 premium 级别以匹配文档中的积分分布】
2. THE API_Registry SHALL 为每个 Tushare 接口标注权限级别（basic/advanced/premium/special），对应所需的积分等级：basic（120-2000积分，如 stock_basic、trade_cal、daily、margin、index_basic、index_dailybasic、daily_info、index_weekly、index_monthly 等）、advanced（2000-6000积分含6000，如 stock_st、limit_list_d、moneyflow_dc、cyq_perf、stk_factor_pro、ths_index、dc_index、tdx_index、stk_nineturn、broker_recommend、index_daily、index_weight、index_classify、index_member_all、sw_daily、ci_index_member、ci_daily、idx_factor_pro、sz_daily_info、index_global 等）、premium（6000积分以上，如 limit_list_ths、limit_step、limit_cpt_list、report_rc、ccass_hold_detail、dc_hot、hm_detail 等）、special（需单独开通，如 stk_premarket、rt_k、rt_min、stk_auction、stk_auction_o、stk_auction_c、rt_idx_k、rt_idx_min、rt_idx_min_daily、idx_mins、rt_sw_k 等） 【调整：根据指数专题文档积分信息更新权限级别标注，index_global 从 basic 调整为 advanced（6000积分属于 advanced 范围），index_daily/index_weight/index_classify 调整为 advanced，新增 index_member_all/ci_index_member/idx_factor_pro/rt_idx_k/rt_idx_min/rt_idx_min_daily/idx_mins/rt_sw_k 的权限标注】
3. WHEN Import_Service 调用 Tushare API 时，THE Import_Service SHALL 根据接口的权限级别自动选择对应的 Token：basic 级别使用 `tushare_token_basic`，advanced 级别使用 `tushare_token_advanced`，premium 级别使用 `tushare_token_premium`，special 级别使用 `tushare_token_special`
4. IF 对应级别的 Token 未配置（为空），THEN THE Import_Service SHALL 回退使用 `tushare_api_token` 作为默认 Token
5. THE TushareImportView SHALL 在页面顶部的连接状态区域显示四个 Token 的配置状态（已配置/未配置），帮助用户了解哪些权限级别可用
6. THE TushareImportView SHALL 在每个 API 接口旁显示其所需的权限级别标签（基础/高级/专业/特殊），IF 对应 Token 未配置 THEN 该接口的导入按钮显示为禁用状态并提示"需配置对应权限 Token"
7. THE Settings SHALL 通过 .env 文件配置四个 Token：`TUSHARE_TOKEN_BASIC`、`TUSHARE_TOKEN_ADVANCED`、`TUSHARE_TOKEN_PREMIUM`、`TUSHARE_TOKEN_SPECIAL`

### 需求 23：导入参数配置

**用户故事：** 作为量化交易员，我希望为每个导入接口配置参数（日期范围、股票代码、市场等），以便精确控制导入范围。

#### 验收标准

1. WHEN 用户选择需要日期范围的接口（daily、index_daily 等），THE TushareImportView SHALL 显示起止日期选择器，默认结束日期为当天
2. WHEN 用户选择需要股票代码的接口，THE TushareImportView SHALL 显示股票代码输入框，支持逗号分隔多个代码，留空表示全市场
3. WHEN 用户选择需要市场参数的接口（index_basic），THE TushareImportView SHALL 显示市场下拉选择器（SSE/SZSE/CSI/全部）
4. IF 用户未填写必填参数，THEN THE TushareImportView SHALL 禁用"开始导入"按钮并显示参数提示

### 需求 24：导入历史记录

**用户故事：** 作为量化交易员，我希望查看历史导入记录，以便了解过去的导入情况和数据覆盖范围。

#### 验收标准

1. THE TushareImportView SHALL 在页面底部显示最近 20 条导入记录列表
2. THE TushareImportView SHALL 为每条记录显示：接口名称、导入时间、数据量、状态（成功/失败/已停止）、耗时
3. WHEN 导入任务完成后，THE Import_Service SHALL 将导入记录写入 PostgreSQL 的 tushare_import_log 表
4. THE Import_Service SHALL 在 tushare_import_log 表中记录 api_name、params_json（JSONB）、status、record_count、error_message、started_at、finished_at 字段
5. WHEN TushareImportView 页面加载时，THE TushareImportView SHALL 从 `/data/tushare/import/history` 接口查询 tushare_import_log 表获取最近 20 条导入记录
6. THE Import_Service SHALL 在导入任务开始时即在 tushare_import_log 表中创建记录（status 为 "running"），任务结束后更新 status、record_count、error_message、finished_at 字段

### 需求 25：数据模型扩展

**用户故事：** 作为量化交易员，我希望系统具备存储 Tushare 各类数据的表结构，以便导入的数据能够持久化并供后续分析使用。

#### 验收标准

1. THE System SHALL 创建 trade_calendar 表（PostgreSQL/PGBase），包含 exchange（String）、cal_date（Date，主键）、is_open（Boolean）字段
2. THE System SHALL 创建 financial_statement 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、report_type（income/balance/cashflow）、data_json（JSONB）字段，使用 (ts_code, end_date, report_type) 复合唯一约束
3. THE System SHALL 创建 dividend 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、div_proc、stk_div、cash_div 字段
4. THE System SHALL 创建 index_info 表（PostgreSQL/PGBase），包含 ts_code（主键）、name、market、publisher、category、base_date、base_point、list_date 字段
5. THE System SHALL 创建 index_weight 表（PostgreSQL/PGBase），包含 index_code、con_code、trade_date、weight 字段，使用 (index_code, con_code, trade_date) 复合唯一约束
6. THE System SHALL 创建 index_dailybasic 表（PostgreSQL/PGBase），包含 ts_code、trade_date、pe、pb、turnover_rate、total_mv、float_mv 字段，使用 (ts_code, trade_date) 复合唯一约束
7. THE System SHALL 创建 money_flow 表（PostgreSQL/PGBase），包含 ts_code、trade_date、buy_sm_amount、sell_sm_amount、buy_md_amount、sell_md_amount、buy_lg_amount、sell_lg_amount、buy_elg_amount、sell_elg_amount、net_mf_amount 字段，使用 (ts_code, trade_date) 复合唯一约束
8. THE System SHALL 创建 suspend_info 表（PostgreSQL/PGBase），包含 ts_code、suspend_date、resume_date、suspend_type 字段
9. THE System SHALL 创建 tushare_import_log 表（PostgreSQL/PGBase），包含 id（自增主键）、api_name、params_json（JSONB）、status、record_count、error_message、started_at、finished_at 字段
10. THE System SHALL 创建 margin_data 表（PostgreSQL/PGBase），包含 trade_date、exchange_id、rzye、rzmre、rzche、rqye、rqmcl、rzrqye 字段，使用 (trade_date, exchange_id) 复合唯一约束
11. THE System SHALL 创建 margin_detail 表（PostgreSQL/PGBase），包含 ts_code、trade_date、rzye、rzmre、rzche、rqye、rqmcl、rqyl 字段，使用 (ts_code, trade_date) 复合唯一约束
12. THE System SHALL 创建 margin_secs 表（PostgreSQL/PGBase），包含 ts_code、trade_date、mg_type、is_new 字段 【调整：替代原 margin_target 表，新增 trade_date 字段】
13. THE System SHALL 创建 block_trade 表（PostgreSQL/PGBase），包含 ts_code、trade_date、price、vol、amount、buyer、seller 字段，使用 (ts_code, trade_date, buyer, seller) 复合唯一约束
14. THE System SHALL 创建 top_holders 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、holder_name、hold_amount、hold_ratio、holder_type 字段，使用 (ts_code, end_date, holder_name, holder_type) 复合唯一约束
15. THE System SHALL 创建 limit_list 表（PostgreSQL/PGBase），包含 ts_code、trade_date、industry、close、pct_chg、amount、limit_amount、float_mv、total_mv、turnover_ratio、fd_amount、first_time、last_time、open_times、up_stat、limit_times、limit 字段，使用 (ts_code, trade_date, limit) 复合唯一约束
16. THE System SHALL 创建 index_global 表（PostgreSQL/PGBase），包含 ts_code、trade_date、open、close、high、low、pre_close、change、pct_chg、vol、amount 字段，使用 (ts_code, trade_date) 复合唯一约束
17. THE System SHALL 创建 index_tech 表（PostgreSQL/PGBase），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、boll_upper、boll_mid、boll_lower 字段，使用 (ts_code, trade_date) 复合唯一约束 【说明：表名保持 index_tech 不变，数据来源接口从 index_tech 更新为 idx_factor_pro】
18. THE System SHALL 创建 stock_company 表（PostgreSQL/PGBase），包含 ts_code（主键）、chairman、manager、secretary、reg_capital、setup_date、province、city、website 字段
19. THE System SHALL 创建 stock_namechange 表（PostgreSQL/PGBase），包含 ts_code、name、start_date、end_date、change_reason 字段
20. THE System SHALL 创建 stock_hsgt 表（PostgreSQL/PGBase），包含 ts_code、hs_type、in_date、out_date、is_new 字段 【调整：替代原 hs_constituent 表】
21. THE System SHALL 创建 stk_rewards 表（PostgreSQL/PGBase），包含 ts_code、ann_date、name、title、reward、hold_vol 字段
22. THE System SHALL 创建 stk_managers 表（PostgreSQL/PGBase），包含 ts_code、ann_date、name、gender、lev、title、edu、national、birthday、begin_date、end_date 字段
23. THE System SHALL 创建 stk_holdernumber 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、holder_num、holder_num_change 字段
24. THE System SHALL 创建 stk_holdertrade 表（PostgreSQL/PGBase），包含 ts_code、ann_date、holder_name、change_vol、change_ratio、after_vol、after_ratio、in_de 字段
25. THE System SHALL 创建 stk_limit 表（PostgreSQL/PGBase），包含 ts_code、trade_date、up_limit、down_limit 字段，使用 (ts_code, trade_date) 复合唯一约束
26. THE System SHALL 创建 slb_len 表（PostgreSQL/PGBase），包含 ts_code、trade_date、len_rate、len_amt 字段
27. THE System SHALL 创建 moneyflow_hsgt 表（PostgreSQL/PGBase），包含 trade_date、ggt_ss、ggt_sz、hgt、sgt、north_money、south_money 字段，使用 (trade_date) 唯一约束
28. THE System SHALL 创建 moneyflow_ind 表（PostgreSQL/PGBase），包含 trade_date、industry_name、data_source、buy_amount、sell_amount、net_amount 字段
29. THE System SHALL 创建 hm_list 表（PostgreSQL/PGBase），包含 hm_name、hm_code、market、desc 字段
30. THE System SHALL 创建 hm_detail 表（PostgreSQL/PGBase），包含 trade_date、ts_code、hm_name、buy_amount、sell_amount、net_amount 字段
31. THE System SHALL 创建 market_daily_info 表（PostgreSQL/PGBase），包含 trade_date、exchange、ts_code、ts_name、com_count、total_share、float_share、total_mv、float_mv、amount、vol、trans_count 字段，使用 (trade_date, exchange, ts_code) 复合唯一约束
32. THE System SHALL 创建 sz_daily_info 表（PostgreSQL/PGBase），包含 trade_date、ts_code、count、amount、vol、total_share、total_mv、float_share、float_mv 字段，使用 (trade_date, ts_code) 复合唯一约束
33. THE System SHALL 创建 top_list 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、pct_change、turnover_rate、amount、l_sell、l_buy、l_amount、net_amount、net_rate、amount_rate、float_values、reason 字段，使用 (trade_date, ts_code, reason) 复合唯一约束
34. THE System SHALL 创建 top_inst 表（PostgreSQL/PGBase），包含 trade_date、ts_code、exalter、buy、buy_rate、sell、sell_rate、net_buy 字段，使用 (trade_date, ts_code, exalter) 复合唯一约束
35. THE System SHALL 创建 new_share 表（PostgreSQL/PGBase），包含 ts_code（主键）、sub_code、name、ipo_date、issue_date、amount、market_amount、price、pe、limit_amount、funds、ballot 字段
36. THE System SHALL 创建 stock_st 表（PostgreSQL/PGBase），包含 ts_code、name、is_st、st_date、st_type 字段
37. THE System SHALL 创建 stk_premarket 表（PostgreSQL/PGBase），包含 ts_code、trade_date、total_share、float_share、free_share、total_mv、float_mv、up_limit、down_limit 字段，使用 (ts_code, trade_date) 复合唯一约束 【调整：替代原 daily_share 表，新增涨跌停价格字段】
38. THE System SHALL 创建 forecast 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、type、p_change_min、p_change_max、net_profit_min、net_profit_max、summary 字段，使用 (ts_code, end_date) 复合唯一约束
39. THE System SHALL 创建 express 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、revenue、operate_profit、total_profit、n_income、total_assets、total_hldr_eqy_exc_min_int、diluted_eps、yoy_net_profit、bps、perf_summary 字段，使用 (ts_code, end_date) 复合唯一约束
40. THE System SHALL 创建 stk_factor 表（PostgreSQL/PGBase），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、rsi_24、boll_upper、boll_mid、boll_lower、cci、wr、dmi、trix、bias 字段，使用 (ts_code, trade_date) 复合唯一约束 【调整：新增 wr、dmi、trix、bias 等专业版字段】
41. THE System SHALL 创建 limit_step 表（PostgreSQL/PGBase），包含 ts_code、trade_date、name、close、pct_chg、step、limit_order、amount、turnover_ratio、fd_amount、first_time、last_time、open_times 字段，使用 (ts_code, trade_date) 复合唯一约束
42. THE System SHALL 创建 limit_list_ths 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、pct_chg、fd_amount、first_time、last_time、open_times、limit 字段，使用 (ts_code, trade_date, limit) 复合唯一约束 【调整：替代原 ths_limit 表】
43. THE System SHALL 创建 dc_hot 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
44. THE System SHALL 创建 ths_hot 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
45. THE System SHALL 创建 kpl_list 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、pct_chg、tag 字段
46. THE System SHALL 创建 moneyflow_mkt_dc 表（PostgreSQL/PGBase），包含 trade_date、close、change、pct_change、net_mf_amount、net_mf_amount_rate、buy_elg_amount、sell_elg_amount、buy_lg_amount、sell_lg_amount、buy_md_amount、sell_md_amount、buy_sm_amount、sell_sm_amount 字段，使用 (trade_date) 唯一约束
47. THE System SHALL 在现有 DataSource 枚举（`app/models/sector.py`）中新增 `CI = "CI"`（中信行业）和 `THS = "THS"`（同花顺概念/行业板块）两个枚举值，原有 `TI = "TI"` 保留用于申万行业数据
48. THE System SHALL 将 ths_index/dc_index/tdx_index 板块数据复用现有 sector_info 表（通过 data_source="THS"/"DC"/"TDX" 区分），将 ths_member/dc_member/tdx_member/index_member_all/ci_index_member 成分股数据复用现有 sector_constituent 表（通过 data_source="THS"/"DC"/"TDX"/"TI"/"CI" 区分），将 ths_daily/dc_daily/tdx_daily/sw_daily/rt_sw_k/ci_daily 板块行情数据复用现有 sector_kline 表，不新建独立表 【调整：新增 index_member_all（申万行业成分）、ci_index_member（中信行业成分）复用 sector_constituent 表，rt_sw_k（申万实时行情）复用 sector_kline 表】
49. THE System SHALL 创建 st_warning 表（PostgreSQL/PGBase），包含 ts_code、trade_date、name、close、pct_chg、vol、amount 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
50. THE System SHALL 创建 bse_mapping 表（PostgreSQL/PGBase），包含 old_code、new_code、name、list_date 字段 【新增】
51. THE System SHALL 创建 hsgt_top10 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、change、rank、market_type、amount、net_amount、buy、sell 字段，使用 (trade_date, ts_code, market_type) 复合唯一约束 【新增】
52. THE System SHALL 创建 ggt_top10 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、p_change、rank、market_type、amount、net_amount、buy、sell 字段，使用 (trade_date, ts_code, market_type) 复合唯一约束 【新增】
53. THE System SHALL 创建 ggt_daily 表（PostgreSQL/PGBase），包含 trade_date、buy_amount、buy_volume、sell_amount、sell_volume 字段，使用 (trade_date) 唯一约束 【新增】
54. THE System SHALL 创建 ggt_monthly 表（PostgreSQL/PGBase），包含 month、buy_amount、buy_volume、sell_amount、sell_volume 字段，使用 (month) 唯一约束 【新增】
55. THE System SHALL 创建 fina_mainbz 表（PostgreSQL/PGBase），包含 ts_code、end_date、bz_item、bz_sales、bz_profit、bz_cost、curr_type 字段，使用 (ts_code, end_date, bz_item) 复合唯一约束 【新增】
56. THE System SHALL 创建 disclosure_date 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、pre_date、actual_date 字段，使用 (ts_code, end_date) 复合唯一约束 【新增】
57. THE System SHALL 创建 stk_shock 表（PostgreSQL/PGBase），包含 ts_code、trade_date、shock_type、pct_chg、vol、amount 字段，使用 (ts_code, trade_date, shock_type) 复合唯一约束 【新增】
58. THE System SHALL 创建 stk_high_shock 表（PostgreSQL/PGBase），包含 ts_code、trade_date、shock_type、pct_chg、vol、amount 字段，使用 (ts_code, trade_date, shock_type) 复合唯一约束 【新增】
59. THE System SHALL 创建 stk_alert 表（PostgreSQL/PGBase），包含 ts_code、trade_date、alert_type、alert_desc 字段 【新增】
60. THE System SHALL 创建 pledge_stat 表（PostgreSQL/PGBase），包含 ts_code、end_date、pledge_count、unrest_pledge、rest_pledge、total_share、pledge_ratio 字段，使用 (ts_code, end_date) 复合唯一约束 【新增】
61. THE System SHALL 创建 pledge_detail 表（PostgreSQL/PGBase），包含 ts_code、ann_date、holder_name、pledge_amount、start_date、end_date、is_release 字段 【新增】
62. THE System SHALL 创建 repurchase 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、proc、exp_date、vol、amount、high_limit、low_limit 字段 【新增】
63. THE System SHALL 创建 share_float 表（PostgreSQL/PGBase），包含 ts_code、ann_date、float_date、float_share、float_ratio、holder_name、share_type 字段 【新增】
64. THE System SHALL 创建 report_rc 表（PostgreSQL/PGBase），包含 ts_code、report_date、broker_name、analyst_name、target_price、rating、eps_est 字段 【新增】
65. THE System SHALL 创建 cyq_perf 表（PostgreSQL/PGBase），包含 ts_code、trade_date、his_low、his_high、cost_5pct、cost_15pct、cost_50pct、cost_85pct、cost_95pct、weight_avg、winner_rate 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
66. THE System SHALL 创建 cyq_chips 表（PostgreSQL/PGBase），包含 ts_code、trade_date、price、percent 字段 【新增】
67. THE System SHALL 创建 ccass_hold 表（PostgreSQL/PGBase），包含 ts_code、trade_date、participant_id、participant_name、hold_amount、hold_ratio 字段 【新增】
68. THE System SHALL 创建 ccass_hold_detail 表（PostgreSQL/PGBase），包含 ts_code、trade_date、participant_id、participant_name、hold_amount、hold_ratio 字段 【新增】
69. THE System SHALL 创建 hk_hold 表（PostgreSQL/PGBase），包含 ts_code、trade_date、code、vol、ratio、exchange 字段，使用 (ts_code, trade_date, exchange) 复合唯一约束 【新增】
70. THE System SHALL 创建 stk_auction_o 表（PostgreSQL/PGBase），包含 ts_code、trade_date、open、vol、amount 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
71. THE System SHALL 创建 stk_auction_c 表（PostgreSQL/PGBase），包含 ts_code、trade_date、close、vol、amount 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
72. THE System SHALL 创建 stk_nineturn 表（PostgreSQL/PGBase），包含 ts_code、trade_date、turn_type、turn_number 字段，使用 (ts_code, trade_date, turn_type) 复合唯一约束 【新增】
73. THE System SHALL 创建 stk_ah_comparison 表（PostgreSQL/PGBase），包含 ts_code、trade_date、a_close、h_close、ah_ratio 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
74. THE System SHALL 创建 stk_surv 表（PostgreSQL/PGBase），包含 ts_code、surv_date、fund_name、surv_type、participants 字段 【新增】
75. THE System SHALL 创建 broker_recommend 表（PostgreSQL/PGBase），包含 month、broker、ts_code、name、rating 字段 【新增】
76. THE System SHALL 创建 moneyflow_ths 表（PostgreSQL/PGBase），包含 ts_code、trade_date、buy_sm_amount、sell_sm_amount、buy_md_amount、sell_md_amount、buy_lg_amount、sell_lg_amount、buy_elg_amount、sell_elg_amount、net_mf_amount 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
77. THE System SHALL 创建 moneyflow_dc 表（PostgreSQL/PGBase），包含 ts_code、trade_date、buy_sm_amount、sell_sm_amount、buy_md_amount、sell_md_amount、buy_lg_amount、sell_lg_amount、buy_elg_amount、sell_elg_amount、net_mf_amount 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
78. THE System SHALL 创建 moneyflow_cnt_ths 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、buy_amount、sell_amount、net_amount 字段 【新增】
79. THE System SHALL 创建 limit_cpt_list 表（PostgreSQL/PGBase），包含 trade_date、concept_name、limit_count、up_count、down_count、amount 字段 【新增】
80. THE System SHALL 创建 stk_auction 表（PostgreSQL/PGBase），包含 ts_code、trade_date、open、vol、amount、bid_price、bid_vol 字段，使用 (ts_code, trade_date) 复合唯一约束 【新增】
81. THE System SHALL 创建 kpl_concept_cons 表（PostgreSQL/PGBase），包含 concept_code、ts_code、name 字段 【新增】
82. THE System SHALL 创建 dc_concept 表（PostgreSQL/PGBase），包含 concept_code、concept_name、src 字段 【新增】
83. THE System SHALL 创建 dc_concept_cons 表（PostgreSQL/PGBase），包含 concept_code、ts_code、name 字段 【新增】
84. THE System SHALL 通过 Alembic 迁移脚本创建上述所有新表
85. 【移除】原 daily_share 表（被 stk_premarket 替代）、原 margin_target 表（被 margin_secs 替代）、原 slb_sec 表（文档中未出现）、原 hs_constituent 表（被 stock_hsgt 替代）、原 stk_account 表（文档中未出现）、原 ths_limit 表（被 limit_list_ths 替代）
86. 【说明】指数专题接口名称变更：index_tech → idx_factor_pro（表名 index_tech 保持不变）、index_1min_realtime → rt_idx_min、index_min → idx_mins；新增接口 rt_idx_k、rt_idx_min_daily、index_member_all、ci_index_member、rt_sw_k 均复用现有表结构（kline/sector_constituent/sector_kline），无需新建表 【新增】

### 需求 26：ts_code 与 symbol 格式转换

**用户故事：** 作为量化交易员，我希望系统自动处理 Tushare ts_code 格式（如 000001.SZ）与系统内部 symbol 格式（如 000001）之间的转换，以便数据一致性。

#### 验收标准

1. WHEN 导入股票相关数据时，THE Import_Task SHALL 将 Tushare 返回的 ts_code（如 600000.SH）转换为纯 6 位 symbol（如 600000）后写入 stock_info 和 kline 表
2. WHEN 导入指数相关数据时，THE Import_Task SHALL 保留完整的 ts_code 格式（如 000001.SH）作为指数标识符写入 index_info 和 kline 表
3. THE Import_Service SHALL 在调用 Tushare API 时自动将用户输入的纯数字代码补全为 ts_code 格式（6 开头补 .SH，0/3 开头补 .SZ）
4. THE Import_Service SHALL 在 API_Registry 中为每个接口标注代码格式要求（stock_symbol/index_code/none）
