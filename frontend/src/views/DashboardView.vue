<template>
  <div class="dashboard">
    <h1 class="page-title">大盘概况</h1>

    <!-- 指数卡片 -->
    <section class="index-cards" aria-label="大盘指数">
      <div v-for="idx in indexCards" :key="idx.label" class="index-card">
        <span class="idx-label">{{ idx.label }}</span>
        <span class="idx-value">{{ idx.value.toFixed(2) }}</span>
        <span class="idx-change" :class="idx.changePct >= 0 ? 'up' : 'down'">
          {{ idx.changePct >= 0 ? '+' : '' }}{{ idx.changePct.toFixed(2) }}%
        </span>
      </div>
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

    <!-- K线图 -->
    <section class="chart-section" aria-label="K线图">
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
        <button class="btn" @click="loadKline">查询</button>
      </div>
      <div ref="klineChartRef" class="kline-chart" role="img" aria-label="K线图表"></div>
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
            <th scope="col">成交额(亿)</th>
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

// K线图
const symbol = ref('000001')
const freq = ref('1d')
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

async function loadKline() {
  try {
    const res = await apiClient.get<KlineData[]>(`/data/kline/${symbol.value}`, {
      params: { freq: freq.value, limit: 120 },
    })
    renderKline(res.data)
  } catch {
    /* API not available yet */
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

// 板块数据
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

// WebSocket 实时刷新
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

onMounted(async () => {
  marketStore.fetchOverview()
  loadSectors()
  loadKline()
  connectWs()
  await nextTick()
  if (klineChartRef.value) {
    chartInstance = echarts.init(klineChartRef.value)
  }
})

onUnmounted(() => {
  chartInstance?.dispose()
  ws?.close()
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
.kline-chart { width: 100%; height: 420px; background: #161b22; border-radius: 8px; border: 1px solid #30363d; }

.sector-section { margin-bottom: 24px; }
.data-table { width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; background: #161b22; }
.data-table td { color: #e6edf3; }
.empty { text-align: center; color: #484f58; padding: 24px; }
</style>
