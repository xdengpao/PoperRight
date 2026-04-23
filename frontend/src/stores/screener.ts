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
  sector_period: number
  sector_top_n: number
}

export interface CoverageSourceStats {
  data_source: string
  total_sectors: number
  sectors_with_constituents: number
  total_stocks: number
  coverage_ratio: number
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
  config_doc: string
}

export const useScreenerStore = defineStore('screener', () => {
  const results = ref<ScreenItem[]>([])
  const strategies = ref<StrategyTemplate[]>([])
  const loading = ref(false)
  const lastUpdated = ref<Date | null>(null)
  const factorRegistry = ref<Record<string, FactorMeta[]>>({})
  const strategyExamples = ref<StrategyExample[]>([])
  const sectorCoverage = ref<CoverageSourceStats[]>([])

  /** 选股执行中标志，持久化在 store 中以跨组件生命周期保持状态 */
  const running = ref(false)
  /** 选股执行错误信息 */
  const runError = ref('')

  /**
   * 执行一键选股
   * @param params - 策略 ID 或自定义策略配置
   * @returns 执行结果 { success: boolean }
   */
  async function runScreen(params: { strategyId?: string; strategyConfig?: object }) {
    running.value = true
    runError.value = ''
    try {
      await apiClient.post('/screen/run', {
        strategy_id: params.strategyId,
        strategy_config: params.strategyConfig,
        screen_type: 'EOD',
      }, { timeout: 120_000 })
      return { success: true }
    } catch (error: unknown) {
      runError.value = error instanceof Error ? error.message : String(error)
      return { success: false }
    } finally {
      running.value = false
    }
  }

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

  async function fetchSectorCoverage() {
    const res = await apiClient.get<{ sources: CoverageSourceStats[] }>(
      '/sector/coverage'
    )
    sectorCoverage.value = res.data.sources
  }

  return {
    results,
    strategies,
    loading,
    lastUpdated,
    factorRegistry,
    strategyExamples,
    running,
    runError,
    fetchResults,
    fetchStrategies,
    activateStrategy,
    fetchFactorRegistry,
    fetchStrategyExamples,
    sectorCoverage,
    fetchSectorCoverage,
    runScreen,
  }
})
