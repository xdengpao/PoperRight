# 需求文档：行业概念板块数据导入

## 简介

量化选股系统当前缺乏行业/概念板块维度的数据支撑。板块数据是量化交易中不可或缺的基础数据，用于板块强势筛选、板块轮动分析、持仓板块集中度风控以及板块行情展示。

本功能从三个数据源（东方财富、同花顺、通达信）导入行业/概念板块数据，包括板块元数据（板块列表）、板块成分股每日快照、板块指数行情K线。数据存储于 `/Volumes/light/行业概念板块` 目录，包含 CSV 和 ZIP 格式文件。系统需要设计统一的存储模型，构建多源数据解析与导入流程，支持全量初始导入和增量更新，并将板块数据接入选股策略、风控模块和分析展示。

## 术语表

- **Sector（板块）**：行业或概念分类的统称，每个板块包含一组成分股票。板块类型包括行业板块、概念板块、地区板块、风格板块
- **SectorInfo（板块信息）**：板块的元数据记录，包含板块代码、名称、类型、数据来源等基本属性，存储于 PostgreSQL
- **SectorConstituent（板块成分）**：记录某个交易日某个板块包含哪些股票的每日快照数据，存储于 PostgreSQL
- **SectorKline（板块行情）**：板块指数的 OHLCV 日K线行情数据，存储于 TimescaleDB 超表
- **DataSource（数据来源）**：板块数据的提供方，本系统支持三个来源：DC（东方财富/Eastmoney）、TI（同花顺/Tonghuashun）、TDX（通达信/Tongdaxin）
- **SectorType（板块类型）**：板块的分类标签，取值包括 CONCEPT（概念）、INDUSTRY（行业）、REGION（地区）、STYLE（风格）
- **SectorImportService（板块导入服务）**：负责解析 CSV/ZIP 文件并将板块数据写入数据库的核心服务模块
- **SectorCSVParser（板块CSV解析器）**：负责将不同数据源、不同格式的 CSV 文件解析为统一内部数据结构的解析模块
- **ImportProgress（导入进度）**：通过 Redis 存储和推送的导入任务执行进度信息，包含已处理文件数、总文件数、当前阶段等
- **IncrementalData（增量数据）**：按月份目录组织的每日更新数据文件，用于在全量导入后持续追加新数据
- **BulkImport（全量导入）**：首次将历史全量数据从文件系统加载到数据库的过程
- **ConstituentSnapshot（成分快照）**：某个交易日某个板块的全部成分股列表，反映该日板块的实际构成
- **LocalKlineImportService（本地K线导入服务）**：系统中已有的本地K线数据导入服务模块，板块导入服务与其完全独立，互不影响

## 需求

### 需求 1：板块元数据存储模型

**用户故事：** 作为量化交易员，我需要系统能够存储来自多个数据源的板块基本信息，以便统一管理和查询行业/概念板块。

#### 验收标准

1. THE SectorInfo SHALL 存储以下字段：板块代码（sector_code）、板块名称（name）、板块类型（sector_type）、数据来源（data_source）、上市日期（list_date，可为空）、成分股数量（constituent_count，可为空）、更新时间（updated_at）
2. THE SectorInfo SHALL 使用板块代码（sector_code）与数据来源（data_source）的组合作为唯一约束，允许不同数据源存在相同板块代码
3. THE SectorInfo SHALL 在数据库层面建立 (sector_code, data_source) 唯一索引，确保同一数据源下板块代码不重复
4. THE SectorInfo SHALL 将 sector_type 限制为 CONCEPT、INDUSTRY、REGION、STYLE 四个枚举值
5. THE SectorInfo SHALL 将 data_source 限制为 DC、TI、TDX 三个枚举值
6. THE SectorInfo SHALL 继承 PGBase，存储于 PostgreSQL 业务数据库

### 需求 2：板块成分股快照存储模型

**用户故事：** 作为量化交易员，我需要系统记录每个交易日每个板块的成分股列表，以便追踪板块成分变化并用于历史回溯分析。

#### 验收标准

1. THE SectorConstituent SHALL 存储以下字段：交易日期（trade_date）、板块代码（sector_code）、数据来源（data_source）、成分股代码（symbol）、成分股名称（stock_name，可为空）
2. THE SectorConstituent SHALL 使用交易日期（trade_date）、板块代码（sector_code）、数据来源（data_source）、成分股代码（symbol）的组合作为唯一约束
3. THE SectorConstituent SHALL 在数据库层面建立 (trade_date, sector_code, data_source, symbol) 唯一索引，确保同一交易日同一板块同一数据源下成分股记录不重复
4. THE SectorConstituent SHALL 继承 PGBase，存储于 PostgreSQL 业务数据库
5. WHEN 查询某只股票在指定日期所属的全部板块时，THE SectorConstituent SHALL 支持按 symbol 和 trade_date 进行高效查询（建立相应索引）
6. WHEN 查询某个板块在指定日期的全部成分股时，THE SectorConstituent SHALL 支持按 sector_code、data_source 和 trade_date 进行高效查询

### 需求 3：板块指数行情存储模型

**用户故事：** 作为量化交易员，我需要系统存储板块指数的历史行情数据，以便进行板块强弱分析和板块轮动策略研究。

#### 验收标准

1. THE SectorKline SHALL 存储以下字段：交易日期（time）、板块代码（sector_code）、数据来源（data_source）、频率（freq）、开盘价（open）、最高价（high）、最低价（low）、收盘价（close）、成交量（volume，可为空）、成交额（amount，可为空）、换手率（turnover，可为空）、涨跌幅（change_pct，可为空）
2. THE SectorKline SHALL 使用 time、sector_code、data_source、freq 的组合作为唯一约束
3. THE SectorKline SHALL 在数据库层面建立 (time, sector_code, data_source, freq) 唯一索引，确保同一时间同一板块同一数据源同一频率下行情记录不重复
4. THE SectorKline SHALL 继承 TSBase，存储于 TimescaleDB 时序数据库，以 time 作为超表分区键
5. THE SectorKline SHALL 支持 1d（日线）、1w（周线）、1M（月线）三种频率
6. WHEN 查询指定板块的行情数据时，THE SectorKline SHALL 支持按 sector_code、data_source、freq 和时间范围进行高效查询

### 需求 4：多源 CSV 文件解析

**用户故事：** 作为量化交易员，我需要系统能够解析三个数据源各自不同格式的 CSV 文件，以便将原始数据转换为统一的内部数据结构。

#### 验收标准

1. WHEN 解析东方财富板块列表 CSV 时，THE SectorCSVParser SHALL 从包含 `板块代码,交易日期,板块名称,领涨股票名称,领涨股票代码,涨跌幅,领涨股票涨跌幅,总市值(万元),换手率,上涨家数,下跌家数,idx_type,level` 列头的文件中提取板块代码、板块名称和板块类型（通过 idx_type 字段映射）
2. WHEN 解析同花顺板块列表 CSV 时，THE SectorCSVParser SHALL 从包含 `代码,名称,成分个数,交易所,上市日期,指数类型` 列头的文件中提取板块代码、名称、成分股数量、上市日期和板块类型（通过指数类型字段映射）
3. WHEN 解析通达信板块列表 CSV 时，THE SectorCSVParser SHALL 从包含 `板块代码,交易日期,板块名称,板块类型,成分个数,总股本(亿),流通股(亿),总市值(亿),流通市值(亿)` 列头的文件中提取板块代码、板块名称、板块类型和成分股数量
4. WHEN 解析东方财富板块成分 ZIP 文件时，THE SectorCSVParser SHALL 从 ZIP 包内的每个 CSV 文件中提取交易日期、板块代码、成分股代码和成分股名称，ZIP 文件名格式为 `板块成分_DC_YYYYMMDD.zip`
5. WHEN 解析同花顺板块成分 CSV 时，THE SectorCSVParser SHALL 从包含 `指数代码,指数名称,指数类型,股票代码,股票名称` 列头的文件中提取板块代码、板块类型、成分股代码和成分股名称，交易日期从文件名中推断
6. WHEN 解析通达信板块成分 ZIP 文件时，THE SectorCSVParser SHALL 从 ZIP 包内的每个 CSV 文件中提取板块代码、交易日期、成分股代码和成分股名称，ZIP 文件名格式为 `板块成分_TDX_YYYYMMDD.zip`
7. WHEN 解析东方财富板块行情 CSV 时，THE SectorCSVParser SHALL 从包含 `日期,概念代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率` 列头的文件中提取 OHLCV 和涨跌幅、换手率数据
8. WHEN 解析同花顺板块行情 CSV 时，THE SectorCSVParser SHALL 从包含 `指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,昨日收盘点,平均价,涨跌点位,涨跌幅,成交量,换手率` 列头的文件中提取 OHLCV 和涨跌幅、换手率数据
9. WHEN 解析通达信板块行情 CSV 时，THE SectorCSVParser SHALL 从包含 `日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数` 列头的文件中提取 OHLCV 数据
10. IF CSV 文件编码不是 UTF-8，THEN THE SectorCSVParser SHALL 自动检测并使用正确的编码（如 GBK、GB2312）进行解析
11. FOR ALL 解析后的板块行情数据，THE SectorCSVParser SHALL 保证同一条记录内 low ≤ open、low ≤ close、high ≥ open、high ≥ close 的价格关系成立（OHLC 保序性验证）

### 需求 5：全量数据导入

**用户故事：** 作为量化交易员，我需要将历史全量板块数据从文件系统一次性导入数据库，以便建立完整的板块数据基础。

#### 验收标准

1. THE SectorImportService SHALL 支持从指定根目录（默认 `/Volumes/light/行业概念板块`）扫描并导入全部板块数据文件。根目录下数据文件按功能组织（板块列表/成分/行情），不按数据源分子目录
2. THE SectorImportService SHALL 按以下顺序执行全量导入：先导入板块列表（SectorInfo），再导入板块成分（SectorConstituent），最后导入板块行情（SectorKline）
3. WHEN 导入板块列表时，THE SectorImportService SHALL 从根目录扫描各数据源的板块列表文件（`概念板块列表_东财.csv`、`行业概念板块_同花顺.csv`、`通达信板块列表.csv`、`板块信息_通达信.zip`），以及历史行情子目录中的板块列表（`东方财富_*板块_历史行情数据/` 内的列表 CSV），使用 UPSERT 策略写入 SectorInfo 表
4. WHEN 导入板块成分时，THE SectorImportService SHALL 解析根目录的成分 ZIP/CSV 文件（`概念板块_东财.zip`、`概念板块成分汇总_同花顺.csv` 等）以及按月份组织的成分目录（`板块成分_东财/YYYY-MM/`、`板块成分_同花顺/*/YYYY-MM/`、`板块成分_通达信/YYYY-MM/`），使用批量写入方式插入 SectorConstituent 表，对重复记录执行冲突忽略
5. WHEN 导入板块行情时，THE SectorImportService SHALL 解析根目录的历史行情 ZIP 包（`板块行情_东财.zip`、`板块指数行情_同花顺.zip`、`板块行情_通达信.zip`）、历史行情子目录中的 ZIP（`东方财富_*板块_历史行情数据/*.zip`、`通达信_*板块_历史行情数据/*.zip`）以及 `增量数据/` 下的增量行情 CSV，使用批量写入方式插入 SectorKline 表，对重复记录执行冲突忽略
6. THE SectorImportService SHALL 使用批量提交策略（每批次 5000 条记录），避免单次事务过大导致内存溢出
7. WHEN 某个文件解析失败时，THE SectorImportService SHALL 记录错误日志（包含文件路径和错误原因），跳过该文件继续处理后续文件
8. THE SectorImportService SHALL 在导入过程中通过 Redis 发布导入进度信息，包含当前阶段（板块列表/成分/行情）、已处理文件数、总文件数、已导入记录数

### 需求 6：增量数据更新

**用户故事：** 作为量化交易员，我需要系统支持增量导入新产生的板块数据，以便在全量导入后持续保持数据最新。

#### 验收标准

1. THE SectorImportService SHALL 支持增量导入模式，仅处理尚未导入的新数据文件
2. WHEN 执行增量导入时，THE SectorImportService SHALL 扫描 `增量数据/` 目录下按数据类型分的子目录（`概念板块_东财/`、`板块行情_东财/`、`板块指数行情_同花顺/`、`板块行情_通达信/`、`板块信息_通达信/`），每个子目录按 `YYYY-MM/` 月份文件夹组织，增量文件命名为 `YYYY-MM-DD.csv`
3. THE SectorImportService SHALL 通过记录已导入文件的路径或最新已导入日期来判断哪些文件需要增量处理
4. WHEN 增量导入板块行情数据时，THE SectorImportService SHALL 对已存在的记录执行冲突忽略，确保重复导入同一文件不会产生重复数据
5. WHEN 增量导入板块成分数据时，THE SectorImportService SHALL 对已存在的记录执行冲突忽略
6. WHEN 增量导入板块列表数据时，THE SectorImportService SHALL 对已存在的记录执行 UPSERT（更新成分股数量等可变字段）

### 需求 7：导入任务管理

**用户故事：** 作为量化交易员，我需要通过 API 触发和监控板块数据导入任务，以便控制导入流程并了解执行状态。

#### 验收标准

1. THE Import_API SHALL 提供触发全量导入的 POST 端点，接受数据源（可选，默认全部）和根目录路径参数
2. THE Import_API SHALL 提供触发增量导入的 POST 端点，接受数据源（可选，默认全部）参数
3. THE Import_API SHALL 提供查询导入进度的 GET 端点，返回当前导入任务的阶段、进度百分比、已处理文件数和已导入记录数
4. WHEN 已有导入任务正在执行时，THE Import_API SHALL 拒绝新的导入请求并返回提示信息
5. THE Import_API SHALL 提供停止当前导入任务的 POST 端点，发送停止信号后导入服务在处理完当前批次后安全终止
6. THE SectorImportService SHALL 作为 Celery 异步任务在 data_sync 队列中执行，避免阻塞 API 请求

### 需求 8：板块数据查询服务

**用户故事：** 作为量化交易员，我需要通过 API 查询板块数据，以便在选股分析和风控决策中使用板块信息。

#### 验收标准

1. THE Sector_API SHALL 提供查询板块列表的 GET 端点，支持按板块类型（sector_type）和数据来源（data_source）筛选
2. THE Sector_API SHALL 提供查询指定板块成分股的 GET 端点，接受板块代码、数据来源和交易日期参数，返回该板块在指定日期的全部成分股列表
3. THE Sector_API SHALL 提供查询指定股票所属板块的 GET 端点，接受股票代码和交易日期参数，返回该股票在指定日期所属的全部板块列表
4. THE Sector_API SHALL 提供查询板块行情K线的 GET 端点，接受板块代码、数据来源、频率和日期范围参数，返回板块指数行情数据
5. WHEN 查询参数中未指定交易日期时，THE Sector_API SHALL 默认使用最近一个有数据的交易日

### 需求 9：板块数据接入风控模块

**用户故事：** 作为量化交易员，我需要风控模块能够基于板块成分数据计算持仓的板块集中度，以便控制单一板块的持仓风险。

#### 验收标准

1. WHEN 执行持仓风控检查时，THE RiskController SHALL 查询当前持仓中每只股票所属的板块列表（基于最新交易日的成分快照）
2. WHEN 某个板块的持仓股票数量占该板块成分股总数的比例超过配置阈值时，THE RiskController SHALL 生成板块集中度预警
3. WHEN 某个板块的持仓市值占总持仓市值的比例超过配置阈值时，THE RiskController SHALL 生成板块集中度预警
4. THE RiskController SHALL 支持配置板块集中度阈值，默认单板块持仓市值占比上限为 30%
5. IF 板块成分数据不可用（未导入或查询失败），THEN THE RiskController SHALL 记录警告日志并跳过板块集中度检查，不阻塞其他风控流程

### 需求 10：板块数据接入选股策略

**用户故事：** 作为量化交易员，我需要选股策略能够使用板块行情数据识别强势板块，以便优先选择处于强势板块中的股票。

#### 验收标准

1. THE ScreenDataProvider SHALL 支持加载指定数据源的板块行情K线数据，用于计算板块强弱指标
2. WHEN 执行板块强势筛选时，THE ScreenDataProvider SHALL 计算板块指数的短期涨跌幅（如近5日、近10日），并按涨跌幅排序识别强势板块
3. WHEN 板块强势筛选条件启用时，THE Screener SHALL 仅保留属于强势板块（排名前 N 或涨幅超过阈值）成分股的候选股票
4. THE Screener SHALL 支持配置板块强势筛选的参数：数据来源、涨幅计算周期、排名阈值或涨幅阈值
5. IF 板块行情数据不可用，THEN THE Screener SHALL 跳过板块强势筛选条件，使用其他条件继续选股，并记录警告日志

### 需求 12：适配实际文件系统目录结构

**用户故事：** 作为量化交易员，我需要板块数据导入服务能够正确识别和解析实际文件系统中的板块数据文件，即使文件目录结构和命名方式与最初设计不同。

#### 验收标准

1. THE SectorImportService SHALL 直接从根目录（`/Volumes/light/行业概念板块`）扫描板块列表文件，而非从数据源子目录（如 `东方财富/`）扫描。实际文件名为 `概念板块列表_东财.csv`（DC）、`行业概念板块_同花顺.csv`（TI）、`通达信板块列表.csv` + `板块信息_通达信.zip`（TDX）。DC 还有 `东方财富_概念板块_历史行情数据/东方财富概念板块列表.csv` 和 `东方财富_行业板块_历史行情数据/东方财富行业板块列表.csv`
2. THE SectorImportService SHALL 从独立的成分目录扫描板块成分文件：DC 从 `板块成分_东财/YYYY-MM/板块成分_DC_YYYYMMDD.zip` 和根目录 `概念板块_东财.zip`；TI 从根目录 `概念板块成分汇总_同花顺.csv`、`行业板块成分汇总_同花顺.csv`、`概念板块成分_同花顺.zip` 和 `板块成分_同花顺/*/YYYY-MM/*.csv`；TDX 从 `板块成分_通达信/YYYY-MM/板块成分_TDX_YYYYMMDD.zip`
3. THE SectorImportService SHALL 从根目录扫描历史行情 ZIP 文件（`板块行情_东财.zip`、`板块指数行情_同花顺.zip`、`板块行情_通达信.zip`），从历史行情子目录扫描 ZIP（`东方财富_概念板块_历史行情数据/概念板块_日k.zip`、`东方财富_行业板块_历史行情数据/行业板块_日k.zip`、`通达信_*板块_历史行情数据/*_K线.zip`），并从 `增量数据/板块行情_东财/`、`增量数据/板块指数行情_同花顺/`、`增量数据/板块行情_通达信/` 扫描增量行情 CSV（`YYYY-MM/YYYY-MM-DD.csv`）
4. THE SectorImportService SHALL 从通达信按板块类型分目录的历史行情目录（`通达信_概念板块_历史行情数据/`、`通达信_行业板块_历史行情数据/`、`通达信_地区板块_历史行情数据/`、`通达信_风格板块_历史行情数据/`）扫描日k/周k/月k ZIP 文件
5. THE SectorCSVParser SHALL 支持从 ZIP 文件中解析板块行情数据（DC、TI、TDX 的历史行情均以 ZIP 格式存储，内含按板块代码命名的 CSV 文件）
6. THE SectorCSVParser SHALL 正确解析东方财富行情 CSV 的实际列顺序：`板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,分类板块`（注意收盘在开盘之前）
7. THE SectorCSVParser SHALL 自动检测通达信行情 CSV 的两种格式：格式 A（历史 ZIP 内）`日期,代码,名称,开盘,收盘,最高,最低,...` 和格式 B（增量/根目录）`板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,...`
8. THE SectorCSVParser SHALL 支持从文件名推断 `YYYY-MM-DD` 格式的日期（增量文件命名如 `2020-05-21.csv`），除已有的 `YYYYMMDD` 格式外
9. THE SectorCSVParser SHALL 支持解析东方财富板块列表 CSV 中少于 13 列的行（增量文件可能不包含 `idx_type` 和 `level` 列），缺少 `idx_type` 时默认为 CONCEPT
10. THE SectorCSVParser SHALL 支持从 ZIP 文件中解析通达信板块列表数据（`板块信息_通达信.zip`）
11. THE SectorCSVParser SHALL 支持从 ZIP 文件中解析同花顺板块成分数据（`概念板块成分_同花顺.zip`，内含 `指数代码,股票代码,股票名称` 3 列格式）
12. THE SectorCSVParser SHALL 在解析同花顺板块成分时自动检测 5 列格式（汇总 CSV）和 3 列格式（ZIP 内 CSV）
13. THE _map_dc_sector_type SHALL 支持包含"板块"后缀的类型值（如 `概念板块`、`行业板块`），使用包含匹配而非精确匹配
14. THE SectorImportService SHALL 从 `增量数据/概念板块_东财/YYYY-MM/YYYY-MM-DD.csv` 扫描东方财富板块列表增量文件，从 `增量数据/板块信息_通达信/YYYY-MM/YYYY-MM-DD.csv` 扫描通达信板块列表增量文件

### 需求 11：板块导入模块独立性

**用户故事：** 作为量化交易员，我需要板块数据导入作为本地数据导入功能中一个独立的功能模块，以便板块导入的开发、运行和维护不影响现有的K线数据导入等其他数据导入功能。

#### 验收标准

1. THE SectorImportService SHALL 作为独立的服务模块实现，与现有的 LocalKlineImportService 在代码层面完全解耦，不共享可变状态
2. THE SectorImportService SHALL 使用独立的 Redis 键前缀（如 `sector_import:`）存储导入进度和运行状态，与现有 K 线导入的 Redis 键互不干扰
3. THE SectorImportService SHALL 使用独立的 Celery 任务名称注册，确保板块导入任务与 K 线导入任务可以独立触发和监控
4. WHEN 板块导入任务执行失败或异常终止时，THE SectorImportService SHALL 不影响正在执行的 K 线导入任务或其他数据同步任务的运行
5. THE SectorImportService SHALL 将板块相关的 ORM 模型（SectorInfo、SectorConstituent）和 TimescaleDB 模型（SectorKline）定义在独立的模型文件中（如 `app/models/sector.py`），不修改现有模型文件
6. THE SectorImportService SHALL 将板块导入的 API 端点注册在独立的路由模块中，不修改现有的数据导入 API 路由

