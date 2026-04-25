<template>
  <div v-if="shouldShow" class="preview-chart">
    <!-- 股票代码选择器：多股票表时显示 -->
    <div v-if="props.availableCodes && props.availableCodes.length > 0" class="code-selector">
      <label class="code-selector-label" for="chart-code-select">股票代码：</label>
      <select
        id="chart-code-select"
        class="code-selector-select"
        :value="props.selectedCode ?? ''"
        @change="emit('update:selectedCode', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="c in props.availableCodes" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>
    <!-- 列选择器：仅折线图/柱状图时显示 -->
    <div v-if="showColumnSelector" class="column-selector">
      <span class="column-selector-label">展示列：</span>
      <label
        v-for="col in numericColumns"
        :key="col.name"
        class="column-selector-item"
      >
        <input
          type="checkbox"
          :value="col.name"
          :checked="activeColumns.includes(col.name)"
          @change="toggleColumn(col.name)"
        />
        <span class="column-selector-text">{{ col.label }}</span>
      </label>
    </div>
    <v-chart
      :option="chartOption"
      :autoresize="true"
      class="preview-chart-echart"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * PreviewChart — 数据预览图表组件
 *
 * 根据 chartType 渲染不同类型的 ECharts 图表：
 * - candlestick：K 线图（需要 open/high/low/close + time 列）
 * - line：折线图（数值列 vs 时间列）
 * - null：不渲染（隐藏组件）
 *
 * 数据不足（< 2 个数据点）时隐藏图表。
 *
 * 对应需求：4.1-4.4
 */
import { computed, watch } from 'vue'
import type { ColumnInfo } from '@/stores/tusharePreview'
import { getDefaultSelectedColumns } from '@/stores/tusharePreview'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  CanvasRenderer,
])

// ─── Props ────────────────────────────────────────────────────────────────────

const props = defineProps<{
  chartType: 'candlestick' | 'line' | 'bar' | null
  rows: Record<string, unknown>[]
  timeField: string | null
  columns: ColumnInfo[]
  selectedColumns?: string[]
  availableCodes?: string[]
  selectedCode?: string | null
}>()

const emit = defineEmits<{
  'update:selectedColumns': [value: string[]]
  'update:selectedCode': [value: string]
}>()

// ─── K 线图所需列名 ──────────────────────────────────────────────────────────

const CANDLESTICK_FIELDS = ['open', 'high', 'low', 'close'] as const

// ─── 计算属性 ──────────────────────────────────────────────────────────────────

/** 判断 K 线图是否具备所需的 OHLC 列 */
const hasCandlestickColumns = computed(() => {
  const colNames = new Set(props.columns.map((c) => c.name))
  return CANDLESTICK_FIELDS.every((f) => colNames.has(f))
})

/** 获取数值类型的列（用于折线图/柱状图） */
const numericColumns = computed(() => {
  return props.columns.filter(
    (c) => c.type === 'number' && c.name !== props.timeField,
  )
})

/** 是否显示列选择器（仅折线图/柱状图） */
const showColumnSelector = computed(() => {
  return (props.chartType === 'line' || props.chartType === 'bar') && numericColumns.value.length > 0
})

/** 当前生效的选中列名列表 */
const activeColumns = computed(() => {
  if (props.selectedColumns && props.selectedColumns.length > 0) {
    // 过滤掉不在当前数值列中的列名
    const validNames = new Set(numericColumns.value.map((c) => c.name))
    const filtered = props.selectedColumns.filter((name) => validNames.has(name))
    return filtered.length > 0 ? filtered : getDefaultSelectedColumns(numericColumns.value.map((c) => c.name))
  }
  return getDefaultSelectedColumns(numericColumns.value.map((c) => c.name))
})

/** 用于折线图/柱状图的列（根据 activeColumns 过滤） */
const chartColumns = computed(() => {
  const active = new Set(activeColumns.value)
  return numericColumns.value.filter((c) => active.has(c.name))
})

/** 当数值列变化时，自动发出默认选中列 */
watch(
  () => numericColumns.value.map((c) => c.name).join(','),
  () => {
    if (props.chartType === 'line' || props.chartType === 'bar') {
      const defaults = getDefaultSelectedColumns(numericColumns.value.map((c) => c.name))
      emit('update:selectedColumns', defaults)
    }
  },
)

/** 切换列选中状态 */
function toggleColumn(colName: string) {
  const current = [...activeColumns.value]
  const idx = current.indexOf(colName)
  if (idx >= 0) {
    // 至少保留一列
    if (current.length > 1) {
      current.splice(idx, 1)
    }
  } else {
    current.push(colName)
  }
  emit('update:selectedColumns', current)
}

/** 是否应该显示图表 */
const shouldShow = computed(() => {
  // chartType 为 null 时不渲染
  if (!props.chartType) return false
  // 数据不足（< 2 个数据点）时隐藏
  if (props.rows.length < 2) return false
  // 需要时间字段
  if (!props.timeField) return false
  // K 线图需要 OHLC 列
  if (props.chartType === 'candlestick' && !hasCandlestickColumns.value) return false
  // 折线图需要至少一个数值列
  if (props.chartType === 'line' && numericColumns.value.length === 0) return false
  // 柱状图需要至少一个数值列
  if (props.chartType === 'bar' && numericColumns.value.length === 0) return false
  return true
})

/** 时间轴数据（X 轴） */
const timeData = computed(() => {
  if (!props.timeField) return []
  return props.rows.map((row) => String(row[props.timeField!] ?? ''))
})

/** ECharts 配置项 */
const chartOption = computed(() => {
  if (!shouldShow.value) return {}

  if (props.chartType === 'candlestick') {
    return buildCandlestickOption()
  }
  if (props.chartType === 'line') {
    return buildLineOption()
  }
  if (props.chartType === 'bar') {
    return buildBarOption()
  }
  return {}
})

// ─── 图表构建函数 ──────────────────────────────────────────────────────────────

/** 构建 K 线图配置 */
function buildCandlestickOption() {
  const times = timeData.value
  // ECharts candlestick 数据格式: [open, close, low, high]
  const ohlc = props.rows.map((row) => [
    Number(row.open ?? 0),
    Number(row.close ?? 0),
    Number(row.low ?? 0),
    Number(row.high ?? 0),
  ])

  // 成交量（如果有 volume 列）
  const hasVolume = props.columns.some((c) => c.name === 'volume')
  const volumes = hasVolume
    ? props.rows.map((row) => Number(row.volume ?? 0))
    : null

  const grids = volumes
    ? [
        { left: 60, right: 20, top: 30, height: '55%' },
        { left: 60, right: 20, top: '72%', height: '18%' },
      ]
    : [{ left: 60, right: 20, top: 30, bottom: 40 }]

  const xAxes: any[] = [
    {
      type: 'category',
      data: times,
      gridIndex: 0,
      axisLabel: { color: '#8b949e', fontSize: 10 },
      axisLine: { lineStyle: { color: '#30363d' } },
    },
  ]
  if (volumes) {
    xAxes.push({
      type: 'category',
      data: times,
      gridIndex: 1,
      show: false,
    })
  }

  const yAxes: any[] = [
    {
      scale: true,
      gridIndex: 0,
      splitLine: { lineStyle: { color: '#21262d' } },
      axisLabel: { color: '#8b949e' },
    },
  ]
  if (volumes) {
    yAxes.push({
      scale: true,
      gridIndex: 1,
      splitLine: { show: false },
      axisLabel: { show: false },
    })
  }

  const series: any[] = [
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
  ]
  if (volumes) {
    series.push({
      type: 'bar',
      data: volumes,
      xAxisIndex: 1,
      yAxisIndex: 1,
      itemStyle: { color: '#30363d' },
    })
  }

  const dataZoomXAxisIndex = volumes ? [0, 1] : [0]

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#161b22',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        if (!p || !p.data) return ''
        const idx = p.dataIndex
        const [open, close, low, high] = ohlc[idx]
        const chg = open ? ((close - open) / open * 100).toFixed(2) : '0.00'
        const color = close >= open ? '#f85149' : '#3fb950'
        let html = `<div style="font-size:12px;line-height:1.6">
          <div style="font-weight:600">${times[idx]}</div>
          <div>开 ${open.toFixed(2)}　高 ${high.toFixed(2)}</div>
          <div>低 ${low.toFixed(2)}　收 ${close.toFixed(2)}</div>
          <div>涨跌幅 <span style="color:${color};font-weight:600">${chg}%</span></div>`
        if (volumes) {
          const vol = (volumes[idx] / 10000).toFixed(0)
          html += `<div>成交量 ${vol} 万手</div>`
        }
        html += '</div>'
        return html
      },
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [{ type: 'inside', xAxisIndex: dataZoomXAxisIndex, start: 0, end: 100 }],
    series,
  }
}

/** 构建折线图配置 */
function buildLineOption() {
  const times = timeData.value
  const cols = chartColumns.value

  // 颜色列表（暗色主题友好）
  const colors = ['#58a6ff', '#3fb950', '#f0883e', '#bc8cff', '#f85149', '#79c0ff', '#56d364']

  const series = cols.map((col, idx) => ({
    name: col.label,
    type: 'line' as const,
    data: props.rows.map((row) => Number(row[col.name] ?? 0)),
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1.5 },
    itemStyle: { color: colors[idx % colors.length] },
  }))

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#161b22',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
    },
    legend: {
      data: cols.map((c) => c.label),
      textStyle: { color: '#8b949e', fontSize: 11 },
      top: 0,
    },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: '#8b949e', fontSize: 10 },
      axisLine: { lineStyle: { color: '#30363d' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#21262d' } },
      axisLabel: { color: '#8b949e' },
    },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    series,
  }
}

/** 构建柱状图配置 */
function buildBarOption() {
  const times = timeData.value
  const cols = chartColumns.value

  const colors = ['#58a6ff', '#3fb950', '#f0883e', '#bc8cff', '#f85149', '#79c0ff', '#56d364']

  const series = cols.map((col, idx) => ({
    name: col.label,
    type: 'bar' as const,
    data: props.rows.map((row) => Number(row[col.name] ?? 0)),
    itemStyle: { color: colors[idx % colors.length] },
  }))

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#161b22',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
    },
    legend: {
      data: cols.map((c) => c.label),
      textStyle: { color: '#8b949e', fontSize: 11 },
      top: 0,
    },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: '#8b949e', fontSize: 10 },
      axisLine: { lineStyle: { color: '#30363d' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#21262d' } },
      axisLabel: { color: '#8b949e' },
    },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    series,
  }
}
</script>

<style scoped>
.preview-chart {
  width: 100%;
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 6px;
  padding: 12px;
}

.code-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  margin-bottom: 4px;
  border-bottom: 1px solid #21262d;
}

.code-selector-label {
  color: #8b949e;
  font-size: 12px;
  white-space: nowrap;
}

.code-selector-select {
  background: #161b22;
  color: #e6edf3;
  border: 1px solid #30363d;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  min-width: 120px;
}

.code-selector-select:focus {
  outline: none;
  border-color: #58a6ff;
}

.column-selector {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  margin-bottom: 8px;
  border-bottom: 1px solid #21262d;
}

.column-selector-label {
  color: #8b949e;
  font-size: 12px;
  white-space: nowrap;
}

.column-selector-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
}

.column-selector-item input[type="checkbox"] {
  accent-color: #58a6ff;
  cursor: pointer;
}

.column-selector-text {
  color: #c9d1d9;
  font-size: 12px;
}

.preview-chart-echart {
  width: 100%;
  height: 400px;
}
</style>
