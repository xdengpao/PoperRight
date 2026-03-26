<template>
  <router-view />
</template>

<script setup lang="ts">
// 根组件：仅挂载路由视图，布局由各页面自行管理
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body,
#app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    sans-serif;
  background-color: #0d1117;
  color: #e6edf3;
}
</style>
