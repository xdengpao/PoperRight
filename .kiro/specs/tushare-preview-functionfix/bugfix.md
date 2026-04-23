# Bugfix Requirements Document

## Introduction

Tushare 数据预览页面在测试中发现多个功能缺陷，涉及数据时间筛选、完整性校验体验、删除功能三大模块。核心问题是：选择 API 接口后数据时间筛选器未自动填充（导致时间筛选和删除功能均不可用）、完整性校验缺少进度反馈、删除功能缺少共享表作用域过滤（存在数据误删风险）且不支持按导入时间删除。这些缺陷严重影响数据预览页面的可用性和数据安全性。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户选择一个 API 接口时，`setSelectedApi()` 调用 `fetchStats()` 获取到 `earliest_time`/`latest_time`，但这些值未被用于自动填充 `filters.dataTimeStart`/`filters.dataTimeEnd`，THEN 数据时间筛选器始终为空，用户无法基于数据时间进行查询

1.2 WHEN 用户点击「完整性校验」按钮后，校验过程中仅将按钮文字变为"校验中..."，THEN 页面无 loading 动画、进度条或其他视觉反馈，用户无法判断系统是否在正常工作

1.3 WHEN 用户选择 API 接口后尝试点击「删除」按钮时，由于数据时间筛选器始终为空（Bug 1.1），删除按钮的 disabled 条件 `!store.filters.dataTimeStart && !store.filters.dataTimeEnd` 始终为 true，THEN 删除按钮始终处于禁用状态，用户无法执行任何删除操作

1.4 WHEN 对共享表（如 `kline` 表被 `daily`/`weekly`/`monthly` 共用）执行删除操作时，后端 `delete_data()` 方法未调用 `_build_scope_filter_pure()` 添加作用域过滤条件（如 `freq='1d'`），THEN 删除操作会误删同一张表中属于其他 API 接口的数据（例如删除 daily 数据时会同时删除 weekly 和 monthly 数据）

1.5 WHEN 用户希望按导入时间范围删除数据时，THEN 删除功能仅支持按数据时间范围删除，不支持按导入时间范围删除，无法满足"删除某次导入的数据"的需求

### Expected Behavior (Correct)

2.1 WHEN 用户选择一个 API 接口后 `fetchStats()` 返回 `earliest_time`/`latest_time` 时，THEN 系统 SHALL 自动将这两个值填充到 `filters.dataTimeStart` 和 `filters.dataTimeEnd`，使数据时间筛选器显示该接口数据的实际时间范围；用户可手动修改这些值

2.2 WHEN 用户点击「完整性校验」按钮后，THEN 系统 SHALL 在校验结果区域立即显示一个带有 loading 动画（旋转图标 + "正在校验数据完整性..."文字）的进度反馈区域，直到校验完成后替换为实际结果

2.3 WHEN 用户选择 API 接口后数据时间被自动填充（Bug 2.1 修复后），THEN 删除按钮 SHALL 变为可用状态，用户可以基于数据时间范围执行删除操作

2.4 WHEN 对共享表执行删除操作时，THEN 后端 `delete_data()` 方法 SHALL 调用 `_build_scope_filter_pure()` 获取作用域过滤条件并添加到 DELETE SQL 的 WHERE 子句中，确保仅删除属于当前所选 API 接口的数据

2.5 WHEN 用户指定导入时间范围执行删除操作时，THEN 系统 SHALL 支持按导入时间范围删除数据：先从 `tushare_import_log` 表查询匹配的导入记录，再根据这些记录的 `params_json` 重建数据查询条件，删除对应的数据记录

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户手动修改数据时间筛选器的值后点击查询时，THEN 系统 SHALL CONTINUE TO 使用用户手动设置的时间范围进行查询，而非强制使用自动填充的值

3.2 WHEN 用户使用导入时间筛选器、增量查询、分页等功能时，THEN 系统 SHALL CONTINUE TO 正常执行这些查询操作，不受数据时间自动填充的影响

3.3 WHEN 完整性校验完成后，THEN 系统 SHALL CONTINUE TO 正确显示校验结果（完整/缺失详情），结果展示逻辑不变

3.4 WHEN 对非共享表（如 `adjustment_factor`、`trade_calendar` 等独占表）执行删除操作时，THEN 系统 SHALL CONTINUE TO 按原有逻辑正常删除，作用域过滤条件为空不影响删除行为

3.5 WHEN 用户使用数据时间范围执行删除操作时，THEN 系统 SHALL CONTINUE TO 支持按数据时间范围删除的原有功能

3.6 WHEN 用户选择 API 接口后，THEN 系统 SHALL CONTINUE TO 并行加载预览数据、统计信息、导入记录和图表数据，加载行为不变

---

## Bug Condition Derivation

### Bug 1 & 3: 数据时间未自动填充 → 删除按钮始终禁用

```pascal
FUNCTION isBugCondition_TimeAutoFill(X)
  INPUT: X of type { apiName: string, statsResponse: StatsResponse }
  OUTPUT: boolean
  
  // 当 stats 返回了 earliest_time/latest_time 但 filters 未被填充时触发
  RETURN X.statsResponse.earliest_time IS NOT NULL
     AND X.statsResponse.latest_time IS NOT NULL
END FUNCTION
```

```pascal
// Property: Fix Checking - 数据时间自动填充
FOR ALL X WHERE isBugCondition_TimeAutoFill(X) DO
  result ← setSelectedApi'(X.apiName)
  ASSERT filters.dataTimeStart = formatDate(X.statsResponse.earliest_time)
  ASSERT filters.dataTimeEnd = formatDate(X.statsResponse.latest_time)
END FOR
```

```pascal
// Property: Preservation Checking - 手动修改不受影响
FOR ALL X WHERE NOT isBugCondition_TimeAutoFill(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

### Bug 2: 完整性校验无进度反馈

```pascal
FUNCTION isBugCondition_IntegrityFeedback(X)
  INPUT: X of type { integrityLoading: boolean, integrityReport: Report | null }
  OUTPUT: boolean
  
  // 当校验正在进行中且结果尚未返回时触发
  RETURN X.integrityLoading = true AND X.integrityReport IS NULL
END FUNCTION
```

```pascal
// Property: Fix Checking - 校验中显示进度反馈
FOR ALL X WHERE isBugCondition_IntegrityFeedback(X) DO
  ui ← render'(X)
  ASSERT ui.contains(loadingSpinner) AND ui.contains("正在校验数据完整性...")
END FOR
```

```pascal
// Property: Preservation Checking - 校验完成后结果展示不变
FOR ALL X WHERE NOT isBugCondition_IntegrityFeedback(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

### Bug 4: 删除缺少共享表作用域过滤

```pascal
FUNCTION isBugCondition_DeleteScopeFilter(X)
  INPUT: X of type { apiName: string, entry: ApiEntry }
  OUTPUT: boolean
  
  // 当 API 对应的表是共享表（有作用域过滤条件）时触发
  RETURN _build_scope_filter_pure(X.entry).length > 0
END FUNCTION
```

```pascal
// Property: Fix Checking - 删除 SQL 包含作用域过滤
FOR ALL X WHERE isBugCondition_DeleteScopeFilter(X) DO
  deleteSql ← delete_data'(X.apiName, timeStart, timeEnd)
  scopeFilters ← _build_scope_filter_pure(X.entry)
  FOR EACH (clause, params) IN scopeFilters DO
    ASSERT deleteSql.WHERE.contains(clause)
  END FOR
END FOR
```

```pascal
// Property: Preservation Checking - 非共享表删除行为不变
FOR ALL X WHERE NOT isBugCondition_DeleteScopeFilter(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

### Bug 5: 删除不支持按导入时间

```pascal
FUNCTION isBugCondition_DeleteByImportTime(X)
  INPUT: X of type { importTimeStart: datetime | null, importTimeEnd: datetime | null }
  OUTPUT: boolean
  
  // 当用户指定了导入时间范围进行删除时触发
  RETURN X.importTimeStart IS NOT NULL OR X.importTimeEnd IS NOT NULL
END FUNCTION
```

```pascal
// Property: Fix Checking - 支持按导入时间删除
FOR ALL X WHERE isBugCondition_DeleteByImportTime(X) DO
  result ← delete_data'(X.apiName, importTimeStart=X.importTimeStart, importTimeEnd=X.importTimeEnd)
  ASSERT result.deleted_count >= 0
  ASSERT 删除的数据仅限于匹配导入时间范围内的导入记录对应的数据
END FOR
```

```pascal
// Property: Preservation Checking - 按数据时间删除不变
FOR ALL X WHERE NOT isBugCondition_DeleteByImportTime(X) DO
  ASSERT F(X) = F'(X)
END FOR
```
