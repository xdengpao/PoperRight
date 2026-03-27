<template>
  <div class="positions-view">
    <div class="page-header">
      <h1 class="page-title">持仓管理</h1>
      <div class="header-actions">
        <span v-if="wsConnected" class="ws-status connected" title="WebSocket 已连接">● 实时</span>
        <span v-else class="ws-status polling" title="轮询模式">● 轮询</span>
        <button class="btn btn-outline" @click="fetchPositions" :disabled="loading" aria-label="刷新持仓">
          <span :class="['refresh-icon', loading && 'spinning']">↻</span>
          {{ loading ? '刷新中...' : '刷新持仓' }}
        </button>
      </div>
    </div>

    <!-- 持仓汇总卡片 -->
    <section class="summary-cards" aria-label="持仓汇总">
      <div class="summary-card">
        <span class="label">总市值</span>
        <span class="value mono">{{ formatMoney(totalMarketValue) }}</span>
      </div>
      <div class="summary-card">
        <span class="label">总盈亏</span>
        <span class="value mono" :class="totalPnl >= 0 ? 'up' : 'down'">
          {{ totalPnl >= 0 ? '+' : '' }}{{ formatMoney(totalPnl) }}
        </span>
      </div>
      <div class="summary-card">
        <span class="label">总盈亏比例</span>
        <span class="value" :class="totalPnlPct >= 0 ? 'up' : 'down'">
          {{ totalPnlPct >= 0 ? '+' : '' }}{{ totalPnlPct.toFixed(2) }}%
        </span>
      </div>
      <div class="summary-card">
        <span class="label">持仓数量</span>
        <span class="value">{{ positions.length }} 只</span>
      </div>
      <div class="summary-card warning-count" v-if="warningCount > 0">
        <span class="label">破位预警</span>
        <span class="value up">{{ warningCount }} 只</span>
      </div>
    </section>

    <!-- 主内容区：表格 + 饼图 -->
    <div class="main-layout">
      <!-- 持仓明细表格 -->
      <section class="card table-section" aria-label="持仓明细">
        <h2 class="section-title">持仓明细</h2>
        <div v-if="loading && positions.length === 0" class="loading-text">加载中...</div>
        <div class="table-wrap">
          <table class="data-table" aria-label="持仓明细表">
            <thead>
              <tr>
                <th scope="col">股票代码</th>
                <th scope="col">名称</th>
                <th scope="col">持仓股数</th>
                <th scope="col">成本价</th>
                <th scope="col">当前价</th>
                <th scope="col">当前市值</th>
                <th scope="col">盈亏金额</th>
                <th scope="col">盈亏比例</th>
                <th scope="col">仓位占比</th>
                <th scope="col">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in positionRows"
                :key="p.symbol"
                :class="['position-row', p.trend_status === 'WARNING' && 'row-warning']"
                :aria-label="p.trend_status === 'WARNING' ? `${p.symbol} 破位预警` : p.symbol"
              >
                <td class="mono symbol-cell">
                  {{ p.symbol }}
                  <span v-if="p.trend_status === 'WARNING'" class="warning-tag" title="趋势破位预警">⚠</span>
                </td>
                <td class="name-cell">{{ p.name || '—' }}</td>
                <td class="mono">{{ p.quantity.toLocaleString() }}</td>
                <td class="mono">{{ p.cost_price.toFixed(2) }}</td>
                <td class="mono price-cell">{{ p.current_price.toFixed(2) }}</td>
                <td class="mono">{{ formatMoney(p.market_value) }}</td>
                <td class="mono" :class="p.pnl >= 0 ? 'up' : 'down'">
                  {{ p.pnl >= 0 ? '+' : '' }}{{ formatMoney(p.pnl) }}
                </td>
                <td :class="p.pnl_pct >= 0 ? 'up' : 'down'">
                  {{ p.pnl_pct >= 0 ? '+' : '' }}{{ (p.pnl_pct * 100).toFixed(2) }}%
                </td>
                <td>
                  <div class="weight-bar-wrap">
                    <div class="weight-bar" :style="{ width: Math.min(p.weight * 100, 100) + '%' }"></div>
                    <span class="weight-text">{{ (p.weight * 100).toFixed(1) }}%</span>
                  </div>
                </td>
                <td>
                  <span v-if="p.trend_status === 'WARNING'" class="status-badge warning">破位预警</span>
                  <span v-else class="status-badge hold">持有</span>
                </td>
              </tr>
              <tr v-if="positionRows.length === 0 && !loading">
                <td colspan="10" class="empty">暂无持仓</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 仓位占比饼图 -->
      <section class="card chart-section" aria-label="仓位占比饼图">
        <h2 class="section-title">仓位占比</h2>
        <div v-if="positions.length === 0" class="chart-empty">暂无持仓数据</div>
        <div v-else ref="chartContainer" class="pie-chart" aria-label="仓位占比饼图"></div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiClient } from '@/api'
import { useAuthStore } from '@/stores/auth'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface Position {
  symbol: string
  name: string
  quantity: number
  cost_price: number
  current_price: number
  market_value: number
  pnl: number
  pnl_pct: number
  weight: number
}

interface PositionRow extends Position {
  trend_status: 'HOLD' | 'WARNING'
}

interface WsPositionUpdate {
  symbol: string
  current_price: number
  market_value: number
  pnl: number
  pnl_pct: number
  weight: number
}

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const authStore = useAuthStore()
const positions = ref<Position[]>([])
const trendStatusMap = ref<Record<string, 'HOLD' | 'WARNING'>>({})
const loading = ref(false)
const wsConnected = ref(false)

// ─── 计算属性 ─────────────────────────────────────────────────────────────────

const positionRows = computed<PositionRow[]>(() =>
  positions.value.map((p) => ({
    ...p,
    trend_status: trendStatusMap.value[p.symbol] ?? 'HOLD',
  }))
)

const totalMarketValue = computed(() =>
  positions.value.reduce((s, p) => s + p.market_value, 0)
)

const totalPnl = computed(() =>
  positions.value.reduce((s, p) => s + p.pnl, 0)
)

const totalPnlPct = computed(() => {
  const cost = positions.value.reduce((s, p) => s + p.cost_price * p.quantity, 0)
  return cost > 0 ? (totalPnl.value / cost) * 100 : 0
})

const warningCount = computed(() =>
  positionRows.value.filter((p) => p.trend_status === 'WARNING').length
)

// ─── 格式化工具 ───────────────────────────────────────────────────────────────

function formatMoney(val: number): string {
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// ─── 获取持仓数据 ─────────────────────────────────────────────────────────────

async function fetchPositions() {
  loading.value = true
  try {
    const res = await apiClient.get<PositionRow[]>('/trade/positions')
    const data = Array.isArray(res.data) ? res.data : []
    // 分离 trend_status 到独立 map，保留 Position 数据
    const newMap: Record<string, 'HOLD' | 'WARNING'> = {}
    const newPositions: Position[] = data.map((item) => {
      newMap[item.symbol] = item.trend_status ?? 'HOLD'
      const { trend_status: _ts, ...pos } = item
      return pos as Position
    })
    positions.value = newPositions
    trendStatusMap.value = newMap
  } catch {
    // 保持现有数据不变
  } finally {
    loading.value = false
  }
}

// ─── WebSocket 实时更新 ───────────────────────────────────────────────────────

let ws: WebSocket | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

function connectWs() {
  const token = localStorage.getItem('access_token')
  const userId = localStorage.getItem('user_id') ?? authStore.user?.id
  if (!token || !userId) {
    startPolling()
    return
  }

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const wsUrl = `${protocol}://localhost:8000/api/v1/ws/${userId}?token=${token}`

  try {
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      wsConnected.value = true
      stopPolling()
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { type: string; data: WsPositionUpdate }
        if (msg.type === 'position_update') {
          applyPositionUpdate(msg.data)
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {
      wsConnected.value = false
    }

    ws.onclose = () => {
      wsConnected.value = false
      ws = null
      // 降级为轮询，5 秒后尝试重连
      startPolling()
      reconnectTimer = setTimeout(() => {
        stopPolling()
        connectWs()
      }, 30_000)
    }
  } catch {
    startPolling()
  }
}

function applyPositionUpdate(update: WsPositionUpdate) {
  const idx = positions.value.findIndex((p) => p.symbol === update.symbol)
  if (idx !== -1) {
    const pos = positions.value[idx]
    positions.value[idx] = {
      ...pos,
      current_price: update.current_price,
      market_value: update.market_value,
      pnl: update.pnl,
      pnl_pct: update.pnl_pct,
      weight: update.weight,
    }
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(fetchPositions, 5_000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ─── ECharts 饼图 ─────────────────────────────────────────────────────────────

const chartContainer = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function initChart() {
  if (!chartContainer.value) return
  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(chartContainer.value, 'dark')
  updateChart()

  // 监听容器 resize
  resizeObserver = new ResizeObserver(() => {
    chartInstance?.resize()
  })
  resizeObserver.observe(chartContainer.value)
}

function updateChart() {
  if (!chartInstance) return
  const data = positions.value
    .filter((p) => p.weight > 0)
    .map((p) => ({
      name: p.symbol + (p.name ? `\n${p.name}` : ''),
      value: parseFloat((p.weight * 100).toFixed(2)),
      itemStyle: trendStatusMap.value[p.symbol] === 'WARNING'
        ? { color: '#f85149', borderColor: '#ff6b6b', borderWidth: 2 }
        : undefined,
    }))

  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params: { name: string; value: number; percent: number }) =>
        `${params.name}<br/>占比：${params.value}%`,
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: '#8b949e', fontSize: 12 },
      formatter: (name: string) => name.split('\n')[0],
    },
    series: [
      {
        name: '仓位占比',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#0d1117',
          borderWidth: 2,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
            color: '#e6edf3',
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        data,
      },
    ],
  })
}

// 监听持仓数据变化，更新图表
watch(
  () => positions.value,
  async () => {
    await nextTick()
    if (positions.value.length > 0) {
      if (!chartInstance && chartContainer.value) {
        initChart()
      } else {
        updateChart()
      }
    }
  },
  { deep: true }
)

// ─── 生命周期 ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await fetchPositions()
  connectWs()
  await nextTick()
  if (positions.value.length > 0 && chartContainer.value) {
    initChart()
  }
})

onUnmounted(() => {
  ws?.close()
  stopPolling()
  if (reconnectTimer) clearTimeout(reconnectTimer)
  resizeObserver?.disconnect()
  chartInstance?.dispose()
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.positions-view { max-width: 1400px; }

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px;
}
.page-title { font-size: 20px; color: #e6edf3; margin: 0; }

.header-actions { display: flex; align-items: center; gap: 12px; }

/* ─── WebSocket 状态指示 ─────────────────────────────────────────────────────── */
.ws-status {
  font-size: 12px; padding: 3px 10px; border-radius: 12px; font-weight: 500;
}
.ws-status.connected { color: #3fb950; background: #1a3a2a; border: 1px solid #2ea04322; }
.ws-status.polling { color: #d29922; background: #3a2a1a; border: 1px solid #d2992222; }

/* ─── 汇总卡片 ───────────────────────────────────────────────────────────────── */
.summary-cards {
  display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap;
}
.summary-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 16px 24px; display: flex; flex-direction: column; gap: 4px; min-width: 150px;
}
.summary-card.warning-count { border-color: #f8514944; background: #1a0d0d; }
.summary-card .label { font-size: 13px; color: #8b949e; }
.summary-card .value { font-size: 22px; font-weight: 600; color: #e6edf3; }

/* ─── 主布局 ─────────────────────────────────────────────────────────────────── */
.main-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .main-layout { grid-template-columns: 1fr; }
}

/* ─── 卡片 ─────────────────────────────────────────────────────────────────── */
.card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px;
}
.section-title { font-size: 16px; color: #e6edf3; margin: 0 0 16px 0; }

/* ─── 表格 ─────────────────────────────────────────────────────────────────── */
.table-wrap { overflow-x: auto; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th,
.data-table td {
  padding: 10px 14px; text-align: left;
  border-bottom: 1px solid #21262d; font-size: 14px;
}
.data-table th { color: #8b949e; font-weight: 500; white-space: nowrap; }
.data-table td { color: #e6edf3; }

/* ─── 持仓行 ─────────────────────────────────────────────────────────────────── */
.position-row { transition: background 0.15s; }
.position-row:hover { background: #1c2128; }

/* 破位预警行高亮 */
.position-row.row-warning {
  background: #1a0d0d;
  border-left: 3px solid #f85149;
}
.position-row.row-warning:hover { background: #220f0f; }
.position-row.row-warning td:first-child { padding-left: 11px; /* compensate border */ }

/* ─── 单元格样式 ─────────────────────────────────────────────────────────────── */
.mono { font-family: 'SF Mono', 'Consolas', monospace; }
.symbol-cell { font-weight: 600; }
.name-cell { color: #8b949e; font-size: 13px; }
.price-cell { color: #e6edf3; }

.up { color: #f85149; }   /* A股：涨红 */
.down { color: #3fb950; } /* A股：跌绿 */

.empty { text-align: center; color: #484f58; padding: 32px; }

/* ─── 预警标签 ───────────────────────────────────────────────────────────────── */
.warning-tag {
  display: inline-block; margin-left: 4px; color: #f85149; font-size: 12px;
  animation: blink 1.5s ease-in-out infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* ─── 状态徽章 ───────────────────────────────────────────────────────────────── */
.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 500; white-space: nowrap;
}
.status-badge.warning { background: #3a1a1a; color: #f85149; border: 1px solid #f8514944; }
.status-badge.hold { background: #1a2a3a; color: #58a6ff; border: 1px solid #58a6ff22; }

/* ─── 仓位进度条 ─────────────────────────────────────────────────────────────── */
.weight-bar-wrap {
  display: flex; align-items: center; gap: 8px; min-width: 100px;
}
.weight-bar {
  height: 6px; background: #1f6feb; border-radius: 3px;
  transition: width 0.3s ease; min-width: 2px;
}
.weight-text { font-size: 13px; color: #e6edf3; white-space: nowrap; }

/* ─── 饼图 ─────────────────────────────────────────────────────────────────── */
.chart-section { position: sticky; top: 16px; }
.pie-chart { width: 100%; height: 320px; }
.chart-empty {
  height: 320px; display: flex; align-items: center; justify-content: center;
  color: #484f58; font-size: 14px;
}

/* ─── 按钮 ─────────────────────────────────────────────────────────────────── */
.btn-outline {
  display: flex; align-items: center; gap: 6px;
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn-outline:hover { color: #e6edf3; border-color: #8b949e; }
.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }

.refresh-icon { display: inline-block; font-size: 16px; }
.refresh-icon.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ─── 加载 ─────────────────────────────────────────────────────────────────── */
.loading-text { color: #8b949e; font-size: 14px; padding: 16px 0; }
</style>
