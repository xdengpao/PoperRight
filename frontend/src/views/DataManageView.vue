<template>
  <div class="data-manage-view">
    <h1 class="page-title">数据管理</h1>

    <!-- ── 数据源健康状态 ── -->
    <section class="card" aria-label="数据源健康状态">
      <h2 class="section-title">数据源健康状态</h2>
      <LoadingSpinner v-if="healthState.loading" text="检测数据源..." />
      <ErrorBanner v-else-if="healthState.error" :message="healthState.error" :retryFn="fetchHealth" />
      <div v-else class="health-grid">
        <div v-for="src in healthState.data?.sources ?? []" :key="src.name"
          class="health-card" :class="src.status === 'connected' ? 'health-ok' : 'health-err'">
          <div class="health-name">{{ src.name }}</div>
          <div class="health-status">{{ src.status === 'connected' ? '✅ 已连接' : '❌ 已断开' }}</div>
          <div class="health-time">{{ formatTime(src.checked_at) }}</div>
        </div>
      </div>
    </section>

    <!-- ── 数据源同步状态 ── -->
    <section class="card" aria-label="数据源同步状态">
      <div class="section-header">
        <h2 class="section-title">数据源同步状态</h2>
        <div class="sync-controls">
          <button class="btn-icon" @click="fetchSyncStatus" :disabled="syncStatusState.loading" aria-label="刷新同步状态" title="刷新">
            <span :class="['refresh-icon', syncStatusState.loading && 'spinning']">↻</span>
          </button>
          <select v-model="syncType" class="sync-select" aria-label="选择同步类型">
            <option value="all">全部同步</option>
            <option value="kline">行情数据</option>
            <option value="fundamentals">基本面数据</option>
            <option value="money_flow">资金流向</option>
          </select>
          <button
            class="btn btn-primary"
            :disabled="syncLoading"
            @click="triggerSync"
            aria-label="手动触发数据同步"
          >
            {{ syncLoading ? '同步中...' : '手动同步' }}
          </button>
        </div>
      </div>

      <span v-if="syncMsg" class="sync-msg" :class="syncMsgType" role="status">{{ syncMsg }}</span>

      <LoadingSpinner v-if="syncStatusState.loading" text="加载同步状态..." />
      <ErrorBanner
        v-else-if="syncStatusState.error"
        :message="syncStatusState.error"
        :retryFn="fetchSyncStatus"
      />
      <div v-else class="sync-cards">
        <div
          v-for="item in syncStatusState.data?.items ?? []"
          :key="item.source"
          class="sync-card"
          :class="syncCardClass(item.status)"
        >
          <div class="sync-card-header">
            <span class="sync-card-title">{{ item.source }}</span>
            <span class="status-badge" :class="statusClass(item.status)">
              {{ statusLabel(item.status) }}
            </span>
          </div>
          <div class="sync-card-body">
            <div class="sync-detail-row">
              <span class="sync-detail-label">数据源</span>
              <span class="sync-detail-value">
                {{ item.data_source }}
                <span v-if="item.is_fallback" class="fallback-badge">（故障转移）</span>
              </span>
            </div>
            <div class="sync-detail-row">
              <span class="sync-detail-label">最后同步</span>
              <span class="sync-detail-value">{{ formatSyncTime(item.last_sync_at) }}</span>
            </div>
            <div class="sync-detail-row">
              <span class="sync-detail-label">同步记录</span>
              <span class="sync-detail-value">{{ item.record_count > 0 ? item.record_count.toLocaleString() + ' 条' : '—' }}</span>
            </div>
          </div>
        </div>
        <div v-if="!syncStatusState.data?.items?.length" class="empty">暂无同步状态数据</div>
      </div>
    </section>

    <!-- ── 数据清洗统计 ── -->
    <section class="card" aria-label="数据清洗统计">
      <h2 class="section-title">数据清洗统计</h2>
      <LoadingSpinner v-if="cleaningState.loading" text="加载清洗统计..." />
      <ErrorBanner v-else-if="cleaningState.error" :message="cleaningState.error" :retryFn="fetchCleaningStats" />
      <div v-else class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">总股票数</div>
          <div class="stat-value">{{ cleaningState.data?.total_stocks?.toLocaleString() ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">有效标的</div>
          <div class="stat-value highlight">{{ cleaningState.data?.valid_stocks?.toLocaleString() ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">ST / 退市剔除</div>
          <div class="stat-value warn">{{ cleaningState.data?.st_delisted_count?.toLocaleString() ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">新股剔除</div>
          <div class="stat-value warn">{{ cleaningState.data?.new_stock_count?.toLocaleString() ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">停牌剔除</div>
          <div class="stat-value warn">{{ cleaningState.data?.suspended_count?.toLocaleString() ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">高质押剔除</div>
          <div class="stat-value warn">{{ cleaningState.data?.high_pledge_count?.toLocaleString() ?? '—' }}</div>
        </div>
      </div>
    </section>

    <!-- ── 历史数据回填 ── -->
    <section class="card" aria-label="历史数据回填">
      <h2 class="section-title">历史数据回填</h2>

      <!-- 数据类型多选 -->
      <div class="backfill-form">
        <div class="form-group">
          <label class="form-label">数据类型</label>
          <div class="checkbox-group">
            <label class="checkbox-item">
              <input type="checkbox" v-model="backfillDataTypes" value="kline" /> 行情数据
            </label>
            <label class="checkbox-item">
              <input type="checkbox" v-model="backfillDataTypes" value="fundamentals" /> 基本面数据
            </label>
            <label class="checkbox-item">
              <input type="checkbox" v-model="backfillDataTypes" value="money_flow" /> 资金流向
            </label>
          </div>
        </div>

        <!-- 股票范围选择 -->
        <div class="form-group">
          <label class="form-label">股票范围</label>
          <div class="radio-group">
            <label class="radio-item">
              <input type="radio" v-model="backfillScope" value="ALL" /> 全市场
            </label>
            <label class="radio-item">
              <input type="radio" v-model="backfillScope" value="CUSTOM" /> 指定股票
            </label>
          </div>
        </div>

        <!-- 股票代码输入（仅指定股票时显示） -->
        <div v-if="backfillScope === 'CUSTOM'" class="form-group">
          <label class="form-label" for="backfill-symbols">股票代码</label>
          <input
            id="backfill-symbols"
            v-model="backfillSymbols"
            type="text"
            class="form-input"
            placeholder="多个股票用逗号分隔，如 600000.SH,000001.SZ"
            aria-label="股票代码，多个用逗号分隔"
          />
        </div>

        <!-- 起止日期 -->
        <div class="form-row">
          <div class="form-group">
            <label class="form-label" for="backfill-start">开始日期</label>
            <input id="backfill-start" v-model="backfillStartDate" type="date" class="form-input" />
          </div>
          <div class="form-group">
            <label class="form-label" for="backfill-end">结束日期</label>
            <input id="backfill-end" v-model="backfillEndDate" type="date" class="form-input" />
          </div>
        </div>

        <!-- K线频率（仅行情数据选中时显示） -->
        <div v-if="backfillDataTypes.includes('kline')" class="form-group">
          <label class="form-label" for="backfill-freq">K线频率</label>
          <select id="backfill-freq" v-model="backfillFreq" class="form-input" aria-label="K线频率">
            <option value="1d">日线</option>
            <option value="1w">周线</option>
            <option value="1M">月线</option>
          </select>
        </div>

        <!-- 开始回填按钮 -->
        <button
          class="btn btn-primary"
          :disabled="backfillLoading || backfillDataTypes.length === 0"
          @click="startBackfill"
          aria-label="开始回填"
        >
          {{ backfillLoading ? '提交中...' : '开始回填' }}
        </button>
        <span v-if="backfillMsg" class="sync-msg" :class="backfillMsgType" role="status">{{ backfillMsg }}</span>
      </div>

      <!-- 回填进度展示 -->
      <div v-if="backfillProgress.status !== 'idle'" class="backfill-progress">
        <div class="progress-header">
          <span class="status-badge" :class="backfillStatusClass(backfillProgress.status)">
            {{ backfillStatusLabel(backfillProgress.status) }}
          </span>
          <span v-if="backfillProgress.failed > 0" class="failed-count">
            失败: {{ backfillProgress.failed }}
          </span>
          <button
            v-if="backfillProgress.status === 'running' || backfillProgress.status === 'pending'"
            class="btn btn-danger"
            :disabled="stopBackfillLoading"
            @click="stopBackfill"
            aria-label="停止回填"
          >
            {{ stopBackfillLoading ? '停止中...' : '停止回填' }}
          </button>
        </div>

        <!-- 进度条 -->
        <div class="progress-bar-container">
          <div class="progress-bar" :style="{ width: backfillPct + '%' }"></div>
        </div>
        <div class="progress-text">
          {{ backfillProgress.completed }} / {{ backfillProgress.total }}
          （{{ backfillPct }}%）
        </div>

        <!-- 当前处理股票 -->
        <div v-if="backfillProgress.current_symbol" class="progress-detail">
          当前处理: <span class="symbol-cell">{{ backfillProgress.current_symbol }}</span>
        </div>

        <!-- 数据类型标签 -->
        <div v-if="backfillProgress.data_types.length" class="progress-tags">
          <span v-for="dt in backfillProgress.data_types" :key="dt" class="data-type-tag">
            {{ dataTypeLabel(dt) }}
          </span>
        </div>
      </div>
    </section>

    <!-- ── 永久剔除名单 ── -->
    <section class="card" aria-label="永久剔除名单">
      <h2 class="section-title">永久剔除名单</h2>

      <LoadingSpinner v-if="exclusionsState.loading" text="加载剔除名单..." />
      <ErrorBanner
        v-else-if="exclusionsState.error"
        :message="exclusionsState.error"
        :retryFn="fetchExclusions"
      />
      <template v-else>
        <table class="data-table" aria-label="永久剔除名单列表">
          <thead>
            <tr>
              <th scope="col">股票代码</th>
              <th scope="col">股票名称</th>
              <th scope="col">剔除原因</th>
              <th scope="col">剔除时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in exclusionsState.data?.items ?? []" :key="item.symbol">
              <td class="symbol-cell">{{ item.symbol }}</td>
              <td>{{ item.name }}</td>
              <td>
                <span class="reason-badge" :class="reasonClass(item.reason)">
                  {{ reasonLabel(item.reason) }}
                </span>
              </td>
              <td>{{ item.created_at?.slice(0, 10) ?? '—' }}</td>
            </tr>
            <tr v-if="!exclusionsState.data?.items?.length">
              <td colspan="4" class="empty">暂无剔除记录</td>
            </tr>
          </tbody>
        </table>
        <div v-if="(exclusionsState.data?.total ?? 0) > pageSize" class="pagination">
          <button class="btn-page" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <span class="page-info">第 {{ page }} 页 / 共 {{ totalPages }} 页</span>
          <button class="btn-page" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiClient } from '@/api'
import { usePageState } from '@/composables/usePageState'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'

// ── 类型定义 ──────────────────────────────────────────────────────────────────

interface DataSourceStatus {
  name: string
  status: 'connected' | 'disconnected'
  checked_at: string
}

interface DataSourceHealthResponse {
  sources: DataSourceStatus[]
}

interface CleaningStatsResponse {
  total_stocks: number
  valid_stocks: number
  st_delisted_count: number
  new_stock_count: number
  suspended_count: number
  high_pledge_count: number
}

interface SyncStatus {
  source: string
  last_sync_at: string
  status: 'OK' | 'ERROR' | 'SYNCING'
  record_count: number
  data_source: string
  is_fallback: boolean
}

interface SyncStatusResponse {
  items: SyncStatus[]
}

interface ExclusionItem {
  symbol: string
  name: string
  reason: string
  created_at: string
}

interface ExclusionResponse {
  total: number
  page: number
  page_size: number
  items: ExclusionItem[]
}

// ── 回填类型定义（需求 25.14, 25.15）─────────────────────────────────────────

interface BackfillRequest {
  data_types: string[]
  symbols: string[]
  start_date: string | null
  end_date: string | null
  freq: string
}

interface BackfillProgress {
  total: number
  completed: number
  failed: number
  current_symbol: string
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed' | 'stopping' | 'stopped'
  data_types: string[]
}

// ── 数据源健康状态 ──────────────────────────────────────────────────────────

const { state: healthState, execute: execHealth } = usePageState<DataSourceHealthResponse>()

async function fetchHealth() {
  await execHealth(() =>
    apiClient.get<DataSourceHealthResponse>('/data/sources/health', { timeout: 45_000 }).then((r) => r.data),
  )
}

// ── 同步状态 ──────────────────────────────────────────────────────────────────

const { state: syncStatusState, execute: execSyncStatus } = usePageState<SyncStatusResponse>()

async function fetchSyncStatus() {
  await execSyncStatus(() =>
    apiClient.get<SyncStatusResponse>('/data/sync/status').then((r) => r.data),
  )
}

// ── 手动触发同步 ──────────────────────────────────────────────────────────────

const syncLoading = ref(false)
const syncMsg = ref('')
const syncMsgType = ref<'success' | 'error'>('success')
const syncType = ref<string>('all')

async function triggerSync() {
  syncLoading.value = true
  syncMsg.value = ''
  try {
    await apiClient.post('/data/sync', { sync_type: syncType.value })
    syncMsg.value = '数据同步任务已触发'
    syncMsgType.value = 'success'
    // 自动刷新同步状态（2s、5s、10s 后各刷新一次）
    setTimeout(fetchSyncStatus, 2000)
    setTimeout(fetchSyncStatus, 5000)
    setTimeout(fetchSyncStatus, 10000)
  } catch (e: unknown) {
    syncMsg.value = e instanceof Error ? e.message : '触发同步失败，请重试'
    syncMsgType.value = 'error'
  } finally {
    syncLoading.value = false
    setTimeout(() => { syncMsg.value = '' }, 5000)
  }
}

// ── 清洗统计 ──────────────────────────────────────────────────────────────────

const { state: cleaningState, execute: execCleaning } = usePageState<CleaningStatsResponse>()

async function fetchCleaningStats() {
  await execCleaning(() =>
    apiClient.get<CleaningStatsResponse>('/data/cleaning/stats').then((r) => r.data),
  )
}

// ── 剔除名单 ──────────────────────────────────────────────────────────────────

const { state: exclusionsState, execute: execExclusions } = usePageState<ExclusionResponse>()
const page = ref(1)
const pageSize = 20

const totalPages = computed(() =>
  Math.ceil((exclusionsState.data?.total ?? 0) / pageSize),
)

async function fetchExclusions() {
  await execExclusions(() =>
    apiClient
      .get<ExclusionResponse>('/data/exclusions', { params: { page: page.value, page_size: pageSize } })
      .then((r) => r.data),
  )
}

function changePage(p: number) {
  page.value = p
  fetchExclusions()
}

// ── 历史数据回填（需求 25.14, 25.15）────────────────────────────────────────

const backfillDataTypes = ref<string[]>(['kline', 'fundamentals', 'money_flow'])
const backfillScope = ref<'ALL' | 'CUSTOM'>('ALL')
const backfillSymbols = ref('')
const backfillStartDate = ref('')
const backfillEndDate = ref('')
const backfillFreq = ref('1d')
const backfillLoading = ref(false)
const backfillMsg = ref('')
const backfillMsgType = ref<'success' | 'error'>('success')
const stopBackfillLoading = ref(false)
let backfillPollTimer: ReturnType<typeof setInterval> | null = null

const backfillProgress = reactive<BackfillProgress>({
  total: 0,
  completed: 0,
  failed: 0,
  current_symbol: '',
  status: 'idle',
  data_types: [],
})

const backfillPct = computed(() => {
  if (backfillProgress.total <= 0) return 0
  return Math.round((backfillProgress.completed / backfillProgress.total) * 100)
})

async function startBackfill() {
  backfillLoading.value = true
  backfillMsg.value = ''
  try {
    const symbols = backfillScope.value === 'ALL'
      ? ['ALL']
      : backfillSymbols.value
          .split(',')
          .map((s) => s.trim())
          .filter((s) => s.length > 0)

    const payload: BackfillRequest = {
      data_types: backfillDataTypes.value,
      symbols,
      start_date: backfillStartDate.value || null,
      end_date: backfillEndDate.value || null,
      freq: backfillFreq.value,
    }

    await apiClient.post('/data/backfill', payload)
    backfillMsg.value = '回填任务已触发'
    backfillMsgType.value = 'success'
    startBackfillPolling()
  } catch (e: unknown) {
    const err = e as { response?: { status: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      backfillMsg.value = err.response.data?.detail ?? '已有回填任务正在执行，请等待完成后再试'
    } else {
      backfillMsg.value = e instanceof Error ? e.message : '触发回填失败，请重试'
    }
    backfillMsgType.value = 'error'
  } finally {
    backfillLoading.value = false
    setTimeout(() => { backfillMsg.value = '' }, 5000)
  }
}

async function stopBackfill() {
  stopBackfillLoading.value = true
  try {
    const { data } = await apiClient.post<{ message: string }>('/data/backfill/stop')
    backfillMsg.value = data.message || '已发送停止信号'
    backfillMsgType.value = 'success'
    // 立即刷新一次状态
    await fetchBackfillStatus()
  } catch {
    backfillMsg.value = '停止回填失败，请重试'
    backfillMsgType.value = 'error'
  } finally {
    stopBackfillLoading.value = false
    setTimeout(() => { backfillMsg.value = '' }, 5000)
  }
}

async function fetchBackfillStatus() {
  try {
    const { data } = await apiClient.get<BackfillProgress>('/data/backfill/status')
    Object.assign(backfillProgress, data)
    if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
      stopBackfillPolling()
    }
  } catch {
    // silently ignore polling errors
  }
}

function startBackfillPolling() {
  stopBackfillPolling()
  fetchBackfillStatus()
  backfillPollTimer = setInterval(fetchBackfillStatus, 3000)
}

function stopBackfillPolling() {
  if (backfillPollTimer) {
    clearInterval(backfillPollTimer)
    backfillPollTimer = null
  }
}

function backfillStatusLabel(status: string): string {
  const map: Record<string, string> = {
    idle: '空闲',
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopping: '停止中...',
    stopped: '已停止',
  }
  return map[status] ?? status
}

function backfillStatusClass(status: string): string {
  const map: Record<string, string> = {
    idle: 'syncing',
    pending: 'syncing',
    running: 'syncing',
    completed: 'ok',
    failed: 'error',
    stopping: 'syncing',
    stopped: 'error',
  }
  return map[status] ?? ''
}

function dataTypeLabel(dt: string): string {
  const map: Record<string, string> = {
    kline: '行情数据',
    fundamentals: '基本面数据',
    money_flow: '资金流向',
  }
  return map[dt] ?? dt
}

// ── 格式化工具 ────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { OK: '正常', ERROR: '异常', SYNCING: '同步中', UNKNOWN: '未同步' }
  return map[status] ?? status
}

function statusClass(status: string): string {
  const map: Record<string, string> = { OK: 'ok', ERROR: 'error', SYNCING: 'syncing', UNKNOWN: 'unknown' }
  return map[status] ?? ''
}

function syncCardClass(status: string): string {
  const map: Record<string, string> = { OK: 'sync-card-ok', ERROR: 'sync-card-err', SYNCING: 'sync-card-syncing', UNKNOWN: 'sync-card-unknown' }
  return map[status] ?? 'sync-card-unknown'
}

function formatSyncTime(iso: string | null): string {
  if (!iso) return '从未同步'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  return iso.replace('T', ' ').slice(0, 16)
}

function reasonLabel(reason: string): string {
  const map: Record<string, string> = {
    ST: 'ST / *ST',
    DELISTED: '退市',
    NEW_STOCK: '新股',
    SUSPENDED: '长期停牌',
  }
  return map[reason] ?? reason
}

function reasonClass(reason: string): string {
  const map: Record<string, string> = {
    ST: 'reason-st',
    DELISTED: 'reason-delisted',
    NEW_STOCK: 'reason-new',
    SUSPENDED: 'reason-suspended',
  }
  return map[reason] ?? ''
}

// ── 生命周期 ──────────────────────────────────────────────────────────────────

onMounted(() => {
  fetchHealth()
  fetchSyncStatus()
  fetchExclusions()
  fetchCleaningStats()
  // Check initial backfill status; start polling if running/pending
  fetchBackfillStatus().then(() => {
    if (backfillProgress.status === 'running' || backfillProgress.status === 'pending') {
      startBackfillPolling()
    }
  })
})

onUnmounted(() => {
  stopBackfillPolling()
})
</script>

<style scoped>
.data-manage-view { max-width: 1100px; }

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #e6edf3;
  margin: 0 0 20px;
}

/* 卡片 */
.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #e6edf3;
  margin: 0 0 14px;
}

.section-header .section-title { margin: 0; }

/* 按钮 */
.btn {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  border: none;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #1f6feb; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #388bfd; }
.btn-danger { background: #da3633; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #f85149; }

/* 同步消息 */
.sync-msg {
  display: block;
  font-size: 13px;
  margin-bottom: 10px;
}
.sync-msg.success { color: #3fb950; }
.sync-msg.error { color: #f85149; }

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th,
.data-table td {
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid #21262d;
  font-size: 14px;
}
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.empty { text-align: center; color: #484f58; padding: 24px; }

.symbol-cell { font-family: monospace; color: #58a6ff; }

/* 状态徽章 */
.status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.ok { background: #1a3a1a; color: #3fb950; }
.status-badge.error { background: #3a1a1a; color: #f85149; }
.status-badge.syncing { background: #1a2a3a; color: #58a6ff; }

/* 原因徽章 */
.reason-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.reason-st { background: #3a1a1a; color: #f85149; }
.reason-delisted { background: #2a2a2a; color: #8b949e; }
.reason-new { background: #1a2a3a; color: #58a6ff; }
.reason-suspended { background: #3a2a1a; color: #d29922; }

/* 清洗统计 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.stat-card {
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 6px;
  padding: 16px;
}
.stat-label { font-size: 12px; color: #8b949e; margin-bottom: 6px; }
.stat-value { font-size: 22px; font-weight: 600; color: #e6edf3; }
.stat-value.highlight { color: #3fb950; }
.stat-value.warn { color: #d29922; }

/* 健康状态卡片 */
.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.health-card {
  border-radius: 6px;
  padding: 16px;
  border: 1px solid #21262d;
}
.health-ok {
  background: #1a3a1a;
  color: #3fb950;
}
.health-err {
  background: #3a1a1a;
  color: #f85149;
}
.health-name {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
.health-status {
  font-size: 16px;
  margin-bottom: 4px;
}
.health-time {
  font-size: 12px;
  opacity: 0.7;
}

/* 同步控制 */
.sync-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sync-select {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}
.sync-select:focus {
  border-color: #58a6ff;
  outline: none;
}

/* 刷新按钮 */
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

/* 同步状态卡片 */
.sync-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}
.sync-card {
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #21262d;
  background: #0d1117;
  transition: border-color 0.2s;
}
.sync-card-ok { border-left: 3px solid #3fb950; }
.sync-card-err { border-left: 3px solid #f85149; }
.sync-card-syncing { border-left: 3px solid #58a6ff; }
.sync-card-unknown { border-left: 3px solid #484f58; }
.sync-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.sync-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #e6edf3;
}
.sync-card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sync-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sync-detail-label {
  font-size: 13px;
  color: #8b949e;
}
.sync-detail-value {
  font-size: 13px;
  color: #e6edf3;
}
.status-badge.unknown { background: #21262d; color: #8b949e; }

/* 故障转移标注 */
.fallback-badge {
  color: #d29922;
  font-size: 12px;
  font-weight: 500;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  justify-content: flex-end;
}
.btn-page {
  background: #21262d;
  border: 1px solid #30363d;
  color: #8b949e;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.btn-page:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-page:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 13px; color: #8b949e; }

/* 回填表单 */
.backfill-form { margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 4px; }
.form-input {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
  max-width: 400px;
  box-sizing: border-box;
}
.form-input:focus { border-color: #58a6ff; outline: none; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.checkbox-group { display: flex; gap: 16px; flex-wrap: wrap; }
.radio-group { display: flex; gap: 16px; flex-wrap: wrap; }
.radio-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #e6edf3;
  cursor: pointer;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #e6edf3;
  cursor: pointer;
}

/* 回填进度 */
.backfill-progress {
  margin-top: 16px;
  padding: 14px;
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 6px;
}
.progress-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.failed-count { font-size: 13px; color: #f85149; }
.progress-bar-container {
  background: #21262d;
  border-radius: 4px;
  height: 8px;
  overflow: hidden;
  margin-bottom: 6px;
}
.progress-bar {
  height: 100%;
  background: #1f6feb;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.progress-text { font-size: 13px; color: #8b949e; margin-bottom: 8px; }
.progress-detail { font-size: 13px; color: #e6edf3; margin-bottom: 8px; }
.progress-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.data-type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background: #1a2a3a;
  color: #58a6ff;
}
</style>
