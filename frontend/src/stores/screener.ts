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

export type ThresholdType = 'absolute' | 'percentile' | 'industry_relative' | 'z_score' | 'boolean' | 'range'

export interface FactorMeta {
  factor_name: string
  label: string
  category: string
  threshold_type: ThresholdType
  default_threshold: number | null
  value_min: number | null
  value_max: number | null
  unit: string
  description: string
  examples: Record<string, unknown>[]
  default_range: [number, number] | null
}

export interface SectorScreenConfig {
  sector_data_source: string
  sector_type: string
  sector_period: number
  sector_top_n: number
}

export interface StrategyExample {
  name: string
  description: string
  factors: Array<{
    factor_name: string
    operator: string
    threshold: number | null
    params: Record<string, unknown>
  }>
  logic: string
  weights: Record<string, number>
  enabled_modules: string[]
  sector_config: SectorScreenConfig | null
}

export const useScreenerStore = defineStore('screener', () => {
  const results = ref<ScreenItem[]>([])
  const strategies = ref<StrategyTemplate[]>([])
  const loading = ref(false)
  const lastUpdated = ref<Date | null>(null)
  const factorRegistry = ref<Record<string, FactorMeta[]>>({})
  const strategyExamples = ref<StrategyExample[]>([])

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

  async function fetchFactorRegistry(category?: string) {
    const params = category ? { category } : {}
    const res = await apiClient.get<Record<string, FactorMeta[]>>('/screen/factor-registry', { params })
    factorRegistry.value = res.data
  }

  async function fetchStrategyExamples() {
    const res = await apiClient.get<StrategyExample[]>('/screen/strategy-examples')
    strategyExamples.value = res.data
  }

  return {
    results,
    strategies,
    loading,
    lastUpdated,
    factorRegistry,
    strategyExamples,
    fetchResults,
    fetchStrategies,
    activateStrategy,
    fetchFactorRegistry,
    fetchStrategyExamples,
  }
})
