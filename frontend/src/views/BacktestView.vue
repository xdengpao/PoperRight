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
          <input id="bt-capital" v-model.number="form.initialCapital" type="number" class="input" />
        </div>
        <div class="config-item">
          <label for="bt-buy-fee">买入手续费率</label>
          <input id="bt-buy-fee" v-model.number="form.commissionBuy" type="number" step="0.0001" class="input" />
        </div>
        <div class="config-item">
          <label for="bt-sell-fee">卖出手续费率</label>
          <input id="bt-sell-fee" v-model.number="form.commissionSell" type="number" step="0.0001" class="input" />
        </div>
        <div class="config-item">
          <label for="bt-slippage">滑点比例</label>
          <input id="bt-slippage" v-model.number="form.slippage" type="number" step="0.0001" class="input" />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn" @click="runBacktest" :disabled="running">
          {{ running ? '回测中...' : '开始回测' }}
        </button>
        <button class="btn btn-outline" @click="runOptimize" :disabled="optimizing">
          {{ optimizing ? '优化中...' : '参数优化' }}
        </button>
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
    <section v-if="result" class="chart-section" aria-label="回测图表">
      <h2 class="section-title">收益曲线 & 最大回撤</h2>
      <div ref="equityChartRef" class="chart" role="img" aria-label="收益曲线图"></div>
    </section>

    <!-- 参数优化结果 -->
    <section v-if="optimizeResults.length" class="card" aria-label="参数优化结果">
      <h2 class="section-title">参数优化结果 (Top 10)</h2>
      <table class="data-table">
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
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { apiClient } from '@/api'
import * as echarts from 'echarts'

interface StrategyItem { id: string; name: string }
interface BacktestResult {
  annual_return: number; total_return: number; win_rate: number
  profit_loss_ratio: number; max_drawdown: number; sharpe_ratio: number
  calmar_ratio: number; total_trades: number; avg_holding_days: number
  equity_curve: [string, number][]; drawdown_curve?: [string, number][]
}
interface OptimizeResult {
  params: Record<string, number>; annual_return: number
  sharpe_ratio: number; max_drawdown: number; overfit: boolean
}

const strategies = ref<StrategyItem[]>([])
const running = ref(false)
const optimizing = ref(false)
const result = ref<BacktestResult | null>(null)
const optimizeResults = ref<OptimizeResult[]>([])
const equityChartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const form = reactive({
  strategyId: '',
  startDate: '2022-01-01',
  endDate: '2024-01-01',
  initialCapital: 1000000,
  commissionBuy: 0.0003,
  commissionSell: 0.0013,
  slippage: 0.001,
})

const metricsCards = computed(() => {
  const r = result.value
  if (!r) return []
  return [
    { label: '年化收益率', display: (r.annual_return * 100).toFixed(2) + '%', colorClass: r.annual_return >= 0 ? 'up' : 'down' },
    { label: '累计收益率', display: (r.total_return * 100).toFixed(2) + '%', colorClass: r.total_return >= 0 ? 'up' : 'down' },
    { label: '胜率', display: (r.win_rate * 100).toFixed(1) + '%', colorClass: '' },
    { label: '盈亏比', display: r.profit_loss_ratio.toFixed(2), colorClass: '' },
    { label: '最大回撤', display: (r.max_drawdown * 100).toFixed(2) + '%', colorClass: 'down' },
    { label: '夏普比率', display: r.sharpe_ratio.toFixed(2), colorClass: r.sharpe_ratio >= 1 ? 'up' : '' },
    { label: '卡玛比率', display: r.calmar_ratio.toFixed(2), colorClass: '' },
    { label: '总交易次数', display: String(r.total_trades), colorClass: '' },
    { label: '平均持仓天数', display: r.avg_holding_days.toFixed(1), colorClass: '' },
  ]
})

async function runBacktest() {
  running.value = true
  try {
    const res = await apiClient.post<BacktestResult>('/backtest/run', {
      strategy_id: form.strategyId || undefined,
      start_date: form.startDate,
      end_date: form.endDate,
      initial_capital: form.initialCapital,
      commission_buy: form.commissionBuy,
      commission_sell: form.commissionSell,
      slippage: form.slippage,
    })
    result.value = res.data
    await nextTick()
    renderEquityChart()
  } catch { /* handle error */ }
  running.value = false
}

async function runOptimize() {
  optimizing.value = true
  try {
    const res = await apiClient.post<OptimizeResult[]>('/backtest/optimize', {
      strategy_id: form.strategyId || undefined,
      start_date: form.startDate,
      end_date: form.endDate,
      initial_capital: form.initialCapital,
    })
    optimizeResults.value = res.data.slice(0, 10)
  } catch { /* handle error */ }
  optimizing.value = false
}

function renderEquityChart() {
  if (!chartInstance || !result.value) return
  const eq = result.value.equity_curve
  const dates = eq.map((e) => e[0])
  const values = eq.map((e) => e[1])
  const dd = result.value.drawdown_curve ?? []

  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['收益曲线', '回撤曲线'], textStyle: { color: '#8b949e' }, top: 0 },
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#8b949e' } },
    yAxis: [
      { type: 'value', name: '净值', splitLine: { lineStyle: { color: '#21262d' } }, axisLabel: { color: '#8b949e' } },
      { type: 'value', name: '回撤%', splitLine: { show: false }, axisLabel: { color: '#8b949e' } },
    ],
    series: [
      { name: '收益曲线', type: 'line', data: values, smooth: true, lineStyle: { color: '#58a6ff' }, itemStyle: { color: '#58a6ff' }, symbol: 'none' },
      { name: '回撤曲线', type: 'line', data: dd.map((d) => d[1]), yAxisIndex: 1, smooth: true, lineStyle: { color: '#f85149' }, areaStyle: { color: '#f8514922' }, itemStyle: { color: '#f85149' }, symbol: 'none' },
    ],
  })
}

async function loadStrategies() {
  try {
    const res = await apiClient.get<StrategyItem[]>('/strategies')
    strategies.value = res.data
  } catch { /* handle error */ }
}

onMounted(async () => {
  loadStrategies()
  await nextTick()
  if (equityChartRef.value) {
    chartInstance = echarts.init(equityChartRef.value)
  }
})

watch(equityChartRef, (el) => {
  if (el && !chartInstance) chartInstance = echarts.init(el)
})

onUnmounted(() => { chartInstance?.dispose() })
</script>

<style scoped>
.backtest-view { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.form-actions { display: flex; gap: 8px; margin-top: 16px; }

.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover { color: #e6edf3; border-color: #8b949e; }

.metrics-section { margin-bottom: 20px; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.metric-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 14px; display: flex; flex-direction: column; gap: 4px;
}
.metric-label { font-size: 12px; color: #8b949e; }
.metric-value { font-size: 20px; font-weight: 600; color: #e6edf3; }
.up { color: #f85149; }
.down { color: #3fb950; }

.chart-section { margin-bottom: 20px; }
.chart { width: 100%; height: 360px; background: #161b22; border-radius: 8px; border: 1px solid #30363d; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', monospace; font-size: 12px; }

.overfit-warn { color: #d29922; }
.overfit-ok { color: #3fb950; }
</style>
