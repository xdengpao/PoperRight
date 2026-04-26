# 实现任务：板块成分数据全量导入（按板块代码遍历）

## 任务列表

- [x] 1. ApiEntry 扩展 batch_by_sector 字段
  - [x] 1.1 在 `app/services/data_engine/tushare_registry.py` 的 `ApiEntry` 数据类中新增 `batch_by_sector: bool = False` 字段
  - [x] 1.2 确保字段位置在 `batch_by_date` 之后，保持字段顺序一致性

- [x] 2. determine_batch_strategy 路由扩展
  - [x] 2.1 在 `app/tasks/tushare_import.py` 的 `determine_batch_strategy` 函数开头插入 `batch_by_sector` 检查，返回 `"by_sector"`
  - [x] 2.2 确保 `batch_by_sector` 优先级高于所有现有策略（`batch_by_code`、`batch_by_date` 等）
  - [x] 2.3 更新函数 docstring，添加优先级 0 的说明

- [x] 3. 实现 _process_batched_by_sector 函数
  - [x] 3.1 在 `app/tasks/tushare_import.py` 中新增 `_process_batched_by_sector` 异步函数
  - [x] 3.2 实现从 `inject_fields` 获取 `data_source` 的逻辑，缺失时返回 `failed` 状态
  - [x] 3.3 实现查询 `sector_info` 表获取板块代码列表的逻辑
  - [x] 3.4 实现空列表检查，返回 WARNING 日志提示需先导入板块信息
  - [x] 3.5 实现遍历板块代码调用 Tushare API 的主循环
  - [x] 3.6 实现停止信号检查（复用 `_check_stop_signal`）
  - [x] 3.7 实现 `inject_fields` + 字段映射 + `_convert_codes` 处理
  - [x] 3.8 实现进度更新（复用 `_update_progress`，`batch_mode="by_sector"`）
  - [x] 3.9 实现频率限制延迟（`time.sleep(rate_delay)`）
  - [x] 3.10 实现错误处理：Token 无效抛出、其他 API 错误继续、空数据跳过、DB 写入失败继续
  - [x] 3.11 实现截断检测：返回行数 ≥ `max_rows` 时记录 WARNING
  - [x] 3.12 实现返回值 `batch_stats`（`total_sectors`、`success_sectors`、`failed_sectors`、`empty_sectors`）
  - [x] 3.13 实现 trade_date 动态注入逻辑：当 API 不返回 trade_date 且字段映射中无 trade_date 时，注入当前日期

- [x] 4. _process_import 路由集成
  - [x] 4.1 在 `app/tasks/tushare_import.py` 的 `_process_import` 函数中新增 `elif strategy == "by_sector"` 分支
  - [x] 4.2 调用 `_process_batched_by_sector` 并传入所有必要参数

- [x] 5. 注册表配置变更
  - [x] 5.1 修改 `ths_member` 注册配置：添加 `batch_by_sector=True`，`code_format=CodeFormat.STOCK_SYMBOL`
  - [x] 5.2 修改 `dc_member` 注册配置：添加 `batch_by_sector=True`，`code_format=CodeFormat.STOCK_SYMBOL`
  - [x] 5.3 修改 `tdx_member` 注册配置：添加 `batch_by_sector=True`，`code_format=CodeFormat.STOCK_SYMBOL`
  - [x] 5.4 验证 `index_member_all` 的 `inject_fields` 包含 `data_source: "TI"`
  - [x] 5.5 验证 `ci_index_member` 的 `inject_fields` 包含 `data_source: "CI"`
  - [x] 5.6 修复 `dc_member` 的 trade_date 映射：添加 `FieldMapping(source="trade_date", target="trade_date")`，移除 `inject_fields` 中的 `trade_date` 硬编码
  - [x] 5.7 修复 `tdx_member` 的 trade_date 映射：添加 `FieldMapping(source="trade_date", target="trade_date")`，移除 `inject_fields` 中的 `trade_date` 硬编码
  - [x] 5.8 修复 `ths_member` 的 trade_date 处理：移除 `inject_fields` 中的 `trade_date` 硬编码，由导入逻辑动态注入当前日期

- [x] 6. 属性测试
  - [x] 6.1 创建 `tests/properties/test_sector_member_batch_props.py` 测试文件
  - [x] 6.2 实现 Property 1 测试：`batch_by_sector` 路由正确性
  - [x] 6.3 实现 Property 3 测试：错误容错——单板块失败不中断（mock 测试）
  - [x] 6.4 实现 Property 4 测试：进度单调递增且最终完整（mock 测试）
  - [x] 6.5 实现 Property 6 测试：symbol 格式正确性（`_convert_codes` 纯函数测试）
  - [x] 6.6 实现 Property 7 测试：停止信号优雅退出（mock 测试）

- [x] 7. 单元测试
  - [x] 7.1 在 `tests/tasks/` 目录下创建或更新测试文件
  - [x] 7.2 测试 `determine_batch_strategy` 返回 `"by_sector"`（`batch_by_sector=True` 时）
  - [x] 7.3 测试注册表配置：验证 `ths_member`/`dc_member`/`tdx_member` 的 `batch_by_sector=True`
  - [x] 7.4 测试注册表配置：验证三个接口的 `code_format=STOCK_SYMBOL`
  - [x] 7.5 测试注册表配置：验证三个接口的 `inject_fields` 包含 `data_source` 和 `trade_date`
  - [x] 7.6 测试空板块列表处理：返回 `completed` + `record_count=0`
  - [x] 7.7 测试 `inject_fields` 缺少 `data_source`：返回 `failed` 状态

- [x] 8. trade_date 字段映射修复验证
  - [x] 8.1 测试 `dc_member` 的 `field_mappings` 包含 `trade_date` 映射
  - [x] 8.2 测试 `tdx_member` 的 `field_mappings` 包含 `trade_date` 映射
  - [x] 8.3 测试 `ths_member` 的 `inject_fields` 不包含 `trade_date` 硬编码
  - [x] 8.4 测试 trade_date 动态注入逻辑：模拟 API 不返回 trade_date 时注入当前日期
  - [ ] 8.5 验证修复后导入的数据：`tdx_member` 和 `dc_member` 的 trade_date 应为真实日期而非 `1900-01-01`

---

## 新增任务：TI batch_by_sector 与 trade_date 统一（高优先级）

- [x] 9. index_member_all（TI）启用 batch_by_sector 模式
  - [x] 9.1 修改 `index_member_all` 注册配置：添加 `batch_by_sector=True`
  - [x] 9.2 验证 `index_member_all` 的 `field_mappings` 保留 `in_date` → `trade_date` 映射
  - [x] 9.3 修改 `index_member_all` 注册配置：提高 `max_rows` 到 5000
  - [x] 9.4 验证 `index_member_all` 的 `inject_fields` 包含 `data_source: "TI"`
  - [x] 9.5 测试 `index_member_all` 的 `batch_by_sector=True` 配置

- [x] 10. ci_index_member（CI）验证配置
  - [x] 10.1 验证 `ci_index_member` 的 `field_mappings` 保留 `in_date` → `trade_date` 映射
  - [x] 10.2 验证 `ci_index_member` 的 `inject_fields` 包含 `data_source: "CI"`

- [x] 11. ths_member 使用导入日期作为纳入日期
  - [x] 11.1 验证 `ths_member` 的 `field_mappings` 不包含 `trade_date` 映射
  - [x] 11.2 验证 `_process_batched_by_sector` 动态注入当前日期作为 `trade_date`
  - [x] 11.3 测试 THS 的 trade_date 动态注入逻辑

- [x] 12. TDX/DC 保留调入日期
  - [x] 12.1 验证 `tdx_member` 的 `field_mappings` 包含 `trade_date` 映射
  - [x] 12.2 验证 `dc_member` 的 `field_mappings` 包含 `trade_date` 映射
  - [x] 12.3 验证 `inject_fields` 移除硬编码的 `trade_date`

- [ ] 13. 导入验证
  - [ ] 13.1 重新导入 `index_member_all`，验证 `data_source='TI'` 的板块数接近 359
  - [ ] 13.2 重新导入 `ci_index_member`，验证 `data_source='CI'` 的记录数大于 3000
  - [ ] 13.3 验证 TI/CI 的 `trade_date` 为 API 返回的 `in_date`
  - [ ] 13.4 验证 TDX/DC 的 `trade_date` 为 API 返回的调入日期
  - [ ] 13.5 验证 THS 的 `trade_date` 为导入当天日期

---

## 新增任务：单元测试更新

- [x] 14. 注册表配置测试更新
  - [x] 14.1 测试 `index_member_all` 的 `batch_by_sector=True`
  - [x] 14.2 测试 `index_member_all` 的 `field_mappings` 包含 `in_date` → `trade_date`
  - [x] 14.3 测试 `ci_index_member` 的 `field_mappings` 包含 `in_date` → `trade_date`
  - [x] 14.4 测试 `tdx_member` 的 `field_mappings` 包含 `trade_date` 映射
  - [x] 14.5 测试 `dc_member` 的 `field_mappings` 包含 `trade_date` 映射
  - [x] 14.6 测试 `ths_member` 的 `field_mappings` 不包含 `trade_date` 映射

- [x] 15. trade_date 处理测试
  - [x] 15.1 测试 TI 的 trade_date：应为 API 返回的 `in_date`
  - [x] 15.2 测试 CI 的 trade_date：应为 API 返回的 `in_date`
  - [x] 15.3 测试 TDX 的 trade_date：应为 API 返回的 `trade_date`
  - [x] 15.4 测试 DC 的 trade_date：应为 API 返回的 `trade_date`
  - [x] 15.5 测试 THS 的 trade_date：应为导入当天日期
