# K 线重复数据归一化修复需求

## 背景

选股结果展开的日 K 图中出现大量相邻重复 K 线。截图中同一日期附近出现两根形态高度一致的日 K，之前已经处理过部分重复写入问题，但问题仍然复现。

本次排查确认，当前不是 TimescaleDB 中完全相同 `(time, symbol, freq, adj_type)` 主键重复，而是同一交易日被写成了两个不同时间戳：

- `2026-01-01 ~ 2026-03-01`、`freq='1d'` 范围内，按 `(symbol, freq, (time AT TIME ZONE 'Asia/Shanghai')::date, adj_type)` 口径统计，存在 `185711` 个重复交易日组、`371422` 行重复，最大每组 2 行。
- 典型样本：`000001.SZ` 在交易日 `2026-02-27` 同时存在 `2026-02-26 16:00:00 UTC` 和 `2026-02-27 00:00:00 UTC` 两条日 K，收盘价均为 `10.9000`。
- 同期 `sector_kline` 按 `(sector_code, data_source, freq, trade_day)` 口径未发现重复组。
- `adjustment_factor` 按 `(symbol, trade_date, adj_type)` 有主键约束，未发现同键重复；但当前 Tushare 写入路径将 `adj_factor` 写为 `adj_type=0`，与模型注释 `1=前复权, 2=后复权` 不一致，属于相邻数据一致性风险。

根因判断：

1. 日线数据缺少统一的“交易日归一化键”。当前唯一索引使用精确 `time`，所以 `2026-02-26 16:00 UTC` 和 `2026-02-27 00:00 UTC` 不冲突。
2. 责任入口已定位到 **Tushare 在线导入服务**，即 `app/tasks/tushare_import.py` 中的 Celery 任务 `app.tasks.tushare_import.run_import`，经由 `app/services/data_engine/tushare_import_service.py` 从前端在线导入入口触发。直接受影响 API 是注册表中的 `daily`，同类风险还包括 `weekly/monthly/bak_daily/rt_k/index_daily` 等 `target_table="kline"` 的 Tushare 时序接口。
3. 旧版 Tushare 时序写入在 `_write_to_kline()` / `_write_to_sector_kline()` 内直接由 `trade_date` 构造写入时间，未形成跨入口统一交易日键；后续规范 UTC 零点入口再次导入同一日期范围后，旧的 `前一日 16:00 UTC` 与新的 `当日 00:00 UTC` 因精确主键不同而并存。
4. 当前导入日志与数据分布相互吻合：`tushare_import_log` 中 `daily` 在 2026-04-21、2026-04-22、2026-04-27、2026-04-28、2026-04-30 多次完成大范围导入，例如 `20250421~20260421`、`20260101~20260427`、`20230428~20260528`、`20230101~20250501`；当前库中 `2025-04-28`、`2025-12-31`、`2026-02-27` 等交易日仍存在数千条 `前一日16:00 UTC` 残留，而 `2026-04` 已被另一轮修复清理为 0，说明问题是旧 Tushare 在线导入残留未全量清理，而不是前端重复渲染自身制造的数据。
5. 之前处理后仍复现的原因有两层：
   - 历史提交 `.kiro/specs/kline-timezone-dedup/` 主要修了 `TushareAdapter.fetch_kline()`、本地导入和行情适配器，没有覆盖当前实际在线批量导入入口 `app/tasks/tushare_import.py::_write_to_kline()`。
   - 旧脚本 `scripts/cleanup_duplicate_kline.py` 以 `time - interval '16 hours'` 查找同 UTC 日的 `00:00` 记录，而本次真实重复关系是 `前一日 16:00 UTC -> 当日 00:00 UTC`，归并方向应为 `time + interval '8 hours'`；已有 `scripts/repair_tushare_timeseries_timezone.py` 方向正确，但此前只清理了部分日期，例如 2026-04，未覆盖 2026-01 ~ 2026-03 和全量历史。
6. 查询 API 和前端图表直接使用 `bar.time.isoformat()` / `slice(0, 10)` 作为 X 轴日期，导致时区偏移后的同一交易日被显示成重复日期。
7. `/api/v1/data/kline/{symbol}` 本地查询未明确区分“原始 K 线基底”和“前复权展示口径”，后续若数据库存在多复权版本，会把原始/复权数据混在同一图表中。`adj_type=0` 过滤的目的不是取消前复权展示，而是确保动态前复权计算只以原始 K 线为输入。
8. `KlineRepository.bulk_insert()` 仍有剥离股票后缀的旧逻辑，与系统统一标准代码规范冲突，虽然当前 `2026-01 ~ 2026-02` 样本均为标准代码，但该路径会造成新写入数据查询不到或形成代码口径分裂。

## 术语

- 精确时间键：当前 `kline` 表使用的 `(time, symbol, freq, adj_type)`。
- 交易日键：日/周/月 K 线用于业务去重的日期键，日线为交易日，周/月线为对应周期日期。
- 原始 K 线基底：`kline.adj_type=0` 的不复权行情，是前端“原始”展示和动态“前复权”计算共同使用的基础数据。
- 前复权展示口径：前端请求 `adj_type=1` 时返回的 K 线口径。当前推荐由原始 K 线基底叠加 `adjustment_factor.adj_type=1` 动态计算得到，不要求把前复权 K 线实体存入 `kline`。
- 时区偏移重复：同一交易日同一股票同一频率同一复权类型，因为 UTC 零点和北京时间零点转换差异产生的两条记录。
- 展示重复：后端返回多条业务等价 K 线，前端按日期字符串渲染后显示为重复 K 线。
- 全库重复数据：TimescaleDB 与 PostgreSQL 中，按模型主键、唯一约束、Tushare 注册表 `conflict_columns` 或本 spec 明确业务唯一键识别出的重复业务记录；不包括审计日志、导入日志、任务进度、历史流水等天然允许多条记录的事件型数据。

## 需求

### 1. K 线日频数据必须按交易日归一化去重

**用户故事：** 作为量化交易员，我希望同一股票同一交易日只出现一根日 K，避免图表、指标和选股因子被重复数据扰乱。

#### 验收标准

1. WHEN 写入 `freq='1d'` 的 K 线 THEN 系统 SHALL 将时间统一归一化到同一交易日的规范时间，不得因为 UTC 零点和北京时间零点差异形成两条业务等价记录。
2. WHEN 目标表已存在同一 `(symbol, freq, trade_day, adj_type)` 的记录 THEN 写入 SHALL 执行幂等更新或跳过，不得新增第二条日 K。
3. WHEN 原始数据包含显式交易日期字段（如 `trade_date`、`日期`、CSV 日期列）THEN 系统 SHALL 优先使用该字段作为交易日，不得通过服务器本地时区推断。
4. WHEN 原始数据只有 `datetime` 时间戳 THEN aware `datetime` SHALL 先转换到 `Asia/Shanghai` 再取日期；naive 日线日期 SHALL 直接使用其日期部分作为交易日。
5. WHEN 生成日/周/月 K 的规范写入时间 THEN 系统 SHALL 使用 `datetime.combine(trade_day, 00:00:00, tzinfo=UTC)`，确保同一交易日只有一个精确时间键。
6. WHEN 执行历史清洗 THEN 系统 SHALL 将同一交易日重复组压缩为 1 条，并保留字段更完整或更可信的数据。
7. WHEN 清洗遇到两条重复记录字段冲突 THEN 系统 SHALL 按明确优先级选择保留行，并记录冲突数量和样本。
8. WHEN 清洗完成 THEN `2026-01-01 ~ 2026-03-01` 的 `freq='1d'` 重复交易日组 SHALL 从 `185711` 降为 `0`。

### 2. 所有 K 线入口必须使用统一时间和代码规范

**用户故事：** 作为数据维护者，我希望 Tushare、本地 CSV、AkShare、实时行情和仓储层都使用同一套 K 线规范，避免这次修完后其他入口再次写入重复数据。

#### 验收标准

1. WHEN 任意入口创建 `KlineBar` THEN 日/周/月 K 线 SHALL 通过统一工具归一化时间，分钟级 K 线 SHALL 保留真实分钟时间。
2. WHEN `KlineRepository.bulk_insert()` 写入股票代码 THEN SHALL 使用 `symbol_utils.to_standard()`，不得剥离 `.SH/.SZ/.BJ` 后缀。
3. WHEN 写入无法标准化的代码 THEN 系统 SHALL 跳过该行并记录诊断，而不是写入非标准代码。
4. WHEN Tushare `daily/weekly/monthly/rt_k` 写入 `kline` THEN SHALL 与仓储层使用同一套归一化逻辑。
5. WHEN AkShare 或本地 CSV 返回无时区日期 THEN 系统 SHALL 按交易日日期处理，而不是隐式按运行环境时区或 UTC instant 处理。

### 3. K 线查询 API 必须返回唯一且复权类型正确的数据

**用户故事：** 作为前端使用者，我希望切换“原始/前复权”时图表只展示所选口径，不混入其他复权类型或重复日期。

#### 验收标准

1. WHEN 请求 `/api/v1/data/kline/{symbol}?adj_type=0` THEN 查询 SHALL 只返回原始 K 线基底，即 `kline.adj_type=0` 的本地 K 线。
2. WHEN 请求 `/api/v1/data/kline/{symbol}?adj_type=1` THEN 系统 SHALL 仍先读取 `kline.adj_type=0` 原始 K 线基底，再叠加 `adjustment_factor.adj_type=1` 动态生成前复权 K 线响应。
3. WHEN 前复权因子缺失 THEN 系统 SHALL 明确返回降级原因或响应字段，不得静默把原始 K 线伪装为前复权 K 线。
4. WHEN 未来支持实体化存储前复权 K 线 THEN 系统 SHALL 通过明确策略选择“动态计算”或“读取实体化前复权”，不得在一次响应中混合两个来源。
5. WHEN 返回日/周/月 K 线给前端 THEN 响应 SHALL 包含稳定的交易日期字段，例如 `trade_date`，前端不得依赖 `time.slice(0, 10)` 推断交易日。
6. WHEN 后端发现查询结果中存在同一交易日多条记录 THEN SHALL 在返回前按交易日去重，并记录 warning，避免用户界面继续显示重复 K 线。
7. WHEN 前端构建 ECharts X 轴 THEN SHALL 优先使用后端 `trade_date`，并对重复日期做防御性去重。
8. WHEN 前端在“原始”和“前复权”之间切换 THEN SHALL 分别请求 `adj_type=0` 和 `adj_type=1`，并为两个口径分别缓存，避免复用错误口径的数据。
9. WHEN 分钟级 K 线返回给前端 THEN 响应 SHALL 包含适合展示的本地交易时间字段，例如 `display_time` 或 `trade_time`，前端不得直接用 UTC ISO 字符串切片展示 HH:mm。
10. WHEN 回测、选股或前复权计算需要从 `KlineBar.time` 推导交易日 THEN SHALL 使用统一交易日推导工具，不得直接使用 `bar.time.date()` 处理日线数据。

### 4. 其他时序和导入数据必须纳入重复巡检

**用户故事：** 作为数据维护者，我希望系统能同样检查板块行情、复权因子、资金流、基础信息和 Tushare 业务表，确认是否存在同类重复问题。

#### 验收标准

1. WHEN 执行重复巡检 THEN 系统 SHALL 检查 TimescaleDB 中 `kline`、`sector_kline`、`adjustment_factor` 的业务唯一键重复。
2. WHEN 检查 `sector_kline` THEN 系统 SHALL 按 `(sector_code, data_source, freq, trade_day)` 口径识别重复；当前样本重复数 SHOULD 为 0。
3. WHEN 检查 `adjustment_factor` THEN 系统 SHALL 按 `(symbol, trade_date, adj_type)` 检查同键重复，并额外报告 `adj_type=0` 异常行。
4. WHEN 检查 PostgreSQL Tushare 表 THEN 系统 SHALL 基于注册表 `conflict_columns` 或模型唯一约束生成重复检测 SQL。
5. WHEN 发现其他表重复 THEN 系统 SHALL 给出清洗策略、唯一约束补强方案和回归测试。
6. WHEN 巡检完成 THEN 系统 SHALL 输出可读报告，包括表名、重复口径、重复组数、重复行数、样本和建议动作。

### 5. 数据修复必须可回滚、可验证

**用户故事：** 作为开发者，我希望清洗生产级行情数据时有备份、批处理和验证步骤，避免误删有效行情。

#### 验收标准

1. WHEN 执行历史清洗前 THEN 系统 SHALL 生成重复组快照或备份表，记录被删除候选行。
2. WHEN 清洗大量 `kline` 数据 THEN SHALL 分时间段或分股票批处理，避免长事务和 TimescaleDB 大表锁表。
3. WHEN 清洗脚本运行 THEN SHALL 支持 dry-run，仅输出将处理的重复组和样本。
4. WHEN 清洗脚本完成 THEN SHALL 输出删除行数、保留行数、冲突组数和复查 SQL 结果。
5. WHEN 自动化测试运行 THEN SHALL 覆盖时间归一化、幂等写入、查询去重、复权过滤和巡检报告。
6. WHEN 执行交叉验证 THEN SHALL 逐项核对 requirements、design、tasks 与现有代码入口，确保所有受影响文件都有任务覆盖。

### 6. 必须清理库中所有可识别重复数据

**用户故事：** 作为系统维护者，我希望一次性清理当前数据库中所有可识别的重复业务数据，并建立全库巡检报告，这样后续选股、回测、风控和数据预览不再被历史脏数据干扰。

#### 验收标准

1. WHEN 执行全库重复清理前 THEN 系统 SHALL 先生成 TimescaleDB 与 PostgreSQL 的全库重复审计报告，列出每张表的重复口径、重复组数、重复行数、样本、风险等级和建议动作。
2. WHEN 表存在主键、唯一约束或注册表 `conflict_columns` THEN 系统 SHALL 按该约束作为默认重复口径；WHEN 约束缺失但业务唯一键明确 THEN SHALL 在报告中声明推导口径并纳入清理。
3. WHEN 表属于审计日志、导入日志、任务进度、交易流水或其他事件型数据 THEN 系统 SHALL 默认只审计不删除，除非另有明确业务唯一口径。
4. WHEN 清理任意表的重复数据 THEN 系统 SHALL 在写库前创建备份快照或导出重复候选，记录保留行、删除行、保留原因和字段冲突摘要。
5. WHEN 重复记录字段完全一致 THEN 系统 SHALL 保留一条 canonical 记录并删除其余重复记录。
6. WHEN 重复记录字段不一致 THEN 系统 SHALL 按表级策略合并或保留最可信记录；若策略无法自动判定 THEN SHALL 输出人工确认清单，不得静默删除。
7. WHEN 清理 K 线类时区重复 THEN 系统 SHALL 使用交易日归一化口径处理 `kline/sector_kline`，并验证 `1d/1w/1M` 不再存在同业务日期多条记录。
8. WHEN 清理 PostgreSQL Tushare 业务表 THEN 系统 SHALL 基于 `tushare_registry.py` 的 `target_table + conflict_columns` 去重，并补充缺失唯一约束的迁移建议。
9. WHEN 全库清理完成 THEN 系统 SHALL 重新运行全库重复审计，确认所有可自动清理表的重复组数为 `0`，剩余不可自动清理项必须有明确原因、样本和后续处理方案。
10. WHEN 后续新增导入或写入路径 THEN 系统 SHALL 有重复巡检测试或幂等写入测试，防止已清理重复数据再次出现。
