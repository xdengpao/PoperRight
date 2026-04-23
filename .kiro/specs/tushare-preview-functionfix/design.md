# Tushare 数据预览功能修复 Bugfix Design

## Overview

Tushare 数据预览页面存在 5 个功能缺陷，涉及数据时间自动填充、完整性校验 UX、删除功能三大模块。本修复方案采用最小化变更策略：在前端 store 的 `setSelectedApi()` 中利用已有的 `fetchStats()` 返回值自动填充数据时间筛选器（解决 Bug 1 & 3）；在 Vue 模板中为完整性校验添加 loading 动画（Bug 2）；在后端 `delete_data()` 中集成已有的 `_build_scope_filter_pure()` 方法（Bug 4）；扩展 `DeleteDataRequest` 和 `delete_data()` 支持按导入时间范围删除（Bug 5）。所有修复均复用现有基础设施，不引入新依赖。

## Glossary

- **Bug_Condition (C)**: 触发缺陷的输入条件集合，如"stats 返回了时间范围但 filters 未被填充"
- **Property (P)**: 修复后的期望行为，如"filters.dataTimeStart 等于 stats.earliest_time"
- **Preservation**: 修复不应改变的现有行为，如"手动修改筛选器后查询使用手动值"
- **`setSelectedApi()`**: `tusharePreview.ts` 中的 Pinia action，选择 API 接口后并行加载数据
- **`_build_scope_filter_pure()`**: `tushare_preview_service.py` 中的纯静态方法，根据 `ApiEntry` 推断共享表的 WHERE 作用域条件
- **`_build_incremental_filter()`**: 从导入记录的 `params_json` 提取参数重建数据查询条件的纯静态方法
- **共享表**: 多个 API 接口指向同一张数据库表（如 `daily`/`weekly`/`monthly` → `kline`）
- **作用域过滤**: 通过 `freq`/`report_type`/`data_source`/`holder_type` 等字段区分共享表中不同 API 的数据

## Bug Details

### Bug Condition

本次修复涉及 5 个相互关联的缺陷。核心问题是 `setSelectedApi()` 在获取 stats 后未自动填充数据时间筛选器，导致时间筛选和删除功能均不可用；完整性校验缺少进度反馈；删除功能缺少共享表作用域过滤且不支持按导入时间删除。

**Formal Specification:**

```
FUNCTION isBugCondition_TimeAutoFill(input)
  INPUT: input of type { apiName: string, statsResponse: PreviewStatsResponse }
  OUTPUT: boolean

  // 当 stats 返回了有效的 earliest_time/latest_time 时，
  // filters.dataTimeStart/dataTimeEnd 应被自动填充但实际未填充
  RETURN input.statsResponse.earliest_time IS NOT NULL
     AND input.statsResponse.latest_time IS NOT NULL
     AND filters.dataTimeStart IS NULL
     AND filters.dataTimeEnd IS NULL
END FUNCTION

FUNCTION isBugCondition_IntegrityLoading(input)
  INPUT: input of type { integrityLoading: boolean, integrityReport: CompletenessReport | null }
  OUTPUT: boolean

  // 校验进行中但无视觉反馈
  RETURN input.integrityLoading = true
     AND input.integrityReport IS NULL
END FUNCTION

FUNCTION isBugCondition_DeleteScopeFilter(input)
  INPUT: input of type { apiName: string, entry: ApiEntry }
  OUTPUT: boolean

  // 当 API 对应的表是共享表（有作用域过滤条件）时，
  // delete_data() 未添加作用域过滤，导致误删其他 API 的数据
  RETURN _build_scope_filter_pure(input.entry).length > 0
END FUNCTION

FUNCTION isBugCondition_DeleteByImportTime(input)
  INPUT: input of type { importTimeStart: datetime | null, importTimeEnd: datetime | null }
  OUTPUT: boolean

  // 用户指定了导入时间范围进行删除，但当前不支持
  RETURN input.importTimeStart IS NOT NULL
      OR input.importTimeEnd IS NOT NULL
END FUNCTION
```

### Examples

- **Bug 1 & 3**: 用户选择 `daily` 接口，`fetchStats()` 返回 `earliest_time="20200101"`, `latest_time="20241231"`，但 `filters.dataTimeStart` 和 `filters.dataTimeEnd` 仍为 `null`，导致删除按钮始终 disabled
- **Bug 2**: 用户点击「完整性校验」，按钮文字变为"校验中..."但页面无 loading 动画，用户等待 10+ 秒不知系统是否正常工作
- **Bug 4**: 用户选择 `daily`（`kline` 表, `freq='1d'`）并删除 2024-01-01 ~ 2024-03-31 的数据，DELETE SQL 缺少 `freq='1d'` 条件，同时删除了 `weekly`（`freq='1w'`）和 `monthly`（`freq='1M'`）的数据
- **Bug 5**: 用户希望删除某次错误导入的数据，但删除功能仅支持按数据时间范围，无法按导入时间范围定位并删除

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 用户手动修改数据时间筛选器的值后，查询使用手动设置的值而非自动填充值
- 导入时间筛选、增量查询、分页等查询功能正常工作
- 完整性校验完成后的结果展示逻辑（完整/缺失详情）不变
- 非共享表（如 `adjustment_factor`、`trade_calendar`）的删除行为不变（作用域过滤条件为空）
- 按数据时间范围删除的原有功能继续正常工作
- 选择 API 接口后并行加载预览数据、统计信息、导入记录和图表数据的行为不变

**Scope:**
所有不涉及以下场景的输入应完全不受影响：
- `setSelectedApi()` 中 stats 返回后的 filters 填充逻辑
- 完整性校验进行中的 UI 渲染
- `delete_data()` 的 WHERE 子句构建
- 按导入时间范围删除的新增路径

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **`setSelectedApi()` 未利用 stats 返回值填充 filters**：当前 `setSelectedApi()` 调用 `fetchStats()` 后将结果存入 `stats` ref，但从未将 `stats.earliest_time`/`latest_time` 写入 `filters.dataTimeStart`/`filters.dataTimeEnd`。这是一个遗漏——原始设计中 stats 仅用于展示统计信息，未考虑作为筛选器默认值的来源。

2. **完整性校验 UI 缺少 loading 状态分支**：`TusharePreviewView.vue` 中完整性校验结果区域仅在 `store.integrityReport` 非空时渲染，缺少 `store.integrityLoading && !store.integrityReport` 时的 loading 状态分支。

3. **`delete_data()` 未调用 `_build_scope_filter_pure()`**：`delete_data()` 方法直接构建 DELETE SQL 的 WHERE 子句，仅包含时间范围条件，未像 `query_preview_data()` 和 `check_integrity()` 那样调用 `_build_scope_filter_pure()` 添加作用域过滤。这是一个实现遗漏——其他查询方法都正确使用了该方法。

4. **`DeleteDataRequest` 和 `delete_data()` 不支持导入时间参数**：`DeleteDataRequest` 模型仅有 `data_time_start`/`data_time_end` 字段，`delete_data()` 方法签名也仅接受数据时间参数，缺少 `import_time_start`/`import_time_end` 参数和对应的按导入记录删除逻辑。

## Correctness Properties

Property 1: Bug Condition - 数据时间自动填充

_For any_ API 接口选择操作，当 `fetchStats()` 返回的 `earliest_time` 和 `latest_time` 均非空时，`setSelectedApi()` 完成后 `filters.dataTimeStart` SHALL 等于格式化后的 `earliest_time`，`filters.dataTimeEnd` SHALL 等于格式化后的 `latest_time`。

**Validates: Requirements 2.1, 2.3**

Property 2: Bug Condition - 完整性校验 Loading 反馈

_For any_ 完整性校验进行中的状态（`integrityLoading === true` 且 `integrityReport === null`），页面 SHALL 渲染一个包含旋转图标和"正在校验数据完整性..."文字的 loading 反馈区域。

**Validates: Requirements 2.2**

Property 3: Bug Condition - 删除 SQL 包含共享表作用域过滤

_For any_ `ApiEntry` 其 `_build_scope_filter_pure()` 返回非空条件列表时，`delete_data()` 生成的 DELETE SQL 的 WHERE 子句 SHALL 包含所有作用域过滤条件（如 `freq = :scope_freq`），确保仅删除属于当前 API 接口的数据。

**Validates: Requirements 2.4**

Property 4: Bug Condition - 支持按导入时间范围删除

_For any_ 删除请求包含 `import_time_start` 或 `import_time_end` 参数时，`delete_data()` SHALL 先查询匹配时间范围内的导入记录，再根据这些记录的 `params_json` 重建数据查询条件，删除对应的数据记录，并返回 `deleted_count >= 0`。

**Validates: Requirements 2.5**

Property 5: Preservation - 非共享表删除行为不变

_For any_ `ApiEntry` 其 `_build_scope_filter_pure()` 返回空列表时，`delete_data()` 生成的 DELETE SQL SHALL 与修复前行为一致，仅包含时间范围条件，不添加额外的 WHERE 子句。

**Validates: Requirements 3.4, 3.5**

Property 6: Preservation - 手动修改筛选器后查询使用手动值

_For any_ 用户在自动填充后手动修改 `filters.dataTimeStart` 或 `filters.dataTimeEnd` 的值，后续查询 SHALL 使用用户手动设置的值，而非自动填充的值。

**Validates: Requirements 3.1, 3.2**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `frontend/src/stores/tusharePreview.ts`

**Function**: `setSelectedApi()`

**Specific Changes**:
1. **自动填充数据时间**: 在 `Promise.all` 完成后，检查 `stats.value` 的 `earliest_time`/`latest_time`，若非空则将格式化后的值写入 `filters.value.dataTimeStart`/`filters.value.dataTimeEnd`。格式化逻辑：将 `"20240101"` 格式转为 `"2024-01-01"`（date input 所需格式），或直接使用已有的 ISO 格式截取前 10 位。

**File**: `frontend/src/stores/tusharePreview.ts`

**Function**: `deleteData()`

**Specific Changes**:
2. **扩展 deleteData 参数**: 增加 `importTimeStart`/`importTimeEnd` 可选参数，传递给后端 API。

**File**: `frontend/src/views/TusharePreviewView.vue`

**Specific Changes**:
3. **完整性校验 loading 状态**: 在完整性校验结果区域之前（或替代），添加一个 `v-if="store.integrityLoading"` 的 loading 区域，包含旋转图标 CSS 动画和"正在校验数据完整性..."文字。当 `integrityLoading` 为 true 时显示 loading，为 false 且 `integrityReport` 非空时显示结果。
4. **删除按钮支持导入时间**: 调整删除按钮的 disabled 条件和 `handleDeleteData()` 方法，支持在有导入时间范围时也可执行删除。

**File**: `app/services/data_engine/tushare_preview_service.py`

**Function**: `delete_data()`

**Specific Changes**:
5. **添加作用域过滤**: 在构建 DELETE SQL 的 WHERE 子句时，调用 `self._build_scope_filter_pure(entry)` 获取作用域条件，将其追加到 `where_clauses` 和 `params` 中。
6. **支持按导入时间删除**: 扩展方法签名增加 `import_time_start`/`import_time_end` 参数。当指定导入时间时，查询 `tushare_import_log` 表获取匹配的导入记录，使用 `_build_incremental_filter()` 从每条记录的 `params_json` 重建数据查询条件，然后按这些条件执行删除。

**File**: `app/api/v1/tushare_preview.py`

**Model**: `DeleteDataRequest`

**Specific Changes**:
7. **扩展请求模型**: 在 `DeleteDataRequest` 中增加 `import_time_start: str | None` 和 `import_time_end: str | None` 字段。
8. **传递新参数**: 在 `delete_data` 端点中将新字段传递给 service 层。

## Testing Strategy

### Validation Approach

测试策略分两阶段：先在未修复代码上编写探索性测试确认缺陷存在，再在修复后验证正确性并确保现有行为不变。

### Exploratory Bug Condition Checking

**Goal**: 在实施修复前，编写测试确认缺陷的存在，验证根因分析。

**Test Plan**: 编写测试模拟各缺陷场景，在未修复代码上运行观察失败。

**Test Cases**:
1. **时间自动填充测试**: Mock `fetchStats` 返回 `earliest_time="20200101"`, `latest_time="20241231"`，调用 `setSelectedApi()`，断言 `filters.dataTimeStart` 非空（将在未修复代码上失败）
2. **完整性校验 Loading 测试**: 设置 `integrityLoading=true, integrityReport=null`，渲染组件，断言存在 loading 元素（将在未修复代码上失败）
3. **删除作用域过滤测试**: 对 `daily`（kline, freq=1d）调用 `delete_data()`，检查生成的 DELETE SQL 是否包含 `freq` 条件（将在未修复代码上失败）
4. **按导入时间删除测试**: 调用 `delete_data()` 传入 `import_time_start`，检查是否支持（将在未修复代码上失败，因为参数不存在）

**Expected Counterexamples**:
- `setSelectedApi()` 完成后 `filters.dataTimeStart` 仍为 `null`
- 完整性校验进行中无 loading DOM 元素
- DELETE SQL 缺少 `freq = :scope_freq` 条件
- `delete_data()` 不接受 `import_time_start` 参数

### Fix Checking

**Goal**: 验证修复后，所有缺陷输入均产生期望行为。

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition_TimeAutoFill(input) DO
  result := setSelectedApi'(input.apiName)
  ASSERT filters.dataTimeStart = formatDate(input.statsResponse.earliest_time)
  ASSERT filters.dataTimeEnd = formatDate(input.statsResponse.latest_time)
END FOR

FOR ALL input WHERE isBugCondition_DeleteScopeFilter(input) DO
  deleteSql := delete_data'(input.apiName, timeStart, timeEnd)
  scopeFilters := _build_scope_filter_pure(input.entry)
  FOR EACH (clause, params) IN scopeFilters DO
    ASSERT deleteSql.WHERE.contains(clause)
  END FOR
END FOR

FOR ALL input WHERE isBugCondition_DeleteByImportTime(input) DO
  result := delete_data'(input.apiName, importTimeStart=input.importTimeStart)
  ASSERT result.deleted_count >= 0
END FOR
```

### Preservation Checking

**Goal**: 验证修复后，所有非缺陷输入的行为与修复前一致。

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition_DeleteScopeFilter(input) DO
  ASSERT delete_data_original(input) = delete_data_fixed(input)
END FOR

FOR ALL input WHERE NOT isBugCondition_TimeAutoFill(input) DO
  // stats 返回 earliest_time=null 时，filters 不应被修改
  ASSERT filters.dataTimeStart = null
  ASSERT filters.dataTimeEnd = null
END FOR
```

**Testing Approach**: 属性测试（Property-Based Testing）适用于保持性检查，因为：
- 自动生成大量测试用例覆盖输入域
- 捕获手动测试可能遗漏的边界情况
- 对非缺陷输入提供强保证

**Test Plan**: 先在未修复代码上观察非缺陷输入的行为，再编写属性测试确保修复后行为一致。

**Test Cases**:
1. **非共享表删除保持**: 对 `adjustment_factor`（独占表）执行删除，验证 DELETE SQL 不包含作用域条件，行为与修复前一致
2. **手动筛选器保持**: 自动填充后手动修改 `dataTimeStart`，执行查询，验证使用手动值
3. **其他查询功能保持**: 导入时间筛选、增量查询、分页在修复后继续正常工作
4. **按数据时间删除保持**: 仅指定 `data_time_start`/`data_time_end`（不指定导入时间）时，删除行为与修复前一致

### Unit Tests

- 测试 `setSelectedApi()` 在 stats 返回有效时间时自动填充 filters
- 测试 `setSelectedApi()` 在 stats 返回 null 时间时不修改 filters
- 测试 `delete_data()` 对共享表生成包含作用域条件的 DELETE SQL
- 测试 `delete_data()` 对非共享表生成不含作用域条件的 DELETE SQL
- 测试 `delete_data()` 按导入时间范围查询导入记录并重建删除条件
- 测试 `DeleteDataRequest` 模型接受 `import_time_start`/`import_time_end` 字段
- 测试完整性校验 loading 状态下的 DOM 渲染

### Property-Based Tests

- 生成随机 `ApiEntry`（含/不含 `extra_config` 中的作用域字段），验证 `_build_scope_filter_pure()` 返回的条件在 `delete_data()` 的 WHERE 子句中被正确包含（后端 Hypothesis）
- 生成随机 `PreviewStatsResponse`（`earliest_time`/`latest_time` 为 null 或有效日期字符串），验证自动填充逻辑的正确性（前端 fast-check）
- 生成随机非共享表 `ApiEntry`，验证删除行为不变（后端 Hypothesis 保持性测试）

### Integration Tests

- 端到端测试：选择 API → stats 返回 → filters 自动填充 → 删除按钮可用 → 执行删除
- 端到端测试：对共享表 `daily`（kline, freq=1d）执行删除，验证仅删除 freq=1d 的数据
- 端到端测试：指定导入时间范围执行删除，验证仅删除匹配导入记录对应的数据
- 端到端测试：完整性校验全流程（点击 → loading → 结果展示）
