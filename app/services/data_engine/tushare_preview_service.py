"""
Tushare 数据预览服务

提供已导入 Tushare 数据的只读查询功能，包括：
- 分页预览数据表内容
- 数据统计信息（总记录数、时间范围等）
- 导入日志查询
- 增量数据查询（基于最近一次成功导入的参数重建查询条件）

核心设计：
- 通过 ApiEntry.target_table + SQLAlchemy text() 构建动态只读 SELECT 查询
- 根据 ApiEntry.storage_engine 路由到 PostgreSQL 或 TimescaleDB
- 提供 _pure 静态方法用于属性测试，隔离数据库依赖
- TIME_FIELD_MAP 覆盖所有 70+ 个 target_table

对应需求：2.1, 2.4, 3.2, 4.1-4.4, 5.1-5.4, 6.2, 6.3, 7.2-7.5,
          8.1-8.6, 9.4, 10.1-10.4
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionPG, AsyncSessionTS
from app.models.tushare_import import TushareImportLog
from app.services.data_engine.tushare_registry import (
    ApiEntry,
    FieldMapping,
    StorageEngine,
    TUSHARE_API_REGISTRY,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic 响应模型
# ---------------------------------------------------------------------------


class ColumnInfo(BaseModel):
    """列信息"""

    name: str  # 数据库列名
    label: str  # 显示名称（来自 field_mappings 或列名本身）
    type: str  # 数据类型提示：string / number / date / datetime


class IncrementalInfo(BaseModel):
    """增量查询关联的导入记录信息"""

    import_log_id: int
    import_time: str  # 导入时间（started_at ISO 格式）
    record_count: int  # 该次导入的记录数
    status: str  # 导入状态
    params_summary: str  # 导入参数摘要（如 "2024-01-01 ~ 2024-12-31"）


class PreviewDataResponse(BaseModel):
    """预览数据响应"""

    columns: list[ColumnInfo]  # 列定义
    rows: list[dict[str, Any]]  # 数据行
    total: int  # 总记录数
    page: int  # 当前页码
    page_size: int  # 每页条数
    time_field: str | None  # 该表的时间字段名（用于前端图表 X 轴）
    chart_type: str | None  # 推荐图表类型：candlestick / line / None
    scope_info: str | None  # 共享表作用域提示
    incremental_info: IncrementalInfo | None  # 增量查询时的关联导入信息


class PreviewStatsResponse(BaseModel):
    """统计信息响应"""

    total_count: int  # 总记录数
    earliest_time: str | None  # 最早数据时间
    latest_time: str | None  # 最晚数据时间
    last_import_at: str | None  # 最近导入时间
    last_import_count: int  # 最近导入记录数


class ImportLogItem(BaseModel):
    """导入记录条目"""

    id: int
    api_name: str
    params_json: dict | None
    status: str
    record_count: int
    error_message: str | None
    started_at: str | None
    finished_at: str | None


class CompletenessReport(BaseModel):
    """完整性校验结果

    包含时序数据（基于交易日历）或非时序数据（基于代码集合）的完整性校验信息。
    """

    check_type: str  # 校验类型："time_series" / "code_based" / "unsupported"
    expected_count: int  # 预期数量
    actual_count: int  # 实际数量
    missing_count: int  # 缺失数量
    completeness_rate: float  # 完整率（0.0 ~ 1.0）
    missing_items: list[str]  # 缺失项列表（日期或代码）
    time_range: dict | None  # 校验时间范围，如 {"start": "20240101", "end": "20241231"}
    message: str | None  # 附加提示信息


class IntegrityRequest(BaseModel):
    """完整性校验请求体

    用于 POST /{api_name}/check-integrity 端点的请求参数。
    """

    data_time_start: str | None = None  # 数据时间范围起始
    data_time_end: str | None = None  # 数据时间范围结束


class ChartDataResponse(BaseModel):
    """图表数据响应

    独立于表格分页的图表数据，按时间升序排列，用于前端图表渲染。
    对于多股票共享表（如 kline），返回单只股票的时间序列数据。
    """

    rows: list[dict]  # 数据行（按时间升序）
    time_field: str | None  # 时间字段名
    chart_type: str | None  # 推荐图表类型：candlestick / line / bar / None
    columns: list[ColumnInfo]  # 列信息
    total_available: int  # 可用数据总量
    available_codes: list[str]  # 可选股票代码列表（多股票表时非空）
    selected_code: str | None  # 当前选中的股票代码（多股票表时非空）


class DeleteDataResponse(BaseModel):
    """数据删除响应"""

    deleted_count: int  # 删除的记录数
    target_table: str  # 目标表名
    time_field: str | None  # 使用的时间字段
    data_time_start: str | None  # 删除范围起始
    data_time_end: str | None  # 删除范围结束


# ---------------------------------------------------------------------------
# 常量：时间字段映射表
# ---------------------------------------------------------------------------

# 完整映射：覆盖所有 target_table
TIME_FIELD_MAP: dict[str, str] = {
    # ── 时序数据（TimescaleDB）──
    "kline": "time",
    "sector_kline": "time",
    "adjustment_factor": "trade_date",
    # ── 基础数据 ──
    "trade_calendar": "cal_date",
    "stock_st": "trade_date",
    "st_warning": "imp_date",
    "stk_premarket": "trade_date",
    "stock_hsgt": "in_date",
    "stock_namechange": "start_date",
    "stk_managers": "ann_date",
    "stk_rewards": "ann_date",
    "new_share": "ipo_date",
    "suspend_info": "suspend_date",
    # stock_info: 无主要时间字段（upsert 模式）
    # stock_company: 无主要时间字段
    # bse_mapping: 无主要时间字段
    # ── 行情数据 ──
    "stk_limit": "trade_date",
    "hsgt_top10": "trade_date",
    "ggt_top10": "trade_date",
    "ggt_daily": "trade_date",
    "ggt_monthly": "month",
    # ── 财务数据 ──
    "financial_statement": "ann_date",
    "dividend": "ann_date",
    "forecast": "ann_date",
    "express": "ann_date",
    "fina_mainbz": "end_date",
    "disclosure_date": "end_date",
    # ── 参考数据 ──
    "stk_shock": "trade_date",
    "stk_high_shock": "trade_date",
    "stk_alert": "trade_date",
    "top_holders": "end_date",
    "pledge_stat": "end_date",
    "pledge_detail": "ann_date",
    "repurchase": "ann_date",
    "share_float": "ann_date",
    "block_trade": "trade_date",
    "stk_holdernumber": "ann_date",
    "stk_holdertrade": "ann_date",
    # ── 特色数据 ──
    "report_rc": "report_date",
    "cyq_perf": "trade_date",
    "cyq_chips": "trade_date",
    "stk_factor": "trade_date",
    "ccass_hold": "trade_date",
    "ccass_hold_detail": "trade_date",
    "hk_hold": "trade_date",
    "stk_auction_o": "trade_date",
    "stk_auction_c": "trade_date",
    "stk_nineturn": "trade_date",
    "stk_ah_comparison": "trade_date",
    "stk_surv": "surv_date",
    "broker_recommend": "month",
    # ── 两融及转融通 ──
    "margin_data": "trade_date",
    "margin_detail": "trade_date",
    "margin_secs": "trade_date",
    "slb_len": "trade_date",
    # ── 资金流向 ──
    "tushare_moneyflow": "trade_date",
    "moneyflow_ths": "trade_date",
    "moneyflow_dc": "trade_date",
    "moneyflow_hsgt": "trade_date",
    "moneyflow_mkt_dc": "trade_date",
    "moneyflow_ind": "trade_date",
    "moneyflow_cnt_ths": "trade_date",
    # ── 打板专题 ──
    "top_list": "trade_date",
    "top_inst": "trade_date",
    "limit_list_ths": "trade_date",
    "limit_list": "trade_date",
    "limit_step": "trade_date",
    "limit_cpt_list": "trade_date",
    "stk_auction": "trade_date",
    "hm_detail": "trade_date",
    "ths_hot": "trade_date",
    "dc_hot": "trade_date",
    "kpl_list": "trade_date",
    # hm_list: 无时间字段（游资名录）
    # kpl_concept_cons: 无时间字段（题材成分）
    # dc_concept: 无时间字段（题材库）
    # dc_concept_cons: 无时间字段（题材成分）
    # ── 指数专题 ──
    "index_weight": "trade_date",
    "index_dailybasic": "trade_date",
    "index_tech": "trade_date",
    "index_global": "trade_date",
    "market_daily_info": "trade_date",
    "sz_daily_info": "trade_date",
    # index_info: 无主要时间字段（指数基本信息）
    # ── 板块复用表 ──
    # sector_info: 无主要数据时间字段（updated_at 是记录更新时间，不适合过滤）
    "sector_constituent": "trade_date",
}

# 自动推断兜底：当 target_table 不在 TIME_FIELD_MAP 中时，
# 按优先级尝试匹配列名
_TIME_FIELD_PRIORITY: list[str] = [
    "trade_date",
    "time",
    "ann_date",
    "cal_date",
    "st_date",
    "suspend_date",
    "surv_date",
    "report_date",
    "month",
    "end_date",
]

# ---------------------------------------------------------------------------
# 常量：图表类型推断
# ---------------------------------------------------------------------------

# K 线表集合（优先级最高，展示 K 线图）
KLINE_TABLES: set[str] = {"kline", "sector_kline"}

# 资金流向子分类（保留向后兼容）
MONEYFLOW_SUBCATEGORY: str = "资金流向数据"

# 完整图表类型映射：subcategory → chart_type
# 优先按 KLINE_TABLES 判断 K 线图，其次按此映射判断折线/柱状图
CHART_TYPE_MAP: dict[str, str] = {
    # 折线图
    "资金流向数据": "line",
    "两融及转融通": "line",
    "特色数据": "line",
    "大盘指数每日指标": "line",
    "指数技术面因子（专业版）": "line",
    # 柱状图
    "打板专题数据": "bar",
    "沪深市场每日交易统计": "bar",
    "深圳市场每日交易情况": "bar",
}

# ---------------------------------------------------------------------------
# 常量：导入状态颜色映射
# ---------------------------------------------------------------------------

_STATUS_COLOR_MAP: dict[str, str] = {
    "completed": "green",
    "failed": "red",
    "running": "blue",
    "pending": "blue",
    "stopped": "gray",
}

# ---------------------------------------------------------------------------
# 常量：sector_type 中文名映射
# ---------------------------------------------------------------------------

_SECTOR_TYPE_NAME_MAP: dict[str, str] = {
    # 同花顺 THS
    "I": "行业板块",
    "N": "概念板块",
    "R": "地域板块",
    "S": "风格板块",
    "BB": "板块指数",
    "ST": "ST板块",
    "TH": "主题板块",
    # 东方财富 DC / 通达信 TDX（中文值，直接映射自身）
    "概念板块": "概念板块",
    "行业板块": "行业板块",
    "风格板块": "风格板块",
    "地域板块": "地域板块",
    "地区板块": "地区板块",
    # 申万 TI
    "L1": "一级行业",
    "L2": "二级行业",
    "L3": "三级行业",
}


# ---------------------------------------------------------------------------
# 服务类
# ---------------------------------------------------------------------------


class TusharePreviewService:
    """Tushare 数据预览服务（只读查询）

    提供以下功能：
    - 分页查询已导入数据
    - 数据统计信息
    - 导入日志列表
    - 增量数据查询

    纯函数方法（_pure 后缀）不依赖数据库，可用于属性测试。
    """

    # ------------------------------------------------------------------
    # 纯函数：无数据库依赖，用于属性测试
    # ------------------------------------------------------------------

    @staticmethod
    def _get_time_field_pure(
        target_table: str, table_columns: list[str] | None = None
    ) -> str | None:
        """从 TIME_FIELD_MAP 查找时间字段，未命中时按优先级自动推断。

        Args:
            target_table: 目标数据表名
            table_columns: 表的实际列名列表（用于自动推断兜底）

        Returns:
            时间字段名，或 None（无法识别时间字段）
        """
        # 优先从映射表查找
        if target_table in TIME_FIELD_MAP:
            return TIME_FIELD_MAP[target_table]

        # 兜底：按优先级尝试匹配列名
        if table_columns:
            for candidate in _TIME_FIELD_PRIORITY:
                if candidate in table_columns:
                    return candidate

        return None


    @staticmethod
    def _coerce_time_param(value: str | Any, storage_engine: "StorageEngine") -> Any:
        """将时间参数转换为数据库兼容类型。

        TimescaleDB 的 timestamp/timestamptz 列需要 datetime 对象，
        PostgreSQL 的 varchar 列（如 trade_date）接受字符串，
        PostgreSQL 的 date 列接受 date 对象或 ISO 字符串。

        Args:
            value: 时间参数值（字符串或已转换的对象）
            storage_engine: 存储引擎类型

        Returns:
            转换后的参数值
        """
        if not isinstance(value, str):
            return value

        # TimescaleDB：转为 datetime
        if storage_engine == StorageEngine.TS:
            normalized = value.replace("-", "")
            if len(normalized) == 8:
                return datetime(
                    int(normalized[:4]), int(normalized[4:6]), int(normalized[6:8])
                )
            # ISO 格式尝试解析
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value

        # PostgreSQL date 列：转为 date 对象
        from datetime import date as date_type
        normalized = value.replace("-", "")
        if len(normalized) == 8:
            try:
                return date_type(
                    int(normalized[:4]), int(normalized[4:6]), int(normalized[6:8])
                )
            except ValueError:
                return value

        return value


    @staticmethod
    def _get_column_info_pure(
        table_columns: list[str],
        field_mappings: list[FieldMapping],
    ) -> list[ColumnInfo]:
        """根据 field_mappings 构建列定义。

        有映射时使用 target 作为 label，无映射时使用列名本身。

        Args:
            table_columns: 数据库表的列名列表
            field_mappings: 字段映射列表（source → target）

        Returns:
            列信息列表
        """
        # 构建 target → source 的反向映射（用于查找列名对应的映射）
        # field_mappings 中 target 是目标表字段名，source 是 Tushare 字段名
        # 在预览场景中，table_columns 是目标表的列名
        target_to_mapping: dict[str, FieldMapping] = {
            fm.target: fm for fm in field_mappings
        }

        result: list[ColumnInfo] = []
        for col in table_columns:
            mapping = target_to_mapping.get(col)
            label = mapping.target if mapping else col
            # 简单类型推断
            col_type = "string"
            col_lower = col.lower()
            if col_lower in (
                "trade_date", "ann_date", "cal_date", "st_date",
                "suspend_date", "start_date", "end_date", "ipo_date",
                "report_date", "surv_date", "in_date",
            ):
                col_type = "date"
            elif col_lower in ("time", "started_at", "finished_at", "updated_at"):
                col_type = "datetime"
            elif col_lower in (
                "open", "high", "low", "close", "vol", "volume", "amount",
                "turnover_rate", "pe_ttm", "pb", "total_mv", "float_mv",
                "record_count", "id", "weight",
            ):
                col_type = "number"

            result.append(ColumnInfo(name=col, label=label, type=col_type))

        return result

    @staticmethod
    def _infer_chart_type_pure(
        target_table: str, subcategory: str, time_field: str | None = None
    ) -> str | None:
        """基于 target_table、subcategory 和 time_field 推断图表类型。

        规则优先级：
        1. target_table 在 KLINE_TABLES 中 → candlestick（K 线图）
        2. subcategory 在 CHART_TYPE_MAP 中 → 对应类型（折线图/柱状图）
        3. time_field 非 None → line（默认折线图）
        4. time_field 为 None → None（不展示图表）

        Args:
            target_table: 目标数据表名
            subcategory: 接口子分类
            time_field: 时间字段名，None 表示无时间字段

        Returns:
            图表类型字符串（"candlestick" / "line" / "bar"）或 None
        """
        if target_table in KLINE_TABLES:
            return "candlestick"
        if subcategory in CHART_TYPE_MAP:
            return CHART_TYPE_MAP[subcategory]
        if time_field is not None:
            return "line"
        return None

    @staticmethod
    def _build_scope_filter_pure(
        entry: ApiEntry,
    ) -> list[tuple[str, dict[str, Any]]]:
        """根据 ApiEntry 推断共享表作用域 WHERE 条件。

        多个 API 接口可能指向同一张表（如 daily/weekly/monthly → kline），
        通过此方法添加作用域过滤条件，确保预览数据与所选接口精确匹配。

        Args:
            entry: API 接口注册信息

        Returns:
            条件列表，每项为 (SQL 片段, 参数字典) 元组
        """
        conditions: list[tuple[str, dict[str, Any]]] = []

        # 1. kline 表：按 freq 过滤（来自 extra_config）
        if entry.target_table == "kline" and "freq" in entry.extra_config:
            conditions.append((
                "freq = :scope_freq",
                {"scope_freq": entry.extra_config["freq"]},
            ))

        # 2. financial_statement 表：按 report_type 过滤
        inject = entry.extra_config.get("inject_fields", {})
        if entry.target_table == "financial_statement" and "report_type" in inject:
            conditions.append((
                "report_type = :scope_report_type",
                {"scope_report_type": inject["report_type"]},
            ))

        # 3. sector_info / sector_constituent / sector_kline：按 data_source 过滤
        if entry.target_table in (
            "sector_info", "sector_constituent", "sector_kline",
        ):
            ds = entry.extra_config.get("data_source")
            if not ds:
                # 也检查 inject_fields 中的 data_source
                ds = inject.get("data_source")
            if ds:
                conditions.append((
                    "data_source = :scope_ds",
                    {"scope_ds": ds},
                ))

        # 4. top_holders 表：按 holder_type 过滤
        if entry.target_table == "top_holders" and "holder_type" in entry.extra_config:
            conditions.append((
                "holder_type = :scope_ht",
                {"scope_ht": entry.extra_config["holder_type"]},
            ))

        return conditions

    @staticmethod
    def _clamp_pagination_pure(
        page: int | None, page_size: int | None
    ) -> tuple[int, int]:
        """分页参数 clamp。

        - page_size 范围 [1, 100]，默认 50
        - page 最小 1

        Args:
            page: 页码（可为 None）
            page_size: 每页条数（可为 None）

        Returns:
            (clamped_page, clamped_page_size) 元组
        """
        if page_size is None:
            clamped_size = 50
        else:
            clamped_size = max(1, min(100, page_size))

        if page is None:
            clamped_page = 1
        else:
            clamped_page = max(1, page)

        return clamped_page, clamped_size

    @staticmethod
    def _build_query_sql_pure(
        target_table: str,
        time_field: str | None,
        scope_filters: list[tuple[str, dict[str, Any]]],
        *,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
        ts_code: str | None = None,
        page: int = 1,
        page_size: int = 50,
        count_only: bool = False,
    ) -> str:
        """构建只读 SELECT SQL 语句。

        生成的 SQL 仅包含 SELECT，不含任何数据修改操作。
        使用参数绑定（:param_name）防止 SQL 注入。

        Args:
            target_table: 目标数据表名
            time_field: 时间字段名（可为 None）
            scope_filters: 作用域过滤条件列表
            data_time_start: 数据时间范围起始
            data_time_end: 数据时间范围结束
            ts_code: 股票代码过滤
            page: 页码
            page_size: 每页条数
            count_only: 是否仅查询总数

        Returns:
            SQL 语句字符串
        """
        if count_only:
            sql = f"SELECT COUNT(*) FROM {target_table}"
        else:
            sql = f"SELECT * FROM {target_table}"

        where_clauses: list[str] = []

        # 作用域过滤条件
        for clause, _params in scope_filters:
            where_clauses.append(clause)

        # 数据时间范围过滤
        if time_field and data_time_start:
            where_clauses.append(f"{time_field} >= :data_time_start")
        if time_field and data_time_end:
            where_clauses.append(f"{time_field} <= :data_time_end")

        # 股票代码过滤
        if ts_code:
            where_clauses.append("ts_code = :ts_code")

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if not count_only:
            # 排序：优先按时间字段降序
            if time_field:
                sql += f" ORDER BY {time_field} DESC"

            # 分页
            offset = (page - 1) * page_size
            sql += f" LIMIT {page_size} OFFSET {offset}"

        return sql

    @staticmethod
    def _get_status_color_pure(status: str) -> str:
        """导入状态到 CSS 类映射。

        已知状态返回确定颜色，未知状态返回默认颜色。

        Args:
            status: 导入状态字符串

        Returns:
            CSS 颜色类名
        """
        return _STATUS_COLOR_MAP.get(status, "default")

    @staticmethod
    def _compute_missing_dates_pure(
        expected_dates: set[str], actual_dates: set[str]
    ) -> list[str]:
        """计算缺失交易日列表（纯函数）。

        对预期交易日集合与实际日期集合求差集，返回排序后的缺失日期列表。

        Args:
            expected_dates: 预期交易日集合（来自交易日历）
            actual_dates: 实际存在的日期集合（来自目标数据表）

        Returns:
            按升序排列的缺失日期列表
        """
        return sorted(expected_dates - actual_dates)

    @staticmethod
    def _compute_missing_codes_pure(
        expected_codes: set[str], actual_codes: set[str]
    ) -> list[str]:
        """计算缺失代码列表（纯函数）。

        对预期代码集合与实际代码集合求差集，返回排序后的缺失代码列表。

        Args:
            expected_codes: 预期代码集合（来自 stock_info 表）
            actual_codes: 实际存在的代码集合（来自目标数据表）

        Returns:
            按升序排列的缺失代码列表
        """
        return sorted(expected_codes - actual_codes)

    @staticmethod
    def _determine_check_type_pure(
        time_field: str | None, has_ts_code: bool
    ) -> str:
        """判断校验类型（纯函数）。

        根据时间字段和 ts_code 列的存在情况，判断应使用的校验策略：
        - 有时间字段 → 时序数据校验（基于交易日历）
        - 无时间字段但有 ts_code → 非时序数据校验（基于代码集合）
        - 两者都没有 → 不支持校验

        Args:
            time_field: 时间字段名，None 表示无时间字段
            has_ts_code: 目标数据表是否包含 ts_code 列

        Returns:
            校验类型字符串："time_series" / "code_based" / "unsupported"
        """
        if time_field is not None:
            return "time_series"
        if has_ts_code:
            return "code_based"
        return "unsupported"

    @staticmethod
    def _build_completeness_report_pure(
        check_type: str,
        expected: set[str],
        actual: set[str],
        missing: list[str],
        time_range: dict | None = None,
        message: str | None = None,
    ) -> dict:
        """构建完整性报告数据（纯函数）。

        根据预期集合、实际集合和缺失列表，计算完整率并组装报告字典。
        当预期集合为空时，完整率为 1.0（视为完整）。

        Args:
            check_type: 校验类型（"time_series" / "code_based" / "unsupported"）
            expected: 预期项集合
            actual: 实际项集合
            missing: 缺失项列表
            time_range: 校验时间范围，如 {"start": "20240101", "end": "20241231"}
            message: 附加提示信息

        Returns:
            完整性报告字典，包含 check_type、expected_count、actual_count、
            missing_count、completeness_rate、missing_items、time_range、message
        """
        expected_count = len(expected)
        actual_count = len(actual)
        missing_count = len(missing)
        rate = actual_count / expected_count if expected_count > 0 else 1.0
        return {
            "check_type": check_type,
            "expected_count": expected_count,
            "actual_count": actual_count,
            "missing_count": missing_count,
            "completeness_rate": round(rate, 4),
            "missing_items": missing,
            "time_range": time_range,
            "message": message,
        }

    @staticmethod
    def _estimate_count_pure(
        reltuples: float, threshold: int = 1_000_000
    ) -> tuple[bool, int]:
        """判断是否使用 COUNT 估算（纯函数）。

        当 PostgreSQL pg_class.reltuples 值超过阈值时，使用估算值替代
        精确 COUNT(*)，避免大表全表扫描导致的查询延迟。

        Args:
            reltuples: PostgreSQL pg_class.reltuples 值（表的估算行数）
            threshold: 使用估算的阈值，默认 1,000,000

        Returns:
            (use_estimate, count) 元组 ——
            use_estimate 为 True 时使用估算值 int(reltuples)，
            为 False 时返回 0 表示需要执行精确 COUNT(*)
        """
        if reltuples > threshold:
            return True, int(reltuples)
        return False, 0

    @staticmethod
    def _clamp_chart_limit_pure(limit: int | None) -> int:
        """图表数据 limit clamp（纯函数）。

        将图表数据请求的 limit 参数限制在 [1, 500] 范围内。
        未提供时使用默认值 250。

        Args:
            limit: 用户请求的数据条数，None 表示使用默认值

        Returns:
            clamp 后的 limit 值，范围 [1, 500]，默认 250
        """
        if limit is None:
            return 250
        return max(1, min(500, limit))


    @staticmethod
    def _get_code_column_pure(target_table: str) -> str | None:
        """获取多股票共享表的代码列名（纯函数）。

        kline / sector_kline 使用 symbol 列，
        其他多股票表使用 ts_code 列，
        非共享表返回 None。
        """
        if target_table in ("kline", "sector_kline"):
            return "symbol"
        _MULTI_CODE_TABLES = {
            "stk_limit", "hsgt_top10", "ggt_top10",
            "financial_statement", "dividend", "forecast", "express",
            "moneyflow_ths", "moneyflow_dc", "tushare_moneyflow",
            "margin_detail", "stk_factor", "cyq_perf", "cyq_chips",
        }
        if target_table in _MULTI_CODE_TABLES:
            return "ts_code"
        return None





    # ------------------------------------------------------------------
    # 异步方法：依赖数据库
    # ------------------------------------------------------------------

    @staticmethod
    def _get_session(
        storage_engine: StorageEngine,
    ) -> "async_sessionmaker[AsyncSession]":
        """根据存储引擎类型返回对应的 Session 工厂。

        Args:
            storage_engine: 存储引擎枚举值

        Returns:
            AsyncSessionPG 或 AsyncSessionTS
        """
        if storage_engine == StorageEngine.TS:
            return AsyncSessionTS
        return AsyncSessionPG

    @staticmethod
    def _build_incremental_filter(
        import_log: TushareImportLog, entry: ApiEntry
    ) -> dict[str, str | None]:
        """从导入记录的 params_json 提取参数，重建数据查询条件。

        增量查询通过导入记录的参数重建查询条件，而非依赖写入时间窗口
        （因为数据表没有 created_at 字段）。

        Args:
            import_log: 导入日志记录
            entry: API 接口注册信息

        Returns:
            包含 data_time_start、data_time_end、ts_code 的过滤条件字典
        """
        params = import_log.params_json or {}
        filters: dict[str, str | None] = {}

        time_field = TusharePreviewService._get_time_field_pure(entry.target_table)
        if time_field:
            # 优先使用 start_date/end_date 参数
            if params.get("start_date"):
                filters["data_time_start"] = params["start_date"]
            if params.get("end_date"):
                filters["data_time_end"] = params["end_date"]
            # 单日期参数（trade_date）
            if params.get("trade_date"):
                filters["data_time_start"] = params["trade_date"]
                filters["data_time_end"] = params["trade_date"]

        # 代码过滤（如果导入时指定了特定代码）
        if params.get("ts_code"):
            filters["ts_code"] = params["ts_code"]

        return filters

    @staticmethod
    def _build_params_summary(params: dict | None) -> str:
        """构建导入参数摘要字符串。

        Args:
            params: 导入参数字典

        Returns:
            参数摘要（如 "2024-01-01 ~ 2024-12-31"）
        """
        if not params:
            return ""
        parts: list[str] = []
        start = params.get("start_date")
        end = params.get("end_date")
        if start and end:
            parts.append(f"{start} ~ {end}")
        elif start:
            parts.append(f"从 {start}")
        elif end:
            parts.append(f"至 {end}")
        trade_date = params.get("trade_date")
        if trade_date and not start and not end:
            parts.append(trade_date)
        ts_code = params.get("ts_code")
        if ts_code:
            parts.append(ts_code)
        return ", ".join(parts) if parts else str(params)

    async def query_preview_data(
        self,
        api_name: str,
        *,
        page: int | None = None,
        page_size: int | None = None,
        import_time_start: datetime | None = None,
        import_time_end: datetime | None = None,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
        incremental: bool = False,
        import_log_id: int | None = None,
    ) -> PreviewDataResponse:
        """查询预览数据。

        根据 api_name 从注册表获取元数据，动态构建 SQL 查询对应数据表。
        支持按导入时间、数据时间过滤，以及增量查询模式。

        Args:
            api_name: Tushare 接口名称
            page: 页码
            page_size: 每页条数
            import_time_start: 导入时间范围起始
            import_time_end: 导入时间范围结束
            data_time_start: 数据时间范围起始
            data_time_end: 数据时间范围结束
            incremental: 是否增量查询
            import_log_id: 指定导入记录 ID

        Returns:
            PreviewDataResponse 预览数据响应

        Raises:
            ValueError: api_name 不在注册表中
        """
        # 1. 从注册表获取 ApiEntry
        entry = TUSHARE_API_REGISTRY.get(api_name)
        if entry is None:
            raise ValueError(f"接口 {api_name} 未注册")

        # 2. 分页参数 clamp
        clamped_page, clamped_page_size = self._clamp_pagination_pure(page, page_size)

        # 3. 获取时间字段
        time_field = self._get_time_field_pure(entry.target_table)

        # 4. 获取作用域过滤条件
        scope_filters = self._build_scope_filter_pure(entry)

        # 5. 增量查询信息
        incremental_info: IncrementalInfo | None = None
        effective_data_time_start = data_time_start
        effective_data_time_end = data_time_end
        ts_code_filter: str | None = None

        # 处理 incremental=True：查询最近一条 status='completed' 的 ImportLog
        if incremental:
            async with AsyncSessionPG() as pg_session:
                stmt = (
                    select(TushareImportLog)
                    .where(
                        TushareImportLog.api_name == api_name,
                        TushareImportLog.status == "completed",
                    )
                    .order_by(TushareImportLog.started_at.desc())
                    .limit(1)
                )
                result = await pg_session.execute(stmt)
                log_record = result.scalar_one_or_none()

            if log_record is not None:
                # 从 params_json 提取参数重建查询条件
                inc_filters = self._build_incremental_filter(log_record, entry)
                effective_data_time_start = inc_filters.get(
                    "data_time_start", effective_data_time_start
                )
                effective_data_time_end = inc_filters.get(
                    "data_time_end", effective_data_time_end
                )
                ts_code_filter = inc_filters.get("ts_code")

                incremental_info = IncrementalInfo(
                    import_log_id=log_record.id,
                    import_time=(
                        log_record.started_at.isoformat()
                        if log_record.started_at
                        else ""
                    ),
                    record_count=log_record.record_count or 0,
                    status=log_record.status,
                    params_summary=self._build_params_summary(
                        log_record.params_json
                    ),
                )

        # 处理 import_log_id：查询指定导入记录
        elif import_log_id is not None:
            async with AsyncSessionPG() as pg_session:
                stmt = select(TushareImportLog).where(
                    TushareImportLog.id == import_log_id,
                    TushareImportLog.api_name == api_name,
                )
                result = await pg_session.execute(stmt)
                log_record = result.scalar_one_or_none()

            if log_record is not None:
                inc_filters = self._build_incremental_filter(log_record, entry)
                effective_data_time_start = inc_filters.get(
                    "data_time_start", effective_data_time_start
                )
                effective_data_time_end = inc_filters.get(
                    "data_time_end", effective_data_time_end
                )
                ts_code_filter = inc_filters.get("ts_code")

                incremental_info = IncrementalInfo(
                    import_log_id=log_record.id,
                    import_time=(
                        log_record.started_at.isoformat()
                        if log_record.started_at
                        else ""
                    ),
                    record_count=log_record.record_count or 0,
                    status=log_record.status,
                    params_summary=self._build_params_summary(
                        log_record.params_json
                    ),
                )

        # 6. 构建查询参数字典（转换时间参数类型以兼容 asyncpg）
        bind_params: dict[str, Any] = {}
        for _clause, params_dict in scope_filters:
            bind_params.update(params_dict)
        if time_field and effective_data_time_start:
            bind_params["data_time_start"] = self._coerce_time_param(
                effective_data_time_start, entry.storage_engine
            )
        if time_field and effective_data_time_end:
            bind_params["data_time_end"] = self._coerce_time_param(
                effective_data_time_end, entry.storage_engine
            )
        if ts_code_filter:
            bind_params["ts_code"] = ts_code_filter

        # 7. 构建 SQL 并执行查询
        SessionFactory = self._get_session(entry.storage_engine)

        # 查询分页数据
        data_sql = self._build_query_sql_pure(
            entry.target_table,
            time_field,
            scope_filters,
            data_time_start=effective_data_time_start,
            data_time_end=effective_data_time_end,
            ts_code=ts_code_filter,
            page=clamped_page,
            page_size=clamped_page_size,
        )

        # 查询总记录数：优先尝试 reltuples 估算，大表跳过精确 COUNT(*)
        # scope_filters 是系统自动添加的作用域过滤（如 kline 表的 freq 过滤），
        # 不算用户指定的过滤条件，仍可使用估算
        has_user_filters = bool(
            (time_field and effective_data_time_start)
            or (time_field and effective_data_time_end)
            or ts_code_filter
        )
        # scope_only: 仅有系统作用域过滤，无用户过滤条件
        scope_only = bool(scope_filters) and not has_user_filters

        count_sql = self._build_query_sql_pure(
            entry.target_table,
            time_field,
            scope_filters,
            data_time_start=effective_data_time_start,
            data_time_end=effective_data_time_end,
            ts_code=ts_code_filter,
            count_only=True,
        )

        async with SessionFactory() as session:
            # 总数：尝试 reltuples 估算
            total: int = 0
            use_estimate = False

            if not has_user_filters:
                try:
                    reltuples_sql = (
                        "SELECT reltuples FROM pg_class "
                        "WHERE relname = :table_name"
                    )
                    rel_result = await session.execute(
                        text(reltuples_sql),
                        {"table_name": entry.target_table},
                    )
                    rel_row = rel_result.scalar()
                    if rel_row is not None and float(rel_row) > 0:
                        use_estimate, estimated_count = (
                            self._estimate_count_pure(float(rel_row))
                        )
                        if use_estimate:
                            total = estimated_count
                    elif float(rel_row or 0) < 0:
                        # TimescaleDB 超表 reltuples = -1，尝试 approximate_row_count
                        try:
                            arc_sql = f"SELECT approximate_row_count('{entry.target_table}')"
                            arc_result = await session.execute(text(arc_sql))
                            arc_val = arc_result.scalar()
                            if arc_val is not None and int(arc_val) > 1_000_000:
                                total = int(arc_val)
                                use_estimate = True
                        except Exception:
                            pass
                except Exception:
                    # reltuples 查询失败时回退到精确 COUNT
                    logger.debug(
                        "reltuples 查询失败，回退到精确 COUNT: %s",
                        entry.target_table,
                    )

            # 若未使用估算，执行精确 COUNT(*)
            # 对于大表（scope_only），先尝试快速估算避免全表扫描
            if not use_estimate:
                if scope_only:
                    # 共享大表（如 kline）：使用 reltuples 整表估算值
                    # 精确 COUNT 可能耗时数十秒，直接使用估算
                    try:
                        reltuples_sql = (
                            "SELECT reltuples FROM pg_class "
                            "WHERE relname = :table_name"
                        )
                        rel_result = await session.execute(
                            text(reltuples_sql),
                            {"table_name": entry.target_table},
                        )
                        rel_row = rel_result.scalar()
                        if rel_row is not None and float(rel_row) > 1_000_000:
                            # 大表：使用估算值，标记为估算
                            total = int(float(rel_row))
                            use_estimate = True
                            logger.debug(
                                "大表 scope 过滤使用 reltuples 估算: table=%s total≈%d",
                                entry.target_table, total,
                            )
                        else:
                            # 小表：执行精确 COUNT
                            count_result = await session.execute(
                                text(count_sql), bind_params
                            )
                            total = count_result.scalar() or 0
                    except Exception:
                        count_result = await session.execute(
                            text(count_sql), bind_params
                        )
                        total = count_result.scalar() or 0
                else:
                    count_result = await session.execute(
                        text(count_sql), bind_params
                    )
                    total = count_result.scalar() or 0

            # 分页数据
            data_result = await session.execute(text(data_sql), bind_params)
            rows_raw = data_result.mappings().all()
            rows = [dict(r) for r in rows_raw]

            # 获取列名（从结果集或空查询）
            if rows_raw:
                table_columns = list(rows_raw[0].keys())
            else:
                # 空结果时通过 LIMIT 0 查询获取列名
                col_sql = f"SELECT * FROM {entry.target_table} LIMIT 0"
                col_result = await session.execute(text(col_sql))
                table_columns = (
                    list(col_result.keys()) if col_result.keys() else []
                )

        # 8. 序列化行数据（处理 datetime 等不可 JSON 序列化的类型）
        serialized_rows: list[dict[str, Any]] = []
        is_sector_info = entry.target_table == "sector_info"
        for row in rows:
            serialized: dict[str, Any] = {}
            for k, v in row.items():
                if isinstance(v, datetime):
                    serialized[k] = v.isoformat()
                else:
                    serialized[k] = v
            # sector_info 表追加 sector_type_name 虚拟列
            if is_sector_info and "sector_type" in serialized:
                serialized["sector_type_name"] = _SECTOR_TYPE_NAME_MAP.get(
                    serialized["sector_type"] or "", serialized.get("sector_type", "")
                )
            serialized_rows.append(serialized)

        # 9. 构建列信息和图表类型
        columns = self._get_column_info_pure(table_columns, entry.field_mappings)
        # sector_info 表追加 sector_type_name 虚拟列定义
        if entry.target_table == "sector_info":
            columns.append(ColumnInfo(name="sector_type_name", label="板块类型", type="string"))
        chart_type = self._infer_chart_type_pure(
            entry.target_table, entry.subcategory, time_field
        )

        # 10. 构建作用域提示信息
        scope_info: str | None = None
        if scope_filters:
            scope_parts = []
            for clause, params_dict in scope_filters:
                for _k, v in params_dict.items():
                    scope_parts.append(f"{clause.split(' = ')[0]}={v}")
            scope_info = ", ".join(scope_parts)

        return PreviewDataResponse(
            columns=columns,
            rows=serialized_rows,
            total=total,
            page=clamped_page,
            page_size=clamped_page_size,
            time_field=time_field,
            chart_type=chart_type,
            scope_info=scope_info,
            incremental_info=incremental_info,
        )

    async def query_stats(self, api_name: str) -> PreviewStatsResponse:
        """查询数据统计信息。

        返回指定接口数据表的总记录数、最早/最晚数据时间、最近导入时间。

        Args:
            api_name: Tushare 接口名称

        Returns:
            PreviewStatsResponse 统计信息响应

        Raises:
            ValueError: api_name 不在注册表中
        """
        # 1. 从注册表获取 ApiEntry
        entry = TUSHARE_API_REGISTRY.get(api_name)
        if entry is None:
            raise ValueError(f"接口 {api_name} 未注册")

        target_table = entry.target_table
        time_field = self._get_time_field_pure(target_table)
        scope_filters = self._build_scope_filter_pure(entry)

        # 构建 WHERE 子句和参数
        where_clauses: list[str] = []
        bind_params: dict[str, Any] = {}
        for clause, params_dict in scope_filters:
            where_clauses.append(clause)
            bind_params.update(params_dict)

        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)

        # 2. 查询数据表统计信息
        SessionFactory = self._get_session(entry.storage_engine)

        async with SessionFactory() as session:
            # 总记录数
            count_sql = f"SELECT COUNT(*) FROM {target_table}{where_sql}"
            count_result = await session.execute(text(count_sql), bind_params)
            total_count = count_result.scalar() or 0

            # 最早/最晚数据时间
            earliest_time: str | None = None
            latest_time: str | None = None
            if time_field:
                time_sql = (
                    f"SELECT MIN({time_field}), MAX({time_field}) "
                    f"FROM {target_table}{where_sql}"
                )
                time_result = await session.execute(text(time_sql), bind_params)
                time_row = time_result.one_or_none()
                if time_row:
                    min_val, max_val = time_row[0], time_row[1]
                    if min_val is not None:
                        earliest_time = (
                            min_val.isoformat()
                            if isinstance(min_val, datetime)
                            else str(min_val)
                        )
                    if max_val is not None:
                        latest_time = (
                            max_val.isoformat()
                            if isinstance(max_val, datetime)
                            else str(max_val)
                        )

        # 3. 查询最近导入记录（从 PG 的 import_log 表）
        last_import_at: str | None = None
        last_import_count: int = 0

        async with AsyncSessionPG() as pg_session:
            stmt = (
                select(TushareImportLog)
                .where(
                    TushareImportLog.api_name == api_name,
                    TushareImportLog.status == "completed",
                )
                .order_by(TushareImportLog.started_at.desc())
                .limit(1)
            )
            result = await pg_session.execute(stmt)
            last_log = result.scalar_one_or_none()

            if last_log is not None:
                last_import_at = (
                    last_log.started_at.isoformat()
                    if last_log.started_at
                    else None
                )
                last_import_count = last_log.record_count or 0

        return PreviewStatsResponse(
            total_count=total_count,
            earliest_time=earliest_time,
            latest_time=latest_time,
            last_import_at=last_import_at,
            last_import_count=last_import_count,
        )

    async def query_import_logs(
        self, api_name: str, *, limit: int = 20
    ) -> list[ImportLogItem]:
        """查询导入记录列表。

        按 started_at 降序排列，返回最近的导入记录。

        Args:
            api_name: Tushare 接口名称
            limit: 返回记录数上限

        Returns:
            导入记录列表
        """
        async with AsyncSessionPG() as pg_session:
            stmt = (
                select(TushareImportLog)
                .where(TushareImportLog.api_name == api_name)
                .order_by(TushareImportLog.started_at.desc())
                .limit(limit)
            )
            result = await pg_session.execute(stmt)
            records = result.scalars().all()

        return [
            ImportLogItem(
                id=record.id,
                api_name=record.api_name,
                params_json=record.params_json,
                status=record.status,
                record_count=record.record_count or 0,
                error_message=record.error_message,
                started_at=(
                    record.started_at.isoformat()
                    if record.started_at
                    else None
                ),
                finished_at=(
                    record.finished_at.isoformat()
                    if record.finished_at
                    else None
                ),
            )
            for record in records
        ]

    async def check_integrity(
        self,
        api_name: str,
        *,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
    ) -> CompletenessReport:
        """执行数据完整性校验。

        根据目标数据表的特征自动选择校验策略：
        - 时序数据：基于 SSE 交易日历比对缺失交易日
        - 非时序数据：基于全部 A 股代码集合比对缺失代码
        - 不支持校验：既无时间字段也无 ts_code 列的表

        Args:
            api_name: Tushare 接口名称
            data_time_start: 数据时间范围起始（如 "20240101"），可选
            data_time_end: 数据时间范围结束（如 "20241231"），可选

        Returns:
            CompletenessReport 完整性校验结果

        Raises:
            ValueError: api_name 不在注册表中
        """
        # 1. 从注册表获取 ApiEntry
        entry = TUSHARE_API_REGISTRY.get(api_name)
        if entry is None:
            raise ValueError(f"接口 {api_name} 未注册")

        # 2. 获取时间字段
        time_field = self._get_time_field_pure(entry.target_table)

        # 3. 检查目标表是否包含 ts_code 列
        SessionFactory = self._get_session(entry.storage_engine)
        async with SessionFactory() as session:
            col_sql = f"SELECT * FROM {entry.target_table} LIMIT 0"
            col_result = await session.execute(text(col_sql))
            table_columns = list(col_result.keys()) if col_result.keys() else []

        has_ts_code = "ts_code" in table_columns

        # 4. 判断校验类型
        check_type = self._determine_check_type_pure(time_field, has_ts_code)

        # 5. 获取作用域过滤条件
        scope_filters = self._build_scope_filter_pure(entry)

        # 6. 根据校验类型执行对应逻辑
        if check_type == "time_series":
            return await self._check_integrity_time_series(
                entry, time_field, scope_filters,
                data_time_start=data_time_start,
                data_time_end=data_time_end,
            )
        elif check_type == "code_based":
            return await self._check_integrity_code_based(
                entry, scope_filters,
            )
        else:
            # 不支持校验
            report_data = self._build_completeness_report_pure(
                check_type="unsupported",
                expected=set(),
                actual=set(),
                missing=[],
                message="该数据表不支持完整性校验",
            )
            return CompletenessReport(**report_data)

    async def _check_integrity_time_series(
        self,
        entry: ApiEntry,
        time_field: str | None,
        scope_filters: list[tuple[str, dict[str, Any]]],
        *,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
    ) -> CompletenessReport:
        """时序数据完整性校验（内部方法）。

        基于 SSE 交易日历，比对目标表在指定时间范围内的实际日期集合，
        计算缺失的交易日。

        Args:
            entry: API 接口注册信息
            time_field: 时间字段名
            scope_filters: 作用域过滤条件
            data_time_start: 时间范围起始
            data_time_end: 时间范围结束

        Returns:
            CompletenessReport 时序数据校验结果
        """
        SessionFactory = self._get_session(entry.storage_engine)

        # 若未指定时间范围，查询目标表的 MIN/MAX 时间字段作为默认范围
        if data_time_start is None or data_time_end is None:
            where_clauses: list[str] = []
            bind_params: dict[str, Any] = {}
            for clause, params_dict in scope_filters:
                where_clauses.append(clause)
                bind_params.update(params_dict)

            where_sql = ""
            if where_clauses:
                where_sql = " WHERE " + " AND ".join(where_clauses)

            range_sql = (
                f"SELECT MIN({time_field}), MAX({time_field}) "
                f"FROM {entry.target_table}{where_sql}"
            )
            async with SessionFactory() as session:
                range_result = await session.execute(
                    text(range_sql), bind_params
                )
                range_row = range_result.one_or_none()
                if range_row and range_row[0] is not None:
                    if data_time_start is None:
                        data_time_start = str(range_row[0])
                    if data_time_end is None:
                        data_time_end = str(range_row[1])

        # 若仍无时间范围（表为空），返回空结果
        if data_time_start is None or data_time_end is None:
            report_data = self._build_completeness_report_pure(
                check_type="time_series",
                expected=set(),
                actual=set(),
                missing=[],
                time_range=None,
                message="目标数据表无数据，无法确定校验范围",
            )
            return CompletenessReport(**report_data)

        time_range = {"start": data_time_start, "end": data_time_end}

        # 查询 trade_calendar 获取 SSE 交易日集合
        cal_sql = (
            "SELECT cal_date FROM trade_calendar "
            "WHERE exchange = :exchange AND is_open = :is_open "
            "AND cal_date >= :cal_start AND cal_date <= :cal_end"
        )
        cal_params = {
            "exchange": "SSE",
            "is_open": 1,
            "cal_start": data_time_start,
            "cal_end": data_time_end,
        }

        async with AsyncSessionPG() as pg_session:
            cal_result = await pg_session.execute(text(cal_sql), cal_params)
            expected_dates: set[str] = {
                str(row[0]) for row in cal_result.fetchall()
            }

        # 查询目标表在时间范围内的 DISTINCT 日期集合（应用 scope_filter）
        where_clauses_data: list[str] = []
        bind_params_data: dict[str, Any] = {}
        for clause, params_dict in scope_filters:
            where_clauses_data.append(clause)
            bind_params_data.update(params_dict)

        where_clauses_data.append(f"{time_field} >= :data_time_start")
        where_clauses_data.append(f"{time_field} <= :data_time_end")
        bind_params_data["data_time_start"] = self._coerce_time_param(
            data_time_start, entry.storage_engine
        )
        bind_params_data["data_time_end"] = self._coerce_time_param(
            data_time_end, entry.storage_engine
        )

        where_sql_data = " WHERE " + " AND ".join(where_clauses_data)
        actual_sql = (
            f"SELECT DISTINCT {time_field} FROM {entry.target_table}"
            f"{where_sql_data}"
        )

        async with SessionFactory() as session:
            actual_result = await session.execute(
                text(actual_sql), bind_params_data
            )
            actual_dates: set[str] = {
                str(row[0]) for row in actual_result.fetchall()
            }

        # 计算缺失交易日
        missing = self._compute_missing_dates_pure(expected_dates, actual_dates)

        report_data = self._build_completeness_report_pure(
            check_type="time_series",
            expected=expected_dates,
            actual=actual_dates,
            missing=missing,
            time_range=time_range,
        )
        return CompletenessReport(**report_data)

    async def _check_integrity_code_based(
        self,
        entry: ApiEntry,
        scope_filters: list[tuple[str, dict[str, Any]]],
    ) -> CompletenessReport:
        """非时序数据完整性校验（内部方法）。

        基于 stock_info 表的全部 A 股代码集合，比对目标表中实际存在的
        ts_code 集合，计算缺失的代码。

        Args:
            entry: API 接口注册信息
            scope_filters: 作用域过滤条件

        Returns:
            CompletenessReport 非时序数据校验结果
        """
        # 查询 stock_info 表获取全部 A 股 ts_code 集合
        async with AsyncSessionPG() as pg_session:
            expected_result = await pg_session.execute(
                text("SELECT DISTINCT ts_code FROM stock_info")
            )
            expected_codes: set[str] = {
                str(row[0]) for row in expected_result.fetchall()
            }

        # 查询目标表的 DISTINCT ts_code 集合（应用 scope_filter）
        SessionFactory = self._get_session(entry.storage_engine)

        where_clauses: list[str] = []
        bind_params: dict[str, Any] = {}
        for clause, params_dict in scope_filters:
            where_clauses.append(clause)
            bind_params.update(params_dict)

        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)

        actual_sql = (
            f"SELECT DISTINCT ts_code FROM {entry.target_table}{where_sql}"
        )

        async with SessionFactory() as session:
            actual_result = await session.execute(
                text(actual_sql), bind_params
            )
            actual_codes: set[str] = {
                str(row[0]) for row in actual_result.fetchall()
            }

        # 计算缺失代码
        missing = self._compute_missing_codes_pure(expected_codes, actual_codes)

        report_data = self._build_completeness_report_pure(
            check_type="code_based",
            expected=expected_codes,
            actual=actual_codes,
            missing=missing,
            message="预期集合基于全部 A 股代码，实际覆盖范围可能因接口特性而异",
        )
        return CompletenessReport(**report_data)

    async def query_chart_data(
        self,
        api_name: str,
        *,
        limit: int = 500,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
        code: str | None = None,
    ) -> ChartDataResponse:
        """查询图表数据（独立于表格分页）。

        返回按时间字段升序排列的数据，用于前端图表渲染。
        - 用户未指定时间范围时，默认限定最近一年
        - 多股票共享表（如 kline）自动选取一只股票，支持前端切换
        - 返回可选股票代码列表供前端选择器使用

        Args:
            api_name: Tushare 接口名称
            limit: 返回数据条数上限，默认 500
            data_time_start: 数据时间范围起始
            data_time_end: 数据时间范围结束
            code: 指定股票代码（多股票表时使用）

        Returns:
            ChartDataResponse 图表数据响应
        """
        entry = TUSHARE_API_REGISTRY.get(api_name)
        if entry is None:
            raise ValueError(f"接口 {api_name} 未注册")

        clamped_limit = max(1, min(5000, limit))
        time_field = self._get_time_field_pure(entry.target_table)

        if time_field is None:
            return ChartDataResponse(
                rows=[], time_field=None, chart_type=None, columns=[],
                total_available=0, available_codes=[], selected_code=None,
            )

        scope_filters = self._build_scope_filter_pure(entry)

        # 构建基础 WHERE
        where_clauses: list[str] = []
        bind_params: dict[str, Any] = {}
        for clause, params_dict in scope_filters:
            where_clauses.append(clause)
            bind_params.update(params_dict)

        # 默认最近一年
        effective_start = data_time_start
        effective_end = data_time_end
        if not effective_start and not effective_end:
            from datetime import timedelta
            one_year_ago = datetime.now() - timedelta(days=365)
            if entry.storage_engine == StorageEngine.TS:
                effective_start = one_year_ago
            else:
                effective_start = one_year_ago.strftime("%Y%m%d")

        if effective_start:
            where_clauses.append(f"{time_field} >= :data_time_start")
            bind_params["data_time_start"] = self._coerce_time_param(
                effective_start, entry.storage_engine
            )
        if effective_end:
            where_clauses.append(f"{time_field} <= :data_time_end")
            bind_params["data_time_end"] = self._coerce_time_param(
                effective_end, entry.storage_engine
            )

        # 判断是否为多股票共享表
        code_column = self._get_code_column_pure(entry.target_table)
        SessionFactory = self._get_session(entry.storage_engine)

        available_codes: list[str] = []
        selected_code: str | None = None

        if code_column:
            # 查询可选股票列表（按数据量降序，取前 50）
            scope_where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            async with SessionFactory() as session:
                codes_sql = (
                    f"SELECT {code_column}, COUNT(*) AS cnt "
                    f"FROM {entry.target_table}{scope_where} "
                    f"GROUP BY {code_column} ORDER BY cnt DESC LIMIT 50"
                )
                codes_result = await session.execute(text(codes_sql), bind_params)
                available_codes = [str(row[0]) for row in codes_result.fetchall()]

            if available_codes:
                selected_code = code if (code and code in available_codes) else available_codes[0]
                where_clauses.append(f"{code_column} = :chart_code")
                bind_params["chart_code"] = selected_code

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        data_sql = (
            f"SELECT * FROM {entry.target_table}{where_sql} "
            f"ORDER BY {time_field} DESC LIMIT {clamped_limit}"
        )
        count_sql = f"SELECT COUNT(*) FROM {entry.target_table}{where_sql}"

        async with SessionFactory() as session:
            count_result = await session.execute(text(count_sql), bind_params)
            total_available = count_result.scalar() or 0

            data_result = await session.execute(text(data_sql), bind_params)
            rows_raw = data_result.mappings().all()
            rows = [dict(r) for r in rows_raw]

            if rows_raw:
                table_columns = list(rows_raw[0].keys())
            else:
                col_sql = f"SELECT * FROM {entry.target_table} LIMIT 0"
                col_result = await session.execute(text(col_sql))
                table_columns = list(col_result.keys()) if col_result.keys() else []

        # 序列化
        serialized_rows: list[dict[str, Any]] = []
        for row in rows:
            serialized: dict[str, Any] = {}
            for k, v in row.items():
                serialized[k] = v.isoformat() if isinstance(v, datetime) else v
            serialized_rows.append(serialized)

        serialized_rows.reverse()

        columns = self._get_column_info_pure(table_columns, entry.field_mappings)
        chart_type = self._infer_chart_type_pure(
            entry.target_table, entry.subcategory, time_field
        )

        return ChartDataResponse(
            rows=serialized_rows,
            time_field=time_field,
            chart_type=chart_type,
            columns=columns,
            total_available=total_available,
            available_codes=available_codes,
            selected_code=selected_code,
        )



    async def delete_data(
        self,
        api_name: str,
        *,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
        import_time_start: str | None = None,
        import_time_end: str | None = None,
    ) -> DeleteDataResponse:
        """删除指定接口在指定数据时间范围内的数据，或按导入时间范围删除。

        根据 api_name 从注册表获取目标表和时间字段，构建 DELETE SQL。
        支持两种删除模式：
        1. 按数据时间范围删除（data_time_start/data_time_end）
        2. 按导入时间范围删除（import_time_start/import_time_end）：
           先查询匹配的导入记录，再根据 params_json 重建数据查询条件删除

        Args:
            api_name: Tushare 接口名称
            data_time_start: 数据时间范围起始（如 "2024-01-01" 或 "20240101"）
            data_time_end: 数据时间范围结束
            import_time_start: 导入时间范围起始（ISO 格式）
            import_time_end: 导入时间范围结束（ISO 格式）

        Returns:
            DeleteDataResponse 包含删除记录数和范围信息

        Raises:
            ValueError: 接口不存在、无时间字段、或未指定任何时间范围
        """
        entry = TUSHARE_API_REGISTRY.get(api_name)
        if entry is None:
            raise ValueError(f"未知接口: {api_name}")

        has_import_time = bool(import_time_start or import_time_end)
        has_data_time = bool(data_time_start or data_time_end)

        if not has_data_time and not has_import_time:
            # 无任何时间范围：全表清空
            return await self._delete_all(api_name, entry)

        # 按导入时间范围删除路径
        if has_import_time and not has_data_time:
            result = await self._delete_by_import_time(
                api_name,
                entry,
                import_time_start=import_time_start,
                import_time_end=import_time_end,
            )
            # 如果导入时间路径删除了 0 条，回退到全表清空
            if result.deleted_count == 0:
                return await self._delete_all(api_name, entry)
            return result

        # 按数据时间范围删除路径
        return await self._delete_by_data_time(
            api_name,
            entry,
            data_time_start=data_time_start,
            data_time_end=data_time_end,
        )

    async def _delete_all(
        self, api_name: str, entry: ApiEntry,
    ) -> DeleteDataResponse:
        """全表清空。"""
        SessionFactory = self._get_session(entry.storage_engine)
        # 共享表需要加作用域过滤，只删当前 API 的数据
        scope_filters = self._build_scope_filter_pure(entry)

        # 共享表（多个 API 写入同一张表）无作用域过滤时，禁止全表清空
        _SHARED_TABLES = {"kline", "sector_kline", "financial_statement", "sector_info",
                          "sector_constituent", "top_holders", "stock_info"}
        if not scope_filters and entry.target_table in _SHARED_TABLES:
            # do_update 类型的接口只更新字段，不产生独立数据，无法单独删除
            if entry.conflict_action == "do_update":
                raise ValueError(
                    f"接口 {api_name} 通过更新方式写入共享表 {entry.target_table}，"
                    f"不产生独立数据行，无需单独删除"
                )
            raise ValueError(
                f"接口 {api_name} 使用共享表 {entry.target_table}，"
                f"请指定数据时间范围后再删除，避免误删其他接口数据"
            )

        if scope_filters:
            where_parts = []
            params: dict[str, Any] = {}
            for clause, p in scope_filters:
                where_parts.append(clause)
                params.update(p)
            sql = f"DELETE FROM {entry.target_table} WHERE {' AND '.join(where_parts)}"
        else:
            sql = f"DELETE FROM {entry.target_table}"
            params = {}

        async with SessionFactory() as session:
            try:
                result = await session.execute(text(sql), params)
                deleted_count = result.rowcount
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        logger.info("清空数据 api=%s table=%s deleted=%d", api_name, entry.target_table, deleted_count)
        return DeleteDataResponse(
            deleted_count=deleted_count,
            target_table=entry.target_table,
            time_field=None,
            data_time_start=None,
            data_time_end=None,
        )

    async def _delete_by_import_time(
        self,
        api_name: str,
        entry: ApiEntry,
        *,
        import_time_start: str | None = None,
        import_time_end: str | None = None,
    ) -> DeleteDataResponse:
        """按导入时间范围删除数据。

        先查询 tushare_import_log 表获取匹配时间范围内的导入记录，
        再使用 _build_incremental_filter() 从每条记录的 params_json
        重建数据查询条件，按这些条件执行删除。

        Args:
            api_name: Tushare 接口名称
            entry: API 接口注册信息
            import_time_start: 导入时间范围起始
            import_time_end: 导入时间范围结束

        Returns:
            DeleteDataResponse 包含删除记录数和范围信息
        """
        # 1. 查询匹配的导入记录
        async with AsyncSessionPG() as pg_session:
            stmt = (
                select(TushareImportLog)
                .where(TushareImportLog.api_name == api_name)
            )
            if import_time_start:
                from datetime import datetime as dt
                try:
                    start_dt = dt.fromisoformat(import_time_start)
                except ValueError:
                    start_dt = dt.fromisoformat(import_time_start + ":00")
                stmt = stmt.where(TushareImportLog.started_at >= start_dt)
            if import_time_end:
                from datetime import datetime as dt
                try:
                    end_dt = dt.fromisoformat(import_time_end)
                except ValueError:
                    end_dt = dt.fromisoformat(import_time_end + ":00")
                stmt = stmt.where(TushareImportLog.started_at <= end_dt)
            result = await pg_session.execute(stmt)
            import_logs = result.scalars().all()

        if not import_logs:
            return DeleteDataResponse(
                deleted_count=0,
                target_table=entry.target_table,
                time_field=self._get_time_field_pure(entry.target_table),
                data_time_start=None,
                data_time_end=None,
            )

        # 2. 获取时间字段和作用域过滤
        SessionFactory = self._get_session(entry.storage_engine)

        async with SessionFactory() as session:
            col_sql = f"SELECT * FROM {entry.target_table} LIMIT 0"
            col_result = await session.execute(text(col_sql))
            table_columns = list(col_result.keys()) if col_result.keys() else []

        time_field = self._get_time_field_pure(entry.target_table, table_columns)
        scope_filters = self._build_scope_filter_pure(entry)

        # 3. 对每条导入记录重建条件并执行删除
        total_deleted = 0
        snapshot_truncated = False  # 防止无时间字段的快照表被重复清空
        is_timestamp_field = time_field in ("time", "started_at", "finished_at", "updated_at") if time_field else False

        for log_record in import_logs:
            inc_filters = self._build_incremental_filter(log_record, entry)
            inc_data_start = inc_filters.get("data_time_start")
            inc_data_end = inc_filters.get("data_time_end")
            inc_ts_code = inc_filters.get("ts_code")

            # 如果导入记录没有可用的过滤条件，对无时间字段的快照表直接清空
            if not inc_data_start and not inc_data_end and not inc_ts_code:
                if not time_field:
                    # 无时间字段的快照表（如 stock_basic），直接 TRUNCATE
                    if not snapshot_truncated:
                        delete_sql = f"DELETE FROM {entry.target_table}"
                        async with SessionFactory() as session:
                            try:
                                result = await session.execute(text(delete_sql))
                                total_deleted += result.rowcount
                                await session.commit()
                            except Exception:
                                await session.rollback()
                                raise
                        snapshot_truncated = True
                continue

            where_clauses: list[str] = []
            params: dict[str, Any] = {}

            if time_field and inc_data_start:
                normalized_start = inc_data_start.replace("-", "")
                if is_timestamp_field:
                    where_clauses.append(f'"{time_field}" >= :start_time')
                    params["start_time"] = datetime(
                        int(normalized_start[:4]),
                        int(normalized_start[4:6]),
                        int(normalized_start[6:8]),
                    )
                else:
                    where_clauses.append(f'"{time_field}" >= :start_time')
                    params["start_time"] = normalized_start

            if time_field and inc_data_end:
                normalized_end = inc_data_end.replace("-", "")
                if is_timestamp_field:
                    where_clauses.append(f'"{time_field}" <= :end_time')
                    params["end_time"] = datetime(
                        int(normalized_end[:4]),
                        int(normalized_end[4:6]),
                        int(normalized_end[6:8]),
                        23, 59, 59,
                    )
                else:
                    where_clauses.append(f'"{time_field}" <= :end_time')
                    params["end_time"] = normalized_end

            if inc_ts_code:
                where_clauses.append("ts_code = :ts_code")
                params["ts_code"] = inc_ts_code

            # 添加作用域过滤条件
            for clause, scope_params in scope_filters:
                where_clauses.append(clause)
                params.update(scope_params)

            if not where_clauses:
                continue

            where_sql = " AND ".join(where_clauses)
            delete_sql = f"DELETE FROM {entry.target_table} WHERE {where_sql}"

            async with SessionFactory() as session:
                try:
                    result = await session.execute(text(delete_sql), params)
                    total_deleted += result.rowcount
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        logger.info(
            "按导入时间删除数据 api=%s table=%s import_time=%s~%s deleted=%d records_count=%d",
            api_name, entry.target_table,
            import_time_start, import_time_end, total_deleted, len(import_logs),
        )

        return DeleteDataResponse(
            deleted_count=total_deleted,
            target_table=entry.target_table,
            time_field=time_field,
            data_time_start=None,
            data_time_end=None,
        )

    async def _delete_by_data_time(
        self,
        api_name: str,
        entry: ApiEntry,
        *,
        data_time_start: str | None = None,
        data_time_end: str | None = None,
    ) -> DeleteDataResponse:
        """按数据时间范围删除数据（原有逻辑）。

        Args:
            api_name: Tushare 接口名称
            entry: API 接口注册信息
            data_time_start: 数据时间范围起始
            data_time_end: 数据时间范围结束

        Returns:
            DeleteDataResponse 包含删除记录数和范围信息

        Raises:
            ValueError: 无时间字段或未指定时间范围
        """

        # 获取时间字段
        SessionFactory = self._get_session(entry.storage_engine)

        async with SessionFactory() as session:
            col_sql = f"SELECT * FROM {entry.target_table} LIMIT 0"
            col_result = await session.execute(text(col_sql))
            table_columns = list(col_result.keys()) if col_result.keys() else []

        time_field = self._get_time_field_pure(entry.target_table, table_columns)
        if not time_field:
            raise ValueError(f"接口 {api_name} 的数据表 {entry.target_table} 无时间字段，无法按时间范围删除")

        # 构建 DELETE SQL
        where_clauses: list[str] = []
        params: dict[str, Any] = {}

        # 查询时间字段的实际数据库列类型，以正确构造参数
        async with SessionFactory() as session:
            col_type_sql = (
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name = :col"
            )
            col_type_result = await session.execute(
                text(col_type_sql),
                {"tbl": entry.target_table, "col": time_field},
            )
            col_type_row = col_type_result.scalar_one_or_none()
            col_data_type = (col_type_row or "").lower()

        # 根据实际列类型分类：timestamp / date / 其他（varchar 等）
        is_timestamp_field = "timestamp" in col_data_type
        is_date_field = col_data_type == "date"

        # 检查时间字段是否全为 NULL（快照表场景），若是则忽略时间条件直接删除
        async with SessionFactory() as session:
            null_check_sql = (
                f'SELECT COUNT(*) FROM {entry.target_table} '
                f'WHERE "{time_field}" IS NOT NULL LIMIT 1'
            )
            non_null_count = (await session.execute(text(null_check_sql))).scalar() or 0
        skip_time_filter = non_null_count == 0

        # NOTE: 时间范围条件先添加，作用域过滤条件在后面追加

        if not skip_time_filter and data_time_start:
            normalized_start = data_time_start.replace("-", "")
            where_clauses.append(f'"{time_field}" >= :start_time')
            if is_timestamp_field:
                from datetime import datetime as dt, timezone, timedelta
                # TIMESTAMPTZ 字段：扩展范围覆盖时区偏移（CST=UTC+8）
                # 起始日期的前一天 16:00 UTC = 当天 00:00 CST
                cst = timezone(timedelta(hours=8))
                start_dt = dt(int(normalized_start[:4]), int(normalized_start[4:6]), int(normalized_start[6:8]), tzinfo=cst)
                # 再往前推一天以确保覆盖
                params["start_time"] = start_dt - timedelta(days=1)
            elif is_date_field:
                from datetime import date as d
                params["start_time"] = d(int(normalized_start[:4]), int(normalized_start[4:6]), int(normalized_start[6:8]))
            else:
                params["start_time"] = normalized_start

        if not skip_time_filter and data_time_end:
            normalized_end = data_time_end.replace("-", "")
            where_clauses.append(f'"{time_field}" <= :end_time')
            if is_timestamp_field:
                from datetime import datetime as dt, timezone, timedelta
                cst = timezone(timedelta(hours=8))
                end_dt = dt(int(normalized_end[:4]), int(normalized_end[4:6]), int(normalized_end[6:8]), 23, 59, 59, tzinfo=cst)
                # 往后推一天以确保覆盖时区偏移
                params["end_time"] = end_dt + timedelta(days=1)
            elif is_date_field:
                from datetime import date as d
                params["end_time"] = d(int(normalized_end[:4]), int(normalized_end[4:6]), int(normalized_end[6:8]))
            else:
                params["end_time"] = normalized_end

        if skip_time_filter:
            logger.info(
                "时间字段 %s 全为 NULL，忽略时间范围条件 api=%s table=%s",
                time_field, api_name, entry.target_table,
            )

        # 共享表作用域过滤：确保仅删除属于当前 API 接口的数据
        scope_filters = self._build_scope_filter_pure(entry)
        for clause, scope_params in scope_filters:
            where_clauses.append(clause)
            params.update(scope_params)

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            delete_sql = f'DELETE FROM {entry.target_table} WHERE {where_sql}'
        else:
            delete_sql = f'DELETE FROM {entry.target_table}'

        async with SessionFactory() as session:
            try:
                result = await session.execute(text(delete_sql), params)
                deleted_count = result.rowcount
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        logger.info(
            "删除数据 api=%s table=%s time_field=%s range=%s~%s deleted=%d",
            api_name, entry.target_table, time_field,
            data_time_start, data_time_end, deleted_count,
        )

        return DeleteDataResponse(
            deleted_count=deleted_count,
            target_table=entry.target_table,
            time_field=time_field,
            data_time_start=data_time_start,
            data_time_end=data_time_end,
        )
