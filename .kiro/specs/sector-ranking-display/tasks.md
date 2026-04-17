# Implementation Plan: 板块涨幅排行展示

## Overview

将 Dashboard 首页的"板块涨幅排行"模块从外部 AkShare API 切换为本地数据库数据源，采用增量实现策略：先实现后端仓储层和 API 端点，再创建前端 Store，最后改造 DashboardView 组件。后端使用双查询合并策略（TimescaleDB 行情 + PostgreSQL 板块信息），前端增加板块类型标签页切换。

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
    - 实现 `toggleSectorKline(sectorCode, dataSource?)` 方法：
      - 点击同一板块 → 收起（expandedSectorCode = null）
      - 点击新板块 → 展开，调用 `GET /sector/{code}/kline` 获取近一年日K线
      - 请求参数：data_source 使用当前选中的数据源或自动选择，freq=1d，start=一年前，end=今天
    - 导出所有新增状态和方法
    - _Requirements: 8.1, 8.2, 8.5, 8.6, 8.7_

  - [x] 7.2 在 DashboardView 中实现K线展开 UI
    - 将排行表格的 `<tr v-for>` 改为 `<template v-for>` 以支持每行后插入展开行
    - 板块名称单元格添加 `@click="sectorStore.toggleSectorKline(s.sector_code, ...)"` 事件
    - 板块名称单元格添加 `.sector-name-cell` 样式（cursor: pointer, hover 下划线）
    - 在每行后添加条件展开行 `<tr v-if="sectorStore.expandedSectorCode === s.sector_code">`
    - 展开行包含 `<td colspan="6">`，内含加载状态/错误提示/K线图容器
    - K线图容器高度 300px，使用 ECharts 渲染蜡烛图 + 成交量
    - 复用现有股票K线图的配色（红涨绿跌：#f85149 / #3fb950）
    - 通过 `watch` 或 `nextTick` 在数据加载完成后初始化 ECharts 实例
    - 在 `onUnmounted` 中 dispose 展开的 ECharts 实例
    - 添加展开行相关 CSS 样式（.kline-expand-row, .sector-kline-chart, .sector-name-cell 等）
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 8.6, 8.8, 8.9_

  - [x] 7.3 编写板块K线展开单元测试
    - 在 `frontend/src/stores/__tests__/sector.test.ts` 中添加测试
    - 测试 toggleSectorKline 展开：expandedSectorCode 设置正确，触发 API 调用
    - 测试 toggleSectorKline 收起：再次点击同一板块，expandedSectorCode 变为 null
    - 测试 toggleSectorKline 切换：点击不同板块，expandedSectorCode 更新
    - 测试 K线加载失败时 expandedKlineError 设置正确
    - _Requirements: 8.5, 8.6, 8.7, 8.8_

- [x] 8. Final checkpoint — 全部功能验证
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (Properties 1-5 from design)
- Unit tests validate specific examples and edge cases
- 后端使用 Python (pytest + Hypothesis)，前端使用 TypeScript (Vitest + fast-check)
