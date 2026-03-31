<template>
  <div class="dashboard">
    <h1 class="page-title">大盘概况</h1>

    <!-- 指数卡片 -->
    <section class="index-cards" aria-label="大盘指数">
      <div v-if="marketStore.loading" class="loading-text">加载大盘数据中...</div>
      <div v-else-if="marketStore.error" class="error-banner-inline">
        {{ marketStore.error }}
        <button class="btn retry-btn" @click="marketStore.fetchOverview()">重试</button>
      </div>
      <template v-else>
        <div v-for="idx in indexCards" :key="idx.label" class="index-card">
          <span class="idx-label">{{ idx.label }}</span>
          <span class="idx-value">{{ idx.value.toFixed(2) }}</span>
          <span class="idx-change" :class="idx.changePct >= 0 ? 'up' : 'down'">
            {{ idx.changePct >= 0 ? '+' : '' }}{{ idx.changePct.toFixed(2) }}%
          </span>
        </div>
      </template>
    </section>

    <!-- 市场情绪 -->
    <section class="market-sentiment" aria-label="市场情绪">
      <div class="sentiment-item">
        <span class="label">上涨</span>
        <span class="value up">{{ overview?.advance_count ?? 0 }}</span>
      </div>
      <div class="sentiment-item">
        <span class="label">下跌</span>
        <span class="value down">{{ overview?.decline_count ?? 0 }}</span>
      </div>
      <div class="sentiment-item">
        <span class="label">涨停</span>
        <span class="value up">{{ overview?.limit_up_count ?? 0 }}</span>
      </div>
      <div class="sentiment-item">
        <span class="label">跌停</span>
        <span class="value down">{{ overview?.limit_down_count ?? 0 }}</span>
      </div>
    </section>

    <!-- K线图 / 基本面 / 资金流向 -->
    <section class="chart-section" aria-label="股票数据">
      <div class="chart-toolbar">
        <label for="symbol-input" class="sr-only">股票代码</label>
        <input
          id="symbol-input"
          v-model="symbol"
          placeholder="输入股票代码，如 000001"
          class="input"
          @keyup.enter="loadKline"
        />
        <select v-model="freq" class="input" aria-label="K线周期">
          <option value="1d">日K</option>
          <option value="1w">周K</option>
          <option value="1M">月K</option>
          <option value="60m">60分钟</option>
          <option value="30m">30分钟</option>
          <option value="15m">15分钟</option>
          <option value="5m">5分钟</option>
        </select>
        <input v-model="klineStart" type="date" class="input" aria-label="开始日期" />
        <input v-model="klineEnd" type="date" class="input" aria-label="结束日期" />
        <button class="btn" @click="loadKline">查询</button>
      </div>
      <div v-if="stockLabel" class="stock-label">{{ stockLabel }}</div>

      <!-- 标签页导航 -->
      <div class="chart-tabs" role="tablist" aria-label="数据视图切换">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          role="tab"
          :aria-selected="activeTab === tab.key"
          :class="['tab-btn', { active: activeTab === tab.key }]"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- K线图面板 -->
      <div v-show="activeTab === 'kline'" role="tabpanel" aria-label="K线图">
        <div ref="klineChartRef" class="kline-chart" role="img" aria-label="K线图表"></div>
      </div>

      <!-- 基本面面板 -->
      <div v-show="activeTab === 'fundamentals'" role="tabpanel" aria-label="基本面数据">
        <div v-if="fundamentalsLoading" class="loading-indicator">加载中...</div>
        <div v-else-if="fundamentalsError" class="error-banner">
          {{ fundamentalsError }}
          <button class="btn retry-btn" @click="loadFundamentals">重试</button>
        </div>
        <div v-else-if="fundamentals" class="fundamentals-cards">
          <div class="fund-card" v-for="item in fundamentalCards" :key="item.key">
            <span class="fund-label">{{ item.label }}</span>
            <span class="fund-value" :class="getFundamentalColorClass(item.key, item.raw)">
              {{ formatFundamentalValue(item.key, item.raw) }}
            </span>
          </div>
          <div class="fund-meta">
            <span v-if="fundamentals.report_period">报告期：{{ fundamentals.report_period }}</span>
            <span v-if="fundamentals.updated_at">更新时间：{{ fundamentals.updated_at }}</span>
          </div>
        </div>
        <div v-else class="empty-panel">请先查询股票代码</div>
      </div>

      <!-- 资金流向面板 -->
      <div v-show="activeTab === 'moneyFlow'" role="tabpanel" aria-label="资金流向数据">
        <div v-if="moneyFlowLoading" class="loading-indicator">加载中...</div>
        <div v-else-if="moneyFlowError" class="error-banner">
          {{ moneyFlowError }}
          <button class="btn retry-btn" @click="loadMoneyFlow">重试</button>
        </div>
        <div v-else-if="moneyFlow" class="money-flow-content">
          <!-- 资金流向汇总卡片 (Task 24.4.2) -->
          <div class="money-flow-summary">
            <div class="mf-card">
              <span class="mf-label">当日主力净流入</span>
              <span class="mf-value" :class="todayInflow >= 0 ? 'up' : 'down'">
                {{ formatWanYuan(todayInflow) }}
              </span>
            </div>
            <div class="mf-card">
              <span class="mf-label">近5日累计净流入</span>
              <span class="mf-value" :class="last5DaysTotal >= 0 ? 'up' : 'down'">
                {{ formatWanYuan(last5DaysTotal) }}
              </span>
            </div>
            <div class="mf-card">
              <span class="mf-label">北向资金变动</span>
              <span class="mf-value" :class="northFlowChange !== null && northFlowChange >= 0 ? 'up' : 'down'">
                {{ northFlowChange !== null ? formatWanYuan(northFlowChange) : '--' }}
              </span>
            </div>
            <div class="mf-card">
              <span class="mf-label">大单成交占比</span>
              <span class="mf-value">
                {{ latestLargeOrderRatio !== null ? latestLargeOrderRatio.toFixed(2) + '%' : '--' }}
              </span>
            </div>
          </div>
          <!-- 资金流向柱状图 (Task 24.4.1) -->
          <div ref="moneyFlowChartRef" class="money-flow-chart"></div>
        </div>
        <div v-else class="empty-panel">请先查询股票代码</div>
      </div>
    </section>

    <!-- 板块热力 -->
    <section class="sector-section" aria-label="板块数据">
      <h2 class="section-title">板块涨幅排行</h2>
      <table class="data-table" aria-label="板块涨幅排行表">
        <thead>
          <tr>
            <th scope="col">板块名称</th>
            <th scope="col">涨跌幅</th>
            <th scope="col">领涨股</th>
            <th scope="col">总市值(亿)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sectors" :key="s.name">
            <td>{{ s.name }}</td>
            <td :class="s.change_pct >= 0 ? 'up' : 'down'">
              {{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
            </td>
            <td>{{ s.leader }}</td>
            <td>{{ (s.amount / 1e8).toFixed(2) }}</td>
          </tr>
          <tr v-if="sectors.length === 0">
            <td colspan="4" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useMarketStore } from '@/stores/market'
import { apiClient } from '@/api'
import * as echarts from 'echarts'
import { getFundamentalColorClass, formatFundamentalValue } from './fundamentalUtils'
import { getMoneyFlowBarColor } from './moneyFlowUtils'

// ─── TypeScript 接口 (Task 24.2.2) ──────────────────────────────────────────

interface StockFundamentalsResponse {
  symbol: string
  name: string | null
  pe_ttm: number | null
  pb: number | null
  roe: number | null
  market_cap: number | null       // 亿元
  revenue_growth: number | null   // %
  net_profit_growth: number | null // %
  report_period: string | null
  updated_at: string | null
}

interface MoneyFlowDailyRecord {
  trade_date: string
  main_net_inflow: number         // 万元
  north_net_inflow: number | null // 万元
  large_order_ratio: number | null // %
  super_large_inflow: number | null // 万元
  large_inflow: number | null     // 万元
}

interface StockMoneyFlowResponse {
  symbol: string
  name: string | null
  days: number
  records: MoneyFlowDailyRecord[]
}

type ChartTab = 'kline' | 'fundamentals' | 'moneyFlow'

// ─── 市场概览 ────────────────────────────────────────────────────────────────

const marketStore = useMarketStore()
const overview = computed(() => marketStore.overview)

const indexCards = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '上证指数', value: o.sh_index, changePct: o.sh_change_pct },
    { label: '深证成指', value: o.sz_index, changePct: o.sz_change_pct },
    { label: '创业板指', value: o.cyb_index, changePct: o.cyb_change_pct },
  ]
})

// ─── 标签页导航 (Task 24.2.1) ────────────────────────────────────────────────

const tabs: { key: ChartTab; label: string }[] = [
  { key: 'kline', label: 'K线图' },
  { key: 'fundamentals', label: '基本面' },
  { key: 'moneyFlow', label: '资金流向' },
]

const activeTab = ref<ChartTab>('kline')

// Track whether each tab has been loaded for the current symbol
const fundamentalsLoaded = ref(false)
const moneyFlowLoaded = ref(false)

// ─── K线图 ───────────────────────────────────────────────────────────────────

const symbol = ref('000001')
const freq = ref('1d')
const klineStart = ref('')
const klineEnd = ref('')
const klineChartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

interface KlineData {
  time: string
  open: number
  close: number
  low: number
  high: number
  volume: number
}

interface KlineBar {
  time: string
  open: string | number
  close: string | number
  low: string | number
  high: string | number
  volume: number
}

interface KlineResponse {
  symbol: string
  name?: string
  freq: string
  bars: KlineBar[]
}

const stockLabel = ref('')

// ─── 基本面 & 资金流向响应式状态 (Task 24.2.2) ──────────────────────────────

const fundamentals = ref<StockFundamentalsResponse | null>(null)
const fundamentalsLoading = ref(false)
const fundamentalsError = ref('')

const moneyFlow = ref<StockMoneyFlowResponse | null>(null)
const moneyFlowLoading = ref(false)
const moneyFlowError = ref('')

// ─── 资金流向图表 (Task 24.4.1) ──────────────────────────────────────────────

const moneyFlowChartRef = ref<HTMLElement | null>(null)
let moneyFlowChartInstance: echarts.ECharts | null = null

// ─── 资金流向汇总计算属性 (Task 24.4.2) ──────────────────────────────────────

const todayInflow = computed(() => {
  const records = moneyFlow.value?.records
  if (!records || records.length === 0) return 0
  return records[records.length - 1].main_net_inflow
})

const last5DaysTotal = computed(() => {
  const records = moneyFlow.value?.records
  if (!records || records.length === 0) return 0
  const last5 = records.slice(-5)
  return last5.reduce((sum, r) => sum + r.main_net_inflow, 0)
})

const northFlowChange = computed<number | null>(() => {
  const records = moneyFlow.value?.records
  if (!records || records.length === 0) return null
  const latest = records[records.length - 1]
  return latest.north_net_inflow
})

const latestLargeOrderRatio = computed<number | null>(() => {
  const records = moneyFlow.value?.records
  if (!records || records.length === 0) return null
  return records[records.length - 1].large_order_ratio
})

function formatWanYuan(value: number): string {
  return value.toFixed(2) + ' 万元'
}

// ─── 基本面数据卡片计算属性 (Task 24.3.1) ────────────────────────────────────

const fundamentalCards = computed(() => {
  const f = fundamentals.value
  if (!f) return []
  return [
    { key: 'pe_ttm', label: 'PE TTM', raw: f.pe_ttm },
    { key: 'pb', label: 'PB', raw: f.pb },
    { key: 'roe', label: 'ROE', raw: f.roe },
    { key: 'market_cap', label: '总市值', raw: f.market_cap },
    { key: 'revenue_growth', label: '营收同比增长率', raw: f.revenue_growth },
    { key: 'net_profit_growth', label: '净利润同比增长率', raw: f.net_profit_growth },
  ]
})

// ─── AbortController 管理 (Task 24.2.3) ─────────────────────────────────────

let fundamentalsAbortController: AbortController | null = null
let moneyFlowAbortController: AbortController | null = null

// ─── 标签页切换逻辑 (Task 24.2.3) ───────────────────────────────────────────

function switchTab(tab: ChartTab) {
  activeTab.value = tab
  if (tab === 'fundamentals' && !fundamentalsLoaded.value) {
    loadFundamentals()
  } else if (tab === 'moneyFlow' && !moneyFlowLoaded.value) {
    loadMoneyFlow()
  }
}

// ─── 数据加载函数 (Task 24.2.3) ─────────────────────────────────────────────

async function loadFundamentals() {
  if (!symbol.value) return

  // Cancel previous request
  fundamentalsAbortController?.abort()
  fundamentalsAbortController = new AbortController()

  fundamentalsLoading.value = true
  fundamentalsError.value = ''
  fundamentals.value = null

  try {
    const res = await apiClient.get<StockFundamentalsResponse>(
      `/data/stock/${symbol.value}/fundamentals`,
      { signal: fundamentalsAbortController.signal },
    )
    fundamentals.value = res.data
    fundamentalsLoaded.value = true
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'CanceledError') return
    if (err instanceof Error && err.name === 'AbortError') return
    fundamentalsError.value = '获取基本面数据失败，请重试'
  } finally {
    fundamentalsLoading.value = false
  }
}

async function loadMoneyFlow() {
  if (!symbol.value) return

  // Cancel previous request
  moneyFlowAbortController?.abort()
  moneyFlowAbortController = new AbortController()

  moneyFlowLoading.value = true
  moneyFlowError.value = ''
  moneyFlow.value = null

  try {
    const res = await apiClient.get<StockMoneyFlowResponse>(
      `/data/stock/${symbol.value}/money-flow`,
      { signal: moneyFlowAbortController.signal },
    )
    moneyFlow.value = res.data
    moneyFlowLoaded.value = true
    // Render chart after data loads and DOM updates
    await nextTick()
    initMoneyFlowChart()
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'CanceledError') return
    if (err instanceof Error && err.name === 'AbortError') return
    moneyFlowError.value = '获取资金流向数据失败，请重试'
  } finally {
    moneyFlowLoading.value = false
  }
}

// ─── 资金流向柱状图渲染 (Task 24.4.1) ───────────────────────────────────────

function initMoneyFlowChart() {
  if (!moneyFlowChartRef.value) return
  if (!moneyFlowChartInstance) {
    moneyFlowChartInstance = echarts.init(moneyFlowChartRef.value)
  }
  const records = moneyFlow.value?.records
  if (records && records.length > 0) {
    renderMoneyFlowChart(records)
  }
}

function renderMoneyFlowChart(records: MoneyFlowDailyRecord[]) {
  if (!moneyFlowChartInstance || !records.length) return

  const dates = records.map(r => r.trade_date)
  const values = records.map(r => r.main_net_inflow)

  moneyFlowChartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>主力净流入：${p.value.toFixed(2)} 万元`
      },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#8b949e', rotate: 45 },
    },
    yAxis: {
      type: 'value',
      name: '万元',
      splitLine: { lineStyle: { color: '#21262d' } },
      axisLabel: { color: '#8b949e' },
    },
    series: [{
      type: 'bar',
      data: values.map((v) => ({
        value: v,
        itemStyle: { color: getMoneyFlowBarColor(v) },
      })),
    }],
  })
}

// ─── 股票切换时重置标签页数据 (Task 24.2.3 / 需求 26.12) ────────────────────

function resetTabData() {
  fundamentals.value = null
  fundamentalsError.value = ''
  fundamentalsLoading.value = false
  fundamentalsLoaded.value = false
  moneyFlow.value = null
  moneyFlowError.value = ''
  moneyFlowLoading.value = false
  moneyFlowLoaded.value = false
  // Dispose money flow chart on stock switch
  moneyFlowChartInstance?.dispose()
  moneyFlowChartInstance = null
  // If currently on a non-kline tab, auto-load data for the new symbol
  if (activeTab.value === 'fundamentals') loadFundamentals()
  if (activeTab.value === 'moneyFlow') loadMoneyFlow()
}

// ─── K线图加载 ───────────────────────────────────────────────────────────────

async function loadKline() {
  try {
    const params: Record<string, string> = { freq: freq.value }
    if (klineStart.value) params.start = klineStart.value
    if (klineEnd.value) params.end = klineEnd.value

    const res = await apiClient.get<KlineResponse>(`/data/kline/${symbol.value}`, { params })
    const resp = res.data
    const name = resp.name || ''
    stockLabel.value = name ? `${name}（${symbol.value}）` : symbol.value

    const data: KlineData[] = (resp.bars ?? []).map((b) => ({
      time: b.time,
      open: Number(b.open),
      close: Number(b.close),
      low: Number(b.low),
      high: Number(b.high),
      volume: b.volume,
    }))
    renderKline(data)
    // Reset tab data when stock changes
    resetTabData()
  } catch {
    stockLabel.value = ''
  }
}

function renderKline(data: KlineData[]) {
  if (!chartInstance || !data.length) return
  const dates = data.map((d) => d.time.slice(0, 10))
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high])
  const volumes = data.map((d) => d.volume)

  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [
      { left: 60, right: 20, top: 30, height: '55%' },
      { left: 60, right: 20, top: '72%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { color: '#8b949e' } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#21262d' } }, axisLabel: { color: '#8b949e' } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { color: '#8b949e' } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: { color: '#f85149', color0: '#3fb950', borderColor: '#f85149', borderColor0: '#3fb950' },
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#30363d' },
      },
    ],
  })
}

// ─── 板块数据 ────────────────────────────────────────────────────────────────

interface SectorData {
  name: string
  change_pct: number
  leader: string
  amount: number
}
const sectors = ref<SectorData[]>([])

async function loadSectors() {
  try {
    const res = await apiClient.get<SectorData[]>('/data/market/sectors')
    sectors.value = res.data
  } catch {
    /* API not available yet */
  }
}

// ─── WebSocket 实时刷新 ─────────────────────────────────────────────────────

let ws: WebSocket | null = null

function connectWs() {
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws/market`
  try {
    ws = new WebSocket(wsUrl)
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'market_overview' && marketStore.overview) {
          Object.assign(marketStore.overview, msg.data)
        }
      } catch { /* ignore parse errors */ }
    }
    ws.onclose = () => {
      setTimeout(connectWs, 5000)
    }
  } catch { /* WebSocket not available */ }
}

// ─── 图表 resize 处理 ────────────────────────────────────────────────────────

function handleResize() {
  chartInstance?.resize()
  moneyFlowChartInstance?.resize()
}

// ─── 生命周期 ────────────────────────────────────────────────────────────────

onMounted(async () => {
  // 先初始化图表实例，再加载数据
  await nextTick()
  if (klineChartRef.value) {
    chartInstance = echarts.init(klineChartRef.value)
  }
  marketStore.fetchOverview()
  loadSectors()
  loadKline()
  connectWs()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chartInstance?.dispose()
  moneyFlowChartInstance?.dispose()
  fundamentalsAbortController?.abort()
  moneyFlowAbortController?.abort()
  ws?.close()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.dashboard { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.index-cards { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.index-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 16px 24px; display: flex; flex-direction: column; gap: 4px; min-width: 180px;
}
.idx-label { font-size: 13px; color: #8b949e; }
.idx-value { font-size: 22px; font-weight: 600; color: #e6edf3; }
.idx-change { font-size: 14px; font-weight: 500; }
.up { color: #f85149; }
.down { color: #3fb950; }

.market-sentiment { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.sentiment-item {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 12px 20px; display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 100px;
}
.sentiment-item .label { font-size: 13px; color: #8b949e; }
.sentiment-item .value { font-size: 20px; font-weight: 600; }

.chart-section { margin-bottom: 24px; }
.chart-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover { background: #2ea043; }
.stock-label { font-size: 15px; font-weight: 600; color: #e6edf3; margin-bottom: 8px; }

/* 标签页导航 */
.chart-tabs {
  display: flex; gap: 0; margin-bottom: 0;
  border-bottom: 1px solid #30363d;
}
.tab-btn {
  background: transparent; border: none; color: #8b949e;
  padding: 10px 20px; font-size: 14px; cursor: pointer;
  border-bottom: 2px solid transparent; transition: color 0.2s, border-color 0.2s;
}
.tab-btn:hover { color: #e6edf3; }
.tab-btn.active {
  color: #e6edf3; border-bottom-color: #238636; font-weight: 500;
}

.kline-chart { width: 100%; height: 420px; background: #161b22; border-radius: 0 0 8px 8px; border: 1px solid #30363d; border-top: none; }

/* 面板通用样式 */
.loading-indicator {
  display: flex; align-items: center; justify-content: center;
  height: 200px; color: #8b949e; font-size: 14px;
  background: #161b22; border: 1px solid #30363d; border-top: none; border-radius: 0 0 8px 8px;
}
.error-banner {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  height: 200px; color: #f85149; font-size: 14px;
  background: #161b22; border: 1px solid #30363d; border-top: none; border-radius: 0 0 8px 8px;
}
.retry-btn { font-size: 12px; padding: 4px 12px; }
.empty-panel {
  display: flex; align-items: center; justify-content: center;
  height: 200px; color: #484f58; font-size: 14px;
  background: #161b22; border: 1px solid #30363d; border-top: none; border-radius: 0 0 8px 8px;
}
.fundamentals-cards, .money-flow-content {
  min-height: 200px; padding: 16px;
  background: #161b22; border: 1px solid #30363d; border-top: none; border-radius: 0 0 8px 8px;
}
.fundamentals-cards {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;
}
.fund-card {
  background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.fund-label { font-size: 13px; color: #8b949e; }
.fund-value { font-size: 20px; font-weight: 600; color: #e6edf3; }
.fund-meta {
  grid-column: 1 / -1; display: flex; gap: 20px; padding-top: 8px;
  border-top: 1px solid #21262d; font-size: 12px; color: #484f58;
}
.color-green { color: #3fb950; }
.color-red { color: #f85149; }

/* 资金流向汇总卡片 */
.money-flow-summary {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;
  margin-bottom: 16px;
}
.mf-card {
  background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.mf-label { font-size: 13px; color: #8b949e; }
.mf-value { font-size: 20px; font-weight: 600; color: #e6edf3; }

/* 资金流向柱状图 */
.money-flow-chart { width: 100%; height: 350px; }

.sector-section { margin-bottom: 24px; }
.data-table { width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; background: #161b22; }
.data-table td { color: #e6edf3; }
.empty { text-align: center; color: #484f58; padding: 24px; }
.loading-text { color: #8b949e; font-size: 14px; padding: 16px 0; }
.error-banner-inline {
  display: flex; align-items: center; gap: 12px;
  color: #f85149; font-size: 14px; padding: 16px 0;
}
</style>
