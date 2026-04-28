# 实现计划：股票与指数代码标准化

## 概述

基于需求文档和设计文档，将代码标准化工作拆分为六个阶段：工具模块、ORM 模型与迁移、数据导入层、查询/服务层、API 与前端、文档与测试。每个任务对应一个可独立验证的代码变更。

## 任务列表

### 阶段一：代码工具模块

- [x] 1.1 创建 `app/core/symbol_utils.py`
  - 实现 `infer_exchange(bare_code)` — 根据首位数字推断交易所
  - 实现 `to_standard(code, exchange=None)` — 任意格式转标准代码（幂等）
  - 实现 `to_bare(code)` — 提取裸代码
  - 实现 `get_exchange(code)` — 提取交易所后缀
  - 实现 `is_standard(code)` — 校验标准代码格式
  - 实现 `is_index(code)` — 判断是否为指数代码
  - 定义指数常量：`INDEX_SH`, `INDEX_SZ`, `INDEX_CYB`, `INDEX_KCB`, `INDEX_HS300`, `INDEX_ZZ500`
  - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 9.2_

- [x] 1.2 编写 `symbol_utils` 单元测试
  - 文件：`tests/core/test_symbol_utils.py`
  - 覆盖：正常转换、幂等性、非法输入异常、边界情况（北交所 4/8/9 开头）
  - 覆盖：指数代码判断、指数常量正确性
  - _需求: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.3 检查点 — 运行 `pytest tests/core/test_symbol_utils.py` 确保通过

### 阶段二：ORM 模型与数据迁移

- [x] 2.1 修改 ORM 模型 symbol 列宽
  - `app/models/stock.py`：StockInfo、PermanentExclusion、StockList 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/kline.py`：Kline 的 `symbol` 从 `String(10)` → `String(12)`，更新注释
  - `app/models/adjustment_factor.py`：AdjustmentFactor 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/money_flow.py`：MoneyFlow 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/strategy.py`：ScreenResult 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/trade.py`：TradeOrder、Position 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/risk_event.py`：RiskEventLog 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/pool.py`：StockPoolItem 的 `symbol` 从 `String(10)` → `String(12)`
  - `app/models/sector.py`：SectorConstituent 的 `symbol` 从 `String(10)` → `String(12)`
  - _需求: 2.1, 2.2, 2.3_

- [x] 2.2 更新 `app/core/schemas.py` 中 dataclass 的 symbol 字段注释
  - `KlineBar.symbol`、`ScreenItem.symbol`、`ScreenChange.symbol` 添加格式说明注释
  - _需求: 8.1, 8.2, 8.3_

- [x] 2.3 创建 Alembic 数据迁移脚本
  - 文件：`alembic/versions/xxxx_standardize_symbol_codes.py`
  - upgrade()：
    1. ALTER COLUMN symbol TYPE VARCHAR(12)（所有 12 张表）
    2. UPDATE 批量添加后缀（按首位数字推断 SH/SZ/BJ，仅处理不含 `.` 的裸代码）
    3. 重建受影响的唯一约束和索引
  - downgrade()：
    1. UPDATE 去除后缀（`split_part(symbol, '.', 1)`）
    2. ALTER COLUMN symbol TYPE VARCHAR(10)
    3. 恢复原始约束
  - _需求: 2.4, 2.5, 2.6_

### 阶段三：数据导入层改造

- [x] 3.1 改造 Tushare 导入 (`app/tasks/tushare_import.py`)
  - `_convert_codes`（第1335行）：`CodeFormat.STOCK_SYMBOL`（枚举在 `tushare_registry.py:33-38`）模式下直接使用 `ts_code`（已是标准格式）赋给 `symbol`
  - `_write_to_kline`（第2155行）、`_write_to_adjustment_factor`（第2237行）：移除去后缀逻辑，直接使用标准代码
  - 使用 `symbol_utils.to_standard()` 替代内联加后缀逻辑（第 1396-1412 行）
  - _需求: 3.1, 3.6_

- [x] 3.2 改造 Tushare 适配器 (`app/services/data_engine/tushare_adapter.py`)
  - `fetch_kline`、`fetch_fundamentals`、`fetch_money_flow` 中的内联加后缀替换为 `symbol_utils.to_standard()`
  - 移除三处重复的 `if "." not in symbol` 判断
  - _需求: 3.6_

- [x] 3.3 改造本地 K 线导入 (`app/services/data_engine/local_kline_import.py`)
  - `infer_symbol_from_csv_name` 返回标准代码（使用 `symbol_utils.to_standard(bare, exchange)`）
  - _需求: 3.2_

- [x] 3.4 改造 AkShare 适配器 (`app/services/data_engine/akshare_adapter.py`)
  - 使用 `symbol_utils.to_bare()` 提取裸代码用于 API 调用
  - 返回的 KlineBar 使用标准代码
  - _需求: 3.3_

- [x] 3.5 改造板块 CSV 解析器 (`app/services/data_engine/sector_csv_parser.py`)
  - 移除 `_normalize_symbol` 函数
  - 使用 `symbol_utils.to_standard()` 替代
  - _需求: 3.4_

- [x] 3.6 改造回填服务 (`app/services/data_engine/backfill_service.py`)
  - 移除 `clean_symbol` 中间变量
  - 使用 `symbol_utils.to_standard()` 统一转换
  - _需求: 3.5_

- [x] 3.7 检查点 — 运行导入相关测试确保通过
  - `pytest tests/services/test_local_kline_import.py tests/tasks/`

### 阶段四：查询/服务层改造

- [x] 4.1 改造 K 线仓储 (`app/services/data_engine/kline_repository.py`)
  - 移除第 138 行的 `symbol.split(".")[0]` 内联去后缀
  - 查询条件直接使用标准代码
  - _需求: 4.1_

- [x] 4.2 改造选股数据提供 (`app/services/screener/screen_data_provider.py`)
  - 移除 `_strip_market_suffix` 函数（第 69-71 行）
  - 移除生成三种后缀变体的逻辑（第 1654-1659 行）
  - `_TARGET_INDICES` 替换为引用 `symbol_utils` 指数常量
  - _需求: 4.2_

- [x] 4.3 改造板块仓储 (`app/services/data_engine/sector_repository.py`)
  - 移除 `symbol_variants` 三变体生成逻辑（第 171 行）
  - 直接使用标准代码查询
  - _需求: 4.3_

- [x] 4.4 改造回测因子加载 (`app/services/backtest_factor_data_loader.py`)
  - 移除 `_strip_suffix` 函数（第 29-30 行）
  - 因子数据关联直接使用标准代码
  - _需求: 4.4_

- [x] 4.5 改造回测引擎 (`app/services/backtest_engine.py`)
  - 第 1272 行指数代码替换为引用 `symbol_utils` 常量
  - _需求: 4.5_

- [x] 4.6 改造风控模块 (`app/api/v1/risk.py`)
  - `_SH_SYMBOL`、`_CYB_SYMBOL`、`_HS300_SYMBOL`、`_ZZ500_SYMBOL` 替换为引用 `symbol_utils` 常量
  - _需求: 4.6_

- [x] 4.7 检查点 — 运行服务层测试确保通过
  - `pytest tests/services/`

### 阶段五：API 层与前端改造

- [x] 5.1 改造数据 API (`app/api/v1/data.py`)
  - 移除内联去后缀（第 230 行）和加后缀（第 233-234 行）逻辑
  - 输入 symbol 参数使用 `symbol_utils.to_standard()` 标准化
  - _需求: 5.1, 5.2, 4.7_

- [x] 5.2 改造其他 API 端点
  - `app/api/v1/screen.py`、`app/api/v1/pool.py`、`app/api/v1/trade.py` 等接受 symbol 参数的端点
  - 输入标准化：`symbol_utils.to_standard()`
  - _需求: 5.1, 5.2, 5.3_

- [x] 5.3 改造前端校验函数 (`frontend/src/stores/stockPool.ts`)
  - `validateStockSymbol` 更新正则为 `/^\d{6}(\.(SH|SZ|BJ))?$/`
  - 更新错误提示文案
  - _需求: 6.2_

- [x] 5.4 改造前端显示与默认值
  - `frontend/src/views/DashboardView.vue:326`：默认 symbol 从 `'000001'` 改为 `'000001.SZ'`
  - `frontend/src/views/DashboardView.vue:50`：placeholder 从 `"输入股票代码，如 000001"` 改为 `"输入股票代码，如 000001.SZ"`
  - `frontend/src/views/TradeView.vue:101,206`：placeholder 从 `"如 000001"` 改为 `"如 000001.SZ"`
  - `frontend/src/views/DataManageView.vue:163`：placeholder 从 `"如 600000,000001"` 改为 `"如 600000.SH,000001.SZ"`
  - `frontend/src/views/RiskView.vue:281`：placeholder 从 `"股票代码，如 000001"` 改为 `"股票代码，如 000001.SZ"`
  - 确认 `RiskView.vue:690` 已使用 `000001.SH` 格式，无需修改
  - _需求: 6.1, 6.5_

- [x] 5.5 更新前端 TypeScript 类型注释
  - `stores/screener.ts`、`stores/positions.ts` 等 `symbol: string` 字段添加格式注释
  - _需求: 6.4_

- [x] 5.6 检查点 — 运行 API 测试和前端测试
  - `pytest tests/api/`
  - `cd frontend && npm test`

- [x] 5.7 更新前端测试数据中的 symbol 格式
  - 涉及文件：`alert.test.ts`、`MainLayout.test.ts`、`StockPoolView.test.ts`、`dashboard-fundamentals-cards.property.test.ts`、`dashboard-tabs.property.test.ts`、`DashboardDualPanel.test.ts`、`DashboardSectorRanking.test.ts`、`ws-alert-flow.integration.test.ts`
  - 将测试数据中的纯数字 symbol 更新为标准代码格式

### 阶段六：文档更新与最终验证

- [x] 6.1 更新 `data-consistency.md`
  - §3.2 股票代码规范：统一为标准代码格式，废弃旧约定
  - 新增 §3.4 代码工具模块使用规范
  - 检查清单新增 symbol 格式检查项
  - _需求: 7.1, 7.2, 7.3_

- [x] 6.2 更新 `product.md`
  - Domain Context 中股票代码格式说明更新
  - _需求: 7.4_

- [x] 6.3 清理旧版频率兼容映射
  - 确认 `"minute"` → `"1min"` 映射是否仍有使用方，如无则移除
  - _需求: 9.1_

- [x] 6.4 全量回归测试
  - 运行 `pytest` 全量后端测试
  - 运行 `cd frontend && npm test` 全量前端测试
  - 全量 grep 排查残留的裸代码硬编码和内联转换逻辑
