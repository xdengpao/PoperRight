# Implementation Plan: Tushare 数据预览 Tab

## Overview

本实现计划将 Tushare 数据预览功能分解为可增量执行的编码任务。采用自底向上的构建顺序：后端服务层（纯函数 + 完整 TIME_FIELD_MAP）→ 后端 API 路由 → 前端 Pinia Store → 前端共享 Tab 导航组件 → 前端预览页面（图表 + 表格）→ 路由/菜单集成 → 集成测试。每个任务构建在前一个任务之上，确保无孤立代码。本功能不新增 ORM 模型，完全复用现有模型和表结构。

## Tasks

- [x] 1. 后端预览服务层核心实现
  - [x] 1.1 创建 TusharePreviewService 核心框架与纯函数
    - 新建 `app/services/data_engine/tushare_preview_service.py`
    - 定义完整的 `TIME_FIELD_MAP` 字典（覆盖所有 70+ 个 target_table），以及 `_TIME_FIELD_PRIORITY` 自动推断兜底列表
    - 定义 `KLINE_TABLES = {"kline", "sector_kline"}` 和 `MONEYFLOW_SUBCATEGORY = "资金流向数据"` 常量
    - 实现以下 `_pure` 静态方法（无数据库依赖，用于属性测试）：
      - `_get_time_field_pure(target_table: str, table_columns: list[str] | None = None) -> str | None`：从 TIME_FIELD_MAP 查找时间字段，未命中时按 `_TIME_FIELD_PRIORITY` 自动推断
      - `_get_column_info_pure(table_columns: list[str], field_mappings: list[FieldMapping]) -> list[ColumnInfo]`：根据 field_mappings 构建列定义，有映射用 target 作 label，无映射用列名本身
      - `_infer_chart_type_pure(target_table: str, subcategory: str) -> str | None`：基于 target_table 推断图表类型（kline/sector_kline → candlestick，资金流向数据 → line，其余 → None）
      - `_build_scope_filter_pure(entry: ApiEntry) -> list[tuple[str, dict]]`：根据 ApiEntry 推断共享表作用域 WHERE 条件（kline freq、financial_statement report_type、sector data_source、top_holders holder_type）
      - `_clamp_pagination_pure(page: int | None, page_size: int | None) -> tuple[int, int]`：分页参数 clamp（page_size 范围 [1, 100] 默认 50，page 最小 1）
      - `_build_query_sql_pure(target_table: str, time_field: str | None, scope_filters: list[tuple[str, dict]], ...) -> str`：构建只读 SELECT SQL 语句
      - `_get_status_color_pure(status: str) -> str`：导入状态到 CSS 类映射（completed→green, failed→red, running→blue, pending→blue, stopped→gray, 其他→default）
    - 实现 `TusharePreviewService` 类骨架，包含异步方法签名：
      - `async query_preview_data(api_name, *, page, page_size, import_time_start, import_time_end, data_time_start, data_time_end, incremental, import_log_id) -> PreviewDataResponse`
      - `async query_stats(api_name) -> PreviewStatsResponse`
      - `async query_import_logs(api_name, *, limit=20) -> list[ImportLogItem]`
    - 所有 docstring 和注释使用中文
    - _Requirements: 2.1, 2.4, 3.2, 4.1-4.4, 6.2, 6.3, 8.3, 8.4, 9.4, 10.4_

  - [x] 1.2 实现 TusharePreviewService 异步查询方法
    - 实现 `_get_session(storage_engine)` 方法：根据 `StorageEngine.PG` 返回 `AsyncSessionPG`，`StorageEngine.TS` 返回 `AsyncSessionTS`
    - 实现 `query_preview_data` 完整逻辑：
      - 从 `TUSHARE_API_REGISTRY` 获取 `ApiEntry`，不存在则抛出 ValueError
      - 调用 `_clamp_pagination_pure` 处理分页参数
      - 调用 `_get_time_field_pure` 获取时间字段
      - 调用 `_build_scope_filter_pure` 获取作用域过滤条件
      - 处理 `incremental=True` 时的增量查询逻辑：查询最近一条 `status='completed'` 的 ImportLog，从 `params_json` 提取参数重建查询条件
      - 处理 `import_log_id` 指定的单条导入记录查询
      - 使用 `sqlalchemy.text()` 构建动态 SELECT SQL（带参数绑定，防 SQL 注入）
      - 查询总记录数和分页数据
      - 调用 `_get_column_info_pure` 和 `_infer_chart_type_pure` 构建响应
    - 实现 `query_stats` 完整逻辑：查询总记录数、最早/最晚数据时间、最近导入时间和记录数
    - 实现 `query_import_logs` 完整逻辑：查询 TushareImportLog 按 started_at 降序排列
    - 实现 `_build_incremental_filter` 方法：从导入记录的 `params_json` 提取 start_date/end_date/trade_date/ts_code 重建查询条件
    - _Requirements: 5.1-5.4, 7.2, 7.3, 7.4, 8.1-8.6, 10.1-10.3_

  - [x] 1.3 编写后端属性测试（Property 1-7, 9）
    - 新建 `tests/properties/test_tushare_preview_properties.py`
    - 编写以下属性测试（使用 Hypothesis，`@settings(max_examples=100)`）：
      - **Property 1: Registry grouping preserves all entries with correct counts**
        - 生成任意 ApiEntry 列表，验证分组后所有条目恰好出现一次，且子分类计数正确
        - **Validates: Requirements 2.1, 2.5**
      - **Property 2: Column info generation from field mappings**
        - 生成任意列名列表和 FieldMapping 列表，验证列信息生成逻辑
        - **Validates: Requirements 3.2**
      - **Property 3: Chart type inference follows deterministic rules**
        - 生成任意 target_table 和 subcategory，验证图表类型推断结果
        - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
      - **Property 4: Time field resolution and query building**
        - 生成任意 target_table，验证时间字段查找结果
        - **Validates: Requirements 6.2, 6.3**
      - **Property 5: Database session routing by storage engine**
        - 验证 PG/TS 路由逻辑
        - **Validates: Requirements 8.3**
      - **Property 6: Pagination parameter clamping**
        - 生成任意整数，验证 clamp 逻辑（page_size ∈ [1,100] 默认 50，page ≥ 1，OFFSET = (page-1)*page_size）
        - **Validates: Requirements 8.4**
      - **Property 7: Read-only SQL generation**
        - 生成任意查询参数组合，验证生成的 SQL 为 SELECT 且不含 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE
        - **Validates: Requirements 9.4**
      - **Property 9: Scope filter correctly isolates shared-table data**
        - 生成带有不同 extra_config 的 ApiEntry，验证作用域过滤条件正确
        - **Validates: Requirements 2.4, 8.3**
    - 每个测试标注 `# Feature: tushare-data-preview, Property N: ...`
    - _Requirements: 2.1, 2.4, 2.5, 3.2, 4.1-4.4, 6.2, 6.3, 8.3, 8.4, 9.4_

  - [x] 1.4 编写后端服务层单元测试
    - 新建 `tests/services/test_tushare_preview_service.py`
    - 编写以下单元测试（Mock 数据库 session）：
      - `test_query_preview_data_returns_correct_columns`
      - `test_query_stats_returns_correct_stats`
      - `test_query_import_logs_sorted_desc`
      - `test_incremental_query_finds_latest_completed`
      - `test_incremental_query_rebuilds_params_from_log`
      - `test_unknown_api_name_raises_error`
      - `test_empty_result_returns_empty_rows`
      - `test_scope_filter_kline_by_freq`
      - `test_scope_filter_financial_by_report_type`
      - `test_scope_filter_sector_by_data_source`
      - `test_time_field_fallback_priority`
    - _Requirements: 2.4, 3.2, 5.1-5.4, 7.2-7.5, 8.1-8.6, 9.4, 10.1-10.3_

- [x] 2. Checkpoint - 确保后端服务层正确
  - 确保所有后端服务层测试通过（属性测试 + 单元测试），如有问题请向用户确认。

- [x] 3. 后端 API 路由层
  - [x] 3.1 创建预览 API 路由和 Pydantic 响应模型
    - 新建 `app/api/v1/tushare_preview.py`
    - 定义 Pydantic 响应模型：`ColumnInfo`、`IncrementalInfo`、`PreviewDataResponse`、`PreviewStatsResponse`、`ImportLogItem`
    - 创建 `router = APIRouter(prefix="/data/tushare/preview", tags=["tushare-preview"])`
    - 实现 3 个端点：
      - `GET /{api_name}`：查询预览数据，接受 page、page_size、import_time_start、import_time_end、data_time_start、data_time_end、incremental、import_log_id 查询参数，调用 `TusharePreviewService.query_preview_data()`
      - `GET /{api_name}/stats`：获取数据统计信息，调用 `TusharePreviewService.query_stats()`
      - `GET /{api_name}/import-logs`：获取导入记录列表，接受 limit 参数，调用 `TusharePreviewService.query_import_logs()`
    - 错误处理：api_name 不存在返回 404，数据库连接失败返回 503，时间范围无效返回 400
    - _Requirements: 8.1-8.6, 9.3_

  - [x] 3.2 注册预览路由到 API v1
    - 在 `app/api/v1/__init__.py` 中导入并注册 `tushare_preview_router`
    - _Requirements: 8.1_

  - [x] 3.3 编写 API 端点集成测试
    - 新建 `tests/api/test_tushare_preview_api.py`
    - 编写以下测试（Mock TusharePreviewService）：
      - `test_preview_endpoint_returns_paginated_data`
      - `test_stats_endpoint_returns_statistics`
      - `test_import_logs_endpoint`
      - `test_import_time_filter`
      - `test_data_time_filter`
      - `test_incremental_query`
      - `test_unknown_api_returns_404`
      - `test_shared_table_scope_filter`
    - _Requirements: 8.1-8.6, 9.3, 9.4_

- [x] 4. 前端 Pinia Store
  - [x] 4.1 创建 tusharePreview Store
    - 新建 `frontend/src/stores/tusharePreview.ts`
    - 定义 TypeScript 类型接口：`ColumnInfo`、`IncrementalInfo`、`PreviewDataResponse`、`PreviewStatsResponse`、`ImportLogItem`、`PreviewFilters`、`ApiRegistryItem`（复用现有 tushare store 中的类型或重新定义）
    - 实现 Pinia store（setup syntax），包含以下状态和方法：
      - 状态：`registry`、`registryLoading`、`selectedApiName`、`selectedCategory`、`previewData`、`previewLoading`、`stats`、`importLogs`、`importLogsLoading`、`filters`、`displayMode`
      - 方法：
        - `fetchRegistry()`：调用 `GET /api/v1/data/tushare/registry` 获取接口列表
        - `fetchPreviewData(apiName, filters)`：调用 `GET /api/v1/data/tushare/preview/{api_name}` 获取预览数据
        - `fetchStats(apiName)`：调用 `GET /api/v1/data/tushare/preview/{api_name}/stats`
        - `fetchImportLogs(apiName, limit?)`：调用 `GET /api/v1/data/tushare/preview/{api_name}/import-logs`
        - `setSelectedApi(apiName)`：设置当前选中的 API 并触发数据加载
        - `setDisplayMode(mode)`：切换展示模式（table/chart/both）
        - `resetFilters()`：重置筛选条件
    - 实现纯函数（导出供属性测试使用）：
      - `groupRegistryByCategory(entries: ApiRegistryItem[])`：将注册表条目按 category → subcategory 分组
      - `getStatusColor(status: string)`：导入状态到 CSS 类映射
      - `inferChartType(targetTable: string, subcategory: string)`：前端侧图表类型判断
    - _Requirements: 2.1-2.5, 3.1-3.4, 4.1-4.5, 5.1-5.4, 7.1-7.5, 8.1, 10.1-10.4_

- [x] 5. 前端共享 Tab 导航组件
  - [x] 5.1 创建 TushareTabNav.vue 组件
    - 新建 `frontend/src/components/TushareTabNav.vue`
    - 使用 Vue 3 Composition API（`<script setup>`）
    - 通过 `useRoute()` 获取当前路由，判断激活的 Tab（`DataOnlineTushare` → 导入 Tab，`DataOnlineTusharePreview` → 预览 Tab）
    - 渲染两个 Tab 标签：「Tushare 数据导入」和「Tushare 数据预览」
    - 点击 Tab 使用 `router.push()` 导航到对应路由
    - 当前激活的 Tab 高亮显示
    - _Requirements: 1.2, 1.3, 1.4_

  - [x] 5.2 在 TushareImportView.vue 中添加 Tab 导航
    - 在 `frontend/src/views/TushareImportView.vue` 的 template 顶部（`<div class="tushare-import-view">` 内、`<h1>` 之前）添加 `<TushareTabNav />` 组件引用
    - 在 `<script setup>` 中导入 `TushareTabNav` 组件
    - 不修改 TushareImportView.vue 的任何业务逻辑代码
    - _Requirements: 1.5, 9.1_

- [x] 6. 前端预览页面组件
  - [x] 6.1 创建 PreviewTable.vue 数据表格组件
    - 新建 `frontend/src/components/PreviewTable.vue`
    - Props：`columns: ColumnInfo[]`、`rows: Record<string, unknown>[]`、`total: number`、`page: number`、`pageSize: number`、`loading: boolean`
    - Events：`update:page`、`update:pageSize`
    - 根据 `columns` 动态生成表头（使用 label 作为显示名称）
    - 支持分页控件：每页 20/50/100 条切换，页码导航
    - 表格上方显示总记录数
    - 空数据时显示「暂无数据」提示
    - _Requirements: 3.1-3.5_

  - [x] 6.2 创建 PreviewChart.vue 图表组件
    - 新建 `frontend/src/components/PreviewChart.vue`
    - Props：`chartType: 'candlestick' | 'line' | 'bar' | null`、`rows: Record<string, unknown>[]`、`timeField: string | null`、`columns: ColumnInfo[]`
    - 使用 vue-echarts + ECharts 5 渲染图表：
      - `candlestick`：K 线图（需要 open/high/low/close + time 列）
      - `line`：折线图（数值列 vs 时间列）
      - `null`：不渲染（隐藏组件）
    - 数据不足（< 2 个数据点）时隐藏图表
    - _Requirements: 4.1-4.4_

  - [x] 6.3 创建 TusharePreviewView.vue 预览主页面
    - 新建 `frontend/src/views/TusharePreviewView.vue`
    - 页面布局：
      - 顶部：`<TushareTabNav />` 组件 + 页面标题
      - 左侧面板：分类选择器（Category_Selector）
        - 从 store 获取 registry 数据，按 category 分为「📈 股票数据」和「📊 指数数据」两组
        - 每组内按 subcategory 分组，可折叠展开
        - 每个子分类旁显示接口数量
        - 展开后显示该子分类下所有 API 接口，点击选中
      - 右侧主区域：
        - 查询条件栏：导入时间范围选择器（快捷选项：今天/最近3天/最近7天/最近30天/自定义）、数据时间范围选择器、「查看增量数据」按钮
        - 导入记录列表（可折叠）：显示最近导入记录，每条显示导入时间、状态（颜色区分）、记录数、参数信息，点击可查看该次导入数据
        - 展示模式切换按钮：「仅表格」「仅图表」「图表+表格」
        - 图表区域：`<PreviewChart />` 组件（条件展示）
        - 数据表格区域：`<PreviewTable />` 组件
    - 增量查询模式下，表格上方显示导入时间、记录数、导入状态和导入参数摘要
    - 无成功导入记录时显示「该接口暂无成功导入记录」提示
    - 数据时间范围筛选器在无时间字段时禁用并显示提示
    - _Requirements: 1.2-1.5, 2.1-2.5, 3.1-3.5, 4.1-4.5, 5.1-5.4, 6.1-6.4, 7.1-7.5, 9.1, 9.5, 10.1-10.4_

  - [x] 6.4 编写前端属性测试（Property 1, 3, 8）
    - 新建 `frontend/src/views/__tests__/tusharePreview.property.test.ts`
    - 编写以下属性测试（使用 fast-check，`fc.assert(property, { numRuns: 100 })`）：
      - **Property 1: Registry grouping preserves all entries with correct counts**
        - 生成任意注册表条目列表，验证 `groupRegistryByCategory` 分组后所有条目恰好出现一次
        - **Validates: Requirements 2.1, 2.5**
      - **Property 3: Chart type inference follows deterministic rules**
        - 生成任意 targetTable 和 subcategory，验证 `inferChartType` 结果
        - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
      - **Property 8: Import status color mapping**
        - 生成任意状态字符串，验证 `getStatusColor` 对已知状态返回确定颜色，未知状态返回默认颜色
        - **Validates: Requirements 10.4**
    - 每个测试标注 `// Feature: tushare-data-preview, Property N: ...`
    - _Requirements: 2.1, 2.5, 4.1-4.4, 10.4_

  - [x] 6.5 编写前端单元测试
    - 新建 `frontend/src/views/__tests__/TusharePreviewView.test.ts`
    - 编写以下单元测试（使用 Vitest + @vue/test-utils）：
      - Tab 导航渲染和切换
      - 分类选择器展开/折叠
      - 表格分页切换
      - 图表/表格展示模式切换
      - 空数据状态展示
      - 增量查询按钮交互
      - 导入记录列表渲染和点击
      - 导入状态颜色区分
    - _Requirements: 1.2-1.5, 2.1-2.5, 3.1-3.5, 4.5, 7.1-7.5, 10.1-10.4_

- [x] 7. Checkpoint - 确保前端组件正确
  - 确保所有前端测试通过（属性测试 + 单元测试），如有问题请向用户确认。

- [x] 8. 路由和菜单集成
  - [x] 8.1 添加前端路由
    - 在 `frontend/src/router/index.ts` 的 MainLayout children 中，在 `DataOnlineTushare` 路由之后新增：
      ```typescript
      {
        path: 'data/online/tushare-preview',
        name: 'DataOnlineTusharePreview',
        component: () => import('@/views/TusharePreviewView.vue'),
        meta: { title: 'Tushare 数据预览' },
      }
      ```
    - _Requirements: 1.1_

  - [x] 8.2 修改侧边栏菜单
    - 在 `frontend/src/layouts/MainLayout.vue` 的菜单定义中，「在线数据」的 children 数组里，在 `{ path: '/data/online/tushare', label: 'tushare', icon: '📡' }` 之后新增：
      ```typescript
      { path: '/data/online/tushare-preview', label: 'tushare预览', icon: '🔍' }
      ```
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 9. Final checkpoint - 确保所有测试通过
  - 确保所有测试通过，包括后端属性测试、后端单元测试、后端 API 测试、前端属性测试、前端单元测试。如有问题请向用户确认。

## Notes

- 标记 `*` 的子任务为可选，可跳过以加速 MVP 交付
- 每个任务引用具体需求编号以确保可追溯性
- Checkpoint 确保增量验证
- 属性测试验证设计文档中的 9 个正确性属性（Property 1-9）
- 单元测试验证具体示例和边界情况
- 实现顺序确保无孤立代码：服务层 → API 路由 → Store → Tab 导航 → 预览页面 → 路由/菜单
- 所有新 Python 文件应包含中文 docstring 和模块级注释
- 本功能不新增 ORM 模型，完全复用现有 `tushare_registry.py` 和 `TushareImportLog` 模型
- Service 层提供 `_pure` 静态方法用于属性测试，隔离数据库依赖
- `TIME_FIELD_MAP` 必须覆盖所有 70+ 个 target_table
- 多个 API 共享同一 target_table 时（如 daily/weekly/monthly → kline），通过 `_build_scope_filter` 添加作用域过滤
- 导入状态值为 "running"、"pending"、"completed"、"failed"、"stopped"（不是 "success"）
- 增量查询通过 `params_json` 重建查询条件，而非时间窗口
- 本功能不修改任何现有导入功能代码（仅在 TushareImportView.vue template 中添加 `<TushareTabNav />`）
