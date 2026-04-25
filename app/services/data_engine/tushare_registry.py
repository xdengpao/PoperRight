"""
Tushare API 接口注册表

以声明式方式定义每个 Tushare 接口的元数据，包括：
- 接口名称、中文说明、所属分类
- Token 权限级别（basic/advanced/premium/special）
- 目标存储表、存储引擎（PG/TS）
- 代码格式转换规则
- ON CONFLICT 去重策略
- 字段映射、参数类型、频率限制分组

Import_Task 根据注册表信息自动完成字段映射、存储路由和去重策略，
新增接口只需注册元数据，无需修改核心逻辑。

对应需求：22a.2, 26.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TokenTier(str, Enum):
    """Token 权限级别（四级）"""

    BASIC = "basic"         # 2000 积分及以下
    ADVANCED = "advanced"   # 2000-6000 积分（包含6000积分）
    PREMIUM = "premium"     # 6000 积分以上
    SPECIAL = "special"     # 需单独开通权限


class CodeFormat(str, Enum):
    """代码格式要求"""

    STOCK_SYMBOL = "stock_symbol"  # ts_code → 纯6位
    INDEX_CODE = "index_code"  # 保留完整 ts_code
    NONE = "none"  # 无代码字段


class StorageEngine(str, Enum):
    """存储引擎"""

    PG = "pg"  # PostgreSQL
    TS = "ts"  # TimescaleDB


class ParamType(str, Enum):
    """参数类型"""

    DATE_RANGE = "date_range"
    STOCK_CODE = "stock_code"
    INDEX_CODE = "index_code"
    MARKET = "market"
    REPORT_PERIOD = "report_period"
    FREQ = "freq"
    HS_TYPE = "hs_type"
    SECTOR_CODE = "sector_code"
    MONTH_RANGE = "month_range"
    CONCEPT_CODE = "concept_code"


class RateLimitGroup(str, Enum):
    """频率限制分组

    原有分组（保留向后兼容）：
        KLINE / FUNDAMENTALS / MONEY_FLOW / LIMIT_UP

    新增 Tushare 官方频率层级：
        TIER_80  — 80次/min（~0.90s）
        TIER_60  — 60次/min（~1.20s）
        TIER_20  — 20次/min（~3.50s）
        TIER_10  — 10次/min（~7.00s），语义上替代 LIMIT_UP
    """

    # --- 原有分组（向后兼容） ---
    KLINE = "kline"  # 0.18s（500次/min）
    FUNDAMENTALS = "fundamentals"  # 0.40s（200次/min）
    MONEY_FLOW = "money_flow"  # 0.30s（300次/min）
    LIMIT_UP = "limit_up"  # 6.0s（10次/min，打板专题接口，保留向后兼容）

    # --- 新增 Tushare 官方频率层级 ---
    TIER_80 = "tier_80"  # 0.90s（80次/min）
    TIER_60 = "tier_60"  # 1.20s（60次/min）
    TIER_20 = "tier_20"  # 3.50s（20次/min）
    TIER_10 = "tier_10"  # 7.00s（10次/min）
    TIER_2 = "tier_2"  # 35.0s（2次/min，券商盈利预测等极低频接口）


@dataclass
class FieldMapping:
    """字段映射：Tushare 字段名 → 目标表字段名"""

    source: str  # Tushare 返回字段名
    target: str  # 目标表字段名
    transform: str | None = None  # 可选转换函数名


@dataclass
class ApiEntry:
    """单个 Tushare API 接口注册信息"""

    api_name: str  # Tushare 接口名
    label: str  # 中文说明
    category: str  # 所属大类（stock_data / index_data）
    subcategory: str  # 所属子分类
    token_tier: TokenTier  # 权限级别
    target_table: str  # 目标存储表名
    storage_engine: StorageEngine  # 存储引擎
    code_format: CodeFormat  # 代码格式
    conflict_columns: list[str]  # ON CONFLICT 列
    conflict_action: str = "do_nothing"  # do_nothing / do_update
    update_columns: list[str] = field(default_factory=list)  # do_update 时更新的列
    field_mappings: list[FieldMapping] = field(default_factory=list)
    required_params: list[ParamType] = field(default_factory=list)
    optional_params: list[ParamType] = field(default_factory=list)
    rate_limit_group: RateLimitGroup = RateLimitGroup.KLINE
    batch_by_code: bool = False  # 是否需要按代码分批
    batch_by_date: bool = False  # 是否需要按日期自动分批
    batch_by_sector: bool = False  # 是否按板块代码遍历导入（需求 1.1）
    date_chunk_days: int = 30  # 日期分批步长（天数）
    extra_config: dict = field(default_factory=dict)  # 额外配置（如 freq 映射）
    vip_variant: str | None = None  # VIP 批量接口变体名（如 "income_vip"）


# ---------------------------------------------------------------------------
# 全局注册表
# ---------------------------------------------------------------------------

TUSHARE_API_REGISTRY: dict[str, ApiEntry] = {}


def register(entry: ApiEntry) -> None:
    """注册一个 API 接口"""
    TUSHARE_API_REGISTRY[entry.api_name] = entry


def get_entry(api_name: str) -> ApiEntry | None:
    """获取接口注册信息"""
    return TUSHARE_API_REGISTRY.get(api_name)


def get_all_entries() -> dict[str, ApiEntry]:
    """获取全部注册接口"""
    return TUSHARE_API_REGISTRY


def get_entries_by_category(category: str) -> list[ApiEntry]:
    """按大类获取接口列表"""
    return [e for e in TUSHARE_API_REGISTRY.values() if e.category == category]


def get_entries_by_subcategory(subcategory: str) -> list[ApiEntry]:
    """按子分类获取接口列表"""
    return [e for e in TUSHARE_API_REGISTRY.values() if e.subcategory == subcategory]


# ===========================================================================
# 股票数据 — 基础数据（13个接口）
# 需求：3.1-3.16
# ===========================================================================

register(ApiEntry(
    api_name="stock_basic",
    label="股票基础列表",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["name", "market", "is_st", "updated_at"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_premarket",
    label="每日股本盘前",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.SPECIAL,
    target_table="stk_premarket",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="trade_cal",
    label="交易日历",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="trade_calendar",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["exchange", "cal_date"],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stock_st",
    label="ST股票列表",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stock_st",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="st",
    label="ST风险警示板",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.ADVANCED,
    target_table="st_warning",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "imp_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"use_trade_date_loop": True},
))

register(ApiEntry(
    api_name="stock_hsgt",
    label="沪深港通股票列表",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stock_hsgt",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.HS_TYPE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="namechange",
    label="股票曾用名",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_namechange",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "start_date"],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stock_company",
    label="上市公司基本信息",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_company",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code"],
    conflict_action="do_update",
    update_columns=["chairman", "manager", "secretary", "reg_capital", "province", "city", "website"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_managers",
    label="上市公司管理层",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_managers",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "name", "begin_date"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_rewards",
    label="管理层薪酬",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_rewards",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "ann_date", "name"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="bse_mapping",
    label="北交所新旧代码对照",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="bse_mapping",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    field_mappings=[
        FieldMapping(source="o_code", target="old_code"),
        FieldMapping(source="n_code", target="new_code"),
    ],
))

register(ApiEntry(
    api_name="new_share",
    label="IPO新股上市",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="new_share",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code"],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="bak_basic",
    label="备用基础信息",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["updated_at"],
    rate_limit_group=RateLimitGroup.KLINE,
))


# ===========================================================================
# 股票数据 — 行情数据低频（13个接口）
# 需求：4.1-4.15
# ===========================================================================

register(ApiEntry(
    api_name="daily",
    label="日线行情",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
    extra_config={"freq": "1d"},
))

register(ApiEntry(
    api_name="weekly",
    label="周线行情",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
    extra_config={"freq": "1w"},
))

register(ApiEntry(
    api_name="monthly",
    label="月线行情",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
    extra_config={"freq": "1M"},
))

register(ApiEntry(
    api_name="stk_weekly_monthly",
    label="周/月行情每日更新",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE, ParamType.FREQ],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
))

register(ApiEntry(
    api_name="adj_factor",
    label="复权因子",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="adjustment_factor",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
))

register(ApiEntry(
    api_name="daily_basic",
    label="每日指标",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["pe_ttm", "pb", "market_cap", "updated_at"],
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
    field_mappings=[
        FieldMapping(source="total_mv", target="market_cap"),
    ],
))

register(ApiEntry(
    api_name="stk_limit",
    label="每日涨跌停价格",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="stk_limit",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="suspend_d",
    label="每日停复牌信息",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="suspend_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "suspend_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=150,
    field_mappings=[
        FieldMapping(source="trade_date", target="suspend_date"),
    ],
))

register(ApiEntry(
    api_name="hsgt_top10",
    label="沪深股通十大成交股",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="hsgt_top10",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "market_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=150,
))

register(ApiEntry(
    api_name="ggt_top10",
    label="港股通十大成交股",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="ggt_top10",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "market_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"use_trade_date_loop": True},
))

register(ApiEntry(
    api_name="ggt_daily",
    label="港股通每日成交统计",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="ggt_daily",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=365,
))

register(ApiEntry(
    api_name="ggt_monthly",
    label="港股通每月成交统计",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.ADVANCED,
    target_table="ggt_monthly",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["month"],
    conflict_action="do_nothing",
    optional_params=[ParamType.MONTH_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    field_mappings=[
        FieldMapping(source="total_buy_amt", target="buy_amount"),
        FieldMapping(source="total_buy_vol", target="buy_volume"),
        FieldMapping(source="total_sell_amt", target="sell_amount"),
        FieldMapping(source="total_sell_vol", target="sell_volume"),
    ],
))

register(ApiEntry(
    api_name="bak_daily",
    label="备用行情",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.ADVANCED,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"freq": "1d"},
))


# ===========================================================================
# 股票数据 — 行情数据中频（4个接口）
# 需求：4a.1-4a.9
# ===========================================================================

register(ApiEntry(
    api_name="stk_mins",
    label="历史分钟行情",
    category="stock_data",
    subcategory="行情数据（中频：分钟级/实时）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE, ParamType.FREQ],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
    batch_by_date=True,
    date_chunk_days=12,
))

register(ApiEntry(
    api_name="rt_k",
    label="实时日线",
    category="stock_data",
    subcategory="行情数据（中频：分钟级/实时）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"freq": "1d"},
))

register(ApiEntry(
    api_name="rt_min",
    label="实时分钟",
    category="stock_data",
    subcategory="行情数据（中频：分钟级/实时）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE, ParamType.FREQ],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="rt_min_daily",
    label="实时分钟日累计",
    category="stock_data",
    subcategory="行情数据（中频：分钟级/实时）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
))


# ===========================================================================
# 股票数据 — 财务数据（9个接口 + VIP 变体）
# 需求：5.1-5.11
# ===========================================================================

register(ApiEntry(
    api_name="income",
    label="利润表",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="financial_statement",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "report_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"report_type": "income"}, "jsonb_pack_column": "data_json", "jsonb_fixed_columns": ["ts_code", "ann_date", "end_date", "report_type"]},
    vip_variant="income_vip",
))

register(ApiEntry(
    api_name="balancesheet",
    label="资产负债表",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="financial_statement",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "report_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"report_type": "balance"}, "jsonb_pack_column": "data_json", "jsonb_fixed_columns": ["ts_code", "ann_date", "end_date", "report_type"]},
    vip_variant="balancesheet_vip",
))

register(ApiEntry(
    api_name="cashflow",
    label="现金流量表",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="financial_statement",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "report_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"report_type": "cashflow"}, "jsonb_pack_column": "data_json", "jsonb_fixed_columns": ["ts_code", "ann_date", "end_date", "report_type"]},
    vip_variant="cashflow_vip",
))

register(ApiEntry(
    api_name="fina_indicator",
    label="财务指标",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["pe_ttm", "pb", "roe", "updated_at"],
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    vip_variant="fina_indicator_vip",
))

register(ApiEntry(
    api_name="dividend",
    label="分红送股",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="dividend",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "div_proc"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="forecast",
    label="业绩预告",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="forecast",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    vip_variant="forecast_vip",
))

register(ApiEntry(
    api_name="express",
    label="业绩快报",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="express",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    vip_variant="express_vip",
))

register(ApiEntry(
    api_name="fina_mainbz",
    label="主营业务构成",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="fina_mainbz",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "bz_item"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    vip_variant="fina_mainbz_vip",
))

register(ApiEntry(
    api_name="disclosure_date",
    label="财报披露日期表",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="disclosure_date",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

# --- VIP 批量接口变体（使用 advanced 权限级别 Token） ---

register(ApiEntry(
    api_name="income_vip",
    label="利润表（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="financial_statement",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "report_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"report_type": "income"}, "jsonb_pack_column": "data_json", "jsonb_fixed_columns": ["ts_code", "ann_date", "end_date", "report_type"]},
))

register(ApiEntry(
    api_name="balancesheet_vip",
    label="资产负债表（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="financial_statement",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "report_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"report_type": "balance"}, "jsonb_pack_column": "data_json", "jsonb_fixed_columns": ["ts_code", "ann_date", "end_date", "report_type"]},
))

register(ApiEntry(
    api_name="cashflow_vip",
    label="现金流量表（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="financial_statement",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "report_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"report_type": "cashflow"}, "jsonb_pack_column": "data_json", "jsonb_fixed_columns": ["ts_code", "ann_date", "end_date", "report_type"]},
))

register(ApiEntry(
    api_name="fina_indicator_vip",
    label="财务指标（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["pe_ttm", "pb", "roe", "updated_at"],
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="forecast_vip",
    label="业绩预告（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="forecast",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="express_vip",
    label="业绩快报（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="express",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="fina_mainbz_vip",
    label="主营业务构成（VIP批量）",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.ADVANCED,
    target_table="fina_mainbz",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "bz_item"],
    conflict_action="do_nothing",
    required_params=[ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))


# ===========================================================================
# 股票数据 — 参考数据（12个接口）
# 需求：6.1-6.13
# ===========================================================================

register(ApiEntry(
    api_name="stk_shock",
    label="个股异常波动",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_shock",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "shock_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=300,
))

register(ApiEntry(
    api_name="stk_high_shock",
    label="个股严重异常波动",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_high_shock",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "shock_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=365,
))

register(ApiEntry(
    api_name="stk_alert",
    label="交易所重点提示证券",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_alert",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=300,
    field_mappings=[
        FieldMapping(source="type", target="alert_type"),
    ],
))

register(ApiEntry(
    api_name="top10_holders",
    label="前十大股东",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="top_holders",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "holder_name", "holder_type"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"holder_type": "top10"},
))

register(ApiEntry(
    api_name="top10_floatholders",
    label="前十大流通股东",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="top_holders",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date", "holder_name", "holder_type"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.REPORT_PERIOD],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"holder_type": "float"},
))

register(ApiEntry(
    api_name="pledge_stat",
    label="股权质押统计",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="pledge_stat",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=4,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 500},
))

register(ApiEntry(
    api_name="pledge_detail",
    label="股权质押明细",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="pledge_detail",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=15,
))

register(ApiEntry(
    api_name="repurchase",
    label="股票回购",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="repurchase",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=60,
))

register(ApiEntry(
    api_name="share_float",
    label="限售股解禁",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="share_float",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=60,
))

register(ApiEntry(
    api_name="block_trade",
    label="大宗交易",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="block_trade",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "buyer", "seller"],
    conflict_action="do_nothing",
    optional_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=30,
))

register(ApiEntry(
    api_name="stk_holdernumber",
    label="股东人数",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_holdernumber",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "end_date"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=10,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 200},
))

register(ApiEntry(
    api_name="stk_holdertrade",
    label="股东增减持",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_holdertrade",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "ann_date", "holder_name"],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    field_mappings=[
        FieldMapping(source="after_share", target="after_vol"),
    ],
))


# ===========================================================================
# 股票数据 — 特色数据（13个接口）
# 需求：7.1-7.15
# ===========================================================================

register(ApiEntry(
    api_name="report_rc",
    label="券商盈利预测",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.PREMIUM,
    target_table="report_rc",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_2,
    batch_by_date=True,
    date_chunk_days=30,
))

register(ApiEntry(
    api_name="cyq_perf",
    label="每日筹码及胜率",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="cyq_perf",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="cyq_chips",
    label="每日筹码分布",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="cyq_chips",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="stk_factor_pro",
    label="股票技术面因子专业版",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_factor",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_update",
    update_columns=["close", "macd_dif", "macd_dea", "macd", "kdj_k", "kdj_d", "kdj_j",
                     "rsi_6", "rsi_12", "rsi_24", "boll_upper", "boll_mid", "boll_lower", "cci"],
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
    field_mappings=[
        FieldMapping(source="macd_dif_bfq", target="macd_dif"),
        FieldMapping(source="macd_dea_bfq", target="macd_dea"),
        FieldMapping(source="macd_bfq", target="macd"),
        FieldMapping(source="kdj_k_bfq", target="kdj_k"),
        FieldMapping(source="kdj_d_bfq", target="kdj_d"),
        FieldMapping(source="kdj_bfq", target="kdj_j"),
        FieldMapping(source="rsi_bfq_6", target="rsi_6"),
        FieldMapping(source="rsi_bfq_12", target="rsi_12"),
        FieldMapping(source="rsi_bfq_24", target="rsi_24"),
        FieldMapping(source="boll_upper_bfq", target="boll_upper"),
        FieldMapping(source="boll_mid_bfq", target="boll_mid"),
        FieldMapping(source="boll_lower_bfq", target="boll_lower"),
        FieldMapping(source="cci_bfq", target="cci"),
        FieldMapping(source="wr_bfq", target="wr"),
        FieldMapping(source="dmi_pdi_bfq", target="dmi"),
        FieldMapping(source="trix_bfq", target="trix"),
        FieldMapping(source="bias1_bfq", target="bias"),
    ],
))

register(ApiEntry(
    api_name="ccass_hold",
    label="中央结算系统持股统计",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="ccass_hold",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=15,
    field_mappings=[
        FieldMapping(source="name", target="participant_name"),
        FieldMapping(source="shareholding", target="hold_amount"),
    ],
))

register(ApiEntry(
    api_name="ccass_hold_detail",
    label="中央结算系统持股明细",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.PREMIUM,
    target_table="ccass_hold_detail",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=15,
))

register(ApiEntry(
    api_name="hk_hold",
    label="沪深股通持股明细",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="hk_hold",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "exchange"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="stk_auction_o",
    label="股票开盘集合竞价",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.SPECIAL,
    target_table="stk_auction_o",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.TIER_20,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"max_rows": 10000, "estimated_daily_rows": 5500},
))

register(ApiEntry(
    api_name="stk_auction_c",
    label="股票收盘集合竞价",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.SPECIAL,
    target_table="stk_auction_c",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.TIER_20,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"max_rows": 10000, "estimated_daily_rows": 5500},
))

register(ApiEntry(
    api_name="stk_nineturn",
    label="神奇九转指标",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_nineturn",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "turn_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=60,
))

register(ApiEntry(
    api_name="stk_ah_comparison",
    label="AH股比价",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_ah_comparison",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    batch_by_date=True,
    date_chunk_days=30,
    field_mappings=[
        FieldMapping(source="close", target="a_close"),
        FieldMapping(source="hk_close", target="h_close"),
        FieldMapping(source="ah_premium", target="ah_ratio"),
    ],
))

register(ApiEntry(
    api_name="stk_surv",
    label="机构调研数据",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="stk_surv",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_80,
    batch_by_date=True,
    date_chunk_days=60,
    field_mappings=[
        FieldMapping(source="rece_org", target="fund_name"),
        FieldMapping(source="org_type", target="surv_type"),
        FieldMapping(source="fund_visitors", target="participants"),
    ],
))

register(ApiEntry(
    api_name="broker_recommend",
    label="券商每月金股",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.ADVANCED,
    target_table="broker_recommend",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.MONTH_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))


# ===========================================================================
# 股票数据 — 两融及转融通（4个接口）
# 需求：8.1-8.6
# ===========================================================================

register(ApiEntry(
    api_name="margin",
    label="融资融券汇总",
    category="stock_data",
    subcategory="两融及转融通",
    token_tier=TokenTier.BASIC,
    target_table="margin_data",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "exchange_id"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_date=True,
    date_chunk_days=365,
))

register(ApiEntry(
    api_name="margin_detail",
    label="融资融券交易明细",
    category="stock_data",
    subcategory="两融及转融通",
    token_tier=TokenTier.BASIC,
    target_table="margin_detail",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
))

register(ApiEntry(
    api_name="margin_secs",
    label="融资融券标的盘前",
    category="stock_data",
    subcategory="两融及转融通",
    token_tier=TokenTier.BASIC,
    target_table="margin_secs",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
))

register(ApiEntry(
    api_name="slb_len",
    label="转融资交易汇总",
    category="stock_data",
    subcategory="两融及转融通",
    token_tier=TokenTier.BASIC,
    target_table="slb_len",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_date=True,
    date_chunk_days=365,
))


# ===========================================================================
# 股票数据 — 资金流向数据（8个接口）
# 需求：9.1-9.10
# ===========================================================================

register(ApiEntry(
    api_name="moneyflow",
    label="个股资金流向",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.BASIC,
    target_table="tushare_moneyflow",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
))

register(ApiEntry(
    api_name="moneyflow_ths",
    label="个股资金流向THS",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.ADVANCED,
    target_table="moneyflow_ths",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_code=True,
    field_mappings=[
        FieldMapping(source="net_amount", target="net_mf_amount"),
    ],
))

register(ApiEntry(
    api_name="moneyflow_dc",
    label="个股资金流向DC",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.ADVANCED,
    target_table="moneyflow_dc",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_code=True,
    field_mappings=[
        FieldMapping(source="net_amount", target="net_mf_amount"),
    ],
))

register(ApiEntry(
    api_name="moneyflow_cnt_ths",
    label="板块资金流向THS",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.ADVANCED,
    target_table="moneyflow_cnt_ths",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_date=True,
    date_chunk_days=7,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 300},
    field_mappings=[
        FieldMapping(source="net_buy_amount", target="buy_amount"),
        FieldMapping(source="net_sell_amount", target="sell_amount"),
    ],
))

register(ApiEntry(
    api_name="moneyflow_ind_ths",
    label="行业资金流向THS",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.ADVANCED,
    target_table="moneyflow_ind",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "industry_name", "data_source"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_80,
    batch_by_date=True,
    date_chunk_days=75,
    extra_config={"inject_fields": {"data_source": "THS"}, "max_rows": 3000, "estimated_daily_rows": 30},
    field_mappings=[
        FieldMapping(source="industry", target="industry_name"),
        FieldMapping(source="net_buy_amount", target="buy_amount"),
        FieldMapping(source="net_sell_amount", target="sell_amount"),
    ],
))

register(ApiEntry(
    api_name="moneyflow_ind_dc",
    label="板块资金流向DC",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.ADVANCED,
    target_table="moneyflow_ind",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "industry_name", "data_source"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_80,
    batch_by_date=True,
    date_chunk_days=75,
    extra_config={"inject_fields": {"data_source": "DC"}, "max_rows": 3000, "estimated_daily_rows": 30},
    field_mappings=[FieldMapping(source="name", target="industry_name")],
))

register(ApiEntry(
    api_name="moneyflow_mkt_dc",
    label="大盘资金流向DC",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.ADVANCED,
    target_table="moneyflow_mkt_dc",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_date=True,
    date_chunk_days=365,
    field_mappings=[
        FieldMapping(source="net_amount", target="net_mf_amount"),
        FieldMapping(source="net_amount_rate", target="net_mf_amount_rate"),
        FieldMapping(source="close_sh", target="close"),
        FieldMapping(source="pct_change_sh", target="pct_change"),
    ],
))

register(ApiEntry(
    api_name="moneyflow_hsgt",
    label="沪港通资金流向",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.BASIC,
    target_table="moneyflow_hsgt",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_date=True,
    date_chunk_days=365,
))


# ===========================================================================
# 股票数据 — 打板专题数据（24个接口）
# 需求：10.1-10.25
# ===========================================================================

register(ApiEntry(
    api_name="top_list",
    label="龙虎榜每日统计单",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="top_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "reason"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"use_trade_date_loop": True},
))

register(ApiEntry(
    api_name="top_inst",
    label="龙虎榜机构交易单",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="top_inst",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "exalter"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"use_trade_date_loop": True},
))

register(ApiEntry(
    api_name="limit_list_ths",
    label="同花顺涨跌停榜单",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.PREMIUM,
    target_table="limit_list_ths",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "limit"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_60,
    batch_by_date=True,
    date_chunk_days=10,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 200},
))

register(ApiEntry(
    api_name="limit_list_d",
    label="涨跌停和炸板数据",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="limit_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "limit"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_80,
    batch_by_date=True,
    date_chunk_days=10,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 200},
))

register(ApiEntry(
    api_name="limit_step",
    label="涨停股票连板天梯",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.PREMIUM,
    target_table="limit_step",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_10,
    batch_by_date=True,
    date_chunk_days=75,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 30},
))

register(ApiEntry(
    api_name="limit_cpt_list",
    label="涨停最强板块统计",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.PREMIUM,
    target_table="limit_cpt_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=100,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 20},
))

register(ApiEntry(
    api_name="ths_index",
    label="同花顺行业概念板块",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["name", "sector_type"],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"inject_fields": {"data_source": "THS"}},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="type", target="sector_type"),
        FieldMapping(source="count", target="constituent_count"),
    ],
))

register(ApiEntry(
    api_name="ths_daily",
    label="同花顺行业概念指数行情",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.TIER_60,
    batch_by_date=True,
    date_chunk_days=2,
    extra_config={"data_source": "THS", "max_rows": 3000, "estimated_daily_rows": 500},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="vol", target="volume"),
        FieldMapping(source="turnover_rate", target="turnover"),
        FieldMapping(source="pct_change", target="change_pct"),
    ],
))

register(ApiEntry(
    api_name="ths_member",
    label="同花顺行业概念成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,  # 确保 symbol 为 6 位数字
    conflict_columns=["trade_date", "sector_code", "data_source", "symbol"],
    conflict_action="do_nothing",
    optional_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.TIER_60,
    batch_by_sector=True,  # 按板块代码遍历导入
    extra_config={"inject_fields": {"data_source": "THS", "trade_date": "19000101"}},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="con_code", target="symbol"),
        FieldMapping(source="con_name", target="stock_name"),
    ],
))

register(ApiEntry(
    api_name="dc_index",
    label="东方财富概念板块",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["name", "sector_type"],
    rate_limit_group=RateLimitGroup.TIER_60,
    extra_config={"inject_fields": {"data_source": "DC"}},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="idx_type", target="sector_type"),
    ],
))

register(ApiEntry(
    api_name="dc_member",
    label="东方财富概念成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,  # 确保 symbol 为 6 位数字
    conflict_columns=["trade_date", "sector_code", "data_source", "symbol"],
    conflict_action="do_nothing",
    optional_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_sector=True,  # 按板块代码遍历导入
    extra_config={"inject_fields": {"data_source": "DC", "trade_date": "19000101"}},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="con_code", target="symbol"),
        FieldMapping(source="name", target="stock_name"),
    ],
))

register(ApiEntry(
    api_name="dc_daily",
    label="东方财富概念板块行情",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.TIER_60,
    batch_by_date=True,
    date_chunk_days=2,
    extra_config={"data_source": "DC", "max_rows": 3000, "estimated_daily_rows": 500},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="vol", target="volume"),
        FieldMapping(source="turnover_rate", target="turnover"),
        FieldMapping(source="pct_change", target="change_pct"),
    ],
))

register(ApiEntry(
    api_name="stk_auction",
    label="开盘竞价成交当日",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.SPECIAL,
    target_table="stk_auction",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.TIER_10,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"max_rows": 10000, "estimated_daily_rows": 5500},
))

register(ApiEntry(
    api_name="hm_list",
    label="市场游资名录",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="hm_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["hm_name"],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    field_mappings=[
        FieldMapping(source="name", target="hm_name"),
        FieldMapping(source="desc", target="description"),
    ],
))

register(ApiEntry(
    api_name="hm_detail",
    label="游资交易每日明细",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.PREMIUM,
    target_table="hm_detail",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "hm_name"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=30,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 50},
))

register(ApiEntry(
    api_name="ths_hot",
    label="同花顺热榜",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="ths_hot",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=30,
    field_mappings=[
        FieldMapping(source="ts_name", target="name"),
        FieldMapping(source="hot", target="hot_value"),
        FieldMapping(source="pct_change", target="pct_chg"),
    ],
))

register(ApiEntry(
    api_name="dc_hot",
    label="东方财富热榜",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.PREMIUM,
    target_table="dc_hot",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=30,
    field_mappings=[
        FieldMapping(source="ts_name", target="name"),
        FieldMapping(source="hot", target="hot_value"),
        FieldMapping(source="pct_change", target="pct_chg"),
    ],
))

register(ApiEntry(
    api_name="tdx_index",
    label="通达信板块信息",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["name", "sector_type"],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    extra_config={"inject_fields": {"data_source": "TDX"}},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="idx_type", target="sector_type"),
        FieldMapping(source="idx_count", target="constituent_count"),
    ],
))

register(ApiEntry(
    api_name="tdx_member",
    label="通达信板块成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["trade_date", "sector_code", "data_source", "symbol"],
    conflict_action="do_nothing",
    optional_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_sector=True,
    extra_config={"inject_fields": {"data_source": "TDX", "trade_date": "19000101"}},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="con_code", target="symbol"),
        FieldMapping(source="con_name", target="stock_name"),
    ],
))

register(ApiEntry(
    api_name="tdx_daily",
    label="通达信板块行情",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=2,
    extra_config={"data_source": "TDX", "max_rows": 3000, "estimated_daily_rows": 200},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="vol", target="volume"),
        FieldMapping(source="turnover_rate", target="turnover"),
        FieldMapping(source="pct_change", target="change_pct"),
    ],
))

register(ApiEntry(
    api_name="kpl_list",
    label="开盘啦榜单数据",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="kpl_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    batch_by_date=True,
    date_chunk_days=30,
))

register(ApiEntry(
    api_name="kpl_concept_cons",
    label="开盘啦题材成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="kpl_concept_cons",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.CONCEPT_CODE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    field_mappings=[
        FieldMapping(source="ts_code", target="concept_code"),
        FieldMapping(source="con_code", target="ts_code"),
        FieldMapping(source="con_name", target="name"),
    ],
))

register(ApiEntry(
    api_name="dc_concept",
    label="东方财富题材库",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="dc_concept",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    field_mappings=[
        FieldMapping(source="theme_code", target="concept_code"),
        FieldMapping(source="name", target="concept_name"),
    ],
))

register(ApiEntry(
    api_name="dc_concept_cons",
    label="东方财富题材成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="dc_concept_cons",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.CONCEPT_CODE],
    rate_limit_group=RateLimitGroup.LIMIT_UP,
    field_mappings=[FieldMapping(source="theme_code", target="concept_code")],
))


# ===========================================================================
# 指数专题 — 指数基本信息（1个接口）
# 需求：11.3
# ===========================================================================

register(ApiEntry(
    api_name="index_basic",
    label="指数基本信息",
    category="index_data",
    subcategory="指数基本信息",
    token_tier=TokenTier.BASIC,
    target_table="index_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code"],
    conflict_action="do_update",
    update_columns=["name", "market", "publisher", "category", "base_date", "base_point", "list_date"],
    optional_params=[ParamType.MARKET],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

# ===========================================================================
# 指数专题 — 指数行情低频（3个接口）
# 需求：12.1-12.7
# ===========================================================================

register(ApiEntry(
    api_name="index_daily",
    label="指数日线行情",
    category="index_data",
    subcategory="指数行情数据（低频：日线/周线/月线）",
    token_tier=TokenTier.ADVANCED,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
    extra_config={"freq": "1d", "max_rows": 8000},
))

register(ApiEntry(
    api_name="index_weekly",
    label="指数周线行情",
    category="index_data",
    subcategory="指数行情数据（低频：日线/周线/月线）",
    token_tier=TokenTier.BASIC,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"freq": "1w", "max_rows": 1000, "use_trade_date_loop": True},
))

register(ApiEntry(
    api_name="index_monthly",
    label="指数月线行情",
    category="index_data",
    subcategory="指数行情数据（低频：日线/周线/月线）",
    token_tier=TokenTier.BASIC,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"freq": "1M", "max_rows": 1000, "use_trade_date_loop": True},
))

# ===========================================================================
# 指数专题 — 指数行情中频（4个接口）
# 需求：12a.1-12a.10
# ===========================================================================

register(ApiEntry(
    api_name="rt_idx_k",
    label="指数实时日线",
    category="index_data",
    subcategory="指数行情数据（中频：实时日线/实时分钟/历史分钟）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"freq": "1d"},
))

register(ApiEntry(
    api_name="rt_idx_min",
    label="指数实时分钟",
    category="index_data",
    subcategory="指数行情数据（中频：实时日线/实时分钟/历史分钟）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"max_rows": 1000},
))

register(ApiEntry(
    api_name="rt_idx_min_daily",
    label="指数实时分钟日累计",
    category="index_data",
    subcategory="指数行情数据（中频：实时日线/实时分钟/历史分钟）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
))

register(ApiEntry(
    api_name="idx_mins",
    label="指数历史分钟行情",
    category="index_data",
    subcategory="指数行情数据（中频：实时日线/实时分钟/历史分钟）",
    token_tier=TokenTier.SPECIAL,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE, ParamType.INDEX_CODE, ParamType.FREQ],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"max_rows": 8000},
))

# ===========================================================================
# 指数专题 — 指数成分和权重（1个接口）
# 需求：13.1-13.5
# ===========================================================================

register(ApiEntry(
    api_name="index_weight",
    label="指数成分权重",
    category="index_data",
    subcategory="指数成分和权重",
    token_tier=TokenTier.ADVANCED,
    target_table="index_weight",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["index_code", "con_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.INDEX_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
))

# ===========================================================================
# 指数专题 — 申万行业数据（4个接口）
# 需求：14.1-14.7
# ===========================================================================

register(ApiEntry(
    api_name="index_classify",
    label="申万行业分类",
    category="index_data",
    subcategory="申万行业数据（分类/成分/日线行情/实时行情）",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["name", "sector_type"],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"inject_fields": {"data_source": "TI"}},
    field_mappings=[
        FieldMapping(source="index_code", target="sector_code"),
        FieldMapping(source="industry_name", target="name"),
        FieldMapping(source="level", target="sector_type"),
    ],
))

register(ApiEntry(
    api_name="index_member_all",
    label="申万行业成分（分级）",
    category="index_data",
    subcategory="申万行业数据（分类/成分/日线行情/实时行情）",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "sector_code", "data_source", "symbol"],
    conflict_action="do_nothing",
    optional_params=[ParamType.SECTOR_CODE, ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"data_source": "TI"}, "max_rows": 2000},
    field_mappings=[
        FieldMapping(source="ts_code", target="symbol"),
        FieldMapping(source="name", target="stock_name"),
        FieldMapping(source="l1_code", target="sector_code"),
        FieldMapping(source="in_date", target="trade_date"),
    ],
))

register(ApiEntry(
    api_name="sw_daily",
    label="申万行业指数日行情",
    category="index_data",
    subcategory="申万行业数据（分类/成分/日线行情/实时行情）",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=10,
    extra_config={"data_source": "TI", "max_rows": 4000, "estimated_daily_rows": 200},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="vol", target="volume"),
        FieldMapping(source="turnover_rate", target="turnover"),
        FieldMapping(source="pct_change", target="change_pct"),
    ],
))

register(ApiEntry(
    api_name="rt_sw_k",
    label="申万实时行情",
    category="index_data",
    subcategory="申万行业数据（分类/成分/日线行情/实时行情）",
    token_tier=TokenTier.SPECIAL,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"data_source": "TI"},
))

# ===========================================================================
# 指数专题 — 中信行业数据（2个接口）
# 需求：15.1-15.5
# ===========================================================================

register(ApiEntry(
    api_name="ci_index_member",
    label="中信行业成分",
    category="index_data",
    subcategory="中信行业数据（成分/日线行情）",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "sector_code", "data_source", "symbol"],
    conflict_action="do_nothing",
    optional_params=[ParamType.SECTOR_CODE, ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"inject_fields": {"data_source": "CI"}, "max_rows": 5000},
    field_mappings=[
        FieldMapping(source="ts_code", target="symbol"),
        FieldMapping(source="name", target="stock_name"),
        FieldMapping(source="l1_code", target="sector_code"),
        FieldMapping(source="in_date", target="trade_date"),
    ],
))

register(ApiEntry(
    api_name="ci_daily",
    label="中信行业指数日行情",
    category="index_data",
    subcategory="中信行业数据（成分/日线行情）",
    token_tier=TokenTier.ADVANCED,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=10,
    extra_config={"data_source": "CI", "max_rows": 4000, "estimated_daily_rows": 300},
    field_mappings=[
        FieldMapping(source="ts_code", target="sector_code"),
        FieldMapping(source="vol", target="volume"),
        FieldMapping(source="turnover_rate", target="turnover"),
        FieldMapping(source="pct_change", target="change_pct"),
    ],
))

# ===========================================================================
# 指数专题 — 大盘指数每日指标（1个接口）
# 需求：16.1-16.5
# ===========================================================================

register(ApiEntry(
    api_name="index_dailybasic",
    label="大盘指数每日指标",
    category="index_data",
    subcategory="大盘指数每日指标",
    token_tier=TokenTier.BASIC,
    target_table="index_dailybasic",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=45,
    extra_config={"max_rows": 3000, "estimated_daily_rows": 50},
))

# ===========================================================================
# 指数专题 — 指数技术面因子（1个接口）
# 需求：17.1-17.5
# ===========================================================================

register(ApiEntry(
    api_name="idx_factor_pro",
    label="指数技术面因子（专业版）",
    category="index_data",
    subcategory="指数技术面因子（专业版）",
    token_tier=TokenTier.ADVANCED,
    target_table="index_tech",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=1,
    extra_config={"max_rows": 8000, "estimated_daily_rows": 50, "use_trade_date_loop": True},
))

# ===========================================================================
# 指数专题 — 沪深市场每日交易统计（2个接口）
# 需求：18.1-18.4
# ===========================================================================

register(ApiEntry(
    api_name="daily_info",
    label="沪深市场每日交易统计",
    category="index_data",
    subcategory="沪深市场每日交易统计",
    token_tier=TokenTier.BASIC,
    target_table="market_daily_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "exchange", "ts_code"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=300,
    extra_config={"max_rows": 4000, "estimated_daily_rows": 10},
))

register(ApiEntry(
    api_name="sz_daily_info",
    label="深圳市场每日交易情况",
    category="index_data",
    subcategory="深圳市场每日交易情况",
    token_tier=TokenTier.ADVANCED,
    target_table="sz_daily_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=365,
    extra_config={"max_rows": 2000},
))

# ===========================================================================
# 指数专题 — 国际主要指数（1个接口）
# 需求：19.1-19.4
# ===========================================================================

register(ApiEntry(
    api_name="index_global",
    label="国际主要指数",
    category="index_data",
    subcategory="国际主要指数",
    token_tier=TokenTier.ADVANCED,
    target_table="index_global",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_date=True,
    date_chunk_days=100,
    extra_config={"max_rows": 4000, "estimated_daily_rows": 30},
))
