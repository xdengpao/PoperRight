# 设计文档：申万/中信行业 L2/L3 成分股数据导入

## 概述

当前 Tushare 导入框架的 `_apply_field_mappings()` 是 1:1 行映射（一条 API 记录 → 一条数据库记录）。申万行业 `index_member_all` 和中信行业 `ci_index_member` API 返回的每条记录包含 `l1_code`/`l2_code`/`l3_code` 三个行业代码字段，但当前只映射了 `l1_code` → `sector_code`，L2/L3 字段在写入数据库时被列过滤丢弃。

本设计通过在导入框架中新增 `_expand_rows()` 机制，将一条 API 记录展开为多条数据库记录（1:N 映射），每条使用不同层级的行业代码作为 `sector_code`。

### 设计原则

- **框架级能力**：`_expand_rows()` 作为通用机制，通过 `extra_config.expand_fields` 声明式配置，不硬编码业务逻辑
- **最小侵入**：仅在 `_apply_field_mappings()` 之后、`_write_to_*()` 之前插入一步，不改变现有数据流
- **向后兼容**：无 `expand_fields` 配置时行为完全不变

---

## 架构

### 数据流（修改后）

```
Tushare API 返回:
  {ts_code: "000001.SZ", l1_code: "801080.SI", l2_code: "801081.SI", l3_code: "851811.SI", in_date: "1991-04-03"}
    │
    ▼ inject_fields (添加 data_source: "TI")
    │
    ▼ _apply_field_mappings (l1_code → sector_code, ts_code → symbol, in_date → trade_date)
  {symbol: "000001.SZ", sector_code: "801080.SI", trade_date: "1991-04-03", l2_code: "801081.SI", l3_code: "851811.SI", data_source: "TI"}
    │
    ▼ _expand_rows (新增) — 按 expand_fields 配置展开
  [
    {symbol: "000001.SZ", sector_code: "801080.SI", trade_date: "1991-04-03", data_source: "TI"},  ← L1
    {symbol: "000001.SZ", sector_code: "801081.SI", trade_date: "1991-04-03", data_source: "TI"},  ← L2
    {symbol: "000001.SZ", sector_code: "851811.SI", trade_date: "1991-04-03", data_source: "TI"},  ← L3
  ]
    │
    ▼ _convert_codes → _write_to_postgresql
```

### 受影响的文件

| 文件路径 | 修改类型 | 对应需求 |
|---------|---------|---------|
| `app/tasks/tushare_import.py` | 修改 | 需求 4 |
| `app/services/data_engine/tushare_registry.py` | 修改 | 需求 1, 2, 3 |

---

## 组件设计

### 组件 1：`_expand_rows()` 函数（需求 4）

位置：`app/tasks/tushare_import.py`，在 `_apply_field_mappings()` 函数附近新增

```python
def _expand_rows(rows: list[dict], entry: ApiEntry) -> list[dict]:
    """
    根据 expand_fields 配置将一条记录展开为多条记录。

    expand_fields 格式: {"target_field": ["source_field_1", "source_field_2", ...]}
    对每条输入记录，为每个非空的 source_field 生成一条输出记录，
    将 source_field 的值写入 target_field。

    无 expand_fields 配置时原样返回（向后兼容）。
    """
    expand_config = entry.extra_config.get("expand_fields")
    if not expand_config:
        return rows

    expanded: list[dict] = []
    for row in rows:
        for target_field, source_fields in expand_config.items():
            for src in source_fields:
                val = row.get(src)
                if val is not None and val != "":
                    new_row = dict(row)
                    new_row[target_field] = val
                    expanded.append(new_row)
    return expanded
```

### 组件 2：插入点修改（需求 4）

在以下代码路径中，`_apply_field_mappings()` 之后插入 `_expand_rows()` 调用：

**路径 1：`_process_single()`（第 466 行）**
```python
# 修改前
mapped_rows = _apply_field_mappings(rows, entry)
converted_rows = _convert_codes(mapped_rows, entry)

# 修改后
mapped_rows = _apply_field_mappings(rows, entry)
mapped_rows = _expand_rows(mapped_rows, entry)
converted_rows = _convert_codes(mapped_rows, entry)
```

**路径 2：`_write_chunk_rows()`（第 734 行）**
```python
mapped_rows = _apply_field_mappings(rows, entry)
mapped_rows = _expand_rows(mapped_rows, entry)
converted_rows = _convert_codes(mapped_rows, entry)
```

**路径 3：`_process_batched_by_sector()`（第 1582 行）**
```python
mapped_rows = _apply_field_mappings(rows, entry)
mapped_rows = _expand_rows(mapped_rows, entry)
converted_rows = _convert_codes(mapped_rows, entry)
```

### 组件 3：申万行业注册表修改（需求 1）

位置：`app/services/data_engine/tushare_registry.py` 第 2369 行

```python
# 修改前
register(ApiEntry(
    api_name="index_member_all",
    ...
    extra_config={"inject_fields": {"data_source": "TI"}, "max_rows": 5000},
    field_mappings=[
        FieldMapping(source="ts_code", target="symbol"),
        FieldMapping(source="name", target="stock_name"),
        FieldMapping(source="l1_code", target="sector_code"),
        FieldMapping(source="in_date", target="trade_date"),
    ],
))

# 修改后
register(ApiEntry(
    api_name="index_member_all",
    ...
    extra_config={
        "inject_fields": {"data_source": "TI"},
        "max_rows": 15000,  # 展开后记录数约为原来的 3 倍
        "expand_fields": {"sector_code": ["l1_code", "l2_code", "l3_code"]},
    },
    field_mappings=[
        FieldMapping(source="ts_code", target="symbol"),
        FieldMapping(source="name", target="stock_name"),
        FieldMapping(source="in_date", target="trade_date"),
        # 注意：移除 l1_code → sector_code 的直接映射，改由 expand_fields 处理
    ],
))
```

### 组件 4：中信行业注册表修改（需求 2）

位置：`app/services/data_engine/tushare_registry.py` 第 2437 行

```python
# 修改后
register(ApiEntry(
    api_name="ci_index_member",
    ...
    extra_config={
        "inject_fields": {"data_source": "CI"},
        "max_rows": 15000,
        "expand_fields": {"sector_code": ["l1_code", "l2_code", "l3_code"]},
    },
    field_mappings=[
        FieldMapping(source="ts_code", target="symbol"),
        FieldMapping(source="name", target="stock_name"),
        FieldMapping(source="in_date", target="trade_date"),
    ],
))
```

### 组件 5：中信行业 sector_info 自动生成（需求 3）

在 `_expand_rows()` 之后、`_write_to_postgresql()` 之前，对 CI 数据源自动提取板块元数据写入 `sector_info` 表。

实现方式：在 `_process_single()` 中，当 `entry.target_table == "sector_constituent"` 且 `inject_fields` 包含 `data_source: "CI"` 时，从展开后的记录中提取唯一的 `sector_code` 列表，批量写入 `sector_info`。

```python
# 在 _process_single() 的 _expand_rows() 之后
if entry.extra_config.get("auto_generate_sector_info"):
    await _auto_generate_sector_info(mapped_rows, entry)
```

`_auto_generate_sector_info()` 函数：
```python
async def _auto_generate_sector_info(rows, entry):
    """从成分股数据中自动提取板块元数据写入 sector_info。"""
    ds = entry.extra_config.get("inject_fields", {}).get("data_source", "")
    seen: dict[str, str] = {}  # sector_code → sector_type
    for row in rows:
        code = row.get("sector_code", "")
        if not code or code in seen:
            continue
        # 根据代码格式推断层级
        if code.startswith("CI005"):
            seen[code] = "L1"  # 30 个一级行业
        elif code.startswith("CI006"):
            seen[code] = "L2"
        elif code.startswith("CI007"):
            seen[code] = "L3"
        else:
            seen[code] = "UNKNOWN"

    # 批量 UPSERT 到 sector_info
    for code, level in seen.items():
        # INSERT ... ON CONFLICT (sector_code, data_source) DO UPDATE SET sector_type = ...
```

注意：CI 的代码前缀规则需要从实际数据中确认。如果无法从代码推断层级，可以在 `expand_fields` 配置中附加层级信息。

---

## 测试策略

### 单元测试

| 测试 | 描述 |
|------|------|
| `test_expand_rows_no_config` | 无 expand_fields 配置时原样返回 |
| `test_expand_rows_l1_l2_l3` | 一条记录展开为 3 条，sector_code 分别为 L1/L2/L3 |
| `test_expand_rows_l3_empty` | l3_code 为空时只展开 2 条 |
| `test_expand_rows_all_empty` | 所有展开字段为空时不生成记录 |

### 集成测试

| 测试 | 描述 |
|------|------|
| TI 导入后覆盖率 | sector_constituent 中 TI 板块数接近 359 |
| CI 导入后覆盖率 | sector_constituent 中 CI 板块数 > 30 |
| CI sector_info | sector_info 中 CI 有完整的板块元数据 |
