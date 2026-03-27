<template>
  <div class="main-layout">
    <nav class="sidebar" aria-label="主导航">
      <div class="sidebar-header">
        <h2>A股量化系统</h2>
      </div>
      <ul class="nav-list">
        <li v-for="item in navItems" :key="item.path">
          <router-link
            :to="item.path"
            class="nav-link"
            :class="{ active: route.path === item.path }"
            v-if="!item.roles || item.roles.includes(authStore.role)"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
      <div class="sidebar-footer">
        <span class="user-info">{{ authStore.user?.username ?? '—' }}</span>
        <button class="logout-btn" @click="handleLogout" aria-label="退出登录">退出</button>
      </div>
    </nav>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const navItems = [
  { path: '/dashboard', label: '大盘概况', icon: '📊' },
  { path: '/screener', label: '智能选股', icon: '🔍' },
  { path: '/screener/results', label: '选股结果', icon: '📋' },
  { path: '/risk', label: '风险控制', icon: '🛡️' },
  { path: '/backtest', label: '策略回测', icon: '📈' },
  { path: '/trade', label: '交易执行', icon: '💹', roles: ['TRADER', 'ADMIN'] },
  { path: '/positions', label: '持仓管理', icon: '💰', roles: ['TRADER', 'ADMIN'] },
  { path: '/review', label: '复盘分析', icon: '📝' },
  { path: '/admin', label: '系统管理', icon: '⚙️', roles: ['ADMIN'] },
] as const

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
}
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
.nav-list {
  list-style: none;
  padding: 8px 0;
  flex: 1;
  overflow-y: auto;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
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
.nav-icon { font-size: 16px; }
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #30363d;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.user-info {
  font-size: 13px;
  color: #8b949e;
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
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
</style>
