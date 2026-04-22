<template>
  <div class="preview-table-wrapper">
    <!-- 总记录数 -->
    <div class="table-summary">
      <span class="total-count">共 {{ total.toLocaleString() }} 条记录</span>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="table-loading">
      <span class="loading-spinner"></span>
      <span class="loading-text">加载中...</span>
    </div>

    <!-- 空数据提示 -->
    <div v-else-if="rows.length === 0" class="table-empty">
      暂无数据
    </div>

    <!-- 数据表格 -->
    <div v-else class="table-scroll-container">
      <table class="data-table" aria-label="数据预览表格">
        <thead>
          <tr>
            <th v-for="col in columns" :key="col.name" scope="col">{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx">
            <td v-for="col in columns" :key="col.name" :class="cellClass(col.type)">
              {{ formatCell(row[col.name], col.type, col.name) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页控件 -->
    <div v-if="totalPages > 0" class="pagination-bar">
      <div class="page-size-selector">
        <span class="page-size-label">每页</span>
        <button
          v-for="size in pageSizeOptions"
          :key="size"
          class="page-size-btn"
          :class="{ active: pageSize === size }"
          @click="changePageSize(size)"
        >
          {{ size }}
        </button>
        <span class="page-size-label">条</span>
      </div>

      <nav class="page-nav" aria-label="分页导航">
        <button
          class="page-btn"
          :disabled="page <= 1"
          aria-label="第一页"
          @click="goToPage(1)"
        >
          «
        </button>
        <button
          class="page-btn"
          :disabled="page <= 1"
          aria-label="上一页"
          @click="goToPage(page - 1)"
        >
          ‹
        </button>

        <button
          v-for="p in visiblePages"
          :key="p"
          class="page-btn"
          :class="{ active: p === page }"
          :aria-current="p === page ? 'page' : undefined"
          @click="goToPage(p)"
        >
          {{ p }}
        </button>

        <button
          class="page-btn"
          :disabled="page >= totalPages"
          aria-label="下一页"
          @click="goToPage(page + 1)"
        >
          ›
        </button>
        <button
          class="page-btn"
          :disabled="page >= totalPages"
          aria-label="最后一页"
          @click="goToPage(totalPages)"
        >
          »
        </button>
      </nav>
    </div>
  </div>
</template>

<script lang="ts">
/**
 * PreviewTable 导出的纯函数与常量
 *
 * 数值精度规则映射、字段精度获取函数、单元格格式化函数。
 * 独立于组件实例，便于单元测试和属性测试导入。
 *
 * 需求: 6.1-6.8, 7.1-7.4
 */

/**
 * 数值精度规则映射
 * 按优先级定义字段名正则 → 小数位数映射
 */
export const PRECISION_RULES: Array<{ pattern: RegExp; decimals: number }> = [
  // 成交量类（0 位小数）— 优先匹配
  { pattern: /^(vol|volume)$/i, decimals: 0 },
  // 价格类（2 位小数）
  { pattern: /(open|high|low|close|price|avg_price|amount)/i, decimals: 2 },
  // 涨跌幅类（2 位小数）
  { pattern: /(pct_chg|change)/i, decimals: 2 },
  // 换手率类（2 位小数）
  { pattern: /turnover_rate/i, decimals: 2 },
  // 市值类（2 位小数）
  { pattern: /(total_mv|circ_mv|market_cap)/i, decimals: 2 },
  // 市盈率/市净率类（2 位小数）
  { pattern: /^(pe|pb|pe_ttm|ps|ps_ttm)(_|$)/i, decimals: 2 },
]

/** 默认精度（未匹配任何规则时使用） */
export const DEFAULT_PRECISION = 4

/**
 * 根据字段名获取显示精度（纯函数）
 *
 * 遍历 PRECISION_RULES，返回第一个匹配的 decimals，
 * 无匹配返回 DEFAULT_PRECISION。
 */
export function getFieldPrecision(fieldName: string): number {
  for (const rule of PRECISION_RULES) {
    if (rule.pattern.test(fieldName)) {
      return rule.decimals
    }
  }
  return DEFAULT_PRECISION
}

/**
 * 格式化单元格显示值（纯函数）
 *
 * - null/undefined → '—'
 * - 数值型 + 整数 → 直接显示整数（大数值添加千分位）
 * - 数值型 + 浮点数 → 按字段精度 toFixed，大数值添加千分位
 * - 其他 → String(value)
 */
export function formatCell(value: unknown, type: string, fieldName: string): string {
  if (value === null || value === undefined) return '—'
  if (type === 'number' && typeof value === 'number') {
    // 整数值直接显示为整数（不添加小数位）
    if (Number.isInteger(value)) {
      if (Math.abs(value) >= 10000) {
        return value.toLocaleString('en-US', { useGrouping: true, maximumFractionDigits: 0 })
      }
      return String(value)
    }
    // 浮点数按字段精度格式化
    const precision = getFieldPrecision(fieldName)
    const formatted = value.toFixed(precision)
    // 大数值（|value| >= 10000）添加千分位分隔符
    if (Math.abs(value) >= 10000) {
      const [intPart, decPart] = formatted.split('.')
      const withCommas = Number(intPart).toLocaleString('en-US')
      return decPart ? `${withCommas}.${decPart}` : withCommas
    }
    return formatted
  }
  return String(value)
}
</script>

<script setup lang="ts">
/**
 * PreviewTable - 数据预览表格组件
 *
 * 根据 columns 动态生成表头，支持分页控件（20/50/100 条切换、页码导航）。
 * 表格上方显示总记录数，空数据时显示「暂无数据」提示。
 *
 * 需求: 3.1-3.5, 6.1-6.8, 7.1-7.4
 */
import { computed } from 'vue'
import type { ColumnInfo } from '@/stores/tusharePreview'

const props = defineProps<{
  columns: ColumnInfo[]
  rows: Record<string, unknown>[]
  total: number
  page: number
  pageSize: number
  loading: boolean
}>()

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()

const pageSizeOptions = [20, 50, 100]

const totalPages = computed(() => {
  if (props.total <= 0 || props.pageSize <= 0) return 0
  return Math.ceil(props.total / props.pageSize)
})

/**
 * 计算可见页码列表，最多显示 7 个页码按钮，
 * 当前页居中，两端自动截断。
 */
const visiblePages = computed(() => {
  const total = totalPages.value
  if (total <= 0) return []
  const current = props.page
  const maxVisible = 7

  if (total <= maxVisible) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const half = Math.floor(maxVisible / 2)
  let start = current - half
  let end = current + half

  if (start < 1) {
    start = 1
    end = maxVisible
  }
  if (end > total) {
    end = total
    start = total - maxVisible + 1
  }

  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})

function goToPage(p: number): void {
  const clamped = Math.max(1, Math.min(p, totalPages.value))
  if (clamped !== props.page) {
    emit('update:page', clamped)
  }
}

function changePageSize(size: number): void {
  if (size !== props.pageSize) {
    emit('update:pageSize', size)
    // 切换每页条数时回到第一页
    emit('update:page', 1)
  }
}

function cellClass(type: string): string {
  if (type === 'number') return 'cell-number'
  if (type === 'date' || type === 'datetime') return 'cell-date'
  return ''
}
</script>

<style scoped>
.preview-table-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── 总记录数 ── */
.table-summary {
  display: flex;
  align-items: center;
  gap: 12px;
}

.total-count {
  font-size: 13px;
  color: #8b949e;
}

/* ── 加载状态 ── */
.table-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: #8b949e;
  font-size: 14px;
}

.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #30363d;
  border-top-color: #58a6ff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: #8b949e;
}

/* ── 空数据 ── */
.table-empty {
  text-align: center;
  color: #484f58;
  padding: 40px;
  font-size: 14px;
}

/* ── 表格滚动容器 ── */
.table-scroll-container {
  overflow-x: auto;
  border: 1px solid #21262d;
  border-radius: 6px;
}

/* ── 数据表格 ── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 600px;
}

.data-table th,
.data-table td {
  padding: 8px 14px;
  text-align: left;
  border-bottom: 1px solid #21262d;
  font-size: 13px;
  white-space: nowrap;
}

.data-table th {
  color: #8b949e;
  font-weight: 500;
  background: #161b22;
  position: sticky;
  top: 0;
  z-index: 1;
}

.data-table td {
  color: #e6edf3;
}

.data-table tbody tr:hover {
  background: #1c2128;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.cell-number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.cell-date {
  font-family: monospace;
  color: #8b949e;
}

/* ── 分页栏 ── */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 4px;
}

/* ── 每页条数选择 ── */
.page-size-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}

.page-size-label {
  font-size: 13px;
  color: #8b949e;
}

.page-size-btn {
  padding: 4px 10px;
  font-size: 13px;
  color: #8b949e;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.page-size-btn:hover {
  color: #e6edf3;
  border-color: #8b949e;
}

.page-size-btn.active {
  color: #e6edf3;
  background: #1f6feb;
  border-color: #1f6feb;
}

/* ── 页码导航 ── */
.page-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  font-size: 13px;
  color: #8b949e;
  background: #21262d;
  border: 1px solid #30363d;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.page-btn:hover:not(:disabled) {
  color: #e6edf3;
  border-color: #8b949e;
}

.page-btn.active {
  color: #e6edf3;
  background: #1f6feb;
  border-color: #1f6feb;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
