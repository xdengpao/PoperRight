# Tushare 导入优化 Bugfix Design

## Overview

Tushare 数据在线导入功能存在 5 个用户体验和功能缺陷，涉及前端 `TushareImportView.vue` 组件和后端 `tushare_import_service.py` / `tushare_import.py` 任务。本设计文档定义每个缺陷的 Bug Condition、修复策略和验证方法，确保修复精准且不引入回归。

**修复范围：**
1. 按钮无 loading 反馈 → 前端 `startImport()` 函数 + 模板按钮状态
2. 日期默认最近一年 → 前端 `getParam()` 或参数初始化逻辑
3. 股票代码留空不阻止提交 → 前端 `requiredParamsFilled()` 函数
4. 批量选择导入 → 前端新增 checkbox + 批量导入按钮 + 批量调用逻辑
5. 失败原因不显示 → 后端 `_update_progress()` 增加 `error_message` + 前端展示

## Glossary

- **Bug_Condition (C)**: 触发缺陷的输入条件集合
- **Property (P)**: 修复后在 Bug_Condition 下的期望行为
- **Preservation**: 修复不应改变的现有行为
- **TushareImportView**: 前端 Tushare 数据导入页面组件（`frontend/src/views/TushareImportView.vue`）
- **startImport(api)**: 前端发起单个 API 导入的异步函数
- **requiredParamsFilled(api)**: 前端判断必填参数是否已填写的函数
- **canImport(api)**: 前端判断"开始导入"按钮是否可用的函数，依赖 `health.connected`、`api.token_available`、`requiredParamsFilled(api)`
- **_update_progress()**: 后端 Celery 任务中更新 Redis 进度数据的函数（`app/tasks/tushare_import.py`）
- **ImportTask**: 前端活跃任务数据结构，包含 `task_id`、`status`、`total`、`completed`、`failed`、`current_item`
- **paramValues**: 前端 reactive 对象，存储每个 API 接口的参数值（`Record<string, Record<string, string>>`）
- **loadingApis**: 新增的前端 reactive Set，跟踪正在发起导入请求的 API 名称

## Bug Details

### Bug 1: 按钮无 loading 反馈

用户点击"开始导入"按钮后，按钮没有任何视觉反馈（无 spinner、无文字变化、无禁用状态），导致用户无法判断请求是否已发出，可能重复点击。

**Formal Specification:**
```
FUNCTION isBugCondition_1(input)
  INPUT: input of type { action: "click_import", api: ApiItem }
  OUTPUT: boolean

  RETURN input.action == "click_import"
         AND canImport(input.api) == true
         AND startImport(input.api) is called
         AND button.loading == false
         AND button.disabled == false
         AND button.text == "开始导入"
END FUNCTION
```

### Bug 2: 日期默认最近一年

展开需要日期范围参数的接口时，`start_date` 字段为空，用户每次都必须手动输入起始日期。

**Formal Specification:**
```
FUNCTION isBugCondition_2(input)
  INPUT: input of type { api: ApiItem, paramType: string }
  OUTPUT: boolean

  RETURN input.paramType == "date_range"
         AND (input.api.required_params.includes("date_range")
              OR input.api.optional_params.includes("date_range"))
         AND getParam(input.api.api_name, "start_date") == ""
END FUNCTION
```

### Bug 3: 股票代码留空阻止提交

当 `stock_code` 出现在 `required_params` 中时，`requiredParamsFilled()` 因值为空返回 false，导致"开始导入"按钮被禁用。但 `stock_code` 留空应表示"全市场"。

**Formal Specification:**
```
FUNCTION isBugCondition_3(input)
  INPUT: input of type { api: ApiItem, stock_code_value: string }
  OUTPUT: boolean

  RETURN "stock_code" IN input.api.required_params
         AND input.stock_code_value == ""
         AND requiredParamsFilled(input.api) == false
END FUNCTION
```

### Bug 4: 无批量选择导入

用户需要同时导入多个 API 接口的数据时，只能逐个展开、逐个点击，无法批量勾选一次性发起。

**Formal Specification:**
```
FUNCTION isBugCondition_4(input)
  INPUT: input of type { subcategory: string, selectedApis: ApiItem[] }
  OUTPUT: boolean

  RETURN input.selectedApis.length > 1
         AND NO batchImport mechanism exists
         AND user must click "开始导入" for each api individually
END FUNCTION
```

### Bug 5: 失败原因不显示

导入任务失败后，前端活跃任务区域仅显示"失败"状态徽章，不显示具体错误原因。后端 `_update_progress()` 函数签名中没有 `error_message` 参数，失败时不将错误信息写入 Redis 进度数据。

**Formal Specification:**
```
FUNCTION isBugCondition_5(input)
  INPUT: input of type { task: ImportTask }
  OUTPUT: boolean

  RETURN input.task.status == "failed"
         AND input.task.error_message is undefined
         AND Redis progress data does NOT contain "error_message" field
END FUNCTION
```

### Examples

- **Bug 1**: 用户点击 `daily` 接口的"开始导入"按钮 → 按钮保持原样，用户不确定是否已发出请求，再次点击 → 收到 409 冲突错误
- **Bug 2**: 用户展开"日K"子分类下的 `daily` 接口 → `start_date` 为空，必须手动输入 `2024-01-01` 才能点击导入
- **Bug 3**: 用户展开 `stk_mins` 接口（`required_params` 包含 `stock_code`）→ 留空股票代码 → "开始导入"按钮被禁用，无法导入全市场数据
- **Bug 4**: 用户需要导入 `daily`、`weekly`、`monthly` 三个接口 → 必须逐个展开、逐个设置参数、逐个点击导入
- **Bug 5**: `daily` 导入因 Token 权限不足失败 → 活跃任务区域显示红色"失败"徽章，但无法看到"Token 权限不足"的具体原因

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 当 Tushare 未连接时，所有导入按钮保持禁用状态并显示"Tushare 未连接"提示
- 非 `stock_code` 的必填参数（如 `hs_type`、`sector_code`、`index_code`）未填写时，"开始导入"按钮保持禁用
- 进度轮询保持每 3 秒一次的频率
- 同一接口已有任务运行时，后端继续返回 409 冲突错误
- 导入成功完成时，正确显示"已完成"状态、数据量和耗时信息
- "停止导入"功能通过 Redis 信号正常工作
- `end_date` 默认值保持为当天日期
- 鼠标点击导入按钮的基本流程（参数构建、API 调用、任务创建、轮询启动）不变

**Scope:**
所有不涉及上述 5 个 Bug Condition 的输入和交互应完全不受修复影响。包括：
- 连接状态检测和 Token 配置显示
- 接口注册表加载和分类展示
- 导入历史记录查询和展示
- 子分类折叠/展开交互
- 参数输入（市场选择、报告期、频率等）

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Bug 1 — 缺少 loading 状态管理**: `startImport()` 函数直接调用 API 但没有在调用前后管理按钮的 loading 状态。没有 `loadingApis` 状态集合来跟踪哪些 API 正在发起请求，模板中按钮也没有绑定 loading 相关的 class 和 disabled 条件。

2. **Bug 2 — `getParam()` 返回空字符串**: `getParam(apiName, 'start_date')` 在 `paramValues` 中无对应值时返回空字符串 `''`。模板中 `:value="getParam(api.api_name, 'start_date')"` 直接使用该空值，没有像 `end_date` 那样提供 `|| todayStr` 的 fallback 默认值。

3. **Bug 3 — `requiredParamsFilled()` 对 `stock_code` 无特殊处理**: 函数中对 `date_range`、`report_period`、`freq`、`market` 有特殊处理（跳过或检查子字段），但 `stock_code` 走了 `else` 分支，执行 `if (!getParam(api.api_name, p)) return false`，导致留空时返回 false。需要将 `stock_code` 加入跳过非空校验的列表。

4. **Bug 4 — 缺少批量选择 UI 和逻辑**: 当前每个 API 接口只有独立的"开始导入"按钮，子分类级别没有 checkbox 和批量操作按钮。需要新增 `selectedApis` 状态、checkbox 组件和 `batchImport()` 函数。

5. **Bug 5 — `_update_progress()` 不存储 `error_message`**: 后端 `_update_progress()` 函数签名中没有 `error_message` 参数。在 `_process_import()` 的 `except` 分支中，`error_msg` 被传给 `_finalize_log()` 写入数据库，但 `_update_progress(task_id, status="failed")` 调用时没有传递错误信息到 Redis。前端 `TushareImportStatusResponse` 模型和 `ImportTask` 类型也没有 `error_message` 字段。

## Correctness Properties

Property 1: Bug Condition — 按钮 Loading 状态

_For any_ API 接口 `api` where `canImport(api)` returns true, when `startImport(api)` is called, the import button for that API SHALL immediately enter loading state (disabled=true, text="导入中..."), and SHALL restore to normal state after the API request completes (success or failure).

**Validates: Requirements 2.1**

Property 2: Bug Condition — 日期默认值

_For any_ API 接口 `api` that has `date_range` in its `required_params` or `optional_params`, the `start_date` field SHALL default to one year ago from today (today - 365 days) when no value has been explicitly set by the user.

**Validates: Requirements 2.2**

Property 3: Bug Condition — Stock Code 可选校验

_For any_ API 接口 `api` that has `stock_code` in its `required_params` or `optional_params`, `requiredParamsFilled(api)` SHALL return true when `stock_code` is empty (treating it as "全市场"), provided all other required params are filled.

**Validates: Requirements 2.3**

Property 4: Bug Condition — 批量选择导入

_For any_ subcategory containing N importable APIs where K APIs (1 ≤ K ≤ N) are selected via checkboxes, clicking "批量导入已选" SHALL initiate import tasks for exactly those K selected APIs, calling `startImport()` for each in sequence.

**Validates: Requirements 2.4**

Property 5: Bug Condition — 失败原因显示

_For any_ import task that fails with an error, the Redis progress data SHALL contain an `error_message` field with the error description, and the frontend SHALL display this error message in the active tasks area and import history.

**Validates: Requirements 2.5**

Property 6: Preservation — 必填参数校验不变

_For any_ API 接口 `api` and any non-stock-code required parameter `p` (such as `hs_type`, `sector_code`, `index_code`) where `p` is empty, `requiredParamsFilled(api)` SHALL return false, preserving the existing validation behavior.

**Validates: Requirements 3.1, 3.2**

Property 7: Preservation — 导入流程不变

_For any_ API 接口 `api` where `canImport(api)` returns true and the user clicks "开始导入", the system SHALL continue to build params via `buildImportParams()`, POST to `/data/tushare/import`, create an active task entry, and start 3-second polling — identical to the original behavior except for the added loading state.

**Validates: Requirements 3.3, 3.4, 3.5, 3.6, 3.7**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `frontend/src/views/TushareImportView.vue`

**Bug 1 — 按钮 Loading 状态**

1. **新增 `loadingApis` 状态**: 添加 `const loadingApis = reactive(new Set<string>())` 用于跟踪正在发起导入请求的 API 名称
2. **修改 `startImport()` 函数**: 在 API 调用前 `loadingApis.add(api.api_name)`，在 `finally` 块中 `loadingApis.delete(api.api_name)`
3. **修改模板按钮**: 将 `:disabled="!canImport(api)"` 改为 `:disabled="!canImport(api) || loadingApis.has(api.api_name)"`，按钮文字根据 loading 状态切换为"导入中..."
4. **添加 loading 样式**: 为 loading 状态的按钮添加 `btn-loading` CSS class

**Bug 2 — 日期默认值**

1. **计算默认 start_date**: 添加 `const oneYearAgoStr` 常量，值为 `new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10)`
2. **修改模板 start_date 输入框**: 将 `:value="getParam(api.api_name, 'start_date')"` 改为 `:value="getParam(api.api_name, 'start_date') || oneYearAgoStr"`，与 `end_date` 的 `|| todayStr` 模式一致
3. **修改 `buildImportParams()` 函数**: 在 `date_range` 分支中，`start_date` 的 fallback 从无默认值改为 `|| oneYearAgoStr`
4. **修改 `requiredParamsFilled()` 函数**: 在 `date_range` 分支中，由于 start_date 现在有默认值，可以移除对 start_date 的空值检查（或保留检查但使用默认值）

**Bug 3 — Stock Code 可选校验**

1. **修改 `requiredParamsFilled()` 函数**: 在 `else` 分支前增加 `stock_code` 的特殊处理：`else if (p === 'stock_code') { continue }` — 跳过 stock_code 的非空校验，因为留空表示全市场

**Bug 4 — 批量选择导入**

1. **新增 `selectedApis` 状态**: 添加 `const selectedApis = reactive(new Map<string, Set<string>>())` — 按子分类存储已勾选的 API 名称
2. **新增 checkbox 模板**: 在每个 `api-item` 前添加 checkbox，绑定到 `selectedApis`
3. **新增"全选/取消全选"**: 在子分类 header 中添加全选 checkbox
4. **新增"批量导入已选"按钮**: 在子分类的 `api-list` 底部添加批量导入按钮，仅当有已勾选项时显示
5. **新增 `batchImport()` 函数**: 遍历已勾选的 API 列表，依次调用 `startImport(api)`，使用 `for...of` 顺序执行（避免并发冲突）

**Bug 5 — 失败原因显示**

**后端修改:**

1. **修改 `_update_progress()` 签名**: 添加 `error_message: str = ""` 参数
2. **修改 `_update_progress()` 实现**: 当 `error_message` 非空时，将其写入 Redis 进度数据的 `error_message` 字段
3. **修改 `_process_import()` 的 except 分支**: 将 `_update_progress(task_id, status="failed")` 改为 `_update_progress(task_id, status="failed", error_message=error_msg)`
4. **修改 `TushareImportService.get_import_status()`**: 返回值中增加 `error_message` 字段

**API 层修改:**

5. **修改 `TushareImportStatusResponse`**: 添加 `error_message: str = ""` 字段
6. **修改 `get_import_status()` 端点**: 返回 `error_message` 字段

**前端修改:**

7. **修改 `ImportTask` 类型**: 添加 `error_message?: string` 字段
8. **修改活跃任务模板**: 在 `status === 'failed'` 时显示 `task.error_message`
9. **修改导入历史表格**: 在"状态"列旁增加"错误信息"列（仅失败记录显示）

## Testing Strategy

### Validation Approach

测试策略分两阶段：先在未修复代码上运行探索性测试确认 Bug 存在，再在修复后验证正确性和行为保持。

### Exploratory Bug Condition Checking

**Goal**: 在未修复代码上运行测试，确认 5 个 Bug 的存在，验证根因分析。

**Test Plan**: 编写前端组件测试和后端单元测试，在未修复代码上运行以观察失败。

**Test Cases**:
1. **Loading 状态测试**: 模拟点击"开始导入"按钮，断言按钮进入 loading 状态（will fail on unfixed code — 按钮无 loading 状态）
2. **日期默认值测试**: 渲染包含 `date_range` 参数的 API 接口，断言 `start_date` 有默认值（will fail on unfixed code — start_date 为空）
3. **Stock Code 校验测试**: 构造 `required_params` 包含 `stock_code` 的 API，留空 stock_code，断言 `requiredParamsFilled()` 返回 true（will fail on unfixed code — 返回 false）
4. **批量导入测试**: 检查子分类中是否存在 checkbox 和批量导入按钮（will fail on unfixed code — 不存在）
5. **错误信息测试**: 模拟失败任务，断言 Redis 进度数据包含 `error_message`（will fail on unfixed code — 字段不存在）

**Expected Counterexamples**:
- `startImport()` 调用后按钮状态不变
- `getParam(api_name, 'start_date')` 返回空字符串
- `requiredParamsFilled()` 对 stock_code 为空时返回 false
- 无 checkbox/批量导入 UI 元素
- `_update_progress(task_id, status="failed")` 不写入 error_message

### Fix Checking

**Goal**: 验证修复后，所有 Bug Condition 下的行为符合预期。

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
END FOR
```

### Preservation Checking

**Goal**: 验证修复后，所有非 Bug Condition 的输入产生与原始代码相同的结果。

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing Approach**: Property-based testing 推荐用于 preservation checking，因为：
- 自动生成大量测试用例覆盖输入域
- 捕获手动单元测试可能遗漏的边界情况
- 对非 Bug 输入的行为不变提供强保证

**Test Plan**: 先在未修复代码上观察非 Bug 输入的行为，然后编写 property-based 测试捕获该行为。

**Test Cases**:
1. **必填参数校验保持**: 验证 `hs_type`、`sector_code`、`index_code` 等非 stock_code 必填参数为空时，`requiredParamsFilled()` 仍返回 false
2. **canImport 逻辑保持**: 验证 `health.connected=false` 或 `token_available=false` 时，`canImport()` 仍返回 false
3. **buildImportParams 保持**: 验证非 date_range 参数的构建逻辑不变
4. **end_date 默认值保持**: 验证 `end_date` 仍默认为今天日期

### Unit Tests

- 测试 `requiredParamsFilled()` 对各种参数组合的返回值（stock_code 空 → true，hs_type 空 → false）
- 测试 `startImport()` 的 loading 状态生命周期（调用前 → loading → 完成后恢复）
- 测试 `buildImportParams()` 的 start_date 默认值（无用户输入 → oneYearAgoStr）
- 测试 `batchImport()` 对已勾选 API 列表的顺序调用
- 测试后端 `_update_progress()` 的 error_message 写入
- 测试后端 `get_import_status()` 返回 error_message 字段

### Property-Based Tests

- **前端 (fast-check)**: 生成随机 `ApiItem` 配置（随机 required_params/optional_params 组合），验证 `requiredParamsFilled()` 对 stock_code 的特殊处理和对其他参数的保持
- **前端 (fast-check)**: 生成随机子分类和 API 列表，验证批量选择后 `batchImport()` 调用次数等于勾选数量
- **后端 (Hypothesis)**: 生成随机 error_message 字符串，验证 `_update_progress()` 正确写入 Redis 并可通过 `get_import_status()` 读取

### Integration Tests

- 完整导入流程测试：点击导入 → loading 状态 → 任务创建 → 轮询进度 → 完成/失败
- 批量导入流程测试：勾选多个接口 → 点击批量导入 → 依次创建任务 → 各自轮询
- 失败场景端到端测试：触发导入失败 → 后端写入 error_message → 前端展示错误原因
