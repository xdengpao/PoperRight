<template>
  <div class="operation-detail">
    <div class="detail-header">
      <button class="btn-back" @click="$router.push('/operations')">&larr; 返回</button>
      <h2>{{ planDetail?.name || '加载中...' }}</h2>
      <span v-if="planDetail" class="status-badge" :class="planStatus.toLowerCase()">
        {{ statusLabel(planStatus) }}
      </span>
    </div>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.badge" class="tab-badge">{{ tab.badge }}</span>
      </button>
    </div>

    <div class="tab-content">
      <!-- 候选股 Tab -->
      <div v-if="activeTab === 'candidates'" class="candidates-tab">
        <div v-if="store.candidates.length === 0" class="empty-tab">今日暂无候选股</div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>股票代码</th>
              <th>趋势评分</th>
              <th>参考买入价</th>
              <th>信号强度</th>
              <th>板块排名</th>
              <th>风控状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in store.candidates" :key="c.id" :class="{ skipped: c.status === 'SKIPPED' }">
              <td>{{ c.symbol }}</td>
              <td>{{ c.trend_score?.toFixed(1) ?? '-' }}</td>
              <td>{{ c.ref_buy_price?.toFixed(2) ?? '-' }}</td>
              <td><span class="signal-badge" :class="c.signal_strength?.toLowerCase()">{{ c.signal_strength }}</span></td>
              <td>{{ c.sector_rank ?? '-' }}</td>
              <td><span :class="riskClass(c.risk_status)">{{ c.risk_status }}</span></td>
              <td>
                <button v-if="c.status === 'PENDING'" class="btn-sm btn-buy" @click="handleBuy(c)">买入</button>
                <button v-if="c.status === 'PENDING'" class="btn-sm" @click="store.skipCandidate(planId, c.id)">跳过</button>
                <span v-else class="status-text">{{ c.status }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 持仓 Tab -->
      <div v-if="activeTab === 'positions'" class="positions-tab">
        <div v-if="store.positions.length === 0" class="empty-tab">暂无持仓</div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>股票代码</th>
              <th>成本价</th>
              <th>现价</th>
              <th>盈亏%</th>
              <th>持仓天数</th>
              <th>止损阶段</th>
              <th>止损价</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in store.positions" :key="p.id">
              <td>{{ p.symbol }}</td>
              <td>{{ p.cost_price.toFixed(2) }}</td>
              <td>{{ p.current_price?.toFixed(2) ?? '-' }}</td>
              <td :class="pnlClass(p.pnl_pct)">{{ p.pnl_pct != null ? (p.pnl_pct * 100).toFixed(2) + '%' : '-' }}</td>
              <td>{{ p.holding_days }}</td>
              <td><span class="stage-badge" :class="`stage-${p.stop_stage}`">{{ stageLabel(p.stop_stage) }}</span></td>
              <td>{{ p.stop_price.toFixed(2) }}</td>
              <td>{{ p.status }}</td>
              <td>
                <button v-if="p.status === 'PENDING_SELL' || p.status === 'HOLDING'" class="btn-sm btn-sell" @click="handleSell(p)">卖出</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 买入记录 Tab -->
      <div v-if="activeTab === 'records'" class="records-tab">
        <div v-if="store.buyRecords.length === 0" class="empty-tab">暂无买入记录</div>
        <table v-else class="data-table">
          <thead><tr><th>股票代码</th><th>买入价</th><th>数量</th><th>时间</th><th>趋势评分</th><th>初始止损</th><th>类型</th></tr></thead>
          <tbody>
            <tr v-for="r in store.buyRecords" :key="r.id">
              <td>{{ r.symbol }}</td>
              <td>{{ r.buy_price.toFixed(2) }}</td>
              <td>{{ r.buy_quantity }}</td>
              <td>{{ formatTime(r.buy_time) }}</td>
              <td>{{ r.trend_score_at_buy?.toFixed(1) ?? '-' }}</td>
              <td>{{ r.initial_stop_price.toFixed(2) }}</td>
              <td>{{ r.is_manual ? '补录' : '系统' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 复盘 Tab -->
      <div v-if="activeTab === 'checklist'" class="checklist-tab">
        <div class="checklist-summary" :class="store.checklistLevel.toLowerCase()">
          今日复盘: {{ store.checklistLevel }}
        </div>
        <div v-if="store.checklist.length === 0" class="empty-tab">今日暂无复盘数据</div>
        <div v-else class="checklist-items">
          <div v-for="(item, idx) in store.checklist" :key="idx" class="checklist-item" :class="item.result.toLowerCase()">
            <span class="check-dimension">{{ item.dimension }}</span>
            <span class="check-symbol">{{ item.symbol || '全局' }}</span>
            <span class="check-result" :class="item.result.toLowerCase()">{{ item.result }}</span>
            <span class="check-message">{{ item.message }}</span>
            <span class="check-action">{{ item.action }}</span>
          </div>
        </div>
      </div>

      <!-- 设置 Tab -->
      <div v-if="activeTab === 'settings'" class="settings-tab">
        <p class="settings-hint">交易计划参数配置（候选股筛选规则、止损配置、市场环境适配）</p>
        <pre v-if="planDetail" class="config-preview">{{ JSON.stringify(planDetail, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiClient } from '@/api'
import { useOperationsStore, type CandidateStock, type PlanPosition } from '@/stores/operations'

const route = useRoute()
const store = useOperationsStore()
const planId = route.params.planId as string
const activeTab = ref('candidates')
interface OperationPlanDetail {
  name?: string
  status: string
  [key: string]: unknown
}

const planDetail = ref<OperationPlanDetail | null>(null)

const tabs = computed(() => [
  { key: 'candidates', label: '候选股', badge: store.candidates.length || undefined },
  { key: 'positions', label: '持仓', badge: store.positions.length || undefined },
  { key: 'records', label: '买入记录' },
  { key: 'checklist', label: '复盘' },
  { key: 'settings', label: '设置' },
])

const planStatus = computed(() => planDetail.value?.status ?? '')

onMounted(async () => {
  const { data } = await apiClient.get(`/operations/plans/${planId}`)
  planDetail.value = data
  store.fetchCandidates(planId)
  store.fetchPositions(planId)
  store.fetchBuyRecords(planId)
  store.fetchChecklist(planId)
})

function statusLabel(status: string) {
  const map: Record<string, string> = { ACTIVE: '运行中', PAUSED: '已暂停', ARCHIVED: '已归档' }
  return map[status] || status
}

function stageLabel(stage: number) {
  const labels: Record<number, string> = { 1: '固定止损', 2: '移动止盈', 3: '收紧止盈', 4: '长期持仓', 5: '趋势破位' }
  return labels[stage] || `阶段${stage}`
}

function riskClass(status: string) {
  if (status === 'NORMAL') return 'risk-normal'
  if (status === 'HIGH_RISK') return 'risk-high'
  return 'risk-warn'
}

function pnlClass(pct: number | null) {
  if (pct == null) return ''
  return pct >= 0 ? 'pnl-positive' : 'pnl-negative'
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function handleBuy(c: CandidateStock) {
  const qty = prompt(`买入 ${c.symbol}，请输入数量（股）:`)
  if (!qty || isNaN(Number(qty))) return
  await store.executeBuy(planId, {
    candidate_id: c.id,
    symbol: c.symbol,
    buy_price: c.ref_buy_price || 0,
    buy_quantity: Number(qty),
    trend_score: c.trend_score || undefined,
    sector_rank: c.sector_rank || undefined,
  })
  store.fetchCandidates(planId)
  store.fetchPositions(planId)
}

async function handleSell(p: PlanPosition) {
  const price = prompt(`卖出 ${p.symbol}，请输入卖出价格:`)
  if (!price || isNaN(Number(price))) return
  await store.confirmSell(planId, p.id, Number(price))
  store.fetchPositions(planId)
}
</script>

<style scoped>
.operation-detail { padding: 24px; }
.detail-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.detail-header h2 { margin: 0; }
.btn-back { background: none; border: none; font-size: 1rem; cursor: pointer; color: #1976d2; }
.status-badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.status-badge.active { background: #e8f5e9; color: #2e7d32; }
.status-badge.paused { background: #fff3e0; color: #e65100; }
.tabs { display: flex; gap: 4px; border-bottom: 2px solid #e0e0e0; margin-bottom: 16px; }
.tab-btn { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 0.95rem; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab-btn.active { border-bottom-color: #1976d2; color: #1976d2; font-weight: 600; }
.tab-badge { background: #ef5350; color: #fff; font-size: 0.7rem; padding: 1px 6px; border-radius: 10px; margin-left: 4px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th { text-align: left; padding: 8px; border-bottom: 2px solid #e0e0e0; color: #666; font-weight: 500; }
.data-table td { padding: 8px; border-bottom: 1px solid #f0f0f0; }
.data-table tr.skipped { opacity: 0.5; }
.signal-badge { padding: 2px 6px; border-radius: 3px; font-size: 0.8rem; }
.signal-badge.strong { background: #e8f5e9; color: #2e7d32; }
.signal-badge.medium { background: #fff3e0; color: #e65100; }
.signal-badge.weak { background: #fce4ec; color: #c62828; }
.risk-normal { color: #2e7d32; }
.risk-high { color: #c62828; }
.risk-warn { color: #e65100; }
.pnl-positive { color: #c62828; }
.pnl-negative { color: #2e7d32; }
.stage-badge { padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
.stage-1 { background: #f5f5f5; color: #666; }
.stage-2 { background: #e8f5e9; color: #2e7d32; }
.stage-3 { background: #e3f2fd; color: #1565c0; }
.stage-4 { background: #fff3e0; color: #e65100; }
.stage-5 { background: #fce4ec; color: #c62828; }
.btn-sm { font-size: 0.8rem; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; background: #fff; }
.btn-buy { color: #c62828; border-color: #c62828; }
.btn-sell { color: #2e7d32; border-color: #2e7d32; }
.empty-tab { text-align: center; padding: 32px; color: #999; }
.checklist-summary { padding: 12px; border-radius: 4px; margin-bottom: 12px; font-weight: 600; }
.checklist-summary.ok { background: #e8f5e9; color: #2e7d32; }
.checklist-summary.warning { background: #fff3e0; color: #e65100; }
.checklist-summary.danger { background: #fce4ec; color: #c62828; }
.checklist-items { display: flex; flex-direction: column; gap: 8px; }
.checklist-item { display: grid; grid-template-columns: 100px 80px 70px 1fr 200px; gap: 8px; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px; align-items: center; font-size: 0.9rem; }
.checklist-item.warning { border-left: 3px solid #ff9800; }
.checklist-item.danger { border-left: 3px solid #f44336; }
.checklist-item.ok { border-left: 3px solid #4caf50; }
.check-result.ok { color: #2e7d32; }
.check-result.warning { color: #e65100; }
.check-result.danger { color: #c62828; }
.check-action { color: #666; font-size: 0.85rem; }
.settings-hint { color: #666; }
.config-preview { background: #f5f5f5; padding: 16px; border-radius: 4px; font-size: 0.85rem; overflow-x: auto; }
</style>
