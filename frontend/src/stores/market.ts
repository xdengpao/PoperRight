import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api'

export interface MarketOverview {
  sh_index: number
  sh_change_pct: number
  sz_index: number
  sz_change_pct: number
  cyb_index: number
  cyb_change_pct: number
  advance_count: number
  decline_count: number
  limit_up_count: number
  limit_down_count: number
  updated_at: string
}

export const useMarketStore = defineStore('market', () => {
  const overview = ref<MarketOverview | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchOverview() {
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get<MarketOverview>('/data/market/overview', { timeout: 20000 })
      overview.value = res.data
    } catch (err) {
      error.value = '获取大盘数据失败'
      // 使用默认值避免页面空白
      if (!overview.value) {
        overview.value = {
          sh_index: 0, sh_change_pct: 0,
          sz_index: 0, sz_change_pct: 0,
          cyb_index: 0, cyb_change_pct: 0,
          advance_count: 0, decline_count: 0,
          limit_up_count: 0, limit_down_count: 0,
          updated_at: '',
        }
      }
    } finally {
      loading.value = false
    }
  }

  return { overview, loading, error, fetchOverview }
})
