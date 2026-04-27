# 需求文档：板块成分股映射修复

## 简介

当前智能选股系统的板块面因子（`sector_rank`、`sector_trend`）对所有股票无法生效，经过数据库实际数据分析，发现存在三层问题：

### 问题 1：symbol 格式不一致（影响所有数据源，覆盖率 0%）

`sector_constituent` 表中的 `symbol` 字段存储的是 Tushare 格式（带市场后缀，如 `"000001.SZ"`），而选股流程中 `stocks_data` 的 key 使用的是 `stock_info` 表的纯数字格式（`"000001"`）。

`SectorStrengthFilter.filter_by_sector_strength()` 中 `stock_sector_map.get(symbol)` 用纯数字格式去查带后缀格式的映射，匹配率为 0%。

**数据库验证：**
```
stock_info.symbol:            "000001"（纯数字）
sector_constituent.symbol:    "000001.SZ"（带后缀）
直接匹配覆盖率:              0/5330 = 0%
去后缀匹配覆盖率（DC/THS）:  5330/5330 = 100%
```

### 问题 2：trade_date 语义不一致导致查询逻辑错误（影响 DC/TDX 等增量数据源）

`sector_constituent.trade_date` 在不同数据源中有不同语义：

| 数据源 | trade_date 语义 | 存储模式 | 查询方式 |
|--------|----------------|---------|---------|
| THS | 导入日期（全量快照） | 同一板块所有成分股共享同一 trade_date | `WHERE trade_date = 最新日期` ✓ |
| DC | 股票调入板块的日期 | 同一板块不同股票有不同 trade_date | `WHERE trade_date = 最新日期` ✗ |
| TDX | 股票调入板块的日期 | 同一板块不同股票有不同 trade_date | `WHERE trade_date = 最新日期` ✗ |
| TI | 股票纳入行业的日期（从1990年起） | 同一行业不同股票有不同 trade_date | `WHERE trade_date = 最新日期` ✗ |
| CI | 股票纳入行业的日期（从2003年起） | 同一行业不同股票有不同 trade_date | `WHERE trade_date = 最新日期` ✗ |

当前代码 `SectorStrengthFilter._get_latest_constituent_date()` 查询 `MAX(trade_date)` 后用 `WHERE trade_date = 最新日期` 过滤，对于 DC/TDX 这种增量数据源，只能查到最新一天调入的少量股票，而非该板块的全部成分股。

**数据库验证（DC BK0817 板块）：**
```
trade_date = '2026-04-27' 查询:  26 只股票
trade_date <= '2026-04-27' 查询: 2419 只股票（全部成分股）
```

**数据库验证（TDX 全量）：**
```
trade_date = '2026-04-27': 6 个板块, 51 只股票
trade_date <= '2026-04-27': 481 个板块, 6291 只股票
```

### 问题 3：回测需要知道股票纳入板块的时间点

对于策略回测，需要知道某只股票在某个历史日期是否属于某个板块。DC/TDX 的增量存储模式（`trade_date` = 调入日期）天然支持这个需求：`WHERE trade_date <= 回测日期` 即可获取截至该日期的全部成分股。但 THS 的全量快照模式只有一个日期，无法回溯历史。

### 解决方案概述

采用**双模式查询策略**：

1. **智能选股（实时）**：对增量数据源（DC/TDX/TI/CI）使用 `trade_date <= 当前日期` 累积查询获取全部成分股；对快照数据源（THS）保持 `trade_date = 最新日期` 查询
2. **策略回测**：对增量数据源使用 `trade_date <= 回测日期` 获取截至该日期的成分股；对快照数据源使用最新快照（无法回溯历史，但覆盖率高）
3. **symbol 格式统一**：在构建映射时对 `sector_constituent.symbol` 做 `_strip_market_suffix()` 转换

## 术语表

- **增量数据源**：`trade_date` 记录股票调入板块的日期，同一板块不同股票有不同日期（DC、TDX、TI、CI）
- **快照数据源**：`trade_date` 记录导入日期，同一板块所有成分股共享同一日期（THS）
- **SectorConstituent**：板块成分股表，PostgreSQL 表 `sector_constituent`
- **SectorStrengthFilter**：板块强势筛选器，位于 `app/services/screener/sector_strength.py`
- **stock_sector_map**：股票→板块映射字典，由 `map_stocks_to_sectors()` 构建
- **_strip_market_suffix**：代码格式转换函数，已在 `screener-data-alignment-fix` 中实现

## 需求

---

### 需求 1：板块成分股映射的 symbol 格式对齐

**用户故事：** 作为量化交易员，我希望选股系统能正确将股票匹配到所属板块，以便板块面因子能参与选股评估。

#### 验收标准

1. THE `SectorStrengthFilter.map_stocks_to_sectors()` 方法 SHALL 在构建 `symbol → [sector_code]` 映射时，将 `SectorConstituent.symbol` 转换为纯数字格式（使用 `_strip_market_suffix()`），确保与 `stocks_data` 的 key 格式一致。
2. THE `ScreenDataProvider._load_sector_classifications()` 方法 SHALL 在构建板块分类映射时，将 `SectorConstituent.symbol` 转换为纯数字格式。
3. THE `ScreenDataProvider._build_industry_map()` 方法 SHALL 在构建行业映射时，将 `SectorConstituent.symbol` 转换为纯数字格式。
4. WHEN 格式转换后，DC 和 THS 数据源的股票匹配率 SHALL 从 0% 提升到接近 100%。

---

### 需求 2：增量数据源的累积查询模式

**用户故事：** 作为量化交易员，我希望使用 DC 或 TDX 数据源时能获取板块的全部成分股（而非仅当天新增的），以便板块面因子的覆盖率完整。

#### 验收标准

1. THE `SectorStrengthFilter.map_stocks_to_sectors()` 方法 SHALL 识别数据源的存储模式：对增量数据源（DC、TDX）使用 `trade_date <= 目标日期` 累积查询，对快照数据源（THS、TI、CI）使用 `trade_date = 最新日期` 精确查询。
2. THE `SectorStrengthFilter` SHALL 维护一个数据源模式映射常量：`_INCREMENTAL_SOURCES = {"DC", "TDX"}`，`_SNAPSHOT_SOURCES = {"THS", "TI", "CI"}`。
3. WHEN 使用 DC 数据源且目标日期为 2026-04-27 时，THE `map_stocks_to_sectors()` SHALL 查询 `trade_date <= '2026-04-27'` 的所有记录，返回该板块截至该日期的全部成分股。
4. WHEN 使用 THS 数据源时，THE `map_stocks_to_sectors()` SHALL 保持现有行为，查询 `trade_date = 最新日期` 的记录。
5. THE `ScreenDataProvider._load_sector_classifications()` 方法 SHALL 同样根据数据源模式选择累积查询或精确查询。
6. THE `ScreenDataProvider._build_industry_map()` 方法 SHALL 同样根据数据源模式选择累积查询或精确查询。

---

### 需求 3：回测环境的历史板块成分查询

**用户故事：** 作为量化交易员，我希望回测引擎在每个历史交易日能获取截至该日期的板块成分股，以便回测中的板块面因子反映历史真实情况。

#### 验收标准

1. THE `BacktestFactorProvider._compute_sector_strength()` 方法 SHALL 接受 `trade_date` 参数，对增量数据源使用 `trade_date <= 回测日期` 查询截至该日期的成分股。
2. THE `BacktestTask` 数据加载 SHALL 对增量数据源（DC/TDX）加载回测日期范围内的全部成分股记录，构建 `{symbol: {date_str: [sector_code, ...]}}` 的时间序列映射。
3. WHEN 回测日期为 2025-06-01 时，THE BacktestEngine SHALL 使用截至 2025-06-01 的成分股数据，不包含 2025-06-01 之后调入的股票。
4. WHEN 使用快照数据源（THS）时，THE BacktestEngine SHALL 使用最新快照数据（无法回溯历史），并在日志中记录"快照数据源不支持历史回溯"警告。

---

### 需求 4：板块数据源覆盖率统计与前端展示修正

**用户故事：** 作为量化交易员，我希望前端板块数据源选择器显示的覆盖率统计能准确反映实际可用的成分股数量，以便选择数据完整的数据源。

#### 验收标准

1. THE `GET /api/v1/sectors/sources` 接口 SHALL 对增量数据源（DC/TDX）使用 `trade_date <= 最新日期` 累积查询统计板块数和股票数，而非仅统计最新日期的记录。
2. THE `GET /api/v1/sectors/sources` 接口中的 `type_stock_count_stmt`（按板块类型分组统计）SHALL 同样根据数据源模式切换查询条件。
3. THE 前端板块数据源选择器 SHALL 显示修正后的覆盖率统计，格式为"数据源名称（板块数 / 股票数）"。
4. WHEN 增量数据源的累积覆盖率低于 50% 时，THE 前端 SHALL 显示警告图标（⚠️）。
5. WHEN 快照数据源的数据超过 5 个交易日未更新时，THE 前端 SHALL 显示"数据过期"提示。

---

### 需求 5：SectorRepository 查询方法修复

**用户故事：** 作为量化交易员，我希望板块成分股浏览、按股票查板块等 API 接口能返回完整的数据，以便在前端查看板块成分时不会遗漏大量股票。

#### 验收标准

1. THE `SectorRepository.get_constituents()` 方法 SHALL 对增量数据源使用 `trade_date <= 目标日期` 累积查询，返回该板块截至目标日期的全部成分股。
2. THE `SectorRepository.get_sectors_by_stock()` 方法 SHALL 对增量数据源使用 `trade_date <= 目标日期` 累积查询，返回该股票截至目标日期所属的全部板块。
3. THE `SectorRepository.get_sectors_by_stock()` 方法 SHALL 在查询前对传入的 `symbol` 参数进行格式适配：若为纯数字格式，需同时匹配 `.SH`/`.SZ`/`.BJ` 后缀格式。
4. THE `SectorRepository.browse_sector_constituent()` 方法 SHALL 对增量数据源使用 `trade_date <= 目标日期` 累积查询。
5. 以上三个方法 SHALL 对增量查询结果进行去重（同一股票在同一板块只返回一条记录）。

---

### 需求 6：回测数据加载器 symbol 格式修复

**用户故事：** 作为量化交易员，我希望回测引擎加载的板块成分股映射和行业映射使用正确的 symbol 格式，以便回测中的板块面因子能正确匹配到股票。

#### 验收标准

1. THE `backtest_factor_data_loader._load_sector_data()` 方法 SHALL 在构建 `stock_sector_map` 时，对 `sector_constituent.symbol` 做 `_strip_suffix()` 转换为纯数字格式。
2. THE `backtest_factor_data_loader._load_sector_data()` 方法 SHALL 在构建 `industry_map` 时，对 `sector_constituent.symbol` 做 `_strip_suffix()` 转换为纯数字格式。
3. THE `backtest_factor_data_loader._load_sector_data()` 方法 SHALL 在查询成分股时包含 `trade_date` 字段，以支持回测按历史日期过滤。
4. THE `backtest_factor_data_loader._load_sector_data()` 方法 SHALL 对增量数据源不限制 `trade_date` 范围（加载全部记录），对快照数据源查询最新日期。

---

### 需求 7：板块分类查询性能优化与数据源扩展

**用户故事：** 作为量化交易员，我希望板块分类数据加载不会因为累积查询导致性能问题，同时能覆盖 THS 等高覆盖率数据源。

#### 验收标准

1. THE `_load_sector_classifications()` 方法 SHALL 使用数据库端 symbol 格式适配（生成带后缀的 symbol 列表传入 `IN` 条件），而非加载全部记录后在 Python 层过滤，避免增量数据源的百万级记录全量加载。
2. THE `_load_sector_classifications()` 方法 SHALL 对每个数据源分别查询各自的最新日期，而非使用跨数据源的单一 `MAX(trade_date)`。
3. THE `_load_sector_classifications()` 方法 SHALL 将 `_DATA_SOURCES` 扩展为包含 THS，格式为 `["DC", "THS", "TDX", "TI"]`，以利用 THS 的高覆盖率数据。
4. THE `_build_industry_map()` 方法的数据源回退路径 SHALL 根据回退到的数据源模式（增量/快照）选择正确的查询条件。

