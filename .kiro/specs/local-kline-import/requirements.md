# 需求文档：本地A股分时数据与复权因子导入

## 简介

本功能为A股右侧量化选股系统提供本地A股分时数据和复权因子的批量导入能力。数据源为 `/Users/poper/AData` 目录，包含三大市场分类（沪深、京市、指数）的分钟级K线数据和前复权/后复权因子。数据按 `市场→频率→月份→日期ZIP` 四级目录结构组织，支持1分钟、5分钟、15分钟、30分钟、60分钟五种频率。导入后的K线数据写入 TimescaleDB 超表，复权因子存储后可用于生成前复权/后复权K线，供选股策略、回测引擎等下游模块使用。

## 术语表

- **导入服务（Import_Service）**：负责扫描本地目录、解压ZIP文件、解析CSV数据并转换为 KlineBar 或 AdjustmentFactor 的后端服务模块
- **K线仓储（Kline_Repository）**：负责将 KlineBar 批量写入 TimescaleDB 超表的数据访问层（已有模块）
- **数据目录（Data_Directory）**：本地数据文件所在的根目录，默认为 `/Users/poper/AData`，可通过配置项覆盖
- **市场分类（Market_Category）**：数据按市场划分为三类：沪深（`A股_分时数据_沪深`）、京市（`A股_分时数据_京市`）、指数（`A股_分时数据_指数`）
- **频率目录（Freq_Directory）**：市场目录下按频率划分的子目录，命名格式为 `{N}分钟_按月归档`（如 `1分钟_按月归档`、`5分钟_按月归档`）
- **月份目录（Month_Directory）**：频率目录下按年月划分的子目录，命名格式为 `YYYY-MM`（如 `2026-03`）
- **日期ZIP文件（Daily_ZIP）**：月份目录下按交易日归档的ZIP文件，命名格式为 `YYYYMMDD_{freq_suffix}.zip`（如 `20260302_1min.zip`）
- **CSV数据文件（CSV_File）**：ZIP文件解压后得到的逗号分隔值文件，每个文件对应一只股票/指数的当日分时数据
- **频率（Freq）**：K线时间周期，取值为 `1m`、`5m`、`15m`、`30m`、`60m`
- **复权因子（Adjustment_Factor）**：用于调整历史K线价格的因子数据，分为前复权（`qfq`）和后复权（`hfq`）两种
- **前复权（Forward_Adjustment）**：以最新价格为基准向前调整历史价格，复权因子ZIP文件为 `复权因子_前复权.zip`
- **后复权（Backward_Adjustment）**：以上市首日价格为基准向后调整价格，复权因子ZIP文件为 `复权因子_后复权.zip`
- **导入任务（Import_Task）**：通过 Celery 异步执行的数据导入任务
- **导入进度（Import_Progress）**：记录在 Redis 中的导入任务执行状态
- **导入页面（Import_Page）**：Vue 3 前端页面组件，提供本地数据导入的参数配置、任务触发和进度展示功能

## 需求

### 需求 1：扫描多级数据目录结构

**用户故事：** 作为量化工程师，我希望系统能自动扫描 AData 目录下的多级目录结构，识别市场分类、频率和月份，以便发现待导入的K线数据文件。

#### 验收标准

1. WHEN 导入任务启动时，THE Import_Service SHALL 按照 `{Data_Directory}/{Market_Category}/{Freq_Directory}/{Month_Directory}/{Daily_ZIP}` 四级结构扫描ZIP文件
2. THE Import_Service SHALL 识别三种 Market_Category 目录：`A股_分时数据_沪深`（沪深市场）、`A股_分时数据_京市`（京市市场）、`A股_分时数据_指数`（指数数据）
3. THE Import_Service SHALL 识别五种 Freq_Directory：`1分钟_按月归档`、`5分钟_按月归档`、`15分钟_按月归档`、`30分钟_按月归档`、`60分钟_按月归档`
4. THE Import_Service SHALL 从 Freq_Directory 名称中提取标准频率映射：`1分钟_按月归档` → `1m`、`5分钟_按月归档` → `5m`、`15分钟_按月归档` → `15m`、`30分钟_按月归档` → `30m`、`60分钟_按月归档` → `60m`
5. THE Import_Service SHALL 通过配置项 `LOCAL_KLINE_DATA_DIR` 读取 Data_Directory 路径，默认值为 `/Users/poper/AData`
6. IF Data_Directory 路径不存在或不可读，THEN THE Import_Service SHALL 记录错误日志并返回包含错误原因的失败结果
7. WHEN 扫描完成时，THE Import_Service SHALL 记录日志，包含各市场分类发现的ZIP文件数量

### 需求 2：解压与解析沪深市场K线数据

**用户故事：** 作为量化工程师，我希望系统能正确解压沪深市场的日期ZIP文件并解析其中的CSV格式K线数据，以便将原始数据转换为系统可用的结构化数据。

#### 验收标准

1. WHEN 处理一个 Daily_ZIP 时，THE Import_Service SHALL 在内存中解压该文件，提取其中所有 CSV_File
2. THE Import_Service SHALL 从 CSV 文件名推断股票代码：`sz000001.csv` → `000001`、`sh600000.csv` → `600000`（去除 `sz`/`sh` 前缀，保留6位数字代码）
3. WHEN 解析沪深市场 CSV_File 时，THE Import_Service SHALL 按表头 `时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额,涨幅,振幅` 映射字段，将每行数据转换为 KlineBar 对象
4. THE Import_Service SHALL 解析时间字段格式 `YYYY/MM/DD HH:MM`（如 `2026/04/01 09:30`）为有效的 datetime 值
5. IF Daily_ZIP 损坏或无法解压，THEN THE Import_Service SHALL 记录错误日志（包含文件路径），跳过该文件并继续处理下一个文件
6. IF CSV_File 中某行数据格式不合法或字段缺失，THEN THE Import_Service SHALL 跳过该行，记录警告日志，并继续解析后续行

### 需求 3：解压与解析京市市场K线数据

**用户故事：** 作为量化工程师，我希望系统能正确解压京市（北交所）市场的日期ZIP文件并解析其中的CSV格式K线数据。

#### 验收标准

1. THE Import_Service SHALL 从京市 CSV 文件名推断股票代码：`bj920000.csv` → `920000`（去除 `bj` 前缀，保留数字代码）
2. WHEN 解析京市 CSV_File 时，THE Import_Service SHALL 按与沪深市场相同的表头格式映射字段（`时间,代码,名称,开盘价,收盘价,最高价,最低价,成交量,成交额,涨幅,振幅`）
3. THE Import_Service SHALL 对京市数据使用与沪深市场相同的解析和校验逻辑

### 需求 4：解压与解析指数K线数据

**用户故事：** 作为量化工程师，我希望系统能正确解压指数数据的日期ZIP文件并解析其中的CSV格式K线数据，特别处理指数数据缺少成交量列的情况。

#### 验收标准

1. THE Import_Service SHALL 从指数 CSV 文件名推断代码：`000001.csv` → `000001`（无前缀，直接使用文件名中的数字代码）
2. WHEN 解析指数 CSV_File 时，THE Import_Service SHALL 按表头 `时间,代码,名称,开盘价,收盘价,最高价,最低价,成交额,涨幅,振幅` 映射字段（注意：无 `成交量` 列）
3. WHERE 指数 CSV 不包含 `成交量` 列，THE Import_Service SHALL 将 KlineBar 的 volume 字段设为 0
4. THE Import_Service SHALL 对指数数据的 volume 校验规则放宽，允许 volume 为 0

### 需求 5：K线数据校验

**用户故事：** 作为量化工程师，我希望系统在导入前对K线数据进行基本校验，以确保写入数据库的数据质量。

#### 验收标准

1. THE Import_Service SHALL 校验每条 KlineBar 的 open、high、low、close 均为正数
2. THE Import_Service SHALL 校验每条 KlineBar 满足 low ≤ open ≤ high 且 low ≤ close ≤ high
3. THE Import_Service SHALL 校验每条 KlineBar 的 volume 为非负整数
4. THE Import_Service SHALL 校验每条 KlineBar 的 time 字段为有效的日期时间值
5. THE Import_Service SHALL 校验 freq 字段取值为 `1m`、`5m`、`15m`、`30m`、`60m` 之一
6. IF 某条 KlineBar 未通过校验，THEN THE Import_Service SHALL 跳过该条记录，记录警告日志（包含股票代码、时间、失败原因），并继续处理后续记录

### 需求 6：批量写入 TimescaleDB

**用户故事：** 作为量化工程师，我希望解析后的K线数据能高效写入 TimescaleDB，以便下游选股和回测模块使用。

#### 验收标准

1. THE Import_Service SHALL 调用 Kline_Repository 的 bulk_insert 方法将校验通过的 KlineBar 批量写入 TimescaleDB
2. THE Import_Service SHALL 按每批不超过 1000 条的粒度分批写入，避免单次 SQL 语句过大
3. THE Kline_Repository SHALL 使用 INSERT ... ON CONFLICT DO NOTHING 策略，保证重复数据（相同 time + symbol + freq + adj_type）不会重复写入
4. WHEN 单个 Daily_ZIP 的数据全部写入完成后，THE Import_Service SHALL 记录日志，包含文件路径、解析行数和实际插入行数

### 需求 7：支持市场分类选择

**用户故事：** 作为量化工程师，我希望能选择导入特定市场分类的数据，以便按需导入沪深、京市或指数数据。

#### 验收标准

1. THE Import_Task SHALL 接受可选的市场分类参数 `markets`，取值为 `hushen`（沪深）、`jingshi`（京市）、`zhishu`（指数）的列表
2. WHERE 指定了 `markets` 参数，THE Import_Service SHALL 仅扫描和导入对应市场分类目录下的数据
3. WHERE 未指定 `markets` 参数，THE Import_Service SHALL 导入所有三种市场分类的数据

### 需求 8：支持频率选择

**用户故事：** 作为量化工程师，我希望系统支持按频率过滤导入数据，以满足不同时间维度的分析需求。

#### 验收标准

1. THE Import_Service SHALL 支持导入频率为 `1m`、`5m`、`15m`、`30m`、`60m` 的K线数据
2. WHEN 导入任务启动时，THE Import_Service SHALL 接受可选的频率过滤参数 `freqs`，仅扫描对应的 Freq_Directory
3. WHERE 未指定频率过滤参数，THE Import_Service SHALL 导入所有五种频率的数据

### 需求 9：支持日期范围过滤

**用户故事：** 作为量化工程师，我希望能按月份范围过滤导入数据，以便只导入特定时间段的数据。

#### 验收标准

1. THE Import_Task SHALL 接受可选的起始月份参数 `start_month`（格式 `YYYY-MM`）和结束月份参数 `end_month`（格式 `YYYY-MM`）
2. WHERE 指定了日期范围参数，THE Import_Service SHALL 仅扫描名称在 `start_month` 至 `end_month` 范围内的 Month_Directory
3. WHERE 未指定日期范围参数，THE Import_Service SHALL 扫描所有 Month_Directory

### 需求 10：复权因子导入

**用户故事：** 作为量化工程师，我希望系统能导入前复权和后复权因子数据，以便生成复权K线用于回测和策略分析。

#### 验收标准

1. THE Import_Service SHALL 支持从 `{Data_Directory}/复权因子/复权因子_前复权.zip` 导入前复权因子数据
2. THE Import_Service SHALL 支持从 `{Data_Directory}/复权因子/复权因子_后复权.zip` 导入后复权因子数据
3. THE Import_Service SHALL 解析复权因子 CSV 文件，表头为 `股票代码,交易日期,复权因子`，其中交易日期格式为 `YYYYMMDD`
4. THE Import_Service SHALL 从复权因子 CSV 文件名推断股票代码：`000001.SZ.csv` → `000001`、`600000.SH.csv` → `600000`（去除 `.SZ`/`.SH` 后缀）
5. THE Import_Service SHALL 将前复权因子数据标记为 `adj_type=1`，后复权因子数据标记为 `adj_type=2`
6. THE Import_Service SHALL 将复权因子数据存储到数据库，包含字段：symbol（股票代码）、trade_date（交易日期）、adj_factor（复权因子值）、adj_type（复权类型）
7. IF 复权因子 ZIP 文件不存在或损坏，THEN THE Import_Service SHALL 记录错误日志并跳过该文件，继续处理其他数据

### 需求 11：Celery 异步任务调度

**用户故事：** 作为量化工程师，我希望数据导入通过 Celery 异步任务执行，支持手动触发和定时调度，以便灵活管理导入流程。

#### 验收标准

1. THE Import_Task SHALL 注册到 Celery 的 `data_sync` 队列，支持通过 Celery Beat 定时调度
2. THE Import_Task SHALL 支持通过 API 接口手动触发，接受可选参数：市场分类列表、频率过滤列表、日期范围、复权因子类型列表、强制全量导入开关
3. WHILE Import_Task 正在执行时，THE Import_Service SHALL 将导入进度写入 Redis，包含状态（running / completed / failed）、已处理文件数、成功文件数、失败文件数、总插入行数
4. IF 同一时刻已有一个 Import_Task 正在运行，THEN THE Import_Service SHALL 拒绝启动新任务并返回提示信息

### 需求 12：增量导入支持

**用户故事：** 作为量化工程师，我希望系统支持增量导入，避免每次全量重新导入浪费时间。

#### 验收标准

1. THE Import_Service SHALL 记录每个已成功导入的ZIP文件的路径和文件修改时间到 Redis 缓存
2. WHEN 扫描到一个 Daily_ZIP 时，THE Import_Service SHALL 检查该文件是否已导入且文件修改时间未变化
3. WHERE 文件已导入且修改时间未变化，THE Import_Service SHALL 跳过该文件
4. WHERE 文件修改时间发生变化，THE Import_Service SHALL 重新导入该文件（依赖数据库 ON CONFLICT DO NOTHING 保证幂等性）
5. THE Import_Task SHALL 接受可选的 `force` 参数，设为 True 时忽略增量检查，强制全量导入

### 需求 13：可配置的数据目录路径

**用户故事：** 作为量化工程师，我希望数据目录路径可通过环境变量配置，以便在不同环境中灵活部署。

#### 验收标准

1. THE Import_Service SHALL 从 Settings 配置类读取 `local_kline_data_dir` 配置项
2. THE Settings SHALL 支持通过环境变量 `LOCAL_KLINE_DATA_DIR` 设置数据目录路径
3. WHERE `LOCAL_KLINE_DATA_DIR` 未设置，THE Settings SHALL 使用默认值 `/Users/poper/AData`

### 需求 14：导入结果汇总与日志

**用户故事：** 作为量化工程师，我希望每次导入完成后能看到完整的结果汇总，以便了解导入质量和排查问题。

#### 验收标准

1. WHEN 导入任务完成时，THE Import_Service SHALL 返回结果摘要字典，包含：总文件数、成功文件数、失败文件数、跳过文件数、总解析行数、总插入行数、总跳过行数（校验失败）、耗时秒数、各市场分类的统计
2. WHEN 导入任务完成时，THE Import_Service SHALL 将结果摘要写入 Redis 缓存（键为 `import:local_kline:result`），有效期 24 小时
3. IF 存在导入失败的文件，THEN THE Import_Service SHALL 在结果摘要中包含失败文件路径列表及对应错误原因

### 需求 15：API 接口

**用户故事：** 作为量化工程师，我希望通过 REST API 触发导入任务和查询导入状态，以便与前端界面集成。

#### 验收标准

1. THE API SHALL 提供 POST `/api/v1/data/import/local-kline` 端点，用于触发本地数据导入任务，接受可选参数：`markets`（市场分类列表）、`freqs`（频率列表）、`start_month`（起始月份）、`end_month`（结束月份）、`adj_factors`（复权因子类型列表，可选 `qfq`/`hfq`）、`force`（强制全量）
2. THE API SHALL 提供 GET `/api/v1/data/import/local-kline/status` 端点，用于查询当前导入任务的进度和最近一次导入结果
3. WHEN 触发导入请求成功时，THE API SHALL 返回任务 ID 和状态码 202（Accepted）
4. IF 当前已有导入任务正在运行，THEN THE API SHALL 返回状态码 409（Conflict）和提示信息

### 需求 16：本地数据导入前端页面

**用户故事：** 作为量化工程师，我希望有一个本地数据导入的前端页面，用于配置和触发导入任务，以便通过可视化界面管理导入流程。

#### 验收标准

1. THE Import_Page SHALL 作为 Vue 3 页面组件（Composition API、`<script setup>`）注册到 vue-router，路由路径为 `/data/local-import`
2. THE Import_Page SHALL 提供市场分类多选控件，支持选择 `沪深`、`京市`、`指数` 中的一种或多种，默认全选
3. THE Import_Page SHALL 提供频率多选控件，支持选择 `1m`、`5m`、`15m`、`30m`、`60m` 中的一种或多种频率，默认全选
4. THE Import_Page SHALL 提供起始月份和结束月份选择器，允许用户指定导入的日期范围（可选）
5. THE Import_Page SHALL 提供"导入复权因子"选项区域，允许用户选择导入前复权因子、后复权因子或两者都导入，默认不导入
6. THE Import_Page SHALL 提供"强制全量导入"开关，对应 Import_Task 的 `force` 参数，默认关闭
7. WHEN 用户点击"开始导入"按钮时，THE Import_Page SHALL 调用 POST API 触发导入任务，并将按钮置为禁用状态直到收到响应
8. IF 后端返回状态码 409，THEN THE Import_Page SHALL 显示"已有导入任务正在运行"的提示信息
9. WHILE 导入任务正在运行时，THE Import_Page SHALL 每 3 秒轮询 GET API，展示实时进度信息，包括状态、已处理文件数、成功文件数、失败文件数、总插入行数
10. THE Import_Page SHALL 以进度条形式展示导入进度百分比（已处理文件数 / 总文件数）
11. WHEN 导入任务完成或失败时，THE Import_Page SHALL 停止轮询并展示结果摘要
12. IF 存在导入失败的文件，THEN THE Import_Page SHALL 在结果摘要中展示失败文件列表及对应错误原因
13. THE Import_Page SHALL 使用 Pinia store 管理导入状态，确保页面切换后返回时状态不丢失
14. THE Import_Page SHALL 在页面挂载时检查是否有正在运行的导入任务，若有则自动恢复进度轮询
15. THE Import_Page SHALL 遵循项目现有的暗色主题样式规范，与 DataManageView 保持视觉一致性
