<template>
  <div class="review-view">
    <h1 class="page-title">复盘分析</h1>

    <!-- 工具栏：周期切换标签 + 日期 + 查询 + 导出 -->
    <div class="toolbar card">
      <!-- 日度/周度/月度切换标签 -->
      <div class="period-tabs" role="tablist" aria-label="报表周期">
        <button
          v-for="p in periodOptions"
          :key="p.value"
          role="tab"
          :aria-selected="period === p.value"
          :class="['tab', period === p.value && 'active']"
          @click="switchPeriod(p.value)"
        >{{ p.label }}</button>
      </div>

      <div class="toolbar-right">
        <label for="review-date" class="sr-only">复盘日期</label>
        <input id="review-date" v-model="reviewDate" type="date" class="input" @change="loadReview" />

        <label for="strategy-select" class="sr-only">选择策略</label>
        <select id="strategy-select" v-model="selectedStrategy" class="input" @change="loadStrategyReport">
          <option value="">全部策略</option>
          <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>

        <button class="btn btn-primary" @click="loadReview" :disabled="loading">
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? '加载中...' : '查询' }}
        </button>

        <button class="btn btn-outline" @click="exportReport" :disabled="exporting" aria-label="导出报表">
          <span v-if="exporting" class="spinner" aria-hidden="true"></span>
          {{ exporting ? '导出中...' : '导出报表' }}
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-banner" role="alert">{{ errorMsg }}</div>

    <!-- 每日复盘报告 -->
    <section v-if="dailyReview" class="card" aria-label="每日复盘报告">
      <h2 class="section-title">每日复盘报告 — {{ reviewDate }}</h2>
      <div class="review-stats">
        <div class="stat-card">
          <span class="stat-label">选股胜率</span>
          <span class="stat-value" :class="dailyReview.win_rate >= 0.5 ? 'up' : 'down'">
            {{ (dailyReview.win_rate * 100).toFixed(1) }}%
          </span>
        </div>
        <div class="stat-card">
          <span class="stat-label">总盈亏</span>
          <span class="stat-value" :class="dailyReview.total_pnl >= 0 ? 'up' : 'down'">
            {{ dailyReview.total_pnl >= 0 ? '+' : '' }}{{ dailyReview.total_pnl.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
          </span>
        </div>
        <div class="stat-card">
          <span class="stat-label">交易笔数</span>
          <span class="stat-value">{{ dailyReview.trade_count }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">成功案例</span>
          <span class="stat-value up">{{ dailyReview.success_cases?.length ?? 0 }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">失败案例</span>
          <span class="stat-value down">{{ dailyReview.failure_cases?.length ?? 0 }}</span>
        </div>
      </div>

      <div class="case-grid">
        <div class="case-box">
          <h3 class="case-title success-title">✓ 成功案例</h3>
          <ul class="case-list">
            <li v-for="c in dailyReview.success_cases" :key="c.symbol" class="case-item">
              <span class="mono symbol">{{ c.symbol }}</span>
              <span class="case-reason">{{ c.reason }}</span>
              <span class="up case-pnl">+{{ c.pnl.toFixed(2) }}</span>
            </li>
            <li v-if="!dailyReview.success_cases?.length" class="empty-li">暂无成功案例</li>
          </ul>
        </div>
        <div class="case-box">
          <h3 class="case-title failure-title">✗ 失败案例</h3>
          <ul class="case-list">
            <li v-for="c in dailyReview.failure_cases" :key="c.symbol" class="case-item">
              <span class="mono symbol">{{ c.symbol }}</span>
              <span class="case-reason">{{ c.reason }}</span>
              <span class="down case-pnl">{{ c.pnl.toFixed(2) }}</span>
            </li>
            <li v-if="!dailyReview.failure_cases?.length" class="empty-li">暂无失败案例</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 策略绩效图表 -->
    <section class="card" aria-label="策略绩效图表">
      <div class="section-header">
        <h2 class="section-title">策略绩效 — {{ periodLabel }}</h2>
        <span v-if="strategyReport" class="strategy-name-badge">{{ strategyReport.strategy_name }}</span>
      </div>

      <div v-if="!strategyReport && !loading" class="empty-chart">请选择策略并点击查询</div>

      <div v-else class="charts-container">
        <!-- 收益柱状图 + 折线图并排 -->
        <div class="chart-row">
          <div class="chart-wrap">
            <p class="chart-label">收益率柱状图</p>
            <div ref="barChartRef" class="chart" role="img" aria-label="策略收益柱状图"></div>
          </div>
          <div class="chart-wrap">
            <p class="chart-label">累计收益折线图</p>
            <div ref="lineChartRef" class="chart" role="img" aria-label="累计收益折线图"></div>
          </div>
        </div>

        <!-- 风险指标饼图 -->
        <div class="chart-row chart-row-bottom">
          <div class="chart-wrap chart-wrap-pie">
            <p class="chart-label">风险指标分布</p>
            <div ref="pieChartRef" class="chart chart-pie" role="img" aria-label="风险指标饼图"></div>
          </div>
          <div v-if="strategyReport" class="risk-metrics-panel">
            <p class="chart-label">关键风险指标</p>
            <div class="risk-metrics-grid">
              <div class="risk-metric">
                <span class="rm-label">最大回撤</span>
                <span class="rm-value down">{{ (strategyReport.risk_metrics.max_drawdown * 100).toFixed(2) }}%</span>
              </div>
              <div class="risk-metric">
                <span class="rm-label">夏普比率</span>
                <span class="rm-value" :class="strategyReport.risk_metrics.sharpe_ratio >= 1 ? 'up' : ''">
                  {{ strategyReport.risk_metrics.sharpe_ratio.toFixed(2) }}
                </span>
              </div>
              <div class="risk-metric">
                <span class="rm-label">胜率</span>
                <span class="rm-value" :class="strategyReport.risk_metrics.win_rate >= 0.5 ? 'up' : 'down'">
                  {{ (strategyReport.risk_metrics.win_rate * 100).toFixed(1) }}%
                </span>
              </div>
              <div class="risk-metric">
                <span class="rm-label">卡玛比率</span>
                <span class="rm-value" :class="strategyReport.risk_metrics.calmar_ratio >= 1 ? 'up' : ''">
                  {{ strategyReport.risk_metrics.calmar_ratio.toFixed(2) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 多策略对比分析 -->
    <section class="card" aria-label="多策略对比分析">
      <div class="section-header">
        <h2 class="section-title">多策略对比分析</h2>
        <button class="btn btn-outline btn-sm" @click="loadCompare" :disabled="compareLoading || compareStrategies.length < 2">
          {{ compareLoading ? '加载中...' : '对比分析' }}
        </button>
      </div>

      <!-- 策略多选 -->
      <div class="compare-select-area">
        <p class="compare-hint">选择 2 个或以上策略进行对比：</p>
        <div class="strategy-checkboxes">
          <label
            v-for="s in strategies"
            :key="s.id"
            class="strategy-checkbox-label"
            :class="compareStrategies.includes(s.id) && 'checked'"
          >
            <input
              type="checkbox"
              :value="s.id"
              v-model="compareStrategies"
              class="sr-only"
            />
            {{ s.name }}
          </label>
        </div>
      </div>

      <!-- 对比折线图 -->
      <div v-if="compareChartVisible" class="compare-chart-wrap">
        <div ref="compareChartRef" class="chart chart-compare" role="img" aria-label="多策略收益对比折线图"></div>
      </div>

      <!-- 对比数据表格 -->
      <div v-if="compareReports.length > 0" class="table-wrap">
        <table class="data-table" aria-label="多策略对比数据表">
          <thead>
            <tr>
              <th scope="col">策略名称</th>
              <th scope="col">周期</th>
              <th scope="col">胜率</th>
              <th scope="col">最大回撤</th>
              <th scope="col">夏普比率</th>
              <th scope="col">卡玛比率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in compareReports" :key="r.strategy_id">
              <td>{{ r.strategy_name }}</td>
              <td>{{ periodLabel }}</td>
              <td :class="r.risk_metrics.win_rate >= 0.5 ? 'up' : 'down'">
                {{ (r.risk_metrics.win_rate * 100).toFixed(1) }}%
              </td>
              <td class="down">{{ (r.risk_metrics.max_drawdown * 100).toFixed(2) }}%</td>
              <td :class="r.risk_metrics.sharpe_ratio >= 1 ? 'up' : ''">
                {{ r.risk_metrics.sharpe_ratio.toFixed(2) }}
              </td>
              <td :class="r.risk_metrics.calmar_ratio >= 1 ? 'up' : ''">
                {{ r.risk_metrics.calmar_ratio.toFixed(2) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!compareLoading" class="empty">请选择至少 2 个策略后点击"对比分析"</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { apiClient } from '@/api'
import * as echarts from 'echarts'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface StrategyItem {
  id: string
  name: string
}

interface DailyReview {
  date: string
  win_rate: number
  total_pnl: number
  trade_count: number
  success_cases: { symbol: string; pnl: number; reason: string }[]
  failure_cases: { symbol: string; pnl: number; reason: string }[]
}

interface RiskMetrics {
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  calmar_ratio: number
}

interface StrategyReport {
  strategy_id: string
  strategy_name: string
  period: string
  returns: [string, number][]  // [日期, 收益率]
  risk_metrics: RiskMetrics
}

type TooltipAxisPoint = {
  axisValue?: string | number
  value?: unknown
}

// ─── 周期选项 ─────────────────────────────────────────────────────────────────

const periodOptions = [
  { value: 'daily', label: '日报' },
  { value: 'weekly', label: '周报' },
  { value: 'monthly', label: '月报' },
] as const

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const period = ref<'daily' | 'weekly' | 'monthly'>('daily')
const reviewDate = ref(new Date().toISOString().slice(0, 10))
const selectedStrategy = ref('')
const loading = ref(false)
const exporting = ref(false)
const compareLoading = ref(false)
const errorMsg = ref('')

const strategies = ref<StrategyItem[]>([])
const dailyReview = ref<DailyReview | null>(null)
const strategyReport = ref<StrategyReport | null>(null)
const compareStrategies = ref<string[]>([])
const compareReports = ref<StrategyReport[]>([])
const compareChartVisible = ref(false)

// ─── 图表 DOM 引用 ────────────────────────────────────────────────────────────

const barChartRef = ref<HTMLElement | null>(null)
const lineChartRef = ref<HTMLElement | null>(null)
const pieChartRef = ref<HTMLElement | null>(null)
const compareChartRef = ref<HTMLElement | null>(null)

let barChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null
let compareChart: echarts.ECharts | null = null

const resizeObservers: ResizeObserver[] = []

// ─── 计算属性 ─────────────────────────────────────────────────────────────────

const periodLabel = computed(() => {
  return periodOptions.find((p) => p.value === period.value)?.label ?? '日报'
})

// ─── 周期切换 ─────────────────────────────────────────────────────────────────

function switchPeriod(p: 'daily' | 'weekly' | 'monthly') {
  period.value = p
  loadStrategyReport()
}

// ─── 数据加载 ─────────────────────────────────────────────────────────────────

async function loadReview() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [dailyRes] = await Promise.all([
      apiClient.get<DailyReview>('/review/daily', { params: { date: reviewDate.value } }),
    ])
    dailyReview.value = dailyRes.data
    await loadStrategyReport()
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载复盘数据失败'
  } finally {
    loading.value = false
  }
}

async function loadStrategyReport() {
  if (!selectedStrategy.value) {
    strategyReport.value = null
    return
  }
  try {
    const res = await apiClient.get<StrategyReport>('/review/strategy-report', {
      params: {
        strategy_id: selectedStrategy.value,
        period: period.value,
      },
    })
    strategyReport.value = res.data
    await nextTick()
    renderStrategyCharts()
  } catch {
    strategyReport.value = null
  }
}

async function loadStrategies() {
  try {
    const res = await apiClient.get<StrategyItem[]>('/strategies')
    strategies.value = Array.isArray(res.data) ? res.data : []
  } catch {
    strategies.value = []
  }
}

// ─── 多策略对比 ───────────────────────────────────────────────────────────────

async function loadCompare() {
  if (compareStrategies.value.length < 2) return
  compareLoading.value = true
  compareReports.value = []
  compareChartVisible.value = false
  try {
    const results = await Promise.all(
      compareStrategies.value.map((sid) =>
        apiClient.get<StrategyReport>('/review/strategy-report', {
          params: { strategy_id: sid, period: period.value },
        })
      )
    )
    compareReports.value = results.map((r) => r.data)
    compareChartVisible.value = true
    await nextTick()
    renderCompareChart()
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '多策略对比加载失败'
  } finally {
    compareLoading.value = false
  }
}

// ─── 报表导出 ─────────────────────────────────────────────────────────────────

async function exportReport() {
  exporting.value = true
  try {
    const params = new URLSearchParams({ period: period.value })
    if (selectedStrategy.value) params.set('strategy_id', selectedStrategy.value)
    const token = localStorage.getItem('access_token')
    const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'
    const url = `${baseUrl}/review/export?${params.toString()}`

    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('导出失败')

    const blob = await res.blob()
    const contentDisposition = res.headers.get('content-disposition') ?? ''
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    const filename = filenameMatch ? filenameMatch[1].replace(/['"]/g, '') : `review_${period.value}_${reviewDate.value}.xlsx`

    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '导出失败，请重试'
  } finally {
    exporting.value = false
  }
}

// ─── ECharts 图表渲染 ─────────────────────────────────────────────────────────

/** 计算累计收益序列 */
function calcCumulative(returns: [string, number][]): number[] {
  let cum = 1
  return returns.map(([, r]) => {
    cum *= 1 + r
    return parseFloat(((cum - 1) * 100).toFixed(4))
  })
}

function renderStrategyCharts() {
  const r = strategyReport.value
  if (!r || !r.returns?.length) return

  const dates = r.returns.map(([d]) => d)
  const dailyReturns = r.returns.map(([, v]) => parseFloat((v * 100).toFixed(4)))
  const cumReturns = calcCumulative(r.returns)

  // 柱状图 - 日/周/月收益率
  if (barChart) {
    barChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1c2128',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 12 },
        formatter: (params: echarts.TooltipComponentFormatterCallbackParams) => {
          if (!Array.isArray(params) || !params[0]) return ''
          const p = params[0] as TooltipAxisPoint
          const val = typeof p.value === 'number' ? p.value.toFixed(2) : p.value
          return `<div style="color:#8b949e">${p.axisValue}</div><div>收益率: <b style="color:${Number(val) >= 0 ? '#f85149' : '#3fb950'}">${val}%</b></div>`
        },
      },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#8b949e', fontSize: 11, rotate: dates.length > 20 ? 45 : 0 },
        axisLine: { lineStyle: { color: '#30363d' } },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: { color: '#8b949e', formatter: (v: number) => v.toFixed(1) + '%' },
      },
      series: [{
        type: 'bar',
        data: dailyReturns.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#f85149' : '#3fb950' },
        })),
      }],
    })
  }

  // 折线图 - 累计收益
  if (lineChart) {
    lineChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1c2128',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 12 },
        formatter: (params: echarts.TooltipComponentFormatterCallbackParams) => {
          if (!Array.isArray(params) || !params[0]) return ''
          const p = params[0] as TooltipAxisPoint
          return `<div style="color:#8b949e">${p.axisValue}</div><div>累计收益: <b style="color:#58a6ff">${p.value}%</b></div>`
        },
      },
      grid: { left: 55, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#8b949e', fontSize: 11, rotate: dates.length > 20 ? 45 : 0 },
        axisLine: { lineStyle: { color: '#30363d' } },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: { color: '#8b949e', formatter: (v: number) => v.toFixed(1) + '%' },
      },
      series: [{
        type: 'line',
        data: cumReturns,
        smooth: true,
        lineStyle: { color: '#58a6ff', width: 2 },
        itemStyle: { color: '#58a6ff' },
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(88,166,255,0.25)' },
            { offset: 1, color: 'rgba(88,166,255,0)' },
          ]),
        },
      }],
    })
  }

  // 饼图 - 风险指标
  if (pieChart && r.risk_metrics) {
    const rm = r.risk_metrics
    // 将各指标归一化为相对权重展示（绝对值）
    const drawdownAbs = Math.abs(rm.max_drawdown * 100)
    const winRatePct = rm.win_rate * 100
    const sharpeNorm = Math.max(rm.sharpe_ratio, 0) * 10
    const calmarNorm = Math.max(rm.calmar_ratio, 0) * 10

    pieChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#1c2128',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 12 },
        formatter: '{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        textStyle: { color: '#8b949e', fontSize: 12 },
      },
      series: [{
        type: 'pie',
        radius: ['38%', '65%'],
        center: ['40%', '50%'],
        data: [
          { value: parseFloat(winRatePct.toFixed(1)), name: `胜率 ${winRatePct.toFixed(1)}%`, itemStyle: { color: '#3fb950' } },
          { value: parseFloat(drawdownAbs.toFixed(1)), name: `最大回撤 ${drawdownAbs.toFixed(1)}%`, itemStyle: { color: '#f85149' } },
          { value: parseFloat(sharpeNorm.toFixed(1)), name: `夏普×10 ${rm.sharpe_ratio.toFixed(2)}`, itemStyle: { color: '#58a6ff' } },
          { value: parseFloat(calmarNorm.toFixed(1)), name: `卡玛×10 ${rm.calmar_ratio.toFixed(2)}`, itemStyle: { color: '#d29922' } },
        ],
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' },
        },
      }],
    })
  }
}

// 多策略对比折线图
const COMPARE_COLORS = ['#58a6ff', '#f85149', '#3fb950', '#d29922', '#bc8cff', '#ff7b72']

function renderCompareChart() {
  if (!compareChart || compareReports.value.length === 0) return

  const series = compareReports.value.map((r, i) => {
    const cumReturns = calcCumulative(r.returns)
    return {
      name: r.strategy_name,
      type: 'line' as const,
      data: cumReturns,
      smooth: true,
      lineStyle: { color: COMPARE_COLORS[i % COMPARE_COLORS.length], width: 2 },
      itemStyle: { color: COMPARE_COLORS[i % COMPARE_COLORS.length] },
      symbol: 'none',
    }
  })

  // 使用第一个策略的日期轴（假设各策略日期对齐）
  const dates = compareReports.value[0]?.returns.map(([d]) => d) ?? []

  compareChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1c2128',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
    },
    legend: {
      data: compareReports.value.map((r) => r.strategy_name),
      textStyle: { color: '#8b949e' },
      top: 4,
    },
    grid: { left: 55, right: 20, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#8b949e', fontSize: 11, rotate: dates.length > 20 ? 45 : 0 },
      axisLine: { lineStyle: { color: '#30363d' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#21262d' } },
      axisLabel: { color: '#8b949e', formatter: (v: number) => v.toFixed(1) + '%' },
    },
    series,
  })
}

// ─── 图表初始化与 ResizeObserver ──────────────────────────────────────────────

function initChart(el: HTMLElement, theme = 'dark'): echarts.ECharts {
  const instance = echarts.init(el, theme)
  const ro = new ResizeObserver(() => instance.resize())
  ro.observe(el)
  resizeObservers.push(ro)
  return instance
}

// ─── 监听 strategyReport 变化重新渲染 ────────────────────────────────────────

watch(strategyReport, async (val) => {
  if (val) {
    await nextTick()
    renderStrategyCharts()
  }
})

watch(compareChartVisible, async (val) => {
  if (val) {
    await nextTick()
    if (compareChartRef.value && !compareChart) {
      compareChart = initChart(compareChartRef.value)
    }
    renderCompareChart()
  }
})

// ─── 生命周期 ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadStrategies()
  await nextTick()
  if (barChartRef.value) barChart = initChart(barChartRef.value)
  if (lineChartRef.value) lineChart = initChart(lineChartRef.value)
  if (pieChartRef.value) pieChart = initChart(pieChartRef.value)
  // 加载当日复盘（不强制要求策略）
  loadReview()
})

onUnmounted(() => {
  resizeObservers.forEach((ro) => ro.disconnect())
  barChart?.dispose()
  lineChart?.dispose()
  pieChart?.dispose()
  compareChart?.dispose()
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.review-view { max-width: 1280px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; color: #e6edf3; margin: 0; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

/* ─── 卡片 ─────────────────────────────────────────────────────────────────── */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }

/* ─── 工具栏 ────────────────────────────────────────────────────────────────── */
.toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 14px 20px; }
.toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* ─── 周期切换标签 ──────────────────────────────────────────────────────────── */
.period-tabs { display: flex; gap: 4px; }
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 18px; border-radius: 6px; cursor: pointer; font-size: 14px;
  transition: all 0.15s;
}
.tab:hover:not(.active) { color: #e6edf3; border-color: #8b949e; }
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; font-weight: 600; }

/* ─── 输入控件 ──────────────────────────────────────────────────────────────── */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 6px 12px; border-radius: 6px; font-size: 14px; min-width: 120px;
}
.input:focus { outline: none; border-color: #58a6ff; }

/* ─── 按钮 ─────────────────────────────────────────────────────────────────── */
.btn { padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; border: none; display: inline-flex; align-items: center; gap: 6px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #238636; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2ea043; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-sm { padding: 5px 12px; font-size: 13px; }

/* ─── 旋转加载图标 ──────────────────────────────────────────────────────────── */
.spinner {
  display: inline-block; width: 13px; height: 13px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 错误提示 ──────────────────────────────────────────────────────────────── */
.error-banner {
  background: #3a1a1a; border: 1px solid #f8514944; color: #f85149;
  padding: 10px 16px; border-radius: 6px; font-size: 14px; margin-bottom: 16px;
}

/* ─── 复盘统计卡片 ──────────────────────────────────────────────────────────── */
.review-stats { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.stat-card {
  background: #0d1117; border: 1px solid #21262d; border-radius: 8px;
  padding: 12px 18px; display: flex; flex-direction: column; gap: 4px; min-width: 130px;
}
.stat-label { font-size: 12px; color: #8b949e; }
.stat-value { font-size: 22px; font-weight: 700; color: #e6edf3; }

/* ─── 成功/失败案例 ─────────────────────────────────────────────────────────── */
.case-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .case-grid { grid-template-columns: 1fr; } }
.case-box { background: #0d1117; border-radius: 6px; padding: 14px; }
.case-title { font-size: 14px; margin-bottom: 10px; font-weight: 600; }
.success-title { color: #3fb950; }
.failure-title { color: #f85149; }
.case-list { list-style: none; }
.case-item { display: flex; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid #21262d; font-size: 13px; color: #e6edf3; }
.case-item:last-child { border-bottom: none; }
.symbol { font-family: 'SF Mono', 'Consolas', monospace; min-width: 70px; }
.case-reason { flex: 1; color: #8b949e; font-size: 12px; }
.case-pnl { font-weight: 600; white-space: nowrap; }
.empty-li { color: #484f58; font-size: 13px; padding: 8px 0; }

/* ─── section header ────────────────────────────────────────────────────────── */
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.strategy-name-badge {
  background: #1f6feb22; color: #58a6ff; border: 1px solid #58a6ff44;
  padding: 3px 10px; border-radius: 12px; font-size: 13px;
}

/* ─── 图表区域 ──────────────────────────────────────────────────────────────── */
.charts-container { display: flex; flex-direction: column; gap: 16px; }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .chart-row { grid-template-columns: 1fr; } }
.chart-row-bottom { align-items: start; }
.chart-wrap { display: flex; flex-direction: column; gap: 6px; }
.chart-wrap-pie { max-width: 420px; }
.chart-label { font-size: 12px; color: #8b949e; margin: 0; }
.chart { width: 100%; height: 280px; background: #0d1117; border-radius: 6px; }
.chart-pie { height: 240px; }
.chart-compare { height: 320px; background: #0d1117; border-radius: 6px; }
.empty-chart { color: #484f58; font-size: 14px; padding: 40px; text-align: center; }

/* ─── 风险指标面板 ──────────────────────────────────────────────────────────── */
.risk-metrics-panel { display: flex; flex-direction: column; gap: 8px; }
.risk-metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.risk-metric {
  background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
  padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;
}
.rm-label { font-size: 12px; color: #8b949e; }
.rm-value { font-size: 20px; font-weight: 700; color: #e6edf3; }

/* ─── 多策略对比 ────────────────────────────────────────────────────────────── */
.compare-select-area { margin-bottom: 16px; }
.compare-hint { font-size: 13px; color: #8b949e; margin-bottom: 10px; }
.strategy-checkboxes { display: flex; flex-wrap: wrap; gap: 8px; }
.strategy-checkbox-label {
  background: #0d1117; border: 1px solid #30363d; color: #8b949e;
  padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
  transition: all 0.15s; user-select: none;
}
.strategy-checkbox-label:hover { color: #e6edf3; border-color: #8b949e; }
.strategy-checkbox-label.checked { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.compare-chart-wrap { margin-bottom: 16px; }

/* ─── 表格 ─────────────────────────────────────────────────────────────────── */
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; min-width: 600px; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 13px; white-space: nowrap; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; }
.empty { text-align: center; color: #484f58; padding: 24px; font-size: 14px; }

/* ─── A 股配色：涨红跌绿 ─────────────────────────────────────────────────────── */
.up { color: #f85149; }
.down { color: #3fb950; }
</style>
