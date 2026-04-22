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
    "stock_st": "st_date",
    "st_warning": "trade_date",
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
    "sector_info": "updated_at",
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

# K 线表集合（展示 K 线图）
KLINE_TABLES: set[str] = {"kline", "sector_kline"}

# 资金流向子分类（展示折线图）
MONEYFLOW_SUBCATEGORY: str = "资金流向数据"

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
    def _infer_chart_type_pure(target_table: str, subcategory: str) -> str | None:
        """基于 target_table 和 subcategory 推断图表类型。

        规则：
        - kline / sector_kline → candlestick（K 线图）
        - subcategory == "资金流向数据" → line（折线图）
        - 其余 → None（仅表格）

        Args:
            target_table: 目标数据表名
            subcategory: 接口子分类

        Returns:
            图表类型字符串或 None
        """
        if target_table in KLINE_TABLES:
            return "candlestick"
        if subcategory == MONEYFLOW_SUBCATEGORY:
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

        # 6. 构建查询参数字典
        bind_params: dict[str, Any] = {}
        for _clause, params_dict in scope_filters:
            bind_params.update(params_dict)
        if time_field and effective_data_time_start:
            bind_params["data_time_start"] = effective_data_time_start
        if time_field and effective_data_time_end:
            bind_params["data_time_end"] = effective_data_time_end
        if ts_code_filter:
            bind_params["ts_code"] = ts_code_filter

        # 7. 构建 SQL 并执行查询
        SessionFactory = self._get_session(entry.storage_engine)

        # 查询总记录数
        count_sql = self._build_query_sql_pure(
            entry.target_table,
            time_field,
            scope_filters,
            data_time_start=effective_data_time_start,
            data_time_end=effective_data_time_end,
            ts_code=ts_code_filter,
            count_only=True,
        )

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

        async with SessionFactory() as session:
            # 总数
            count_result = await session.execute(text(count_sql), bind_params)
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
        for row in rows:
            serialized: dict[str, Any] = {}
            for k, v in row.items():
                if isinstance(v, datetime):
                    serialized[k] = v.isoformat()
                else:
                    serialized[k] = v
            serialized_rows.append(serialized)

        # 9. 构建列信息和图表类型
        columns = self._get_column_info_pure(table_columns, entry.field_mappings)
        chart_type = self._infer_chart_type_pure(
            entry.target_table, entry.subcategory
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
