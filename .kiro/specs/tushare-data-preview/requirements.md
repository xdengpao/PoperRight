# Requirements Document

## Introduction

本功能在现有 Tushare 数据导入页面旁新增一个平级的「Tushare 数据预览」Tab 页，用于查看已从 Tushare 导入到数据库中的数据，帮助量化交易员验证数据是否正确导入。预览支持表格与图表结合展示，支持按导入时间、数据自带时间进行查询，并提供一键增量数据查询功能。数据类型分类与 Tushare 数据导入的分类保持一致。该功能完全独立，不影响现有 Tushare 数据导入功能。

## Glossary

- **Preview_Tab**: Tushare 数据预览 Tab 页，与「Tushare 数据导入」Tab 平级的独立页面组件
- **Data_Preview_Service**: 后端数据预览服务层，负责从数据库查询已导入的 Tushare 数据并返回给前端
- **Data_Preview_API**: 后端数据预览 REST API 端点，位于 `/api/v1/data/tushare/preview` 路径下
- **Import_Log**: TushareImportLog 表中的导入日志记录，包含 api_name、params_json、status、record_count、started_at、finished_at 等字段
- **Category_Selector**: 数据类型分类选择器，按 stock_data（股票数据）和 index_data（指数数据）两大类及其子分类组织
- **Time_Filter**: 时间筛选组件，支持按导入时间（Import_Log.started_at/finished_at）和数据自带时间字段（如 trade_date、ann_date）进行过滤
- **Incremental_Query**: 增量数据查询，指查询自上次成功导入以来新增的数据记录
- **Chart_View**: 基于 ECharts 的图表展示组件，用于可视化时间序列类数据（如 K 线、资金流向趋势）
- **Table_View**: 数据表格展示组件，用于以行列形式展示查询结果
- **API_Registry**: Tushare API 接口注册表（tushare_registry.py），定义了 120+ 个接口的元数据，包括 api_name、category、subcategory、target_table 等

## Requirements

### Requirement 1: Tab 页路由与导航

**User Story:** 作为量化交易员，我需要在导航中看到与「Tushare 数据导入」平级的「Tushare 数据预览」Tab，以便快速切换到数据预览功能。

#### Acceptance Criteria

1. THE Preview_Tab SHALL 在 vue-router 中注册为独立路由 `data/online/tushare-preview`，与 `data/online/tushare` 路由平级
2. WHEN 用户访问 Tushare 数据导入页面或 Tushare 数据预览页面时，THE Preview_Tab SHALL 在页面顶部显示「Tushare 数据导入」和「Tushare 数据预览」两个可点击的 Tab 标签
3. WHEN 用户点击「Tushare 数据预览」Tab 标签时，THE Preview_Tab SHALL 导航到数据预览页面并高亮当前 Tab
4. WHEN 用户点击「Tushare 数据导入」Tab 标签时，THE Preview_Tab SHALL 导航回数据导入页面并高亮当前 Tab
5. THE Preview_Tab SHALL 使用独立的 Vue 组件（TusharePreviewView.vue），不修改 TushareImportView.vue 的业务逻辑

### Requirement 2: 数据类型分类选择

**User Story:** 作为量化交易员，我需要按照与导入页面一致的数据类型分类来选择要预览的数据，以便快速定位到目标数据。

#### Acceptance Criteria

1. THE Category_Selector SHALL 从 API_Registry 获取分类信息，展示与 Tushare 数据导入页面一致的两级分类结构（大类 → 子分类 → 接口列表）
2. THE Category_Selector SHALL 将大类分为「📈 股票数据」（stock_data）和「📊 指数数据」（index_data）两组
3. WHEN 用户选择某个子分类时，THE Category_Selector SHALL 展示该子分类下所有已注册的 API 接口供用户选择
4. WHEN 用户选择某个具体 API 接口时，THE Data_Preview_Service SHALL 查询该接口对应的 target_table 中的数据
5. THE Category_Selector SHALL 在每个子分类旁显示该子分类下的接口数量

### Requirement 3: 数据表格预览

**User Story:** 作为量化交易员，我需要以表格形式查看已导入的数据，以便逐行检查数据的正确性。

#### Acceptance Criteria

1. WHEN 用户选择某个 API 接口并执行查询后，THE Table_View SHALL 以分页表格形式展示该接口对应数据表中的记录
2. THE Table_View SHALL 根据 API_Registry 中的 field_mappings 动态生成表头列名
3. THE Table_View SHALL 支持分页，每页默认显示 50 条记录，用户可切换为 20、50、100 条
4. THE Table_View SHALL 在表格上方显示当前查询的总记录数
5. IF 查询结果为空，THEN THE Table_View SHALL 显示「暂无数据」提示信息

### Requirement 4: 数据图表预览

**User Story:** 作为量化交易员，我需要以图表形式直观查看时间序列数据的趋势，以便快速判断数据是否合理。

#### Acceptance Criteria

1. WHEN 查询的数据包含时间字段（如 trade_date）和数值字段（如 close、volume、amount）时，THE Chart_View SHALL 在表格上方展示对应的 ECharts 图表
2. WHEN 查询的数据属于行情类接口（如 daily、weekly、monthly、stk_mins）时，THE Chart_View SHALL 展示 K 线图（包含 open、high、low、close 四个价格字段）
3. WHEN 查询的数据属于资金流向类接口时，THE Chart_View SHALL 展示折线图或柱状图展示资金流向趋势
4. WHEN 查询的数据不包含可绘图的时间序列字段时，THE Chart_View SHALL 隐藏图表区域，仅展示表格
5. THE Chart_View SHALL 支持用户通过切换按钮在「仅表格」「仅图表」「图表+表格」三种展示模式间切换

### Requirement 5: 按导入时间查询

**User Story:** 作为量化交易员，我需要按照数据的导入时间来筛选数据，以便查看某次导入操作的具体结果。

#### Acceptance Criteria

1. THE Time_Filter SHALL 提供「导入时间范围」筛选器，允许用户选择 Import_Log 的 started_at 起止时间
2. WHEN 用户设置导入时间范围后，THE Data_Preview_Service SHALL 先查询 Import_Log 中匹配的导入记录，再根据这些记录关联查询对应数据表中的数据
3. THE Time_Filter SHALL 提供快捷时间选项：「今天」「最近 3 天」「最近 7 天」「最近 30 天」「自定义范围」
4. WHEN 用户选择某条具体的导入记录时，THE Data_Preview_Service SHALL 仅展示该次导入操作写入的数据

### Requirement 6: 按数据自带时间查询

**User Story:** 作为量化交易员，我需要按照数据本身的时间字段（如交易日期）来筛选数据，以便查看特定时间段的数据。

#### Acceptance Criteria

1. THE Time_Filter SHALL 提供「数据时间范围」筛选器，允许用户按数据表自带的时间字段（如 trade_date、ann_date、cal_date）进行过滤
2. WHEN 用户设置数据时间范围后，THE Data_Preview_API SHALL 在查询对应数据表时添加时间字段的 WHERE 条件
3. THE Data_Preview_Service SHALL 根据 API_Registry 中的 target_table 自动识别该表的主要时间字段名称
4. WHEN 数据表不包含时间字段时，THE Time_Filter SHALL 禁用「数据时间范围」筛选器并显示提示

### Requirement 7: 一键增量数据查询

**User Story:** 作为量化交易员，我需要一键查看自上次检查以来新导入的增量数据，以便快速验证最新一批导入是否成功。

#### Acceptance Criteria

1. THE Preview_Tab SHALL 提供「查看增量数据」按钮，位于查询条件区域的显著位置
2. WHEN 用户点击「查看增量数据」按钮时，THE Data_Preview_Service SHALL 查询所选 API 接口最近一次成功导入（Import_Log.status = 'completed'）的记录
3. WHEN 获取到最近一次成功导入记录后，THE Data_Preview_Service SHALL 从该导入记录的 params_json 中提取导入参数（如 start_date/end_date、ts_code 等），并根据这些参数重建查询条件来查询目标数据表中对应的数据
4. THE Table_View SHALL 在增量查询模式下，在表格上方显示本次增量的导入时间、记录数、导入状态和导入参数摘要
5. IF 所选 API 接口没有成功的导入记录，THEN THE Preview_Tab SHALL 显示「该接口暂无成功导入记录」提示

### Requirement 8: 后端数据预览 API

**User Story:** 作为量化交易员，我需要后端提供高效的数据预览查询接口，以便前端能快速加载和展示数据。

#### Acceptance Criteria

1. THE Data_Preview_API SHALL 提供 `GET /api/v1/data/tushare/preview/{api_name}` 端点，接受 api_name 路径参数和查询参数（page、page_size、import_time_start、import_time_end、data_time_start、data_time_end、incremental）
2. THE Data_Preview_API SHALL 提供 `GET /api/v1/data/tushare/preview/{api_name}/stats` 端点，返回指定接口数据表的统计信息（总记录数、最早/最晚数据时间、最近导入时间）
3. THE Data_Preview_API SHALL 根据 API_Registry 中的 target_table 和 storage_engine 动态路由到正确的数据库（PostgreSQL 或 TimescaleDB）进行查询
4. THE Data_Preview_API SHALL 对查询结果进行分页，默认每页 50 条，最大 100 条
5. IF 请求的 api_name 在 API_Registry 中不存在，THEN THE Data_Preview_API SHALL 返回 HTTP 404 错误和描述性错误信息
6. THE Data_Preview_API SHALL 遵循现有架构分层：api/ → services/ → models/，不直接在 API 层操作数据库

### Requirement 9: 功能独立性

**User Story:** 作为量化交易员，我需要数据预览功能完全独立于数据导入功能，以确保预览操作不会影响正在进行的导入任务。

#### Acceptance Criteria

1. THE Preview_Tab SHALL 使用独立的 Vue 组件文件（TusharePreviewView.vue），不修改现有 TushareImportView.vue 文件的业务逻辑代码（仅允许在其 template 中添加共享的 Tab 导航组件 TushareTabNav）
2. THE Data_Preview_Service SHALL 作为独立的服务模块（tushare_preview_service.py），不修改现有 TushareImportService 的代码
3. THE Data_Preview_API SHALL 使用独立的路由模块，不修改现有 tushare.py 中的导入相关端点
4. THE Data_Preview_Service SHALL 使用只读数据库查询（SELECT），不执行任何写入操作
5. THE Preview_Tab SHALL 使用独立的 Pinia store（如需要），不修改现有导入相关的 store

### Requirement 10: 导入记录列表展示

**User Story:** 作为量化交易员，我需要在预览页面看到所选接口的导入历史记录列表，以便选择具体某次导入的数据进行查看。

#### Acceptance Criteria

1. WHEN 用户选择某个 API 接口后，THE Preview_Tab SHALL 展示该接口的最近导入记录列表（从 Import_Log 查询，按 started_at 降序排列）
2. THE Preview_Tab SHALL 在导入记录列表中显示每条记录的导入时间、状态、记录数和参数信息
3. WHEN 用户点击某条导入记录时，THE Data_Preview_Service SHALL 查询并展示该次导入对应的数据
4. THE Preview_Tab SHALL 用颜色区分导入状态：成功（绿色）、失败（红色）、进行中（蓝色）、已停止（灰色）

### Requirement 11: 侧边栏菜单集成

**User Story:** 作为量化交易员，我需要在侧边栏菜单中看到 Tushare 数据预览的入口，以便从任意页面快速导航到预览功能。

#### Acceptance Criteria

1. THE Preview_Tab SHALL 在 MainLayout.vue 侧边栏的「在线数据」子菜单中新增「tushare预览」菜单项，位于现有「tushare」菜单项之后
2. WHEN 用户点击侧边栏的「tushare预览」菜单项时，THE Preview_Tab SHALL 导航到 `/data/online/tushare-preview` 路由
3. WHEN 用户处于 Tushare 数据预览页面时，THE Preview_Tab SHALL 高亮侧边栏中的「tushare预览」菜单项
