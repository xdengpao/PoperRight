# K 线唯一约束迁移建议

## 背景

当前 `kline` 主唯一键是 `(time, symbol, freq, adj_type)`。该约束能阻止同一 UTC 时间点重复写入，但不能阻止日/周/月级 K 线在同一本地交易日同时存在 `前一日 16:00 UTC` 和 `当日 00:00 UTC` 两种时间口径。

## 建议方案

1. 短期保持现有唯一索引，同时保留写入归一化：
   - 写入统一通过 `normalize_kline_time()`。
   - 日/周/月级统一存储为 `trade_date 00:00:00 UTC`。
   - 分钟级保留真实分钟时间。

2. 中期增加冗余交易日列：
   - 新增 `trade_date date`。
   - 对 `freq in ('1d', '1w', '1M')` 的数据回填 `derive_trade_date(time, freq)`。
   - 新写入链路显式填充 `trade_date`。
   - 增加部分唯一索引：`(symbol, freq, adj_type, trade_date) WHERE freq in ('1d', '1w', '1M')`。

3. 分钟级继续使用现有唯一索引：
   - `(time, symbol, freq, adj_type)` 仍适用于分钟级真实时间。
   - 不将分钟 K 按 `trade_date` 唯一化，避免压缩日内多根 K 线。

4. Tushare 业务表：
   - 已由 `TUSHARE_API_REGISTRY.conflict_columns` 驱动审计。
   - 对仍缺少数据库唯一索引但有明确 `conflict_columns` 的表，后续迁移应补齐同口径唯一索引。

## 迁移风险

- TimescaleDB hypertable 对涉及分区键的更新较敏感，历史修复优先使用 `INSERT 规范时间行 -> DELETE 旧时间行`。
- 新增 `trade_date` 前必须完成历史重复清理，否则唯一索引创建会失败。
- 建议先在影子库验证索引创建时间和锁影响，再在生产低峰期执行。
