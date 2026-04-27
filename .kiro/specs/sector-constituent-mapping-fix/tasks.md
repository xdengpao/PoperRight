# 任务列表：板块成分股映射修复

## 阶段 1：数据源模式常量与核心查询修复（需求 1, 2）— 最高优先级

- [x] 1.1 新增数据源模式常量
  - 在 `app/services/screener/sector_strength.py` 中新增 `_INCREMENTAL_SOURCES` 和 `_SNAPSHOT_SOURCES`
  - 初始版本：DC/TDX 为增量，THS/TI/CI 为快照
  - **修正**：经数据分析确认 TI/CI 也是增量模式（trade_date 为纳入日期），已移入 `_INCREMENTAL_SOURCES`
  - 最终：`_INCREMENTAL_SOURCES = {"DC", "TDX", "TI", "CI"}`，`_SNAPSHOT_SOURCES = {"THS"}`

- [x] 1.2 修复 `map_stocks_to_sectors()` 查询逻辑与 symbol 格式
  - 根据 `data_source in _INCREMENTAL_SOURCES` 切换查询条件：`<=` 累积查询 vs `=` 精确查询
  - 使用 `SELECT DISTINCT symbol, sector_code` 替代 `SELECT *` 优化增量查询性能
  - 构建映射时对 `SectorConstituent.symbol` 做 `_strip_market_suffix()` 转换
  - 增量查询结果去重：同一股票同一板块不重复添加

- [x] 1.3 修复 `_build_industry_map()` 查询逻辑与 symbol 格式
  - 根据数据源模式切换查询条件（增量用 `<=`，快照用 `=`）
  - 构建映射时对 `c.symbol` 做 `_strip_market_suffix()` 转换

- [x] 1.4 修复 `_load_sector_classifications()` 查询逻辑与 symbol 格式
  - 生成带后缀的 symbol 变体列表推送到数据库端过滤
  - 按数据源分别查询，各自使用正确的 trade_date 条件和各自的最新日期
  - 查询结果中对 `c.symbol` 做 `_strip_market_suffix()` 转换
  - 扩展 `_DATA_SOURCES` 加入 THS：`["DC", "THS", "TDX", "TI"]`

---

## 阶段 2：SectorRepository 查询方法修复（需求 5）

- [x] 2.1 修复 `get_constituents()` 双模式查询
  - 增量数据源使用 `trade_date <=`，快照数据源使用 `trade_date =`
  - 已包含 TI/CI 在增量数据源列表中

- [x] 2.2 修复 `get_sectors_by_stock()` 双模式查询 + symbol 格式适配
  - 双模式查询修复
  - 纯数字 symbol 输入时生成 `.SH/.SZ/.BJ` 变体匹配

- [x] 2.3 修复 `browse_sector_constituent()` 双模式查询
  - 双模式查询修复
  - 已包含 TI/CI 在增量数据源列表中

---

## 阶段 3：覆盖率统计修正（需求 4）

- [x] 3.1 修复 `GET /api/v1/sector/coverage` 接口
  - `sectors_with_stmt` 和 `stocks_stmt` 根据数据源模式切换查询条件
  - `type_stock_count_stmt` 同样根据数据源模式切换
  - 已包含 TI/CI 在增量数据源列表中

---

## 阶段 4：回测数据加载器修复（需求 3, 6）

- [x] 4.1 修复 `_load_sector_data()` symbol 格式
  - `stock_sector_map` 构建时对 `symbol` 做 `_strip_suffix()` 转换
  - `industry_map` 构建时对 `symbol` 做 `_strip_suffix()` 转换
  - 成分股查询添加 `SELECT DISTINCT` 去重

- [ ] 4.2 修改 `_load_sector_data()` 支持增量查询
  - 增量数据源加载全部记录（含 `trade_date` 字段），支持回测按历史日期过滤
  - 快照数据源查询最新日期

- [ ] 4.3 修改 `_compute_sector_strength()` 支持历史日期过滤
  - 接受增量数据源的时间序列映射
  - 对增量数据源按 `entry_date <= trade_date` 过滤
  - 对快照数据源使用全部记录并记录 WARNING

---

## 阶段 5：验证与测试

- [x] 5.1 数据库验证（已通过线上 API 验证）
  - DC: 1020/1020 板块, 5738 只股票 ✓
  - THS: 1511/1724 板块, 13935 只股票 ✓
  - TDX: 481/481 板块, 6291 只股票 ✓
  - TI: 31/359 板块, 5201 只股票 ✓（修正后）
  - CI: 30/0 板块, 5201 只股票 ✓（修正后，sector_info 无 CI 元数据）

- [ ] 5.2 编写单元测试
  - 测试 `map_stocks_to_sectors` 增量查询返回全部成分股
  - 测试 `map_stocks_to_sectors` symbol 格式转换正确
  - 测试 `get_constituents` 增量查询返回全部成分股
  - 测试 `get_sectors_by_stock` 纯数字 symbol 输入正确匹配
  - 测试 `_load_sector_classifications` 按数据源分别查询各自最新日期
  - 测试 `_build_industry_map` 回退路径根据数据源模式选择查询条件
  - 测试覆盖率统计使用累积查询

- [ ] 5.3 回归测试
  - 运行现有 screener 相关测试确保无回归
  - 验证 THS 快照数据源的查询行为不变
  - 验证回测板块因子在历史日期正确过滤
