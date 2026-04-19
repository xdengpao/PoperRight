# Implementation Plan: 板块涨幅排行展示

## Overview

将 Dashboard 首页的"板块涨幅排行"模块从外部 AkShare API 切换为本地数据库数据源，采用增量实现策略：先实现后端仓储层和 API 端点，再创建前端 Store，最后改造 DashboardView 组件。后端使用双查询合并策略（TimescaleDB 行情 + PostgreSQL 板块信息），前端增加板块类型标签页切换。

第二阶段新增板块数据浏览面板（双面板布局）、分页查询 API、数据修复（TDX 后缀 + DC 简版格式）。

## Tasks

- [x] 1. 实现后端仓储层 get_sector_ranking 方法
  - [x] 1.1 在 `app/services/data_engine/sector_repository.py` 中添加 `SectorRankingItem` dataclass 和 `get_sector_ranking` 方法
    - 在文件顶部添加 `from dataclasses import dataclass` 导入
    - 定义 `SectorRankingItem` dataclass，包含 sector_code、name、sector_type、change_pct、close、volume、amount、turnover 字段
    - 实现 `_get_latest_kline_trade_date` 私有方法，查询 SectorKline 表中指定数据源的最新交易日
    - 实现 `get_sector_ranking` 方法，接受 sector_type（可选）、data_source（默认 DC）、trade_date（可选）参数
    - 实现双查询合并逻辑：先从 TimescaleDB 查询最新交易日日线行情，再从 PostgreSQL 批量查询板块信息，Python 内存合并
    - 合并结果按 change_pct 降序排序，None 值排最后
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.2 编写 get_sector_ranking 属性测试 — Property 1: 双查询合并正确性
    - **Property 1: Dual-query merge correctness**
    - **Validates: Requirements 1.2, 1.3, 2.3**
    - 在 `tests/properties/test_sector_ranking_properties.py` 中创建测试
    - 使用 Hypothesis 生成随机 SectorKline 和 SectorInfo 数据，mock 数据库 session
    - 验证合并结果中每条记录的 name、sector_type 来自 SectorInfo，change_pct、close 等来自 SectorKline
    - 验证只有同时存在于两个表中的 sector_code 才出现在结果中
    - `@settings(max_examples=100)`

  - [x] 1.3 编写 get_sector_ranking 属性测试 — Property 2: 排序不变量
    - **Property 2: Ranking sort order invariant**
    - **Validates: Requirements 1.4, 2.4**
    - 在 `tests/properties/test_sector_ranking_properties.py` 中添加测试
    - 使用 Hypothesis 生成随机 change_pct 值列表（含 None）
    - 验证结果按 change_pct 降序排列，非 None 值在 None 值之前
    - `@settings(max_examples=100)`

  - [x] 1.4 编写 get_sector_ranking 属性测试 — Property 3: 板块类型过滤正确性
    - **Property 3: Sector type filtering correctness**
    - **Validates: Requirements 1.5, 1.6**
    - 在 `tests/properties/test_sector_ranking_properties.py` 中添加测试
    - 使用 Hypothesis 生成混合类型的板块数据
    - 验证指定 sector_type 时只返回该类型，未指定时返回所有类型
    - `@settings(max_examples=100)`

  - [x] 1.5 编写 get_sector_ranking 单元测试
    - 在 `tests/services/test_sector_ranking.py` 中创建测试
    - 测试正常数据的查询和合并
    - 测试空数据处理（SectorKline 无数据时返回空列表）
    - 测试默认数据源（未指定 data_source 时使用 DC）
    - 测试最新交易日自动查询
    - 测试部分匹配（SectorKline 有记录但 SectorInfo 无对应记录时跳过）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2. 实现后端 API 端点 GET /sector/ranking
  - [x] 2.1 在 `app/api/v1/sector.py` 中添加 `SectorRankingResponse` 模型和 `/ranking` 端点
    - 定义 `SectorRankingResponse` Pydantic 模型，包含 sector_code、name、sector_type、change_pct、close、volume、amount、turnover 字段
    - 实现 `GET /ranking` 端点，接受可选的 sector_type 和 data_source 查询参数
    - 参数校验：无效的 sector_type 返回 422，无效的 data_source 返回 422
    - data_source 默认使用 DC
    - 调用 SectorRepository.get_sector_ranking 获取数据并序列化返回
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [x] 2.2 编写 API 端点属性测试 — Property 4: 无效参数拒绝
    - **Property 4: Invalid parameter rejection**
    - **Validates: Requirements 1.9**
    - 在 `tests/properties/test_sector_ranking_properties.py` 中添加测试
    - 使用 Hypothesis 生成随机非枚举字符串，验证 422 响应
    - 验证所有有效枚举值被正常接受
    - `@settings(max_examples=100)`

  - [x] 2.3 编写 API 端点单元测试
    - 在 `tests/api/test_sector_ranking_api.py` 中创建测试
    - 测试 GET /sector/ranking 正常响应格式和字段
    - 测试 sector_type 筛选功能
    - 测试 data_source 默认值为 DC
    - 测试无效参数返回 422
    - 测试空数据返回 200 和空列表
    - _Requirements: 1.1, 1.5, 1.7, 1.8, 1.9_

- [x] 3. Checkpoint — 后端验证
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 实现前端 SectorStore 和改造 DashboardView
  - [x] 4.1 创建 `frontend/src/stores/sector.ts` Pinia Store
    - 定义 `SectorRankingItem` 接口和 `SectorTypeFilter` 类型
    - 实现 `useSectorStore`，管理 rankings、currentType、loading、error 状态
    - 实现 `fetchRanking` 方法，调用 `/sector/ranking` 接口获取数据
    - 实现 `setSectorType` 方法，更新当前类型并触发 fetchRanking
    - 请求失败时保留上一次成功数据
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.2 改造 `frontend/src/views/DashboardView.vue` 板块排行模块
    - 移除现有的 `SectorData` 接口、`sectors` ref、`loadSectors` 函数
    - 引入 `useSectorStore`
    - 在板块区域添加标签页导航（全部/行业板块/概念板块/地区板块/风格板块），使用与现有 chart-tabs 一致的样式
    - 替换现有表格为新的 6 列表格：排名序号、板块名称、涨跌幅、收盘价、成交额(亿)、换手率
    - 涨跌幅正值显示红色（class="up"）+ "+"前缀，负值显示绿色（class="down"），保留两位小数 + "%"后缀
    - 成交额以亿为单位（amount / 1e8），保留两位小数
    - 换手率保留两位小数 + "%"后缀
    - 空值显示"--"占位符
    - 添加加载状态提示和错误提示 + 重试按钮
    - 添加"暂无数据"空状态提示
    - 设置 ARIA 属性：标签页 role="tab" + aria-selected，表格 aria-label，列标题 scope="col"
    - 在 onMounted 中将 `loadSectors()` 替换为 `sectorStore.fetchRanking()`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.5, 6.1, 6.2, 6.3, 6.4_

  - [x] 4.3 编写前端属性测试 — Property 5: 排行项显示格式化
    - **Property 5: Ranking item display formatting**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**
    - 在 `frontend/src/stores/__tests__/sector.property.test.ts` 中创建测试
    - 使用 fast-check 生成随机 SectorRankingItem 数据
    - 验证涨跌幅格式化：正值 "+" 前缀、两位小数、"%" 后缀、CSS class 正确
    - 验证成交额亿元转换、换手率格式化、空值 "--" 占位符
    - 最少 100 次迭代

  - [x] 4.4 编写 SectorStore 单元测试
    - 在 `frontend/src/stores/__tests__/sector.test.ts` 中创建测试
    - 测试初始状态（空列表、空类型、非加载、无错误）
    - 测试 fetchRanking 成功时数据更新
    - 测试 fetchRanking 失败时错误状态设置和数据保留
    - 测试 setSectorType 更新类型并触发 fetchRanking
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 4.5 编写 DashboardView 板块排行组件测试
    - 在 `frontend/src/views/__tests__/DashboardSectorRanking.test.ts` 中创建测试
    - 测试 5 个标签页按钮渲染
    - 测试"全部"标签页默认选中
    - 测试点击标签页触发 setSectorType
    - 测试 6 列表头渲染
    - 测试加载状态提示文字
    - 测试错误状态和重试按钮
    - 测试空数据"暂无数据"提示
    - 测试 ARIA 属性（role="tab"、aria-selected、aria-label）
    - 验证 loadSectors 和 SectorData 不再存在
    - _Requirements: 3.1, 3.2, 3.4, 3.6, 4.1, 4.7, 4.8, 5.5, 6.2_

- [x] 5. Final checkpoint — 全部测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 实现前端数据源切换功能
  - [x] 6.1 在 SectorStore 中添加数据源状态管理
    - 新增 `DataSourceFilter` 类型（'' | 'DC' | 'TI' | 'TDX'）
    - 新增 `currentDataSource` ref 状态
    - 更新 `fetchRanking` 方法，接受可选的 `dataSource` 参数并传递到 API 请求
    - 新增 `setDataSource` 方法，更新数据源并触发 fetchRanking
    - 切换数据源时保持当前板块类型不变
    - _Requirements: 7.3, 7.5, 7.6_

  - [x] 6.2 在 DashboardView 中添加数据源选择器 UI
    - 在板块类型标签页下方添加数据源按钮组（自动/东方财富/同花顺/通达信）
    - 使用紧凑的按钮组样式，字号 12px，与板块类型标签页视觉区分
    - 高亮当前选中的数据源，默认"自动"
    - 点击按钮调用 `sectorStore.setDataSource()`
    - _Requirements: 7.1, 7.2, 7.4, 7.7_

- [x] 7. 实现板块K线图展开功能
  - [x] 7.1 在 SectorStore 中添加K线展开状态管理
    - 新增 `SectorKlineBar` 接口（time, open, high, low, close, volume）
    - 新增 `expandedSectorCode` ref（string | null，当前展开的板块代码）
    - 新增 `expandedKlineData` ref（SectorKlineBar[]，展开板块的K线数据）
    - 新增 `expandedKlineLoading` ref 和 `expandedKlineError` ref
    - 实现 `toggleSectorKline(sectorCode, dataSource?)` 方法
    - 导出所有新增状态和方法
    - _Requirements: 8.1, 8.2, 8.5, 8.6, 8.7_

  - [x] 7.2 在 DashboardView 中实现K线展开 UI
    - 将排行表格的 `<tr v-for>` 改为 `<template v-for>` 以支持每行后插入展开行
    - 板块名称单元格添加点击事件和可点击样式
    - 在每行后添加条件展开行，包含加载状态/错误提示/K线图容器
    - K线图容器高度 300px，使用 ECharts 渲染蜡烛图 + 成交量
    - 复用现有股票K线图的配色（红涨绿跌）
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 8.6, 8.8, 8.9_

  - [x] 7.3 编写板块K线展开单元测试
    - 在 `frontend/src/stores/__tests__/sector.test.ts` 中添加测试
    - 测试 toggleSectorKline 展开、收起、切换
    - 测试 K线加载失败时错误状态
    - _Requirements: 8.5, 8.6, 8.7, 8.8_

- [x] 8. Final checkpoint — 全部功能验证
  - Ensure all tests pass, ask the user if questions arise.


- [x] 9. 实现后端分页浏览 API
  - [x] 9.1 在 `SectorRepository` 中添加 `PaginatedResult` 和分页查询方法
    - 在 `app/services/data_engine/sector_repository.py` 中添加 `PaginatedResult` dataclass
    - 实现 `browse_sector_info` 方法：支持 data_source、sector_type、keyword 筛选，OFFSET/LIMIT 分页
    - 实现 `browse_sector_constituent` 方法：data_source 必填，支持 sector_code、trade_date、keyword 筛选
    - 实现 `browse_sector_kline` 方法：data_source 必填，支持 sector_code、freq、start/end 日期筛选
    - keyword 使用 ILIKE '%keyword%' 模糊匹配
    - 每个方法返回 PaginatedResult(total, items)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.7_

  - [x] 9.2 在 `app/api/v1/sector.py` 中添加 3 个浏览端点
    - 添加 `SectorInfoBrowseItem`、`ConstituentBrowseItem`、`KlineBrowseItem` Pydantic 模型
    - 实现 `GET /sector/info/browse` 端点：可选 data_source、sector_type、keyword、page、page_size
    - 实现 `GET /sector/constituent/browse` 端点：必填 data_source，可选 sector_code、trade_date、keyword、page、page_size
    - 实现 `GET /sector/kline/browse` 端点：必填 data_source，可选 sector_code、freq、start、end、page、page_size
    - 所有端点返回 `{total, page, page_size, items}` 格式
    - 参数校验：无效枚举值返回 422，无效日期格式返回 422
    - page_size 范围 1-200，page >= 1
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 9.3 编写分页浏览属性测试 — Property 7: 分页响应结构不变量
    - **Property 7: Browse pagination response structure invariant**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    - 在 `tests/properties/test_sector_browse_properties.py` 中创建测试
    - 使用 Hypothesis 生成随机有效分页参数（page, page_size）
    - 验证响应包含 total >= 0、page >= 1、page_size >= 1、len(items) <= page_size
    - `@settings(max_examples=100)`

  - [x] 9.4 编写分页浏览属性测试 — Property 8: 无效参数拒绝
    - **Property 8: Browse endpoint invalid parameter rejection**
    - **Validates: Requirements 10.5**
    - 在 `tests/properties/test_sector_browse_properties.py` 中添加测试
    - 使用 Hypothesis 生成随机非枚举字符串，验证 422 响应
    - `@settings(max_examples=100)`

  - [x] 9.5 编写分页浏览属性测试 — Property 9: 关键词搜索过滤正确性
    - **Property 9: Keyword search filtering correctness**
    - **Validates: Requirements 10.7**
    - 在 `tests/properties/test_sector_browse_properties.py` 中添加测试
    - 使用 Hypothesis 生成随机 keyword 和板块数据
    - 验证返回结果中所有 item 的 sector_code 或 name 包含 keyword（不区分大小写）
    - `@settings(max_examples=100)`

  - [x] 9.6 编写分页浏览单元测试
    - 在 `tests/services/test_sector_browse.py` 中创建测试
    - 测试 browse_sector_info 基本分页、筛选组合、空结果
    - 测试 browse_sector_constituent 基本分页、默认交易日
    - 测试 browse_sector_kline 基本分页、日期范围过滤
    - 在 `tests/api/test_sector_browse_api.py` 中创建 API 测试
    - 测试 3 个端点的正常响应格式、无效参数 422、page_size 边界
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [x] 10. Checkpoint — 后端分页 API 验证
  - 运行所有后端测试确保通过

- [x] 11. 实现前端浏览面板状态管理
  - [x] 11.1 在 `SectorStore` 中添加浏览面板状态
    - 在 `frontend/src/stores/sector.ts` 中扩展现有 store
    - 新增 `BrowserTab`、`BrowseTabState`、`SectorInfoBrowseItem`、`ConstituentBrowseItem`、`KlineBrowseItem`、`BrowseResponse` 类型定义
    - 新增 `browserActiveTab` ref（默认 'info'）
    - 新增 `infoBrowse`、`constituentBrowse`、`klineBrowse` 三个独立的 `BrowseTabState` ref
    - 实现 `setBrowserTab(tab)` 方法
    - 实现 `fetchSectorInfoBrowse(page?)` 方法：调用 `/sector/info/browse`，更新 infoBrowse 状态
    - 实现 `fetchConstituentBrowse(page?)` 方法：调用 `/sector/constituent/browse`，更新 constituentBrowse 状态
    - 实现 `fetchKlineBrowse(page?)` 方法：调用 `/sector/kline/browse`，更新 klineBrowse 状态
    - 实现各标签页的 `updateFilters` 方法：修改筛选条件时重置 page=1 并重新请求
    - 请求失败时保留上次数据，设置 error 状态
    - 导出所有新增状态和方法
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 11.2 编写浏览面板状态属性测试 — Property 10: 标签页状态隔离
    - **Property 10: Browser tab state isolation**
    - **Validates: Requirements 14.2, 14.3**
    - 在 `frontend/src/stores/__tests__/sector.property.test.ts` 中添加测试
    - 使用 fast-check 生成随机标签页切换序列
    - 验证切换标签页不影响其他标签页的 items、total、page、filters、loading、error
    - 最少 100 次迭代

  - [x] 11.3 编写浏览面板状态单元测试
    - 在 `frontend/src/stores/__tests__/sectorBrowse.test.ts` 中创建测试
    - 测试 browserActiveTab 初始状态为 'info'
    - 测试 setBrowserTab 切换标签页
    - 测试 fetchSectorInfoBrowse 成功时数据和分页状态更新
    - 测试 fetchSectorInfoBrowse 失败时错误状态和数据保留
    - 测试 fetchConstituentBrowse 和 fetchKlineBrowse 成功
    - 测试标签页状态隔离（修改一个标签页不影响其他标签页）
    - 测试筛选条件变更时 page 重置为 1
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [x] 12. 实现前端 SectorBrowserPanel 组件
  - [x] 12.1 创建 `frontend/src/components/SectorBrowserPanel.vue` 组件
    - 实现 3 个标签页按钮（板块数据/板块成分/板块行情），使用 role="tab" + aria-selected
    - 默认选中"板块数据"标签页
    - 从 SectorStore 读取 browserActiveTab 状态
    - 点击标签页调用 sectorStore.setBrowserTab()
    - _Requirements: 9.4, 9.5, 9.6_

  - [x] 12.2 实现板块数据标签页（Sector Info Tab）
    - 数据源选择器（东方财富/同花顺/通达信），默认 DC
    - 板块类型筛选下拉框（全部/行业/概念/地区/风格），默认全部
    - 搜索输入框（板块名称或代码模糊搜索）
    - 修改筛选条件时重置到第 1 页并重新请求
    - 数据表格：sector_code、name、sector_type、data_source、list_date、constituent_count
    - 分页控件：上一页/下一页按钮 + 页码/总页数信息
    - 加载状态提示和"暂无数据"提示
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [x] 12.3 实现板块成分标签页（Sector Constituent Tab）
    - 数据源选择器，默认 DC
    - 板块代码输入框（精确查询）
    - 交易日期选择器（date input），默认最新交易日
    - 搜索输入框（股票代码或名称模糊搜索）
    - 修改筛选条件时重置到第 1 页并重新请求
    - 数据表格：trade_date、sector_code、data_source、symbol、stock_name
    - 分页控件 + 加载状态 + 空数据提示
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9_

  - [x] 12.4 实现板块行情标签页（Sector Kline Tab）
    - 数据源选择器，默认 DC
    - 板块代码输入框（精确查询）
    - K线频率选择器（日K/周K/月K），默认 1d
    - 开始日期和结束日期选择器
    - 修改筛选条件时重置到第 1 页并重新请求
    - 数据表格：time、sector_code、open、high、low、close、volume、amount、change_pct
    - change_pct 正值红色（class="up"），负值绿色（class="down"）
    - 分页控件 + 加载状态 + 空数据提示
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10_

  - [x] 12.5 编写 SectorBrowserPanel 组件测试
    - 在 `frontend/src/components/__tests__/SectorBrowserPanel.test.ts` 中创建测试
    - 测试 3 个标签页按钮渲染和默认选中
    - 测试标签页 ARIA 属性
    - 测试板块数据表格 6 列表头
    - 测试板块成分表格 5 列表头
    - 测试板块行情表格 9 列表头
    - 测试分页控件渲染
    - 测试加载状态和空数据提示
    - 测试行情标签页 change_pct 红涨绿跌
    - _Requirements: 9.4, 9.5, 9.6, 11.5, 11.6, 12.6, 12.7, 13.6, 13.7, 13.8_

- [x] 13. 改造 DashboardView 双面板布局
  - [x] 13.1 修改 `DashboardView.vue` 板块区域为双面板布局
    - 在 `<section class="sector-section">` 内部添加 `.sector-panels` flex 容器
    - 左侧 `.sector-panel-left`：包含现有的板块类型标签页 + 数据源选择器 + 排行表格 + K线展开
    - 右侧 `.sector-panel-right`：包含 `<SectorBrowserPanel />` 组件
    - 引入 SectorBrowserPanel 组件
    - 添加 CSS：`.sector-panels { display: flex; gap: 16px; }`
    - 添加响应式 CSS：`@media (max-width: 900px) { .sector-panels { flex-direction: column; } }`
    - 左右面板各 `flex: 1; min-width: 0;`
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 13.2 编写双面板布局测试
    - 在 `frontend/src/views/__tests__/DashboardDualPanel.test.ts` 中创建测试
    - 测试 `.sector-panel-left` 和 `.sector-panel-right` 容器存在
    - 测试 SectorBrowserPanel 组件被渲染
    - _Requirements: 9.1_

- [x] 14. Final checkpoint — 全部新功能验证
  - 运行全部后端测试：`pytest`
  - 运行全部前端测试：`cd frontend && npm test`
  - 确保所有测试通过

## Notes

- Tasks 1-8 are already implemented and marked as [x]
- Tasks 9-14 cover new requirements 9-14（板块数据浏览面板）
- 数据修复任务（需求 15/16：TDX 后缀修复、DC 简版格式修复、清理脚本）已移至 sector-data-import spec
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (Properties 1-10 from design)
- Unit tests validate specific examples and edge cases
- 后端使用 Python (pytest + Hypothesis)，前端使用 TypeScript (Vitest + fast-check)
