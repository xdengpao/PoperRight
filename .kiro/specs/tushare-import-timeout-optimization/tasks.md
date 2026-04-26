# 实现计划：Tushare 导入超时优化

## 概述

本计划优化 15 个 Tushare 导入接口的分批策略，解决导入任务超时问题。

**问题分类：**
1. **第一批（6 个）**：改为 `batch_by_code=True`
2. **第二批 - 双重分批（5 个）**：改为 `batch_by_code=True`
3. **第二批 - 日期分批过多（4 个）**：增加 `date_chunk_days=30`
4. **Celery 超时配置**：增加超时时间

## 任务

- [ ] 1. 修改注册表配置 - 第一批接口（6 个）
  - [ ] 1.1 修改 `pledge_stat` 接口：`batch_by_date=False`, `batch_by_code=True`, 移除 `date_chunk_days`
  - [ ] 1.2 修改 `pledge_detail` 接口：同上
  - [ ] 1.3 修改 `repurchase` 接口：同上
  - [ ] 1.4 修改 `share_float` 接口：同上
  - [ ] 1.5 修改 `block_trade` 接口：同上
  - [ ] 1.6 修改 `stk_holdernumber` 接口：同上
  - 修改文件：`app/services/data_engine/tushare_registry.py`
  - _Requirements: 1.1-1.8_

- [ ] 2. 修改注册表配置 - 第二批接口（双重分批问题，5 个）
  - [ ] 2.1 修改 `report_rc` 接口：`batch_by_date=False`, `batch_by_code=True`, 移除 `date_chunk_days`
  - [ ] 2.2 修改 `ccass_hold_detail` 接口：同上
  - [ ] 2.3 修改 `stk_nineturn` 接口：同上
  - [ ] 2.4 修改 `stk_ah_comparison` 接口：同上
  - [ ] 2.5 修改 `stk_surv` 接口：同上
  - 修改文件：`app/services/data_engine/tushare_registry.py`
  - _Requirements: 1B.1-1B.7_

- [ ] 3. 修改注册表配置 - 第二批接口（日期分批过多，4 个）
  - [ ] 3.1 修改 `daily_basic` 接口：`date_chunk_days=30`
  - [ ] 3.2 修改 `bak_daily` 接口：`date_chunk_days=30`
  - [ ] 3.3 修改 `stk_factor_pro` 接口：`date_chunk_days=30`
  - [ ] 3.4 修改 `hk_hold` 接口：`date_chunk_days=30`
  - 修改文件：`app/services/data_engine/tushare_registry.py`
  - _Requirements: 1C.1-1C.5_

- [ ] 4. 修改 Celery 任务超时配置
  - 将 `soft_time_limit` 从 7200 改为 14400
  - 将 `time_limit` 从 10800 改为 18000
  - 修改文件：`app/tasks/tushare_import.py` 第 214-222 行
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 5. 检查点 - 验证配置修改正确
  - 确保所有测试通过，如有问题请询问用户。

- [ ] 6. 编写属性测试（可选）
  - [ ]* 6.1 编写接口配置正确性属性测试
    - 验证 15 个接口的配置正确
    - 测试文件：`tests/properties/test_tushare_import_timeout_props.py`
  - [ ]* 6.2 编写 Celery 超时配置属性测试
    - 验证 `soft_time_limit=14400`，`time_limit=18000`
  - [ ]* 6.3 编写向后兼容性属性测试
    - 验证 `target_table`、`conflict_columns`、`rate_limit_group` 不变

- [ ] 7. 编写单元测试（可选）
  - [ ]* 7.1 编写接口配置单元测试
    - 验证 15 个接口的配置值正确
    - 测试文件：`tests/services/test_tushare_registry.py`
  - [ ]* 7.2 编写分批策略路由单元测试
    - 验证 `determine_batch_strategy()` 对修改后接口的路由正确
    - 测试文件：`tests/tasks/test_tushare_import.py`

- [ ] 8. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加快 MVP
- 每个任务引用具体需求编号，确保可追溯性
- 检查点确保增量验证
