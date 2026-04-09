<template>
  <div class="minute-kline-panel">
    <!-- 日期标签 -->
    <div class="panel-header">
      <span class="date-label">{{ dateLabel }}</span>
    </div>

    <!-- 周期选择器 -->
    <div class="freq-selector" role="group" aria-label="分钟周期选择">
      <button
        v-for="f in FREQ_OPTIONS"
        :key="f"
        :class="['freq-btn', freq === f && 'active']"
        :aria-pressed="freq === f"
        @click="freq = f"
      >
        {{ f }}
      </button>
    </div>

    <!-- 图表区域 -->
    <div class="chart-area">
      <div v-if="loading" class="chart-placeholder">加载分钟K线中...</div>
      <div v-else-if="error" class="chart-placeholder chart-error">{{ error }}</div>
      <div v-else-if="!bars.length" class="chart-placeholder">该交易日暂无分钟K线数据</div>
      <v-chart
        v-else
        :option="chartOption"
        :autoresize="true"
        class="minute-kline-echart"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { apiClient } from '@/api'
import { type KlineBar, minuteKlineCache, buildCacheKey, buildRequestParams } from './minuteKlineUtils'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

// ─── 常量 ─────────────────────────────────────────────────────────────────────

const FREQ_OPTIONS = ['1m', '5m', '15m', '30m', '60m'] as const

// ─── Props & Emits ────────────────────────────────────────────────────────────

const props = defineProps<{
  symbol: string
  selectedDate: string | null
  latestTradeDate: string
}>()

const emit = defineEmits<{
  (e: 'loading', value: boolean): void
}>()

// ─── 内部状态 ──────────────────────────────────────────────────────────────────

const freq = ref<string>('5m')
const bars = ref<KlineBar[]>([])
const loading = ref(false)
const error = ref('')

// ─── 计算属性 ──────────────────────────────────────────────────────────────────

/** 当前展示日期：优先使用 selectedDate，否则使用 latestTradeDate */
const displayDate = computed(() => props.selectedDate ?? props.latestTradeDate)

/** 日期标签格式: "YYYY-MM-DD 分钟K线" */
const dateLabel = computed(() => `${displayDate.value} 分钟K线`)

/** ECharts 配置项：复用日K线图的蜡烛图 + 成交量柱状图风格 */
const chartOption = computed(() => {
  if (!bars.value.length) return {}

  const times = bars.value.map((b) => b.time.slice(11, 16)) // HH:mm
  const ohlc = bars.value.map((b) => [+b.open, +b.close, +b.low, +b.high])
  const vols = bars.value.map((b) => b.volume)

  return {
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
          <div style="font-weight:600">${times[idx]}</div>
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
      { type: 'category', data: times, gridIndex: 0, axisLabel: { color: '#8b949e', fontSize: 10 } },
      { type: 'category', data: times, gridIndex: 1, show: false },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#21262d' } }, axisLabel: { color: '#8b949e' } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
    series: [
      {
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#f85149',
          color0: '#3fb950',
          borderColor: '#f85149',
          borderColor0: '#3fb950',
        },
      },
      {
        type: 'bar',
        data: vols,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#30363d' },
      },
    ],
  }
})

// ─── 数据加载 ──────────────────────────────────────────────────────────────────

async function loadMinuteKline() {
  const date = displayDate.value
  if (!date) return

  const key = buildCacheKey(props.symbol, date, freq.value)

  // 缓存命中
  if (minuteKlineCache.has(key)) {
    bars.value = minuteKlineCache.get(key)!
    error.value = ''
    return
  }

  loading.value = true
  error.value = ''
  emit('loading', true)

  try {
    const res = await apiClient.get(`/data/kline/${props.symbol}`, {
      params: buildRequestParams(freq.value, date),
    })
    const raw: KlineBar[] = res.data?.bars ?? []
    // 过滤掉非日内数据（time 不含 HH:mm 或为 T00:00:00 的是日K线误入）
    const data = raw.filter((b) => {
      const timePart = b.time.slice(11, 16)
      return timePart && timePart !== '00:00'
    })
    minuteKlineCache.set(key, data)
    bars.value = data
  } catch {
    error.value = '加载分钟K线失败'
    bars.value = []
  } finally {
    loading.value = false
    emit('loading', false)
  }
}

// ─── 侦听器：selectedDate 或 freq 变化时重新加载 ──────────────────────────────

watch(
  [displayDate, freq],
  () => { loadMinuteKline() },
  { immediate: true },
)

// ─── 暴露给测试 ───────────────────────────────────────────────────────────────

defineExpose({ cache: minuteKlineCache, loadMinuteKline })
</script>

<style scoped>
.minute-kline-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.date-label {
  font-size: 13px;
  font-weight: 600;
  color: #8b949e;
}

/* ─── 周期选择器 ────────────────────────────────────────────────────────────── */
.freq-selector {
  display: flex;
  gap: 6px;
}

.freq-btn {
  background: transparent;
  border: 1px solid #30363d;
  color: #8b949e;
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.freq-btn:hover {
  color: #e6edf3;
  border-color: #8b949e;
}

.freq-btn.active {
  background: #1f6feb22;
  color: #58a6ff;
  border-color: #58a6ff;
}

/* ─── 图表区域 ──────────────────────────────────────────────────────────────── */
.chart-area {
  flex: 1;
  min-height: 280px;
}

.minute-kline-echart {
  width: 100%;
  height: 280px;
}

.chart-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 280px;
  color: #8b949e;
  font-size: 13px;
}

.chart-error {
  color: #ffa198;
}
</style>
