# 需求文档：申万/中信行业 L2/L3 成分股数据导入

## 简介

当前申万行业（TI）和中信行业（CI）的板块成分股数据仅导入了一级行业（L1）的成分股，二级行业（L2）和三级行业（L3）的成分股数据在 Tushare API 导入时被丢弃。

### 问题分析

**申万行业（TI）：**

Tushare `index_member_all` API 返回的每条记录包含 `l1_code`、`l2_code`、`l3_code` 三个字段，分别对应该股票所属的一级、二级、三级行业代码。当前导入注册表（`tushare_registry.py` 第 2388 行）只映射了 `l1_code` → `sector_code`，L2/L3 字段被丢弃。

```
sector_info 表：359 个板块（28 L1 + 104 L2 + 227 L3）— 分类数据完整
sector_constituent 表：仅 31 个 L1 板块有成分股（5201 只股票）— L2/L3 成分股缺失
前端显示：TI (31/359 板块) ⚠️
```

**中信行业（CI）：**

Tushare `ci_index_member` API 同样返回 `l1_code`、`l2_code`、`l3_code`，导入注册表（第 2454 行）也只映射了 `l1_code`。此外，CI 没有板块分类导入接口，`sector_info` 表中无 CI 数据。

```
sector_info 表：0 个板块 — 分类数据完全缺失
sector_constituent 表：仅 30 个 L1 板块有成分股（5201 只股票）— L2/L3 成分股缺失
前端显示：CI (30/0 板块) ⚠️
```

### 影响范围

- 用户选择 TI 或 CI 数据源时，只能使用 L1 一级行业分类（31/30 个板块），无法使用更细粒度的 L2/L3 行业分类
- 行业相对值计算（`_build_industry_map`）使用 DC 数据源的 INDUSTRY 类型板块，不受此问题影响
- 板块涨幅排名和板块趋势因子在 TI/CI 数据源下仅基于 L1 行业计算

## 术语表

- **L1**：申万/中信一级行业分类，约 28-30 个大类（如"电子"、"医药生物"）
- **L2**：申万/中信二级行业分类，约 104 个中类（如"半导体"、"消费电子"）
- **L3**：申万/中信三级行业分类，约 227 个小类（如"集成电路设计"、"LED"）
- **index_member_all**：Tushare 申万行业成分 API，返回 `ts_code`、`name`、`l1_code`、`l2_code`、`l3_code`、`in_date` 等字段
- **ci_index_member**：Tushare 中信行业成分 API，返回相同结构的字段
- **index_classify**：Tushare 申万行业分类 API，返回行业代码、名称、层级（L1/L2/L3）

## 需求

---

### 需求 1：申万行业 L2/L3 成分股导入

**用户故事：** 作为量化交易员，我希望申万行业数据源能提供二级和三级行业的成分股映射，以便使用更细粒度的行业分类进行板块轮动分析。

#### 验收标准

1. THE Tushare 导入服务 SHALL 在处理 `index_member_all` API 返回数据时，为每条记录生成 3 条 `sector_constituent` 记录：分别对应 `l1_code`、`l2_code`、`l3_code`（当字段非空时）。
2. WHEN `index_member_all` API 返回一条记录 `{ts_code: "000001.SZ", l1_code: "801080.SI", l2_code: "801081.SI", l3_code: "851811.SI", in_date: "1991-04-03"}` 时，THE 导入服务 SHALL 生成以下 3 条 `sector_constituent` 记录：
   - `(trade_date=1991-04-03, sector_code=801080.SI, data_source=TI, symbol=000001.SZ)`
   - `(trade_date=1991-04-03, sector_code=801081.SI, data_source=TI, symbol=000001.SZ)`
   - `(trade_date=1991-04-03, sector_code=851811.SI, data_source=TI, symbol=000001.SZ)`
3. WHEN `l2_code` 或 `l3_code` 为空时，THE 导入服务 SHALL 跳过该层级的记录，不生成空 sector_code 的记录。
4. THE 导入完成后，TI 数据源的覆盖率 SHALL 从 31/359 板块提升到接近 359/359 板块。

---

### 需求 2：中信行业 L2/L3 成分股导入

**用户故事：** 作为量化交易员，我希望中信行业数据源也能提供完整的多级行业成分股映射。

#### 验收标准

1. THE Tushare 导入服务 SHALL 在处理 `ci_index_member` API 返回数据时，同样为每条记录生成 L1/L2/L3 三条 `sector_constituent` 记录。
2. THE 导入逻辑 SHALL 与需求 1 的申万行业导入使用相同的多级展开机制。

---

### 需求 3：中信行业板块分类数据补全

**用户故事：** 作为量化交易员，我希望中信行业数据源有完整的板块元数据（名称、类型），以便前端能正确显示板块名称和分类。

#### 验收标准

1. THE Tushare 导入服务 SHALL 在处理 `ci_index_member` API 返回数据时，从返回的 `l1_name`/`l2_name`/`l3_name` 字段提取板块名称，自动生成 `sector_info` 记录。
2. IF Tushare `ci_index_member` API 不返回板块名称字段，THEN THE 导入服务 SHALL 从成分股数据中提取唯一的 `l1_code`/`l2_code`/`l3_code` 列表，以代码作为名称写入 `sector_info` 表，`sector_type` 分别设为 `L1`/`L2`/`L3`。
3. THE 导入完成后，CI 数据源在 `sector_info` 表中 SHALL 有完整的板块元数据记录。

---

### 需求 4：导入注册表多级展开机制

**用户故事：** 作为开发者，我希望 Tushare 导入框架支持将一条 API 返回记录展开为多条数据库记录的能力，以便复用于申万和中信两个数据源。

#### 验收标准

1. THE Tushare 导入框架 SHALL 支持 `field_mappings` 中的多级展开配置，通过新增 `expand_fields` 配置项指定需要展开的字段列表。
2. WHEN `expand_fields` 配置为 `[{"source": "l1_code", "target": "sector_code"}, {"source": "l2_code", "target": "sector_code"}, {"source": "l3_code", "target": "sector_code"}]` 时，THE 导入服务 SHALL 为每条 API 返回记录生成最多 3 条数据库记录，每条使用不同的 `sector_code` 值。
3. WHEN 展开字段的值为空或 None 时，THE 导入服务 SHALL 跳过该条展开记录。
4. THE 现有的 `field_mappings` 行为 SHALL 保持不变，`expand_fields` 为可选配置。
