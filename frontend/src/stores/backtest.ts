/**
 * 回测状态 Pinia Store
 *
 * 将回测结果和轮询状态持久化到 store 中，
 * 切换页面不会丢失回测数据和进度。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

export interface TradeOrder {
  symbol: string
  direction: 'BUY' | 'SELL'
  quantity: number
  price: number
  amount: number
  commission: number
  status: string
  created_at: string
  sell_reason?: string
}

export interface BacktestResult {
  annual_return: number
  total_return: number
  win_rate: number
  profit_loss_ratio: number
  max_drawdown: number
  sharpe_ratio: number
  calmar_ratio: number
  total_trades: number
  avg_holding_days: number
  equity_curve: [string, number][]
  trade_records: TradeOrder[]
}

export interface OptimizeResult {
  params: Record<string, number>
  annual_return: number
  sharpe_ratio: number
  max_drawdown: number
  overfit: boolean
}

export interface ExitConditionForm {
  freq: 'daily' | 'minute'
  indicator: string
  operator: string
  threshold: number | null
  crossTarget: string | null
  params: Record<string, number>
}

export type RunStatus = 'idle' | 'pending' | 'running' | 'success' | 'failed'

export const useBacktestStore = defineStore('backtest', () => {
  const running = ref(false)
  const result = ref<BacktestResult | null>(null)
  const runStatus = ref<RunStatus>('idle')
  const runProgress = ref(0)
  const runError = ref('')
  const optimizeResults = ref<OptimizeResult[]>([])
  const activeTaskId = ref<string | null>(null)

  // 回测参数（跨页面保持）
  const form = ref({
    strategyId: '',
    startDate: '',
    endDate: '',
    initialCapital: 1_000_000,
    commissionBuy: 0.0003,
    commissionSell: 0.0013,
    slippage: 0.001,
    exitConditions: {
      conditions: [] as ExitConditionForm[],
      logic: 'AND' as 'AND' | 'OR',
    },
  })

  let pollAborted = false

  const tradeRecords = computed<TradeOrder[]>(() => result.value?.trade_records ?? [])

  function reset() {
    result.value = null
    runStatus.value = 'idle'
    runProgress.value = 0
    runError.value = ''
    activeTaskId.value = null
    pollAborted = false
  }

  async function startBacktest(params: {
    strategyId?: string
    startDate: string
    endDate: string
    initialCapital: number
    commissionBuy: number
    commissionSell: number
    slippage: number
  }) {
    if (running.value) return
    running.value = true
    runStatus.value = 'pending'
    runProgress.value = 5
    runError.value = ''
    result.value = null
    pollAborted = false

    try {
      // 从风控配置读取止损止盈参数
      let stopLossPct = 0.08
      let trailingStopPct = 0.05
      let trendStopMa = 20
      try {
        const riskRes = await apiClient.get<{
          fixed_stop_loss: number
          trailing_stop: number
          trend_stop_ma: number
        }>('/risk/stop-config')
        stopLossPct = riskRes.data.fixed_stop_loss / 100
        trailingStopPct = riskRes.data.trailing_stop / 100
        trendStopMa = riskRes.data.trend_stop_ma
      } catch {
        // 风控配置不可用时使用默认值
      }

      // 序列化自定义平仓条件（camelCase → snake_case）
      const exitConds = form.value.exitConditions
      const exitConditionsPayload =
        exitConds.conditions.length > 0
          ? {
              conditions: exitConds.conditions.map((c) => ({
                freq: c.freq,
                indicator: c.indicator,
                operator: c.operator,
                threshold: c.threshold,
                cross_target: c.crossTarget,
                params: c.params,
              })),
              logic: exitConds.logic,
            }
          : null

      const res = await apiClient.post<BacktestResult | { task_id: string }>('/backtest/run', {
        strategy_id: params.strategyId || undefined,
        start_date: params.startDate,
        end_date: params.endDate,
        initial_capital: params.initialCapital,
        commission_buy: params.commissionBuy,
        commission_sell: params.commissionSell,
        slippage: params.slippage,
        stop_loss_pct: stopLossPct,
        trailing_stop_pct: trailingStopPct,
        trend_stop_ma: trendStopMa,
        exit_conditions: exitConditionsPayload,
      })

      if ('equity_curve' in res.data) {
        result.value = res.data as BacktestResult
        runStatus.value = 'success'
        runProgress.value = 100
      } else {
        const data = res.data as Record<string, unknown>
        const taskId = (data.task_id ?? data.id) as string | undefined
        if (!taskId) {
          runStatus.value = 'failed'
          runError.value = '回测任务提交成功但未返回任务ID'
          return
        }
        activeTaskId.value = taskId
        runStatus.value = 'running'
        runProgress.value = 20
        await pollResult(taskId)
      }
    } catch (e: unknown) {
      runStatus.value = 'failed'
      runError.value = e instanceof Error ? e.message : '回测启动失败，请重试'
    } finally {
      running.value = false
    }
  }

  async function pollResult(taskId: string) {
    const maxAttempts = 600
    let attempts = 0

    while (attempts < maxAttempts && !pollAborted) {
      attempts++
      runProgress.value = Math.min(20 + Math.floor((attempts / maxAttempts) * 70), 90)

      try {
        const res = await apiClient.get<BacktestResult & { status?: string }>(`/backtest/${taskId}/result`)
        const data = res.data

        if (data.status === 'PENDING' || data.status === 'RUNNING') {
          await new Promise(resolve => setTimeout(resolve, 2000))
          continue
        }

        if (data.status === 'FAILED') {
          runStatus.value = 'failed'
          runError.value = '回测任务执行失败'
          return
        }

        result.value = data
        runStatus.value = 'success'
        runProgress.value = 100
        activeTaskId.value = null
        return
      } catch {
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
    }

    if (!pollAborted) {
      runStatus.value = 'failed'
      runError.value = '回测超时，请检查策略配置后重试'
    }
  }

  /** 恢复轮询（页面重新进入时调用） */
  async function resumePolling() {
    if (activeTaskId.value && runStatus.value === 'running' && !running.value) {
      running.value = true
      pollAborted = false
      await pollResult(activeTaskId.value)
      running.value = false
    }
  }

  function abortPolling() {
    pollAborted = true
  }

  return {
    running,
    result,
    runStatus,
    runProgress,
    runError,
    optimizeResults,
    activeTaskId,
    tradeRecords,
    form,
    reset,
    startBacktest,
    resumePolling,
    abortPolling,
  }
})
