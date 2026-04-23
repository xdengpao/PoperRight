<template>
  <div class="tushare-preview-view">
    <TushareTabNav />
    <h1 class="page-title">Tushare 数据预览</h1>

    <div class="preview-layout">
      <!-- ── 左侧面板：分类选择器 ── -->
      <aside class="category-panel" aria-label="数据分类选择器">
        <div v-if="store.registryLoading" class="empty">加载接口列表...</div>
        <div v-else-if="categoryGroups.length === 0" class="empty">暂无接口数据</div>
        <template v-else>
          <div v-for="group in categoryGroups" :key="group.category" class="category-group">
            <h2 class="category-title">{{ categoryLabel(group.category) }}</h2>
            <div
              v-for="sub in group.subcategories"
              :key="sub.subcategory"
              class="subcategory-group"
            >
              <button
                class="subcategory-header"
                @click="toggleSubcategory(sub.subcategory)"
                :aria-expanded="expandedSubcategories.has(sub.subcategory)"
              >
                <span
                  class="subcategory-arrow"
                  :class="{ expanded: expandedSubcategories.has(sub.subcategory) }"
                >▸</span>
                <span class="subcategory-name">{{ sub.subcategory }}</span>
                <span class="subcategory-count">{{ sub.apis.length }}</span>
              </button>
              <div v-if="expandedSubcategories.has(sub.subcategory)" class="api-list">
                <button
                  v-for="api in sub.apis"
                  :key="api.api_name"
                  class="api-item-btn"
                  :class="{ active: store.selectedApiName === api.api_name }"
                  @click="selectApi(api.api_name)"
                >
                  <span class="api-name">{{ api.api_name }}</span>
                  <span class="api-label">{{ api.label }}</span>
                </button>
              </div>
            </div>
          </div>
        </template>
      </aside>

      <!-- ── 右侧主区域 ── -->
      <main class="main-panel">
        <!-- 未选择接口时的提示 -->
        <div v-if="!store.selectedApiName" class="empty-main">
          <span class="empty-icon">📋</span>
          <p>请从左侧选择一个 API 接口以预览数据</p>
        </div>

        <template v-else>
          <!-- 查询条件栏 -->
          <section class="card query-bar" aria-label="查询条件">
            <div class="query-row">
              <!-- 导入时间范围 -->
              <div class="filter-group">
                <label class="filter-label">导入时间</label>
                <div class="filter-controls">
                  <div class="shortcut-btns">
                    <button
                      v-for="shortcut in importTimeShortcuts"
                      :key="shortcut.label"
                      class="shortcut-btn"
                      :class="{ active: activeImportShortcut === shortcut.label }"
                      @click="applyImportTimeShortcut(shortcut)"
                    >{{ shortcut.label }}</button>
                  </div>
                  <div class="date-range-inputs">
                    <input
                      type="datetime-local"
                      class="form-input"
                      :value="store.filters.importTimeStart ?? ''"
                      @input="setImportTimeStart(($event.target as HTMLInputElement).value)"
                      aria-label="导入开始时间"
                    />
                    <span class="date-sep">至</span>
                    <input
                      type="datetime-local"
                      class="form-input"
                      :value="store.filters.importTimeEnd ?? ''"
                      @input="setImportTimeEnd(($event.target as HTMLInputElement).value)"
                      aria-label="导入结束时间"
                    />
                  </div>
                </div>
              </div>

              <!-- 数据时间范围 -->
              <div class="filter-group" :class="{ disabled: !hasTimeField }">
                <label class="filter-label">
                  数据时间
                  <span
                    v-if="!hasTimeField"
                    class="filter-tip"
                    title="该接口数据表无时间字段，无法按数据时间筛选"
                  >ⓘ 无时间字段</span>
                </label>
                <div class="date-range-inputs">
                  <input
                    type="date"
                    class="form-input"
                    :disabled="!hasTimeField"
                    :value="store.filters.dataTimeStart ?? ''"
                    @input="setDataTimeStart(($event.target as HTMLInputElement).value)"
                    aria-label="数据开始时间"
                  />
                  <span class="date-sep">至</span>
                  <input
                    type="date"
                    class="form-input"
                    :disabled="!hasTimeField"
                    :value="store.filters.dataTimeEnd ?? ''"
                    @input="setDataTimeEnd(($event.target as HTMLInputElement).value)"
                    aria-label="数据结束时间"
                  />
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="query-actions">
                <button
                  class="btn btn-primary"
                  :disabled="store.previewLoading"
                  @click="handleQuery"
                >查询</button>
                <button
                  class="btn btn-secondary"
                  :disabled="store.previewLoading"
                  @click="handleIncrementalQuery"
                >查看增量数据</button>
                <button
                  class="btn btn-secondary"
                  :disabled="!store.selectedApiName || store.integrityLoading"
                  @click="handleCheckIntegrity"
                >{{ store.integrityLoading ? '校验中...' : '完整性校验' }}</button>
                <button
                  class="btn btn-danger"
                  :disabled="!store.selectedApiName || store.deleteLoading"
                  @click="handleDeleteData"
                  title="删除数据时间范围或导入时间范围内的记录"
                >{{ store.deleteLoading ? '删除中...' : '删除' }}</button>
              </div>
            </div>
          </section>

          <!-- 完整性校验 Loading 反馈 -->
          <section
            v-if="store.integrityLoading"
            class="card integrity-loading-section"
            aria-label="正在校验数据完整性"
          >
            <div class="integrity-loading-content">
              <span class="integrity-spinner" aria-hidden="true"></span>
              <span class="integrity-loading-text">正在校验数据完整性...</span>
            </div>
          </section>

          <!-- 完整性校验结果（可折叠卡片） -->
          <section
            v-else-if="store.integrityReport"
            class="card integrity-report-section"
            aria-label="完整性校验结果"
          >
            <div class="integrity-header">
              <span class="integrity-title">🔍 完整性校验结果</span>
              <button class="integrity-close-btn" @click="store.clearIntegrityReport()" aria-label="关闭校验结果">✕</button>
            </div>
            <!-- 数据完整时绿色提示 -->
            <div v-if="store.integrityReport.missing_count === 0" class="integrity-complete">
              ✅ 数据完整，无缺失
            </div>
            <!-- 有缺失时红色高亮摘要 -->
            <template v-else>
              <div class="integrity-summary integrity-missing">
                <div class="integrity-summary-row">
                  <span class="integrity-stat-label">校验类型：</span>
                  <span>{{ integrityCheckTypeLabel }}</span>
                  <span class="integrity-stat-label">预期数量：</span>
                  <span>{{ store.integrityReport.expected_count.toLocaleString() }}</span>
                  <span class="integrity-stat-label">实际数量：</span>
                  <span>{{ store.integrityReport.actual_count.toLocaleString() }}</span>
                  <span class="integrity-stat-label">缺失数量：</span>
                  <span class="integrity-missing-count">{{ store.integrityReport.missing_count.toLocaleString() }}</span>
                  <span class="integrity-stat-label">完整率：</span>
                  <span>{{ (store.integrityReport.completeness_rate * 100).toFixed(2) }}%</span>
                </div>
              </div>
              <!-- 缺失详情列表 -->
              <div class="integrity-details">
                <div class="integrity-details-header">
                  <span class="integrity-details-title">缺失详情</span>
                  <button
                    v-if="store.integrityReport.missing_items.length > 50"
                    class="integrity-expand-btn"
                    @click="integrityDetailsExpanded = !integrityDetailsExpanded"
                  >{{ integrityDetailsExpanded ? '收起' : `展开全部 (${store.integrityReport.missing_items.length})` }}</button>
                </div>
                <div class="integrity-missing-list">
                  <span
                    v-for="item in visibleMissingItems"
                    :key="item"
                    class="integrity-missing-item"
                  >{{ item }}</span>
                </div>
              </div>
            </template>
            <!-- 摘要信息（数据完整时也显示） -->
            <div v-if="store.integrityReport.missing_count === 0" class="integrity-summary">
              <div class="integrity-summary-row">
                <span class="integrity-stat-label">校验类型：</span>
                <span>{{ integrityCheckTypeLabel }}</span>
                <span class="integrity-stat-label">预期数量：</span>
                <span>{{ store.integrityReport.expected_count.toLocaleString() }}</span>
                <span class="integrity-stat-label">实际数量：</span>
                <span>{{ store.integrityReport.actual_count.toLocaleString() }}</span>
                <span class="integrity-stat-label">完整率：</span>
                <span>{{ (store.integrityReport.completeness_rate * 100).toFixed(2) }}%</span>
              </div>
            </div>
            <!-- 附加提示信息 -->
            <div v-if="store.integrityReport.message" class="integrity-message">
              ⓘ {{ store.integrityReport.message }}
            </div>
          </section>

          <!-- 导入记录列表（可折叠） -->
          <section class="card import-logs-section" aria-label="导入记录">
            <button class="section-toggle" @click="toggleImportLogs" :aria-expanded="importLogsExpanded">
              <span class="subcategory-arrow" :class="{ expanded: importLogsExpanded }">▸</span>
              <span class="section-title-text">📋 导入记录</span>
              <span class="section-count">{{ store.importLogs.length }} 条</span>
            </button>
            <div v-if="importLogsExpanded" class="import-logs-body">
              <div v-if="store.importLogsLoading" class="empty">加载导入记录...</div>
              <div v-else-if="store.importLogs.length === 0" class="empty">暂无导入记录</div>
              <div v-else class="import-log-list">
                <button
                  v-for="log in store.importLogs"
                  :key="log.id"
                  class="import-log-item"
                  :class="{ active: store.filters.importLogId === log.id }"
                  @click="selectImportLog(log)"
                >
                  <span class="log-time">{{ formatTime(log.started_at) }}</span>
                  <span class="status-badge" :class="getStatusColor(log.status)">{{ statusLabel(log.status) }}</span>
                  <span class="log-count">{{ log.record_count.toLocaleString() }} 条</span>
                  <span v-if="log.params_json" class="log-params">{{ formatParams(log.params_json) }}</span>
                </button>
              </div>
            </div>
          </section>

          <!-- 增量查询信息 -->
          <div
            v-if="store.previewData?.incremental_info"
            class="card incremental-info"
            aria-label="增量查询信息"
          >
            <div class="incremental-row">
              <span class="incremental-label">导入时间:</span>
              <span>{{ formatTime(store.previewData.incremental_info.import_time) }}</span>
              <span class="incremental-label">记录数:</span>
              <span>{{ store.previewData.incremental_info.record_count.toLocaleString() }} 条</span>
              <span class="incremental-label">状态:</span>
              <span class="status-badge" :class="getStatusColor(store.previewData.incremental_info.status)">
                {{ statusLabel(store.previewData.incremental_info.status) }}
              </span>
              <span class="incremental-label">参数:</span>
              <span class="incremental-params">{{ store.previewData.incremental_info.params_summary }}</span>
            </div>
          </div>

          <!-- 无成功导入记录提示 -->
          <div
            v-if="showNoSuccessMessage"
            class="card empty-notice"
          >
            该接口暂无成功导入记录
          </div>

          <!-- 展示模式切换 -->
          <div class="display-mode-bar">
            <button
              v-for="mode in displayModes"
              :key="mode.value"
              class="mode-btn"
              :class="{ active: store.displayMode === mode.value }"
              @click="store.setDisplayMode(mode.value)"
            >{{ mode.label }}</button>
          </div>

          <!-- 图表区域 -->
          <PreviewChart
            v-if="showChart"
            :chart-type="chartDisplayType"
            :rows="chartDisplayRows"
            :time-field="chartDisplayTimeField"
            :columns="chartDisplayColumns"
            :selected-columns="store.selectedChartColumns"
            @update:selected-columns="store.setSelectedChartColumns"
          />

          <!-- 数据表格区域 -->
          <PreviewTable
            v-if="showTable"
            :columns="store.previewData?.columns ?? []"
            :rows="store.previewData?.rows ?? []"
            :total="store.previewData?.total ?? 0"
            :page="store.previewData?.page ?? 1"
            :page-size="store.previewData?.page_size ?? 50"
            :loading="store.previewLoading"
            @update:page="handlePageChange"
            @update:page-size="handlePageSizeChange"
          />
        </template>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * TusharePreviewView — Tushare 数据预览主页面
 *
 * 提供已导入 Tushare 数据的预览功能，包括：
 * - 左侧分类选择器（按 category → subcategory 分组）
 * - 右侧查询条件栏（导入时间、数据时间、增量查询、完整性校验）
 * - 完整性校验结果展示（可折叠卡片）
 * - 导入记录列表（可折叠，点击查看该次导入数据）
 * - 图表 + 表格展示（支持模式切换，图表使用独立数据源）
 *
 * 需求: 1.1-1.6, 2.1-2.5, 3.1-3.5, 4.1-4.5, 5.1-5.4, 6.1-6.4, 7.1-7.5, 9.1, 9.5, 10.1-10.6, 11.1-11.5
 */
import { ref, reactive, computed, onMounted } from 'vue'
import TushareTabNav from '@/components/TushareTabNav.vue'
import PreviewChart from '@/components/PreviewChart.vue'
import PreviewTable from '@/components/PreviewTable.vue'
import {
  useTusharePreviewStore,
  groupRegistryByCategory,
  getStatusColor,
} from '@/stores/tusharePreview'
import type { ImportLogItem, DisplayMode } from '@/stores/tusharePreview'

const store = useTusharePreviewStore()

// ── 分类选择器状态 ────────────────────────────────────────────────────────────

const expandedSubcategories = reactive(new Set<string>())
const importLogsExpanded = ref(true)
const activeImportShortcut = ref<string | null>(null)
/** 完整性校验缺失详情是否展开（超过 50 条时默认折叠） */
const integrityDetailsExpanded = ref(false)

// ── 分类标签映射 ──────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  stock_data: '📈 股票数据',
  index_data: '📊 指数数据',
}

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category
}

// ── 计算属性 ──────────────────────────────────────────────────────────────────

/** 按 category → subcategory 分组的注册表数据 */
const categoryGroups = computed(() => groupRegistryByCategory(store.registry))

/** 当前选中接口是否有时间字段 */
const hasTimeField = computed(() => {
  return store.previewData?.time_field != null
})

/** 是否显示图表 */
const showChart = computed(() => {
  return (store.displayMode === 'chart' || store.displayMode === 'both')
    && store.previewData != null
})

/** 是否显示表格 */
const showTable = computed(() => {
  return store.displayMode === 'table' || store.displayMode === 'both'
})

/** 是否显示无成功导入记录提示 */
const showNoSuccessMessage = computed(() => {
  if (!store.selectedApiName) return false
  if (store.importLogsLoading) return false
  // 检查是否有成功的导入记录
  const hasSuccess = store.importLogs.some(log => log.status === 'completed')
  return !hasSuccess && store.importLogs.length >= 0 && !store.importLogsLoading
    && store.previewData?.incremental_info === undefined
    && store.filters.incremental
})

/** 完整性校验类型标签 */
const integrityCheckTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    time_series: '时序数据校验',
    code_based: '代码集合校验',
    unsupported: '不支持校验',
  }
  return labels[store.integrityReport?.check_type ?? ''] ?? store.integrityReport?.check_type ?? ''
})

/** 可见的缺失项列表（超过 50 条时默认只显示前 50 条） */
const visibleMissingItems = computed(() => {
  const items = store.integrityReport?.missing_items ?? []
  if (items.length <= 50 || integrityDetailsExpanded.value) return items
  return items.slice(0, 50)
})

/** 图表使用的 chart_type（优先使用 chartData） */
const chartDisplayType = computed(() => {
  return store.chartData?.chart_type ?? store.previewData?.chart_type ?? null
})

/** 图表使用的数据行（优先使用 chartData） */
const chartDisplayRows = computed(() => {
  return store.chartData?.rows ?? store.previewData?.rows ?? []
})

/** 图表使用的时间字段（优先使用 chartData） */
const chartDisplayTimeField = computed(() => {
  return store.chartData?.time_field ?? store.previewData?.time_field ?? null
})

/** 图表使用的列信息（优先使用 chartData） */
const chartDisplayColumns = computed(() => {
  return store.chartData?.columns ?? store.previewData?.columns ?? []
})

// ── 展示模式 ──────────────────────────────────────────────────────────────────

const displayModes: { value: DisplayMode; label: string }[] = [
  { value: 'table', label: '仅表格' },
  { value: 'chart', label: '仅图表' },
  { value: 'both', label: '图表+表格' },
]

// ── 导入时间快捷选项 ──────────────────────────────────────────────────────────

interface TimeShortcut {
  label: string
  getRange: () => { start: string; end: string }
}

const importTimeShortcuts: TimeShortcut[] = [
  {
    label: '今天',
    getRange: () => {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      return { start: toLocalDatetime(today), end: toLocalDatetime(new Date()) }
    },
  },
  {
    label: '最近3天',
    getRange: () => {
      const end = new Date()
      const start = new Date(Date.now() - 3 * 86400000)
      start.setHours(0, 0, 0, 0)
      return { start: toLocalDatetime(start), end: toLocalDatetime(end) }
    },
  },
  {
    label: '最近7天',
    getRange: () => {
      const end = new Date()
      const start = new Date(Date.now() - 7 * 86400000)
      start.setHours(0, 0, 0, 0)
      return { start: toLocalDatetime(start), end: toLocalDatetime(end) }
    },
  },
  {
    label: '最近30天',
    getRange: () => {
      const end = new Date()
      const start = new Date(Date.now() - 30 * 86400000)
      start.setHours(0, 0, 0, 0)
      return { start: toLocalDatetime(start), end: toLocalDatetime(end) }
    },
  },
]

// ── 工具函数 ──────────────────────────────────────────────────────────────────

/** 将 Date 转为 datetime-local 输入框格式 */
function toLocalDatetime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 格式化 ISO 时间字符串 */
function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

/** 导入状态标签 */
function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    completed: '成功',
    failed: '失败',
    running: '运行中',
    pending: '等待中',
    stopped: '已停止',
  }
  return labels[status] ?? status
}

/** 格式化导入参数摘要 */
function formatParams(params: Record<string, unknown> | null): string {
  if (!params) return ''
  const parts: string[] = []
  if (params.start_date && params.end_date) {
    parts.push(`${params.start_date} ~ ${params.end_date}`)
  } else if (params.trade_date) {
    parts.push(String(params.trade_date))
  }
  if (params.ts_code) {
    parts.push(String(params.ts_code))
  }
  return parts.join(' | ')
}

// ── 交互方法 ──────────────────────────────────────────────────────────────────

function toggleSubcategory(sub: string): void {
  if (expandedSubcategories.has(sub)) expandedSubcategories.delete(sub)
  else expandedSubcategories.add(sub)
}

function toggleImportLogs(): void {
  importLogsExpanded.value = !importLogsExpanded.value
}

/** 选择 API 接口 */
function selectApi(apiName: string): void {
  activeImportShortcut.value = null
  store.setSelectedApi(apiName)
}

/** 应用导入时间快捷选项 */
function applyImportTimeShortcut(shortcut: TimeShortcut): void {
  activeImportShortcut.value = shortcut.label
  const { start, end } = shortcut.getRange()
  store.filters.importTimeStart = start
  store.filters.importTimeEnd = end
}

/** 设置导入开始时间 */
function setImportTimeStart(value: string): void {
  activeImportShortcut.value = null
  store.filters.importTimeStart = value || null
}

/** 设置导入结束时间 */
function setImportTimeEnd(value: string): void {
  activeImportShortcut.value = null
  store.filters.importTimeEnd = value || null
}

/** 设置数据开始时间 */
function setDataTimeStart(value: string): void {
  store.filters.dataTimeStart = value || null
}

/** 设置数据结束时间 */
function setDataTimeEnd(value: string): void {
  store.filters.dataTimeEnd = value || null
}

/** 执行查询（并行发送表格分页请求和图表数据请求） */
function handleQuery(): void {
  if (!store.selectedApiName) return
  store.filters.incremental = false
  store.filters.importLogId = null
  store.filters.page = 1
  // 并行请求表格数据和图表数据
  store.fetchPreviewData(store.selectedApiName, store.filters)
  store.fetchChartData(store.selectedApiName)
}

/** 执行增量查询 */
function handleIncrementalQuery(): void {
  if (!store.selectedApiName) return
  store.filters.incremental = true
  store.filters.importLogId = null
  store.filters.page = 1
  store.fetchPreviewData(store.selectedApiName, store.filters)
}

/** 执行完整性校验 */
function handleCheckIntegrity(): void {
  if (!store.selectedApiName) return
  integrityDetailsExpanded.value = false
  const timeRange: { start?: string; end?: string } = {}
  if (store.filters.dataTimeStart) timeRange.start = store.filters.dataTimeStart
  if (store.filters.dataTimeEnd) timeRange.end = store.filters.dataTimeEnd
  store.checkIntegrity(store.selectedApiName, Object.keys(timeRange).length > 0 ? timeRange : undefined)
}

/** 删除数据时间范围或导入时间范围内的记录 */
async function handleDeleteData(): Promise<void> {
  if (!store.selectedApiName) return
  const start = store.filters.dataTimeStart
  const end = store.filters.dataTimeEnd
  const importStart = store.filters.importTimeStart
  const importEnd = store.filters.importTimeEnd

  let confirmMsg: string
  if (!start && !end && !importStart && !importEnd) {
    confirmMsg = `确认清空 ${store.selectedApiName} 的全部数据？\n此操作不可撤销。`
  } else {
    const rangeParts: string[] = []
    if (start || end) {
      rangeParts.push(`数据时间 ${[start, end].filter(Boolean).join(' ~ ')}`)
    }
    if (importStart || importEnd) {
      rangeParts.push(`导入时间 ${[importStart, importEnd].filter(Boolean).join(' ~ ')}`)
    }
    confirmMsg = `确认删除 ${store.selectedApiName} 在${rangeParts.join('，')}范围内的所有记录？\n此操作不可撤销。`
  }

  if (!window.confirm(confirmMsg)) return

  const result = await store.deleteData(
    store.selectedApiName,
    start,
    end,
    importStart,
    importEnd,
  )
  if (result) {
    window.alert(`已删除 ${result.deleted_count.toLocaleString()} 条记录`)
  } else {
    window.alert('删除失败，请查看控制台日志')
  }
}

/** 选择某条导入记录查看数据 */
function selectImportLog(log: ImportLogItem): void {
  if (!store.selectedApiName) return
  store.filters.importLogId = log.id
  store.filters.incremental = false
  store.filters.page = 1
  store.fetchPreviewData(store.selectedApiName, store.filters)
}

/** 分页切换 */
function handlePageChange(page: number): void {
  if (!store.selectedApiName) return
  store.filters.page = page
  store.fetchPreviewData(store.selectedApiName, store.filters)
}

/** 每页条数切换 */
function handlePageSizeChange(pageSize: number): void {
  if (!store.selectedApiName) return
  store.filters.pageSize = pageSize
  store.filters.page = 1
  store.fetchPreviewData(store.selectedApiName, store.filters)
}

// ── 生命周期 ──────────────────────────────────────────────────────────────────

onMounted(() => {
  store.fetchRegistry()
})
</script>

<style scoped>
.tushare-preview-view { max-width: 1400px; }

.page-title {
  font-size: 20px; font-weight: 600; color: #e6edf3; margin: 0 0 20px;
}

/* ── 布局 ── */
.preview-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

/* ── 左侧分类面板 ── */
.category-panel {
  width: 280px;
  min-width: 280px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 12px;
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  position: sticky;
  top: 20px;
}

.category-group {
  margin-bottom: 8px;
}

.category-title {
  font-size: 14px;
  font-weight: 600;
  color: #e6edf3;
  margin: 0 0 6px;
  padding: 6px 4px;
  border-bottom: 1px solid #21262d;
}

.subcategory-group {
  border-bottom: 1px solid #21262d;
}
.subcategory-group:last-child { border-bottom: none; }

.subcategory-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 7px 4px;
  background: none;
  border: none;
  color: #e6edf3;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  text-align: left;
}
.subcategory-header:hover { background: #1f2937; border-radius: 4px; }

.subcategory-arrow {
  font-size: 11px;
  color: #484f58;
  transition: transform 0.2s;
  display: inline-block;
}
.subcategory-arrow.expanded { transform: rotate(90deg); }

.subcategory-name { font-weight: 500; flex: 1; }

.subcategory-count {
  font-size: 11px;
  color: #484f58;
  background: #21262d;
  padding: 1px 6px;
  border-radius: 8px;
}

.api-list {
  padding: 2px 0 4px 12px;
}

.api-item-btn {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 6px 8px;
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.15s;
}
.api-item-btn:hover { background: #1f2937; }
.api-item-btn.active { background: #1a2a3a; border-left: 2px solid #1f6feb; }

.api-name {
  font-family: monospace;
  font-size: 12px;
  color: #58a6ff;
  font-weight: 500;
}
.api-label {
  font-size: 11px;
  color: #8b949e;
}

/* ── 右侧主区域 ── */
.main-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #484f58;
  font-size: 14px;
  text-align: center;
}
.empty-icon { font-size: 40px; margin-bottom: 12px; }

/* ── 卡片 ── */
.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px;
}

.empty {
  text-align: center;
  color: #484f58;
  padding: 20px;
  font-size: 13px;
}

/* ── 查询条件栏 ── */
.query-bar { padding: 14px 16px; }

.query-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.filter-group.disabled { opacity: 0.5; }

.filter-label {
  font-size: 12px;
  color: #8b949e;
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-tip {
  font-size: 11px;
  color: #d29922;
  cursor: help;
}

.filter-controls {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.shortcut-btns {
  display: flex;
  gap: 4px;
}

.shortcut-btn {
  padding: 3px 10px;
  font-size: 12px;
  color: #8b949e;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.shortcut-btn:hover { color: #e6edf3; border-color: #8b949e; }
.shortcut-btn.active { color: #e6edf3; background: #1f6feb; border-color: #1f6feb; }

.date-range-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}
.date-sep { color: #484f58; font-size: 13px; }

.form-input {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 13px;
  box-sizing: border-box;
}
.form-input:focus { border-color: #58a6ff; outline: none; }
.form-input:disabled { opacity: 0.5; cursor: not-allowed; }

.query-actions {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

/* ── 按钮 ── */
.btn {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  border: none;
  font-family: inherit;
  transition: background 0.15s;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #1f6feb; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #388bfd; }
.btn-secondary { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }
.btn-secondary:hover:not(:disabled) { border-color: #8b949e; }
.btn-danger { background: #da3633; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #f85149; }

/* ── 导入记录区域 ── */
.import-logs-section { padding: 0; }

.section-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 12px 16px;
  background: none;
  border: none;
  color: #e6edf3;
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
  text-align: left;
}
.section-toggle:hover { background: #1c2128; border-radius: 8px; }

.section-title-text { font-weight: 600; font-size: 14px; }
.section-count { margin-left: auto; font-size: 12px; color: #484f58; }

.import-logs-body {
  padding: 0 16px 12px;
  border-top: 1px solid #21262d;
}

.import-log-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.import-log-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  color: #e6edf3;
  text-align: left;
  width: 100%;
  transition: border-color 0.15s, background 0.15s;
}
.import-log-item:hover { border-color: #30363d; background: #1c2128; }
.import-log-item.active { border-color: #1f6feb; background: #1a2a3a; }

.log-time { color: #8b949e; font-size: 12px; white-space: nowrap; }
.log-count { color: #8b949e; font-size: 12px; white-space: nowrap; }
.log-params { color: #484f58; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }

/* ── 状态徽章 ── */
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.status-green { background: #1a3a1a; color: #3fb950; }
.status-red { background: #3a1a1a; color: #f85149; }
.status-blue { background: #1a2a3a; color: #58a6ff; }
.status-gray { background: #21262d; color: #8b949e; }
.status-default { background: #21262d; color: #8b949e; }

/* ── 增量查询信息 ── */
.incremental-info { padding: 10px 16px; }

.incremental-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #e6edf3;
}

.incremental-label {
  color: #8b949e;
  font-weight: 500;
}

.incremental-params {
  color: #58a6ff;
  font-family: monospace;
  font-size: 12px;
}

/* ── 无成功导入记录提示 ── */
.empty-notice {
  text-align: center;
  color: #d29922;
  font-size: 14px;
  padding: 24px;
}

/* ── 展示模式切换 ── */
.display-mode-bar {
  display: flex;
  gap: 4px;
}

.mode-btn {
  padding: 5px 14px;
  font-size: 13px;
  color: #8b949e;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.mode-btn:hover { color: #e6edf3; border-color: #8b949e; }
.mode-btn.active { color: #e6edf3; background: #1f6feb; border-color: #1f6feb; }

/* ── 完整性校验 Loading ── */
.integrity-loading-section {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}

.integrity-loading-content {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #8b949e;
  font-size: 14px;
}

.integrity-spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid #30363d;
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: integrity-spin 0.8s linear infinite;
}

@keyframes integrity-spin {
  to { transform: rotate(360deg); }
}

.integrity-loading-text {
  color: #8b949e;
}

/* ── 完整性校验结果 ── */
.integrity-report-section { padding: 0; }

.integrity-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #21262d;
}

.integrity-title {
  font-weight: 600;
  font-size: 14px;
  color: #e6edf3;
}

.integrity-close-btn {
  background: none;
  border: none;
  color: #484f58;
  cursor: pointer;
  font-size: 16px;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: inherit;
  transition: color 0.15s, background 0.15s;
}
.integrity-close-btn:hover { color: #e6edf3; background: #21262d; }

.integrity-complete {
  padding: 16px;
  color: #3fb950;
  font-size: 14px;
  font-weight: 500;
}

.integrity-summary {
  padding: 12px 16px;
}

.integrity-summary.integrity-missing {
  background: #3a1a1a;
  border-bottom: 1px solid #5a2020;
}

.integrity-summary-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #e6edf3;
}

.integrity-stat-label {
  color: #8b949e;
  font-weight: 500;
}

.integrity-missing-count {
  color: #f85149;
  font-weight: 600;
}

.integrity-details {
  padding: 12px 16px;
  border-top: 1px solid #21262d;
}

.integrity-details-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.integrity-details-title {
  font-size: 13px;
  font-weight: 500;
  color: #8b949e;
}

.integrity-expand-btn {
  background: none;
  border: none;
  color: #58a6ff;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  padding: 2px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}
.integrity-expand-btn:hover { background: #1a2a3a; }

.integrity-missing-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.integrity-missing-item {
  display: inline-block;
  padding: 2px 8px;
  background: #3a1a1a;
  color: #f85149;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}

.integrity-message {
  padding: 8px 16px 12px;
  font-size: 12px;
  color: #d29922;
}
</style>
