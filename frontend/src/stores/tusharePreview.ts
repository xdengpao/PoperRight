/**
 * Tushare 数据预览 Pinia Store
 *
 * 管理 Tushare 数据预览页面的状态，包括：
 * - API 注册表（复用 /data/tushare/registry 端点）
 * - 预览数据查询（分页、时间筛选、增量查询）
 * - 统计信息和导入记录
 * - 展示模式切换（表格/图表/两者）
 *
 * 纯函数（groupRegistryByCategory、getStatusColor、inferChartType、getDefaultSelectedColumns）
 * 独立导出供属性测试使用。
 *
 * 对应需求：2.1-2.5, 3.1-3.4, 4.1-4.5, 5.1-5.4, 7.1-7.5, 8.1, 10.1-10.4
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

/** API 注册表条目（与后端 ApiRegistryItem 对应） */
export interface ApiRegistryItem {
  api_name: string
  label: string
  category: string
  subcategory: string
  token_tier: string
  required_params: string[]
  optional_params: string[]
  token_available: boolean
  vip_variant?: string | null
}

/** 列信息 */
export interface ColumnInfo {
  name: string
  label: string
  type: 'string' | 'number' | 'date' | 'datetime'
}

/** 增量查询关联的导入记录信息 */
export interface IncrementalInfo {
  import_log_id: number
  import_time: string
  record_count: number
  status: string
  params_summary: string
}

/** 预览数据响应 */
export interface PreviewDataResponse {
  columns: ColumnInfo[]
  rows: Record<string, unknown>[]
  total: number
  page: number
  page_size: number
  time_field: string | null
  chart_type: 'candlestick' | 'line' | 'bar' | null
  scope_info: string | null
  incremental_info: IncrementalInfo | null
}

/** 统计信息响应 */
export interface PreviewStatsResponse {
  total_count: number
  earliest_time: string | null
  latest_time: string | null
  last_import_at: string | null
  last_import_count: number
}

/** 导入记录条目 */
export interface ImportLogItem {
  id: number
  api_name: string
  params_json: Record<string, unknown> | null
  status: string
  record_count: number
  error_message: string | null
  started_at: string | null
  finished_at: string | null
}

/** 预览筛选条件 */
export interface PreviewFilters {
  importTimeStart: string | null
  importTimeEnd: string | null
  dataTimeStart: string | null
  dataTimeEnd: string | null
  incremental: boolean
  importLogId: number | null
  page: number
  pageSize: number
}

/** 展示模式 */
export type DisplayMode = 'table' | 'chart' | 'both'

/** 完整性校验结果报告 */
export interface CompletenessReport {
  check_type: 'time_series' | 'code_based' | 'unsupported'
  expected_count: number
  actual_count: number
  missing_count: number
  completeness_rate: number
  missing_items: string[]
  time_range: { start: string; end: string } | null
  message: string | null
}

/** 图表数据响应（独立于表格分页） */
export interface ChartDataResponse {
  rows: Record<string, unknown>[]
  time_field: string | null
  chart_type: 'candlestick' | 'line' | 'bar' | null
  columns: ColumnInfo[]
  total_available: number
}

// ─── 纯函数（导出供属性测试使用） ─────────────────────────────────────────────

/** 分组结构：category → subcategory → api 列表 */
export interface CategoryGroup {
  category: string
  subcategories: SubcategoryGroup[]
}

export interface SubcategoryGroup {
  subcategory: string
  apis: ApiRegistryItem[]
}

/**
 * 将注册表条目按 category → subcategory 分组
 *
 * 每个条目恰好出现一次，子分类计数等于该组内条目数。
 */
export function groupRegistryByCategory(
  entries: ApiRegistryItem[],
): CategoryGroup[] {
  const categoryMap = new Map<string, Map<string, ApiRegistryItem[]>>()

  for (const entry of entries) {
    let subcatMap = categoryMap.get(entry.category)
    if (!subcatMap) {
      subcatMap = new Map<string, ApiRegistryItem[]>()
      categoryMap.set(entry.category, subcatMap)
    }
    let apis = subcatMap.get(entry.subcategory)
    if (!apis) {
      apis = []
      subcatMap.set(entry.subcategory, apis)
    }
    apis.push(entry)
  }

  const result: CategoryGroup[] = []
  for (const [category, subcatMap] of categoryMap) {
    const subcategories: SubcategoryGroup[] = []
    for (const [subcategory, apis] of subcatMap) {
      subcategories.push({ subcategory, apis })
    }
    result.push({ category, subcategories })
  }
  return result
}

/**
 * 导入状态到 CSS 类映射
 *
 * completed → 'status-green'
 * failed    → 'status-red'
 * running   → 'status-blue'
 * pending   → 'status-blue'
 * stopped   → 'status-gray'
 * 其他      → 'status-default'
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'status-green'
    case 'failed':
      return 'status-red'
    case 'running':
    case 'pending':
      return 'status-blue'
    case 'stopped':
      return 'status-gray'
    default:
      return 'status-default'
  }
}

/** K 线表集合 */
const KLINE_TABLES = new Set(['kline', 'sector_kline'])

/**
 * 完整图表类型映射（与后端 CHART_TYPE_MAP 一致）
 *
 * subcategory → chart_type
 */
export const CHART_TYPE_MAP = new Map<string, 'line' | 'bar'>([
  ['资金流向数据', 'line'],
  ['两融及转融通', 'line'],
  ['特色数据', 'line'],
  ['大盘指数每日指标', 'line'],
  ['指数技术面因子（专业版）', 'line'],
  ['打板专题数据', 'bar'],
  ['沪深市场每日交易统计', 'bar'],
  ['深圳市场每日交易情况', 'bar'],
])

/**
 * 前端侧图表类型推断
 *
 * 规则优先级：
 * 1. target_table 在 KLINE_TABLES 中 → candlestick
 * 2. subcategory 在 CHART_TYPE_MAP 中 → 对应类型（line 或 bar）
 * 3. timeField 非 null → line（默认折线图）
 * 4. timeField 为 null → null
 */
export function inferChartType(
  targetTable: string,
  subcategory: string,
  timeField: string | null,
): 'candlestick' | 'line' | 'bar' | null {
  if (KLINE_TABLES.has(targetTable)) {
    return 'candlestick'
  }
  const mapped = CHART_TYPE_MAP.get(subcategory)
  if (mapped) {
    return mapped
  }
  if (timeField != null) {
    return 'line'
  }
  return null
}

/**
 * 获取默认选中的图表列
 *
 * 返回前 min(3, N) 个列名，保持原始顺序。
 */
export function getDefaultSelectedColumns(numericColumns: string[]): string[] {
  return numericColumns.slice(0, Math.min(3, numericColumns.length))
}

// ─── 默认筛选条件 ─────────────────────────────────────────────────────────────

function createDefaultFilters(): PreviewFilters {
  return {
    importTimeStart: null,
    importTimeEnd: null,
    dataTimeStart: null,
    dataTimeEnd: null,
    incremental: false,
    importLogId: null,
    page: 1,
    pageSize: 50,
  }
}

// ─── Pinia Store ──────────────────────────────────────────────────────────────

export const useTusharePreviewStore = defineStore('tusharePreview', () => {
  // ── 状态 ──────────────────────────────────────────────────────────────────

  /** API 注册表列表 */
  const registry = ref<ApiRegistryItem[]>([])
  /** 注册表加载中 */
  const registryLoading = ref(false)

  /** 当前选中的 API 名称 */
  const selectedApiName = ref<string | null>(null)
  /** 当前选中的分类 */
  const selectedCategory = ref<string | null>(null)

  /** 预览数据 */
  const previewData = ref<PreviewDataResponse | null>(null)
  /** 预览数据加载中 */
  const previewLoading = ref(false)

  /** 统计信息 */
  const stats = ref<PreviewStatsResponse | null>(null)

  /** 导入记录列表 */
  const importLogs = ref<ImportLogItem[]>([])
  /** 导入记录加载中 */
  const importLogsLoading = ref(false)

  /** 筛选条件 */
  const filters = ref<PreviewFilters>(createDefaultFilters())

  /** 展示模式 */
  const displayMode = ref<DisplayMode>('table')

  /** 完整性校验结果 */
  const integrityReport = ref<CompletenessReport | null>(null)
  /** 完整性校验加载中 */
  const integrityLoading = ref(false)

  /** 图表数据（独立于表格分页） */
  const chartData = ref<ChartDataResponse | null>(null)
  /** 图表数据加载中 */
  const chartDataLoading = ref(false)

  /** 图表选中的列名列表 */
  const selectedChartColumns = ref<string[]>([])

  // ── 方法 ──────────────────────────────────────────────────────────────────

  /** 获取 API 注册表列表 */
  async function fetchRegistry() {
    registryLoading.value = true
    try {
      const res = await apiClient.get<ApiRegistryItem[]>('/data/tushare/registry')
      registry.value = res.data
    } catch {
      registry.value = []
    } finally {
      registryLoading.value = false
    }
  }

  /** 获取预览数据 */
  async function fetchPreviewData(apiName: string, queryFilters?: Partial<PreviewFilters>) {
    previewLoading.value = true
    try {
      const f = queryFilters ?? filters.value
      const params: Record<string, unknown> = {
        page: f.page ?? 1,
        page_size: f.pageSize ?? 50,
      }
      if (f.importTimeStart) params.import_time_start = f.importTimeStart
      if (f.importTimeEnd) params.import_time_end = f.importTimeEnd
      if (f.dataTimeStart) params.data_time_start = f.dataTimeStart
      if (f.dataTimeEnd) params.data_time_end = f.dataTimeEnd
      if (f.incremental) params.incremental = true
      if (f.importLogId != null) params.import_log_id = f.importLogId

      const res = await apiClient.get<PreviewDataResponse>(
        `/data/tushare/preview/${encodeURIComponent(apiName)}`,
        { params },
      )
      previewData.value = res.data
    } catch {
      previewData.value = null
    } finally {
      previewLoading.value = false
    }
  }

  /** 获取统计信息 */
  async function fetchStats(apiName: string) {
    try {
      const res = await apiClient.get<PreviewStatsResponse>(
        `/data/tushare/preview/${encodeURIComponent(apiName)}/stats`,
      )
      stats.value = res.data
    } catch {
      stats.value = null
    }
  }

  /** 获取导入记录列表 */
  async function fetchImportLogs(apiName: string, limit?: number) {
    importLogsLoading.value = true
    try {
      const params: Record<string, unknown> = {}
      if (limit != null) params.limit = limit
      const res = await apiClient.get<ImportLogItem[]>(
        `/data/tushare/preview/${encodeURIComponent(apiName)}/import-logs`,
        { params },
      )
      importLogs.value = res.data
    } catch {
      importLogs.value = []
    } finally {
      importLogsLoading.value = false
    }
  }

  /** 完整性校验 */
  async function checkIntegrity(apiName: string, timeRange?: { start?: string; end?: string }) {
    integrityLoading.value = true
    try {
      const body: Record<string, unknown> = {}
      if (timeRange?.start) body.data_time_start = timeRange.start
      if (timeRange?.end) body.data_time_end = timeRange.end

      const res = await apiClient.post<CompletenessReport>(
        `/data/tushare/preview/${encodeURIComponent(apiName)}/check-integrity`,
        body,
      )
      integrityReport.value = res.data
    } catch {
      integrityReport.value = null
    } finally {
      integrityLoading.value = false
    }
  }

  /** 获取图表数据（独立于表格分页） */
  async function fetchChartData(apiName: string, limit?: number) {
    chartDataLoading.value = true
    try {
      const params: Record<string, unknown> = {}
      if (limit != null) params.limit = limit

      const res = await apiClient.get<ChartDataResponse>(
        `/data/tushare/preview/${encodeURIComponent(apiName)}/chart-data`,
        { params },
      )
      chartData.value = res.data
    } catch {
      chartData.value = null
    } finally {
      chartDataLoading.value = false
    }
  }

  /** 设置图表选中列 */
  function setSelectedChartColumns(columns: string[]) {
    selectedChartColumns.value = columns
  }

  /** 清除完整性校验结果 */
  function clearIntegrityReport() {
    integrityReport.value = null
  }

  /** 设置当前选中的 API 并触发数据加载 */
  async function setSelectedApi(apiName: string) {
    selectedApiName.value = apiName
    filters.value = createDefaultFilters()
    // 并行加载预览数据、统计信息、导入记录和图表数据
    await Promise.all([
      fetchPreviewData(apiName),
      fetchStats(apiName),
      fetchImportLogs(apiName),
      fetchChartData(apiName),
    ])
  }

  /** 切换展示模式 */
  function setDisplayMode(mode: DisplayMode) {
    displayMode.value = mode
  }

  /** 重置筛选条件 */
  function resetFilters() {
    filters.value = createDefaultFilters()
  }

  /** 删除数据状态 */
  const deleteLoading = ref(false)

  /** 删除指定时间范围内的数据 */
  async function deleteData(apiName: string, dataTimeStart: string | null, dataTimeEnd: string | null): Promise<{ deleted_count: number } | null> {
    deleteLoading.value = true
    try {
      const res = await apiClient.post<{ deleted_count: number; target_table: string }>(
        `/data/tushare/preview/${encodeURIComponent(apiName)}/delete-data`,
        {
          data_time_start: dataTimeStart || null,
          data_time_end: dataTimeEnd || null,
        },
      )
      // 删除后刷新数据
      await Promise.all([
        fetchPreviewData(apiName),
        fetchStats(apiName),
        fetchChartData(apiName),
      ])
      return res.data
    } catch {
      return null
    } finally {
      deleteLoading.value = false
    }
  }

  return {
    // 状态
    registry,
    registryLoading,
    selectedApiName,
    selectedCategory,
    previewData,
    previewLoading,
    stats,
    importLogs,
    importLogsLoading,
    filters,
    displayMode,
    integrityReport,
    integrityLoading,
    chartData,
    chartDataLoading,
    selectedChartColumns,
    deleteLoading,
    // 方法
    fetchRegistry,
    fetchPreviewData,
    fetchStats,
    fetchImportLogs,
    checkIntegrity,
    fetchChartData,
    deleteData,
    setSelectedChartColumns,
    clearIntegrityReport,
    setSelectedApi,
    setDisplayMode,
    resetFilters,
  }
})
