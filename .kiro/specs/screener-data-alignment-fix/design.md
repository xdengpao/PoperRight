# 技术设计文档：智能选股数据对齐与算法修复

## 概述

本设计文档针对智能选股系统中发现的 12 个核心问题，提供详细的技术修复方案。修复范围涵盖后端 `app/services/screener/`、`app/services/data_engine/`、`app/core/schemas.py`、`app/api/v1/screen.py`、`app/tasks/screening.py` 以及前端 `frontend/src/stores/screener.ts`。

核心修复目标：
- 修复股票代码格式不一致导致约 30 个 Tushare 因子全部匹配失败的问题
- 修复 StrategyEngine 加权得分计算的量纲混乱问题
- 消除信号重复构建
- 补全缺失的涨跌幅因子和 PSY/OBV 因子
- 修复 StrategyConfig 重复定义与 indicator_params 前后端数据契约不匹配
- 修复 large_order_ratio 量纲不一致导致大单信号永远为 False
- 修复假突破检测使用错误日期的逻辑缺陷
- 修复实时选股增量缓存的 Decimal 序列化问题
- 修复前端 screener store 响应类型不匹配

---

## 架构

### 数据流与代码格式转换点

```
stock_info (PG)                    Tushare 导入表 (PG)
symbol: "000001"                   ts_code: "000001.SZ"
        │                                   │
        ▼                                   ▼
ScreenDataProvider.load_screen_data()       _enrich_*() 方法
        │                                   │
        │  stocks_data key: "000001"        │  row_map key: "000001.SZ" ← 问题根源
        │                                   │
        ▼                                   ▼
    row_map.get("000001") → None（匹配失败）
        │
        ▼
    因子降级为 None（约 30 个因子全部失效）
```

修复后的数据流：

```
stock_info (PG)                    Tushare 导入表 (PG)
symbol: "000001"                   ts_code: "000001.SZ"
        │                                   │
        ▼                                   ▼
ScreenDataProvider.load_screen_data()       _enrich_*() 方法
        │                                   │
        │  stocks_data key: "000001"        │  _strip_market_suffix("000001.SZ") → "000001"
        │                                   │  row_map key: "000001" ← 修复后
        ▼                                   ▼
    row_map.get("000001") → 匹配成功 ✓
```

### 受影响的文件清单

| 文件路径 | 修改类型 | 对应需求 |
|---------|---------|---------|
| `app/services/screener/screen_data_provider.py` | 修改 | 需求 1, 5, 6, 8, 9 |
| `app/services/data_engine/kline_repository.py` | 修改 | 需求 2 |
| `app/services/data_engine/adj_factor_repository.py` | 修改 | 需求 2 |
| `app/services/screener/strategy_engine.py` | 修改 | 需求 3 |
| `app/services/screener/screen_executor.py` | 修改 | 需求 4, 5 |
| `app/services/screener/indicators.py` | 修改 | 需求 6 |
| `app/core/schemas.py` | 修改 | 需求 7 |
| `app/api/v1/screen.py` | 无需修改 | 需求 7（修复在 schemas 层） |
| `app/tasks/screening.py` | 修改 | 需求 10 |
| `frontend/src/stores/screener.ts` | 修改 | 需求 11 |
| `tests/services/test_screen_data_provider.py` | 新增/修改 | 需求 1, 5, 6, 8, 9 |
| `tests/services/test_strategy_engine.py` | 修改 | 需求 3 |
| `tests/services/test_screen_executor.py` | 修改 | 需求 4, 5 |
| `tests/properties/test_screener_properties.py` | 修改 | 需求 3 |

---

## 组件设计

### 组件 1：股票代码格式转换层（需求 1, 2）

#### 设计决策

**方案对比：**
- 方案 A：在查询层做格式转换（选中）— 最小改动，不改变数据库存储
- 方案 B：统一数据库存储格式 — 需要数据迁移，风险大
- 方案 C：在 ORM 模型层做自动转换 — 侵入性强，影响其他模块

选择方案 A，在 `ScreenDataProvider` 的 `_enrich_*` 方法中统一做格式转换。

#### 详细设计

**1.1 新增辅助方法 `_strip_market_suffix`**

位置：`app/services/screener/screen_data_provider.py`

```python
@staticmethod
def _strip_market_suffix(ts_code: str) -> str:
    """将 Tushare ts_code 格式（如 '000001.SZ'）转换为纯数字格式（'000001'）。"""
    return ts_code.split(".")[0] if "." in ts_code else ts_code
```

**1.2 修改所有 `_enrich_*` 方法的 row_map 构建逻辑**

以 `_enrich_stk_factor_factors` 为例，修改前：
```python
row_map: dict[str, StkFactor] = {r.ts_code: r for r in rows}
```

修改后：
```python
row_map: dict[str, StkFactor] = {self._strip_market_suffix(r.ts_code): r for r in rows}
```

需要同样修改的方法：
- `_enrich_stk_factor_factors`：`row_map` 键转换
- `_enrich_chip_factors`：`row_map` 键转换
- `_enrich_margin_factors`：`grouped` 分组键转换
- `_enrich_enhanced_money_flow_factors`：`row_map` 键转换
- `_enrich_board_hit_factors`：`limit_grouped`、`step_map`、`top_grouped` 键转换
- `_enrich_index_factors`：`basic_map`、`tech_map` 键转换，`stock_index_map` 中 `con_code` 转换

**1.3 KlineRepository 查询格式标准化**

位置：`app/services/data_engine/kline_repository.py`

在 `query()` 方法开头添加格式标准化：
```python
async def query(self, symbol: str, freq: str, start, end, adj_type=0):
    symbol = symbol.split(".")[0] if "." in symbol else symbol
    # ... 原有逻辑
```

**1.4 AdjFactorRepository 批量查询格式标准化**

位置：`app/services/data_engine/adj_factor_repository.py`

在 `query_batch()` 方法中对 symbols 列表做格式标准化：
```python
async def query_batch(self, symbols, adj_type, start, end):
    symbols = [s.split(".")[0] if "." in s else s for s in symbols]
    # ... 原有逻辑
```

---

### 组件 2：StrategyEngine 加权得分归一化（需求 3）

#### 设计决策

当前问题：`weighted_sum += result.value * weight`，其中 `result.value` 是因子原始值（如 `pe_ttm=25.0`、`ma_trend=85.0`），量纲不同导致加权求和无意义。

修复方案：在 `FactorEvaluator.evaluate()` 返回结果中新增 `normalized_score` 字段，`StrategyEngine.evaluate()` 使用归一化分数替代原始值。

#### 详细设计

**2.1 扩展 FactorEvalResult 数据类**

```python
@dataclass
class FactorEvalResult:
    factor_name: str
    passed: bool
    value: float | None = None
    weight: float = 1.0
    normalized_score: float = 0.0  # 新增：归一化分数 [0, 100]
```

**2.2 归一化计算逻辑**

在 `FactorEvaluator.evaluate()` 方法末尾，根据 `threshold_type` 计算 `normalized_score`：

| ThresholdType | 归一化规则 |
|--------------|-----------|
| BOOLEAN | 通过=100.0，未通过=0.0 |
| ABSOLUTE | 通过时：`60 + 40 × min(abs(value - threshold) / abs(threshold), 1.0)`；未通过时：`60 × (1 - min(abs(value - threshold) / abs(threshold), 1.0))` |
| PERCENTILE | 直接使用百分位值（已在 0-100） |
| INDUSTRY_RELATIVE | `min(100, max(0, value / median × 50))` |
| RANGE | 在区间内=100.0；偏离区间时按距离衰减 |

**2.3 修改 StrategyEngine.evaluate() 加权求和**

```python
# 修改前
if result.passed and result.value is not None:
    weighted_sum += result.value * weight

# 修改后
weighted_sum += result.normalized_score * weight
```

最终 `weighted_score = weighted_sum / total_weight`，结果自然在 [0, 100] 范围内。

---

### 组件 3：信号去重机制（需求 4）

#### 详细设计

在 `ScreenExecutor._execute()` 方法中，信号构建完成后添加去重逻辑：

```python
# 信号去重：以 (category, label) 为键，优先保留非 factor_editor 路径的信号
seen_keys: set[tuple[str, str]] = set()
deduped_signals: list[SignalDetail] = []

# 先添加非 factor_editor 路径的信号（包含更丰富的上下文）
for sig in signals:
    key = (sig.category, sig.label)
    if key not in seen_keys:
        seen_keys.add(key)
        deduped_signals.append(sig)

signals = deduped_signals
```

实现方式：将非 `factor_editor` 路径的信号先添加到列表，再处理 `factor_editor` 路径的信号时跳过已存在的 key。

---

### 组件 4：涨跌幅因子计算（需求 5）

#### 详细设计

在 `ScreenDataProvider._build_factor_dict()` 方法中，在派生因子计算区域添加：

```python
# 涨跌幅因子
if len(bars) >= 2:
    prev_close = float(bars[-2].close)
    curr_close = float(bars[-1].close)
    if prev_close > 0:
        stock_data["daily_change_pct"] = (curr_close - prev_close) / prev_close * 100.0
    else:
        stock_data["daily_change_pct"] = 0.0
else:
    stock_data["daily_change_pct"] = 0.0

# 近 3 日累计涨幅
if len(bars) >= 4:
    close_3d_ago = float(bars[-4].close)
    if close_3d_ago > 0:
        stock_data["change_pct_3d"] = (curr_close - close_3d_ago) / close_3d_ago * 100.0
    else:
        stock_data["change_pct_3d"] = 0.0
else:
    stock_data["change_pct_3d"] = 0.0
```

在 `ScreenExecutor._apply_risk_filters_pure()` 中添加 `change_pct_3d > 20.0` 的过滤条件。

---

### 组件 5：PSY 和 OBV 因子本地计算（需求 6）

#### 详细设计

**5.1 PSY 计算**

在 `app/services/screener/indicators.py` 中新增：

```python
def calculate_psy(closes: list[float], period: int = 12) -> float | None:
    """计算心理线指标。PSY = 最近 period 日中上涨天数 / period × 100"""
    if len(closes) < period + 1:
        return None
    recent = closes[-(period + 1):]
    up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
    return up_days / period * 100.0
```

**5.2 OBV 信号计算**

```python
def calculate_obv_signal(closes: list[float], volumes: list[int], short: int = 5, long: int = 20) -> bool | None:
    """计算 OBV 能量潮信号。当 OBV 短期均值 > 长期均值时返回 True。"""
    n = len(closes)
    if n < long + 1 or len(volumes) < long + 1:
        return None
    obv = [0.0] * n
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    obv_short_avg = sum(obv[-short:]) / short
    obv_long_avg = sum(obv[-long:]) / long
    return obv_short_avg > obv_long_avg
```

**5.3 集成到 _build_factor_dict()**

在 `_build_factor_dict()` 的派生因子计算区域添加 PSY 和 OBV 计算调用，并在 `_enrich_stk_factor_factors()` 中移除 `fd["psy"] = None` 和 `fd["obv_signal"] = None` 的硬编码覆盖，改为 `fd.setdefault("psy", None)` 和 `fd.setdefault("obv_signal", None)` 以保留 `_build_factor_dict()` 中已计算的值。

同时为 `profit_growth` 和 `revenue_growth` 因子添加数据来源：从 Tushare 导入的财务数据表（`financial_statement`）中查询最新报告期的净利润同比增长率和营收同比增长率，在 `_build_factor_dict()` 或新增的 `_enrich_financial_growth_factors()` 方法中写入 Factor_Dict。

---

### 组件 6：StrategyConfig 去重与 indicator_params 数据契约修复（需求 7）

#### 设计决策

当前 `schemas.py` 中存在两个 `StrategyConfig` 类定义（第 239 行和第 497 行），Python 使用最后一个定义，第一个成为死代码。同时前端 API 层 `IndicatorParamsConfigIn` 使用嵌套结构（`macd.fast_period`），但 `IndicatorParamsConfig.from_dict()` 期望扁平键（`macd_fast`），导致用户自定义参数被静默忽略。

#### 详细设计

**6.1 移除第一个 StrategyConfig 定义**

删除 `schemas.py` 第 239-283 行的第一个 `StrategyConfig` 类定义（`indicator_params: dict` 版本）。

**6.2 修改 IndicatorParamsConfig.from_dict() 支持双格式**

```python
@classmethod
def from_dict(cls, data: dict) -> "IndicatorParamsConfig":
    # 检测嵌套格式：如果 data 中包含 "macd"/"boll"/"rsi"/"dma" 子字典
    if isinstance(data.get("macd"), dict):
        macd = data.get("macd", {})
        boll = data.get("boll", {})
        rsi = data.get("rsi", {})
        dma = data.get("dma", {})
        return cls(
            macd_fast=macd.get("fast_period", 12),
            macd_slow=macd.get("slow_period", 26),
            macd_signal=macd.get("signal_period", 9),
            boll_period=boll.get("period", 20),
            boll_std_dev=boll.get("std_dev", 2.0),
            rsi_period=rsi.get("period", 14),
            rsi_lower=rsi.get("lower_bound", 55),
            rsi_upper=rsi.get("upper_bound", 75),
            dma_short=dma.get("short_period", 10),
            dma_long=dma.get("long_period", 50),
        )
    # 扁平格式（原有逻辑）
    return cls(
        macd_fast=data.get("macd_fast", 12),
        macd_slow=data.get("macd_slow", 26),
        # ... 原有逻辑不变
    )
```

---

### 组件 7：large_order_ratio 量纲转换（需求 8）

#### 详细设计

在 `screen_data_provider.py` 的 `_enrich_money_flow_factors()` 方法中，修改 `large_order_ratio` 的读取逻辑：

```python
# 修改前
latest_large_order_ratio = (
    float(latest_row.large_order_ratio)
    if latest_row.large_order_ratio is not None
    else 0.0
)

# 修改后：将比率格式（0-1）转换为百分比格式（0-100）
raw_ratio = float(latest_row.large_order_ratio) if latest_row.large_order_ratio is not None else 0.0
latest_large_order_ratio = raw_ratio * 100.0 if raw_ratio <= 1.0 else raw_ratio
```

使用 `raw_ratio <= 1.0` 作为判断条件，兼容两种可能的存储格式（比率或百分比）。同时修改写入 Factor_Dict 的 `large_order_ratio` 也使用百分比格式。

---

### 组件 8：假突破检测数据窗口前移（需求 9）

#### 设计决策

**方案对比：**
- 方案 A：数据窗口前移（选中）— 用 `closes[:-1]` 做突破检测，`closes[-1]` 做确认
- 方案 B：两阶段流程（先产生待确认信号，次日再验证）— 需要状态持久化，复杂度高

选择方案 A，最小改动且逻辑清晰。

#### 详细设计

修改 `_detect_all_breakouts()` 方法：

```python
@staticmethod
def _detect_all_breakouts(closes, highs, lows, volumes, bo_cfg=None):
    # ... 配置解析不变 ...

    # 数据窗口前移：用 [:-1] 做突破检测，[-1] 做确认
    if len(closes) < 2:
        return []

    detect_closes = closes[:-1]
    detect_highs = highs[:-1]
    detect_lows = lows[:-1]
    detect_volumes = volumes[:-1]
    confirm_close = closes[-1]  # 确认日收盘价

    # 箱体突破（使用前移窗口）
    if enable_box:
        box = detect_box_breakout(
            detect_closes, detect_highs, detect_lows, detect_volumes,
            volume_multiplier=vol_threshold,
        )
        if box is not None:
            if confirm_days > 0:
                box = check_false_breakout(box, confirm_close, hold_days=confirm_days)
            breakout_list.append(_signal_to_dict(box))

    # 前期高点突破、下降趋势线突破同理...
```

---

### 组件 9：增量缓存 Decimal 序列化修复（需求 10）

#### 详细设计

修改 `app/tasks/screening.py` 中的 `_serialize_factor_dict()` 函数：

```python
def _serialize_factor_dict(factor_dict: dict) -> dict:
    """将因子字典序列化为 JSON 兼容格式。"""
    result = {}
    for k, v in factor_dict.items():
        if isinstance(v, Decimal):
            result[k] = float(v)  # 修改：Decimal → float（而非 str）
        elif isinstance(v, list):
            result[k] = [float(x) if isinstance(x, Decimal) else x for x in v]
        else:
            result[k] = v
    return result
```

---

### 组件 10：前端 screener store 修复（需求 11）

#### 详细设计

**10.1 修复 fetchResults 响应处理**

```typescript
// 修改前
const res = await apiClient.get<ScreenItem[]>('/screen/results')
results.value = res.data

// 修改后
const res = await apiClient.get('/screen/results')
const data = res.data
results.value = Array.isArray(data) ? data : (data.items ?? [])
```

**10.2 修复 ScreenItem.signals 类型**

```typescript
// 新增 SignalDetail 接口
export interface SignalDetail {
  category: string
  label: string
  strength: 'STRONG' | 'MEDIUM' | 'WEAK' | null
  description: string
  freshness: 'NEW' | 'CONTINUING' | null
  is_fake_breakout: boolean
}

// 修改 ScreenItem 接口
export interface ScreenItem {
  symbol: string
  name: string
  ref_buy_price: number
  trend_score: number
  risk_level: string
  signals: SignalDetail[]  // 修改：从 Record<string, unknown> 改为 SignalDetail[]
  has_fake_breakout: boolean
  has_new_signal: boolean
  market_risk_level: string
}
```

---

## 测试策略

### 单元测试

| 测试文件 | 测试内容 | 对应需求 |
|---------|---------|---------|
| `tests/services/test_screen_data_provider.py` | `_strip_market_suffix` 各种格式输入 | 需求 1 |
| `tests/services/test_screen_data_provider.py` | `_build_factor_dict` 包含 `daily_change_pct`、`change_pct_3d`、`psy`、`obv_signal` | 需求 5, 6 |
| `tests/services/test_screen_data_provider.py` | `large_order_ratio` 量纲转换正确性 | 需求 8 |
| `tests/services/test_screen_data_provider.py` | 假突破检测使用确认日价格 | 需求 9 |
| `tests/services/test_strategy_engine.py` | `FactorEvalResult.normalized_score` 各 ThresholdType 归一化正确性 | 需求 3 |
| `tests/services/test_strategy_engine.py` | `StrategyEngine.evaluate()` 加权得分在 [0, 100] 范围内 | 需求 3 |
| `tests/services/test_screen_executor.py` | 信号去重：同一因子不产生重复 SignalDetail | 需求 4 |
| `tests/services/test_screen_executor.py` | 风控过滤：`daily_change_pct > 9` 和 `change_pct_3d > 20` 正确剔除 | 需求 5 |
| `tests/services/test_indicators.py` | `calculate_psy` 和 `calculate_obv_signal` 边界条件 | 需求 6 |
| `tests/services/test_schemas.py` | `IndicatorParamsConfig.from_dict()` 嵌套格式和扁平格式均正确解析 | 需求 7 |
| `tests/tasks/test_screening.py` | `_serialize_factor_dict` Decimal 转 float 而非 str | 需求 10 |

### 属性测试（Hypothesis）

| 测试文件 | 属性 | 对应需求 |
|---------|------|---------|
| `tests/properties/test_screener_properties.py` | `normalized_score` 始终在 [0, 100] 闭区间 | 需求 3 |
| `tests/properties/test_screener_properties.py` | `weighted_score` 始终在 [0, 100] 闭区间 | 需求 3 |
| `tests/properties/test_screener_properties.py` | `_strip_market_suffix` 幂等性：`f(f(x)) == f(x)` | 需求 1 |
| `tests/properties/test_screener_properties.py` | PSY 结果始终在 [0, 100] 闭区间 | 需求 6 |

### 集成测试

| 测试场景 | 验证内容 |
|---------|---------|
| 端到端选股流程 | 使用包含 Tushare 因子条件的策略执行选股，验证因子数据非 None |
| 涨停股过滤 | 构造涨幅 > 9% 的股票数据，验证被正确剔除 |
| 信号去重 | 启用 factor_editor + indicator_params 模块，验证 MACD 信号不重复 |
| indicator_params 嵌套格式 | 通过 API 提交嵌套格式的技术指标参数，验证后端正确解析 |
| 假突破检测 | 构造突破后次日跌回压力位的数据，验证标记为假突破 |
| 大单信号 | 构造 large_order_ratio=0.35 的数据，验证大单信号触发 |
