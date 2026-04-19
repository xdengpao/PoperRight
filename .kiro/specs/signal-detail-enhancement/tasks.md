# Implementation Plan: 信号详情增强（Signal Detail Enhancement）

## Overview

本计划将设计文档中的信号详情增强方案转化为可执行的编码任务。后端使用 Python（FastAPI + dataclasses），前端使用 TypeScript（Vue 3 Composition API）。任务按增量方式组织：先扩展数据模型，再实现描述文本生成逻辑，然后增强 API 序列化，最后完成前端展示增强。

## Tasks

- [x] 1. 扩展 SignalDetail 数据模型
  - [x] 1.1 在 `app/core/schemas.py` 的 `SignalDetail` dataclass 中添加 `description: str = ""` 字段
    - 在 `freshness` 字段之后添加，保持字段顺序与设计文档一致
    - 添加中文注释说明该字段用途
    - _Requirements: 8.1, 8.2_

  - [x] 1.2 编写属性测试验证 SignalDetail JSON 往返一致性
    - **Property 1: SignalDetail JSON round-trip**
    - 在 `tests/properties/test_signal_detail_props.py` 中使用 Hypothesis 生成任意合法 `SignalDetail` 对象
    - 验证 `dataclasses.asdict()` 序列化后重建对象字段值完全一致
    - 最少 100 次迭代
    - **Validates: Requirements 1.4, 8.3**

- [x] 2. 实现描述文本生成逻辑
  - [x] 2.1 在 `app/services/screener/screen_executor.py` 的 `ScreenExecutor` 类中新增 `_generate_signal_description()` 静态纯函数
    - 接受 `signal: SignalDetail` 和 `stock_data: dict[str, Any]` 参数，返回 `str`
    - 按设计文档中的模板为每种 `SignalCategory` 生成描述文本：
      - `MA_TREND`: 从 `stock_data["ma_trend"]` 读取趋势评分，生成 `"均线多头排列, 趋势评分 {score}"`
      - `MACD`: 固定文本 `"MACD 金叉, DIF 上穿 DEA"`
      - `BOLL`: 固定文本 `"价格突破布林带中轨, 接近上轨"`
      - `RSI`: 从 `stock_data` 读取 RSI 值，生成 `"RSI(14) = {value}, 处于强势区间"`
      - `DMA`: 从 `stock_data["dma"]["dma"]` 读取值，生成 `"DMA 上穿 AMA, DMA={value}"`
      - `BREAKOUT`: 从突破数据读取类型和量比，生成 `"{type}突破, 量比 {ratio} 倍"`，使用中文映射（BOX→箱体, PREVIOUS_HIGH→前高, TRENDLINE→趋势线）
      - `CAPITAL_INFLOW`: 固定文本 `"主力资金净流入"`
      - `LARGE_ORDER`: 固定文本 `"大单成交活跃"`
      - `MA_SUPPORT`: 固定文本 `"回调至均线获支撑"`
      - `SECTOR_STRONG`: 从 `stock_data["sector_name"]` 读取板块名，生成 `"所属板块涨幅排名前列"`
    - 当 `stock_data` 缺少预期字段时返回通用描述文本（如 `"均线趋势信号"`），不抛异常
    - 未知 `SignalCategory` 返回空字符串
    - 添加中文 docstring
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11_

  - [x] 2.2 在 `ScreenExecutor._execute()` 方法中，信号强度计算之后、新鲜度标记之前，为每个 `SignalDetail` 调用 `_generate_signal_description()` 并将返回值赋给 `signal.description`
    - 需要在信号列表构建完成、`_compute_signal_strength()` 调用之后的循环中添加
    - 传入对应股票的 `stock_data`
    - _Requirements: 2.11_

  - [x] 2.3 编写属性测试验证描述文本生成非空
    - **Property 3: Description generation non-empty**
    - 在 `tests/properties/test_signal_detail_props.py` 中使用 Hypothesis 生成任意合法 `SignalDetail`（已知 `SignalCategory`）和包含类别相关因子值的 `stock_data` 字典
    - 验证 `_generate_signal_description(signal, stock_data)` 返回非空字符串
    - 最少 100 次迭代
    - **Validates: Requirements 2.1, 2.4, 2.5, 2.6, 2.10, 2.11**

  - [x] 2.4 编写单元测试验证各信号类别的描述文本内容
    - 在 `tests/services/test_signal_description.py` 中编写测试
    - 覆盖所有 10 种 `SignalCategory` 的正常描述文本生成
    - 覆盖 `stock_data` 缺少字段时的降级描述
    - 覆盖 `SignalDetail` 默认 `description` 为空字符串
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

- [x] 3. Checkpoint - 确保后端核心逻辑测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 增强 API 序列化
  - [x] 4.1 修改 `app/api/v1/screen.py` 中 `run_screen` 函数的信号序列化逻辑
    - 在现有的 `signals` 列表推导中添加 `strength`、`freshness`、`description` 三个字段
    - `strength` 使用 `s.strength.value`，`freshness` 使用 `s.freshness.value`，`description` 使用 `s.description`
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 4.2 编写属性测试验证 API 序列化字段完整性
    - **Property 2: API serialization completeness**
    - 在 `tests/properties/test_signal_detail_props.py` 中使用 Hypothesis 生成任意合法 `SignalDetail` 对象
    - 模拟 API 序列化逻辑，验证输出 dict 包含全部六个字段（`category`、`label`、`is_fake_breakout`、`strength`、`freshness`、`description`）
    - 验证 `strength` 值为 `"STRONG"`/`"MEDIUM"`/`"WEAK"` 之一，`freshness` 值为 `"NEW"`/`"CONTINUING"` 之一，`description` 为字符串
    - 最少 100 次迭代
    - **Validates: Requirements 1.1, 1.2, 1.3**

- [x] 5. Checkpoint - 确保后端全部测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 前端信号类型扩展与标签增强
  - [x] 6.1 在 `frontend/src/views/ScreenerResultsView.vue` 中扩展 `SignalDetail` TypeScript 接口
    - 添加可选字段 `strength?: 'STRONG' | 'MEDIUM' | 'WEAK'`
    - 添加可选字段 `freshness?: 'NEW' | 'CONTINUING'`
    - 添加可选字段 `description?: string`
    - 所有新字段使用可选类型确保向后兼容
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 6.2 增强信号标签组件展示
    - 修改 `signal-tags` 区域的信号标签渲染逻辑：
      - 优先显示 `sig.description`（非空时），缺失或为空时回退到 `sig.label`
      - 格式为 `"分类名：描述文本"` 或 `"分类名：label"`
    - 根据 `sig.strength` 添加强度 CSS 类（`sig-strong`、`sig-medium`、`sig-weak`）
    - 在标签内添加强度文字标注（"强"/"中"/"弱"），`strength` 缺失时默认 `MEDIUM`
    - 当 `sig.freshness === 'NEW'` 时显示"新"徽章，缺失时不显示
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 6.1, 6.2, 6.3_

  - [x] 6.3 添加信号强度颜色 CSS 样式
    - 添加 `.sig-strong` 样式：边框色 `#f85149`（红），背景色 `#3a1a1a`
    - 添加 `.sig-medium` 样式：边框色 `#d29922`（橙），背景色 `#3a2a1a`
    - 添加 `.sig-weak` 样式：边框色 `#484f58`（灰），背景色 `#21262d`
    - 添加 `.freshness-badge` 样式用于"新"徽章
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 7. 前端信号强度图例与摘要增强
  - [x] 7.1 新增 `SignalStrengthLegend` 图例组件
    - 在信号详情区域（`detail-signals`）的 `detail-header` 下方添加图例
    - 展示三个强度等级的颜色样本和中文说明：`"🔴 强：多个因子共振确认  🟡 中：部分因子确认  ⚪ 弱：单一因子触发"`
    - 当选股结果列表为空时不显示图例
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 7.2 增强 `signalSummary` 函数
    - 修改 `signalSummary` 函数，在信号数量旁展示强信号数量
    - 当存在 `STRONG` 信号时显示 `"N 个信号（M 强）"`
    - 当无 `STRONG` 信号时仅显示 `"N 个信号"`
    - 保留原有的分类名展示逻辑
    - _Requirements: 7.1, 7.2_

  - [x] 7.3 编写属性测试验证信号摘要强信号计数
    - **Property 4: Signal summary strong count**
    - 在 `frontend/src/views/__tests__/signalSummary.property.test.ts` 中使用 fast-check 生成任意信号列表
    - 验证摘要字符串包含强信号数量当且仅当至少一个信号为 `STRONG`
    - **Validates: Requirements 7.1, 7.2**

  - [x] 7.4 编写单元测试验证前端信号标签增强
    - 在 `frontend/src/views/__tests__/ScreenerResultsView.test.ts` 中编写测试
    - 覆盖描述文本显示与回退逻辑
    - 覆盖强度颜色编码 CSS 类映射
    - 覆盖新鲜度徽章显示/隐藏逻辑
    - 覆盖图例组件条件渲染（空结果时隐藏）
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.5, 5.4, 6.1, 6.2, 6.3_

- [x] 8. Final checkpoint - 确保全部测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. 后端：板块分类数据加载
  - [x] 9.1 在 `app/services/screener/screen_data_provider.py` 的 `ScreenDataProvider` 类中新增 `_load_sector_classifications()` 异步方法
    - 接受 `pg_session: AsyncSession`、`symbols: list[str]`、`trade_date: date | None = None` 参数
    - 批量查询 `SectorConstituent` 表，获取所有目标股票在三个数据源（DC/TI/TDX）的成分股记录，使用 `SectorConstituent.symbol.in_(symbols)` + `SectorConstituent.data_source.in_(["DC", "TI", "TDX"])` 避免 N+1 查询
    - 若 `trade_date` 为 None，先查询 `SectorConstituent` 表中 `func.max(trade_date)` 获取最新交易日
    - 批量查询 `SectorInfo` 表，构建 `(sector_code, data_source) → name` 映射，用于将 `sector_code` 转换为人类可读的板块名称；若 `SectorInfo` 中缺少某 `sector_code`，使用 `sector_code` 原始值作为板块名称
    - 返回 `{symbol: {"DC": [板块名, ...], "TI": [...], "TDX": [...]}}` 格式的字典
    - 添加中文 docstring
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 9.2 在 `load_screen_data()` 方法的步骤 6（板块强势数据加载）之后，新增步骤 7 调用 `_load_sector_classifications()`
    - 传入 `pg_session=self._pg_session`、`symbols=list(result.keys())`
    - 将返回的板块分类数据写入每只股票的 `factor_dict["sector_classifications"]`
    - 使用 `try/except` 包裹，加载失败时降级为空分类 `{"DC": [], "TI": [], "TDX": []}`，记录 WARNING 日志，不阻断选股主流程
    - _Requirements: 9.1, 9.3, 9.7_

  - [x] 9.3 编写单元测试验证板块分类数据加载
    - 在 `tests/services/test_sector_classifications.py` 中编写测试
    - 覆盖正常加载三个数据源板块数据的场景
    - 覆盖某数据源无数据时返回空列表的场景
    - 覆盖数据库查询失败时降级为空分类的场景
    - 覆盖数据源代码到 API 键名映射正确性（DC→eastmoney, TI→tonghuashun, TDX→tongdaxin）
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 10. 后端：API 序列化板块分类字段
  - [x] 10.1 修改 `app/api/v1/screen.py` 中 `run_screen` 函数的响应构建逻辑
    - 在模块顶部定义数据源代码到 API 键名的映射常量 `_SOURCE_TO_API_KEY = {"DC": "eastmoney", "TI": "tonghuashun", "TDX": "tongdaxin"}`
    - 在 item 序列化字典中添加 `sector_classifications` 字段，从 `stocks_data.get(item.symbol, {}).get("sector_classifications", {"DC": [], "TI": [], "TDX": []})` 读取，使用 `_SOURCE_TO_API_KEY` 映射键名
    - 确保 `sector_classifications` 缺失时使用默认空对象 `{"eastmoney": [], "tonghuashun": [], "tongdaxin": []}`
    - _Requirements: 9.1, 9.2, 9.3, 9.7_

  - [x] 10.2 编写属性测试验证 sector_classifications 序列化完整性
    - **Property 5: sector_classifications serialization completeness**
    - 在 `tests/properties/test_signal_detail_props.py` 中使用 Hypothesis 生成任意板块分类数据（每个数据源映射到零或多个板块名称字符串）
    - 模拟 API 序列化逻辑（DC→eastmoney, TI→tonghuashun, TDX→tongdaxin），验证输出对象包含恰好三个键（`eastmoney`、`tonghuashun`、`tongdaxin`），每个值为字符串列表
    - 验证 JSON 序列化再反序列化后产生相同对象
    - 最少 100 次迭代
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.7**

- [x] 11. Checkpoint - 确保后端板块分类相关测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. 前端：板块分类类型定义与三列布局展示
  - [x] 12.1 在 `frontend/src/views/ScreenerResultsView.vue` 中扩展类型定义
    - 新增 `SectorClassifications` 接口：`{ eastmoney: string[]; tonghuashun: string[]; tongdaxin: string[] }`
    - 在 `ScreenResultRow` 接口中添加可选字段 `sector_classifications?: SectorClassifications`
    - 新增 `sectorSources` 常量数组：`[{ key: 'eastmoney', label: '东方财富' }, { key: 'tonghuashun', label: '同花顺' }, { key: 'tongdaxin', label: '通达信' }]`
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

  - [x] 12.2 在 `detail-signals` 区域内部、信号标签列表下方嵌套板块分类区域
    - 板块分类区域嵌套在 `detail-signals` 内部（而非作为与信号区和K线图表并列的独立 flex 子项），避免挤占K线图表水平空间
    - 使用 `v-if="row.sector_classifications"` 条件渲染，`sector_classifications` 缺失时不渲染
    - 添加 `detail-header` 标题"板块分类"
    - 使用 `v-for="source in sectorSources"` 遍历三个数据源，每列显示数据源中文标题和板块标签列表
    - 当某数据源板块列表为空时显示"暂无数据"占位文本
    - _Requirements: 9.4, 9.5, 9.6, 9.8_

  - [x] 12.3 添加板块分类 CSS 样式
    - 添加 `.sector-classifications` 容器样式（margin-top、padding-top、border-top 分隔线）
    - 添加 `.sector-columns` 三列 flex 布局（`display: flex; gap: 16px`）
    - 添加 `.sector-column` 等宽列样式（`flex: 1; min-width: 0`）
    - 添加 `.sector-source-title` 数据源标题样式（12px、#8b949e 灰色、font-weight 600）
    - 添加 `.sector-tags` 标签容器样式（flex-wrap）
    - 添加 `.sector-tag` 单个板块标签样式（#1c2128 背景、#e6edf3 文字、#30363d 边框、4px 圆角）
    - 添加 `.sector-empty` 空数据占位样式（12px、#484f58 灰色）
    - _Requirements: 9.4, 9.5, 9.6_

  - [x] 12.4 编写前端单元测试验证板块分类渲染
    - 在 `frontend/src/views/__tests__/ScreenerResultsView.test.ts` 中编写测试
    - 覆盖板块分类三列布局渲染（三个数据源均有数据）
    - 覆盖数据源中文标题正确显示（"东方财富"、"同花顺"、"通达信"）
    - 覆盖某数据源板块列表为空时显示"暂无数据"占位文本
    - 覆盖 `sector_classifications` 字段缺失时不渲染板块分类区域
    - _Requirements: 9.4, 9.5, 9.6_

- [x] 13. Final checkpoint - 确保全部测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. 后端：信号维度映射与 API 序列化
  - [x] 14.1 在 `app/api/v1/screen.py` 模块顶部定义 `_SIGNAL_DIMENSION_MAP` 常量
    - 定义 `dict[str, str]` 类型的映射：`MA_TREND`/`MACD`/`BOLL`/`RSI`/`DMA`/`BREAKOUT`/`MA_SUPPORT` → `"技术面"`，`CAPITAL_INFLOW`/`LARGE_ORDER` → `"资金面"`，`SECTOR_STRONG` → `"板块面"`
    - 添加中文注释说明映射用途和需求编号（需求 10）
    - _Requirements: 10.1_

  - [x] 14.2 修改 `app/api/v1/screen.py` 中 `run_screen` 函数的信号序列化逻辑，在每条信号的序列化字典中添加 `dimension` 字段
    - 使用 `_SIGNAL_DIMENSION_MAP.get(s.category.value, "其他")` 实时派生 `dimension` 值
    - 确保缓存读取路径也包含 `dimension` 字段序列化（需求 10.6）
    - _Requirements: 10.1, 10.2, 10.6_

  - [x] 14.3 修改 `app/services/screener/screen_executor.py` 中 `_generate_signal_description()` 的 `SECTOR_STRONG` 分支
    - 从 `stock_data.get("sector_name")` 读取板块名称
    - 当 `sector_name` 存在时生成 `"所属板块【{sector_name}】涨幅排名前列"`
    - 当 `sector_name` 缺失时回退为 `"所属板块涨幅排名前列"`
    - _Requirements: 10.7, 2.10_

  - [x] 14.4 编写属性测试验证信号维度映射完整性
    - **Property 6: dimension mapping completeness**
    - 在 `tests/properties/test_signal_detail_props.py` 中使用 Hypothesis 生成任意合法 `SignalDetail` 对象（已知 `SignalCategory`）
    - 模拟 API 序列化逻辑，验证输出 dict 包含 `dimension` 字段，值为 `"技术面"`、`"资金面"`、`"基本面"`、`"板块面"` 之一
    - 验证所有已知 `SignalCategory` 值均在 `_SIGNAL_DIMENSION_MAP` 中有映射
    - 最少 100 次迭代
    - **Validates: Requirements 10.1, 10.2, 10.5**

  - [x] 14.5 编写单元测试验证维度映射和 SECTOR_STRONG 描述更新
    - 在 `tests/services/test_signal_description.py` 中新增测试：
      - SECTOR_STRONG 信号在 `sector_name` 存在时描述包含板块名（如 `"所属板块【半导体】涨幅排名前列"`）
      - SECTOR_STRONG 信号在 `sector_name` 缺失时回退为通用描述
    - 在 `tests/api/test_screen_api.py` 中新增测试：
      - `_SIGNAL_DIMENSION_MAP` 覆盖所有已知 `SignalCategory` 值
      - API 序列化中 `dimension` 字段值与映射一致
    - _Requirements: 10.1, 10.2, 10.7_

- [x] 15. Checkpoint - 确保后端维度映射相关测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. 前端：信号维度分组展示
  - [x] 16.1 在 `frontend/src/views/ScreenerResultsView.vue` 中扩展 `SignalDetail` TypeScript 接口
    - 添加可选字段 `dimension?: string`
    - _Requirements: 10.2_

  - [x] 16.2 添加维度分组常量和分组函数
    - 定义 `DIMENSION_ORDER` 常量数组：`['技术面', '板块面', '资金面', '基本面']`（需求 10.4 指定顺序）
    - 实现 `groupSignalsByDimension(signals: SignalDetail[])` 函数：
      - 按 `dimension` 字段分组信号，`dimension` 缺失时归入 `"其他"`（需求 10.5）
      - 按 `DIMENSION_ORDER` 固定顺序排列分组，跳过无信号的维度
      - 不在预定义顺序中的维度（如"其他"）追加到末尾
    - _Requirements: 10.3, 10.4, 10.5_

  - [x] 16.3 修改信号标签区域模板，按维度分组渲染
    - 将现有的 `v-for="(sig, idx) in row.signals"` 替换为嵌套的 `v-for` 结构：
      - 外层遍历 `groupSignalsByDimension(row.signals)` 获取维度分组
      - 每组渲染一个 `.dimension-header` 标题（维度中文名）
      - 内层遍历分组内的信号，保留现有的信号标签渲染逻辑不变
    - _Requirements: 10.3, 10.4_

  - [x] 16.4 添加维度分组标题 CSS 样式
    - 添加 `.dimension-header` 样式：`width: 100%`、`font-size: 12px`、`font-weight: 600`、`color: #8b949e`、`margin-top: 8px`、`margin-bottom: 4px`、`border-bottom: 1px solid #21262d`
    - 添加 `.dimension-header:first-child` 样式：`margin-top: 0`（首个分组无上边距）
    - _Requirements: 10.3_

  - [x] 16.5 编写前端单元测试验证维度分组渲染
    - 在 `frontend/src/views/__tests__/ScreenerResultsView.test.ts` 中编写测试
    - 覆盖信号按维度分组展示，每组有维度标题
    - 覆盖维度分组按固定顺序（技术面 → 板块面 → 资金面 → 基本面）
    - 覆盖无信号的维度分组被跳过
    - 覆盖 `dimension` 缺失时信号归入"其他"分组
    - _Requirements: 10.3, 10.4, 10.5_

- [x] 17. Final checkpoint - 确保全部测试通过（含维度分类功能）
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (Hypothesis for backend, fast-check for frontend)
- Unit tests validate specific examples and edge cases
- 所有代码注释和 docstring 使用中文
