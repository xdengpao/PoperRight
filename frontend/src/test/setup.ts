// Vitest 全局测试环境初始化
import { config } from '@vue/test-utils'

// 全局组件/插件可在此注册
// config.global.plugins = [...]

// 抑制 Vue 控制台警告（测试环境）
config.global.config.warnHandler = () => null

// Node.js 22+ 内置 localStorage 与 jsdom 冲突修复
// jsdom 提供完整的 Web Storage API，但 Node.js 原生 localStorage 会覆盖它
// 这里确保 localStorage 具备标准 Web Storage API 方法
if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage.getItem !== 'function') {
  const store: Record<string, string> = {}
  globalThis.localStorage = {
    getItem(key: string) { return store[key] ?? null },
    setItem(key: string, value: string) { store[key] = String(value) },
    removeItem(key: string) { delete store[key] },
    clear() { Object.keys(store).forEach(k => delete store[k]) },
    get length() { return Object.keys(store).length },
    key(index: number) { return Object.keys(store)[index] ?? null },
  } as Storage
}
