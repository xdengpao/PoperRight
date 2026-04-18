# 需求文档：智能选股因子条件编辑器优化

## 简介

当前智能选股系统的因子条件编辑器存在三个核心问题：

1. **阈值类型不合理**：多数因子指标使用绝对值阈值（如主力资金净流入 ≥ 1000 万、市值 ≥ 50 亿），无法适应不同市值、不同行业的股票特征，导致跨市场比较失真。部分因子应改用相对值（百分位排名、行业相对值、Z-Score）。
2. **因子设置缺乏文档化**：每项因子指标缺少清晰的说明文档，量化交易员难以理解各因子的含义、适用场景、推荐阈值和配置示例。
3. **板块面指标数据源单一**：当前板块强势筛选仅使用 TimescaleDB K线数据聚合，未接入已导入数据库的通达信、同花顺、东方财富板块数据，也不支持按行业/概念/地区/风格等不同板块分类标准进行筛选。

本功能将对因子条件编辑器进行全面优化，涵盖阈值类型评估与修正、因子元数据文档化、板块面指标多数据源接入三个方面。

## 术语表

- **Factor_Editor（因子条件编辑器）**：智能选股系统中用于配置因子筛选条件的前端可视化组件，支持技术面、资金面、基本面、板块面四类因子
- **Threshold_Type（阈值类型）**：因子条件的比较基准类型，包括 absolute（绝对值）、percentile（百分位排名）、industry_relative（行业相对值）、z_score（标准化分数）
- **Factor_Meta（因子元数据）**：描述单个因子指标的结构化信息，包含因子名称、中文标签、所属类别、阈值类型、默认值、取值范围、说明文本和配置示例
- **ScreenDataProvider（选股数据提供服务）**：后端服务模块，负责从数据库加载股票行情和基本面数据，转换为选股执行器所需的因子字典格式
- **SectorStrengthFilter（板块强势筛选器）**：后端服务模块，负责计算板块涨跌幅排名并过滤候选股票
- **SectorKline（板块行情）**：已导入数据库的板块指数日K线行情数据，存储于 TimescaleDB
- **SectorConstituent（板块成分）**：已导入数据库的板块成分股每日快照数据，存储于 PostgreSQL
- **SectorInfo（板块信息）**：已导入数据库的板块元数据，包含板块代码、名称、类型、数据来源
- **DataSource（数据来源）**：板块数据的提供方，取值为 DC（东方财富）、TI（同花顺）、TDX（通达信）
- **SectorType（板块类型）**：板块分类标准，取值为 INDUSTRY（行业板块）、CONCEPT（概念板块）、REGION（地区板块）、STYLE（风格板块）
- **StrategyConfig（策略配置）**：选股策略的完整配置数据结构，包含因子条件列表、逻辑运算、权重等
- **FactorCondition（因子条件）**：单个因子筛选条件，包含因子名称、运算符、阈值和参数
- **STRATEGY_EXAMPLES（策略示例库）**：系统内置的实战选股策略示例集合，每个示例包含完整的 StrategyConfig 配置，可一键加载到因子条件编辑器

## 需求

### 需求 1：因子元数据注册表

**用户故事：** 作为量化交易员，我需要系统为每个因子指标维护结构化的元数据信息，以便在因子条件编辑器中展示因子说明、推荐阈值和配置示例。

#### 验收标准

1. THE Factor_Editor SHALL 维护一个因子元数据注册表（FACTOR_REGISTRY），包含技术面、资金面、基本面、板块面四类因子的全部指标定义
2. THE FACTOR_REGISTRY SHALL 为每个因子指标存储以下元数据字段：因子名称（factor_name）、中文标签（label）、所属类别（category）、阈值类型（threshold_type）、默认阈值（default_threshold）、取值范围下限（value_min）、取值范围上限（value_max）、单位（unit）、说明文本（description）、配置示例列表（examples）
3. THE FACTOR_REGISTRY SHALL 将阈值类型（threshold_type）限制为以下枚举值：absolute（绝对值）、percentile（百分位排名）、industry_relative（行业相对值）、z_score（标准化分数）、boolean（布尔型）、range（区间型）
4. WHEN 前端因子条件编辑器加载时，THE Factor_Editor SHALL 通过 API 获取 FACTOR_REGISTRY 数据，用于展示因子选择列表、默认阈值和说明提示
5. THE FACTOR_REGISTRY SHALL 作为后端 Python 模块中的常量字典定义，并通过 API 端点暴露给前端

### 需求 2：技术面因子阈值评估与优化

**用户故事：** 作为量化交易员，我需要技术面因子指标使用合理的阈值类型和默认值，以便获得准确的技术信号筛选结果。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 将 ma_trend（MA趋势打分）定义为：阈值类型 absolute，取值范围 0-100，默认阈值 80，单位"分"，说明"基于均线排列程度、斜率和价格距离的综合打分，≥80 表示强势多头趋势"
2. THE FACTOR_REGISTRY SHALL 将 ma_support（均线支撑信号）定义为：阈值类型 boolean，默认阈值 true，说明"价格回调至 20/60 日均线附近后企稳反弹的信号"
3. THE FACTOR_REGISTRY SHALL 将 macd（MACD金叉信号）定义为：阈值类型 boolean，默认阈值 true，说明"DIF/DEA 零轴上方金叉 + 红柱放大 + DEA 向上的多头信号"
4. THE FACTOR_REGISTRY SHALL 将 boll（布林带突破信号）定义为：阈值类型 boolean，默认阈值 true，说明"股价站稳中轨、触碰上轨且布林带开口向上的突破信号"
5. THE FACTOR_REGISTRY SHALL 将 rsi（RSI强势信号）定义为：阈值类型 range，取值范围 0-100，默认阈值区间 [50, 80]，说明"RSI 处于强势区间且无超买背离，50-80 为适中强势区间"
6. THE FACTOR_REGISTRY SHALL 将 dma（DMA平行线差）定义为：阈值类型 boolean，默认阈值 true，说明"DMA 线在 AMA 线上方，表示短期均线强于长期均线"
7. THE FACTOR_REGISTRY SHALL 将 breakout（形态突破）定义为：阈值类型 boolean，默认阈值 true，说明"箱体突破/前期高点突破/下降趋势线突破，需量价确认（量比 ≥ 1.5 倍）"

### 需求 3：资金面因子阈值评估与优化

**用户故事：** 作为量化交易员，我需要资金面因子指标使用合理的阈值类型，特别是将不适合使用绝对值的指标改为相对值，以便在不同市值股票间进行公平比较。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 将 turnover（换手率）定义为：阈值类型 range，取值范围 0-100，默认阈值区间 [3.0, 15.0]，单位"%"，说明"换手率反映交易活跃度，3%-15% 为适中活跃区间，过低表示流动性不足，过高可能存在异常交易"。阈值类型保持 absolute，因为换手率本身已是标准化百分比指标
2. THE FACTOR_REGISTRY SHALL 将 money_flow（主力资金净流入）定义为：阈值类型由 absolute 改为 percentile，默认阈值 80（即排名前 20%），说明"主力资金净流入的全市场百分位排名。原绝对值阈值 1000 万对大盘股偏低、对小盘股偏高，改用百分位排名可跨市值公平比较"
3. WHEN 使用 percentile 阈值类型评估 money_flow 时，THE ScreenDataProvider SHALL 计算全市场股票主力资金净流入的百分位排名，将排名值（0-100）作为因子值供 FactorEvaluator 比较
4. THE FACTOR_REGISTRY SHALL 将 large_order（大单成交占比）定义为：阈值类型 absolute，取值范围 0-100，默认阈值 30，单位"%"，说明"大单成交额占总成交额的比例，>30% 表示主力资金活跃。该指标本身为百分比，适合使用绝对值阈值"
5. THE FACTOR_REGISTRY SHALL 将 volume_price（日均成交额）定义为：阈值类型由 absolute 改为 percentile，默认阈值 70（即排名前 30%），说明"近 20 日日均成交额的全市场百分位排名。原绝对值阈值 5000 万对微盘股过高，改用百分位排名可自适应市场整体流动性水平"
6. WHEN 使用 percentile 阈值类型评估 volume_price 时，THE ScreenDataProvider SHALL 计算全市场股票日均成交额的百分位排名，将排名值（0-100）作为因子值供 FactorEvaluator 比较

### 需求 4：基本面因子阈值评估与优化

**用户故事：** 作为量化交易员，我需要基本面因子指标使用行业相对值或百分位排名，以便在不同行业间进行合理的估值比较。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 将 pe（市盈率 TTM）定义为：阈值类型由 absolute 改为 industry_relative，默认阈值 1.0（即等于行业中位数），取值范围 0-5.0（行业中位数的倍数），说明"市盈率的行业相对值（当前 PE / 行业中位数 PE）。原绝对值阈值无法跨行业比较（银行 PE 5-10 vs 科技 PE 30-80），改用行业相对值可识别行业内的相对低估"
2. THE FACTOR_REGISTRY SHALL 将 pb（市净率）定义为：阈值类型由 absolute 改为 industry_relative，默认阈值 1.0，取值范围 0-5.0，说明"市净率的行业相对值（当前 PB / 行业中位数 PB）。不同行业 PB 差异极大（银行 0.5-1.0 vs 科技 3-10），行业相对值更有意义"
3. THE FACTOR_REGISTRY SHALL 将 roe（净资产收益率）定义为：阈值类型 percentile，默认阈值 70（即排名前 30%），取值范围 0-100，说明"ROE 的全市场百分位排名。ROE 绝对值受行业特性影响大，百分位排名可筛选各行业中盈利能力较强的公司"
4. THE FACTOR_REGISTRY SHALL 将 profit_growth（利润增长率）定义为：阈值类型 percentile，默认阈值 70，取值范围 0-100，说明"净利润同比增长率的全市场百分位排名。增长率绝对值波动大且受基数效应影响，百分位排名更稳定"
5. THE FACTOR_REGISTRY SHALL 将 market_cap（总市值）定义为：阈值类型由 absolute 改为 percentile，默认阈值 30（即排名前 70%，过滤掉最小的 30% 微盘股），取值范围 0-100，说明"总市值的全市场百分位排名。原绝对值阈值 50 亿会随市场整体估值变化而失效，百分位排名可自适应"
6. THE FACTOR_REGISTRY SHALL 新增 revenue_growth（营收增长率）因子定义：阈值类型 percentile，默认阈值 70，取值范围 0-100，说明"营业收入同比增长率的全市场百分位排名"
7. WHEN 使用 industry_relative 阈值类型评估 pe 或 pb 时，THE ScreenDataProvider SHALL 基于股票所属行业板块计算行业中位数，将（个股值 / 行业中位数）作为因子值供 FactorEvaluator 比较
8. WHEN 使用 percentile 阈值类型评估基本面因子时，THE ScreenDataProvider SHALL 计算全市场有效股票（排除 ST、退市）的百分位排名，将排名值（0-100）作为因子值供 FactorEvaluator 比较

### 需求 5：板块面因子多数据源支持

**用户故事：** 作为量化交易员，我需要板块面指标能够使用已导入数据库的通达信、同花顺和东方财富板块数据，并可灵活选择数据源和板块分类标准，以便获得更全面准确的板块强弱分析。

#### 验收标准

1. THE StrategyConfig SHALL 新增板块筛选配置字段：数据来源（sector_data_source，枚举值 DC/TI/TDX，默认 DC）、板块类型（sector_type，枚举值 INDUSTRY/CONCEPT/REGION/STYLE，默认 CONCEPT）、涨幅计算周期（sector_period，默认 5 天）、排名阈值（sector_top_n，默认 30）
2. WHEN 执行板块强势筛选时，THE ScreenDataProvider SHALL 从 SectorKline 表查询指定数据来源和板块类型的板块行情数据，替代当前从个股 K 线聚合的方式
3. WHEN 执行板块强势筛选时，THE ScreenDataProvider SHALL 从 SectorConstituent 表查询最近交易日的板块成分股数据，用于将候选股票映射到所属板块
4. THE SectorStrengthFilter SHALL 使用 SectorKline 行情数据计算板块涨跌幅排名，按 sector_period 天的累计涨跌幅降序排列
5. THE SectorStrengthFilter SHALL 使用 SectorConstituent 成分数据将候选股票映射到板块，仅保留属于排名前 sector_top_n 板块的成分股
6. IF 指定数据来源的板块数据不可用（未导入或查询失败），THEN THE ScreenDataProvider SHALL 记录警告日志并跳过板块强势筛选，不阻塞其他因子的评估

### 需求 6：板块面因子元数据定义

**用户故事：** 作为量化交易员，我需要板块面因子指标在因子元数据注册表中有清晰的定义和配置说明，以便在因子条件编辑器中正确配置板块筛选条件。

#### 验收标准

1. THE FACTOR_REGISTRY SHALL 将 sector_rank（板块涨幅排名）定义为：阈值类型 absolute，取值范围 1-300，默认阈值 30，说明"股票所属板块在全市场板块涨幅排名中的位次，≤30 表示处于强势板块前 30 名"
2. THE FACTOR_REGISTRY SHALL 将 sector_trend（板块趋势）定义为：阈值类型 boolean，默认阈值 true，说明"股票所属板块是否处于多头趋势（板块指数短期均线在长期均线上方）"
3. THE FACTOR_REGISTRY SHALL 为 sector_rank 和 sector_trend 的配置示例中包含数据来源和板块类型的选择说明

### 需求 7：前端因子条件编辑器增强

**用户故事：** 作为量化交易员，我需要因子条件编辑器在界面上展示因子说明、推荐阈值和阈值类型标识，以便快速理解和配置因子条件。

#### 验收标准

1. WHEN 用户选择一个因子指标时，THE Factor_Editor SHALL 在因子行中显示该因子的阈值类型标签（如"百分位"、"行业相对"、"绝对值"、"布尔"）
2. WHEN 用户选择一个因子指标时，THE Factor_Editor SHALL 在阈值输入框旁显示该因子的单位和取值范围提示
3. WHEN 用户将鼠标悬停在因子名称上时，THE Factor_Editor SHALL 显示工具提示（tooltip），包含因子的说明文本和配置示例
4. WHEN 因子的阈值类型为 boolean 时，THE Factor_Editor SHALL 将阈值输入框替换为开关控件（toggle），隐藏运算符选择器
5. WHEN 因子的阈值类型为 range 时，THE Factor_Editor SHALL 将单一阈值输入框替换为双输入框（下限和上限），运算符自动设为"BETWEEN"
6. THE Factor_Editor SHALL 为每个因子提供"恢复默认"按钮，点击后将阈值重置为 FACTOR_REGISTRY 中定义的默认值

### 需求 8：前端板块面数据源选择器

**用户故事：** 作为量化交易员，我需要在因子条件编辑器中选择板块数据来源和板块分类标准，以便灵活配置板块筛选条件。

#### 验收标准

1. WHEN 用户添加板块面因子条件时，THE Factor_Editor SHALL 显示数据来源下拉选择器，选项包括：东方财富（DC）、同花顺（TI）、通达信（TDX）
2. WHEN 用户添加板块面因子条件时，THE Factor_Editor SHALL 显示板块类型下拉选择器，选项包括：行业板块（INDUSTRY）、概念板块（CONCEPT）、地区板块（REGION）、风格板块（STYLE）
3. WHEN 用户添加板块面因子条件时，THE Factor_Editor SHALL 显示涨幅计算周期输入框，默认值为 5 天，取值范围 1-60 天
4. THE Factor_Editor SHALL 将板块面因子的数据来源、板块类型和涨幅计算周期参数保存到 StrategyConfig 的板块筛选配置字段中
5. WHEN 加载已保存的策略模板时，THE Factor_Editor SHALL 正确回显板块面因子的数据来源、板块类型和涨幅计算周期配置

### 需求 9：百分位排名计算服务

**用户故事：** 作为量化交易员，我需要系统能够计算全市场股票各因子的百分位排名，以便支持 percentile 类型阈值的因子评估。

#### 验收标准

1. THE ScreenDataProvider SHALL 在加载选股数据时，对所有 percentile 类型因子计算全市场百分位排名值（0-100）
2. WHEN 计算百分位排名时，THE ScreenDataProvider SHALL 排除因子值为 None 的股票，仅对有效值进行排名
3. WHEN 计算百分位排名时，THE ScreenDataProvider SHALL 使用升序百分位公式：percentile = (排名位置 / 有效股票总数) × 100，其中排名位置从 1 开始
4. THE ScreenDataProvider SHALL 将计算得到的百分位排名值写入因子字典，使用原因子名称加 `_pctl` 后缀（如 `money_flow_pctl`、`market_cap_pctl`）
5. WHEN FactorEvaluator 评估 percentile 类型因子时，THE FactorEvaluator SHALL 自动读取对应的 `_pctl` 后缀字段值进行比较，而非原始绝对值
6. FOR ALL 有效股票的百分位排名值，THE ScreenDataProvider SHALL 保证排名值在 [0, 100] 闭区间内

### 需求 10：行业相对值计算服务

**用户故事：** 作为量化交易员，我需要系统能够计算基本面因子的行业相对值，以便支持 industry_relative 类型阈值的因子评估。

#### 验收标准

1. THE ScreenDataProvider SHALL 在加载选股数据时，对所有 industry_relative 类型因子计算行业相对值
2. WHEN 计算行业相对值时，THE ScreenDataProvider SHALL 使用 SectorConstituent 表查询每只股票所属的行业板块（sector_type = INDUSTRY），确定行业分组
3. WHEN 计算行业相对值时，THE ScreenDataProvider SHALL 计算每个行业内所有有效股票该因子的中位数，将（个股因子值 / 行业中位数）作为行业相对值
4. THE ScreenDataProvider SHALL 将计算得到的行业相对值写入因子字典，使用原因子名称加 `_ind_rel` 后缀（如 `pe_ind_rel`、`pb_ind_rel`）
5. WHEN FactorEvaluator 评估 industry_relative 类型因子时，THE FactorEvaluator SHALL 自动读取对应的 `_ind_rel` 后缀字段值进行比较
6. IF 某只股票未找到所属行业板块或行业中位数为零，THEN THE ScreenDataProvider SHALL 将该股票的行业相对值设为 None，FactorEvaluator 将该因子视为不通过

### 需求 11：因子元数据 API 端点

**用户故事：** 作为量化交易员，我需要通过 API 获取因子元数据注册表信息，以便前端因子条件编辑器动态加载因子定义。

#### 验收标准

1. THE Screen_API SHALL 提供 GET /api/v1/screen/factor-registry 端点，返回完整的因子元数据注册表
2. THE GET /api/v1/screen/factor-registry 端点 SHALL 返回按类别（technical、money_flow、fundamental、sector）分组的因子元数据列表
3. THE 端点返回的每个因子元数据 SHALL 包含：factor_name、label、category、threshold_type、default_threshold、value_min、value_max、unit、description、examples 字段
4. THE GET /api/v1/screen/factor-registry 端点 SHALL 支持可选的 category 查询参数，用于筛选特定类别的因子

### 需求 12：FactorEvaluator 阈值类型适配

**用户故事：** 作为量化交易员，我需要因子评估器能够根据因子的阈值类型自动选择正确的比较字段，以便 percentile 和 industry_relative 类型的因子条件能够正确评估。

#### 验收标准

1. WHEN 评估一个因子条件时，THE FactorEvaluator SHALL 查询 FACTOR_REGISTRY 获取该因子的阈值类型
2. WHEN 因子的阈值类型为 percentile 时，THE FactorEvaluator SHALL 从 stock_data 中读取 `{factor_name}_pctl` 字段值进行比较
3. WHEN 因子的阈值类型为 industry_relative 时，THE FactorEvaluator SHALL 从 stock_data 中读取 `{factor_name}_ind_rel` 字段值进行比较
4. WHEN 因子的阈值类型为 absolute 或 boolean 时，THE FactorEvaluator SHALL 保持现有行为，直接读取 `{factor_name}` 字段值进行比较
5. WHEN 因子的阈值类型为 range 时，THE FactorEvaluator SHALL 检查因子值是否在 [threshold_low, threshold_high] 区间内，FactorCondition 的 params 字段存储 threshold_low 和 threshold_high
6. IF 因子的阈值类型对应的字段（如 `_pctl` 或 `_ind_rel`）在 stock_data 中不存在或为 None，THEN THE FactorEvaluator SHALL 将该因子评估结果设为不通过

### 需求 13：向后兼容性保障

**用户故事：** 作为量化交易员，我需要已保存的策略模板在因子优化后仍能正常运行，以便不丢失已有的策略配置。

#### 验收标准

1. WHEN 加载不包含 threshold_type 信息的旧版 FactorCondition 时，THE FactorEvaluator SHALL 回退到 absolute 阈值类型，使用原始因子值进行比较
2. WHEN 加载不包含板块筛选配置字段的旧版 StrategyConfig 时，THE StrategyConfig SHALL 使用默认值（sector_data_source=DC, sector_type=CONCEPT, sector_period=5, sector_top_n=30）
3. THE StrategyConfig.from_dict 方法 SHALL 正确反序列化包含新字段的配置，同时兼容不包含新字段的旧配置
4. THE StrategyConfig.to_dict 方法 SHALL 将新增的板块筛选配置字段序列化到输出字典中

### 需求 14：实战选股策略示例库

**用户故事：** 作为量化交易员，我需要系统内置至少 10 个以技术面指标、板块面指标或两者组合为主的可实战选股策略示例，以便快速加载经过验证的策略模板进行实盘选股。

#### 验收标准

1. THE Factor_Editor SHALL 内置一个策略示例库（STRATEGY_EXAMPLES），包含至少 12 个可直接加载为 StrategyConfig 的实战选股策略
2. WHEN 用户在因子条件编辑器中点击"加载示例策略"时，THE Factor_Editor SHALL 展示策略示例列表，每个示例包含策略名称、适用场景说明和涉及的因子类别标签
3. WHEN 用户选择一个策略示例时，THE Factor_Editor SHALL 将该示例的完整 StrategyConfig（包括 factors、logic、weights、enabled_modules 和板块筛选配置）加载到编辑器中
4. THE STRATEGY_EXAMPLES SHALL 包含以下策略示例：

**示例 1：强势多头趋势追踪**
- 适用场景：捕捉处于强势上升趋势中的个股，适合趋势跟踪型交易
- factors:
  - ma_trend, operator: ">=", threshold: 85
  - ma_support, operator: "==", threshold: null（boolean true）
  - dma, operator: "==", threshold: null（boolean true）
- logic: "AND"
- weights: {"ma_trend": 0.5, "ma_support": 0.3, "dma": 0.2}
- enabled_modules: ["ma_trend"]

**示例 2：MACD 金叉放量突破**
- 适用场景：MACD 金叉配合成交量放大，确认短期多头启动信号
- factors:
  - macd, operator: "==", threshold: null（boolean true）
  - turnover, operator: "BETWEEN", params: {"threshold_low": 5.0, "threshold_high": 15.0}
  - volume_price, operator: ">=", threshold: 80（percentile 前 20%）
- logic: "AND"
- weights: {"macd": 0.4, "turnover": 0.3, "volume_price": 0.3}
- enabled_modules: ["indicator_params", "volume_price"]

**示例 3：概念板块热点龙头**
- 适用场景：追踪概念板块轮动热点，筛选强势概念板块中的龙头股
- factors:
  - sector_rank, operator: "<=", threshold: 15
  - sector_trend, operator: "==", threshold: null（boolean true）
  - ma_trend, operator: ">=", threshold: 70
- logic: "AND"
- weights: {"sector_rank": 0.4, "sector_trend": 0.3, "ma_trend": 0.3}
- enabled_modules: ["ma_trend"]
- sector_data_source: "DC", sector_type: "CONCEPT", sector_period: 3, sector_top_n: 15

**示例 4：行业板块轮动策略**
- 适用场景：跟踪行业板块轮动节奏，在强势行业中选择技术面共振的个股
- factors:
  - sector_rank, operator: "<=", threshold: 20
  - sector_trend, operator: "==", threshold: null（boolean true）
  - macd, operator: "==", threshold: null（boolean true）
  - rsi, operator: "BETWEEN", params: {"threshold_low": 55, "threshold_high": 75}
- logic: "AND"
- weights: {"sector_rank": 0.3, "sector_trend": 0.2, "macd": 0.3, "rsi": 0.2}
- enabled_modules: ["indicator_params"]
- sector_data_source: "TI", sector_type: "INDUSTRY", sector_period: 5, sector_top_n: 20

**示例 5：形态突破放量买入**
- 适用场景：捕捉箱体突破或前高突破的个股，要求量价配合确认突破有效性
- factors:
  - breakout, operator: "==", threshold: null（boolean true）
  - turnover, operator: "BETWEEN", params: {"threshold_low": 5.0, "threshold_high": 20.0}
  - large_order, operator: ">=", threshold: 35
  - ma_trend, operator: ">=", threshold: 60
- logic: "AND"
- weights: {"breakout": 0.35, "turnover": 0.2, "large_order": 0.25, "ma_trend": 0.2}
- enabled_modules: ["breakout", "ma_trend", "volume_price"]

**示例 6：技术指标多重共振**
- 适用场景：多个技术指标同时发出多头信号，形成共振确认，提高信号可靠性
- factors:
  - macd, operator: "==", threshold: null（boolean true）
  - boll, operator: "==", threshold: null（boolean true）
  - rsi, operator: "BETWEEN", params: {"threshold_low": 50, "threshold_high": 80}
  - dma, operator: "==", threshold: null（boolean true）
  - ma_trend, operator: ">=", threshold: 75
- logic: "AND"
- weights: {"macd": 0.25, "boll": 0.2, "rsi": 0.2, "dma": 0.15, "ma_trend": 0.2}
- enabled_modules: ["indicator_params", "ma_trend"]

**示例 7：均线支撑反弹策略**
- 适用场景：在上升趋势中回调至均线支撑位企稳反弹的买入机会
- factors:
  - ma_support, operator: "==", threshold: null（boolean true）
  - ma_trend, operator: ">=", threshold: 65
  - rsi, operator: "BETWEEN", params: {"threshold_low": 40, "threshold_high": 60}
  - turnover, operator: "BETWEEN", params: {"threshold_low": 3.0, "threshold_high": 10.0}
- logic: "AND"
- weights: {"ma_support": 0.35, "ma_trend": 0.3, "rsi": 0.2, "turnover": 0.15}
- enabled_modules: ["ma_trend", "indicator_params", "volume_price"]

**示例 8：板块强势 + 布林突破**
- 适用场景：在强势板块中寻找布林带突破的个股，板块动量与个股技术面双重确认
- factors:
  - sector_rank, operator: "<=", threshold: 25
  - boll, operator: "==", threshold: null（boolean true）
  - ma_trend, operator: ">=", threshold: 70
  - volume_price, operator: ">=", threshold: 70（percentile 前 30%）
- logic: "AND"
- weights: {"sector_rank": 0.3, "boll": 0.3, "ma_trend": 0.2, "volume_price": 0.2}
- enabled_modules: ["indicator_params", "ma_trend", "volume_price"]
- sector_data_source: "DC", sector_type: "CONCEPT", sector_period: 5, sector_top_n: 25

**示例 9：主力资金驱动策略**
- 适用场景：筛选主力资金持续流入且技术面配合的个股，适合中短线波段操作
- factors:
  - money_flow, operator: ">=", threshold: 85（percentile 前 15%）
  - large_order, operator: ">=", threshold: 30
  - macd, operator: "==", threshold: null（boolean true）
  - ma_trend, operator: ">=", threshold: 70
- logic: "AND"
- weights: {"money_flow": 0.3, "large_order": 0.25, "macd": 0.25, "ma_trend": 0.2}
- enabled_modules: ["indicator_params", "ma_trend", "volume_price"]

**示例 10：概念板块 + 形态突破联动**
- 适用场景：在热门概念板块中寻找形态突破的个股，板块热度与技术突破共振
- factors:
  - sector_rank, operator: "<=", threshold: 10
  - sector_trend, operator: "==", threshold: null（boolean true）
  - breakout, operator: "==", threshold: null（boolean true）
  - turnover, operator: "BETWEEN", params: {"threshold_low": 5.0, "threshold_high": 20.0}
- logic: "AND"
- weights: {"sector_rank": 0.3, "sector_trend": 0.2, "breakout": 0.3, "turnover": 0.2}
- enabled_modules: ["breakout", "volume_price"]
- sector_data_source: "DC", sector_type: "CONCEPT", sector_period: 3, sector_top_n: 10

**示例 11：多数据源板块交叉验证**
- 适用场景：使用通达信行业数据与东方财富概念数据交叉验证，筛选同时处于强势行业和热门概念的个股
- factors:
  - sector_rank, operator: "<=", threshold: 30, params: {"sector_data_source": "TDX", "sector_type": "INDUSTRY", "sector_period": 5}
  - sector_rank, operator: "<=", threshold: 20, params: {"sector_data_source": "DC", "sector_type": "CONCEPT", "sector_period": 3}
  - ma_trend, operator: ">=", threshold: 70
- logic: "AND"
- weights: {"sector_rank": 0.6, "ma_trend": 0.4}
- enabled_modules: ["ma_trend"]
- 说明：该策略使用两组不同数据源的 sector_rank 条件，第一组基于通达信行业板块 5 日涨幅排名，第二组基于东方财富概念板块 3 日涨幅排名

**示例 12：RSI 超卖反弹 + 板块支撑**
- 适用场景：在强势板块中寻找 RSI 短期超卖后反弹的个股，逆向买入但有板块趋势保护
- factors:
  - rsi, operator: "BETWEEN", params: {"threshold_low": 30, "threshold_high": 50}
  - sector_trend, operator: "==", threshold: null（boolean true）
  - sector_rank, operator: "<=", threshold: 30
  - ma_trend, operator: ">=", threshold: 55
- logic: "AND"
- weights: {"rsi": 0.3, "sector_trend": 0.25, "sector_rank": 0.25, "ma_trend": 0.2}
- enabled_modules: ["indicator_params", "ma_trend"]
- sector_data_source: "TI", sector_type: "INDUSTRY", sector_period: 5, sector_top_n: 30

5. THE STRATEGY_EXAMPLES 中每个策略示例 SHALL 包含以下字段：策略名称（name）、适用场景说明（description）、因子条件列表（factors）、逻辑运算（logic）、因子权重（weights）、启用模块列表（enabled_modules），板块面策略额外包含板块筛选配置（sector_data_source、sector_type、sector_period、sector_top_n）
6. THE STRATEGY_EXAMPLES SHALL 作为后端 Python 模块中的常量列表定义，并通过 GET /api/v1/screen/strategy-examples 端点暴露给前端
7. WHEN 用户加载一个策略示例时，THE Factor_Editor SHALL 自动启用该示例所需的模块（enabled_modules），并填充所有因子条件、权重和板块筛选配置
8. THE STRATEGY_EXAMPLES 中的所有因子条件 SHALL 使用 FACTOR_REGISTRY 中定义的阈值类型和取值范围，确保示例配置与因子元数据一致
