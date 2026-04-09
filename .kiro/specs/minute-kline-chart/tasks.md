# 实现计划：分钟K线图

## 概述

在选股结果页面新增分钟K线图功能，包括：后端修改 `get_kline` 端点使分钟级查询跳过外部数据源回退；前端新增 `MinuteKlineChart.vue` 组件（含周期选择器）；修改 `ScreenerResultsView.vue` 集成日K线点击联动和左右并排布局。

## 任务

- [x] 1. 后端：修改 get_kline 端点，分钟级查询跳过外部数据源回退
  - [x] 1.1 在 `app/api/v1/data.py` 的 `get_kline` 函数中定义 `MINUTE_FREQS = {"1m", "5m", "15m", "30m", "60m"}`
    - 在本地 DB 无数据的回退逻辑处增加条件判断：`if not bars and freq not in MINUTE_FREQS:` 才回退到 DataSourceRouter
    - 分钟级 freq 本地无数据时直接返回空 bars，不调用第三方 API
    - _需求: 5.2, 5.3, 5.5_

  - [x] 1.2 编写后端单元测试验证分钟级回退逻辑
    - 在 `tests/api/` 下新建 `test_kline_minute_freq.py`
    - 测试分钟级 freq（如 5m）本地无数据时返回空 bars，不调用 DataSourceRouter
    - 测试日级 freq（如 1d）本地无数据时仍回退到 DataSourceRouter
    - _需求: 5.2, 5.5_

  - [x] 1.3 编写后端属性测试：KlineBar JSON 往返一致性
    - 在 `tests/properties/` 下新建 `test_kline_bar_roundtrip_properties.py`
    - **Property 5: KlineBar JSON 序列化往返一致性**
    - 使用 Hypothesis 生成随机 KlineBar 对象，验证序列化为 dict 再反序列化后与原始数据等价
    - **验证: 需求 6.2, 6.3**

- [x] 2. 检查点 - 后端修改验证
  - 确保所有后端测试通过，如有问题请向用户确认。

- [x] 3. 前端：新增 MinuteKlineChart.vue 组件
  - [x] 3.1 创建 `frontend/src/components/MinuteKlineChart.vue` 组件骨架
    - 定义 props: `symbol: string`, `selectedDate: string | null`, `latestTradeDate: string`
    - 定义 emits: `loading`
    - 内部状态: `freq` (默认 `'5m'`), `bars`, `loading`, `error`
    - 实现 FreqSelector 周期按钮组（1m/5m/15m/30m/60m），默认高亮 5m
    - 实现日期标签显示，格式为 `"YYYY-MM-DD 分钟K线"`
    - _需求: 2.1, 2.2, 2.4, 3.3_

  - [x] 3.2 实现分钟K线数据加载与缓存逻辑
    - 使用 `apiClient.get(`/data/kline/${symbol}`, { params: { freq, start: date, end: date } })` 请求数据
    - 实现 `Map<string, KlineBar[]>` 缓存，key 为 `${symbol}-${date}-${freq}`
    - watch `selectedDate` 和 `freq` 变化触发数据加载
    - 首次加载时若 `selectedDate` 为 null，使用 `latestTradeDate`
    - _需求: 3.2, 3.4, 5.1, 5.6_

  - [x] 3.3 实现分钟K线 ECharts 渲染
    - 复用日K线图的 ECharts 配置风格（蜡烛图 + 成交量柱状图）
    - 加载中显示提示文字，空数据显示"该交易日暂无分钟K线数据"，请求失败显示"加载分钟K线失败"
    - _需求: 1.4, 2.5, 3.5, 5.4_

  - [x] 3.4 编写前端属性测试：日期标签格式化
    - 在 `frontend/src/components/__tests__/` 下新建 `minute-kline-chart.property.test.ts`
    - **Property 2: 分钟K线日期标签格式化**
    - 使用 fast-check 生成随机日期字符串，验证格式化后匹配 `"YYYY-MM-DD 分钟K线"` 模式
    - **验证: 需求 3.3**

  - [x] 3.5 编写前端属性测试：API 请求参数构造
    - **Property 3: 分钟K线 API 请求参数构造**
    - 使用 fast-check 生成随机 symbol/freq/date，验证构造的请求 URL 包含正确的路径参数和 query 参数
    - **验证: 需求 5.1**

  - [x] 3.6 编写前端属性测试：缓存命中避免重复请求
    - **Property 4: 前端缓存命中避免重复请求**
    - 使用 fast-check 生成随机 symbol/freq/date 组合，验证首次请求后相同参数再次请求时命中缓存
    - **验证: 需求 5.6**

- [x] 4. 检查点 - MinuteKlineChart 组件验证
  - 确保所有前端测试通过，如有问题请向用户确认。

- [x] 5. 前端：修改 ScreenerResultsView.vue 集成分钟K线联动
  - [x] 5.1 修改 `ScreenerResultsView.vue` 布局为左右并排
    - 详情面板从单图改为左右双图（flex 布局，日K线 50% + 分钟K线 50%）
    - 添加响应式样式：`@media (max-width: 768px)` 切换为上下堆叠，各 100% 宽度
    - 引入并渲染 `MinuteKlineChart` 组件
    - _需求: 1.1, 1.2, 1.3_

  - [x] 5.2 实现日K线点击事件联动
    - 新增 `selectedDates: Record<string, string>` 状态，记录每只股票的选中日期
    - 在日K线 ECharts 实例上注册 `click` 事件，从 `params.dataIndex` 提取日期更新 `selectedDates[symbol]`
    - 将 `selectedDates[symbol]` 作为 `selectedDate` prop 传递给 MinuteKlineChart
    - 计算 `latestTradeDate`（日K线 bars 数组最后一条的日期）传递给 MinuteKlineChart
    - _需求: 3.1, 3.2, 3.4_

  - [x] 5.3 实现日K线点击视觉反馈（markLine 高亮线）
    - 点击日K线后，在 ECharts option 中添加 `markLine` 配置，在选中日期位置绘制垂直高亮线
    - 高亮线颜色使用 `#58a6ff` 半透明蓝色
    - 点击新K线时移除旧标记线，仅保留一条
    - _需求: 4.1, 4.2, 4.3_

  - [x] 5.4 编写前端属性测试：日K线点击提取正确日期
    - 在 `frontend/src/views/__tests__/` 下新建 `screener-results-kline.property.test.ts`
    - **Property 1: 日K线点击提取正确日期**
    - 使用 fast-check 生成随机 bars 数组和索引，验证点击后 selectedDate 等于 `bars[i].time` 的日期部分
    - **验证: 需求 3.1**

- [x] 6. 最终检查点 - 全部测试通过
  - 确保所有前端和后端测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选，可跳过以加速 MVP 交付
- 每个任务引用了对应的需求编号，确保可追溯性
- 检查点任务用于增量验证，确保每个阶段的代码质量
- 属性测试验证设计文档中定义的正确性属性，单元测试验证具体示例和边界情况
