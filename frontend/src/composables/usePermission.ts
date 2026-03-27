import { computed, type ComputedRef } from 'vue'
import { useAuthStore, type UserRole } from '@/stores/auth'

/**
 * 权限检查 composable
 * 提供基于角色的权限判断，用于页面内操作按钮级别的角色校验
 */
export function usePermission() {
  const authStore = useAuthStore()

  /**
   * 检查当前用户是否拥有指定角色之一
   */
  function hasRole(roles: UserRole[]): boolean {
    return roles.includes(authStore.role)
  }

  /**
   * 是否可以执行交易操作（TRADER 或 ADMIN）
   */
  const canTrade: ComputedRef<boolean> = computed(() =>
    hasRole(['TRADER', 'ADMIN'])
  )

  /**
   * 是否可以访问系统管理（仅 ADMIN）
   */
  const canAdmin: ComputedRef<boolean> = computed(() =>
    hasRole(['ADMIN'])
  )

  /**
   * 是否为只读观察员
   */
  const isReadonly: ComputedRef<boolean> = computed(() =>
    authStore.role === 'READONLY'
  )

  return { hasRole, canTrade, canAdmin, isReadonly }
}
