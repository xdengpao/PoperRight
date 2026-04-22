# Implementation Plan: Tushare 数据预览增强

## Overview

本实现计划将 Tushare 数据预览增强功能分解为可增量执行的编码任务。采用自底向上的构建顺序：后端纯函数与常量定义 → 后端服务方法实现 → 后端 API 端点 → 前端纯函数与精度规则 → 前端 Store 扩展 → 前端组件增强 → 属性测试与单元测试。每个任务构建在前一个任务之上，确保无孤立代码。所有新增逻辑在现有文件中扩展，不新建服务文件或组件文件（列选择器除外）。

## Tasks

- [x] 1. 后端纯函数与常量扩展
  - [x] 1.1 扩展图表类型推断规则（CHART_TYPE_MAP）
    - 在 `app/services/data_engine/tushare_preview_service.py` 中新增 `CHART_TYPE_MAP` 字典常量，定义 subcategory → chart_type 的完整映射：
      - `"资金流向数据"` → `"line"`
      - `"两融及转融通"` → `"line"`
      - `"特色数据"` → `"line"`
      - `"大盘指数每日指标"` → `"line"`
      - `"指数技术面因子（专业版）"` → `"line"`
      - `"打板专题数据"` → `"bar"`
      - `"沪深市场每日交易统计"` → `"bar"`
      - `"深圳市场每日交易情况"` → `"bar"`
    - 修改 `_infer_chart_type_pure` 方法签名，新增 `time_field: str | None` 参数
    - 更新推断逻辑优先级：(1) KLINE_TABLES → candlestick；(2) CHART_TYPE_MAP → 对应类型；(3) time_field 非 None → line（默认折线图）；(4) time_field 为 None → None
    - 更新所有调用 `_infer_chart_type_pure` 的地方，传入 `time_field` 参数
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 1.2 新增完整性校验纯函数
    - 在 `app/services/data_engine/tushare_preview_service.py` 的 `TusharePreviewService` 类中新增以下 `_pure` 静态方法：
      - `_compute_missing_dates_pure(expected_dates: set[str], actual_dates: set[str]) -> list[str]`：计算缺失交易日列表，返回 `sorted(expected - actual)`
      - `_compute_missing_codes_pure(expected_codes: set[str], actual_codes: set[str]) -> list[str]`：计算缺失代码列表，返回 `sorted(expected - actual)`
      - `_determine_check_type_pure(time_field: str | None, has_ts_code: bool) -> str`：判断校验类型（time_series / code_based / unsupported）
      - `_build_completeness_report_pure(check_type: str, expected: set[str], actual: set[str], missing: list[str], time_range: dict | None = None, message: str | None = None) -> dict`：构建完整性报告数据
    - 所有 docstring 使用中文
    - _Requirements: 2.5, 3.3, 3.6, 2.6, 3.4_

  - [x] 1.3 新增 COUNT 估算纯函数
    - 在 `TusharePreviewService` 类中新增静态方法：
      - `_estimate_count_pure(reltuples: float, threshold: int = 1_000_000) -> tuple[bool, int]`：判断是否使用 COUNT 估算，reltuples > threshold 时返回 `(True, int(reltuples))`，否则返回 `(False, 0)`
    - _Requirements: 5.6_

  - [x] 1.4 新增图表数据 limit clamp 纯函数
    - 在 `TusharePreviewService` 类中新增静态方法：
      - `_clamp_chart_limit_pure(limit: int | None) -> int`：图表数据 limit clamp，范围 [1, 500]，默认 250
    - _Requirements: 10.2_

- [x] 2. 后端新增 Pydantic 模型与服务方法
  - [x] 2.1 新增 Pydantic 响应模型
    - 在 `app/services/data_engine/tushare_preview_service.py` 中新增：
      - `CompletenessReport(BaseModel)`：check_type, expected_count, actual_count, missing_count, completeness_rate, missing_items, time_range, message
      - `IntegrityRequest(BaseModel)`：data_time_start, data_time_end（均可选）
      - `ChartDataResponse(BaseModel)`：rows, time_field, chart_type, columns, total_available
    - _Requirements: 8.4, 10.4_

  - [x] 2.2 实现完整性校验服务方法
    - 在 `TusharePreviewService` 类中新增 `async def check_integrity(self, api_name: str, *, data_time_start: str | None = None, data_time_end: str | None = None) -> CompletenessReport`
    - 实现逻辑：
      - 从 `TUSHARE_API_REGISTRY` 获取 `ApiEntry`，不存在则抛出 ValueError
      - 调用 `_get_time_field_pure` 获取时间字段
      - 调用 `_determine_check_type_pure` 判断校验类型
      - 时序数据校验：
        - 查询 `trade_calendar` 表获取 SSE 交易日集合（`exchange='SSE' AND is_open=1`）
        - 若未指定时间范围，查询目标表的 MIN/MAX 时间字段作为默认范围
        - 查询目标表在时间范围内的 DISTINCT 日期集合（应用 scope_filter）
        - 调用 `_compute_missing_dates_pure` 计算缺失
      - 非时序数据校验：
        - 查询 `stock_info` 表获取全部 A 股 ts_code 集合
        - 查询目标表的 DISTINCT ts_code 集合
        - 调用 `_compute_missing_codes_pure` 计算缺失
        - 附加提示信息「预期集合基于全部 A 股代码，实际覆盖范围可能因接口特性而异」
      - 不支持校验：返回 check_type="unsupported"，message="该数据表不支持完整性校验"
      - 调用 `_build_completeness_report_pure` 构建报告
    - 使用只读 SELECT 查询，复用现有 `_get_session` 和 `_build_scope_filter_pure`
    - _Requirements: 2.1-2.8, 3.1-3.6, 8.1-8.6_

  - [x] 2.3 实现图表数据查询服务方法
    - 在 `TusharePreviewService` 类中新增 `async def query_chart_data(self, api_name: str, *, limit: int = 250, data_time_start: str | None = None, data_time_end: str | None = None) -> ChartDataResponse`
    - 实现逻辑：
      - 从 `TUSHARE_API_REGISTRY` 获取 `ApiEntry`
      - 调用 `_clamp_chart_limit_pure` 处理 limit 参数
      - 获取时间字段，无时间字段时返回空 ChartDataResponse（chart_type=None）
      - 构建 SQL：`SELECT * FROM {target_table} WHERE ... ORDER BY {time_field} DESC LIMIT {limit}`
      - 应用 scope_filter 和时间范围过滤
      - 查询数据后反转为升序（图表需要时间升序）
      - 调用扩展后的 `_infer_chart_type_pure` 获取图表类型
      - 构建 `ChartDataResponse`
    - _Requirements: 10.1-10.4_

  - [x] 2.4 实现 COUNT 估算逻辑
    - 修改 `query_preview_data` 方法中的 COUNT 查询逻辑：
      - 先查询 `pg_class.reltuples` 获取估算值
      - 调用 `_estimate_count_pure` 判断是否使用估算
      - 若使用估算，直接用 reltuples 值作为 total；否则执行精确 `COUNT(*)`
      - 捕获 reltuples 查询异常时回退到精确 COUNT
    - _Requirements: 5.6_

- [x] 3. 后端 API 端点扩展
  - [x] 3.1 新增完整性校验端点
    - 在 `app/api/v1/tushare_preview.py` 中新增：
      - `POST /{api_name}/check-integrity`：接受 JSON body（IntegrityRequest），调用 `TusharePreviewService.check_integrity()`
      - 错误处理：api_name 不存在返回 404，数据库查询失败返回 500
    - _Requirements: 2.1, 8.1, 8.5_

  - [x] 3.2 新增图表数据端点
    - 在 `app/api/v1/tushare_preview.py` 中新增：
      - `GET /{api_name}/chart-data`：接受 limit、data_time_start、data_time_end 查询参数，调用 `TusharePreviewService.query_chart_data()`
      - 错误处理：api_name 不存在返回 404
    - _Requirements: 10.1-10.4_

- [x] 4. Checkpoint - 后端增强功能验证
  - 运行 `pytest tests/services/test_tushare_preview_service.py tests/properties/test_tushare_preview_properties.py` 确保现有测试不受影响
  - 手动验证新增端点可正常响应（可选）

- [x] 5. 前端纯函数与精度规则
  - [x] 5.1 实现数值精度规则
    - 在 `frontend/src/components/PreviewTable.vue` 中新增导出的纯函数和常量：
      - `PRECISION_RULES` 常量数组：按优先级定义字段名正则 → 小数位数映射
        - 成交量类（vol, volume）→ 0
        - 价格类（open, high, low, close, price, avg_price, amount）→ 2
        - 涨跌幅类（pct_chg, change）→ 2
        - 换手率类（turnover_rate）→ 2
        - 市值类（total_mv, circ_mv, market_cap）→ 2
        - 市盈率/市净率类（pe, pb, pe_ttm, ps, ps_ttm）→ 2
      - `DEFAULT_PRECISION = 4`
      - `getFieldPrecision(fieldName: string): number`：遍历 PRECISION_RULES，返回第一个匹配的 decimals，无匹配返回 DEFAULT_PRECISION
    - 修改 `formatCell` 函数：
      - 新增 `fieldName` 参数
      - 对数值型单元格调用 `getFieldPrecision` 获取精度，使用 `toFixed()` 格式化
      - 对大数值（|value| >= 10000）添加千分位分隔符
      - 整数值直接显示为整数（不添加小数位）
    - 更新 template 中 `formatCell` 调用，传入 `col.name`
    - _Requirements: 6.1-6.8, 7.1-7.4_

  - [x] 5.2 扩展前端图表类型推断
    - 在 `frontend/src/stores/tusharePreview.ts` 中：
      - 新增 `CHART_TYPE_MAP` 常量（与后端一致的 subcategory → chart_type 映射）
      - 修改 `inferChartType` 函数签名，新增 `timeField: string | null` 参数
      - 更新推断逻辑：KLINE_TABLES → candlestick；CHART_TYPE_MAP → 对应类型；timeField 非 null → line；否则 → null
      - 返回类型扩展为 `'candlestick' | 'line' | 'bar' | null`
    - _Requirements: 9.1, 9.3, 9.4_

  - [x] 5.3 新增默认列选择纯函数
    - 在 `frontend/src/stores/tusharePreview.ts` 中新增导出函数：
      - `getDefaultSelectedColumns(numericColumns: string[]): string[]`：返回前 `min(3, N)` 个列名
    - _Requirements: 11.2_

- [x] 6. 前端 Store 扩展
  - [x] 6.1 扩展 tusharePreview Store
    - 在 `frontend/src/stores/tusharePreview.ts` 中新增：
      - 类型定义：`CompletenessReport`、`ChartDataResponse`
      - 状态：`integrityReport`、`integrityLoading`、`chartData`、`chartDataLoading`、`selectedChartColumns`
      - 方法：
        - `checkIntegrity(apiName, timeRange?)`：调用 `POST /preview/{api_name}/check-integrity`
        - `fetchChartData(apiName, limit?)`：调用 `GET /preview/{api_name}/chart-data`
        - `setSelectedChartColumns(columns)`：设置图表选中列
        - `clearIntegrityReport()`：清除校验结果
      - 修改 `setSelectedApi`：并行请求中新增 `fetchChartData`
    - _Requirements: 1.3, 10.5, 11.3_

- [x] 7. 前端组件增强
  - [x] 7.1 增强 PreviewChart.vue — 列选择器与独立数据
    - 在 `frontend/src/components/PreviewChart.vue` 中：
      - 新增 props：`selectedColumns?: string[]`
      - 新增 emit：`update:selectedColumns`
      - 在图表上方新增列选择器 UI（仅 chartType 为 line 或 bar 时显示）：
        - 显示所有数值列的中文标签（来自 columns 的 label）
        - 支持勾选/取消勾选
        - 默认选中前 3 个数值列
      - K 线图（candlestick）不显示列选择器
      - 修改折线图/柱状图构建函数，仅使用 selectedColumns 中的列
    - _Requirements: 11.1-11.5_

  - [x] 7.2 增强 TusharePreviewView.vue — 完整性校验与图表数据
    - 在 `frontend/src/views/TusharePreviewView.vue` 中：
      - 查询条件栏新增「完整性校验」按钮（在「查看增量数据」按钮右侧）
        - 未选择 API 时禁用
        - 点击时调用 `store.checkIntegrity()`，按钮显示加载状态
      - 查询条件栏下方新增可折叠的 Completeness_Report 卡片：
        - 显示校验摘要：校验类型、预期数量、实际数量、缺失数量、完整率
        - 数据完整时绿色提示「数据完整，无缺失」
        - 有缺失时红色高亮摘要 + 缺失详情列表
        - 缺失列表超过 50 条时默认折叠，提供「展开全部」按钮
        - 提供「关闭」按钮
      - 图表区域改用 `store.chartData` 数据渲染（而非 `store.previewData.rows`）
      - 图表组件传入 `selectedChartColumns` 和 `update:selectedColumns` 事件
      - 查询时并行发送表格分页请求和图表数据请求
    - _Requirements: 1.1-1.6, 4.1-4.5, 10.5, 10.6, 11.1-11.5_

- [x] 8. 后端属性测试
  - [x] 8.1 编写增强功能后端属性测试
    - 新建 `tests/properties/test_tushare_preview_enhancement_properties.py`
    - 编写以下属性测试（使用 Hypothesis，`@settings(max_examples=100)`）：
      - **Property 1: Set difference computation for missing items**
        - 生成任意两个字符串集合，验证 `_compute_missing_dates_pure` 和 `_compute_missing_codes_pure` 返回 `sorted(expected - actual)`
        - Tag: `# Feature: tushare-data-preview-enhancement, Property 1: Set difference computation for missing items`
      - **Property 2: Completeness report field consistency**
        - 生成任意 expected/actual 集合，验证 `_build_completeness_report_pure` 返回的字段一致性
        - Tag: `# Feature: tushare-data-preview-enhancement, Property 2: Completeness report field consistency`
      - **Property 3: Check type determination**
        - 生成任意 (time_field, has_ts_code) 组合，验证 `_determine_check_type_pure` 返回正确类型
        - Tag: `# Feature: tushare-data-preview-enhancement, Property 3: Check type determination`
      - **Property 4: COUNT estimation threshold**
        - 生成任意非负浮点数，验证 `_estimate_count_pure` 的阈值行为
        - Tag: `# Feature: tushare-data-preview-enhancement, Property 4: COUNT estimation threshold`
      - **Property 7: Expanded chart type inference follows priority rules**
        - 生成任意 (target_table, subcategory, time_field) 组合，验证扩展后的 `_infer_chart_type_pure` 优先级规则
        - Tag: `# Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules`
      - **Property 8: Chart data limit clamping**
        - 生成任意整数，验证 `_clamp_chart_limit_pure` 的 clamp 行为
        - Tag: `# Feature: tushare-data-preview-enhancement, Property 8: Chart data limit clamping`
    - _Requirements: 2.5, 2.6, 3.3, 3.4, 3.6, 5.6, 9.1, 9.3, 9.4, 10.2_

- [x] 9. 后端单元测试与集成测试
  - [x] 9.1 编写增强功能后端单元测试
    - 新建 `tests/services/test_tushare_preview_enhancement.py`
    - 编写以下单元测试（Mock 数据库 session）：
      - `test_check_integrity_time_series_complete`：时序数据完整时 missing_count=0
      - `test_check_integrity_time_series_with_gaps`：时序数据有缺失时返回正确缺失日期
      - `test_check_integrity_code_based`：非时序数据校验返回缺失代码
      - `test_check_integrity_unsupported`：不支持校验的表返回 unsupported
      - `test_check_integrity_uses_sse_calendar`：验证使用 SSE 交易日历
      - `test_check_integrity_applies_scope_filter`：验证校验时应用作用域过滤
      - `test_query_chart_data_returns_ascending_order`：图表数据按时间升序
      - `test_query_chart_data_default_limit_250`：默认返回 250 条
      - `test_query_chart_data_no_time_field_returns_empty`：无时间字段返回空
      - `test_estimate_count_uses_reltuples_for_large_tables`：大表使用估算
      - `test_estimate_count_uses_exact_for_small_tables`：小表使用精确 COUNT
      - `test_infer_chart_type_expanded_mapping`：验证各 subcategory 的图表类型映射
    - _Requirements: 2.1-2.8, 3.1-3.6, 5.6, 9.1-9.4, 10.1-10.4_

  - [x] 9.2 编写增强功能 API 集成测试
    - 新建 `tests/api/test_tushare_preview_enhancement_api.py`
    - 编写以下测试（Mock TusharePreviewService）：
      - `test_check_integrity_endpoint_time_series`：完整性校验端点（时序）
      - `test_check_integrity_endpoint_code_based`：完整性校验端点（非时序）
      - `test_check_integrity_endpoint_unknown_api`：未知接口返回 404
      - `test_chart_data_endpoint_returns_data`：图表数据端点返回数据
      - `test_chart_data_endpoint_with_filters`：图表数据端点带筛选参数
      - `test_chart_data_endpoint_limit_clamping`：limit 参数 clamp
    - _Requirements: 2.1, 8.1, 8.5, 10.1-10.4_

- [x] 10. Checkpoint - 后端增强测试通过
  - 运行 `pytest tests/services/test_tushare_preview_enhancement.py tests/properties/test_tushare_preview_enhancement_properties.py tests/api/test_tushare_preview_enhancement_api.py` 确保所有后端测试通过
  - 运行 `pytest tests/services/test_tushare_preview_service.py tests/properties/test_tushare_preview_properties.py` 确保现有测试不受影响

- [x] 11. 前端属性测试与单元测试
  - [x] 11.1 编写增强功能前端属性测试
    - 新建 `frontend/src/components/__tests__/previewEnhancement.property.test.ts`
    - 编写以下属性测试（使用 fast-check，`fc.assert(property, { numRuns: 100 })`）：
      - **Property 5: Field precision rule matching**
        - 生成任意字段名字符串，验证 `getFieldPrecision` 对已知模式返回正确精度，未知字段返回 4
        - Tag: `// Feature: tushare-data-preview-enhancement, Property 5: Field precision rule matching`
      - **Property 6: Large number formatting includes thousand separators**
        - 生成任意数值（|value| >= 10000），验证格式化结果包含逗号；生成 |value| < 10000 的数值，验证无逗号
        - Tag: `// Feature: tushare-data-preview-enhancement, Property 6: Large number formatting includes thousand separators`
      - **Property 7: Expanded chart type inference follows priority rules**
        - 生成任意 (targetTable, subcategory, timeField) 组合，验证 `inferChartType` 优先级规则
        - Tag: `// Feature: tushare-data-preview-enhancement, Property 7: Expanded chart type inference follows priority rules`
      - **Property 9: Default chart column selection**
        - 生成任意字符串数组，验证 `getDefaultSelectedColumns` 返回前 min(3, N) 个元素
        - Tag: `// Feature: tushare-data-preview-enhancement, Property 9: Default chart column selection`
    - _Requirements: 6.1-6.7, 7.3, 9.1, 9.3, 9.4, 11.2_

  - [x] 11.2 编写增强功能前端单元测试
    - 新建 `frontend/src/components/__tests__/PreviewTableEnhancement.test.ts`
    - 编写以下单元测试：
      - `test_format_cell_price_precision`：价格字段 2 位小数
      - `test_format_cell_volume_integer`：成交量字段整数显示
      - `test_format_cell_large_number_with_commas`：大数值千分位
      - `test_format_cell_integer_no_decimals`：整数值不添加小数位
      - `test_format_cell_default_precision`：未知字段 4 位小数
    - 新建 `frontend/src/components/__tests__/PreviewChartEnhancement.test.ts`
    - 编写以下单元测试：
      - `test_column_selector_shown_for_line_chart`：折线图显示列选择器
      - `test_column_selector_hidden_for_candlestick`：K 线图不显示列选择器
      - `test_default_selected_columns_max_3`：默认选中前 3 列
      - `test_column_toggle_updates_chart`：切换列更新图表
    - _Requirements: 6.1-6.8, 7.2-7.3, 11.1-11.5_

- [x] 12. Final checkpoint - 全部测试通过
  - 运行后端全部测试：`pytest tests/services/test_tushare_preview_enhancement.py tests/properties/test_tushare_preview_enhancement_properties.py tests/api/test_tushare_preview_enhancement_api.py`
  - 运行前端全部测试：`cd frontend && npm test`
  - 确保现有 tushare-data-preview 测试不受影响
  - 如有问题请向用户确认

## Notes

- 所有新增逻辑在现有文件中扩展（tushare_preview_service.py、tushare_preview.py、PreviewTable.vue、PreviewChart.vue、TusharePreviewView.vue、tusharePreview.ts），不新建服务文件
- 纯函数（`_pure` 后缀或独立导出）用于属性测试，隔离数据库依赖
- 完整性校验使用 SSE 交易日历（SSE 和 SZSE 交易日一致）
- COUNT 估算仅在 reltuples > 1,000,000 时启用，小表仍用精确 COUNT
- 图表数据端点默认 250 条，最大 500 条，独立于表格分页
- 列选择器仅限折线图/柱状图，K 线图固定 OHLC 四列
- 精度规则按优先级匹配：成交量(0) > 价格/涨跌幅/换手率/市值/PE-PB(2) > 默认(4)
- 所有新 Python 代码使用中文 docstring 和注释
- 属性测试验证设计文档中的 9 个正确性属性（Property 1-9）
- 本增强不修改现有端点的请求/响应格式，不修改现有方法签名
