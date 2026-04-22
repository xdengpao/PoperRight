# Requirements Document

## Introduction

本功能是对现有「Tushare 数据预览」页面的多项增强，旨在帮助量化交易员更高效地验证已导入数据的质量，并提升图表可视化的实用性：

1. **数据完整性校验**：在数据预览页面新增「完整性校验」按钮，一键检测所选时间段内导入数据的完整性与连续性，对缺失的交易日（时序数据）或缺失的股票代码（非时序数据）给出明确报告。
2. **后端分页加载优化**：确认并优化现有后端分页机制，确保前端在翻页、切换每页条数时均通过后端分页加载，并在大数据量场景下优化 COUNT 查询性能。
3. **数值精度控制**：对数据表格中的数值型字段设定合理的显示精度，根据字段语义（价格、成交量、涨跌幅、换手率等）自动匹配适当的小数位数。
4. **图表类型扩展**：将图表推断规则从仅覆盖 K 线和资金流向扩展到覆盖所有 20 个 subcategory，为两融、特色数据、打板专题、指数指标等数据类型增加折线图/柱状图支持。
5. **图表数据独立加载**：图表数据不再依赖表格分页数据（默认 50 条），而是独立请求最近 N 条时序数据用于图表渲染，确保 K 线图等有足够的数据量。
6. **图表列选择器**：折线图/柱状图默认展示前 3 个最有代表性的数值列，并提供列选择器让用户自定义展示列，避免数值列过多导致图表混乱。

本增强功能完全基于现有 `tushare-data-preview` 功能构建，不修改原有功能的核心逻辑。

## Glossary

- **Integrity_Checker**: 数据完整性校验服务，负责检测指定时间段内导入数据的缺失情况
- **Completeness_Report**: 完整性校验结果报告，包含缺失的交易日列表（时序数据）或缺失的代码列表（非时序数据）
- **Trade_Calendar**: 交易日历表（trade_calendar），存储 A 股市场的交易日信息，用于判断某日是否为交易日
- **Time_Series_Table**: 时序数据表，包含时间字段（如 trade_date、time）的数据表，完整性校验基于交易日历比对
- **Non_Time_Series_Table**: 非时序数据表，不包含时间字段的数据表（如 stock_info、stock_company），完整性校验基于预期代码集合比对
- **Precision_Rule**: 数值精度规则，定义特定字段名模式对应的小数位数（如价格类字段保留 2 位，涨跌幅保留 2 位，换手率保留 2 位，成交量保留 0 位）
- **Chart_Type_Map**: 图表类型映射表，定义 subcategory/target_table 到推荐图表类型的完整映射
- **Chart_Data_Endpoint**: 独立的图表数据端点，返回用于图表渲染的时序数据（不受表格分页限制）
- **Column_Selector**: 图表列选择器，允许用户选择折线图/柱状图中要展示的数值列
- **Data_Preview_Service**: 现有后端数据预览服务（TusharePreviewService），本增强在其基础上扩展
- **Data_Preview_API**: 现有后端数据预览 REST API 端点
- **Preview_Tab**: 现有 Tushare 数据预览页面（TusharePreviewView.vue）
- **Table_View**: 现有数据表格组件（PreviewTable.vue）
- **Chart_View**: 现有图表组件（PreviewChart.vue）

## Requirements

### Requirement 1: 完整性校验按钮与交互

**User Story:** 作为量化交易员，我需要在数据预览页面的查询条件栏中看到一个「完整性校验」按钮，以便一键触发数据完整性检测。

#### Acceptance Criteria

1. THE Preview_Tab SHALL 在查询条件栏的「查询」按钮和「查看增量数据」按钮右侧显示一个「完整性校验」按钮
2. WHEN 用户未选择任何 API 接口时，THE Preview_Tab SHALL 禁用「完整性校验」按钮
3. WHEN 用户点击「完整性校验」按钮时，THE Preview_Tab SHALL 向后端发送校验请求，并在按钮上显示加载状态
4. WHEN 完整性校验请求返回结果后，THE Preview_Tab SHALL 在查询条件栏下方以独立区域展示 Completeness_Report
5. WHEN 校验结果显示数据完整时，THE Preview_Tab SHALL 显示绿色提示「数据完整，无缺失」
6. WHEN 校验结果显示数据存在缺失时，THE Preview_Tab SHALL 以红色高亮显示缺失摘要，并展示缺失详情列表

### Requirement 2: 时序数据完整性校验逻辑

**User Story:** 作为量化交易员，我需要系统基于交易日历检测时序数据在指定时间段内是否存在缺失的交易日，以便发现数据导入遗漏。

#### Acceptance Criteria

1. THE Integrity_Checker SHALL 提供 `POST /api/v1/data/tushare/preview/{api_name}/check-integrity` 端点，接受 data_time_start 和 data_time_end 参数
2. WHEN 目标数据表包含时间字段时，THE Integrity_Checker SHALL 从 Trade_Calendar 获取指定时间段内的所有交易日集合
3. THE Integrity_Checker SHALL 在查询 Trade_Calendar 时默认使用 SSE（上交所）日历，因为 SSE 和 SZSE 的交易日历一致
4. WHEN 获取到交易日集合后，THE Integrity_Checker SHALL 查询目标数据表在该时间段内实际存在的日期集合
5. THE Integrity_Checker SHALL 计算交易日集合与实际日期集合的差集，将差集中的日期作为缺失交易日输出
6. THE Integrity_Checker SHALL 在 Completeness_Report 中包含以下信息：校验的时间范围、预期交易日数量、实际数据日数量、缺失交易日列表
7. WHEN 用户未指定数据时间范围时，THE Integrity_Checker SHALL 使用目标数据表中最早和最晚数据时间作为默认校验范围
8. THE Integrity_Checker SHALL 在查询实际日期时应用与预览查询相同的作用域过滤条件（scope_filter），确保校验范围与预览数据一致

### Requirement 3: 非时序数据完整性校验逻辑

**User Story:** 作为量化交易员，我需要系统检测非时序数据表中是否存在缺失的股票代码或其他关键标识，以便发现数据导入遗漏。

#### Acceptance Criteria

1. WHEN 目标数据表不包含时间字段时，THE Integrity_Checker SHALL 从 stock_info 表获取当前全部 A 股代码集合作为预期集合
2. WHEN 目标数据表包含 ts_code 列时，THE Integrity_Checker SHALL 查询该表中实际存在的 ts_code 集合
3. THE Integrity_Checker SHALL 计算预期代码集合与实际代码集合的差集，将差集中的代码作为缺失代码输出
4. THE Integrity_Checker SHALL 在 Completeness_Report 中包含以下信息：预期代码数量、实际代码数量、缺失代码列表
5. THE Completeness_Report SHALL 在非时序校验结果中标注提示信息「预期集合基于全部 A 股代码，实际覆盖范围可能因接口特性而异」
6. IF 目标数据表既不包含时间字段也不包含 ts_code 列，THEN THE Integrity_Checker SHALL 返回提示信息「该数据表不支持完整性校验」

### Requirement 4: 完整性校验结果展示

**User Story:** 作为量化交易员，我需要清晰地查看完整性校验结果，包括缺失数据的具体详情，以便针对性地补充导入。

#### Acceptance Criteria

1. THE Completeness_Report SHALL 在预览页面的查询条件栏下方以可折叠卡片形式展示
2. THE Completeness_Report SHALL 显示校验摘要：校验类型（时序/非时序）、预期数量、实际数量、缺失数量、完整率百分比
3. WHEN 缺失数量大于 0 时，THE Completeness_Report SHALL 展示缺失详情列表，时序数据显示缺失日期列表，非时序数据显示缺失代码列表
4. WHEN 缺失列表超过 50 条时，THE Completeness_Report SHALL 默认折叠详情列表，仅显示前 50 条，并提供「展开全部」按钮
5. THE Completeness_Report SHALL 提供「关闭」按钮，允许用户隐藏校验结果

### Requirement 5: 后端分页加载确认与优化

**User Story:** 作为量化交易员，我需要在浏览大数据量的时序数据时，系统通过后端分页加载数据，避免一次性加载导致页面卡顿。

#### Acceptance Criteria

1. THE Data_Preview_API SHALL 在 `GET /api/v1/data/tushare/preview/{api_name}` 端点中使用 SQL LIMIT/OFFSET 进行服务端分页查询（确认现有实现）
2. WHEN 用户切换页码时，THE Preview_Tab SHALL 向后端发送包含新页码的查询请求，而非在前端对已加载数据进行切片（确认现有实现）
3. WHEN 用户切换每页条数时，THE Preview_Tab SHALL 重置页码为 1 并向后端发送新的分页查询请求（确认现有实现）
4. THE Data_Preview_API SHALL 在响应中返回 total（总记录数）、page（当前页码）、page_size（每页条数），供前端分页控件使用（确认现有实现）
5. THE Table_View SHALL 在分页切换时显示加载状态指示器，直到后端返回新一页数据
6. WHEN 目标数据表的总记录数超过 100 万条时，THE Data_Preview_Service SHALL 使用 PostgreSQL 的 `reltuples` 估算值替代精确 `COUNT(*)`，以避免全表扫描导致的查询延迟

### Requirement 6: 数值精度规则定义

**User Story:** 作为量化交易员，我需要数据表格中的数值型字段按照金融数据的惯例显示合适的精度，以便快速准确地阅读数据。

#### Acceptance Criteria

1. THE Table_View SHALL 对价格类字段（字段名包含 open、high、low、close、price、avg_price、amount 等）显示 2 位小数
2. THE Table_View SHALL 对涨跌幅类字段（字段名包含 pct_chg、change 等）显示 2 位小数
3. THE Table_View SHALL 对换手率类字段（字段名包含 turnover_rate 等）显示 2 位小数
4. THE Table_View SHALL 对成交量类字段（字段名包含 vol、volume 等）显示为整数（0 位小数）
5. THE Table_View SHALL 对市值类字段（字段名包含 total_mv、circ_mv、market_cap 等）显示 2 位小数
6. THE Table_View SHALL 对市盈率/市净率类字段（字段名包含 pe、pb、pe_ttm、ps、ps_ttm 等）显示 2 位小数
7. WHEN 数值字段不匹配任何已知精度规则时，THE Table_View SHALL 使用默认精度 4 位小数
8. THE Table_View SHALL 对整数值（无小数部分）直接显示为整数，不添加多余的小数位

### Requirement 7: 数值精度前端实现

**User Story:** 作为量化交易员，我需要精度规则在前端表格渲染时生效，确保所有数值型单元格按规则格式化显示。

#### Acceptance Criteria

1. THE Table_View SHALL 定义一个纯函数 `getFieldPrecision(fieldName: string): number`，根据字段名匹配精度规则并返回小数位数
2. THE Table_View SHALL 在渲染数值型单元格时调用 `getFieldPrecision` 获取精度，并使用 `toFixed()` 格式化显示
3. THE Table_View SHALL 对大数值（绝对值 >= 10000）同时使用千分位分隔符提升可读性
4. THE Table_View SHALL 将精度规则定义为独立的常量映射，便于后续维护和扩展

### Requirement 8: 完整性校验后端 API

**User Story:** 作为量化交易员，我需要后端提供高效的完整性校验接口，以便前端能快速获取校验结果。

#### Acceptance Criteria

1. THE Data_Preview_API SHALL 提供 `POST /api/v1/data/tushare/preview/{api_name}/check-integrity` 端点，接受 JSON body 包含 data_time_start 和 data_time_end 参数
2. THE Integrity_Checker SHALL 根据 API_Registry 中的 target_table 和 storage_engine 动态路由到正确的数据库进行校验查询
3. THE Integrity_Checker SHALL 使用只读 SELECT 查询，不执行任何写入操作
4. THE Integrity_Checker SHALL 返回 Completeness_Report 响应，包含 check_type（time_series 或 code_based 或 unsupported）、expected_count、actual_count、missing_count、completeness_rate、missing_items 列表、time_range（校验时间范围）
5. IF 请求的 api_name 在 API_Registry 中不存在，THEN THE Data_Preview_API SHALL 返回 HTTP 404 错误
6. THE Integrity_Checker SHALL 作为 TusharePreviewService 的新方法实现，复用现有的数据库路由和作用域过滤逻辑

### Requirement 9: 图表类型扩展

**User Story:** 作为量化交易员，我需要系统为更多类型的数据提供图表展示，而不仅限于 K 线和资金流向，以便直观验证各类数据的趋势和合理性。

#### Acceptance Criteria

1. THE Chart_View SHALL 支持以下 subcategory 到图表类型的完整映射：
   - K 线图（candlestick）：target_table 为 `kline` 或 `sector_kline` 的接口
   - 折线图（line）：「资金流向数据」「两融及转融通」「特色数据」「大盘指数每日指标」「指数技术面因子（专业版）」subcategory 的接口
   - 柱状图（bar）：「打板专题数据」「沪深市场每日交易统计」「深圳市场每日交易情况」subcategory 的接口
   - 折线图（line）：「指数行情数据（低频）」「指数行情数据（中频）」中 target_table 不是 kline/sector_kline 的接口（如 index_dailybasic）
2. THE Data_Preview_Service SHALL 更新 `_infer_chart_type_pure` 方法，使用完整的 Chart_Type_Map 替代现有的 3 条规则
3. WHEN subcategory 不在 Chart_Type_Map 中且数据表包含时间字段和数值字段时，THE Chart_View SHALL 默认使用折线图展示
4. WHEN 数据表不包含时间字段时，THE Chart_View SHALL 不展示图表（返回 chart_type = None）

### Requirement 10: 图表数据独立加载

**User Story:** 作为量化交易员，我需要图表展示足够多的数据点（如 250 个交易日的 K 线），而不是仅展示当前分页的 50 条数据，以便进行有意义的趋势分析。

#### Acceptance Criteria

1. THE Data_Preview_API SHALL 提供 `GET /api/v1/data/tushare/preview/{api_name}/chart-data` 端点，返回用于图表渲染的时序数据
2. THE chart-data 端点 SHALL 接受 `limit` 参数（默认 250，最大 500），返回按时间字段排序的最近 N 条数据
3. THE chart-data 端点 SHALL 接受与预览查询相同的筛选参数（data_time_start、data_time_end），并应用相同的作用域过滤条件
4. THE chart-data 端点 SHALL 返回 rows（数据行）、time_field（时间字段名）、chart_type（推荐图表类型）、columns（列信息）
5. WHEN 用户选择 API 接口并执行查询时，THE Preview_Tab SHALL 同时发送表格分页请求和图表数据请求，两者独立加载
6. THE Chart_View SHALL 使用 chart-data 端点返回的数据渲染图表，而非使用表格分页数据

### Requirement 11: 图表列选择器

**User Story:** 作为量化交易员，我需要在折线图/柱状图中选择要展示的数值列，避免数值列过多导致图表混乱不可读。

#### Acceptance Criteria

1. WHEN chart_type 为 line 或 bar 时，THE Chart_View SHALL 在图表上方显示一个列选择器，列出所有可用的数值列
2. THE Chart_View SHALL 默认选中前 3 个数值列进行展示
3. WHEN 用户通过列选择器勾选/取消勾选某列时，THE Chart_View SHALL 实时更新图表，仅展示被选中的列
4. THE Column_Selector SHALL 显示列的中文标签（来自 field_mappings），而非数据库列名
5. WHEN chart_type 为 candlestick 时，THE Chart_View SHALL 不显示列选择器（K 线图固定使用 OHLC 四列）

### Requirement 12: 功能独立性与兼容性

**User Story:** 作为量化交易员，我需要本次增强功能不影响现有数据预览功能的正常使用。

#### Acceptance Criteria

1. THE Integrity_Checker SHALL 作为 TusharePreviewService 的扩展方法实现，不修改现有 query_preview_data、query_stats、query_import_logs 方法的签名和行为
2. THE Data_Preview_API SHALL 在现有路由模块（tushare_preview.py）中新增校验端点和图表数据端点，不修改现有端点的请求/响应格式
3. THE Table_View SHALL 在 PreviewTable.vue 中扩展数值格式化逻辑，不修改现有的列渲染结构和分页交互
4. THE Preview_Tab SHALL 在 TusharePreviewView.vue 中新增校验按钮、结果展示区域和图表列选择器，不修改现有的查询、筛选、导入记录等交互逻辑
5. THE Chart_View SHALL 在 PreviewChart.vue 中扩展图表类型和列选择功能，保持现有 K 线图和折线图的渲染逻辑不变
