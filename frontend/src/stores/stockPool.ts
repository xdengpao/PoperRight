/**
 * 选股池 Pinia Store
 *
 * 管理选股池 CRUD 及池内股票增删的前端状态。
 * 对应需求 2-6：选股池页面展示、创建管理、股票添加/移除、数据持久化。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '@/api'

// ---------------------------------------------------------------------------
// 接口定义
// ---------------------------------------------------------------------------

export interface StockPool {
  id: string
  name: string
  stock_count: number
  created_at: string
  updated_at: string
}

export interface StockPoolItem {
  symbol: string
  stock_name: string | null
  added_at: string
}

export type SignalCategory =
  | 'MA_TREND' | 'MACD' | 'BOLL' | 'RSI' | 'DMA'
  | 'BREAKOUT' | 'CAPITAL_INFLOW' | 'LARGE_ORDER'
  | 'MA_SUPPORT' | 'SECTOR_STRONG'

export interface SignalDetail {
  category: SignalCategory
  label: string
  is_fake_breakout: boolean
  strength?: 'STRONG' | 'MEDIUM' | 'WEAK'
  freshness?: 'NEW' | 'CONTINUING'
  description?: string
  dimension?: string
}

export interface SectorClassifications {
  eastmoney: string[]
  tonghuashun: string[]
  tongdaxin: string[]
}

/** 富化后的选股池股票（需求 7） */
export interface EnrichedPoolStock extends StockPoolItem {
  ref_buy_price: number | null
  trend_score: number | null
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | null
  signals: SignalDetail[] | null
  screen_time: string | null
  has_fake_breakout: boolean
  sector_classifications: SectorClassifications | null
}

// ---------------------------------------------------------------------------
// 前端校验函数（与后端校验逻辑一致）
// ---------------------------------------------------------------------------

export interface ValidationResult {
  valid: boolean
  error?: string
}

/**
 * 校验选股池名称。
 * - strip 后不能为空
 * - 长度不能超过 50 个字符
 */
export function validatePoolName(name: string): ValidationResult {
  const trimmed = name.trim()
  if (trimmed.length === 0) {
    return { valid: false, error: '选股池名称不能为空' }
  }
  if (trimmed.length > 50) {
    return { valid: false, error: '选股池名称长度不能超过50个字符' }
  }
  return { valid: true }
}

/**
 * 校验 A 股股票代码格式（支持 600000 或 600000.SH 格式）。
 */
export function validateStockSymbol(symbol: string): ValidationResult {
  if (!/^\d{6}(\.(SH|SZ|BJ))?$/.test(symbol)) {
    return { valid: false, error: '请输入有效的A股代码（如 600000 或 600000.SH）' }
  }
  return { valid: true }
}

// ---------------------------------------------------------------------------
// Pinia Store
// ---------------------------------------------------------------------------

export const useStockPoolStore = defineStore('stockPool', () => {
  /** 用户所有选股池列表 */
  const pools = ref<StockPool[]>([])
  /** 当前选中选股池的股票列表 */
  const currentPoolStocks = ref<StockPoolItem[]>([])
  /** 加载状态 */
  const loading = ref(false)
  /** 股票列表加载状态 */
  const stocksLoading = ref(false)
  /** 富化后的选股池股票列表（需求 7） */
  const enrichedPoolStocks = ref<EnrichedPoolStock[]>([])
  /** 富化数据加载状态 */
  const enrichedLoading = ref(false)

  // ─── 选股池 CRUD ──────────────────────────────────────────────────────────

  /** 获取用户所有选股池 */
  async function fetchPools() {
    loading.value = true
    try {
      const res = await apiClient.get<StockPool[]>('/pools')
      pools.value = res.data
    } finally {
      loading.value = false
    }
  }

  /** 创建选股池 */
  async function createPool(name: string) {
    const res = await apiClient.post<StockPool>('/pools', { name })
    // 创建成功后刷新列表以获取完整数据（含 stock_count）
    await fetchPools()
    return res.data
  }

  /** 删除选股池 */
  async function deletePool(poolId: string) {
    await apiClient.delete(`/pools/${poolId}`)
    // 从本地列表中移除
    pools.value = pools.value.filter((p) => p.id !== poolId)
  }

  /** 重命名选股池 */
  async function renamePool(poolId: string, name: string) {
    const res = await apiClient.put<{ id: string; name: string; updated_at: string }>(
      `/pools/${poolId}`,
      { name },
    )
    // 更新本地列表中对应的选股池
    const idx = pools.value.findIndex((p) => p.id === poolId)
    if (idx !== -1) {
      pools.value[idx] = {
        ...pools.value[idx],
        name: res.data.name,
        updated_at: res.data.updated_at,
      }
    }
    return res.data
  }

  // ─── 池内股票管理 ─────────────────────────────────────────────────────────

  /** 获取选股池内股票列表 */
  async function fetchPoolStocks(poolId: string) {
    stocksLoading.value = true
    try {
      const res = await apiClient.get<StockPoolItem[]>(`/pools/${poolId}/stocks`)
      currentPoolStocks.value = res.data
    } finally {
      stocksLoading.value = false
    }
  }

  /** 获取选股池内富化股票列表（含选股结果数据） */
  async function fetchEnrichedPoolStocks(poolId: string) {
    enrichedLoading.value = true
    try {
      const res = await apiClient.get<EnrichedPoolStock[]>(`/pools/${poolId}/stocks`, {
        params: { enriched: true },
      })
      enrichedPoolStocks.value = res.data
    } finally {
      enrichedLoading.value = false
    }
  }

  /** 批量添加股票到选股池 */
  async function addStocksToPool(poolId: string, symbols: string[]) {
    const res = await apiClient.post<{ added: number; skipped: number }>(
      `/pools/${poolId}/stocks`,
      { symbols },
    )
    return res.data
  }

  /** 批量移除选股池内的股票 */
  async function removeStocksFromPool(poolId: string, symbols: string[]) {
    const res = await apiClient.delete<{ removed: number }>(`/pools/${poolId}/stocks`, {
      data: { symbols },
    })
    return res.data
  }

  /** 手动添加单只股票到选股池 */
  async function addStockManual(poolId: string, symbol: string) {
    const res = await apiClient.post<{ symbol: string; added_at: string }>(
      `/pools/${poolId}/stocks/manual`,
      { symbol },
    )
    return res.data
  }

  return {
    // 状态
    pools,
    currentPoolStocks,
    loading,
    stocksLoading,
    enrichedPoolStocks,
    enrichedLoading,
    // 选股池 CRUD
    fetchPools,
    createPool,
    deletePool,
    renamePool,
    // 池内股票管理
    fetchPoolStocks,
    fetchEnrichedPoolStocks,
    addStocksToPool,
    removeStocksFromPool,
    addStockManual,
  }
})
