# 实现计划：本地A股分时数据与复权因子导入

## 概述

基于更新后的需求文档和设计文档，将本地数据导入功能拆分为：核心服务重构（市场感知扫描与解析）、复权因子导入、API扩展、前端扩展四个阶段。已有的基础设施（配置、Celery任务、Redis进度、增量导入）大部分可复用，重点在于适配实际的四级目录结构和市场特定的CSV格式。

## 任务列表

- [x] 1. 核心服务重构：市场感知目录扫描与解析
  - [x] 1.1 重构 `LocalKlineImportService` 的目录扫描逻辑
    - 新增 `scan_market_zip_files(base_dir, markets, freqs, start_month, end_month)` 方法
    - 按 `{市场目录}/{频率目录}/{月份目录}/{日期ZIP}` 四级结构扫描
    - 新增 `MARKET_DIR_MAP` 和 `FREQ_DIR_MAP` 常量映射
    - 支持 `markets` 参数过滤市场分类（hushen/jingshi/zhishu）
    - 支持 `freqs` 参数过滤频率目录
    - 支持 `start_month`/`end_month` 参数过滤月份目录
    - 返回 `[(zip_path, market, freq), ...]` 元组列表
    - 更新 `infer_freq_from_path` 支持 `{N}分钟_按月归档` 目录名
    - 新增 `infer_market_from_path` 方法
    - _需求: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 8.2, 8.3, 9.1, 9.2, 9.3_

  - [x] 1.2 重构 CSV 解析逻辑，支持市场感知解析
    - 更新 `infer_symbol_from_csv_name(csv_name, market)` 支持三种市场的文件名格式
    - 沪深: `sz000001.csv` → `000001`, `sh600000.csv` → `600000`
    - 京市: `bj920000.csv` → `920000`
    - 指数: `000001.csv` → `000001`（无前缀）
    - 更新 `parse_csv_content` 接受 `market` 参数
    - 指数市场 CSV 无 `成交量` 列时，volume 设为 0
    - 更新 `_build_column_map` 处理指数表头（无成交量列）
    - _需求: 2.2, 2.3, 3.1, 3.2, 4.1, 4.2, 4.3_

  - [x] 1.3 重构 `extract_and_parse_zip` 方法
    - 接受 `market` 参数，传递给 CSV 解析
    - 从四级路径推断 freq 和 market
    - _需求: 2.1, 2.5, 2.6_

  - [x] 1.4 重构 `execute` 主流程方法
    - 使用 `scan_market_zip_files` 替代 `scan_zip_files`
    - 接受新参数：`markets`, `start_month`, `end_month`, `adj_factors`
    - 按市场分类统计导入结果
    - 在进度中包含 `market_stats` 字段
    - _需求: 7.1, 8.1, 9.1, 11.2, 11.3, 14.1_

  - [x] 1.5 编写属性测试：市场分类过滤正确性
    - **Property 8: 市场分类过滤正确性**
    - 使用 Hypothesis 生成随机市场分类集合，验证扫描结果仅包含对应市场目录下的文件
    - **验证: 需求 7.1, 7.2, 7.3**

  - [x] 1.6 编写属性测试：月份范围过滤正确性
    - **Property 9: 月份范围过滤正确性**
    - 使用 Hypothesis 生成随机月份范围，验证扫描结果仅包含范围内的月份目录
    - **验证: 需求 9.1, 9.2, 9.3**

  - [x] 1.7 编写属性测试：指数数据 volume 为零
    - **Property 12: 指数数据 volume 为零**
    - 使用 Hypothesis 生成随机指数 CSV 数据，验证解析后所有 KlineBar 的 volume 为 0
    - **验证: 需求 4.3**

- [x] 2. 检查点 - 确保核心服务重构测试通过
  - 运行 `pytest tests/properties/test_local_kline_import_properties.py tests/services/test_local_kline_import.py`，确保所有测试通过。

- [x] 3. 复权因子导入
  - [x] 3.1 创建 `app/models/adjustment_factor.py` 复权因子 ORM 模型
    - 定义 `AdjustmentFactor` 模型，主键 `(symbol, trade_date, adj_type)`
    - 字段：symbol、trade_date、adj_type（1=前复权, 2=后复权）、adj_factor
    - 使用 `TSBase`（TimescaleDB）
    - _需求: 10.6_

  - [x] 3.2 创建 `app/services/data_engine/adj_factor_repository.py` 复权因子仓储
    - 实现 `bulk_insert(factors)` 方法，ON CONFLICT DO NOTHING
    - _需求: 10.6_

  - [x] 3.3 创建 Alembic 迁移脚本，新增 `adjustment_factor` 表
    - _需求: 10.6_

  - [x] 3.4 在 `LocalKlineImportService` 中实现复权因子导入逻辑
    - 实现 `parse_adj_factor_zip(zip_path, adj_type)` 方法
    - 实现 `infer_symbol_from_adj_csv_name(csv_name)` 方法：`000001.SZ.csv` → `000001`
    - 解析 CSV 表头 `股票代码,交易日期,复权因子`，交易日期格式 `YYYYMMDD`
    - 在 `execute` 中根据 `adj_factors` 参数调用复权因子导入
    - _需求: 10.1, 10.2, 10.3, 10.4, 10.5, 10.7_

  - [x] 3.5 编写属性测试：复权因子文件名推断正确性
    - **Property 13: 复权因子 CSV 文件名推断正确性**
    - 使用 Hypothesis 生成 `{code}.{suffix}.csv` 格式文件名，验证正确提取股票代码
    - **验证: 需求 10.4**

- [x] 4. 检查点 - 确保复权因子导入测试通过
  - 运行相关测试，确保所有测试通过。

- [x] 5. API 扩展与 Celery 任务更新
  - [x] 5.1 更新 `app/api/v1/data.py` 中的请求模型
    - 扩展 `LocalKlineImportRequest`，新增字段：`markets`、`start_month`、`end_month`、`adj_factors`
    - 更新 `start_local_kline_import` 端点，传递新参数给 Celery 任务
    - _需求: 15.1, 15.3, 15.4_

  - [x] 5.2 更新 `app/tasks/data_sync.py` 中的 Celery 任务
    - 扩展 `import_local_kline` 任务参数：`markets`、`start_month`、`end_month`、`adj_factors`
    - 传递新参数给 `LocalKlineImportService.execute()`
    - _需求: 11.1, 11.2_

  - [x] 5.3 更新单元测试
    - 更新 `tests/services/test_local_kline_import.py` 中的测试用例
    - 新增市场分类过滤测试
    - 新增月份范围过滤测试
    - 新增复权因子导入测试
    - 新增指数数据（无成交量列）解析测试
    - _需求: 2.3, 3.1, 4.2, 7.2, 9.2, 10.3_

- [x] 6. 检查点 - 确保后端全部测试通过
  - 运行 `pytest`，确保所有测试通过。

- [x] 7. 前端扩展
  - [x] 7.1 更新 `frontend/src/stores/localImport.ts` Pinia store
    - 扩展 `ImportParams` 接口，新增 `markets`、`start_month`、`end_month`、`adj_factors` 字段
    - 更新 `startImport` 方法传递新参数
    - _需求: 16.13_

  - [x] 7.2 更新 `frontend/src/views/LocalImportView.vue` 页面组件
    - 新增市场分类多选控件（checkbox group：沪深、京市、指数，默认全选）
    - 新增月份范围选择器（起始月份、结束月份，input[type=month]）
    - 新增复权因子选择控件（checkbox group：前复权、后复权，默认不选）
    - 移除定时任务配置区域（简化页面，定时任务通过 Celery Beat 配置）
    - 更新"开始导入"按钮逻辑，传递新参数
    - _需求: 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.15_

  - [x] 7.3 更新前端单元测试
    - 更新 `frontend/src/views/__tests__/LocalImportView.test.ts`
    - 新增市场分类选择控件测试
    - 新增月份范围选择器测试
    - 新增复权因子选择控件测试
    - _需求: 16.2, 16.4, 16.5_

- [x] 8. 最终检查点 - 确保全部测试通过
  - 运行后端 `pytest` 和前端 `npm test`，确保所有测试通过。

## 备注

- 已有的基础设施（配置项、Redis进度追踪、增量导入、并发保护）大部分可复用
- 核心变更集中在目录扫描逻辑（四级结构）和CSV解析逻辑（市场感知）
- 复权因子导入是全新功能，需要新建模型和仓储
- 每个任务引用了对应的需求编号，确保需求可追溯
- 检查点用于阶段性验证，确保增量正确性
