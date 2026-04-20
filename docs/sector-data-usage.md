# 板块数据在选股策略中的使用方式

## 概述

智能选股系统通过板块数据实现两个核心功能：

1. **板块面因子评估**：在因子条件编辑器中配置的 `sector_rank`（板块涨幅排名）和 `sector_trend`（板块趋势）因子，用于筛选处于强势板块中的个股
2. **板块分类展示**：在选股结果详情中展示每只股票在东方财富、同花顺、通达信三个数据源的所属板块

本文档聚焦于板块面因子评估的数据流程。

## 数据表结构

板块数据涉及三张数据库表：

| 表名 | 数据库 | 用途 |
|------|--------|------|
| `sector_info` | PostgreSQL | 板块元数据（板块代码、名称、类型、数据源） |
| `sector_constituent` | PostgreSQL | 板块成分股快照（哪些股票属于哪个板块，按交易日存储） |
| `sector_kline` | TimescaleDB | 板块指数日K线行情（开高低收、成交量、涨跌幅） |

### 数据源

系统支持三个数据源，通过策略配置中的 `sector_data_source` 参数选择：

| 代码 | 数据源 | 说明 |
|------|--------|------|
| `DC` | 东方财富 | 默认数据源 |
| `TI` | 同花顺 | |
| `TDX` | 通达信 | |

### 板块类型

通过策略配置中的 `sector_type` 参数选择：

| 类型 | 说明 |
|------|------|
| `CONCEPT` | 概念板块（默认） |
| `INDUSTRY` | 行业板块 |
| `REGION` | 地区板块 |
| `STYLE` | 风格板块 |

## 选股执行时的数据流程

选股执行时，板块数据的加载和使用发生在 `ScreenDataProvider.load_screen_data()` 的步骤 6：

```
选股执行
  ↓
ScreenDataProvider.load_screen_data()
  ├─ 步骤 1-5: 加载K线、技术指标、资金流等数据
  ├─ 步骤 6: 加载板块强势数据 ← 本文档重点
  ├─ 步骤 7: 加载板块分类数据（用于前端展示）
  └─ 返回 stocks_data 字典
  ↓
ScreenExecutor._execute()
  ├─ 因子评估（sector_rank、sector_trend 等）
  └─ 信号生成（SECTOR_STRONG 等）
```

### 步骤 6 详细流程

```
SectorStrengthFilter.compute_sector_ranks()
  │
  ├─ 1. 查询 sector_info 表获取板块元数据
  │     → 按 data_source + sector_type 过滤
  │     → 得到板块代码列表
  │
  ├─ 2. 查询 sector_kline 表获取最近 N 天日K线
  │     → 先查 MAX(time) 获取表中最新交易日
  │     → 从最新交易日往前取 period 天（默认5天）的K线
  │     → 同时取至少20天数据用于均线计算
  │
  ├─ 3. 计算每个板块的累计涨跌幅
  │     → 优先使用 change_pct 字段累加
  │     → change_pct 全为 NULL 时使用收盘价 fallback
  │
  ├─ 4. 按累计涨跌幅降序排列，分配排名
  │     → rank=1 为涨幅最大的板块
  │
  └─ 5. 判断多头趋势
        → 计算5日均线和20日均线
        → MA5 > MA20 则 is_bullish=True

SectorStrengthFilter.map_stocks_to_sectors()
  │
  └─ 查询 sector_constituent 表
        → 获取最新 trade_date 的成分股数据
        → 构建 symbol → [sector_code, ...] 映射

SectorStrengthFilter.filter_by_sector_strength()
  │
  └─ 为每只股票写入因子值
        → 查找该股票所属板块中排名最高（rank 值最小）的板块
        → 写入 sector_rank (int)：该板块的排名
        → 写入 sector_trend (bool)：该板块是否多头趋势
        → 写入 sector_name (str)：该板块的名称
```

### 因子评估

因子条件编辑器中配置的板块面因子在 `StrategyEngine` 中评估：

| 因子 | 类型 | 评估方式 | 示例 |
|------|------|----------|------|
| `sector_rank` | 绝对值比较 | `sector_rank <= threshold` | `sector_rank <= 15` → 板块排名前15 |
| `sector_trend` | 布尔值 | `sector_trend == True` | 板块处于多头趋势 |

### 信号生成

当因子评估通过后，`ScreenExecutor` 生成 `SECTOR_STRONG` 类别的信号，归属于"板块面"维度。

## 配置参数

板块面因子的行为受策略配置中 `SectorScreenConfig` 控制：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `sector_data_source` | `"DC"` | 数据源（DC/TI/TDX） |
| `sector_type` | `"CONCEPT"` | 板块类型（CONCEPT/INDUSTRY/REGION/STYLE） |
| `sector_period` | `5` | 涨跌幅计算周期（天） |
| `sector_top_n` | `30` | 排名阈值（用于日志，实际写入完整排名） |

这些参数在策略模板的 `config.sector_config` 中配置，也可在因子条件编辑器的板块面因子中通过数据源和板块类型下拉框选择。

## 数据缺失时的降级行为

系统在板块数据缺失时有多层降级保护，确保选股主流程不中断：

### 降级场景一览

| 场景 | 系统行为 | 对选股结果的影响 |
|------|----------|-----------------|
| `sector_kline` 表完全无数据 | `compute_sector_ranks()` 返回空列表 | 所有股票 `sector_rank=None`，板块面因子不通过 |
| `sector_kline` 表有数据但不是最新的 | **使用表中最新交易日的数据计算排名** | 排名基于旧数据，可能不反映当前市场状态 |
| `sector_constituent` 表无数据 | `map_stocks_to_sectors()` 返回空字典 | 所有股票无板块映射，`sector_rank=None` |
| 数据库会话不可用 | 降级为默认值 | `sector_rank=None`，`sector_trend=False` |
| 任何异常 | `try/except` 捕获，记录 WARNING 日志 | 降级为默认值，选股继续 |

### 关键行为：数据过期时的静默使用

**这是需要特别注意的点。** 当板块K线数据缺失最近若干天时：

1. `_load_sector_klines()` 查询 `MAX(time)` 获取表中最新交易日
2. 如果最新交易日是一周前，系统会使用一周前的数据计算排名
3. **系统不会报错或告警**，排名结果看起来正常，但反映的是过时的市场状态

```
示例：
  今天是 2026-04-20（周一）
  sector_kline 表最新数据是 2026-04-11（上周五之前）
  
  系统行为：
  → MAX(time) = 2026-04-11
  → 取 2026-04-07 ~ 2026-04-11 的5天K线
  → 基于这5天数据计算板块排名
  → 排名结果反映的是 4/7~4/11 的市场状态，不是当前状态
```

## 数据同步

板块数据通过 Celery 异步任务同步，定义在 `app/tasks/sector_sync.py`：

| 任务 | 说明 | 队列 |
|------|------|------|
| `sector_import_full` | 全量导入（板块列表 → 成分股 → K线） | `data_sync` |
| `sector_import_incremental` | 增量导入（仅处理新数据） | `data_sync` |

### 手动触发数据同步

```bash
# 全量导入所有数据源
celery -A app.core.celery_app call app.tasks.sector_sync.sector_import_full

# 指定数据源导入
celery -A app.core.celery_app call app.tasks.sector_sync.sector_import_full \
  --args='[["DC"]]'

# 增量导入
celery -A app.core.celery_app call app.tasks.sector_sync.sector_import_incremental
```

### 数据新鲜度检查

可通过以下 SQL 查询检查数据是否最新：

```sql
-- 检查板块K线最新交易日
SELECT data_source, MAX(time) AS latest_date
FROM sector_kline
WHERE freq = '1d'
GROUP BY data_source;

-- 检查成分股最新交易日
SELECT data_source, MAX(trade_date) AS latest_date
FROM sector_constituent
GROUP BY data_source;

-- 检查最近7天是否有数据
SELECT data_source, COUNT(DISTINCT time) AS days_count
FROM sector_kline
WHERE freq = '1d' AND time >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY data_source;
```

## 相关代码文件

| 文件 | 职责 |
|------|------|
| `app/services/screener/sector_strength.py` | `SectorStrengthFilter` — 板块排名计算、成分股映射、因子写入 |
| `app/services/screener/screen_data_provider.py` | 步骤 6 调用 `SectorStrengthFilter`，步骤 7 加载板块分类 |
| `app/services/screener/screen_executor.py` | 信号生成（`SECTOR_STRONG`）和因子模块映射 |
| `app/services/screener/factor_registry.py` | `sector_rank` 和 `sector_trend` 因子定义 |
| `app/models/sector.py` | `SectorInfo`、`SectorConstituent`、`SectorKline` ORM 模型 |
| `app/core/schemas.py` | `SectorScreenConfig` 配置类 |
| `app/tasks/sector_sync.py` | 板块数据同步 Celery 任务 |
