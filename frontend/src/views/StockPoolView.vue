<template>
  <div class="stock-pool">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1 class="page-title">选股池管理</h1>
      <div class="header-actions">
        <button class="btn btn-primary" @click="openCreateDialog">➕ 新建选股池</button>
      </div>
    </div>

    <!-- 加载中 -->
    <LoadingSpinner v-if="store.loading" text="加载选股池中..." />

    <!-- 错误 -->
    <ErrorBanner v-else-if="loadError" :message="loadError" :retryFn="loadPools" />

    <!-- 空状态 -->
    <div v-else-if="!store.pools.length" class="empty-state">
      <div class="empty-icon">📦</div>
      <p class="empty-text">暂无选股池，请点击"新建选股池"创建</p>
    </div>

    <!-- 选股池列表 -->
    <div v-else class="pool-list">
      <div
        v-for="pool in store.pools"
        :key="pool.id"
        class="pool-card"
        :class="{ expanded: expandedPoolId === pool.id }"
      >
        <!-- 选股池头部行 -->
        <div
          class="pool-header"
          @click="togglePool(pool.id)"
          tabindex="0"
          @keyup.enter="togglePool(pool.id)"
          :aria-expanded="expandedPoolId === pool.id"
        >
          <span class="expand-icon">{{ expandedPoolId === pool.id ? '▼' : '▶' }}</span>
          <div class="pool-info">
            <span class="pool-name">{{ pool.name }}</span>
            <span class="pool-meta">{{ pool.stock_count }} 只股票 · 创建于 {{ formatTime(pool.created_at) }}</span>
          </div>
          <div class="pool-actions" @click.stop>
            <button class="btn-icon" title="重命名" @click="openRenameDialog(pool)">✏️</button>
            <button class="btn-icon btn-icon-danger" title="删除" @click="openDeleteDialog(pool)">🗑️</button>
          </div>
        </div>

        <!-- 选股池详情展开 -->
        <div v-if="expandedPoolId === pool.id" class="pool-detail">
          <!-- 手动添加股票 -->
          <div class="add-stock-bar">
            <div class="add-stock-input-wrap">
              <input
                v-model="manualSymbol"
                class="input"
                placeholder="输入股票代码（6位数字）"
                maxlength="6"
                @keyup.enter="handleAddManual(pool.id)"
              />
              <span v-if="manualError" class="field-error">{{ manualError }}</span>
            </div>
            <button class="btn btn-sm" @click="handleAddManual(pool.id)">添加</button>
            <button
              v-if="selectedSymbols.size > 0"
              class="btn btn-sm btn-danger"
              @click="handleBatchRemove(pool.id)"
            >
              移除 ({{ selectedSymbols.size }})
            </button>
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
            <span class="result-count">共 {{ store.enrichedPoolStocks.length }} 条</span>
          </div>

          <!-- 股票列表加载中 -->
          <LoadingSpinner v-if="store.enrichedLoading" size="sm" text="加载股票列表..." />

          <!-- 空池状态 -->
          <div v-else-if="!store.enrichedPoolStocks.length" class="empty-pool">
            选股池为空，请从选股结果中添加股票
          </div>

          <!-- 股票表格 -->
          <table v-else class="stock-table" aria-label="选股池股票列表">
            <thead>
              <tr>
                <th class="th-checkbox">
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
                <th>趋势评分</th>
                <th>风险等级</th>
                <th>触发信号</th>
                <th>选股时间</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="stock in sortedStocks" :key="stock.symbol">
                <!-- 主行 -->
                <tr
                  class="stock-row"
                  :class="{ expanded: expandedSymbol === stock.symbol }"
                  @click="toggleExpandStock(stock)"
                  tabindex="0"
                  @keyup.enter="toggleExpandStock(stock)"
                >
                  <td class="td-checkbox" @click.stop>
                    <input
                      type="checkbox"
                      :checked="selectedSymbols.has(stock.symbol)"
                      @change="toggleSelect(stock.symbol)"
                      :aria-label="`选择 ${stock.symbol}`"
                    />
                  </td>
                  <td class="symbol-cell">
                    <span class="expand-icon">{{ expandedSymbol === stock.symbol ? '▼' : (stock.signals !== null ? '▶' : '') }}</span>
                    <span class="symbol-code">{{ stock.symbol }}</span>
                  </td>
                  <td>{{ stock.stock_name || '—' }}</td>
                  <td class="price-cell">
                    <template v-if="stock.signals !== null && stock.ref_buy_price !== null">¥{{ stock.ref_buy_price.toFixed(2) }}</template>
                    <template v-else>—</template>
                  </td>
                  <td class="score-cell">
                    <template v-if="stock.signals !== null && stock.trend_score !== null">
                      <div class="score-bar-wrap">
                        <div
                          class="score-bar"
                          :style="{ width: stock.trend_score + '%', background: scoreColor(stock.trend_score) }"
                          :aria-valuenow="stock.trend_score"
                          aria-valuemin="0"
                          aria-valuemax="100"
                          role="progressbar"
                        ></div>
                        <span class="score-value">{{ stock.trend_score }}</span>
                      </div>
                    </template>
                    <template v-else>—</template>
                  </td>
                  <td>
                    <template v-if="stock.signals !== null && stock.risk_level !== null">
                      <span class="risk-badge" :class="'risk-' + stock.risk_level.toLowerCase()">
                        {{ riskLabel(stock.risk_level) }}
                      </span>
                    </template>
                    <template v-else>—</template>
                  </td>
                  <td class="signals-cell">
                    <template v-if="stock.signals !== null">
                      <span class="signal-count">{{ signalSummary(stock.signals) }}</span>
                      <span v-if="stock.has_fake_breakout" class="fake-breakout-badge">⚠ 假突破</span>
                    </template>
                    <template v-else>—</template>
                  </td>
                  <td class="time-cell">
                    <template v-if="stock.signals !== null && stock.screen_time">{{ formatTime(stock.screen_time) }}</template>
                    <template v-else>—</template>
                  </td>
                </tr>
                <!-- 展开详情行 -->
                <tr v-if="expandedSymbol === stock.symbol && stock.signals !== null" class="detail-row">
                  <td colspan="8">
                    <div class="detail-panel detail-panel-flex">
                      <div class="detail-signals">
                        <div class="detail-header">触发信号详情</div>
                        <div class="signal-strength-legend">
                          🔴 强：多个因子共振确认&nbsp;&nbsp;🟡 中：部分因子确认&nbsp;&nbsp;⚪ 弱：单一因子触发
                        </div>
                        <div v-if="stock.signals.length === 0" class="detail-empty">无触发信号</div>
                        <div v-else class="signal-tags">
                          <template v-for="group in groupSignalsByDimension(stock.signals)" :key="group.dimension">
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
                        <!-- 板块分类展示 -->
                        <div class="sector-classifications" v-if="stock.sector_classifications">
                          <div class="detail-header">板块分类</div>
                          <div class="sector-columns">
                            <div class="sector-column" v-for="source in sectorSources" :key="source.key">
                              <div class="sector-source-title">{{ source.label }}</div>
                              <div v-if="(stock.sector_classifications[source.key] ?? []).length > 0" class="sector-tags">
                                <span
                                  v-for="name in stock.sector_classifications[source.key]"
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
                              :class="['adj-btn', (dailyAdjType[stock.symbol] ?? 0) === opt.value && 'active']"
                              :disabled="klineLoading[stock.symbol]"
                              @click="onDailyAdjTypeChange(stock.symbol, opt.value)"
                            >
                              {{ opt.label }}
                            </button>
                          </div>
                          <div v-if="klineLoading[stock.symbol]" class="chart-loading">加载K线中...</div>
                          <div v-else-if="klineError[stock.symbol]" class="chart-error">{{ klineError[stock.symbol] }}</div>
                          <v-chart
                            v-else-if="klineOptions[stock.symbol]"
                            :option="klineOptions[stock.symbol]"
                            :autoresize="true"
                            class="kline-chart"
                            @click="(params: any) => onDailyKlineClick(stock.symbol, params)"
                          />
                        </div>
                        <div class="detail-chart">
                          <MinuteKlineChart
                            :symbol="stock.symbol"
                            :selected-date="selectedDates[stock.symbol] ?? null"
                            :latest-trade-date="latestTradeDates[stock.symbol] ?? ''"
                          />
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 新建选股池对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="closeCreateDialog">
      <div class="dialog" role="dialog" aria-labelledby="create-dialog-title">
        <h3 id="create-dialog-title" class="dialog-title">新建选股池</h3>
        <div class="dialog-body">
          <label class="field-label">选股池名称</label>
          <input
            v-model="createName"
            class="input"
            placeholder="请输入选股池名称"
            maxlength="50"
            @keyup.enter="handleCreate"
            ref="createInputRef"
          />
          <span v-if="createError" class="field-error">{{ createError }}</span>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-outline" @click="closeCreateDialog">取消</button>
          <button class="btn btn-primary" :disabled="creating" @click="handleCreate">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 重命名对话框 -->
    <div v-if="showRenameDialog" class="dialog-overlay" @click.self="closeRenameDialog">
      <div class="dialog" role="dialog" aria-labelledby="rename-dialog-title">
        <h3 id="rename-dialog-title" class="dialog-title">重命名选股池</h3>
        <div class="dialog-body">
          <label class="field-label">新名称</label>
          <input
            v-model="renameName"
            class="input"
            placeholder="请输入新名称"
            maxlength="50"
            @keyup.enter="handleRename"
            ref="renameInputRef"
          />
          <span v-if="renameError" class="field-error">{{ renameError }}</span>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-outline" @click="closeRenameDialog">取消</button>
          <button class="btn btn-primary" :disabled="renaming" @click="handleRename">
            {{ renaming ? '保存中...' : '确认' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认对话框 -->
    <div v-if="showDeleteDialog" class="dialog-overlay" @click.self="closeDeleteDialog">
      <div class="dialog" role="dialog" aria-labelledby="delete-dialog-title">
        <h3 id="delete-dialog-title" class="dialog-title">删除选股池</h3>
        <div class="dialog-body">
          <p class="delete-confirm-text">
            确定要删除选股池「<strong>{{ deleteTarget?.name }}</strong>」吗？
          </p>
          <p class="delete-confirm-hint">
            该选股池包含 <strong>{{ deleteTarget?.stock_count }}</strong> 只股票，删除后无法恢复。
          </p>
        </div>
        <div class="dialog-footer">
          <button class="btn btn-outline" @click="closeDeleteDialog">取消</button>
          <button class="btn btn-danger" :disabled="deleting" @click="handleDelete">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 选股池管理页面
 *
 * 对应需求 2-5：选股池列表展示、创建/重命名/删除管理、池内股票增删。
 * 对应需求 7：选股池股票富化展示，与选股结果页面一致的表格列和可展开详情面板。
 */
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { useStockPoolStore, validatePoolName, validateStockSymbol } from '@/stores/stockPool'
import type { StockPool, SignalDetail, SignalCategory, EnrichedPoolStock } from '@/stores/stockPool'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import MinuteKlineChart from '@/components/MinuteKlineChart.vue'
import {
  type AdjType,
  dedupeKlineByTradeDate,
  extractDateFromClick,
  getKlineTradeDate,
} from '@/components/minuteKlineUtils'
import { apiClient } from '@/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer])

const store = useStockPoolStore()

// ─── 常量（复用自 ScreenerResultsView）─────────────────────────────────────────

type SortKey = 'trend_score' | 'risk_level' | 'signal_count'
type SortDir = 'asc' | 'desc'

const RISK_ORDER: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2 }

const sortOptions: { key: SortKey; label: string }[] = [
  { key: 'trend_score', label: '趋势评分' },
  { key: 'risk_level', label: '风险等级' },
  { key: 'signal_count', label: '信号数量' },
]

const sectorSources = [
  { key: 'eastmoney' as const, label: '东方财富' },
  { key: 'tonghuashun' as const, label: '同花顺' },
  { key: 'tongdaxin' as const, label: '通达信' },
]

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

const DIMENSION_ORDER = ['技术面', '板块面', '资金面', '基本面'] as const

const DAILY_ADJ_OPTIONS = [
  { value: 0 as AdjType, label: '原始' },
  { value: 1 as AdjType, label: '前复权' },
] as const

// ─── 辅助函数（复用自 ScreenerResultsView）─────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 70) return '#3fb950'
  if (score >= 40) return '#d29922'
  return '#f85149'
}

function riskLabel(level: string): string {
  return { LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' }[level] ?? level
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

function groupSignalsByDimension(signals: SignalDetail[]): { dimension: string; signals: SignalDetail[] }[] {
  const groups = new Map<string, SignalDetail[]>()
  for (const sig of signals) {
    const dim = sig.dimension ?? '其他'
    if (!groups.has(dim)) groups.set(dim, [])
    groups.get(dim)!.push(sig)
  }
  const ordered: { dimension: string; signals: SignalDetail[] }[] = []
  for (const dim of DIMENSION_ORDER) {
    const sigs = groups.get(dim)
    if (sigs && sigs.length > 0) {
      ordered.push({ dimension: dim, signals: sigs })
      groups.delete(dim)
    }
  }
  for (const [dim, sigs] of groups) {
    if (sigs.length > 0) ordered.push({ dimension: dim, signals: sigs })
  }
  return ordered
}

const SIGNAL_STRENGTH_CLASS: Record<string, string> = {
  STRONG: 'sig-strong',
  MEDIUM: 'sig-medium',
  WEAK: 'sig-weak',
}

const SIGNAL_STRENGTH_TEXT: Record<string, string> = {
  STRONG: '强',
  MEDIUM: '中',
  WEAK: '弱',
}

function signalStrengthClass(strength?: string): string {
  return SIGNAL_STRENGTH_CLASS[strength ?? 'MEDIUM'] ?? 'sig-medium'
}

function signalStrengthText(strength?: string): string {
  return SIGNAL_STRENGTH_TEXT[strength ?? 'MEDIUM'] ?? '中'
}

function formatTime(iso: string): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}

// ─── 页面状态 ─────────────────────────────────────────────────────────────────

const loadError = ref<string | null>(null)
const expandedPoolId = ref<string | null>(null)
const expandedSymbol = ref<string | null>(null)
const selectedSymbols = ref<Set<string>>(new Set())
const manualSymbol = ref('')
const manualError = ref('')

// ─── 排序状态（需求 7.8）─────────────────────────────────────────────────────

const sortKey = ref<SortKey>('trend_score')
const sortDir = ref<SortDir>('desc')

const sortedStocks = computed(() => {
  const arr = [...store.enrichedPoolStocks]
  arr.sort((a, b) => {
    let cmp = 0
    if (sortKey.value === 'trend_score') {
      cmp = (a.trend_score ?? -1) - (b.trend_score ?? -1)
    } else if (sortKey.value === 'risk_level') {
      cmp = (RISK_ORDER[a.risk_level ?? ''] ?? -1) - (RISK_ORDER[b.risk_level ?? ''] ?? -1)
    } else if (sortKey.value === 'signal_count') {
      cmp = (a.signals?.length ?? -1) - (b.signals?.length ?? -1)
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
  return arr
})

function toggleSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = (key === 'trend_score' || key === 'signal_count') ? 'desc' : 'asc'
  }
}

// ─── K线图数据（复用自 ScreenerResultsView）──────────────────────────────────

const klineLoading = reactive<Record<string, boolean>>({})
const klineError = reactive<Record<string, string>>({})
const klineOptions = reactive<Record<string, any>>({})
const latestTradeDates = reactive<Record<string, string>>({})
const selectedDates = reactive<Record<string, string>>({})
const klineDateArrays = reactive<Record<string, string[]>>({})
const dailyAdjType = reactive<Record<string, AdjType>>({})
const dailyKlineCache = new Map<string, any[]>()

function buildDailyKlineCacheKey(symbol: string, adjType: AdjType): string {
  return `daily-${symbol}-${adjType}`
}

async function fetchKline(symbol: string, adjType: AdjType = 0) {
  const cacheKey = buildDailyKlineCacheKey(symbol, adjType)
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
    dailyKlineCache.set(cacheKey, bars)
    rebuildKlineOptions(symbol, bars)
  } catch {
    klineError[symbol] = '加载K线失败'
  } finally {
    klineLoading[symbol] = false
  }
}

function rebuildKlineOptions(symbol: string, bars: any[]) {
  const prevOpt = klineOptions[symbol]
  const prevDataZoom = prevOpt?.dataZoom?.[0]
    ? { start: prevOpt.dataZoom[0].start, end: prevOpt.dataZoom[0].end }
    : null
  const prevMarkLine = prevOpt?.series?.[0]?.markLine ?? null

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

function onDailyKlineClick(symbol: string, params: any) {
  const dates = klineDateArrays[symbol]
  if (!dates) return
  const date = extractDateFromClick(dates, params.dataIndex)
  if (date) {
    selectedDates[symbol] = date
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
      klineOptions[symbol] = { ...opt }
    }
  }
}

function onDailyAdjTypeChange(symbol: string, adjType: AdjType) {
  dailyAdjType[symbol] = adjType
  fetchKline(symbol, adjType)
}

// ─── 新建对话框 ───────────────────────────────────────────────────────────────

const showCreateDialog = ref(false)
const createName = ref('')
const createError = ref('')
const creating = ref(false)
const createInputRef = ref<HTMLInputElement | null>(null)

function openCreateDialog() {
  createName.value = ''
  createError.value = ''
  showCreateDialog.value = true
  nextTick(() => createInputRef.value?.focus())
}

function closeCreateDialog() {
  showCreateDialog.value = false
}

async function handleCreate() {
  const validation = validatePoolName(createName.value)
  if (!validation.valid) {
    createError.value = validation.error!
    return
  }
  createError.value = ''
  creating.value = true
  try {
    await store.createPool(createName.value.trim())
    closeCreateDialog()
  } catch (e: any) {
    createError.value = e?.response?.data?.detail || e?.message || '创建失败，请重试'
  } finally {
    creating.value = false
  }
}

// ─── 重命名对话框 ─────────────────────────────────────────────────────────────

const showRenameDialog = ref(false)
const renameName = ref('')
const renameError = ref('')
const renaming = ref(false)
const renameTarget = ref<StockPool | null>(null)
const renameInputRef = ref<HTMLInputElement | null>(null)

function openRenameDialog(pool: StockPool) {
  renameTarget.value = pool
  renameName.value = pool.name
  renameError.value = ''
  showRenameDialog.value = true
  nextTick(() => renameInputRef.value?.focus())
}

function closeRenameDialog() {
  showRenameDialog.value = false
  renameTarget.value = null
}

async function handleRename() {
  const validation = validatePoolName(renameName.value)
  if (!validation.valid) {
    renameError.value = validation.error!
    return
  }
  renameError.value = ''
  renaming.value = true
  try {
    await store.renamePool(renameTarget.value!.id, renameName.value.trim())
    closeRenameDialog()
  } catch (e: any) {
    renameError.value = e?.response?.data?.detail || e?.message || '重命名失败，请重试'
  } finally {
    renaming.value = false
  }
}

// ─── 删除对话框 ───────────────────────────────────────────────────────────────

const showDeleteDialog = ref(false)
const deleteTarget = ref<StockPool | null>(null)
const deleting = ref(false)

function openDeleteDialog(pool: StockPool) {
  deleteTarget.value = pool
  showDeleteDialog.value = true
}

function closeDeleteDialog() {
  showDeleteDialog.value = false
  deleteTarget.value = null
}

async function handleDelete() {
  deleting.value = true
  try {
    const poolId = deleteTarget.value!.id
    await store.deletePool(poolId)
    if (expandedPoolId.value === poolId) {
      expandedPoolId.value = null
    }
    closeDeleteDialog()
  } catch (e: any) {
    alert(e?.response?.data?.detail || e?.message || '删除失败，请重试')
  } finally {
    deleting.value = false
  }
}

// ─── 选股池展开/收起（需求 7：使用富化数据）──────────────────────────────────

async function togglePool(poolId: string) {
  if (expandedPoolId.value === poolId) {
    expandedPoolId.value = null
    return
  }
  expandedPoolId.value = poolId
  expandedSymbol.value = null
  selectedSymbols.value = new Set()
  manualSymbol.value = ''
  manualError.value = ''
  try {
    await store.fetchEnrichedPoolStocks(poolId)
  } catch (e: any) {
    // 加载失败时仍保持展开，显示错误
  }
}

// ─── 股票行展开/收起（需求 7.2）──────────────────────────────────────────────

function toggleExpandStock(stock: EnrichedPoolStock) {
  // 无选股结果数据的股票行不展开
  if (stock.signals === null) return
  if (expandedSymbol.value === stock.symbol) {
    expandedSymbol.value = null
  } else {
    expandedSymbol.value = stock.symbol
    fetchKline(stock.symbol, dailyAdjType[stock.symbol] ?? 0)
  }
}

// ─── 手动添加股票 ─────────────────────────────────────────────────────────────

async function handleAddManual(poolId: string) {
  const symbol = manualSymbol.value.trim()
  const validation = validateStockSymbol(symbol)
  if (!validation.valid) {
    manualError.value = validation.error!
    return
  }
  manualError.value = ''
  try {
    await store.addStockManual(poolId, symbol)
    manualSymbol.value = ''
    // 刷新富化股票列表和选股池列表（更新 stock_count）
    await Promise.all([store.fetchEnrichedPoolStocks(poolId), store.fetchPools()])
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    manualError.value = typeof detail === 'string' ? detail : (e?.message || '添加失败')
  }
}

// ─── 批量选择 ─────────────────────────────────────────────────────────────────

const isAllSelected = computed(() => {
  return sortedStocks.value.length > 0 && selectedSymbols.value.size === sortedStocks.value.length
})

const isIndeterminate = computed(() => {
  return selectedSymbols.value.size > 0 && selectedSymbols.value.size < sortedStocks.value.length
})

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedSymbols.value = new Set()
  } else {
    selectedSymbols.value = new Set(sortedStocks.value.map((s) => s.symbol))
  }
}

function toggleSelect(symbol: string) {
  const next = new Set(selectedSymbols.value)
  if (next.has(symbol)) {
    next.delete(symbol)
  } else {
    next.add(symbol)
  }
  selectedSymbols.value = next
}

// ─── 批量移除 ─────────────────────────────────────────────────────────────────

async function handleBatchRemove(poolId: string) {
  const symbols = [...selectedSymbols.value]
  if (!symbols.length) return
  try {
    await store.removeStocksFromPool(poolId, symbols)
    selectedSymbols.value = new Set()
    await Promise.all([store.fetchEnrichedPoolStocks(poolId), store.fetchPools()])
  } catch (e: any) {
    alert(e?.response?.data?.detail || e?.message || '移除失败，请重试')
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

async function loadPools() {
  loadError.value = null
  try {
    await store.fetchPools()
  } catch (e: any) {
    loadError.value = e?.response?.data?.detail || e?.message || '加载选股池失败'
  }
}

onMounted(() => {
  loadPools()
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.stock-pool { max-width: 1200px; }

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

/* ─── 选股池卡片 ────────────────────────────────────────────────────────────── */
.pool-list { display: flex; flex-direction: column; gap: 8px; }

.pool-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  overflow: hidden; transition: border-color 0.15s;
}
.pool-card.expanded { border-color: #58a6ff44; }

.pool-header {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px; cursor: pointer; transition: background 0.12s;
}
.pool-header:hover { background: #1c2128; }
.pool-header:focus { outline: 2px solid #58a6ff44; outline-offset: -2px; }

.expand-icon { font-size: 10px; color: #484f58; flex-shrink: 0; }

.pool-info { flex: 1; min-width: 0; }
.pool-name { font-size: 15px; font-weight: 600; color: #e6edf3; }
.pool-meta { display: block; font-size: 12px; color: #8b949e; margin-top: 2px; }

.pool-actions { display: flex; gap: 4px; flex-shrink: 0; }

/* ─── 选股池详情 ────────────────────────────────────────────────────────────── */
.pool-detail {
  padding: 12px 16px 16px;
  border-top: 1px solid #21262d;
}

.empty-pool {
  text-align: center; padding: 30px 0;
  font-size: 14px; color: #8b949e;
}

/* ─── 手动添加股票栏 ────────────────────────────────────────────────────────── */
.add-stock-bar {
  display: flex; align-items: flex-start; gap: 8px; margin-bottom: 12px;
}
.add-stock-input-wrap { display: flex; flex-direction: column; flex: 0 0 200px; }

/* ─── 排序栏 ────────────────────────────────────────────────────────────────── */
.sort-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 16px; background: #161b22; border: 1px solid #30363d;
  border-bottom: none; border-radius: 8px 8px 0 0; margin-bottom: 0;
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

/* ─── 股票表格 ──────────────────────────────────────────────────────────────── */
.stock-table {
  width: 100%; border-collapse: collapse;
  background: #0d1117; border: 1px solid #21262d;
  border-radius: 0 0 6px 6px; overflow: hidden; font-size: 14px;
}
.stock-table thead tr { background: #1c2128; border-bottom: 1px solid #30363d; }
.stock-table th {
  padding: 8px 12px; text-align: left; color: #8b949e;
  font-weight: 600; font-size: 13px; white-space: nowrap;
}
.stock-table td { padding: 8px 12px; color: #e6edf3; vertical-align: middle; }
.stock-table tbody tr { border-bottom: 1px solid #21262d; }
.stock-table tbody tr:last-child { border-bottom: none; }

.th-checkbox, .td-checkbox { width: 36px; text-align: center; }

/* ─── 主行 ─────────────────────────────────────────────────────────────────── */
.stock-row {
  border-bottom: 1px solid #21262d; cursor: pointer;
  transition: background 0.12s;
}
.stock-row:hover { background: #1c2128; }
.stock-row.expanded { background: #1c2128; }
.stock-row:focus { outline: 2px solid #58a6ff44; outline-offset: -2px; }

.symbol-cell { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.symbol-code { font-family: monospace; font-weight: 600; color: #58a6ff; }
.time-cell { font-size: 12px; color: #484f58; white-space: nowrap; }

/* ─── 买入参考价 ────────────────────────────────────────────────────────────── */
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

/* ─── 信号摘要 ──────────────────────────────────────────────────────────────── */
.signals-cell { color: #8b949e; white-space: nowrap; }
.signal-count { font-size: 13px; }
.fake-breakout-badge {
  display: inline-block; margin-left: 6px;
  background: #3a1a1a; color: #f85149; border: 1px solid #f8514944;
  font-size: 11px; padding: 1px 7px; border-radius: 8px; font-weight: 600;
}

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
  display: flex; gap: 6px; margin-bottom: 6px;
}
.adj-btn {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.adj-btn:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.adj-btn.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.adj-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.detail-header {
  font-size: 13px; font-weight: 600; color: #8b949e;
  margin-bottom: 10px;
}
.detail-empty { font-size: 13px; color: #484f58; }

/* ─── 信号强度图例 ──────────────────────────────────────────────────────────── */
.signal-strength-legend {
  font-size: 11px; color: #6e7681; margin-bottom: 8px; line-height: 1.6;
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

/* ─── 板块分类 ──────────────────────────────────────────────────────────────── */
.sector-classifications {
  margin-top: 14px; padding-top: 14px; border-top: 1px solid #21262d;
}
.sector-columns { display: flex; gap: 16px; }
.sector-column { flex: 1; min-width: 0; }
.sector-source-title {
  font-size: 12px; font-weight: 600; color: #8b949e; margin-bottom: 8px;
}
.sector-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.sector-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; background: #1c2128; color: #e6edf3; border: 1px solid #30363d;
}
.sector-empty { font-size: 12px; color: #484f58; }

/* ─── 维度分组标题 ──────────────────────────────────────────────────────────── */
.dimension-header {
  width: 100%; font-size: 12px; font-weight: 600; color: #8b949e;
  margin-top: 8px; margin-bottom: 4px; border-bottom: 1px solid #21262d;
}
.dimension-header:first-child { margin-top: 0; }

/* ─── 对话框 ────────────────────────────────────────────────────────────────── */
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.dialog {
  background: #161b22; border: 1px solid #30363d; border-radius: 10px;
  width: 420px; max-width: 90vw; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
}
.dialog-title {
  font-size: 16px; color: #e6edf3; margin: 0;
  padding: 16px 20px; border-bottom: 1px solid #21262d;
}
.dialog-body { padding: 16px 20px; }
.dialog-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid #21262d;
}

.field-label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 6px; }
.field-error { display: block; font-size: 12px; color: #f85149; margin-top: 4px; }

.delete-confirm-text { font-size: 14px; color: #e6edf3; margin: 0 0 8px; }
.delete-confirm-hint { font-size: 13px; color: #8b949e; margin: 0; }

/* ─── 输入框 ────────────────────────────────────────────────────────────────── */
.input {
  width: 100%; padding: 7px 10px; font-size: 14px;
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  color: #e6edf3; outline: none; transition: border-color 0.15s;
  box-sizing: border-box;
}
.input:focus { border-color: #58a6ff; }
.input::placeholder { color: #484f58; }

/* ─── 按钮 ──────────────────────────────────────────────────────────────────── */
.btn {
  background: #238636; color: #fff; border: none; padding: 7px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
}
.btn:hover:not(:disabled) { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary { background: #238636; }
.btn-primary:hover:not(:disabled) { background: #2ea043; }

.btn-outline {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
}
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }

.btn-danger { background: #da3633; }
.btn-danger:hover:not(:disabled) { background: #f85149; }

.btn-sm { padding: 5px 12px; font-size: 13px; }

.btn-icon {
  background: none; border: 1px solid transparent; cursor: pointer;
  font-size: 14px; padding: 4px 6px; border-radius: 4px;
  transition: background 0.12s, border-color 0.12s;
}
.btn-icon:hover { background: #21262d; border-color: #30363d; }
.btn-icon-danger:hover { background: #3a1a1a; border-color: #f8514944; }

/* ─── 响应式 ────────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .add-stock-bar { flex-wrap: wrap; }
  .add-stock-input-wrap { flex: 1 1 100%; }
  .detail-charts-container { flex-direction: column; }
  .detail-charts-container > .detail-chart { width: 100%; }
}
</style>
