<template>
  <div class="operations-view">
    <div class="page-header">
      <h2>交易计划</h2>
      <button class="btn-primary" @click="showCreateDialog = true">新建交易计划</button>
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

    <!-- 新建对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog" role="dialog" aria-label="新建交易计划">
        <h3>新建交易计划</h3>
        <div class="form-group">
          <label for="plan-name">计划名称</label>
          <input id="plan-name" v-model="newPlanName" maxlength="100" placeholder="输入计划名称" />
        </div>
        <div class="form-group">
          <label for="strategy-id">策略模板 ID</label>
          <input id="strategy-id" v-model="newStrategyId" placeholder="输入策略模板 UUID" />
        </div>
        <div class="dialog-actions">
          <button class="btn-secondary" @click="showCreateDialog = false">取消</button>
          <button class="btn-primary" @click="handleCreate" :disabled="!newPlanName || !newStrategyId">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useOperationsStore } from '@/stores/operations'

const store = useOperationsStore()
const router = useRouter()

const showCreateDialog = ref(false)
const newPlanName = ref('')
const newStrategyId = ref('')

onMounted(() => { store.fetchPlans() })

function statusLabel(status: string) {
  const map: Record<string, string> = { ACTIVE: '运行中', PAUSED: '已暂停', ARCHIVED: '已归档' }
  return map[status] || status
}

function goToDetail(planId: string) {
  router.push(`/operations/${planId}`)
}

async function handleCreate() {
  if (!newPlanName.value || !newStrategyId.value) return
  await store.createPlan({ name: newPlanName.value, strategy_id: newStrategyId.value })
  showCreateDialog.value = false
  newPlanName.value = ''
  newStrategyId.value = ''
}

async function handleDelete(planId: string, planName: string) {
  if (confirm(`确定删除交易计划「${planName}」？此操作不可恢复。`)) {
    await store.deletePlan(planId)
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
.btn-secondary { background: #f5f5f5; border: 1px solid #ddd; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-sm { font-size: 0.8rem; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; background: #fff; }
.btn-danger { color: #d32f2f; border-color: #d32f2f; }
.empty-state, .loading-state { text-align: center; padding: 48px; color: #666; }
.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: #fff; border-radius: 8px; padding: 24px; min-width: 400px; }
.dialog h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 0.9rem; color: #333; }
.form-group input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
