<template>
  <div class="admin-view">
    <h1 class="page-title">系统管理</h1>

    <!-- 管理标签页 -->
    <div class="tabs" role="tablist">
      <button v-for="t in tabs" :key="t.key" :class="['tab', activeTab === t.key && 'active']"
        role="tab" :aria-selected="activeTab === t.key" @click="activeTab = t.key">
        {{ t.label }}
      </button>
    </div>

    <!-- 用户管理 -->
    <section v-if="activeTab === 'users'" class="card" aria-label="用户管理">
      <div class="section-header">
        <h2 class="section-title">用户管理</h2>
        <button class="btn" @click="showAddUser = true">新增用户</button>
      </div>
      <table class="data-table" aria-label="用户列表">
        <thead>
          <tr>
            <th scope="col">用户名</th>
            <th scope="col">角色</th>
            <th scope="col">状态</th>
            <th scope="col">创建时间</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td><span class="role-badge" :class="`role-${u.role.toLowerCase()}`">{{ roleLabel(u.role) }}</span></td>
            <td><span :class="u.is_active ? 'status-active' : 'status-inactive'">{{ u.is_active ? '启用' : '禁用' }}</span></td>
            <td>{{ u.created_at?.slice(0, 10) ?? '—' }}</td>
            <td>
              <button class="btn-sm" @click="toggleUserActive(u)">{{ u.is_active ? '禁用' : '启用' }}</button>
              <button class="btn-sm danger" @click="deleteUser(u.id)">删除</button>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="5" class="empty">暂无用户</td>
          </tr>
        </tbody>
      </table>

      <!-- 新增用户对话框 -->
      <div v-if="showAddUser" class="dialog-overlay" @click.self="showAddUser = false">
        <div class="dialog" role="dialog" aria-label="新增用户">
          <h3>新增用户</h3>
          <div class="form-group">
            <label for="new-username">用户名</label>
            <input id="new-username" v-model="newUser.username" class="input full" />
          </div>
          <div class="form-group">
            <label for="new-password">密码</label>
            <input id="new-password" v-model="newUser.password" type="password" class="input full" />
          </div>
          <div class="form-group">
            <label for="new-role">角色</label>
            <select id="new-role" v-model="newUser.role" class="input full">
              <option value="TRADER">量化交易员</option>
              <option value="ADMIN">系统管理员</option>
              <option value="READONLY">只读观察员</option>
            </select>
          </div>
          <div class="dialog-actions">
            <button class="btn" @click="createUser">创建</button>
            <button class="btn btn-outline" @click="showAddUser = false">取消</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 系统监控 -->
    <section v-if="activeTab === 'monitor'" class="card" aria-label="系统监控">
      <h2 class="section-title">系统监控状态</h2>
      <div class="monitor-grid">
        <div v-for="s in systemHealth" :key="s.name" class="monitor-card">
          <div class="monitor-header">
            <span class="monitor-name">{{ s.name }}</span>
            <span class="monitor-status" :class="s.status === 'healthy' ? 'healthy' : 'unhealthy'">
              {{ s.status === 'healthy' ? '● 正常' : '● 异常' }}
            </span>
          </div>
          <div class="monitor-details">
            <span v-if="s.latency_ms != null">延迟: {{ s.latency_ms }}ms</span>
            <span v-if="s.message">{{ s.message }}</span>
          </div>
        </div>
      </div>
      <button class="btn btn-outline" @click="fetchHealth" style="margin-top: 12px;">刷新状态</button>
    </section>

    <!-- 日志查询 -->
    <section v-if="activeTab === 'logs'" class="card" aria-label="日志查询">
      <h2 class="section-title">操作日志</h2>
      <div class="filter-row">
        <label for="log-start" class="sr-only">开始日期</label>
        <input id="log-start" v-model="logStart" type="date" class="input" />
        <label for="log-end" class="sr-only">结束日期</label>
        <input id="log-end" v-model="logEnd" type="date" class="input" />
        <label for="log-action" class="sr-only">操作类型</label>
        <input id="log-action" v-model="logAction" class="input" placeholder="操作类型筛选" />
        <button class="btn btn-outline" @click="fetchLogs">查询</button>
      </div>
      <table class="data-table" aria-label="操作日志列表">
        <thead>
          <tr>
            <th scope="col">时间</th>
            <th scope="col">操作人</th>
            <th scope="col">操作类型</th>
            <th scope="col">操作对象</th>
            <th scope="col">详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td>{{ log.created_at?.slice(0, 19) ?? '—' }}</td>
            <td>{{ log.username ?? log.user_id }}</td>
            <td>{{ log.action }}</td>
            <td>{{ log.target }}</td>
            <td class="detail-cell">{{ log.detail ? JSON.stringify(log.detail) : '—' }}</td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="5" class="empty">暂无日志</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { apiClient } from '@/api'

const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'monitor', label: '系统监控' },
  { key: 'logs', label: '操作日志' },
]
const activeTab = ref('users')

// ── 用户管理 ──
interface User { id: string; username: string; role: string; is_active: boolean; created_at: string }
const users = ref<User[]>([])
const showAddUser = ref(false)
const newUser = reactive({ username: '', password: '', role: 'TRADER' })

async function fetchUsers() {
  try {
    const res = await apiClient.get<User[]>('/admin/users')
    users.value = res.data
  } catch { /* handle error */ }
}

async function createUser() {
  try {
    await apiClient.post('/admin/users', newUser)
    showAddUser.value = false
    newUser.username = ''
    newUser.password = ''
    newUser.role = 'TRADER'
    await fetchUsers()
  } catch { /* handle error */ }
}

async function deleteUser(id: string) {
  try {
    await apiClient.delete(`/admin/users/${id}`)
    await fetchUsers()
  } catch { /* handle error */ }
}

async function toggleUserActive(u: User) {
  try {
    await apiClient.patch(`/admin/users/${u.id}`, { is_active: !u.is_active })
    await fetchUsers()
  } catch { /* handle error */ }
}

function roleLabel(role: string) {
  const m: Record<string, string> = { TRADER: '交易员', ADMIN: '管理员', READONLY: '观察员' }
  return m[role] ?? role
}

// ── 系统监控 ──
interface HealthItem { name: string; status: string; latency_ms?: number; message?: string }
const systemHealth = ref<HealthItem[]>([])

async function fetchHealth() {
  try {
    const res = await apiClient.get<{ services: HealthItem[] }>('/admin/system-health')
    systemHealth.value = res.data.services
  } catch { /* handle error */ }
}

// ── 日志查询 ──
interface LogEntry { id: number; user_id: string; username?: string; action: string; target: string; detail: unknown; created_at: string }
const logs = ref<LogEntry[]>([])
const logStart = ref(new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10))
const logEnd = ref(new Date().toISOString().slice(0, 10))
const logAction = ref('')

async function fetchLogs() {
  try {
    const res = await apiClient.get<LogEntry[]>('/admin/logs', {
      params: { start: logStart.value, end: logEnd.value, action: logAction.value || undefined },
    })
    logs.value = res.data
  } catch { /* handle error */ }
}

onMounted(() => {
  fetchUsers()
  fetchHealth()
  fetchLogs()
})
</script>

<style scoped>
.admin-view { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.tabs { display: flex; gap: 4px; margin-bottom: 20px; }
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.filter-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }

.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.input.full { width: 100%; }
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover { background: #2ea043; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover { color: #e6edf3; border-color: #8b949e; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.empty { text-align: center; color: #484f58; padding: 24px; }
.detail-cell { font-size: 12px; color: #8b949e; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.btn-sm { background: none; border: 1px solid #30363d; color: #8b949e; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px; }
.btn-sm.danger:hover { color: #f85149; border-color: #f85149; }

.role-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.role-admin { background: #da363322; color: #f85149; }
.role-trader { background: #58a6ff22; color: #58a6ff; }
.role-readonly { background: #484f5822; color: #8b949e; }
.status-active { color: #3fb950; }
.status-inactive { color: #484f58; }

.monitor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.monitor-card { background: #0d1117; border-radius: 6px; padding: 14px; }
.monitor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.monitor-name { font-size: 14px; color: #e6edf3; }
.monitor-status { font-size: 13px; }
.healthy { color: #3fb950; }
.unhealthy { color: #f85149; }
.monitor-details { font-size: 12px; color: #8b949e; }
.monitor-details span { margin-right: 12px; }

.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex;
  align-items: center; justify-content: center; z-index: 100;
}
.dialog {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 24px; width: 400px; max-width: 90vw;
}
.dialog h3 { margin-bottom: 16px; color: #e6edf3; }
.form-group { margin-bottom: 12px; }
.form-group label { font-size: 13px; color: #8b949e; display: block; margin-bottom: 4px; }
.dialog-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }
</style>
