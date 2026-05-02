<template>
  <div class="screener-results">
    <div class="page-header">
      <h1 class="page-title">选股结果</h1>
      <div class="header-actions">
        <button class="btn btn-outline" @click="loadResults">🔄 刷新</button>
        <button class="btn btn-export" :disabled="exporting || !allResults.length" @click="exportCsv">
          <span v-if="exporting" class="spinner" aria-hidden="true"></span>
          {{ exporting ? '导出中...' : '📥 导出 CSV' }}
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
      <!-- 选中操作栏 -->
      <div v-if="selectedSymbols.size > 0" class="selection-bar">
        <span class="selection-count">已选 {{ selectedSymbols.size }} 只</span>
        <div class="pool-dropdown-wrapper" ref="poolDropdownRef">
          <button class="btn btn-add-pool" @click="togglePoolDropdown">添加到选股池</button>
          <div v-if="showPoolDropdown" class="pool-dropdown">
            <template v-if="poolStore.pools.length > 0">
              <div
                v-for="pool in poolStore.pools"
                :key="pool.id"
                class="pool-dropdown-item"
                @click="addToPool(pool.id, pool.name)"
              >
                {{ pool.name }}（{{ pool.stock_count }} 只）
              </div>
            </template>
            <div v-else class="pool-dropdown-empty">
              <span>暂无选股池</span>
              <a class="pool-dropdown-link" @click="goCreatePool">新建选股池</a>
            </div>
          </div>
        </div>
      </div>

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
            <th class="checkbox-col">
              <input
                type="checkbox"
                :checked="isAllSelected"
                :indeterminate="isIndeterminate"
                @change="toggleSelectAll"
                aria-label="全选"
              />
            </th>
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
              <td class="checkbox-col" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedSymbols.has(row.symbol)"
                  @change="toggleSelectSymbol(row.symbol)"
                  :aria-label="'选择 ' + row.symbol"
                />
              </td>
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
              <td colspan="8">
                <div class="detail-panel detail-panel-flex">
                  <div class="detail-signals">
                    <div class="detail-header">触发信号详情</div>
                    <div v-if="allResults.length > 0" class="signal-strength-legend">
                      🔴 强：多个因子共振确认&nbsp;&nbsp;🟡 中：部分因子确认&nbsp;&nbsp;⚪ 弱：单一因子触发
                    </div>
                    <div v-if="row.signals.length === 0" class="detail-empty">无触发信号</div>
                    <div v-else class="signal-tags">
                      <template v-for="group in groupSignalsByDimension(row.signals)" :key="group.dimension">
                        <div class="dimension-header">{{ group.dimension }}</div>
                        <span
                          v-for="(sig, idx) in group.signals"
                          :key="idx"
                          :class="['signal-tag', SIGNAL_CATEGORY_CLASS[sig.category], signalStrengthClass(sig.strength)]"
                        >
                          {{ SIGNAL_CATEGORY_LABEL[sig.category] }}：{{ sig.description || sig.label }}
                          <span class="strength-label">{{ signalStrengthText(sig.strength) }}</span>
                          <span v-if="sig.freshness === 'NEW'" class="freshness-badge">新</span>
                          <span v-if="sig.is_fake_breakout" class="fake-tag">假突破</span>
                        </span>
                      </template>
                    </div>
                    <!-- 板块分类展示（需求 9）—— 放在信号详情下方 -->
                    <div class="sector-classifications" v-if="row.sector_classifications">
                      <div class="detail-header">板块分类</div>
                      <div class="sector-columns">
                        <div class="sector-column" v-for="source in sectorSources" :key="source.key">
                          <div class="sector-source-title">{{ source.label }}</div>
                          <div v-if="(row.sector_classifications[source.key] ?? []).length > 0" class="sector-tags">
                            <span
                              v-for="name in row.sector_classifications[source.key]"
                              :key="name"
                              class="sector-tag"
                            >{{ name }}</span>
                          </div>
                          <div v-else class="sector-empty">暂无数据</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="detail-charts-container">
                    <div class="detail-chart">
                      <!-- 日K线复权切换 -->
                      <div class="adj-selector" role="group" aria-label="日K线复权类型选择">
                        <button
                          v-for="opt in DAILY_ADJ_OPTIONS"
                          :key="opt.value"
                          :class="['adj-btn', (dailyAdjType[row.symbol] ?? 0) === opt.value && 'active']"
                          :disabled="klineLoading[row.symbol]"
                          @click="onDailyAdjTypeChange(row.symbol, opt.value)"
                        >
                          {{ opt.label }}
                        </button>
                      </div>
                      <div v-if="klineLoading[row.symbol]" class="chart-loading">加载K线中...</div>
                      <div v-else-if="klineError[row.symbol]" class="chart-error">{{ klineError[row.symbol] }}</div>
                      <v-chart
                        v-else-if="klineOptions[row.symbol]"
                        :option="klineOptions[row.symbol]"
                        :autoresize="true"
                        class="kline-chart"
                        @click="(params: any) => onDailyKlineClick(row.symbol, params)"
                      />
                    </div>
                    <div class="detail-chart">
                      <MinuteKlineChart
                        :symbol="row.symbol"
                        :selected-date="selectedDates[row.symbol] ?? null"
                        :latest-trade-date="latestTradeDates[row.symbol] ?? ''"
                      />
                    </div>
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
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api'
import { usePageState } from '@/composables/usePageState'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import MinuteKlineChart from '@/components/MinuteKlineChart.vue'
import {
  type AdjType,
  dedupeKlineByTradeDate,
  extractDateFromClick,
  getKlineTradeDate,
} from '@/components/minuteKlineUtils'
import { useStockPoolStore } from '@/stores/stockPool'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer])

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type SignalCategory =
  | 'MA_TREND' | 'MACD' | 'BOLL' | 'RSI' | 'DMA'
  | 'BREAKOUT' | 'CAPITAL_INFLOW' | 'LARGE_ORDER'
  | 'MA_SUPPORT' | 'SECTOR_STRONG'

interface SignalDetail {
  category: SignalCategory
  label: string
  is_fake_breakout: boolean
  strength?: 'STRONG' | 'MEDIUM' | 'WEAK'
  freshness?: 'NEW' | 'CONTINUING'
  description?: string
  dimension?: string  // 信号维度（"技术面"/"资金面"/"基本面"/"板块面"）
}

interface SectorClassifications {
  eastmoney: string[]
  tonghuashun: string[]
  tongdaxin: string[]
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
  sector_classifications?: SectorClassifications
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

// 板块分类数据源
const sectorSources = [
  { key: 'eastmoney' as const, label: '东方财富' },
  { key: 'tonghuashun' as const, label: '同花顺' },
  { key: 'tongdaxin' as const, label: '通达信' },
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
  const strongCount = signals.filter(s => s.strength === 'STRONG').length
  const base = strongCount > 0
    ? `${signals.length} 个信号（${strongCount} 强）`
    : `${signals.length} 个信号`
  const cats = [...new Set(signals.map((s) => SIGNAL_CATEGORY_LABEL[s.category] ?? s.category))]
  return `${base}：${cats.slice(0, 3).join(' / ')}${cats.length > 3 ? ' …' : ''}`
}

// 维度展示顺序（需求 10.4）
const DIMENSION_ORDER = ['技术面', '板块面', '资金面', '基本面'] as const

// 按维度分组信号（需求 10.3, 10.4, 10.5）
function groupSignalsByDimension(signals: SignalDetail[]): { dimension: string; signals: SignalDetail[] }[] {
  const groups = new Map<string, SignalDetail[]>()
  for (const sig of signals) {
    const dim = sig.dimension ?? '其他'
    if (!groups.has(dim)) groups.set(dim, [])
    groups.get(dim)!.push(sig)
  }
  // 按固定顺序排列，跳过无信号的维度
  const ordered: { dimension: string; signals: SignalDetail[] }[] = []
  for (const dim of DIMENSION_ORDER) {
    const sigs = groups.get(dim)
    if (sigs && sigs.length > 0) {
      ordered.push({ dimension: dim, signals: sigs })
      groups.delete(dim)
    }
  }
  // 追加不在预定义顺序中的维度（如"其他"）
  for (const [dim, sigs] of groups) {
    if (sigs.length > 0) ordered.push({ dimension: dim, signals: sigs })
  }
  return ordered
}

// 信号强度 → CSS 类映射
const SIGNAL_STRENGTH_CLASS: Record<string, string> = {
  STRONG: 'sig-strong',
  MEDIUM: 'sig-medium',
  WEAK: 'sig-weak',
}

// 信号强度 → 中文文字标注映射
const SIGNAL_STRENGTH_TEXT: Record<string, string> = {
  STRONG: '强',
  MEDIUM: '中',
  WEAK: '弱',
}

/** 根据信号强度返回对应 CSS 类，缺失时默认 MEDIUM */
function signalStrengthClass(strength?: string): string {
  return SIGNAL_STRENGTH_CLASS[strength ?? 'MEDIUM'] ?? 'sig-medium'
}

/** 根据信号强度返回中文文字标注，缺失时默认"中" */
function signalStrengthText(strength?: string): string {
  return SIGNAL_STRENGTH_TEXT[strength ?? 'MEDIUM'] ?? '中'
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

// ─── 选股池相关状态 ───────────────────────────────────────────────────────────

const poolStore = useStockPoolStore()
const selectedSymbols = ref<Set<string>>(new Set())
const showPoolDropdown = ref(false)
const poolDropdownRef = ref<HTMLElement | null>(null)
const addingToPool = ref(false)

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
const latestTradeDates = reactive<Record<string, string>>({})
const selectedDates = reactive<Record<string, string>>({})
const klineDateArrays = reactive<Record<string, string[]>>({})

// ─── 日K线复权切换状态 ────────────────────────────────────────────────────────

const DAILY_ADJ_OPTIONS = [
  { value: 0 as AdjType, label: '原始' },
  { value: 1 as AdjType, label: '前复权' },
] as const

/** 每只股票的日K线复权类型（独立于分钟K线的 adjType） */
const dailyAdjType = reactive<Record<string, AdjType>>({})

/** 日K线数据缓存：key 为 `daily-${symbol}-${adjType}` */
const dailyKlineCache = new Map<string, any[]>()

// 开发环境下 HMR 时自动清空缓存
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    dailyKlineCache.clear()
  })
}

/** 构造日K线缓存键 */
function buildDailyKlineCacheKey(symbol: string, adjType: AdjType): string {
  return `daily-${symbol}-${adjType}`
}

async function fetchKline(symbol: string, adjType: AdjType = 0) {
  const cacheKey = buildDailyKlineCacheKey(symbol, adjType)

  // 缓存命中：直接从缓存构建图表选项
  if (dailyKlineCache.has(cacheKey)) {
    rebuildKlineOptions(symbol, dailyKlineCache.get(cacheKey)!)
    return
  }

  if (klineLoading[symbol]) return
  klineLoading[symbol] = true
  klineError[symbol] = ''
  try {
    const today = new Date()
    const oneYearAgo = new Date(today)
    oneYearAgo.setFullYear(today.getFullYear() - 1)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    const res = await apiClient.get(`/data/kline/${symbol}`, {
      params: { freq: '1d', start: fmt(oneYearAgo), end: fmt(today), adj_type: adjType },
    })
    const bars = dedupeKlineByTradeDate(res.data?.bars ?? [])
    if (!bars.length) {
      klineError[symbol] = '暂无K线数据'
      return
    }
    // 写入缓存
    dailyKlineCache.set(cacheKey, bars)
    rebuildKlineOptions(symbol, bars)
  } catch {
    klineError[symbol] = '加载K线失败'
  } finally {
    klineLoading[symbol] = false
  }
}

/** 从 bars 数据构建/重建 ECharts 图表选项，保留已有的 dataZoom 和 markLine */
function rebuildKlineOptions(symbol: string, bars: any[]) {
  // 保存当前 dataZoom 范围和 markLine
  const prevOpt = klineOptions[symbol]
  const prevDataZoom = prevOpt?.dataZoom?.[0]
    ? { start: prevOpt.dataZoom[0].start, end: prevOpt.dataZoom[0].end }
    : null
  const prevMarkLine = prevOpt?.series?.[0]?.markLine ?? null

  // 记录最近交易日（日K线最后一根bar的日期）
  const lastBar = bars[bars.length - 1]
  latestTradeDates[symbol] = getKlineTradeDate(lastBar)
  const dates = bars.map((b: any) => getKlineTradeDate(b))
  klineDateArrays[symbol] = dates
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
    dataZoom: [{
      type: 'inside',
      xAxisIndex: [0, 1],
      start: prevDataZoom?.start ?? 60,
      end: prevDataZoom?.end ?? 100,
    }],
    series: [
      {
        type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: '#f85149', color0: '#3fb950', borderColor: '#f85149', borderColor0: '#3fb950' },
        ...(prevMarkLine ? { markLine: prevMarkLine } : {}),
      },
      {
        type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: '#30363d' },
      },
    ],
  }
}

// ─── 交互 ─────────────────────────────────────────────────────────────────────

function onDailyKlineClick(symbol: string, params: any) {
  const dates = klineDateArrays[symbol]
  if (!dates) return
  const date = extractDateFromClick(dates, params.dataIndex)
  if (date) {
    selectedDates[symbol] = date
    // 更新日K线图 markLine 高亮线
    const opt = klineOptions[symbol]
    if (opt?.series?.[0]) {
      opt.series[0] = {
        ...opt.series[0],
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#58a6ff88', width: 1.5, type: 'solid' },
          data: [{ xAxis: date }],
          label: { show: false },
        },
      }
      // 触发 Vue 响应式更新
      klineOptions[symbol] = { ...opt }
    }
  }
}

function toggleExpand(symbol: string) {
  if (expandedSymbols.value.has(symbol)) {
    expandedSymbols.value.delete(symbol)
  } else {
    expandedSymbols.value.add(symbol)
    fetchKline(symbol, dailyAdjType[symbol] ?? 0)
  }
}

function onDailyAdjTypeChange(symbol: string, adjType: AdjType) {
  dailyAdjType[symbol] = adjType
  fetchKline(symbol, adjType)
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

// ─── 选股池：复选框与操作 ─────────────────────────────────────────────────────

/** 当前页是否全选 */
const isAllSelected = computed(() => {
  if (results.value.length === 0) return false
  return results.value.every((r) => selectedSymbols.value.has(r.symbol))
})

/** 当前页是否部分选中（indeterminate 状态） */
const isIndeterminate = computed(() => {
  if (results.value.length === 0) return false
  const some = results.value.some((r) => selectedSymbols.value.has(r.symbol))
  return some && !isAllSelected.value
})

/** 切换当前页全选/取消全选 */
function toggleSelectAll() {
  if (isAllSelected.value) {
    // 取消当前页所有选中
    for (const row of results.value) {
      selectedSymbols.value.delete(row.symbol)
    }
  } else {
    // 选中当前页所有
    for (const row of results.value) {
      selectedSymbols.value.add(row.symbol)
    }
  }
  // 触发响应式更新
  selectedSymbols.value = new Set(selectedSymbols.value)
}

/** 切换单只股票选中状态 */
function toggleSelectSymbol(symbol: string) {
  if (selectedSymbols.value.has(symbol)) {
    selectedSymbols.value.delete(symbol)
  } else {
    selectedSymbols.value.add(symbol)
  }
  selectedSymbols.value = new Set(selectedSymbols.value)
}

/** 切换选股池下拉菜单 */
function togglePoolDropdown() {
  showPoolDropdown.value = !showPoolDropdown.value
  if (showPoolDropdown.value) {
    poolStore.fetchPools()
  }
}

/** 点击外部关闭下拉菜单 */
function onClickOutside(e: MouseEvent) {
  if (poolDropdownRef.value && !poolDropdownRef.value.contains(e.target as Node)) {
    showPoolDropdown.value = false
  }
}

/** 添加选中股票到指定选股池 */
async function addToPool(poolId: string, poolName: string) {
  if (addingToPool.value) return
  addingToPool.value = true
  showPoolDropdown.value = false
  try {
    const symbols = [...selectedSymbols.value]
    const result = await poolStore.addStocksToPool(poolId, symbols)
    const parts: string[] = []
    if (result.added > 0) parts.push(`成功添加 ${result.added} 只到「${poolName}」`)
    if (result.skipped > 0) parts.push(`已跳过 ${result.skipped} 只重复股票`)
    alert(parts.join('，'))
    // 清除选中状态
    selectedSymbols.value = new Set()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    alert(typeof detail === 'string' ? detail : '添加失败，请稍后重试')
  } finally {
    addingToPool.value = false
  }
}

/** 跳转到新建选股池页面 */
function goCreatePool() {
  showPoolDropdown.value = false
  router.push('/stock-pool')
}

// ─── 导出 CSV ─────────────────────────────────────────────────────────────────

async function exportCsv() {
  exporting.value = true
  try {
    const res = await apiClient.get('/screen/export/csv', { responseType: 'blob' })
    const blob = new Blob([res.data as BlobPart], {
      type: 'text/csv',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `screener_results_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    alert('导出功能暂不可用，请稍后再试')
  } finally {
    exporting.value = false
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

onMounted(() => {
  loadResults()
  document.addEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
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

.selection-bar + .sort-bar {
  border-radius: 0;
  border-top: none;
}

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
.detail-charts-container {
  display: flex; gap: 16px; flex: 1; min-width: 0;
}
.detail-charts-container > .detail-chart {
  flex: 1; min-width: 0;
}
.kline-chart { width: 100%; height: 280px; }
.chart-loading, .chart-error {
  display: flex; align-items: center; justify-content: center;
  height: 280px; color: #8b949e; font-size: 13px;
}

/* ─── 日K线复权切换 ─────────────────────────────────────────────────────────── */
.adj-selector {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.adj-btn {
  background: transparent;
  border: 1px solid #30363d;
  color: #8b949e;
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.adj-btn:hover:not(:disabled) {
  color: #e6edf3;
  border-color: #8b949e;
}

.adj-btn.active {
  background: #1f6feb22;
  color: #58a6ff;
  border-color: #58a6ff;
}

.adj-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.detail-header {
  font-size: 13px; font-weight: 600; color: #8b949e;
  margin-bottom: 10px;
}
.detail-empty { font-size: 13px; color: #484f58; }

/* ─── 信号强度图例 ──────────────────────────────────────────────────────────── */
.signal-strength-legend {
  font-size: 11px;
  color: #6e7681;
  margin-bottom: 8px;
  line-height: 1.6;
}

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

/* ─── 信号强度颜色编码 ─────────────────────────────────────────────────────── */
.sig-strong { border-color: #f85149; background: #3a1a1a; }
.sig-medium { border-color: #d29922; background: #3a2a1a; }
.sig-weak   { border-color: #484f58; background: #21262d; }

/* 强度文字标注 */
.strength-label {
  font-size: 10px; font-weight: 700; padding: 1px 5px;
  border-radius: 6px; margin-left: 4px;
  background: rgba(255, 255, 255, 0.1); color: inherit;
}

/* 新鲜度"新"徽章 */
.freshness-badge {
  font-size: 10px; font-weight: 700; padding: 1px 5px;
  border-radius: 6px; margin-left: 2px;
  background: #1f6feb; color: #fff;
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

/* ─── 板块分类 ──────────────────────────────────────────────────────────────── */
.sector-classifications {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #21262d;
}
.sector-columns {
  display: flex;
  gap: 16px;
}
.sector-column {
  flex: 1;
  min-width: 0;
}
.sector-source-title {
  font-size: 12px;
  font-weight: 600;
  color: #8b949e;
  margin-bottom: 8px;
}
.sector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sector-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background: #1c2128;
  color: #e6edf3;
  border: 1px solid #30363d;
}
.sector-empty {
  font-size: 12px;
  color: #484f58;
}

/* ─── 维度分组标题（需求 10）──────────────────────────────────────────────── */
.dimension-header {
  width: 100%;
  font-size: 12px;
  font-weight: 600;
  color: #8b949e;
  margin-top: 8px;
  margin-bottom: 4px;
  border-bottom: 1px solid #21262d;
}

.dimension-header:first-child {
  margin-top: 0;
}

/* ─── 复选框列 ──────────────────────────────────────────────────────────────── */
.checkbox-col {
  width: 40px;
  text-align: center;
  padding: 10px 8px !important;
}
.checkbox-col input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #58a6ff;
}

/* ─── 选中操作栏 ────────────────────────────────────────────────────────────── */
.selection-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #1f6feb18;
  border: 1px solid #1f6feb44;
  border-radius: 8px 8px 0 0;
  margin-bottom: 0;
}
.selection-count {
  font-size: 14px;
  color: #58a6ff;
  font-weight: 600;
}
.btn-add-pool {
  background: #238636;
  color: #fff;
  border: none;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}
.btn-add-pool:hover { background: #2ea043; }

/* ─── 选股池下拉菜单 ────────────────────────────────────────────────────────── */
.pool-dropdown-wrapper {
  position: relative;
}
.pool-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 220px;
  max-height: 260px;
  overflow-y: auto;
  background: #1c2128;
  border: 1px solid #30363d;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 100;
}
.pool-dropdown-item {
  padding: 10px 14px;
  font-size: 13px;
  color: #e6edf3;
  cursor: pointer;
  transition: background 0.12s;
}
.pool-dropdown-item:hover {
  background: #30363d;
}
.pool-dropdown-empty {
  padding: 14px;
  font-size: 13px;
  color: #8b949e;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.pool-dropdown-link {
  color: #58a6ff;
  cursor: pointer;
  font-size: 13px;
}
.pool-dropdown-link:hover {
  text-decoration: underline;
}

/* ─── 响应式：小屏幕上下堆叠 ───────────────────────────────────────────────── */
@media (max-width: 768px) {
  .detail-charts-container {
    flex-direction: column;
  }
  .detail-charts-container > .detail-chart {
    width: 100%;
  }
}
</style>
