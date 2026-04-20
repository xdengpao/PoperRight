# 任务清单：选股池管理

## 任务

- [x] 1. 后端数据模型与迁移
  - [x] 1.1 创建 `app/models/pool.py`，定义 `StockPool` 和 `StockPoolItem` ORM 模型（继承 PGBase，使用 Mapped[] + mapped_column()，含 UniqueConstraint 和 ForeignKey ON DELETE CASCADE）
  - [x] 1.2 生成 Alembic 迁移脚本：`alembic revision --autogenerate -m "add stock_pool and stock_pool_item tables"`，确认生成的 SQL 包含 `uq_stock_pool_user_name` 唯一约束和 `ON DELETE CASCADE` 外键
  - [x] 1.3 在 `app/models/__init__.py` 中导入新模型，确保 Alembic 能发现它们

- [x] 2. 后端服务层：纯函数与校验逻辑
  - [x] 2.1 创建 `app/services/pool_manager.py`，实现纯校验函数 `validate_pool_name(name) -> str`（strip 后非空、长度 ≤ 50，否则抛 ValueError）和 `validate_stock_symbol(symbol) -> str`（匹配 `^\d{6}$`，否则抛 ValueError）
  - [x] 2.2 在 `app/services/pool_manager.py` 中定义业务约束常量：`MAX_POOLS_PER_USER = 20`、`MAX_STOCKS_PER_POOL = 200`、`MAX_POOL_NAME_LENGTH = 50`、`STOCK_SYMBOL_PATTERN`

- [x] 3. 后端服务层：PoolManager 业务方法
  - [x] 3.1 实现 `PoolManager.create_pool(session, user_id, name)` — 校验名称、检查数量上限（≤ 20）、检查同用户名称唯一性、创建并 flush
  - [x] 3.2 实现 `PoolManager.delete_pool(session, user_id, pool_id)` — 校验归属、删除（CASCADE 自动清理条目）
  - [x] 3.3 实现 `PoolManager.rename_pool(session, user_id, pool_id, new_name)` — 校验名称、检查唯一性、更新 name 和 updated_at
  - [x] 3.4 实现 `PoolManager.list_pools(session, user_id)` — 查询用户所有选股池，LEFT JOIN 统计每个池的股票数量
  - [x] 3.5 实现 `PoolManager.get_pool_stocks(session, user_id, pool_id)` — 校验归属、查询池内所有股票（JOIN stock_info 获取股票名称）
  - [x] 3.6 实现 `PoolManager.add_stocks(session, user_id, pool_id, symbols)` — 校验归属、检查 200 上限、使用 INSERT ... ON CONFLICT DO NOTHING 批量插入、返回 added/skipped 数量
  - [x] 3.7 实现 `PoolManager.remove_stocks(session, user_id, pool_id, symbols)` — 校验归属、批量删除
  - [x] 3.8 实现 `PoolManager.add_stock_manual(session, user_id, pool_id, symbol)` — 校验代码格式、检查重复（已存在则抛异常）、检查 200 上限、插入

- [x] 4. 后端服务层：CSV 导出
  - [x] 4.1 创建 `app/services/csv_exporter.py`，实现 `sanitize_filename(name) -> str`（将 `/\:*?"<>|` 替换为下划线）
  - [x] 4.2 实现 `build_csv_content(items, strategy_name, export_time) -> bytes` — 生成 UTF-8 BOM 编码的 CSV 内容，包含 7 列（股票代码、股票名称、买入参考价、趋势评分、风险等级、触发信号摘要、选股时间）
  - [x] 4.3 实现 `build_export_filename(strategy_name, export_time) -> str` — 组合 sanitize_filename 和时间戳生成 `{name}_{YYYYMMDD_HHmmss}.csv` 格式文件名

- [-] 5. 后端 API 端点：选股池
  - [x] 5.1 创建 `app/api/v1/pool.py`，定义 Pydantic 请求/响应模型（CreatePoolRequest、RenamePoolRequest、AddStocksRequest、RemoveStocksRequest、ManualAddStockRequest）
  - [x] 5.2 实现 `POST /pools` — 创建选股池端点，调用 PoolManager.create_pool
  - [x] 5.3 实现 `GET /pools` — 列出用户所有选股池端点，调用 PoolManager.list_pools
  - [x] 5.4 实现 `PUT /pools/{pool_id}` — 重命名选股池端点，调用 PoolManager.rename_pool
  - [x] 5.5 实现 `DELETE /pools/{pool_id}` — 删除选股池端点，调用 PoolManager.delete_pool
  - [x] 5.6 实现 `GET /pools/{pool_id}/stocks` — 获取选股池内股票列表端点
  - [x] 5.7 实现 `POST /pools/{pool_id}/stocks` — 批量添加股票端点
  - [x] 5.8 实现 `DELETE /pools/{pool_id}/stocks` — 批量移除股票端点
  - [x] 5.9 实现 `POST /pools/{pool_id}/stocks/manual` — 手动添加单只股票端点
  - [x] 5.10 在 `app/api/v1/__init__.py` 中注册 pool_router

- [x] 6. 后端 API 端点：CSV 导出
  - [x] 6.1 在 `app/api/v1/screen.py` 中实现 `GET /screen/export/csv` — 从 Redis 读取选股结果、查询策略名称、调用 csv_exporter 生成内容、返回 StreamingResponse（Content-Disposition 含文件名）
  - [x] 6.2 更新或移除原有的 `GET /screen/export` stub 端点，避免路由冲突

- [x] 7. 后端属性测试
  - [x] 7.1 🧪 PBT: 创建 `tests/properties/test_pool_properties.py`，实现 Property 1 测试：CSV 生成保留所有选股结果且包含必需列（使用 Hypothesis 生成随机选股结果列表，验证 CSV 行数、列头、BOM 编码）
  - [x] 7.2 🧪 PBT: 实现 Property 2 测试：文件名生成与特殊字符清理（生成含特殊字符的策略名称，验证 sanitize_filename 输出不含禁止字符且匹配格式）
  - [x] 7.3 🧪 PBT: 实现 Property 3 测试：选股池名称校验拒绝无效输入（生成纯空白字符串和超长字符串验证拒绝，生成合法字符串验证接受）
  - [x] 7.4 🧪 PBT: 实现 Property 5 测试：股票添加幂等性（生成随机股票代码集合，添加两次验证第二次 added=0）
  - [x] 7.5 🧪 PBT: 实现 Property 6 测试：股票移除后剩余集合正确（生成随机股票集合和移除子集，验证剩余集合）
  - [x] 7.6 🧪 PBT: 实现 Property 7 测试：非法股票代码拒绝（生成不匹配 6 位数字的字符串验证拒绝，生成 6 位数字字符串验证接受）

- [x] 8. 后端单元测试
  - [x] 8.1 创建 `tests/services/test_pool_manager.py`，编写 PoolManager 业务方法的单元测试（创建成功、名称重复、数量上限、删除级联、重命名、批量添加跳过重复、超 200 上限部分添加、手动添加格式校验）
  - [x] 8.2 创建 `tests/services/test_csv_exporter.py`，编写 CSV 导出单元测试（正常导出、空结果处理、中文字符编码）

- [-] 9. 前端：Pinia Store 与 API 层
  - [x] 9.1 创建 `frontend/src/stores/stockPool.ts`，定义 StockPool 和 StockPoolItem 接口，实现 Pinia store（fetchPools、createPool、deletePool、renamePool、fetchPoolStocks、addStocksToPool、removeStocksFromPool、addStockManual）
  - [x] 9.2 在 store 中实现前端校验函数 `validatePoolName(name)` 和 `validateStockSymbol(symbol)`，与后端校验逻辑一致

- [x] 10. 前端：路由与导航
  - [x] 10.1 在 `frontend/src/router/index.ts` 中添加 `/stock-pool` 路由，指向 `StockPoolView.vue`，meta.title 为「选股池」
  - [x] 10.2 在 `frontend/src/layouts/MainLayout.vue` 的 menuGroups「选股」分组中添加 `{ path: '/stock-pool', label: '选股池', icon: '📦' }` 菜单项，位于「选股结果」之后

- [x] 11. 前端：选股池管理页面
  - [x] 11.1 创建 `frontend/src/views/StockPoolView.vue`，实现选股池列表展示（名称、股票数量、创建时间、操作按钮），空状态提示「暂无选股池，请点击"新建选股池"创建」
  - [x] 11.2 实现新建选股池对话框（输入框 + 名称校验 + 创建按钮），校验失败时在输入框下方显示错误提示
  - [x] 11.3 实现选股池重命名对话框（预填当前名称 + 校验 + 确认按钮）
  - [x] 11.4 实现选股池删除确认对话框（显示选股池名称和股票数量，确认后调用 API 删除）
  - [x] 11.5 实现选股池详情展开：点击选股池后展示池内股票表格（股票代码、股票名称、加入时间、删除按钮），空池显示「选股池为空，请从选股结果中添加股票」
  - [x] 11.6 实现手动添加股票功能：输入框 + 代码格式校验 + 添加按钮，重复时提示「该股票已在选股池中」
  - [x] 11.7 实现批量移除股票功能：复选框选中 + 「移除」按钮

- [x] 12. 前端：选股结果页面修改
  - [x] 12.1 在 `ScreenerResultsView.vue` 的结果表格中增加复选框列（表头全选 + 每行单选），维护 selectedSymbols 状态
  - [x] 12.2 实现选中后的操作栏：显示已选数量和「添加到选股池」按钮，未选中时隐藏
  - [x] 12.3 实现选股池选择下拉菜单：列出用户所有选股池，无选股池时显示「暂无选股池」和「新建选股池」快捷入口
  - [x] 12.4 实现添加到选股池操作：调用 API、显示成功/跳过提示、清除选中状态
  - [x] 12.5 将导出按钮标签从「📥 导出 Excel」改为「📥 导出 CSV」，修改 exportExcel 函数为 exportCsv（调用 `/screen/export/csv`，下载 CSV 文件）

- [x] 13. 前端测试
  - [x] 13.1 创建 `frontend/src/views/__tests__/StockPoolView.test.ts`，编写选股池页面单元测试（空状态渲染、列表渲染、创建对话框、删除确认）
  - [x] 13.2 创建 `frontend/src/views/__tests__/stockPool.property.test.ts`，使用 fast-check 实现 Property 3（名称校验）和 Property 7（代码校验）的前端属性测试

- [x] 14. 后端：选股池股票富化服务（需求 7）
  - [x] 14.1 在 `app/services/pool_manager.py` 中实现纯函数 `merge_pool_stocks_with_screen_results(pool_stocks: list[dict], screen_results_map: dict[str, dict]) -> list[dict]`：将选股池股票列表与选股结果字典按 symbol 合并，匹配到的股票附带 ref_buy_price/trend_score/risk_level/signals/screen_time/has_fake_breakout/sector_classifications 字段，未匹配到的这些字段设为 None；返回列表长度等于输入 pool_stocks 长度，symbol 和 stock_name 保持不变
    - _Requirements: 7.1, 7.3, 7.6_
  - [x] 14.2 在 `app/services/pool_manager.py` 中实现 `PoolManager.get_enriched_pool_stocks(session, redis, user_id, pool_id) -> list[dict]`：(1) 调用 `get_pool_stocks` 获取基础列表；(2) 从 Redis `screen:results:latest` 读取最新选股结果 JSON，按 symbol 建立索引；(3) 对 Redis 未命中的 symbol，查询 `screen_result` 表中每只股票最近一次记录（使用 `ScreenResult` 模型，按 `screen_time DESC` + `DISTINCT ON symbol`）；(4) Redis 读取失败时静默降级继续从 DB 回退；(5) 调用 `merge_pool_stocks_with_screen_results` 合并返回
    - 需要从 `app/models/strategy.py` 导入 `ScreenResult`
    - 需要从 `app/core/redis_client.py` 导入 Redis 类型
    - _Requirements: 7.3, 7.4, 7.5, 7.6_
  - [x] 14.3 更新 `app/api/v1/pool.py` 中的 `GET /pools/{pool_id}/stocks` 端点：增加可选查询参数 `enriched: bool = False`；当 `enriched=True` 时，通过 `Depends(get_redis)` 注入 Redis 客户端，调用 `PoolManager.get_enriched_pool_stocks` 返回富化数据（含 ref_buy_price, trend_score, risk_level, signals, screen_time, has_fake_breakout, sector_classifications）；当 `enriched=False` 时保持原有行为不变
    - 需要在 `pool.py` 中导入 `get_redis` 依赖
    - 响应格式参见 design.md 中的 API 响应格式示例
    - _Requirements: 7.3, 7.4, 7.5_

- [x] 15. 后端：富化服务测试（需求 7）
  - [x] 15.1 🧪 PBT: 在 `tests/properties/test_pool_properties.py` 中实现 Property 8 测试：选股池股票富化合并完整性 — 使用 Hypothesis 生成随机 pool_stocks 列表（含 symbol, stock_name, added_at）和随机 screen_results_map 字典（部分 symbol 匹配、部分不匹配），验证：(a) 返回列表长度等于输入列表长度；(b) 匹配到的股票富化字段（ref_buy_price, trend_score, risk_level, signals, screen_time）均不为 None；(c) 未匹配到的股票富化字段均为 None；(d) 所有记录的 symbol 和 stock_name 保持不变
    - **Property 8: 选股池股票富化合并完整性**
    - **Validates: Requirements 7.1, 7.3, 7.6**
  - [x] 15.2 在 `tests/services/test_pool_manager.py` 中添加富化查询单元测试：(a) Redis 缓存命中时返回完整富化数据（mock Redis.get 返回 JSON，验证 ref_buy_price/trend_score/signals 等字段非 None）；(b) Redis 未命中时从 PostgreSQL 回退查询（mock Redis.get 返回 None，mock session 查询 ScreenResult，验证回退数据正确）；(c) Redis 和 PostgreSQL 均无数据时返回 null 富化字段；(d) 混合场景（部分 symbol 命中 Redis、部分回退 DB、部分无数据）
    - _Requirements: 7.3, 7.4, 7.5, 7.6_

- [x] 16. Checkpoint — 后端富化服务验证
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. 前端：Store 与 API 层扩展（需求 7）
  - [x] 17.1 在 `frontend/src/stores/stockPool.ts` 中新增 `EnrichedPoolStock` 接口（extends `StockPoolItem`，增加 ref_buy_price: number | null, trend_score: number | null, risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | null, signals: SignalDetail[] | null, screen_time: string | null, has_fake_breakout: boolean, sector_classifications: SectorClassifications | null），同时定义 `SignalDetail` 和 `SectorClassifications` 类型（与 ScreenerResultsView 中的类型定义一致）
    - _Requirements: 7.1, 7.3_
  - [x] 17.2 在 stockPool store 中新增 `enrichedPoolStocks: ref<EnrichedPoolStock[]>([])` 状态和 `fetchEnrichedPoolStocks(poolId: string)` action：调用 `GET /pools/{poolId}/stocks?enriched=true`，将响应存入 `enrichedPoolStocks`；新增 `enrichedLoading: ref<boolean>(false)` 加载状态
    - _Requirements: 7.1, 7.3_

- [x] 18. 前端：选股池富化展示页面（需求 7）
  - [x] 18.1 更新 `StockPoolView.vue` 中的 `togglePool` 方法：展开选股池时调用 `store.fetchEnrichedPoolStocks(poolId)` 替代原有的 `store.fetchPoolStocks(poolId)`，使用 `store.enrichedPoolStocks` 替代 `store.currentPoolStocks` 渲染表格
    - _Requirements: 7.1_
  - [x] 18.2 更新 `StockPoolView.vue` 中的股票表格：将表头和列从基础 4 列（代码、名称、加入时间、操作）扩展为富化 8 列（复选框、股票代码、股票名称、买入参考价、趋势评分含进度条、风险等级含徽章、触发信号摘要、选股时间），复用 ScreenerResultsView 中的 `scoreColor`/`riskLabel`/`signalSummary` 辅助函数和对应 CSS 样式（score-bar-wrap、risk-badge、signals-cell 等）；无选股结果数据的股票（signals === null）其余列显示占位符「—」
    - _Requirements: 7.1, 7.6_
  - [x] 18.3 在 `StockPoolView.vue` 中实现可展开详情面板：点击有选股结果数据的股票行（signals !== null）时展开详情行，复用 ScreenerResultsView 的详情面板模板代码，包含：(a) 触发信号详情（含强度指示器 sig-strong/sig-medium/sig-weak、维度分组 groupSignalsByDimension、新鲜度徽章、假突破标签）；(b) 板块分类展示（东方财富/同花顺/通达信三列布局）；(c) 日 K 线图（含原始/前复权切换，复用 fetchKline/rebuildKlineOptions 逻辑和 v-chart 组件）；(d) 分钟 K 线图（复用 `MinuteKlineChart` 组件，传入 symbol/selectedDate/latestTradeDate props）；无选股结果数据的股票行点击不展开
    - 需要导入 VChart、MinuteKlineChart、ECharts 模块（CandlestickChart, BarChart, GridComponent 等）
    - 需要导入 minuteKlineUtils 中的 AdjType 和 extractDateFromClick
    - _Requirements: 7.2, 7.6, 7.7_
  - [x] 18.4 在 `StockPoolView.vue` 中实现排序功能：添加排序栏（与 ScreenerResultsView 一致），支持按趋势评分（trend_score）、风险等级（risk_level）、信号数量（signals.length）排序；客户端排序，使用 computed 属性对 enrichedPoolStocks 排序后渲染；排序逻辑复用 ScreenerResultsView 中的 RISK_ORDER 映射和 sortKey/sortDir 状态管理模式
    - _Requirements: 7.8_

- [x] 19. 前端：富化展示测试（需求 7）
  - [x] 19.1 在 `frontend/src/views/__tests__/StockPoolView.test.ts` 中添加富化展示测试：(a) 富化表格渲染 — mock fetchEnrichedPoolStocks 返回含完整数据的股票列表，验证表格显示买入参考价、趋势评分进度条、风险等级徽章、信号摘要、选股时间；(b) 无选股结果数据的股票行显示占位符「—」— mock 返回 signals/trend_score 等为 null 的记录，验证对应列显示「—」；(c) 点击有选股结果的股票行展开详情面板 — 验证 detail-panel 元素出现；(d) 点击无选股结果的股票行不展开详情面板 — 验证 detail-panel 不出现；(e) 排序功能 — 点击趋势评分排序按钮后验证表格行顺序变化
    - _Requirements: 7.1, 7.2, 7.6, 7.8_

- [x] 20. Final checkpoint — 全部富化功能验证
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks 1-13 are completed (original stock pool CRUD, CSV export, and basic UI)
- Tasks 14-20 implement Requirement 7 (选股池股票展示与选股结果一致)
- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property tests validate universal correctness properties from the design document
- Frontend detail panel code should be extracted/copied from ScreenerResultsView.vue patterns, not abstracted into shared components (per requirement 7.7 "复用模板代码")
