# 因子编辑器指标数据源选择 Design

## Overview

本设计为因子编辑器增加“指标数据源选择”能力，重点解决资金流因子在 `factor_editor` 中无法选择 `moneyflow_dc/moneyflow_ths`，导致默认使用旧 `money_flow` 表的问题。

实现策略：

1. 后端因子元数据声明哪些因子支持数据源选择。
2. 前端因子编辑器根据元数据在行内展示对应数据源控件。
3. 资金流数据源仍落到现有 `StrategyConfig.volume_price.money_flow_source`，保持后端筛选链路兼容。
4. 板块数据源仍落到现有 `StrategyConfig.sector_config`，但 UI 只在 `sector_rank/sector_trend` 上展示，避免误导指数专题因子。
5. 默认资金流数据源从旧 `money_flow` 调整为 `moneyflow_dc`，优先选择当前库中覆盖更完整的数据源。

## Current Behavior

### 后端

- `money_flow` 因子注册为 `PERCENTILE`，实际评估字段是 `money_flow_pctl`。
- `money_flow_pctl` 由 `ScreenDataProvider._compute_percentile_ranks(result, ["money_flow", ...])` 计算。
- `money_flow_value` 来源由 `ScreenDataProvider._resolve_money_flow_source()` 决定：
  - 缺失或非法：回退 `money_flow` 旧表；
  - `moneyflow_ths`：查询 `moneyflow_ths`；
  - `moneyflow_dc`：查询 `moneyflow_dc`。
- `VolumePriceConfig.money_flow_source` 已存在，但默认值为 `money_flow`。

### 前端

- “量价资金筛选”模块已有资金流数据源下拉，绑定 `volumePriceConfig.money_flow_source`。
- “因子条件编辑器”中资金流因子行没有资金流数据源下拉。
- 板块类因子行对所有 `factor.type === 'sector'` 都展示板块数据源控件，包括实际不使用板块源的 `index_*` 因子。

## Data Source Capability Model

### 后端元数据结构

扩展 `FactorMeta`，新增可选字段：

```python
@dataclass(frozen=True)
class FactorDataSourceOption:
    value: str
    label: str
    description: str = ""
    recommended: bool = False
    legacy: bool = False

@dataclass(frozen=True)
class FactorDataSourceConfig:
    kind: str                 # "money_flow" | "sector"
    config_path: str          # "volume_price.money_flow_source" / "sector_config.sector_data_source"
    scope: str = "strategy"   # 本次均为策略级数据源
    options: tuple[FactorDataSourceOption, ...] = ()

@dataclass(frozen=True)
class FactorMeta:
    ...
    data_source_config: FactorDataSourceConfig | None = None
```

序列化到 API：

```json
{
  "factor_name": "money_flow",
  "label": "主力资金净流入",
  "data_source_config": {
    "kind": "money_flow",
    "config_path": "volume_price.money_flow_source",
    "scope": "strategy",
    "options": [
      {"value": "moneyflow_dc", "label": "东方财富资金流", "recommended": true},
      {"value": "moneyflow_ths", "label": "同花顺资金流"},
      {"value": "money_flow", "label": "旧资金流表", "legacy": true}
    ]
  }
}
```

### 资金流数据源适用因子

使用 `MONEY_FLOW_DATA_SOURCE_CONFIG`：

- `money_flow`
- `large_order`
- `super_large_net_inflow`
- `large_net_inflow`
- `small_net_outflow`
- `money_flow_strength`
- `net_inflow_rate`

说明：

- `money_flow` 和 `large_order` 兼容三源：`moneyflow_dc/moneyflow_ths/money_flow`。
- 增强资金流因子主要来自 `moneyflow_dc/moneyflow_ths`；为了保持配置统一，仍展示同一个策略级数据源控件。若用户选择旧 `money_flow`，这些增强因子会因缺少字段而降级，这一点由 UI 警告提示。

### 板块数据源适用因子

使用 `SECTOR_DATA_SOURCE_CONFIG`：

- `sector_rank`
- `sector_trend`

不适用：

- `index_pe`
- `index_turnover`
- `index_ma_trend`
- `index_vol_ratio`

这些指数专题因子来自 `index_dailybasic/index_tech/index_weight` 与指数 K 线，不使用 `sector_config.sector_data_source`。

## Backend Design

### 1. 扩展因子注册表

文件：`app/services/screener/factor_registry.py`

新增数据类与常量：

```python
@dataclass(frozen=True)
class FactorDataSourceOption:
    value: str
    label: str
    description: str = ""
    recommended: bool = False
    legacy: bool = False

@dataclass(frozen=True)
class FactorDataSourceConfig:
    kind: str
    config_path: str
    scope: str = "strategy"
    options: tuple[FactorDataSourceOption, ...] = ()
```

新增常量：

```python
MONEY_FLOW_DATA_SOURCE_CONFIG = FactorDataSourceConfig(...)
SECTOR_DATA_SOURCE_CONFIG = FactorDataSourceConfig(...)
```

给适用的 `FactorMeta` 添加 `data_source_config`。

### 2. API 序列化

文件：`app/api/v1/screen.py`

修改 `_factor_meta_to_dict(meta)`：

```python
"data_source_config": _factor_data_source_config_to_dict(meta.data_source_config)
```

兼容性：

- 字段新增，不破坏现有前端。
- `None` 序列化为 `None` 或省略均可；推荐返回 `None`，前端类型更明确。

### 3. 默认资金流数据源

文件：

- `app/core/schemas.py`
- `app/api/v1/screen.py`
- `frontend/src/views/ScreenerView.vue`

将默认值从 `money_flow` 调整为 `moneyflow_dc`。

后端变更：

```python
money_flow_source: str = "moneyflow_dc"
```

`normalize_money_flow_source()` 的非法回退也改为 `moneyflow_dc`。

兼容性：

- 旧策略 JSON 中已有 `"money_flow_source": "money_flow"` 时继续使用旧表。
- 旧策略缺失该字段时采用新默认 `moneyflow_dc`。

### 4. 筛选数据加载逻辑

当前 `ScreenDataProvider` 已支持：

- `_resolve_money_flow_source()`
- `_enrich_selected_money_flow_factors(..., "moneyflow_ths" | "moneyflow_dc")`
- `_enrich_money_flow_factors()` 旧表路径

本次不改变筛选算法，只确保前端和默认值把配置正确传入。

可选增强：

- `_resolve_money_flow_source()` 的非法回退改为 `moneyflow_dc`，与 `VolumePriceConfig` 默认值一致。
- 日志中输出实际使用的数据源，便于排查。

## Frontend Design

### 1. 类型扩展

文件：`frontend/src/stores/screener.ts`

扩展 `FactorMeta`：

```ts
export interface FactorDataSourceOption {
  value: string
  label: string
  description: string
  recommended: boolean
  legacy: boolean
}

export interface FactorDataSourceConfig {
  kind: 'money_flow' | 'sector' | string
  config_path: string
  scope: 'strategy' | string
  options: FactorDataSourceOption[]
}

export interface FactorMeta {
  ...
  data_source_config?: FactorDataSourceConfig | null
}
```

### 2. 因子编辑器辅助函数

文件：`frontend/src/views/ScreenerView.vue`

新增函数：

```ts
function getFactorDataSourceConfig(factorName: string) {
  return getFactorMeta(factorName)?.data_source_config ?? null
}

function isMoneyFlowSourceFactor(factorName: string): boolean {
  return getFactorDataSourceConfig(factorName)?.kind === 'money_flow'
}

function isSectorSourceFactor(factorName: string): boolean {
  return getFactorDataSourceConfig(factorName)?.kind === 'sector'
}

function onMoneyFlowSourceChange(value: string) {
  volumePriceConfig.money_flow_source = isMoneyFlowSource(value)
    ? value
    : 'moneyflow_dc'
}
```

### 3. 行内资金流数据源控件

在因子行中，阈值/单位之后、权重之前展示：

```vue
<div v-if="isMoneyFlowSourceFactor(factor.factor_name)" class="factor-source-selectors">
  <select
    :value="volumePriceConfig.money_flow_source"
    @change="onMoneyFlowSourceChange(($event.target as HTMLSelectElement).value)"
    class="input factor-source-select"
    aria-label="资金流数据源"
  >
    <option
      v-for="opt in getFactorDataSourceConfig(factor.factor_name)?.options ?? moneyFlowSourceOptions"
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
>
  旧资金流表覆盖不足，建议使用东方财富或同花顺资金流。
</div>
```

交互规则：

- 多个资金流因子共享同一个 `volumePriceConfig.money_flow_source`。
- 任意行修改数据源，所有资金流因子行显示同步更新。
- 即使 `volume_price` 模块未启用，也写入策略配置。

### 4. 收窄板块控件展示条件

当前：

```vue
<div v-if="factor.type === 'sector'" class="sector-selectors">
```

改为：

```vue
<div v-if="isSectorSourceFactor(factor.factor_name)" class="sector-selectors">
```

覆盖率警告同样改为 `isSectorSourceFactor(factor.factor_name)`。

### 5. 默认值与加载策略

前端默认：

```ts
money_flow_source: 'moneyflow_dc'
```

加载策略：

- 若 `cfg.volume_price.money_flow_source` 合法：回显该值；
- 若缺失或非法：使用 `moneyflow_dc`；
- 加载示例策略时，若示例包含资金流数据源因子且未配置 `volume_price.money_flow_source`，设置为 `moneyflow_dc`。

辅助函数：

```ts
const MONEY_FLOW_SOURCE_FACTOR_NAMES = new Set([...])

function strategyUsesMoneyFlowSource(factors: FactorCondition[]): boolean {
  return factors.some(f => isMoneyFlowSourceFactor(f.factor_name) || MONEY_FLOW_SOURCE_FACTOR_NAMES.has(f.factor_name))
}
```

使用元数据尚未加载时的静态 Set 兜底。

## API Contract

### `/api/v1/screen/factor-registry`

新增字段：

```json
{
  "money_flow": [
    {
      "factor_name": "money_flow",
      "data_source_config": {
        "kind": "money_flow",
        "config_path": "volume_price.money_flow_source",
        "scope": "strategy",
        "options": [
          {
            "value": "moneyflow_dc",
            "label": "东方财富资金流",
            "description": "覆盖较完整，推荐默认使用",
            "recommended": true,
            "legacy": false
          }
        ]
      }
    }
  ]
}
```

### `/api/v1/screen/factors/{factor_name}/usage`

可同步返回 `data_source_config`，供使用说明面板后续展示。本次若只用于因子编辑器，最小实现可先只扩展 registry/list 响应。

## Backward Compatibility

- 旧策略中已有 `volume_price.money_flow_source` 保持不变。
- 旧策略缺失 `money_flow_source` 时使用新默认 `moneyflow_dc`。
- 前端若访问旧后端，`data_source_config` 缺失时不展示行内数据源控件。
- 后端 `FactorCondition.params` 不新增数据源字段，避免单因子源和策略级源冲突。
- 板块数据源仍使用 `sector_config`，不改变后端筛选逻辑。

## Risks And Mitigations

- **风险：用户以为每个资金流因子可以独立选择数据源。**
  - 缓解：UI 显示“策略级”，所有资金流因子共享一个值。

- **风险：增强资金流因子选择旧 `money_flow` 后仍缺数据。**
  - 缓解：旧表选项标记 legacy，并显示覆盖不足警告。

- **风险：默认值变更影响旧策略结果。**
  - 缓解：只影响缺失 `money_flow_source` 的策略；已有显式配置不变。

- **风险：板块指数专题因子隐藏数据源后用户疑惑。**
  - 缓解：因子说明中保持“指数专题表”描述，不展示无效控件。

## Test Plan

### Backend

- `tests/services/test_factor_registry.py`
  - 断言资金流适用因子包含 `data_source_config.kind == "money_flow"`。
  - 断言 `turnover/volume_price` 不包含资金流数据源配置。
  - 断言 `sector_rank/sector_trend` 包含 `kind == "sector"`。
  - 断言 `index_*` 不包含板块数据源配置。

- `tests/api/test_screen_factor_registry.py` 或现有 screen API 测试
  - 断言 `/screen/factor-registry` 序列化包含 `data_source_config`。

- `tests/core/test_schemas_param_optimization.py`
  - 更新默认资金流数据源为 `moneyflow_dc`。
  - 更新非法数据源回退为 `moneyflow_dc`。

### Frontend

- `frontend/src/views/__tests__/ScreenerView.test.ts`
  - 资金流因子显示资金流数据源下拉。
  - 切换资金流数据源后保存配置包含 `volume_price.money_flow_source`。
  - `sector_rank/sector_trend` 显示板块数据源。
  - `index_pe/index_turnover/index_ma_trend/index_vol_ratio` 不显示板块数据源。
  - 加载旧策略缺失资金流源时默认回显 `moneyflow_dc`。

## Implementation Notes

- 本次优先使用已有配置字段，不把数据源写入 `FactorCondition.params`。
- 若后续需要单因子独立数据源，可扩展 `FactorCondition.params.data_source`，但需要后端 `ScreenDataProvider` 支持同一策略内多源混合加载；本次不做。
- 如果后续新增资金流覆盖率 API，可把 `FactorDataSourceOption.description` 替换为实时覆盖率标签。
