# 需求文档：Tushare 数据在线导入

## 简介

在数据管理模块的"在线数据"菜单下新增"tushare"子菜单，提供 Tushare 平台股票数据和指数专题数据的在线导入功能。用户可按数据分类选择导入内容、设置日期范围和参数，通过 Celery 异步任务执行导入，并实时查看导入进度。

## 术语表

- **Tushare_Adapter**：已有的 Tushare 数据源适配器（`app/services/data_engine/tushare_adapter.py`），通过 HTTP POST + Token 认证访问 Tushare API
- **Import_Service**：Tushare 数据导入编排服务，负责参数校验、任务分发和进度管理
- **Import_Task**：Celery 异步导入任务，执行实际的 API 调用和数据写入
- **TushareImportView**：前端 Tushare 数据导入页面组件
- **Stock_Data**：Tushare 股票数据大类，包含基础数据、行情数据、财务数据、参考数据、特色数据、两融及转融通、资金流向数据、打板专题数据等子分类
- **Index_Data**：Tushare 指数专题数据大类，包含指数基本信息、指数行情（日线/周线/月线/分钟）、指数成分和权重、申万行业、中信行业、大盘指数每日指标、指数技术面因子、沪深市场每日交易统计、深圳市场每日交易情况、国际主要指数等子分类
- **ts_code**：Tushare 股票/指数代码格式，如 600000.SH（上海）、000001.SZ（深圳）、000001.BJ（北京）
- **symbol**：系统内部使用的纯 6 位数字股票代码格式，如 600000、000001
- **API_Registry**：Tushare API 接口注册表，定义每个接口的名称、参数、字段映射和目标存储表
- **Rate_Limiter**：API 调用频率限制器，根据 Tushare 接口限制控制调用间隔
- **Import_Record**：导入历史记录，持久化存储在 PostgreSQL 的 tushare_import_log 表中，记录每次导入任务的元数据和执行结果
- **Reference_Data**：Tushare 参考数据子分类，包含上市公司信息（stock_company）、股票曾用名（namechange）、沪深股通成份股（hs_const）、管理层薪酬和持股（stk_rewards）、上市公司管理层（stk_managers）
- **Special_Data**：Tushare 特色数据子分类，包含融资融券交易明细（margin_detail）、前十大股东（top10_holders）、前十大流通股东（top10_floatholders）、股东人数（stk_holdernumber）、股东增减持（stk_holdertrade）、大宗交易（block_trade）、股票开户数据（stk_account）、每日涨跌停价格（stk_limit）
- **Margin_Data**：Tushare 两融及转融通子分类，包含融资融券汇总（margin）、融资融券交易明细（margin_detail）、融资融券标的（margin_target）、转融通出借（slb_len）、转融通证券出借（slb_sec）
- **Limit_Up_Data**：Tushare 打板专题数据子分类，包含每日涨跌停统计（limit_list_d）、涨停股票连板天梯（limit_step）、每日涨跌停价格（stk_limit）、游资名录（hm_list）、游资每日明细（hm_detail）、龙虎榜每日明细（top_list）、龙虎榜机构交易明细（top_inst）、同花顺涨跌停榜单（ths_limit）、东方财富App热榜（dc_hot）、同花顺App热榜（ths_hot）、同花顺行业概念板块（ths_index → 复用 sector_info，data_source="THS"）、同花顺行业概念成分（ths_member → 复用 sector_constituent，data_source="THS"）、东方财富概念板块（dc_index → 复用 sector_info，data_source="DC"）、东方财富概念成分（dc_member → 复用 sector_constituent，data_source="DC"）、开盘啦榜单数据（kpl_list）
- **DataSource_Enum**：板块数据来源枚举（`app/models/sector.py`），现有值 DC（东方财富）、TI（申万行业）、TDX（通达信），需新增 CI（中信行业）和 THS（同花顺概念/行业板块）
- **Token_Tier**：Tushare API Token 权限级别，分为 basic（6000 积分及以下）、advanced（6000 积分以上）、special（需单独开通权限）三级，系统根据接口权限级别自动选择对应 Token
- **Low_Freq_Data**：低频行情数据，包含日K（daily/index_daily）、周K（weekly/index_weekly）、月K（monthly/index_monthly），与中频数据分开导入
- **Mid_Freq_Data**：中频行情数据，包含分钟级行情（stk_mins/index_min/index_1min_realtime），数据量较大，与低频数据分开导入

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
3. THE TushareImportView SHALL 在"股票数据"分类下显示以下子分类：基础数据、行情数据（低频：日K/周K/月K）、行情数据（中频：分钟级）、财务数据、参考数据、特色数据、两融及转融通、资金流向数据、打板专题数据
4. THE TushareImportView SHALL 在"指数专题"分类下显示以下子分类：指数基本信息、指数行情数据（低频：日线/周线/月线）、指数行情数据（中频：实时分钟/历史分钟）、指数成分和权重、申万行业数据、中信行业数据、大盘指数每日指标、指数技术面因子、沪深市场每日交易统计、深圳市场每日交易情况、国际主要指数
5. WHEN 用户展开某个子分类，THE TushareImportView SHALL 显示该子分类下所有可导入的 Tushare API 接口列表
6. THE TushareImportView SHALL 为每个 API 接口显示接口名称（如 stock_basic）和中文说明（如"股票基础列表"）
7. THE TushareImportView SHALL 在页面底部显示导入历史记录区域

### 需求 3：股票基础数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 股票基础数据（stock_basic、trade_cal、new_share、stock_st、stk_delist、daily_share、bak_basic），以便获取全市场股票列表、交易日历、IPO新股、ST列表、退市历史和每日股本信息。

#### 验收标准

1. WHEN 用户选择 stock_basic 接口并点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("stock_basic")` 获取全市场股票列表
2. WHEN stock_basic 数据获取成功，THE Import_Task SHALL 将 ts_code 转换为纯 6 位 symbol 格式后写入 stock_info 表，使用 ON CONFLICT (symbol) 策略更新已有记录
3. WHEN 用户选择 trade_cal 接口并点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("trade_cal")` 获取交易日历数据
4. WHEN trade_cal 数据获取成功，THE Import_Task SHALL 将数据写入 trade_calendar 表（PostgreSQL），包含 exchange、cal_date、is_open 字段
5. WHEN 用户选择 new_share 接口并点击"开始导入"，THE Import_Task SHALL 将 IPO 新股上市数据写入 new_share 表（PostgreSQL），包含 ts_code、sub_code、name、ipo_date、issue_date、amount、market_amount、price、pe、limit_amount、funds、ballot 字段，使用 ON CONFLICT (ts_code) 策略去重
6. WHEN 用户选择 stock_st（或 st）接口并点击"开始导入"，THE Import_Task SHALL 将 ST 股票列表数据写入 stock_st 表（PostgreSQL），包含 ts_code、name、is_st（Y/N）、st_date、st_type 字段
7. WHEN 用户选择 stk_delist 接口并点击"开始导入"，THE Import_Task SHALL 将退市股票历史列表数据写入 stock_info 表，更新 is_delisted 字段为 True，同时记录 delist_date
8. WHEN 用户选择 daily_share 接口并设置日期范围，THE Import_Task SHALL 将每日股本（盘前）数据写入 daily_share 表（PostgreSQL），包含 ts_code、trade_date、total_share、float_share、free_share、total_mv、float_mv 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
9. WHEN 用户选择 bak_basic 接口并点击"开始导入"，THE Import_Task SHALL 将备用基础信息数据写入 stock_info 表，补充更新已有字段
10. IF Tushare API 调用失败，THEN THE Import_Task SHALL 记录错误日志并将任务状态标记为失败，同时更新 Import_Record

### 需求 4：股票低频行情数据导入（日K/周K/月K）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 股票低频行情数据（daily、weekly、monthly、adj_factor、daily_basic、suspend_d），低频数据与中频数据分开导入，以便分别管理不同频率的数据导入任务。

#### 验收标准

1. THE TushareImportView SHALL 在"行情数据"子分类下将接口分为"低频行情（日K/周K/月K）"和"中频行情（分钟级）"两个独立分组
2. WHEN 用户选择低频行情接口（daily/weekly/monthly）并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器和可选的股票代码输入框
3. WHEN 用户点击"开始导入"，THE Import_Service SHALL 通过 Celery 分发异步导入任务到 data_sync 队列
4. WHEN 导入 daily/weekly/monthly 数据时，THE Import_Task SHALL 将行情数据写入 TimescaleDB 的 kline 超表，freq 字段分别设为 "1d"/"1w"/"1M"，symbol 字段存储纯 6 位代码
5. WHEN 导入 adj_factor 数据时，THE Import_Task SHALL 将复权因子写入 adjustment_factor 表
6. WHEN 导入 daily_basic 数据时，THE Import_Task SHALL 将每日基本指标（换手率、市盈率、市净率、总市值等）更新到 stock_info 表对应字段
7. WHEN 导入 suspend_d 数据时，THE Import_Task SHALL 将停复牌信息写入 suspend_info 表（PostgreSQL），包含 ts_code、suspend_date、resume_date、suspend_type 字段
8. THE Import_Task SHALL 按 BATCH_SIZE=50 分批处理股票列表，每次 API 调用间隔遵循 settings.rate_limit_kline（0.18 秒）频率限制

### 需求 4a：股票中频行情数据导入（分钟级）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 股票分钟级行情数据（stk_mins），中频数据与低频数据分开导入，以便独立控制分钟级数据的导入范围和频率。

#### 验收标准

1. WHEN 用户选择中频行情接口（stk_mins）并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器、股票代码输入框和频率选择器（1min/5min/15min/30min/60min）
2. WHEN 用户点击"开始导入"，THE Import_Service SHALL 通过 Celery 分发异步导入任务到 data_sync 队列
3. WHEN 导入 stk_mins 数据时，THE Import_Task SHALL 将分钟行情数据写入 TimescaleDB 的 kline 超表，freq 字段根据用户选择设为 "1m"/"5m"/"15m"/"30m"/"60m"，symbol 字段存储纯 6 位代码
4. THE Import_Task SHALL 使用 ON CONFLICT (time, symbol, freq, adj_type) 策略去重
5. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
6. THE TushareImportView SHALL 在中频行情分组中提示用户"分钟级数据量较大，建议按单只股票或短日期范围分批导入"

### 需求 5：股票财务数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 财务数据（income、balancesheet、cashflow、fina_indicator、dividend、forecast、express），以便进行基本面分析和业绩预期跟踪。

#### 验收标准

1. WHEN 用户选择财务数据接口并设置报告期范围，THE TushareImportView SHALL 提供报告期选择器（年份+季度）
2. WHEN 用户点击"开始导入"，THE Import_Service SHALL 通过 Celery 分发异步导入任务
3. WHEN 导入 income/balancesheet/cashflow 数据时，THE Import_Task SHALL 将财务报表数据写入对应的 financial_statement 表（PostgreSQL），使用 ON CONFLICT (ts_code, end_date, report_type) 策略去重
4. WHEN 导入 fina_indicator 数据时，THE Import_Task SHALL 将财务指标数据更新到 stock_info 表的 pe_ttm、pb、roe 字段
5. WHEN 导入 dividend 数据时，THE Import_Task SHALL 将分红送股数据写入 dividend 表（PostgreSQL），包含 ts_code、ann_date、div_proc、stk_div、cash_div 字段
6. WHEN 导入 forecast 数据时，THE Import_Task SHALL 将业绩预告数据写入 forecast 表（PostgreSQL），包含 ts_code、ann_date、end_date、type（预增/预减/扭亏/首亏/续亏/续盈/略增/略减）、p_change_min、p_change_max、net_profit_min、net_profit_max、summary 字段，使用 ON CONFLICT (ts_code, end_date) 策略去重
7. WHEN 导入 express 数据时，THE Import_Task SHALL 将业绩快报数据写入 express 表（PostgreSQL），包含 ts_code、ann_date、end_date、revenue、operate_profit、total_profit、n_income、total_assets、total_hldr_eqy_exc_min_int、diluted_eps、yoy_net_profit、bps、perf_summary 字段，使用 ON CONFLICT (ts_code, end_date) 策略去重
8. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制

### 需求 6：参考数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 参考数据（stock_company、namechange、hs_const、stk_rewards、stk_managers），以便获取上市公司详细信息、曾用名、沪深股通成份股和管理层信息。

#### 验收标准

1. WHEN 用户选择 stock_company 接口并点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("stock_company")` 获取上市公司基本信息
2. WHEN stock_company 数据获取成功，THE Import_Task SHALL 将数据写入 stock_company 表（PostgreSQL），包含 ts_code、chairman、manager、secretary、reg_capital、setup_date、province、city、website 字段，使用 ON CONFLICT (ts_code) 策略更新已有记录
3. WHEN 用户选择 namechange 接口并点击"开始导入"，THE Import_Task SHALL 将股票曾用名数据写入 stock_namechange 表（PostgreSQL），包含 ts_code、name、start_date、end_date、change_reason 字段
4. WHEN 用户选择 hs_const 接口并指定类型（SH/SZ），THE Import_Task SHALL 将沪深股通成份股数据写入 hs_constituent 表（PostgreSQL），包含 ts_code、hs_type、in_date、out_date、is_new 字段
5. WHEN 用户选择 stk_rewards 接口，THE Import_Task SHALL 将管理层薪酬和持股数据写入 stk_rewards 表（PostgreSQL），包含 ts_code、ann_date、name、title、reward、hold_vol 字段
6. WHEN 用户选择 stk_managers 接口，THE Import_Task SHALL 将上市公司管理层数据写入 stk_managers 表（PostgreSQL），包含 ts_code、ann_date、name、gender、lev、title、edu、national、birthday、begin_date、end_date 字段
7. IF Tushare API 调用失败，THEN THE Import_Task SHALL 记录错误日志并将任务状态标记为失败，同时更新 Import_Record

### 需求 7：特色数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 特色数据（top10_holders、top10_floatholders、stk_holdernumber、stk_holdertrade、block_trade、stk_account、stk_limit），以便分析股东结构、大宗交易和涨跌停信息。

#### 验收标准

1. WHEN 用户选择 top10_holders 或 top10_floatholders 接口并设置报告期，THE Import_Task SHALL 将前十大股东/流通股东数据写入 top_holders 表（PostgreSQL），包含 ts_code、ann_date、end_date、holder_name、hold_amount、hold_ratio、holder_type（top10/float）字段，使用 ON CONFLICT (ts_code, end_date, holder_name, holder_type) 策略去重
2. WHEN 用户选择 stk_holdernumber 接口并设置日期范围，THE Import_Task SHALL 将股东人数数据写入 stk_holdernumber 表（PostgreSQL），包含 ts_code、ann_date、end_date、holder_num、holder_num_change 字段
3. WHEN 用户选择 stk_holdertrade 接口，THE Import_Task SHALL 将股东增减持数据写入 stk_holdertrade 表（PostgreSQL），包含 ts_code、ann_date、holder_name、change_vol、change_ratio、after_vol、after_ratio、in_de（增持/减持）字段
4. WHEN 用户选择 block_trade 接口并设置日期范围，THE Import_Task SHALL 将大宗交易数据写入 block_trade 表（PostgreSQL），包含 ts_code、trade_date、price、vol、amount、buyer、seller 字段，使用 ON CONFLICT (ts_code, trade_date, buyer, seller) 策略去重
5. WHEN 用户选择 stk_account 接口并设置日期范围，THE Import_Task SHALL 将股票开户数据写入 stk_account 表（PostgreSQL），包含 date、weekly_new、total、weekly_hold 字段
6. WHEN 用户选择 stk_limit 接口并设置日期范围，THE Import_Task SHALL 将每日涨跌停价格数据写入 stk_limit 表（PostgreSQL），包含 ts_code、trade_date、up_limit、down_limit 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
7. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制

### 需求 7a：股票技术面因子导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 股票技术面因子数据（stk_factor、stk_factor_pro），以便获取 MACD、KDJ、RSI、BOLL 等技术指标用于量化策略开发。

#### 验收标准

1. WHEN 用户选择 stk_factor 接口并设置日期范围和可选股票代码，THE TushareImportView SHALL 提供起止日期选择器和股票代码输入框
2. WHEN 导入 stk_factor 数据时，THE Import_Task SHALL 将股票技术面因子数据写入 stk_factor 表（PostgreSQL），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、rsi_24、boll_upper、boll_mid、boll_lower、cci 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. WHEN 用户选择 stk_factor_pro 接口（专业版）并设置日期范围和股票代码，THE Import_Task SHALL 将专业版技术面因子数据写入 stk_factor 表，包含更多技术指标字段（如 wr、dmi、trix、bias 等），使用 ON CONFLICT (ts_code, trade_date) 策略更新
4. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
5. THE API_Registry SHALL 将 stk_factor 标注为 basic 权限级别，stk_factor_pro 标注为 special 权限级别

### 需求 8：两融及转融通数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 两融及转融通数据（margin、margin_detail、margin_target、slb_len、slb_sec），以便分析融资融券和转融通市场动态。

#### 验收标准

1. WHEN 用户选择 margin 接口并设置日期范围，THE Import_Task SHALL 将融资融券汇总数据写入 margin_data 表（PostgreSQL），包含 trade_date、exchange_id、rzye（融资余额）、rzmre（融资买入额）、rzche（融资偿还额）、rqye（融券余额）、rqmcl（融券卖出量）、rzrqye（融资融券余额）字段，使用 ON CONFLICT (trade_date, exchange_id) 策略去重
2. WHEN 用户选择 margin_detail 接口并设置日期范围和可选股票代码，THE Import_Task SHALL 将融资融券交易明细写入 margin_detail 表（PostgreSQL），包含 ts_code、trade_date、rzye、rzmre、rzche、rqye、rqmcl、rqyl 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. WHEN 用户选择 margin_target 接口，THE Import_Task SHALL 将融资融券标的数据写入 margin_target 表（PostgreSQL），包含 ts_code、mg_type（融资/融券）、is_new 字段
4. WHEN 用户选择 slb_len 接口并设置日期范围，THE Import_Task SHALL 将转融通出借数据写入 slb_len 表（PostgreSQL），包含 ts_code、trade_date、len_rate、len_amt 字段
5. WHEN 用户选择 slb_sec 接口并设置日期范围，THE Import_Task SHALL 将转融通证券出借数据写入 slb_sec 表（PostgreSQL），包含 ts_code、trade_date、sec_amt、sec_vol 字段
6. THE Import_Task SHALL 遵循 settings.rate_limit_money_flow（0.30 秒）频率限制

### 需求 9：资金流向数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 资金流向数据（moneyflow、moneyflow_hsgt、moneyflow_ind_dc、moneyflow_ind_ths），以便分析主力资金动向、沪深港通资金和行业资金流向。

#### 验收标准

1. WHEN 用户选择 moneyflow 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器和可选的股票代码输入框
2. WHEN 导入 moneyflow 数据时，THE Import_Task SHALL 将个股资金流向数据写入 money_flow 表（PostgreSQL），包含 ts_code、trade_date、主力净流入、大单净流入等字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. WHEN 用户选择 moneyflow_hsgt 接口并设置日期范围，THE Import_Task SHALL 将沪深港通资金流向数据写入 moneyflow_hsgt 表（PostgreSQL），包含 trade_date、ggt_ss（港股通上海）、ggt_sz（港股通深圳）、hgt（沪股通）、sgt（深股通）、north_money（北向资金）、south_money（南向资金）字段，使用 ON CONFLICT (trade_date) 策略去重
4. WHEN 用户选择 moneyflow_ind_dc 接口并设置日期范围，THE Import_Task SHALL 将东财行业资金流向数据写入 moneyflow_ind 表（PostgreSQL），包含 trade_date、industry_name、data_source（DC）、buy_amount、sell_amount、net_amount 字段
5. WHEN 用户选择 moneyflow_ind_ths 接口并设置日期范围，THE Import_Task SHALL 将同花顺行业资金流向数据写入 moneyflow_ind 表（PostgreSQL），data_source 设为 "THS"
6. WHEN 用户选择 moneyflow_mkt_dc 接口并设置日期范围，THE Import_Task SHALL 将大盘资金流向（东财）数据写入 moneyflow_mkt_dc 表（PostgreSQL），包含 trade_date、close、change、pct_change、net_mf_amount、net_mf_amount_rate、buy_elg_amount、sell_elg_amount、buy_lg_amount、sell_lg_amount、buy_md_amount、sell_md_amount、buy_sm_amount、sell_sm_amount 字段，使用 ON CONFLICT (trade_date) 策略去重
7. THE Import_Task SHALL 遵循 settings.rate_limit_money_flow（0.30 秒）频率限制

### 需求 10：打板专题数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 打板专题完整数据（limit_list_d、limit_step、stk_limit、hm_list、hm_detail、top_list、top_inst、ths_limit、dc_hot、ths_hot、ths_index、ths_member、dc_index、dc_member、kpl_list），以便全面分析涨跌停统计、连板天梯、龙虎榜、游资动向、热榜和概念板块。

#### 验收标准

1. WHEN 用户选择 limit_list_d 接口并设置日期范围，THE Import_Task SHALL 将每日涨跌停统计数据写入 limit_list 表（PostgreSQL），包含 ts_code、trade_date、industry、close、pct_chg、amount、limit_amount、float_mv、total_mv、turnover_ratio、fd_amount、first_time、last_time、open_times、up_stat、limit_times、limit（U涨停/D跌停）字段，使用 ON CONFLICT (ts_code, trade_date, limit) 策略去重
2. WHEN 用户选择 limit_step 接口并设置日期范围，THE Import_Task SHALL 将涨停股票连板天梯数据写入 limit_step 表（PostgreSQL），包含 ts_code、trade_date、name、close、pct_chg、step（连板天数）、limit_order（封板顺序）、amount、turnover_ratio、fd_amount、first_time、last_time、open_times 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. WHEN 用户选择 stk_limit 接口并设置日期范围，THE Import_Task SHALL 将每日涨跌停价格数据写入 stk_limit 表（复用需求 7 中的表），使用 ON CONFLICT (ts_code, trade_date) 策略去重
4. WHEN 用户选择 hm_list 接口，THE Import_Task SHALL 将游资名录数据写入 hm_list 表（PostgreSQL），包含 hm_name、hm_code、market、desc 字段
5. WHEN 用户选择 hm_detail 接口并设置日期范围，THE Import_Task SHALL 将游资每日明细数据写入 hm_detail 表（PostgreSQL），包含 trade_date、ts_code、hm_name、buy_amount、sell_amount、net_amount 字段
6. WHEN 用户选择 top_list 接口并设置日期范围，THE Import_Task SHALL 将龙虎榜每日明细数据写入 top_list 表（PostgreSQL），包含 trade_date、ts_code、name、close、pct_change、turnover_rate、amount、l_sell、l_buy、l_amount、net_amount、net_rate、amount_rate、float_values、reason 字段，使用 ON CONFLICT (trade_date, ts_code, reason) 策略去重
7. WHEN 用户选择 top_inst 接口并设置日期范围，THE Import_Task SHALL 将龙虎榜机构交易明细数据写入 top_inst 表（PostgreSQL），包含 trade_date、ts_code、exalter（营业部名称）、buy、buy_rate、sell、sell_rate、net_buy 字段，使用 ON CONFLICT (trade_date, ts_code, exalter) 策略去重
8. WHEN 用户选择 ths_limit 接口并设置日期范围，THE Import_Task SHALL 将同花顺涨跌停榜单数据写入 ths_limit 表（PostgreSQL），包含 trade_date、ts_code、name、close、pct_chg、fd_amount、first_time、last_time、open_times、limit（U/D）字段，使用 ON CONFLICT (ts_code, trade_date, limit) 策略去重
9. WHEN 用户选择 dc_hot 接口并设置日期范围，THE Import_Task SHALL 将东方财富App热榜数据写入 dc_hot 表（PostgreSQL），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
10. WHEN 用户选择 ths_hot 接口并设置日期范围，THE Import_Task SHALL 将同花顺App热榜数据写入 ths_hot 表（PostgreSQL），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
11. WHEN 用户选择 ths_index 接口，THE Import_Task SHALL 将同花顺行业概念板块列表写入现有 sector_info 表（PostgreSQL），将 ts_code 映射为 sector_code、type 映射为 sector_type（CONCEPT/INDUSTRY）、data_source 设为 "THS"，使用 ON CONFLICT (sector_code, data_source) 策略更新
12. WHEN 用户选择 ths_member 接口并指定板块代码，THE Import_Task SHALL 将同花顺行业概念成分股写入现有 sector_constituent 表（PostgreSQL），将 con_code 映射为 symbol、con_name 映射为 stock_name、data_source 设为 "THS"
13. WHEN 用户选择 dc_index 接口，THE Import_Task SHALL 将东方财富概念板块列表写入现有 sector_info 表（PostgreSQL），将 ts_code 映射为 sector_code、data_source 设为 "DC"，使用 ON CONFLICT (sector_code, data_source) 策略更新
14. WHEN 用户选择 dc_member 接口并指定板块代码，THE Import_Task SHALL 将东方财富概念成分股写入现有 sector_constituent 表（PostgreSQL），将 con_code 映射为 symbol、con_name 映射为 stock_name、data_source 设为 "DC"
15. WHEN 用户选择 kpl_list 接口并设置日期范围，THE Import_Task SHALL 将开盘啦榜单数据写入 kpl_list 表（PostgreSQL），包含 trade_date、ts_code、name、close、pct_chg、tag 字段
16. THE Import_Task SHALL 遵循 settings.rate_limit_fundamentals（0.40 秒）频率限制

### 需求 11：指数基本信息导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 指数基本信息（index_basic），以便获取指数元数据。

#### 验收标准

1. WHEN 用户选择 index_basic 接口并指定市场（SSE/SZSE/CSI/全部），THE TushareImportView SHALL 提供市场下拉选择器
2. WHEN 用户点击"开始导入"，THE Import_Service SHALL 调用 Tushare_Adapter 的 `_call_api("index_basic")` 获取指数列表
3. WHEN index_basic 数据获取成功，THE Import_Task SHALL 将指数信息写入 index_info 表（PostgreSQL），包含 ts_code、name、market、publisher、category、list_date 字段
4. THE Import_Task SHALL 使用 ON CONFLICT (ts_code) 策略更新已有记录
5. IF Tushare API 返回错误码，THEN THE Import_Task SHALL 记录错误详情并将任务状态标记为失败

### 需求 12：指数低频行情数据导入（日线/周线/月线）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 指数低频行情数据（index_daily、index_weekly、index_monthly），低频与中频分开导入，以便分别管理不同频率的指数数据。

#### 验收标准

1. THE TushareImportView SHALL 在"指数行情数据"子分类下将接口分为"低频行情（日线/周线/月线）"和"中频行情（分钟级）"两个独立分组
2. WHEN 用户选择指数低频行情接口并设置日期范围和指数代码，THE TushareImportView SHALL 提供起止日期选择器和指数代码输入框
3. WHEN 导入 index_daily/index_weekly/index_monthly 数据时，THE Import_Task SHALL 将指数行情写入 TimescaleDB 的 kline 超表，symbol 字段存储指数 ts_code（如 000001.SH），freq 字段分别对应 "1d"/"1w"/"1M"
4. THE Import_Task SHALL 使用 ON CONFLICT (time, symbol, freq, adj_type) 策略去重
5. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔

### 需求 12a：指数中频行情数据导入（分钟级）

**用户故事：** 作为量化交易员，我希望按日期范围导入 Tushare 指数分钟级行情数据（index_1min_realtime、index_min），中频与低频分开导入，以便独立控制分钟级指数数据的导入。

#### 验收标准

1. WHEN 用户选择指数中频行情接口并设置日期范围和指数代码，THE TushareImportView SHALL 提供起止日期选择器、指数代码输入框和频率选择器（1min/5min/15min/30min/60min）
2. WHEN 导入 index_1min_realtime 数据时，THE Import_Task SHALL 将指数实时分钟行情写入 kline 超表，freq 字段设为 "1m"
3. WHEN 导入 index_min 数据时，THE Import_Task SHALL 将指数历史分钟行情写入 kline 超表，freq 字段根据用户选择的频率设置（"1m"/"5m"/"15m"/"30m"/"60m"）
4. THE Import_Task SHALL 使用 ON CONFLICT (time, symbol, freq, adj_type) 策略去重
5. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔
6. THE TushareImportView SHALL 在中频行情分组中提示用户"分钟级数据量较大，建议按单只指数或短日期范围分批导入"

### 需求 13：指数成分和权重导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 指数成分和权重数据（index_weight），以便了解指数构成。

#### 验收标准

1. WHEN 用户选择 index_weight 接口并指定指数代码和日期，THE TushareImportView SHALL 提供指数代码输入框和日期选择器
2. WHEN 导入 index_weight 数据时，THE Import_Task SHALL 将成分权重数据写入 index_weight 表（PostgreSQL），包含 index_code、con_code、trade_date、weight 字段
3. THE Import_Task SHALL 使用 ON CONFLICT (index_code, con_code, trade_date) 策略去重
4. IF 指定日期无成分数据，THEN THE Import_Task SHALL 记录警告日志并返回空结果

### 需求 14：申万行业数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 申万行业分类和行情数据（index_classify、sw_daily），以便进行行业分析。

#### 验收标准

1. WHEN 用户选择 index_classify 接口，THE Import_Service SHALL 调用 Tushare_Adapter 获取申万行业分类数据
2. WHEN index_classify 数据获取成功，THE Import_Task SHALL 将行业分类写入 sector_info 表，sector_type 设为 "INDUSTRY"，data_source 设为 "TI"
3. WHEN 用户选择 sw_daily 接口并设置日期范围，THE Import_Task SHALL 将申万行业指数日行情写入 sector_kline 表，data_source 设为 "TI"
4. THE Import_Task SHALL 使用 ON CONFLICT 策略去重

### 需求 15：中信行业数据导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 中信行业成分和行情数据（ci_daily），以便进行多维度行业对比。

#### 验收标准

1. WHEN 用户选择中信行业接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器
2. WHEN 导入中信行业行情数据时，THE Import_Task SHALL 将数据写入 sector_kline 表，data_source 设为 "CI"
3. THE Import_Task SHALL 使用 ON CONFLICT 策略去重

### 需求 16：大盘指数每日指标导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 大盘指数每日指标（index_dailybasic），以便获取指数估值和成交数据。

#### 验收标准

1. WHEN 用户选择 index_dailybasic 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器
2. WHEN 导入 index_dailybasic 数据时，THE Import_Task SHALL 将指数每日指标写入 index_dailybasic 表（PostgreSQL），包含 ts_code、trade_date、pe、pb、turnover_rate、total_mv 字段
3. THE Import_Task SHALL 使用 ON CONFLICT (ts_code, trade_date) 策略去重

### 需求 17：指数技术面因子导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 指数技术面因子数据（index_tech，专业版接口），以便获取指数技术分析指标。

#### 验收标准

1. WHEN 用户选择 index_tech 接口并设置日期范围和指数代码，THE TushareImportView SHALL 提供起止日期选择器和指数代码输入框
2. WHEN 导入 index_tech 数据时，THE Import_Task SHALL 将指数技术面因子数据写入 index_tech 表（PostgreSQL），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、boll_upper、boll_mid、boll_lower 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔

### 需求 18：沪深市场每日交易统计导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 沪深市场每日交易统计数据（daily_info、sz_daily_info），以便了解市场整体交易情况。

#### 验收标准

1. WHEN 用户选择 daily_info 接口并设置日期范围，THE Import_Task SHALL 将沪深市场每日交易统计数据写入 market_daily_info 表（PostgreSQL），包含 trade_date、exchange、ts_code、ts_name、com_count、total_share、float_share、total_mv、float_mv、amount、vol、trans_count 字段，使用 ON CONFLICT (trade_date, exchange, ts_code) 策略去重
2. WHEN 用户选择 sz_daily_info 接口并设置日期范围，THE Import_Task SHALL 将深圳市场每日交易情况数据写入 sz_daily_info 表（PostgreSQL），包含 trade_date、ts_code、count、amount、vol、total_share、total_mv、float_share、float_mv 字段，使用 ON CONFLICT (trade_date, ts_code) 策略去重
3. THE Import_Task SHALL 遵循 settings.rate_limit_kline（0.18 秒）频率限制

### 需求 19：国际主要指数导入

**用户故事：** 作为量化交易员，我希望导入 Tushare 国际主要指数数据（index_global），以便跟踪全球市场走势。

#### 验收标准

1. WHEN 用户选择 index_global 接口并设置日期范围，THE TushareImportView SHALL 提供起止日期选择器和可选的指数代码输入框
2. WHEN 导入 index_global 数据时，THE Import_Task SHALL 将国际指数行情数据写入 index_global 表（PostgreSQL），包含 ts_code、trade_date、open、close、high、low、pre_close、change、pct_chg、vol、amount 字段，使用 ON CONFLICT (ts_code, trade_date) 策略去重
3. THE Import_Task SHALL 按 settings.rate_limit_kline（0.18 秒）频率限制控制 API 调用间隔

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

### 需求 22a：三级权限 Token 配置

**用户故事：** 作为量化交易员，我希望系统支持三种不同积分权限级别的 Tushare API Token 配置，以便根据接口权限要求自动选择对应的 Token 进行数据导入。

#### 验收标准

1. THE Settings SHALL 新增三个 Token 配置项：`tushare_token_basic`（6000 积分及以下权限接口）、`tushare_token_advanced`（6000 积分以上权限接口）、`tushare_token_special`（需单独开通权限的接口），原有 `tushare_api_token` 作为默认 fallback
2. THE API_Registry SHALL 为每个 Tushare 接口标注权限级别（basic/advanced/special），对应所需的积分等级
3. WHEN Import_Service 调用 Tushare API 时，THE Import_Service SHALL 根据接口的权限级别自动选择对应的 Token：basic 级别使用 `tushare_token_basic`，advanced 级别使用 `tushare_token_advanced`，special 级别使用 `tushare_token_special`
4. IF 对应级别的 Token 未配置（为空），THEN THE Import_Service SHALL 回退使用 `tushare_api_token` 作为默认 Token
5. THE TushareImportView SHALL 在页面顶部的连接状态区域显示三个 Token 的配置状态（已配置/未配置），帮助用户了解哪些权限级别可用
6. THE TushareImportView SHALL 在每个 API 接口旁显示其所需的权限级别标签（基础/高级/特殊），IF 对应 Token 未配置 THEN 该接口的导入按钮显示为禁用状态并提示"需配置对应权限 Token"
7. THE Settings SHALL 通过 .env 文件配置三个 Token：`TUSHARE_TOKEN_BASIC`、`TUSHARE_TOKEN_ADVANCED`、`TUSHARE_TOKEN_SPECIAL`

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
12. THE System SHALL 创建 margin_target 表（PostgreSQL/PGBase），包含 ts_code、mg_type、is_new 字段
13. THE System SHALL 创建 block_trade 表（PostgreSQL/PGBase），包含 ts_code、trade_date、price、vol、amount、buyer、seller 字段，使用 (ts_code, trade_date, buyer, seller) 复合唯一约束
14. THE System SHALL 创建 top_holders 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、holder_name、hold_amount、hold_ratio、holder_type 字段，使用 (ts_code, end_date, holder_name, holder_type) 复合唯一约束
15. THE System SHALL 创建 limit_list 表（PostgreSQL/PGBase），包含 ts_code、trade_date、industry、close、pct_chg、amount、limit_amount、float_mv、total_mv、turnover_ratio、fd_amount、first_time、last_time、open_times、up_stat、limit_times、limit 字段，使用 (ts_code, trade_date, limit) 复合唯一约束
16. THE System SHALL 创建 index_global 表（PostgreSQL/PGBase），包含 ts_code、trade_date、open、close、high、low、pre_close、change、pct_chg、vol、amount 字段，使用 (ts_code, trade_date) 复合唯一约束
17. THE System SHALL 创建 index_tech 表（PostgreSQL/PGBase），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、boll_upper、boll_mid、boll_lower 字段，使用 (ts_code, trade_date) 复合唯一约束
18. THE System SHALL 创建 stock_company 表（PostgreSQL/PGBase），包含 ts_code（主键）、chairman、manager、secretary、reg_capital、setup_date、province、city、website 字段
19. THE System SHALL 创建 stock_namechange 表（PostgreSQL/PGBase），包含 ts_code、name、start_date、end_date、change_reason 字段
20. THE System SHALL 创建 hs_constituent 表（PostgreSQL/PGBase），包含 ts_code、hs_type、in_date、out_date、is_new 字段
21. THE System SHALL 创建 stk_rewards 表（PostgreSQL/PGBase），包含 ts_code、ann_date、name、title、reward、hold_vol 字段
22. THE System SHALL 创建 stk_managers 表（PostgreSQL/PGBase），包含 ts_code、ann_date、name、gender、lev、title、edu、national、birthday、begin_date、end_date 字段
23. THE System SHALL 创建 stk_holdernumber 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、holder_num、holder_num_change 字段
24. THE System SHALL 创建 stk_holdertrade 表（PostgreSQL/PGBase），包含 ts_code、ann_date、holder_name、change_vol、change_ratio、after_vol、after_ratio、in_de 字段
25. THE System SHALL 创建 stk_account 表（PostgreSQL/PGBase），包含 date、weekly_new、total、weekly_hold 字段
26. THE System SHALL 创建 stk_limit 表（PostgreSQL/PGBase），包含 ts_code、trade_date、up_limit、down_limit 字段，使用 (ts_code, trade_date) 复合唯一约束
27. THE System SHALL 创建 slb_len 表（PostgreSQL/PGBase），包含 ts_code、trade_date、len_rate、len_amt 字段
28. THE System SHALL 创建 slb_sec 表（PostgreSQL/PGBase），包含 ts_code、trade_date、sec_amt、sec_vol 字段
29. THE System SHALL 创建 moneyflow_hsgt 表（PostgreSQL/PGBase），包含 trade_date、ggt_ss、ggt_sz、hgt、sgt、north_money、south_money 字段，使用 (trade_date) 唯一约束
30. THE System SHALL 创建 moneyflow_ind 表（PostgreSQL/PGBase），包含 trade_date、industry_name、data_source、buy_amount、sell_amount、net_amount 字段
31. THE System SHALL 创建 hm_list 表（PostgreSQL/PGBase），包含 hm_name、hm_code、market、desc 字段
32. THE System SHALL 创建 hm_detail 表（PostgreSQL/PGBase），包含 trade_date、ts_code、hm_name、buy_amount、sell_amount、net_amount 字段
33. THE System SHALL 创建 market_daily_info 表（PostgreSQL/PGBase），包含 trade_date、exchange、ts_code、ts_name、com_count、total_share、float_share、total_mv、float_mv、amount、vol、trans_count 字段，使用 (trade_date, exchange, ts_code) 复合唯一约束
34. THE System SHALL 创建 sz_daily_info 表（PostgreSQL/PGBase），包含 trade_date、ts_code、count、amount、vol、total_share、total_mv、float_share、float_mv 字段，使用 (trade_date, ts_code) 复合唯一约束
35. THE System SHALL 创建 top_list 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、pct_change、turnover_rate、amount、l_sell、l_buy、l_amount、net_amount、net_rate、amount_rate、float_values、reason 字段，使用 (trade_date, ts_code, reason) 复合唯一约束
36. THE System SHALL 创建 top_inst 表（PostgreSQL/PGBase），包含 trade_date、ts_code、exalter、buy、buy_rate、sell、sell_rate、net_buy 字段，使用 (trade_date, ts_code, exalter) 复合唯一约束
37. THE System SHALL 创建 new_share 表（PostgreSQL/PGBase），包含 ts_code（主键）、sub_code、name、ipo_date、issue_date、amount、market_amount、price、pe、limit_amount、funds、ballot 字段
38. THE System SHALL 创建 stock_st 表（PostgreSQL/PGBase），包含 ts_code、name、is_st、st_date、st_type 字段
39. THE System SHALL 创建 daily_share 表（PostgreSQL/PGBase），包含 ts_code、trade_date、total_share、float_share、free_share、total_mv、float_mv 字段，使用 (ts_code, trade_date) 复合唯一约束
40. THE System SHALL 创建 forecast 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、type、p_change_min、p_change_max、net_profit_min、net_profit_max、summary 字段，使用 (ts_code, end_date) 复合唯一约束
41. THE System SHALL 创建 express 表（PostgreSQL/PGBase），包含 ts_code、ann_date、end_date、revenue、operate_profit、total_profit、n_income、total_assets、total_hldr_eqy_exc_min_int、diluted_eps、yoy_net_profit、bps、perf_summary 字段，使用 (ts_code, end_date) 复合唯一约束
42. THE System SHALL 创建 stk_factor 表（PostgreSQL/PGBase），包含 ts_code、trade_date、close、macd_dif、macd_dea、macd、kdj_k、kdj_d、kdj_j、rsi_6、rsi_12、rsi_24、boll_upper、boll_mid、boll_lower、cci 字段，使用 (ts_code, trade_date) 复合唯一约束
43. THE System SHALL 创建 limit_step 表（PostgreSQL/PGBase），包含 ts_code、trade_date、name、close、pct_chg、step、limit_order、amount、turnover_ratio、fd_amount、first_time、last_time、open_times 字段，使用 (ts_code, trade_date) 复合唯一约束
44. THE System SHALL 创建 ths_limit 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、pct_chg、fd_amount、first_time、last_time、open_times、limit 字段，使用 (ts_code, trade_date, limit) 复合唯一约束
45. THE System SHALL 创建 dc_hot 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
46. THE System SHALL 创建 ths_hot 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、rank、pct_chg、hot_value 字段
47. THE System SHALL 创建 kpl_list 表（PostgreSQL/PGBase），包含 trade_date、ts_code、name、close、pct_chg、tag 字段
48. THE System SHALL 创建 moneyflow_mkt_dc 表（PostgreSQL/PGBase），包含 trade_date、close、change、pct_change、net_mf_amount、net_mf_amount_rate、buy_elg_amount、sell_elg_amount、buy_lg_amount、sell_lg_amount、buy_md_amount、sell_md_amount、buy_sm_amount、sell_sm_amount 字段，使用 (trade_date) 唯一约束
49. THE System SHALL 在现有 DataSource 枚举（`app/models/sector.py`）中新增 `CI = "CI"`（中信行业）和 `THS = "THS"`（同花顺概念/行业板块）两个枚举值，原有 `TI = "TI"` 保留用于申万行业数据
50. THE System SHALL 将 ths_index/dc_index 板块数据复用现有 sector_info 表（通过 data_source="THS"/"DC" 区分），将 ths_member/dc_member 成分股数据复用现有 sector_constituent 表（通过 data_source="THS"/"DC" 区分），不新建独立表
51. THE System SHALL 通过 Alembic 迁移脚本创建上述所有新表

### 需求 26：ts_code 与 symbol 格式转换

**用户故事：** 作为量化交易员，我希望系统自动处理 Tushare ts_code 格式（如 000001.SZ）与系统内部 symbol 格式（如 000001）之间的转换，以便数据一致性。

#### 验收标准

1. WHEN 导入股票相关数据时，THE Import_Task SHALL 将 Tushare 返回的 ts_code（如 600000.SH）转换为纯 6 位 symbol（如 600000）后写入 stock_info 和 kline 表
2. WHEN 导入指数相关数据时，THE Import_Task SHALL 保留完整的 ts_code 格式（如 000001.SH）作为指数标识符写入 index_info 和 kline 表
3. THE Import_Service SHALL 在调用 Tushare API 时自动将用户输入的纯数字代码补全为 ts_code 格式（6 开头补 .SH，0/3 开头补 .SZ）
4. THE Import_Service SHALL 在 API_Registry 中为每个接口标注代码格式要求（stock_symbol/index_code/none）