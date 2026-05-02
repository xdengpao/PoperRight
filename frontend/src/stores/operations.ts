import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api'

export interface TradingPlanSummary {
  id: string
  name: string
  strategy_id: string
  status: 'ACTIVE' | 'PAUSED' | 'ARCHIVED'
  position_count: number
  max_positions: number
  candidate_count: number
  warning_count: number
  created_at: string
}

export interface CandidateStock {
  id: string
  symbol: string
  trend_score: number | null
  ref_buy_price: number | null
  signal_strength: string | null
  signal_freshness: string | null
  sector_rank: number | null
  risk_status: string
  signals_summary: Record<string, unknown>[] | null
  status: string
  screen_date: string
}

export interface PlanPosition {
  id: string
  symbol: string
  quantity: number
  cost_price: number
  current_price: number | null
  pnl_pct: number | null
  holding_days: number
  stop_stage: number
  stop_price: number
  latest_trend_score: number | null
  latest_sector_rank: number | null
  status: string
  sell_signals: Record<string, unknown>[] | null
  opened_at: string
  closed_at: string | null
}

export interface ChecklistItem {
  dimension: string
  symbol: string | null
  result: 'OK' | 'WARNING' | 'DANGER'
  value: number | string
  threshold: number | string
  message: string
  action: string
}

export interface BuyRecord {
  id: string
  symbol: string
  buy_price: number
  buy_quantity: number
  buy_time: string
  trend_score_at_buy: number | null
  sector_rank_at_buy: number | null
  initial_stop_price: number
  is_manual: boolean
  signals_at_buy: Record<string, unknown> | null
}

export interface StrategyTemplate {
  id: string
  name: string
  config: Record<string, unknown>
  is_active: boolean
  is_builtin: boolean
  enabled_modules: string[]
  created_at: string
}

export const useOperationsStore = defineStore('operations', () => {
  const plans = ref<TradingPlanSummary[]>([])
  const candidates = ref<CandidateStock[]>([])
  const positions = ref<PlanPosition[]>([])
  const checklist = ref<ChecklistItem[]>([])
  const checklistLevel = ref<string>('OK')
  const buyRecords = ref<BuyRecord[]>([])
  const strategies = ref<StrategyTemplate[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  function getErrorMessage(e: unknown, fallback: string) {
    if (e instanceof Error) return e.message
    const maybeAxiosError = e as { response?: { data?: { detail?: string } } }
    return maybeAxiosError.response?.data?.detail || fallback
  }

  async function fetchPlans() {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get('/operations/plans')
      plans.value = data.items || []
    } catch (e: unknown) {
      plans.value = []
      error.value = getErrorMessage(e, '加载交易计划失败')
    } finally {
      loading.value = false
    }
  }

  async function createPlan(payload: {
    name: string
    strategy_id: string
    candidate_filter?: Record<string, unknown>
    stage_stop_config?: Record<string, unknown>
    position_control?: Record<string, unknown>
    market_profile?: Record<string, unknown>
  }) {
    error.value = null
    try {
      const { data } = await apiClient.post('/operations/plans', payload)
      await fetchPlans()
      return data
    } catch (e: unknown) {
      error.value = getErrorMessage(e, '创建交易计划失败')
      throw e
    }
  }

  async function updatePlanStatus(planId: string, status: string) {
    await apiClient.patch(`/operations/plans/${planId}/status`, { status })
    await fetchPlans()
  }

  async function deletePlan(planId: string) {
    await apiClient.delete(`/operations/plans/${planId}`)
    await fetchPlans()
  }

  async function fetchCandidates(planId: string, date?: string) {
    loading.value = true
    try {
      const params = date ? { date } : {}
      const { data } = await apiClient.get(`/operations/plans/${planId}/candidates`, { params })
      candidates.value = data.items
    } finally {
      loading.value = false
    }
  }

  async function skipCandidate(planId: string, candidateId: string) {
    await apiClient.delete(`/operations/plans/${planId}/candidates/${candidateId}`)
    candidates.value = candidates.value.filter(c => c.id !== candidateId)
  }

  async function executeBuy(planId: string, payload: {
    candidate_id?: string
    symbol: string
    buy_price: number
    buy_quantity: number
    trend_score?: number
    sector_rank?: number
  }) {
    const { data } = await apiClient.post(`/operations/plans/${planId}/buy`, payload)
    return data
  }

  async function fetchPositions(planId: string, status?: string) {
    loading.value = true
    try {
      const params = status ? { status } : {}
      const { data } = await apiClient.get(`/operations/plans/${planId}/positions`, { params })
      positions.value = data.items
    } finally {
      loading.value = false
    }
  }

  async function confirmSell(planId: string, positionId: string, sellPrice: number, sellQuantity?: number) {
    const { data } = await apiClient.post(
      `/operations/plans/${planId}/positions/${positionId}/sell`,
      { sell_price: sellPrice, sell_quantity: sellQuantity }
    )
    return data
  }

  async function fetchChecklist(planId: string, date?: string) {
    const params = date ? { date } : {}
    const { data } = await apiClient.get(`/operations/plans/${planId}/checklist`, { params })
    checklist.value = data.items || []
    checklistLevel.value = data.summary_level || 'OK'
  }

  async function fetchBuyRecords(planId: string, page = 1) {
    const { data } = await apiClient.get(`/operations/plans/${planId}/buy-records`, {
      params: { page, page_size: 20 }
    })
    buyRecords.value = data.items
    return data
  }

  async function fetchStrategies() {
    try {
      const { data } = await apiClient.get('/strategies')
      console.log('[fetchStrategies] raw data type:', typeof data, Array.isArray(data))
      strategies.value = Array.isArray(data) ? data : (data.items || [])
      console.log('[fetchStrategies] strategies loaded:', strategies.value.map(s => s.name))
    } catch (e) {
      console.error('[fetchStrategies] error:', e)
      strategies.value = []
    }
  }

  async function runScreening(planId: string) {
    const { data } = await apiClient.post(`/operations/plans/${planId}/screen`)
    return data
  }

  return {
    plans, candidates, positions, checklist, checklistLevel, buyRecords, strategies, loading, error,
    fetchPlans, createPlan, updatePlanStatus, deletePlan,
    fetchCandidates, skipCandidate, executeBuy,
    fetchPositions, confirmSell,
    fetchChecklist, fetchBuyRecords, fetchStrategies, runScreening,
  }
})
