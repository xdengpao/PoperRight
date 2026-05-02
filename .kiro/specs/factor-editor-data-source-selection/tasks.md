# 因子编辑器指标数据源选择 Tasks

## Phase 1：后端元数据与默认值

- [x] 1. 扩展因子注册表数据结构
  - 在 `app/services/screener/factor_registry.py` 新增 `FactorDataSourceOption`、`FactorDataSourceConfig`。
  - 为 `FactorMeta` 新增可选 `data_source_config` 字段。
  - 定义资金流与板块两类数据源配置常量。

- [x] 2. 标注支持数据源选择的因子
  - 为 `money_flow`、`large_order`、`super_large_net_inflow`、`large_net_inflow`、`small_net_outflow`、`money_flow_strength`、`net_inflow_rate` 绑定资金流数据源配置。
  - 为 `sector_rank`、`sector_trend` 绑定板块数据源配置。
  - 确认 `turnover`、`volume_price`、`index_pe`、`index_turnover`、`index_ma_trend`、`index_vol_ratio` 不声明数据源配置。

- [x] 3. 扩展 API 序列化
  - 在 `app/api/v1/screen.py` 中为因子元数据响应增加 `data_source_config`。
  - 若使用说明接口返回因子元数据，同步补充该字段。

- [x] 4. 调整资金流默认数据源
  - 将 `VolumePriceConfig.money_flow_source` 默认值改为 `moneyflow_dc`。
  - 将非法资金流源回退值改为 `moneyflow_dc`。
  - 同步 API 输入模型与前端默认配置。

## Phase 2：前端因子编辑器

- [x] 5. 扩展前端因子元数据类型
  - 在 `frontend/src/stores/screener.ts` 增加 `FactorDataSourceOption`、`FactorDataSourceConfig` 类型。
  - 为 `FactorMeta` 增加可选 `data_source_config` 字段。

- [x] 6. 增加资金流因子行内数据源选择
  - 在 `frontend/src/views/ScreenerView.vue` 增加元数据读取、静态兜底集合、合法值校验和标签格式化函数。
  - 在支持资金流数据源的因子行展示数据源下拉。
  - 多个资金流因子共享 `volumePriceConfig.money_flow_source`，并显示策略级提示。
  - 选择旧 `money_flow` 时显示覆盖不足警告。

- [x] 7. 收窄板块数据源控件展示范围
  - 将因子行板块数据源控件条件从 `factor.type === 'sector'` 改为元数据声明或静态兜底的 `sector_rank/sector_trend`。
  - 保持板块类型列表刷新和 `sector_config` 序列化格式不变。

- [x] 8. 保证策略加载、导入、保存一致
  - 加载旧策略缺失资金流源时回显 `moneyflow_dc`。
  - 导入策略 JSON 时保留合法资金流源，非法值回退 `moneyflow_dc`。
  - `buildStrategyConfig()` 始终写入 `volume_price.money_flow_source`。

## Phase 3：测试与验证

- [x] 9. 增加后端测试
  - 覆盖资金流/板块因子的 `data_source_config` 声明。
  - 覆盖不适用因子不会声明数据源配置。
  - 覆盖 API 序列化包含 `data_source_config`。
  - 覆盖资金流默认值与非法回退为 `moneyflow_dc`。

- [x] 10. 增加前端测试
  - 覆盖资金流因子显示数据源下拉。
  - 覆盖切换资金流源后策略配置写入正确。
  - 覆盖 `sector_rank/sector_trend` 展示板块控件，`index_*` 不展示。

- [x] 11. 执行聚焦验证与代码质量自检
  - 运行相关后端 pytest。
  - 运行相关前端 Vitest 或类型检查。
  - 按 `.kiro/hooks/code-quality-review.kiro.hook` 做自检并修正问题。
