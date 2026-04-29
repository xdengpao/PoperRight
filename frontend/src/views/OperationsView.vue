<template>
  <div class="operations-view">
    <div class="page-header">
      <h2>交易计划</h2>
      <button class="btn-primary" @click="openCreateDialog">新建交易计划</button>
    </div>

    <div v-if="store.loading" class="loading-state">加载中...</div>

    <div v-else-if="store.plans.length === 0" class="empty-state">
      <p>暂无交易计划，点击「新建交易计划」开始</p>
    </div>

    <div v-else class="plan-grid">
      <div
        v-for="plan in store.plans"
        :key="plan.id"
        class="plan-card"
        :class="[`status-${plan.status.toLowerCase()}`]"
        @click="goToDetail(plan.id)"
      >
        <div class="card-header">
          <span class="plan-name">{{ plan.name }}</span>
          <span class="status-badge" :class="plan.status.toLowerCase()">{{ statusLabel(plan.status) }}</span>
        </div>
        <div class="card-body">
          <div class="stat-row">
            <span class="stat-label">持仓</span>
            <span class="stat-value">{{ plan.position_count }} / {{ plan.max_positions }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">今日候选</span>
            <span class="stat-value">{{ plan.candidate_count }}</span>
          </div>
          <div class="stat-row" v-if="plan.warning_count > 0">
            <span class="stat-label warning-text">待处理</span>
            <span class="stat-value warning-text">{{ plan.warning_count }}</span>
          </div>
        </div>
        <div class="card-actions" @click.stop>
          <button
            v-if="plan.status === 'ACTIVE'"
            class="btn-sm btn-primary"
            @click="handleRunScreening(plan.id, plan.name)"
          >执行选股</button>
          <button
            v-if="plan.status === 'ACTIVE'"
            class="btn-sm"
            @click="store.updatePlanStatus(plan.id, 'PAUSED')"
          >暂停</button>
          <button
            v-if="plan.status === 'PAUSED'"
            class="btn-sm"
            @click="store.updatePlanStatus(plan.id, 'ACTIVE')"
          >启用</button>
          <button class="btn-sm btn-danger" @click="handleDelete(plan.id, plan.name)">删除</button>
        </div>
      </div>
    </div>

    <!-- 新建交易计划对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog dialog-wide" role="dialog" aria-label="新建交易计划">
        <h3>新建交易计划</h3>

        <!-- 步骤指示器 -->
        <div class="steps">
          <div v-for="(s, i) in stepLabels" :key="i" class="step" :class="{ active: step === i, done: step > i }">
            <span class="step-num">{{ i + 1 }}</span>
            <span class="step-label">{{ s }}</span>
          </div>
        </div>

        <!-- Step 0: 基本信息 -->
        <div v-if="step === 0" class="step-content">
          <div class="form-group">
            <label>计划名称 <span class="required">*</span></label>
            <input v-model="selectedName" maxlength="100" placeholder="如：右侧趋势突破交易计划" />
          </div>
          <div class="form-group">
            <label>关联策略模板 <span class="required">*</span></label>
            <select v-model="selectedStrategyId">
              <option value="" disabled>{{ store.strategies.length ? '选择策略模板' : '加载中...' }}</option>
              <option v-for="s in store.strategies" :key="s.id" :value="s.id">
                {{ s.name }}{{ s.is_builtin ? ' (内置)' : '' }}
              </option>
            </select>
          </div>
          <div v-if="selectedStrategy" class="strategy-preview">
            <h4>策略因子</h4>
            <div class="factor-list">
              <div v-for="f in strategyFactors" :key="f.factor_name" class="factor-tag">
                {{ f.factor_label }}
              </div>
            </div>
            <div class="module-list">
              <span v-for="m in selectedStrategy.enabled_modules" :key="m" class="module-tag">{{ moduleLabel(m) }}</span>
            </div>
          </div>
        </div>

        <!-- Step 1: 候选股筛选规则 -->
        <div v-if="step === 1" class="step-content">
          <div class="config-grid">
            <div class="form-group">
              <label>最低 trend_score</label>
              <input type="number" v-model.number="form.candidate_filter.min_trend_score" min="0" max="100" step="5" />
              <span class="hint">推荐 80，越高信号越严格</span>
            </div>
            <div class="form-group">
              <label>板块过热天数</label>
              <input type="number" v-model.number="form.candidate_filter.sector_overheat_days" min="1" max="20" />
              <span class="hint">连续上涨超过此天数排除</span>
            </div>
            <div class="form-group">
              <label>板块过热涨幅 %</label>
              <input type="number" v-model.number="form.candidate_filter.sector_overheat_pct" min="1" max="50" step="1" />
              <span class="hint">涨幅超过此百分比排除</span>
            </div>
          </div>
          <div class="toggle-grid">
            <label class="toggle-item">
              <input type="checkbox" v-model="form.candidate_filter.require_new_signal" />
              <span>要求 NEW 信号新鲜度</span>
            </label>
            <label class="toggle-item">
              <input type="checkbox" v-model="form.candidate_filter.require_strong_signal" />
              <span>要求 STRONG 信号强度</span>
            </label>
            <label class="toggle-item">
              <input type="checkbox" v-model="form.candidate_filter.exclude_fake_breakout" />
              <span>排除假突破</span>
            </label>
          </div>
        </div>

        <!-- Step 2: 止损配置 -->
        <div v-if="step === 2" class="step-content">
          <h4>分阶段止损参数</h4>
          <div class="config-grid">
            <div class="form-group">
              <label>固定止损 %</label>
              <input type="number" v-model.number="form.stage_stop_config.fixed_stop_pct" min="1" max="20" step="0.5" />
              <span class="hint">买入当日最大亏损限制</span>
            </div>
            <div class="form-group">
              <label>移动止盈触发 %</label>
              <input type="number" v-model.number="form.stage_stop_config.trailing_trigger_pct" min="1" max="30" step="0.5" />
              <span class="hint">盈利达到此比例后启用移动止盈</span>
            </div>
            <div class="form-group">
              <label>移动止盈回撤 %</label>
              <input type="number" v-model.number="form.stage_stop_config.trailing_stop_pct" min="1" max="20" step="0.5" />
              <span class="hint">从高点回撤此比例触发卖出</span>
            </div>
            <div class="form-group">
              <label>收紧止盈触发 %</label>
              <input type="number" v-model.number="form.stage_stop_config.tight_trigger_pct" min="1" max="50" step="0.5" />
            </div>
            <div class="form-group">
              <label>收紧止盈回撤 %</label>
              <input type="number" v-model.number="form.stage_stop_config.tight_stop_pct" min="1" max="10" step="0.5" />
            </div>
            <div class="form-group">
              <label>长持评估天数</label>
              <input type="number" v-model.number="form.stage_stop_config.long_hold_days" min="1" max="60" />
              <span class="hint">持仓超此天数评估趋势</span>
            </div>
            <div class="form-group">
              <label>长持趋势阈值</label>
              <input type="number" v-model.number="form.stage_stop_config.long_hold_trend_threshold" min="0" max="100" />
            </div>
            <div class="form-group">
              <label>趋势止损均线</label>
              <input type="number" v-model.number="form.stage_stop_config.trend_stop_ma" min="5" max="120" />
              <span class="hint">跌破此均线无条件止损</span>
            </div>
          </div>
        </div>

        <!-- Step 3: 仓位控制 -->
        <div v-if="step === 3" class="step-content">
          <div class="config-grid">
            <div class="form-group">
              <label>单票最大仓位 %</label>
              <input type="number" v-model.number="form.position_control.max_stock_weight" min="1" max="100" />
              <span class="hint">不超过总资金的此比例</span>
            </div>
            <div class="form-group">
              <label>同板块最大仓位 %</label>
              <input type="number" v-model.number="form.position_control.max_sector_weight" min="1" max="100" />
            </div>
            <div class="form-group">
              <label>最大持仓数</label>
              <input type="number" v-model.number="form.position_control.max_positions" min="1" max="50" />
            </div>
            <div class="form-group">
              <label>总仓位上限 %</label>
              <input type="number" v-model.number="form.position_control.max_total_weight" min="1" max="100" />
              <span class="hint">NORMAL 环境下推荐 80%</span>
            </div>
          </div>
        </div>

        <!-- Step 4: 市场环境适配 -->
        <div v-if="step === 4" class="step-content">
          <div v-for="level in (['normal', 'caution', 'danger'] as const)" :key="level" class="profile-section">
            <h4>
              <span class="level-dot" :class="level"></span>
              {{ levelLabel(level) }}
            </h4>
            <div class="config-grid">
              <template v-if="level !== 'danger'">
                <div class="form-group">
                  <label>ma_trend 阈值</label>
                  <input type="number" v-model.number="form.market_profile[level].ma_trend" min="0" max="100" />
                </div>
                <div class="form-group">
                  <label>money_flow 阈值</label>
                  <input type="number" v-model.number="form.market_profile[level].money_flow" min="0" max="100" />
                </div>
                <div class="form-group">
                  <label>RSI 下限</label>
                  <input type="number" v-model.number="form.market_profile[level].rsi_low" min="0" max="100" />
                </div>
                <div class="form-group">
                  <label>RSI 上限</label>
                  <input type="number" v-model.number="form.market_profile[level].rsi_high" min="0" max="100" />
                </div>
                <div class="form-group">
                  <label>换手率下限 %</label>
                  <input type="number" v-model.number="form.market_profile[level].turnover_low" min="0" max="50" step="0.5" />
                </div>
                <div class="form-group">
                  <label>换手率上限 %</label>
                  <input type="number" v-model.number="form.market_profile[level].turnover_high" min="0" max="50" step="0.5" />
                </div>
                <div class="form-group">
                  <label>板块排名阈值</label>
                  <input type="number" v-model.number="form.market_profile[level].sector_rank" min="1" max="100" />
                </div>
                <div class="form-group">
                  <label>总仓位上限 %</label>
                  <input type="number" v-model.number="form.market_profile[level].max_total_weight" min="0" max="100" />
                </div>
              </template>
              <template v-else>
                <div class="form-group">
                  <label>
                    <input type="checkbox" v-model="form.market_profile.danger.suspend_new_positions" />
                    暂停新开仓
                  </label>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="dialog-actions">
          <button class="btn-secondary" @click="showCreateDialog = false">取消</button>
          <button v-if="step > 0" class="btn-secondary" @click="step--">上一步</button>
          <button v-if="step < 4" class="btn-primary" @click="nextStep" :disabled="!canNext">下一步</button>
          <button v-if="step === 4" class="btn-primary" @click="handleCreate" :disabled="creating">
            {{ creating ? '创建中...' : '创建计划' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useOperationsStore, type StrategyTemplate } from '@/stores/operations'

const store = useOperationsStore()
const router = useRouter()

const showCreateDialog = ref(false)
const step = ref(0)
const creating = ref(false)
const selectedName = ref('')
const selectedStrategyId = ref('')

const stepLabels = ['基本信息', '候选股筛选', '止损配置', '仓位控制', '市场适配']

const form = reactive({
  name: '',
  strategy_id: '',
  candidate_filter: {
    min_trend_score: 80,
    require_new_signal: true,
    require_strong_signal: true,
    exclude_fake_breakout: true,
    sector_overheat_days: 5,
    sector_overheat_pct: 15,
  },
  stage_stop_config: {
    fixed_stop_pct: 8,
    trailing_trigger_pct: 5,
    trailing_stop_pct: 5,
    tight_trigger_pct: 10,
    tight_stop_pct: 3,
    long_hold_days: 15,
    long_hold_trend_threshold: 60,
    trend_stop_ma: 20,
  },
  position_control: {
    max_stock_weight: 15,
    max_sector_weight: 30,
    max_positions: 10,
    max_total_weight: 80,
  },
  market_profile: {
    normal: { ma_trend: 75, money_flow: 75, rsi_low: 55, rsi_high: 80, turnover_low: 3, turnover_high: 15, sector_rank: 25, max_total_weight: 80 },
    caution: { ma_trend: 85, money_flow: 80, rsi_low: 60, rsi_high: 75, turnover_low: 3, turnover_high: 12, sector_rank: 15, max_total_weight: 50 },
    danger: { suspend_new_positions: true, max_total_weight: 0 },
  },
})

const FACTOR_LABELS: Record<string, string> = {
  ma_trend: '均线趋势', breakout: '形态突破', sector_rank: '板块排名',
  sector_trend: '板块趋势', macd: 'MACD', turnover: '换手率',
  money_flow: '资金流', rsi: 'RSI', pe_ttm: 'PE-TTM', roe: 'ROE', market_cap: '市值',
}

const selectedStrategy = computed<StrategyTemplate | undefined>(() =>
  store.strategies.find(s => s.id === selectedStrategyId.value)
)

const strategyFactors = computed(() => {
  const cfg = selectedStrategy.value?.config as Record<string, unknown> | undefined
  const factors = cfg?.factors as Array<{ factor_name: string; operator: string; threshold?: number; params?: Record<string, unknown> }> | undefined
  if (!factors?.length) return []
  return factors.map(f => ({
    ...f,
    factor_label: FACTOR_LABELS[f.factor_name] || f.factor_name,
  }))
})

const canNext = computed(() => {
  if (step.value === 0) {
    const ok = !!selectedName.value && !!selectedStrategyId.value
    console.log('[canNext step0]', { name: selectedName.value, sid: selectedStrategyId.value, ok })
    return ok
  }
  return true
})

watch([selectedName, selectedStrategyId], () => {
  console.log('[watch] name:', selectedName.value, 'sid:', selectedStrategyId.value)
})

// 选择策略后自动填充计划名称（如果名称为空）
watch(selectedStrategyId, (newId) => {
  if (newId && !selectedName.value) {
    const strategy = store.strategies.find(s => s.id === newId)
    if (strategy) {
      selectedName.value = strategy.name + '交易计划'
    }
  }
})

function moduleLabel(m: string) {
  const map: Record<string, string> = { ma_trend: '均线趋势', breakout: '形态突破', indicator_params: '技术指标', volume_price: '量价资金', factor_editor: '因子编辑' }
  return map[m] || m
}

function levelLabel(l: string) {
  const map: Record<string, string> = { normal: 'NORMAL 正常', caution: 'CAUTION 警戒', danger: 'DANGER 危险' }
  return map[l] || l
}

function statusLabel(status: string) {
  const map: Record<string, string> = { ACTIVE: '运行中', PAUSED: '已暂停', ARCHIVED: '已归档' }
  return map[status] || status
}

async function openCreateDialog() {
  step.value = 0
  selectedName.value = ''
  selectedStrategyId.value = ''
  await store.fetchStrategies()
  showCreateDialog.value = true
}

function nextStep() {
  if (canNext.value) step.value++
}

function goToDetail(planId: string) {
  router.push(`/operations/${planId}`)
}

async function handleCreate() {
  creating.value = true
  try {
    await store.createPlan({
      name: selectedName.value,
      strategy_id: selectedStrategyId.value,
      candidate_filter: { ...form.candidate_filter },
      stage_stop_config: { ...form.stage_stop_config },
      position_control: { ...form.position_control },
      market_profile: {
        normal: { ...form.market_profile.normal },
        caution: { ...form.market_profile.caution },
        danger: { ...form.market_profile.danger },
      },
    })
    showCreateDialog.value = false
  } finally {
    creating.value = false
  }
}

async function handleDelete(planId: string, planName: string) {
  if (confirm(`确定删除交易计划「${planName}」？此操作不可恢复。`)) {
    await store.deletePlan(planId)
  }
}

async function handleRunScreening(planId: string, planName: string) {
  if (!confirm(`确定执行选股「${planName}」？`)) return
  try {
    const result = await store.runScreening(planId)
    alert(`选股完成：筛选 ${result.screened_count} 只，二次筛选 ${result.filtered_count} 只，保存 ${result.saved_count} 只候选股`)
    await store.fetchPlans()
  } catch (e: any) {
    alert(`选股失败：${e.response?.data?.detail || e.message}`)
  }
}
</script>

<style scoped>
.operations-view { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { margin: 0; font-size: 1.5rem; }
.plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.plan-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; cursor: pointer; transition: box-shadow 0.2s; }
.plan-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.plan-card.status-paused { opacity: 0.7; }
.plan-card.status-archived { opacity: 0.5; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.plan-name { font-weight: 600; font-size: 1.1rem; }
.status-badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.status-badge.active { background: #e8f5e9; color: #2e7d32; }
.status-badge.paused { background: #fff3e0; color: #e65100; }
.status-badge.archived { background: #f5f5f5; color: #757575; }
.stat-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
.stat-label { color: #666; font-size: 0.9rem; }
.stat-value { font-weight: 500; }
.warning-text { color: #d32f2f; }
.card-actions { margin-top: 12px; display: flex; gap: 8px; }
.btn-primary { background: #1976d2; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #f5f5f5; border: 1px solid #ddd; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-sm { font-size: 0.8rem; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; background: #fff; }
.btn-sm.btn-primary { background: #1976d2; color: #fff; border-color: #1976d2; }
.btn-danger { color: #d32f2f; border-color: #d32f2f; }
.empty-state, .loading-state { text-align: center; padding: 48px; color: #666; }
.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: #fff; border-radius: 8px; padding: 24px; min-width: 400px; }
.dialog-wide { min-width: 560px; max-width: 680px; max-height: 85vh; overflow-y: auto; }
.dialog h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 0.9rem; color: #333; }
.form-group input[type="number"],
.form-group input[type="text"],
.form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
.form-group input[type="checkbox"] { width: auto; margin-right: 6px; }
.required { color: #d32f2f; }
.hint { font-size: 0.78rem; color: #888; margin-top: 2px; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

/* Steps */
.steps { display: flex; gap: 8px; margin-bottom: 20px; }
.step { display: flex; align-items: center; gap: 4px; font-size: 0.8rem; color: #aaa; }
.step.active { color: #1976d2; font-weight: 600; }
.step.done { color: #2e7d32; }
.step-num { width: 22px; height: 22px; border-radius: 50%; border: 2px solid currentColor; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; }
.step.active .step-num { background: #1976d2; color: #fff; border-color: #1976d2; }
.step.done .step-num { background: #2e7d32; color: #fff; border-color: #2e7d32; }

/* Step content */
.step-content { min-height: 200px; }

/* Config grid */
.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 600px) { .config-grid { grid-template-columns: 1fr; } }

/* Toggle grid */
.toggle-grid { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
.toggle-item { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; cursor: pointer; }

/* Strategy preview */
.strategy-preview { margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 6px; }
.strategy-preview h4 { margin: 0 0 8px; font-size: 0.9rem; color: #555; }
.factor-list { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.factor-tag { background: #e3f2fd; color: #1565c0; padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; }
.module-list { display: flex; flex-wrap: wrap; gap: 6px; }
.module-tag { background: #f3e5f5; color: #7b1fa2; padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; }

/* Profile sections */
.profile-section { margin-bottom: 16px; }
.profile-section h4 { margin: 0 0 8px; font-size: 0.95rem; display: flex; align-items: center; gap: 6px; }
.level-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.level-dot.normal { background: #2e7d32; }
.level-dot.caution { background: #e65100; }
.level-dot.danger { background: #c62828; }
</style>
