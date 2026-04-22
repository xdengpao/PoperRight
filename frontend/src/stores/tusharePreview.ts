/**
 * Tushare 数据预览 Pinia Store
 *
 * 管理 Tushare 数据预览页面的状态，包括：
 * - API 注册表（复用 /data/tushare/registry 端点）
 * - 预览数据查询（分页、时间筛选、增量查询）
 * - 统计信息和导入记录
 * - 展示模式切换（表格/图表/两者）
 *
 * 纯函数（groupRegistryByCategory、getStatusColor、inferChartType）
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

/** 资金流向数据子分类 */
const MONEYFLOW_SUBCATEGORY = '资金流向数据'

/**
 * 前端侧图表类型推断
 *
 * kline / sector_kline → 'candlestick'
 * subcategory 为 '资金流向数据' → 'line'
 * 其余 → null
 */
export function inferChartType(
  targetTable: string,
  subcategory: string,
): 'candlestick' | 'line' | null {
  if (KLINE_TABLES.has(targetTable)) {
    return 'candlestick'
  }
  if (subcategory === MONEYFLOW_SUBCATEGORY) {
    return 'line'
  }
  return null
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

  /** 设置当前选中的 API 并触发数据加载 */
  async function setSelectedApi(apiName: string) {
    selectedApiName.value = apiName
    filters.value = createDefaultFilters()
    // 并行加载预览数据、统计信息和导入记录
    await Promise.all([
      fetchPreviewData(apiName),
      fetchStats(apiName),
      fetchImportLogs(apiName),
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
    // 方法
    fetchRegistry,
    fetchPreviewData,
    fetchStats,
    fetchImportLogs,
    setSelectedApi,
    setDisplayMode,
    resetFilters,
  }
})
