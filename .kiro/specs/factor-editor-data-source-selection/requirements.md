# 因子编辑器指标数据源选择 Requirements

## 背景

因子编辑器模块中，“主力资金净流入”属于 `money_flow` 百分位因子。后端评估时不会读取 `money_flow` 布尔值或原始金额，而是根据 `FactorMeta.threshold_type=PERCENTILE` 读取 `money_flow_pctl`。`money_flow_pctl` 来自 `ScreenDataProvider._compute_percentile_ranks()` 对 `money_flow_value` 的全市场排名。

当前后端已有资金流数据源配置：

- `volume_price.money_flow_source = "money_flow"`：旧资金流表；
- `volume_price.money_flow_source = "moneyflow_ths"`：同花顺资金流；
- `volume_price.money_flow_source = "moneyflow_dc"`：东方财富资金流。

但因子编辑器行内没有数据源选择。用户在因子编辑器中添加“主力资金净流入 >= 75”时，无法知道或修改实际使用的数据源。若策略没有启用或展开“量价资金筛选”模块，配置会默认回退到旧 `money_flow` 表。

当前库中数据完整性差异明显：

- `money_flow` 旧表：最新 `2026-03-27`，最近每天约 5 只股票；
- `moneyflow_ths`：最新 `20260429`，最近每天约 5145 只股票；
- `moneyflow_dc`：最新 `20260429`，最近每天约 5519 只股票。

因此，因子编辑器需要把“指标可选数据源”明确暴露出来，并写入策略配置，避免资金流因子因为默认旧表而大面积缺失。

## 可选择数据源的因子分析

### 资金流数据源（可选择）

这些因子由 `moneyflow_ths/moneyflow_dc` 或旧 `money_flow` 数据驱动，应共享 `volume_price.money_flow_source`：

| 因子 | 含义 | 数据字段 | 可选数据源 |
|------|------|----------|------------|
| `money_flow` | 主力资金净流入百分位 | `money_flow_value -> money_flow_pctl` | `money_flow` / `moneyflow_ths` / `moneyflow_dc` |
| `large_order` | 大单成交占比 | `large_order_ratio` | `money_flow` / `moneyflow_ths` / `moneyflow_dc` |
| `super_large_net_inflow` | 超大单净流入百分位 | `super_large_net_inflow -> super_large_net_inflow_pctl` | `moneyflow_ths` / `moneyflow_dc` |
| `large_net_inflow` | 大单净流入百分位 | `large_net_inflow -> large_net_inflow_pctl` | `moneyflow_ths` / `moneyflow_dc` |
| `small_net_outflow` | 小单净流出 | `small_net_outflow` | `moneyflow_ths` / `moneyflow_dc` |
| `money_flow_strength` | 资金流强度综合评分 | `money_flow_strength` | `moneyflow_ths` / `moneyflow_dc` |
| `net_inflow_rate` | 净流入占比 | `net_inflow_rate` | `moneyflow_ths` / `moneyflow_dc` |

说明：

- `turnover` 来自 K 线辅助字段，不需要资金流数据源选择。
- `volume_price` 当前表示日均成交额/量价活跃度，不直接依赖 `moneyflow_ths/moneyflow_dc`，不纳入行内资金流数据源选择。

### 板块数据源（已有选择，但需收窄适用范围）

这些因子由板块行情和板块成分映射驱动，已通过 `sector_config` 支持数据源：

| 因子 | 含义 | 配置字段 | 可选数据源 |
|------|------|----------|------------|
| `sector_rank` | 板块涨幅排名 | `sector_config.sector_data_source` | `DC` / `THS` / `TDX` / `TI` / `CI` |
| `sector_trend` | 板块趋势 | `sector_config.sector_data_source` | `DC` / `THS` / `TDX` / `TI` / `CI` |

说明：

- 当前前端对所有 `sector` 类型因子展示板块数据源选择，但 `index_pe/index_turnover/index_ma_trend/index_vol_ratio` 实际来自指数专题表和指数 K 线，不使用 `sector_config.sector_data_source`。本次应收窄 UI 展示条件，避免误导。

### 暂不支持行内数据源选择的因子

- 技术面：来自 K 线或计算指标。
- 基本面：来自 `stock_info` / `stk_factor` 等固定表。
- 筹码面：来自 `cyq_perf` 等 Tushare 筹码专题表。
- 两融面：来自 `margin_detail`。
- 打板面：来自 `limit_list/limit_step/top_list`。
- 指数专题：来自 `index_dailybasic/index_tech/index_weight` 与指数 K 线，当前没有多个同类数据源。

## Requirements

### Requirement 1：因子元数据声明可选数据源

**User Story:** 作为策略配置用户，我希望因子注册表告诉前端哪些因子支持数据源选择，这样因子编辑器只在正确的因子上展示数据源控件。

#### Acceptance Criteria

1. WHEN API 返回 `money_flow`、`large_order`、`super_large_net_inflow`、`large_net_inflow`、`small_net_outflow`、`money_flow_strength`、`net_inflow_rate` 元数据 THEN 响应 SHALL 包含资金流数据源选项。
2. WHEN API 返回 `sector_rank`、`sector_trend` 元数据 THEN 响应 SHALL 包含板块数据源选项。
3. WHEN API 返回 `turnover`、`volume_price`、`index_pe`、`index_turnover`、`index_ma_trend`、`index_vol_ratio` 元数据 THEN 响应 SHALL 不声明资金流或板块数据源选择。
4. WHEN 前端加载旧版本 API 或元数据缺少数据源字段 THEN 因子编辑器 SHALL 保持现有行为，不报错。

### Requirement 2：因子编辑器行内展示资金流数据源选择

**User Story:** 作为策略配置用户，我希望在因子编辑器中选择“主力资金净流入”等资金流指标时能直接选择数据源，这样不用再去量价资金模块里找全局配置。

#### Acceptance Criteria

1. WHEN 用户选择支持资金流数据源的因子 THEN 因子行 SHALL 展示资金流数据源下拉。
2. WHEN 用户将资金流数据源切换为 `moneyflow_dc` THEN `buildStrategyConfig()` SHALL 写入 `volume_price.money_flow_source = "moneyflow_dc"`。
3. WHEN 用户将资金流数据源切换为 `moneyflow_ths` THEN `buildStrategyConfig()` SHALL 写入 `volume_price.money_flow_source = "moneyflow_ths"`。
4. WHEN 用户选择旧资金流表 THEN `buildStrategyConfig()` SHALL 写入 `volume_price.money_flow_source = "money_flow"`。
5. WHEN 策略只启用 `factor_editor` 而未启用 `volume_price` 模块 THEN 资金流数据源选择仍 SHALL 写入 `volume_price.money_flow_source`，供 `ScreenDataProvider` 使用。
6. WHEN 同一策略中存在多个资金流数据源因子 THEN 这些因子 SHALL 使用同一个 `money_flow_source`，前端 SHALL 明确这是策略级资金流数据源，而不是单因子独立数据源。

### Requirement 3：因子编辑器板块数据源展示只作用于板块强度因子

**User Story:** 作为策略配置用户，我希望只有真正使用板块数据源的因子才展示板块数据源控件，这样不会误以为指数专题因子能切换 DC/TI/TDX。

#### Acceptance Criteria

1. WHEN 用户选择 `sector_rank` 或 `sector_trend` THEN 因子行 SHALL 展示板块数据源、板块类型和周期控件。
2. WHEN 用户选择 `index_pe`、`index_turnover`、`index_ma_trend` 或 `index_vol_ratio` THEN 因子行 SHALL 不展示板块数据源和板块类型控件。
3. WHEN 用户切换板块数据源 THEN `sector_config.sector_data_source` SHALL 更新，并继续触发板块类型列表刷新。
4. WHEN 用户保存策略 THEN `sector_config` SHALL 保持现有序列化格式，兼容后端。

### Requirement 4：加载、保存、示例策略保持数据源配置一致

**User Story:** 作为策略用户，我希望保存、加载、导入和示例策略都能正确保留数据源选择，这样不会因为页面刷新或策略切换回退到旧表。

#### Acceptance Criteria

1. WHEN 加载已有策略且 `config.volume_price.money_flow_source` 存在 THEN 因子编辑器行内资金流数据源下拉 SHALL 回显该值。
2. WHEN 加载已有策略且 `config.volume_price.money_flow_source` 缺失 THEN 前端 SHALL 使用当前默认值；默认值应优先考虑数据完整性更好的 `moneyflow_dc`，而不是旧 `money_flow`。
3. WHEN 加载示例策略包含资金流因子但没有显式资金流数据源 THEN 前端 SHALL 设置 `volume_price.money_flow_source = "moneyflow_dc"`。
4. WHEN 导入策略 JSON 包含 `volume_price.money_flow_source` THEN 系统 SHALL 保留该配置。
5. WHEN 保存策略 THEN 后端 SHALL 继续通过 `VolumePriceConfig.from_dict()` 校验合法数据源；非法值 SHALL 回退到默认安全值。

### Requirement 5：数据完整性提示

**User Story:** 作为策略配置用户，我希望看到不同资金流数据源的含义和完整性提示，这样可以避免误选旧表导致没有结果。

#### Acceptance Criteria

1. WHEN 用户打开资金流数据源下拉 THEN 选项标签 SHALL 区分“旧资金流表”、“同花顺资金流”、“东方财富资金流”。
2. WHEN 选择旧 `money_flow` THEN UI SHALL 显示警告，提示该表可能覆盖不足，建议优先使用 `moneyflow_dc` 或 `moneyflow_ths`。
3. WHEN 后端未来提供资金流数据源覆盖率 API THEN 前端 SHOULD 在选项中展示最近日期和覆盖股票数；本次实现可先使用静态说明。
4. WHEN 用户使用 `moneyflow_dc` 或 `moneyflow_ths` THEN UI SHALL 不显示旧表覆盖不足警告。

### Requirement 6：测试覆盖

**User Story:** 作为开发者，我希望自动化测试覆盖因子编辑器的数据源选择，避免后续 UI 或配置转换改动再次丢失数据源。

#### Acceptance Criteria

1. WHEN 运行前端单元测试 THEN 应覆盖资金流因子行显示数据源选择。
2. WHEN 运行前端单元测试 THEN 应覆盖切换资金流数据源后 `buildStrategyConfig()` 输出正确的 `volume_price.money_flow_source`。
3. WHEN 运行前端单元测试 THEN 应覆盖 `sector_rank/sector_trend` 显示板块数据源，而 `index_*` 因子不显示板块数据源。
4. WHEN 运行后端单元测试 THEN 应覆盖因子元数据序列化包含可选数据源字段。
5. WHEN 运行后端单元测试 THEN 应覆盖 `VolumePriceConfig` 对资金流数据源的默认值和非法值回退。
