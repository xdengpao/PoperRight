# 需求文档：本地分钟级K线数据导入

## 简介

本功能为A股右侧量化选股系统提供本地分钟级K线数据的批量导入能力。量化工程师将本地 `/Users/poper/AData` 目录下的ZIP压缩格式K线数据文件导入系统，支持1分钟、5分钟、15分钟、30分钟、60分钟五种频率。导入后的数据写入 TimescaleDB 超表，供选股策略、回测引擎等下游模块使用。

## 术语表

- **导入服务（Import_Service）**：负责扫描本地目录、解压ZIP文件、解析CSV数据并转换为 KlineBar 的后端服务模块
- **K线仓储（Kline_Repository）**：负责将 KlineBar 批量写入 TimescaleDB 超表的数据访问层（已有模块）
- **数据目录（Data_Directory）**：本地K线ZIP文件所在的根目录，默认为 `/Users/poper/AData`，可通过配置项覆盖
- **ZIP数据文件（ZIP_File）**：包含CSV格式K线数据的ZIP压缩文件，位于数据目录的子文件夹中
- **CSV数据文件（CSV_File）**：ZIP文件解压后得到的逗号分隔值文件，每行代表一根K线
- **频率（Freq）**：K线时间周期，取值为 `1m`、`5m`、`15m`、`30m`、`60m`
- **导入任务（Import_Task）**：通过 Celery 异步执行的K线数据导入任务
- **导入进度（Import_Progress）**：记录在 Redis 中的导入任务执行状态，包括已处理文件数、成功数、失败数等
- **导入页面（Import_Page）**：Vue 3 前端页面组件，提供本地K线数据导入的参数配置、任务触发、进度展示和定时任务管理功能

## 需求

### 需求 1：扫描本地数据目录

**用户故事：** 作为量化工程师，我希望系统能自动扫描指定本地目录下的ZIP数据文件，以便发现待导入的K线数据。

#### 验收标准

1. WHEN 导入任务启动时，THE Import_Service SHALL 递归扫描 Data_Directory 下所有子文件夹，收集所有扩展名为 `.zip` 的文件路径列表
2. THE Import_Service SHALL 通过配置项 `LOCAL_KLINE_DATA_DIR` 读取 Data_Directory 路径，默认值为 `/Users/poper/AData`
3. IF Data_Directory 路径不存在或不可读，THEN THE Import_Service SHALL 记录错误日志并返回包含错误原因的失败结果
4. WHEN 扫描完成时，THE Import_Service SHALL 记录日志，包含发现的ZIP文件总数

### 需求 2：解压与解析ZIP数据文件

**用户故事：** 作为量化工程师，我希望系统能正确解压ZIP文件并解析其中的CSV格式K线数据，以便将原始数据转换为系统可用的结构化数据。

#### 验收标准

1. WHEN 处理一个 ZIP_File 时，THE Import_Service SHALL 在内存中解压该文件，提取其中的 CSV_File 内容
2. WHEN 解析 CSV_File 时，THE Import_Service SHALL 将每行数据映射为 KlineBar 对象，包含以下字段：time（时间戳）、symbol（股票代码）、freq（频率）、open（开盘价）、high（最高价）、low（最低价）、close（收盘价）、volume（成交量）、amount（成交额）
3. THE Import_Service SHALL 根据文件路径或文件名推断股票代码（symbol）和K线频率（freq）
4. IF ZIP_File 损坏或无法解压，THEN THE Import_Service SHALL 记录错误日志（包含文件路径），跳过该文件并继续处理下一个文件
5. IF CSV_File 中某行数据格式不合法或字段缺失，THEN THE Import_Service SHALL 跳过该行，记录警告日志，并继续解析后续行

### 需求 3：数据校验

**用户故事：** 作为量化工程师，我希望系统在导入前对K线数据进行基本校验，以确保写入数据库的数据质量。

#### 验收标准

1. THE Import_Service SHALL 校验每条 KlineBar 的 open、high、low、close 均为正数
2. THE Import_Service SHALL 校验每条 KlineBar 满足 low ≤ open ≤ high 且 low ≤ close ≤ high
3. THE Import_Service SHALL 校验每条 KlineBar 的 volume 为非负整数
4. THE Import_Service SHALL 校验每条 KlineBar 的 time 字段为有效的日期时间值
5. THE Import_Service SHALL 校验 freq 字段取值为 `1m`、`5m`、`15m`、`30m`、`60m` 之一
6. IF 某条 KlineBar 未通过校验，THEN THE Import_Service SHALL 跳过该条记录，记录警告日志（包含股票代码、时间、失败原因），并继续处理后续记录

### 需求 4：批量写入 TimescaleDB

**用户故事：** 作为量化工程师，我希望解析后的K线数据能高效写入 TimescaleDB，以便下游选股和回测模块使用。

#### 验收标准

1. THE Import_Service SHALL 调用 Kline_Repository 的 bulk_insert 方法将校验通过的 KlineBar 批量写入 TimescaleDB
2. THE Import_Service SHALL 按每批不超过 1000 条的粒度分批写入，避免单次 SQL 语句过大
3. THE Kline_Repository SHALL 使用 INSERT ... ON CONFLICT DO NOTHING 策略，保证重复数据（相同 time + symbol + freq + adj_type）不会重复写入
4. WHEN 单个ZIP文件的数据全部写入完成后，THE Import_Service SHALL 记录日志，包含文件路径、解析行数和实际插入行数

### 需求 5：支持五种分钟级频率

**用户故事：** 作为量化工程师，我希望系统支持导入1分钟、5分钟、15分钟、30分钟、60分钟五种频率的K线数据，以满足不同时间维度的分析需求。

#### 验收标准

1. THE Import_Service SHALL 支持导入频率为 `1m`、`5m`、`15m`、`30m`、`60m` 的K线数据
2. WHEN 导入任务启动时，THE Import_Service SHALL 接受可选的频率过滤参数，仅导入指定频率的数据
3. WHERE 未指定频率过滤参数，THE Import_Service SHALL 导入所有五种频率的数据

### 需求 6：Celery 异步任务调度

**用户故事：** 作为量化工程师，我希望K线数据导入通过 Celery 异步任务执行，支持每日定时调度和手动触发，以便灵活管理导入流程。

#### 验收标准

1. THE Import_Task SHALL 注册到 Celery 的 `data_sync` 队列，支持通过 Celery Beat 每日定时调度
2. THE Import_Task SHALL 支持通过 API 接口手动触发，接受可选参数：频率过滤列表、指定子目录路径
3. WHILE Import_Task 正在执行时，THE Import_Service SHALL 将导入进度写入 Redis，包含状态（running / completed / failed）、已处理文件数、成功文件数、失败文件数、总插入行数
4. IF 同一时刻已有一个 Import_Task 正在运行，THEN THE Import_Service SHALL 拒绝启动新任务并返回提示信息

### 需求 7：可配置的数据目录路径

**用户故事：** 作为量化工程师，我希望数据目录路径可通过环境变量配置，以便在不同环境中灵活部署。

#### 验收标准

1. THE Import_Service SHALL 从 Settings 配置类读取 `local_kline_data_dir` 配置项
2. THE Settings SHALL 支持通过环境变量 `LOCAL_KLINE_DATA_DIR` 设置数据目录路径
3. WHERE `LOCAL_KLINE_DATA_DIR` 未设置，THE Settings SHALL 使用默认值 `/Users/poper/AData`

### 需求 8：导入结果汇总与日志

**用户故事：** 作为量化工程师，我希望每次导入完成后能看到完整的结果汇总，以便了解导入质量和排查问题。

#### 验收标准

1. WHEN 导入任务完成时，THE Import_Service SHALL 返回结果摘要字典，包含：总文件数、成功文件数、失败文件数、总解析行数、总插入行数、总跳过行数（校验失败）、耗时秒数
2. WHEN 导入任务完成时，THE Import_Service SHALL 将结果摘要写入 Redis 缓存（键为 `import:local_kline:result`），有效期 24 小时
3. IF 存在导入失败的文件，THEN THE Import_Service SHALL 在结果摘要中包含失败文件路径列表及对应错误原因

### 需求 9：增量导入支持

**用户故事：** 作为量化工程师，我希望系统支持增量导入，避免每次全量重新导入浪费时间。

#### 验收标准

1. THE Import_Service SHALL 记录每个已成功导入的ZIP文件的路径和文件修改时间到 Redis 缓存
2. WHEN 扫描到一个 ZIP_File 时，THE Import_Service SHALL 检查该文件是否已导入且文件修改时间未变化
3. WHERE 文件已导入且修改时间未变化，THE Import_Service SHALL 跳过该文件
4. WHERE 文件修改时间发生变化，THE Import_Service SHALL 重新导入该文件（依赖数据库 ON CONFLICT DO NOTHING 保证幂等性）
5. THE Import_Task SHALL 接受可选的 `force` 参数，设为 True 时忽略增量检查，强制全量导入

### 需求 10：API 接口

**用户故事：** 作为量化工程师，我希望通过 REST API 触发导入任务和查询导入状态，以便与前端界面集成。

#### 验收标准

1. THE API SHALL 提供 POST `/api/v1/data/import/local-kline` 端点，用于触发本地K线导入任务，接受可选参数：`freqs`（频率列表）、`sub_dir`（子目录）、`force`（强制全量）
2. THE API SHALL 提供 GET `/api/v1/data/import/local-kline/status` 端点，用于查询当前导入任务的进度和最近一次导入结果
3. WHEN 触发导入请求成功时，THE API SHALL 返回任务 ID 和状态码 202（Accepted）
4. IF 当前已有导入任务正在运行，THEN THE API SHALL 返回状态码 409（Conflict）和提示信息

### 需求 11：本地K线导入前端页面

**用户故事：** 作为量化工程师，我希望有一个本地数据导入的前端页面，用于设置和触发本地K线导入的定时任务，以便通过可视化界面管理导入流程。

#### 验收标准

1. THE Import_Page SHALL 作为 Vue 3 页面组件（Composition API、`<script setup>`）注册到 vue-router，路由路径为 `/data/local-import`
2. THE Import_Page SHALL 提供频率多选控件，支持选择 `1m`、`5m`、`15m`、`30m`、`60m` 中的一种或多种频率，默认全选
3. THE Import_Page SHALL 提供可选的子目录路径输入框，允许用户指定 Data_Directory 下的子目录
4. THE Import_Page SHALL 提供"强制全量导入"开关，对应 Import_Task 的 `force` 参数，默认关闭
5. WHEN 用户点击"开始导入"按钮时，THE Import_Page SHALL 调用 POST `/api/v1/data/import/local-kline` 接口触发导入任务，并将按钮置为禁用状态直到收到响应
6. WHEN 导入任务触发成功时，THE Import_Page SHALL 显示任务 ID 和成功提示信息
7. IF 后端返回状态码 409，THEN THE Import_Page SHALL 显示"已有导入任务正在运行"的提示信息，不重复触发
8. THE Import_Page SHALL 提供定时任务配置区域，允许用户设置每日自动导入的执行时间（小时、分钟），并通过 API 保存 Celery Beat 调度配置
9. WHILE 导入任务正在运行时，THE Import_Page SHALL 每 3 秒轮询 GET `/api/v1/data/import/local-kline/status` 接口，展示实时进度信息，包括状态、已处理文件数、成功文件数、失败文件数、总插入行数
10. THE Import_Page SHALL 以进度条形式展示导入进度百分比（已处理文件数 / 总文件数）
11. WHEN 导入任务完成或失败时，THE Import_Page SHALL 停止轮询并展示结果摘要，包括总文件数、成功数、失败数、总插入行数、耗时
12. IF 存在导入失败的文件，THEN THE Import_Page SHALL 在结果摘要中展示失败文件列表及对应错误原因
13. THE Import_Page SHALL 使用 Pinia store 管理导入状态（任务ID、进度、结果），确保页面切换后返回时状态不丢失
14. THE Import_Page SHALL 在页面挂载时检查是否有正在运行的导入任务，若有则自动恢复进度轮询
15. THE Import_Page SHALL 遵循项目现有的暗色主题样式规范，与 DataManageView 保持视觉一致性
