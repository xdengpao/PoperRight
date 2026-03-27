<template>
  <div class="screener">
    <h1 class="page-title">智能选股</h1>

    <!-- 错误提示 -->
    <ErrorBanner v-if="pageError" :message="pageError" :retryFn="() => loadStrategies()" />

    <!-- 策略模板列表 -->
    <section class="card" aria-label="策略模板">
      <div class="section-header">
        <h2 class="section-title">策略模板</h2>
        <div class="header-actions">
          <!-- 导入按钮 -->
          <label class="btn btn-outline" role="button" tabindex="0" aria-label="导入策略模板">
            <input
              ref="importInputRef"
              type="file"
              accept=".json"
              class="hidden-input"
              @change="onImportFile"
            />
            📥 导入
          </label>
          <button class="btn btn-outline" @click="showCreateDialog = true">＋ 新建策略</button>
        </div>
      </div>

      <LoadingSpinner v-if="strategiesLoading" text="加载策略中..." />

      <div v-else-if="strategies.length === 0" class="empty">暂无策略模板，点击「新建策略」创建</div>

      <div v-else class="strategy-list">
        <div
          v-for="s in strategies"
          :key="s.id"
          class="strategy-item"
          :class="{ active: activeStrategyId === s.id }"
          @click="selectStrategy(s.id)"
        >
          <div class="strategy-info">
            <span class="strategy-name">{{ s.name }}</span>
            <span v-if="s.is_active" class="active-badge">当前</span>
          </div>
          <div class="strategy-meta">
            <span class="strategy-date">{{ s.created_at?.slice(0, 10) ?? '—' }}</span>
          </div>
          <div class="strategy-actions" @click.stop>
            <button class="btn-icon" title="导出策略" @click="exportStrategy(s)">📤</button>
            <button class="btn-icon danger" title="删除策略" @click="confirmDelete(s)">🗑</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 因子条件可视化编辑器 -->
    <section class="card" aria-label="因子条件编辑器">
      <div class="section-header">
        <h2 class="section-title">因子条件编辑器</h2>
        <!-- AND/OR 逻辑切换 -->
        <div class="logic-toggle" role="group" aria-label="逻辑运算">
          <button
            :class="['logic-btn', config.logic === 'AND' && 'active']"
            @click="config.logic = 'AND'"
          >AND（全部满足）</button>
          <button
            :class="['logic-btn', config.logic === 'OR' && 'active']"
            @click="config.logic = 'OR'"
          >OR（满足其一）</button>
        </div>
      </div>

      <!-- 因子条件列表 -->
      <div class="factor-list">
        <div
          v-for="(factor, idx) in config.factors"
          :key="idx"
          class="factor-row"
        >
          <div class="factor-type-badge" :class="factor.type">
            {{ factorTypeLabel(factor.type) }}
          </div>

          <select v-model="factor.type" class="input factor-type-select" :aria-label="`因子类型 ${idx + 1}`">
            <option v-for="ft in factorTypes" :key="ft.key" :value="ft.key">{{ ft.label }}</option>
          </select>

          <input
            v-model="factor.factor_name"
            class="input factor-name"
            placeholder="因子名称（如 ma_trend）"
            :aria-label="`因子名称 ${idx + 1}`"
          />

          <select v-model="factor.operator" class="input factor-op" :aria-label="`运算符 ${idx + 1}`">
            <option value=">">&gt;</option>
            <option value=">=">&gt;=</option>
            <option value="<">&lt;</option>
            <option value="<=">&lt;=</option>
            <option value="==">==</option>
          </select>

          <input
            v-model.number="factor.threshold"
            type="number"
            class="input factor-threshold"
            placeholder="阈值"
            :aria-label="`阈值 ${idx + 1}`"
          />

          <!-- 权重滑块 -->
          <div class="weight-control">
            <label :for="`weight-${idx}`" class="weight-label">权重</label>
            <input
              :id="`weight-${idx}`"
              v-model.number="factor.weight"
              type="range"
              min="0"
              max="100"
              step="1"
              class="weight-slider"
            />
            <span class="weight-value">{{ factor.weight }}</span>
          </div>

          <button class="btn-icon danger" @click="removeFactor(idx)" :aria-label="`删除因子 ${idx + 1}`">✕</button>
        </div>

        <div v-if="config.factors.length === 0" class="empty-factors">
          暂无因子条件，点击下方按钮添加
        </div>
      </div>

      <!-- 添加因子按钮组 -->
      <div class="add-factor-row">
        <span class="add-label">添加因子：</span>
        <button
          v-for="ft in factorTypes"
          :key="ft.key"
          class="btn btn-outline btn-sm"
          @click="addFactor(ft.key)"
        >＋ {{ ft.label }}</button>
      </div>

      <!-- 其他参数 -->
      <div class="extra-config">
        <div class="config-item">
          <label for="ma-periods">均线周期</label>
          <input id="ma-periods" v-model="config.maPeriods" class="input" placeholder="5,10,20,60,120" />
        </div>
        <div class="config-item">
          <label for="trend-threshold">趋势打分阈值</label>
          <input id="trend-threshold" v-model.number="config.trendThreshold" type="number" min="0" max="100" class="input" />
        </div>
      </div>
    </section>

    <!-- 执行选股 -->
    <section class="card run-section" aria-label="执行选股">
      <div class="run-row">
        <div class="run-info">
          <span v-if="activeStrategyId" class="run-hint">
            当前策略：<strong>{{ activeStrategyName }}</strong>
          </span>
          <span v-else class="run-hint muted">未选择策略，将使用当前因子配置执行</span>
        </div>
        <button
          class="btn btn-run"
          @click="runScreen"
          :disabled="running"
          aria-label="执行选股"
        >
          <span v-if="running" class="spinner" aria-hidden="true"></span>
          {{ running ? '选股中...' : '🚀 一键执行选股' }}
        </button>
      </div>
      <p v-if="runError" class="run-error">{{ runError }}</p>
    </section>

    <!-- 新建策略对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="新建策略">
        <h3 class="dialog-title">新建策略模板</h3>
        <label for="new-strategy-name" class="dialog-label">策略名称</label>
        <input
          id="new-strategy-name"
          v-model="newStrategyName"
          class="input full"
          placeholder="输入策略名称"
          @keyup.enter="createStrategy"
        />
        <div class="dialog-actions">
          <button class="btn" @click="createStrategy" :disabled="!newStrategyName.trim()">保存</button>
          <button class="btn btn-outline" @click="showCreateDialog = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 删除确认对话框 -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="确认删除">
        <h3 class="dialog-title">确认删除</h3>
        <p class="dialog-body">
          确定要删除策略 <strong>「{{ deleteTarget.name }}」</strong> 吗？此操作不可撤销。
        </p>
        <div class="dialog-actions">
          <button class="btn btn-danger" @click="deleteStrategy" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
          <button class="btn btn-outline" @click="deleteTarget = null">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type FactorType = 'technical' | 'capital' | 'fundamental' | 'sector'

interface FactorCondition {
  type: FactorType
  factor_name: string
  operator: string
  threshold: number | null
  weight: number
}

interface StrategyTemplate {
  id: string
  name: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

// ─── 常量 ─────────────────────────────────────────────────────────────────────

const factorTypes: { key: FactorType; label: string }[] = [
  { key: 'technical', label: '技术面' },
  { key: 'capital', label: '资金面' },
  { key: 'fundamental', label: '基本面' },
  { key: 'sector', label: '板块面' },
]

function factorTypeLabel(type: string): string {
  return factorTypes.find((f) => f.key === type)?.label ?? type
}

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const router = useRouter()

const strategies = ref<StrategyTemplate[]>([])
const strategiesLoading = ref(false)
const pageError = ref<string | null>(null)

const activeStrategyId = ref('')
const activeStrategyName = computed(
  () => strategies.value.find((s) => s.id === activeStrategyId.value)?.name ?? ''
)

const running = ref(false)
const runError = ref('')

const showCreateDialog = ref(false)
const newStrategyName = ref('')

const deleteTarget = ref<StrategyTemplate | null>(null)
const deleting = ref(false)

const importInputRef = ref<HTMLInputElement | null>(null)

const config = reactive({
  logic: 'AND' as 'AND' | 'OR',
  maPeriods: '5,10,20,60,120',
  trendThreshold: 80,
  factors: [] as FactorCondition[],
})

// ─── 策略列表 ─────────────────────────────────────────────────────────────────

async function loadStrategies() {
  strategiesLoading.value = true
  pageError.value = null
  try {
    const res = await apiClient.get<{ items?: StrategyTemplate[] } | StrategyTemplate[]>('/strategies')
    const data = res.data
    strategies.value = Array.isArray(data) ? data : (data.items ?? [])
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '加载策略失败'
  } finally {
    strategiesLoading.value = false
  }
}

function selectStrategy(id: string) {
  activeStrategyId.value = activeStrategyId.value === id ? '' : id
}

// ─── 新建策略 ─────────────────────────────────────────────────────────────────

async function createStrategy() {
  const name = newStrategyName.value.trim()
  if (!name) return
  try {
    await apiClient.post('/strategies', {
      name,
      config: buildStrategyConfig(),
      is_active: false,
    })
    showCreateDialog.value = false
    newStrategyName.value = ''
    await loadStrategies()
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '创建策略失败'
  }
}

// ─── 删除策略 ─────────────────────────────────────────────────────────────────

function confirmDelete(strategy: StrategyTemplate) {
  deleteTarget.value = strategy
}

async function deleteStrategy() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await apiClient.delete(`/strategies/${deleteTarget.value.id}`)
    if (activeStrategyId.value === deleteTarget.value.id) {
      activeStrategyId.value = ''
    }
    deleteTarget.value = null
    await loadStrategies()
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '删除策略失败'
  } finally {
    deleting.value = false
  }
}

// ─── 导出策略 ─────────────────────────────────────────────────────────────────

async function exportStrategy(strategy: StrategyTemplate) {
  try {
    const res = await apiClient.get<StrategyTemplate>(`/strategies/${strategy.id}`)
    const json = JSON.stringify(res.data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `strategy_${strategy.name}_${strategy.id.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '导出策略失败'
  }
}

// ─── 导入策略 ─────────────────────────────────────────────────────────────────

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    const parsed = JSON.parse(text) as Partial<StrategyTemplate>

    if (!parsed.name || !parsed.config) {
      throw new Error('JSON 文件格式无效，缺少 name 或 config 字段')
    }

    await apiClient.post('/strategies', {
      name: parsed.name,
      config: parsed.config,
      is_active: false,
    })

    await loadStrategies()
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '导入策略失败'
  } finally {
    // 重置 input 以允许重复导入同一文件
    if (importInputRef.value) importInputRef.value.value = ''
  }
}

// ─── 因子编辑器 ───────────────────────────────────────────────────────────────

function addFactor(type: FactorType) {
  config.factors.push({
    type,
    factor_name: '',
    operator: '>',
    threshold: null,
    weight: 50,
  })
}

function removeFactor(idx: number) {
  config.factors.splice(idx, 1)
}

function buildStrategyConfig() {
  return {
    logic: config.logic,
    factors: config.factors.map(({ type: _type, weight: _weight, ...f }) => f),
    weights: Object.fromEntries(
      config.factors.map((f) => [f.factor_name || f.type, f.weight / 100])
    ),
    ma_periods: config.maPeriods.split(',').map(Number).filter(Boolean),
    indicator_params: { trend_threshold: config.trendThreshold },
  }
}

// ─── 执行选股 ─────────────────────────────────────────────────────────────────

async function runScreen() {
  running.value = true
  runError.value = ''
  try {
    await apiClient.post('/screen/run', {
      strategy_id: activeStrategyId.value || undefined,
      strategy_config: activeStrategyId.value ? undefined : buildStrategyConfig(),
      screen_type: 'EOD',
    })
    router.push('/screener/results')
  } catch (e) {
    runError.value = e instanceof Error ? e.message : '执行选股失败，请重试'
    running.value = false
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.screener { max-width: 1000px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; color: #e6edf3; margin: 0; }

/* ─── 卡片 ─────────────────────────────────────────────────────────────────── */
.card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 20px; margin-bottom: 20px;
}

/* ─── 区块头部 ──────────────────────────────────────────────────────────────── */
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px; flex-wrap: wrap; gap: 8px;
}
.header-actions { display: flex; gap: 8px; align-items: center; }

/* ─── 策略列表 ──────────────────────────────────────────────────────────────── */
.strategy-list { display: flex; flex-direction: column; gap: 8px; }

.strategy-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; border-radius: 6px;
  border: 1px solid #21262d; background: #0d1117;
  cursor: pointer; transition: border-color 0.15s, background 0.15s;
}
.strategy-item:hover { border-color: #58a6ff44; background: #161b22; }
.strategy-item.active { border-color: #58a6ff; background: #1f6feb11; }

.strategy-info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.strategy-name { font-size: 14px; color: #e6edf3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.active-badge {
  font-size: 11px; padding: 1px 6px; border-radius: 10px;
  background: #1f6feb33; color: #58a6ff; border: 1px solid #58a6ff44;
  flex-shrink: 0;
}
.strategy-meta { flex-shrink: 0; }
.strategy-date { font-size: 12px; color: #484f58; }
.strategy-actions { display: flex; gap: 4px; flex-shrink: 0; }

/* ─── 因子编辑器 ────────────────────────────────────────────────────────────── */
.logic-toggle { display: flex; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }
.logic-btn {
  background: transparent; border: none; color: #8b949e;
  padding: 6px 14px; cursor: pointer; font-size: 13px; transition: background 0.15s, color 0.15s;
}
.logic-btn.active { background: #1f6feb33; color: #58a6ff; }
.logic-btn:hover:not(.active) { background: #21262d; color: #e6edf3; }

.factor-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }

.factor-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px; background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
}

.factor-type-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600;
  flex-shrink: 0; white-space: nowrap;
}
.factor-type-badge.technical { background: #1f3a5f; color: #58a6ff; }
.factor-type-badge.capital { background: #3a2a1a; color: #d29922; }
.factor-type-badge.fundamental { background: #1a3a2a; color: #3fb950; }
.factor-type-badge.sector { background: #2a1a3a; color: #bc8cff; }

.factor-type-select { width: 90px; flex-shrink: 0; }
.factor-name { flex: 1; min-width: 120px; }
.factor-op { width: 70px; flex-shrink: 0; }
.factor-threshold { width: 90px; flex-shrink: 0; }

.weight-control { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.weight-label { font-size: 12px; color: #8b949e; white-space: nowrap; }
.weight-slider { width: 80px; accent-color: #58a6ff; cursor: pointer; }
.weight-value { font-size: 12px; color: #e6edf3; width: 24px; text-align: right; }

.empty-factors { color: #484f58; font-size: 14px; padding: 16px 0; text-align: center; }

.add-factor-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.add-label { font-size: 13px; color: #8b949e; }

.extra-config {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px; padding-top: 12px; border-top: 1px solid #21262d;
}
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }

/* ─── 执行选股 ──────────────────────────────────────────────────────────────── */
.run-section { }
.run-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.run-info { flex: 1; }
.run-hint { font-size: 14px; color: #e6edf3; }
.run-hint.muted { color: #8b949e; }
.run-hint strong { color: #58a6ff; }
.run-error { margin-top: 10px; font-size: 13px; color: #f85149; }

/* ─── 通用输入 ──────────────────────────────────────────────────────────────── */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 6px 12px; border-radius: 6px; font-size: 14px;
}
.input:focus { outline: none; border-color: #58a6ff; }
.input.full { width: 100%; box-sizing: border-box; }
.hidden-input { display: none; }

/* ─── 按钮 ─────────────────────────────────────────────────────────────────── */
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
.btn-sm { padding: 4px 10px; font-size: 13px; }
.btn-run { background: #1f6feb; font-size: 15px; padding: 10px 24px; }
.btn-run:hover:not(:disabled) { background: #388bfd; }
.btn-danger { background: #da3633; }
.btn-danger:hover:not(:disabled) { background: #f85149; }

.btn-icon {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  width: 30px; height: 30px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 14px;
  padding: 0;
}
.btn-icon:hover { color: #e6edf3; border-color: #8b949e; }
.btn-icon.danger:hover { color: #f85149; border-color: #f85149; }

/* ─── 旋转加载 ──────────────────────────────────────────────────────────────── */
.spinner {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 对话框 ────────────────────────────────────────────────────────────────── */
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center; z-index: 200;
}
.dialog {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 24px; width: 420px; max-width: 90vw;
}
.dialog-title { font-size: 16px; color: #e6edf3; margin: 0 0 16px; }
.dialog-label { font-size: 13px; color: #8b949e; display: block; margin-bottom: 6px; }
.dialog-body { font-size: 14px; color: #8b949e; margin: 0 0 20px; line-height: 1.6; }
.dialog-body strong { color: #e6edf3; }
.dialog-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }

/* ─── 空状态 ────────────────────────────────────────────────────────────────── */
.empty { color: #484f58; font-size: 14px; padding: 24px 0; text-align: center; }
</style>
