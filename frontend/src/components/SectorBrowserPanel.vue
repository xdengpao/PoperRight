<template>
  <div class="sector-browser-panel">
    <!-- 标签页导航 -->
    <div class="browser-tabs" role="tablist" aria-label="板块数据浏览">
      <button
        v-for="tab in browserTabs"
        :key="tab.key"
        role="tab"
        :aria-selected="sectorStore.browserActiveTab === tab.key"
        :class="['tab-btn', { active: sectorStore.browserActiveTab === tab.key }]"
        @click="sectorStore.setBrowserTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ═══ 板块数据标签页 ═══ -->
    <div v-show="sectorStore.browserActiveTab === 'info'" role="tabpanel" class="tab-panel">
      <!-- 筛选条件 -->
      <div class="filter-bar">
        <div class="source-selector">
          <span class="source-label">数据源：</span>
          <button
            v-for="src in dataSourceOptions"
            :key="src.key"
            :class="['source-btn', { active: sectorStore.infoBrowse.filters.data_source === src.key }]"
            @click="sectorStore.updateInfoFilters({ data_source: src.key })"
          >
            {{ src.label }}
          </button>
        </div>
        <select
          class="input filter-select"
          :value="sectorStore.infoBrowse.filters.sector_type"
          aria-label="板块类型筛选"
          @change="sectorStore.updateInfoFilters({ sector_type: ($event.target as HTMLSelectElement).value })"
        >
          <option value="">全部</option>
          <option value="INDUSTRY">行业</option>
          <option value="CONCEPT">概念</option>
          <option value="REGION">地区</option>
          <option value="STYLE">风格</option>
        </select>
        <input
          class="input filter-input"
          placeholder="搜索板块名称或代码"
          :value="sectorStore.infoBrowse.filters.keyword"
          aria-label="板块搜索"
          @change="sectorStore.updateInfoFilters({ keyword: ($event.target as HTMLInputElement).value })"
        />
      </div>

      <!-- 错误状态 -->
      <div v-if="sectorStore.infoBrowse.error" class="error-banner-inline">
        {{ sectorStore.infoBrowse.error }}
        <button class="btn retry-btn" @click="sectorStore.fetchSectorInfoBrowse()">重试</button>
      </div>
      <!-- 加载状态 -->
      <div v-else-if="sectorStore.infoBrowse.loading" class="loading-text">加载中...</div>
      <!-- 数据表格 -->
      <template v-else>
        <table v-if="sectorStore.infoBrowse.items.length > 0" class="data-table" aria-label="板块数据表">
          <thead>
            <tr>
              <th scope="col">板块代码</th>
              <th scope="col">板块名称</th>
              <th scope="col">板块类型</th>
              <th scope="col">数据来源</th>
              <th scope="col">上市日期</th>
              <th scope="col">成分股数量</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in sectorStore.infoBrowse.items" :key="item.sector_code">
              <td>{{ item.sector_code }}</td>
              <td>{{ item.name }}</td>
              <td>{{ item.sector_type }}</td>
              <td>{{ item.data_source }}</td>
              <td>{{ item.list_date ?? '--' }}</td>
              <td>{{ item.constituent_count ?? '--' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无数据</div>
      </template>

      <!-- 分页控件 -->
      <div v-if="sectorStore.infoBrowse.items.length > 0 || sectorStore.infoBrowse.total > 0" class="pagination">
        <button :disabled="sectorStore.infoBrowse.page <= 1" @click="sectorStore.fetchSectorInfoBrowse(sectorStore.infoBrowse.page - 1)">上一页</button>
        <span>第 {{ sectorStore.infoBrowse.page }} / {{ infoTotalPages }} 页（共 {{ sectorStore.infoBrowse.total }} 条）</span>
        <button :disabled="sectorStore.infoBrowse.page >= infoTotalPages" @click="sectorStore.fetchSectorInfoBrowse(sectorStore.infoBrowse.page + 1)">下一页</button>
      </div>
    </div>

    <!-- ═══ 板块成分标签页 ═══ -->
    <div v-show="sectorStore.browserActiveTab === 'constituent'" role="tabpanel" class="tab-panel">
      <!-- 筛选条件 -->
      <div class="filter-bar">
        <div class="source-selector">
          <span class="source-label">数据源：</span>
          <button
            v-for="src in dataSourceOptionsRequired"
            :key="src.key"
            :class="['source-btn', { active: sectorStore.constituentBrowse.filters.data_source === src.key }]"
            @click="sectorStore.updateConstituentFilters({ data_source: src.key })"
          >
            {{ src.label }}
          </button>
        </div>
        <input
          class="input filter-input"
          placeholder="板块代码"
          :value="sectorStore.constituentBrowse.filters.sector_code"
          aria-label="板块代码"
          @change="sectorStore.updateConstituentFilters({ sector_code: ($event.target as HTMLInputElement).value })"
        />
        <input
          class="input filter-input"
          type="date"
          :value="sectorStore.constituentBrowse.filters.trade_date"
          aria-label="交易日期"
          @change="sectorStore.updateConstituentFilters({ trade_date: ($event.target as HTMLInputElement).value })"
        />
        <input
          class="input filter-input"
          placeholder="搜索股票代码或名称"
          :value="sectorStore.constituentBrowse.filters.keyword"
          aria-label="股票搜索"
          @change="sectorStore.updateConstituentFilters({ keyword: ($event.target as HTMLInputElement).value })"
        />
      </div>

      <!-- 错误状态 -->
      <div v-if="sectorStore.constituentBrowse.error" class="error-banner-inline">
        {{ sectorStore.constituentBrowse.error }}
        <button class="btn retry-btn" @click="sectorStore.fetchConstituentBrowse()">重试</button>
      </div>
      <!-- 加载状态 -->
      <div v-else-if="sectorStore.constituentBrowse.loading" class="loading-text">加载中...</div>
      <!-- 数据表格 -->
      <template v-else>
        <table v-if="sectorStore.constituentBrowse.items.length > 0" class="data-table" aria-label="板块成分表">
          <thead>
            <tr>
              <th scope="col">交易日期</th>
              <th scope="col">板块代码</th>
              <th scope="col">数据来源</th>
              <th scope="col">股票代码</th>
              <th scope="col">股票名称</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in sectorStore.constituentBrowse.items" :key="idx">
              <td>{{ item.trade_date }}</td>
              <td>{{ item.sector_code }}</td>
              <td>{{ item.data_source }}</td>
              <td>{{ item.symbol }}</td>
              <td>{{ item.stock_name ?? '--' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无数据</div>
      </template>

      <!-- 分页控件 -->
      <div v-if="sectorStore.constituentBrowse.items.length > 0 || sectorStore.constituentBrowse.total > 0" class="pagination">
        <button :disabled="sectorStore.constituentBrowse.page <= 1" @click="sectorStore.fetchConstituentBrowse(sectorStore.constituentBrowse.page - 1)">上一页</button>
        <span>第 {{ sectorStore.constituentBrowse.page }} / {{ constituentTotalPages }} 页（共 {{ sectorStore.constituentBrowse.total }} 条）</span>
        <button :disabled="sectorStore.constituentBrowse.page >= constituentTotalPages" @click="sectorStore.fetchConstituentBrowse(sectorStore.constituentBrowse.page + 1)">下一页</button>
      </div>
    </div>

    <!-- ═══ 板块行情标签页 ═══ -->
    <div v-show="sectorStore.browserActiveTab === 'kline'" role="tabpanel" class="tab-panel">
      <!-- 筛选条件 -->
      <div class="filter-bar">
        <div class="source-selector">
          <span class="source-label">数据源：</span>
          <button
            v-for="src in dataSourceOptionsRequired"
            :key="src.key"
            :class="['source-btn', { active: sectorStore.klineBrowse.filters.data_source === src.key }]"
            @click="sectorStore.updateKlineFilters({ data_source: src.key })"
          >
            {{ src.label }}
          </button>
        </div>
        <input
          class="input filter-input"
          placeholder="板块代码"
          :value="sectorStore.klineBrowse.filters.sector_code"
          aria-label="板块代码"
          @change="sectorStore.updateKlineFilters({ sector_code: ($event.target as HTMLInputElement).value })"
        />
        <select
          class="input filter-select"
          :value="sectorStore.klineBrowse.filters.freq"
          aria-label="K线频率"
          @change="sectorStore.updateKlineFilters({ freq: ($event.target as HTMLSelectElement).value })"
        >
          <option value="1d">日K</option>
          <option value="1w">周K</option>
          <option value="1M">月K</option>
        </select>
        <input
          class="input filter-input"
          type="date"
          :value="sectorStore.klineBrowse.filters.start"
          aria-label="开始日期"
          @change="sectorStore.updateKlineFilters({ start: ($event.target as HTMLInputElement).value })"
        />
        <input
          class="input filter-input"
          type="date"
          :value="sectorStore.klineBrowse.filters.end"
          aria-label="结束日期"
          @change="sectorStore.updateKlineFilters({ end: ($event.target as HTMLInputElement).value })"
        />
      </div>

      <!-- 错误状态 -->
      <div v-if="sectorStore.klineBrowse.error" class="error-banner-inline">
        {{ sectorStore.klineBrowse.error }}
        <button class="btn retry-btn" @click="sectorStore.fetchKlineBrowse()">重试</button>
      </div>
      <!-- 加载状态 -->
      <div v-else-if="sectorStore.klineBrowse.loading" class="loading-text">加载中...</div>
      <!-- 数据表格 -->
      <template v-else>
        <table v-if="sectorStore.klineBrowse.items.length > 0" class="data-table" aria-label="板块行情表">
          <thead>
            <tr>
              <th scope="col">时间</th>
              <th scope="col">板块代码</th>
              <th scope="col">开盘</th>
              <th scope="col">最高</th>
              <th scope="col">最低</th>
              <th scope="col">收盘</th>
              <th scope="col">成交量</th>
              <th scope="col">成交额</th>
              <th scope="col">涨跌幅</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in sectorStore.klineBrowse.items" :key="idx">
              <td>{{ item.time }}</td>
              <td>{{ item.sector_code }}</td>
              <td>{{ item.open != null ? item.open.toFixed(2) : '--' }}</td>
              <td>{{ item.high != null ? item.high.toFixed(2) : '--' }}</td>
              <td>{{ item.low != null ? item.low.toFixed(2) : '--' }}</td>
              <td>{{ item.close != null ? item.close.toFixed(2) : '--' }}</td>
              <td>{{ item.volume != null ? item.volume : '--' }}</td>
              <td>{{ item.amount != null ? item.amount.toFixed(2) : '--' }}</td>
              <td :class="getChangePctClass(item.change_pct)">
                {{ formatChangePct(item.change_pct) }}
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无数据</div>
      </template>

      <!-- 分页控件 -->
      <div v-if="sectorStore.klineBrowse.items.length > 0 || sectorStore.klineBrowse.total > 0" class="pagination">
        <button :disabled="sectorStore.klineBrowse.page <= 1" @click="sectorStore.fetchKlineBrowse(sectorStore.klineBrowse.page - 1)">上一页</button>
        <span>第 {{ sectorStore.klineBrowse.page }} / {{ klineTotalPages }} 页（共 {{ sectorStore.klineBrowse.total }} 条）</span>
        <button :disabled="sectorStore.klineBrowse.page >= klineTotalPages" @click="sectorStore.fetchKlineBrowse(sectorStore.klineBrowse.page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSectorStore } from '@/stores/sector'
import type { BrowserTab } from '@/stores/sector'

const sectorStore = useSectorStore()

// 标签页定义
const browserTabs: { key: BrowserTab; label: string }[] = [
  { key: 'info', label: '板块数据' },
  { key: 'constituent', label: '板块成分' },
  { key: 'kline', label: '板块行情' },
]

// 数据源选项（板块数据标签页，DC/TI/TDX）
const dataSourceOptions = [
  { key: 'DC', label: '东方财富' },
  { key: 'TI', label: '同花顺' },
  { key: 'TDX', label: '通达信' },
]

// 数据源选项（成分/行情标签页，必填 data_source）
const dataSourceOptionsRequired = dataSourceOptions

// ─── 分页计算属性 ────────────────────────────────────────────────────────────

const infoTotalPages = computed(() =>
  Math.max(1, Math.ceil(sectorStore.infoBrowse.total / sectorStore.infoBrowse.pageSize)),
)

const constituentTotalPages = computed(() =>
  Math.max(1, Math.ceil(sectorStore.constituentBrowse.total / sectorStore.constituentBrowse.pageSize)),
)

const klineTotalPages = computed(() =>
  Math.max(1, Math.ceil(sectorStore.klineBrowse.total / sectorStore.klineBrowse.pageSize)),
)

// ─── 行情涨跌幅格式化 ───────────────────────────────────────────────────────

function getChangePctClass(changePct: number | null): string {
  if (changePct == null) return ''
  return changePct >= 0 ? 'up' : 'down'
}

function formatChangePct(changePct: number | null): string {
  if (changePct == null) return '--'
  return (changePct >= 0 ? '+' : '') + changePct.toFixed(2) + '%'
}
</script>

<style scoped>
.sector-browser-panel {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  overflow: hidden;
}

/* 标签页导航 */
.browser-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #30363d;
}

.tab-btn {
  background: transparent;
  border: none;
  color: #8b949e;
  padding: 10px 20px;
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}
.tab-btn:hover { color: #e6edf3; }
.tab-btn.active {
  color: #e6edf3;
  border-bottom-color: #238636;
  font-weight: 500;
}

/* 标签页面板 */
.tab-panel {
  padding: 12px;
}

/* 筛选条件栏 */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.source-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}
.source-label { font-size: 12px; color: #8b949e; }
.source-btn {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #8b949e;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}
.source-btn:hover { color: #e6edf3; border-color: #484f58; }
.source-btn.active {
  color: #e6edf3;
  border-color: #238636;
  background: #161b22;
  font-weight: 500;
}

.input {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
}
.filter-select { min-width: 80px; }
.filter-input { min-width: 120px; }

/* 数据表格 */
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: #161b22;
  border-radius: 8px;
  overflow: hidden;
}
.data-table th,
.data-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid #21262d;
  font-size: 13px;
}
.data-table th {
  color: #8b949e;
  font-weight: 500;
  background: #161b22;
}
.data-table td { color: #e6edf3; }

/* 涨跌颜色 */
.up { color: #f85149; }
.down { color: #3fb950; }

/* 状态提示 */
.loading-text {
  color: #8b949e;
  font-size: 14px;
  padding: 24px 0;
  text-align: center;
}
.empty {
  text-align: center;
  color: #484f58;
  padding: 24px;
}
.error-banner-inline {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #f85149;
  font-size: 14px;
  padding: 16px 0;
}

.btn {
  background: #238636;
  color: #fff;
  border: none;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.btn:hover { background: #2ea043; }
.retry-btn { font-size: 12px; padding: 4px 12px; }

/* 分页控件 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 0 4px;
}
.pagination button {
  background: #0d1117;
  border: 1px solid #30363d;
  color: #e6edf3;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.pagination button:hover:not(:disabled) {
  border-color: #484f58;
}
.pagination button:disabled {
  color: #484f58;
  cursor: not-allowed;
}
.pagination span {
  font-size: 12px;
  color: #8b949e;
}
</style>
