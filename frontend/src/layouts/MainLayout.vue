<template>
  <div class="main-layout">
    <!-- Sidebar -->
    <nav class="sidebar" aria-label="主导航">
      <div class="sidebar-header">
        <h2>A股量化系统</h2>
      </div>
      <div class="nav-groups">
        <div
          v-for="(items, groupName) in filteredMenuGroups"
          :key="groupName"
          class="nav-group"
        >
          <div class="nav-group-label">{{ groupName }}</div>
          <ul class="nav-list">
            <li v-for="item in items" :key="item.path">
              <router-link
                :to="item.path"
                class="nav-link"
                :class="{ active: isActiveRoute(item.path) }"
              >
                <span class="nav-icon">{{ item.icon }}</span>
                <span class="nav-label">{{ item.label }}</span>
              </router-link>
            </li>
          </ul>
        </div>
      </div>
    </nav>

    <!-- Main area -->
    <div class="main-area">
      <!-- Top navbar -->
      <header class="top-navbar">
        <div class="navbar-left">
          <span class="system-name">A股右侧量化选股系统</span>
        </div>
        <div class="navbar-right">
          <!-- Notification bell -->
          <div class="notification-wrapper" ref="notificationRef">
            <button
              class="notification-bell"
              @click="toggleNotificationPanel"
              aria-label="预警通知"
            >
              🔔
              <span
                v-if="alertStore.unreadCount > 0"
                class="badge"
              >{{ alertStore.unreadCount > 99 ? '99+' : alertStore.unreadCount }}</span>
            </button>
            <div v-if="showNotificationPanel" class="notification-panel">
              <div class="notification-panel-header">
                <span>预警通知</span>
                <button
                  v-if="alertStore.alerts.length > 0"
                  class="clear-btn"
                  @click="alertStore.clearAll()"
                >清空</button>
              </div>
              <div class="notification-panel-body">
                <div
                  v-if="alertStore.alerts.length === 0"
                  class="notification-empty"
                >暂无预警消息</div>
                <div
                  v-for="alert in recentAlerts"
                  :key="alert.id"
                  class="notification-item"
                  :class="[`level-${alert.level.toLowerCase()}`, { unread: !alert.read }]"
                  @click="handleAlertClick(alert)"
                >
                  <div class="notification-item-header">
                    <span class="notification-level">{{ levelLabel(alert.level) }}</span>
                    <span class="notification-symbol">{{ alert.symbol }}</span>
                    <span class="notification-time">{{ formatTime(alert.created_at) }}</span>
                  </div>
                  <div class="notification-message">{{ alert.message }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- User info -->
          <span class="user-info">{{ authStore.user?.username ?? '—' }}</span>
          <span class="user-role-badge">{{ roleLabel }}</span>
          <button class="logout-btn" @click="handleLogout" aria-label="退出登录">退出</button>
        </div>
      </header>

      <!-- Content -->
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>

  <!-- 全局预警弹出通知 -->
  <AlertNotification />

  <!-- 全局离线提示条 -->
  <Teleport to="body">
    <Transition name="offline-bar">
      <div v-if="isOffline" class="offline-bar" role="status" aria-live="assertive">
        <span>⚠️ 网络连接已断开，请检查网络设置</span>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

// --- Offline detection ---
const isOffline = ref(!navigator.onLine)

function handleOnline() { isOffline.value = false }
function handleOffline() { isOffline.value = true }
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, type UserRole } from '@/stores/auth'
import { useAlertStore, type AlertMessage } from '@/stores/alert'
import AlertNotification from '@/components/AlertNotification.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const alertStore = useAlertStore()

const showNotificationPanel = ref(false)
const notificationRef = ref<HTMLElement | null>(null)

// --- Menu definition ---

interface NavItem {
  path: string
  label: string
  icon: string
  roles?: UserRole[]
}

const menuGroups: Record<string, NavItem[]> = {
  '数据': [
    { path: '/dashboard', label: '大盘概况', icon: '📊' },
    { path: '/data', label: '数据管理', icon: '💾' },
  ],
  '选股': [
    { path: '/screener', label: '智能选股', icon: '🔍' },
    { path: '/screener/results', label: '选股结果', icon: '📋' },
  ],
  '风控': [
    { path: '/risk', label: '风险控制', icon: '🛡️' },
  ],
  '交易': [
    { path: '/trade', label: '交易执行', icon: '💹', roles: ['TRADER', 'ADMIN'] },
    { path: '/positions', label: '持仓管理', icon: '💰', roles: ['TRADER', 'ADMIN'] },
  ],
  '分析': [
    { path: '/backtest', label: '策略回测', icon: '📈' },
    { path: '/review', label: '复盘分析', icon: '📝' },
  ],
  '系统': [
    { path: '/admin', label: '系统管理', icon: '⚙️', roles: ['ADMIN'] },
  ],
}

const filteredMenuGroups = computed(() => {
  const result: Record<string, NavItem[]> = {}
  const userRole = authStore.role
  for (const [group, items] of Object.entries(menuGroups)) {
    const filtered = items.filter(
      (item) => !item.roles || item.roles.includes(userRole),
    )
    if (filtered.length > 0) {
      result[group] = filtered
    }
  }
  return result
})

function isActiveRoute(path: string): boolean {
  return route.path === path
}

// --- Notification ---

const recentAlerts = computed(() => alertStore.alerts.slice(0, 20))

function toggleNotificationPanel() {
  showNotificationPanel.value = !showNotificationPanel.value
}

function handleAlertClick(alert: AlertMessage) {
  alertStore.markRead(alert.id)
  showNotificationPanel.value = false
}

function levelLabel(level: string): string {
  switch (level) {
    case 'DANGER': return '🔴 危险'
    case 'WARNING': return '🟡 警告'
    default: return '🔵 信息'
  }
}

function formatTime(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ''
  }
}

// Close notification panel on outside click
function handleClickOutside(e: MouseEvent) {
  if (notificationRef.value && !notificationRef.value.contains(e.target as Node)) {
    showNotificationPanel.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
})

// --- User ---

const roleLabel = computed(() => {
  switch (authStore.role) {
    case 'ADMIN': return '管理员'
    case 'TRADER': return '交易员'
    default: return '观察员'
  }
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  background: #0d1117;
}

/* Sidebar */
.sidebar {
  width: 200px;
  background: #161b22;
  border-right: 1px solid #30363d;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #30363d;
}
.sidebar-header h2 {
  font-size: 15px;
  color: #58a6ff;
  margin: 0;
}
.nav-groups {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.nav-group {
  margin-bottom: 4px;
}
.nav-group-label {
  padding: 8px 16px 4px;
  font-size: 11px;
  color: #484f58;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}
.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  color: #8b949e;
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}
.nav-link:hover {
  background: #1f2937;
  color: #e6edf3;
}
.nav-link.active {
  background: #1f6feb22;
  color: #58a6ff;
  border-right: 3px solid #58a6ff;
}
.nav-icon {
  font-size: 16px;
}

/* Main area */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Top navbar */
.top-navbar {
  height: 48px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}
.navbar-left {
  display: flex;
  align-items: center;
}
.system-name {
  font-size: 14px;
  color: #e6edf3;
  font-weight: 500;
}
.navbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Notification bell */
.notification-wrapper {
  position: relative;
}
.notification-bell {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  position: relative;
  padding: 4px;
  line-height: 1;
}
.badge {
  position: absolute;
  top: -4px;
  right: -6px;
  background: #f85149;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}

/* Notification panel */
.notification-panel {
  position: absolute;
  top: 36px;
  right: 0;
  width: 340px;
  max-height: 400px;
  background: #1c2128;
  border: 1px solid #30363d;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 100;
  display: flex;
  flex-direction: column;
}
.notification-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #30363d;
  font-size: 14px;
  font-weight: 600;
  color: #e6edf3;
}
.clear-btn {
  background: none;
  border: none;
  color: #58a6ff;
  font-size: 12px;
  cursor: pointer;
}
.clear-btn:hover {
  text-decoration: underline;
}
.notification-panel-body {
  overflow-y: auto;
  flex: 1;
}
.notification-empty {
  padding: 24px;
  text-align: center;
  color: #484f58;
  font-size: 13px;
}
.notification-item {
  padding: 10px 16px;
  border-bottom: 1px solid #21262d;
  cursor: pointer;
  transition: background 0.15s;
}
.notification-item:hover {
  background: #21262d;
}
.notification-item.unread {
  border-left: 3px solid #58a6ff;
}
.notification-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.notification-level {
  font-size: 12px;
}
.notification-symbol {
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
}
.notification-time {
  margin-left: auto;
  font-size: 11px;
  color: #484f58;
}
.notification-message {
  font-size: 13px;
  color: #8b949e;
  line-height: 1.4;
}
.level-danger { }
.level-warning { }
.level-info { }

/* User info */
.user-info {
  font-size: 13px;
  color: #e6edf3;
}
.user-role-badge {
  font-size: 11px;
  color: #8b949e;
  background: #21262d;
  padding: 2px 8px;
  border-radius: 10px;
}
.logout-btn {
  background: none;
  border: 1px solid #30363d;
  color: #8b949e;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.logout-btn:hover {
  color: #f85149;
  border-color: #f85149;
}

/* Content */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-width: 1080px;
}

/* Offline bar */
.offline-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10000;
  background: #d29922;
  color: #0d1117;
  text-align: center;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
}

.offline-bar-enter-active,
.offline-bar-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.offline-bar-enter-from,
.offline-bar-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
