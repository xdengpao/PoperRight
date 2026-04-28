---
inclusion: manual
---

# 数据一致性规范 (Data Consistency Skill)

本规范确保项目中相同类型的数据使用相同的类型、相同的编码方式、相同的术语 key，从数据结构到数据库存储到 API 传输到前端展示保持全链路一致。

---

## 1. 数值类型规范

### 1.1 金额与价格 — 必须使用 `Decimal`

| 字段 | Python 类型 | DB 列类型 | TypeScript 类型 | 精度 |
|------|------------|-----------|----------------|------|
| 股价 (open/high/low/close) | `Decimal` | `NUMERIC(12, 4)` | `number` | 4 位小数 |
| 成交额 (amount) | `Decimal` | `NUMERIC(18, 2)` | `number` | 2 位小数 |
| 初始资金 (initial_capital) | `Decimal` | `NUMERIC(18, 2)` | `number` | 2 位小数 |
| 成本价 (cost_price) | `Decimal` | `NUMERIC(12, 4)` | `number` | 4 位小数 |
| 市值 (market_value) | `Decimal` | 计算字段 | `number` | 2 位小数 |
| 盈亏 (pnl) | `Decimal` | 计算字段 | `number` | 2 位小数 |
| 手续费率 (commission_buy/sell) | `Decimal` | `NUMERIC(8, 6)` | `number` | 6 位小数 |
| 滑点 (slippage) | `Decimal` | `NUMERIC(8, 6)` | `number` | 6 位小数 |
| 复权因子 (adj_factor) | `Decimal` | `NUMERIC(18, 8)` | `number` | 8 位小数 |
| 涨停/跌停价 (limit_up/down) | `Decimal` | `NUMERIC(12, 4)` | `number` | 4 位小数 |

**规则：**
- 所有金额和价格字段在 Python 中必须使用 `Decimal`，禁止使用 `float`
- JSON 序列化时 `Decimal` 转为 `float`（`float(self.price)`），反序列化时用 `Decimal(str(value))`
- 前端使用 `number` 类型，高精度计算场景应传字符串

### 1.2 百分比 — 两种范围约定

| 范围 | 适用场景 | 示例字段 | Python 类型 |
|------|---------|---------|------------|
| **0-100** | 配置参数、趋势打分、换手率、涨跌幅 | `trend_score`, `turnover`, `daily_change_pct`, `stop_loss`(配置) | `float` |
| **0-1** | 计算结果比率 | `win_rate`, `max_drawdown`, `pnl_pct`, `weight` | `float` |

**规则：**
- 配置类百分比（用户输入/展示）统一用 **0-100** 范围
- 计算类比率（内部计算结果）统一用 **0-1** 范围
- 在 API 边界转换时必须注明：`stop_loss_pct: float = 0.08  # 0-1 范围`
- 风控检查器接收 0-100 范围的仓位百分比（如 `stock_weight: float` 表示 12.5%）
- 止损/止盈检查器接收 0-1 范围的比率（如 `stop_pct: float = 0.05` 表示 5%）

### 1.3 成交量 — 必须使用整数

| 字段 | Python 类型 | DB 列类型 | 说明 |
|------|------------|-----------|------|
| volume | `int` | `BIGINT` | 成交量（股数） |
| quantity | `int` | `INTEGER` | 委托/持仓数量 |

### 1.4 换手率与量比

| 字段 | Python 类型 | DB 列类型 | 范围 |
|------|------------|-----------|------|
| turnover (换手率) | `Decimal` | `NUMERIC(5, 2)` | 0-100 (%) |
| vol_ratio (量比) | `Decimal` | `NUMERIC(5, 2)` | 通常 0.5-3.0 |

---

## 2. 枚举类型规范

### 2.1 定义规则

所有枚举必须继承 `(str, Enum)`，值为大写英文字符串：

```python
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
```

### 2.2 数据库存储

枚举在数据库中统一存储为 `VARCHAR` 字符串，**禁止使用数字编码**：

| 枚举 | DB 列类型 | 值示例 |
|------|-----------|--------|
| RiskLevel | `VARCHAR(10)` | LOW, MEDIUM, HIGH |
| MarketRiskLevel | `VARCHAR(10)` | NORMAL, CAUTION, DANGER |
| OrderDirection | `VARCHAR(5)` | BUY, SELL |
| OrderType | `VARCHAR(20)` | LIMIT, MARKET, CONDITION |
| OrderStatus | `VARCHAR(20)` | PENDING, FILLED, CANCELLED, REJECTED |
| TradeMode | `VARCHAR(10)` | LIVE, PAPER |
| ScreenType | `VARCHAR(10)` | EOD, REALTIME |
| AlertType | `VARCHAR(20)` | SCREEN_RESULT, STOP_LOSS, PRICE_THRESHOLD, MARKET_RISK, SYSTEM |
| SignalCategory | `VARCHAR(20)` | MA_TREND, MACD, BOLL, RSI, DMA, BREAKOUT, CAPITAL_INFLOW, LARGE_ORDER, MA_SUPPORT, SECTOR_STRONG |
| DataSource | `VARCHAR(10)` | DC, TI, TDX |
| SectorType | `VARCHAR(20)` | CONCEPT, INDUSTRY, REGION, STYLE |
| ConditionTriggerType | `VARCHAR(20)` | BREAKOUT_BUY, STOP_LOSS, TAKE_PROFIT, TRAILING_STOP |
| UserRole | `VARCHAR(30)` | ADMIN, TRADER, READONLY |
| BacktestStatus | `VARCHAR(20)` | PENDING, RUNNING, DONE, FAILED |
| StockListType | `VARCHAR(10)` | BLACK, WHITE |

### 2.3 JSON/API 序列化

```python
# 序列化：使用 .value
"status": self.status.value  # → "FILLED"

# 反序列化：使用枚举构造
status = OrderStatus(data["status"])  # "FILLED" → OrderStatus.FILLED
```

### 2.4 前端类型映射

前端使用 TypeScript 字符串字面量联合类型：

```typescript
type UserRole = 'TRADER' | 'ADMIN' | 'READONLY'
type AlertLevel = 'INFO' | 'WARNING' | 'DANGER'
type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'
```

---

## 3. 标识符规范

### 3.1 UUID

| 规则 | 说明 |
|------|------|
| 生成方式 | 服务端 PostgreSQL `gen_random_uuid()` |
| Python 类型 | `UUID` (from uuid) |
| DB 列类型 | `PG_UUID(as_uuid=True)` |
| JSON 序列化 | `str(uuid_value)` → `"550e8400-..."` |
| 前端类型 | `string` |
| 前端禁止生成 | 业务实体 UUID 必须由后端生成 |

### 3.2 股票代码 (symbol)

| 规则 | 说明 |
|------|------|
| 格式 | 标准代码：`{6位数字}.{交易所}`，如 `600000.SH`、`000001.SZ`、`830799.BJ` |
| 存储 | `VARCHAR(12)` |
| 交易所 | SH (上海), SZ (深圳), BJ (北京) |
| 转换工具 | `app/core/symbol_utils.py` |

**规则：**
- 所有表的 symbol 字段统一使用标准代码格式（`{code}.{exchange}`）
- 禁止在业务代码中自行实现代码格式转换（如 `split(".")`、内联 if/else 加后缀），必须使用 `symbol_utils` 模块
- API 层兼容裸代码输入（如 `600000`），内部自动转为标准代码
- Tushare 原始数据表的 `ts_code` 字段已是标准格式，与 `symbol` 字段格式一致

### 3.3 板块代码 (sector_code)

| 规则 | 说明 |
|------|------|
| 格式 | 数据源特定编码 |
| 存储 | `VARCHAR(20)` |
| 唯一约束 | `(sector_code, data_source)` 联合唯一 |

---

## 4. 时间类型规范

### 4.1 日期与时间戳

| 字段类型 | Python 类型 | DB 列类型 | JSON 格式 | 时区 |
|---------|------------|-----------|-----------|------|
| 交易日期 | `date` | `DATE` | `"YYYY-MM-DD"` | 无 |
| K线时间 | `datetime` | `TIMESTAMPTZ` | ISO 8601 | Asia/Shanghai |
| 创建/更新时间 | `datetime` | `TIMESTAMPTZ` | ISO 8601 | Asia/Shanghai |
| 委托/成交时间 | `datetime` | `TIMESTAMPTZ` | ISO 8601 | Asia/Shanghai |

**规则：**
- 所有时间戳使用 `TIMESTAMPTZ`（带时区），禁止使用 `TIMESTAMP`
- 默认值使用 `server_default=sa_text("NOW()")`
- 前端接收 ISO 8601 字符串，使用 `new Date()` 解析
- 系统时区统一为 `Asia/Shanghai`

### 4.2 K线频率 (freq)

| 值 | 含义 | 存储 |
|----|------|------|
| `"1m"` | 1 分钟 | `VARCHAR(5)` |
| `"5m"` | 5 分钟 | |
| `"15m"` | 15 分钟 | |
| `"30m"` | 30 分钟 | |
| `"60m"` | 60 分钟 | |
| `"1d"` | 日线 | |
| `"1w"` | 周线 | |
| `"1M"` | 月线 | |

**向后兼容：** 旧版 `"minute"` 映射为 `"1min"`；自定义平仓条件中使用 `"daily"`, `"1min"`, `"5min"` 等格式（见 `VALID_FREQS`）。

### 4.3 复权类型 (adj_type)

| 值 | 含义 | 存储 |
|----|------|------|
| `0` | 不复权 | `SMALLINT` |
| `1` | 前复权 | |
| `2` | 后复权 | |

---

## 5. 术语与字段名映射

### 5.1 核心术语 — 中英文对照

在代码中使用英文 key，在 UI/注释中使用中文：

| 中文术语 | 英文 key | 字段名 |
|---------|---------|--------|
| 大盘 | market / index | — |
| 大盘风控 | market_risk | `market_risk_level` |
| 个股 | stock | — |
| 风险等级 | risk_level | `risk_level` |
| 趋势打分 | trend_score | `trend_score` |
| 均线 | ma (moving average) | `ma_periods`, `ma20`, `ma60` |
| 多头排列 | bullish_alignment | — |
| 破位 | breakdown | — |
| 止损 | stop_loss | `stop_loss`, `stop_loss_pct` |
| 止盈 | take_profit | `take_profit` |
| 移动止盈 | trailing_stop | `trailing_stop_pct`, `trailing_pct` |
| 换手率 | turnover | `turnover`, `turnover_rate_min/max` |
| 量比 | vol_ratio / volume_ratio | `vol_ratio`, `volume_ratio_threshold` |
| 主力资金 | main_flow | `main_flow_threshold`, `main_flow_days` |
| 大单 | large_order | `large_order_ratio` |
| 板块 | sector | `sector_code`, `sector_type` |
| 涨幅/涨跌幅 | change_pct / gain | `change_pct`, `daily_change_pct` |
| 成交额 | amount | `amount`, `min_daily_amount` |
| 复权 | adjustment | `adj_type`, `adj_factor` |
| 前复权 | forward_adjustment | `adj_type=1` |
| 后复权 | backward_adjustment | `adj_type=2` |
| 选股 | screen / screening | `screen_type`, `screen_time` |
| 回测 | backtest | `backtest_run` |
| 委托 | order | `trade_order` |
| 成交 | filled | `OrderStatus.FILLED` |
| 撤单 | cancel | `OrderStatus.CANCELLED` |
| 持仓 | position | `position` |
| 仓位 | weight / position_pct | `weight`, `stock_weight` |
| 盈亏 | pnl / profit_loss | Python: `pnl`, 前端: `profit_loss` |
| 盈亏比例 | pnl_pct / profit_loss_ratio | Python: `pnl_pct`, 前端: `profit_loss_ratio` |
| 市值 | market_value | `market_value` |
| 成本价 | cost_price | `cost_price` |
| 当前价 | current_price | `current_price` |
| 买入参考价 | ref_buy_price | `ref_buy_price` |
| 交易日 | trading_day / trade_date | `trade_date` |
| 预警 | alert | `alert_type` |
| 审计日志 | audit_log | `audit_log` |

### 5.2 跨层字段名差异（已知且允许）

以下字段在前后端使用不同名称，这是已知的设计决策：

| 概念 | Python (schemas.py) | 前端 (TypeScript) | 说明 |
|------|---------------------|-------------------|------|
| 盈亏金额 | `pnl` | `profit_loss` | 前端更具可读性 |
| 盈亏比例 | `pnl_pct` | `profit_loss_ratio` | 前端更具可读性 |

**规则：** 新增字段时，前后端应使用相同的 key 名称。上述差异仅为历史遗留，不应扩大。

---

## 6. 数据库编码规范

### 6.1 ORM 基类选择

| 数据类型 | ORM 基类 | 数据库 | 说明 |
|---------|---------|--------|------|
| 业务数据 | `PGBase` | PostgreSQL | 用户、策略、交易、持仓、板块元数据 |
| 时序数据 | `TSBase` | TimescaleDB | K线、板块行情、复权因子 |

**规则：** 同一个模型禁止混用两个基类。

### 6.2 JSONB 存储

以下数据使用 JSONB 列存储：

| 表 | 列 | 存储内容 | 序列化方式 |
|---|---|---------|-----------|
| strategy_template | `config` | StrategyConfig | `.to_dict()` / `.from_dict()` |
| strategy_template | `enabled_modules` | 模块名列表 | 原生 list |
| screen_result | `signals` | 信号详情列表 | 手动 dict 构造 |
| backtest_run | `result` | BacktestResult | `.to_dict()` 或手动 dict |
| exit_condition_template | `exit_conditions` | ExitConditionConfig | `.to_dict()` / `.from_dict()` |
| audit_log | `detail` | 操作详情 | 原生 dict |

### 6.3 to_dict / from_dict 模式

所有配置类 dataclass 必须实现双向序列化：

```python
@dataclass
class SomeConfig:
    def to_dict(self) -> dict:
        """序列化为可 JSON 存储的字典"""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "SomeConfig":
        """从字典反序列化（需向后兼容旧格式）"""
        ...
```

**规则：**
- `from_dict()` 必须处理缺失字段（使用 `data.get(key, default)`）
- `from_dict()` 必须向后兼容旧版数据格式
- 嵌套配置对象递归调用子对象的 `from_dict()`

---

## 7. API 边界规范

### 7.1 请求/响应模型

- API 层使用 Pydantic `BaseModel` 定义请求/响应
- 业务层使用 `dataclass`（定义在 `app/core/schemas.py`）
- 禁止在业务层直接使用 Pydantic 模型

### 7.2 分页响应格式

```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "items": [...]
}
```

### 7.3 删除响应格式

```json
{"id": "uuid-string", "deleted": true}
```

### 7.4 时间序列化

所有 `datetime` 字段在 API 响应中使用 `.isoformat()` 序列化。

---

## 8. 前端类型规范

### 8.1 接口定义位置

| 类型 | 定义位置 | 说明 |
|------|---------|------|
| API 响应类型 | 对应的 Pinia store 文件 | `export interface` |
| WebSocket 消息 | `services/wsClient.ts` | `WsMessage` |
| 路由 meta | `router/index.ts` | `meta.roles`, `meta.title` |

### 8.2 Store 命名

| Store | 文件 | 管理内容 |
|-------|------|---------|
| auth | `stores/auth.ts` | 登录状态、JWT、用户信息 |
| alert | `stores/alert.ts` | 预警消息、toast 通知 |
| market | `stores/market.ts` | 大盘概况数据 |
| positions | `stores/positions.ts` | 持仓列表 |
| screener | `stores/screener.ts` | 选股结果、策略模板 |
| backtest | `stores/backtest.ts` | 回测状态与结果 |
| sector | `stores/sector.ts` | 板块数据 |

---

## 9. 检查清单

新增字段或模型时，按以下清单逐项确认：

- [ ] 金额/价格字段使用 `Decimal` + `NUMERIC(精度)`
- [ ] 百分比字段明确标注范围（0-100 或 0-1）
- [ ] 枚举继承 `(str, Enum)`，值为大写字符串
- [ ] 枚举存储为 `VARCHAR`，禁止数字编码
- [ ] 时间戳使用 `TIMESTAMPTZ`，默认值 `NOW()`
- [ ] UUID 使用 `PG_UUID(as_uuid=True)` + `gen_random_uuid()`
- [ ] 股票代码使用 `VARCHAR(12)`，统一标准代码格式（`{code}.{exchange}`），使用 `symbol_utils` 转换
- [ ] JSONB 配置类实现 `to_dict()` / `from_dict()`
- [ ] `from_dict()` 向后兼容旧格式
- [ ] 前后端字段名一致（除已知例外）
- [ ] 中文术语对应的英文 key 与现有术语表一致
- [ ] ORM 模型选择正确的基类（PGBase / TSBase）
