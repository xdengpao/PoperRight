<template>
  <!-- 因子使用说明面板 -->
  <div v-if="factorName" class="factor-usage-panel" role="region" aria-label="因子使用说明">
    <!-- 加载状态 -->
    <div v-if="loading" class="usage-loading">
      <span class="usage-spinner" aria-hidden="true"></span>
      <span>加载因子说明中...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="usage-error" role="alert">
      <span class="usage-error-icon">⚠️</span>
      <span>{{ error }}</span>
    </div>

    <!-- 内容展示 -->
    <div v-else-if="usageData" class="usage-content">
      <!-- 因子名称与标签 -->
      <div class="usage-header">
        <span class="usage-label">{{ usageData.label }}</span>
        <span v-if="usageData.threshold_type" class="usage-type-badge">{{ thresholdTypeText }}</span>
      </div>

      <!-- 描述文本 -->
      <p v-if="usageData.description" class="usage-description">{{ usageData.description }}</p>

      <!-- 推荐阈值范围 -->
      <div v-if="hasThresholdInfo" class="usage-threshold">
        <span class="usage-section-label">推荐阈值：</span>
        <span v-if="usageData.default_range" class="usage-threshold-value">
          {{ usageData.default_range[0] }} – {{ usageData.default_range[1] }}
          <span v-if="usageData.unit" class="usage-unit">{{ usageData.unit }}</span>
        </span>
        <span v-else-if="usageData.default_threshold != null" class="usage-threshold-value">
          {{ usageData.default_threshold }}
          <span v-if="usageData.unit" class="usage-unit">{{ usageData.unit }}</span>
        </span>
      </div>

      <!-- 配置示例列表 -->
      <div v-if="usageData.examples && usageData.examples.length > 0" class="usage-examples">
        <span class="usage-section-label">配置示例：</span>
        <ul class="usage-example-list">
          <li v-for="(ex, idx) in usageData.examples" :key="idx" class="usage-example-item">
            <code v-if="ex.operator && ex.threshold != null">{{ ex.operator }} {{ ex.threshold }}</code>
            <span v-if="ex['说明'] || ex.description" class="usage-example-desc">
              {{ ex['说明'] || ex.description }}
            </span>
          </li>
        </ul>
      </div>
    </div>

    <!-- 空状态（无数据） -->
    <div v-else class="usage-empty">
      <span>暂无该因子的使用说明</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { apiClient } from '@/api'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

/** 因子使用说明 API 响应数据 */
export interface FactorUsageData {
  factor_name: string
  label: string
  description: string
  examples: Array<Record<string, unknown>>
  default_threshold: number | null
  default_range: [number, number] | null
  unit: string
  threshold_type: string
}

// ─── Props ────────────────────────────────────────────────────────────────────

const props = defineProps<{
  /** 当前选中的因子名称，为空时不展示面板 */
  factorName: string
}>()

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const loading = ref(false)
const error = ref<string | null>(null)
const usageData = ref<FactorUsageData | null>(null)

// ─── 阈值类型文本映射 ─────────────────────────────────────────────────────────

const THRESHOLD_TYPE_LABELS: Record<string, string> = {
  absolute: '绝对值',
  percentile: '百分位',
  industry_relative: '行业相对',
  boolean: '布尔',
  range: '区间',
  z_score: 'Z分数',
}

/** 阈值类型显示文本 */
const thresholdTypeText = ref('')

/** 是否有推荐阈值信息 */
const hasThresholdInfo = ref(false)

// ─── 获取因子使用说明 ─────────────────────────────────────────────────────────

async function fetchFactorUsage(factorName: string) {
  if (!factorName) {
    usageData.value = null
    return
  }

  loading.value = true
  error.value = null

  try {
    const res = await apiClient.get<FactorUsageData>(
      `/screen/factors/${encodeURIComponent(factorName)}/usage`
    )
    usageData.value = res.data
    thresholdTypeText.value = THRESHOLD_TYPE_LABELS[res.data.threshold_type] ?? res.data.threshold_type
    hasThresholdInfo.value = res.data.default_range != null || res.data.default_threshold != null
  } catch (e) {
    usageData.value = null
    error.value = e instanceof Error ? e.message : '获取因子说明失败'
  } finally {
    loading.value = false
  }
}

// ─── 监听因子名称变化，自动更新面板 ───────────────────────────────────────────

watch(
  () => props.factorName,
  (newName) => {
    fetchFactorUsage(newName)
  },
  { immediate: true }
)
</script>

<style scoped>
/* ─── 面板容器 ──────────────────────────────────────────────────────────────── */
.factor-usage-panel {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 12px 14px;
  margin-top: 8px;
  font-size: 13px;
  color: #e6edf3;
}

/* ─── 加载状态 ──────────────────────────────────────────────────────────────── */
.usage-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8b949e;
}

.usage-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(139, 148, 158, 0.3);
  border-top-color: #8b949e;
  border-radius: 50%;
  animation: usage-spin 0.7s linear infinite;
}

@keyframes usage-spin {
  to { transform: rotate(360deg); }
}

/* ─── 错误状态 ──────────────────────────────────────────────────────────────── */
.usage-error {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #f85149;
}

.usage-error-icon {
  flex-shrink: 0;
}

/* ─── 内容区域 ──────────────────────────────────────────────────────────────── */
.usage-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.usage-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.usage-label {
  font-weight: 600;
  color: #e6edf3;
}

.usage-type-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #1f3a5f;
  color: #58a6ff;
}

.usage-description {
  margin: 0;
  color: #8b949e;
  line-height: 1.5;
}

/* ─── 推荐阈值 ──────────────────────────────────────────────────────────────── */
.usage-threshold {
  display: flex;
  align-items: center;
  gap: 6px;
}

.usage-section-label {
  color: #8b949e;
  flex-shrink: 0;
}

.usage-threshold-value {
  color: #58a6ff;
  font-weight: 500;
}

.usage-unit {
  color: #8b949e;
  font-weight: 400;
}

/* ─── 配置示例 ──────────────────────────────────────────────────────────────── */
.usage-examples {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.usage-example-list {
  margin: 4px 0 0;
  padding-left: 18px;
  list-style: disc;
}

.usage-example-item {
  color: #8b949e;
  line-height: 1.6;
}

.usage-example-item code {
  background: #161b22;
  padding: 1px 6px;
  border-radius: 3px;
  color: #e6edf3;
  font-size: 12px;
}

.usage-example-desc {
  margin-left: 6px;
}

/* ─── 空状态 ────────────────────────────────────────────────────────────────── */
.usage-empty {
  color: #484f58;
  text-align: center;
  padding: 8px 0;
}
</style>
