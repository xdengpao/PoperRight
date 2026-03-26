// Vitest 全局测试环境初始化
import { config } from '@vue/test-utils'

// 全局组件/插件可在此注册
// config.global.plugins = [...]

// 抑制 Vue 控制台警告（测试环境）
config.global.config.warnHandler = () => null
