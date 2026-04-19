<template>
  <div class="local-import-view">
    <h1 class="page-title">本地数据导入</h1>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- K线数据导入 -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <section class="card" aria-label="K线数据导入">
      <h2 class="section-title">K线数据导入</h2>

      <div class="form-group">
        <label class="form-label">市场分类</label>
        <div class="checkbox-group" role="group" aria-label="市场分类">
          <label v-for="m in marketOptions" :key="m.value" class="checkbox-item">
            <input type="checkbox" :value="m.value" v-model="selectedMarkets" /> {{ m.label }}
          </label>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">频率选择</label>
        <div class="checkbox-group">
          <label v-for="f in freqOptions" :key="f" class="checkbox-item">
            <input type="checkbox" :value="f" v-model="selectedFreqs" /> {{ f }}
          </label>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">日期范围（可选）</label>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">起始日期</label>
            <DatePicker v-model="startDate" placeholder="选择起始日期" aria-label="起始日期" />
          </div>
          <div class="form-group">
            <label class="form-label">结束日期</label>
            <DatePicker v-model="endDate" placeholder="选择结束日期" aria-label="结束日期" />
          </div>
        </div>
      </div>

      <div class="form-group">
        <div class="checkbox-group">
          <label class="checkbox-item">
            <input type="checkbox" v-model="forceImport" /> 强制全量导入
          </label>
        </div>
      </div>

      <button
        class="btn btn-primary"
        :disabled="store.loading || store.progress.status === 'running' || store.progress.status === 'pending'"
        @click="handleStartImport"
        aria-label="开始导入"
      >
        {{ store.loading ? '提交中...' : '开始导入' }}
      </button>

      <button
        v-if="store.progress.status === 'running' || store.progress.status === 'pending'"
        class="btn btn-danger"
        @click="store.requestStopImport()"
        aria-label="停止导入"
      >
        停止导入
      </button>

      <span v-if="store.error" class="sync-msg error" role="status">{{ store.error }}</span>
      <span v-if="klineSuccessMsg" class="sync-msg success" role="status">{{ klineSuccessMsg }}</span>

      <button
        v-if="store.progress.status === 'completed' || store.progress.status === 'failed' || store.progress.status === 'stopped'"
        class="btn btn-secondary"
        @click="handleResetImport"
        aria-label="清空导入状态"
      >
        清空状态
      </button>
    </section>

    <!-- ── K线导入进度 ── -->
    <section v-if="store.progress.status !== 'idle'" class="card" aria-label="导入进度">
      <h2 class="section-title">K线导入进度</h2>

      <div class="progress-header">
        <span class="status-badge" :class="progressStatusClass">{{ progressStatusLabel }}</span>
      </div>

      <div class="progress-bar-container">
        <div class="progress-bar" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div class="progress-text">
        已处理 {{ store.progress.processed_files }} / {{ store.progress.total_files }} 文件 ({{ progressPct }}%)
        <span v-if="store.progress.skipped_files > 0" class="skip-hint">
          · 跳过 {{ store.progress.skipped_files }} 个已导入文件
        </span>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">总解析行数</div>
          <div class="stat-value">{{ store.progress.total_parsed.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">总插入行数</div>
          <div class="stat-value highlight">{{ store.progress.total_inserted.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">总跳过行数</div>
          <div class="stat-value warn">{{ store.progress.total_skipped.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">耗时</div>
          <div class="stat-value">{{ store.progress.elapsed_seconds.toFixed(1) }}s</div>
        </div>
      </div>
    </section>

    <!-- ── K线结果摘要 ── -->
    <section
      v-if="store.result.status === 'completed' || store.result.status === 'failed' || store.result.status === 'stopped'"
      class="card"
      aria-label="结果摘要"
    >
      <h2 class="section-title">K线导入结果</h2>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">总文件数</div>
          <div class="stat-value">{{ store.result.total_files }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">成功文件数</div>
          <div class="stat-value highlight">{{ store.result.success_files }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">失败文件数</div>
          <div class="stat-value" :class="store.result.failed_files > 0 ? 'error-text' : ''">
            {{ store.result.failed_files }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">跳过文件数</div>
          <div class="stat-value muted">{{ store.result.skipped_files }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">总插入行数</div>
          <div class="stat-value highlight">{{ store.result.total_inserted.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">总跳过行数</div>
          <div class="stat-value warn">{{ store.result.total_skipped.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">耗时</div>
          <div class="stat-value">{{ store.result.elapsed_seconds.toFixed(1) }}s</div>
        </div>
      </div>

      <div v-if="store.result.failed_details.length > 0" class="failed-section">
        <h3 class="section-title">失败文件列表</h3>
        <table class="data-table" aria-label="失败文件列表">
          <thead>
            <tr><th scope="col">文件路径</th><th scope="col">错误原因</th></tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in store.result.failed_details" :key="idx">
              <td class="symbol-cell">{{ item.path }}</td>
              <td class="error-text">{{ item.error }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- 复权因子导入 -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <section class="card" aria-label="复权因子导入">
      <h2 class="section-title">复权因子导入</h2>

      <div class="form-group">
        <label class="form-label">选择复权类型</label>
        <div class="checkbox-group" role="group" aria-label="复权因子">
          <label v-for="a in adjFactorOptions" :key="a.value" class="checkbox-item">
            <input type="checkbox" :value="a.value" v-model="selectedAdjFactors" /> {{ a.label }}
          </label>
        </div>
      </div>

      <button
        class="btn btn-primary"
        :disabled="store.adjLoading || selectedAdjFactors.length === 0 || store.adjResult.status === 'running'"
        @click="handleStartAdjImport"
        aria-label="导入复权因子"
      >
        {{ store.adjLoading ? '提交中...' : '导入复权因子' }}
      </button>

      <button
        v-if="store.adjResult.status === 'running'"
        class="btn btn-danger"
        @click="store.requestStopAdjImport()"
        aria-label="停止复权因子导入"
      >
        停止导入
      </button>

      <span v-if="store.adjError" class="sync-msg error" role="status">{{ store.adjError }}</span>
      <span v-if="adjSuccessMsg" class="sync-msg success" role="status">{{ adjSuccessMsg }}</span>

      <button
        v-if="store.adjResult.status === 'completed' || store.adjResult.status === 'failed' || store.adjResult.status === 'stopped'"
        class="btn btn-secondary"
        @click="handleResetAdjImport"
        aria-label="清空复权因子导入状态"
      >
        清空状态
      </button>
    </section>

    <!-- ── 复权因子导入进度 ── -->
    <section
      v-if="store.adjResult.status === 'running'"
      class="card"
      aria-label="复权因子导入进度"
    >
      <h2 class="section-title">复权因子导入进度</h2>

      <div class="progress-header">
        <span class="status-badge syncing">运行中</span>
        <span v-if="store.adjResult.current_type" class="progress-step">
          {{ store.adjResult.current_type }}
        </span>
      </div>

      <div v-if="store.adjResult.current_step" class="progress-detail">
        {{ store.adjResult.current_step }}
      </div>

      <div class="progress-bar-container">
        <div class="progress-bar" :style="{ width: adjProgressPct + '%' }"></div>
      </div>
      <div class="progress-text">
        已完成 {{ store.adjResult.completed_types }} / {{ store.adjResult.total_types }} 项 ({{ adjProgressPct }}%)
        <span v-if="store.adjResult.elapsed_seconds"> · {{ formatElapsed(store.adjResult.elapsed_seconds) }}</span>
      </div>

      <!-- 已完成的类型实时展示 -->
      <div v-if="Object.keys(store.adjResult.adj_factor_stats).length > 0" class="stats-grid">
        <div
          v-for="(stat, key) in store.adjResult.adj_factor_stats"
          :key="key"
          class="stat-card"
        >
          <div class="stat-label">{{ key === 'qfq' ? '前复权' : '后复权' }}</div>
          <div class="stat-value" :class="adjStatClass(stat.status)">
            {{ adjStatLabel(stat.status) }}
          </div>
          <div class="stat-detail">解析 {{ stat.parsed?.toLocaleString() ?? 0 }} 条，插入 {{ stat.inserted?.toLocaleString() ?? 0 }} 条</div>
        </div>
      </div>
    </section>

    <!-- ── 复权因子导入结果 ── -->
    <section
      v-if="store.adjResult.status === 'completed' || store.adjResult.status === 'failed' || store.adjResult.status === 'stopped'"
      class="card"
      aria-label="复权因子导入结果"
    >
      <h2 class="section-title">复权因子导入结果</h2>

      <div class="stats-grid">
        <div
          v-for="(stat, key) in store.adjResult.adj_factor_stats"
          :key="key"
          class="stat-card"
        >
          <div class="stat-label">{{ key === 'qfq' ? '前复权' : '后复权' }}</div>
          <div class="stat-value" :class="adjStatClass(stat.status)">
            {{ adjStatLabel(stat.status) }}
          </div>
          <div class="stat-detail">解析 {{ stat.parsed?.toLocaleString() ?? 0 }} 条，插入 {{ stat.inserted?.toLocaleString() ?? 0 }} 条</div>
          <div v-if="stat.error" class="stat-detail error-text">{{ stat.error }}</div>
        </div>
      </div>

      <div v-if="store.adjResult.elapsed_seconds" class="progress-text" style="margin-top: 8px;">
        耗时 {{ formatElapsed(store.adjResult.elapsed_seconds) }}
      </div>
    </section>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- 板块数据导入 -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <section class="card" aria-label="板块数据导入">
      <h2 class="section-title">板块数据导入</h2>

      <div class="form-group">
        <label class="form-label">数据来源</label>
        <div class="checkbox-group" role="group" aria-label="数据来源">
          <label v-for="s in sectorSourceOptions" :key="s.value" class="checkbox-item">
            <input type="checkbox" :value="s.value" v-model="selectedSectorSources" /> {{ s.label }}
          </label>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">导入模式</label>
        <div class="checkbox-group" role="group" aria-label="导入模式">
          <label class="checkbox-item">
            <input type="radio" value="full" v-model="sectorImportType" name="sectorImportType" /> 全量导入
          </label>
          <label class="checkbox-item">
            <input type="radio" value="incremental" v-model="sectorImportType" name="sectorImportType" /> 增量导入
          </label>
        </div>
      </div>

      <button
        class="btn btn-primary"
        :disabled="store.sectorLoading || store.sectorProgress.status === 'running'"
        @click="handleStartSectorImport"
        aria-label="开始板块导入"
      >
        {{ store.sectorLoading ? '提交中...' : '开始板块导入' }}
      </button>

      <button
        v-if="store.sectorProgress.status === 'running'"
        class="btn btn-danger"
        @click="store.requestStopSectorImport()"
        aria-label="停止板块导入"
      >
        停止导入
      </button>

      <span v-if="store.sectorError" class="sync-msg error" role="status">{{ store.sectorError }}</span>
      <span v-if="sectorSuccessMsg" class="sync-msg success" role="status">{{ sectorSuccessMsg }}</span>

      <button
        v-if="store.sectorProgress.status !== 'idle' && store.sectorProgress.status !== 'running'"
        class="btn btn-secondary"
        @click="handleResetSectorImport"
        aria-label="清空板块导入状态"
      >
        清空状态
      </button>
    </section>

    <!-- ── 板块导入进度 ── -->
    <section v-if="store.sectorProgress.status !== 'idle'" class="card" aria-label="板块导入进度">
      <h2 class="section-title">板块导入进度</h2>

      <div class="progress-header">
        <span class="status-badge" :class="sectorStatusClass">{{ sectorStatusLabel }}</span>
        <span v-if="store.sectorProgress.stage" class="progress-step">
          {{ sectorStageLabel }}
        </span>
      </div>

      <!-- 进度条 -->
      <div v-if="sectorProgressPct != null" class="progress-bar-container" style="margin: 12px 0;">
        <div class="progress-bar" :style="{ width: sectorProgressPct + '%' }"></div>
      </div>
      <div v-if="sectorProgressPct != null" class="progress-text" style="margin-bottom: 8px;">
        {{ sectorProgressPct }}%
      </div>

      <div class="stats-grid">
        <div v-if="store.sectorProgress.total_files != null" class="stat-card">
          <div class="stat-label">文件进度</div>
          <div class="stat-value">{{ store.sectorProgress.processed_files ?? 0 }} / {{ store.sectorProgress.total_files }}</div>
        </div>
        <div v-else-if="store.sectorProgress.processed_files != null" class="stat-card">
          <div class="stat-label">已处理文件数</div>
          <div class="stat-value">{{ store.sectorProgress.processed_files }}</div>
        </div>
        <div v-if="store.sectorProgress.imported_records != null" class="stat-card">
          <div class="stat-label">已导入记录数</div>
          <div class="stat-value highlight">{{ (store.sectorProgress.imported_records ?? 0).toLocaleString() }}</div>
        </div>
        <div v-if="store.sectorProgress.error_count != null" class="stat-card">
          <div class="stat-label">出错记录数</div>
          <div class="stat-value error">{{ (store.sectorProgress.error_count ?? 0).toLocaleString() }}</div>
        </div>
      </div>

      <!-- 导出错误报告按钮 -->
      <button
        v-if="store.sectorProgress.error_count != null && store.sectorProgress.error_count > 0"
        class="btn btn-secondary"
        style="margin-top: 12px;"
        @click="handleExportErrors"
        aria-label="导出错误报告"
      >
        导出错误报告
      </button>

      <!-- 当前处理文件 -->
      <div v-if="store.sectorProgress.current_file && store.sectorProgress.status === 'running'" class="current-file-info" style="margin-top: 8px; font-size: 0.85em; color: var(--text-secondary, #888);">
        正在处理: {{ store.sectorProgress.current_file }}
      </div>

      <div v-if="store.sectorProgress.error" class="sync-msg error" style="margin-top: 8px;">
        {{ store.sectorProgress.error }}
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useLocalImportStore } from '@/stores/localImport'
import { apiClient } from '@/api'
import DatePicker from '@/components/DatePicker.vue'

const store = useLocalImportStore()

// ── K线导入配置 ───────────────────────────────────────────────────────────────

const marketOptions = [
  { value: 'hushen', label: '沪深' },
  { value: 'jingshi', label: '京市' },
  { value: 'zhishu', label: '指数' },
]
const selectedMarkets = ref<string[]>(['hushen', 'jingshi', 'zhishu'])

const freqOptions = ['1m', '5m', '15m', '30m', '60m']
const selectedFreqs = ref<string[]>([...freqOptions])

const startDate = ref('')
const endDate = ref('')
const forceImport = ref(false)
const klineSuccessMsg = ref('')

async function handleStartImport() {
  klineSuccessMsg.value = ''
  const params = {
    markets: selectedMarkets.value.length === marketOptions.length ? null : selectedMarkets.value,
    freqs: selectedFreqs.value.length === freqOptions.length ? null : selectedFreqs.value,
    start_date: startDate.value || null,
    end_date: endDate.value || null,
    force: forceImport.value,
  }
  // 缓存参数到 Redis（不阻塞导入）
  store.saveParams({
    markets: selectedMarkets.value,
    freqs: selectedFreqs.value,
    start_date: startDate.value || null,
    end_date: endDate.value || null,
    force: forceImport.value,
    adj_factors: selectedAdjFactors.value.length > 0 ? selectedAdjFactors.value : null,
  })
  await store.startImport(params)
  if (!store.error && store.taskId) {
    klineSuccessMsg.value = `导入任务已触发，任务ID: ${store.taskId}`
    store.startPolling()
    setTimeout(() => { klineSuccessMsg.value = '' }, 5000)
  }
}

// ── 复权因子导入配置 ──────────────────────────────────────────────────────────

const adjFactorOptions = [
  { value: 'qfq', label: '前复权' },
  { value: 'hfq', label: '后复权' },
]
const selectedAdjFactors = ref<string[]>([])
const adjSuccessMsg = ref('')

async function handleStartAdjImport() {
  adjSuccessMsg.value = ''
  // 缓存参数到 Redis（不阻塞导入）
  store.saveParams({
    markets: selectedMarkets.value,
    freqs: selectedFreqs.value,
    start_date: startDate.value || null,
    end_date: endDate.value || null,
    force: forceImport.value,
    adj_factors: selectedAdjFactors.value.length > 0 ? selectedAdjFactors.value : null,
  })
  await store.startAdjImport({ adj_factors: selectedAdjFactors.value })
  if (!store.adjError) {
    adjSuccessMsg.value = '复权因子导入任务已触发'
    setTimeout(() => { adjSuccessMsg.value = '' }, 5000)
  }
}

async function handleResetImport() {
  await store.resetImportStatus()
}

async function handleResetAdjImport() {
  await store.resetAdjImportStatus()
}

// ── 板块数据导入配置 ──────────────────────────────────────────────────────────

const sectorSourceOptions = [
  { value: 'DC', label: '东方财富' },
  { value: 'TI', label: '同花顺' },
  { value: 'TDX', label: '通达信' },
]
const selectedSectorSources = ref<string[]>(['DC', 'TI', 'TDX'])
const sectorImportType = ref<'full' | 'incremental'>('incremental')
const sectorSuccessMsg = ref('')

async function handleStartSectorImport() {
  sectorSuccessMsg.value = ''
  const params = {
    data_sources: selectedSectorSources.value.length === sectorSourceOptions.length ? null : selectedSectorSources.value,
    import_type: sectorImportType.value,
  }
  await store.startSectorImport(params)
  if (!store.sectorError && store.sectorTaskId) {
    sectorSuccessMsg.value = `板块导入任务已触发，任务ID: ${store.sectorTaskId}`
    store.startSectorPolling()
    setTimeout(() => { sectorSuccessMsg.value = '' }, 5000)
  }
}

async function handleResetSectorImport() {
  await store.resetSectorImportStatus()
}

/** 导出板块导入错误报告 CSV */
async function handleExportErrors() {
  try {
    const res = await apiClient.get('/sector/import/errors/export', { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'sector_import_errors.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    // 静默忽略
  }
}

const sectorStatusLabel = computed(() => {
  const map: Record<string, string> = { running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' }
  return map[store.sectorProgress.status] ?? store.sectorProgress.status
})

const sectorStatusClass = computed(() => {
  const map: Record<string, string> = { running: 'syncing', completed: 'ok', failed: 'error', stopped: 'warn-badge' }
  return map[store.sectorProgress.status] ?? ''
})

const sectorStageLabel = computed(() => {
  const stage = store.sectorProgress.stage ?? ''
  // 后端直接使用中文阶段名，直接返回
  return stage
})

const sectorProgressPct = computed(() => {
  const total = store.sectorProgress.total_files
  const processed = store.sectorProgress.processed_files
  if (total == null || total === 0 || processed == null) return null
  return Math.min(100, Math.round((processed / total) * 100))
})

// ── K线进度计算 ───────────────────────────────────────────────────────────────

const progressPct = computed(() => {
  if (store.progress.total_files === 0) return 0
  return Math.round((store.progress.processed_files / store.progress.total_files) * 100)
})

const progressStatusLabel = computed(() => {
  const map: Record<string, string> = { pending: '准备中', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' }
  return map[store.progress.status] ?? store.progress.status
})

const progressStatusClass = computed(() => {
  const map: Record<string, string> = { pending: 'syncing', running: 'syncing', completed: 'ok', failed: 'error', stopped: 'warn-badge' }
  return map[store.progress.status] ?? ''
})

// ── 复权因子进度计算 ──────────────────────────────────────────────────────────

const adjProgressPct = computed(() => {
  if (store.adjResult.total_types === 0) return 0
  return Math.round((store.adjResult.completed_types / store.adjResult.total_types) * 100)
})

function adjStatLabel(status: string): string {
  if (status === 'completed') return '成功'
  if (status === 'skipped') return '已跳过'
  return '失败'
}

function adjStatClass(status: string): string {
  if (status === 'completed') return 'highlight'
  if (status === 'skipped') return 'muted'
  return 'error-text'
}

/** 将秒数格式化为友好的时间字符串 */
function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  if (m < 60) return `${m}分${s}秒`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return `${h}时${rm}分${s}秒`
}

// ── 生命周期 ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  // 加载缓存的导入参数
  const cached = await store.loadParams()
  if (cached) {
    if (cached.markets && cached.markets.length > 0) selectedMarkets.value = cached.markets
    if (cached.freqs && cached.freqs.length > 0) selectedFreqs.value = cached.freqs
    if (cached.start_date) startDate.value = cached.start_date
    if (cached.end_date) endDate.value = cached.end_date
    if (cached.force !== undefined) forceImport.value = cached.force
    if (cached.adj_factors && cached.adj_factors.length > 0) selectedAdjFactors.value = cached.adj_factors
  }

  await store.fetchStatus()
  await store.fetchAdjStatus()
  await store.fetchSectorStatus()
  if (store.progress.status === 'running' || store.progress.status === 'pending') {
    store.startPolling()
  }
  if (store.adjResult.status === 'running') {
    store.startAdjPolling()
  }
  if (store.sectorProgress.status === 'running') {
    store.startSectorPolling()
  }
})

onUnmounted(() => {
  store.stopPolling()
  store.stopAdjPolling()
  store.stopSectorPolling()
})
</script>

<style scoped>
.local-import-view { max-width: 1100px; }

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #e6edf3;
  margin: 0 0 20px;
}

.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #e6edf3;
  margin: 0 0 14px;
}

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
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #e6edf3;
  cursor: pointer;
}

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
.btn-danger { background: #da3633; color: #fff; margin-left: 8px; }
.btn-danger:hover { background: #f85149; }
.btn-secondary { background: #21262d; color: #c9d1d9; margin-left: 8px; border: 1px solid #30363d; }
.btn-secondary:hover { background: #30363d; }

.sync-msg {
  display: inline-block;
  font-size: 13px;
  margin-left: 10px;
}
.sync-msg.success { color: #3fb950; }
.sync-msg.error { color: #f85149; }

.progress-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
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
.progress-text { font-size: 13px; color: #8b949e; margin-bottom: 12px; }

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
.status-badge.warn-badge { background: #2a2a1a; color: #d29922; }

.progress-step {
  font-size: 13px;
  color: #8b949e;
}

.progress-detail {
  font-size: 13px;
  color: #58a6ff;
  margin-bottom: 10px;
  font-family: monospace;
}

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
.stat-value.error { color: #f85149; }
.stat-value.warn { color: #d29922; }
.stat-value.muted { color: #8b949e; }
.stat-detail { font-size: 12px; color: #8b949e; margin-top: 4px; }

.skip-hint { color: #8b949e; }

.error-text { color: #f85149; }

.failed-section { margin-top: 16px; }

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

.symbol-cell { font-family: monospace; color: #58a6ff; }
</style>
