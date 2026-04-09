<template>
  <div class="backtest-view">
    <h1 class="page-title">策略回测</h1>

    <!-- 回测参数配置 -->
    <section class="card" aria-label="回测参数配置">
      <h2 class="section-title">回测参数</h2>
      <div class="config-grid">
        <div class="config-item">
          <label for="bt-strategy">选股策略</label>
          <select id="bt-strategy" v-model="form.strategyId" class="input">
            <option value="">-- 选择策略 --</option>
            <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="config-item">
          <label for="bt-start">起始日期</label>
          <input id="bt-start" v-model="form.startDate" type="date" class="input" />
        </div>
        <div class="config-item">
          <label for="bt-end">结束日期</label>
          <input id="bt-end" v-model="form.endDate" type="date" class="input" />
        </div>
        <div class="config-item">
          <label for="bt-capital">初始资金 (元)</label>
          <input id="bt-capital" v-model.number="form.initialCapital" type="number" min="10000" step="10000" class="input" />
        </div>
        <div class="config-item">
          <label for="bt-buy-fee">买入手续费率</label>
          <input id="bt-buy-fee" v-model.number="form.commissionBuy" type="number" step="0.0001" min="0" class="input" />
          <span class="hint">默认 0.03%</span>
        </div>
        <div class="config-item">
          <label for="bt-sell-fee">卖出手续费率</label>
          <input id="bt-sell-fee" v-model.number="form.commissionSell" type="number" step="0.0001" min="0" class="input" />
          <span class="hint">默认 0.13%（含印花税）</span>
        </div>
        <div class="config-item">
          <label for="bt-slippage">滑点比例</label>
          <input id="bt-slippage" v-model.number="form.slippage" type="number" step="0.0001" min="0" class="input" />
          <span class="hint">默认 0.1%</span>
        </div>
      </div>
      <!-- 自定义平仓条件面板 -->
      <div class="exit-conditions-panel">
        <button
          class="panel-toggle"
          @click="exitPanelOpen = !exitPanelOpen"
          :aria-expanded="exitPanelOpen"
          aria-controls="exit-conditions-content"
        >
          <span>自定义平仓条件</span>
          <span class="toggle-icon">{{ exitPanelOpen ? '▲' : '▼' }}</span>
        </button>
        <div v-if="exitPanelOpen" id="exit-conditions-content" class="panel-content">
          <div class="logic-selector">
            <label for="exit-logic">条件逻辑:</label>
            <select id="exit-logic" v-model="form.exitConditions.logic" class="input input-sm">
              <option value="AND">AND</option>
              <option value="OR">OR</option>
            </select>
          </div>

          <div v-if="form.exitConditions.conditions.length" class="conditions-list">
            <div
              v-for="(cond, idx) in form.exitConditions.conditions"
              :key="idx"
              class="condition-row"
            >
              <div class="condition-fields">
                <select v-model="cond.freq" class="input input-sm" :aria-label="'条件' + (idx + 1) + '数据源频率'">
                  <option v-for="f in freqOptions" :key="f.value" :value="f.value">{{ f.label }}</option>
                </select>
                <select v-model="cond.indicator" class="input input-sm" :aria-label="'条件' + (idx + 1) + '指标'" @change="onIndicatorChange(idx)">
                  <option v-for="ind in indicatorOptions" :key="ind.value" :value="ind.value">{{ ind.label }}</option>
                </select>
                <select v-model="cond.operator" class="input input-sm" :aria-label="'条件' + (idx + 1) + '运算符'" @change="onOperatorChange(idx)">
                  <option v-for="op in operatorOptions" :key="op.value" :value="op.value">{{ op.label }}</option>
                </select>
                <select
                  v-if="isCrossOperator(cond.operator)"
                  v-model="cond.crossTarget"
                  class="input input-sm"
                  :aria-label="'条件' + (idx + 1) + '交叉目标'"
                >
                  <option v-for="ind in indicatorOptions" :key="ind.value" :value="ind.value">{{ ind.label }}</option>
                </select>
                <input
                  v-else
                  v-model.number="cond.threshold"
                  type="number"
                  step="any"
                  class="input input-sm"
                  placeholder="阈值"
                  :aria-label="'条件' + (idx + 1) + '阈值'"
                />
                <button class="btn btn-icon btn-danger-ghost" @click="removeCondition(idx)" :aria-label="'删除条件' + (idx + 1)">✕</button>
              </div>
              <div v-if="cond.indicator === 'ma'" class="condition-params">
                <label :for="'ma-period-' + idx">周期:</label>
                <input
                  :id="'ma-period-' + idx"
                  v-model.number="cond.params.period"
                  type="number"
                  min="1"
                  step="1"
                  class="input input-sm input-narrow"
                  placeholder="20"
                />
              </div>
            </div>
          </div>

          <button class="btn btn-outline btn-sm" @click="addCondition" aria-label="添加平仓条件">+ 添加条件</button>
        </div>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" @click="runBacktest" :disabled="running" aria-label="开始回测">
          <span v-if="running" class="spinner" aria-hidden="true"></span>
          {{ running ? '回测中...' : '开始回测' }}
        </button>
        <button class="btn btn-outline" @click="runOptimize" :disabled="optimizing || running">
          {{ optimizing ? '优化中...' : '参数优化' }}
        </button>
      </div>

      <!-- 进度状态 -->
      <div v-if="running || runStatus" class="progress-bar-wrap" aria-live="polite">
        <div class="progress-label">
          <span>{{ runStatusText }}</span>
          <span v-if="runProgress > 0">{{ runProgress }}%</span>
        </div>
        <div class="progress-track">
          <div
            class="progress-fill"
            :class="runStatusClass"
            :style="{ width: runProgress + '%' }"
          ></div>
        </div>
        <p v-if="runError" class="run-error">{{ runError }}</p>
      </div>
    </section>

    <!-- 绩效指标卡片 -->
    <section v-if="result" class="metrics-section" aria-label="绩效指标">
      <h2 class="section-title">绩效指标</h2>
      <div class="metrics-grid">
        <div v-for="m in metricsCards" :key="m.label" class="metric-card">
          <span class="metric-label">{{ m.label }}</span>
          <span class="metric-value" :class="m.colorClass">{{ m.display }}</span>
        </div>
      </div>
    </section>

    <!-- 收益曲线 / 最大回撤图表 -->
    <section v-if="result" class="chart-section card" aria-label="回测图表">
      <h2 class="section-title">收益曲线 &amp; 最大回撤</h2>
      <div ref="equityChartRef" class="chart" role="img" aria-label="收益曲线与最大回撤图"></div>
    </section>

    <!-- 交易流水明细 -->
    <section v-if="result && tradeRecords.length" class="card" aria-label="交易流水明细">
      <div class="section-header">
        <h2 class="section-title">交易流水明细</h2>
        <div class="section-header-right">
          <span class="record-count">共 {{ tradeRecords.length }} 笔</span>
          <button class="btn btn-outline btn-sm" @click="exportTradeCSV" aria-label="导出全部交易流水">导出 CSV</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table" aria-label="交易流水明细表">
          <thead>
            <tr>
              <th scope="col">时间</th>
              <th scope="col">股票代码</th>
              <th scope="col">方向</th>
              <th scope="col">数量（股）</th>
              <th scope="col">价格（元）</th>
              <th scope="col">金额（元）</th>
              <th scope="col">手续费（元）</th>
              <th scope="col">平仓原因</th>
              <th scope="col">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in pagedTradeRecords" :key="i">
              <td>{{ t.created_at?.slice(0, 16) ?? '—' }}</td>
              <td class="mono">{{ t.symbol }}</td>
              <td>
                <span class="direction-badge" :class="t.direction === 'BUY' ? 'buy' : 'sell'">
                  {{ t.direction === 'BUY' ? '买入' : '卖出' }}
                </span>
              </td>
              <td>{{ t.quantity?.toLocaleString() ?? '—' }}</td>
              <td>{{ t.price?.toFixed(2) ?? '—' }}</td>
              <td>{{ t.amount != null ? t.amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '—' }}</td>
              <td>{{ t.commission?.toFixed(2) ?? '—' }}</td>
              <td>{{ t.direction === 'SELL' ? formatSellReason(t.sell_reason) : '—' }}</td>
              <td>
                <span class="status-badge" :class="t.status?.toLowerCase()">{{ t.status ?? '—' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 分页 -->
      <nav v-if="tradeTotalPages > 1" class="pagination" aria-label="交易流水分页">
        <button class="page-btn" :disabled="tradePage === 1" @click="tradePage = 1" aria-label="首页">«</button>
        <button class="page-btn" :disabled="tradePage === 1" @click="tradePage--" aria-label="上一页">‹</button>
        <template v-for="p in tradeVisiblePages" :key="p">
          <span v-if="p === -1" class="page-ellipsis">…</span>
          <button v-else class="page-btn" :class="{ active: p === tradePage }" @click="tradePage = p">{{ p }}</button>
        </template>
        <button class="page-btn" :disabled="tradePage === tradeTotalPages" @click="tradePage++" aria-label="下一页">›</button>
        <button class="page-btn" :disabled="tradePage === tradeTotalPages" @click="tradePage = tradeTotalPages" aria-label="末页">»</button>
        <select v-model.number="tradePageSize" class="page-size-select" aria-label="每页条数">
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
          <option :value="100">100 条/页</option>
        </select>
      </nav>
    </section>

    <!-- 参数优化结果 -->
    <section v-if="optimizeResults.length" class="card" aria-label="参数优化结果">
      <h2 class="section-title">参数优化结果 (Top 10)</h2>
      <table class="data-table" aria-label="参数优化结果表">
        <thead>
          <tr>
            <th scope="col">排名</th>
            <th scope="col">参数组合</th>
            <th scope="col">年化收益</th>
            <th scope="col">夏普比率</th>
            <th scope="col">最大回撤</th>
            <th scope="col">过拟合</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in optimizeResults" :key="i">
            <td>{{ i + 1 }}</td>
            <td class="mono">{{ JSON.stringify(r.params) }}</td>
            <td :class="r.annual_return >= 0 ? 'up' : 'down'">{{ (r.annual_return * 100).toFixed(2) }}%</td>
            <td>{{ r.sharpe_ratio.toFixed(2) }}</td>
            <td class="down">{{ (r.max_drawdown * 100).toFixed(2) }}%</td>
            <td>
              <span :class="r.overfit ? 'overfit-warn' : 'overfit-ok'">{{ r.overfit ? '⚠ 过拟合' : '✓ 正常' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { apiClient } from '@/api'
import * as echarts from 'echarts'
import { useBacktestStore } from '@/stores/backtest'
import type { TradeOrder, BacktestResult, OptimizeResult, RunStatus } from '@/stores/backtest'

// ─── Store ────────────────────────────────────────────────────────────────────

const store = useBacktestStore()

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface StrategyItem {
  id: string
  name: string
}

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const strategies = ref<StrategyItem[]>([])
const running = computed(() => store.running)
const optimizing = ref(false)
const result = computed(() => store.result)
const optimizeResults = computed(() => store.optimizeResults)
const equityChartRef = ref<HTMLElement | null>(null)
const runStatus = computed(() => store.runStatus)
const runProgress = computed(() => store.runProgress)
const runError = computed(() => store.runError)

let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// 初始化默认日期（仅在 store 中尚未设置时）
if (!store.form.startDate) {
  const today = new Date()
  const halfYearAgo = new Date(today)
  halfYearAgo.setMonth(halfYearAgo.getMonth() - 6)
  store.form.startDate = formatDate(halfYearAgo)
  store.form.endDate = formatDate(today)
}

const form = store.form

// ─── 自定义平仓条件 ───────────────────────────────────────────────────────────

const exitPanelOpen = ref(false)

const freqOptions = [
  { value: 'daily', label: 'daily' },
  { value: 'minute', label: 'minute' },
]

const indicatorOptions = [
  { value: 'ma', label: 'MA' },
  { value: 'macd_dif', label: 'MACD_DIF' },
  { value: 'macd_dea', label: 'MACD_DEA' },
  { value: 'macd_histogram', label: 'MACD_HIST' },
  { value: 'boll_upper', label: 'BOLL_UP' },
  { value: 'boll_middle', label: 'BOLL_MID' },
  { value: 'boll_lower', label: 'BOLL_LOW' },
  { value: 'rsi', label: 'RSI' },
  { value: 'dma', label: 'DMA' },
  { value: 'ama', label: 'AMA' },
  { value: 'close', label: 'CLOSE' },
  { value: 'volume', label: 'VOLUME' },
  { value: 'turnover', label: 'TURNOVER' },
]

const operatorOptions = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
  { value: 'cross_up', label: 'cross_up' },
  { value: 'cross_down', label: 'cross_down' },
]

function isCrossOperator(op: string): boolean {
  return op === 'cross_up' || op === 'cross_down'
}

function addCondition() {
  form.exitConditions.conditions.push({
    freq: 'daily',
    indicator: 'rsi',
    operator: '>',
    threshold: null,
    crossTarget: null,
    params: {},
  })
}

function removeCondition(index: number) {
  form.exitConditions.conditions.splice(index, 1)
}

function onOperatorChange(index: number) {
  const cond = form.exitConditions.conditions[index]
  if (isCrossOperator(cond.operator)) {
    cond.threshold = null
    if (!cond.crossTarget) cond.crossTarget = 'close'
  } else {
    cond.crossTarget = null
  }
}

function onIndicatorChange(index: number) {
  const cond = form.exitConditions.conditions[index]
  if (cond.indicator === 'ma') {
    if (!cond.params.period) cond.params.period = 20
  } else {
    delete cond.params.period
  }
}

// ─── 平仓原因格式化 ───────────────────────────────────────────────────────────

const SELL_REASON_MAP: Record<string, string> = {
  STOP_LOSS: '固定止损',
  TREND_BREAK: '趋势破位',
  TRAILING_STOP: '移动止盈',
  MAX_HOLDING_DAYS: '持仓超期',
}

function formatSellReason(reason?: string): string {
  if (!reason) return '—'
  if (SELL_REASON_MAP[reason]) return SELL_REASON_MAP[reason]
  if (reason.startsWith('EXIT_CONDITION')) {
    const desc = reason.replace(/^EXIT_CONDITION[:\s]*/, '').trim()
    return desc ? `自定义条件: ${desc}` : '自定义条件'
  }
  return reason
}

// ─── 计算属性 ─────────────────────────────────────────────────────────────────

const tradeRecords = computed<TradeOrder[]>(() => result.value?.trade_records ?? [])

// ─── 交易流水分页 ─────────────────────────────────────────────────────────────

const tradePage = ref(1)
const tradePageSize = ref(20)

const tradeTotalPages = computed(() => Math.max(1, Math.ceil(tradeRecords.value.length / tradePageSize.value)))

const pagedTradeRecords = computed(() => {
  const start = (tradePage.value - 1) * tradePageSize.value
  return tradeRecords.value.slice(start, start + tradePageSize.value)
})

const tradeVisiblePages = computed(() => {
  const total = tradeTotalPages.value
  const cur = tradePage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: number[] = [1]
  const left = Math.max(2, cur - 1)
  const right = Math.min(total - 1, cur + 1)
  if (left > 2) pages.push(-1)
  for (let i = left; i <= right; i++) pages.push(i)
  if (right < total - 1) pages.push(-1)
  pages.push(total)
  return pages
})

// 换页或换 pageSize 时重置页码
watch(tradePageSize, () => { tradePage.value = 1 })
watch(tradeRecords, () => { tradePage.value = 1 })

// ─── 导出 CSV ─────────────────────────────────────────────────────────────────

function exportTradeCSV() {
  const rows = tradeRecords.value
  if (!rows.length) return
  const header = '时间,股票代码,方向,数量(股),价格(元),金额(元),手续费(元),平仓原因,状态'
  const lines = rows.map(t =>
    [
      t.created_at?.slice(0, 16) ?? '',
      t.symbol,
      t.direction === 'BUY' ? '买入' : '卖出',
      t.quantity ?? '',
      t.price?.toFixed(2) ?? '',
      t.amount?.toFixed(2) ?? '',
      t.commission?.toFixed(2) ?? '',
      t.direction === 'SELL' ? formatSellReason(t.sell_reason) : '',
      t.status ?? '',
    ].join(',')
  )
  const bom = '\uFEFF'
  const blob = new Blob([bom + header + '\n' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const strategyName = strategies.value.find(s => s.id === form.strategyId)?.name ?? '未选策略'
  const now = new Date()
  const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`
  a.download = `${strategyName}_backtest_${ts}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const runStatusText = computed(() => {
  switch (runStatus.value) {
    case 'pending': return '等待回测任务启动...'
    case 'running': return '回测执行中，请稍候...'
    case 'success': return '回测完成'
    case 'failed': return '回测失败'
    default: return ''
  }
})

const runStatusClass = computed(() => {
  if (runStatus.value === 'success') return 'fill-success'
  if (runStatus.value === 'failed') return 'fill-error'
  return 'fill-active'
})

const metricsCards = computed(() => {
  const r = result.value
  if (!r) return []
  return [
    { label: '年化收益率', display: (r.annual_return * 100).toFixed(2) + '%', colorClass: r.annual_return >= 0 ? 'up' : 'down' },
    { label: '累计收益率', display: (r.total_return * 100).toFixed(2) + '%', colorClass: r.total_return >= 0 ? 'up' : 'down' },
    { label: '胜率', display: (r.win_rate * 100).toFixed(1) + '%', colorClass: r.win_rate >= 0.5 ? 'up' : '' },
    { label: '盈亏比', display: r.profit_loss_ratio.toFixed(2), colorClass: r.profit_loss_ratio >= 1.5 ? 'up' : '' },
    { label: '最大回撤', display: (r.max_drawdown * 100).toFixed(2) + '%', colorClass: 'down' },
    { label: '夏普比率', display: r.sharpe_ratio.toFixed(2), colorClass: r.sharpe_ratio >= 1 ? 'up' : '' },
    { label: '卡玛比率', display: r.calmar_ratio.toFixed(2), colorClass: r.calmar_ratio >= 1 ? 'up' : '' },
    { label: '总交易次数', display: String(r.total_trades), colorClass: '' },
    { label: '平均持仓天数', display: r.avg_holding_days.toFixed(1), colorClass: '' },
  ]
})

// ─── 回测执行（支持异步任务轮询）────────────────────────────────────────────

async function runBacktest() {
  if (store.running) return

  // 销毁旧图表实例，避免 v-if 移除 DOM 后实例悬空
  if (chartInstance) {
    resizeObserver?.disconnect()
    resizeObserver = null
    chartInstance.dispose()
    chartInstance = null
  }

  await store.startBacktest({
    strategyId: form.strategyId,
    startDate: form.startDate,
    endDate: form.endDate,
    initialCapital: form.initialCapital,
    commissionBuy: form.commissionBuy,
    commissionSell: form.commissionSell,
    slippage: form.slippage,
  })

  if (store.result?.equity_curve?.length) {
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))
    renderEquityChart()
  }
}

// ─── 参数优化 ─────────────────────────────────────────────────────────────────

async function runOptimize() {
  optimizing.value = true
  try {
    const res = await apiClient.post<OptimizeResult[]>('/backtest/optimize', {
      strategy_id: form.strategyId || undefined,
      start_date: form.startDate,
      end_date: form.endDate,
      initial_capital: form.initialCapital,
    })
    store.optimizeResults = res.data.slice(0, 10)
  } catch { /* handle error */ }
  optimizing.value = false
}

// ─── ECharts 图表渲染 ─────────────────────────────────────────────────────────

/** 从净值曲线计算最大回撤序列 */
function calcDrawdownSeries(equityCurve: [string, number][]): number[] {
  let peak = -Infinity
  return equityCurve.map(([, v]) => {
    if (v > peak) peak = v
    return peak > 0 ? ((v - peak) / peak) * 100 : 0
  })
}

function renderEquityChart() {
  // 确保图表实例已初始化（v-if 切换后 DOM 可能刚创建）
  if (!chartInstance && equityChartRef.value) {
    initChart(equityChartRef.value)
  }
  if (!chartInstance || !result.value) return
  const eq = result.value.equity_curve
  if (!eq || eq.length === 0) return

  const dates = eq.map((e) => e[0])
  const values = eq.map((e) => e[1])
  const drawdowns = calcDrawdownSeries(eq)

  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c2128',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
      formatter: (params: echarts.TooltipComponentFormatterCallbackParams) => {
        if (!Array.isArray(params)) return ''
        const date = params[0]?.axisValue ?? ''
        let html = `<div style="margin-bottom:4px;color:#8b949e">${date}</div>`
        for (const p of params) {
          const val = typeof p.value === 'number' ? p.value.toFixed(4) : p.value
          const unit = p.seriesName === '最大回撤' ? '%' : ''
          html += `<div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <b>${val}${unit}</b></div>`
        }
        return html
      },
    },
    legend: {
      data: ['净值曲线', '最大回撤'],
      textStyle: { color: '#8b949e' },
      top: 4,
      right: 10,
    },
    grid: { left: 60, right: 60, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#8b949e', fontSize: 11 },
      axisLine: { lineStyle: { color: '#30363d' } },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '净值',
        nameTextStyle: { color: '#8b949e' },
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: { color: '#8b949e', formatter: (v: number) => v.toFixed(2) },
      },
      {
        type: 'value',
        name: '回撤%',
        nameTextStyle: { color: '#8b949e' },
        splitLine: { show: false },
        axisLabel: { color: '#8b949e', formatter: (v: number) => v.toFixed(1) + '%' },
        max: 0,
      },
    ],
    series: [
      {
        name: '净值曲线',
        type: 'line',
        data: values,
        smooth: true,
        lineStyle: { color: '#58a6ff', width: 2 },
        itemStyle: { color: '#58a6ff' },
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(88,166,255,0.2)' },
            { offset: 1, color: 'rgba(88,166,255,0)' },
          ]),
        },
      },
      {
        name: '最大回撤',
        type: 'line',
        data: drawdowns,
        yAxisIndex: 1,
        smooth: true,
        lineStyle: { color: '#f85149', width: 1.5 },
        areaStyle: { color: 'rgba(248,81,73,0.15)' },
        itemStyle: { color: '#f85149' },
        symbol: 'none',
      },
    ],
  })
}

// ─── 策略列表 ─────────────────────────────────────────────────────────────────

async function loadStrategies() {
  try {
    const res = await apiClient.get<StrategyItem[]>('/strategies')
    strategies.value = Array.isArray(res.data) ? res.data : []
  } catch { /* API 暂不可用 */ }
}

// ─── 生命周期 ─────────────────────────────────────────────────────────────────

function initChart(el: HTMLElement) {
  chartInstance = echarts.init(el, 'dark')
  resizeObserver = new ResizeObserver(() => chartInstance?.resize())
  resizeObserver.observe(el)
}

onMounted(async () => {
  loadStrategies()
  await nextTick()
  if (equityChartRef.value) initChart(equityChartRef.value)

  // 恢复：如果有正在运行的回测任务，继续轮询
  await store.resumePolling()

  // 恢复：如果已有结果，渲染图表
  if (store.result?.equity_curve?.length) {
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    renderEquityChart()
  }
})

watch(equityChartRef, (el) => {
  if (el && !chartInstance) initChart(el)
  if (el && result.value && result.value.equity_curve?.length) {
    if (!chartInstance) initChart(el)
    renderEquityChart()
  }
})

// 当 result 变化时也尝试渲染图表（确保 v-if 切换后图表能渲染）
watch(result, async (newResult) => {
  if (newResult && newResult.equity_curve?.length) {
    await nextTick()
    // 等待 DOM 完全渲染
    await new Promise(resolve => setTimeout(resolve, 100))
    renderEquityChart()
  }
})

onUnmounted(() => {
  // 不中断轮询 — store 会在后台继续
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.backtest-view { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-header .section-title { margin-bottom: 0; }
.record-count { font-size: 13px; color: #8b949e; }

/* ─── 卡片 ─────────────────────────────────────────────────────────────────── */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }

/* ─── 参数表单 ──────────────────────────────────────────────────────────────── */
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.hint { font-size: 11px; color: #484f58; }
.form-actions { display: flex; gap: 8px; margin-top: 16px; align-items: center; }

/* ─── 输入控件 ──────────────────────────────────────────────────────────────── */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 6px 12px; border-radius: 6px; font-size: 14px;
}
.input:focus { outline: none; border-color: #58a6ff; }

/* ─── 按钮 ─────────────────────────────────────────────────────────────────── */
.btn { padding: 7px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; border: none; display: inline-flex; align-items: center; gap: 6px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #238636; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2ea043; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }

/* ─── 进度条 ────────────────────────────────────────────────────────────────── */
.progress-bar-wrap { margin-top: 16px; }
.progress-label { display: flex; justify-content: space-between; font-size: 13px; color: #8b949e; margin-bottom: 6px; }
.progress-track { height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
.fill-active { background: linear-gradient(90deg, #58a6ff, #79c0ff); animation: pulse 1.5s ease-in-out infinite; }
.fill-success { background: #3fb950; }
.fill-error { background: #f85149; }
.run-error { margin-top: 8px; font-size: 13px; color: #f85149; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* ─── 旋转加载图标 ──────────────────────────────────────────────────────────── */
.spinner {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 绩效指标 ──────────────────────────────────────────────────────────────── */
.metrics-section { margin-bottom: 20px; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.metric-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.metric-label { font-size: 12px; color: #8b949e; }
.metric-value { font-size: 22px; font-weight: 600; color: #e6edf3; }
/* A 股配色：涨红跌绿 */
.up { color: #f85149; }
.down { color: #3fb950; }

/* ─── 图表 ─────────────────────────────────────────────────────────────────── */
.chart-section { padding-bottom: 16px; }
.chart { width: 100%; height: 380px; }

/* ─── 交易流水表格 ──────────────────────────────────────────────────────────── */
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; min-width: 800px; }
.data-table th,
.data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 13px; white-space: nowrap; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; }

.direction-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
}
.direction-badge.buy { background: rgba(248,81,73,0.15); color: #f85149; }
.direction-badge.sell { background: rgba(63,185,80,0.15); color: #3fb950; }

.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px;
  background: #21262d; color: #8b949e;
}
.status-badge.filled { background: rgba(63,185,80,0.15); color: #3fb950; }
.status-badge.cancelled { background: rgba(248,81,73,0.1); color: #f85149; }
.status-badge.pending { background: rgba(210,153,34,0.15); color: #d29922; }

/* ─── 参数优化 ──────────────────────────────────────────────────────────────── */
.overfit-warn { color: #d29922; }
.overfit-ok { color: #3fb950; }

/* ─── 分页 ─────────────────────────────────────────────────────────────────── */
.section-header-right { display: flex; align-items: center; gap: 10px; }
.btn-sm { padding: 4px 12px; font-size: 12px; }
.pagination { display: flex; align-items: center; gap: 4px; margin-top: 14px; flex-wrap: wrap; }
.page-btn {
  background: #0d1117; border: 1px solid #30363d; color: #8b949e;
  padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; min-width: 32px; text-align: center;
}
.page-btn:hover:not(:disabled):not(.active) { color: #e6edf3; border-color: #58a6ff; }
.page-btn.active { background: #58a6ff; color: #fff; border-color: #58a6ff; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-ellipsis { color: #484f58; padding: 0 4px; font-size: 13px; }
.page-size-select {
  background: #0d1117; border: 1px solid #30363d; color: #8b949e;
  padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-left: 8px; cursor: pointer;
}
.page-size-select:focus { outline: none; border-color: #58a6ff; }

/* ─── 自定义平仓条件面板 ────────────────────────────────────────────────────── */
.exit-conditions-panel { margin-top: 16px; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }
.panel-toggle {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; background: #0d1117; border: none; color: #e6edf3;
  font-size: 14px; cursor: pointer;
}
.panel-toggle:hover { background: #161b22; }
.toggle-icon { font-size: 12px; color: #8b949e; }
.panel-content { padding: 14px; background: #0d1117; border-top: 1px solid #30363d; }
.logic-selector { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 13px; color: #8b949e; }
.conditions-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.condition-row { display: flex; flex-direction: column; gap: 6px; }
.condition-fields { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.condition-params { display: flex; align-items: center; gap: 6px; margin-left: 4px; font-size: 13px; color: #8b949e; }
.input-sm { padding: 4px 8px; font-size: 13px; }
.input-narrow { width: 70px; }
.btn-icon { padding: 4px 8px; font-size: 13px; line-height: 1; border-radius: 4px; }
.btn-danger-ghost { background: transparent; border: 1px solid #30363d; color: #f85149; cursor: pointer; }
.btn-danger-ghost:hover { background: rgba(248,81,73,0.1); border-color: #f85149; }
</style>
