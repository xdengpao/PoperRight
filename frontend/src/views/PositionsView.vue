<template>
  <div class="positions-view">
    <h1 class="page-title">持仓管理</h1>

    <!-- 持仓汇总 -->
    <section class="summary-cards" aria-label="持仓汇总">
      <div class="summary-card">
        <span class="label">总市值</span>
        <span class="value">{{ totalMarketValue.toFixed(2) }}</span>
      </div>
      <div class="summary-card">
        <span class="label">总盈亏</span>
        <span class="value" :class="totalPnl >= 0 ? 'up' : 'down'">
          {{ totalPnl >= 0 ? '+' : '' }}{{ totalPnl.toFixed(2) }}
        </span>
      </div>
      <div class="summary-card">
        <span class="label">持仓数量</span>
        <span class="value">{{ positions.length }}</span>
      </div>
    </section>

    <div class="toolbar">
      <button class="btn btn-outline" @click="fetchPositions" :disabled="loading">
        {{ loading ? '刷新中...' : '刷新持仓' }}
      </button>
    </div>

    <!-- 持仓表格 -->
    <table class="data-table" aria-label="持仓明细">
      <thead>
        <tr>
          <th scope="col">股票代码</th>
          <th scope="col">持仓股数</th>
          <th scope="col">成本价</th>
          <th scope="col">当前价</th>
          <th scope="col">市值</th>
          <th scope="col">盈亏金额</th>
          <th scope="col">盈亏比例</th>
          <th scope="col">仓位占比</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in positions" :key="p.symbol">
          <td class="mono">{{ p.symbol }}</td>
          <td>{{ p.quantity }}</td>
          <td class="mono">{{ p.cost_price.toFixed(2) }}</td>
          <td class="mono">{{ p.current_price.toFixed(2) }}</td>
          <td class="mono">{{ p.market_value.toFixed(2) }}</td>
          <td :class="p.pnl >= 0 ? 'up' : 'down'" class="mono">
            {{ p.pnl >= 0 ? '+' : '' }}{{ p.pnl.toFixed(2) }}
          </td>
          <td :class="p.pnl_pct >= 0 ? 'up' : 'down'">
            {{ p.pnl_pct >= 0 ? '+' : '' }}{{ (p.pnl_pct * 100).toFixed(2) }}%
          </td>
          <td>{{ (p.weight * 100).toFixed(1) }}%</td>
        </tr>
        <tr v-if="positions.length === 0">
          <td colspan="8" class="empty">暂无持仓</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiClient } from '@/api'

interface Position {
  symbol: string; quantity: number; cost_price: number; current_price: number
  market_value: number; pnl: number; pnl_pct: number; weight: number
}

const positions = ref<Position[]>([])
const loading = ref(false)

const totalMarketValue = computed(() => positions.value.reduce((s, p) => s + p.market_value, 0))
const totalPnl = computed(() => positions.value.reduce((s, p) => s + p.pnl, 0))

async function fetchPositions() {
  loading.value = true
  try {
    const res = await apiClient.get<Position[]>('/trade/positions')
    positions.value = res.data
  } catch { /* handle error */ }
  loading.value = false
}

// WebSocket 实时盈亏更新
let ws: WebSocket | null = null

function connectWs() {
  const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws/positions`
  try {
    ws = new WebSocket(wsUrl)
    ws.onmessage = (event) => {
      try {
        const updates = JSON.parse(event.data) as Partial<Position>[]
        for (const u of updates) {
          const pos = positions.value.find((p) => p.symbol === u.symbol)
          if (pos) Object.assign(pos, u)
        }
      } catch { /* ignore */ }
    }
    ws.onclose = () => { setTimeout(connectWs, 5000) }
  } catch { /* WebSocket not available */ }
}

onMounted(() => {
  fetchPositions()
  connectWs()
})

onUnmounted(() => { ws?.close() })
</script>

<style scoped>
.positions-view { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }

.summary-cards { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.summary-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 16px 24px; display: flex; flex-direction: column; gap: 4px; min-width: 160px;
}
.summary-card .label { font-size: 13px; color: #8b949e; }
.summary-card .value { font-size: 22px; font-weight: 600; color: #e6edf3; }

.toolbar { margin-bottom: 12px; }

.data-table { width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', monospace; }
.up { color: #f85149; }
.down { color: #3fb950; }
.empty { text-align: center; color: #484f58; padding: 24px; }

.btn-outline {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn-outline:hover { color: #e6edf3; border-color: #8b949e; }
.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
