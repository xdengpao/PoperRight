import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api'

export interface SectorRankingItem {
  sector_code: string
  name: string
  sector_type: string
  change_pct: number | null
  close: number | null
  volume: number | null
  amount: number | null
  turnover: number | null
}

export interface SectorKlineBar {
  time: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
}

export type SectorTypeFilter = '' | 'CONCEPT' | 'INDUSTRY' | 'REGION' | 'STYLE'
export type DataSourceFilter = '' | 'DC' | 'TI' | 'TDX'

// ─── 浏览面板类型定义（需求 14） ──────────────────────────────────────────────

export type BrowserTab = 'info' | 'constituent' | 'kline'

export interface BrowseTabState<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  error: string
  filters: Record<string, string>
}

export interface SectorInfoBrowseItem {
  sector_code: string
  name: string
  sector_type: string
  data_source: string
  list_date: string | null
  constituent_count: number | null
}

export interface ConstituentBrowseItem {
  trade_date: string
  sector_code: string
  data_source: string
  symbol: string
  stock_name: string | null
}

export interface KlineBrowseItem {
  time: string
  sector_code: string
  data_source: string
  freq: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  amount: number | null
  change_pct: number | null
}

export interface BrowseResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export const useSectorStore = defineStore('sector', () => {
  const rankings = ref<SectorRankingItem[]>([])
  const currentType = ref<SectorTypeFilter>('')
  const currentDataSource = ref<DataSourceFilter>('')
  const loading = ref(false)
  const error = ref('')

  // K线展开状态
  const expandedSectorCode = ref<string | null>(null)
  const expandedKlineData = ref<SectorKlineBar[]>([])
  const expandedKlineLoading = ref(false)
  const expandedKlineError = ref('')

  async function fetchRanking(sectorType?: SectorTypeFilter, dataSource?: DataSourceFilter) {
    loading.value = true
    error.value = ''
    try {
      const params: Record<string, string> = {}
      const st = sectorType ?? currentType.value
      const ds = dataSource ?? currentDataSource.value
      if (st) params.sector_type = st
      if (ds) params.data_source = ds
      const res = await apiClient.get<SectorRankingItem[]>('/sector/ranking', { params })
      rankings.value = res.data
    } catch (err) {
      error.value = '获取板块排行数据失败'
      // 保留上一次成功数据，不清空 rankings
    } finally {
      loading.value = false
    }
  }

  function setSectorType(type: SectorTypeFilter) {
    currentType.value = type
    fetchRanking(type || undefined, currentDataSource.value || undefined)
  }

  function setDataSource(source: DataSourceFilter) {
    currentDataSource.value = source
    fetchRanking(currentType.value || undefined, source || undefined)
  }

  async function toggleSectorKline(sectorCode: string, dataSource?: string) {
    // 点击同一板块 → 收起
    if (expandedSectorCode.value === sectorCode) {
      expandedSectorCode.value = null
      expandedKlineData.value = []
      expandedKlineError.value = ''
      return
    }

    // 展开新板块
    expandedSectorCode.value = sectorCode
    expandedKlineLoading.value = true
    expandedKlineError.value = ''
    expandedKlineData.value = []

    try {
      const today = new Date()
      const oneYearAgo = new Date(today)
      oneYearAgo.setFullYear(today.getFullYear() - 1)

      const params: Record<string, string> = {
        data_source: dataSource || currentDataSource.value || 'DC',
        freq: '1d',
        start: oneYearAgo.toISOString().slice(0, 10),
        end: today.toISOString().slice(0, 10),
      }

      const res = await apiClient.get<SectorKlineBar[]>(
        `/sector/${sectorCode}/kline`,
        { params },
      )
      expandedKlineData.value = res.data
    } catch {
      expandedKlineError.value = '获取板块K线数据失败'
    } finally {
      expandedKlineLoading.value = false
    }
  }

  // ─── 浏览面板状态（需求 14） ──────────────────────────────────────────────

  const browserActiveTab = ref<BrowserTab>('info')

  const infoBrowse = ref<BrowseTabState<SectorInfoBrowseItem>>({
    items: [],
    total: 0,
    page: 1,
    pageSize: 50,
    loading: false,
    error: '',
    filters: { data_source: 'DC', sector_type: '', keyword: '' },
  })

  const constituentBrowse = ref<BrowseTabState<ConstituentBrowseItem>>({
    items: [],
    total: 0,
    page: 1,
    pageSize: 50,
    loading: false,
    error: '',
    filters: { data_source: 'DC', sector_code: '', trade_date: '', keyword: '' },
  })

  const klineBrowse = ref<BrowseTabState<KlineBrowseItem>>({
    items: [],
    total: 0,
    page: 1,
    pageSize: 50,
    loading: false,
    error: '',
    filters: { data_source: 'DC', sector_code: '', freq: '1d', start: '', end: '' },
  })

  function setBrowserTab(tab: BrowserTab) {
    browserActiveTab.value = tab
  }

  async function fetchSectorInfoBrowse(page?: number) {
    const state = infoBrowse.value
    if (page !== undefined) state.page = page
    state.loading = true
    state.error = ''
    try {
      const params: Record<string, string> = {
        page: String(state.page),
        page_size: String(state.pageSize),
      }
      for (const [key, val] of Object.entries(state.filters)) {
        if (val) params[key] = val
      }
      const res = await apiClient.get<BrowseResponse<SectorInfoBrowseItem>>(
        '/sector/info/browse',
        { params },
      )
      state.items = res.data.items
      state.total = res.data.total
      state.page = res.data.page
    } catch {
      state.error = '获取板块数据失败'
      // 保留上次数据
    } finally {
      state.loading = false
    }
  }

  async function fetchConstituentBrowse(page?: number) {
    const state = constituentBrowse.value
    if (page !== undefined) state.page = page
    state.loading = true
    state.error = ''
    try {
      const params: Record<string, string> = {
        page: String(state.page),
        page_size: String(state.pageSize),
      }
      for (const [key, val] of Object.entries(state.filters)) {
        if (val) params[key] = val
      }
      const res = await apiClient.get<BrowseResponse<ConstituentBrowseItem>>(
        '/sector/constituent/browse',
        { params },
      )
      state.items = res.data.items
      state.total = res.data.total
      state.page = res.data.page
    } catch {
      state.error = '获取板块成分数据失败'
      // 保留上次数据
    } finally {
      state.loading = false
    }
  }

  async function fetchKlineBrowse(page?: number) {
    const state = klineBrowse.value
    if (page !== undefined) state.page = page
    state.loading = true
    state.error = ''
    try {
      const params: Record<string, string> = {
        page: String(state.page),
        page_size: String(state.pageSize),
      }
      for (const [key, val] of Object.entries(state.filters)) {
        if (val) params[key] = val
      }
      const res = await apiClient.get<BrowseResponse<KlineBrowseItem>>(
        '/sector/kline/browse',
        { params },
      )
      state.items = res.data.items
      state.total = res.data.total
      state.page = res.data.page
    } catch {
      state.error = '获取板块行情数据失败'
      // 保留上次数据
    } finally {
      state.loading = false
    }
  }

  function updateInfoFilters(newFilters: Partial<Record<string, string>>) {
    Object.assign(infoBrowse.value.filters, newFilters)
    infoBrowse.value.page = 1
    fetchSectorInfoBrowse()
  }

  function updateConstituentFilters(newFilters: Partial<Record<string, string>>) {
    Object.assign(constituentBrowse.value.filters, newFilters)
    constituentBrowse.value.page = 1
    fetchConstituentBrowse()
  }

  function updateKlineFilters(newFilters: Partial<Record<string, string>>) {
    Object.assign(klineBrowse.value.filters, newFilters)
    klineBrowse.value.page = 1
    fetchKlineBrowse()
  }

  return {
    rankings,
    currentType,
    currentDataSource,
    loading,
    error,
    fetchRanking,
    setSectorType,
    setDataSource,
    expandedSectorCode,
    expandedKlineData,
    expandedKlineLoading,
    expandedKlineError,
    toggleSectorKline,
    // 浏览面板状态和方法
    browserActiveTab,
    infoBrowse,
    constituentBrowse,
    klineBrowse,
    setBrowserTab,
    fetchSectorInfoBrowse,
    fetchConstituentBrowse,
    fetchKlineBrowse,
    updateInfoFilters,
    updateConstituentFilters,
    updateKlineFilters,
  }
})
