import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api'

export interface ScreenItem {
  symbol: string
  name: string
  ref_buy_price: number
  trend_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  signals: Record<string, unknown>
}

export interface StrategyTemplate {
  id: string
  name: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

export const useScreenerStore = defineStore('screener', () => {
  const results = ref<ScreenItem[]>([])
  const strategies = ref<StrategyTemplate[]>([])
  const loading = ref(false)
  const lastUpdated = ref<Date | null>(null)

  async function fetchResults() {
    loading.value = true
    try {
      const res = await apiClient.get<ScreenItem[]>('/screen/results')
      results.value = res.data
      lastUpdated.value = new Date()
    } finally {
      loading.value = false
    }
  }

  async function fetchStrategies() {
    const res = await apiClient.get<StrategyTemplate[]>('/strategies')
    strategies.value = res.data
  }

  async function activateStrategy(id: string) {
    await apiClient.post(`/strategies/${id}/activate`)
    await fetchStrategies()
  }

  return { results, strategies, loading, lastUpdated, fetchResults, fetchStrategies, activateStrategy }
})
