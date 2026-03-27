<template>
  <div class="loading-spinner" :class="`size-${size}`" role="status" aria-label="加载中">
    <div class="spinner-ring"></div>
    <span v-if="text" class="spinner-text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg'
    text?: string
  }>(),
  { size: 'md' },
)
</script>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.spinner-ring {
  border-radius: 50%;
  border-style: solid;
  border-color: #30363d;
  border-top-color: #58a6ff;
  animation: spin 0.8s linear infinite;
}

.size-sm .spinner-ring { width: 20px; height: 20px; border-width: 2px; }
.size-md .spinner-ring { width: 36px; height: 36px; border-width: 3px; }
.size-lg .spinner-ring { width: 56px; height: 56px; border-width: 4px; }

.spinner-text {
  font-size: 13px;
  color: #8b949e;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
