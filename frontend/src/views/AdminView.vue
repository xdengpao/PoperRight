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

    <!-- ── 用户管理 ── -->
    <section v-if="activeTab === 'users'" class="card" aria-label="用户管理">
      <div class="section-header">
        <h2 class="section-title">用户账号管理</h2>
        <button class="btn" @click="openAddUser">新增用户</button>
      </div>
      <div v-if="usersLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" aria-label="用户列表">
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
            <td>
              <select class="role-select" :value="u.role" @change="changeRole(u, ($event.target as HTMLSelectElement).value as UserRole)"
                :aria-label="`修改 ${u.username} 的角色`">
                <option value="TRADER">量化交易员</option>
                <option value="ADMIN">系统管理员</option>
                <option value="READONLY">只读观察员</option>
              </select>
            </td>
            <td><span :class="u.is_active ? 'status-active' : 'status-inactive'">{{ u.is_active ? '启用' : '禁用' }}</span></td>
            <td>{{ u.created_at?.slice(0, 10) ?? '—' }}</td>
            <td>
              <button class="btn-sm danger" @click="confirmDeleteUser(u)">删除</button>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="5" class="empty">暂无用户</td>
          </tr>
        </tbody>
      </table>
      <span v-if="userMsg" class="save-msg" :class="userMsgType">{{ userMsg }}</span>
    </section>

    <!-- ── 系统运行状态监控 ── -->
    <section v-if="activeTab === 'monitor'" class="card" aria-label="系统运行状态监控">
      <div class="section-header">
        <h2 class="section-title">系统运行状态</h2>
        <div class="header-right">
          <span class="auto-refresh-hint">每 30 秒自动刷新</span>
          <button class="btn-icon" @click="fetchHealth" :disabled="healthLoading" aria-label="立即刷新">
            <span :class="['refresh-icon', healthLoading && 'spinning']">↻</span>
          </button>
        </div>
      </div>

      <div v-if="healthLoading && !systemHealth" class="loading-text">加载中...</div>
      <template v-else-if="systemHealth">
        <!-- 模块状态 -->
        <h3 class="sub-title">模块状态</h3>
        <div class="monitor-grid">
          <div v-for="m in systemHealth.modules" :key="m.name" class="monitor-card">
            <div class="monitor-header">
              <span class="monitor-name">{{ m.name }}</span>
              <span class="monitor-status" :class="m.status === 'OK' ? 'healthy' : 'unhealthy'">
                {{ m.status === 'OK' ? '● 正常' : '● 异常' }}
              </span>
            </div>
            <div class="monitor-meta">上次检查：{{ m.last_check?.slice(0, 19) ?? '—' }}</div>
          </div>
        </div>

        <!-- 数据源连接 -->
        <h3 class="sub-title" style="margin-top: 16px;">数据源连接</h3>
        <div class="monitor-grid">
          <div v-for="ds in systemHealth.data_sources" :key="ds.name" class="monitor-card">
            <div class="monitor-header">
              <span class="monitor-name">{{ ds.name }}</span>
              <span class="monitor-status" :class="ds.connected ? 'healthy' : 'unhealthy'">
                {{ ds.connected ? '● 已连接' : '● 断开' }}
              </span>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="empty">暂无监控数据</div>

      <!-- 数据备份与恢复 -->
      <div class="backup-row">
        <h3 class="sub-title">数据备份与恢复</h3>
        <div class="backup-actions">
          <button class="btn" @click="confirmBackup" :disabled="backupLoading">
            {{ backupLoading ? '备份中...' : '触发备份' }}
          </button>
          <button class="btn btn-warning" @click="confirmRestore" :disabled="restoreLoading">
            {{ restoreLoading ? '恢复中...' : '触发恢复' }}
          </button>
        </div>
        <span v-if="backupMsg" class="save-msg" :class="backupMsgType">{{ backupMsg }}</span>
      </div>
    </section>

    <!-- ── 操作日志 ── -->
    <section v-if="activeTab === 'logs'" class="card" aria-label="操作日志查询">
      <h2 class="section-title">操作日志</h2>
      <div class="filter-row">
        <label for="log-start" class="sr-only">开始日期</label>
        <input id="log-start" v-model="logStart" type="date" class="input" />
        <label for="log-end" class="sr-only">结束日期</label>
        <input id="log-end" v-model="logEnd" type="date" class="input" />
        <label for="log-action-type" class="sr-only">操作类型</label>
        <select id="log-action-type" v-model="logActionType" class="input">
          <option value="">全部操作类型</option>
          <option value="LOGIN">登录</option>
          <option value="LOGOUT">登出</option>
          <option value="CREATE_USER">新增用户</option>
          <option value="DELETE_USER">删除用户</option>
          <option value="CHANGE_ROLE">修改角色</option>
          <option value="BACKUP">数据备份</option>
          <option value="RESTORE">数据恢复</option>
          <option value="TRADE">交易操作</option>
          <option value="CONFIG_CHANGE">配置变更</option>
        </select>
        <button class="btn btn-outline" @click="fetchLogs" :disabled="logsLoading">查询</button>
      </div>
      <div v-if="logsLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" aria-label="操作日志列表">
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
            <td><span class="action-badge">{{ log.action }}</span></td>
            <td>{{ log.target ?? '—' }}</td>
            <td class="detail-cell">{{ log.detail ? JSON.stringify(log.detail) : '—' }}</td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="5" class="empty">暂无日志</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ── 新增用户对话框 ── -->
    <div v-if="showAddUser" class="dialog-overlay" @click.self="showAddUser = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="新增用户">
        <h3>新增用户</h3>
        <div class="form-group">
          <label for="new-username">用户名</label>
          <input id="new-username" v-model="newUser.username" class="input full" autocomplete="off" />
        </div>
        <div class="form-group">
          <label for="new-password">密码</label>
          <input id="new-password" v-model="newUser.password" type="password" class="input full" autocomplete="new-password" />
        </div>
        <div class="form-group">
          <label for="new-role">角色</label>
          <select id="new-role" v-model="newUser.role" class="input full">
            <option value="TRADER">量化交易员</option>
            <option value="ADMIN">系统管理员</option>
            <option value="READONLY">只读观察员</option>
          </select>
        </div>
        <span v-if="addUserError" class="save-msg error">{{ addUserError }}</span>
        <div class="dialog-actions">
          <button class="btn" @click="createUser" :disabled="addUserLoading">
            {{ addUserLoading ? '创建中...' : '创建' }}
          </button>
          <button class="btn btn-outline" @click="showAddUser = false">取消</button>
        </div>
      </div>
    </div>

    <!-- ── 删除用户确认对话框 ── -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="确认删除用户">
        <h3>确认删除用户</h3>
        <p class="confirm-text">确定要删除用户 <strong>{{ deleteTarget.username }}</strong> 吗？此操作不可撤销。</p>
        <div class="dialog-actions">
          <button class="btn btn-danger" @click="doDeleteUser" :disabled="deleteLoading">
            {{ deleteLoading ? '删除中...' : '确认删除' }}
          </button>
          <button class="btn btn-outline" @click="deleteTarget = null">取消</button>
        </div>
      </div>
    </div>

    <!-- ── 备份确认对话框 ── -->
    <div v-if="showBackupConfirm" class="dialog-overlay" @click.self="showBackupConfirm = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="确认数据备份">
        <h3>确认数据备份</h3>
        <p class="confirm-text">将触发全量数据备份，备份期间系统性能可能受到影响，确认继续？</p>
        <div class="dialog-actions">
          <button class="btn" @click="doBackup" :disabled="backupLoading">
            {{ backupLoading ? '备份中...' : '确认备份' }}
          </button>
          <button class="btn btn-outline" @click="showBackupConfirm = false">取消</button>
        </div>
      </div>
    </div>

    <!-- ── 恢复确认对话框 ── -->
    <div v-if="showRestoreConfirm" class="dialog-overlay" @click.self="showRestoreConfirm = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="确认数据恢复">
        <h3 class="danger-title">⚠ 确认数据恢复</h3>
        <p class="confirm-text">数据恢复将覆盖当前数据，此操作不可撤销，请谨慎操作！确认继续？</p>
        <div class="dialog-actions">
          <button class="btn btn-danger" @click="doRestore" :disabled="restoreLoading">
            {{ restoreLoading ? '恢复中...' : '确认恢复' }}
          </button>
          <button class="btn btn-outline" @click="showRestoreConfirm = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { apiClient } from '@/api'

type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'

interface UserManageRow {
  id: string
  username: string
  role: UserRole
  is_active: boolean
  created_at: string
}

interface SystemHealth {
  modules: { name: string; status: 'OK' | 'ERROR'; last_check: string }[]
  data_sources: { name: string; connected: boolean }[]
}

interface LogEntry {
  id: number
  user_id: string
  username?: string
  action: string
  target?: string
  detail?: unknown
  created_at: string
}

// ── 标签页 ──
const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'monitor', label: '系统监控' },
  { key: 'logs', label: '操作日志' },
]
const activeTab = ref('users')

// ── 用户管理 ──
const users = ref<UserManageRow[]>([])
const usersLoading = ref(false)
const userMsg = ref('')
const userMsgType = ref<'success' | 'error'>('success')

const showAddUser = ref(false)
const newUser = reactive({ username: '', password: '', role: 'TRADER' as UserRole })
const addUserLoading = ref(false)
const addUserError = ref('')

const deleteTarget = ref<UserManageRow | null>(null)
const deleteLoading = ref(false)

async function fetchUsers() {
  usersLoading.value = true
  try {
    const res = await apiClient.get<UserManageRow[]>('/admin/users')
    users.value = res.data
  } catch {
    /* handle error */
  } finally {
    usersLoading.value = false
  }
}

function openAddUser() {
  newUser.username = ''
  newUser.password = ''
  newUser.role = 'TRADER'
  addUserError.value = ''
  showAddUser.value = true
}

async function createUser() {
  if (!newUser.username.trim() || !newUser.password.trim()) {
    addUserError.value = '用户名和密码不能为空'
    return
  }
  addUserLoading.value = true
  addUserError.value = ''
  try {
    await apiClient.post('/admin/users', { ...newUser })
    showAddUser.value = false
    showMsg('用户创建成功', 'success')
    await fetchUsers()
  } catch (e: unknown) {
    addUserError.value = e instanceof Error ? e.message : '创建失败，请重试'
  } finally {
    addUserLoading.value = false
  }
}

function confirmDeleteUser(u: UserManageRow) {
  deleteTarget.value = u
}

async function doDeleteUser() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  try {
    await apiClient.delete(`/admin/users/${deleteTarget.value.id}`)
    deleteTarget.value = null
    showMsg('用户已删除', 'success')
    await fetchUsers()
  } catch (e: unknown) {
    showMsg(e instanceof Error ? e.message : '删除失败', 'error')
    deleteTarget.value = null
  } finally {
    deleteLoading.value = false
  }
}

async function changeRole(u: UserManageRow, role: UserRole) {
  try {
    await apiClient.patch(`/admin/users/${u.id}/role`, { role })
    u.role = role
    showMsg(`已将 ${u.username} 的角色修改为 ${roleLabel(role)}`, 'success')
  } catch (e: unknown) {
    showMsg(e instanceof Error ? e.message : '角色修改失败', 'error')
    await fetchUsers()
  }
}

function roleLabel(role: string) {
  const m: Record<string, string> = { TRADER: '量化交易员', ADMIN: '系统管理员', READONLY: '只读观察员' }
  return m[role] ?? role
}

function showMsg(msg: string, type: 'success' | 'error') {
  userMsg.value = msg
  userMsgType.value = type
  setTimeout(() => { userMsg.value = '' }, 3000)
}

// ── 系统监控 ──
const systemHealth = ref<SystemHealth | null>(null)
const healthLoading = ref(false)
let healthTimer: ReturnType<typeof setInterval> | null = null

async function fetchHealth() {
  healthLoading.value = true
  try {
    const res = await apiClient.get<SystemHealth>('/admin/system-health')
    systemHealth.value = res.data
  } catch {
    /* handle error */
  } finally {
    healthLoading.value = false
  }
}

// ── 备份与恢复 ──
const showBackupConfirm = ref(false)
const showRestoreConfirm = ref(false)
const backupLoading = ref(false)
const restoreLoading = ref(false)
const backupMsg = ref('')
const backupMsgType = ref<'success' | 'error'>('success')

function confirmBackup() { showBackupConfirm.value = true }
function confirmRestore() { showRestoreConfirm.value = true }

async function doBackup() {
  backupLoading.value = true
  showBackupConfirm.value = false
  try {
    await apiClient.post('/admin/backup')
    backupMsg.value = '备份任务已触发，请稍后查看结果'
    backupMsgType.value = 'success'
  } catch (e: unknown) {
    backupMsg.value = e instanceof Error ? e.message : '备份失败，请重试'
    backupMsgType.value = 'error'
  } finally {
    backupLoading.value = false
    setTimeout(() => { backupMsg.value = '' }, 4000)
  }
}

async function doRestore() {
  restoreLoading.value = true
  showRestoreConfirm.value = false
  try {
    await apiClient.post('/admin/restore')
    backupMsg.value = '恢复任务已触发，请稍后查看结果'
    backupMsgType.value = 'success'
  } catch (e: unknown) {
    backupMsg.value = e instanceof Error ? e.message : '恢复失败，请重试'
    backupMsgType.value = 'error'
  } finally {
    restoreLoading.value = false
    setTimeout(() => { backupMsg.value = '' }, 4000)
  }
}

// ── 操作日志 ──
const logs = ref<LogEntry[]>([])
const logsLoading = ref(false)
const logStart = ref(new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10))
const logEnd = ref(new Date().toISOString().slice(0, 10))
const logActionType = ref('')

async function fetchLogs() {
  logsLoading.value = true
  try {
    const res = await apiClient.get<LogEntry[]>('/admin/logs', {
      params: {
        start: logStart.value,
        end: logEnd.value,
        action_type: logActionType.value || undefined,
      },
    })
    logs.value = res.data
  } catch {
    /* handle error */
  } finally {
    logsLoading.value = false
  }
}

// ── 生命周期 ──
onMounted(() => {
  fetchUsers()
  fetchHealth()
  fetchLogs()
  // 每 30 秒自动刷新系统健康状态
  healthTimer = setInterval(fetchHealth, 30_000)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
})
</script>

<style scoped>
.admin-view { max-width: 1200px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sub-title { font-size: 14px; color: #8b949e; margin-bottom: 10px; font-weight: 500; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

/* 标签页 */
.tabs { display: flex; gap: 4px; margin-bottom: 20px; }
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.tab:hover:not(.active) { color: #e6edf3; }

/* 卡片 */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.header-right { display: flex; align-items: center; gap: 8px; }
.auto-refresh-hint { font-size: 12px; color: #484f58; }

/* 输入 */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.input.full { width: 100%; box-sizing: border-box; }
.input:focus { outline: none; border-color: #58a6ff; }

/* 按钮 */
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover:not(:disabled) { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-warning { background: #9a6700; color: #fff; border: none; }
.btn-warning:hover:not(:disabled) { background: #b07800; }
.btn-danger { background: #da3633; color: #fff; border: none; }
.btn-danger:hover:not(:disabled) { background: #f85149; }

.btn-icon {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  width: 30px; height: 30px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.btn-icon:hover { color: #e6edf3; border-color: #58a6ff; }
.btn-icon:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm {
  background: none; border: 1px solid #30363d; color: #8b949e;
  padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px;
}
.btn-sm.danger:hover { color: #f85149; border-color: #f85149; }

/* 刷新图标 */
.refresh-icon { display: inline-block; }
.refresh-icon.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.empty { text-align: center; color: #484f58; padding: 24px; }
.detail-cell { font-size: 12px; color: #8b949e; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 角色选择 */
.role-select {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 3px 8px; border-radius: 4px; font-size: 13px; cursor: pointer;
}
.role-select:focus { outline: none; border-color: #58a6ff; }

/* 状态 */
.status-active { color: #3fb950; font-size: 13px; }
.status-inactive { color: #484f58; font-size: 13px; }

/* 操作类型徽章 */
.action-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; background: #1f6feb22; color: #58a6ff;
}

/* 消息提示 */
.save-msg { font-size: 13px; display: block; margin-top: 8px; }
.save-msg.success { color: #3fb950; }
.save-msg.error { color: #f85149; }

/* 筛选行 */
.filter-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }

/* 系统监控 */
.monitor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.monitor-card { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 14px; }
.monitor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.monitor-name { font-size: 14px; color: #e6edf3; }
.monitor-status { font-size: 13px; font-weight: 500; }
.healthy { color: #3fb950; }
.unhealthy { color: #f85149; }
.monitor-meta { font-size: 12px; color: #484f58; }

/* 备份区域 */
.backup-row { margin-top: 20px; padding-top: 16px; border-top: 1px solid #21262d; }
.backup-actions { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }

/* 对话框 */
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65); display: flex;
  align-items: center; justify-content: center; z-index: 200;
}
.dialog {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 24px; width: 420px; max-width: 90vw;
}
.dialog h3 { margin-bottom: 16px; color: #e6edf3; font-size: 16px; }
.danger-title { color: #f85149; }
.confirm-text { color: #8b949e; font-size: 14px; line-height: 1.6; margin-bottom: 4px; }
.confirm-text strong { color: #e6edf3; }
.form-group { margin-bottom: 12px; }
.form-group label { font-size: 13px; color: #8b949e; display: block; margin-bottom: 4px; }
.dialog-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }

.loading-text { color: #8b949e; font-size: 14px; padding: 16px 0; }
</style>
