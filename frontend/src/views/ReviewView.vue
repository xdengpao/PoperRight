<template>
  <div class="review-view">
    <h1 class="page-title">复盘分析</h1>

    <!-- 日期选择 & 策略选择 -->
    <div class="toolbar">
      <label for="review-date" class="sr-only">复盘日期</label>
      <input id="review-date" v-model="reviewDate" type="date" class="input" />
      <select v-model="selectedStrategy" class="input" aria-label="选择策略">
        <option value="">全部策略</option>
        <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <select v-model="period" class="input" aria-label="报表周期">
        <option value="daily">日报</option>
        <option value="weekly">周报</option>
        <option value="monthly">月报</option>
      </select>
      <button class="btn" @click="loadReview">查询</button>
    </div>

    <!-- 每日复盘报告 -->
    <section v-if="dailyReview" class="card" aria-label="每日复盘报告">
      <h2 class="section-title">每日复盘报告 — {{ reviewDate }}</h2>
      <div class="review-stats">
        <div class="stat">
          <span class="label">选股胜率</span>
          <span class="value">{{ (dailyReview.win_rate * 100).toFixed(1) }}%</span>
        </div>
        <div class="stat">
          <span class="label">盈利笔数</span>
          <span class="value up">{{ dailyReview.win_count }}</span>
        </div>
        <div class="stat">
          <span class="label">亏损笔数</span>
          <span class="value down">{{ dailyReview.loss_count }}</span>
        </div>
        <div class="stat">
          <span class="label">总盈亏</span>
          <span class="value" :class="dailyReview.total_pnl >= 0 ? 'up' : 'down'">
            {{ dailyReview.total_pnl >= 0 ? '+' : '' }}{{ dailyReview.total_pnl.toFixed(2) }}
          </span>
        </div>
      </div>

      <!-- 成功/失败案例 -->
      <div class="case-grid">
        <div class="case-box">
          <h3>成功案例</h3>
          <ul>
            <li v-for="c in dailyReview.success_cases" :key="c.symbol">
              <span class="mono">{{ c.symbol }}</span> — {{ c.reason }}
              <span class="up">+{{ (c.return_pct * 100).toFixed(2) }}%</span>
            </li>
            <li v-if="!dailyReview.success_cases?.length" class="empty-li">暂无</li>
          </ul>
        </div>
        <div class="case-box">
          <h3>失败案例</h3>
          <ul>
            <li v-for="c in dailyReview.failure_cases" :key="c.symbol">
              <span class="mono">{{ c.symbol }}</span> — {{ c.reason }}
              <span class="down">{{ (c.return_pct * 100).toFixed(2) }}%</span>
            </li>
            <li v-if="!dailyReview.failure_cases?.length" class="empty-li">暂无</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 策略绩效图表 -->
    <section class="card" aria-label="策略绩效图表">
      <h2 class="section-title">策略绩效</h2>
      <div class="chart-row">
        <div ref="barChartRef" class="chart" role="img" aria-label="收益柱状图"></div>
        <div ref="lineChartRef" class="chart" role="img" aria-label="累计收益折线图"></div>
      </div>
      <div ref="pieChartRef" class="chart chart-small" role="img" aria-label="盈亏分布饼图"></div>
    </section>

    <!-- 多策略对比 -->
    <section v-if="compareData.length > 1" class="card" aria-label="多策略对比">
      <h2 class="section-title">多策略对比</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th scope="col">策略名称</th>
            <th scope="col">累计收益</th>
            <th scope="col">胜率</th>
            <th scope="col">最大回撤</th>
            <th scope="col">夏普比率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in compareData" :key="c.strategy_name">
            <td>{{ c.strategy_name }}</td>
            <td :class="c.total_return >= 0 ? 'up' : 'down'">{{ (c.total_return * 100).toFixed(2) }}%</td>
            <td>{{ (c.win_rate * 100).toFixed(1) }}%</td>
            <td class="down">{{ (c.max_drawdown * 100).toFixed(2) }}%</td>
            <td>{{ c.sharpe_ratio.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { apiClient } from '@/api'
import * as echarts from 'echarts'

interface DailyReview {
  win_rate: number; win_count: number; loss_count: number; total_pnl: number
  success_cases: { symbol: string; reason: string; return_pct: number }[]
  failure_cases: { symbol: string; reason: string; return_pct: number }[]
}
interface StrategyCompare {
  strategy_name: string; total_return: number; win_rate: number
  max_drawdown: number; sharpe_ratio: number
}
interface StrategyReport {
  dates: string[]; daily_returns: number[]; cumulative_returns: number[]
  win_count: number; loss_count: number
}

const reviewDate = ref(new Date().toISOString().slice(0, 10))
const selectedStrategy = ref('')
const period = ref('daily')
const strategies = ref<{ id: string; name: string }[]>([])
const dailyReview = ref<DailyReview | null>(null)
const compareData = ref<StrategyCompare[]>([])
const report = ref<StrategyReport | null>(null)

const barChartRef = ref<HTMLElement | null>(null)
const lineChartRef = ref<HTMLElement | null>(null)
const pieChartRef = ref<HTMLElement | null>(null)
let barChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

async function loadReview() {
  try {
    const [dailyRes, reportRes, compareRes] = await Promise.all([
      apiClient.get<DailyReview>('/review/daily', { params: { date: reviewDate.value } }),
      apiClient.get<StrategyReport>('/review/strategy-report', {
        params: { strategy_id: selectedStrategy.value || undefined, period: period.value },
      }),
      apiClient.get<StrategyCompare[]>('/review/strategy-compare'),
    ])
    dailyReview.value = dailyRes.data
    report.value = reportRes.data
    compareData.value = compareRes.data
    await nextTick()
    renderCharts()
  } catch { /* handle error */ }
}

function renderCharts() {
  const r = report.value
  if (!r) return

  // 柱状图 - 日收益
  if (barChart) {
    barChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: r.dates, axisLabel: { color: '#8b949e', rotate: 45 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#21262d' } }, axisLabel: { color: '#8b949e' } },
      series: [{
        type: 'bar', data: r.daily_returns.map((v) => ({
          value: (v * 100),
          itemStyle: { color: v >= 0 ? '#f85149' : '#3fb950' },
        })),
      }],
    })
  }

  // 折线图 - 累计收益
  if (lineChart) {
    lineChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: r.dates, axisLabel: { color: '#8b949e', rotate: 45 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#21262d' } }, axisLabel: { color: '#8b949e' } },
      series: [{
        type: 'line', data: r.cumulative_returns.map((v) => (v * 100).toFixed(2)),
        smooth: true, lineStyle: { color: '#58a6ff' }, itemStyle: { color: '#58a6ff' }, symbol: 'none',
        areaStyle: { color: '#58a6ff22' },
      }],
    })
  }

  // 饼图 - 盈亏分布
  if (pieChart) {
    pieChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: [
          { value: r.win_count, name: '盈利', itemStyle: { color: '#f85149' } },
          { value: r.loss_count, name: '亏损', itemStyle: { color: '#3fb950' } },
        ],
        label: { color: '#8b949e' },
      }],
    })
  }
}

async function loadStrategies() {
  try {
    const res = await apiClient.get<{ id: string; name: string }[]>('/strategies')
    strategies.value = res.data
  } catch { /* handle error */ }
}

onMounted(async () => {
  loadStrategies()
  await nextTick()
  if (barChartRef.value) barChart = echarts.init(barChartRef.value)
  if (lineChartRef.value) lineChart = echarts.init(lineChartRef.value)
  if (pieChartRef.value) pieChart = echarts.init(pieChartRef.value)
})

onUnmounted(() => {
  barChart?.dispose()
  lineChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.review-view { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.toolbar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }

.review-stats { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.stat { display: flex; flex-direction: column; gap: 2px; min-width: 120px; }
.stat .label { font-size: 13px; color: #8b949e; }
.stat .value { font-size: 20px; font-weight: 600; color: #e6edf3; }

.case-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.case-box { background: #0d1117; border-radius: 6px; padding: 12px; }
.case-box h3 { font-size: 14px; color: #8b949e; margin-bottom: 8px; }
.case-box ul { list-style: none; }
.case-box li { font-size: 13px; padding: 4px 0; color: #e6edf3; display: flex; gap: 8px; }
.empty-li { color: #484f58; }

.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart { width: 100%; height: 280px; background: #0d1117; border-radius: 6px; }
.chart-small { height: 240px; max-width: 400px; }

.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover { background: #2ea043; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', monospace; }
.up { color: #f85149; }
.down { color: #3fb950; }
</style>
