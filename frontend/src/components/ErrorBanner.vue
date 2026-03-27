<template>
  <div class="error-banner" role="alert">
    <span class="error-icon">⚠️</span>
    <span class="error-message">{{ message }}</span>
    <button v-if="retryFn" class="retry-btn" @click="retryFn">重试</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  message: string
  retryFn: (() => void) | null
}>()
</script>

<style scoped>
.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #1c2128;
  border: 1px solid #f8514966;
  border-left: 4px solid #f85149;
  border-radius: 6px;
  color: #e6edf3;
  font-size: 14px;
}

.error-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.error-message {
  flex: 1;
  color: #ffa198;
}

.retry-btn {
  background: none;
  border: 1px solid #f85149;
  color: #f85149;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
}

.retry-btn:hover {
  background: #f85149;
  color: #fff;
}
</style>
