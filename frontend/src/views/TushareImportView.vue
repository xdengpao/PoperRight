<template>
  <div class="tushare-import-view">
    <TushareTabNav />
    <h1 class="page-title">Tushare 数据导入</h1>

    <!-- ── 连接状态 + Token 配置 ── -->
    <section class="card" aria-label="Tushare 连接状态">
      <div class="connection-bar">
        <div class="connection-info">
          <span class="connection-label">连接状态:</span>
          <span v-if="healthLoading" class="connection-status checking">⏳ 检测中...</span>
          <span v-else-if="health.connected" class="connection-status connected">✅ 已连接</span>
          <span v-else class="connection-status disconnected">❌ 未连接</span>
          <span class="token-divider">|</span>
          <span class="token-label">Token:</span>
          <span class="token-status">基础{{ health.tokens.basic.configured ? '✅' : '❌' }}</span>
          <span class="token-status">高级{{ health.tokens.advanced.configured ? '✅' : '❌' }}</span>
          <span class="token-status">专业{{ health.tokens.premium.configured ? '✅' : '❌' }}</span>
          <span class="token-status">特殊{{ health.tokens.special.configured ? '✅' : '❌' }}</span>
        </div>
        <button class="btn btn-secondary" :disabled="healthLoading" @click="checkHealth"
          aria-label="重新检测 Tushare 连接">{{ healthLoading ? '检测中...' : '重新检测' }}</button>
      </div>
    </section>

    <!-- ── 股票数据 ── -->
    <section class="card" aria-label="股票数据">
      <h2 class="section-title">📈 股票数据</h2>
      <div v-if="registryLoading" class="empty">加载接口列表...</div>
      <div v-else-if="stockCategories.length === 0" class="empty">暂无股票数据接口</div>
      <div v-else>
        <div v-for="group in stockCategories" :key="'s-' + group.subcategory" class="subcategory-group">
          <button class="subcategory-header" @click="toggleSubcategory(group.subcategory)"
            :aria-expanded="expandedSubcategories.has(group.subcategory)">
            <span class="subcategory-arrow" :class="{ expanded: expandedSubcategories.has(group.subcategory) }">▸</span>
            <span class="subcategory-name">{{ group.subcategory }}</span>
            <span class="subcategory-count">{{ group.apis.length }} 个接口</span>
          </button>
          <div v-if="expandedSubcategories.has(group.subcategory)" class="api-list">
            <div class="batch-select-header">
              <label class="batch-checkbox-label" @click.stop>
                <input type="checkbox" class="batch-checkbox"
                  :checked="getSelectedCount(group.subcategory) === group.apis.length && group.apis.length > 0"
                  :indeterminate="getSelectedCount(group.subcategory) > 0 && getSelectedCount(group.subcategory) < group.apis.length"
                  @change="toggleAllApis(group.subcategory, group.apis)" />
                <span>全选</span>
              </label>
            </div>
            <div v-if="isMidFreqSubcategory(group.subcategory)" class="mid-freq-warning">
              ⚠️ 分钟级数据量较大，建议按单只股票或短日期范围分批导入</div>
            <div v-for="api in group.apis" :key="api.api_name" class="api-item">
              <div class="api-item-header">
                <label class="batch-checkbox-label" @click.stop>
                  <input type="checkbox" class="batch-checkbox"
                    :checked="selectedApis.get(group.subcategory)?.has(api.api_name) ?? false"
                    @change="toggleApiSelection(group.subcategory, api.api_name)" />
                </label>
                <span class="api-name">{{ api.api_name }}</span>
                <span class="api-label">{{ api.label }}</span>
                <span class="tier-badge" :class="'tier-' + api.token_tier">{{ tierLabel(api.token_tier) }}</span>
              </div>
              <div class="api-params">
                <template v-for="p in uniqueParams(api)" :key="api.api_name + p">
                  <div v-if="p === 'date_range'" class="param-field">
                    <label class="param-label">日期范围<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <div class="date-range-inputs">
                      <input type="date" class="form-input param-input" :value="getParam(api.api_name, 'start_date') || oneYearAgoStr"
                        @input="setParam(api.api_name, 'start_date', ($event.target as HTMLInputElement).value)" aria-label="开始日期" />
                      <span class="date-sep">至</span>
                      <input type="date" class="form-input param-input" :value="getParam(api.api_name, 'end_date') || todayStr"
                        @input="setParam(api.api_name, 'end_date', ($event.target as HTMLInputElement).value)" aria-label="结束日期" />
                    </div>
                  </div>
                  <div v-else-if="p === 'stock_code'" class="param-field">
                    <label class="param-label">股票代码<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="text" class="form-input param-input" placeholder="股票代码，逗号分隔，留空表示全市场"
                      :value="getParam(api.api_name, 'stock_code')"
                      @input="setParam(api.api_name, 'stock_code', ($event.target as HTMLInputElement).value)" />
                  </div>
                  <div v-else-if="p === 'index_code'" class="param-field">
                    <label class="param-label">指数代码<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="text" class="form-input param-input" placeholder="指数代码"
                      :value="getParam(api.api_name, 'index_code')"
                      @input="setParam(api.api_name, 'index_code', ($event.target as HTMLInputElement).value)" />
                  </div>
                  <div v-else-if="p === 'market'" class="param-field">
                    <label class="param-label">市场<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <select class="form-input param-input" :value="getParam(api.api_name, 'market')"
                      @change="setParam(api.api_name, 'market', ($event.target as HTMLSelectElement).value)">
                      <option value="">全部</option><option value="SSE">SSE（上交所）</option>
                      <option value="SZSE">SZSE（深交所）</option><option value="CSI">CSI（中证）</option>
                    </select>
                  </div>
                  <div v-else-if="p === 'report_period'" class="param-field">
                    <label class="param-label">报告期<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <div class="report-period-inputs">
                      <select class="form-input param-input" :value="getParam(api.api_name, 'report_year') || currentYear"
                        @change="setParam(api.api_name, 'report_year', ($event.target as HTMLSelectElement).value)">
                        <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}年</option>
                      </select>
                      <select class="form-input param-input" :value="getParam(api.api_name, 'report_quarter') || '1'"
                        @change="setParam(api.api_name, 'report_quarter', ($event.target as HTMLSelectElement).value)">
                        <option value="1">一季报</option><option value="2">中报</option>
                        <option value="3">三季报</option><option value="4">年报</option>
                      </select>
                    </div>
                  </div>
                  <div v-else-if="p === 'freq'" class="param-field">
                    <label class="param-label">频率<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <select class="form-input param-input" :value="getParam(api.api_name, 'freq') || freqDefault(api)"
                      @change="setParam(api.api_name, 'freq', ($event.target as HTMLSelectElement).value)">
                      <template v-if="isWeeklyMonthlyApi(api)">
                        <option value="W">周线 (W)</option><option value="M">月线 (M)</option>
                      </template>
                      <template v-else>
                        <option value="1min">1min</option><option value="5min">5min</option>
                        <option value="15min">15min</option><option value="30min">30min</option><option value="60min">60min</option>
                      </template>
                    </select>
                  </div>
                  <div v-else-if="p === 'hs_type'" class="param-field">
                    <label class="param-label">类型<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <select class="form-input param-input" :value="getParam(api.api_name, 'hs_type')"
                      @change="setParam(api.api_name, 'hs_type', ($event.target as HTMLSelectElement).value)">
                      <option value="">请选择</option><option value="SH">SH（沪股通）</option><option value="SZ">SZ（深股通）</option>
                    </select>
                  </div>
                  <div v-else-if="p === 'sector_code'" class="param-field">
                    <label class="param-label">板块代码<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="text" class="form-input param-input" placeholder="板块代码"
                      :value="getParam(api.api_name, 'sector_code')"
                      @input="setParam(api.api_name, 'sector_code', ($event.target as HTMLInputElement).value)" />
                  </div>
                  <div v-else-if="p === 'month_range'" class="param-field">
                    <label class="param-label">月份<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="month" class="form-input param-input"
                      :value="getParam(api.api_name, 'month') || currentMonthStr"
                      @input="setParam(api.api_name, 'month', ($event.target as HTMLInputElement).value)"
                      aria-label="月份" />
                  </div>
                </template>
                <button class="btn btn-primary btn-import" :class="{ 'btn-loading': loadingApis.has(api.api_name) }"
                  :disabled="!canImport(api) || loadingApis.has(api.api_name)" @click="startImport(api)"
                  :title="importButtonTitle(api)" :aria-label="'开始导入 ' + api.api_name">{{ loadingApis.has(api.api_name) ? '导入中...' : '开始导入' }}</button>
                <span v-if="formatLastImportTime(api.api_name)" class="last-import-time">
                  最近: {{ formatLastImportTime(api.api_name) }}
                </span>
              </div>
            </div>
            <div class="batch-import-bar">
              <button class="btn btn-primary btn-batch-import"
                :disabled="getSelectedCount(group.subcategory) === 0"
                @click="batchImport(group.subcategory, group.apis)"
                :aria-label="'批量导入已选 ' + getSelectedCount(group.subcategory) + ' 个接口'">
                批量导入已选 ({{ getSelectedCount(group.subcategory) }})
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 指数专题 ── -->
    <section class="card" aria-label="指数专题">
      <h2 class="section-title">📊 指数专题</h2>
      <div v-if="registryLoading" class="empty">加载接口列表...</div>
      <div v-else-if="indexCategories.length === 0" class="empty">暂无指数专题接口</div>
      <div v-else>
        <div v-for="group in indexCategories" :key="'i-' + group.subcategory" class="subcategory-group">
          <button class="subcategory-header" @click="toggleSubcategory(group.subcategory)"
            :aria-expanded="expandedSubcategories.has(group.subcategory)">
            <span class="subcategory-arrow" :class="{ expanded: expandedSubcategories.has(group.subcategory) }">▸</span>
            <span class="subcategory-name">{{ group.subcategory }}</span>
            <span class="subcategory-count">{{ group.apis.length }} 个接口</span>
          </button>
          <div v-if="expandedSubcategories.has(group.subcategory)" class="api-list">
            <div class="batch-select-header">
              <label class="batch-checkbox-label" @click.stop>
                <input type="checkbox" class="batch-checkbox"
                  :checked="getSelectedCount(group.subcategory) === group.apis.length && group.apis.length > 0"
                  :indeterminate="getSelectedCount(group.subcategory) > 0 && getSelectedCount(group.subcategory) < group.apis.length"
                  @change="toggleAllApis(group.subcategory, group.apis)" />
                <span>全选</span>
              </label>
            </div>
            <div v-if="isMidFreqSubcategory(group.subcategory)" class="mid-freq-warning">
              ⚠️ 分钟级数据量较大，建议按单只指数或短日期范围分批导入</div>
            <div v-for="api in group.apis" :key="api.api_name" class="api-item">
              <div class="api-item-header">
                <label class="batch-checkbox-label" @click.stop>
                  <input type="checkbox" class="batch-checkbox"
                    :checked="selectedApis.get(group.subcategory)?.has(api.api_name) ?? false"
                    @change="toggleApiSelection(group.subcategory, api.api_name)" />
                </label>
                <span class="api-name">{{ api.api_name }}</span>
                <span class="api-label">{{ api.label }}</span>
                <span class="tier-badge" :class="'tier-' + api.token_tier">{{ tierLabel(api.token_tier) }}</span>
              </div>
              <div class="api-params">
                <template v-for="p in uniqueParams(api)" :key="api.api_name + p">
                  <div v-if="p === 'date_range'" class="param-field">
                    <label class="param-label">日期范围<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <div class="date-range-inputs">
                      <input type="date" class="form-input param-input" :value="getParam(api.api_name, 'start_date') || oneYearAgoStr"
                        @input="setParam(api.api_name, 'start_date', ($event.target as HTMLInputElement).value)" aria-label="开始日期" />
                      <span class="date-sep">至</span>
                      <input type="date" class="form-input param-input" :value="getParam(api.api_name, 'end_date') || todayStr"
                        @input="setParam(api.api_name, 'end_date', ($event.target as HTMLInputElement).value)" aria-label="结束日期" />
                    </div>
                  </div>
                  <div v-else-if="p === 'stock_code'" class="param-field">
                    <label class="param-label">股票代码<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="text" class="form-input param-input" placeholder="股票代码，逗号分隔，留空表示全市场"
                      :value="getParam(api.api_name, 'stock_code')"
                      @input="setParam(api.api_name, 'stock_code', ($event.target as HTMLInputElement).value)" />
                  </div>
                  <div v-else-if="p === 'index_code'" class="param-field">
                    <label class="param-label">指数代码<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="text" class="form-input param-input" placeholder="指数代码"
                      :value="getParam(api.api_name, 'index_code')"
                      @input="setParam(api.api_name, 'index_code', ($event.target as HTMLInputElement).value)" />
                  </div>
                  <div v-else-if="p === 'market'" class="param-field">
                    <label class="param-label">市场<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <select class="form-input param-input" :value="getParam(api.api_name, 'market')"
                      @change="setParam(api.api_name, 'market', ($event.target as HTMLSelectElement).value)">
                      <option value="">全部</option><option value="SSE">SSE（上交所）</option>
                      <option value="SZSE">SZSE（深交所）</option><option value="CSI">CSI（中证）</option>
                    </select>
                  </div>
                  <div v-else-if="p === 'report_period'" class="param-field">
                    <label class="param-label">报告期<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <div class="report-period-inputs">
                      <select class="form-input param-input" :value="getParam(api.api_name, 'report_year') || currentYear"
                        @change="setParam(api.api_name, 'report_year', ($event.target as HTMLSelectElement).value)">
                        <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}年</option>
                      </select>
                      <select class="form-input param-input" :value="getParam(api.api_name, 'report_quarter') || '1'"
                        @change="setParam(api.api_name, 'report_quarter', ($event.target as HTMLSelectElement).value)">
                        <option value="1">一季报</option><option value="2">中报</option>
                        <option value="3">三季报</option><option value="4">年报</option>
                      </select>
                    </div>
                  </div>
                  <div v-else-if="p === 'freq'" class="param-field">
                    <label class="param-label">频率<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <select class="form-input param-input" :value="getParam(api.api_name, 'freq') || freqDefault(api)"
                      @change="setParam(api.api_name, 'freq', ($event.target as HTMLSelectElement).value)">
                      <template v-if="isWeeklyMonthlyApi(api)">
                        <option value="W">周线 (W)</option><option value="M">月线 (M)</option>
                      </template>
                      <template v-else>
                        <option value="1min">1min</option><option value="5min">5min</option>
                        <option value="15min">15min</option><option value="30min">30min</option><option value="60min">60min</option>
                      </template>
                    </select>
                  </div>
                  <div v-else-if="p === 'hs_type'" class="param-field">
                    <label class="param-label">类型<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <select class="form-input param-input" :value="getParam(api.api_name, 'hs_type')"
                      @change="setParam(api.api_name, 'hs_type', ($event.target as HTMLSelectElement).value)">
                      <option value="">请选择</option><option value="SH">SH（沪股通）</option><option value="SZ">SZ（深股通）</option>
                    </select>
                  </div>
                  <div v-else-if="p === 'sector_code'" class="param-field">
                    <label class="param-label">板块代码<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="text" class="form-input param-input" placeholder="板块代码"
                      :value="getParam(api.api_name, 'sector_code')"
                      @input="setParam(api.api_name, 'sector_code', ($event.target as HTMLInputElement).value)" />
                  </div>
                  <div v-else-if="p === 'month_range'" class="param-field">
                    <label class="param-label">月份<span v-if="api.required_params.includes(p)" class="req">*</span></label>
                    <input type="month" class="form-input param-input"
                      :value="getParam(api.api_name, 'month') || currentMonthStr"
                      @input="setParam(api.api_name, 'month', ($event.target as HTMLInputElement).value)"
                      aria-label="月份" />
                  </div>
                </template>
                <button class="btn btn-primary btn-import" :class="{ 'btn-loading': loadingApis.has(api.api_name) }"
                  :disabled="!canImport(api) || loadingApis.has(api.api_name)" @click="startImport(api)"
                  :title="importButtonTitle(api)" :aria-label="'开始导入 ' + api.api_name">{{ loadingApis.has(api.api_name) ? '导入中...' : '开始导入' }}</button>
                <span v-if="formatLastImportTime(api.api_name)" class="last-import-time">
                  最近: {{ formatLastImportTime(api.api_name) }}
                </span>
              </div>
            </div>
            <div class="batch-import-bar">
              <button class="btn btn-primary btn-batch-import"
                :disabled="getSelectedCount(group.subcategory) === 0"
                @click="batchImport(group.subcategory, group.apis)"
                :aria-label="'批量导入已选 ' + getSelectedCount(group.subcategory) + ' 个接口'">
                批量导入已选 ({{ getSelectedCount(group.subcategory) }})
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 活跃任务 ── -->
    <section v-if="activeTasks.length > 0" class="card" aria-label="活跃任务">
      <div class="section-header">
        <h2 class="section-title">🔄 活跃任务</h2>
        <button v-if="hasTerminalTasks" class="btn btn-secondary btn-sm" @click="clearTerminalTasks">
          清除已结束任务
        </button>
      </div>
      <div v-for="task in activeTasks" :key="task.task_id" class="active-task">
        <div class="task-header">
          <span class="task-api-name">{{ task.api_name }}</span>
          <span class="status-badge" :class="taskStatusClass(task.status)">{{ taskStatusLabel(task.status) }}</span>
          <button v-if="task.status === 'pending' || task.status === 'running'" class="btn btn-danger btn-sm"
            @click="stopImport(task.task_id)" :aria-label="'停止导入 ' + task.api_name">停止导入</button>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar" :class="taskBarClass(task.status)" :style="{ width: taskPct(task) + '%' }"></div>
        </div>
        <div class="task-details">
          <span class="task-pct">{{ taskPct(task) }}%</span>
          <span class="task-counts">已完成 {{ task.completed }}/{{ task.total }}
            <span v-if="task.failed > 0" class="task-failed">失败 {{ task.failed }}</span></span>
          <span v-if="task.current_item" class="task-current">当前: {{ task.current_item }}</span>
        </div>
        <div v-if="task.status === 'failed' && task.error_message" class="task-error-message">
          {{ task.error_message }}
        </div>
      </div>
    </section>

    <!-- ── 导入历史 ── -->
    <section class="card" aria-label="导入历史">
      <h2 class="section-title">📋 导入历史</h2>
      <div v-if="historyLoading" class="empty">加载导入历史...</div>
      <div v-else-if="historyList.length === 0" class="empty">暂无导入记录</div>
      <table v-else class="data-table" aria-label="导入历史记录列表">
        <thead><tr>
          <th scope="col">接口名称</th><th scope="col">导入时间</th>
          <th scope="col">数据量</th><th scope="col">状态</th><th scope="col">耗时</th>
        </tr></thead>
        <tbody>
          <tr v-for="log in historyList" :key="log.id">
            <td class="api-name-cell">{{ log.api_name }}</td>
            <td>{{ formatTime(log.started_at) }}</td>
            <td>{{ log.record_count.toLocaleString() }} 条</td>
            <td><span class="status-badge" :class="historyStatusClass(log.status)">{{ historyStatusLabel(log.status) }}</span>
              <div v-if="log.status === 'failed' && log.error_message" class="history-error-message">{{ log.error_message }}</div>
            </td>
            <td>{{ formatDuration(log.started_at, log.finished_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * TushareImportView - Tushare 数据在线导入页面
 *
 * 提供 Tushare 平台 60+ 个 API 接口的数据导入能力，
 * 覆盖股票数据和指数专题两大分类。
 *
 * 需求: 2.1-2.7, 20.3, 21.1, 22.1-22.4, 22a.5-22a.6, 23.1-23.4, 24.1-24.5
 */
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiClient } from '@/api'
import TushareTabNav from '@/components/TushareTabNav.vue'

// ── 类型定义 ──────────────────────────────────────────────────────────────────

/** API 注册表条目 */
export interface ApiItem {
  api_name: string
  label: string
  category: string
  subcategory: string
  token_tier: string
  required_params: string[]
  optional_params: string[]
  token_available: boolean
}

/** 按子分类分组 */
interface SubcategoryGroup {
  subcategory: string
  apis: ApiItem[]
}

/** 活跃导入任务 */
export interface ImportTask {
  task_id: string
  api_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  total: number
  completed: number
  failed: number
  current_item: string
  error_message?: string
}

/** 导入历史记录 */
export interface ImportLog {
  id: number
  api_name: string
  status: string
  record_count: number
  error_message: string | null
  celery_task_id: string | null
  started_at: string
  finished_at: string | null
}

/** 健康检查响应 */
interface HealthResponse {
  connected: boolean
  tokens: {
    basic: { configured: boolean }
    advanced: { configured: boolean }
    premium: { configured: boolean }
    special: { configured: boolean }
  }
}

// ── 状态 ──────────────────────────────────────────────────────────────────────

const healthLoading = ref(false)
const health = reactive<HealthResponse>({
  connected: false,
  tokens: {
    basic: { configured: false },
    advanced: { configured: false },
    premium: { configured: false },
    special: { configured: false },
  },
})

const registryLoading = ref(false)
const registryList = ref<ApiItem[]>([])
const paramValues = reactive<Record<string, Record<string, string>>>({})
const expandedSubcategories = reactive(new Set<string>())

const loadingApis = reactive(new Set<string>())

/** 按子分类存储已勾选的 API 名称 */
const selectedApis = reactive(new Map<string, Set<string>>())

const activeTasks = ref<ImportTask[]>([])
const pollTimers = ref<Record<string, ReturnType<typeof setInterval>>>({})

const historyLoading = ref(false)
const historyList = ref<ImportLog[]>([])
const lastImportTimes = ref<Record<string, string>>({})

// ── 常量 ──────────────────────────────────────────────────────────────────────

const todayStr = new Date().toISOString().slice(0, 10)
const oneYearAgoStr = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10)
const currentMonthStr = todayStr.slice(0, 7)  // YYYY-MM 格式
const currentYear = new Date().getFullYear().toString()
const yearOptions = Array.from({ length: 10 }, (_, i) => (new Date().getFullYear() - i).toString())
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'stopped', 'unknown'])
const POLL_INTERVAL = 3000

// ── 计算属性 ──────────────────────────────────────────────────────────────────

const stockCategories = computed<SubcategoryGroup[]>(() =>
  groupBySubcategory(registryList.value.filter(a => a.category === 'stock_data')),
)

const indexCategories = computed<SubcategoryGroup[]>(() =>
  groupBySubcategory(registryList.value.filter(a => a.category === 'index_data')),
)

// ── 工具函数 ──────────────────────────────────────────────────────────────────

function groupBySubcategory(apis: ApiItem[]): SubcategoryGroup[] {
  const map = new Map<string, ApiItem[]>()
  for (const api of apis) {
    const list = map.get(api.subcategory)
    if (list) list.push(api)
    else map.set(api.subcategory, [api])
  }
  return Array.from(map.entries()).map(([subcategory, apis]) => ({ subcategory, apis }))
}

function isMidFreqSubcategory(sub: string): boolean {
  return sub.includes('中频') || sub.includes('分钟')
}

function tierLabel(tier: string): string {
  return ({ basic: '基础', advanced: '高级', premium: '专业', special: '特殊' } as Record<string, string>)[tier] ?? tier
}

/** 判断是否为周/月行情接口（频率选择器显示 W/M 而非分钟） */
function isWeeklyMonthlyApi(api: ApiItem): boolean {
  return api.api_name === 'stk_weekly_monthly'
}

/** 根据接口类型返回频率默认值 */
function freqDefault(api: ApiItem): string {
  return isWeeklyMonthlyApi(api) ? 'W' : '1min'
}

/** 合并 required + optional 并去重 */
function uniqueParams(api: ApiItem): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const p of [...api.required_params, ...api.optional_params]) {
    if (!seen.has(p)) { seen.add(p); result.push(p) }
  }
  return result
}

function getParam(apiName: string, key: string): string {
  return paramValues[apiName]?.[key] ?? ''
}

function setParam(apiName: string, key: string, value: string): void {
  if (!paramValues[apiName]) paramValues[apiName] = {}
  paramValues[apiName][key] = value
}

function requiredParamsFilled(api: ApiItem): boolean {
  for (const p of api.required_params) {
    if (p === 'date_range') {
      // start_date 有默认值 oneYearAgoStr，无需校验
      continue
    } else if (p === 'report_period' || p === 'freq' || p === 'market' || p === 'month_range') {
      continue // 有默认值或允许空
    } else if (p === 'stock_code') {
      continue // 留空表示全市场，无需校验
    } else if (p === 'index_code') {
      continue // 留空表示全部指数，无需校验
    } else {
      if (!getParam(api.api_name, p)) return false
    }
  }
  return true
}

function canImport(api: ApiItem): boolean {
  return health.connected && api.token_available && requiredParamsFilled(api)
}

function importButtonTitle(api: ApiItem): string {
  if (!health.connected) return 'Tushare 未连接'
  if (!api.token_available) return '需配置对应权限 Token'
  if (!requiredParamsFilled(api)) return '请填写必填参数'
  return '开始导入 ' + api.api_name
}

function toggleSubcategory(sub: string): void {
  if (expandedSubcategories.has(sub)) expandedSubcategories.delete(sub)
  else expandedSubcategories.add(sub)
}

/** 切换单个 API 的选中状态 */
function toggleApiSelection(subcategory: string, apiName: string): void {
  if (!selectedApis.has(subcategory)) {
    selectedApis.set(subcategory, new Set<string>())
  }
  const set = selectedApis.get(subcategory)!
  if (set.has(apiName)) set.delete(apiName)
  else set.add(apiName)
}

/** 全选/取消全选子分类下的所有 API */
function toggleAllApis(subcategory: string, apis: ApiItem[]): void {
  const current = selectedApis.get(subcategory)
  if (current && current.size === apis.length) {
    // 已全选 → 取消全选
    selectedApis.set(subcategory, new Set<string>())
  } else {
    // 未全选 → 全选
    selectedApis.set(subcategory, new Set(apis.map(a => a.api_name)))
  }
}

/** 获取子分类已选数量 */
function getSelectedCount(subcategory: string): number {
  return selectedApis.get(subcategory)?.size ?? 0
}

/** 批量导入已选 API，顺序执行 */
async function batchImport(subcategory: string, apis: ApiItem[]): Promise<void> {
  const selected = selectedApis.get(subcategory)
  if (!selected || selected.size === 0) return
  const toImport = apis.filter(a => selected.has(a.api_name))
  for (const api of toImport) {
    await startImport(api)
  }
}

function buildImportParams(api: ApiItem): Record<string, string> {
  const params: Record<string, string> = {}
  for (const p of [...api.required_params, ...api.optional_params]) {
    if (p === 'date_range') {
      params['start_date'] = getParam(api.api_name, 'start_date') || oneYearAgoStr
      params['end_date'] = getParam(api.api_name, 'end_date') || todayStr
    } else if (p === 'report_period') {
      params['report_year'] = getParam(api.api_name, 'report_year') || currentYear
      params['report_quarter'] = getParam(api.api_name, 'report_quarter') || '1'
    } else if (p === 'freq') {
      params['freq'] = getParam(api.api_name, 'freq') || freqDefault(api)
    } else if (p === 'month_range') {
      // 月份参数：YYYY-MM → YYYYMM（Tushare 要求的 month 格式）
      const monthVal = getParam(api.api_name, 'month') || currentMonthStr
      params['month'] = monthVal.replace('-', '')
    } else {
      const v = getParam(api.api_name, p)
      if (v) params[p] = v
    }
  }
  return params
}

// ── 任务状态工具 ──────────────────────────────────────────────────────────────

const hasTerminalTasks = computed(() =>
  activeTasks.value.some(t => TERMINAL_STATUSES.has(t.status)),
)

function clearTerminalTasks(): void {
  activeTasks.value = activeTasks.value.filter(t => !TERMINAL_STATUSES.has(t.status))
}

function taskPct(t: ImportTask): number {
  return t.total <= 0 ? 0 : Math.min(100, Math.round((t.completed / t.total) * 100))
}

function taskStatusLabel(s: string): string {
  return ({ pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止', unknown: '已丢失' } as Record<string, string>)[s] ?? s
}

function taskStatusClass(s: string): string {
  return ({ pending: 'syncing', running: 'syncing', completed: 'ok', failed: 'error', stopped: 'error' } as Record<string, string>)[s] ?? ''
}

function taskBarClass(s: string): string {
  if (s === 'failed') return 'progress-bar-error'
  if (s === 'stopped') return 'progress-bar-stopped'
  return ''
}

function historyStatusLabel(s: string): string {
  return ({ completed: '✅成功', failed: '❌失败', stopped: '⏹已停止', running: '🔄运行中' } as Record<string, string>)[s] ?? s
}

function historyStatusClass(s: string): string {
  return ({ completed: 'ok', failed: 'error', stopped: 'error', running: 'syncing' } as Record<string, string>)[s] ?? ''
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return '—'
  try {
    const diffMs = new Date(finishedAt).getTime() - new Date(startedAt).getTime()
    if (diffMs < 0) return '—'
    if (diffMs < 1000) return `${diffMs}ms`
    const sec = diffMs / 1000
    if (sec < 60) return `${sec.toFixed(1)}s`
    return `${Math.floor(sec / 60)}m${Math.round(sec % 60)}s`
  } catch { return '—' }
}

// ── API 调用 ──────────────────────────────────────────────────────────────────

async function checkHealth(): Promise<void> {
  healthLoading.value = true
  try {
    const { data } = await apiClient.get<HealthResponse>('/data/tushare/health')
    health.connected = data.connected
    health.tokens.basic.configured = data.tokens?.basic?.configured ?? false
    health.tokens.advanced.configured = data.tokens?.advanced?.configured ?? false
    health.tokens.premium.configured = data.tokens?.premium?.configured ?? false
    health.tokens.special.configured = data.tokens?.special?.configured ?? false
  } catch {
    health.connected = false
  } finally {
    healthLoading.value = false
  }
}

async function fetchRegistry(): Promise<void> {
  registryLoading.value = true
  try {
    const { data } = await apiClient.get<ApiItem[]>('/data/tushare/registry')
    registryList.value = data
  } catch {
    registryList.value = []
  } finally {
    registryLoading.value = false
  }
}

async function startImport(api: ApiItem): Promise<void> {
  const params = buildImportParams(api)
  loadingApis.add(api.api_name)
  try {
    const { data } = await apiClient.post<{ task_id: string; log_id: number; status: string }>(
      '/data/tushare/import', { api_name: api.api_name, params },
    )
    activeTasks.value.push({
      task_id: data.task_id, api_name: api.api_name,
      status: 'pending', total: 0, completed: 0, failed: 0, current_item: '',
    })
    startPolling(data.task_id)
  } catch (e: unknown) {
    const err = e as { response?: { status: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      alert(err.response.data?.detail ?? '该接口已有导入任务正在运行')
    } else {
      alert(e instanceof Error ? e.message : '启动导入失败')
    }
  } finally {
    loadingApis.delete(api.api_name)
  }
}

async function stopImport(taskId: string): Promise<void> {
  try { await apiClient.post(`/data/tushare/import/stop/${taskId}`) } catch { /* 轮询会更新状态 */ }
}

async function fetchTaskStatus(taskId: string): Promise<void> {
  try {
    const { data } = await apiClient.get<ImportTask>(`/data/tushare/import/status/${taskId}`)
    const idx = activeTasks.value.findIndex(t => t.task_id === taskId)
    if (idx >= 0) {
      // 后端返回 unknown 表示 Redis 进度数据已过期（服务重启等），标记为失败并清理
      if (data.status === 'unknown') {
        activeTasks.value[idx] = {
          ...activeTasks.value[idx],
          status: 'failed',
          error_message: '任务状态丢失（服务可能已重启）',
        }
        stopPolling(taskId)
        fetchHistory()
        fetchLastImportTimes()
        return
      }
      activeTasks.value[idx] = { ...activeTasks.value[idx], ...data }
      if (TERMINAL_STATUSES.has(data.status)) {
        stopPolling(taskId)
        fetchHistory()
        fetchLastImportTimes()
      }
    }
  } catch {
    // 网络错误（后端不可达）：增加失败计数，连续 3 次失败后标记任务为丢失
    const idx = activeTasks.value.findIndex(t => t.task_id === taskId)
    if (idx >= 0) {
      const task = activeTasks.value[idx]
      const errCount = (task as unknown as Record<string, number>)._pollErrors ?? 0
      ;(task as unknown as Record<string, number>)._pollErrors = errCount + 1
      if (errCount + 1 >= 3) {
        activeTasks.value[idx] = {
          ...task,
          status: 'failed',
          error_message: '无法连接后端服务',
        }
        stopPolling(taskId)
      }
    }
  }
}

async function fetchHistory(): Promise<void> {
  historyLoading.value = true
  try {
    const { data } = await apiClient.get<ImportLog[]>('/data/tushare/import/history', { params: { limit: 20 } })
    historyList.value = data
  } catch {
    historyList.value = []
  } finally {
    historyLoading.value = false
  }
}

/**
 * 从后端查询所有 running 状态的导入任务，恢复到活跃任务列表并启动轮询。
 * 不受 history limit 限制，确保页面刷新后能看到全部活跃任务。
 */
async function restoreRunningTasks(): Promise<void> {
  try {
    const { data } = await apiClient.get<ImportLog[]>('/data/tushare/import/running')
    for (const log of data) {
      if (!log.celery_task_id) continue
      if (activeTasks.value.some(t => t.task_id === log.celery_task_id)) continue
      const taskId = log.celery_task_id
      activeTasks.value.push({
        task_id: taskId,
        api_name: log.api_name,
        status: 'running',
        total: 0,
        completed: 0,
        failed: 0,
        current_item: '',
      })
      startPolling(taskId)
    }
  } catch {
    // 静默失败，不影响页面加载
  }
}

async function fetchLastImportTimes(): Promise<void> {
  try {
    const { data } = await apiClient.get<Record<string, string>>('/data/tushare/import/last-times')
    lastImportTimes.value = data
  } catch { /* 静默处理 */ }
}

function formatLastImportTime(apiName: string): string {
  const iso = lastImportTimes.value[apiName]
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return '' }
}

// ── 轮询管理 ──────────────────────────────────────────────────────────────────

function startPolling(taskId: string): void {
  stopPolling(taskId)
  fetchTaskStatus(taskId)
  pollTimers.value[taskId] = setInterval(() => fetchTaskStatus(taskId), POLL_INTERVAL)
}

function stopPolling(taskId: string): void {
  const timer = pollTimers.value[taskId]
  if (timer) { clearInterval(timer); delete pollTimers.value[taskId] }
}

function stopAllPolling(): void {
  for (const id of Object.keys(pollTimers.value)) stopPolling(id)
}

// ── 生命周期 ──────────────────────────────────────────────────────────────────

onMounted(() => {
  checkHealth()
  fetchRegistry()
  fetchHistory()
  fetchLastImportTimes()
  restoreRunningTasks()
})

onUnmounted(() => {
  stopAllPolling()
})
</script>

<style scoped>
.tushare-import-view { max-width: 1100px; }

.page-title {
  font-size: 20px; font-weight: 600; color: #e6edf3; margin: 0 0 20px;
}

/* ── 卡片 ── */
.card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 20px; margin-bottom: 20px;
}
.section-title {
  font-size: 15px; font-weight: 600; color: #e6edf3; margin: 0 0 14px;
}
.section-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;
}
.section-header .section-title { margin: 0; }
.empty { text-align: center; color: #484f58; padding: 24px; font-size: 13px; }

/* ── 连接状态栏 ── */
.connection-bar {
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
}
.connection-info { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.connection-label { font-size: 14px; color: #8b949e; }
.connection-status { font-size: 14px; font-weight: 500; }
.connection-status.connected { color: #3fb950; }
.connection-status.disconnected { color: #f85149; }
.connection-status.checking { color: #d29922; }
.token-divider { color: #30363d; }
.token-label { font-size: 14px; color: #8b949e; }
.token-status { font-size: 14px; color: #e6edf3; }

/* ── 按钮 ── */
.btn {
  padding: 6px 16px; border-radius: 6px; font-size: 14px; cursor: pointer; border: none;
  transition: background 0.15s;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #1f6feb; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #388bfd; }
.btn-secondary { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }
.btn-secondary:hover:not(:disabled) { border-color: #8b949e; }
.btn-danger { background: #da3633; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #f85149; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-import { flex-shrink: 0; align-self: flex-end; }
.last-import-time {
  font-size: 12px; color: #484f58; white-space: nowrap; align-self: flex-end;
}
.btn-loading { opacity: 0.7; cursor: wait; position: relative; }
.btn-loading::after {
  content: ''; display: inline-block; width: 12px; height: 12px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: btn-spin 0.6s linear infinite;
  margin-left: 6px; vertical-align: middle;
}
@keyframes btn-spin { to { transform: rotate(360deg); } }

/* ── 子分类折叠 ── */
.subcategory-group { border-bottom: 1px solid #21262d; }
.subcategory-group:last-child { border-bottom: none; }
.subcategory-header {
  display: flex; align-items: center; gap: 8px; width: 100%; padding: 10px 4px;
  background: none; border: none; color: #e6edf3; cursor: pointer; font-size: 14px;
  font-family: inherit; text-align: left;
}
.subcategory-header:hover { background: #1f2937; border-radius: 4px; }
.subcategory-arrow {
  font-size: 12px; color: #484f58; transition: transform 0.2s; display: inline-block;
}
.subcategory-arrow.expanded { transform: rotate(90deg); }
.subcategory-name { font-weight: 500; }
.subcategory-count { margin-left: auto; font-size: 12px; color: #484f58; }

/* ── 中频行情提示 ── */
.mid-freq-warning {
  background: #3a2a1a; border: 1px solid #d29922; border-radius: 6px;
  padding: 8px 12px; margin: 8px 0; font-size: 13px; color: #d29922;
}

/* ── API 条目 ── */
.api-list { padding: 4px 0 8px 16px; }
.api-item {
  padding: 10px 0; border-bottom: 1px solid #21262d;
}
.api-item:last-child { border-bottom: none; }
.api-item-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.api-name { font-family: monospace; font-size: 13px; color: #58a6ff; font-weight: 500; }
.api-label { font-size: 13px; color: #8b949e; }

/* ── Token 权限标签 ── */
.tier-badge {
  display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 500;
}
.tier-basic { background: #1a3a1a; color: #3fb950; }
.tier-advanced { background: #1a2a3a; color: #58a6ff; }
.tier-premium { background: #2a1a3a; color: #bc8cff; }
.tier-special { background: #3a2a1a; color: #d29922; }

/* ── 参数表单 ── */
.api-params { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.param-field { display: flex; flex-direction: column; gap: 4px; }
.param-label { font-size: 12px; color: #8b949e; white-space: nowrap; }
.req { color: #f85149; margin-left: 2px; }
.form-input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 5px 10px; border-radius: 6px; font-size: 13px; box-sizing: border-box;
}
.form-input:focus { border-color: #58a6ff; outline: none; }
.param-input { min-width: 120px; max-width: 200px; }
.date-range-inputs { display: flex; align-items: center; gap: 6px; }
.date-sep { color: #484f58; font-size: 13px; }
.report-period-inputs { display: flex; gap: 6px; }

/* ── 状态徽章 ── */
.status-badge {
  display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500;
}
.status-badge.ok { background: #1a3a1a; color: #3fb950; }
.status-badge.error { background: #3a1a1a; color: #f85149; }
.status-badge.syncing { background: #1a2a3a; color: #58a6ff; }

/* ── 活跃任务 ── */
.active-task {
  padding: 12px; background: #0d1117; border: 1px solid #21262d; border-radius: 6px; margin-bottom: 10px;
}
.active-task:last-child { margin-bottom: 0; }
.task-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.task-api-name { font-family: monospace; font-size: 14px; color: #58a6ff; font-weight: 500; }
.progress-bar-container {
  background: #21262d; border-radius: 4px; height: 8px; overflow: hidden; margin-bottom: 6px;
}
.progress-bar {
  height: 100%; background: #1f6feb; border-radius: 4px; transition: width 0.3s ease;
}
.progress-bar-error { background: #f85149; }
.progress-bar-stopped { background: #484f58; }
.task-details { display: flex; align-items: center; gap: 16px; font-size: 13px; color: #8b949e; }
.task-pct { font-weight: 600; color: #e6edf3; }
.task-failed { color: #f85149; }
.task-current { color: #58a6ff; }

/* ── 任务错误信息 ── */
.task-error-message {
  margin-top: 6px; padding: 6px 10px; font-size: 13px; color: #f85149;
  background: #3a1a1a; border: 1px solid #f8514933; border-radius: 4px;
  word-break: break-word;
}

/* ── 导入历史表格 ── */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td {
  padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 14px;
}
.data-table th { color: #8b949e; font-weight: 500; }
.data-table td { color: #e6edf3; }
.api-name-cell { font-family: monospace; color: #58a6ff; }

/* ── 历史错误信息 ── */
.history-error-message {
  margin-top: 4px; font-size: 12px; color: #f85149; word-break: break-word;
}

/* ── 批量选择 ── */
.batch-select-header {
  display: flex; align-items: center; padding: 6px 0; margin-bottom: 4px;
  border-bottom: 1px solid #21262d;
}
.batch-checkbox-label {
  display: flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 13px; color: #8b949e; user-select: none;
}
.batch-checkbox {
  width: 16px; height: 16px; accent-color: #1f6feb; cursor: pointer;
}
.batch-import-bar {
  display: flex; justify-content: flex-end; padding: 10px 0 4px;
  border-top: 1px solid #21262d; margin-top: 4px;
}
.btn-batch-import {
  padding: 6px 20px; font-size: 13px; font-weight: 500;
}
</style>
