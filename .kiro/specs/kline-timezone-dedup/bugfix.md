# Bugfix Requirements Document

## Introduction

修复 K 线数据重复存储和时区处理不一致的问题。该问题导致前端显示 K 线数据时出现重复，同一交易日显示两条记录，影响用户体验和数据准确性。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN K 线数据导入时使用不同的时区假设 THEN 系统将同一交易日的数据存储为两个不同的时间戳（`00:00:00 UTC` 和 `16:00:00 UTC`）

1.2 WHEN 前端查询 K 线数据时 THEN 系统返回同一交易日的两条记录，导致显示重复

1.3 WHEN 本地 CSV 导入解析日期字符串时 THEN `_parse_datetime` 函数创建 naive datetime 对象，存入数据库时被解释为 UTC 时间

1.4 WHEN Tushare API 导入解析交易日期时 THEN `_parse_trade_date` 函数同样创建 naive datetime 对象，导致时区不一致

### Expected Behavior (Correct)

2.1 WHEN K 线数据导入时 THEN 系统 SHALL 统一使用 `00:00:00 UTC` 时间戳存储日线数据（对应北京时间 08:00）

2.2 WHEN 检测到已存在 `16:00:00 UTC` 时间戳的记录时 THEN 系统 SHALL 将其删除并保留 `00:00:00 UTC` 的记录

2.3 WHEN 新数据导入时 THEN 系统 SHALL 标准化时间戳为 `00:00:00 UTC`，确保唯一约束正确生效

2.4 WHEN `_parse_datetime` 和 `_parse_trade_date` 解析日期时 THEN 系统 SHALL 明确使用 UTC 时区创建 datetime 对象

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 查询 K 线数据时 THEN 系统 SHALL CONTINUE TO 按时间范围、股票代码、频率、复权类型正确返回数据

3.2 WHEN 批量写入 K 线数据时 THEN 系统 SHALL CONTINUE TO 使用 ON CONFLICT DO NOTHING 保证幂等性

3.3 WHEN 分钟级 K 线数据导入时 THEN 系统 SHALL CONTINUE TO 正确处理带时间戳的分钟数据

3.4 WHEN 前端展示 K 线图表时 THEN 系统 SHALL CONTINUE TO 按交易日正确渲染，无重复显示
