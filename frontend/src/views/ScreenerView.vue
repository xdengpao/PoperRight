<template>
  <div class="screener">
    <h1 class="page-title">智能选股</h1>

    <!-- 错误提示 -->
    <ErrorBanner v-if="pageError" :message="pageError" :retryFn="() => loadStrategies()" />

    <!-- 策略模板列表 -->
    <section class="card" aria-label="策略模板">
      <div class="section-header">
        <h2 class="section-title">策略模板</h2>
        <div class="header-actions">
          <!-- 导入按钮 -->
          <label class="btn btn-outline" role="button" tabindex="0" aria-label="导入策略模板">
            <input
              ref="importInputRef"
              type="file"
              accept=".json"
              class="hidden-input"
              @change="onImportFile"
            />
            📥 导入
          </label>
          <button
            class="btn btn-outline"
            @click="showCreateDialog = true"
            :disabled="strategies.length >= MAX_STRATEGIES"
            :title="strategies.length >= MAX_STRATEGIES ? '已达策略上限（20 套）' : '新建策略'"
          >＋ 新建策略</button>
          <span v-if="strategies.length >= MAX_STRATEGIES" class="limit-hint">已达策略上限（20 套）</span>
        </div>
      </div>

      <LoadingSpinner v-if="strategiesLoading" text="加载策略中..." />

      <div v-else-if="strategies.length === 0" class="empty">暂无策略模板，点击「新建策略」创建</div>

      <div v-else class="strategy-list">
        <div
          v-for="s in strategies"
          :key="s.id"
          class="strategy-item"
          :class="{ active: activeStrategyId === s.id }"
          @click="selectStrategy(s.id)"
        >
          <div class="strategy-info">
            <span class="strategy-name">{{ s.name }}</span>
            <span v-if="s.is_active" class="active-badge">当前</span>
          </div>
          <div class="strategy-meta">
            <span class="strategy-date">{{ s.created_at?.slice(0, 10) ?? '—' }}</span>
          </div>
          <div class="strategy-actions" @click.stop>
            <button class="btn-icon" title="重命名策略" @click="startRename(s.id, s.name)">✏️</button>
            <button class="btn-icon" title="导出策略" @click="exportStrategy(s)">📤</button>
            <button class="btn-icon danger" title="删除策略" @click="confirmDelete(s)">🗑</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 管理模块 + 保存修改按钮栏（仅当有策略选中时显示） -->
    <div v-if="activeStrategyId" class="module-manage-bar card">
      <button class="btn btn-outline" @click="openModulesDialog">
        ⚙️ 管理模块
      </button>
      <span class="module-summary">已启用 {{ currentEnabledModules.length }} 个模块</span>
      <button
        class="btn btn-save"
        @click="saveStrategy"
        :disabled="saving"
        aria-label="保存修改"
      >
        <span v-if="saving" class="spinner" aria-hidden="true"></span>
        {{ saving ? '保存中...' : '💾 保存修改' }}
      </button>
      <span v-if="saveSuccess" class="save-success">✓ 保存成功</span>
    </div>

    <!-- 因子条件可视化编辑器 -->
    <section v-if="isModuleEnabled('factor_editor')" class="card" aria-label="因子条件编辑器">
      <div class="section-header">
        <h2 class="section-title">因子条件编辑器</h2>
        <!-- AND/OR 逻辑切换 -->
        <div class="logic-toggle" role="group" aria-label="逻辑运算">
          <button
            :class="['logic-btn', config.logic === 'AND' && 'active']"
            @click="config.logic = 'AND'"
          >AND（全部满足）</button>
          <button
            :class="['logic-btn', config.logic === 'OR' && 'active']"
            @click="config.logic = 'OR'"
          >OR（满足其一）</button>
        </div>
        <div class="group-rule-controls">
          <select v-model="groupRules.confirmation_logic" class="input group-rule-select" aria-label="确认因子逻辑">
            <option value="OR">确认 OR</option>
            <option value="AND">确认 AND</option>
            <option value="AT_LEAST_N">至少 N 个</option>
          </select>
          <input
            v-if="groupRules.confirmation_logic === 'AT_LEAST_N'"
            v-model.number="groupRules.confirmation_min_pass_count"
            type="number"
            min="1"
            class="input group-min-input"
            aria-label="确认因子最少通过数量"
          />
          <label class="group-blocking-toggle">
            <input v-model="groupRules.confirmation_blocking" type="checkbox" />
            <span>确认拦截</span>
          </label>
        </div>
        <button class="btn btn-outline btn-sm" @click="showExamplesDialog = true">📋 加载示例策略</button>
      </div>

      <!-- 因子条件列表 -->
      <div class="factor-list">
        <div
          v-for="(factor, idx) in config.factors"
          :key="idx"
          class="factor-row"
          @click="selectedFactorName = factor.factor_name"
        >
          <div class="factor-type-badge" :class="factor.type">
            {{ factorTypeLabel(factor.type) }}
          </div>

          <select v-model="factor.type" class="input factor-type-select" :aria-label="`因子类型 ${idx + 1}`"
            @change="factor.factor_name = factorNameOptions[factor.type]?.[0]?.value ?? ''"
          >
            <option v-for="ft in factorTypes" :key="ft.key" :value="ft.key">{{ ft.label }}</option>
          </select>

          <div class="factor-name-wrapper" :title="getFactorMeta(factor.factor_name)?.description ?? ''">
            <select
              v-model="factor.factor_name"
              class="input factor-name"
              :aria-label="`因子名称 ${idx + 1}`"
              @change="selectedFactorName = factor.factor_name"
            >
              <option value="" disabled>选择因子</option>
              <option
                v-for="opt in factorNameOptions[factor.type]"
                :key="opt.value"
                :value="opt.value"
              >{{ opt.label }}</option>
            </select>
          </div>

          <span class="threshold-type-badge" :class="getFactorThresholdType(factor.factor_name)">
            {{ thresholdTypeLabel(getFactorThresholdType(factor.factor_name)) }}
          </span>

          <select v-model="factor.role" class="input factor-role-select" :aria-label="`因子角色 ${idx + 1}`">
            <option v-for="role in factorRoleOptions" :key="role.value" :value="role.value">
              {{ role.label }}
            </option>
          </select>

          <!-- Boolean type: toggle switch, hide operator -->
          <template v-if="getFactorThresholdType(factor.factor_name) === 'boolean'">
            <label class="toggle-switch factor-toggle">
              <input type="checkbox" :checked="factor.threshold !== 0" @change="factor.threshold = ($event.target as HTMLInputElement).checked ? null : 0" />
              <span class="toggle-track"></span>
            </label>
          </template>

          <!-- Range type: dual inputs -->
          <template v-else-if="getFactorThresholdType(factor.factor_name) === 'range'">
            <div class="range-inputs">
              <input v-model.number="(factor.params as Record<string, unknown>).threshold_low" type="number" class="input factor-threshold-half" placeholder="下限" :aria-label="`下限 ${idx + 1}`" />
              <span class="range-sep">–</span>
              <input v-model.number="(factor.params as Record<string, unknown>).threshold_high" type="number" class="input factor-threshold-half" placeholder="上限" :aria-label="`上限 ${idx + 1}`" />
            </div>
          </template>

          <!-- Default: existing threshold input + operator -->
          <template v-else>
            <select v-model="factor.operator" class="input factor-op" :aria-label="`运算符 ${idx + 1}`">
              <option value=">">&gt;</option>
              <option value=">=">&gt;=</option>
              <option value="<">&lt;</option>
              <option value="<=">&lt;=</option>
              <option value="==">==</option>
            </select>

            <input
              v-model.number="factor.threshold"
              type="number"
              class="input factor-threshold"
              placeholder="阈值"
              :aria-label="`阈值 ${idx + 1}`"
            />
          </template>

          <span v-if="getFactorMeta(factor.factor_name)?.unit" class="factor-unit">
            {{ getFactorMeta(factor.factor_name)?.unit }}
          </span>
          <span v-if="getFactorMeta(factor.factor_name)?.value_min != null" class="factor-range-hint">
            ({{ getFactorMeta(factor.factor_name)?.value_min }}–{{ getFactorMeta(factor.factor_name)?.value_max }})
          </span>

          <!-- Money-flow source selector: 策略级资金流数据源 -->
          <div v-if="isMoneyFlowSourceFactor(factor.factor_name)" class="factor-source-selectors">
            <select
              :value="volumePriceConfig.money_flow_source"
              @change="onMoneyFlowSourceChange(($event.target as HTMLSelectElement).value)"
              class="input factor-source-select"
              aria-label="资金流数据源"
            >
              <option
                v-for="opt in getMoneyFlowSourceOptions(factor.factor_name)"
                :key="opt.value"
                :value="opt.value"
              >
                {{ formatDataSourceOptionLabel(opt) }}
              </option>
            </select>
            <span class="factor-source-scope">策略级</span>
          </div>
          <div
            v-if="isMoneyFlowSourceFactor(factor.factor_name) && volumePriceConfig.money_flow_source === 'money_flow'"
            class="factor-source-warning"
            role="alert"
          >
            旧资金流表覆盖不足，建议使用东方财富或同花顺资金流。
          </div>

          <!-- Sector-specific selectors: 两级下拉（需求 22.6, 22.7） -->
          <div v-if="isSectorSourceFactor(factor.factor_name)" class="sector-selectors">
            <select
              :value="sectorConfig.sector_data_source"
              @change="onDataSourceChange(($event.target as HTMLSelectElement).value)"
              class="input sector-select sector-source-select"
              aria-label="数据来源"
            >
              <option v-for="opt in sectorDataSourceOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select
              :value="sectorConfig.sector_type"
              @change="sectorConfig.sector_type = ($event.target as HTMLSelectElement).value || null"
              class="input sector-select sector-type-select"
              aria-label="板块类型"
            >
              <option v-for="opt in sectorTypeOptions" :key="String(opt.value)" :value="opt.value ?? ''">{{ opt.label }}</option>
            </select>
            <div class="sector-period-input">
              <input v-model.number="sectorConfig.sector_period" type="number" min="1" max="60" class="input param-input" aria-label="涨幅周期" />
              <span class="param-hint">天</span>
            </div>
          </div>
          <div v-if="isSectorSourceFactor(factor.factor_name) && selectedSourceCoverage && selectedSourceCoverage.sectors_with_constituents < selectedSourceCoverage.total_sectors * 0.1" class="sector-coverage-warning" role="alert">
            ⚠️ {{ sectorConfig.sector_data_source }} 仅 {{ selectedSourceCoverage.sectors_with_constituents }}/{{ selectedSourceCoverage.total_sectors }} 个板块有成分股映射，大部分股票无法匹配到板块，板块涨幅排名和板块趋势因子将无法生效。请前往「Tushare 数据导入」页面导入对应的板块成分数据{{ bestAlternativeSource ? `，或切换到数据更完整的${bestAlternativeSource}` : '' }}。
          </div>

          <!-- 权重滑块 -->
          <div class="weight-control">
            <label :for="`weight-${idx}`" class="weight-label">权重</label>
            <input
              :id="`weight-${idx}`"
              v-model.number="factor.weight"
              type="range"
              min="0"
              max="100"
              step="1"
              class="weight-slider"
            />
            <span class="weight-value">{{ factor.weight }}</span>
          </div>

          <button class="btn-icon" title="恢复默认" @click="resetFactorDefault(idx)" aria-label="恢复默认">↺</button>
          <button class="btn-icon danger" @click="removeFactor(idx)" :aria-label="`删除因子 ${idx + 1}`">✕</button>
        </div>

        <div v-if="config.factors.length === 0" class="empty-factors">
          暂无因子条件，点击下方按钮添加
        </div>
      </div>

      <!-- 因子使用说明面板 -->
      <FactorUsagePanel :factor-name="selectedFactorName" />

      <!-- 添加因子按钮组 -->
      <div class="add-factor-row">
        <span class="add-label">添加因子：</span>
        <button
          v-for="ft in factorTypes"
          :key="ft.key"
          class="btn btn-outline btn-sm"
          @click="addFactor(ft.key)"
        >＋ {{ ft.label }}</button>
      </div>
    </section>

    <!-- 均线趋势配置 -->
    <section v-if="isModuleEnabled('ma_trend')" class="card" aria-label="均线趋势配置">
      <details>
        <summary class="panel-summary">
          <span class="section-title">均线趋势配置</span>
          <span class="panel-hint">MA Trend</span>
        </summary>

        <div class="panel-body">
          <!-- 均线周期组合 -->
          <div class="panel-row">
            <label class="panel-label">均线周期组合</label>
            <div class="tag-input-area">
              <span
                v-for="p in maTrend.ma_periods"
                :key="p"
                class="period-tag"
              >
                {{ p }} 日
                <button class="tag-remove" @click="removeMaPeriod(p)" :aria-label="`删除 ${p} 日均线`">×</button>
              </span>
              <div class="tag-add-row">
                <input
                  v-model.number="newPeriodInput"
                  type="number"
                  min="1"
                  step="1"
                  class="input period-input"
                  placeholder="周期"
                  @keyup.enter="addMaPeriod"
                  aria-label="新增均线周期"
                />
                <button class="btn btn-outline btn-sm" @click="addMaPeriod">＋ 添加</button>
              </div>
            </div>
          </div>

          <!-- 多头排列斜率阈值 -->
          <div class="panel-row">
            <label class="panel-label" for="slope-threshold">多头排列斜率阈值</label>
            <input
              id="slope-threshold"
              v-model.number="maTrend.slope_threshold"
              type="number"
              step="0.01"
              class="input param-input"
              aria-label="多头排列斜率阈值"
            />
          </div>

          <!-- 趋势打分阈值 -->
          <div class="panel-row">
            <label class="panel-label" for="trend-score-threshold">趋势打分阈值</label>
            <div class="slider-row">
              <input
                id="trend-score-threshold"
                v-model.number="maTrend.trend_score_threshold"
                type="range"
                min="0"
                max="100"
                step="1"
                class="trend-slider"
                aria-label="趋势打分阈值"
              />
              <span class="slider-value">{{ maTrend.trend_score_threshold }}</span>
            </div>
          </div>

          <!-- 均线支撑回调均线 -->
          <div class="panel-row">
            <label class="panel-label">均线支撑回调均线</label>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  :checked="maTrend.support_ma_lines.includes(20)"
                  @change="toggleSupportMa(20)"
                />
                20 日
              </label>
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  :checked="maTrend.support_ma_lines.includes(60)"
                  @change="toggleSupportMa(60)"
                />
                60 日
              </label>
            </div>
          </div>
        </div>
      </details>
    </section>

    <!-- 技术指标配置 -->
    <section v-if="isModuleEnabled('indicator_params')" class="card" aria-label="技术指标配置">
      <details>
        <summary class="panel-summary">
          <span class="section-title">技术指标配置</span>
          <span class="panel-hint">Indicator Params</span>
        </summary>

        <div class="panel-body">

          <!-- MACD 面板 -->
          <details class="indicator-group">
            <summary class="indicator-summary">
              <span class="indicator-title">MACD</span>
              <button
                class="btn-reset"
                @click.stop="resetIndicator('macd')"
                title="恢复 MACD 默认值"
              >恢复默认</button>
            </summary>
            <div class="indicator-body">
              <div class="param-row">
                <label class="param-label" for="macd-fast">
                  快线周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.macd.fast_period }}</span>
                </label>
                <input
                  id="macd-fast"
                  v-model.number="indicatorParams.macd.fast_period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="MACD 快线周期"
                />
              </div>
              <div class="param-row">
                <label class="param-label" for="macd-slow">
                  慢线周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.macd.slow_period }}</span>
                </label>
                <input
                  id="macd-slow"
                  v-model.number="indicatorParams.macd.slow_period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="MACD 慢线周期"
                />
              </div>
              <div class="param-row">
                <label class="param-label" for="macd-signal">
                  信号线周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.macd.signal_period }}</span>
                </label>
                <input
                  id="macd-signal"
                  v-model.number="indicatorParams.macd.signal_period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="MACD 信号线周期"
                />
              </div>
            </div>
          </details>

          <!-- BOLL 面板 -->
          <details class="indicator-group">
            <summary class="indicator-summary">
              <span class="indicator-title">BOLL</span>
              <button
                class="btn-reset"
                @click.stop="resetIndicator('boll')"
                title="恢复 BOLL 默认值"
              >恢复默认</button>
            </summary>
            <div class="indicator-body">
              <div class="param-row">
                <label class="param-label" for="boll-period">
                  周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.boll.period }}</span>
                </label>
                <input
                  id="boll-period"
                  v-model.number="indicatorParams.boll.period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="BOLL 周期"
                />
              </div>
              <div class="param-row">
                <label class="param-label" for="boll-std">
                  标准差倍数
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.boll.std_dev }}</span>
                </label>
                <input
                  id="boll-std"
                  v-model.number="indicatorParams.boll.std_dev"
                  type="number"
                  min="0.1"
                  step="0.1"
                  class="input param-input"
                  aria-label="BOLL 标准差倍数"
                />
              </div>
            </div>
          </details>

          <!-- RSI 面板 -->
          <details class="indicator-group">
            <summary class="indicator-summary">
              <span class="indicator-title">RSI</span>
              <button
                class="btn-reset"
                @click.stop="resetIndicator('rsi')"
                title="恢复 RSI 默认值"
              >恢复默认</button>
            </summary>
            <div class="indicator-body">
              <div class="param-row">
                <label class="param-label" for="rsi-period">
                  周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.rsi.period }}</span>
                </label>
                <input
                  id="rsi-period"
                  v-model.number="indicatorParams.rsi.period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="RSI 周期"
                />
              </div>
              <div class="param-row">
                <label class="param-label">
                  强势区间
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.rsi.lower_bound }}–{{ INDICATOR_DEFAULTS.rsi.upper_bound }}</span>
                </label>
                <div class="rsi-range">
                  <div class="rsi-slider-row">
                    <span class="rsi-bound-label">下限</span>
                    <input
                      v-model.number="indicatorParams.rsi.lower_bound"
                      type="range"
                      min="0"
                      max="100"
                      step="1"
                      class="trend-slider"
                      aria-label="RSI 强势区间下限"
                    />
                    <span class="slider-value">{{ indicatorParams.rsi.lower_bound }}</span>
                  </div>
                  <div class="rsi-slider-row">
                    <span class="rsi-bound-label">上限</span>
                    <input
                      v-model.number="indicatorParams.rsi.upper_bound"
                      type="range"
                      min="0"
                      max="100"
                      step="1"
                      class="trend-slider"
                      aria-label="RSI 强势区间上限"
                    />
                    <span class="slider-value">{{ indicatorParams.rsi.upper_bound }}</span>
                  </div>
                </div>
              </div>
            </div>
          </details>

          <!-- DMA 面板 -->
          <details class="indicator-group">
            <summary class="indicator-summary">
              <span class="indicator-title">DMA</span>
              <button
                class="btn-reset"
                @click.stop="resetIndicator('dma')"
                title="恢复 DMA 默认值"
              >恢复默认</button>
            </summary>
            <div class="indicator-body">
              <div class="param-row">
                <label class="param-label" for="dma-short">
                  短期周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.dma.short_period }}</span>
                </label>
                <input
                  id="dma-short"
                  v-model.number="indicatorParams.dma.short_period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="DMA 短期周期"
                />
              </div>
              <div class="param-row">
                <label class="param-label" for="dma-long">
                  长期周期
                  <span class="param-default">默认 {{ INDICATOR_DEFAULTS.dma.long_period }}</span>
                </label>
                <input
                  id="dma-long"
                  v-model.number="indicatorParams.dma.long_period"
                  type="number"
                  min="1"
                  step="1"
                  class="input param-input"
                  aria-label="DMA 长期周期"
                />
              </div>
            </div>
          </details>

        </div>
      </details>
    </section>

    <!-- 形态突破配置 -->
    <section v-if="isModuleEnabled('breakout')" class="card" aria-label="形态突破配置">
      <details>
        <summary class="panel-summary">
          <span class="section-title">形态突破配置</span>
          <span class="panel-hint">Breakout</span>
        </summary>
        <div class="panel-body">
          <!-- 突破形态开关 -->
          <div class="panel-row">
            <label class="panel-label">突破形态</label>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="breakoutConfig.box_breakout" />
                箱体突破
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="breakoutConfig.high_breakout" />
                前期高点突破
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="breakoutConfig.trendline_breakout" />
                下降趋势线突破
              </label>
            </div>
          </div>
          <!-- 量比倍数阈值 -->
          <div class="panel-row">
            <label class="panel-label" for="volume-ratio">量比倍数阈值</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <input
                id="volume-ratio"
                v-model.number="breakoutConfig.volume_ratio_threshold"
                type="number"
                min="0.1"
                step="0.1"
                class="input param-input"
                aria-label="量比倍数阈值"
              />
              <span style="font-size:13px;color:#8b949e;">倍近 20 日均量</span>
            </div>
          </div>
          <!-- 站稳确认天数 -->
          <div class="panel-row">
            <label class="panel-label" for="confirm-days">站稳确认天数</label>
            <input
              id="confirm-days"
              v-model.number="breakoutConfig.confirm_days"
              type="number"
              min="1"
              step="1"
              class="input param-input"
              aria-label="站稳确认天数"
            />
          </div>
        </div>
      </details>
    </section>

    <!-- 量价资金筛选 -->
    <section v-if="isModuleEnabled('volume_price')" class="card" aria-label="量价资金筛选">
      <details>
        <summary class="panel-summary">
          <span class="section-title">量价资金筛选</span>
          <span class="panel-hint">Volume &amp; Capital</span>
        </summary>
        <div class="panel-body">
          <!-- 换手率区间 -->
          <div class="panel-row">
            <label class="panel-label">换手率区间</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <input
                v-model.number="volumePriceConfig.turnover_rate_min"
                type="number"
                min="0"
                step="0.1"
                class="input param-input"
                aria-label="换手率下限"
                placeholder="下限 %"
              />
              <span style="color:#8b949e;font-size:13px;">—</span>
              <input
                v-model.number="volumePriceConfig.turnover_rate_max"
                type="number"
                min="0"
                step="0.1"
                class="input param-input"
                aria-label="换手率上限"
                placeholder="上限 %"
              />
              <span style="font-size:13px;color:#8b949e;">%</span>
            </div>
          </div>
          <!-- 资金流数据源 -->
          <div class="panel-row">
            <label class="panel-label" for="money-flow-source">资金流数据源</label>
            <select
              id="money-flow-source"
              v-model="volumePriceConfig.money_flow_source"
              class="input param-select"
              aria-label="资金流数据源"
            >
              <option
                v-for="opt in moneyFlowSourceOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ formatDataSourceOptionLabel(opt) }}
              </option>
            </select>
          </div>
          <!-- 主力资金净流入阈值 -->
          <div class="panel-row">
            <label class="panel-label" for="main-flow">主力净流入阈值</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <input
                id="main-flow"
                v-model.number="volumePriceConfig.main_flow_threshold"
                type="number"
                min="0"
                step="100"
                class="input param-input"
                aria-label="主力资金净流入阈值"
              />
              <span style="font-size:13px;color:#8b949e;">万元</span>
            </div>
          </div>
          <!-- 连续净流入天数 -->
          <div class="panel-row">
            <label class="panel-label" for="main-flow-days">连续净流入天数</label>
            <input
              id="main-flow-days"
              v-model.number="volumePriceConfig.main_flow_days"
              type="number"
              min="1"
              step="1"
              class="input param-input"
              aria-label="连续净流入天数"
            />
          </div>
          <!-- 大单成交占比阈值 -->
          <div class="panel-row">
            <label class="panel-label" for="large-order">大单成交占比</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <input
                id="large-order"
                v-model.number="volumePriceConfig.large_order_ratio"
                type="number"
                min="0"
                max="100"
                step="1"
                class="input param-input"
                aria-label="大单成交占比阈值"
              />
              <span style="font-size:13px;color:#8b949e;">%</span>
            </div>
          </div>
          <!-- 日均成交额下限 -->
          <div class="panel-row">
            <label class="panel-label" for="min-amount">日均成交额下限</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <input
                id="min-amount"
                v-model.number="volumePriceConfig.min_daily_amount"
                type="number"
                min="0"
                step="500"
                class="input param-input"
                aria-label="日均成交额下限"
              />
              <span style="font-size:13px;color:#8b949e;">万元</span>
            </div>
          </div>
          <!-- 板块涨幅排名范围 -->
          <div class="panel-row">
            <label class="panel-label" for="sector-rank">板块涨幅排名</label>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:13px;color:#8b949e;">前</span>
              <input
                id="sector-rank"
                v-model.number="volumePriceConfig.sector_rank_top"
                type="number"
                min="1"
                step="1"
                class="input param-input"
                aria-label="板块涨幅排名范围"
              />
            </div>
          </div>
        </div>
      </details>
    </section>

    <!-- 执行选股 -->
    <section class="card run-section" aria-label="执行选股">
      <!-- 策略数量上限提示 -->
      <div v-if="strategies.length >= MAX_STRATEGIES" class="limit-warning" role="alert">
        ⚠️ 已达策略上限（20 套），请删除旧策略后再新建
      </div>

      <!-- 盘后调度状态 -->
      <div v-if="scheduleStatus" class="schedule-status">
        <span class="schedule-label">📅 盘后选股</span>
        <span class="schedule-item">
          下次执行：<strong>{{ formatScheduleTime(scheduleStatus.next_run_at) }}</strong>
        </span>
        <span v-if="scheduleStatus.last_run_at" class="schedule-item">
          上次执行：{{ formatScheduleTime(scheduleStatus.last_run_at) }}
          <span v-if="scheduleStatus.last_run_duration_ms != null">
            （{{ scheduleStatus.last_run_duration_ms }}ms，选出 {{ scheduleStatus.last_run_result_count ?? 0 }} 只）
          </span>
        </span>
      </div>

      <!-- 实时选股开关 -->
      <div class="realtime-row">
        <label class="realtime-label" for="realtime-toggle">实时选股</label>
        <label class="toggle-switch">
          <input
            id="realtime-toggle"
            type="checkbox"
            :checked="realtimeEnabled"
            :disabled="!isTradingHoursComputed"
            @change="toggleRealtime"
            aria-label="实时选股开关"
          />
          <span class="toggle-track"></span>
        </label>
        <span v-if="!isTradingHoursComputed" class="realtime-status muted">非交易时段</span>
        <span v-else-if="realtimeEnabled" class="realtime-status active">
          {{ realtimeCountdown }}s 后刷新 · 最近：{{ lastRefreshTime ?? '—' }}
        </span>
        <span v-else class="realtime-status muted">已关闭</span>
      </div>

      <div class="run-row">
        <div class="run-info">
          <span v-if="activeStrategyId" class="run-hint">
            当前策略：<strong>{{ activeStrategyName }}</strong>
          </span>
          <span v-else class="run-hint muted">未选择策略，将使用当前因子配置执行</span>
        </div>
        <div v-if="factorStatsForRun.length" class="factor-stats-strip" aria-label="因子筛选统计">
          <span
            v-for="stat in factorStatsForRun"
            :key="`${stat.factor_name}-${stat.group_id ?? 'none'}`"
            :class="['factor-stat-pill', stat.role ?? 'unknown']"
            :title="formatFactorStatTooltip(stat)"
          >
            {{ stat.label || stat.factor_name }} 通过 {{ stat.passed_count }} 只<span v-if="stat.missing_count">，缺失 {{ stat.missing_count }} 只</span>
          </span>
        </div>
        <button
          class="btn btn-run"
          @click="runScreen"
          :disabled="running"
          aria-label="执行选股"
        >
          <span v-if="running" class="spinner" aria-hidden="true"></span>
          {{ running ? '选股中...' : '🚀 一键执行选股' }}
        </button>
      </div>
      <p v-if="runError" class="run-error">{{ runError }}</p>
    </section>

    <!-- 新建策略对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="新建策略">
        <h3 class="dialog-title">新建策略模板</h3>
        <label for="new-strategy-name" class="dialog-label">策略名称</label>
        <input
          id="new-strategy-name"
          v-model="newStrategyName"
          class="input full"
          placeholder="输入策略名称"
          @keyup.enter="createStrategy"
        />
        <fieldset class="module-fieldset">
          <legend class="module-legend">配置模块（可选）</legend>
          <p class="module-hint">所有模块均为可选，可不勾选任何模块直接创建空策略</p>
          <label v-for="mod in ALL_MODULES" :key="mod.key" class="checkbox-label">
            <input
              type="checkbox"
              :value="mod.key"
              v-model="newStrategyModules"
            />
            {{ mod.label }}
          </label>
        </fieldset>
        <div class="dialog-actions">
          <button class="btn" @click="createStrategy" :disabled="!newStrategyName.trim()">保存</button>
          <button class="btn btn-outline" @click="showCreateDialog = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 重命名对话框 -->
    <div v-if="renameDialogVisible" class="dialog-overlay" @click.self="renameDialogVisible = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="重命名策略">
        <h3 class="dialog-title">重命名策略</h3>
        <label for="rename-strategy-name" class="dialog-label">策略名称</label>
        <input
          id="rename-strategy-name"
          v-model="renameNewName"
          class="input full"
          placeholder="输入新的策略名称"
          @keyup.enter="confirmRename"
        />
        <div class="dialog-actions">
          <button class="btn" @click="confirmRename" :disabled="!renameNewName.trim() || renaming">
            {{ renaming ? '保存中...' : '确认' }}
          </button>
          <button class="btn btn-outline" @click="renameDialogVisible = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 删除确认对话框 -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="确认删除">
        <h3 class="dialog-title">确认删除</h3>
        <p class="dialog-body">
          确定要删除策略 <strong>「{{ deleteTarget.name }}」</strong> 吗？此操作不可撤销。
        </p>
        <div class="dialog-actions">
          <button class="btn btn-danger" @click="deleteStrategy" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
          <button class="btn btn-outline" @click="deleteTarget = null">取消</button>
        </div>
      </div>
    </div>

    <!-- 管理模块对话框 -->
    <div v-if="showModulesDialog" class="dialog-overlay" @click.self="showModulesDialog = false">
      <div class="dialog" role="dialog" aria-modal="true" aria-label="管理配置模块">
        <h3 class="dialog-title">管理配置模块</h3>
        <fieldset class="module-fieldset">
          <legend class="module-legend">选择要启用的配置模块</legend>
          <label v-for="mod in ALL_MODULES" :key="mod.key" class="checkbox-label">
            <input
              type="checkbox"
              :value="mod.key"
              v-model="editingModules"
            />
            {{ mod.label }}
          </label>
        </fieldset>
        <div class="dialog-actions">
          <button class="btn" @click="saveModules">确认</button>
          <button class="btn btn-outline" @click="showModulesDialog = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 策略示例对话框 -->
    <div v-if="showExamplesDialog" class="dialog-overlay" @click.self="showExamplesDialog = false">
      <div class="dialog dialog-wide" role="dialog" aria-modal="true" aria-label="加载示例策略">
        <h3 class="dialog-title">选择策略示例</h3>
        <div class="example-list">
          <div
            v-for="(ex, idx) in screenerStore.strategyExamples"
            :key="idx"
            class="example-item"
            @click="loadStrategyExample(ex)"
          >
            <div class="example-name">{{ ex.name }}</div>
            <div class="example-desc">{{ ex.description }}</div>
            <div class="example-tags">
              <span v-for="mod in ex.enabled_modules" :key="mod" class="example-tag">{{ mod }}</span>
            </div>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="btn btn-outline" @click="showExamplesDialog = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import FactorUsagePanel from '@/components/FactorUsagePanel.vue'
import { storeToRefs } from 'pinia'
import { useScreenerStore } from '@/stores/screener'
import type { FactorConditionStats, FactorDataSourceOption, FactorMeta, FactorRole, StrategyExample } from '@/stores/screener'

// ─── 类型定义 ─────────────────────────────────────────────────────────────────

type FactorType = 'technical' | 'capital' | 'fundamental' | 'sector' | 'chip' | 'margin' | 'board_hit'

interface FactorCondition {
  type: FactorType
  factor_name: string
  operator: string
  threshold: number | null
  weight: number
  params: Record<string, unknown>
  role: FactorRole
  group_id: string | null
}

interface FactorGroupConfig {
  group_id: string
  label: string
  role: FactorRole
  logic: 'AND' | 'OR' | 'AT_LEAST_N' | 'SCORE_ONLY'
  factor_names: string[]
  min_pass_count?: number | null
  blocking: boolean
}

type StrategyModule = 'factor_editor' | 'ma_trend' | 'indicator_params' | 'breakout' | 'volume_price'

interface ModuleOption {
  key: StrategyModule
  label: string
}

interface StrategyTemplate {
  id: string
  name: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
  enabled_modules: StrategyModule[]
}

interface MaTrendConfig {
  ma_periods: number[]
  slope_threshold: number
  trend_score_threshold: number
  support_ma_lines: number[]
}

interface IndicatorParamsConfig {
  macd: { fast_period: number; slow_period: number; signal_period: number }
  boll: { period: number; std_dev: number }
  rsi: { period: number; lower_bound: number; upper_bound: number }
  dma: { short_period: number; long_period: number }
}

// ─── 常量 ─────────────────────────────────────────────────────────────────────

const ALL_MODULES: ModuleOption[] = [
  { key: 'factor_editor', label: '因子条件编辑器' },
  { key: 'ma_trend', label: '均线趋势配置' },
  { key: 'indicator_params', label: '技术指标配置' },
  { key: 'breakout', label: '形态突破配置' },
  { key: 'volume_price', label: '量价资金筛选' },
]

const factorTypes: { key: FactorType; label: string }[] = [
  { key: 'technical', label: '技术面' },
  { key: 'capital', label: '资金面' },
  { key: 'fundamental', label: '基本面' },
  { key: 'sector', label: '板块面' },
  { key: 'chip', label: '筹码面' },
  { key: 'margin', label: '两融面' },
  { key: 'board_hit', label: '打板面' },
]

const factorRoleOptions: { value: FactorRole; label: string }[] = [
  { value: 'primary', label: '主条件' },
  { value: 'confirmation', label: '确认' },
  { value: 'score_only', label: '加分' },
  { value: 'disabled', label: '禁用' },
]

/** 每个因子类型下可选的因子名称枚举
 *
 * 因子名称与后端 FACTOR_REGISTRY 保持一致。
 * 前端 FactorType 'capital' 对应后端 FactorCategory 'money_flow'。
 */
const factorNameOptions: Record<FactorType, { value: string; label: string }[]> = {
  technical: [
    { value: 'ma_trend', label: 'MA趋势打分' },
    { value: 'ma_support', label: '均线支撑信号' },
    { value: 'macd', label: 'MACD金叉信号' },
    { value: 'boll', label: '布林带突破信号' },
    { value: 'rsi', label: 'RSI强势信号' },
    { value: 'dma', label: 'DMA平行线差' },
    { value: 'breakout', label: '形态突破' },
    { value: 'kdj_k', label: 'KDJ-K值' },
    { value: 'kdj_d', label: 'KDJ-D值' },
    { value: 'kdj_j', label: 'KDJ-J值' },
    { value: 'cci', label: 'CCI顺势指标' },
    { value: 'wr', label: '威廉指标' },
    { value: 'trix', label: 'TRIX三重指数平滑' },
    { value: 'bias', label: '乖离率' },
    { value: 'psy', label: '心理线指标' },
    { value: 'obv_signal', label: 'OBV能量潮信号' },
  ],
  capital: [
    { value: 'turnover', label: '换手率' },
    { value: 'money_flow', label: '主力资金净流入' },
    { value: 'large_order', label: '大单成交占比' },
    { value: 'volume_price', label: '日均成交额' },
    { value: 'super_large_net_inflow', label: '超大单净流入' },
    { value: 'large_net_inflow', label: '大单净流入' },
    { value: 'small_net_outflow', label: '小单净流出' },
    { value: 'money_flow_strength', label: '资金流强度综合评分' },
    { value: 'net_inflow_rate', label: '净流入占比' },
  ],
  fundamental: [
    { value: 'pe', label: '市盈率 TTM' },
    { value: 'pb', label: '市净率' },
    { value: 'roe', label: '净资产收益率' },
    { value: 'profit_growth', label: '利润增长率' },
    { value: 'market_cap', label: '总市值' },
    { value: 'revenue_growth', label: '营收增长率' },
  ],
  sector: [
    { value: 'sector_rank', label: '板块涨幅排名' },
    { value: 'sector_trend', label: '板块趋势' },
    { value: 'index_pe', label: '指数市盈率' },
    { value: 'index_turnover', label: '指数换手率' },
    { value: 'index_ma_trend', label: '指数均线趋势' },
    { value: 'index_vol_ratio', label: '指数量比' },
  ],
  chip: [
    { value: 'chip_winner_rate', label: '获利比例' },
    { value: 'chip_cost_5pct', label: '5%成本集中度' },
    { value: 'chip_cost_15pct', label: '15%成本集中度' },
    { value: 'chip_cost_50pct', label: '50%成本集中度' },
    { value: 'chip_weight_avg', label: '筹码加权平均成本' },
    { value: 'chip_concentration', label: '筹码集中度综合评分' },
  ],
  margin: [
    { value: 'rzye_change', label: '融资余额变化率' },
    { value: 'rqye_ratio', label: '融券余额占比' },
    { value: 'rzrq_balance_trend', label: '两融余额趋势' },
    { value: 'margin_net_buy', label: '融资净买入额' },
  ],
  board_hit: [
    { value: 'limit_up_count', label: '近期涨停次数' },
    { value: 'limit_up_streak', label: '连板天数' },
    { value: 'limit_up_open_pct', label: '涨停封板率' },
    { value: 'dragon_tiger_net_buy', label: '龙虎榜净买入' },
    { value: 'first_limit_up', label: '首板涨停标记' },
  ],
}

const MONEY_FLOW_SOURCE_FACTOR_NAMES = new Set([
  'money_flow',
  'large_order',
  'super_large_net_inflow',
  'large_net_inflow',
  'small_net_outflow',
  'money_flow_strength',
  'net_inflow_rate',
])

const SECTOR_SOURCE_FACTOR_NAMES = new Set([
  'sector_rank',
  'sector_trend',
])

const moneyFlowSourceOptions: FactorDataSourceOption[] = [
  {
    value: 'moneyflow_dc',
    label: '东方财富资金流',
    description: '覆盖较完整，推荐默认使用',
    recommended: true,
    legacy: false,
  },
  {
    value: 'moneyflow_ths',
    label: '同花顺资金流',
    description: '覆盖较完整，可作为备选资金流源',
    recommended: false,
    legacy: false,
  },
  {
    value: 'money_flow',
    label: '旧资金流表',
    description: '历史旧表，当前覆盖不足',
    recommended: false,
    legacy: true,
  },
]

/** 根据因子名称推断所属类型（用于加载旧配置时的兼容） */
function inferFactorType(name: string): FactorType {
  for (const [type, options] of Object.entries(factorNameOptions) as [FactorType, { value: string }[]][]) {
    if (options.some((o) => o.value === name)) return type
  }
  return 'technical'
}

function factorTypeLabel(type: string): string {
  return factorTypes.find((f) => f.key === type)?.label ?? type
}

// ─── Screener Store ───────────────────────────────────────────────────────────

const screenerStore = useScreenerStore()

// ─── 因子元数据辅助函数 ───────────────────────────────────────────────────────

function getFactorMeta(factorName: string): FactorMeta | undefined {
  for (const factors of Object.values(screenerStore.factorRegistry)) {
    const found = factors.find(f => f.factor_name === factorName)
    if (found) return found
  }
  return undefined
}

function getFactorThresholdType(factorName: string): string {
  return getFactorMeta(factorName)?.threshold_type ?? 'absolute'
}

function getFactorDataSourceConfig(factorName: string) {
  return getFactorMeta(factorName)?.data_source_config ?? null
}

function isMoneyFlowSourceFactor(factorName: string): boolean {
  const dataSourceConfig = getFactorDataSourceConfig(factorName)
  return dataSourceConfig?.kind === 'money_flow'
    || (dataSourceConfig == null && MONEY_FLOW_SOURCE_FACTOR_NAMES.has(factorName))
}

function isSectorSourceFactor(factorName: string): boolean {
  const dataSourceConfig = getFactorDataSourceConfig(factorName)
  return dataSourceConfig?.kind === 'sector'
    || (dataSourceConfig == null && SECTOR_SOURCE_FACTOR_NAMES.has(factorName))
}

function getMoneyFlowSourceOptions(factorName: string): FactorDataSourceOption[] {
  const options = getFactorDataSourceConfig(factorName)?.options
  return options && options.length > 0 ? options : moneyFlowSourceOptions
}

function formatDataSourceOptionLabel(option: FactorDataSourceOption): string {
  if (option.recommended) return `${option.label}（推荐）`
  if (option.legacy) return `${option.label}（旧表）`
  return option.label
}

function thresholdTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    absolute: '绝对值',
    percentile: '百分位',
    industry_relative: '行业相对',
    boolean: '布尔',
    range: '区间',
    z_score: 'Z分数',
  }
  return labels[type] ?? type
}

function groupIdForRole(role: FactorRole): string | null {
  if (role === 'primary') return 'primary_core'
  if (role === 'confirmation') return 'confirmation'
  if (role === 'score_only') return 'score_only'
  return null
}

function inferRoleFromConfig(factor: Record<string, unknown>, groups: Array<Record<string, unknown>>): FactorRole {
  const explicit = factor.role as FactorRole | undefined
  if (explicit) return explicit
  const groupId = factor.group_id as string | undefined
  const matched = groups.find((group) => group.group_id === groupId)
  return (matched?.role as FactorRole | undefined) ?? 'primary'
}

function getFactorCategory(factorName: string): string {
  const meta = getFactorMeta(factorName)
  const category = meta?.category ?? 'technical'
  // 后端 FactorCategory 'money_flow' 对应前端 FactorType 'capital'
  if (category === 'money_flow') return 'capital'
  // 新增类别 chip、margin、board_hit 与后端一致
  return category
}

function resetFactorDefault(idx: number) {
  const factor = config.factors[idx]
  const meta = getFactorMeta(factor.factor_name)
  if (!meta) return
  if (meta.threshold_type === 'range' && meta.default_range) {
    factor.threshold = null
    factor.params = { ...factor.params, threshold_low: meta.default_range[0], threshold_high: meta.default_range[1] }
    factor.operator = 'BETWEEN'
  } else if (meta.threshold_type === 'boolean') {
    factor.threshold = null
    factor.operator = '=='
  } else {
    factor.threshold = meta.default_threshold
  }
}

// ─── 状态 ─────────────────────────────────────────────────────────────────────

const router = useRouter()

const strategies = ref<StrategyTemplate[]>([])
const strategiesLoading = ref(false)
const pageError = ref<string | null>(null)

const activeStrategyId = ref('')
const activeStrategyName = computed(
  () => strategies.value.find((s) => s.id === activeStrategyId.value)?.name ?? ''
)

// running / runError 从 store 获取，跨组件生命周期保持状态
const { running, runError, lastFactorStats, lastFactorStatsStrategyKey } = storeToRefs(screenerStore)

const factorStatsForRun = computed(() => {
  if (!lastFactorStats.value.length) return []
  const statsStrategyKey = lastFactorStatsStrategyKey.value
  if (activeStrategyId.value) {
    return statsStrategyKey === activeStrategyId.value ? lastFactorStats.value : []
  }
  return lastFactorStats.value
})

function formatFactorStatTooltip(stat: FactorConditionStats): string {
  return `${stat.label || stat.factor_name}：通过 ${stat.passed_count}，失败 ${stat.failed_count}，缺失 ${stat.missing_count}`
}

const showCreateDialog = ref(false)
const newStrategyName = ref('')
const newStrategyModules = ref<StrategyModule[]>([])

const deleteTarget = ref<StrategyTemplate | null>(null)
const deleting = ref(false)

const renameDialogVisible = ref(false)
const renameStrategyId = ref('')
const renameNewName = ref('')
const renaming = ref(false)

const saving = ref(false)
const saveSuccess = ref(false)
const hydratingStrategyConfig = ref(false)

const currentEnabledModules = ref<StrategyModule[]>([])

function isModuleEnabled(moduleKey: StrategyModule): boolean {
  return currentEnabledModules.value.includes(moduleKey)
}

const showModulesDialog = ref(false)
const editingModules = ref<StrategyModule[]>([])

function openModulesDialog() {
  editingModules.value = [...currentEnabledModules.value]
  showModulesDialog.value = true
}

async function saveModules() {
  if (!activeStrategyId.value) return
  try {
    await apiClient.put(`/strategies/${activeStrategyId.value}`, {
      enabled_modules: editingModules.value,
    })
    currentEnabledModules.value = [...editingModules.value]
    showModulesDialog.value = false
  } catch {
    pageError.value = '更新模块配置失败'
  }
}

const importInputRef = ref<HTMLInputElement | null>(null)

const config = reactive({
  logic: 'AND' as 'AND' | 'OR',
  factors: [] as FactorCondition[],
})

const groupRules = reactive({
  confirmation_logic: 'OR' as 'AND' | 'OR' | 'AT_LEAST_N',
  confirmation_min_pass_count: 1,
  confirmation_blocking: true,
})

// ─── 因子使用说明面板：跟踪当前选中的因子名称 ─────────────────────────────────

const selectedFactorName = ref('')

// ─── 技术指标默认值 ────────────────────────────────────────────────────────────

const INDICATOR_DEFAULTS: IndicatorParamsConfig = {
  macd: { fast_period: 12, slow_period: 26, signal_period: 9 },
  boll: { period: 20, std_dev: 2 },
  rsi: { period: 14, lower_bound: 50, upper_bound: 80 },
  dma: { short_period: 10, long_period: 50 },
}

// ─── 均线趋势配置 ──────────────────────────────────────────────────────────────

const maTrend = reactive<MaTrendConfig>({
  ma_periods: [5, 10, 20, 60, 120],
  slope_threshold: 0,
  trend_score_threshold: 80,
  support_ma_lines: [20, 60],
})

const newPeriodInput = ref<number | null>(null)

function addMaPeriod() {
  const p = newPeriodInput.value
  if (!p || p < 1 || maTrend.ma_periods.includes(p)) return
  maTrend.ma_periods = [...maTrend.ma_periods, p].sort((a, b) => a - b)
  newPeriodInput.value = null
}

function removeMaPeriod(period: number) {
  maTrend.ma_periods = maTrend.ma_periods.filter((p) => p !== period)
}

function toggleSupportMa(line: number) {
  if (maTrend.support_ma_lines.includes(line)) {
    maTrend.support_ma_lines = maTrend.support_ma_lines.filter((l) => l !== line)
  } else {
    maTrend.support_ma_lines = [...maTrend.support_ma_lines, line].sort((a, b) => a - b)
  }
}

// ─── 技术指标配置 ──────────────────────────────────────────────────────────────

const indicatorParams = reactive<IndicatorParamsConfig>({
  macd: { ...INDICATOR_DEFAULTS.macd },
  boll: { ...INDICATOR_DEFAULTS.boll },
  rsi: { ...INDICATOR_DEFAULTS.rsi },
  dma: { ...INDICATOR_DEFAULTS.dma },
})

function resetIndicator(name: keyof IndicatorParamsConfig) {
  Object.assign(indicatorParams[name], INDICATOR_DEFAULTS[name])
}

// ─── 形态突破配置 ──────────────────────────────────────────────────────────────

interface BreakoutConfig {
  box_breakout: boolean
  high_breakout: boolean
  trendline_breakout: boolean
  volume_ratio_threshold: number
  confirm_days: number
}

const breakoutConfig = reactive<BreakoutConfig>({
  box_breakout: true,
  high_breakout: true,
  trendline_breakout: true,
  volume_ratio_threshold: 1.5,
  confirm_days: 1,
})

// ─── 量价资金筛选配置 ──────────────────────────────────────────────────────────

interface VolumePriceConfig {
  turnover_rate_min: number
  turnover_rate_max: number
  main_flow_threshold: number
  main_flow_days: number
  large_order_ratio: number
  min_daily_amount: number
  sector_rank_top: number
  money_flow_source: 'money_flow' | 'moneyflow_ths' | 'moneyflow_dc'
}

function isMoneyFlowSource(
  value: unknown,
): value is VolumePriceConfig['money_flow_source'] {
  return value === 'money_flow' || value === 'moneyflow_ths' || value === 'moneyflow_dc'
}

function normalizeMoneyFlowSource(value: unknown): VolumePriceConfig['money_flow_source'] {
  return isMoneyFlowSource(value) ? value : 'moneyflow_dc'
}

function onMoneyFlowSourceChange(value: string) {
  volumePriceConfig.money_flow_source = normalizeMoneyFlowSource(value)
}

const volumePriceConfig = reactive<VolumePriceConfig>({
  turnover_rate_min: 3,
  turnover_rate_max: 15,
  main_flow_threshold: 1000,
  main_flow_days: 2,
  large_order_ratio: 30,
  min_daily_amount: 5000,
  sector_rank_top: 30,
  money_flow_source: 'moneyflow_dc',
})

// ─── 板块筛选配置 ──────────────────────────────────────────────────────────────

const sectorConfig = reactive({
  sector_data_source: 'DC',
  sector_type: null as string | null,
  sector_period: 5,
  sector_top_n: 30,
})

// ─── 板块数据源覆盖率 ────────────────────────────────────────────────────────

const DATA_SOURCE_LABELS: Record<string, string> = {
  DC: '东方财富 DC',
  THS: '同花顺 THS',
  TDX: '通达信 TDX',
  TI: '申万行业 TI',
  CI: '中信行业 CI',
}

/** 当前选中数据源的覆盖率统计 */
const selectedSourceCoverage = computed(() => {
  const coverage = screenerStore.sectorCoverage
  if (!Array.isArray(coverage)) return null
  return coverage.find(
    (s) => s.data_source === sectorConfig.sector_data_source
  ) ?? null
})

/** 数据源中文名映射 */
const DS_LABELS: Record<string, string> = {
  DC: '东方财富 DC', THS: '同花顺 THS', TDX: '通达信 TDX', TI: '申万行业 TI', CI: '中信行业 CI',
}

/** 推荐的替代数据源（覆盖率最高且不是当前选中的） */
const bestAlternativeSource = computed(() => {
  const coverage = screenerStore.sectorCoverage
  if (!Array.isArray(coverage) || coverage.length === 0) return null
  const current = sectorConfig.sector_data_source
  const alternatives = coverage
    .filter((s) => s.data_source !== current && s.coverage_ratio > 0.1)
    .sort((a, b) => b.coverage_ratio - a.coverage_ratio)
  if (alternatives.length === 0) return null
  return DS_LABELS[alternatives[0].data_source] ?? alternatives[0].data_source
})

/** 数据源下拉选项（含覆盖率摘要） */
const sectorDataSourceOptions = computed(() => {
  const sources = ['DC', 'THS', 'TDX', 'TI', 'CI']
  const coverage = screenerStore.sectorCoverage
  return sources.map((ds) => {
    const stats = Array.isArray(coverage)
      ? coverage.find((s) => s.data_source === ds)
      : undefined
    const baseName = DATA_SOURCE_LABELS[ds] ?? ds
    if (stats) {
      const warn = stats.coverage_ratio < 0.5 ? ' ⚠️' : ''
      return {
        value: ds,
        label: `${baseName} (${stats.total_sectors} 板块 / ${stats.total_stocks} 股票)${warn}`,
      }
    }
    return { value: ds, label: baseName }
  })
})

/** 板块类型下拉选项（动态从 API 获取） */
const sectorTypeOptions = computed(() => {
  const opts: { value: string | null; label: string }[] = [
    { value: null, label: '全部' },
  ]
  for (const t of screenerStore.sectorTypes) {
    const code = t.sector_type
    const label = code != null ? `${t.label} (${code})` : t.label
    opts.push({ value: code, label })
  }
  return opts
})

/** 切换数据来源时重置板块类型并获取新类型列表 */
function onDataSourceChange(ds: string) {
  sectorConfig.sector_data_source = ds
  sectorConfig.sector_type = null
  screenerStore.fetchSectorTypes(ds)
}

function strategyUsesMoneyFlowSource(factors: FactorCondition[]): boolean {
  return factors.some((factor) => isMoneyFlowSourceFactor(factor.factor_name))
}

// ─── 策略示例 ──────────────────────────────────────────────────────────────────

const showExamplesDialog = ref(false)

function loadStrategyExample(ex: StrategyExample) {
  // Load factors
    config.factors = ex.factors.map(f => ({
    type: (getFactorCategory(f.factor_name) as FactorType),
    factor_name: f.factor_name,
    operator: f.operator,
    threshold: f.threshold,
    params: { ...f.params },
    weight: Math.round((ex.weights[f.factor_name] ?? 1.0) * 100),
    role: 'primary',
    group_id: 'primary_core',
  }))
  config.logic = ex.logic as 'AND' | 'OR'
  if (strategyUsesMoneyFlowSource(config.factors)) {
    volumePriceConfig.money_flow_source = 'moneyflow_dc'
  }

  // Load sector config
  if (ex.sector_config) {
    sectorConfig.sector_data_source = ex.sector_config.sector_data_source
    sectorConfig.sector_type = ex.sector_config.sector_type ?? null
    sectorConfig.sector_period = ex.sector_config.sector_period
    sectorConfig.sector_top_n = ex.sector_config.sector_top_n
    screenerStore.fetchSectorTypes(sectorConfig.sector_data_source)
  }

  // Enable required modules
  currentEnabledModules.value = [...ex.enabled_modules] as StrategyModule[]
  if (ex.factors.length > 0 && !currentEnabledModules.value.includes('factor_editor')) {
    currentEnabledModules.value.push('factor_editor')
  }

  showExamplesDialog.value = false
}

// ─── 策略数量上限 ──────────────────────────────────────────────────────────────

const MAX_STRATEGIES = 20

// ─── 实时选股 ─────────────────────────────────────────────────────────────────

interface EodScheduleStatus {
  next_run_at: string
  last_run_at: string | null
  last_run_duration_ms: number | null
  last_run_result_count: number | null
}

const realtimeEnabled = ref(false)
const realtimeCountdown = ref(10)
const lastRefreshTime = ref<string | null>(null)
const scheduleStatus = ref<EodScheduleStatus | null>(null)

let realtimeTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

function isTradingHours(): boolean {
  const now = new Date()
  // CST = UTC+8
  const cst = new Date(now.getTime() + 8 * 60 * 60 * 1000)
  const h = cst.getUTCHours()
  const m = cst.getUTCMinutes()
  const day = cst.getUTCDay() // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false
  const minutes = h * 60 + m
  return minutes >= 9 * 60 + 30 && minutes < 15 * 60
}

// Make isTradingHours a computed-like ref for template reactivity
const _isTradingHoursRef = ref(isTradingHours())
let _tradingHoursTimer: ReturnType<typeof setInterval> | null = null

function startTradingHoursCheck() {
  _isTradingHoursRef.value = isTradingHours()
  _tradingHoursTimer = setInterval(() => {
    _isTradingHoursRef.value = isTradingHours()
    if (!_isTradingHoursRef.value && realtimeEnabled.value) {
      stopRealtime()
    }
  }, 30_000)
}

// Expose as computed name for template
const isTradingHoursComputed = _isTradingHoursRef

function startRealtime() {
  realtimeCountdown.value = 10
  realtimeTimer = setInterval(async () => {
    if (!isTradingHours()) { stopRealtime(); return }
    try {
      await apiClient.post('/screen/run', {
        strategy_id: activeStrategyId.value || undefined,
        strategy_config: activeStrategyId.value ? undefined : buildStrategyConfig(),
        screen_type: 'REALTIME',
      }, {
        timeout: 120_000,
      })
      lastRefreshTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch { /* ignore */ }
    realtimeCountdown.value = 10
  }, 10_000)
  countdownTimer = setInterval(() => {
    if (realtimeCountdown.value > 0) realtimeCountdown.value--
  }, 1_000)
}

function stopRealtime() {
  realtimeEnabled.value = false
  if (realtimeTimer) { clearInterval(realtimeTimer); realtimeTimer = null }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

function toggleRealtime() {
  if (realtimeEnabled.value) {
    stopRealtime()
  } else {
    if (!isTradingHours()) return
    realtimeEnabled.value = true
    startRealtime()
  }
}

async function loadScheduleStatus() {
  try {
    const res = await apiClient.get<EodScheduleStatus>('/screen/schedule')
    scheduleStatus.value = res.data
  } catch { /* non-critical */ }
}

function formatScheduleTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

// ─── 策略列表 ─────────────────────────────────────────────────────────────────

async function loadStrategies() {
  strategiesLoading.value = true
  pageError.value = null
  try {
    const res = await apiClient.get<{ items?: StrategyTemplate[] } | StrategyTemplate[]>('/strategies')
    const data = res.data
    strategies.value = Array.isArray(data) ? data : (data.items ?? [])
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '加载策略失败'
  } finally {
    strategiesLoading.value = false
  }
}

// ─── 默认值常量（用于取消选中时恢复） ──────────────────────────────────────

const MA_TREND_DEFAULTS: MaTrendConfig = {
  ma_periods: [5, 10, 20, 60, 120],
  slope_threshold: 0,
  trend_score_threshold: 80,
  support_ma_lines: [20, 60],
}

const BREAKOUT_DEFAULTS: BreakoutConfig = {
  box_breakout: true,
  high_breakout: true,
  trendline_breakout: true,
  volume_ratio_threshold: 1.5,
  confirm_days: 1,
}

const VOLUME_PRICE_DEFAULTS: VolumePriceConfig = {
  turnover_rate_min: 3,
  turnover_rate_max: 15,
  main_flow_threshold: 1000,
  main_flow_days: 2,
  large_order_ratio: 30,
  min_daily_amount: 5000,
  sector_rank_top: 30,
  money_flow_source: 'moneyflow_dc',
}

function resetToDefaults() {
  // 因子条件编辑器
  config.logic = 'AND'
  config.factors = []

  // 均线趋势配置
  Object.assign(maTrend, {
    ma_periods: [...MA_TREND_DEFAULTS.ma_periods],
    slope_threshold: MA_TREND_DEFAULTS.slope_threshold,
    trend_score_threshold: MA_TREND_DEFAULTS.trend_score_threshold,
    support_ma_lines: [...MA_TREND_DEFAULTS.support_ma_lines],
  })

  // 技术指标配置
  Object.assign(indicatorParams.macd, { ...INDICATOR_DEFAULTS.macd })
  Object.assign(indicatorParams.boll, { ...INDICATOR_DEFAULTS.boll })
  Object.assign(indicatorParams.rsi, { ...INDICATOR_DEFAULTS.rsi })
  Object.assign(indicatorParams.dma, { ...INDICATOR_DEFAULTS.dma })

  // 形态突破配置
  Object.assign(breakoutConfig, { ...BREAKOUT_DEFAULTS })

  // 量价资金筛选配置
  Object.assign(volumePriceConfig, { ...VOLUME_PRICE_DEFAULTS })

  Object.assign(groupRules, {
    confirmation_logic: 'OR',
    confirmation_min_pass_count: 1,
    confirmation_blocking: true,
  })
}

async function selectStrategy(id: string) {
  // 取消选中
  if (activeStrategyId.value === id) {
    activeStrategyId.value = ''
    currentEnabledModules.value = []
    resetToDefaults()
    screenerStore.clearFactorStats()
    return
  }

  screenerStore.clearFactorStats()
  hydratingStrategyConfig.value = true

  try {
    activeStrategyId.value = id
    const res = await apiClient.get<StrategyTemplate>(`/strategies/${id}`)
    const cfg = res.data.config as Record<string, unknown>

    // 读取 enabled_modules（旧策略无此字段时默认空列表，向后兼容）
    currentEnabledModules.value = Array.isArray(res.data.enabled_modules)
      ? [...res.data.enabled_modules]
      : []

    // 回填因子条件编辑器
    config.logic = (cfg.logic as 'AND' | 'OR') ?? 'AND'
    const factors = (cfg.factors ?? []) as Array<Record<string, unknown>>
    const weights = (cfg.weights ?? {}) as Record<string, number>
    const factorGroups = (cfg.factor_groups ?? []) as Array<Record<string, unknown>>
    const confirmationGroup = factorGroups.find((group) => group.group_id === 'confirmation')
    groupRules.confirmation_logic = (confirmationGroup?.logic as 'AND' | 'OR' | 'AT_LEAST_N') ?? 'OR'
    groupRules.confirmation_min_pass_count = (confirmationGroup?.min_pass_count as number | null) ?? 1
    groupRules.confirmation_blocking = (confirmationGroup?.blocking as boolean | undefined) ?? true
    config.factors = factors.map((f) => ({
      type: (f.type as FactorType) ?? inferFactorType((f.factor_name as string) ?? ''),
      factor_name: (f.factor_name as string) ?? '',
      operator: (f.operator as string) ?? '>',
      threshold: (f.threshold as number | null) ?? null,
      weight: Math.round(((weights[(f.factor_name as string) ?? ''] ?? 0.5) * 100)),
      params: (f.params as Record<string, unknown>) ?? {},
      role: inferRoleFromConfig(f, factorGroups),
      group_id: (f.group_id as string | null) ?? groupIdForRole(inferRoleFromConfig(f, factorGroups)),
    }))

    // 回填均线趋势配置
    const mt = cfg.ma_trend as Record<string, unknown> | undefined
    if (mt) {
      maTrend.ma_periods = Array.isArray(mt.ma_periods) ? [...mt.ma_periods] : [...MA_TREND_DEFAULTS.ma_periods]
      maTrend.slope_threshold = typeof mt.slope_threshold === 'number' ? mt.slope_threshold : MA_TREND_DEFAULTS.slope_threshold
      maTrend.trend_score_threshold = typeof mt.trend_score_threshold === 'number' ? mt.trend_score_threshold : MA_TREND_DEFAULTS.trend_score_threshold
      maTrend.support_ma_lines = Array.isArray(mt.support_ma_lines) ? [...mt.support_ma_lines] : [...MA_TREND_DEFAULTS.support_ma_lines]
    } else {
      Object.assign(maTrend, {
        ma_periods: [...MA_TREND_DEFAULTS.ma_periods],
        slope_threshold: MA_TREND_DEFAULTS.slope_threshold,
        trend_score_threshold: MA_TREND_DEFAULTS.trend_score_threshold,
        support_ma_lines: [...MA_TREND_DEFAULTS.support_ma_lines],
      })
    }

    // 回填技术指标配置
    const ip = cfg.indicator_params as Record<string, Record<string, unknown>> | undefined
    if (ip) {
      if (ip.macd) Object.assign(indicatorParams.macd, ip.macd)
      if (ip.boll) Object.assign(indicatorParams.boll, ip.boll)
      if (ip.rsi) Object.assign(indicatorParams.rsi, ip.rsi)
      if (ip.dma) Object.assign(indicatorParams.dma, ip.dma)
    } else {
      Object.assign(indicatorParams.macd, { ...INDICATOR_DEFAULTS.macd })
      Object.assign(indicatorParams.boll, { ...INDICATOR_DEFAULTS.boll })
      Object.assign(indicatorParams.rsi, { ...INDICATOR_DEFAULTS.rsi })
      Object.assign(indicatorParams.dma, { ...INDICATOR_DEFAULTS.dma })
    }

    // 回填形态突破配置
    const bo = cfg.breakout as Record<string, unknown> | undefined
    if (bo) {
      Object.assign(breakoutConfig, {
        box_breakout: bo.box_breakout ?? BREAKOUT_DEFAULTS.box_breakout,
        high_breakout: bo.high_breakout ?? BREAKOUT_DEFAULTS.high_breakout,
        trendline_breakout: bo.trendline_breakout ?? BREAKOUT_DEFAULTS.trendline_breakout,
        volume_ratio_threshold: bo.volume_ratio_threshold ?? BREAKOUT_DEFAULTS.volume_ratio_threshold,
        confirm_days: bo.confirm_days ?? BREAKOUT_DEFAULTS.confirm_days,
      })
    } else {
      Object.assign(breakoutConfig, { ...BREAKOUT_DEFAULTS })
    }

    // 回填量价资金筛选配置
    const vp = cfg.volume_price as Record<string, unknown> | undefined
    if (vp) {
      Object.assign(volumePriceConfig, {
        turnover_rate_min: vp.turnover_rate_min ?? VOLUME_PRICE_DEFAULTS.turnover_rate_min,
        turnover_rate_max: vp.turnover_rate_max ?? VOLUME_PRICE_DEFAULTS.turnover_rate_max,
        main_flow_threshold: vp.main_flow_threshold ?? VOLUME_PRICE_DEFAULTS.main_flow_threshold,
        main_flow_days: vp.main_flow_days ?? VOLUME_PRICE_DEFAULTS.main_flow_days,
        large_order_ratio: vp.large_order_ratio ?? VOLUME_PRICE_DEFAULTS.large_order_ratio,
        min_daily_amount: vp.min_daily_amount ?? VOLUME_PRICE_DEFAULTS.min_daily_amount,
        sector_rank_top: vp.sector_rank_top ?? VOLUME_PRICE_DEFAULTS.sector_rank_top,
        money_flow_source: normalizeMoneyFlowSource(vp.money_flow_source),
      })
    } else {
      Object.assign(volumePriceConfig, { ...VOLUME_PRICE_DEFAULTS })
    }

    // 回填板块筛选配置
    const sc = cfg.sector_config as Record<string, unknown> | undefined
    if (sc) {
      sectorConfig.sector_data_source = (sc.sector_data_source as string) ?? 'DC'
      sectorConfig.sector_type = (sc.sector_type as string | null) ?? null
      sectorConfig.sector_period = (sc.sector_period as number) ?? 5
      sectorConfig.sector_top_n = (sc.sector_top_n as number) ?? 30
      screenerStore.fetchSectorTypes(sectorConfig.sector_data_source)
    } else {
      Object.assign(sectorConfig, { sector_data_source: 'DC', sector_type: null, sector_period: 5, sector_top_n: 30 })
    }

    // 激活该策略（需求 22.3）
    try {
      await apiClient.post(`/strategies/${id}/activate`)
      await loadStrategies()
    } catch {
      // 激活失败不阻塞配置回显，仅静默处理
    }
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '加载策略配置失败'
  } finally {
    hydratingStrategyConfig.value = false
  }
}

// ─── 保存修改 ─────────────────────────────────────────────────────────────────

async function saveStrategy() {
  if (!activeStrategyId.value) return
  saving.value = true
  saveSuccess.value = false
  try {
    await apiClient.put(`/strategies/${activeStrategyId.value}`, {
      config: buildStrategyConfig(),
      enabled_modules: currentEnabledModules.value,
    })
    await loadStrategies()
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 2000)
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '保存策略失败'
  } finally {
    saving.value = false
  }
}

// ─── 新建策略 ─────────────────────────────────────────────────────────────────

async function createStrategy() {
  const name = newStrategyName.value.trim()
  if (!name) return
  try {
    await apiClient.post('/strategies', {
      name,
      config: buildStrategyConfig(),
      is_active: false,
      enabled_modules: newStrategyModules.value,
    })
    showCreateDialog.value = false
    newStrategyName.value = ''
    newStrategyModules.value = []
    await loadStrategies()
  } catch (e: any) {
    // 策略名称重复时后端返回 409
    const detail = e?.response?.data?.detail
    pageError.value = typeof detail === 'string' ? detail : (e instanceof Error ? e.message : '创建策略失败')
  }
}

// ─── 删除策略 ─────────────────────────────────────────────────────────────────

function confirmDelete(strategy: StrategyTemplate) {
  deleteTarget.value = strategy
}

async function deleteStrategy() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await apiClient.delete(`/strategies/${deleteTarget.value.id}`)
    if (activeStrategyId.value === deleteTarget.value.id) {
      activeStrategyId.value = ''
    }
    deleteTarget.value = null
    await loadStrategies()
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '删除策略失败'
  } finally {
    deleting.value = false
  }
}

// ─── 导出策略 ─────────────────────────────────────────────────────────────────

// ─── 重命名策略 ───────────────────────────────────────────────────────────────

function startRename(id: string, currentName: string) {
  renameStrategyId.value = id
  renameNewName.value = currentName
  renameDialogVisible.value = true
}

async function confirmRename() {
  const name = renameNewName.value.trim()
  if (!name || !renameStrategyId.value) return
  renaming.value = true
  try {
    await apiClient.put(`/strategies/${renameStrategyId.value}`, { name })
    renameDialogVisible.value = false
    await loadStrategies()
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '修改策略名称失败'
  } finally {
    renaming.value = false
  }
}

// ─── 导出策略 ─────────────────────────────────────────────────────────────────

async function exportStrategy(strategy: StrategyTemplate) {
  try {
    const res = await apiClient.get<StrategyTemplate>(`/strategies/${strategy.id}`)
    const json = JSON.stringify(res.data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `strategy_${strategy.name}_${strategy.id.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '导出策略失败'
  }
}

// ─── 导入策略 ─────────────────────────────────────────────────────────────────

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (strategies.value.length >= MAX_STRATEGIES) {
    pageError.value = '已达策略上限（20 套），请删除旧策略后再导入'
    if (importInputRef.value) importInputRef.value.value = ''
    return
  }

  try {
    const text = await file.text()
    const parsed = JSON.parse(text) as Partial<StrategyTemplate>

    if (!parsed.name || !parsed.config) {
      throw new Error('JSON 文件格式无效，缺少 name 或 config 字段')
    }

    await apiClient.post('/strategies', {
      name: parsed.name,
      config: parsed.config,
      is_active: false,
    })

    await loadStrategies()
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '导入策略失败'
  } finally {
    // 重置 input 以允许重复导入同一文件
    if (importInputRef.value) importInputRef.value.value = ''
  }
}

// ─── 因子编辑器 ───────────────────────────────────────────────────────────────

function addFactor(type: FactorType) {
  config.factors.push({
    type,
    factor_name: factorNameOptions[type]?.[0]?.value ?? '',
    operator: '>',
    threshold: null,
    weight: 50,
    params: {},
    role: 'primary',
    group_id: 'primary_core',
  })
}

function removeFactor(idx: number) {
  config.factors.splice(idx, 1)
}

function buildStrategyConfig() {
  const factorGroups = buildFactorGroups(config.factors)
  return {
    logic: config.logic,
    factors: config.factors.map(({ weight: _weight, type: _type, group_id: _groupId, ...f }) => ({
      ...f,
      group_id: groupIdForRole(f.role),
    })),
    factor_groups: factorGroups,
    confirmation_mode: 'blocking',
    weights: Object.fromEntries(
      config.factors.map((f) => [f.factor_name || f.type, f.weight / 100])
    ),
    ma_periods: [...maTrend.ma_periods],
    indicator_params: {
      macd: { ...indicatorParams.macd },
      boll: { ...indicatorParams.boll },
      rsi: { ...indicatorParams.rsi },
      dma: { ...indicatorParams.dma },
    },
    ma_trend: {
      ma_periods: maTrend.ma_periods,
      slope_threshold: maTrend.slope_threshold,
      trend_score_threshold: maTrend.trend_score_threshold,
      support_ma_lines: maTrend.support_ma_lines,
    },
    breakout: { ...breakoutConfig },
    volume_price: { ...volumePriceConfig },
    sector_config: {
      sector_data_source: sectorConfig.sector_data_source,
      ...(sectorConfig.sector_type != null ? { sector_type: sectorConfig.sector_type } : {}),
      sector_period: sectorConfig.sector_period,
      sector_top_n: sectorConfig.sector_top_n,
    },
  }
}

function buildFactorGroups(factors: FactorCondition[]): FactorGroupConfig[] {
  const enabled = factors.filter((f) => f.factor_name && f.role !== 'disabled')
  const primary = enabled.filter((f) => f.role === 'primary')
  const confirmation = enabled.filter((f) => f.role === 'confirmation')
  const scoreOnly = enabled.filter((f) => f.role === 'score_only')
  const groups: FactorGroupConfig[] = []
  if (primary.length) {
    groups.push({
      group_id: 'primary_core',
      label: '主条件',
      role: 'primary',
      logic: config.logic,
      factor_names: primary.map((f) => f.factor_name),
      blocking: true,
    })
  }
  if (confirmation.length) {
    groups.push({
      group_id: 'confirmation',
      label: '确认因子',
      role: 'confirmation',
      logic: groupRules.confirmation_logic,
      factor_names: confirmation.map((f) => f.factor_name),
      min_pass_count: groupRules.confirmation_logic === 'AT_LEAST_N'
        ? Math.max(1, groupRules.confirmation_min_pass_count || 1)
        : null,
      blocking: groupRules.confirmation_blocking,
    })
  }
  if (scoreOnly.length) {
    groups.push({
      group_id: 'score_only',
      label: '仅加分',
      role: 'score_only',
      logic: 'SCORE_ONLY',
      factor_names: scoreOnly.map((f) => f.factor_name),
      blocking: false,
    })
  }
  return groups
}

watch(
  () => JSON.stringify({
    activeStrategyId: activeStrategyId.value,
    logic: config.logic,
    factors: config.factors.map((factor) => ({
      factor_name: factor.factor_name,
      operator: factor.operator,
      threshold: factor.threshold,
      params: factor.params,
      role: factor.role,
    })),
    groupRules,
  }),
  () => {
    if (!hydratingStrategyConfig.value) screenerStore.clearFactorStats()
  },
)

// ─── 执行选股 ─────────────────────────────────────────────────────────────────

async function runScreen() {
  const result = await screenerStore.runScreen({
    strategyId: activeStrategyId.value || undefined,
    strategyConfig: activeStrategyId.value ? undefined : buildStrategyConfig(),
  })
  if (result.success) router.push('/screener/results')
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadStrategies()
  // 加载因子注册表和策略示例
  screenerStore.fetchFactorRegistry()
  screenerStore.fetchStrategyExamples()
  // 加载板块数据源覆盖率
  screenerStore.fetchSectorCoverage()
  // 加载默认数据来源的板块类型列表（需求 22.7）
  screenerStore.fetchSectorTypes(sectorConfig.sector_data_source)
  // 自动选中 is_active=true 的策略并回显配置（需求 22.3）
  const active = strategies.value.find((s) => s.is_active)
  if (active) {
    await selectStrategy(active.id)
  }
  await screenerStore.fetchResults()
  loadScheduleStatus()
  startTradingHoursCheck()
})

onUnmounted(() => {
  stopRealtime()
  if (_tradingHoursTimer) clearInterval(_tradingHoursTimer)
})
</script>

<style scoped>
/* ─── 布局 ─────────────────────────────────────────────────────────────────── */
.screener { max-width: 1000px; }
.page-title { font-size: 20px; margin-bottom: 20px; color: #e6edf3; }
.section-title { font-size: 16px; color: #e6edf3; margin: 0; }

/* ─── 卡片 ─────────────────────────────────────────────────────────────────── */
.card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 20px; margin-bottom: 20px;
}

/* ─── 区块头部 ──────────────────────────────────────────────────────────────── */
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px; flex-wrap: wrap; gap: 8px;
}
.header-actions { display: flex; gap: 8px; align-items: center; }

/* ─── 策略列表 ──────────────────────────────────────────────────────────────── */
.strategy-list { display: flex; flex-direction: column; gap: 8px; }

.strategy-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; border-radius: 6px;
  border: 1px solid #21262d; background: #0d1117;
  cursor: pointer; transition: border-color 0.15s, background 0.15s;
}
.strategy-item:hover { border-color: #58a6ff44; background: #161b22; }
.strategy-item.active { border-color: #58a6ff; background: #1f6feb11; }

.strategy-info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.strategy-name { font-size: 14px; color: #e6edf3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.active-badge {
  font-size: 11px; padding: 1px 6px; border-radius: 10px;
  background: #1f6feb33; color: #58a6ff; border: 1px solid #58a6ff44;
  flex-shrink: 0;
}
.strategy-meta { flex-shrink: 0; }
.strategy-date { font-size: 12px; color: #484f58; }
.strategy-actions { display: flex; gap: 4px; flex-shrink: 0; }

/* ─── 因子编辑器 ────────────────────────────────────────────────────────────── */
.logic-toggle { display: flex; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }
.logic-btn {
  background: transparent; border: none; color: #8b949e;
  padding: 6px 14px; cursor: pointer; font-size: 13px; transition: background 0.15s, color 0.15s;
}
.logic-btn.active { background: #1f6feb33; color: #58a6ff; }
.logic-btn:hover:not(.active) { background: #21262d; color: #e6edf3; }

.factor-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }

.factor-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px; background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
}

.factor-type-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600;
  flex-shrink: 0; white-space: nowrap;
}
.factor-type-badge.technical { background: #1f3a5f; color: #58a6ff; }
.factor-type-badge.capital { background: #3a2a1a; color: #d29922; }
.factor-type-badge.fundamental { background: #1a3a2a; color: #3fb950; }
.factor-type-badge.sector { background: #2a1a3a; color: #bc8cff; }
.factor-type-badge.chip { background: #1a3a3a; color: #56d4dd; }
.factor-type-badge.margin { background: #3a1a2a; color: #f778ba; }
.factor-type-badge.board_hit { background: #3a2a0a; color: #f0883e; }

.factor-type-select { width: 90px; flex-shrink: 0; }
.factor-name { flex: 1; min-width: 120px; }
.factor-op { width: 70px; flex-shrink: 0; }
.factor-threshold { width: 90px; flex-shrink: 0; }

.weight-control { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.factor-role-select { width: 78px; flex-shrink: 0; }
.group-rule-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.group-rule-select { width: 112px; }
.group-min-input { width: 72px; }
.group-blocking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #8b949e;
  font-size: 12px;
  white-space: nowrap;
}
.weight-label { font-size: 12px; color: #8b949e; white-space: nowrap; }
.weight-slider { width: 80px; accent-color: #58a6ff; cursor: pointer; }
.weight-value { font-size: 12px; color: #e6edf3; width: 24px; text-align: right; }

.empty-factors { color: #484f58; font-size: 14px; padding: 16px 0; text-align: center; }

.add-factor-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.add-label { font-size: 13px; color: #8b949e; }

.extra-config {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px; padding-top: 12px; border-top: 1px solid #21262d;
}
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-item label { font-size: 13px; color: #8b949e; }

/* ─── 执行选股 ──────────────────────────────────────────────────────────────── */
.run-section { }
.run-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.run-info { flex: 0 1 160px; min-width: 140px; }
.run-hint { font-size: 14px; color: #e6edf3; }
.run-hint.muted { color: #8b949e; }
.run-hint strong { color: #58a6ff; }
.factor-stats-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  flex: 1 1 640px;
  gap: 6px;
  max-width: 920px;
  min-width: min(100%, 360px);
  overflow: visible;
  padding: 2px 0;
}
.factor-stat-pill {
  min-width: 0;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #c9d1d9;
  background: #0d1117;
  padding: 4px 8px;
  font-size: 12px;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.factor-stat-pill.primary { border-color: #238636; color: #d2f8d2; }
.factor-stat-pill.confirmation { border-color: #1f6feb; color: #d8e9ff; }
.factor-stat-pill.score_only { border-color: #8b949e; color: #d0d7de; }
.run-error { margin-top: 10px; font-size: 13px; color: #f85149; }

@media (max-width: 900px) {
  .factor-stats-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    flex-basis: 100%;
  }
}

@media (max-width: 520px) {
  .run-info,
  .factor-stats-strip,
  .btn-run {
    flex-basis: 100%;
  }

  .factor-stats-strip {
    grid-template-columns: 1fr;
    min-width: 0;
  }
}

/* ─── 通用输入 ──────────────────────────────────────────────────────────────── */
.input {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  padding: 6px 12px; border-radius: 6px; font-size: 14px;
}
.input:focus { outline: none; border-color: #58a6ff; }
.input.full { width: 100%; box-sizing: border-box; }
.hidden-input { display: none; }

/* ─── 按钮 ─────────────────────────────────────────────────────────────────── */
.btn {
  background: #238636; color: #fff; border: none; padding: 7px 16px;
  border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
}
.btn:hover:not(:disabled) { background: #2ea043; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
}
.btn-outline:hover:not(:disabled) { color: #e6edf3; border-color: #8b949e; }
.btn-sm { padding: 4px 10px; font-size: 13px; }
.btn-run { background: #1f6feb; font-size: 15px; padding: 10px 24px; }
.btn-run:hover:not(:disabled) { background: #388bfd; }
.btn-danger { background: #da3633; }
.btn-danger:hover:not(:disabled) { background: #f85149; }

.btn-icon {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  width: 30px; height: 30px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 14px;
  padding: 0;
}
.btn-icon:hover { color: #e6edf3; border-color: #8b949e; }
.btn-icon.danger:hover { color: #f85149; border-color: #f85149; }

/* ─── 旋转加载 ──────────────────────────────────────────────────────────────── */
.spinner {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 对话框 ────────────────────────────────────────────────────────────────── */
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center; z-index: 200;
}
.dialog {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 24px; width: 420px; max-width: 90vw;
}
.dialog-title { font-size: 16px; color: #e6edf3; margin: 0 0 16px; }
.dialog-label { font-size: 13px; color: #8b949e; display: block; margin-bottom: 6px; }
.dialog-body { font-size: 14px; color: #8b949e; margin: 0 0 20px; line-height: 1.6; }
.dialog-body strong { color: #e6edf3; }
.dialog-actions { display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }

.module-fieldset {
  border: 1px solid #30363d; border-radius: 6px; padding: 12px 16px; margin-top: 12px;
}
.module-legend { font-size: 13px; color: #e6edf3; padding: 0 4px; }
.module-hint { font-size: 12px; color: #8b949e; margin: 0 0 8px; }

/* ─── 空状态 ────────────────────────────────────────────────────────────────── */
.empty { color: #484f58; font-size: 14px; padding: 24px 0; text-align: center; }

/* ─── 折叠面板 ──────────────────────────────────────────────────────────────── */
details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }

.panel-summary {
  display: flex; align-items: center; gap: 10px;
  cursor: pointer; user-select: none; padding: 2px 0;
}
.panel-summary:hover .section-title { color: #58a6ff; }
.panel-hint { font-size: 12px; color: #484f58; }

.panel-body {
  display: flex; flex-direction: column; gap: 16px;
  margin-top: 16px; padding-top: 16px; border-top: 1px solid #21262d;
}

.panel-row { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.panel-label { font-size: 13px; color: #8b949e; min-width: 130px; padding-top: 6px; flex-shrink: 0; }

/* 标签输入 */
.tag-input-area { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; flex: 1; }
.period-tag {
  display: inline-flex; align-items: center; gap: 4px;
  background: #1f3a5f; color: #58a6ff; border: 1px solid #1f6feb44;
  border-radius: 12px; padding: 2px 10px; font-size: 13px;
}
.tag-remove {
  background: none; border: none; color: #58a6ff; cursor: pointer;
  font-size: 14px; line-height: 1; padding: 0; opacity: 0.7;
}
.tag-remove:hover { opacity: 1; }
.tag-add-row { display: flex; align-items: center; gap: 6px; }
.period-input { width: 70px; padding: 4px 8px; }

/* 数值输入 */
.param-input { width: 120px; }
.param-select { min-width: 160px; }

/* 趋势打分滑块 */
.slider-row { display: flex; align-items: center; gap: 10px; flex: 1; }
.trend-slider { flex: 1; max-width: 240px; accent-color: #58a6ff; cursor: pointer; }
.slider-value {
  font-size: 14px; color: #e6edf3; font-weight: 600;
  min-width: 28px; text-align: right;
}

/* 复选框组 */
.checkbox-group { display: flex; gap: 16px; align-items: center; padding-top: 4px; }
.checkbox-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 14px; color: #e6edf3; cursor: pointer;
}
.checkbox-label input[type="checkbox"] { accent-color: #58a6ff; width: 15px; height: 15px; cursor: pointer; }

/* ─── 技术指标 Accordion ────────────────────────────────────────────────────── */
.indicator-group {
  border: 1px solid #21262d; border-radius: 6px; overflow: hidden;
}
.indicator-group + .indicator-group { margin-top: 8px; }

.indicator-summary {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; cursor: pointer; user-select: none;
  background: #0d1117; list-style: none;
}
.indicator-summary::-webkit-details-marker { display: none; }
.indicator-summary:hover { background: #161b22; }

.indicator-title { font-size: 14px; color: #e6edf3; font-weight: 600; }

.btn-reset {
  background: transparent; border: 1px solid #30363d; color: #8b949e;
  padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;
  white-space: nowrap; flex-shrink: 0;
}
.btn-reset:hover { color: #58a6ff; border-color: #58a6ff; }

.indicator-body {
  display: flex; flex-direction: column; gap: 12px;
  padding: 14px 16px; border-top: 1px solid #21262d; background: #0d1117;
}

.param-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.param-label {
  font-size: 13px; color: #8b949e; min-width: 100px; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 2px;
}
.param-default { font-size: 11px; color: #484f58; }

/* RSI 双端滑块 */
.rsi-range { display: flex; flex-direction: column; gap: 8px; flex: 1; }
.rsi-slider-row { display: flex; align-items: center; gap: 8px; }
.rsi-bound-label { font-size: 12px; color: #8b949e; width: 28px; flex-shrink: 0; }

/* ─── 策略上限提示 ──────────────────────────────────────────────────────────── */
.limit-warning {
  background: #3a1a1a; border: 1px solid #f8514944; color: #f85149;
  border-radius: 6px; padding: 8px 14px; font-size: 13px; margin-bottom: 14px;
}
.limit-hint { font-size: 12px; color: #f85149; margin-left: 4px; }

/* ─── 盘后调度状态 ──────────────────────────────────────────────────────────── */
.schedule-status {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 8px 12px; background: #0d1117; border: 1px solid #21262d;
  border-radius: 6px; margin-bottom: 14px; font-size: 13px;
}
.schedule-label { color: #58a6ff; font-weight: 600; flex-shrink: 0; }
.schedule-item { color: #8b949e; }
.schedule-item strong { color: #e6edf3; }

/* ─── 实时选股开关 ──────────────────────────────────────────────────────────── */
.realtime-row {
  display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
  padding-bottom: 14px; border-bottom: 1px solid #21262d;
}
.realtime-label { font-size: 14px; color: #e6edf3; }
.realtime-status { font-size: 13px; }
.realtime-status.muted { color: #484f58; }
.realtime-status.active { color: #3fb950; }

/* Toggle switch */
.toggle-switch { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-track {
  position: absolute; inset: 0; background: #21262d; border-radius: 11px;
  cursor: pointer; transition: background 0.2s;
  border: 1px solid #30363d;
}
.toggle-track::before {
  content: ''; position: absolute; width: 16px; height: 16px;
  left: 2px; top: 2px; background: #8b949e; border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}
.toggle-switch input:checked + .toggle-track { background: #1f6feb; border-color: #388bfd; }
.toggle-switch input:checked + .toggle-track::before { transform: translateX(18px); background: #fff; }
.toggle-switch input:disabled + .toggle-track { opacity: 0.4; cursor: not-allowed; }

/* ─── 保存修改 ──────────────────────────────────────────────────────────────── */

/* ─── 管理模块按钮栏 ────────────────────────────────────────────────────────── */
.module-manage-bar {
  display: flex; align-items: center; gap: 12px;
}
.module-summary {
  font-size: 13px; color: #8b949e; margin-right: auto;
}
.btn-save { background: #238636; }
.btn-save:hover:not(:disabled) { background: #2ea043; }
.save-success {
  font-size: 13px; color: #3fb950; font-weight: 500;
  animation: fadeIn 0.2s ease-in;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

/* ─── 因子元数据增强 ────────────────────────────────────────────────────────── */
.factor-name-wrapper { flex: 1; min-width: 120px; }
.factor-name-wrapper .factor-name { width: 100%; }

.threshold-type-badge {
  font-size: 11px; padding: 2px 6px; border-radius: 4px;
  background: var(--bg-secondary, #2d333b); color: var(--text-secondary, #8b949e);
  white-space: nowrap; flex-shrink: 0;
}
.threshold-type-badge.percentile { background: #1a3a5c; color: #58a6ff; }
.threshold-type-badge.industry_relative { background: #2a3a2a; color: #7ee787; }
.threshold-type-badge.boolean { background: #3a2a3a; color: #d2a8ff; }
.threshold-type-badge.range { background: #3a3a1a; color: #e3b341; }

.range-inputs { display: flex; align-items: center; gap: 4px; }
.factor-threshold-half { width: 70px; }
.range-sep { color: var(--text-secondary, #8b949e); font-size: 13px; }

.factor-toggle { flex-shrink: 0; }

.factor-source-selectors {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.factor-source-select { min-width: 150px; }
.factor-source-scope {
  font-size: 11px;
  color: var(--text-secondary, #8b949e);
  border: 1px solid var(--border, #30363d);
  border-radius: 4px;
  padding: 2px 6px;
  white-space: nowrap;
}
.factor-source-warning {
  width: 100%;
  margin-top: 6px;
  padding: 8px 12px;
  background: #3a2a1a;
  border: 1px solid #d2992244;
  border-radius: 6px;
  font-size: 12px;
  color: #d29922;
  line-height: 1.5;
}

.sector-selectors { display: flex; gap: 8px; align-items: center; margin-top: 4px; width: 100%; flex-wrap: wrap; }
.sector-select { width: 100px; }
.sector-source-select { width: auto; min-width: 140px; }
.sector-type-select { width: auto; min-width: 120px; }
.sector-period-input { display: flex; align-items: center; gap: 4px; }
.param-hint { font-size: 12px; color: #8b949e; }

.sector-coverage-warning {
  width: 100%; margin-top: 6px; padding: 8px 12px;
  background: #3a2a1a; border: 1px solid #d2992244; border-radius: 6px;
  font-size: 12px; color: #d29922; line-height: 1.5;
}

.factor-unit { font-size: 12px; color: var(--text-secondary, #8b949e); flex-shrink: 0; }
.factor-range-hint { font-size: 11px; color: var(--text-secondary, #8b949e); flex-shrink: 0; }

/* ─── 策略示例对话框 ────────────────────────────────────────────────────────── */
.dialog-wide { max-width: 600px; }
.example-list { max-height: 400px; overflow-y: auto; }
.example-item {
  padding: 12px; border-bottom: 1px solid var(--border, #30363d);
  cursor: pointer; transition: background 0.15s;
}
.example-item:hover { background: var(--bg-secondary, #2d333b); }
.example-name { font-weight: 600; margin-bottom: 4px; color: #e6edf3; }
.example-desc { font-size: 13px; color: var(--text-secondary, #8b949e); margin-bottom: 6px; }
.example-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.example-tag {
  font-size: 11px; padding: 1px 6px; border-radius: 3px;
  background: var(--bg-secondary, #2d333b); color: #8b949e;
}
</style>
