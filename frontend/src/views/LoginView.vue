<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">A股量化选股系统</h1>
      <p class="login-subtitle">右侧趋势交易 · 智能量化选股</p>

      <form class="login-form" @submit.prevent="handleLogin" novalidate>
        <div class="form-group">
          <label for="username" class="form-label">用户名</label>
          <input
            id="username"
            v-model.trim="username"
            type="text"
            class="form-input"
            placeholder="请输入用户名"
            autocomplete="username"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label for="password" class="form-label">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="请输入密码"
            autocomplete="current-password"
            :disabled="loading"
          />
        </div>

        <div v-if="errorMessage" class="error-message" role="alert">
          {{ errorMessage }}
        </div>

        <button type="submit" class="login-button" :disabled="loading || !username || !password">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <div class="login-footer">
        <router-link to="/register" class="register-link">还没有账号？立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) return

  errorMessage.value = ''
  loading.value = true

  try {
    await authStore.login(username.value, password.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: unknown) {
    password.value = ''
    if (err instanceof Error) {
      errorMessage.value = err.message
    } else {
      errorMessage.value = '用户名或密码错误'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 40px 32px;
  background-color: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
}

.login-title {
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  color: #e6edf3;
  margin-bottom: 4px;
}

.login-subtitle {
  text-align: center;
  font-size: 14px;
  color: #8b949e;
  margin-bottom: 32px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 14px;
  color: #c9d1d9;
}

.form-input {
  padding: 10px 12px;
  font-size: 14px;
  color: #e6edf3;
  background-color: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: #58a6ff;
}

.form-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-input::placeholder {
  color: #484f58;
}

.error-message {
  padding: 10px 12px;
  font-size: 13px;
  color: #f85149;
  background-color: rgba(248, 81, 73, 0.1);
  border: 1px solid rgba(248, 81, 73, 0.3);
  border-radius: 6px;
}

.login-button {
  padding: 10px;
  font-size: 15px;
  font-weight: 500;
  color: #ffffff;
  background-color: #238636;
  border: 1px solid rgba(240, 246, 252, 0.1);
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.login-button:hover:not(:disabled) {
  background-color: #2ea043;
}

.login-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
}

.register-link {
  font-size: 13px;
  color: #58a6ff;
  text-decoration: none;
}

.register-link:hover {
  text-decoration: underline;
}
</style>
