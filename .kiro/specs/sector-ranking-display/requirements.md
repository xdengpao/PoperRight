# 需求文档：板块涨幅排行展示

## 简介

首页大盘概况中的"板块涨幅排行"模块当前通过外部 AkShare API（`/data/market/sectors`）获取板块数据，展示为一个简单的表格，无分类筛选和排序控制。本功能将该模块替换为基于本地数据库（sector-data-import 已导入的板块数据）的分类展示与强弱排序，使量化交易员能够按板块类型（行业、概念、地区、风格）切换查看，并按涨跌幅从强到弱排列板块，快速识别当日强势板块。

## 术语表

- **Dashboard（首页大盘概况）**：系统首页视图 DashboardView.vue，展示大盘指数、市场情绪、K线图和板块涨幅排行等模块
- **Sector_Ranking_Module（板块涨幅排行模块）**：Dashboard 中展示板块涨跌幅排行的区域，本功能的改造目标
- **SectorInfo（板块信息）**：存储于 PostgreSQL 的板块元数据，包含 sector_code、name、sector_type、data_source 等字段
- **SectorKline（板块行情）**：存储于 TimescaleDB 的板块指数 OHLCV 行情数据，包含 change_pct（涨跌幅）字段
- **SectorType（板块类型）**：板块分类枚举，取值为 CONCEPT（概念板块）、INDUSTRY（行业板块）、REGION（地区板块）、STYLE（风格板块）
- **DataSource（数据来源）**：板块数据提供方枚举，取值为 DC（东方财富）、TI（同花顺）、TDX（通达信）
- **Sector_Ranking_API（板块排行接口）**：后端提供的聚合查询接口，返回指定板块类型下各板块的最新涨跌幅数据并按强弱排序
- **SectorStore（板块状态管理）**：前端 Pinia store，负责管理板块排行数据的获取、缓存和状态
- **Latest_Trade_Date（最新交易日）**：数据库中已有行情数据的最近一个交易日期

## 需求

### 需求 1：板块排行聚合查询接口

**用户故事：** 作为量化交易员，我需要后端提供一个聚合查询接口，能够返回指定板块类型下各板块的最新涨跌幅并按强弱排序，以便前端高效展示板块排行数据。

#### 验收标准

1. THE Sector_Ranking_API SHALL 提供 GET `/sector/ranking` 端点，接受可选的 `sector_type` 查询参数（CONCEPT/INDUSTRY/REGION/STYLE）和可选的 `data_source` 查询参数（DC/TI/TDX）
2. WHEN 收到排行查询请求时，THE Sector_Ranking_API SHALL 查询 SectorKline 表中最新交易日的日线（freq=1d）行情数据，关联 SectorInfo 表获取板块名称和类型
3. THE Sector_Ranking_API SHALL 返回的每条记录包含以下字段：板块代码（sector_code）、板块名称（name）、板块类型（sector_type）、涨跌幅（change_pct）、收盘价（close）、成交量（volume）、成交额（amount）、换手率（turnover）
4. THE Sector_Ranking_API SHALL 将返回结果按涨跌幅（change_pct）从大到小降序排列
5. WHEN `sector_type` 参数被指定时，THE Sector_Ranking_API SHALL 仅返回该类型的板块数据
6. WHEN `sector_type` 参数未指定时，THE Sector_Ranking_API SHALL 返回所有类型的板块数据
7. WHEN `data_source` 参数未指定时，THE Sector_Ranking_API SHALL 默认使用 DC（东方财富）作为数据来源
8. IF 数据库中无任何板块行情数据，THEN THE Sector_Ranking_API SHALL 返回空列表和 HTTP 200 状态码
9. WHEN 传入无效的 `sector_type` 或 `data_source` 参数值时，THE Sector_Ranking_API SHALL 返回 HTTP 422 状态码和描述性错误信息

### 需求 2：板块排行仓储层查询方法

**用户故事：** 作为量化交易员，我需要仓储层提供高效的板块排行查询方法，以便聚合接口能够快速获取排序后的板块涨跌幅数据。

#### 验收标准

1. THE SectorRepository SHALL 提供 `get_sector_ranking` 方法，接受 `sector_type`（可选）、`data_source`（默认 DC）和 `trade_date`（可选）参数
2. WHEN `trade_date` 参数未指定时，THE SectorRepository SHALL 自动查询 SectorKline 表中该数据源最新的交易日期
3. THE SectorRepository SHALL 通过 JOIN 查询将 SectorKline 的行情数据与 SectorInfo 的板块名称和类型关联
4. THE SectorRepository SHALL 将查询结果按 change_pct 降序排列后返回
5. WHEN 指定的数据源在 SectorKline 表中无数据时，THE SectorRepository SHALL 返回空列表

### 需求 3：前端板块类型标签页切换

**用户故事：** 作为量化交易员，我需要在板块涨幅排行模块中通过标签页切换不同板块类型，以便分类查看行业板块、概念板块、地区板块和风格板块的涨跌幅排行。

#### 验收标准

1. THE Sector_Ranking_Module SHALL 在表格上方展示板块类型标签页，包含"全部"、"行业板块"、"概念板块"、"地区板块"、"风格板块"五个选项
2. WHEN 页面首次加载时，THE Sector_Ranking_Module SHALL 默认选中"全部"标签页并加载所有类型的板块排行数据
3. WHEN 用户点击某个板块类型标签页时，THE Sector_Ranking_Module SHALL 切换到该类型并请求对应类型的板块排行数据
4. WHILE 板块排行数据正在加载时，THE Sector_Ranking_Module SHALL 展示加载状态提示文字
5. THE Sector_Ranking_Module SHALL 使用与现有图表标签页（K线图/基本面/资金流向）一致的视觉样式渲染板块类型标签页
6. THE Sector_Ranking_Module SHALL 为每个标签页按钮设置 `role="tab"` 和 `aria-selected` 属性，确保无障碍访问

### 需求 4：板块排行表格展示

**用户故事：** 作为量化交易员，我需要板块排行以表格形式展示各板块的关键行情指标，以便快速浏览和比较板块强弱。

#### 验收标准

1. THE Sector_Ranking_Module SHALL 展示包含以下列的数据表格：排名序号、板块名称、涨跌幅（%）、收盘价、成交额、换手率
2. THE Sector_Ranking_Module SHALL 将涨跌幅为正值的单元格显示为红色（class="up"），涨跌幅为负值的单元格显示为绿色（class="down"），与现有大盘指数涨跌颜色规则一致
3. THE Sector_Ranking_Module SHALL 在涨跌幅为正值时添加"+"前缀，并保留两位小数后附加"%"后缀
4. THE Sector_Ranking_Module SHALL 将成交额以"亿"为单位展示，保留两位小数
5. THE Sector_Ranking_Module SHALL 将换手率保留两位小数后附加"%"后缀
6. WHEN 收盘价、成交额或换手率数据为空时，THE Sector_Ranking_Module SHALL 显示"--"占位符
7. THE Sector_Ranking_Module SHALL 为表格设置 `aria-label="板块涨幅排行表"` 属性，为每个列标题设置 `scope="col"` 属性
8. WHEN 查询结果为空时，THE Sector_Ranking_Module SHALL 在表格中显示"暂无数据"提示

### 需求 5：前端板块状态管理

**用户故事：** 作为量化交易员，我需要前端对板块排行数据进行集中管理，以便在标签页切换时避免重复请求并保持数据一致性。

#### 验收标准

1. THE SectorStore SHALL 使用 Pinia 定义，管理板块排行数据列表、当前选中的板块类型、加载状态和错误信息
2. THE SectorStore SHALL 提供 `fetchRanking` 方法，接受可选的 `sectorType` 参数，调用 `/sector/ranking` 接口获取数据
3. WHEN `fetchRanking` 请求失败时，THE SectorStore SHALL 将错误信息存储到 error 状态，并保留上一次成功获取的数据
4. THE SectorStore SHALL 提供 `setSectorType` 方法，更新当前选中的板块类型并触发 `fetchRanking` 重新获取数据
5. IF 网络请求失败，THEN THE Sector_Ranking_Module SHALL 展示错误提示信息和"重试"按钮

### 需求 7：前端数据源切换

**用户故事：** 作为量化交易员，我需要在板块涨幅排行模块中手动切换东方财富、同花顺、通达信三个数据源，以便对比不同数据源的板块排行差异并选择自己信任的数据来源。

#### 验收标准

1. THE Sector_Ranking_Module SHALL 在板块类型标签页下方展示数据源选择器，包含"东方财富"、"同花顺"、"通达信"三个选项
2. WHEN 页面首次加载时，THE Sector_Ranking_Module SHALL 默认不选中任何数据源（使用系统自动选择逻辑）
3. WHEN 用户点击某个数据源选项时，THE Sector_Ranking_Module SHALL 使用该数据源重新请求板块排行数据，请求参数中携带 `data_source` 参数
4. THE Sector_Ranking_Module SHALL 高亮当前选中的数据源选项，未选中时显示"自动"状态
5. THE SectorStore SHALL 管理当前选中的数据源状态（currentDataSource），并在 `fetchRanking` 方法中将其作为请求参数传递
6. WHEN 用户切换数据源时，THE Sector_Ranking_Module SHALL 保持当前选中的板块类型不变，仅更换数据来源
7. THE Sector_Ranking_Module SHALL 使用紧凑的按钮组样式渲染数据源选择器，与板块类型标签页视觉上区分（如使用较小的字号或不同的背景色）

### 需求 6：替换现有外部 API 数据源

**用户故事：** 作为量化交易员，我需要板块涨幅排行模块完全使用本地数据库数据替代当前的 AkShare 外部 API 数据，以便获得更稳定和更丰富的板块数据展示。

#### 验收标准

1. THE Sector_Ranking_Module SHALL 调用本地 `/sector/ranking` 接口替代当前的 `/data/market/sectors` 外部 API 调用
2. THE Sector_Ranking_Module SHALL 移除 DashboardView.vue 中现有的 `loadSectors` 函数和 `SectorData` 接口定义
3. THE Sector_Ranking_Module SHALL 使用 SectorStore 管理板块数据，替代当前的 `sectors` ref 变量
4. WHEN Dashboard 页面挂载时，THE Sector_Ranking_Module SHALL 自动调用 SectorStore 的 `fetchRanking` 方法加载板块排行数据

### 需求 8：板块K线图展开查看

**用户故事：** 作为量化交易员，我需要在板块排行表格中点击某个板块名称时展开显示该板块近一年的日K线图，以便快速判断板块的中长期走势强弱。

#### 验收标准

1. WHEN 用户点击板块排行表格中某一行的板块名称时，THE Sector_Ranking_Module SHALL 在该行下方展开一个K线图面板，展示该板块近一年的日K线数据
2. THE Sector_Ranking_Module SHALL 调用现有的 `GET /sector/{code}/kline` 接口获取板块K线数据，传入板块代码、当前数据源（或自动选择的数据源）、freq=1d、start 为一年前日期、end 为当天日期
3. WHILE K线数据正在加载时，THE Sector_Ranking_Module SHALL 在展开面板中显示加载状态提示
4. THE Sector_Ranking_Module SHALL 使用 ECharts 渲染K线图（蜡烛图），包含开盘价、收盘价、最高价、最低价和成交量，样式与现有股票K线图一致（红涨绿跌）
5. WHEN 用户再次点击同一板块名称时，THE Sector_Ranking_Module SHALL 收起该K线图面板
6. WHEN 用户点击另一个板块名称时，THE Sector_Ranking_Module SHALL 收起当前展开的K线图并展开新板块的K线图
7. THE SectorStore SHALL 管理当前展开的板块代码状态（expandedSectorCode），以及展开板块的K线数据、加载状态和错误状态
8. IF K线数据加载失败，THEN THE Sector_Ranking_Module SHALL 在展开面板中显示错误提示和"重试"按钮
9. THE Sector_Ranking_Module SHALL 将板块名称单元格渲染为可点击样式（cursor: pointer、hover 下划线），提示用户可以交互
