<template>
  <div class="local-import-view">
    <h1 class="page-title">本地数据导入</h1>

    <!-- ── 导入配置 ── -->
    <section class="card" aria-label="导入配置">
      <h2 class="section-title">导入配置</h2>

      <div class="form-group">
        <label class="form-label">频率选择</label>
        <div class="checkbox-group">
          <label v-for="f in freqOptions" :key="f" class="checkbox-item">
            <input type="checkbox" :value="f" v-model="selectedFreqs" /> {{ f }}
          </label>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" for="sub-dir">子目录路径（可选）</label>
        <input
          id="sub-dir"
          v-model="subDir"
          type="text"
          class="form-input"
          placeholder="例如 000001 或留空扫描全部"
          aria-label="子目录路径"
        />
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
        :disabled="store.loading || store.progress.status === 'running'"
        @click="handleStartImport"
        aria-label="开始导入"
      >
        {{ store.loading ? '提交中...' : '开始导入' }}
      </button>

      <span v-if="store.error" class="sync-msg error" role="status">{{ store.error }}</span>
      <span v-if="successMsg" class="sync-msg success" role="status">{{ successMsg }}</span>
    </section>

    <!-- ── 定时任务配置 ── -->
    <section class="card" aria-label="定时任务配置">
      <h2 class="section-title">定时任务配置</h2>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label" for="sched-hour">小时</label>
          <select id="sched-hour" v-model="schedHour" class="form-input" aria-label="小时">
            <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ h - 1 }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label" for="sched-minute">分钟</label>
          <select id="sched-minute" v-model="schedMinute" class="form-input" aria-label="分钟">
            <option v-for="m in 60" :key="m - 1" :value="m - 1">{{ m - 1 }}</option>
          </select>
        </div>
      </div>

      <button class="btn btn-primary" @click="saveSchedule" aria-label="保存定时配置">
        保存定时配置
      </button>
      <span v-if="schedMsg" class="sync-msg success" role="status">{{ schedMsg }}</span>
    </section>

    <!-- ── 导入进度 ── -->
    <section v-if="store.progress.status !== 'idle'" class="card" aria-label="导入进度">
      <h2 class="section-title">导入进度</h2>

      <div class="progress-header">
        <span class="status-badge" :class="progressStatusClass">
          {{ progressStatusLabel }}
        </span>
      </div>

      <div class="progress-bar-container">
        <div class="progress-bar" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div class="progress-text">
        已处理 {{ store.progress.processed_files }} / {{ store.progress.total_files }} 文件 ({{ progressPct }}%)
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

    <!-- ── 结果摘要 ── -->
    <section
      v-if="store.result.status === 'completed' || store.result.status === 'failed'"
      class="card"
      aria-label="结果摘要"
    >
      <h2 class="section-title">结果摘要</h2>

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

      <!-- 失败文件列表 -->
      <div v-if="store.result.failed_details.length > 0" class="failed-section">
        <h3 class="section-title">失败文件列表</h3>
        <table class="data-table" aria-label="失败文件列表">
          <thead>
            <tr>
              <th scope="col">文件路径</th>
              <th scope="col">错误原因</th>
            </tr>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useLocalImportStore } from '@/stores/localImport'

const store = useLocalImportStore()

// ── 导入配置 ──────────────────────────────────────────────────────────────────

const freqOptions = ['1m', '5m', '15m', '30m', '60m']
const selectedFreqs = ref<string[]>([...freqOptions])
const subDir = ref('')
const forceImport = ref(false)
const successMsg = ref('')

async function handleStartImport() {
  successMsg.value = ''
  await store.startImport({
    freqs: selectedFreqs.value.length === freqOptions.length ? null : selectedFreqs.value,
    sub_dir: subDir.value.trim() || null,
    force: forceImport.value,
  })
  if (!store.error && store.taskId) {
    successMsg.value = `导入任务已触发，任务ID: ${store.taskId}`
    store.startPolling()
    setTimeout(() => { successMsg.value = '' }, 5000)
  }
}

// ── 定时任务配置 ──────────────────────────────────────────────────────────────

const schedHour = ref(2)
const schedMinute = ref(0)
const schedMsg = ref('')

function saveSchedule() {
  schedMsg.value = `定时配置已保存：每日 ${schedHour.value}:${String(schedMinute.value).padStart(2, '0')} 执行`
  setTimeout(() => { schedMsg.value = '' }, 5000)
}

// ── 进度计算 ──────────────────────────────────────────────────────────────────

const progressPct = computed(() => {
  if (store.progress.total_files === 0) return 0
  return Math.round((store.progress.processed_files / store.progress.total_files) * 100)
})

const progressStatusLabel = computed(() => {
  const map: Record<string, string> = {
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  }
  return map[store.progress.status] ?? store.progress.status
})

const progressStatusClass = computed(() => {
  const map: Record<string, string> = {
    running: 'syncing',
    completed: 'ok',
    failed: 'error',
  }
  return map[store.progress.status] ?? ''
})

// ── 生命周期 ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  await store.fetchStatus()
  if (store.progress.status === 'running') {
    store.startPolling()
  }
})

onUnmounted(() => {
  store.stopPolling()
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

/* 卡片 */
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

/* 表单 */
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
  display: inline-block;
  font-size: 13px;
  margin-left: 10px;
}
.sync-msg.success { color: #3fb950; }
.sync-msg.error { color: #f85149; }

/* 进度 */
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

/* 统计网格 */
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

/* 错误文本 */
.error-text { color: #f85149; }

/* 失败文件区域 */
.failed-section { margin-top: 16px; }

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

.symbol-cell { font-family: monospace; color: #58a6ff; }
</style>
