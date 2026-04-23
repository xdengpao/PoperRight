# Implementation Plan — Tushare 数据预览功能修复

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - 数据时间自动填充 & 删除作用域过滤 & 导入时间删除
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bugs exist
  - **Backend (Hypothesis)** — 文件: `tests/properties/test_tushare_preview_functionfix_exploration.py`
    - **P1 数据时间自动填充**: 测试纯逻辑——给定 `earliest_time`/`latest_time` 非空的 `PreviewStatsResponse`，模拟 `setSelectedApi()` 完成后 `filters.dataTimeStart`/`filters.dataTimeEnd` 应被填充（前端逻辑，用 fast-check 测试）
    - **P3 删除 SQL 作用域过滤**: 生成随机共享表 `ApiEntry`（`_build_scope_filter_pure()` 返回非空），验证当前 `delete_data()` 构建的 DELETE SQL **缺少**作用域条件（确认 Bug 存在）。具体：构造 `entry` 使 `target_table="kline"` 且 `extra_config={"freq": "1d"}`，断言 `delete_data()` 生成的 SQL 应包含 `freq = :scope_freq` 但实际不包含
    - **P4 按导入时间删除**: 验证当前 `delete_data()` 方法签名不接受 `import_time_start`/`import_time_end` 参数（确认 Bug 存在）
  - **Frontend (fast-check)** — 文件: `frontend/src/stores/__tests__/tusharePreviewFunctionfix.exploration.property.test.ts`
    - **P1 数据时间自动填充**: 生成随机 `PreviewStatsResponse`（`earliest_time`/`latest_time` 非空），mock `fetchStats` 返回该响应，调用 `setSelectedApi()`，断言 `filters.dataTimeStart` 等于格式化后的 `earliest_time`（在未修复代码上失败）
    - **P2 完整性校验 Loading**: 设置 `integrityLoading=true, integrityReport=null`，渲染组件，断言存在包含"正在校验数据完整性..."文字的 loading 元素（在未修复代码上失败）
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct - it proves the bugs exist)
  - Document counterexamples found to understand root cause
  - Mark task complete when tests are written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - 非共享表删除不变 & 手动筛选器覆盖
  - **IMPORTANT**: Follow observation-first methodology
  - **Backend (Hypothesis)** — 文件: `tests/properties/test_tushare_preview_functionfix_preservation.py`
    - **P5 非共享表删除行为不变**: 生成随机非共享表 `ApiEntry`（`_build_scope_filter_pure()` 返回空列表，如 `target_table="adjustment_factor"`），观察 `delete_data()` 在未修复代码上的 DELETE SQL 仅包含时间范围条件，编写属性测试断言此行为
    - **P6 按数据时间删除保持**: 生成随机 `data_time_start`/`data_time_end`（不指定 `import_time_start`/`import_time_end`），验证 `delete_data()` 行为与修复前一致
  - **Frontend (fast-check)** — 文件: `frontend/src/stores/__tests__/tusharePreviewFunctionfix.preservation.property.test.ts`
    - **P6 手动筛选器覆盖**: 生成随机日期字符串，模拟自动填充后用户手动修改 `filters.dataTimeStart`/`filters.dataTimeEnd`，验证后续查询使用手动值而非自动填充值
    - **完整性校验结果展示不变**: 设置 `integrityLoading=false, integrityReport` 为非空完整性报告，渲染组件，验证结果展示逻辑不变
  - Verify tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3. Fix for Tushare 数据预览功能缺陷

  - [x] 3.1 实现数据时间自动填充（Bug 1 & 3）
    - 修改 `frontend/src/stores/tusharePreview.ts` 的 `setSelectedApi()` 方法
    - 在 `Promise.all` 完成后，检查 `stats.value` 的 `earliest_time`/`latest_time`
    - 若非空，将格式化后的值写入 `filters.value.dataTimeStart`/`filters.value.dataTimeEnd`
    - 格式化逻辑：`"20240101"` → `"2024-01-01"`（date input 所需格式），或 ISO 格式截取前 10 位
    - 删除按钮的 disabled 条件自动满足（因为 filters 已被填充）
    - _Bug_Condition: isBugCondition_TimeAutoFill(input) where statsResponse.earliest_time IS NOT NULL AND statsResponse.latest_time IS NOT NULL_
    - _Expected_Behavior: filters.dataTimeStart = formatDate(statsResponse.earliest_time), filters.dataTimeEnd = formatDate(statsResponse.latest_time)_
    - _Preservation: 用户手动修改筛选器后查询使用手动值；并行加载行为不变_
    - _Requirements: 2.1, 2.3, 3.1, 3.2, 3.6_

  - [x] 3.2 添加完整性校验 Loading 反馈（Bug 2）
    - 修改 `frontend/src/views/TusharePreviewView.vue`
    - 在完整性校验结果 `<section v-if="store.integrityReport">` 之前添加 loading 状态区域
    - 添加 `v-if="store.integrityLoading"` 的 loading 区域，包含旋转图标 CSS 动画和"正在校验数据完整性..."文字
    - 当 `integrityLoading` 为 true 时显示 loading，为 false 且 `integrityReport` 非空时显示结果
    - _Bug_Condition: isBugCondition_IntegrityLoading(input) where integrityLoading = true AND integrityReport IS NULL_
    - _Expected_Behavior: UI 渲染包含旋转图标和"正在校验数据完整性..."文字的 loading 区域_
    - _Preservation: 校验完成后结果展示逻辑不变_
    - _Requirements: 2.2, 3.3_

  - [x] 3.3 添加删除 SQL 共享表作用域过滤（Bug 4）
    - 修改 `app/services/data_engine/tushare_preview_service.py` 的 `delete_data()` 方法
    - 在构建 DELETE SQL 的 WHERE 子句时，调用 `self._build_scope_filter_pure(entry)` 获取作用域条件
    - 将返回的 `list[tuple[str, dict]]` 中的每个 `(clause, params)` 追加到 `where_clauses` 和 `params` 中
    - _Bug_Condition: isBugCondition_DeleteScopeFilter(input) where _build_scope_filter_pure(entry).length > 0_
    - _Expected_Behavior: DELETE SQL WHERE 子句包含所有作用域过滤条件（如 freq = :scope_freq）_
    - _Preservation: 非共享表（_build_scope_filter_pure 返回空列表）删除行为不变_
    - _Requirements: 2.4, 3.4_

  - [x] 3.4 支持按导入时间范围删除（Bug 5）
    - 修改 `app/api/v1/tushare_preview.py` 的 `DeleteDataRequest` 模型，增加 `import_time_start: str | None = None` 和 `import_time_end: str | None = None` 字段
    - 修改 `delete_data` 端点，将新字段传递给 service 层
    - 修改 `app/services/data_engine/tushare_preview_service.py` 的 `delete_data()` 方法签名，增加 `import_time_start`/`import_time_end` 参数
    - 当指定导入时间时：查询 `tushare_import_log` 表获取匹配时间范围内的导入记录，使用 `_build_incremental_filter()` 从每条记录的 `params_json` 重建数据查询条件，按这些条件执行删除
    - 修改 `frontend/src/stores/tusharePreview.ts` 的 `deleteData()` 方法，增加 `importTimeStart`/`importTimeEnd` 可选参数并传递给后端
    - 修改 `frontend/src/views/TusharePreviewView.vue` 的删除按钮 disabled 条件和 `handleDeleteData()` 方法，支持在有导入时间范围时也可执行删除
    - _Bug_Condition: isBugCondition_DeleteByImportTime(input) where importTimeStart IS NOT NULL OR importTimeEnd IS NOT NULL_
    - _Expected_Behavior: delete_data() 先查询匹配导入记录，再根据 params_json 重建条件删除数据，返回 deleted_count >= 0_
    - _Preservation: 仅指定 data_time_start/data_time_end 时删除行为与修复前一致_
    - _Requirements: 2.5, 3.5_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - 数据时间自动填充 & 删除作用域过滤 & 导入时间删除
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests PASS (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - 非共享表删除不变 & 手动筛选器覆盖
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - 运行后端测试: `pytest tests/properties/test_tushare_preview_functionfix_exploration.py tests/properties/test_tushare_preview_functionfix_preservation.py`
  - 运行前端测试: `cd frontend && npx vitest --run src/stores/__tests__/tusharePreviewFunctionfix.exploration.property.test.ts src/stores/__tests__/tusharePreviewFunctionfix.preservation.property.test.ts`
  - 运行完整测试套件确保无回归: `pytest` 和 `cd frontend && npm test`
  - Ensure all tests pass, ask the user if questions arise.
