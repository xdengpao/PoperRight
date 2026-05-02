<template>
  <div class="register-page">
    <div class="register-card">
      <h1 class="register-title">创建账号</h1>
      <p class="register-subtitle">A股量化选股系统 · 注册新用户</p>

      <form class="register-form" @submit.prevent="handleRegister" novalidate>
        <div class="form-group">
          <label for="reg-username" class="form-label">用户名</label>
          <div class="input-wrapper">
            <input
              id="reg-username"
              v-model.trim="username"
              type="text"
              class="form-input"
              :class="usernameInputClass"
              placeholder="请输入用户名"
              autocomplete="username"
              :disabled="loading"
              @input="onUsernameInput"
            />
            <span v-if="usernameChecking" class="input-status checking">检查中...</span>
            <span v-else-if="username && usernameAvailable === true" class="input-status valid">✓</span>
            <span v-else-if="username && usernameAvailable === false" class="input-status invalid">✗</span>
          </div>
          <p v-if="username && usernameAvailable === false" class="field-error">{{ usernameMessage }}</p>
        </div>

        <div class="form-group">
          <label for="reg-password" class="form-label">密码</label>
          <input
            id="reg-password"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="请输入密码"
            autocomplete="new-password"
            :disabled="loading"
          />
          <ul class="password-rules">
            <li :class="passwordChecks.minLength ? 'rule-pass' : 'rule-fail'">
              <span class="rule-icon">{{ passwordChecks.minLength ? '✓' : '✗' }}</span> ≥8 位字符
            </li>
            <li :class="passwordChecks.hasUppercase ? 'rule-pass' : 'rule-fail'">
              <span class="rule-icon">{{ passwordChecks.hasUppercase ? '✓' : '✗' }}</span> 包含大写字母
            </li>
            <li :class="passwordChecks.hasLowercase ? 'rule-pass' : 'rule-fail'">
              <span class="rule-icon">{{ passwordChecks.hasLowercase ? '✓' : '✗' }}</span> 包含小写字母
            </li>
            <li :class="passwordChecks.hasDigit ? 'rule-pass' : 'rule-fail'">
              <span class="rule-icon">{{ passwordChecks.hasDigit ? '✓' : '✗' }}</span> 包含数字
            </li>
          </ul>
        </div>

        <div v-if="errorMessage" class="error-message" role="alert">
          {{ errorMessage }}
        </div>

        <button type="submit" class="register-button" :disabled="!canSubmit">
          {{ loading ? '注册中...' : '注 册' }}
        </button>
      </form>

      <div class="register-footer">
        <router-link to="/login" class="login-link">已有账号？返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api'

const router = useRouter()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const loading = ref(false)

// Username availability state
const usernameAvailable = ref<boolean | null>(null)
const usernameChecking = ref(false)
const usernameMessage = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Password strength checks (reactive)
const passwordChecks = computed(() => ({
  minLength: password.value.length >= 8,
  hasUppercase: /[A-Z]/.test(password.value),
  hasLowercase: /[a-z]/.test(password.value),
  hasDigit: /\d/.test(password.value),
}))

const allPasswordValid = computed(
  () =>
    passwordChecks.value.minLength &&
    passwordChecks.value.hasUppercase &&
    passwordChecks.value.hasLowercase &&
    passwordChecks.value.hasDigit,
)

const canSubmit = computed(
  () =>
    !loading.value &&
    username.value.length > 0 &&
    usernameAvailable.value === true &&
    allPasswordValid.value,
)

const usernameInputClass = computed(() => {
  if (!username.value) return ''
  if (usernameChecking.value) return ''
  if (usernameAvailable.value === true) return 'input-valid'
  if (usernameAvailable.value === false) return 'input-invalid'
  return ''
})

function onUsernameInput() {
  // Reset state on each keystroke
  usernameAvailable.value = null
  usernameMessage.value = ''

  if (debounceTimer) clearTimeout(debounceTimer)

  if (!username.value) {
    usernameChecking.value = false
    return
  }

  usernameChecking.value = true
  debounceTimer = setTimeout(() => {
    checkUsername(username.value)
  }, 400)
}

async function checkUsername(name: string) {
  if (!name) {
    usernameChecking.value = false
    return
  }
  try {
    const res = await apiClient.get<{ available: boolean; message: string }>(
      '/auth/check-username',
      { params: { username: name } },
    )
    // Only update if the username hasn't changed while we were checking
    if (username.value === name) {
      usernameAvailable.value = res.data.available
      usernameMessage.value = res.data.message ?? '用户名已被占用'
    }
  } catch {
    if (username.value === name) {
      usernameAvailable.value = null
      usernameMessage.value = ''
    }
  } finally {
    if (username.value === name) {
      usernameChecking.value = false
    }
  }
}

async function handleRegister() {
  if (!canSubmit.value) return

  errorMessage.value = ''
  loading.value = true

  try {
    await apiClient.post('/auth/register', {
      username: username.value,
      password: password.value,
    })
    router.push('/login')
  } catch (err: unknown) {
    if (err instanceof Error) {
      errorMessage.value = err.message
    } else {
      errorMessage.value = '注册失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}

// Clean up debounce timer
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<style scoped>
.register-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
}

.register-card {
  width: 100%;
  max-width: 400px;
  padding: 40px 32px;
  background-color: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
}

.register-title {
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  color: #e6edf3;
  margin-bottom: 4px;
}

.register-subtitle {
  text-align: center;
  font-size: 14px;
  color: #8b949e;
  margin-bottom: 32px;
}

.register-form {
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

.input-wrapper {
  position: relative;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  padding-right: 80px;
  font-size: 14px;
  color: #e6edf3;
  background-color: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
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

.form-input.input-valid {
  border-color: #3fb950;
}

.form-input.input-invalid {
  border-color: #f85149;
}

.input-status {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 13px;
}

.input-status.checking {
  color: #8b949e;
}

.input-status.valid {
  color: #3fb950;
  font-weight: 600;
}

.input-status.invalid {
  color: #f85149;
  font-weight: 600;
}

.field-error {
  font-size: 12px;
  color: #f85149;
  margin: 0;
}

.password-rules {
  list-style: none;
  padding: 0;
  margin: 4px 0 0 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.password-rules li {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.rule-pass {
  color: #3fb950;
}

.rule-fail {
  color: #f85149;
}

.rule-icon {
  font-weight: 600;
  width: 14px;
  text-align: center;
}

.error-message {
  padding: 10px 12px;
  font-size: 13px;
  color: #f85149;
  background-color: rgba(248, 81, 73, 0.1);
  border: 1px solid rgba(248, 81, 73, 0.3);
  border-radius: 6px;
}

.register-button {
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

.register-button:hover:not(:disabled) {
  background-color: #2ea043;
}

.register-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.register-footer {
  margin-top: 24px;
  text-align: center;
}

.login-link {
  font-size: 13px;
  color: #58a6ff;
  text-decoration: none;
}

.login-link:hover {
  text-decoration: underline;
}
</style>
