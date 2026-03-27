<template>
  <div class="data-manage-view">
    <h1 class="page-title">数据管理</h1>

    <!-- ── 数据源同步状态 ── -->
    <section class="card" aria-label="数据源同步状态">
      <div class="section-header">
        <h2 class="section-title">数据源同步状态</h2>
        <button
          class="btn btn-primary"
          :disabled="syncLoading"
          @click="triggerSync"
          aria-label="手动触发数据同步"
        >
          {{ syncLoading ? '同步中...' : '手动同步' }}
        </button>
      </div>

      <span v-if="syncMsg" class="sync-msg" :class="syncMsgType" role="status">{{ syncMsg }}</span>

      <LoadingSpinner v-if="syncStatusState.loading" text="加载同步状态..." />
      <ErrorBanner
        v-else-if="syncStatusState.error"
        :message="syncStatusState.error"
        :retryFn="fetchSyncStatus"
      />
      <table v-else class="data-table" aria-label="数据源同步状态列表">
        <thead>
          <tr>
            <th scope="col">数据源</th>
            <th scope="col">最后同步时间</th>
            <th scope="col">状态</th>
            <th scope="col">已同步记录数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in syncStatusState.data?.items ?? []" :key="item.source">
            <td>{{ item.source }}</td>
            <td>{{ formatTime(item.last_sync_at) }}</td>
            <td>
              <span class="status-badge" :class="statusClass(item.status)">
                {{ statusLabel(item.status) }}
              </span>
            </td>
            <td>{{ item.record_count.toLocaleString() }}</td>
          </tr>
          <tr v-if="!syncStatusState.data?.items?.length">
            <td colspan="4" class="empty">暂无同步状态数据</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ── 数据清洗统计 ── -->
    <section class="card" aria-label="数据清洗统计">
      <h2 class="section-title">数据清洗统计</h2>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">总股票数</div>
          <div class="stat-value">5,354</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">有效标的</div>
          <div class="stat-value highlight">4,821</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">ST / 退市剔除</div>
          <div class="stat-value warn">312</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">新股剔除（上市 &lt; 1年）</div>
          <div class="stat-value warn">221</div>
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
import { ref, computed, onMounted } from 'vue'
import { apiClient } from '@/api'
import { usePageState } from '@/composables/usePageState'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'

// ── 类型定义 ──────────────────────────────────────────────────────────────────

interface SyncStatus {
  source: string
  last_sync_at: string
  status: 'OK' | 'ERROR' | 'SYNCING'
  record_count: number
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

async function triggerSync() {
  syncLoading.value = true
  syncMsg.value = ''
  try {
    await apiClient.post('/data/sync')
    syncMsg.value = '数据同步任务已触发，请稍后刷新查看状态'
    syncMsgType.value = 'success'
    setTimeout(fetchSyncStatus, 2000)
  } catch (e: unknown) {
    syncMsg.value = e instanceof Error ? e.message : '触发同步失败，请重试'
    syncMsgType.value = 'error'
  } finally {
    syncLoading.value = false
    setTimeout(() => { syncMsg.value = '' }, 5000)
  }
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

// ── 格式化工具 ────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { OK: '正常', ERROR: '异常', SYNCING: '同步中' }
  return map[status] ?? status
}

function statusClass(status: string): string {
  const map: Record<string, string> = { OK: 'ok', ERROR: 'error', SYNCING: 'syncing' }
  return map[status] ?? ''
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
  fetchSyncStatus()
  fetchExclusions()
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
</style>
