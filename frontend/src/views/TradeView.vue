<template>
  <div class="trade-view">
    <h1 class="page-title">交易执行</h1>

    <!-- 一键下单 -->
    <section class="card" aria-label="一键下单">
      <h2 class="section-title">委托下单</h2>
      <div class="config-grid">
        <div class="config-item">
          <label for="order-symbol">股票代码</label>
          <input id="order-symbol" v-model="order.symbol" class="input" placeholder="如 000001" />
        </div>
        <div class="config-item">
          <label for="order-direction">方向</label>
          <select id="order-direction" v-model="order.direction" class="input">
            <option value="BUY">买入</option>
            <option value="SELL">卖出</option>
          </select>
        </div>
        <div class="config-item">
          <label for="order-type">委托类型</label>
          <select id="order-type" v-model="order.orderType" class="input">
            <option value="LIMIT">限价委托</option>
            <option value="MARKET">市价委托</option>
          </select>
        </div>
        <div class="config-item" v-if="order.orderType === 'LIMIT'">
          <label for="order-price">委托价格</label>
          <input id="order-price" v-model.number="order.price" type="number" step="0.01" class="input" />
        </div>
        <div class="config-item">
          <label for="order-qty">委托数量 (股)</label>
          <input id="order-qty" v-model.number="order.quantity" type="number" step="100" class="input" />
        </div>
        <div class="config-item">
          <label for="order-sl">止损价</label>
          <input id="order-sl" v-model.number="order.stopLoss" type="number" step="0.01" class="input" />
        </div>
        <div class="config-item">
          <label for="order-tp">止盈价</label>
          <input id="order-tp" v-model.number="order.takeProfit" type="number" step="0.01" class="input" />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn" :class="order.direction === 'BUY' ? 'btn-buy' : 'btn-sell'" @click="submitOrder" :disabled="submitting">
          {{ submitting ? '提交中...' : order.direction === 'BUY' ? '买入' : '卖出' }}
        </button>
      </div>
    </section>

    <!-- 条件单配置 -->
    <section class="card" aria-label="条件单配置">
      <h2 class="section-title">条件单</h2>
      <div class="config-grid">
        <div class="config-item">
          <label for="cond-symbol">股票代码</label>
          <input id="cond-symbol" v-model="condOrder.symbol" class="input" placeholder="如 000001" />
        </div>
        <div class="config-item">
          <label for="cond-type">条件类型</label>
          <select id="cond-type" v-model="condOrder.condType" class="input">
            <option value="BREAKOUT_BUY">突破买入</option>
            <option value="STOP_LOSS_SELL">止损卖出</option>
            <option value="TAKE_PROFIT_SELL">止盈卖出</option>
            <option value="TRAILING_SELL">移动止盈卖出</option>
          </select>
        </div>
        <div class="config-item">
          <label for="cond-trigger">触发价格</label>
          <input id="cond-trigger" v-model.number="condOrder.triggerPrice" type="number" step="0.01" class="input" />
        </div>
        <div class="config-item">
          <label for="cond-qty">委托数量</label>
          <input id="cond-qty" v-model.number="condOrder.quantity" type="number" step="100" class="input" />
        </div>
      </div>
      <button class="btn btn-outline" @click="submitCondOrder" style="margin-top: 12px;">创建条件单</button>
    </section>

    <!-- 交易流水 -->
    <section class="card" aria-label="交易流水">
      <h2 class="section-title">交易流水</h2>
      <div class="filter-row">
        <label for="flow-start" class="sr-only">开始日期</label>
        <input id="flow-start" v-model="flowStart" type="date" class="input" />
        <label for="flow-end" class="sr-only">结束日期</label>
        <input id="flow-end" v-model="flowEnd" type="date" class="input" />
        <button class="btn btn-outline" @click="fetchOrders">查询</button>
      </div>
      <table class="data-table" aria-label="委托记录">
        <thead>
          <tr>
            <th scope="col">时间</th>
            <th scope="col">代码</th>
            <th scope="col">方向</th>
            <th scope="col">类型</th>
            <th scope="col">价格</th>
            <th scope="col">数量</th>
            <th scope="col">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td>{{ o.submitted_at?.slice(0, 16) ?? '—' }}</td>
            <td class="mono">{{ o.symbol }}</td>
            <td :class="o.direction === 'BUY' ? 'up' : 'down'">{{ o.direction === 'BUY' ? '买入' : '卖出' }}</td>
            <td>{{ orderTypeLabel(o.order_type) }}</td>
            <td class="mono">{{ o.filled_price?.toFixed(2) ?? o.price?.toFixed(2) ?? '市价' }}</td>
            <td>{{ o.filled_qty ?? o.quantity }}</td>
            <td><span class="status-badge" :class="`status-${o.status.toLowerCase()}`">{{ statusLabel(o.status) }}</span></td>
          </tr>
          <tr v-if="orders.length === 0">
            <td colspan="7" class="empty">暂无记录</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { apiClient } from '@/api'

// 下单
const submitting = ref(false)
const order = reactive({
  symbol: '', direction: 'BUY' as 'BUY' | 'SELL', orderType: 'LIMIT' as 'LIMIT' | 'MARKET',
  price: null as number | null, quantity: 100, stopLoss: null as number | null, takeProfit: null as number | null,
})

async function submitOrder() {
  submitting.value = true
  try {
    await apiClient.post('/trade/order', {
      symbol: order.symbol, direction: order.direction, order_type: order.orderType,
      price: order.orderType === 'LIMIT' ? order.price : undefined,
      quantity: order.quantity, stop_loss: order.stopLoss, take_profit: order.takeProfit,
    })
    await fetchOrders()
  } catch { /* handle error */ }
  submitting.value = false
}

// 条件单
const condOrder = reactive({
  symbol: '', condType: 'BREAKOUT_BUY', triggerPrice: null as number | null, quantity: 100,
})

async function submitCondOrder() {
  try {
    await apiClient.post('/trade/conditions', {
      symbol: condOrder.symbol, condition_type: condOrder.condType,
      trigger_price: condOrder.triggerPrice, quantity: condOrder.quantity,
    })
  } catch { /* handle error */ }
}

// 交易流水
interface OrderRecord {
  id: string; symbol: string; direction: string; order_type: string
  price: number | null; quantity: number; status: string
  filled_price: number | null; filled_qty: number | null; submitted_at: string
}
const orders = ref<OrderRecord[]>([])
const flowStart = ref(new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10))
const flowEnd = ref(new Date().toISOString().slice(0, 10))

async function fetchOrders() {
  try {
    const res = await apiClient.get<OrderRecord[]>('/trade/orders', {
      params: { start: flowStart.value, end: flowEnd.value },
    })
    orders.value = res.data
  } catch { /* handle error */ }
}

function orderTypeLabel(t: string) {
  const m: Record<string, string> = { LIMIT: '限价', MARKET: '市价', CONDITION: '条件单' }
  return m[t] ?? t
}
function statusLabel(s: string) {
  const m: Record<string, string> = { PENDING: '待成交', FILLED: '已成交', CANCELLED: '已撤单', REJECTED: '已拒绝' }
  return m[s] ?? s
}

onMounted(() => { fetchOrders() })
</script>

<style scoped>
.trade-view { max-width: 1100px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.form-actions { margin-top: 16px; }
.filter-row { display: flex; gap: 8px; margin-bottom: 12px; }

.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.btn {
  background: #238636; color: #fff; border: none; padding: 8px 24px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-buy { background: #f85149; }
.btn-buy:hover { background: #da3633; }
.btn-sell { background: #3fb950; }
.btn-sell:hover { background: #2ea043; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover { color: #e6edf3; border-color: #8b949e; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', monospace; }
.up { color: #f85149; }
.down { color: #3fb950; }
.empty { text-align: center; color: #484f58; padding: 24px; }

.status-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.status-pending { background: #d2992222; color: #d29922; }
.status-filled { background: #3fb95022; color: #3fb950; }
.status-cancelled { background: #484f5822; color: #484f58; }
.status-rejected { background: #f8514922; color: #f85149; }
</style>
