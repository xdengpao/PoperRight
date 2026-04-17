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
  }
})
