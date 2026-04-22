<template>
  <nav class="tushare-tab-nav" aria-label="Tushare 功能导航">
    <button
      v-for="tab in tabs"
      :key="tab.routeName"
      class="tab-item"
      :class="{ active: currentRouteName === tab.routeName }"
      :aria-current="currentRouteName === tab.routeName ? 'page' : undefined"
      @click="navigateTo(tab.routeName)"
    >
      {{ tab.label }}
    </button>
  </nav>
</template>

<script setup lang="ts">
/**
 * TushareTabNav - Tushare 功能 Tab 导航组件
 *
 * 在 Tushare 数据导入页面和数据预览页面顶部渲染共享的 Tab 标签栏，
 * 通过 vue-router 的 useRoute() 判断当前激活的 Tab。
 *
 * 需求: 1.2, 1.3, 1.4
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { routeName: 'DataOnlineTushare', label: 'Tushare 数据导入' },
  { routeName: 'DataOnlineTusharePreview', label: 'Tushare 数据预览' },
]

const currentRouteName = computed(() => route.name)

function navigateTo(routeName: string): void {
  if (routeName !== currentRouteName.value) {
    router.push({ name: routeName })
  }
}
</script>

<style scoped>
.tushare-tab-nav {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #30363d;
  margin-bottom: 20px;
}

.tab-item {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  color: #8b949e;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.15s, border-color 0.15s;
}

.tab-item:hover {
  color: #e6edf3;
}

.tab-item.active {
  color: #e6edf3;
  border-bottom-color: #1f6feb;
}
</style>
