# 需求文档：行业概念板块数据导入（重构版 v2）

## 简介

量化选股系统需要从三个数据源（东方财富 DC、同花顺 TI、通达信 TDX）导入行业/概念板块数据，包括板块元数据（板块列表）、板块成分股每日快照、板块指数行情K线。

数据目录 `/Volumes/light/行业概念板块` 已按**数据源**重新整理为三个独立子目录（`东方财富/`、`同花顺/`、`通达信/`）。每个数据源子目录内的组织方式各不相同，需要为每个数据源设计独立的解析引擎。

本次重构的核心目标：
1. **保持现有数据存储模型不变**（SectorInfo、SectorConstituent、SectorKline）
2. **保持现有流式处理方式**（iter_zip_entries 模式用于 ZIP 文件）
3. **为三个数据源设计独立的解析引擎**，替代当前混合在 SectorCSVParser 中的单一解析器
4. **重写文件扫描逻辑**以匹配重新整理后的实际目录结构
5. **确保解析后的数据正确映射到已有的数据结构**（ParsedSectorInfo、ParsedConstituent、ParsedSectorKline）

## 术语表

- **Sector（板块）**：行业或概念分类的统称，每个板块包含一组成分股票。板块类型包括行业板块、概念板块、地区板块、风格板块
- **SectorInfo（板块信息）**：板块的元数据记录，包含板块代码、名称、类型、数据来源等基本属性，存储于 PostgreSQL
- **SectorConstituent（板块成分）**：记录某个交易日某个板块包含哪些股票的每日快照数据，存储于 PostgreSQL
- **SectorKline（板块行情）**：板块指数的 OHLCV K线行情数据，存储于 TimescaleDB 超表
- **DataSource（数据来源）**：板块数据的提供方，本系统支持三个来源：DC（东方财富）、TI（同花顺）、TDX（通达信）
- **SectorType（板块类型）**：板块的分类标签，取值包括 CONCEPT（概念）、INDUSTRY（行业）、REGION（地区）、STYLE（风格）
- **DCParsingEngine（东方财富解析引擎）**：专门负责解析东方财富数据源格式的 CSV/ZIP 文件的独立解析模块
- **TIParsingEngine（同花顺解析引擎）**：专门负责解析同花顺数据源格式的 CSV/ZIP 文件的独立解析模块
- **TDXParsingEngine（通达信解析引擎）**：专门负责解析通达信数据源格式的 CSV/ZIP 文件的独立解析模块
- **散装CSV（Individual CSV）**：按板块代码命名的独立 CSV 文件（如 `BK0145.DC.csv`、`700001.TI.csv`），每个文件包含一个板块的全部历史数据
- **ParsedSectorInfo / ParsedConstituent / ParsedSectorKline**：解析层输出的中间数据结构（dataclass）
- **SectorImportService（板块导入服务）**：负责文件扫描、调用解析引擎、批量写入数据库、管理导入进度的核心服务模块
- **StreamingProcessing（流式处理）**：逐个读取文件并分批写入数据库的处理模式，避免将大量数据一次性加载到内存

## 需求

### 需求 1：板块元数据存储模型（保持不变）

**用户故事：** 作为量化交易员，我需要系统能够存储来自多个数据源的板块基本信息，以便统一管理和查询行业/概念板块。

#### 验收标准

1. THE SectorInfo SHALL 存储以下字段：板块代码（sector_code）、板块名称（name）、板块类型（sector_type）、数据来源（data_source）、上市日期（list_date，可为空）、成分股数量（constituent_count，可为空）、更新时间（updated_at）
2. THE SectorInfo SHALL 使用板块代码（sector_code）与数据来源（data_source）的组合作为唯一约束
3. THE SectorInfo SHALL 在数据库层面建立 (sector_code, data_source) 唯一索引
4. THE SectorInfo SHALL 将 sector_type 限制为 CONCEPT、INDUSTRY、REGION、STYLE 四个枚举值
5. THE SectorInfo SHALL 将 data_source 限制为 DC、TI、TDX 三个枚举值
6. THE SectorInfo SHALL 继承 PGBase，存储于 PostgreSQL 业务数据库

### 需求 2：板块成分股快照存储模型（保持不变）

**用户故事：** 作为量化交易员，我需要系统记录每个交易日每个板块的成分股列表，以便追踪板块成分变化并用于历史回溯分析。

#### 验收标准

1. THE SectorConstituent SHALL 存储以下字段：交易日期（trade_date）、板块代码（sector_code）、数据来源（data_source）、成分股代码（symbol）、成分股名称（stock_name，可为空）
2. THE SectorConstituent SHALL 使用 (trade_date, sector_code, data_source, symbol) 组合作为唯一约束
3. THE SectorConstituent SHALL 继承 PGBase，存储于 PostgreSQL 业务数据库
4. THE SectorConstituent SHALL 建立 (symbol, trade_date) 和 (sector_code, data_source, trade_date) 查询索引

### 需求 3：板块指数行情存储模型（保持不变）

**用户故事：** 作为量化交易员，我需要系统存储板块指数的历史行情数据，以便进行板块强弱分析和板块轮动策略研究。

#### 验收标准

1. THE SectorKline SHALL 存储以下字段：交易日期（time）、板块代码（sector_code）、数据来源（data_source）、频率（freq）、开盘价（open）、最高价（high）、最低价（low）、收盘价（close）、成交量（volume，可为空）、成交额（amount，可为空）、换手率（turnover，可为空）、涨跌幅（change_pct，可为空）
2. THE SectorKline SHALL 使用 (time, sector_code, data_source, freq) 组合作为唯一约束
3. THE SectorKline SHALL 继承 TSBase，存储于 TimescaleDB 时序数据库
4. THE SectorKline SHALL 支持 1d（日线）、1w（周线）、1M（月线）三种频率


### 需求 4：实际目录结构与文件扫描

**用户故事：** 作为量化交易员，我已将 `/Volumes/light/行业概念板块` 目录下的数据按数据源重新整理，我需要导入服务能够正确识别和扫描实际的目录结构。

#### 实际目录结构

```
/Volumes/light/行业概念板块/
├── 东方财富/
│   ├── 东方财富_板块列表/
│   │   ├── 东方财富_板块列表1.csv                     # 简版板块列表（列头: 名称,代码）
│   │   ├── 东方财富_板块列表2.csv                     # 简版板块列表（列头: 名称,代码）
│   │   └── 东方财富_概念板块列表/                     # 散装 CSV（~1531 个文件）
│   │       └── BK*.DC.csv                             # 列头: 板块代码,交易日期,板块名称,...,idx_type,level (13列)
│   ├── 东方财富_板块行情/
│   │   ├── 东方财富_地区板块行情/                     # 散装 CSV（~1029 个文件）
│   │   │   └── BK*.DC.csv                             # 列头: 板块代码,交易日期,收盘点位,开盘点位,... (13列, 收盘在前)
│   │   └── 东方财富_行业板块行情/                     # 散装 CSV（~497 个文件）
│   │       └── BK*_daily.csv                          # 列头: 日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率 (12列, 标准OHLC)
│   ├── 东方财富_板块成分/                             # 按月份组织（17 months, 314 zip）
│   │   └── YYYY-MM/板块成分_DC_YYYYMMDD.zip           # 每日成分快照 ZIP
│   └── 东方财富_增量数据/
│       ├── 东方财富_板块列表/                         # 增量板块列表（8 months, 218 csv）
│       │   └── YYYY-MM/BK*.DC.csv                     # 列头同概念板块列表
│       └── 东方财富_板块行情/                         # 增量行情（72 months, 1431 csv）
│           └── YYYY-MM/YYYY-MM-DD.csv                 # 列头同板块行情
│
├── 同花顺/
│   ├── 同花顺_板块列表/
│   │   └── 同花顺_板块列表.csv                        # 全量板块列表（列头: 代码,名称,成分个数,交易所,上市日期,指数类型）
│   ├── 同花顺_板块行情/                               # 散装 CSV（~1573 个文件）
│   │   └── 700001.TI.csv                              # 列头: 指数代码,交易日期,开盘点位,...,换手率 (12列)
│   ├── 同花顺_板块成分/
│   │   ├── 同花顺_概念板块成分汇总.csv                # 列头: 指数代码,指数名称,指数类型,股票代码,股票名称
│   │   └── 同花顺_行业板块成分汇总.csv                # 列头: 同上
│   └── 同花顺_增量数据/
│       ├── 同花顺_板块行情/                           # 增量行情（59 months, 1260 csv）
│       │   └── YYYY-MM/YYYY-MM-DD.csv
│       ├── 同花顺_概念板块成分/                       # 增量概念成分（4 months, 95 csv）
│       │   └── YYYY-MM/*.csv                          # 列头: 指数代码,指数名称,指数类型,股票代码,股票名称
│       └── 同花顺_行业板块成分/                       # 增量行业成分（4 months, 95 csv）
│           └── YYYY-MM/*.csv                          # 列头: 同上
│
└── 通达信/
    ├── 通达信_板块列表/
    │   ├── 通达信_板块列表.csv                        # 全量板块列表（列头: 板块代码,交易日期,板块名称,板块类型,成分个数,... 9列）
    │   └── 通达信_板块列表汇总/                       # 散装 CSV（~615 个文件）
    │       └── 880*.TDX.csv                           # 列头同板块列表格式
    ├── 通达信_板块行情/
    │   ├── 通达信_板块行情汇总/                       # 散装 CSV（~615 个文件）
    │   │   └── 880*.TDX.csv                           # 列头: 板块代码,交易日期,收盘点位,开盘点位,... (38列)
    │   ├── 通达信_概念板块历史行情/                   # 历史行情 ZIP（3 zip: 日k/周k/月k）
    │   ├── 通达信_行业板块历史行情/                   # 同上模式
    │   ├── 通达信_地区板块历史行情/                   # 同上模式
    │   └── 通达信_风格板块历史行情/                   # 同上模式
    ├── 通达信_板块成分/                               # 按月份组织（14 months, 253 zip）
    │   └── YYYY-MM/板块成分_TDX_YYYYMMDD.zip
    └── 通达信_增量数据/
        ├── 通达信_板块列表/                           # 增量板块列表（8 months, 153 csv）
        │   └── YYYY-MM/*.csv
        └── 通达信_板块行情/                           # 增量行情（14 months, 260 csv）
            └── YYYY-MM/*.csv
```

#### 验收标准

1. THE SectorImportService SHALL 从根目录 `/Volumes/light/行业概念板块` 下按数据源子目录扫描文件，三个数据源子目录分别为 `东方财富/`（DC）、`同花顺/`（TI）、`通达信/`（TDX）
2. WHEN 扫描东方财富板块列表文件时，THE SectorImportService SHALL 扫描 `东方财富/东方财富_板块列表/东方财富_板块列表1.csv`、`东方财富/东方财富_板块列表/东方财富_板块列表2.csv`（简版列表）以及 `东方财富/东方财富_板块列表/东方财富_概念板块列表/*.csv`（散装概念板块列表，含 idx_type 等 13 列）
3. WHEN 扫描东方财富板块行情文件时，THE SectorImportService SHALL 扫描两个散装 CSV 目录：`东方财富_板块行情/东方财富_地区板块行情/*.csv`、`东方财富_板块行情/东方财富_行业板块行情/*.csv`，每个目录包含按板块代码命名的独立 CSV 文件
4. WHEN 扫描东方财富板块成分文件时，THE SectorImportService SHALL 扫描 `东方财富_板块成分/YYYY-MM/板块成分_DC_YYYYMMDD.zip`
5. WHEN 扫描东方财富增量数据时，THE SectorImportService SHALL 扫描 `东方财富_增量数据/东方财富_板块行情/YYYY-MM/YYYY-MM-DD.csv`（增量行情）和 `东方财富_增量数据/东方财富_板块列表/YYYY-MM/BK*.DC.csv`（增量板块列表）
6. WHEN 扫描同花顺板块列表文件时，THE SectorImportService SHALL 扫描 `同花顺/同花顺_板块列表/同花顺_板块列表.csv`
7. WHEN 扫描同花顺板块行情文件时，THE SectorImportService SHALL 扫描散装 CSV 目录 `同花顺_板块行情/*.csv`，每个文件按板块代码命名（如 `700001.TI.csv`）
8. WHEN 扫描同花顺板块成分文件时，THE SectorImportService SHALL 扫描：概念板块成分汇总 `同花顺_板块成分/同花顺_概念板块成分汇总.csv`、行业板块成分汇总 `同花顺_板块成分/同花顺_行业板块成分汇总.csv`、增量概念板块成分 `同花顺_增量数据/同花顺_概念板块成分/YYYY-MM/*.csv`、增量行业板块成分 `同花顺_增量数据/同花顺_行业板块成分/YYYY-MM/*.csv`
9. WHEN 扫描同花顺增量数据时，THE SectorImportService SHALL 扫描 `同花顺_增量数据/同花顺_板块行情/YYYY-MM/YYYY-MM-DD.csv`
10. WHEN 扫描通达信板块列表文件时，THE SectorImportService SHALL 扫描 `通达信/通达信_板块列表/通达信_板块列表.csv`（全量列表）和散装 CSV 目录 `通达信_板块列表/通达信_板块列表汇总/*.csv`（每个板块的历史信息快照）
11. WHEN 扫描通达信板块行情文件时，THE SectorImportService SHALL 扫描散装 CSV 目录 `通达信_板块行情/通达信_板块行情汇总/*.csv`（每个板块的历史行情）以及四个历史行情 ZIP 目录（`通达信_板块行情/通达信_概念板块历史行情/`、`通达信_板块行情/通达信_行业板块历史行情/`、`通达信_板块行情/通达信_地区板块历史行情/`、`通达信_板块行情/通达信_风格板块历史行情/`，每个目录下有日k/周k/月k ZIP 文件）
12. WHEN 扫描通达信板块成分文件时，THE SectorImportService SHALL 扫描 `通达信_板块成分/YYYY-MM/板块成分_TDX_YYYYMMDD.zip`
13. WHEN 扫描通达信增量数据时，THE SectorImportService SHALL 扫描 `通达信_增量数据/通达信_板块列表/YYYY-MM/*.csv`（增量板块列表）和 `通达信_增量数据/通达信_板块行情/YYYY-MM/*.csv`（增量行情）
14. IF 某个数据源子目录不存在，THEN THE SectorImportService SHALL 记录警告日志并跳过该数据源
15. IF 某个功能子目录不存在，THEN THE SectorImportService SHALL 返回空文件列表，不报错

### 需求 5：东方财富解析引擎（DCParsingEngine）

**用户故事：** 作为量化交易员，我需要一个专门的东方财富解析引擎来处理东方财富特有的数据格式。

#### 验收标准

1. THE DCParsingEngine SHALL 作为独立的解析模块实现
2. WHEN 解析板块列表 CSV 时（`东方财富_板块列表.csv` 或各类型板块列表），THE DCParsingEngine SHALL 从列头 `板块代码,交易日期,板块名称,...,idx_type,level` 中提取板块代码、板块名称和板块类型（通过 idx_type 字段映射），按 sector_code 去重，映射为 ParsedSectorInfo 列表
3. THE DCParsingEngine SHALL 支持 idx_type 包含"板块"后缀的值（如 `地域板块`、`概念板块`），使用包含匹配
4. WHEN 解析板块列表 CSV 中少于 13 列的行时，THE DCParsingEngine SHALL 缺少 idx_type 时默认为 CONCEPT
5. WHEN 解析散装行情 CSV 时，THE DCParsingEngine SHALL 自动检测两种列头格式：
   - **格式 A**（地区板块行情 + 增量行情）：列头 `板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,分类板块`（收盘在开盘之前）
   - **格式 B**（行业板块行情）：列头 `日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率`（标准 OHLC 顺序）
   检测方式：读取列头第一个字段，若为"日期"则使用格式 B，否则使用格式 A
6. WHEN 解析板块成分 ZIP 时（`板块成分_DC_YYYYMMDD.zip`），THE DCParsingEngine SHALL 从 ZIP 内每个 CSV（列头: `交易日期,板块代码,成分股票代码,成分股票名称`）提取成分数据，映射为 ParsedConstituent 列表。若 ZIP 文件名无日期则从 CSV 行内容读取日期
7. WHEN 解析增量行情 CSV 时，THE DCParsingEngine SHALL 使用与散装行情格式 A 相同的解析逻辑（列头格式相同）
8. WHEN 解析增量板块列表 CSV 时，THE DCParsingEngine SHALL 使用与板块列表 CSV 相同的解析逻辑

### 需求 6：同花顺解析引擎（TIParsingEngine）

**用户故事：** 作为量化交易员，我需要一个专门的同花顺解析引擎来处理同花顺特有的数据格式。

#### 验收标准

1. THE TIParsingEngine SHALL 作为独立的解析模块实现
2. WHEN 解析板块列表 CSV 时（`同花顺_板块列表.csv`），THE TIParsingEngine SHALL 从列头 `代码,名称,成分个数,交易所,上市日期,指数类型` 中提取板块代码、名称、成分股数量、上市日期和板块类型（通过指数类型映射），映射为 ParsedSectorInfo 列表
3. WHEN 解析散装行情 CSV 时（如 `700001.TI.csv`），THE TIParsingEngine SHALL 从列头 `指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,昨日收盘点,平均价,涨跌点位,涨跌幅,成交量,换手率` 中提取 OHLCV 数据，映射为 ParsedSectorKline 列表
4. WHEN 解析成分汇总 CSV 时（5 列格式: `指数代码,指数名称,指数类型,股票代码,股票名称`），THE TIParsingEngine SHALL 提取板块代码和成分股信息，映射为 ParsedConstituent 列表
5. WHEN 解析散装成分 CSV 时（3 列格式: `指数代码,股票代码,股票名称`），THE TIParsingEngine SHALL 提取板块代码和成分股信息，映射为 ParsedConstituent 列表
6. WHEN 解析增量成分 CSV 时（`行业板块成分汇总_同花顺_YYYYMMDD.csv`），THE TIParsingEngine SHALL 从文件名推断交易日期
7. WHEN 解析增量行情 CSV 时，THE TIParsingEngine SHALL 使用与散装行情 CSV 相同的解析逻辑

### 需求 7：通达信解析引擎（TDXParsingEngine）

**用户故事：** 作为量化交易员，我需要一个专门的通达信解析引擎来处理通达信特有的数据格式。

#### 验收标准

1. THE TDXParsingEngine SHALL 作为独立的解析模块实现
2. WHEN 解析板块列表 CSV 时（`通达信_板块列表.csv`），THE TDXParsingEngine SHALL 从列头 `板块代码,交易日期,板块名称,板块类型,成分个数,...` 中提取板块代码、板块名称、板块类型和成分股数量，映射为 ParsedSectorInfo 列表
3. WHEN 解析散装板块信息 CSV 时（`通达信_板块信息汇总/*.csv`），THE TDXParsingEngine SHALL 使用与板块列表相同的列头格式解析，映射为 ParsedSectorInfo 列表（用于获取每日板块信息快照）
4. WHEN 解析散装行情 CSV 时（`通达信_板块行情汇总/*.csv`），THE TDXParsingEngine SHALL 从列头 `板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,...`（38 列格式）中提取 OHLCV 数据，映射为 ParsedSectorKline 列表
5. WHEN 解析历史行情 ZIP 时（如 `概念板块_日k_K线.zip`），THE TDXParsingEngine SHALL 从 ZIP 内每个 CSV（列头: `日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,...`）提取 OHLCV 数据，映射为 ParsedSectorKline 列表
6. THE TDXParsingEngine SHALL 自动检测两种行情 CSV 格式：格式 A（历史 ZIP 内: `日期,代码,名称,开盘,收盘,...`）和格式 B（散装/增量: `板块代码,交易日期,收盘点位,开盘点位,...`）
7. THE TDXParsingEngine SHALL 从历史行情 ZIP 文件名推断频率（日k→1d、周k→1w、月k→1M）
8. THE TDXParsingEngine SHALL 提供流式解析方法（iter_kline_zip），以生成器方式逐个 yield ZIP 内部 CSV 解析结果
9. WHEN 解析板块成分 ZIP 时（`板块成分_TDX_YYYYMMDD.zip`），THE TDXParsingEngine SHALL 从 ZIP 内 CSV 提取成分数据，映射为 ParsedConstituent 列表
10. WHEN 解析增量行情/板块信息 CSV 时，THE TDXParsingEngine SHALL 使用与对应散装 CSV 相同的解析逻辑

### 需求 8：解析引擎通用能力

**用户故事：** 作为量化交易员，我需要三个解析引擎共享一组通用的基础能力。

#### 验收标准

1. IF CSV 文件编码不是 UTF-8，THEN 每个解析引擎 SHALL 自动检测编码（UTF-8 → GBK → GB2312）
2. FOR ALL 解析后的板块行情数据，每个解析引擎 SHALL 验证 OHLC 保序性（low ≤ open, low ≤ close, high ≥ open, high ≥ close），不满足的记录跳过
3. 每个解析引擎 SHALL 支持从文件名推断日期（YYYYMMDD 和 YYYY-MM-DD 两种格式）
4. 每个解析引擎 SHALL 提供 `iter_zip_entries(zip_path)` 生成器方法，直接从文件系统打开 ZIP 文件逐个 yield 内部文件
5. 每个解析引擎 SHALL 将解析结果统一映射为 ParsedSectorInfo、ParsedConstituent、ParsedSectorKline
6. WHEN 解析 CSV 行时字段不足或数值解析失败，每个解析引擎 SHALL 跳过该行并记录 WARNING 日志
7. WHEN 处理散装 CSV 目录（包含数百至数千个独立 CSV 文件）时，每个解析引擎 SHALL 支持逐文件处理并分批写入数据库，避免将所有文件的解析结果一次性加载到内存

### 需求 9：全量数据导入

**用户故事：** 作为量化交易员，我需要将历史全量板块数据从文件系统导入数据库。

#### 验收标准

1. THE SectorImportService SHALL 按顺序执行：板块列表 → 板块成分 → 板块行情
2. THE SectorImportService SHALL 对板块列表使用 UPSERT 策略（ON CONFLICT DO UPDATE）
3. THE SectorImportService SHALL 对板块成分和行情使用 ON CONFLICT DO NOTHING
4. THE SectorImportService SHALL 使用批量提交策略（每批次 5000 条记录）
5. WHEN 处理散装 CSV 目录时，THE SectorImportService SHALL 逐文件解析并写入，每个文件处理完后更新进度
6. WHEN 某个文件解析失败时，THE SectorImportService SHALL 记录错误日志，跳过该文件继续处理
7. THE SectorImportService SHALL 通过 Redis 发布导入进度信息

### 需求 10：增量数据更新

**用户故事：** 作为量化交易员，我需要系统支持增量导入新产生的板块数据。

#### 验收标准

1. THE SectorImportService SHALL 支持增量导入模式，仅处理尚未导入的新数据文件
2. THE SectorImportService SHALL 通过 Redis 记录已导入文件的路径和 mtime 来判断增量
3. 增量文件按 `YYYY-MM/YYYY-MM-DD.csv` 组织在各数据源的增量数据目录下
4. 增量导入 SHALL 使用与全量导入相同的冲突处理策略

### 需求 11：大型文件集流式处理

**用户故事：** 作为量化交易员，我需要导入能够处理包含数千个文件的散装 CSV 目录和大型 ZIP 文件，而不会因内存不足导致进程终止。

#### 验收标准

1. WHEN 处理散装 CSV 目录（如东方财富概念板块行情 ~1531 个文件）时，THE SectorImportService SHALL 逐文件读取、解析、写入数据库，每个文件处理完后释放内存
2. WHEN 处理大型 ZIP 文件（如通达信历史行情 ZIP）时，每个解析引擎 SHALL 使用 iter_zip_entries 生成器逐个读取内部 CSV
3. THE SectorImportService SHALL 在处理每个文件之间检查停止信号
4. THE SectorImportService SHALL 在处理每个文件后更新 Redis 导入进度

### 需求 12：导入任务管理（保持不变）

**用户故事：** 作为量化交易员，我需要通过 API 触发和监控板块数据导入任务。

#### 验收标准

1. THE Import_API SHALL 提供触发全量导入的 POST 端点
2. THE Import_API SHALL 提供触发增量导入的 POST 端点
3. THE Import_API SHALL 提供查询导入进度的 GET 端点
4. WHEN 已有导入任务正在执行时，THE Import_API SHALL 拒绝新请求
5. THE Import_API SHALL 提供停止当前导入任务的 POST 端点
6. THE SectorImportService SHALL 作为 Celery 异步任务在 data_sync 队列中执行

### 需求 13：板块数据查询服务（保持不变）

**用户故事：** 作为量化交易员，我需要通过 API 查询板块数据。

#### 验收标准

1. THE Sector_API SHALL 提供查询板块列表的 GET 端点，支持按 sector_type 和 data_source 筛选
2. THE Sector_API SHALL 提供查询板块成分股的 GET 端点
3. THE Sector_API SHALL 提供查询股票所属板块的 GET 端点
4. THE Sector_API SHALL 提供查询板块行情K线的 GET 端点
5. WHEN 未指定交易日期时，THE Sector_API SHALL 默认使用最近有数据的交易日

### 需求 14：板块数据接入风控模块（保持不变）

**用户故事：** 作为量化交易员，我需要风控模块能够基于板块成分数据计算持仓的板块集中度。

#### 验收标准

1. THE RiskController SHALL 查询持仓股票所属板块列表
2. THE RiskController SHALL 在板块集中度超过阈值时生成预警
3. THE RiskController SHALL 支持配置板块集中度阈值（默认 30%）
4. IF 板块数据不可用，THEN THE RiskController SHALL 跳过板块集中度检查

### 需求 15：板块数据接入选股策略（保持不变）

**用户故事：** 作为量化交易员，我需要选股策略能够使用板块行情数据识别强势板块。

#### 验收标准

1. THE Screener SHALL 支持计算板块短期涨跌幅并排序
2. THE Screener SHALL 支持仅保留强势板块成分股
3. IF 板块数据不可用，THEN THE Screener SHALL 跳过板块筛选条件

### 需求 16：板块导入模块独立性（保持不变）

**用户故事：** 作为量化交易员，我需要板块导入作为独立模块，不影响其他数据导入功能。

#### 验收标准

1. THE SectorImportService SHALL 与 LocalKlineImportService 完全解耦
2. THE SectorImportService SHALL 使用独立的 Redis 键前缀 `sector_import:`
3. THE SectorImportService SHALL 使用独立的 Celery 任务名称
4. THE SectorImportService SHALL 将 ORM 模型定义在独立的 `app/models/sector.py`
5. THE SectorImportService SHALL 将 API 端点注册在独立的路由模块

### 需求 17：导入错误统计与导出

**用户故事：** 作为量化交易员，我需要知道板块数据导入过程中有多少数据出错，以便评估数据质量并排查问题。

#### 验收标准

1. THE SectorImportService SHALL 在导入过程中统计错误数据条数（`error_count`），包括解析失败的行、OHLC 验证失败的行、数据库写入失败的批次
2. THE SectorImportService SHALL 在导入过程中记录失败文件列表（`failed_files`），每个条目包含文件名和错误原因摘要
3. THE SectorImportService SHALL 将 `error_count` 和 `failed_files` 写入 Redis 导入进度 JSON，与 `imported_records` 同级
4. THE Import_API GET /sector/import/status 端点 SHALL 在响应中返回 `error_count`（整数）和 `failed_files`（数组）字段
5. THE Import_API SHALL 提供 GET /sector/import/errors 端点，返回完整的错误详情列表，支持分页
6. THE Import_API SHALL 提供 GET /sector/import/errors/export 端点，以 CSV 格式导出错误详情（文件名、行号、错误类型、错误信息、原始数据摘要）
7. THE 前端导入进度页面 SHALL 在"已导入记录数"卡片右侧新增"出错记录数"卡片，以红色高亮显示 `error_count`
8. WHEN `error_count > 0` 时，THE 前端 SHALL 显示"导出错误报告"按钮，点击后下载 CSV 文件
9. THE SectorImportService SHALL 将错误详情暂存于 Redis 列表（键 `sector_import:errors`），每条记录为 JSON 对象，包含 `file`、`line`、`error_type`（parse_error / ohlc_invalid / db_error）、`message`、`raw_data`（截断至 200 字符）
10. THE SectorImportService SHALL 在每次新导入开始时清空 `sector_import:errors` 列表


### 需求 18：板块代码统一添加数据源后缀

**用户故事：** 作为量化交易员，我需要通过板块代码直接区分数据来源（如 `BK0001.DC`、`880201.TDX`、`700001.TI`），因此解析引擎在入库时应统一为 sector_code 添加数据源后缀。目前 TDX 历史行情 ZIP 解析出的板块代码不带后缀（如 `880201`），与其他记录格式不一致，导致跨表 JOIN 时匹配失败，部分板块排行数据查不到。

#### 背景

当前数据库中 sector_code 存在后缀不一致问题：
- **sector_info 表**：DC 为 `BK0001.DC`，TI 为 `700001.TI`，TDX 为 `880201.TDX`（全部带后缀，正确）
- **sector_kline 表**：DC 为 `BK0001.DC`（带后缀，正确），TI 为 `700001.TI`（带后缀，正确），TDX 同时存在 `880201.TDX`（散装 CSV 解析，正确）和 `880201`（历史 ZIP 解析，**缺少后缀**）两种格式
- **sector_constituent 表**：与 sector_info 格式一致（带后缀，正确）

TDX 历史行情 ZIP 内的 CSV 文件中板块代码不带 `.TDX` 后缀，解析引擎未补充后缀导致入库数据格式不一致。需要：
1. 修复 TDXParsingEngine 的历史行情 ZIP 解析逻辑，确保 sector_code 统一带 `.TDX` 后缀
2. 清除已入库的不带后缀的 TDX 行情数据，后续重新导入

#### 验收标准

1. THE TDXParsingEngine SHALL 在解析历史行情 ZIP（`parse_kline_zip` 和 `iter_kline_zip`）时，对解析出的 sector_code 检查是否已包含 `.TDX` 后缀，若不包含则自动追加 `.TDX` 后缀
2. THE 解析引擎（DCParsingEngine、TIParsingEngine、TDXParsingEngine）SHALL 确保所有解析方法输出的 sector_code 统一包含对应的数据源后缀（`.DC`、`.TI`、`.TDX`）
3. THE 系统 SHALL 提供数据清理脚本，删除 sector_kline 表中 data_source='TDX' 且 sector_code 不以 '.TDX' 结尾的所有记录（即不带后缀的 TDX 行情数据）
4. THE 数据清理脚本 SHALL 记录删除的记录数量，输出清理报告
5. AFTER 清理完成后，用户 SHALL 通过清空 Redis 增量缓存并触发全量导入来重新导入 TDX 历史行情数据
6. AFTER 重新导入完成后，THE sector_kline 表中 data_source='TDX' 的所有记录的 sector_code SHALL 以 '.TDX' 结尾，格式与 sector_info 表一致

### 需求 19：修复 DC 简版板块列表解析错误

**用户故事：** 作为量化交易员，我发现东方财富的板块列表数据中存在大量垃圾记录（日期被当作板块代码、价格被当作板块名称），这是因为简版板块列表文件（`东方财富_板块列表1.csv`、`东方财富_板块列表2.csv`，列头为 `名称,代码`，仅 2 列）被错误地按 13 列格式解析。我需要修复解析逻辑并清理已入库的垃圾数据。

#### 背景

当前 DC sector_info 中有 7,394 条记录，其中：
- 正确的 BK 格式记录：1,031 条
- 垃圾数据（日期格式的 sector_code）：6,363 条

垃圾数据来源于简版板块列表文件，这些文件的格式为 `名称,代码`（2 列），与标准的 13 列格式完全不同。

#### 验收标准

1. THE DCParsingEngine SHALL 在 `parse_sector_list` 方法中检测简版板块列表格式（列头为 `名称,代码` 或列数 ≤ 2），对简版格式使用独立的解析逻辑：第 1 列为板块名称（name），第 2 列为板块代码（sector_code），板块类型默认为 CONCEPT
2. THE DCParsingEngine SHALL 对简版格式解析出的 sector_code 进行有效性校验：sector_code 必须以 `BK` 开头，不符合的行跳过并记录 WARNING 日志
3. THE 系统 SHALL 提供数据清理脚本，删除 sector_info 表中 data_source='DC' 且 sector_code 不以 'BK' 开头的所有垃圾记录
4. THE 数据清理脚本 SHALL 记录删除的垃圾记录数量，输出清理报告
5. AFTER 清理完成后，THE DC sector_info 中所有记录的 sector_code SHALL 以 'BK' 开头

### 需求 20：修复 DC 行业板块行情 sector_code 缺少 `.DC` 后缀

**用户故事：** 作为量化交易员，我发现东方财富行业板块行情数据（格式 B：`日期,行业代码,开盘,...`）入库后 sector_code 不带 `.DC` 后缀（如 `BK0420`），而 sector_info 表中对应记录为 `BK0420.DC`，导致 SectorStrengthFilter 查询板块行情时无法匹配行业板块数据，DC 行业板块排名完全失效。

#### 背景

当前数据库中 DC sector_kline 数据存在后缀不一致问题：
- **带 `.DC` 后缀**：1,390,863 条记录（1,030 个板块），来自地区板块行情目录（格式 A）— 正确
- **不带 `.DC` 后缀**：1,896,759 条记录（497 个板块），来自行业板块行情目录（格式 B）— **缺少后缀**
- 这 497 个不带后缀的板块代码，添加 `.DC` 后缀后全部能匹配到 sector_info 表中的行业板块记录

根因：DCParsingEngine 解析行业板块行情 CSV（格式 B）时，"行业代码"列的原始值不带 `.DC` 后缀（如 `BK0420`），解析引擎未自动追加后缀。此问题与需求 18（TDX 历史行情 ZIP 缺少 `.TDX` 后缀）性质完全一致。

#### 验收标准

1. THE DCParsingEngine SHALL 在解析行业板块行情 CSV（格式 B：`日期,行业代码,开盘,...`）时，对解析出的 sector_code 检查是否已包含 `.DC` 后缀，若不包含则自动追加 `.DC` 后缀
2. THE DCParsingEngine SHALL 在解析增量行情 CSV 时同样执行后缀检查和追加逻辑，确保所有 DC 行情解析路径输出的 sector_code 统一包含 `.DC` 后缀
3. THE 系统 SHALL 提供数据清理脚本，删除 sector_kline 表中 data_source='DC' 且 sector_code 不以 '.DC' 结尾的所有记录（即不带后缀的 DC 行业板块行情数据）
4. THE 数据清理脚本 SHALL 记录删除的记录数量，输出清理报告
5. AFTER 清理完成后，用户 SHALL 通过清空 Redis 增量缓存并触发全量导入来重新导入 DC 行业板块行情数据
6. AFTER 重新导入完成后，THE sector_kline 表中 data_source='DC' 的所有记录的 sector_code SHALL 以 '.DC' 结尾，格式与 sector_info 表一致
