"""
Tushare API 接口注册表

以声明式方式定义每个 Tushare 接口的元数据，包括：
- 接口名称、中文说明、所属分类
- Token 权限级别（basic/advanced/special）
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
    """Token 权限级别"""

    BASIC = "basic"
    ADVANCED = "advanced"
    SPECIAL = "special"


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


class RateLimitGroup(str, Enum):
    """频率限制分组"""

    KLINE = "kline"  # 0.18s
    FUNDAMENTALS = "fundamentals"  # 0.40s
    MONEY_FLOW = "money_flow"  # 0.30s


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
    extra_config: dict = field(default_factory=dict)  # 额外配置（如 freq 映射）


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


# ===========================================================================
# 股票数据 — 基础数据
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
    api_name="stock_st",
    label="ST股票列表",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_st",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_delist",
    label="退市股票列表",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["is_delisted", "delist_date", "updated_at"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="daily_share",
    label="每日股本（盘前）",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="daily_share",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="bak_basic",
    label="备用基础信息",
    category="stock_data",
    subcategory="基础数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["updated_at"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))


# ===========================================================================
# 股票数据 — 行情数据（低频：日K/周K/月K）
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
    api_name="adj_factor",
    label="复权因子",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="adjustment_factor",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
))

register(ApiEntry(
    api_name="daily_basic",
    label="每日基本指标",
    category="stock_data",
    subcategory="行情数据（低频：日K/周K/月K）",
    token_tier=TokenTier.BASIC,
    target_table="stock_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["symbol"],
    conflict_action="do_update",
    update_columns=["turnover_rate", "pe_ttm", "pb", "total_mv", "float_mv", "updated_at"],
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
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
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

# ===========================================================================
# 股票数据 — 行情数据（中频：分钟级）
# ===========================================================================

register(ApiEntry(
    api_name="stk_mins",
    label="历史分钟行情",
    category="stock_data",
    subcategory="行情数据（中频：分钟级）",
    token_tier=TokenTier.ADVANCED,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.STOCK_SYMBOL,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE, ParamType.FREQ],
    rate_limit_group=RateLimitGroup.KLINE,
    batch_by_code=True,
))


# ===========================================================================
# 股票数据 — 财务数据
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
    extra_config={"report_type": "income"},
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
    extra_config={"report_type": "balance"},
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
    extra_config={"report_type": "cashflow"},
))

register(ApiEntry(
    api_name="fina_indicator",
    label="财务指标数据",
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
))

register(ApiEntry(
    api_name="dividend",
    label="分红送股数据",
    category="stock_data",
    subcategory="财务数据",
    token_tier=TokenTier.BASIC,
    target_table="dividend",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
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
))

# ===========================================================================
# 股票数据 — 参考数据
# ===========================================================================

register(ApiEntry(
    api_name="stock_company",
    label="上市公司基本信息",
    category="stock_data",
    subcategory="参考数据",
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
    api_name="namechange",
    label="股票曾用名",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="stock_namechange",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="hs_const",
    label="沪深股通成份股",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="hs_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.HS_TYPE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_rewards",
    label="管理层薪酬和持股",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_rewards",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_managers",
    label="上市公司管理层",
    category="stock_data",
    subcategory="参考数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_managers",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))


# ===========================================================================
# 股票数据 — 特色数据
# ===========================================================================

register(ApiEntry(
    api_name="top10_holders",
    label="前十大股东",
    category="stock_data",
    subcategory="特色数据",
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
    subcategory="特色数据",
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
    api_name="stk_holdernumber",
    label="股东人数",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_holdernumber",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_holdertrade",
    label="股东增减持",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_holdertrade",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="block_trade",
    label="大宗交易",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="block_trade",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "buyer", "seller"],
    conflict_action="do_nothing",
    optional_params=[ParamType.DATE_RANGE, ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_account",
    label="股票开户数据",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_account",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    optional_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_limit",
    label="每日涨跌停价格",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_limit",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="stk_factor",
    label="股票技术面因子",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.BASIC,
    target_table="stk_factor",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
))

register(ApiEntry(
    api_name="stk_factor_pro",
    label="股票技术面因子（专业版）",
    category="stock_data",
    subcategory="特色数据",
    token_tier=TokenTier.SPECIAL,
    target_table="stk_factor",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_update",
    update_columns=["close", "macd_dif", "macd_dea", "macd", "kdj_k", "kdj_d", "kdj_j", "rsi_6", "rsi_12", "rsi_24", "boll_upper", "boll_mid", "boll_lower", "cci"],
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
))

# ===========================================================================
# 股票数据 — 两融及转融通
# ===========================================================================

register(ApiEntry(
    api_name="margin",
    label="融资融券交易汇总",
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
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
))

register(ApiEntry(
    api_name="margin_target",
    label="融资融券标的（盘前）",
    category="stock_data",
    subcategory="两融及转融通",
    token_tier=TokenTier.BASIC,
    target_table="margin_target",
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
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
))

register(ApiEntry(
    api_name="slb_sec",
    label="转融券交易汇总",
    category="stock_data",
    subcategory="两融及转融通",
    token_tier=TokenTier.BASIC,
    target_table="slb_sec",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
))


# ===========================================================================
# 股票数据 — 资金流向数据
# ===========================================================================

register(ApiEntry(
    api_name="moneyflow",
    label="个股资金流向",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.BASIC,
    target_table="tushare_money_flow",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.STOCK_CODE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    batch_by_code=True,
))

register(ApiEntry(
    api_name="moneyflow_hsgt",
    label="沪深港通资金流向",
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
))

register(ApiEntry(
    api_name="moneyflow_ind_dc",
    label="行业资金流向（东财）",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.BASIC,
    target_table="moneyflow_ind",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    extra_config={"data_source": "DC"},
))

register(ApiEntry(
    api_name="moneyflow_ind_ths",
    label="行业资金流向（同花顺）",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.BASIC,
    target_table="moneyflow_ind",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
    extra_config={"data_source": "THS"},
))

register(ApiEntry(
    api_name="moneyflow_mkt_dc",
    label="大盘资金流向（东财）",
    category="stock_data",
    subcategory="资金流向数据",
    token_tier=TokenTier.BASIC,
    target_table="moneyflow_mkt_dc",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.MONEY_FLOW,
))

# ===========================================================================
# 股票数据 — 打板专题数据
# ===========================================================================

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
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="limit_step",
    label="涨停股票连板天梯",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="limit_step",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="hm_list",
    label="游资名录",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="hm_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="hm_detail",
    label="游资每日明细",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.ADVANCED,
    target_table="hm_detail",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="top_list",
    label="龙虎榜每日明细",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="top_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "reason"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="top_inst",
    label="龙虎榜机构交易明细",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="top_inst",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code", "exalter"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="ths_limit",
    label="同花顺涨跌停榜单",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="ths_limit",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["ts_code", "trade_date", "limit"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="dc_hot",
    label="东方财富App热榜",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="dc_hot",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="ths_hot",
    label="同花顺App热榜",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="ths_hot",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

register(ApiEntry(
    api_name="ths_index",
    label="同花顺行业概念板块",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["sector_name", "sector_type"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"data_source": "THS"},
))

register(ApiEntry(
    api_name="ths_member",
    label="同花顺行业概念成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"data_source": "THS"},
))

register(ApiEntry(
    api_name="dc_index",
    label="东方财富概念板块",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["sector_name", "sector_type"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"data_source": "DC"},
))

register(ApiEntry(
    api_name="dc_member",
    label="东方财富概念成分",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_constituent",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.SECTOR_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"data_source": "DC"},
))

register(ApiEntry(
    api_name="kpl_list",
    label="开盘啦榜单数据",
    category="stock_data",
    subcategory="打板专题数据",
    token_tier=TokenTier.BASIC,
    target_table="kpl_list",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))


# ===========================================================================
# 指数专题 — 指数基本信息
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
# 指数专题 — 指数行情数据（低频：日线/周线/月线）
# ===========================================================================

register(ApiEntry(
    api_name="index_daily",
    label="指数日线行情",
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
    batch_by_code=True,
    extra_config={"freq": "1d"},
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
    extra_config={"freq": "1w"},
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
    extra_config={"freq": "1M"},
))

# ===========================================================================
# 指数专题 — 指数行情数据（中频：分钟级）
# ===========================================================================

register(ApiEntry(
    api_name="index_1min_realtime",
    label="指数实时分钟行情",
    category="index_data",
    subcategory="指数行情数据（中频：分钟级）",
    token_tier=TokenTier.ADVANCED,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"freq": "1m"},
))

register(ApiEntry(
    api_name="index_min",
    label="指数历史分钟行情",
    category="index_data",
    subcategory="指数行情数据（中频：分钟级）",
    token_tier=TokenTier.ADVANCED,
    target_table="kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["time", "symbol", "freq", "adj_type"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE, ParamType.INDEX_CODE, ParamType.FREQ],
    rate_limit_group=RateLimitGroup.KLINE,
))

# ===========================================================================
# 指数专题 — 指数成分和权重
# ===========================================================================

register(ApiEntry(
    api_name="index_weight",
    label="指数成分和权重",
    category="index_data",
    subcategory="指数成分和权重",
    token_tier=TokenTier.BASIC,
    target_table="index_weight",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["index_code", "con_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.INDEX_CODE, ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

# ===========================================================================
# 指数专题 — 申万行业数据
# ===========================================================================

register(ApiEntry(
    api_name="index_classify",
    label="申万行业分类",
    category="index_data",
    subcategory="申万行业数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["sector_code", "data_source"],
    conflict_action="do_update",
    update_columns=["sector_name", "sector_type"],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
    extra_config={"data_source": "TI"},
))

register(ApiEntry(
    api_name="sw_daily",
    label="申万行业指数日行情",
    category="index_data",
    subcategory="申万行业数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"data_source": "TI"},
))

# ===========================================================================
# 指数专题 — 中信行业数据
# ===========================================================================

register(ApiEntry(
    api_name="ci_daily",
    label="中信行业指数日行情",
    category="index_data",
    subcategory="中信行业数据",
    token_tier=TokenTier.BASIC,
    target_table="sector_kline",
    storage_engine=StorageEngine.TS,
    code_format=CodeFormat.NONE,
    conflict_columns=[],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
    extra_config={"data_source": "CI"},
))

# ===========================================================================
# 指数专题 — 大盘指数每日指标
# ===========================================================================

register(ApiEntry(
    api_name="index_dailybasic",
    label="大盘指数每日指标",
    category="index_data",
    subcategory="大盘指数每日指标",
    token_tier=TokenTier.ADVANCED,
    target_table="index_dailybasic",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.FUNDAMENTALS,
))

# ===========================================================================
# 指数专题 — 指数技术面因子
# ===========================================================================

register(ApiEntry(
    api_name="index_tech",
    label="指数技术面因子",
    category="index_data",
    subcategory="指数技术面因子",
    token_tier=TokenTier.SPECIAL,
    target_table="index_tech",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
))

# ===========================================================================
# 指数专题 — 沪深市场每日交易统计
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
))

# ===========================================================================
# 指数专题 — 深圳市场每日交易情况
# ===========================================================================

register(ApiEntry(
    api_name="sz_daily_info",
    label="深圳市场每日交易情况",
    category="index_data",
    subcategory="深圳市场每日交易情况",
    token_tier=TokenTier.BASIC,
    target_table="sz_daily_info",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.NONE,
    conflict_columns=["trade_date", "ts_code"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    rate_limit_group=RateLimitGroup.KLINE,
))

# ===========================================================================
# 指数专题 — 国际主要指数
# ===========================================================================

register(ApiEntry(
    api_name="index_global",
    label="国际主要指数",
    category="index_data",
    subcategory="国际主要指数",
    token_tier=TokenTier.BASIC,
    target_table="index_global",
    storage_engine=StorageEngine.PG,
    code_format=CodeFormat.INDEX_CODE,
    conflict_columns=["ts_code", "trade_date"],
    conflict_action="do_nothing",
    required_params=[ParamType.DATE_RANGE],
    optional_params=[ParamType.INDEX_CODE],
    rate_limit_group=RateLimitGroup.KLINE,
))
