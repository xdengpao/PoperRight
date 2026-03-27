<template>
  <div class="risk-view">
    <h1 class="page-title">风险控制</h1>

    <!-- 止损止盈配置 -->
    <section class="card" aria-label="止损止盈配置">
      <h2 class="section-title">止损止盈参数</h2>
      <div class="config-grid">
        <div class="config-item">
          <label for="stop-loss-type">止损方式</label>
          <select id="stop-loss-type" v-model="stopLoss.type" class="input">
            <option value="fixed">固定比例止损</option>
            <option value="trailing">移动止损</option>
            <option value="trend">趋势止损</option>
          </select>
        </div>
        <div class="config-item" v-if="stopLoss.type === 'fixed'">
          <label for="stop-loss-pct">止损比例</label>
          <select id="stop-loss-pct" v-model.number="stopLoss.fixedPct" class="input">
            <option :value="5">5%</option>
            <option :value="8">8%</option>
            <option :value="10">10%</option>
          </select>
        </div>
        <div class="config-item" v-if="stopLoss.type === 'trailing'">
          <label for="trailing-pct">回撤比例</label>
          <select id="trailing-pct" v-model.number="stopLoss.trailingPct" class="input">
            <option :value="3">3%</option>
            <option :value="5">5%</option>
          </select>
        </div>
        <div class="config-item" v-if="stopLoss.type === 'trend'">
          <label for="trend-ma">关键均线</label>
          <select id="trend-ma" v-model.number="stopLoss.trendMa" class="input">
            <option :value="5">5日均线</option>
            <option :value="10">10日均线</option>
            <option :value="20">20日均线</option>
            <option :value="60">60日均线</option>
          </select>
        </div>
        <div class="config-item">
          <label for="take-profit-pct">止盈比例 (%)</label>
          <input id="take-profit-pct" v-model.number="stopLoss.takeProfitPct" type="number" min="1" max="100" class="input" />
        </div>
      </div>
      <button class="btn save-btn" @click="saveStopLoss">保存止损止盈配置</button>
    </section>

    <!-- 仓位限制 -->
    <section class="card" aria-label="仓位限制配置">
      <h2 class="section-title">仓位限制</h2>
      <div class="config-grid">
        <div class="config-item">
          <label for="stock-limit">单只个股仓位上限 (%)</label>
          <input id="stock-limit" v-model.number="positionLimits.stockMax" type="number" min="1" max="100" class="input" />
          <span class="hint">默认 15%，超出将拒绝买入</span>
        </div>
        <div class="config-item">
          <label for="sector-limit">单一板块仓位上限 (%)</label>
          <input id="sector-limit" v-model.number="positionLimits.sectorMax" type="number" min="1" max="100" class="input" />
          <span class="hint">默认 30%，超出将拒绝买入</span>
        </div>
      </div>
      <button class="btn save-btn" @click="savePositionLimits">保存仓位限制</button>
    </section>

    <!-- 黑白名单 -->
    <section class="card" aria-label="黑白名单管理">
      <h2 class="section-title">黑白名单管理</h2>
      <div class="list-tabs">
        <button :class="['tab', activeList === 'BLACK' && 'active']" @click="activeList = 'BLACK'">黑名单</button>
        <button :class="['tab', activeList === 'WHITE' && 'active']" @click="activeList = 'WHITE'">白名单</button>
      </div>

      <div class="add-row">
        <label :for="`add-${activeList}`" class="sr-only">添加股票代码</label>
        <input :id="`add-${activeList}`" v-model="newSymbol" class="input" placeholder="输入股票代码" @keyup.enter="addToList" />
        <label for="add-reason" class="sr-only">原因</label>
        <input id="add-reason" v-model="newReason" class="input" placeholder="原因（可选）" />
        <button class="btn" @click="addToList">添加</button>
      </div>

      <table class="data-table" :aria-label="activeList === 'BLACK' ? '黑名单' : '白名单'">
        <thead>
          <tr>
            <th scope="col">股票代码</th>
            <th scope="col">原因</th>
            <th scope="col">添加时间</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in currentList" :key="item.symbol">
            <td class="mono">{{ item.symbol }}</td>
            <td>{{ item.reason || '—' }}</td>
            <td>{{ item.created_at?.slice(0, 10) ?? '—' }}</td>
            <td><button class="btn-sm danger" @click="removeFromList(item.symbol)">移除</button></td>
          </tr>
          <tr v-if="currentList.length === 0">
            <td colspan="4" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { apiClient } from '@/api'

// 止损止盈
const stopLoss = reactive({
  type: 'fixed' as 'fixed' | 'trailing' | 'trend',
  fixedPct: 8,
  trailingPct: 5,
  trendMa: 20,
  takeProfitPct: 15,
})

async function saveStopLoss() {
  try {
    await apiClient.post('/risk/stop-loss-config', stopLoss)
  } catch { /* handle error */ }
}

// 仓位限制
const positionLimits = reactive({ stockMax: 15, sectorMax: 30 })

async function savePositionLimits() {
  try {
    await apiClient.post('/risk/position-limits', positionLimits)
  } catch { /* handle error */ }
}

// 黑白名单
interface ListItem { symbol: string; reason: string; created_at: string }
const activeList = ref<'BLACK' | 'WHITE'>('BLACK')
const blacklist = ref<ListItem[]>([])
const whitelist = ref<ListItem[]>([])
const newSymbol = ref('')
const newReason = ref('')

const currentList = computed(() => activeList.value === 'BLACK' ? blacklist.value : whitelist.value)

async function fetchLists() {
  try {
    const [bRes, wRes] = await Promise.all([
      apiClient.get<ListItem[]>('/blacklist'),
      apiClient.get<ListItem[]>('/whitelist'),
    ])
    blacklist.value = bRes.data
    whitelist.value = wRes.data
  } catch { /* handle error */ }
}

async function addToList() {
  if (!newSymbol.value.trim()) return
  const endpoint = activeList.value === 'BLACK' ? '/blacklist' : '/whitelist'
  try {
    await apiClient.post(endpoint, { symbol: newSymbol.value, reason: newReason.value })
    newSymbol.value = ''
    newReason.value = ''
    await fetchLists()
  } catch { /* handle error */ }
}

async function removeFromList(symbol: string) {
  const endpoint = activeList.value === 'BLACK' ? '/blacklist' : '/whitelist'
  try {
    await apiClient.delete(`${endpoint}/${symbol}`)
    await fetchLists()
  } catch { /* handle error */ }
}

onMounted(() => { fetchLists() })
</script>

<style scoped>
.risk-view { max-width: 1000px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.hint { font-size: 11px; color: #484f58; }

.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover { background: #2ea043; }
.save-btn { margin-top: 16px; }

.list-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }

.add-row { display: flex; gap: 8px; margin-bottom: 12px; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', monospace; }
.empty { text-align: center; color: #484f58; padding: 24px; }

.btn-sm { background: none; border: 1px solid #30363d; color: #8b949e; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-sm.danger:hover { color: #f85149; border-color: #f85149; }
</style>
