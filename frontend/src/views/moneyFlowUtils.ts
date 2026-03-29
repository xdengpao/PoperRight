/**
 * 资金流向柱状图颜色映射纯函数
 *
 * 根据主力资金净流入金额返回对应的柱状图颜色：
 * - main_net_inflow ≥ 0 → '#f85149'（红色，资金流入）
 * - main_net_inflow < 0 → '#3fb950'（绿色，资金流出）
 *
 * @param value - 主力资金净流入金额（万元）
 * @returns 十六进制颜色字符串
 */
export function getMoneyFlowBarColor(value: number): string {
  return value >= 0 ? '#f85149' : '#3fb950'
}
