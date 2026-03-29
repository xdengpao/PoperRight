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

  async function fetchOverview() {
    loading.value = true
    try {
      const res = await apiClient.get<MarketOverview>('/data/market/overview')
      overview.value = res.data
    } finally {
      loading.value = false
    }
  }

  return { overview, loading, fetchOverview }
})
