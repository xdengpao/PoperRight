# 技术设计文档：回测自定义平仓条件

## 概述

本功能在现有回测引擎中新增自定义平仓条件支持。用户可配置基于技术指标（MA、MACD、BOLL、RSI、DMA、量价等）的平仓规则，支持日K线和多种分钟K线（1分钟、5分钟、15分钟、30分钟、60分钟）数据源，这些规则与现有风控止损止盈条件并行生效。此外，用户可将配置好的平仓条件保存为命名模版，在后续回测中直接加载复用。

核心变更范围：
- 新增 `ExitCondition` / `ExitConditionConfig` 数据模型（`app/core/schemas.py`）
- 新增 `VALID_FREQS` 常量定义合法频率集合：`{"daily", "1min", "5min", "15min", "30min", "60min"}`
- 新增 `ExitConditionEvaluator` 评估引擎（`app/services/exit_condition_evaluator.py`），按频率分别加载对应K线数据
- 扩展 `BacktestEngine._check_sell_conditions` 集成自定义平仓条件
- 扩展 `IndicatorCache` 支持按频率分组的自定义参数指标缓存
- 扩展回测 API 和前端配置面板（频率下拉框支持6种选项）
- 向后兼容：旧版 `"minute"` 频率值自动映射为 `"1min"`
- 新增 `ExitConditionTemplate` ORM 模型（`app/models/backtest.py`），支持平仓条件模版持久化，含 `is_system` 字段区分系统内置与用户自定义模版
- 新增模版 CRUD REST API 端点（`app/api/v1/backtest.py`），含名称唯一性校验、数量上限和系统模版保护
- 新增 5 个系统内置平仓条件模版（RSI 超买、MACD 死叉、布林带上轨回落、均线空头排列、量价背离）
- 新增前端指标使用说明数据（`INDICATOR_DESCRIPTIONS`），覆盖全部 13 个指标的中文名称、计算逻辑、参数说明和典型场景
- 扩展前端 Pinia store 和 `BacktestView.vue`，支持模版保存、加载、管理、指标说明展示
- 回测引擎使用前复权K线数据计算自定义平仓条件指标，与选股引擎（ScreenDataProvider）保持一致

设计原则：
1. 最小侵入：不修改现有风控逻辑，仅在卖出条件检测链末尾追加
2. 复用优先：复用现有 `IndicatorCache` 和指标计算函数；模版 ORM 遵循 `StrategyTemplate` 设计模式；前复权计算复用 `ForwardAdjustmentCalculator`
3. 向后兼容：未配置自定义条件时行为与现有完全一致；旧版 `"minute"` 配置自动迁移
4. 数据一致性：自定义平仓条件的指标计算与选股引擎使用相同的前复权K线数据和计算函数

## 架构

### 整体流程

```mermaid
flowchart TD
    A[回测主循环 - 每个交易日] --> B[解冻资金 / 处理待卖]
    B --> C[现有卖出条件检测]
    C --> D{风控已触发?}
    D -->|是| E[跳过自定义条件]
    D -->|否| F[ExitConditionEvaluator 评估]
    F --> G{条件满足?}
    G -->|是| H[生成 EXIT_CONDITION 卖出信号 priority=5]
    G -->|否| I[保持持仓]
    E --> J[执行卖出]
    H --> J
    I --> K[评估大盘风控 → 生成买入信号 → 执行买入]
    J --> K
```

### 模块依赖

```mermaid
graph LR
    API[backtest API] --> Config[BacktestConfig]
    Config --> Engine[BacktestEngine]
    Engine --> Evaluator[ExitConditionEvaluator]
    Evaluator --> Cache[IndicatorCache]
    Evaluator --> Indicators[indicators.py / ma_trend.py]
    Engine --> FAC[ForwardAdjustmentCalculator]
    Frontend[BacktestView.vue] --> API
    Frontend --> TemplateAPI[exit-templates API]
    Frontend --> DescRegistry[INDICATOR_DESCRIPTIONS]
    TemplateAPI --> TemplateModel[ExitConditionTemplate ORM]
    TemplateModel --> PG[(PostgreSQL)]
    TemplateAPI --> SystemTemplates[系统内置模版]
```

### 模版管理流程

```mermaid
flowchart TD
    A[用户配置平仓条件] --> B{保存为模版?}
    B -->|是| C[弹出名称/描述对话框]
    C --> D[POST /exit-templates]
    D --> E{名称重复?}
    E -->|是| F[返回 409，提示重复]
    E -->|否| G{数量超限?}
    G -->|是| H[返回 409，提示超限]
    G -->|否| I[保存成功，刷新列表]
    B -->|否| J[直接提交回测]
    K[用户选择已有模版] --> L[GET /exit-templates/id]
    L --> M[替换当前平仓条件配置]
    M --> J
```

## 组件与接口

### 1. ExitConditionEvaluator（新增）

文件：`app/services/exit_condition_evaluator.py`

职责：
- 接收 `ExitConditionConfig` 和指标缓存，对单只持仓评估所有自定义平仓条件
- 根据每条条件的 `freq` 字段选择对应频率的K线指标缓存进行评估
- 支持数值比较（`>`, `<`, `>=`, `<=`）和交叉检测（`cross_up`, `cross_down`）
- 支持 AND / OR 逻辑组合
- 向后兼容：`freq="minute"` 自动视为 `"1min"`

```python
# 合法频率常量
VALID_FREQS = {"daily", "1min", "5min", "15min", "30min", "60min"}

# 旧版频率映射
_FREQ_MIGRATION = {"minute": "1min"}

class ExitConditionEvaluator:
    """自定义平仓条件评估器"""

    def evaluate(
        self,
        config: ExitConditionConfig,
        symbol: str,
        bar_index: int,
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, dict[str, list[float]]] | None = None,
    ) -> tuple[bool, str | None]:
        """
        评估单只持仓的自定义平仓条件。

        Args:
            config: 平仓条件配置
            symbol: 股票代码
            bar_index: 当前交易日在 K 线序列中的索引
            indicator_cache: 日K线预计算指标缓存
            exit_indicator_cache: 按频率分组的补充缓存
                格式: {freq: {cache_key: values}}
                例: {"daily": {"ma_10": [...]}, "5min": {"rsi_14": [...]}}

        Returns:
            (triggered, reason) - triggered 为 True 时 reason 包含触发条件描述
        """

    def _resolve_freq(self, freq: str) -> str:
        """将旧版频率值映射为新版，如 'minute' → '1min'"""

    def _evaluate_single(
        self,
        condition: ExitCondition,
        bar_index: int,
        indicator_cache: IndicatorCache,
        freq_indicator_cache: dict[str, list[float]] | None,
    ) -> bool:
        """评估单条平仓条件，使用对应频率的指标缓存"""

    def _get_indicator_value(
        self,
        indicator_name: str,
        bar_index: int,
        indicator_cache: IndicatorCache,
        freq_indicator_cache: dict[str, list[float]] | None,
        params: dict | None = None,
    ) -> float | None:
        """从缓存获取指标值，支持自定义参数"""

    def _check_cross(
        self,
        indicator_name: str,
        cross_target: str,
        bar_index: int,
        indicator_cache: IndicatorCache,
        freq_indicator_cache: dict[str, list[float]] | None,
        direction: str,  # "up" or "down"
        params: dict | None = None,
    ) -> bool:
        """检测交叉信号"""
```

评估流程中的频率处理：
1. 对每条条件，先调用 `_resolve_freq()` 将 `freq` 标准化（处理 `"minute"` → `"1min"` 映射）
2. 根据标准化后的 `freq` 从 `exit_indicator_cache[freq]` 获取对应频率的指标缓存
3. 若对应频率的分钟K线缓存不可用，回退到 `"daily"` 频率的缓存，记录 INFO 日志

### 2. BacktestEngine 扩展

在 `_check_sell_conditions` 方法末尾追加自定义条件评估：

```python
# 现有 _check_sell_conditions 末尾追加：
# 5. 自定义平仓条件（优先级 5，最低）
if config.exit_conditions is not None:
    evaluator = ExitConditionEvaluator()
    triggered, reason = evaluator.evaluate(
        config.exit_conditions, position.symbol, bar_index,
        indicator_cache, exit_indicator_cache,
    )
    if triggered:
        return _SellSignal(
            symbol=position.symbol,
            reason="EXIT_CONDITION",
            trigger_date=trade_date,
            priority=5,
        )
```

交易记录序列化扩展 — 在 `_TradeRecord` 中新增 `sell_reason` 字段：

```python
@dataclass
class _TradeRecord:
    date: date
    symbol: str
    action: str
    price: Decimal
    quantity: int
    cost: Decimal
    amount: Decimal
    sell_reason: str = ""  # 新增：卖出原因
```

### 3. IndicatorCache 扩展

在预计算阶段，检查 `ExitConditionConfig` 中引用的指标参数组合和频率类型，按频率分组补充计算：

```python
def _precompute_exit_indicators(
    kline_data: dict[str, dict[str, list[KlineBar]]],
    exit_config: ExitConditionConfig | None,
    existing_cache: dict[str, IndicatorCache],
) -> dict[str, dict[str, dict[str, list[float]]]]:
    """
    为自定义平仓条件补充计算非默认参数的指标，按频率分组。

    Args:
        kline_data: 按频率和股票代码组织的K线数据
            格式: {freq: {symbol: [KlineBar, ...]}}
            例: {"daily": {"600519.SH": [...]}, "5min": {"600519.SH": [...]}}
        exit_config: 平仓条件配置
        existing_cache: 现有日K线指标缓存

    Returns:
        {symbol: {freq: {cache_key: values}}} 格式的按频率分组补充缓存。
        cache_key 格式如 "ma_10", "rsi_7", "macd_dif_8_21_5" 等。
    """
```

预计算流程：
1. 遍历 `exit_config.conditions`，收集所有引用的 `(freq, indicator, params)` 组合
2. 将 `freq="minute"` 映射为 `"1min"`（向后兼容）
3. 对每个频率，加载对应的K线数据并计算所需指标
4. 日K线频率（`"daily"`）的指标优先从 `existing_cache` 复用
5. 分钟K线频率的指标需独立计算，每种分钟类型使用各自的K线数据

指标值获取的映射关系：

| 指标名称 | IndicatorCache 字段 | 备注 |
|---------|-------------------|------|
| `close` | `closes[i]` | 直接读取 |
| `volume` | `volumes[i]` | 直接读取 |
| `turnover` | `turnovers[i]` | 直接读取 |
| `ma` | 需按周期从 `exit_indicator_cache` 查找 | 支持自定义周期 |
| `macd_dif` | 从 MACD 计算结果的 `dif[i]` | 支持自定义参数 |
| `macd_dea` | 从 MACD 计算结果的 `dea[i]` | 支持自定义参数 |
| `macd_histogram` | 从 MACD 计算结果的 `macd[i]` | 支持自定义参数 |
| `boll_upper` | 从 BOLL 计算结果的 `upper[i]` | 支持自定义参数 |
| `boll_middle` | 从 BOLL 计算结果的 `middle[i]` | 支持自定义参数 |
| `boll_lower` | 从 BOLL 计算结果的 `lower[i]` | 支持自定义参数 |
| `rsi` | 从 RSI 计算结果的 `values[i]` | 支持自定义周期 |
| `dma` | 从 DMA 计算结果的 `dma[i]` | 支持自定义参数 |
| `ama` | 从 DMA 计算结果的 `ama[i]` | 支持自定义参数 |

## 数据模型

### ExitConditionTemplate（新增，`app/models/backtest.py`）

遵循现有 `StrategyTemplate`（`app/models/strategy.py`）的设计模式：UUID 主键、JSONB 配置字段、时间戳字段、`PGBase` 基类。

```python
class ExitConditionTemplate(PGBase):
    """平仓条件模版"""

    __tablename__ = "exit_condition_template"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exit_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)  # ExitConditionConfig.to_dict()
    is_system: Mapped[bool] = mapped_column(
        Boolean, server_default=sa_text("false"), nullable=False
    )  # 新增：标识系统内置模版
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=sa_text("NOW()"), nullable=False
    )
```

`exit_conditions` 字段存储 `ExitConditionConfig.to_dict()` 的序列化结果，加载时通过 `ExitConditionConfig.from_dict()` 反序列化。与 `StrategyTemplate.config` 存储 `StrategyConfig` 的模式一致。

### 数据库迁移（Alembic）

新增迁移文件 `alembic/versions/004_create_exit_condition_template.py`：

```sql
CREATE TABLE IF NOT EXISTS exit_condition_template (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            VARCHAR(100) NOT NULL,
    description     VARCHAR(500),
    exit_conditions JSONB NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_exit_condition_template_user_id
    ON exit_condition_template (user_id);

CREATE UNIQUE INDEX idx_exit_condition_template_user_name
    ON exit_condition_template (user_id, name)
    WHERE is_system = FALSE;

CREATE UNIQUE INDEX idx_exit_condition_template_system_name
    ON exit_condition_template (name)
    WHERE is_system = TRUE;
```

- `idx_exit_condition_template_user_id`：按用户查询模版列表
- `idx_exit_condition_template_user_name`：保证同一用户下**用户自定义**模版名称唯一（部分唯一索引，排除系统模版）
- `idx_exit_condition_template_system_name`：保证系统内置模版名称全局唯一

### ExitCondition（新增，`app/core/schemas.py`）

```python
VALID_FREQS = {"daily", "1min", "5min", "15min", "30min", "60min"}

@dataclass
class ExitCondition:
    """单条自定义平仓条件"""
    freq: str                          # 数据源频率："daily" | "1min" | "5min" | "15min" | "30min" | "60min"
    indicator: str                     # 指标名称
    operator: str                      # 比较运算符
    threshold: float | None = None     # 数值阈值（数值比较时使用）
    cross_target: str | None = None    # 交叉目标指标（cross_up/cross_down 时使用）
    params: dict = field(default_factory=dict)  # 指标参数（如 {"period": 10}）

    def to_dict(self) -> dict:
        return {
            "freq": self.freq,
            "indicator": self.indicator,
            "operator": self.operator,
            "threshold": self.threshold,
            "cross_target": self.cross_target,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExitCondition":
        freq = data["freq"]
        # 向后兼容：旧版 "minute" 映射为 "1min"
        if freq == "minute":
            freq = "1min"
        return cls(
            freq=freq,
            indicator=data["indicator"],
            operator=data["operator"],
            threshold=data.get("threshold"),
            cross_target=data.get("cross_target"),
            params=data.get("params", {}),
        )
```

支持的指标名称（`VALID_INDICATORS`）：
`"ma"`, `"macd_dif"`, `"macd_dea"`, `"macd_histogram"`, `"boll_upper"`, `"boll_middle"`, `"boll_lower"`, `"rsi"`, `"dma"`, `"ama"`, `"close"`, `"volume"`, `"turnover"`

支持的运算符（`VALID_OPERATORS`）：
`">"`, `"<"`, `">="`, `"<="`, `"cross_up"`, `"cross_down"`

### ExitConditionConfig（新增，`app/core/schemas.py`）

```python
@dataclass
class ExitConditionConfig:
    """自定义平仓条件配置"""
    conditions: list[ExitCondition] = field(default_factory=list)
    logic: str = "AND"  # "AND" | "OR"

    def to_dict(self) -> dict:
        return {
            "conditions": [c.to_dict() for c in self.conditions],
            "logic": self.logic,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExitConditionConfig":
        conditions = [
            ExitCondition.from_dict(c)
            for c in data.get("conditions", [])
        ]
        return cls(
            conditions=conditions,
            logic=data.get("logic", "AND"),
        )
```

### BacktestConfig 扩展

```python
@dataclass
class BacktestConfig:
    # ... 现有字段 ...
    exit_conditions: ExitConditionConfig | None = None  # 新增
```

### _TradeRecord 扩展

```python
@dataclass
class _TradeRecord:
    # ... 现有字段 ...
    sell_reason: str = ""  # 新增：卖出原因标识
```

### _SellSignal 扩展

新增优先级 5 用于自定义平仓条件：

| 优先级 | 原因 | 描述 |
|-------|------|------|
| 1 | STOP_LOSS | 固定止损 |
| 2 | TREND_BREAK | 趋势破位 |
| 3 | TRAILING_STOP | 移动止盈 |
| 4 | MAX_HOLDING_DAYS | 持仓超期 |
| 5 | EXIT_CONDITION | 自定义平仓条件（新增） |


## 正确性属性

*正确性属性是在系统所有有效执行中都应成立的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范与机器可验证正确性保证之间的桥梁。*

### Property 1: ExitConditionConfig 序列化往返一致性

*对于任意*有效的 `ExitConditionConfig` 对象（包含任意数量的条件、任意合法频率值（`"daily"`, `"1min"`, `"5min"`, `"15min"`, `"30min"`, `"60min"`）、任意合法指标名称、任意合法运算符、任意阈值或交叉目标），调用 `to_dict()` 序列化为字典后再调用 `from_dict()` 反序列化，所得对象应与原对象在所有字段上等价。

**Validates: Requirements 1.1, 1.6, 1.7**

### Property 2: 逻辑运算符评估正确性

*对于任意*逻辑运算符（AND 或 OR）和任意非空布尔值列表（代表各条件的评估结果），`ExitConditionEvaluator` 的逻辑组合结果应满足：当 logic="AND" 时结果等于 `all(results)`，当 logic="OR" 时结果等于 `any(results)`。

**Validates: Requirements 2.2, 2.3**

### Property 3: 数值比较运算符正确性

*对于任意*浮点数 `indicator_value`、任意合法数值比较运算符（`>`, `<`, `>=`, `<=`）和任意浮点数 `threshold`，`ExitConditionEvaluator` 的单条件评估结果应与 Python 原生比较运算的结果一致。

**Validates: Requirements 2.4**

### Property 4: 交叉检测正确性

*对于任意*两组连续两日的浮点数值对 `(prev_indicator, curr_indicator)` 和 `(prev_target, curr_target)`：
- `cross_up` 应在且仅在 `prev_indicator <= prev_target` 且 `curr_indicator > curr_target` 时返回 True
- `cross_down` 应在且仅在 `prev_indicator >= prev_target` 且 `curr_indicator < curr_target` 时返回 True

**Validates: Requirements 2.5, 2.6**

### Property 5: 无自定义条件时向后兼容

*对于任意*有效的 `BacktestConfig`（其中 `exit_conditions` 为 None），回测引擎的卖出条件检测结果应与未引入自定义平仓条件功能前的行为完全一致——即不会产生任何 `EXIT_CONDITION` 类型的卖出信号。

**Validates: Requirements 3.5**

### Property 6: 所有卖出记录包含平仓原因

*对于任意*回测执行产生的交易记录列表，其中所有 `action="SELL"` 的记录都应包含非空的 `sell_reason` 字段，且 `sell_reason` 的值必须属于合法集合 `{"STOP_LOSS", "TREND_BREAK", "TRAILING_STOP", "MAX_HOLDING_DAYS", "EXIT_CONDITION"}`。

**Validates: Requirements 7.1, 7.4**

### Property 7: 旧版 "minute" 频率向后兼容映射

*对于任意*有效的 `ExitCondition` 字典（其中 `freq` 字段值为 `"minute"`），调用 `ExitCondition.from_dict()` 反序列化后所得对象的 `freq` 字段应等于 `"1min"`。进一步地，*对于任意*包含 `freq="minute"` 条件的 `ExitConditionConfig` 字典，`from_dict()` 后再 `to_dict()` 所得字典中对应条件的 `freq` 应为 `"1min"`（即迁移后不可逆）。

**Validates: Requirements 8.1, 8.3**

### Property 8: 模版 exit_conditions 往返一致性

*对于任意*有效的 `ExitConditionConfig` 对象，将其通过 `to_dict()` 序列化后存入 `ExitConditionTemplate` 的 `exit_conditions` JSONB 字段，再从数据库读取该字段并通过 `ExitConditionConfig.from_dict()` 反序列化，所得对象应与原对象在所有字段上等价。

**Validates: Requirements 9.4, 9.9, 9.10**

### Property 9: 同一用户下模版名称唯一性

*对于任意*有效的模版名称字符串（非空，长度 ≤ 100），同一用户创建两个同名模版时，第二次创建请求应返回 HTTP 409 冲突错误，且数据库中该用户下该名称的模版数量始终为 1。

**Validates: Requirements 9.5**

### Property 10: 指标使用说明注册表完整性

*对于任意*合法指标名称（属于 `VALID_INDICATORS` 集合的 13 个指标），`INDICATOR_DESCRIPTIONS` 注册表中应存在对应条目，且该条目包含非空的 `chineseName`（中文名称）、非空的 `calculationSummary`（计算逻辑简述）、非空的 `typicalUsage`（典型使用场景）。对于包含可配置参数的指标（ma、macd_dif、macd_dea、macd_histogram、boll_upper、boll_middle、boll_lower、rsi、dma、ama），`params` 数组应非空，且每个参数条目包含 `name`、`defaultValue` 和 `suggestedRange` 字段。

**Validates: Requirements 11.1, 11.3, 11.4, 11.5**

### Property 11: 系统模版在列表中排序优先

*对于任意*模版列表 API 响应（包含系统模版和用户自定义模版），所有 `is_system=true` 的模版在列表中的索引应小于所有 `is_system=false` 的模版的索引——即系统模版始终排列在用户自定义模版之前。

**Validates: Requirements 12.3**

### Property 12: 前复权指标计算跨模块一致性

*对于任意*有效的前复权收盘价序列，使用相同的指标计算函数（`calculate_ma`、`calculate_macd`、`calculate_rsi`、`calculate_boll`、`calculate_dma`）和相同的参数，无论从回测引擎（`_precompute_exit_indicators`）还是选股引擎（`ScreenDataProvider`）调用，计算结果应完全一致。

**Validates: Requirements 13.3, 13.5**

## 错误处理

### 评估器错误处理

| 场景 | 处理方式 |
|------|---------|
| 指标数据不足（K线数量 < 指标最小周期） | 跳过该条件，记录 WARNING 日志，该条件视为"未满足" |
| 指标值为 NaN | 跳过该条件，视为"未满足" |
| 无效指标名称（运行时） | 跳过该条件，记录 ERROR 日志 |
| 交叉检测缺少前一日数据（bar_index=0） | 跳过该条件，视为"未满足" |
| 分钟K线数据不可用 | 回退到日K线数据，记录 INFO 日志（适用于所有5种分钟K线类型） |

### API 验证错误

| 场景 | HTTP 状态码 | 错误信息 |
|------|-----------|---------|
| 无效指标名称 | 422 | `"无效的指标名称: {name}，支持: ma, macd_dif, ..."` |
| 无效运算符 | 422 | `"无效的比较运算符: {op}，支持: >, <, >=, <=, cross_up, cross_down"` |
| 无效数据源频率 | 422 | `"无效的数据源频率: {freq}，支持: daily, 1min, 5min, 15min, 30min, 60min"` |
| cross_up/cross_down 缺少 cross_target | 422 | `"交叉运算符需要指定 cross_target"` |
| 数值运算符缺少 threshold | 422 | `"数值比较运算符需要指定 threshold"` |
| 无效逻辑运算符 | 422 | `"无效的逻辑运算符: {logic}，支持: AND, OR"` |

### 回测引擎错误处理

- `ExitConditionEvaluator` 内部异常不应中断回测主循环
- 捕获异常后记录 ERROR 日志，跳过该持仓的自定义条件评估
- 确保回测结果的完整性不受单条件评估失败影响

### 模版 API 错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|-----------|---------|
| 模版名称与该用户已有模版重复 | 409 | `"模版名称已存在: {name}"` |
| 用户模版数量已达上限（50 个） | 409 | `"模版数量已达上限（50个），请删除不需要的模版后重试"` |
| 更新/删除非本人模版 | 403 | `"无权操作该模版"` |
| 更新系统内置模版 | 403 | `"系统内置模版不可修改"` |
| 删除系统内置模版 | 403 | `"系统内置模版不可删除"` |
| 请求的模版 ID 不存在 | 404 | `"模版不存在"` |
| exit_conditions 字段包含无效数据 | 422 | 复用 `ExitConditionsSchema` 的验证错误信息 |
| 模版名称为空或超过 100 字符 | 422 | `"模版名称不能为空且长度不超过100字符"` |

## 测试策略

### 单元测试

1. `ExitCondition` / `ExitConditionConfig` 数据模型
   - 构造、字段验证、默认值
   - 各种指标和运算符组合的实例化

2. `ExitConditionEvaluator`
   - 各运算符的具体评估场景（RSI > 80、MACD_DIF cross_down MACD_DEA 等）
   - AND/OR 逻辑组合的具体场景
   - 边界条件：空条件列表、单条件、数据不足
   - 错误处理：无效指标、NaN 值

3. `BacktestEngine` 集成
   - 自定义条件在风控之后执行
   - 风控已触发时跳过自定义条件
   - 卖出记录包含正确的 sell_reason
   - 无自定义条件时行为不变

4. API 层
   - 请求验证（有效/无效的 exit_conditions）
   - 参数传递到 BacktestConfig

5. 模版 CRUD API
   - 创建模版：有效数据、名称重复（409）、数量超限（409）、无效 exit_conditions（422）
   - 列出模版：返回系统模版 + 当前用户所有模版，系统模版排在前面
   - 获取模版：存在的 ID、不存在的 ID（404）
   - 更新模版：本人模版、非本人模版（403）、不存在的 ID（404）、系统模版（403）
   - 删除模版：本人模版、非本人模版（403）、系统模版（403）

6. 系统内置模版
   - 数据库中存在至少 5 个 `is_system=True` 的模版
   - 5 个模版的名称和 exit_conditions 配置正确
   - 系统模版的 exit_conditions 可通过 `ExitConditionConfig.from_dict()` 正确反序列化
   - PUT/DELETE 系统模版返回 403
   - 列表 API 中系统模版排在用户模版之前

7. 前端组件
   - 条件面板的展开/折叠
   - 添加/删除条件行
   - 运算符切换时输入框变化
   - 表单序列化
   - 选择指标后展示使用说明卡片
   - 使用说明包含中文名称、计算逻辑、参数说明、典型场景

8. 前端模版管理
   - "保存为模版"按钮状态（有条件时启用，无条件时禁用）
   - 保存对话框弹出与提交
   - 模版选择下拉框加载与选择（系统模版带"系统"标签，排在前面）
   - 模版加载后替换当前配置
   - 系统模版不显示重命名和删除操作
   - 模版重命名和删除（仅用户自定义模版）

9. 前复权K线数据集成
   - 回测引擎接收的日K线数据已经过前复权处理
   - `_precompute_exit_indicators` 使用前复权后的 closes 计算指标
   - `ExitConditionEvaluator` 获取的 close 值为前复权收盘价
   - 无复权因子时使用原始K线数据并记录警告日志
   - 分钟K线数据同样应用前复权处理

### 属性测试（Hypothesis）

后端使用 Hypothesis 库，每个属性测试最少运行 100 次迭代。

- Property 1: `ExitConditionConfig` 序列化往返（freq 从 VALID_FREQS 6种值中生成）
  - Tag: `Feature: backtest-exit-conditions, Property 1: ExitConditionConfig round-trip serialization`
- Property 2: 逻辑运算符正确性
  - Tag: `Feature: backtest-exit-conditions, Property 2: Logic operator evaluation correctness`
- Property 3: 数值比较运算符正确性
  - Tag: `Feature: backtest-exit-conditions, Property 3: Numeric comparison operator correctness`
- Property 4: 交叉检测正确性
  - Tag: `Feature: backtest-exit-conditions, Property 4: Cross detection correctness`
- Property 5: 无自定义条件时向后兼容
  - Tag: `Feature: backtest-exit-conditions, Property 5: Backward compatibility without exit conditions`
- Property 6: 所有卖出记录包含平仓原因
  - Tag: `Feature: backtest-exit-conditions, Property 6: All sell records contain sell_reason`
- Property 7: 旧版 "minute" 频率向后兼容映射
  - Tag: `Feature: backtest-exit-conditions, Property 7: Legacy minute freq backward compatibility mapping`
- Property 8: 模版 exit_conditions 往返一致性
  - Tag: `Feature: backtest-exit-conditions, Property 8: Template exit_conditions round-trip consistency`
- Property 9: 同一用户下模版名称唯一性
  - Tag: `Feature: backtest-exit-conditions, Property 9: Template name uniqueness per user`
- Property 10: 指标使用说明注册表完整性
  - Tag: `Feature: backtest-exit-conditions, Property 10: Indicator description registry completeness`
- Property 11: 系统模版在列表中排序优先
  - Tag: `Feature: backtest-exit-conditions, Property 11: System templates ordering priority in list`
- Property 12: 前复权指标计算跨模块一致性
  - Tag: `Feature: backtest-exit-conditions, Property 12: Forward-adjusted indicator calculation cross-module consistency`

### 前端属性测试（fast-check）

- `ExitConditionConfig` JSON 序列化往返（与后端 Property 1 对应）
- 条件表单状态管理的一致性
- 指标使用说明注册表完整性（与后端 Property 10 对应）：对任意合法指标名称，`INDICATOR_DESCRIPTIONS` 包含完整条目

### API 变更

#### `BacktestRunRequest` 扩展

```python
class ExitConditionSchema(BaseModel):
    freq: str = "daily"
    indicator: str
    operator: str
    threshold: float | None = None
    cross_target: str | None = None
    params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_condition(self) -> "ExitConditionSchema":
        # 向后兼容：接受 "minute" 并映射为 "1min"
        if self.freq == "minute":
            self.freq = "1min"
        if self.freq not in VALID_FREQS:
            raise ValueError(
                f"无效的数据源频率: {self.freq}，支持: daily, 1min, 5min, 15min, 30min, 60min"
            )
        if self.indicator not in VALID_INDICATORS:
            raise ValueError(f"无效的指标名称: {self.indicator}")
        if self.operator not in VALID_OPERATORS:
            raise ValueError(f"无效的比较运算符: {self.operator}")
        if self.operator in ("cross_up", "cross_down") and not self.cross_target:
            raise ValueError("交叉运算符需要指定 cross_target")
        if self.operator not in ("cross_up", "cross_down") and self.threshold is None:
            raise ValueError("数值比较运算符需要指定 threshold")
        return self

class ExitConditionsSchema(BaseModel):
    conditions: list[ExitConditionSchema] = Field(default_factory=list)
    logic: str = "AND"

class BacktestRunRequest(BaseModel):
    # ... 现有字段 ...
    exit_conditions: ExitConditionsSchema | None = None  # 新增
```

#### 回测结果交易记录扩展

交易记录 JSON 新增 `sell_reason` 字段：

```json
{
  "date": "2024-01-15",
  "symbol": "600519.SH",
  "action": "SELL",
  "price": 1850.0,
  "quantity": 100,
  "cost": 24.05,
  "amount": 185000.0,
  "sell_reason": "EXIT_CONDITION: RSI > 80"
}
```

### 前端组件设计

#### ExitConditionPanel 组件

在 `BacktestView.vue` 的回测参数区域新增可折叠面板：

```
┌─ 自定义平仓条件 ──────────────────────── [▼ 展开/收起] ─┐
│                                                          │
│  条件逻辑: [AND ▼]                                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ [日K   ▼] [RSI ▼] [> ▼] [80        ] [✕ 删除]  │    │
│  │ [5分钟 ▼] [MA  ▼] [< ▼] [close     ] [✕ 删除]  │    │
│  │            周期: [20  ]                           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  [+ 添加条件]                                            │
└──────────────────────────────────────────────────────────┘
```

频率下拉框选项与中文标签映射：

| 值 | 中文标签 |
|----|---------|
| `daily` | 日K |
| `1min` | 1分钟 |
| `5min` | 5分钟 |
| `15min` | 15分钟 |
| `30min` | 30分钟 |
| `60min` | 60分钟 |

状态管理：在 `useBacktestStore` 的 `form` 中新增 `exitConditions` 字段：

```typescript
interface ExitConditionForm {
  freq: 'daily' | '1min' | '5min' | '15min' | '30min' | '60min'
  indicator: string
  operator: string
  threshold: number | null
  crossTarget: string | null
  params: Record<string, number>
}

// 频率选项常量
const FREQ_OPTIONS = [
  { value: 'daily', label: '日K' },
  { value: '1min', label: '1分钟' },
  { value: '5min', label: '5分钟' },
  { value: '15min', label: '15分钟' },
  { value: '30min', label: '30分钟' },
  { value: '60min', label: '60分钟' },
] as const

// form 扩展
const form = ref({
  // ... 现有字段 ...
  exitConditions: {
    conditions: [] as ExitConditionForm[],
    logic: 'AND' as 'AND' | 'OR',
  },
})
```

交易流水表格新增"平仓原因"列，展示 `sell_reason` 字段值。

---

## 模版功能设计（需求 9、10）

### 4. ExitConditionTemplate CRUD API（新增）

文件：`app/api/v1/backtest.py`

在现有回测 API 路由中新增模版管理端点，复用 `ExitConditionsSchema` 进行 exit_conditions 字段验证。

#### Pydantic 请求/响应模型

```python
class ExitTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    exit_conditions: ExitConditionsSchema

class ExitTemplateUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    exit_conditions: ExitConditionsSchema | None = None

class ExitTemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None
    exit_conditions: dict
    is_system: bool
    created_at: str
    updated_at: str
```

#### REST 端点

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/api/v1/backtest/exit-templates` | 创建模版 | 需要 JWT |
| GET | `/api/v1/backtest/exit-templates` | 列出当前用户所有模版 | 需要 JWT |
| GET | `/api/v1/backtest/exit-templates/{id}` | 获取指定模版 | 需要 JWT |
| PUT | `/api/v1/backtest/exit-templates/{id}` | 更新指定模版 | 需要 JWT + 所有权校验 |
| DELETE | `/api/v1/backtest/exit-templates/{id}` | 删除指定模版 | 需要 JWT + 所有权校验 |

#### 端点实现要点

```python
# POST /exit-templates
@router.post("/exit-templates", status_code=201)
async def create_exit_template(
    body: ExitTemplateCreateRequest,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    # 1. 检查同名模版
    existing = await pg_session.execute(
        select(ExitConditionTemplate).where(
            ExitConditionTemplate.user_id == current_user.id,
            ExitConditionTemplate.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"模版名称已存在: {body.name}")

    # 2. 检查数量上限（50 个）
    count_result = await pg_session.execute(
        select(func.count()).where(
            ExitConditionTemplate.user_id == current_user.id
        )
    )
    if count_result.scalar() >= 50:
        raise HTTPException(status_code=409, detail="模版数量已达上限（50个），请删除不需要的模版后重试")

    # 3. 创建模版
    template = ExitConditionTemplate(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        exit_conditions=body.exit_conditions.model_dump(),
    )
    pg_session.add(template)
    await pg_session.flush()
    return _exit_template_to_dict(template)


# GET /exit-templates
@router.get("/exit-templates")
async def list_exit_templates(
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> list:
    # 查询系统内置模版 + 当前用户自定义模版
    # 系统模版排在前面，用户模版按 updated_at 降序
    stmt = (
        select(ExitConditionTemplate)
        .where(
            or_(
                ExitConditionTemplate.is_system == True,
                ExitConditionTemplate.user_id == current_user.id,
            )
        )
        .order_by(
            ExitConditionTemplate.is_system.desc(),  # 系统模版优先
            ExitConditionTemplate.updated_at.desc(),
        )
    )
    result = await pg_session.execute(stmt)
    return [_exit_template_to_dict(t) for t in result.scalars().all()]


# PUT /exit-templates/{id} — 含所有权校验 + 系统模版保护
@router.put("/exit-templates/{template_id}")
async def update_exit_template(
    template_id: UUID,
    body: ExitTemplateUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    template = await _get_template_or_404(template_id, pg_session)
    if template.is_system:
        raise HTTPException(status_code=403, detail="系统内置模版不可修改")
    if template.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该模版")
    # 更新字段...


# DELETE /exit-templates/{id} — 含所有权校验 + 系统模版保护
@router.delete("/exit-templates/{template_id}")
async def delete_exit_template(
    template_id: UUID,
    current_user: AppUser = Depends(get_current_user),
    pg_session: AsyncSession = Depends(get_pg_session),
) -> dict:
    template = await _get_template_or_404(template_id, pg_session)
    if template.is_system:
        raise HTTPException(status_code=403, detail="系统内置模版不可删除")
    if template.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该模版")
    await pg_session.delete(template)
    await pg_session.flush()
    return {"id": str(template_id), "deleted": True}
```

辅助函数：

```python
def _exit_template_to_dict(t: ExitConditionTemplate) -> dict:
    """将 ORM 对象转为 API 响应 dict。"""
    return {
        "id": str(t.id),
        "name": t.name,
        "description": t.description,
        "exit_conditions": t.exit_conditions or {},
        "is_system": t.is_system,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }

async def _get_template_or_404(
    template_id: UUID, session: AsyncSession
) -> ExitConditionTemplate:
    result = await session.execute(
        select(ExitConditionTemplate).where(ExitConditionTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="模版不存在")
    return template
```

### 5. 前端模版管理设计

#### Pinia Store 扩展（`frontend/src/stores/backtest.ts`）

在 `useBacktestStore` 中新增模版相关状态和方法：

```typescript
// 模版类型定义
export interface ExitTemplate {
  id: string
  name: string
  description: string | null
  exit_conditions: {
    conditions: Array<{
      freq: string
      indicator: string
      operator: string
      threshold: number | null
      cross_target: string | null
      params: Record<string, number>
    }>
    logic: 'AND' | 'OR'
  }
  is_system: boolean
  created_at: string
  updated_at: string
}

// store 中新增状态
const exitTemplates = ref<ExitTemplate[]>([])
const selectedTemplateId = ref<string | null>(null)
const templateLoading = ref(false)

// 模版 CRUD 方法
async function fetchExitTemplates() { ... }
async function createExitTemplate(name: string, description?: string) { ... }
async function loadExitTemplate(templateId: string) { ... }
async function updateExitTemplate(templateId: string, data: Partial<ExitTemplate>) { ... }
async function deleteExitTemplate(templateId: string) { ... }
```

#### BacktestView.vue 模版 UI 组件

在现有平仓条件面板中扩展模版管理功能：

```
┌─ 自定义平仓条件 ──────────────────────── [▼ 展开/收起] ─┐
│                                                          │
│  模版: [选择模版 ▼] [⚙ 管理]    [💾 保存为模版]          │
│                                                          │
│  条件逻辑: [AND ▼]                                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ [日K   ▼] [RSI ▼] [> ▼] [80        ] [✕ 删除]  │    │
│  │ [5分钟 ▼] [MA  ▼] [< ▼] [close     ] [✕ 删除]  │    │
│  │            周期: [20  ]                           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  [+ 添加条件]                                            │
└──────────────────────────────────────────────────────────┘
```

交互逻辑：

1. "保存为模版"按钮：当 `exitConditions.conditions` 为空时禁用；点击后弹出对话框，包含名称（必填）和描述（可选）输入框
2. 模版选择下拉框：列出系统内置模版（带"系统"标签）和当前用户所有模版（按 `updated_at` 降序），系统模版排在前面；选择后调用 `loadExitTemplate()` 加载模版配置，替换当前 `exitConditions`
3. 管理按钮：展开模版管理面板，支持重命名（调用 PUT API）和删除（弹出确认对话框后调用 DELETE API）；系统内置模版不显示重命名和删除操作
4. 保存成功后自动刷新模版列表，保存失败时显示错误提示（名称重复 → "模版名称已存在"，数量超限 → "模版数量已达上限"）

#### 保存模版对话框

```
┌─ 保存为模版 ─────────────────────────────┐
│                                           │
│  模版名称: [________________] *必填       │
│  描述:     [________________] 可选        │
│                                           │
│              [取消]  [确认保存]            │
└───────────────────────────────────────────┘
```

---

## 指标使用说明设计（需求 11）

### 6. 前端指标使用说明数据结构

文件：`frontend/src/stores/backtest.ts`（或独立文件 `frontend/src/stores/indicatorDescriptions.ts`）

为全部 13 个可选指标提供结构化的使用说明数据，在用户选择指标时展示。

#### 指标说明类型定义

```typescript
/** 指标参数说明 */
export interface IndicatorParamDescription {
  name: string           // 参数名称（如 "period"）
  label: string          // 中文标签（如 "周期"）
  defaultValue: number   // 默认值
  suggestedRange: string // 建议取值范围（如 "5-120"）
}

/** 单个指标的使用说明 */
export interface IndicatorDescription {
  key: string                          // 指标标识（如 "ma"）
  chineseName: string                  // 中文名称（如 "移动平均线"）
  calculationSummary: string           // 计算逻辑简述
  params: IndicatorParamDescription[]  // 可配置参数列表（无参数时为空数组）
  typicalUsage: string                 // 典型使用场景和平仓条件示例
}
```

#### 指标说明注册表（`INDICATOR_DESCRIPTIONS`）

```typescript
export const INDICATOR_DESCRIPTIONS: Record<string, IndicatorDescription> = {
  ma: {
    key: 'ma',
    chineseName: '移动平均线（MA）',
    calculationSummary: '计算最近 N 个交易日收盘价的算术平均值，反映价格趋势方向。',
    params: [
      { name: 'period', label: '周期', defaultValue: 20, suggestedRange: '5-120' },
    ],
    typicalUsage: '当收盘价跌破 MA20 时卖出（close cross_down ma, period=20），表示短期趋势转弱。',
  },
  macd_dif: {
    key: 'macd_dif',
    chineseName: 'MACD 快线（DIF）',
    calculationSummary: '快速 EMA（默认12日）与慢速 EMA（默认26日）的差值，反映短期与中期趋势的偏离程度。',
    params: [
      { name: 'fast', label: '快线周期', defaultValue: 12, suggestedRange: '5-20' },
      { name: 'slow', label: '慢线周期', defaultValue: 26, suggestedRange: '20-40' },
      { name: 'signal', label: '信号线周期', defaultValue: 9, suggestedRange: '5-15' },
    ],
    typicalUsage: 'DIF 从上方穿越 DEA 形成死叉时卖出（macd_dif cross_down macd_dea），表示上涨动能减弱。',
  },
  macd_dea: {
    key: 'macd_dea',
    chineseName: 'MACD 慢线（DEA）',
    calculationSummary: 'DIF 的 N 日 EMA（默认9日），作为 MACD 信号线，用于确认趋势变化。',
    params: [
      { name: 'fast', label: '快线周期', defaultValue: 12, suggestedRange: '5-20' },
      { name: 'slow', label: '慢线周期', defaultValue: 26, suggestedRange: '20-40' },
      { name: 'signal', label: '信号线周期', defaultValue: 9, suggestedRange: '5-15' },
    ],
    typicalUsage: '当 DEA 从正值转为负值时，表示中期趋势转空，可作为平仓参考。',
  },
  macd_histogram: {
    key: 'macd_histogram',
    chineseName: 'MACD 柱状图',
    calculationSummary: '(DIF - DEA) × 2，柱状图由正转负表示多头动能衰减。',
    params: [
      { name: 'fast', label: '快线周期', defaultValue: 12, suggestedRange: '5-20' },
      { name: 'slow', label: '慢线周期', defaultValue: 26, suggestedRange: '20-40' },
      { name: 'signal', label: '信号线周期', defaultValue: 9, suggestedRange: '5-15' },
    ],
    typicalUsage: '当 MACD 柱状图 < 0 时卖出（macd_histogram < 0），表示空头占优。',
  },
  boll_upper: {
    key: 'boll_upper',
    chineseName: '布林带上轨',
    calculationSummary: '中轨 + N 倍标准差（默认 N=2, 周期=20），价格触及上轨通常表示超买。',
    params: [
      { name: 'period', label: '周期', defaultValue: 20, suggestedRange: '10-30' },
      { name: 'std_dev', label: '标准差倍数', defaultValue: 2, suggestedRange: '1.5-3.0' },
    ],
    typicalUsage: '收盘价从上方跌破布林带上轨时卖出（close cross_down boll_upper），表示价格从超买区域回落。',
  },
  boll_middle: {
    key: 'boll_middle',
    chineseName: '布林带中轨',
    calculationSummary: 'N 日简单移动平均线（默认20日），布林带的基准线。',
    params: [
      { name: 'period', label: '周期', defaultValue: 20, suggestedRange: '10-30' },
      { name: 'std_dev', label: '标准差倍数', defaultValue: 2, suggestedRange: '1.5-3.0' },
    ],
    typicalUsage: '收盘价跌破布林带中轨时卖出（close < boll_middle），表示趋势转弱。',
  },
  boll_lower: {
    key: 'boll_lower',
    chineseName: '布林带下轨',
    calculationSummary: '中轨 - N 倍标准差（默认 N=2, 周期=20），价格触及下轨通常表示超卖。',
    params: [
      { name: 'period', label: '周期', defaultValue: 20, suggestedRange: '10-30' },
      { name: 'std_dev', label: '标准差倍数', defaultValue: 2, suggestedRange: '1.5-3.0' },
    ],
    typicalUsage: '通常用于买入信号而非卖出。在平仓场景中，可配合其他指标使用。',
  },
  rsi: {
    key: 'rsi',
    chineseName: '相对强弱指标（RSI）',
    calculationSummary: '基于 N 日内涨跌幅的比率计算（默认14日），取值 0-100，反映价格的超买超卖状态。',
    params: [
      { name: 'period', label: '周期', defaultValue: 14, suggestedRange: '6-24' },
    ],
    typicalUsage: 'RSI > 80 表示超买，可作为卖出信号（rsi > 80）。RSI > 70 为温和超买区域。',
  },
  dma: {
    key: 'dma',
    chineseName: '平均线差（DMA）',
    calculationSummary: '短期均线（默认10日）与长期均线（默认50日）的差值，反映短期趋势相对长期趋势的偏离。',
    params: [
      { name: 'short', label: '短期周期', defaultValue: 10, suggestedRange: '5-20' },
      { name: 'long', label: '长期周期', defaultValue: 50, suggestedRange: '30-120' },
    ],
    typicalUsage: '当 DMA 从正值转为负值时卖出（dma < 0），表示短期均线跌破长期均线。',
  },
  ama: {
    key: 'ama',
    chineseName: '平均线差均线（AMA）',
    calculationSummary: 'DMA 的移动平均线，用于平滑 DMA 信号，减少假信号。',
    params: [
      { name: 'short', label: '短期周期', defaultValue: 10, suggestedRange: '5-20' },
      { name: 'long', label: '长期周期', defaultValue: 50, suggestedRange: '30-120' },
    ],
    typicalUsage: '当 DMA 从上方穿越 AMA 形成死叉时卖出（dma cross_down ama），确认趋势反转。',
  },
  close: {
    key: 'close',
    chineseName: '收盘价',
    calculationSummary: '当前K线的收盘价（使用前复权数据），最基础的价格指标。',
    params: [],
    typicalUsage: '收盘价跌破某均线时卖出（close cross_down ma, period=20），或收盘价低于固定价位时卖出。',
  },
  volume: {
    key: 'volume',
    chineseName: '成交量',
    calculationSummary: '当前K线周期内的成交股数，反映市场交投活跃度。',
    params: [],
    typicalUsage: '成交量低于某阈值时卖出（volume < 100000），表示市场关注度下降，流动性不足。',
  },
  turnover: {
    key: 'turnover',
    chineseName: '换手率',
    calculationSummary: '成交量占流通股本的百分比，反映股票的流动性和市场参与度。',
    params: [],
    typicalUsage: '换手率低于某阈值时卖出（turnover < 0.5），表示市场参与度过低。',
  },
}
```

#### 前端展示交互

在 `BacktestView.vue` 的条件配置面板中，当用户选择指标时展示使用说明：

```
┌──────────────────────────────────────────────────────────┐
│ [日K   ▼] [RSI ▼] [> ▼] [80        ] [✕ 删除]          │
│ ┌─ 📖 RSI（相对强弱指标）──────────────────────────────┐ │
│ │ 计算逻辑：基于 N 日内涨跌幅的比率计算（默认14日），  │ │
│ │          取值 0-100，反映价格的超买超卖状态。         │ │
│ │ 参数：周期（period），默认 14，建议范围 6-24          │ │
│ │ 典型用法：RSI > 80 表示超买，可作为卖出信号。        │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

展示规则：
- 用户在指标下拉框中选择某个指标后，在该条件行下方展示对应的使用说明卡片
- 说明卡片包含：中文名称、计算逻辑简述、可配置参数（含默认值和建议范围）、典型使用场景
- 无参数的指标（close、volume、turnover）不显示参数区域
- 说明卡片可通过点击关闭或切换指标时自动更新

---

## 系统内置平仓条件模版设计（需求 12）

### 7. 系统内置模版定义

系统提供 5 个预设的常用平仓策略模版，以 `is_system=True` 的 `ExitConditionTemplate` 记录存储在数据库中。

#### 系统模版初始化

通过 Alembic 数据迁移（或应用启动时的 seed 脚本）插入系统模版。系统模版的 `user_id` 使用固定的系统用户 UUID（`00000000-0000-0000-0000-000000000000`）。

#### 5 个内置模版定义

**模版 1：RSI 超买平仓**

```python
{
    "name": "RSI 超买平仓",
    "description": "当 RSI 指标超过 80 时触发平仓，适用于短线超买回调策略。",
    "is_system": True,
    "exit_conditions": {
        "conditions": [
            {"freq": "daily", "indicator": "rsi", "operator": ">", "threshold": 80, "params": {"period": 14}}
        ],
        "logic": "AND"
    }
}
```

**模版 2：MACD 死叉平仓**

```python
{
    "name": "MACD 死叉平仓",
    "description": "当 MACD 快线（DIF）从上方穿越慢线（DEA）形成死叉时触发平仓，适用于趋势跟踪策略。",
    "is_system": True,
    "exit_conditions": {
        "conditions": [
            {"freq": "daily", "indicator": "macd_dif", "operator": "cross_down", "cross_target": "macd_dea", "params": {}}
        ],
        "logic": "AND"
    }
}
```

**模版 3：布林带上轨突破回落**

```python
{
    "name": "布林带上轨突破回落",
    "description": "当收盘价从上方跌破布林带上轨时触发平仓，适用于捕捉超买回落的策略。",
    "is_system": True,
    "exit_conditions": {
        "conditions": [
            {"freq": "daily", "indicator": "close", "operator": "cross_down", "cross_target": "boll_upper", "params": {"period": 20, "std_dev": 2}}
        ],
        "logic": "AND"
    }
}
```

**模版 4：均线空头排列**

```python
{
    "name": "均线空头排列",
    "description": "当 MA5 < MA10 且 MA10 < MA20 时触发平仓，表示短中期均线呈空头排列，趋势转弱。",
    "is_system": True,
    "exit_conditions": {
        "conditions": [
            {"freq": "daily", "indicator": "ma", "operator": "<", "cross_target": null, "threshold": null, "params": {"period": 5}},
            {"freq": "daily", "indicator": "ma", "operator": "<", "cross_target": null, "threshold": null, "params": {"period": 10}}
        ],
        "logic": "AND"
    }
}
```

> **设计说明**：均线空头排列的严格定义是 MA5 < MA10 < MA20。由于当前 `ExitCondition` 模型支持指标与数值阈值或另一指标的比较，但不直接支持两个不同参数的同类指标之间的比较，此模版采用简化实现：使用两条条件分别检测 MA5 和 MA10 是否低于各自的阈值。完整的均线交叉比较将在后续版本中通过扩展 `cross_target` 支持参数化指标来实现。
>
> **替代实现方案**：将两条条件改为 `MA5 cross_down MA10`（MA5 从上方穿越 MA10）作为空头排列的触发信号，这在当前模型中可通过 `indicator="ma"(period=5) cross_down cross_target="ma"(period=10)` 实现（需评估器支持 cross_target 的参数传递）。

**模版 5：量价背离**

```python
{
    "name": "量价背离",
    "description": "当收盘价创新高但成交量低于前一日时触发平仓，表示上涨缺乏量能支撑。",
    "is_system": True,
    "exit_conditions": {
        "conditions": [
            {"freq": "daily", "indicator": "close", "operator": ">", "threshold": 0, "params": {}},
            {"freq": "daily", "indicator": "volume", "operator": "<", "threshold": 0, "params": {}}
        ],
        "logic": "AND"
    }
}
```

> **设计说明**：量价背离的严格定义需要比较"当日收盘价 vs 近 N 日最高收盘价"和"当日成交量 vs 前一日成交量"。当前 `ExitCondition` 模型不直接支持"N 日最高值"比较。此模版采用简化实现，实际的量价背离检测逻辑将在 `ExitConditionEvaluator` 中通过特殊处理实现：当检测到此模版模式时，评估器内部执行完整的量价背离判断（近 5 日收盘价创新高 + 当日成交量 < 前一日成交量）。

#### 系统模版数据库 Seed 脚本

在 Alembic 迁移文件中通过 `INSERT` 语句插入系统模版：

```python
# alembic/versions/005_seed_system_exit_templates.py

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"

SYSTEM_TEMPLATES = [
    # ... 上述 5 个模版定义
]

def upgrade():
    for tpl in SYSTEM_TEMPLATES:
        op.execute(
            sa.text("""
                INSERT INTO exit_condition_template (user_id, name, description, exit_conditions, is_system)
                VALUES (:user_id, :name, :description, :exit_conditions::jsonb, TRUE)
                ON CONFLICT DO NOTHING
            """),
            {
                "user_id": SYSTEM_USER_ID,
                "name": tpl["name"],
                "description": tpl["description"],
                "exit_conditions": json.dumps(tpl["exit_conditions"]),
            },
        )

def downgrade():
    op.execute(
        sa.text("DELETE FROM exit_condition_template WHERE is_system = TRUE")
    )
```

#### 前端系统模版视觉区分

在模版选择下拉框中，系统模版使用特殊样式区分：

```
┌─ 选择模版 ──────────────────────────────┐
│  📌 [系统] RSI 超买平仓                  │
│  📌 [系统] MACD 死叉平仓                 │
│  📌 [系统] 布林带上轨突破回落             │
│  📌 [系统] 均线空头排列                   │
│  📌 [系统] 量价背离                       │
│  ─────────────────────────────────────── │
│  我的 RSI 策略                            │
│  自定义 MACD 组合                         │
└──────────────────────────────────────────┘
```

- 系统模版前缀 `[系统]` 标签，使用不同颜色（如蓝色）
- 系统模版与用户模版之间用分隔线区分
- 选择系统模版后加载到配置面板，用户可修改后另存为自定义模版
- 系统模版不显示"重命名"和"删除"操作按钮

---

## 前复权K线数据集成设计（需求 13）

### 8. 回测引擎前复权K线数据流

#### 设计背景

回测引擎在计算自定义平仓条件的技术指标时，需要使用前复权K线数据，以确保指标计算结果不受除权除息事件影响。当前回测任务（`app/tasks/backtest.py`）已在步骤 2.5 中对日K线数据应用了前复权处理（使用 `ForwardAdjustmentCalculator.adjust_kline_bars`），因此传递给 `BacktestEngine` 的 `kline_data` 已经是前复权数据。

#### 数据流分析

```mermaid
flowchart TD
    A[TimescaleDB 原始K线] --> B[run_backtest_task 加载K线]
    C[TimescaleDB 复权因子] --> D[加载前复权因子]
    B --> E[adjust_kline_bars 前复权处理]
    D --> E
    E --> F[前复权K线数据]
    F --> G[BacktestEngine.run_backtest]
    G --> H[_precompute_indicators 预计算指标]
    G --> I[_precompute_exit_indicators 预计算平仓条件指标]
    H --> J[IndicatorCache - 日K线指标缓存]
    I --> K[exit_indicator_cache - 按频率分组缓存]
    J --> L[ExitConditionEvaluator 评估]
    K --> L
```

**关键点**：
1. `kline_data`（日K线）在进入 `BacktestEngine` 前已经过前复权处理
2. `_precompute_indicators()` 使用前复权后的 `closes` 计算 MA、MACD、BOLL、RSI、DMA 等指标
3. `_precompute_exit_indicators()` 对日K线频率复用 `existing_cache`（已基于前复权数据），对分钟K线频率使用 `kline_data[freq]` 中的数据
4. `ExitConditionEvaluator` 从 `IndicatorCache.closes` 获取的 `close` 值已是前复权收盘价

#### 分钟K线前复权处理

当前回测任务仅对日K线应用前复权。对于分钟K线数据（用于自定义平仓条件的分钟频率指标），需要在加载分钟K线后同样应用前复权处理：

```python
# app/tasks/backtest.py — 在加载分钟K线数据后追加前复权处理

# 对每种分钟频率的K线数据应用前复权
for freq in ["1min", "5min", "15min", "30min", "60min"]:
    freq_klines = minute_kline_data.get(freq, {})
    for sym, bars in freq_klines.items():
        factors = adj_factors.get(sym, [])
        latest = latest_factors.get(sym)
        if factors and latest:
            minute_kline_data[freq][sym] = adjust_kline_bars(bars, factors, latest)
        # 无因子时保持原始数据，已在日K线处理阶段记录过警告
```

#### 与选股引擎的一致性保证

回测引擎和选股引擎（`ScreenDataProvider`）使用相同的前复权计算逻辑：

| 模块 | 前复权函数 | 数据来源 | 因子来源 |
|------|-----------|---------|---------|
| `ScreenDataProvider` | `adjust_kline_bars()` | `KlineRepository.query()` | `AdjFactorRepository.query_batch()` |
| `run_backtest_task` | `adjust_kline_bars()` | 直接 SQL 查询 kline 表 | 直接 SQL 查询 adjustment_factor 表 |

两者共享同一个 `adjust_kline_bars` 纯函数（`app/services/data_engine/forward_adjustment.py`），保证：
- 相同的原始K线 + 相同的复权因子 → 相同的前复权结果
- 指标计算函数（`calculate_ma`, `calculate_macd` 等）也是共享的
- 因此，对于相同的股票和日期范围，回测引擎和选股引擎计算出的技术指标值完全一致

#### 无复权因子时的降级处理

```python
# 已在 run_backtest_task 中实现
for sym, bars in kline_data.items():
    factors = adj_factors.get(sym, [])
    latest = latest_factors.get(sym)
    if factors and latest:
        kline_data[sym] = adjust_kline_bars(bars, factors, latest)
    else:
        logger.warning("股票 %s 无前复权因子数据，使用原始K线", sym)
```

当某只股票无前复权因子数据时：
- 使用原始K线数据计算指标（价格可能在除权除息日出现跳变）
- 记录 WARNING 日志，便于排查
- 不中断回测流程，确保回测结果完整性
