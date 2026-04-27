# 任务列表：申万/中信行业 L2/L3 成分股数据导入

## 阶段 1：导入框架多级展开机制（需求 4）— 最高优先级

- [ ] 1.1 实现 `_expand_rows()` 函数
  - 在 `app/tasks/tushare_import.py` 中新增 `_expand_rows(rows, entry)` 函数
  - 从 `entry.extra_config["expand_fields"]` 读取展开配置
  - 对每条输入记录，为每个非空的 source_field 生成一条输出记录
  - 无配置时原样返回（向后兼容）

- [ ] 1.2 在数据流管道中插入 `_expand_rows()`
  - `_process_single()`：`_apply_field_mappings()` 之后插入
  - `_write_chunk_rows()`：`_apply_field_mappings()` 之后插入
  - `_process_batched_by_sector()`：`_apply_field_mappings()` 之后插入

- [ ] 1.3 编写 `_expand_rows()` 单元测试
  - 无配置时原样返回
  - L1/L2/L3 全部非空时展开为 3 条
  - L3 为空时展开为 2 条
  - 全部为空时不生成记录

---

## 阶段 2：申万行业注册表修改（需求 1）

- [ ] 2.1 修改 `index_member_all` 注册配置
  - 移除 `field_mappings` 中的 `l1_code → sector_code` 映射
  - 新增 `expand_fields: {"sector_code": ["l1_code", "l2_code", "l3_code"]}`
  - 调整 `max_rows` 为 15000（展开后约 3 倍）

- [ ] 2.2 重新导入申万行业成分数据
  - 通过 Tushare 数据导入页面重新执行 `index_member_all` 导入
  - 验证 sector_constituent 中 TI 板块数从 31 提升到接近 359

---

## 阶段 3：中信行业注册表修改与 sector_info 补全（需求 2, 3）

- [ ] 3.1 修改 `ci_index_member` 注册配置
  - 移除 `field_mappings` 中的 `l1_code → sector_code` 映射
  - 新增 `expand_fields: {"sector_code": ["l1_code", "l2_code", "l3_code"]}`
  - 新增 `auto_generate_sector_info: true` 配置

- [ ] 3.2 实现 CI sector_info 自动生成
  - 在 `_process_single()` 中检测 `auto_generate_sector_info` 配置
  - 从展开后的记录中提取唯一 sector_code 列表
  - 根据代码格式推断层级（L1/L2/L3）
  - 批量 UPSERT 到 sector_info 表

- [ ] 3.3 重新导入中信行业成分数据
  - 通过 Tushare 数据导入页面重新执行 `ci_index_member` 导入
  - 验证 sector_constituent 中 CI 板块数 > 30
  - 验证 sector_info 中 CI 有完整的板块元数据

---

## 阶段 4：验证

- [ ] 4.1 覆盖率验证
  - TI: 板块数接近 359/359，股票数 ~5201
  - CI: 板块数 > 30，股票数 ~5201，sector_info 有数据
  - DC/THS/TDX: 行为不变（无 expand_fields 配置）

- [ ] 4.2 选股功能验证
  - 使用 TI 数据源配置板块面因子，验证 sector_rank 非 None 的股票数 > 5000
  - 使用 CI 数据源配置板块面因子，验证 sector_rank 非 None 的股票数 > 5000

- [ ] 4.3 回归测试
  - 现有 DC/THS/TDX 数据源的导入和选股行为不变
  - 其他 Tushare API 导入不受影响
