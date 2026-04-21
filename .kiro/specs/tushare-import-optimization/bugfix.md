# Bugfix Requirements Document

## Introduction

Tushare 数据在线导入功能存在 5 个用户体验和功能缺陷，影响量化交易员的日常数据导入工作效率。主要问题包括：导入按钮点击后无视觉反馈、日期参数缺少合理默认值、股票代码字段在非必填场景下仍阻止提交、不支持批量选择多个接口同时导入、以及导入失败时前端仅显示"失败"状态而不展示具体错误原因。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 用户点击某个 API 接口的"开始导入"按钮时 THEN 按钮没有任何 loading 状态反馈（无 spinner、无文字变化、无禁用状态），用户无法判断请求是否已发出，可能重复点击

1.2 WHEN 用户展开一个需要日期范围参数的接口（如 daily、index_daily 等）时 THEN 开始日期（start_date）字段为空，用户每次都必须手动输入起始日期，无法快速开始导入最近一年的数据

1.3 WHEN 用户展开一个包含 stock_code 可选参数的接口（如 daily、moneyflow 等）时 THEN 虽然 placeholder 提示"留空表示全市场"，但如果 stock_code 被列为 required_params，`requiredParamsFilled()` 函数会因为值为空而返回 false，导致"开始导入"按钮被禁用

1.4 WHEN 用户需要同时导入多个 API 接口的数据时 THEN 只能逐个展开子分类、逐个点击每个接口的"开始导入"按钮，无法批量勾选多个接口一次性发起导入

1.5 WHEN 导入任务执行失败后 THEN 前端活跃任务区域仅显示"失败"状态徽章，不显示具体的错误原因（如 API 调用超时、Token 权限不足、数据写入冲突等），用户无法定位问题

### Expected Behavior (Correct)

2.1 WHEN 用户点击"开始导入"按钮后 THEN 系统 SHALL 立即将按钮切换为 loading 状态（显示"导入中..."文字、添加 loading 样式、禁用按钮防止重复点击），直到 API 请求返回结果或超时后恢复按钮状态

2.2 WHEN 用户展开一个需要日期范围参数的接口时 THEN 系统 SHALL 自动将开始日期（start_date）默认设置为一年前的今天（即 today - 365 天），结束日期保持默认为今天，使用户可以直接点击导入获取最近一年数据

2.3 WHEN 用户展开一个包含 stock_code 参数的接口时 THEN 系统 SHALL 将 stock_code 视为可选参数（留空表示全市场），`requiredParamsFilled()` 函数 SHALL 对 stock_code 参数跳过非空校验，确保留空时"开始导入"按钮不被禁用

2.4 WHEN 用户需要批量导入数据时 THEN 系统 SHALL 在每个子分类的接口列表中提供复选框（checkbox），允许用户勾选多个接口，并在子分类级别提供"批量导入已选"按钮，点击后依次为所有已勾选的接口发起导入任务

2.5 WHEN 导入任务执行失败后 THEN 系统 SHALL 在活跃任务区域和导入历史记录中显示具体的错误原因信息，后端 SHALL 在 Redis 进度数据中存储 error_message 字段，前端 SHALL 读取并展示该错误信息

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 用户点击"开始导入"且 Tushare 未连接时 THEN 系统 SHALL CONTINUE TO 禁用导入按钮并显示"Tushare 未连接"提示

3.2 WHEN 用户未填写必填参数（如 hs_type、sector_code、concept_code 等非日期非股票代码的必填参数）时 THEN 系统 SHALL CONTINUE TO 禁用"开始导入"按钮并显示参数提示

3.3 WHEN 导入任务正在运行时 THEN 系统 SHALL CONTINUE TO 每 3 秒轮询进度接口并更新进度条、状态文本和已完成数量

3.4 WHEN 同一接口已有导入任务在运行时 THEN 系统 SHALL CONTINUE TO 返回 409 冲突错误并提示用户等待

3.5 WHEN 导入任务成功完成时 THEN 系统 SHALL CONTINUE TO 正确显示"已完成"状态、数据量和耗时信息

3.6 WHEN 用户点击"停止导入"按钮时 THEN 系统 SHALL CONTINUE TO 通过 Redis 信号停止任务并更新状态为"已停止"

3.7 WHEN 结束日期未手动设置时 THEN 系统 SHALL CONTINUE TO 默认使用当天日期作为结束日期
