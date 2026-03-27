<template>
  <div class="screener">
    <h1 class="page-title">智能选股</h1>

    <!-- 策略模板选择 -->
    <section class="strategy-section" aria-label="策略模板">
      <h2 class="section-title">策略模板</h2>
      <div class="strategy-bar">
        <select v-model="activeStrategyId" class="input" aria-label="选择策略模板" @change="onStrategySwitch">
          <option value="">-- 选择策略 --</option>
          <option v-for="s in screenerStore.strategies" :key="s.id" :value="s.id">
            {{ s.name }} {{ s.is_active ? '(当前)' : '' }}
          </option>
        </select>
        <button class="btn" @click="runScreen" :disabled="running">
          {{ running ? '选股中...' : '执行选股' }}
        </button>
        <button class="btn btn-outline" @click="showCreateDialog = true">新建策略</button>
      </div>
    </section>

    <!-- 因子配置 -->
    <section class="factor-config" aria-label="因子配置">
      <h2 class="section-title">因子组合配置</h2>
      <div class="config-grid">
        <!-- 逻辑运算 -->
        <div class="config-item">
          <label for="logic-select">逻辑运算</label>
          <select id="logic-select" v-model="config.logic" class="input">
            <option value="AND">AND（全部满足）</option>
            <option value="OR">OR（满足其一）</option>
          </select>
        </div>

        <!-- 均线周期 -->
        <div class="config-item">
          <label for="ma-periods">均线周期</label>
          <input id="ma-periods" v-model="config.maPeriods" class="input" placeholder="5,10,20,60,120" />
        </div>

        <!-- 趋势打分阈值 -->
        <div class="config-item">
          <label for="trend-threshold">趋势打分阈值</label>
          <input id="trend-threshold" v-model.number="config.trendThreshold" type="number" min="0" max="100" class="input" />
        </div>

        <!-- 换手率范围 -->
        <div class="config-item">
          <label for="turnover-min">换手率范围 (%)</label>
          <div class="range-inputs">
            <input id="turnover-min" v-model.number="config.turnoverMin" type="number" step="0.1" class="input small" placeholder="3" />
            <span>—</span>
            <input v-model.number="config.turnoverMax" type="number" step="0.1" class="input small" placeholder="15" aria-label="换手率上限" />
          </div>
        </div>
      </div>

      <!-- 因子权重 -->
      <h3 class="subsection-title">因子权重</h3>
      <div class="weight-grid">
        <div v-for="f in factorTypes" :key="f.key" class="weight-item">
          <label :for="`weight-${f.key}`">{{ f.label }}</label>
          <input :id="`weight-${f.key}`" v-model.number="config.weights[f.key]" type="number" min="0" max="1" step="0.1" class="input small" />
        </div>
      </div>

      <!-- MACD 参数 -->
      <h3 class="subsection-title">MACD 参数</h3>
      <div class="config-grid">
        <div class="config-item">
          <label for="macd-fast">快线周期</label>
          <input id="macd-fast" v-model.number="config.macdFast" type="number" class="input small" />
        </div>
        <div class="config-item">
          <label for="macd-slow">慢线周期</label>
          <input id="macd-slow" v-model.number="config.macdSlow" type="number" class="input small" />
        </div>
        <div class="config-item">
          <label for="macd-signal">信号线周期</label>
          <input id="macd-signal" v-model.number="config.macdSignal" type="number" class="input small" />
        </div>
      </div>
    </section>

    <!-- 新建策略对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog" role="dialog" aria-label="新建策略">
        <h3>新建策略模板</h3>
        <label for="new-strategy-name">策略名称</label>
        <input id="new-strategy-name" v-model="newStrategyName" class="input full" placeholder="输入策略名称" />
        <div class="dialog-actions">
          <button class="btn" @click="createStrategy">保存</button>
          <button class="btn btn-outline" @click="showCreateDialog = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useScreenerStore } from '@/stores/screener'
import { apiClient } from '@/api'

const screenerStore = useScreenerStore()
const activeStrategyId = ref('')
const running = ref(false)
const showCreateDialog = ref(false)
const newStrategyName = ref('')

const factorTypes = [
  { key: 'technical', label: '技术面' },
  { key: 'money_flow', label: '资金面' },
  { key: 'fundamental', label: '基本面' },
  { key: 'sector', label: '板块面' },
]

const config = reactive({
  logic: 'AND' as 'AND' | 'OR',
  maPeriods: '5,10,20,60,120',
  trendThreshold: 80,
  turnoverMin: 3,
  turnoverMax: 15,
  weights: { technical: 0.4, money_flow: 0.3, fundamental: 0.2, sector: 0.1 } as Record<string, number>,
  macdFast: 12,
  macdSlow: 26,
  macdSignal: 9,
})

async function onStrategySwitch() {
  if (!activeStrategyId.value) return
  try {
    await screenerStore.activateStrategy(activeStrategyId.value)
  } catch { /* handle error */ }
}

async function runScreen() {
  running.value = true
  try {
    await apiClient.post('/screen/run', {
      strategy_id: activeStrategyId.value || undefined,
      config: {
        logic: config.logic,
        ma_periods: config.maPeriods.split(',').map(Number),
        trend_threshold: config.trendThreshold,
        turnover_range: [config.turnoverMin, config.turnoverMax],
        weights: config.weights,
        indicator_params: { macd: { fast: config.macdFast, slow: config.macdSlow, signal: config.macdSignal } },
      },
    })
    await screenerStore.fetchResults()
  } catch { /* handle error */ }
  running.value = false
}

async function createStrategy() {
  if (!newStrategyName.value.trim()) return
  try {
    await apiClient.post('/strategies', {
      name: newStrategyName.value,
      config: {
        logic: config.logic,
        ma_periods: config.maPeriods.split(',').map(Number),
        weights: config.weights,
      },
    })
    await screenerStore.fetchStrategies()
    showCreateDialog.value = false
    newStrategyName.value = ''
  } catch { /* handle error */ }
}

onMounted(() => {
  screenerStore.fetchStrategies()
})
</script>

<style scoped>
.screener { max-width: 1000px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.subsection-title { font-size: 14px; margin: 16px 0 8px; color: #8b949e; }

.strategy-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 24px; }
.strategy-section { margin-bottom: 24px; }
.factor-config { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }

.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.range-inputs { display: flex; align-items: center; gap: 6px; }
.range-inputs span { color: #484f58; }

.weight-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.weight-item { display: flex; flex-direction: column; gap: 4px; }
.weight-item label { font-size: 13px; color: #8b949e; }

.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.input.small { width: 100px; }
.input.full { width: 100%; }
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap;
}
.btn:hover { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover { color: #e6edf3; border-color: #8b949e; }

.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex;
  align-items: center; justify-content: center; z-index: 100;
}
.dialog {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 24px; width: 400px; max-width: 90vw;
}
.dialog h3 { margin-bottom: 16px; color: #e6edf3; }
.dialog label { font-size: 13px; color: #8b949e; display: block; margin-bottom: 4px; }
.dialog-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
</style>
