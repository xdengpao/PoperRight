<template>
  <div class="screener-results">
    <div class="page-header">
      <h1 class="page-title">选股结果</h1>
      <div class="header-actions">
        <button class="btn btn-outline" @click="loadResults">🔄 刷新</button>
        <button class="btn btn-export" :disabled="exporting || !allResults.length" @click="exportExcel">
          <span v-if="exporting" class="spinner" aria-hidden="true"></span>
          {{ exporting ? '导出中...' : '📥 导出 Excel' }}
        </button>
      </div>
    </div>

    <!-- 加载中 -->
    <LoadingSpinner v-if="state.loading" text="加载选股结果中..." />

    <!-- 错误 -->
    <ErrorBanner v-else-if="state.error" :message="state.error" :retryFn="loadResults" />

    <!-- 空状态 -->
    <div v-else-if="!allResults.length" class="empty-state">
      <div class="empty-icon">📊</div>
      <p class="empty-text">暂无选股结果</p>
      <p class="empty-hint">请先在「智能选股」页面执行选股</p>
      <button class="btn" @click="$router.push('/screener')">前往选股</button>
    </div>

    <!-- 结果表格 -->
    <div v-else class="table-wrapper">
      <!-- 排序控制 -->
      <div class="sort-bar">
        <span class="sort-label">排序：</span>
        <button
          v-for="col in sortOptions"
          :key="col.key"
          :class="['sort-btn', sortKey === col.key && 'active']"
          @click="toggleSort(col.key)"
        >
          {{ col.label }}
          <span v-if="sortKey === col.key" class="sort-arrow">
            {{ sortDir === 'asc' ? '↑' : '↓' }}
          </span>
        </button>
        <span class="result-count">共 {{ allResults.length }} 条</span>
      </div>

      <table class="result-table" aria-label="选股结果列表">
        <thead>
          <tr>
            <th>股票代码</th>
            <th>股票名称</th>
            <th>买入参考价</th>
            <th>
              <button class="th-sort-btn" @click="toggleSort('trend_score')">
                趋势强度
                <span v-if="sortKey === 'trend_score'" class="sort-arrow">
                  {{ sortDir === 'asc' ? '↑' : '↓' }}
                </span>
              </button>
            </th>
            <th>
              <button class="th-sort-btn" @click="toggleSort('risk_level')">
                风险等级
                <span v-if="sortKey === 'risk_level'" class="sort-arrow">
                  {{ sortDir === 'asc' ? '↑' : '↓' }}
                </span>
              </button>
            </th>
            <th>触发信号</th>
            <th>选股时间</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in results" :key="row.symbol">
            <!-- 主行 -->
            <tr
              class="result-row"
              :class="{ expanded: expandedSymbols.has(row.symbol) }"
              @click="toggleExpand(row.symbol)"
              :aria-expanded="expandedSymbols.has(row.symbol)"
              tabindex="0"
              @keyup.enter="toggleExpand(row.symbol)"
            >
              <td class="symbol-cell">
                <span class="expand-icon">{{ expandedSymbols.has(row.symbol) ? '▼' : '▶' }}</span>
                <span class="symbol-code">{{ row.symbol }}</span>
              </td>
              <td class="name-cell">{{ row.name }}</td>
              <td class="price-cell">¥{{ row.ref_buy_price.toFixed(2) }}</td>
              <td class="score-cell">
                <div class="score-bar-wrap">
                  <div
                    class="score-bar"
                    :style="{ width: row.trend_score + '%', background: scoreColor(row.trend_score) }"
                    :aria-valuenow="row.trend_score"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    role="progressbar"
                  ></div>
                  <span class="score-value">{{ row.trend_score }}</span>
                </div>
              </td>
              <td class="risk-cell">
                <span class="risk-badge" :class="'risk-' + row.risk_level.toLowerCase()">
                  {{ riskLabel(row.risk_level) }}
                </span>
              </td>
              <td class="signals-cell">
                <span class="signal-count">{{ signalSummary(row.signals) }}</span>
                <span v-if="row.has_fake_breakout" class="fake-breakout-badge">⚠ 假突破</span>
              </td>
              <td class="time-cell">{{ formatTime(row.screen_time) }}</td>
            </tr>
            <!-- 展开详情行 -->
            <tr v-if="expandedSymbols.has(row.symbol)" class="detail-row">
              <td colspan="7">
                <div class="detail-panel detail-panel-flex">
                  <div class="detail-signals">
                    <div class="detail-header">触发信号详情</div>
                    <div v-if="row.signals.length === 0" class="detail-empty">无触发信号</div>
                    <div v-else class="signal-tags">
                      <span
                        v-for="(sig, idx) in row.signals"
                        :key="idx"
                        :class="['signal-tag', SIGNAL_CATEGORY_CLASS[sig.category]]"
                      >
                        {{ SIGNAL_CATEGORY_LABEL[sig.category] }}：{{ sig.label }}
                        <span v-if="sig.is_fake_breakout" class="fake-tag">假突破</span>
                      </span>
                    </div>
                  </div>
                  <div class="detail-chart">
                    <div v-if="klineLoading[row.symbol]" class="chart-loading">加载K线中...</div>
                    <div v-else-if="klineError[row.symbol]" class="chart-error">{{ klineError[row.symbol] }}</div>
                    <v-chart
                      v-else-if="klineOptions[row.symbol]"
                      :option="klineOptions[row.symbol]"
                      :autoresize="true"
                      class="kline-chart"
                    />
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn-page" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <span class="page-info">第 {{ currentPage }} 页 / 共 {{ totalPages }} 页（{{ allResults.length }} 条）</span>
        <button class="btn-page" :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api'
import { usePageState } from '@/composables/usePageState'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type SignalCategory =
  | 'MA_TREND' | 'MACD' | 'BOLL' | 'RSI' | 'DMA'
  | 'BREAKOUT' | 'CAPITAL_INFLOW' | 'LARGE_ORDER'
  | 'MA_SUPPORT' | 'SECTOR_STRONG'

interface SignalDetail {
  category: SignalCategory
  label: string
  is_fake_breakout: boolean
}

interface ScreenResultRow {
  symbol: string
  name: string
  ref_buy_price: number
  trend_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  signals: SignalDetail[]
  screen_time: string
  has_fake_breakout: boolean
}

type SortKey = 'trend_score' | 'risk_level' | 'signal_count'
type SortDir = 'asc' | 'desc'

// ─── 常量 ─────────────────────────────────────────────────────────────────────

const RISK_ORDER: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2 }

const sortOptions: { key: SortKey; label: string }[] = [
  { key: 'trend_score', label: '趋势评分' },
  { key: 'risk_level', label: '风险等级' },
  { key: 'signal_count', label: '信号数量' },
]

// 信号分类 → 颜色 CSS 类
const SIGNAL_CATEGORY_CLASS: Record<SignalCategory, string> = {
  MA_TREND:      'sig-ma-trend',
  MACD:          'sig-indicator',
  BOLL:          'sig-indicator',
  RSI:           'sig-indicator',
  DMA:           'sig-indicator',
  BREAKOUT:      'sig-breakout',
  CAPITAL_INFLOW:'sig-capital',
  LARGE_ORDER:   'sig-large-order',
  MA_SUPPORT:    'sig-ma-support',
  SECTOR_STRONG: 'sig-sector',
}

// 信号分类中文名
const SIGNAL_CATEGORY_LABEL: Record<SignalCategory, string> = {
  MA_TREND:      '均线趋势',
  MACD:          'MACD',
  BOLL:          'BOLL',
  RSI:           'RSI',
  DMA:           'DMA',
  BREAKOUT:      '形态突破',
  CAPITAL_INFLOW:'资金流入',
  LARGE_ORDER:   '大单活跃',
  MA_SUPPORT:    '均线支撑',
  SECTOR_STRONG: '板块强势',
}

function signalSummary(signals: SignalDetail[]): string {
  if (!signals.length) return '无信号'
  const cats = [...new Set(signals.map((s) => SIGNAL_CATEGORY_LABEL[s.category] ?? s.category))]
  return `${signals.length} 个信号：${cats.slice(0, 3).join(' / ')}${cats.length > 3 ? ' …' : ''}`
}

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const router = useRouter()
const { state, execute } = usePageState<ScreenResultRow[]>()

// ─── 全量数据（一次性加载，前端排序+分页）─────────────────────────────────────

const allResults = ref<ScreenResultRow[]>([])
const expandedSymbols = ref<Set<string>>(new Set())
const sortKey = ref<SortKey>('trend_score')
const sortDir = ref<SortDir>('desc')
const exporting = ref(false)
const currentPage = ref(1)
const pageSize = 20

const sortedResults = computed(() => {
  const arr = [...allResults.value]
  arr.sort((a, b) => {
    let cmp = 0
    if (sortKey.value === 'trend_score') {
      cmp = a.trend_score - b.trend_score
    } else if (sortKey.value === 'risk_level') {
      cmp = (RISK_ORDER[a.risk_level] ?? 0) - (RISK_ORDER[b.risk_level] ?? 0)
    } else if (sortKey.value === 'signal_count') {
      cmp = (a.signals?.length ?? 0) - (b.signals?.length ?? 0)
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
  return arr
})

const totalPages = computed(() => Math.ceil(sortedResults.value.length / pageSize))
const results = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return sortedResults.value.slice(start, start + pageSize)
})

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function riskLabel(level: string): string {
  return { LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' }[level] ?? level
}

function scoreColor(score: number): string {
  if (score >= 70) return '#3fb950'
  if (score >= 40) return '#d29922'
  return '#f85149'
}

function formatTime(iso: string): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}

// ─── K线图数据 ────────────────────────────────────────────────────────────────

const klineLoading = reactive<Record<string, boolean>>({})
const klineError = reactive<Record<string, string>>({})
const klineOptions = reactive<Record<string, any>>({})

async function fetchKline(symbol: string) {
  if (klineOptions[symbol] || klineLoading[symbol]) return
  klineLoading[symbol] = true
  klineError[symbol] = ''
  try {
    const today = new Date()
    const oneYearAgo = new Date(today)
    oneYearAgo.setFullYear(today.getFullYear() - 1)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    const res = await apiClient.get(`/data/kline/${symbol}`, {
      params: { freq: '1d', start: fmt(oneYearAgo), end: fmt(today) },
    })
    const bars = res.data?.bars ?? []
    if (!bars.length) {
      klineError[symbol] = '暂无K线数据'
      return
    }
    const dates = bars.map((b: any) => b.time.slice(0, 10))
    const ohlc = bars.map((b: any) => [+b.open, +b.close, +b.low, +b.high])
    const vols = bars.map((b: any) => b.volume)
    klineOptions[symbol] = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params
          if (!p || !p.data) return ''
          const idx = p.dataIndex
          const [open, close, low, high] = ohlc[idx]
          const chg = open ? ((close - open) / open * 100).toFixed(2) : '0.00'
          const color = close >= open ? '#f85149' : '#3fb950'
          const vol = (vols[idx] / 10000).toFixed(0)
          return `<div style="font-size:12px;line-height:1.6">
            <div style="font-weight:600">${dates[idx]}</div>
            <div>开 ${open.toFixed(2)}　高 ${high.toFixed(2)}</div>
            <div>低 ${low.toFixed(2)}　收 ${close.toFixed(2)}</div>
            <div>涨跌幅 <span style="color:${color};font-weight:600">${chg}%</span></div>
            <div>成交量 ${vol} 万手</div>
          </div>`
        },
      },
      grid: [
        { left: 50, right: 20, top: 20, height: '55%' },
        { left: 50, right: 20, top: '72%', height: '18%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, axisLabel: { color: '#8b949e', fontSize: 10 } },
        { type: 'category', data: dates, gridIndex: 1, show: false },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#21262d' } }, axisLabel: { color: '#8b949e' } },
        { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 }],
      series: [
        {
          type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
          itemStyle: { color: '#f85149', color0: '#3fb950', borderColor: '#f85149', borderColor0: '#3fb950' },
        },
        {
          type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1,
          itemStyle: { color: '#30363d' },
        },
      ],
    }
  } catch {
    klineError[symbol] = '加载K线失败'
  } finally {
    klineLoading[symbol] = false
  }
}

// ─── 交互 ─────────────────────────────────────────────────────────────────────

function toggleExpand(symbol: string) {
  if (expandedSymbols.value.has(symbol)) {
    expandedSymbols.value.delete(symbol)
  } else {
    expandedSymbols.value.add(symbol)
    fetchKline(symbol)
  }
}

function toggleSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = (key === 'trend_score' || key === 'signal_count') ? 'desc' : 'asc'
  }
  currentPage.value = 1
}

// ─── 数据加载 ─────────────────────────────────────────────────────────────────

async function loadResults() {
  await execute(async () => {
    try {
      const res = await apiClient.get<{ total?: number; items?: ScreenResultRow[] } | ScreenResultRow[]>(
        '/screen/results',
        { params: { page: 1, page_size: 10000 } },
      )
      const data = res.data
      const items = Array.isArray(data) ? data : (data.items ?? [])
      allResults.value = items
      currentPage.value = 1
      return items
    } catch (e: any) {
      allResults.value = []
      const detail = e?.response?.data?.detail
      throw new Error(typeof detail === 'string' ? detail : (e?.message ?? '加载选股结果失败'))
    }
  })
}

function changePage(p: number) {
  currentPage.value = p
}

// ─── 导出 Excel ───────────────────────────────────────────────────────────────

async function exportExcel() {
  exporting.value = true
  try {
    const res = await apiClient.get('/screen/export', { responseType: 'blob' })
    const blob = new Blob([res.data as BlobPart], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `screener_results_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    // 如果后端返回 JSON（stub），尝试作为 JSON 处理并提示
    alert('导出功能暂不可用，请稍后再试')
  } finally {
    exporting.value = false
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

onMounted(() => {
  loadResults()
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.screener-results { max-width: 1200px; }

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px; flex-wrap: wrap; gap: 10px;
}
.page-title { font-size: 20px; color: #e6edf3; margin: 0; }
.header-actions { display: flex; gap: 8px; }

/* ─── 空状态 ────────────────────────────────────────────────────────────────── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 20px; background: #161b22; border: 1px solid #30363d;
  border-radius: 8px; gap: 10px;
}
.empty-icon { font-size: 48px; }
.empty-text { font-size: 16px; color: #e6edf3; margin: 0; }
.empty-hint { font-size: 14px; color: #8b949e; margin: 0; }

/* ─── 排序栏 ────────────────────────────────────────────────────────────────── */
.sort-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 16px; background: #161b22; border: 1px solid #30363d;
  border-bottom: none; border-radius: 8px 8px 0 0;
}
.sort-label { font-size: 13px; color: #8b949e; }
.sort-btn {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 13px;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.sort-btn:hover { color: #e6edf3; border-color: #8b949e; }
.sort-btn.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.sort-arrow { margin-left: 4px; }
.result-count { margin-left: auto; font-size: 13px; color: #484f58; }

/* ─── 表格容器 ──────────────────────────────────────────────────────────────── */
.table-wrapper { overflow-x: auto; }

.result-table {
  width: 100%; border-collapse: collapse;
  background: #161b22; border: 1px solid #30363d;
  border-radius: 0 0 8px 8px; overflow: hidden;
  font-size: 14px;
}

.result-table thead tr {
  background: #1c2128; border-bottom: 1px solid #30363d;
}
.result-table th {
  padding: 10px 14px; text-align: left; color: #8b949e;
  font-weight: 600; font-size: 13px; white-space: nowrap;
}
.th-sort-btn {
  background: none; border: none; color: #8b949e; cursor: pointer;
  font-size: 13px; font-weight: 600; padding: 0;
  display: flex; align-items: center; gap: 4px;
}
.th-sort-btn:hover { color: #e6edf3; }

/* ─── 主行 ─────────────────────────────────────────────────────────────────── */
.result-row {
  border-bottom: 1px solid #21262d; cursor: pointer;
  transition: background 0.12s;
}
.result-row:hover { background: #1c2128; }
.result-row.expanded { background: #1c2128; }
.result-row:focus { outline: 2px solid #58a6ff44; outline-offset: -2px; }

.result-table td { padding: 10px 14px; color: #e6edf3; vertical-align: middle; }

.symbol-cell { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.expand-icon { font-size: 10px; color: #484f58; flex-shrink: 0; }
.symbol-code { font-family: monospace; font-weight: 600; color: #58a6ff; }

.name-cell { color: #e6edf3; }
.price-cell { font-family: monospace; color: #3fb950; font-weight: 600; }

/* ─── 趋势评分进度条 ────────────────────────────────────────────────────────── */
.score-cell { min-width: 120px; }
.score-bar-wrap {
  display: flex; align-items: center; gap: 8px;
}
.score-bar {
  height: 8px; border-radius: 4px; flex: 1; max-width: 80px;
  transition: width 0.3s;
}
.score-value { font-size: 13px; color: #e6edf3; font-weight: 600; min-width: 24px; }

/* ─── 风险等级徽章 ──────────────────────────────────────────────────────────── */
.risk-badge {
  display: inline-block; padding: 2px 10px; border-radius: 10px;
  font-size: 12px; font-weight: 600; white-space: nowrap;
}
.risk-low { background: #1a3a2a; color: #3fb950; border: 1px solid #3fb95044; }
.risk-medium { background: #3a2a1a; color: #d29922; border: 1px solid #d2992244; }
.risk-high { background: #3a1a1a; color: #f85149; border: 1px solid #f8514944; }

.time-cell { font-size: 12px; color: #484f58; white-space: nowrap; }

/* ─── 展开详情行 ────────────────────────────────────────────────────────────── */
.detail-row { background: #0d1117; }
.detail-row td { padding: 0; }

.detail-panel {
  padding: 14px 20px 14px 40px;
  border-top: 1px solid #21262d;
}
.detail-panel-flex {
  display: flex; gap: 20px; align-items: flex-start;
}
.detail-signals { flex: 0 0 280px; min-width: 200px; }
.detail-chart { flex: 1; min-width: 0; }
.kline-chart { width: 100%; height: 280px; }
.chart-loading, .chart-error {
  display: flex; align-items: center; justify-content: center;
  height: 280px; color: #8b949e; font-size: 13px;
}
.detail-header {
  font-size: 13px; font-weight: 600; color: #8b949e;
  margin-bottom: 10px;
}
.detail-empty { font-size: 13px; color: #484f58; }

/* ─── 信号标签 ──────────────────────────────────────────────────────────────── */
.signal-tags { display: flex; flex-wrap: wrap; gap: 8px; }

.signal-tag {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;
  border: 1px solid transparent;
}

/* 均线趋势 — 蓝色 */
.sig-ma-trend    { background: #1f3a5f; color: #58a6ff; border-color: #1f6feb44; }
/* 技术指标 MACD/BOLL/RSI/DMA — 青色 */
.sig-indicator   { background: #0d2a2a; color: #39d353; border-color: #39d35344; }
/* 形态突破 — 绿色 */
.sig-breakout    { background: #1a3a1a; color: #3fb950; border-color: #3fb95044; }
/* 资金流入 — 橙色 */
.sig-capital     { background: #3a2a0a; color: #d29922; border-color: #d2992244; }
/* 大单活跃 — 黄色 */
.sig-large-order { background: #2a2a0a; color: #e3b341; border-color: #e3b34144; }
/* 均线支撑 — 紫色 */
.sig-ma-support  { background: #2a1a3a; color: #bc8cff; border-color: #bc8cff44; }
/* 板块强势 — 品红 */
.sig-sector      { background: #3a0a2a; color: #f778ba; border-color: #f778ba44; }

/* 假突破警告标签 */
.fake-tag {
  background: #f85149; color: #fff; font-size: 11px; font-weight: 700;
  padding: 1px 6px; border-radius: 8px; margin-left: 2px;
}

/* 主行假突破徽章 */
.fake-breakout-badge {
  display: inline-block; margin-left: 6px;
  background: #3a1a1a; color: #f85149; border: 1px solid #f8514944;
  font-size: 11px; padding: 1px 7px; border-radius: 8px; font-weight: 600;
}

.signals-cell { color: #8b949e; white-space: nowrap; }
.signal-count { font-size: 13px; }
.btn {
  background: #238636; color: #fff; border: none; padding: 7px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
}
.btn:hover:not(:disabled) { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
}
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-export { background: #1f6feb; }
.btn-export:hover:not(:disabled) { background: #388bfd; }

/* ─── 旋转加载 ──────────────────────────────────────────────────────────────── */
.spinner {
  display: inline-block; width: 13px; height: 13px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 分页 ──────────────────────────────────────────────────────────────────── */
.pagination {
  display: flex; align-items: center; gap: 12px;
  justify-content: flex-end; margin-top: 14px;
}
.btn-page {
  background: #21262d; border: 1px solid #30363d; color: #8b949e;
  padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-page:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-page:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 13px; color: #8b949e; }
</style>
