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
  freq: 'daily' | '1min' | '5min' | '15min' | '30min' | '60min'
  indicator: string
  operator: string
  threshold: number | null
  crossTarget: string | null
  params: Record<string, number>
}

export const FREQ_OPTIONS = [
  { value: 'daily', label: '日K' },
  { value: '1min', label: '1分钟' },
  { value: '5min', label: '5分钟' },
  { value: '15min', label: '15分钟' },
  { value: '30min', label: '30分钟' },
  { value: '60min', label: '60分钟' },
] as const

export interface ExitTemplate {
  id: string
  name: string
  description: string | null
  exit_conditions: {
    conditions: Array<{
      freq: string
      indicator: string
      operator: string
      threshold: number | null
      cross_target: string | null
      params: Record<string, number>
    }>
    logic: 'AND' | 'OR'
  }
  is_system: boolean
  created_at: string
  updated_at: string
}

// ─── 指标使用说明注册表 ──────────────────────────────────────────────────────

export interface IndicatorParamDescription {
  name: string
  label: string
  defaultValue: number
  suggestedRange: [number, number]
}

export interface IndicatorDescription {
  key: string
  chineseName: string
  calculationSummary: string
  params: IndicatorParamDescription[]
  typicalUsage: string
}

export const INDICATOR_DESCRIPTIONS: Record<string, IndicatorDescription> = {
  ma: {
    key: 'ma',
    chineseName: '移动平均线 (MA)',
    calculationSummary: '计算过去N个交易日收盘价的算术平均值',
    params: [
      { name: 'period', label: '均线周期', defaultValue: 20, suggestedRange: [5, 250] },
    ],
    typicalUsage: 'MA5 < MA10 表示短期均线跌破中期均线，可作为趋势转弱的卖出信号',
  },
  macd_dif: {
    key: 'macd_dif',
    chineseName: 'MACD快线 (DIF)',
    calculationSummary: '短期EMA与长期EMA的差值',
    params: [
      { name: 'macd_fast', label: '快线周期', defaultValue: 12, suggestedRange: [5, 20] },
      { name: 'macd_slow', label: '慢线周期', defaultValue: 26, suggestedRange: [20, 40] },
      { name: 'macd_signal', label: '信号线周期', defaultValue: 9, suggestedRange: [5, 15] },
    ],
    typicalUsage: 'DIF cross_down DEA 形成死叉，可作为趋势反转的卖出信号',
  },
  macd_dea: {
    key: 'macd_dea',
    chineseName: 'MACD慢线 (DEA)',
    calculationSummary: 'DIF的N日指数移动平均',
    params: [
      { name: 'macd_fast', label: '快线周期', defaultValue: 12, suggestedRange: [5, 20] },
      { name: 'macd_slow', label: '慢线周期', defaultValue: 26, suggestedRange: [20, 40] },
      { name: 'macd_signal', label: '信号线周期', defaultValue: 9, suggestedRange: [5, 15] },
    ],
    typicalUsage: 'DEA < 0 表示中期趋势偏空',
  },
  macd_histogram: {
    key: 'macd_histogram',
    chineseName: 'MACD柱状图',
    calculationSummary: '(DIF - DEA) × 2',
    params: [
      { name: 'macd_fast', label: '快线周期', defaultValue: 12, suggestedRange: [5, 20] },
      { name: 'macd_slow', label: '慢线周期', defaultValue: 26, suggestedRange: [20, 40] },
      { name: 'macd_signal', label: '信号线周期', defaultValue: 9, suggestedRange: [5, 15] },
    ],
    typicalUsage: 'MACD柱状图由正转负，表示多头动能减弱',
  },
  boll_upper: {
    key: 'boll_upper',
    chineseName: '布林带上轨',
    calculationSummary: '中轨 + N倍标准差',
    params: [
      { name: 'boll_period', label: '布林带周期', defaultValue: 20, suggestedRange: [10, 50] },
      { name: 'boll_std_dev', label: '标准差倍数', defaultValue: 2.0, suggestedRange: [1.0, 3.0] },
    ],
    typicalUsage: '收盘价 cross_down 布林带上轨，表示价格冲高回落',
  },
  boll_middle: {
    key: 'boll_middle',
    chineseName: '布林带中轨',
    calculationSummary: 'N日移动平均线',
    params: [
      { name: 'boll_period', label: '布林带周期', defaultValue: 20, suggestedRange: [10, 50] },
      { name: 'boll_std_dev', label: '标准差倍数', defaultValue: 2.0, suggestedRange: [1.0, 3.0] },
    ],
    typicalUsage: '收盘价跌破布林带中轨，表示中期趋势转弱',
  },
  boll_lower: {
    key: 'boll_lower',
    chineseName: '布林带下轨',
    calculationSummary: '中轨 - N倍标准差',
    params: [
      { name: 'boll_period', label: '布林带周期', defaultValue: 20, suggestedRange: [10, 50] },
      { name: 'boll_std_dev', label: '标准差倍数', defaultValue: 2.0, suggestedRange: [1.0, 3.0] },
    ],
    typicalUsage: '收盘价接近布林带下轨，可能出现超卖反弹',
  },
  rsi: {
    key: 'rsi',
    chineseName: '相对强弱指标 (RSI)',
    calculationSummary: '衡量价格变动速度和幅度的动量指标，范围0-100',
    params: [
      { name: 'rsi_period', label: 'RSI周期', defaultValue: 14, suggestedRange: [6, 24] },
    ],
    typicalUsage: 'RSI > 80 表示超买，可作为卖出信号',
  },
  dma: {
    key: 'dma',
    chineseName: '平均线差 (DMA)',
    calculationSummary: '短期均线与长期均线的差值',
    params: [
      { name: 'dma_short', label: '短期均线周期', defaultValue: 10, suggestedRange: [5, 20] },
      { name: 'dma_long', label: '长期均线周期', defaultValue: 50, suggestedRange: [30, 120] },
    ],
    typicalUsage: 'DMA < 0 表示短期均线低于长期均线，趋势偏空',
  },
  ama: {
    key: 'ama',
    chineseName: '平均线差均线 (AMA)',
    calculationSummary: 'DMA的移动平均线',
    params: [
      { name: 'dma_short', label: '短期均线周期', defaultValue: 10, suggestedRange: [5, 20] },
      { name: 'dma_long', label: '长期均线周期', defaultValue: 50, suggestedRange: [30, 120] },
    ],
    typicalUsage: 'DMA cross_down AMA 表示均线差趋势转弱',
  },
  close: {
    key: 'close',
    chineseName: '收盘价',
    calculationSummary: '当日收盘价（前复权）',
    params: [],
    typicalUsage: '收盘价跌破特定价位可作为止损信号',
  },
  volume: {
    key: 'volume',
    chineseName: '成交量',
    calculationSummary: '当日成交量（手）',
    params: [],
    typicalUsage: '成交量大幅萎缩可能预示趋势即将反转',
  },
  turnover: {
    key: 'turnover',
    chineseName: '换手率',
    calculationSummary: '当日换手率（%）',
    params: [],
    typicalUsage: '换手率异常放大可能预示主力出货',
  },
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

  // 模版状态
  const exitTemplates = ref<ExitTemplate[]>([])
  const selectedTemplateId = ref<string | null>(null)
  const templateLoading = ref(false)

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

  // ─── 模版 CRUD 方法 ──────────────────────────────────────────────────────────

  async function fetchExitTemplates() {
    templateLoading.value = true
    try {
      const res = await apiClient.get<ExitTemplate[]>('/backtest/exit-templates')
      exitTemplates.value = res.data
    } finally {
      templateLoading.value = false
    }
  }

  async function createExitTemplate(name: string, description?: string) {
    const exitConds = form.value.exitConditions
    const payload = {
      name,
      description: description ?? null,
      exit_conditions: {
        conditions: exitConds.conditions.map((c) => ({
          freq: c.freq,
          indicator: c.indicator,
          operator: c.operator,
          threshold: c.threshold,
          cross_target: c.crossTarget,
          params: c.params,
        })),
        logic: exitConds.logic,
      },
    }
    const res = await apiClient.post<ExitTemplate>('/backtest/exit-templates', payload)
    await fetchExitTemplates()
    return res.data
  }

  async function loadExitTemplate(templateId: string) {
    templateLoading.value = true
    try {
      const res = await apiClient.get<ExitTemplate>(`/backtest/exit-templates/${templateId}`)
      const tpl = res.data
      selectedTemplateId.value = templateId
      // snake_case → camelCase 转换
      form.value.exitConditions = {
        conditions: (tpl.exit_conditions.conditions ?? []).map((c) => ({
          freq: c.freq as ExitConditionForm['freq'],
          indicator: c.indicator,
          operator: c.operator,
          threshold: c.threshold ?? null,
          crossTarget: c.cross_target ?? null,
          params: c.params ?? {},
        })),
        logic: (tpl.exit_conditions.logic ?? 'AND') as 'AND' | 'OR',
      }
    } finally {
      templateLoading.value = false
    }
  }

  async function updateExitTemplate(templateId: string, data: Partial<{ name: string; description: string | null; exit_conditions: ExitTemplate['exit_conditions'] }>) {
    const res = await apiClient.put<ExitTemplate>(`/backtest/exit-templates/${templateId}`, data)
    await fetchExitTemplates()
    return res.data
  }

  async function deleteExitTemplate(templateId: string) {
    await apiClient.delete(`/backtest/exit-templates/${templateId}`)
    if (selectedTemplateId.value === templateId) {
      selectedTemplateId.value = null
    }
    await fetchExitTemplates()
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
    exitTemplates,
    selectedTemplateId,
    templateLoading,
    reset,
    startBacktest,
    resumePolling,
    abortPolling,
    fetchExitTemplates,
    createExitTemplate,
    loadExitTemplate,
    updateExitTemplate,
    deleteExitTemplate,
  }
})

// ─── 频率标签辅助函数 ──────────────────────────────────────────────────────

const FREQ_LABEL_MAP: Record<string, string> = {
  '1min': '1分钟',
  '5min': '5分钟',
  '15min': '15分钟',
  '30min': '30分钟',
  '60min': '60分钟',
}

/** 从模版条件中提取主要频率标签 */
export function getTemplateFreqLabel(template: ExitTemplate): string | null {
  const conditions = template.exit_conditions?.conditions ?? []
  if (!conditions.length) return null

  const minuteFreqs = new Set(
    conditions
      .map(c => c.freq)
      .filter(f => f !== 'daily')
  )

  if (minuteFreqs.size === 1) {
    const freq = [...minuteFreqs][0]
    return FREQ_LABEL_MAP[freq] ?? null
  }
  if (minuteFreqs.size > 1) {
    return '多频率'
  }
  return null
}
