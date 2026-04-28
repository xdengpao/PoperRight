# 需求文档：股票与指数代码标准化

## 简介

当前项目中股票代码（symbol）和指数代码存在格式不统一的问题：业务表使用纯 6 位数字（如 `000001`），Tushare 原始数据表使用带后缀的 `ts_code`（如 `000001.SZ`），kline 表存储纯数字但注释标注为带后缀格式，板块成分表 `SectorConstituent` 声明 `String(10)` 但实际存储带后缀格式。此外，去后缀/加后缀的转换逻辑在至少 9 处重复实现，且部分简化版本不覆盖北交所代码。

为与行业标准（Tushare/Wind/Choice 等主流数据源均使用 `{code}.{exchange}` 格式）接轨，本需求将全系统股票和指数代码统一为带市场后缀的标准格式（如 `600000.SH`、`000001.SZ`、`399300.SZ`、`830799.BJ`），并提供统一的代码工具模块消除重复逻辑。

## 术语表

- **标准代码（Standard_Code）**：带市场后缀的证券代码，格式为 `{6位数字}.{交易所}`，如 `600000.SH`、`000001.SZ`、`830799.BJ`
- **裸代码（Bare_Code）**：不带后缀的纯 6 位数字代码，如 `600000`、`000001`
- **交易所后缀（Exchange_Suffix）**：标识证券所属交易所的后缀，取值为 `SH`（上海证券交易所）、`SZ`（深圳证券交易所）、`BJ`（北京证券交易所）
- **代码工具模块（Symbol_Utils）**：提供代码格式转换、校验、交易所推断等功能的统一工具模块
- **业务表（Business_Table）**：存储在 PostgreSQL 中的业务数据表，使用 `PGBase` 基类
- **时序表（TimeSeries_Table）**：存储在 TimescaleDB 中的时序数据表，使用 `TSBase` 基类

## 现状分析

### 当前格式分布

| 模块/表 | 当前格式 | 字段名 | 问题 |
|---------|---------|--------|------|
| StockInfo | 裸代码 | `symbol` | 无后缀，无法区分交易所 |
| Kline | 裸代码 | `symbol` | 注释写"如 000001.SZ"但实际存纯数字 |
| AdjustmentFactor | 裸代码 | `symbol` | 无后缀 |
| MoneyFlow | 裸代码 | `symbol` | 无后缀 |
| ScreenResult | 裸代码 | `symbol` | 无后缀 |
| TradeOrder / Position | 裸代码 | `symbol` | 无后缀 |
| StockPoolItem | 裸代码 | `symbol` | 无后缀 |
| SectorConstituent | 带后缀 | `symbol` | 字段声明 `String(10)` 但实际存 9 字符 |
| Tushare 86 张表 | 带后缀 | `ts_code` | 已符合标准，字段名不同 |
| 指数硬编码 | 带后缀 | — | 散落在多个文件中 |

### 重复转换逻辑

| 位置 | 函数/逻辑 | 方向 |
|------|----------|------|
| `screen_data_provider.py:69` | `_strip_market_suffix` | 去后缀 |
| `backtest_factor_data_loader.py:29` | `_strip_suffix` | 去后缀 |
| `sector_csv_parser.py:83` | `_normalize_symbol` | 去后缀 |
| `kline_repository.py:138` | 内联 `split(".")` | 去后缀 |
| `api/v1/data.py:230` | 内联 `split(".")` | 去后缀 |
| `tushare_adapter.py:215` | 内联 if/else | 加后缀（不含 BJ） |
| `api/v1/data.py:233` | 内联 if/else | 加后缀（不含 BJ） |
| `tasks/tushare_import.py:1396` | 内联 if/elif | 加后缀（含 BJ） |
| `sector_repository.py:171` | 生成三种变体 | 加后缀（暴力匹配） |

## 需求

### 需求 1：统一代码工具模块

**用户故事：** 作为量化开发者，我希望有一个统一的代码工具模块，提供标准化的代码格式转换和校验功能，以消除项目中散落的重复转换逻辑。

#### 验收标准

1. THE Symbol_Utils SHALL 作为 `app/core/symbol_utils.py` 模块提供以下核心函数：
   - `to_standard(code: str, market: str | None = None) -> str`：将任意格式代码转为标准代码
   - `to_bare(code: str) -> str`：从标准代码提取裸代码
   - `get_exchange(code: str) -> str`：从标准代码提取交易所后缀
   - `infer_exchange(bare_code: str) -> str`：根据裸代码首位数字推断交易所
   - `is_standard(code: str) -> bool`：校验是否为合法标准代码
   - `is_index(code: str) -> bool`：判断是否为指数代码
2. THE `infer_exchange` 函数 SHALL 按以下规则推断交易所：
   - `6` 开头 → `SH`（上海）
   - `0` 或 `3` 开头 → `SZ`（深圳）
   - `4`、`8` 或 `9` 开头 → `BJ`（北京）
3. THE `to_standard` 函数 SHALL 处理以下输入格式：
   - 裸代码 `"600000"` → `"600000.SH"`（自动推断交易所）
   - 已标准化 `"600000.SH"` → `"600000.SH"`（幂等）
   - 带 market 参数 `to_standard("600000", "SH")` → `"600000.SH"`（显式指定）
4. THE Symbol_Utils SHALL 提供完整的类型注解和中文文档字符串
5. IF 输入代码格式不合法（非 6 位数字、未知交易所后缀），THEN 相关函数 SHALL 抛出 `ValueError` 并附带清晰的错误信息

### 需求 2：数据库 symbol 字段统一为标准代码

**用户故事：** 作为量化交易员，我希望数据库中所有表的股票/指数代码字段统一使用带后缀的标准格式，以便跨表查询时无需格式转换。

#### 验收标准

1. THE 以下 ORM 模型的 `symbol` 字段 SHALL 统一存储标准代码格式：
   - `StockInfo`、`StockList`、`PermanentExclusion`（`app/models/stock.py`）
   - `Kline`（`app/models/kline.py`）
   - `AdjustmentFactor`（`app/models/adjustment_factor.py`）
   - `MoneyFlow`（`app/models/money_flow.py`）
   - `ScreenResult`（`app/models/strategy.py`）
   - `TradeOrder`、`Position`（`app/models/trade.py`）
   - `RiskEventLog`（`app/models/risk_event.py`）
   - `StockPoolItem`（`app/models/pool.py`）
2. THE `SectorConstituent` 模型的 `symbol` 字段 SHALL 将列类型从 `String(10)` 扩展为 `String(12)`，以正确容纳标准代码
3. THE 所有 `symbol` 字段的列类型 SHALL 统一为 `String(12)`，以容纳最长的标准代码格式（如 `830799.BJ`，9 字符，预留余量）
4. SHALL 提供 Alembic 数据迁移脚本，将现有裸代码数据批量转换为标准代码格式
5. THE 迁移脚本 SHALL 使用 SQL UPDATE 语句批量转换，根据代码首位数字推断交易所后缀
6. THE 迁移脚本 SHALL 支持回滚（downgrade），将标准代码还原为裸代码

### 需求 3：数据导入层统一输出标准代码

**用户故事：** 作为量化开发者，我希望所有数据导入通道在写入数据库前统一将代码转为标准格式，以确保数据源差异不影响存储一致性。

#### 验收标准

1. WHEN Tushare 导入服务写入业务表时，THE `tushare_import.py` SHALL 使用 Symbol_Utils 将 `ts_code` 转为标准代码存入 `symbol` 字段
2. WHEN 本地 CSV 导入服务解析文件名时，THE `local_kline_import.py` SHALL 使用 Symbol_Utils 将推断出的裸代码转为标准代码
3. WHEN AkShare 适配器获取数据时，THE `akshare_adapter.py` SHALL 使用 Symbol_Utils 进行代码格式转换
4. WHEN 板块 CSV 解析器处理成分股代码时，THE `sector_csv_parser.py` SHALL 使用 Symbol_Utils 替代现有的 `_normalize_symbol` 函数
5. WHEN 回填服务处理股票列表时，THE `backfill_service.py` SHALL 使用 Symbol_Utils 替代内联转换逻辑
6. THE 所有导入通道 SHALL 删除各自的重复转换函数，统一调用 Symbol_Utils

### 需求 4：查询层与服务层适配

**用户故事：** 作为量化开发者，我希望所有数据查询和业务逻辑层使用标准代码进行查询，消除查询时的格式转换开销。

#### 验收标准

1. THE `kline_repository.py` SHALL 移除查询时的 `symbol.split(".")[0]` 去后缀逻辑，直接使用标准代码查询
2. THE `screen_data_provider.py` SHALL 移除 `_strip_market_suffix` 函数，使用标准代码进行板块成分匹配
3. THE `sector_repository.py` SHALL 移除生成三种后缀变体的暴力匹配逻辑，直接使用标准代码查询
4. THE `backtest_factor_data_loader.py` SHALL 移除 `_strip_suffix` 函数，使用标准代码进行因子数据关联
5. THE `backtest_engine.py` SHALL 使用标准代码格式的指数代码常量
6. THE `risk_controller.py` 和 `api/v1/risk.py` SHALL 使用标准代码格式的指数代码常量
7. THE `api/v1/data.py` SHALL 移除内联的去后缀/加后缀逻辑，使用 Symbol_Utils

### 需求 5：API 层适配

**用户故事：** 作为量化交易员，我希望 API 接口统一接受和返回标准代码格式，以便前端和外部系统使用行业标准格式交互。

#### 验收标准

1. THE 所有接受 `symbol` 参数的 API 端点 SHALL 同时兼容标准代码和裸代码输入
2. WHEN API 接收到裸代码时，SHALL 使用 Symbol_Utils 自动转为标准代码后再进行业务处理
3. THE 所有 API 响应中的 `symbol` 字段 SHALL 返回标准代码格式
4. THE API 文档（OpenAPI schema）SHALL 更新 symbol 字段的描述和示例为标准代码格式

### 需求 6：前端适配

**用户故事：** 作为量化交易员，我希望前端界面统一显示带后缀的标准代码格式，并在输入时支持智能补全后缀，以便与行业惯例一致。

#### 验收标准

1. THE 前端所有股票代码显示位置 SHALL 展示标准代码格式（如 `600000.SH`）
2. THE `validateStockSymbol` 函数 SHALL 更新为同时接受标准代码（`600000.SH`）和裸代码（`600000`）输入
3. WHEN 用户输入裸代码时，THE 前端 SHALL 在提交前自动补全交易所后缀
4. THE 前端 TypeScript 类型定义中的 `symbol: string` SHALL 添加注释说明格式为标准代码
5. THE DashboardView 中的默认 symbol 值 SHALL 从 `'000001'` 更新为 `'000001.SZ'`

### 需求 7：数据一致性规范文档更新

**用户故事：** 作为量化开发者，我希望数据一致性规范文档反映新的标准代码格式约定，以便团队成员遵循统一标准。

#### 验收标准

1. THE `data-consistency.md` 中 §3.2 股票代码规范 SHALL 更新为：所有表统一使用标准代码格式，废弃"kline 表带后缀、其他表纯数字"的旧约定
2. THE `data-consistency.md` SHALL 新增 §3.4 代码工具模块使用规范，说明 Symbol_Utils 的使用方式和禁止自行实现转换逻辑的规则
3. THE `data-consistency.md` 检查清单 SHALL 新增：`symbol 字段使用标准代码格式（{code}.{exchange}）`
4. THE `product.md` 中的 Domain Context SHALL 更新股票代码格式说明

### 需求 8：schemas.py 数据结构适配

**用户故事：** 作为量化开发者，我希望核心数据结构中的 symbol 字段明确标注为标准代码格式，以便在代码层面强化格式约定。

#### 验收标准

1. THE `KlineBar` dataclass 的 `symbol` 字段 SHALL 添加注释说明格式为标准代码
2. THE `ScreenItem` dataclass 的 `symbol` 字段 SHALL 添加注释说明格式为标准代码
3. THE `ScreenChange` dataclass 的 `symbol` 字段 SHALL 添加注释说明格式为标准代码
4. THE 所有 `to_dict()` / `from_dict()` 方法 SHALL 确保序列化/反序列化时保持标准代码格式

### 需求 9：其他与行业标准不符的数据结构修正

**用户故事：** 作为量化交易员，我希望在代码标准化的同时修正其他与行业标准不符的数据结构问题，以提升系统的专业性和兼容性。

#### 验收标准

1. THE K线频率枚举 SHALL 保持当前 `1m/5m/15m/30m/60m/1d/1w/1M` 格式（已符合行业惯例），但 SHALL 清理旧版 `"minute"` 兼容映射，统一使用标准频率值
2. THE 指数代码硬编码 SHALL 统一收敛到一个常量模块（如 `app/core/constants.py` 或 Symbol_Utils 中），消除多处重复定义
3. THE `SectorConstituent` 模型 SHALL 确保 `symbol` 字段存储格式与其他业务表一致（标准代码）
