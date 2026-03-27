import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Position {
  symbol: string
  name?: string
  quantity: number
  available_quantity: number
  cost_price: number
  current_price: number
  market_value: number
  profit_loss: number
  profit_loss_ratio: number
  updated_at?: string
}

export const usePositionsStore = defineStore('positions', () => {
  const positions = ref<Position[]>([])
  const loading = ref(false)

  function updatePosition(pos: Position) {
    const idx = positions.value.findIndex((p) => p.symbol === pos.symbol)
    if (idx !== -1) {
      positions.value[idx] = { ...positions.value[idx], ...pos }
    } else {
      positions.value.push(pos)
    }
  }

  function setPositions(list: Position[]) {
    positions.value = list
  }

  function clearPositions() {
    positions.value = []
  }

  return { positions, loading, updatePosition, setPositions, clearPositions }
})
