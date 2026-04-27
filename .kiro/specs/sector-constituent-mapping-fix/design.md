# 设计文档：板块成分股映射修复

## 概述

本设计文档针对板块成分股映射的三层问题（symbol 格式不一致、trade_date 查询逻辑错误、回测历史成分查询）提供技术修复方案。

核心修改集中在 3 个文件：
- `app/services/screener/sector_strength.py`：修复 `map_stocks_to_sectors()` 的查询逻辑和 symbol 格式
- `app/services/screener/screen_data_provider.py`：修复 `_build_industry_map()` 和 `_load_sector_classifications()` 的查询逻辑和 symbol 格式
- `app/api/v1/sector.py`：修复覆盖率统计和 `type_stock_count_stmt` 的查询逻辑
- `app/services/data_engine/sector_repository.py`：修复 `get_constituents()`、`get_sectors_by_stock()`、`browse_sector_constituent()` 的查询逻辑和 symbol 格式
- `app/services/backtest_factor_data_loader.py`：修复 `_load_sector_data()` 的 symbol 格式和 trade_date 查询

---

## 架构

### 数据源模式分类

```
┌─────────────────────────────────────────────────────────┐
│                  sector_constituent 表                    │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  增量数据源   │  │  增量数据源   │  │  快照数据源   │   │
│  │  DC           │  │  TDX          │  │  THS/TI/CI   │   │
│  │              │  │              │  │              │   │
│  │ trade_date = │  │ trade_date = │  │ trade_date = │   │
│  │ 调入日期     │  │ 调入日期     │  │ 导入日期     │   │
│  │              │  │              │  │              │   │
│  │ 查询方式:    │  │ 查询方式:    │  │ 查询方式:    │   │
│  │ <= 目标日期  │  │ <= 目标日期  │  │ = 最新日期   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  _strip_market_suffix │
              │  "000001.SZ" → "000001" │
              └──────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  stock_sector_map     │
              │  {"000001": ["BK0817.DC", ...]} │
              └──────────────────────┘
```

### 受影响的文件清单

| 文件路径 | 修改类型 | 对应需求 |
|---------|---------|---------|
| `app/services/screener/sector_strength.py` | 修改 | 需求 1, 2 |
| `app/services/screener/screen_data_provider.py` | 修改 | 需求 1, 2, 7 |
| `app/services/backtest_factor_provider.py` | 修改 | 需求 3 |
| `app/services/backtest_factor_data_loader.py` | 修改 | 需求 3, 6 |
| `app/services/data_engine/sector_repository.py` | 修改 | 需求 5 |
| `app/api/v1/sector.py` | 修改 | 需求 4 |

---

## 组件设计

### 组件 1：数据源模式常量（需求 2）

在 `app/services/screener/sector_strength.py` 中新增模块级常量：

```python
# 增量数据源：trade_date 记录股票调入板块的日期，需用 <= 累积查询
_INCREMENTAL_SOURCES: set[str] = {"DC", "TDX", "TI", "CI"}

# 快照数据源：trade_date 记录导入日期，用 = 精确查询
_SNAPSHOT_SOURCES: set[str] = {"THS"}
```

同时在 `screen_data_provider.py` 中导入使用。

### 组件 2：`map_stocks_to_sectors()` 修复（需求 1, 2）

位置：`app/services/screener/sector_strength.py` 第 185-277 行

**修改点 1：查询条件根据数据源模式切换**

```python
# 修改前（第 248-254 行）
stmt = (
    select(SectorConstituent)
    .where(
        SectorConstituent.data_source == data_source,
        SectorConstituent.trade_date == trade_date,  # 精确匹配
        SectorConstituent.sector_code.in_(valid_sector_codes),
    )
)

# 修改后
if data_source in _INCREMENTAL_SOURCES:
    # 增量数据源：累积查询截至目标日期的全部成分股
    stmt = (
        select(SectorConstituent)
        .where(
            SectorConstituent.data_source == data_source,
            SectorConstituent.trade_date <= trade_date,
            SectorConstituent.sector_code.in_(valid_sector_codes),
        )
    )
else:
    # 快照数据源：精确匹配最新日期
    stmt = (
        select(SectorConstituent)
        .where(
            SectorConstituent.data_source == data_source,
            SectorConstituent.trade_date == trade_date,
            SectorConstituent.sector_code.in_(valid_sector_codes),
        )
    )
```

**修改点 2：symbol 格式转换**

```python
# 修改前（第 260-262 行）
mapping: dict[str, list[str]] = defaultdict(list)
for c in constituents:
    mapping[c.symbol].append(c.sector_code)

# 修改后
from app.services.screener.screen_data_provider import _strip_market_suffix

mapping: dict[str, list[str]] = defaultdict(list)
for c in constituents:
    bare_symbol = _strip_market_suffix(c.symbol)
    mapping[bare_symbol].append(c.sector_code)
```

**修改点 3：增量数据源去重**

增量查询可能返回同一股票在同一板块的多条记录（不同调入日期），需要去重：

```python
mapping: dict[str, list[str]] = defaultdict(list)
for c in constituents:
    bare_symbol = _strip_market_suffix(c.symbol)
    if c.sector_code not in mapping[bare_symbol]:
        mapping[bare_symbol].append(c.sector_code)
```

### 组件 3：`_build_industry_map()` 修复（需求 1, 2）

位置：`app/services/screener/screen_data_provider.py` 第 872-964 行

**修改点 1：查询条件根据数据源模式切换**

```python
# 修改前（第 938-945 行）
stmt = (
    select(SectorConstituent)
    .where(
        SectorConstituent.data_source == data_source,
        SectorConstituent.trade_date == latest_date,
        SectorConstituent.sector_code.in_(valid_sector_codes),
    )
)

# 修改后
if data_source in _INCREMENTAL_SOURCES:
    stmt = (
        select(SectorConstituent)
        .where(
            SectorConstituent.data_source == data_source,
            SectorConstituent.trade_date <= latest_date,
            SectorConstituent.sector_code.in_(valid_sector_codes),
        )
    )
else:
    stmt = (
        select(SectorConstituent)
        .where(
            SectorConstituent.data_source == data_source,
            SectorConstituent.trade_date == latest_date,
            SectorConstituent.sector_code.in_(valid_sector_codes),
        )
    )
```

**修改点 2：symbol 格式转换**

```python
# 修改前（第 951-954 行）
mapping: dict[str, str] = {}
for c in constituents:
    if c.symbol not in mapping:
        mapping[c.symbol] = c.sector_code

# 修改后
mapping: dict[str, str] = {}
for c in constituents:
    bare = _strip_market_suffix(c.symbol)
    if bare not in mapping:
        mapping[bare] = c.sector_code
```

### 组件 4：`_load_sector_classifications()` 修复（需求 1, 2）

位置：`app/services/screener/screen_data_provider.py` 第 1614-1710 行

**修改点 1：symbols 格式适配**

`_load_sector_classifications` 接收的 `symbols` 是纯数字格式，但 `SectorConstituent.symbol` 是带后缀格式。需要改为在查询结果中做格式转换，而非在查询条件中转换（避免全表扫描）。

```python
# 修改前（第 1654-1659 行）
constituents_stmt = (
    select(SectorConstituent)
    .where(
        SectorConstituent.symbol.in_(symbols),  # 纯数字 vs 带后缀，永远匹配不到
        SectorConstituent.trade_date == trade_date,
        SectorConstituent.data_source.in_(_DATA_SOURCES),
    )
)

# 修改后：查询全部成分股，在 Python 层做 symbol 过滤
# 对增量数据源使用 <= 查询
symbols_set = set(symbols)
all_stmts = []
for ds in _DATA_SOURCES:
    if ds in _INCREMENTAL_SOURCES:
        all_stmts.append(
            select(SectorConstituent).where(
                SectorConstituent.data_source == ds,
                SectorConstituent.trade_date <= trade_date,
            )
        )
    else:
        all_stmts.append(
            select(SectorConstituent).where(
                SectorConstituent.data_source == ds,
                SectorConstituent.trade_date == trade_date,
            )
        )
# 合并查询结果，在 Python 层按 _strip_market_suffix 过滤
```

**修改点 2：结果映射中的 symbol 格式转换**

```python
# 修改前（第 1699-1706 行）
for c in constituents:
    if c.symbol not in classifications:
        classifications[c.symbol] = {src: [] for src in _DATA_SOURCES}
    ...
    source_list = classifications[c.symbol][c.data_source]

# 修改后
for c in constituents:
    bare = _strip_market_suffix(c.symbol)
    if bare not in symbols_set:
        continue  # 不在目标股票列表中，跳过
    if bare not in classifications:
        classifications[bare] = {src: [] for src in _DATA_SOURCES}
    ...
    source_list = classifications[bare][c.data_source]
```

### 组件 5：回测历史板块成分查询（需求 3）

位置：`app/services/backtest_factor_data_loader.py` 和 `app/services/backtest_factor_provider.py`

**数据加载层修改**

`_load_sector_data()` 对增量数据源加载全部成分股记录（不限日期范围），构建可按日期查询的映射：

```python
# 增量数据源：加载全部记录，保留 trade_date 信息
# 构建 {bare_symbol: [(trade_date, sector_code), ...]} 映射
# 回测时按 trade_date <= 回测日期 过滤
```

**因子提供器层修改**

`_compute_sector_strength()` 接受 `trade_date` 参数，对增量数据源过滤 `trade_date <= 回测日期` 的记录：

```python
def _compute_sector_strength(stocks_data, trade_date, ...):
    # 对增量数据源：从预加载数据中过滤 entry_date <= trade_date 的记录
    # 对快照数据源：使用全部记录（无法回溯）
```

### 组件 6：覆盖率统计修正（需求 4）

位置：`app/api/v1/sector.py` 第 195-246 行

```python
# 修改前（第 219-238 行）
sectors_with_stmt = (
    select(func.count(func.distinct(SectorConstituent.sector_code)))
    .where(
        SectorConstituent.data_source == ds,
        SectorConstituent.trade_date == latest_date,  # 仅最新日
    )
)

# 修改后
if ds in _INCREMENTAL_SOURCES:
    sectors_with_stmt = (
        select(func.count(func.distinct(SectorConstituent.sector_code)))
        .where(
            SectorConstituent.data_source == ds,
            SectorConstituent.trade_date <= latest_date,  # 累积
        )
    )
else:
    sectors_with_stmt = (
        select(func.count(func.distinct(SectorConstituent.sector_code)))
        .where(
            SectorConstituent.data_source == ds,
            SectorConstituent.trade_date == latest_date,  # 精确
        )
    )
# stocks_stmt 同理
```

### 组件 7：SectorRepository 查询方法修复（需求 5）

位置：`app/services/data_engine/sector_repository.py`

三个方法需要同样的双模式查询修复：

**`get_constituents()` (line 128)**

```python
# 修改前
SectorConstituent.trade_date == trade_date,

# 修改后
from app.services.screener.sector_strength import _INCREMENTAL_SOURCES

if data_source in _INCREMENTAL_SOURCES:
    stmt = stmt.where(SectorConstituent.trade_date <= trade_date)
else:
    stmt = stmt.where(SectorConstituent.trade_date == trade_date)
```

增量查询需要去重：添加 `.distinct(SectorConstituent.symbol)` 或在结果中去重。

**`get_sectors_by_stock()` (line 174)**

同样的双模式修复，额外需要 symbol 格式适配：

```python
# 修改前
SectorConstituent.symbol == symbol,

# 修改后：支持纯数字和带后缀两种输入格式
if "." not in symbol:
    # 纯数字格式，需匹配 .SH/.SZ/.BJ 后缀
    symbol_variants = [f"{symbol}.SH", f"{symbol}.SZ", f"{symbol}.BJ"]
    stmt = stmt.where(SectorConstituent.symbol.in_(symbol_variants))
else:
    stmt = stmt.where(SectorConstituent.symbol == symbol)
```

**`browse_sector_constituent()` (line 618)**

同样的双模式修复。

### 组件 8：回测数据加载器 symbol 格式修复（需求 6）

位置：`app/services/backtest_factor_data_loader.py`

**`_load_sector_data()` stock_sector_map 修复 (line 185-190)**

```python
# 修改前
rows = session.execute(text("""
    SELECT symbol, sector_code FROM sector_constituent
    WHERE data_source = :ds
"""), {"ds": ds}).fetchall()
ssm: dict[str, list[str]] = {}
for r in rows:
    ssm.setdefault(r[0], []).append(r[1])  # r[0] = "000001.SZ"

# 修改后：添加 _strip_suffix + trade_date 字段
rows = session.execute(text("""
    SELECT DISTINCT symbol, sector_code FROM sector_constituent
    WHERE data_source = :ds
"""), {"ds": ds}).fetchall()
ssm: dict[str, list[str]] = {}
for r in rows:
    bare = _strip_suffix(r[0])
    if r[1] not in ssm.get(bare, []):
        ssm.setdefault(bare, []).append(r[1])
```

**`_load_sector_data()` industry_map 修复 (line 202-211)**

```python
# 修改前
result["industry_map"] = {r[0]: r[1] for r in rows}  # r[0] = "000001.SZ"

# 修改后
result["industry_map"] = {_strip_suffix(r[0]): r[1] for r in rows}
```

### 组件 9：板块分类查询性能优化（需求 7）

位置：`app/services/screener/screen_data_provider.py` `_load_sector_classifications()`

**方案：数据库端 symbol 格式适配**

不加载全部记录到 Python，而是在查询条件中生成带后缀的 symbol 列表：

```python
# 生成带后缀的 symbol 变体
suffixed_symbols = []
for s in symbols:
    if "." not in s:
        suffixed_symbols.extend([f"{s}.SH", f"{s}.SZ", f"{s}.BJ"])
    else:
        suffixed_symbols.append(s)

# 按数据源分别查询，各自使用正确的 trade_date 条件
for ds in _DATA_SOURCES:
    ds_latest = await _get_latest_date_for_source(pg_session, ds)
    if ds_latest is None:
        continue
    if ds in _INCREMENTAL_SOURCES:
        stmt = select(SectorConstituent).where(
            SectorConstituent.symbol.in_(suffixed_symbols),
            SectorConstituent.data_source == ds,
            SectorConstituent.trade_date <= ds_latest,
        )
    else:
        stmt = select(SectorConstituent).where(
            SectorConstituent.symbol.in_(suffixed_symbols),
            SectorConstituent.data_source == ds,
            SectorConstituent.trade_date == ds_latest,
        )
```

**`_DATA_SOURCES` 扩展**

```python
# 修改前
_DATA_SOURCES = ["DC", "TI", "TDX"]

# 修改后：加入 THS（覆盖率最高）
_DATA_SOURCES = ["DC", "THS", "TDX", "TI"]
```

---

## 数据模型

### 查询模式对照表

| 场景 | 增量数据源（DC/TDX） | 快照数据源（THS/TI/CI） |
|------|---------------------|----------------------|
| 智能选股（实时） | `trade_date <= NOW()` | `trade_date = MAX(trade_date)` |
| 策略回测（历史） | `trade_date <= 回测日期` | `trade_date = MAX(trade_date)` |
| 覆盖率统计 | `trade_date <= MAX(trade_date)` | `trade_date = MAX(trade_date)` |

### 预期覆盖率修正

| 数据源 | 修复前（最新日精确查询） | 修复后（累积查询 + symbol 转换） |
|--------|----------------------|-------------------------------|
| DC | 535 板块 / 0 股票匹配 | 1020 板块 / 5738 股票 ✓ |
| THS | ~1511 板块 / 0 股票匹配 | 1511 板块 / 13935 股票 ✓ |
| TDX | 6 板块 / 0 股票匹配 | 481 板块 / 6291 股票 ✓ |
| TI | 5 板块 / 6 股票 | 31 板块 / 5201 股票 ✓ |
| CI | 3 板块 / 3 股票 | 30 板块 / 5201 股票 ✓ |

---

## 性能考量

### 增量查询的数据量

增量查询（`trade_date <=`）会返回更多记录：

| 数据源 | 精确查询记录数 | 累积查询记录数 | 增幅 |
|--------|-------------|-------------|------|
| DC | ~52,000 | ~4,412,450 | ~85x |
| TDX | ~100 | ~1,430,856 | ~14,000x |

**优化策略：**

1. `map_stocks_to_sectors()` 只需要 `DISTINCT (symbol, sector_code)`，不需要全部记录。对增量数据源使用 `SELECT DISTINCT symbol, sector_code` 替代 `SELECT *`，大幅减少数据传输量。

2. `_load_sector_classifications()` 同样使用 `SELECT DISTINCT` 去重。

3. 回测数据加载在初始化阶段一次性完成，不影响逐日计算性能。

```python
# 优化后的增量查询
stmt = (
    select(
        SectorConstituent.symbol,
        SectorConstituent.sector_code,
    ).distinct()
    .where(
        SectorConstituent.data_source == data_source,
        SectorConstituent.trade_date <= trade_date,
        SectorConstituent.sector_code.in_(valid_sector_codes),
    )
)
```

---

## 测试策略

### 单元测试

| 测试文件 | 测试内容 | 对应需求 |
|---------|---------|---------|
| `tests/services/test_sector_strength.py` | `map_stocks_to_sectors` 增量查询返回全部成分股 | 需求 2 |
| `tests/services/test_sector_strength.py` | `map_stocks_to_sectors` symbol 格式转换正确 | 需求 1 |
| `tests/services/test_sector_strength.py` | 增量查询结果去重（同一股票同一板块不重复） | 需求 2 |
| `tests/services/test_screen_data_provider.py` | `_build_industry_map` 增量查询 + symbol 转换 | 需求 1, 2 |
| `tests/services/test_screen_data_provider.py` | `_load_sector_classifications` 增量查询 + symbol 过滤 | 需求 1, 2 |
| `tests/services/test_backtest_factor_provider.py` | 回测历史板块成分按日期过滤 | 需求 3 |
| `tests/api/test_sector.py` | 覆盖率统计使用累积查询 | 需求 4 |

### 集成测试

| 测试场景 | 验证内容 |
|---------|---------|
| DC 数据源选股 | 板块因子 `sector_rank` 非 None 的股票数 > 5000 |
| TDX 数据源选股 | 板块因子 `sector_rank` 非 None 的股票数 > 5000 |
| THS 数据源选股 | 板块因子 `sector_rank` 非 None 的股票数 > 5000 |
| 回测 DC 数据源 | 2025-06-01 的成分股不包含 2025-06-01 之后调入的股票 |
