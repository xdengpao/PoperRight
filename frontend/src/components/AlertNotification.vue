<template>
  <Teleport to="body">
    <div class="alert-notification-container" aria-live="polite" aria-label="预警通知">
      <TransitionGroup name="toast" tag="div" class="toast-list">
        <div
          v-for="toast in alertStore.toasts"
          :key="toast.id"
          class="toast-card"
          :class="`level-${toast.level.toLowerCase()}`"
          role="alert"
          @click="handleClick(toast)"
        >
          <div class="toast-icon">{{ typeIcon(toast.type) }}</div>
          <div class="toast-body">
            <div class="toast-header">
              <span class="toast-symbol">{{ toast.symbol }}</span>
              <span class="toast-level-badge">{{ levelLabel(toast.level) }}</span>
            </div>
            <div class="toast-message">{{ toast.message }}</div>
          </div>
          <button
            class="toast-close"
            aria-label="关闭通知"
            @click.stop="alertStore.removeToast(toast.id)"
          >×</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAlertStore, type AlertToast, type AlertType, type AlertLevel } from '@/stores/alert'

const alertStore = useAlertStore()
const router = useRouter()

// 自动 5 秒后移除 toast
const timers = new Map<string, ReturnType<typeof setTimeout>>()

function scheduleRemove(id: string) {
  if (timers.has(id)) return
  const t = setTimeout(() => {
    alertStore.removeToast(id)
    timers.delete(id)
  }, 5000)
  timers.set(id, t)
}

// 监听新增 toast，为每条启动计时器
watch(
  () => alertStore.toasts.length,
  () => {
    for (const toast of alertStore.toasts) {
      scheduleRemove(toast.id)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  for (const t of timers.values()) clearTimeout(t)
  timers.clear()
})

function handleClick(toast: AlertToast) {
  alertStore.removeToast(toast.id)
  if (toast.link_to) {
    router.push(toast.link_to)
  }
}

function typeIcon(type: AlertType): string {
  switch (type) {
    case 'SCREEN': return '🔍'
    case 'RISK':   return '🛡️'
    case 'TRADE':  return '💹'
    case 'SYSTEM': return '⚙️'
    default:       return '🔔'
  }
}

function levelLabel(level: AlertLevel): string {
  switch (level) {
    case 'DANGER':  return '危险'
    case 'WARNING': return '警告'
    default:        return '信息'
  }
}
</script>

<style scoped>
.alert-notification-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  pointer-events: none;
}

.toast-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-end;
}

.toast-card {
  pointer-events: all;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 320px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #1c2128;
  border: 1px solid #30363d;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.toast-card:hover {
  transform: translateX(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
}

/* Level color accents */
.toast-card.level-info    { border-left: 4px solid #58a6ff; }
.toast-card.level-warning { border-left: 4px solid #d29922; }
.toast-card.level-danger  { border-left: 4px solid #f85149; }

.toast-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 1px;
}

.toast-body {
  flex: 1;
  min-width: 0;
}

.toast-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.toast-symbol {
  font-size: 14px;
  font-weight: 700;
  color: #e6edf3;
}

.toast-level-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #21262d;
  color: #8b949e;
}

.level-info    .toast-level-badge { color: #58a6ff; }
.level-warning .toast-level-badge { color: #d29922; }
.level-danger  .toast-level-badge { color: #f85149; }

.toast-message {
  font-size: 13px;
  color: #8b949e;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toast-close {
  background: none;
  border: none;
  color: #484f58;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
  flex-shrink: 0;
  transition: color 0.15s;
}

.toast-close:hover {
  color: #e6edf3;
}

/* TransitionGroup animations */
.toast-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.toast-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>
