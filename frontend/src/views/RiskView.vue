<template>
  <div class="risk-view">
    <h1 class="page-title">风险控制</h1>

    <!-- 大盘风控状态卡片 -->
    <section class="card" aria-label="大盘风控状态">
      <div class="section-header">
        <h2 class="section-title">大盘风控状态</h2>
        <button class="btn-icon" @click="fetchRiskOverview" :disabled="overviewLoading" aria-label="刷新风控状态">
          <span :class="['refresh-icon', overviewLoading && 'spinning']">↻</span>
        </button>
      </div>

      <div v-if="overviewLoading" class="loading-text">加载中...</div>
      <div v-else-if="riskOverview" class="risk-overview">
        <!-- 风控级别徽章 -->
        <div class="risk-level-badge" :class="riskLevelClass">
          <span class="risk-level-dot"></span>
          <span class="risk-level-text">{{ riskLevelLabel }}</span>
        </div>

        <!-- 指数均线关系 -->
        <div class="ma-grid">
          <div class="ma-item">
            <span class="ma-label">上证 / MA20</span>
            <span class="ma-status" :class="riskOverview.sh_above_ma20 ? 'above' : 'below'">
              {{ riskOverview.sh_above_ma20 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item">
            <span class="ma-label">上证 / MA60</span>
            <span class="ma-status" :class="riskOverview.sh_above_ma60 ? 'above' : 'below'">
              {{ riskOverview.sh_above_ma60 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item">
            <span class="ma-label">创业板 / MA20</span>
            <span class="ma-status" :class="riskOverview.cyb_above_ma20 ? 'above' : 'below'">
              {{ riskOverview.cyb_above_ma20 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item">
            <span class="ma-label">创业板 / MA60</span>
            <span class="ma-status" :class="riskOverview.cyb_above_ma60 ? 'above' : 'below'">
              {{ riskOverview.cyb_above_ma60 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item threshold-item">
            <span class="ma-label">当前趋势阈值</span>
            <span class="threshold-value">{{ riskOverview.current_threshold }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无风控数据</div>
    </section>

    <!-- 止损止盈参数配置 -->
    <section class="card" aria-label="止损止盈参数配置">
      <h2 class="section-title">止损止盈参数</h2>
      <div class="config-grid">
        <div class="config-item">
          <label for="fixed-stop-loss">固定止损比例 (%)</label>
          <input
            id="fixed-stop-loss"
            v-model.number="stopConfig.fixed_stop_loss"
            type="number"
            min="1"
            max="50"
            step="0.5"
            class="input"
          />
          <span class="hint">触发固定止损的亏损比例</span>
        </div>
        <div class="config-item">
          <label for="trailing-stop">移动止损回撤比例 (%)</label>
          <input
            id="trailing-stop"
            v-model.number="stopConfig.trailing_stop"
            type="number"
            min="1"
            max="30"
            step="0.5"
            class="input"
          />
          <span class="hint">从最高点回撤触发移动止损</span>
        </div>
        <div class="config-item">
          <label for="trend-stop-ma">趋势止损均线周期</label>
          <select id="trend-stop-ma" v-model.number="stopConfig.trend_stop_ma" class="input">
            <option :value="5">5 日均线</option>
            <option :value="10">10 日均线</option>
            <option :value="20">20 日均线</option>
            <option :value="60">60 日均线</option>
          </select>
          <span class="hint">收盘价跌破该均线触发趋势止损</span>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn save-btn" @click="saveStopConfig" :disabled="stopConfigSaving">
          {{ stopConfigSaving ? '保存中...' : '保存止损止盈配置' }}
        </button>
        <span v-if="stopConfigMsg" class="save-msg" :class="stopConfigMsgType">{{ stopConfigMsg }}</span>
      </div>
    </section>

    <!-- 黑白名单管理 -->
    <section class="card" aria-label="黑白名单管理">
      <h2 class="section-title">黑白名单管理</h2>
      <div class="list-tabs">
        <button
          :class="['tab', activeList === 'BLACK' && 'active']"
          @click="switchList('BLACK')"
        >黑名单</button>
        <button
          :class="['tab', activeList === 'WHITE' && 'active']"
          @click="switchList('WHITE')"
        >白名单</button>
      </div>

      <div class="add-row">
        <label :for="`add-symbol-${activeList}`" class="sr-only">添加股票代码</label>
        <input
          :id="`add-symbol-${activeList}`"
          v-model="newSymbol"
          class="input"
          placeholder="股票代码，如 000001"
          @keyup.enter="addToList"
        />
        <label for="add-reason" class="sr-only">原因</label>
        <input
          id="add-reason"
          v-model="newReason"
          class="input"
          placeholder="原因（可选）"
          @keyup.enter="addToList"
        />
        <button class="btn" @click="addToList" :disabled="listLoading">添加</button>
      </div>

      <div v-if="listLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" :aria-label="activeList === 'BLACK' ? '黑名单列表' : '白名单列表'">
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
            <td>
              <button class="btn-sm danger" @click="removeFromList(item.symbol)">移除</button>
            </td>
          </tr>
          <tr v-if="currentList.length === 0">
            <td colspan="4" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>

      <div v-if="listTotal > currentList.length" class="pagination-hint">
        共 {{ listTotal }} 条，当前显示 {{ currentList.length }} 条
      </div>
    </section>

    <!-- 仓位风控预警 -->
    <section class="card" aria-label="仓位风控预警">
      <div class="section-header">
        <h2 class="section-title">仓位风控预警</h2>
        <button class="btn-icon" @click="fetchPositionWarnings" aria-label="刷新预警">
          <span class="refresh-icon">↻</span>
        </button>
      </div>

      <div v-if="warningsLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" aria-label="仓位风控预警列表">
        <thead>
          <tr>
            <th scope="col">股票代码</th>
            <th scope="col">预警类型</th>
            <th scope="col">当前值</th>
            <th scope="col">阈值</th>
            <th scope="col">时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(w, i) in positionWarnings" :key="i" :class="['warning-row', w.level]">
            <td class="mono">{{ w.symbol }}</td>
            <td>
              <span class="warning-badge" :class="w.level">{{ w.type }}</span>
            </td>
            <td>{{ w.current_value }}</td>
            <td>{{ w.threshold }}</td>
            <td>{{ w.time?.slice(0, 16) ?? '—' }}</td>
          </tr>
          <tr v-if="positionWarnings.length === 0">
            <td colspan="5" class="empty">暂无风控预警</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { apiClient } from '@/api'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface RiskOverview {
  market_risk_level: 'NORMAL' | 'ELEVATED' | 'SUSPENDED'
  sh_above_ma20: boolean
  sh_above_ma60: boolean
  cyb_above_ma20: boolean
  cyb_above_ma60: boolean
  current_threshold: number
}

interface StopConfig {
  fixed_stop_loss: number
  trailing_stop: number
  trend_stop_ma: number
}

interface ListItem {
  symbol: string
  reason: string
  created_at: string
}

interface PositionWarning {
  symbol: string
  type: string
  level: 'danger' | 'warning' | 'info'
  current_value: string
  threshold: string
  time: string
}

// ─── 大盘风控状态 ─────────────────────────────────────────────────────────────

const riskOverview = ref<RiskOverview | null>(null)
const overviewLoading = ref(false)

const riskLevelClass = computed(() => {
  const level = riskOverview.value?.market_risk_level
  if (level === 'SUSPENDED') return 'level-suspended'
  if (level === 'ELEVATED') return 'level-elevated'
  return 'level-normal'
})

const riskLevelLabel = computed(() => {
  const level = riskOverview.value?.market_risk_level
  if (level === 'SUSPENDED') return '暂停交易'
  if (level === 'ELEVATED') return '风险提升'
  return '正常'
})

async function fetchRiskOverview() {
  overviewLoading.value = true
  try {
    const res = await apiClient.get<RiskOverview>('/risk/overview')
    riskOverview.value = res.data
  } catch {
    // API 暂不可用时使用默认值
    riskOverview.value = {
      market_risk_level: 'NORMAL',
      sh_above_ma20: true,
      sh_above_ma60: true,
      cyb_above_ma20: false,
      cyb_above_ma60: false,
      current_threshold: 60,
    }
  } finally {
    overviewLoading.value = false
  }
}

// ─── 止损止盈配置 ─────────────────────────────────────────────────────────────

const stopConfig = reactive<StopConfig>({
  fixed_stop_loss: 8,
  trailing_stop: 5,
  trend_stop_ma: 20,
})

const stopConfigSaving = ref(false)
const stopConfigMsg = ref('')
const stopConfigMsgType = ref<'success' | 'error'>('success')

async function saveStopConfig() {
  stopConfigSaving.value = true
  stopConfigMsg.value = ''
  try {
    await apiClient.post('/risk/stop-config', stopConfig)
    stopConfigMsg.value = '保存成功'
    stopConfigMsgType.value = 'success'
  } catch {
    stopConfigMsg.value = '保存失败，请重试'
    stopConfigMsgType.value = 'error'
  } finally {
    stopConfigSaving.value = false
    setTimeout(() => { stopConfigMsg.value = '' }, 3000)
  }
}

// ─── 黑白名单管理 ─────────────────────────────────────────────────────────────

const activeList = ref<'BLACK' | 'WHITE'>('BLACK')
const blacklist = ref<ListItem[]>([])
const whitelist = ref<ListItem[]>([])
const listLoading = ref(false)
const listTotal = ref(0)
const newSymbol = ref('')
const newReason = ref('')

const currentList = computed(() =>
  activeList.value === 'BLACK' ? blacklist.value : whitelist.value
)

async function fetchLists() {
  listLoading.value = true
  try {
    const [bRes, wRes] = await Promise.all([
      apiClient.get<{ items: ListItem[]; total: number }>('/blacklist'),
      apiClient.get<{ items: ListItem[]; total: number }>('/whitelist'),
    ])
    // 兼容数组和分页对象两种响应格式
    blacklist.value = Array.isArray(bRes.data) ? bRes.data : (bRes.data.items ?? [])
    whitelist.value = Array.isArray(wRes.data) ? wRes.data : (wRes.data.items ?? [])
    listTotal.value = Array.isArray(bRes.data) ? bRes.data.length : (bRes.data.total ?? 0)
  } catch {
    /* API 暂不可用 */
  } finally {
    listLoading.value = false
  }
}

function switchList(type: 'BLACK' | 'WHITE') {
  activeList.value = type
  listTotal.value = currentList.value.length
}

async function addToList() {
  const sym = newSymbol.value.trim().toUpperCase()
  if (!sym) return
  const endpoint = activeList.value === 'BLACK' ? '/blacklist' : '/whitelist'
  try {
    await apiClient.post(endpoint, { symbol: sym, reason: newReason.value || null })
    newSymbol.value = ''
    newReason.value = ''
    await fetchLists()
  } catch {
    /* handle error */
  }
}

async function removeFromList(symbol: string) {
  const endpoint = activeList.value === 'BLACK' ? '/blacklist' : '/whitelist'
  try {
    await apiClient.delete(`${endpoint}/${symbol}`)
    await fetchLists()
  } catch {
    /* handle error */
  }
}

// ─── 仓位风控预警 ─────────────────────────────────────────────────────────────

const positionWarnings = ref<PositionWarning[]>([])
const warningsLoading = ref(false)

async function fetchPositionWarnings() {
  warningsLoading.value = true
  try {
    const res = await apiClient.get<PositionWarning[]>('/risk/position-warnings')
    positionWarnings.value = res.data
  } catch {
    positionWarnings.value = []
  } finally {
    warningsLoading.value = false
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

async function loadStopConfig() {
  try {
    const res = await apiClient.get<StopConfig>('/risk/stop-config')
    Object.assign(stopConfig, res.data)
  } catch {
    // 加载失败时保留前端默认值
  }
}

onMounted(() => {
  fetchRiskOverview()
  loadStopConfig()
  fetchLists()
  fetchPositionWarnings()
})
</script>

<style scoped>
.risk-view { max-width: 1000px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }

.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-header .section-title { margin-bottom: 0; }

.btn-icon {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  width: 30px; height: 30px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.btn-icon:hover { color: #e6edf3; border-color: #58a6ff; }
.btn-icon:disabled { opacity: 0.5; cursor: not-allowed; }

.refresh-icon { display: inline-block; }
.refresh-icon.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 风控状态 */
.risk-overview { display: flex; flex-direction: column; gap: 16px; }

.risk-level-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: 600;
  width: fit-content;
}
.risk-level-dot { width: 8px; height: 8px; border-radius: 50%; }
.level-normal { background: #1a3a2a; color: #3fb950; border: 1px solid #2ea04322; }
.level-normal .risk-level-dot { background: #3fb950; }
.level-elevated { background: #3a2a1a; color: #d29922; border: 1px solid #d2992222; }
.level-elevated .risk-level-dot { background: #d29922; }
.level-suspended { background: #3a1a1a; color: #f85149; border: 1px solid #f8514922; }
.level-suspended .risk-level-dot { background: #f85149; }

.ma-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.ma-item {
  background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
  padding: 10px 16px; display: flex; flex-direction: column; gap: 4px; min-width: 140px;
}
.ma-label { font-size: 12px; color: #8b949e; }
.ma-status { font-size: 14px; font-weight: 600; }
.ma-status.above { color: #3fb950; }
.ma-status.below { color: #f85149; }
.threshold-item { min-width: 160px; }
.threshold-value { font-size: 20px; font-weight: 700; color: #58a6ff; }

/* 止损止盈配置 */
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.hint { font-size: 11px; color: #484f58; }

.form-actions { display: flex; align-items: center; gap: 12px; margin-top: 16px; }
.save-msg { font-size: 13px; }
.save-msg.success { color: #3fb950; }
.save-msg.error { color: #f85149; }

/* 通用输入 */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.input:focus { outline: none; border-color: #58a6ff; }
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover:not(:disabled) { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.save-btn { align-self: flex-start; }

/* 黑白名单 */
.list-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.tab:hover:not(.active) { color: #e6edf3; }

.add-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.pagination-hint { font-size: 12px; color: #484f58; margin-top: 8px; text-align: right; }

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; }
.empty { text-align: center; color: #484f58; padding: 24px; }

.btn-sm {
  background: none; border: 1px solid #30363d; color: #8b949e;
  padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-sm.danger:hover { color: #f85149; border-color: #f85149; }

/* 预警 */
.warning-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;
}
.warning-badge.danger { background: #3a1a1a; color: #f85149; }
.warning-badge.warning { background: #3a2a1a; color: #d29922; }
.warning-badge.info { background: #1a2a3a; color: #58a6ff; }

.loading-text { color: #8b949e; font-size: 14px; padding: 16px 0; }
</style>
