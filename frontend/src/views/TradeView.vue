<template>
  <div class="trade-view">
    <div class="page-header">
      <h1 class="page-title">交易执行</h1>
      <!-- 实盘/模拟盘切换 -->
      <div class="mode-switch" role="group" aria-label="交易模式切换">
        <button
          :class="['mode-btn', tradeMode === 'PAPER' && 'active-paper']"
          @click="tradeMode = 'PAPER'"
          aria-pressed="tradeMode === 'PAPER'"
        >模拟盘</button>
        <button
          :class="['mode-btn', tradeMode === 'LIVE' && 'active-live']"
          @click="confirmSwitchLive"
          aria-pressed="tradeMode === 'LIVE'"
        >实盘</button>
      </div>
    </div>

    <!-- 实盘警告横幅 -->
    <div v-if="tradeMode === 'LIVE'" class="live-banner" role="alert">
      ⚠ 当前为实盘模式，委托将直接提交至真实账户，请谨慎操作
    </div>

    <div class="main-layout">
      <!-- 左侧：选股池标的列表 -->
      <aside class="stock-pool-panel" aria-label="选股池标的">
        <div class="panel-header">
          <h2 class="section-title">选股池标的</h2>
          <button class="btn-icon" @click="fetchScreenResults" :disabled="poolLoading" aria-label="刷新选股池">
            <span :class="['refresh-icon', poolLoading && 'spinning']">↻</span>
          </button>
        </div>
        <div v-if="poolLoading" class="loading-text">加载中...</div>
        <ul v-else class="stock-list" role="listbox" aria-label="选股池标的列表">
          <li
            v-for="s in screenResults"
            :key="s.symbol"
            class="stock-item"
            :class="selectedSymbol === s.symbol && 'selected'"
            role="option"
            :aria-selected="selectedSymbol === s.symbol"
            @click="fillOrderFromPool(s)"
            tabindex="0"
            @keyup.enter="fillOrderFromPool(s)"
          >
            <div class="stock-item-top">
              <span class="stock-code">{{ s.symbol }}</span>
              <span class="stock-change" :class="s.change_pct >= 0 ? 'up' : 'down'">
                {{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct?.toFixed(2) }}%
              </span>
            </div>
            <div class="stock-item-bottom">
              <span class="stock-name">{{ s.name }}</span>
              <span class="stock-price">{{ s.close?.toFixed(2) }}</span>
            </div>
            <div v-if="s.ref_buy_price" class="stock-hints">
              <span class="hint-tag">参考买入 {{ s.ref_buy_price?.toFixed(2) }}</span>
            </div>
          </li>
          <li v-if="screenResults.length === 0" class="empty-pool">暂无选股结果</li>
        </ul>
      </aside>

      <!-- 右侧：下单区域 -->
      <div class="order-area">
        <!-- 只读观察员提示 -->
        <div v-if="isReadonly" class="readonly-notice" role="alert">
          🔒 您没有交易权限，仅可查看委托与成交记录
        </div>

        <!-- 下单表单（仅 TRADER / ADMIN 可见） -->
        <section v-if="canTrade" class="card" aria-label="委托下单">
          <div class="section-header">
            <h2 class="section-title">委托下单</h2>
            <div class="order-type-tabs" role="tablist">
              <button
                role="tab"
                :aria-selected="orderTab === 'normal'"
                :class="['tab', orderTab === 'normal' && 'active']"
                @click="orderTab = 'normal'"
              >普通委托</button>
              <button
                role="tab"
                :aria-selected="orderTab === 'condition'"
                :class="['tab', orderTab === 'condition' && 'active']"
                @click="orderTab = 'condition'"
              >条件单</button>
            </div>
          </div>

          <!-- 普通委托表单 -->
          <div v-if="orderTab === 'normal'" class="order-form">
            <div class="config-grid">
              <div class="config-item">
                <label for="order-symbol">股票代码</label>
                <input
                  id="order-symbol"
                  v-model="order.symbol"
                  class="input"
                  placeholder="如 000001.SZ"
                  @input="order.symbol = (order.symbol as string).toUpperCase()"
                />
              </div>
              <div class="config-item">
                <label for="order-direction">方向</label>
                <div class="direction-btns" role="group" aria-label="买卖方向">
                  <button
                    :class="['dir-btn', 'dir-buy', order.direction === 'BUY' && 'active']"
                    @click="order.direction = 'BUY'"
                    aria-pressed="order.direction === 'BUY'"
                  >买入</button>
                  <button
                    :class="['dir-btn', 'dir-sell', order.direction === 'SELL' && 'active']"
                    @click="order.direction = 'SELL'"
                    aria-pressed="order.direction === 'SELL'"
                  >卖出</button>
                </div>
              </div>
              <div class="config-item">
                <label for="order-type">委托类型</label>
                <select id="order-type" v-model="order.orderType" class="input">
                  <option value="LIMIT">限价委托</option>
                  <option value="MARKET">市价委托</option>
                </select>
              </div>
              <div class="config-item" v-if="order.orderType === 'LIMIT'">
                <label for="order-price">委托价格 (元)</label>
                <input
                  id="order-price"
                  v-model.number="order.price"
                  type="number"
                  step="0.01"
                  min="0"
                  class="input"
                  placeholder="限价价格"
                />
              </div>
              <div v-else class="config-item">
                <label>委托价格</label>
                <div class="market-price-hint">市价成交</div>
              </div>
              <div class="config-item">
                <label for="order-qty">委托数量 (股)</label>
                <input
                  id="order-qty"
                  v-model.number="order.quantity"
                  type="number"
                  step="100"
                  min="100"
                  class="input"
                />
              </div>
              <div class="config-item">
                <label for="order-sl">止损价 (元)</label>
                <input
                  id="order-sl"
                  v-model.number="order.stopLoss"
                  type="number"
                  step="0.01"
                  min="0"
                  class="input"
                  placeholder="可选"
                />
              </div>
              <div class="config-item">
                <label for="order-tp">止盈价 (元)</label>
                <input
                  id="order-tp"
                  v-model.number="order.takeProfit"
                  type="number"
                  step="0.01"
                  min="0"
                  class="input"
                  placeholder="可选"
                />
              </div>
            </div>

            <div v-if="orderMsg" class="order-msg" :class="orderMsgType" role="alert">{{ orderMsg }}</div>

            <div class="form-actions">
              <button
                class="btn submit-btn"
                :class="order.direction === 'BUY' ? 'btn-buy' : 'btn-sell'"
                @click="submitOrder"
                :disabled="submitting"
                :aria-label="order.direction === 'BUY' ? '提交买入委托' : '提交卖出委托'"
              >
                <span v-if="submitting" class="spinner" aria-hidden="true"></span>
                {{ submitting ? '提交中...' : order.direction === 'BUY' ? '买入委托' : '卖出委托' }}
              </button>
              <button class="btn btn-outline" @click="resetOrderForm">重置</button>
            </div>
          </div>

          <!-- 条件单表单 -->
          <div v-else class="order-form">
            <div class="config-grid">
              <div class="config-item">
                <label for="cond-symbol">股票代码</label>
                <input
                  id="cond-symbol"
                  v-model="condOrder.symbol"
                  class="input"
                  placeholder="如 000001.SZ"
                  @input="condOrder.symbol = (condOrder.symbol as string).toUpperCase()"
                />
              </div>
              <div class="config-item">
                <label for="cond-type">条件类型</label>
                <select id="cond-type" v-model="condOrder.type" class="input">
                  <option value="BREAKOUT_BUY">突破买入</option>
                  <option value="STOP_LOSS">止损卖出</option>
                  <option value="TAKE_PROFIT">止盈卖出</option>
                  <option value="TRAILING_STOP">移动止盈</option>
                </select>
              </div>
              <div class="config-item">
                <label for="cond-trigger">触发价格 (元)</label>
                <input
                  id="cond-trigger"
                  v-model.number="condOrder.trigger_price"
                  type="number"
                  step="0.01"
                  min="0"
                  class="input"
                />
              </div>
              <div class="config-item">
                <label for="cond-qty">委托数量 (股)</label>
                <input
                  id="cond-qty"
                  v-model.number="condOrder.order_quantity"
                  type="number"
                  step="100"
                  min="100"
                  class="input"
                />
              </div>
            </div>

            <div class="cond-type-desc">
              <span class="hint-tag">{{ condTypeDesc }}</span>
            </div>

            <div v-if="condMsg" class="order-msg" :class="condMsgType" role="alert">{{ condMsg }}</div>

            <div class="form-actions">
              <button class="btn btn-primary" @click="submitCondOrder" :disabled="condSubmitting">
                <span v-if="condSubmitting" class="spinner" aria-hidden="true"></span>
                {{ condSubmitting ? '创建中...' : '创建条件单' }}
              </button>
              <button class="btn btn-outline" @click="resetCondForm">重置</button>
            </div>
          </div>
        </section>

        <!-- 委托记录 & 成交记录 -->
        <section class="card" aria-label="委托与成交记录">
          <div class="section-header">
            <h2 class="section-title">委托 / 成交记录</h2>
            <div class="record-tabs" role="tablist">
              <button
                role="tab"
                :aria-selected="recordTab === 'orders'"
                :class="['tab', recordTab === 'orders' && 'active']"
                @click="recordTab = 'orders'"
              >委托记录</button>
              <button
                role="tab"
                :aria-selected="recordTab === 'filled'"
                :class="['tab', recordTab === 'filled' && 'active']"
                @click="recordTab = 'filled'"
              >成交记录</button>
              <button
                role="tab"
                :aria-selected="recordTab === 'conditions'"
                :class="['tab', recordTab === 'conditions' && 'active']"
                @click="recordTab = 'conditions'; fetchConditions()"
              >条件单</button>
            </div>
          </div>

          <!-- 查询过滤 -->
          <div v-if="recordTab !== 'conditions'" class="filter-row">
            <label for="flow-start" class="sr-only">开始日期</label>
            <input id="flow-start" v-model="flowStart" type="date" class="input input-sm" />
            <label for="flow-end" class="sr-only">结束日期</label>
            <input id="flow-end" v-model="flowEnd" type="date" class="input input-sm" />
            <select v-model="filterMode" class="input input-sm" aria-label="模式筛选">
              <option value="">全部模式</option>
              <option value="LIVE">实盘</option>
              <option value="PAPER">模拟盘</option>
            </select>
            <button class="btn btn-outline btn-sm" @click="fetchOrders">查询</button>
          </div>

          <!-- 委托记录表 -->
          <div v-if="recordTab === 'orders'" class="table-wrap">
            <div v-if="ordersLoading" class="loading-text">加载中...</div>
            <table v-else class="data-table" aria-label="委托记录表">
              <thead>
                <tr>
                  <th scope="col">提交时间</th>
                  <th scope="col">代码</th>
                  <th scope="col">方向</th>
                  <th scope="col">类型</th>
                  <th scope="col">委托价</th>
                  <th scope="col">数量</th>
                  <th scope="col">模式</th>
                  <th scope="col">状态</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="o in orders" :key="o.id">
                  <td>{{ o.submitted_at?.slice(0, 16) ?? '—' }}</td>
                  <td class="mono">{{ o.symbol }}</td>
                  <td>
                    <span class="direction-badge" :class="o.direction === 'BUY' ? 'buy' : 'sell'">
                      {{ o.direction === 'BUY' ? '买入' : '卖出' }}
                    </span>
                  </td>
                  <td>{{ orderTypeLabel(o.order_type) }}</td>
                  <td class="mono">{{ o.price?.toFixed(2) ?? '市价' }}</td>
                  <td>{{ o.quantity.toLocaleString() }}</td>
                  <td>
                    <span class="mode-badge" :class="o.mode === 'LIVE' ? 'live' : 'paper'">
                      {{ o.mode === 'LIVE' ? '实盘' : '模拟' }}
                    </span>
                  </td>
                  <td>
                    <span class="status-badge" :class="`status-${o.status.toLowerCase()}`">
                      {{ statusLabel(o.status) }}
                    </span>
                  </td>
                  <td>
                    <button
                      v-if="o.status === 'PENDING'"
                      class="btn-sm danger"
                      @click="cancelOrder(o.id)"
                      aria-label="`撤单 ${o.symbol}`"
                    >撤单</button>
                    <span v-else class="text-muted">—</span>
                  </td>
                </tr>
                <tr v-if="orders.length === 0">
                  <td colspan="9" class="empty">暂无委托记录</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 成交记录表 -->
          <div v-else-if="recordTab === 'filled'" class="table-wrap">
            <div v-if="ordersLoading" class="loading-text">加载中...</div>
            <table v-else class="data-table" aria-label="成交记录表">
              <thead>
                <tr>
                  <th scope="col">成交时间</th>
                  <th scope="col">代码</th>
                  <th scope="col">方向</th>
                  <th scope="col">成交价</th>
                  <th scope="col">数量</th>
                  <th scope="col">模式</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="o in filledOrders" :key="o.id">
                  <td>{{ o.filled_at?.slice(0, 16) ?? '—' }}</td>
                  <td class="mono">{{ o.symbol }}</td>
                  <td>
                    <span class="direction-badge" :class="o.direction === 'BUY' ? 'buy' : 'sell'">
                      {{ o.direction === 'BUY' ? '买入' : '卖出' }}
                    </span>
                  </td>
                  <td class="mono">{{ o.filled_price?.toFixed(2) ?? '—' }}</td>
                  <td>{{ o.quantity.toLocaleString() }}</td>
                  <td>
                    <span class="mode-badge" :class="o.mode === 'LIVE' ? 'live' : 'paper'">
                      {{ o.mode === 'LIVE' ? '实盘' : '模拟' }}
                    </span>
                  </td>
                </tr>
                <tr v-if="filledOrders.length === 0">
                  <td colspan="6" class="empty">暂无成交记录</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 条件单列表 -->
          <div v-else class="table-wrap">
            <div v-if="conditionsLoading" class="loading-text">加载中...</div>
            <table v-else class="data-table" aria-label="条件单列表">
              <thead>
                <tr>
                  <th scope="col">代码</th>
                  <th scope="col">条件类型</th>
                  <th scope="col">触发价</th>
                  <th scope="col">数量</th>
                  <th scope="col">状态</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in conditions" :key="c.id">
                  <td class="mono">{{ c.symbol }}</td>
                  <td>{{ condTypeLabel(c.type) }}</td>
                  <td class="mono">{{ c.trigger_price?.toFixed(2) }}</td>
                  <td>{{ c.order_quantity?.toLocaleString() }}</td>
                  <td>
                    <span class="status-badge" :class="`status-${(c.status ?? 'pending').toLowerCase()}`">
                      {{ statusLabel(c.status ?? 'PENDING') }}
                    </span>
                  </td>
                  <td>
                    <button class="btn-sm danger" @click="deleteCondition(c.id)" aria-label="`删除条件单 ${c.symbol}`">删除</button>
                  </td>
                </tr>
                <tr v-if="conditions.length === 0">
                  <td colspan="6" class="empty">暂无条件单</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>

    <!-- 实盘确认对话框 -->
    <div v-if="showLiveConfirm" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="live-confirm-title">
      <div class="modal">
        <h3 id="live-confirm-title" class="modal-title">切换至实盘模式</h3>
        <p class="modal-body">切换后，所有委托将直接提交至真实账户，资金存在实际风险。确认切换？</p>
        <div class="modal-actions">
          <button class="btn btn-danger" @click="doSwitchLive">确认切换实盘</button>
          <button class="btn btn-outline" @click="showLiveConfirm = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { apiClient } from '@/api'
import { usePermission } from '@/composables/usePermission'

const { canTrade, isReadonly } = usePermission()

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

interface ScreenResult {
  symbol: string
  name: string
  close: number
  change_pct: number
  ref_buy_price: number | null
  stop_loss: number | null
  take_profit: number | null
}

interface TradeOrder {
  id: string
  symbol: string
  direction: 'BUY' | 'SELL'
  order_type: 'LIMIT' | 'MARKET' | 'CONDITION'
  price: number | null
  quantity: number
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED'
  mode: 'LIVE' | 'PAPER'
  submitted_at: string
  filled_at: string | null
  filled_price: number | null
}

interface ConditionOrder {
  id: string
  type: 'BREAKOUT_BUY' | 'STOP_LOSS' | 'TAKE_PROFIT' | 'TRAILING_STOP'
  symbol: string
  trigger_price: number
  order_quantity: number
  status?: string
}

// ─── 实盘/模拟盘模式 ──────────────────────────────────────────────────────────

const tradeMode = ref<'LIVE' | 'PAPER'>('PAPER')
const showLiveConfirm = ref(false)

function confirmSwitchLive() {
  if (tradeMode.value === 'LIVE') return
  showLiveConfirm.value = true
}

function doSwitchLive() {
  tradeMode.value = 'LIVE'
  showLiveConfirm.value = false
}

// ─── 选股池标的 ───────────────────────────────────────────────────────────────

const screenResults = ref<ScreenResult[]>([])
const poolLoading = ref(false)
const selectedSymbol = ref('')

async function fetchScreenResults() {
  poolLoading.value = true
  try {
    const res = await apiClient.get<ScreenResult[]>('/screen/results')
    screenResults.value = Array.isArray(res.data) ? res.data : []
  } catch {
    screenResults.value = []
  } finally {
    poolLoading.value = false
  }
}

function fillOrderFromPool(stock: ScreenResult) {
  selectedSymbol.value = stock.symbol
  order.symbol = stock.symbol
  order.direction = 'BUY'
  order.orderType = 'LIMIT'
  order.price = stock.ref_buy_price ?? stock.close ?? null
  order.stopLoss = stock.stop_loss ?? null
  order.takeProfit = stock.take_profit ?? null
  order.quantity = 100
  // 同步条件单代码
  condOrder.symbol = stock.symbol
  condOrder.trigger_price = stock.ref_buy_price ?? stock.close ?? 0
  // 切换到普通委托 tab
  orderTab.value = 'normal'
}

// ─── 普通委托表单 ─────────────────────────────────────────────────────────────

const orderTab = ref<'normal' | 'condition'>('normal')
const submitting = ref(false)
const orderMsg = ref('')
const orderMsgType = ref<'success' | 'error'>('success')

const order = reactive({
  symbol: '',
  direction: 'BUY' as 'BUY' | 'SELL',
  orderType: 'LIMIT' as 'LIMIT' | 'MARKET',
  price: null as number | null,
  quantity: 100,
  stopLoss: null as number | null,
  takeProfit: null as number | null,
})

function resetOrderForm() {
  order.symbol = ''
  order.direction = 'BUY'
  order.orderType = 'LIMIT'
  order.price = null
  order.quantity = 100
  order.stopLoss = null
  order.takeProfit = null
  selectedSymbol.value = ''
  orderMsg.value = ''
}

async function submitOrder() {
  if (!order.symbol.trim()) {
    orderMsg.value = '请输入股票代码'
    orderMsgType.value = 'error'
    return
  }
  if (order.orderType === 'LIMIT' && (!order.price || order.price <= 0)) {
    orderMsg.value = '请输入有效的委托价格'
    orderMsgType.value = 'error'
    return
  }
  if (!order.quantity || order.quantity < 100) {
    orderMsg.value = '委托数量不能少于 100 股'
    orderMsgType.value = 'error'
    return
  }

  submitting.value = true
  orderMsg.value = ''
  try {
    await apiClient.post('/trade/order', {
      symbol: order.symbol.trim().toUpperCase(),
      direction: order.direction,
      order_type: order.orderType,
      price: order.orderType === 'LIMIT' ? order.price : null,
      quantity: order.quantity,
      stop_loss: order.stopLoss || null,
      take_profit: order.takeProfit || null,
      mode: tradeMode.value,
    })
    orderMsg.value = '委托提交成功'
    orderMsgType.value = 'success'
    await fetchOrders()
    setTimeout(() => { orderMsg.value = '' }, 3000)
  } catch (e: unknown) {
    orderMsg.value = e instanceof Error ? e.message : '委托提交失败，请重试'
    orderMsgType.value = 'error'
  } finally {
    submitting.value = false
  }
}

// ─── 条件单表单 ───────────────────────────────────────────────────────────────

const condSubmitting = ref(false)
const condMsg = ref('')
const condMsgType = ref<'success' | 'error'>('success')

const condOrder = reactive<ConditionOrder>({
  id: '',
  type: 'BREAKOUT_BUY',
  symbol: '',
  trigger_price: 0,
  order_quantity: 100,
})

const condTypeDesc = computed(() => {
  const map: Record<string, string> = {
    BREAKOUT_BUY: '价格突破触发价时自动买入',
    STOP_LOSS: '价格跌破触发价时自动止损卖出',
    TAKE_PROFIT: '价格涨至触发价时自动止盈卖出',
    TRAILING_STOP: '从最高点回撤至触发价时自动卖出',
  }
  return map[condOrder.type] ?? ''
})

function resetCondForm() {
  condOrder.symbol = ''
  condOrder.type = 'BREAKOUT_BUY'
  condOrder.trigger_price = 0
  condOrder.order_quantity = 100
  condMsg.value = ''
}

async function submitCondOrder() {
  if (!condOrder.symbol.trim()) {
    condMsg.value = '请输入股票代码'
    condMsgType.value = 'error'
    return
  }
  if (!condOrder.trigger_price || condOrder.trigger_price <= 0) {
    condMsg.value = '请输入有效的触发价格'
    condMsgType.value = 'error'
    return
  }

  condSubmitting.value = true
  condMsg.value = ''
  try {
    await apiClient.post('/trade/conditions', {
      type: condOrder.type,
      symbol: condOrder.symbol.trim().toUpperCase(),
      trigger_price: condOrder.trigger_price,
      order_quantity: condOrder.order_quantity,
    })
    condMsg.value = '条件单创建成功'
    condMsgType.value = 'success'
    await fetchConditions()
    setTimeout(() => { condMsg.value = '' }, 3000)
  } catch (e: unknown) {
    condMsg.value = e instanceof Error ? e.message : '条件单创建失败，请重试'
    condMsgType.value = 'error'
  } finally {
    condSubmitting.value = false
  }
}

// ─── 委托/成交记录 ────────────────────────────────────────────────────────────

const recordTab = ref<'orders' | 'filled' | 'conditions'>('orders')
const ordersLoading = ref(false)
const orders = ref<TradeOrder[]>([])
const flowStart = ref(new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10))
const flowEnd = ref(new Date().toISOString().slice(0, 10))
const filterMode = ref('')

const filledOrders = computed(() =>
  orders.value.filter((o) => o.status === 'FILLED')
)

async function fetchOrders() {
  ordersLoading.value = true
  try {
    const params: Record<string, string> = {
      start: flowStart.value,
      end: flowEnd.value,
    }
    if (filterMode.value) params.mode = filterMode.value
    const res = await apiClient.get<TradeOrder[]>('/trade/orders', { params })
    orders.value = Array.isArray(res.data) ? res.data : []
  } catch {
    orders.value = []
  } finally {
    ordersLoading.value = false
  }
}

async function cancelOrder(id: string) {
  try {
    await apiClient.delete(`/trade/order/${id}`)
    await fetchOrders()
  } catch {
    /* handle error */
  }
}

// ─── 条件单列表 ───────────────────────────────────────────────────────────────

const conditionsLoading = ref(false)
const conditions = ref<ConditionOrder[]>([])

async function fetchConditions() {
  conditionsLoading.value = true
  try {
    const res = await apiClient.get<ConditionOrder[]>('/trade/conditions')
    conditions.value = Array.isArray(res.data) ? res.data : []
  } catch {
    conditions.value = []
  } finally {
    conditionsLoading.value = false
  }
}

async function deleteCondition(id: string) {
  try {
    await apiClient.delete(`/trade/conditions/${id}`)
    await fetchConditions()
  } catch {
    /* handle error */
  }
}

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

function orderTypeLabel(t: string) {
  const m: Record<string, string> = { LIMIT: '限价', MARKET: '市价', CONDITION: '条件单' }
  return m[t] ?? t
}

function statusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: '待成交', FILLED: '已成交', CANCELLED: '已撤单', REJECTED: '已拒绝',
  }
  return m[s] ?? s
}

function condTypeLabel(t: string) {
  const m: Record<string, string> = {
    BREAKOUT_BUY: '突破买入', STOP_LOSS: '止损卖出',
    TAKE_PROFIT: '止盈卖出', TRAILING_STOP: '移动止盈',
  }
  return m[t] ?? t
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

onMounted(() => {
  fetchScreenResults()
  fetchOrders()
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.trade-view { max-width: 1300px; }

/* ─── 只读提示 ───────────────────────────────────────────────────────────────── */
.readonly-notice {
  background: #1c2128; border: 1px solid #30363d; border-left: 4px solid #8b949e;
  color: #8b949e; padding: 12px 16px; border-radius: 6px; font-size: 14px;
}

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; color: #e6edf3; margin: 0; }

.main-layout { display: grid; grid-template-columns: 220px 1fr; gap: 16px; }

/* ─── 实盘/模拟盘切换 ────────────────────────────────────────────────────────── */
.mode-switch {
  display: flex; border: 1px solid #30363d; border-radius: 6px; overflow: hidden;
}
.mode-btn {
  padding: 6px 18px; background: transparent; border: none; color: #8b949e;
  cursor: pointer; font-size: 13px; transition: all 0.15s;
}
.mode-btn:hover { color: #e6edf3; background: #21262d; }
.active-paper { background: #1f6feb22; color: #58a6ff; }
.active-live { background: #f8514922; color: #f85149; }

.live-banner {
  background: #3a1a1a; border: 1px solid #f8514944; color: #f85149;
  padding: 8px 16px; border-radius: 6px; font-size: 13px; margin-bottom: 16px;
}

/* ─── 选股池面板 ─────────────────────────────────────────────────────────────── */
.stock-pool-panel {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 16px; height: fit-content; position: sticky; top: 16px;
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
}
.panel-header .section-title { margin: 0; }

.stock-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }

.stock-item {
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid transparent; transition: all 0.15s;
}
.stock-item:hover { background: #21262d; border-color: #30363d; }
.stock-item.selected { background: #1f6feb22; border-color: #58a6ff44; }
.stock-item:focus { outline: 2px solid #58a6ff; outline-offset: 1px; }

.stock-item-top { display: flex; justify-content: space-between; align-items: center; }
.stock-code { font-family: 'SF Mono', monospace; font-size: 13px; font-weight: 600; color: #e6edf3; }
.stock-change { font-size: 12px; font-weight: 600; }

.stock-item-bottom { display: flex; justify-content: space-between; margin-top: 2px; }
.stock-name { font-size: 12px; color: #8b949e; }
.stock-price { font-size: 12px; color: #e6edf3; font-family: 'SF Mono', monospace; }

.stock-hints { margin-top: 4px; }
.hint-tag {
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  background: #1f6feb22; color: #58a6ff; font-size: 11px;
}

.empty-pool { color: #484f58; font-size: 13px; text-align: center; padding: 16px 0; }

/* ─── 下单区域 ───────────────────────────────────────────────────────────────── */
.order-area { display: flex; flex-direction: column; gap: 16px; }

/* ─── 卡片 ─────────────────────────────────────────────────────────────────── */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }

.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.section-title { font-size: 16px; color: #e6edf3; margin: 0; }

/* ─── Tabs ──────────────────────────────────────────────────────────────────── */
.order-type-tabs, .record-tabs {
  display: flex; gap: 4px;
}
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.tab:hover:not(.active) { color: #e6edf3; }

/* ─── 表单 ─────────────────────────────────────────────────────────────────── */
.order-form { }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }

.direction-btns { display: flex; gap: 4px; }
.dir-btn {
  flex: 1; padding: 6px 0; border: 1px solid #30363d; border-radius: 6px;
  background: transparent; color: #8b949e; cursor: pointer; font-size: 14px; font-weight: 600;
}
.dir-btn.dir-buy.active { background: #f8514922; color: #f85149; border-color: #f85149; }
.dir-btn.dir-sell.active { background: #3fb95022; color: #3fb950; border-color: #3fb950; }
.dir-btn:hover:not(.active) { background: #21262d; color: #e6edf3; }

.market-price-hint {
  background: #0d1117; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 12px; border-radius: 6px; font-size: 14px;
}

.cond-type-desc { margin-top: 10px; }

.form-actions { display: flex; gap: 8px; margin-top: 16px; align-items: center; }

.order-msg { margin-top: 10px; font-size: 13px; padding: 6px 12px; border-radius: 6px; }
.order-msg.success { background: #1a3a2a; color: #3fb950; }
.order-msg.error { background: #3a1a1a; color: #f85149; }

/* ─── 输入控件 ──────────────────────────────────────────────────────────────── */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 6px 12px; border-radius: 6px; font-size: 14px;
}
.input:focus { outline: none; border-color: #58a6ff; }
.input-sm { padding: 5px 10px; font-size: 13px; }

/* ─── 按钮 ─────────────────────────────────────────────────────────────────── */
.btn {
  padding: 7px 18px; border-radius: 6px; cursor: pointer; font-size: 14px;
  border: none; display: inline-flex; align-items: center; gap: 6px;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #238636; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2ea043; }
.btn-buy { background: #f85149; color: #fff; }
.btn-buy:hover:not(:disabled) { background: #da3633; }
.btn-sell { background: #3fb950; color: #fff; }
.btn-sell:hover:not(:disabled) { background: #2ea043; }
.btn-outline { background: transparent; border: 1px solid #30363d; color: #8b949e; }
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-danger { background: #da3633; color: #fff; }
.btn-danger:hover { background: #f85149; }
.btn-sm { padding: 3px 10px; font-size: 12px; }
.submit-btn { min-width: 120px; justify-content: center; }

.btn-icon {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  width: 28px; height: 28px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 15px;
}
.btn-icon:hover { color: #e6edf3; border-color: #58a6ff; }
.btn-icon:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm.danger { background: none; border: 1px solid #30363d; color: #8b949e; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-sm.danger:hover { color: #f85149; border-color: #f85149; }

/* ─── 旋转图标 ──────────────────────────────────────────────────────────────── */
.refresh-icon { display: inline-block; }
.refresh-icon.spinning { animation: spin 1s linear infinite; }
.spinner {
  display: inline-block; width: 13px; height: 13px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 查询过滤行 ─────────────────────────────────────────────────────────────── */
.filter-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }

/* ─── 表格 ─────────────────────────────────────────────────────────────────── */
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; min-width: 600px; }
.data-table th, .data-table td {
  padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d;
  font-size: 13px; white-space: nowrap;
}
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; }
.empty { text-align: center; color: #484f58; padding: 24px; }
.text-muted { color: #484f58; }
.loading-text { color: #8b949e; font-size: 14px; padding: 16px 0; }

/* ─── 徽章 ─────────────────────────────────────────────────────────────────── */
.direction-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
}
.direction-badge.buy { background: rgba(248,81,73,0.15); color: #f85149; }
.direction-badge.sell { background: rgba(63,185,80,0.15); color: #3fb950; }

.mode-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
}
.mode-badge.live { background: #f8514922; color: #f85149; }
.mode-badge.paper { background: #58a6ff22; color: #58a6ff; }

.status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.status-pending { background: #d2992222; color: #d29922; }
.status-filled { background: #3fb95022; color: #3fb950; }
.status-cancelled { background: #484f5822; color: #484f58; }
.status-rejected { background: #f8514922; color: #f85149; }

/* A 股配色 */
.up { color: #f85149; }
.down { color: #3fb950; }

/* ─── 辅助 ─────────────────────────────────────────────────────────────────── */
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0;
  margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0;
}

/* ─── 确认对话框 ─────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal {
  background: #161b22; border: 1px solid #30363d; border-radius: 10px;
  padding: 24px; max-width: 400px; width: 90%;
}
.modal-title { font-size: 16px; color: #e6edf3; margin: 0 0 12px; }
.modal-body { font-size: 14px; color: #8b949e; margin: 0 0 20px; line-height: 1.6; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }

/* ─── 响应式 ─────────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .main-layout { grid-template-columns: 1fr; }
  .stock-pool-panel { position: static; }
}
</style>
