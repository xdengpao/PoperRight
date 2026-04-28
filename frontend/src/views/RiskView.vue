<template>
  <div class="risk-view">
    <h1 class="page-title">风险控制</h1>

    <!-- 大盘风控状态卡片 -->
    <section class="card" aria-label="大盘风控状态">
      <div class="section-header">
        <h2 class="section-title">大盘风控状态</h2>
        <button class="btn-icon" @click="fetchRiskOverview" :disabled="overviewLoading" aria-label="刷新风控状态">
          <span :class="['refresh-icon', overviewLoading && 'spinning']">↻</span>
        </button>
      </div>

      <div v-if="overviewLoading" class="loading-text">加载中...</div>
      <div v-else-if="riskOverview" class="risk-overview">
        <!-- 风控级别徽章 -->
        <div class="risk-level-badge" :class="riskLevelClass">
          <span class="risk-level-dot"></span>
          <span class="risk-level-text">{{ riskLevelLabel }}</span>
        </div>

        <!-- 指数均线关系（需求 9：展示所有监控指数） -->
        <div class="ma-grid" v-if="riskOverview.indices && riskOverview.indices.length">
          <div class="ma-item" v-for="idx in riskOverview.indices" :key="idx.index_code">
            <span class="ma-index-name">{{ idx.index_name }}</span>
            <div class="ma-row">
              <span class="ma-label">MA20</span>
              <span class="ma-status" :class="idx.above_ma20 ? 'above' : 'below'">
                {{ idx.above_ma20 ? '站上' : '跌破' }}
              </span>
            </div>
            <div class="ma-row">
              <span class="ma-label">MA60</span>
              <span class="ma-status" :class="idx.above_ma60 ? 'above' : 'below'">
                {{ idx.above_ma60 ? '站上' : '跌破' }}
              </span>
            </div>
            <div class="ma-row">
              <span class="ma-label">风险</span>
              <span class="ma-status" :class="indexRiskClass(idx.risk_level)">
                {{ indexRiskLabel(idx.risk_level) }}
              </span>
            </div>
          </div>
          <div class="ma-item threshold-item">
            <span class="ma-label">当前趋势阈值</span>
            <span class="threshold-value">{{ riskOverview.current_threshold }}</span>
          </div>
        </div>
        <!-- 向后兼容：无 indices 时使用旧字段 -->
        <div class="ma-grid" v-else>
          <div class="ma-item">
            <span class="ma-label">上证 / MA20</span>
            <span class="ma-status" :class="riskOverview.sh_above_ma20 ? 'above' : 'below'">
              {{ riskOverview.sh_above_ma20 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item">
            <span class="ma-label">上证 / MA60</span>
            <span class="ma-status" :class="riskOverview.sh_above_ma60 ? 'above' : 'below'">
              {{ riskOverview.sh_above_ma60 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item">
            <span class="ma-label">创业板 / MA20</span>
            <span class="ma-status" :class="riskOverview.cyb_above_ma20 ? 'above' : 'below'">
              {{ riskOverview.cyb_above_ma20 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item">
            <span class="ma-label">创业板 / MA60</span>
            <span class="ma-status" :class="riskOverview.cyb_above_ma60 ? 'above' : 'below'">
              {{ riskOverview.cyb_above_ma60 ? '站上' : '跌破' }}
            </span>
          </div>
          <div class="ma-item threshold-item">
            <span class="ma-label">当前趋势阈值</span>
            <span class="threshold-value">{{ riskOverview.current_threshold }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无风控数据</div>

      <!-- 指数 K 线迷你图（需求 11） -->
      <div class="kline-mini-charts" v-if="riskOverview">
        <h3 class="kline-section-title">指数 K 线走势</h3>
        <div class="kline-chart-grid">
          <div class="kline-chart-item" v-for="idx in klineIndices" :key="idx.symbol">
            <span class="kline-chart-label">{{ idx.name }}</span>
            <div v-if="klineLoading[idx.symbol]" class="kline-chart-placeholder">加载中...</div>
            <div v-else-if="!klineData[idx.symbol]?.length" class="kline-chart-placeholder">暂无数据</div>
            <v-chart
              v-else
              :option="buildKlineOption(idx.symbol)"
              :autoresize="true"
              class="kline-mini-chart"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- 总仓位状态（需求 5） -->
    <section class="card" aria-label="总仓位状态">
      <div class="section-header">
        <h2 class="section-title">总仓位状态</h2>
        <button class="btn-icon" @click="fetchTotalPosition" :disabled="totalPosLoading" aria-label="刷新总仓位">
          <span :class="['refresh-icon', totalPosLoading && 'spinning']">↻</span>
        </button>
      </div>

      <div v-if="totalPosLoading" class="loading-text">加载中...</div>
      <div v-else-if="totalPosition" class="total-position-area">
        <!-- 仓位比例进度条 -->
        <div class="position-progress">
          <div class="progress-header">
            <span class="progress-label">当前仓位</span>
            <span class="progress-value" :class="totalPositionStatus">
              {{ totalPosition.total_position_pct.toFixed(1) }}%
            </span>
          </div>
          <div class="progress-bar-bg" role="progressbar"
            :aria-valuenow="totalPosition.total_position_pct"
            aria-valuemin="0" aria-valuemax="100"
            :aria-label="`总仓位 ${totalPosition.total_position_pct.toFixed(1)}%`"
          >
            <div
              class="progress-bar-fill"
              :class="totalPositionStatus"
              :style="{ width: Math.min(totalPosition.total_position_pct, 100) + '%' }"
            ></div>
            <div
              class="progress-bar-limit"
              :style="{ left: totalPosition.position_limit_pct + '%' }"
              :title="`仓位上限 ${totalPosition.position_limit_pct}%`"
            ></div>
          </div>
          <div class="progress-footer">
            <span class="limit-label">上限 {{ totalPosition.position_limit_pct }}%（{{ totalPositionRiskLabel }}）</span>
          </div>
        </div>

        <!-- 数值详情 -->
        <div class="position-details">
          <div class="detail-item">
            <span class="detail-label">持仓总市值</span>
            <span class="detail-value">¥{{ formatMoney(totalPosition.total_market_value) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">可用现金</span>
            <span class="detail-value">¥{{ formatMoney(totalPosition.available_cash) }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">仓位上限</span>
            <span class="detail-value">{{ totalPosition.position_limit_pct }}%</span>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无仓位数据</div>
    </section>

    <!-- 止损止盈参数配置 -->
    <section class="card" aria-label="止损止盈参数配置">
      <h2 class="section-title">止损止盈参数</h2>

      <!-- 止损模式切换 -->
      <div class="mode-switch">
        <label class="mode-label">止损模式</label>
        <div class="mode-tabs">
          <button
            :class="['tab', stopConfig.mode === 'fixed' && 'active']"
            @click="stopConfig.mode = 'fixed'"
          >固定比例</button>
          <button
            :class="['tab', stopConfig.mode === 'atr_adaptive' && 'active']"
            @click="stopConfig.mode = 'atr_adaptive'"
          >ATR 自适应</button>
        </div>
      </div>

      <div class="config-grid">
        <!-- 固定比例模式参数 -->
        <template v-if="stopConfig.mode === 'fixed'">
          <div class="config-item">
            <label for="fixed-stop-loss">固定止损比例 (%)</label>
            <input
              id="fixed-stop-loss"
              v-model.number="stopConfig.fixed_stop_loss"
              type="number"
              min="1"
              max="50"
              step="0.5"
              class="input"
            />
            <span class="hint">触发固定止损的亏损比例</span>
          </div>
          <div class="config-item">
            <label for="trailing-stop">移动止损回撤比例 (%)</label>
            <input
              id="trailing-stop"
              v-model.number="stopConfig.trailing_stop"
              type="number"
              min="1"
              max="30"
              step="0.5"
              class="input"
            />
            <span class="hint">从最高点回撤触发移动止损</span>
          </div>
        </template>

        <!-- ATR 自适应模式参数 -->
        <template v-if="stopConfig.mode === 'atr_adaptive'">
          <div class="config-item">
            <label for="atr-fixed-multiplier">ATR 固定止损倍数</label>
            <input
              id="atr-fixed-multiplier"
              v-model.number="stopConfig.atr_fixed_multiplier"
              type="number"
              min="0.5"
              max="10"
              step="0.1"
              class="input"
            />
            <span class="hint">止损价 = 成本价 - ATR × 倍数</span>
          </div>
          <div class="config-item">
            <label for="atr-trailing-multiplier">ATR 移动止损倍数</label>
            <input
              id="atr-trailing-multiplier"
              v-model.number="stopConfig.atr_trailing_multiplier"
              type="number"
              min="0.5"
              max="10"
              step="0.1"
              class="input"
            />
            <span class="hint">回撤幅度 = ATR × 倍数 / 最高价</span>
          </div>
        </template>

        <div class="config-item">
          <label for="trend-stop-ma">趋势止损均线周期</label>
          <select id="trend-stop-ma" v-model.number="stopConfig.trend_stop_ma" class="input">
            <option :value="5">5 日均线</option>
            <option :value="10">10 日均线</option>
            <option :value="20">20 日均线</option>
            <option :value="60">60 日均线</option>
          </select>
          <span class="hint">收盘价跌破该均线触发趋势止损</span>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn save-btn" @click="saveStopConfig" :disabled="stopConfigSaving">
          {{ stopConfigSaving ? '保存中...' : '保存止损止盈配置' }}
        </button>
        <span v-if="stopConfigMsg" class="save-msg" :class="stopConfigMsgType">{{ stopConfigMsg }}</span>
      </div>
    </section>

    <!-- 黑白名单管理 -->
    <section class="card" aria-label="黑白名单管理">
      <h2 class="section-title">黑白名单管理</h2>
      <div class="list-tabs">
        <button
          :class="['tab', activeList === 'BLACK' && 'active']"
          @click="switchList('BLACK')"
        >黑名单</button>
        <button
          :class="['tab', activeList === 'WHITE' && 'active']"
          @click="switchList('WHITE')"
        >白名单</button>
      </div>

      <div class="add-row">
        <label :for="`add-symbol-${activeList}`" class="sr-only">添加股票代码</label>
        <input
          :id="`add-symbol-${activeList}`"
          v-model="newSymbol"
          class="input"
          placeholder="股票代码，如 000001.SZ"
          @keyup.enter="addToList"
        />
        <label for="add-reason" class="sr-only">原因</label>
        <input
          id="add-reason"
          v-model="newReason"
          class="input"
          placeholder="原因（可选）"
          @keyup.enter="addToList"
        />
        <button class="btn" @click="addToList" :disabled="listLoading">添加</button>
      </div>

      <div v-if="listLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" :aria-label="activeList === 'BLACK' ? '黑名单列表' : '白名单列表'">
        <thead>
          <tr>
            <th scope="col">股票代码</th>
            <th scope="col">原因</th>
            <th scope="col">添加时间</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in currentList" :key="item.symbol">
            <td class="mono">{{ item.symbol }}</td>
            <td>{{ item.reason || '—' }}</td>
            <td>{{ item.created_at?.slice(0, 10) ?? '—' }}</td>
            <td>
              <button class="btn-sm danger" @click="removeFromList(item.symbol)">移除</button>
            </td>
          </tr>
          <tr v-if="currentList.length === 0">
            <td colspan="4" class="empty">暂无数据</td>
          </tr>
        </tbody>
      </table>

      <div v-if="listTotal > currentList.length" class="pagination-hint">
        共 {{ listTotal }} 条，当前显示 {{ currentList.length }} 条
      </div>
    </section>

    <!-- 仓位风控预警 -->
    <section class="card" aria-label="仓位风控预警">
      <div class="section-header">
        <h2 class="section-title">仓位风控预警</h2>
        <div class="header-actions">
          <span v-if="wsStatus !== 'hidden'" class="ws-status" :class="wsStatus">
            {{ wsStatusLabel }}
          </span>
          <button class="btn-icon" @click="fetchPositionWarnings" aria-label="刷新预警">
            <span class="refresh-icon">↻</span>
          </button>
        </div>
      </div>

      <div v-if="warningsLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" aria-label="仓位风控预警列表">
        <thead>
          <tr>
            <th scope="col">股票代码</th>
            <th scope="col">预警类型</th>
            <th scope="col">成本价</th>
            <th scope="col">当前值</th>
            <th scope="col">阈值</th>
            <th scope="col">盈亏</th>
            <th scope="col">建议操作</th>
            <th scope="col">时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(w, i) in positionWarnings"
            :key="`${w.symbol}-${w.type}-${i}`"
            :class="['warning-row', w.level, w._flash && 'flash']"
          >
            <td class="mono">{{ w.symbol }}</td>
            <td>
              <span class="warning-badge" :class="[w.level, breakdownClass(w.type)]">{{ w.type }}</span>
            </td>
            <td>{{ w.cost_price != null ? w.cost_price.toFixed(2) : '—' }}</td>
            <td>{{ w.current_value }}</td>
            <td>{{ w.threshold }}</td>
            <td>
              <span
                v-if="w.pnl_pct != null"
                :class="w.pnl_pct >= 0 ? 'pnl-profit' : 'pnl-loss'"
              >
                {{ w.pnl_pct >= 0 ? '+' : '' }}{{ w.pnl_pct.toFixed(2) }}%
              </span>
              <span v-else>—</span>
            </td>
            <td>
              <span
                v-if="w.suggested_action"
                class="action-tag"
                :class="suggestedActionClass(w.suggested_action)"
              >
                {{ w.suggested_action }}
              </span>
              <span v-else>—</span>
            </td>
            <td>{{ w.time?.slice(0, 16) ?? '—' }}</td>
          </tr>
          <tr v-if="positionWarnings.length === 0">
            <td colspan="8" class="empty">暂无风控预警</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 策略健康状态（需求 8） -->
    <section class="card" aria-label="策略健康状态">
      <div class="section-header">
        <h2 class="section-title">策略健康状态</h2>
        <button class="btn-icon" @click="fetchStrategyHealth" :disabled="healthLoading" aria-label="刷新策略健康">
          <span :class="['refresh-icon', healthLoading && 'spinning']">↻</span>
        </button>
      </div>

      <div v-if="healthLoading" class="loading-text">加载中...</div>
      <div v-else-if="strategyHealth" class="health-columns">
        <!-- 回测表现 -->
        <div class="health-column">
          <h3 class="health-column-title">回测表现</h3>
          <div class="health-metrics">
            <div class="health-metric">
              <span class="health-label">胜率</span>
              <span class="health-value">{{ formatPct(strategyHealth.win_rate) }}</span>
            </div>
            <div class="health-metric">
              <span class="health-label">最大回撤</span>
              <span class="health-value">{{ formatPct(strategyHealth.max_drawdown) }}</span>
            </div>
            <div class="health-metric">
              <span class="health-label">状态</span>
              <span class="health-status" :class="strategyHealth.is_healthy ? 'healthy' : 'unhealthy'">
                {{ strategyHealth.is_healthy ? '健康' : '不健康' }}
              </span>
            </div>
          </div>
        </div>

        <!-- 实盘表现 -->
        <div class="health-column">
          <h3 class="health-column-title">实盘表现</h3>
          <div class="health-metrics">
            <div class="health-metric">
              <span class="health-label">胜率</span>
              <span class="health-value">{{ formatPct(strategyHealth.live_win_rate) }}</span>
            </div>
            <div class="health-metric">
              <span class="health-label">最大回撤</span>
              <span class="health-value">{{ formatPct(strategyHealth.live_max_drawdown) }}</span>
            </div>
            <div class="health-metric">
              <span class="health-label">状态</span>
              <span
                v-if="strategyHealth.live_is_healthy != null"
                class="health-status"
                :class="strategyHealth.live_is_healthy ? 'healthy' : 'unhealthy'"
              >
                {{ strategyHealth.live_is_healthy ? '健康' : '不健康' }}
              </span>
              <span v-else class="health-status na">—</span>
            </div>
            <div v-if="strategyHealth.live_data_sufficient === false" class="health-note">
              实盘数据不足，仅供参考
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无策略健康数据</div>

      <!-- 预警信息 -->
      <div v-if="strategyHealth?.warnings?.length" class="health-warnings">
        <div v-for="(w, i) in strategyHealth.warnings" :key="i" class="health-warning-item">
          ⚠ {{ w }}
        </div>
      </div>
    </section>

    <!-- 风控日志（需求 10） -->
    <section class="card" aria-label="风控日志">
      <div class="section-header">
        <h2 class="section-title">风控日志</h2>
        <button class="btn-icon" @click="fetchEventLog" :disabled="eventLogLoading" aria-label="刷新风控日志">
          <span :class="['refresh-icon', eventLogLoading && 'spinning']">↻</span>
        </button>
      </div>

      <!-- 筛选条件 -->
      <div class="event-log-filters">
        <div class="filter-item">
          <label for="event-log-start">起始日期</label>
          <input id="event-log-start" v-model="eventLogStartDate" type="date" class="input" />
        </div>
        <div class="filter-item">
          <label for="event-log-end">结束日期</label>
          <input id="event-log-end" v-model="eventLogEndDate" type="date" class="input" />
        </div>
        <button class="btn" @click="fetchEventLog" :disabled="eventLogLoading">查询</button>
      </div>

      <div v-if="eventLogLoading" class="loading-text">加载中...</div>
      <table v-else class="data-table" aria-label="风控事件日志列表">
        <thead>
          <tr>
            <th scope="col">时间</th>
            <th scope="col">事件类型</th>
            <th scope="col">股票代码</th>
            <th scope="col">规则名称</th>
            <th scope="col">结果</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in eventLogItems" :key="item.id">
            <td>{{ item.triggered_at?.slice(0, 16) ?? '—' }}</td>
            <td>
              <span class="event-type-badge" :class="eventTypeBadgeClass(item.event_type)">
                {{ eventTypeLabel(item.event_type) }}
              </span>
            </td>
            <td class="mono">{{ item.symbol || '—' }}</td>
            <td>{{ item.rule_name }}</td>
            <td>
              <span class="result-badge" :class="item.result === 'REJECTED' ? 'rejected' : 'warned'">
                {{ item.result === 'REJECTED' ? '拒绝' : '预警' }}
              </span>
            </td>
          </tr>
          <tr v-if="eventLogItems.length === 0">
            <td colspan="5" class="empty">暂无风控日志</td>
          </tr>
        </tbody>
      </table>

      <div v-if="eventLogTotal > eventLogItems.length" class="pagination-hint">
        共 {{ eventLogTotal }} 条，当前显示 {{ eventLogItems.length }} 条
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiClient } from '@/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([CandlestickChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer])

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

/** 单个监控指数的风控状态（需求 9） */
interface IndexRiskItem {
  index_code: string
  index_name: string
  above_ma20: boolean
  above_ma60: boolean
  risk_level: string
}

interface RiskOverview {
  market_risk_level: 'NORMAL' | 'ELEVATED' | 'SUSPENDED'
  sh_above_ma20: boolean
  sh_above_ma60: boolean
  cyb_above_ma20: boolean
  cyb_above_ma60: boolean
  current_threshold: number
  indices?: IndexRiskItem[]
}

interface StopConfig {
  mode: 'fixed' | 'atr_adaptive'
  fixed_stop_loss: number
  trailing_stop: number
  trend_stop_ma: number
  atr_fixed_multiplier: number
  atr_trailing_multiplier: number
}

interface ListItem {
  symbol: string
  reason: string
  created_at: string
}

interface PositionWarning {
  symbol: string
  type: string
  level: 'danger' | 'warning' | 'info'
  current_value: string
  threshold: string
  time: string
  cost_price?: number | null
  current_price?: number | null
  pnl_pct?: number | null
  suggested_action?: string | null
  _flash?: boolean
}

/** 止损预警 WebSocket 消息 */
interface RiskAlertMessage {
  type: 'risk:alert'
  symbol: string
  alert_type: string
  current_price: number
  trigger_threshold: number
  alert_level: 'danger' | 'warning'
  trigger_time: string
}

/** 总仓位状态 */
interface TotalPosition {
  total_position_pct: number
  total_market_value: number
  available_cash: number
  position_limit_pct: number
  market_risk_level: string
}

/** 策略健康状态（需求 8） */
interface StrategyHealth {
  strategy_id: string | null
  win_rate: number
  max_drawdown: number
  is_healthy: boolean
  warnings: string[]
  live_win_rate: number | null
  live_max_drawdown: number | null
  live_is_healthy: boolean | null
  live_data_sufficient: boolean | null
}

// ─── 大盘风控状态 ─────────────────────────────────────────────────────────────

const riskOverview = ref<RiskOverview | null>(null)
const overviewLoading = ref(false)

const riskLevelClass = computed(() => {
  const level = riskOverview.value?.market_risk_level
  if (level === 'SUSPENDED') return 'level-suspended'
  if (level === 'ELEVATED') return 'level-elevated'
  return 'level-normal'
})

const riskLevelLabel = computed(() => {
  const level = riskOverview.value?.market_risk_level
  if (level === 'SUSPENDED') return '暂停交易'
  if (level === 'ELEVATED') return '风险提升'
  return '正常'
})

async function fetchRiskOverview() {
  overviewLoading.value = true
  try {
    const res = await apiClient.get<RiskOverview>('/risk/overview')
    riskOverview.value = res.data
  } catch {
    // API 暂不可用时使用默认值
    riskOverview.value = {
      market_risk_level: 'NORMAL',
      sh_above_ma20: true,
      sh_above_ma60: true,
      cyb_above_ma20: false,
      cyb_above_ma60: false,
      current_threshold: 60,
      indices: [],
    }
  } finally {
    overviewLoading.value = false
  }
}

/** 根据指数风险等级返回 CSS 类名（需求 9） */
function indexRiskClass(level: string): string {
  if (level === 'DANGER') return 'below'
  if (level === 'CAUTION') return 'caution'
  return 'above'
}

/** 根据指数风险等级返回中文标签（需求 9） */
function indexRiskLabel(level: string): string {
  if (level === 'DANGER') return '危险'
  if (level === 'CAUTION') return '警戒'
  return '正常'
}

// ─── 指数 K 线迷你图（需求 11）─────────────────────────────────────────────

/** 指数 K 线数据条目 */
interface IndexKlineItem {
  time: string
  open: number
  high: number
  low: number
  close: number
  ma20: number | null
  ma60: number | null
}

/** 监控指数列表 */
const klineIndices = [
  { symbol: '000001.SH', name: '上证指数' },
  { symbol: '399006.SZ', name: '创业板指' },
]

const klineData = ref<Record<string, IndexKlineItem[]>>({})
const klineLoading = ref<Record<string, boolean>>({})

async function fetchIndexKline(symbol: string) {
  klineLoading.value[symbol] = true
  try {
    const res = await apiClient.get<IndexKlineItem[]>('/risk/index-kline', { params: { symbol } })
    klineData.value[symbol] = res.data
  } catch {
    klineData.value[symbol] = []
  } finally {
    klineLoading.value[symbol] = false
  }
}

async function fetchAllIndexKlines() {
  await Promise.all(klineIndices.map(idx => fetchIndexKline(idx.symbol)))
}

/** 构建 ECharts K 线迷你图配置（需求 11.2 + 11.3） */
function buildKlineOption(symbol: string) {
  const data = klineData.value[symbol] || []
  if (!data.length) return {}

  // 日期标签
  const dates = data.map(d => d.time.slice(0, 10))
  // OHLC 数据：[open, close, low, high]（ECharts candlestick 格式）
  const ohlc = data.map(d => [d.open, d.close, d.low, d.high])
  // MA20 数据
  const ma20Data = data.map(d => d.ma20)
  // MA60 数据
  const ma60Data = data.map(d => d.ma60)

  // MA20 颜色：站上（close >= ma20）为绿色，跌破为红色
  const ma20Colors = data.map(d => {
    if (d.ma20 == null) return '#3fb950'
    return d.close >= d.ma20 ? '#3fb950' : '#f85149'
  })

  // 构建 MA20 分段线数据（按颜色分段）
  const ma20Pieces: Array<{ gt: number; lte: number; color: string }> = []
  if (data.length > 1) {
    let segStart = 0
    let segColor = ma20Colors[0]
    for (let i = 1; i < data.length; i++) {
      if (ma20Colors[i] !== segColor || i === data.length - 1) {
        const endIdx = i === data.length - 1 && ma20Colors[i] === segColor ? i : i - 1
        ma20Pieces.push({ gt: segStart - 1, lte: endIdx, color: segColor })
        if (i === data.length - 1 && ma20Colors[i] !== segColor) {
          ma20Pieces.push({ gt: endIdx, lte: i, color: ma20Colors[i] })
        }
        segStart = i
        segColor = ma20Colors[i]
      }
    }
    // 确保最后一段被添加
    if (!ma20Pieces.length || ma20Pieces[ma20Pieces.length - 1].lte < data.length - 1) {
      ma20Pieces.push({ gt: segStart - 1, lte: data.length - 1, color: segColor })
    }
  }

  return {
    animation: false,
    grid: {
      left: 8,
      right: 8,
      top: 8,
      bottom: 24,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#161b22',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
      formatter: (params: Array<{ dataIndex: number }>) => {
        if (!params.length) return ''
        const idx = params[0].dataIndex
        const item = data[idx]
        if (!item) return ''
        return [
          `<b>${item.time.slice(0, 10)}</b>`,
          `开: ${item.open.toFixed(2)}`,
          `高: ${item.high.toFixed(2)}`,
          `低: ${item.low.toFixed(2)}`,
          `收: ${item.close.toFixed(2)}`,
          item.ma20 != null ? `MA20: ${item.ma20.toFixed(2)}` : '',
          item.ma60 != null ? `MA60: ${item.ma60.toFixed(2)}` : '',
        ].filter(Boolean).join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { show: true, fontSize: 10, color: '#484f58', interval: 'auto' },
      axisLine: { lineStyle: { color: '#21262d' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { show: true, fontSize: 10, color: '#484f58' },
      splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
      axisLine: { show: false },
    },
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#f85149',       // 阳线填充（收 > 开）
          color0: '#3fb950',      // 阴线填充（收 < 开）
          borderColor: '#f85149', // 阳线边框
          borderColor0: '#3fb950', // 阴线边框
        },
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20Data,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5 },
        // 使用 visualMap 实现分段颜色
        ...(ma20Pieces.length > 0
          ? {}
          : { lineStyle: { width: 1.5, color: '#3fb950' } }),
      },
      {
        name: 'MA60',
        type: 'line',
        data: ma60Data,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#58a6ff' },
      },
    ],
    // MA20 分段着色
    ...(ma20Pieces.length > 0
      ? {
          visualMap: {
            show: false,
            seriesIndex: 1,
            dimension: 0,
            pieces: ma20Pieces,
          },
        }
      : {}),
  }
}

// ─── 总仓位状态（需求 5）─────────────────────────────────────────────────────

const totalPosition = ref<TotalPosition | null>(null)
const totalPosLoading = ref(false)

const totalPositionStatus = computed(() => {
  if (!totalPosition.value) return 'safe'
  const pct = totalPosition.value.total_position_pct
  const limit = totalPosition.value.position_limit_pct
  if (pct > limit) return 'over-limit'
  if (pct > limit * 0.8) return 'near-limit'
  return 'safe'
})

const totalPositionRiskLabel = computed(() => {
  const level = totalPosition.value?.market_risk_level
  if (level === 'DANGER') return '危险'
  if (level === 'CAUTION') return '警戒'
  return '正常'
})

function formatMoney(value: number): string {
  if (value >= 10000) {
    return (value / 10000).toFixed(2) + '万'
  }
  return value.toFixed(2)
}

/** 根据预警类型返回破位预警 CSS 类名 */
function breakdownClass(type: string): string {
  if (type === '急跌破位预警') return 'breakdown-rapid'
  if (type === '阴跌破位预警') return 'breakdown-gradual'
  return ''
}

/** 根据建议操作返回标签 CSS 类名（需求 12） */
function suggestedActionClass(action: string): string {
  if (action === '建议止损卖出') return 'action-sell'
  if (action === '建议减仓') return 'action-reduce'
  if (action === '建议关注，考虑减仓') return 'action-watch'
  if (action === '建议不再加仓') return 'action-hold'
  return 'action-default'
}

async function fetchTotalPosition() {
  totalPosLoading.value = true
  try {
    const res = await apiClient.get<TotalPosition>('/risk/total-position')
    totalPosition.value = res.data
  } catch {
    totalPosition.value = null
  } finally {
    totalPosLoading.value = false
  }
}

// ─── 止损止盈配置 ─────────────────────────────────────────────────────────────

const stopConfig = reactive<StopConfig>({
  mode: 'fixed',
  fixed_stop_loss: 8,
  trailing_stop: 5,
  trend_stop_ma: 20,
  atr_fixed_multiplier: 2.0,
  atr_trailing_multiplier: 1.5,
})

const stopConfigSaving = ref(false)
const stopConfigMsg = ref('')
const stopConfigMsgType = ref<'success' | 'error'>('success')

async function saveStopConfig() {
  stopConfigSaving.value = true
  stopConfigMsg.value = ''
  try {
    await apiClient.post('/risk/stop-config', stopConfig)
    stopConfigMsg.value = '保存成功'
    stopConfigMsgType.value = 'success'
  } catch {
    stopConfigMsg.value = '保存失败，请重试'
    stopConfigMsgType.value = 'error'
  } finally {
    stopConfigSaving.value = false
    setTimeout(() => { stopConfigMsg.value = '' }, 3000)
  }
}

// ─── 黑白名单管理 ─────────────────────────────────────────────────────────────

const activeList = ref<'BLACK' | 'WHITE'>('BLACK')
const blacklist = ref<ListItem[]>([])
const whitelist = ref<ListItem[]>([])
const listLoading = ref(false)
const listTotal = ref(0)
const newSymbol = ref('')
const newReason = ref('')

const currentList = computed(() =>
  activeList.value === 'BLACK' ? blacklist.value : whitelist.value
)

async function fetchLists() {
  listLoading.value = true
  try {
    const [bRes, wRes] = await Promise.all([
      apiClient.get<{ items: ListItem[]; total: number }>('/blacklist'),
      apiClient.get<{ items: ListItem[]; total: number }>('/whitelist'),
    ])
    // 兼容数组和分页对象两种响应格式
    blacklist.value = Array.isArray(bRes.data) ? bRes.data : (bRes.data.items ?? [])
    whitelist.value = Array.isArray(wRes.data) ? wRes.data : (wRes.data.items ?? [])
    listTotal.value = Array.isArray(bRes.data) ? bRes.data.length : (bRes.data.total ?? 0)
  } catch {
    /* API 暂不可用 */
  } finally {
    listLoading.value = false
  }
}

function switchList(type: 'BLACK' | 'WHITE') {
  activeList.value = type
  listTotal.value = currentList.value.length
}

async function addToList() {
  const sym = newSymbol.value.trim().toUpperCase()
  if (!sym) return
  const endpoint = activeList.value === 'BLACK' ? '/blacklist' : '/whitelist'
  try {
    await apiClient.post(endpoint, { symbol: sym, reason: newReason.value || null })
    newSymbol.value = ''
    newReason.value = ''
    await fetchLists()
  } catch {
    /* handle error */
  }
}

async function removeFromList(symbol: string) {
  const endpoint = activeList.value === 'BLACK' ? '/blacklist' : '/whitelist'
  try {
    await apiClient.delete(`${endpoint}/${symbol}`)
    await fetchLists()
  } catch {
    /* handle error */
  }
}

// ─── 仓位风控预警 ─────────────────────────────────────────────────────────────

const positionWarnings = ref<PositionWarning[]>([])
const warningsLoading = ref(false)

async function fetchPositionWarnings() {
  warningsLoading.value = true
  try {
    const res = await apiClient.get<PositionWarning[]>('/risk/position-warnings')
    positionWarnings.value = res.data
  } catch {
    positionWarnings.value = []
  } finally {
    warningsLoading.value = false
  }
}

// ─── 止损预警 WebSocket 实时推送（需求 2）─────────────────────────────────────

const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000/api/v1/ws'
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000] // 指数退避

let riskWs: WebSocket | null = null
let reconnectAttempts = 0
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let manualClose = false

const wsStatus = ref<'connected' | 'connecting' | 'disconnected' | 'hidden'>('hidden')

const wsStatusLabel = computed(() => {
  if (wsStatus.value === 'connected') return '实时连接'
  if (wsStatus.value === 'connecting') return '连接中...'
  if (wsStatus.value === 'disconnected') return '连接断开'
  return ''
})

function connectRiskWebSocket() {
  const token = localStorage.getItem('access_token')
  if (!token) return

  // 从 token 中解析 user_id（JWT payload.sub）
  let userId: string
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    userId = payload.sub
    if (!userId) return
  } catch {
    return
  }

  manualClose = false
  wsStatus.value = 'connecting'

  const url = `${WS_BASE}/${userId}?token=${encodeURIComponent(token)}`
  try {
    riskWs = new WebSocket(url)
  } catch {
    scheduleReconnect()
    return
  }

  riskWs.onopen = () => {
    reconnectAttempts = 0
    wsStatus.value = 'connected'
  }

  riskWs.onmessage = (event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data as string)
      if (msg.type === 'risk:alert') {
        handleRiskAlert(msg as RiskAlertMessage)
      }
    } catch {
      // 忽略非 JSON 消息
    }
  }

  riskWs.onclose = () => {
    riskWs = null
    if (!manualClose) {
      wsStatus.value = 'disconnected'
      scheduleReconnect()
    }
  }

  riskWs.onerror = () => {
    // onerror 后会触发 onclose，由 onclose 处理重连
  }
}

function scheduleReconnect() {
  if (manualClose || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return

  const delay = RECONNECT_DELAYS[reconnectAttempts] ?? RECONNECT_DELAYS[RECONNECT_DELAYS.length - 1]
  reconnectAttempts++
  wsStatus.value = 'connecting'

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connectRiskWebSocket()
  }, delay)
}

function disconnectRiskWebSocket() {
  manualClose = true
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  reconnectAttempts = 0
  if (riskWs) {
    riskWs.close()
    riskWs = null
  }
  wsStatus.value = 'hidden'
}

function handleRiskAlert(msg: RiskAlertMessage) {
  // 在预警表格顶部插入新行并添加闪烁动画
  const newWarning: PositionWarning = {
    symbol: msg.symbol,
    type: msg.alert_type,
    level: msg.alert_level,
    current_value: `价格 ${msg.current_price.toFixed(2)}`,
    threshold: `${msg.trigger_threshold}`,
    time: msg.trigger_time,
    _flash: true,
  }
  positionWarnings.value.unshift(newWarning)

  // 3 秒后移除闪烁动画
  setTimeout(() => {
    newWarning._flash = false
  }, 3000)
}

// ─── 策略健康状态（需求 8）─────────────────────────────────────────────────

const strategyHealth = ref<StrategyHealth | null>(null)
const healthLoading = ref(false)

/** 格式化百分比显示 */
function formatPct(value: number | null | undefined): string {
  if (value == null) return '—'
  return (value * 100).toFixed(1) + '%'
}

async function fetchStrategyHealth() {
  healthLoading.value = true
  try {
    const res = await apiClient.get<StrategyHealth>('/risk/strategy-health')
    strategyHealth.value = res.data
  } catch {
    strategyHealth.value = null
  } finally {
    healthLoading.value = false
  }
}

// ─── 风控事件日志（需求 10）─────────────────────────────────────────────────

interface EventLogItem {
  id: string
  user_id: string
  event_type: string
  symbol: string | null
  rule_name: string
  trigger_value: number
  threshold: number
  result: string
  triggered_at: string
  created_at: string
}

const eventLogItems = ref<EventLogItem[]>([])
const eventLogTotal = ref(0)
const eventLogLoading = ref(false)
const eventLogStartDate = ref('')
const eventLogEndDate = ref('')

function eventTypeLabel(type: string): string {
  const map: Record<string, string> = {
    ORDER_REJECTED: '委托拒绝',
    STOP_LOSS: '止损预警',
    POSITION_LIMIT: '仓位超限',
    BREAKDOWN: '破位预警',
  }
  return map[type] || type
}

function eventTypeBadgeClass(type: string): string {
  if (type === 'ORDER_REJECTED') return 'badge-rejected'
  if (type === 'STOP_LOSS') return 'badge-stop-loss'
  if (type === 'POSITION_LIMIT') return 'badge-position'
  if (type === 'BREAKDOWN') return 'badge-breakdown'
  return ''
}

async function fetchEventLog() {
  eventLogLoading.value = true
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50 }
    if (eventLogStartDate.value) params.start_date = eventLogStartDate.value
    if (eventLogEndDate.value) params.end_date = eventLogEndDate.value
    const res = await apiClient.get<{ total: number; items: EventLogItem[] }>('/risk/event-log', { params })
    eventLogItems.value = res.data.items ?? []
    eventLogTotal.value = res.data.total ?? 0
  } catch {
    eventLogItems.value = []
    eventLogTotal.value = 0
  } finally {
    eventLogLoading.value = false
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

async function loadStopConfig() {
  try {
    const res = await apiClient.get<StopConfig>('/risk/stop-config')
    Object.assign(stopConfig, res.data)
  } catch {
    // 加载失败时保留前端默认值
  }
}

onMounted(() => {
  fetchRiskOverview()
  fetchTotalPosition()
  loadStopConfig()
  fetchLists()
  fetchPositionWarnings()
  fetchStrategyHealth()
  fetchEventLog()
  fetchAllIndexKlines()
  connectRiskWebSocket()
})

onUnmounted(() => {
  disconnectRiskWebSocket()
})
</script>

<style scoped>
.risk-view { max-width: 1000px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; margin-bottom: 12px; color: #e6edf3; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }

.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-header .section-title { margin-bottom: 0; }

.btn-icon {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  width: 30px; height: 30px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.btn-icon:hover { color: #e6edf3; border-color: #58a6ff; }
.btn-icon:disabled { opacity: 0.5; cursor: not-allowed; }

.refresh-icon { display: inline-block; }
.refresh-icon.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* 风控状态 */
.risk-overview { display: flex; flex-direction: column; gap: 16px; }

.risk-level-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: 600;
  width: fit-content;
}
.risk-level-dot { width: 8px; height: 8px; border-radius: 50%; }
.level-normal { background: #1a3a2a; color: #3fb950; border: 1px solid #2ea04322; }
.level-normal .risk-level-dot { background: #3fb950; }
.level-elevated { background: #3a2a1a; color: #d29922; border: 1px solid #d2992222; }
.level-elevated .risk-level-dot { background: #d29922; }
.level-suspended { background: #3a1a1a; color: #f85149; border: 1px solid #f8514922; }
.level-suspended .risk-level-dot { background: #f85149; }

.ma-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.ma-item {
  background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
  padding: 10px 16px; display: flex; flex-direction: column; gap: 4px; min-width: 140px;
}
.ma-label { font-size: 12px; color: #8b949e; }
.ma-status { font-size: 14px; font-weight: 600; }
.ma-status.above { color: #3fb950; }
.ma-status.below { color: #f85149; }
.threshold-item { min-width: 160px; }
.threshold-value { font-size: 20px; font-weight: 700; color: #58a6ff; }

/* 止损止盈配置 */
.mode-switch { margin-bottom: 16px; }
.mode-label { font-size: 13px; color: #8b949e; display: block; margin-bottom: 6px; }
.mode-tabs { display: flex; gap: 4px; }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }
.hint { font-size: 11px; color: #484f58; }

.form-actions { display: flex; align-items: center; gap: 12px; margin-top: 16px; }
.save-msg { font-size: 13px; }
.save-msg.success { color: #3fb950; }
.save-msg.error { color: #f85149; }

/* 通用输入 */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.input:focus { outline: none; border-color: #58a6ff; }
.btn {
  background: #238636; color: #fff; border: none; padding: 6px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn:hover:not(:disabled) { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.save-btn { align-self: flex-start; }

/* 黑白名单 */
.list-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;
}
.tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
.tab:hover:not(.active) { color: #e6edf3; }

.add-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.pagination-hint { font-size: 12px; color: #484f58; margin-top: 8px; text-align: right; }

/* 表格 */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px; }
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; }
.empty { text-align: center; color: #484f58; padding: 24px; }

.btn-sm {
  background: none; border: 1px solid #30363d; color: #8b949e;
  padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-sm.danger:hover { color: #f85149; border-color: #f85149; }

/* 预警 */
.warning-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;
}
.warning-badge.danger { background: #3a1a1a; color: #f85149; }
.warning-badge.warning { background: #3a2a1a; color: #d29922; }
.warning-badge.info { background: #1a2a3a; color: #58a6ff; }

/* 破位预警类型区分（需求 7） */
.warning-badge.breakdown-rapid { background: #3a1a1a; color: #f85149; border: 1px solid #f8514944; }
.warning-badge.breakdown-gradual { background: #3a2a1a; color: #d29922; border: 1px solid #d2992244; }

/* 盈亏百分比颜色（需求 12） */
.pnl-profit { color: #3fb950; font-weight: 600; }
.pnl-loss { color: #f85149; font-weight: 600; }

/* 建议操作标签（需求 12） */
.action-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 500; white-space: nowrap;
}
.action-tag.action-sell { background: #3a1a1a; color: #f85149; }
.action-tag.action-reduce { background: #3a2a1a; color: #d29922; }
.action-tag.action-watch { background: #1a2a3a; color: #58a6ff; }
.action-tag.action-hold { background: #2a1a3a; color: #bc8cff; }
.action-tag.action-default { background: #21262d; color: #8b949e; }

/* 总仓位状态（需求 5） */
.total-position-area { display: flex; flex-direction: column; gap: 16px; }

.position-progress { display: flex; flex-direction: column; gap: 6px; }
.progress-header { display: flex; justify-content: space-between; align-items: baseline; }
.progress-label { font-size: 13px; color: #8b949e; }
.progress-value { font-size: 20px; font-weight: 700; }
.progress-value.safe { color: #3fb950; }
.progress-value.near-limit { color: #d29922; }
.progress-value.over-limit { color: #f85149; }

.progress-bar-bg {
  position: relative; height: 10px; background: #21262d; border-radius: 5px; overflow: visible;
}
.progress-bar-fill {
  height: 100%; border-radius: 5px; transition: width 0.4s ease;
}
.progress-bar-fill.safe { background: #238636; }
.progress-bar-fill.near-limit { background: #d29922; }
.progress-bar-fill.over-limit { background: #f85149; }

.progress-bar-limit {
  position: absolute; top: -3px; width: 2px; height: 16px;
  background: #e6edf3; border-radius: 1px; transform: translateX(-1px);
}

.progress-footer { display: flex; justify-content: flex-end; }
.limit-label { font-size: 12px; color: #8b949e; }

.position-details { display: flex; flex-wrap: wrap; gap: 10px; }
.detail-item {
  background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
  padding: 10px 16px; display: flex; flex-direction: column; gap: 4px; min-width: 140px; flex: 1;
}
.detail-label { font-size: 12px; color: #8b949e; }
.detail-value { font-size: 16px; font-weight: 600; color: #e6edf3; }

.loading-text { color: #8b949e; font-size: 14px; padding: 16px 0; }

/* 止损预警闪烁动画（需求 2） */
@keyframes flash {
  0%, 100% { background: transparent; }
  50% { background: rgba(248, 81, 73, 0.15); }
}
.warning-row.flash { animation: flash 0.6s ease-in-out 5; }

/* WebSocket 连接状态 */
.header-actions { display: flex; align-items: center; gap: 8px; }
.ws-status {
  font-size: 12px; padding: 2px 8px; border-radius: 4px; font-weight: 500;
}
.ws-status.connected { color: #3fb950; background: #1a3a2a; }
.ws-status.connecting { color: #d29922; background: #3a2a1a; }
.ws-status.disconnected { color: #f85149; background: #3a1a1a; }

/* 策略健康状态（需求 8） */
.health-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.health-column {
  background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 16px;
}
.health-column-title { font-size: 14px; color: #8b949e; margin-bottom: 12px; font-weight: 600; }
.health-metrics { display: flex; flex-direction: column; gap: 10px; }
.health-metric { display: flex; justify-content: space-between; align-items: center; }
.health-label { font-size: 13px; color: #8b949e; }
.health-value { font-size: 16px; font-weight: 600; color: #e6edf3; }
.health-status {
  display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 13px; font-weight: 500;
}
.health-status.healthy { color: #3fb950; background: #1a3a2a; }
.health-status.unhealthy { color: #f85149; background: #3a1a1a; }
.health-status.na { color: #484f58; }
.health-note { font-size: 12px; color: #d29922; margin-top: 4px; }
.health-warnings { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.health-warning-item {
  font-size: 13px; color: #d29922; background: #3a2a1a; padding: 6px 12px; border-radius: 4px;
}

/* 多指数均线状态（需求 9） */
.ma-index-name { font-size: 14px; font-weight: 600; color: #e6edf3; margin-bottom: 4px; }
.ma-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.ma-status.caution { color: #d29922; }

/* 风控日志（需求 10） */
.event-log-filters { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 12px; flex-wrap: wrap; }
.filter-item { display: flex; flex-direction: column; gap: 4px; }
.filter-item label { font-size: 12px; color: #8b949e; }

.event-type-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;
}
.badge-rejected { background: #3a1a1a; color: #f85149; }
.badge-stop-loss { background: #3a2a1a; color: #d29922; }
.badge-position { background: #1a2a3a; color: #58a6ff; }
.badge-breakdown { background: #2a1a3a; color: #bc8cff; }

.result-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;
}
.result-badge.rejected { background: #3a1a1a; color: #f85149; }
.result-badge.warned { background: #3a2a1a; color: #d29922; }

/* 指数 K 线迷你图（需求 11） */
.kline-mini-charts { margin-top: 16px; border-top: 1px solid #21262d; padding-top: 16px; }
.kline-section-title { font-size: 14px; color: #8b949e; margin-bottom: 12px; font-weight: 600; }
.kline-chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.kline-chart-item {
  background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
  padding: 10px; display: flex; flex-direction: column; gap: 6px;
}
.kline-chart-label { font-size: 13px; font-weight: 600; color: #e6edf3; }
.kline-mini-chart { width: 100%; height: 200px; }
.kline-chart-placeholder { height: 200px; display: flex; align-items: center; justify-content: center; color: #484f58; font-size: 13px; }

@media (max-width: 700px) {
  .kline-chart-grid { grid-template-columns: 1fr; }
}
</style>
