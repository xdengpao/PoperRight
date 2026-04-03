# 实现计划：本地分钟级K线数据导入

## 概述

基于需求文档和设计文档，将本地K线数据导入功能拆分为后端服务层、Celery 任务层、API 层和前端四个阶段，逐步实现并集成。后端使用 Python（FastAPI + Celery + Hypothesis），前端使用 TypeScript（Vue 3 + Pinia + fast-check）。

## 任务列表

- [ ] 1. 配置扩展与核心服务实现
  - [ ] 1.1 在 `app/core/config.py` 的 Settings 类中新增 `local_kline_data_dir` 配置项
    - 类型 `str`，默认值 `/Users/poper/AData`，对应环境变量 `LOCAL_KLINE_DATA_DIR`
    - _需求: 7.1, 7.2, 7.3_

  - [ ] 1.2 创建 `app/services/data_engine/local_kline_import.py`，实现 `LocalKlineImportService` 核心类
    - 实现 `scan_zip_files(base_dir, sub_dir)` 方法：递归扫描目录下所有 `.zip` 文件，返回路径列表
    - 实现 `infer_symbol_and_freq(zip_path)` 方法：从文件路径推断股票代码和频率
    - 实现 `validate_bar(bar)` 方法：校验 KlineBar 数据质量（价格正数、high/low 关系、volume 非负、freq 合法）
    - 实现 `parse_csv_content(csv_text, symbol, freq)` 方法：解析 CSV 文本为 KlineBar 列表，跳过不合法行
    - 实现 `extract_and_parse_zip(zip_path, freq_filter)` 方法：内存解压 ZIP 并解析 CSV
    - _需求: 1.1, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.1_

  - [ ]* 1.3 编写属性测试：目录扫描仅返回 ZIP 文件
    - **Property 1: 目录扫描仅返回 ZIP 文件**
    - 在 `tests/properties/test_local_kline_import_properties.py` 中实现
    - 使用 Hypothesis 生成随机目录结构（含各种扩展名文件），验证 `scan_zip_files` 仅返回 `.zip` 文件且不遗漏
    - **验证: 需求 1.1**

  - [ ]* 1.4 编写属性测试：文件路径推断股票代码和频率
    - **Property 3: 文件路径推断股票代码和频率**
    - 使用 Hypothesis 生成符合命名规则的文件路径，验证 `infer_symbol_and_freq` 正确提取 symbol 和 freq
    - **验证: 需求 2.3**

  - [ ]* 1.5 编写属性测试：KlineBar 数据校验完备性
    - **Property 4: KlineBar 数据校验完备性**
    - 使用 Hypothesis 生成随机 KlineBar（含合法和非法值），验证 `validate_bar` 的判定逻辑与规则一致
    - **验证: 需求 3.1, 3.2, 3.3, 3.4, 3.5**

  - [ ]* 1.6 编写属性测试：CSV 解析往返一致性
    - **Property 2: CSV 解析往返一致性**
    - 使用 Hypothesis 生成有效 KlineBar，序列化为 CSV 行后再解析回 KlineBar，验证数值字段等价
    - **验证: 需求 2.1, 2.2**

- [ ] 2. 检查点 - 确保核心服务测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 3. 批量写入、增量导入与执行流程
  - [ ] 3.1 在 `LocalKlineImportService` 中实现批量写入和增量导入逻辑
    - 实现 `check_incremental(zip_path)` 方法：基于 Redis 哈希表检查文件 mtime 是否变化
    - 实现 `mark_imported(zip_path)` 方法：将文件路径和 mtime 写入 Redis 增量缓存
    - 实现 `update_progress(**kwargs)` 方法：更新 Redis 中的导入进度 JSON
    - 实现 `is_running()` 方法：检查是否有导入任务正在运行
    - 实现 `execute(freqs, sub_dir, force)` 主流程方法：编排扫描→增量检查→解压解析→校验→分批写入→进度更新→结果摘要
    - 调用 `KlineRepository.bulk_insert` 分批写入，每批不超过 1000 条
    - _需求: 4.1, 4.2, 4.3, 4.4, 5.2, 5.3, 6.3, 6.4, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 3.2 编写属性测试：批量写入分批不超过上限
    - **Property 5: 批量写入分批不超过上限**
    - 使用 Hypothesis 生成随机长度的 KlineBar 列表，验证每批 `bulk_insert` 调用不超过 1000 条且总数等于 N
    - **验证: 需求 4.2**

  - [ ]* 3.3 编写属性测试：频率过滤正确性
    - **Property 7: 频率过滤正确性**
    - 使用 Hypothesis 生成随机频率集合和文件集合，验证导入后数据的 freq 字段都属于过滤列表
    - **验证: 需求 5.2, 5.3**

  - [ ]* 3.4 编写属性测试：增量导入跳过未变化文件
    - **Property 8: 增量导入跳过未变化文件**
    - 使用 Hypothesis 生成随机文件路径和 mtime，验证 mtime 未变化时文件被跳过，变化时重新导入
    - **验证: 需求 9.1, 9.2, 9.3, 9.4**

  - [ ]* 3.5 编写属性测试：强制导入忽略增量缓存
    - **Property 9: 强制导入忽略增量缓存**
    - 使用 Hypothesis 生成已导入文件集合，验证 `force=True` 时所有文件都被重新处理
    - **验证: 需求 9.5**

  - [ ]* 3.6 编写属性测试：结果摘要字段完整性
    - **Property 10: 结果摘要字段完整性**
    - 使用 Hypothesis 生成随机导入执行结果，验证摘要字典包含所有必需字段且数值关系正确
    - **验证: 需求 8.1, 6.3**

- [ ] 4. 检查点 - 确保批量写入和增量导入测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 5. Celery 任务与 API 端点
  - [ ] 5.1 在 `app/tasks/data_sync.py` 中新增 `import_local_kline` Celery 任务
    - 注册到 `data_sync` 队列，设置 `soft_time_limit=7200`、`time_limit=10800`
    - 接受 `freqs`、`sub_dir`、`force` 参数，调用 `LocalKlineImportService.execute()`
    - 使用 `_run_async` 辅助函数在同步 worker 中运行异步协程
    - _需求: 6.1, 6.2_

  - [ ] 5.2 在 `app/api/v1/data.py` 中新增请求/响应模型和两个 API 端点
    - 定义 `LocalKlineImportRequest`、`LocalKlineImportResponse`、`LocalKlineImportStatusResponse` Pydantic 模型
    - 实现 `POST /import/local-kline` 端点：检查并发锁→分发 Celery 任务→返回 202 + task_id
    - 实现 `GET /import/local-kline/status` 端点：从 Redis 读取进度和最近结果→返回状态
    - 已有任务运行中时返回 HTTP 409
    - _需求: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 5.3 编写单元测试：API 端点和 Celery 任务
    - 在 `tests/services/test_local_kline_import.py` 中编写单元测试
    - 测试配置项读取和默认值（需求 7）
    - 测试目录不存在时的错误处理（需求 1.3）
    - 测试 ZIP 文件损坏时的跳过行为（需求 2.4）
    - 测试 CSV 行格式不合法时的跳过行为（需求 2.5）
    - 测试 API 端点 202/409 响应（需求 10.3, 10.4）
    - 测试并发任务保护（需求 6.4）
    - _需求: 1.3, 2.4, 2.5, 6.4, 7, 10.3, 10.4_

- [ ] 6. 检查点 - 确保后端全部测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 7. 前端实现
  - [ ] 7.1 创建 `frontend/src/stores/localImport.ts` Pinia store
    - 定义状态：`taskId`、`progress`（reactive 对象）、`result`、`loading`、`polling`
    - 实现 `startImport(params)` 动作：调用 POST API 触发导入
    - 实现 `fetchStatus()` 动作：调用 GET API 获取进度
    - 实现 `startPolling()` / `stopPolling()` 方法：3 秒间隔轮询进度
    - _需求: 11.5, 11.6, 11.7, 11.9, 11.13_

  - [ ] 7.2 创建 `frontend/src/views/LocalImportView.vue` 页面组件
    - 使用 Vue 3 Composition API + `<script setup>`
    - 实现频率多选控件（checkbox group，默认全选 1m/5m/15m/30m/60m）
    - 实现子目录路径输入框
    - 实现"强制全量导入"开关（toggle）
    - 实现定时任务配置区域（小时/分钟选择器 + 保存按钮）
    - 实现"开始导入"按钮（点击后禁用直到收到响应）
    - 实现进度条（已处理文件数 / 总文件数）
    - 实现结果摘要卡片和失败文件列表
    - 页面挂载时检查是否有运行中任务，自动恢复轮询
    - 遵循项目暗色主题样式，与 DataManageView 保持视觉一致性
    - _需求: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11, 11.12, 11.14, 11.15_

  - [ ] 7.3 在 `frontend/src/router/index.ts` 中注册路由
    - 在 MainLayout children 中新增 `{ path: 'data/local-import', name: 'LocalImport', component: () => import('@/views/LocalImportView.vue'), meta: { title: '本地数据导入' } }`
    - _需求: 11.1_

  - [ ]* 7.4 编写前端属性测试：进度百分比计算
    - 在 `frontend/src/views/__tests__/LocalImportView.property.test.ts` 中实现
    - 使用 fast-check 生成随机 `processed_files` 和 `total_files`，验证进度百分比始终在 [0, 100] 范围内
    - _需求: 11.10_

  - [ ]* 7.5 编写前端单元测试
    - 在 `frontend/src/views/__tests__/LocalImportView.test.ts` 中实现
    - 测试组件挂载和渲染
    - 测试频率多选控件交互
    - 测试开始导入按钮禁用/启用状态
    - 测试 409 错误提示展示
    - 测试进度轮询启动/停止
    - _需求: 11.2, 11.5, 11.7, 11.9_

- [ ] 8. 最终检查点 - 确保全部测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的任务为可选测试任务，可跳过以加速 MVP 交付
- 每个任务引用了对应的需求编号，确保需求可追溯
- 检查点用于阶段性验证，确保增量正确性
- 属性测试验证通用正确性属性，单元测试验证具体示例和边界情况
