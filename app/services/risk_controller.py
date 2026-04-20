"""
风险控制模块（Risk Controller）

提供：
- MarketRiskChecker: 大盘风控状态检测（事前）
  - check_market_risk: 根据指数收盘价序列判定大盘风险等级
  - get_trend_threshold: 根据风险等级返回趋势打分阈值
  - is_buy_suspended: 判断是否暂停买入信号
- StockRiskFilter: 个股风控过滤（事前）
  - check_daily_gain: 单日涨幅 > 9% 剔除
  - check_3day_cumulative_gain: 连续 3 日累计涨幅 > 20% 剔除
- BlackWhiteListManager: 黑白名单管理（事前）
  - add_to_blacklist / remove_from_blacklist
  - add_to_whitelist / remove_from_whitelist
  - is_blacklisted / is_whitelisted
  - get_blacklist / get_whitelist
- PositionRiskChecker: 事中风控（仓位与破位检测）
  - check_stock_position_limit: 单只个股仓位 ≤ 15%
  - check_sector_position_limit: 单一板块仓位 ≤ 30%
  - check_position_breakdown: 持仓破位预警（跌破 MA20 + 放量下跌 > 5%）
- RiskGateway: 交易执行链路风控网关（需求 1）
  - check_order_risk_pure: 纯函数版本的风控校验链
  - check_and_submit: 执行风控校验链并提交委托
- build_stop_loss_alert_message: 构建止损预警 JSON 消息（需求 2）
- is_risk_alert_active: 交易时段判断，非交易时段抑制推送（需求 2）
- StopLossChecker: 事后止损止盈控制
  - check_fixed_stop_loss: 固定比例止损（5%/8%/10%）
  - check_trailing_stop_loss: 移动止损（跟踪最高价回撤 3%/5%）
  - check_trend_stop_loss: 趋势止损（跌破关键均线）
  - check_strategy_health: 策略风险预警（胜率 < 50% 或最大回撤 > 15%）

对应需求：
- 需求 9.1：大盘跌破 20 日均线 → 阈值从 80 提升至 90
- 需求 9.2：大盘跌破 60 日均线 → 暂停所有买入信号
- 需求 9.3：个股单日涨幅 > 9% → 剔除
- 需求 9.4：个股连续 3 日累计涨幅 > 20% → 剔除
- 需求 9.5：黑名单/白名单手动维护
- 需求 10.1：单只个股仓位 ≤ 15%，超出拒绝买入并预警
- 需求 10.2：单一板块仓位 ≤ 30%，超出拒绝买入并预警
- 需求 10.3：持仓跌破 20 日均线且放量下跌 > 5% → 减仓预警
- 需求 11.1：固定比例止损（5%/8%/10%）
- 需求 11.2：移动止损（跟踪最高价回撤 3%/5%）
- 需求 11.3：趋势止损（跌破关键均线）
- 需求 11.4：策略胜率 < 50% 或最大回撤 > 15% → 策略风险预警
"""

from __future__ import annotations

from dataclasses import dataclass, field

import logging

from app.core.schemas import (
    MarketRiskLevel,
    OrderDirection,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    RiskCheckResult,
)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_NORMAL_THRESHOLD = 80.0    # 正常市场趋势打分阈值
_CAUTION_THRESHOLD = 90.0   # 警戒市场趋势打分阈值

_DAILY_GAIN_LIMIT = 9.0     # 单日涨幅剔除阈值 (%)
_3DAY_GAIN_LIMIT = 20.0     # 连续 3 日累计涨幅剔除阈值 (%)

_MA20_PERIOD = 20
_MA60_PERIOD = 60

_STOCK_POSITION_LIMIT = 15.0    # 单只个股仓位上限 (%)
_SECTOR_POSITION_LIMIT = 30.0   # 单一板块仓位上限 (%)
_BREAKDOWN_DECLINE_THRESHOLD = -5.0  # 破位下跌幅度阈值 (%)
_BREAKDOWN_VOLUME_RATIO = 1.0   # 破位放量阈值（量比）


# ---------------------------------------------------------------------------
# MarketRiskChecker — 大盘风控
# ---------------------------------------------------------------------------

class MarketRiskChecker:
    """
    大盘风控状态检测器。

    根据指数收盘价序列计算 20 日 / 60 日均线，
    判定当前大盘风险等级：NORMAL / CAUTION / DANGER。
    """

    @staticmethod
    def _simple_ma(closes: list[float], period: int) -> float | None:
        """计算最近 period 日的简单移动平均线值。数据不足返回 None。"""
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period

    def check_market_risk(
        self,
        index_closes: list[float],
        market_breadth: float | None = None,
        volume_change_rate: float | None = None,
        breadth_threshold: float = 0.5,
    ) -> MarketRiskLevel:
        """
        根据指数收盘价序列和多维度市场数据判定大盘风险等级。

        规则：
        1. 先用均线逻辑计算基础风险等级：
           - 最新收盘价 < 60 日均线 → DANGER
           - 最新收盘价 < 20 日均线 → CAUTION
           - 其他 → NORMAL
        2. 若 market_breadth 可用且 < breadth_threshold，风险等级提升一级：
           - NORMAL → CAUTION
           - CAUTION → DANGER
           - DANGER 保持不变（已是最高级别）
        3. market_breadth 为 None 时仅使用均线判定（降级为现有逻辑）

        数据不足以计算均线时，保守返回 NORMAL（不自动放宽风控）。

        Args:
            index_closes: 指数收盘价序列（按时间升序）
            market_breadth: 市场广度（涨跌比 = 上涨数/下跌数），None 表示不可用
            volume_change_rate: 成交量变化率（预留参数，当前未使用）
            breadth_threshold: 市场广度阈值，低于此值时提升风险等级，默认 0.5

        Returns:
            MarketRiskLevel 枚举值
        """
        if not index_closes:
            return MarketRiskLevel.NORMAL

        current_price = index_closes[-1]

        # 第一步：均线逻辑计算基础风险等级
        base_level = MarketRiskLevel.NORMAL

        # 先检查 60 日均线（更严格的条件优先）
        ma60 = self._simple_ma(index_closes, _MA60_PERIOD)
        if ma60 is not None and current_price < ma60:
            base_level = MarketRiskLevel.DANGER
        else:
            # 再检查 20 日均线
            ma20 = self._simple_ma(index_closes, _MA20_PERIOD)
            if ma20 is not None and current_price < ma20:
                base_level = MarketRiskLevel.CAUTION

        # 第二步：市场广度维度提升风险等级
        if market_breadth is not None and market_breadth < breadth_threshold:
            base_level = self._escalate_risk_level(base_level)

        return base_level

    @staticmethod
    def _escalate_risk_level(level: MarketRiskLevel) -> MarketRiskLevel:
        """
        将风险等级提升一级（纯函数）。

        NORMAL → CAUTION, CAUTION → DANGER, DANGER 保持不变。

        Args:
            level: 当前风险等级

        Returns:
            提升后的风险等级
        """
        if level == MarketRiskLevel.NORMAL:
            return MarketRiskLevel.CAUTION
        if level == MarketRiskLevel.CAUTION:
            return MarketRiskLevel.DANGER
        return MarketRiskLevel.DANGER

    @staticmethod
    def get_trend_threshold(risk_level: MarketRiskLevel) -> float:
        """
        根据大盘风险等级返回趋势打分阈值。

        - NORMAL → 80
        - CAUTION → 90
        - DANGER → 90（虽然买入已暂停，阈值仍为 90）

        Args:
            risk_level: 大盘风险等级

        Returns:
            趋势打分阈值
        """
        if risk_level == MarketRiskLevel.NORMAL:
            return _NORMAL_THRESHOLD
        return _CAUTION_THRESHOLD

    @staticmethod
    def is_buy_suspended(risk_level: MarketRiskLevel) -> bool:
        """
        判断是否暂停所有买入信号。

        仅 DANGER 级别暂停买入。

        Args:
            risk_level: 大盘风险等级

        Returns:
            True 表示暂停买入
        """
        return risk_level == MarketRiskLevel.DANGER

    def check_multi_index_risk(
        self, index_data: dict[str, list[float]],
    ) -> tuple[MarketRiskLevel, dict[str, dict]]:
        """多指数综合风控：取所有指数中最严重的风险等级。

        对每个指数调用 check_market_risk()，空数据的指数跳过。
        综合风险等级为所有单个指数风险等级中最严重的那个
        （DANGER > CAUTION > NORMAL）。

        对应需求 9.1、9.3：多指数风控最严重等级聚合。

        Args:
            index_data: 指数代码 → 收盘价序列映射，
                        如 {"000001.SH": [3100.0, 3120.0, ...], ...}

        Returns:
            (综合风险等级, {指数代码: {"risk_level": MarketRiskLevel, "above_ma20": bool, "above_ma60": bool}})
        """
        _severity = {
            MarketRiskLevel.NORMAL: 0,
            MarketRiskLevel.CAUTION: 1,
            MarketRiskLevel.DANGER: 2,
        }

        combined_level = MarketRiskLevel.NORMAL
        details: dict[str, dict] = {}

        for code, closes in index_data.items():
            if not closes:
                continue

            risk_level = self.check_market_risk(closes)

            # 计算均线状态
            ma20 = self._simple_ma(closes, _MA20_PERIOD)
            ma60 = self._simple_ma(closes, _MA60_PERIOD)
            above_ma20 = closes[-1] >= ma20 if ma20 is not None else True
            above_ma60 = closes[-1] >= ma60 if ma60 is not None else True

            details[code] = {
                "risk_level": risk_level,
                "above_ma20": above_ma20,
                "above_ma60": above_ma60,
            }

            # 取最严重等级
            if _severity[risk_level] > _severity[combined_level]:
                combined_level = risk_level

        return combined_level, details


# ---------------------------------------------------------------------------
# StockRiskFilter — 个股风控过滤
# ---------------------------------------------------------------------------

class StockRiskFilter:
    """
    个股风控过滤器。

    检测个股是否因涨幅过大而需要从选股池中剔除。
    """

    @staticmethod
    def check_daily_gain(daily_change_pct: float) -> bool:
        """
        检查个股单日涨幅是否超过 9%。

        Args:
            daily_change_pct: 当日涨跌幅百分比（如 9.5 表示涨 9.5%）

        Returns:
            True 表示应剔除（涨幅 > 9%）
        """
        return daily_change_pct > _DAILY_GAIN_LIMIT

    @staticmethod
    def check_3day_cumulative_gain(daily_changes: list[float]) -> bool:
        """
        检查个股连续 3 个交易日累计涨幅是否超过 20%。

        累计涨幅采用复合收益率计算：
        cumulative = (1 + d1/100) * (1 + d2/100) * (1 + d3/100) - 1

        取最近 3 个交易日的数据。数据不足 3 日返回 False。

        Args:
            daily_changes: 每日涨跌幅百分比列表（按时间升序）

        Returns:
            True 表示应剔除（累计涨幅 > 20%）
        """
        if len(daily_changes) < 3:
            return False

        # 取最近 3 日
        last_3 = daily_changes[-3:]
        cumulative = 1.0
        for pct in last_3:
            cumulative *= (1.0 + pct / 100.0)
        cumulative_pct = (cumulative - 1.0) * 100.0

        return cumulative_pct > _3DAY_GAIN_LIMIT


# ---------------------------------------------------------------------------
# BlackWhiteListManager — 黑白名单管理
# ---------------------------------------------------------------------------

@dataclass
class _BlacklistEntry:
    """黑名单条目"""
    symbol: str
    reason: str


class BlackWhiteListManager:
    """
    个股黑名单/白名单管理器（内存缓存 + PostgreSQL 持久化双写）。

    - 黑名单中的股票不出现在任何选股结果中
    - 白名单中的股票不受弱势板块过滤规则影响
    - 启动时从数据库加载数据到内存缓存
    - 增删操作同时更新内存缓存和数据库，数据库失败时回滚内存变更

    对应需求：
    - 需求 3.1：启动时从 stock_list 表加载数据到内存缓存
    - 需求 3.2：添加操作同时写入内存缓存和数据库
    - 需求 3.3：删除操作同时从内存缓存和数据库删除
    - 需求 3.4：数据库写入失败时回滚内存缓存变更
    - 需求 3.7：纯函数版本便于属性测试
    """

    def __init__(self) -> None:
        self._blacklist: dict[str, str] = {}   # symbol -> reason
        self._whitelist: set[str] = set()
        self._cache: dict[str, set[str]] = {
            "BLACK": set(),
            "WHITE": set(),
        }

    # --- 数据库加载 ---

    async def load_from_db(self, session: "AsyncSession", user_id: str) -> None:
        """
        从 stock_list 表加载黑白名单数据到内存缓存。

        启动时调用，将数据库中的黑白名单数据加载到 _cache、_blacklist 和 _whitelist。

        Args:
            session: SQLAlchemy 异步 Session
            user_id: 用户 ID
        """
        from sqlalchemy import select
        from app.models.stock import StockList

        # 加载黑名单
        bl_stmt = select(StockList).where(
            StockList.list_type == "BLACK",
            StockList.user_id == user_id,
        )
        bl_result = await session.execute(bl_stmt)
        bl_rows = bl_result.scalars().all()

        self._blacklist.clear()
        self._cache["BLACK"].clear()
        for row in bl_rows:
            self._blacklist[row.symbol] = row.reason or ""
            self._cache["BLACK"].add(row.symbol)

        # 加载白名单
        wl_stmt = select(StockList).where(
            StockList.list_type == "WHITE",
            StockList.user_id == user_id,
        )
        wl_result = await session.execute(wl_stmt)
        wl_rows = wl_result.scalars().all()

        self._whitelist.clear()
        self._cache["WHITE"].clear()
        for row in wl_rows:
            self._whitelist.add(row.symbol)
            self._cache["WHITE"].add(row.symbol)

    # --- 黑名单操作 ---

    def add_to_blacklist(self, symbol: str, reason: str = "") -> None:
        """
        将股票加入黑名单（仅内存操作，向后兼容）。

        Args:
            symbol: 股票代码
            reason: 加入原因
        """
        self._blacklist[symbol] = reason
        self._cache["BLACK"].add(symbol)

    async def add_to_blacklist_persistent(
        self, symbol: str, reason: str, session: "AsyncSession", user_id: str,
    ) -> None:
        """
        将股票加入黑名单（内存缓存 + 数据库双写）。

        数据库写入失败时回滚内存缓存变更。

        Args:
            symbol: 股票代码
            reason: 加入原因
            session: SQLAlchemy 异步 Session
            user_id: 用户 ID

        Raises:
            Exception: 数据库写入失败时抛出异常
        """
        from sqlalchemy import select
        from app.models.stock import StockList

        # 记录旧状态用于回滚
        old_reason = self._blacklist.get(symbol)
        was_in_cache = symbol in self._cache["BLACK"]

        # 先更新内存缓存
        self._blacklist[symbol] = reason
        self._cache["BLACK"].add(symbol)

        try:
            # 检查数据库中是否已存在
            check_stmt = select(StockList).where(
                StockList.symbol == symbol,
                StockList.list_type == "BLACK",
                StockList.user_id == user_id,
            )
            existing = await session.execute(check_stmt)
            row = existing.scalar_one_or_none()

            if row is not None:
                # 已存在，更新 reason
                row.reason = reason
            else:
                # 不存在，新增
                entry = StockList(
                    symbol=symbol,
                    list_type="BLACK",
                    user_id=user_id,
                    reason=reason,
                )
                session.add(entry)

            await session.flush()
        except Exception:
            # 数据库写入失败，回滚内存缓存
            if old_reason is not None:
                self._blacklist[symbol] = old_reason
            else:
                self._blacklist.pop(symbol, None)
            if not was_in_cache:
                self._cache["BLACK"].discard(symbol)
            raise

    def remove_from_blacklist(self, symbol: str) -> None:
        """
        将股票从黑名单移除（仅内存操作，向后兼容）。

        Args:
            symbol: 股票代码
        """
        self._blacklist.pop(symbol, None)
        self._cache["BLACK"].discard(symbol)

    async def remove_from_blacklist_persistent(
        self, symbol: str, session: "AsyncSession", user_id: str,
    ) -> None:
        """
        将股票从黑名单移除（内存缓存 + 数据库双删）。

        数据库删除失败时回滚内存缓存变更。

        Args:
            symbol: 股票代码
            session: SQLAlchemy 异步 Session
            user_id: 用户 ID

        Raises:
            Exception: 数据库删除失败时抛出异常
        """
        from sqlalchemy import delete
        from app.models.stock import StockList

        # 记录旧状态用于回滚
        old_reason = self._blacklist.get(symbol)
        was_in_cache = symbol in self._cache["BLACK"]

        # 先更新内存缓存
        self._blacklist.pop(symbol, None)
        self._cache["BLACK"].discard(symbol)

        try:
            del_stmt = delete(StockList).where(
                StockList.symbol == symbol,
                StockList.list_type == "BLACK",
                StockList.user_id == user_id,
            )
            await session.execute(del_stmt)
            await session.flush()
        except Exception:
            # 数据库删除失败，回滚内存缓存
            if old_reason is not None:
                self._blacklist[symbol] = old_reason
            if was_in_cache:
                self._cache["BLACK"].add(symbol)
            raise

    def is_blacklisted(self, symbol: str) -> bool:
        """
        检查股票是否在黑名单中（使用内存缓存查询）。

        Args:
            symbol: 股票代码

        Returns:
            True 表示在黑名单中
        """
        return symbol in self._blacklist

    def get_blacklist(self) -> set[str]:
        """
        获取黑名单中所有股票代码。

        Returns:
            股票代码集合
        """
        return set(self._blacklist.keys())

    # --- 白名单操作 ---

    def add_to_whitelist(self, symbol: str) -> None:
        """
        将股票加入白名单（仅内存操作，向后兼容）。

        Args:
            symbol: 股票代码
        """
        self._whitelist.add(symbol)
        self._cache["WHITE"].add(symbol)

    async def add_to_whitelist_persistent(
        self, symbol: str, reason: str | None, session: "AsyncSession", user_id: str,
    ) -> None:
        """
        将股票加入白名单（内存缓存 + 数据库双写）。

        数据库写入失败时回滚内存缓存变更。

        Args:
            symbol: 股票代码
            reason: 加入原因
            session: SQLAlchemy 异步 Session
            user_id: 用户 ID

        Raises:
            Exception: 数据库写入失败时抛出异常
        """
        from sqlalchemy import select
        from app.models.stock import StockList

        # 记录旧状态用于回滚
        was_in_whitelist = symbol in self._whitelist
        was_in_cache = symbol in self._cache["WHITE"]

        # 先更新内存缓存
        self._whitelist.add(symbol)
        self._cache["WHITE"].add(symbol)

        try:
            # 检查数据库中是否已存在
            check_stmt = select(StockList).where(
                StockList.symbol == symbol,
                StockList.list_type == "WHITE",
                StockList.user_id == user_id,
            )
            existing = await session.execute(check_stmt)
            row = existing.scalar_one_or_none()

            if row is None:
                entry = StockList(
                    symbol=symbol,
                    list_type="WHITE",
                    user_id=user_id,
                    reason=reason,
                )
                session.add(entry)

            await session.flush()
        except Exception:
            # 数据库写入失败，回滚内存缓存
            if not was_in_whitelist:
                self._whitelist.discard(symbol)
            if not was_in_cache:
                self._cache["WHITE"].discard(symbol)
            raise

    def remove_from_whitelist(self, symbol: str) -> None:
        """
        将股票从白名单移除（仅内存操作，向后兼容）。

        Args:
            symbol: 股票代码
        """
        self._whitelist.discard(symbol)
        self._cache["WHITE"].discard(symbol)

    async def remove_from_whitelist_persistent(
        self, symbol: str, session: "AsyncSession", user_id: str,
    ) -> None:
        """
        将股票从白名单移除（内存缓存 + 数据库双删）。

        数据库删除失败时回滚内存缓存变更。

        Args:
            symbol: 股票代码
            session: SQLAlchemy 异步 Session
            user_id: 用户 ID

        Raises:
            Exception: 数据库删除失败时抛出异常
        """
        from sqlalchemy import delete
        from app.models.stock import StockList

        # 记录旧状态用于回滚
        was_in_whitelist = symbol in self._whitelist
        was_in_cache = symbol in self._cache["WHITE"]

        # 先更新内存缓存
        self._whitelist.discard(symbol)
        self._cache["WHITE"].discard(symbol)

        try:
            del_stmt = delete(StockList).where(
                StockList.symbol == symbol,
                StockList.list_type == "WHITE",
                StockList.user_id == user_id,
            )
            await session.execute(del_stmt)
            await session.flush()
        except Exception:
            # 数据库删除失败，回滚内存缓存
            if was_in_whitelist:
                self._whitelist.add(symbol)
            if was_in_cache:
                self._cache["WHITE"].add(symbol)
            raise

    def is_whitelisted(self, symbol: str) -> bool:
        """
        检查股票是否在白名单中（使用内存缓存查询）。

        Args:
            symbol: 股票代码

        Returns:
            True 表示在白名单中
        """
        return symbol in self._whitelist

    def get_whitelist(self) -> set[str]:
        """
        获取白名单中所有股票代码。

        Returns:
            股票代码集合
        """
        return set(self._whitelist)

    # --- 纯函数版本（用于属性测试） ---

    @staticmethod
    def is_blacklisted_pure(symbol: str, blacklist: set[str]) -> bool:
        """
        纯函数版本的黑名单查询（无实例依赖，便于属性测试）。

        Args:
            symbol: 股票代码
            blacklist: 黑名单股票代码集合

        Returns:
            True 表示在黑名单中
        """
        return symbol in blacklist

    @staticmethod
    def is_whitelisted_pure(symbol: str, whitelist: set[str]) -> bool:
        """
        纯函数版本的白名单查询（无实例依赖，便于属性测试）。

        Args:
            symbol: 股票代码
            whitelist: 白名单股票代码集合

        Returns:
            True 表示在白名单中
        """
        return symbol in whitelist


# ---------------------------------------------------------------------------
# PositionRiskChecker — 事中风控
# ---------------------------------------------------------------------------

class PositionRiskChecker:
    """
    事中风控检测器。

    提供持仓仓位上限校验和破位减仓预警：
    - 单只个股仓位不超过总资产 15%（需求 10.1）
    - 单一板块仓位不超过总资产 30%（需求 10.2）
    - 持仓跌破 20 日均线且放量下跌 > 5% 时触发减仓预警（需求 10.3）
    """

    @staticmethod
    def check_stock_position_limit(
        stock_weight: float,
        max_pct: float = _STOCK_POSITION_LIMIT,
    ) -> RiskCheckResult:
        """
        校验单只个股仓位是否超过上限。

        Args:
            stock_weight: 该个股仓位占总资产的百分比（如 12.5 表示 12.5%）
            max_pct: 仓位上限百分比，默认 15.0

        Returns:
            RiskCheckResult: passed=True 表示未超限，可以买入；
                             passed=False 表示超限，应拒绝买入并推送预警
        """
        if stock_weight > max_pct:
            return RiskCheckResult(
                passed=False,
                reason=f"单只个股仓位 {stock_weight:.2f}% 超过上限 {max_pct:.2f}%，拒绝新增买入",
            )
        return RiskCheckResult(passed=True)

    @staticmethod
    def check_sector_position_limit(
        sector_weight: float,
        max_pct: float = _SECTOR_POSITION_LIMIT,
    ) -> RiskCheckResult:
        """
        校验单一板块仓位是否超过上限。

        Args:
            sector_weight: 该板块仓位占总资产的百分比（如 25.0 表示 25.0%）
            max_pct: 仓位上限百分比，默认 30.0

        Returns:
            RiskCheckResult: passed=True 表示未超限；
                             passed=False 表示超限，应拒绝该板块新增买入并推送预警
        """
        if sector_weight > max_pct:
            return RiskCheckResult(
                passed=False,
                reason=f"板块仓位 {sector_weight:.2f}% 超过上限 {max_pct:.2f}%，拒绝该板块新增买入",
            )
        return RiskCheckResult(passed=True)

    @staticmethod
    def check_position_breakdown(
        current_price: float,
        ma20: float,
        daily_change_pct: float,
        volume_ratio: float,
    ) -> bool:
        """
        检测持仓个股是否触发破位减仓预警。

        触发条件（三个条件同时满足）：
        1. 当前价格跌破 20 日均线（current_price < ma20）
        2. 当日跌幅超过 5%（daily_change_pct < -5%）
        3. 放量（volume_ratio > 1.0，即当日成交量大于近期均量）

        Args:
            current_price: 当前价格
            ma20: 20 日移动平均线值
            daily_change_pct: 当日涨跌幅百分比（如 -6.0 表示跌 6%）
            volume_ratio: 量比（当日成交量 / 近期均量）

        Returns:
            True 表示应触发减仓/平仓预警
        """
        below_ma20 = current_price < ma20
        heavy_decline = daily_change_pct < _BREAKDOWN_DECLINE_THRESHOLD
        heavy_volume = volume_ratio > _BREAKDOWN_VOLUME_RATIO
        return below_ma20 and heavy_decline and heavy_volume

    @staticmethod
    def check_position_breakdown_relaxed(
        current_price: float,
        ma20: float,
        daily_change_pct: float,
        volume_ratio: float,
    ) -> bool:
        """放宽版破位检测：三个条件满足其中两个即触发。

        三个条件：
        1. 当前价格跌破 20 日均线（current_price < ma20）
        2. 当日跌幅超过 5%（daily_change_pct < -5%）
        3. 放量（volume_ratio > 2.0，即当日成交量大于近期均量 2 倍）

        当恰好两个或三个条件为真时返回 True，
        当零个或一个条件为真时返回 False。

        对应需求 7.3：将现有破位检测条件从「三个条件全部满足」改为
        「三个条件满足其中两个」即触发预警。

        Args:
            current_price: 当前价格
            ma20: 20 日移动平均线值
            daily_change_pct: 当日涨跌幅百分比（如 -6.0 表示跌 6%）
            volume_ratio: 量比（当日成交量 / 近期均量）

        Returns:
            True 表示应触发急跌破位预警
        """
        below_ma20 = current_price < ma20
        heavy_decline = daily_change_pct < _BREAKDOWN_DECLINE_THRESHOLD
        heavy_volume = volume_ratio > 2.0
        count = sum([below_ma20, heavy_decline, heavy_volume])
        return count >= 2

    @staticmethod
    def check_consecutive_decline_pure(
        closes: list[float],
        n_days: int = 3,
        threshold_pct: float = 8.0,
    ) -> bool:
        """连续阴跌检测：连续 N 个交易日下跌且累计跌幅超过阈值。

        仅依赖最近 N+1 个收盘价数据（局部性不变量）。
        当数据不足 N+1 个时返回 False。

        检测逻辑：
        1. 取最近 N+1 个收盘价
        2. 检查最近 N 个交易日是否每日收盘价均低于前一日
        3. 计算累计跌幅 = (最早收盘价 - 最新收盘价) / 最早收盘价 × 100
        4. 累计跌幅超过阈值时返回 True

        对应需求 7.1、7.6：连续阴跌检测，局部性不变量。

        Args:
            closes: 收盘价序列（按时间升序）
            n_days: 连续下跌天数，默认 3
            threshold_pct: 累计跌幅阈值百分比，默认 8.0

        Returns:
            True 表示应触发阴跌破位预警
        """
        if len(closes) < n_days + 1:
            return False

        # 仅使用最近 N+1 个数据点
        recent = closes[-(n_days + 1):]

        # 检查连续 N 个交易日是否每日下跌
        for i in range(1, len(recent)):
            if recent[i] >= recent[i - 1]:
                return False

        # 计算累计跌幅
        start_price = recent[0]
        end_price = recent[-1]
        if start_price <= 0:
            return False
        cumulative_decline_pct = (start_price - end_price) / start_price * 100.0

        return cumulative_decline_pct > threshold_pct

    # --- 行业仓位计算（需求 6）---

    @staticmethod
    def compute_industry_positions_pure(
        positions: list[dict],
        industry_map: dict[str, str],
    ) -> dict[str, float]:
        """纯函数版本：计算各行业仓位占比。

        按申万一级行业汇总持仓市值并计算各行业仓位占比，
        缺失行业数据的股票归入「未分类」。

        Args:
            positions: 持仓列表，每个字典包含 "symbol" 和 "market_value"
            industry_map: 股票代码 → 行业名称映射，如 {"600000": "银行", "000001": "半导体"}

        Returns:
            各行业仓位占比字典，如 {"银行": 30.5, "半导体": 15.2, "未分类": 5.0}
            百分比值，所有值之和等于总仓位占比（允许浮点精度误差 ≤ 0.01%）
        """
        if not positions:
            return {}

        total_market_value = sum(p["market_value"] for p in positions)
        if total_market_value <= 0:
            return {}

        # 按行业汇总市值
        industry_values: dict[str, float] = {}
        for pos in positions:
            symbol = pos["symbol"]
            mv = pos["market_value"]
            industry = industry_map.get(symbol, "未分类")
            industry_values[industry] = industry_values.get(industry, 0.0) + mv

        # 计算各行业占比
        result: dict[str, float] = {}
        for industry, value in industry_values.items():
            result[industry] = value / total_market_value * 100.0

        return result

    # --- 总仓位控制（需求 5）---

    @staticmethod
    def compute_total_position_pct(
        total_market_value: float, available_cash: float,
    ) -> float:
        """计算总仓位比例 = 持仓总市值 / (持仓总市值 + 可用现金) × 100。

        当持仓市值和可用现金均为 0 时返回 0.0（不触发超限）。
        当可用现金为 0（且市值 > 0）时返回 100.0。
        当持仓市值为 0 时返回 0.0。

        Args:
            total_market_value: 持仓总市值（≥ 0）
            available_cash: 可用现金（≥ 0）

        Returns:
            总仓位比例百分比，范围 [0, 100]
        """
        total_assets = total_market_value + available_cash
        if total_assets <= 0:
            return 0.0
        return total_market_value / total_assets * 100.0

    @staticmethod
    def check_total_position_limit(
        total_market_value: float, available_cash: float, limit_pct: float,
    ) -> RiskCheckResult:
        """检查总仓位是否超过上限。

        Args:
            total_market_value: 持仓总市值（≥ 0）
            available_cash: 可用现金（≥ 0）
            limit_pct: 总仓位上限百分比（如 80.0 表示 80%）

        Returns:
            RiskCheckResult: passed=True 表示未超限；
                             passed=False 表示超限，应拒绝新的买入委托
        """
        pct = PositionRiskChecker.compute_total_position_pct(
            total_market_value, available_cash,
        )
        if pct > limit_pct:
            return RiskCheckResult(
                passed=False,
                reason=f"总仓位 {pct:.2f}% 超过上限 {limit_pct:.2f}%，拒绝买入",
            )
        return RiskCheckResult(passed=True)

    @staticmethod
    def get_total_position_limit_by_risk_level(
        risk_level: MarketRiskLevel,
    ) -> float:
        """根据大盘风险等级返回总仓位上限。

        映射关系：
        - NORMAL → 80.0%
        - CAUTION → 60.0%
        - DANGER → 30.0%

        Args:
            risk_level: 大盘风险等级

        Returns:
            总仓位上限百分比
        """
        _LIMIT_MAP = {
            MarketRiskLevel.NORMAL: 80.0,
            MarketRiskLevel.CAUTION: 60.0,
            MarketRiskLevel.DANGER: 30.0,
        }
        return _LIMIT_MAP.get(risk_level, 80.0)


# ---------------------------------------------------------------------------
# StopLossChecker — 事后止损止盈
# ---------------------------------------------------------------------------

_STRATEGY_WIN_RATE_THRESHOLD = 0.5      # 策略胜率预警阈值
_STRATEGY_MAX_DRAWDOWN_THRESHOLD = 0.15  # 策略最大回撤预警阈值


class StopLossChecker:
    """
    事后止损止盈检测器。

    提供四种止损/止盈检测方式：
    - 固定比例止损：持仓亏损达到设定比例（5%/8%/10%）时触发（需求 11.1）
    - 移动止损：价格从持仓期间最高价回撤达到设定比例（3%/5%）时触发（需求 11.2）
    - 趋势止损：收盘价跌破用户指定的关键均线时触发（需求 11.3）
    - 策略风险预警：策略胜率 < 50% 或最大回撤 > 15% 时触发（需求 11.4）
    """

    @staticmethod
    def check_fixed_stop_loss(
        cost_price: float,
        current_price: float,
        stop_pct: float,
    ) -> bool:
        """
        检查是否触发固定比例止损。

        当持仓亏损比例 >= stop_pct 时触发。
        亏损比例 = (cost_price - current_price) / cost_price

        Args:
            cost_price: 持仓成本价（必须 > 0）
            current_price: 当前价格
            stop_pct: 止损比例（如 0.05 表示 5%）

        Returns:
            True 表示应触发止损预警
        """
        if cost_price <= 0:
            return False
        loss_pct = (cost_price - current_price) / cost_price
        return loss_pct >= stop_pct

    @staticmethod
    def check_trailing_stop_loss(
        peak_price: float,
        current_price: float,
        retrace_pct: float,
    ) -> bool:
        """
        检查是否触发移动止损（跟踪最高价回撤）。

        当价格从最高价回撤比例 >= retrace_pct 时触发。
        回撤比例 = (peak_price - current_price) / peak_price

        Args:
            peak_price: 持仓期间最高价（必须 > 0）
            current_price: 当前价格
            retrace_pct: 回撤止损比例（如 0.03 表示 3%）

        Returns:
            True 表示应触发移动止损预警
        """
        if peak_price <= 0:
            return False
        retrace = (peak_price - current_price) / peak_price
        return retrace >= retrace_pct

    @staticmethod
    def check_trend_stop_loss(
        current_price: float,
        ma_value: float,
    ) -> bool:
        """
        检查是否触发趋势止损（跌破关键均线）。

        当收盘价 < 用户指定的关键均线值时触发。

        Args:
            current_price: 当前收盘价
            ma_value: 用户指定的关键均线值

        Returns:
            True 表示应触发趋势止损预警
        """
        return current_price < ma_value

    @staticmethod
    def check_strategy_health(
        win_rate: float,
        max_drawdown: float,
    ) -> bool:
        """
        检查策略是否处于不健康状态。

        当策略胜率 < 50% 或最大回撤 > 15% 时判定为不健康。

        Args:
            win_rate: 策略胜率，范围 [0, 1]（如 0.45 表示 45%）
            max_drawdown: 策略最大回撤，范围 [0, 1]（如 0.20 表示 20%）

        Returns:
            True 表示策略不健康，应触发风险预警
        """
        return win_rate < _STRATEGY_WIN_RATE_THRESHOLD or max_drawdown > _STRATEGY_MAX_DRAWDOWN_THRESHOLD

    # --- ATR 自适应止损方法（需求 4）---

    @staticmethod
    def compute_atr_fixed_stop_price(
        cost_price: float, atr: float, multiplier: float = 2.0,
    ) -> float:
        """ATR 自适应固定止损价 = 成本价 - ATR × 倍数。

        Args:
            cost_price: 持仓成本价（必须 > 0）
            atr: 14 日 ATR 值（必须 > 0）
            multiplier: ATR 倍数，默认 2.0

        Returns:
            固定止损触发价
        """
        return cost_price - atr * multiplier

    @staticmethod
    def compute_atr_trailing_retrace_pct(
        atr: float, peak_price: float, multiplier: float = 1.5,
    ) -> float:
        """ATR 自适应移动止损回撤比例 = ATR × 倍数 / 最高价。

        Args:
            atr: 14 日 ATR 值（必须 > 0）
            peak_price: 持仓期间最高价（必须 > 0）
            multiplier: ATR 倍数，默认 1.5

        Returns:
            移动止损回撤比例（如 0.03 表示 3%）
        """
        if peak_price <= 0:
            return 0.0
        return atr * multiplier / peak_price

    @staticmethod
    def compute_atr_stop_loss_pure(
        cost_price: float,
        current_price: float,
        peak_price: float,
        atr: float,
        fixed_multiplier: float,
        trailing_multiplier: float,
    ) -> dict:
        """纯函数版本：同时计算 ATR 自适应固定止损和移动止损触发状态。

        Args:
            cost_price: 持仓成本价
            current_price: 当前价格
            peak_price: 持仓期间最高价
            atr: 14 日 ATR 值
            fixed_multiplier: 固定止损 ATR 倍数
            trailing_multiplier: 移动止损 ATR 倍数

        Returns:
            字典包含：
            - fixed_stop_price: 固定止损触发价
            - fixed_triggered: 是否触发固定止损
            - trailing_retrace_pct: 移动止损回撤比例
            - trailing_triggered: 是否触发移动止损
        """
        fixed_stop_price = StopLossChecker.compute_atr_fixed_stop_price(
            cost_price, atr, fixed_multiplier,
        )
        fixed_triggered = current_price <= fixed_stop_price

        trailing_retrace_pct = StopLossChecker.compute_atr_trailing_retrace_pct(
            atr, peak_price, trailing_multiplier,
        )
        # 计算实际回撤比例
        actual_retrace = (peak_price - current_price) / peak_price if peak_price > 0 else 0.0
        trailing_triggered = actual_retrace >= trailing_retrace_pct

        return {
            "fixed_stop_price": fixed_stop_price,
            "fixed_triggered": fixed_triggered,
            "trailing_retrace_pct": trailing_retrace_pct,
            "trailing_triggered": trailing_triggered,
        }


# ---------------------------------------------------------------------------
# SectorConcentrationChecker — 板块集中度风控
# ---------------------------------------------------------------------------

_SECTOR_CONCENTRATION_THRESHOLD = 30.0  # 板块集中度预警阈值 (%)

logger = logging.getLogger(__name__)


class SectorConcentrationChecker:
    """
    板块集中度风控检测器。

    基于板块成分数据计算持仓的板块集中度，当单一板块的持仓股票数量占比
    或持仓市值占比超过配置阈值时生成预警。

    对应需求：
    - 需求 9.1：查询持仓股票所属板块
    - 需求 9.2：持仓股票数量占板块成分股总数比例超阈值 → 预警
    - 需求 9.3：持仓市值占总持仓市值比例超阈值 → 预警
    - 需求 9.4：支持配置板块集中度阈值，默认 30%
    - 需求 9.5：板块数据不可用时跳过检查，不阻塞其他风控
    """

    def __init__(
        self,
        threshold_pct: float = _SECTOR_CONCENTRATION_THRESHOLD,
    ) -> None:
        """
        Args:
            threshold_pct: 板块集中度预警阈值百分比，默认 30.0
        """
        self.threshold_pct = threshold_pct

    async def check_sector_concentration(
        self,
        positions: list[Position],
    ) -> list[dict]:
        """
        检查持仓的板块集中度。

        对每只持仓股票查询其所属板块，汇总计算每个板块的：
        - 持仓股票数 / 成分股总数（count_ratio）
        - 板块持仓市值 / 总持仓市值（value_ratio）

        当任一比率超过阈值时生成预警。

        Args:
            positions: 持仓列表，每个元素需有 symbol 和 market_value 属性

        Returns:
            预警字典列表，每个字典包含：
            - sector_code: 板块代码
            - sector_name: 板块名称（如可获取）
            - count_ratio: 持仓股票数占比 (%)
            - value_ratio: 持仓市值占比 (%)
            - warning_type: 预警类型 ("count" / "value" / "both")
        """
        try:
            from app.services.data_engine.sector_repository import SectorRepository

            repo = SectorRepository()
            return await self._compute_concentration(positions, repo)
        except Exception:
            logger.warning(
                "板块成分数据不可用，跳过板块集中度检查",
                exc_info=True,
            )
            return []

    async def _compute_concentration(
        self,
        positions: list[Position],
        repo: "SectorRepository",
    ) -> list[dict]:
        """内部计算逻辑，分离以便测试。"""
        if not positions:
            return []

        # 总持仓市值
        total_market_value = sum(
            float(p.market_value) for p in positions
        )
        if total_market_value <= 0:
            return []

        # 收集每只股票所属板块
        # sector_code → { "name": str, "symbols": set, "market_value": float, "constituent_count": int }
        sector_map: dict[str, dict] = {}

        for pos in positions:
            try:
                constituents = await repo.get_sectors_by_stock(pos.symbol)
            except Exception:
                logger.warning(
                    "查询股票 %s 所属板块失败，跳过", pos.symbol, exc_info=True,
                )
                continue

            for c in constituents:
                code = c.sector_code
                if code not in sector_map:
                    sector_map[code] = {
                        "name": "",
                        "symbols": set(),
                        "market_value": 0.0,
                        "constituent_count": 0,
                    }
                sector_map[code]["symbols"].add(pos.symbol)
                sector_map[code]["market_value"] += float(pos.market_value)

        # 查询每个板块的成分股总数和名称
        for code, info in sector_map.items():
            try:
                # 获取板块信息（名称和成分股数量）
                from app.models.sector import DataSource

                sector_list = await repo.get_sector_list()
                for si in sector_list:
                    if si.sector_code == code:
                        info["name"] = si.name
                        if si.constituent_count is not None:
                            info["constituent_count"] = si.constituent_count
                        break

                # 如果 constituent_count 仍为 0，尝试从成分表计数
                if info["constituent_count"] == 0:
                    for ds in DataSource:
                        constituents = await repo.get_constituents(code, ds)
                        if constituents:
                            info["constituent_count"] = len(constituents)
                            break
            except Exception:
                logger.warning(
                    "查询板块 %s 成分股数量失败", code, exc_info=True,
                )

        # 计算比率并生成预警
        warnings: list[dict] = []
        threshold = self.threshold_pct

        for code, info in sector_map.items():
            holding_count = len(info["symbols"])
            constituent_count = info["constituent_count"]
            sector_mv = info["market_value"]

            # 持仓股票数占比
            count_ratio = (
                (holding_count / constituent_count * 100.0)
                if constituent_count > 0
                else 0.0
            )

            # 持仓市值占比
            value_ratio = (
                (sector_mv / total_market_value * 100.0)
                if total_market_value > 0
                else 0.0
            )

            count_exceeded = count_ratio > threshold
            value_exceeded = value_ratio > threshold

            if count_exceeded or value_exceeded:
                if count_exceeded and value_exceeded:
                    warning_type = "both"
                elif count_exceeded:
                    warning_type = "count"
                else:
                    warning_type = "value"

                warnings.append({
                    "sector_code": code,
                    "sector_name": info["name"],
                    "count_ratio": round(count_ratio, 2),
                    "value_ratio": round(value_ratio, 2),
                    "warning_type": warning_type,
                })

        return warnings

    @staticmethod
    def compute_concentration_pure(
        positions: list[dict],
        sector_assignments: dict[str, list[str]],
        sector_constituent_counts: dict[str, int],
        threshold_pct: float = _SECTOR_CONCENTRATION_THRESHOLD,
    ) -> list[dict]:
        """
        纯函数版本的板块集中度计算（无数据库依赖，用于属性测试）。

        Args:
            positions: 持仓列表，每个字典包含 "symbol" 和 "market_value"
            sector_assignments: 股票 → 所属板块代码列表的映射
            sector_constituent_counts: 板块代码 → 成分股总数的映射
            threshold_pct: 预警阈值百分比

        Returns:
            预警字典列表
        """
        if not positions:
            return []

        total_market_value = sum(p["market_value"] for p in positions)
        if total_market_value <= 0:
            return []

        # 汇总每个板块的持仓信息
        sector_map: dict[str, dict] = {}

        for pos in positions:
            symbol = pos["symbol"]
            mv = pos["market_value"]
            sectors = sector_assignments.get(symbol, [])

            for code in sectors:
                if code not in sector_map:
                    sector_map[code] = {
                        "symbols": set(),
                        "market_value": 0.0,
                    }
                sector_map[code]["symbols"].add(symbol)
                sector_map[code]["market_value"] += mv

        # 计算比率并生成预警
        warnings: list[dict] = []

        for code, info in sector_map.items():
            holding_count = len(info["symbols"])
            constituent_count = sector_constituent_counts.get(code, 0)
            sector_mv = info["market_value"]

            count_ratio = (
                (holding_count / constituent_count * 100.0)
                if constituent_count > 0
                else 0.0
            )

            value_ratio = (
                (sector_mv / total_market_value * 100.0)
                if total_market_value > 0
                else 0.0
            )

            count_exceeded = count_ratio > threshold_pct
            value_exceeded = value_ratio > threshold_pct

            if count_exceeded or value_exceeded:
                if count_exceeded and value_exceeded:
                    warning_type = "both"
                elif count_exceeded:
                    warning_type = "count"
                else:
                    warning_type = "value"

                warnings.append({
                    "sector_code": code,
                    "sector_name": "",
                    "count_ratio": round(count_ratio, 2),
                    "value_ratio": round(value_ratio, 2),
                    "warning_type": warning_type,
                })

        return warnings


# ---------------------------------------------------------------------------
# RiskGateway — 交易执行链路风控网关（需求 1）
# ---------------------------------------------------------------------------


class RiskGateway:
    """交易执行链路风控网关，在委托提交前执行完整风控校验链。

    对应需求：
    - 需求 1.1：委托提交前执行完整风控校验链
    - 需求 1.2：任一检查未通过则拒绝委托
    - 需求 1.3：卖出委托跳过买入相关风控检查
    - 需求 1.4：风控通过后提交至 BrokerClient
    - 需求 1.6：异常时拒绝委托并记录异常
    - 需求 1.7：纯函数版本便于属性测试
    """

    @staticmethod
    def check_order_risk_pure(
        order: OrderRequest,
        positions: list[dict],
        blacklist: set[str],
        daily_change_pct: float,
        industry_map: dict[str, str],
        total_market_value: float,
        available_cash: float,
        total_position_limit: float,
        stock_position_limit: float = 15.0,
        sector_position_limit: float = 30.0,
    ) -> RiskCheckResult:
        """纯函数版本的风控校验（无 DB 依赖），便于属性测试。

        校验链顺序（短路求值）：
        1. 卖出委托 → 直接通过
        2. 黑名单检查
        3. 涨幅检查（当日涨幅 > 9%）
        4. 单股仓位检查
        5. 板块仓位检查
        6. 总仓位检查

        Args:
            order: 委托请求
            positions: 持仓列表，每个字典包含 "symbol"、"market_value"
            blacklist: 黑名单股票代码集合
            daily_change_pct: 委托股票当日涨跌幅百分比
            industry_map: 股票代码 → 行业名称映射
            total_market_value: 持仓总市值
            available_cash: 可用现金
            total_position_limit: 总仓位上限百分比
            stock_position_limit: 单股仓位上限百分比，默认 15.0
            sector_position_limit: 板块仓位上限百分比，默认 30.0

        Returns:
            RiskCheckResult: passed=True 表示校验通过，passed=False 表示被拒绝
        """
        # 1. 卖出委托直接通过
        if order.direction == OrderDirection.SELL:
            return RiskCheckResult(passed=True)

        # 2. 黑名单检查
        if order.symbol in blacklist:
            return RiskCheckResult(
                passed=False,
                reason=f"股票 {order.symbol} 在黑名单中，拒绝买入",
            )

        # 3. 涨幅检查
        if StockRiskFilter.check_daily_gain(daily_change_pct):
            return RiskCheckResult(
                passed=False,
                reason=f"股票 {order.symbol} 当日涨幅 {daily_change_pct:.2f}% 超过 {_DAILY_GAIN_LIMIT}%，拒绝买入",
            )

        # 4. 单股仓位检查
        total_assets = total_market_value + available_cash
        if total_assets > 0:
            # 计算该股票当前仓位占比
            stock_mv = sum(
                p["market_value"] for p in positions if p["symbol"] == order.symbol
            )
            # 加上本次委托金额
            order_amount = float(order.price or 0) * order.quantity
            new_stock_mv = stock_mv + order_amount
            stock_weight = new_stock_mv / total_assets * 100.0
            stock_check = PositionRiskChecker.check_stock_position_limit(
                stock_weight, max_pct=stock_position_limit,
            )
            if not stock_check.passed:
                return RiskCheckResult(
                    passed=False,
                    reason=stock_check.reason,
                )

        # 5. 板块仓位检查
        if total_assets > 0:
            order_industry = industry_map.get(order.symbol, "未分类")
            sector_mv = sum(
                p["market_value"]
                for p in positions
                if industry_map.get(p["symbol"], "未分类") == order_industry
            )
            order_amount = float(order.price or 0) * order.quantity
            new_sector_mv = sector_mv + order_amount
            sector_weight = new_sector_mv / total_assets * 100.0
            sector_check = PositionRiskChecker.check_sector_position_limit(
                sector_weight, max_pct=sector_position_limit,
            )
            if not sector_check.passed:
                return RiskCheckResult(
                    passed=False,
                    reason=sector_check.reason,
                )

        # 6. 总仓位检查
        total_pos_check = PositionRiskChecker.check_total_position_limit(
            total_market_value, available_cash, total_position_limit,
        )
        if not total_pos_check.passed:
            return total_pos_check

        # 所有检查通过
        return RiskCheckResult(passed=True)

    def check_and_submit(
        self,
        order: OrderRequest,
        broker: "BrokerClient",
        positions: list[Position],
        market_data: dict,
        blacklist: set[str],
        total_position_limit: float,
        session: "AsyncSession | None" = None,
        user_id: str | None = None,
    ) -> OrderResponse:
        """执行风控校验链并提交委托。

        对买入委托执行完整风控校验链，通过则提交至 BrokerClient；
        未通过则返回 REJECTED 状态的 OrderResponse（含拒绝原因），
        并记录拒绝事件到风控事件日志。
        异常时捕获并返回 REJECTED + 异常描述。

        Args:
            order: 委托请求
            broker: 券商客户端
            positions: 持仓列表
            market_data: 行情数据字典，需包含：
                - daily_change_pct: 当日涨跌幅
                - industry_map: 股票代码→行业映射
                - total_market_value: 持仓总市值
                - available_cash: 可用现金
            blacklist: 黑名单股票代码集合
            total_position_limit: 总仓位上限百分比
            session: 可选的 SQLAlchemy 异步 Session，用于记录风控事件日志
            user_id: 可选的用户 ID，用于记录风控事件日志

        Returns:
            OrderResponse: 委托响应
        """
        try:
            # 卖出委托直接提交
            if order.direction == OrderDirection.SELL:
                return broker.submit_order(order)

            # 构建纯函数参数
            positions_dicts = [
                {"symbol": p.symbol, "market_value": float(p.market_value)}
                for p in positions
            ]
            daily_change_pct = market_data.get("daily_change_pct", 0.0)
            industry_map = market_data.get("industry_map", {})
            total_market_value = market_data.get("total_market_value", 0.0)
            available_cash = market_data.get("available_cash", 0.0)

            # 执行风控校验
            result = self.check_order_risk_pure(
                order=order,
                positions=positions_dicts,
                blacklist=blacklist,
                daily_change_pct=daily_change_pct,
                industry_map=industry_map,
                total_market_value=total_market_value,
                available_cash=available_cash,
                total_position_limit=total_position_limit,
            )

            if not result.passed:
                # 记录拒绝事件到风控事件日志（不阻塞主流程）
                if session is not None and user_id is not None:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(
                                RiskEventLogger.log_event(
                                    session=session,
                                    user_id=user_id,
                                    event_type="ORDER_REJECTED",
                                    symbol=order.symbol,
                                    rule_name=result.reason or "风控校验未通过",
                                    trigger_value=0.0,
                                    threshold=0.0,
                                    result="REJECTED",
                                    triggered_at=datetime.now(),
                                )
                            )
                        else:
                            loop.run_until_complete(
                                RiskEventLogger.log_event(
                                    session=session,
                                    user_id=user_id,
                                    event_type="ORDER_REJECTED",
                                    symbol=order.symbol,
                                    rule_name=result.reason or "风控校验未通过",
                                    trigger_value=0.0,
                                    threshold=0.0,
                                    result="REJECTED",
                                    triggered_at=datetime.now(),
                                )
                            )
                    except Exception:
                        logger.error(
                            "记录风控拒绝事件失败: %s", order.symbol, exc_info=True,
                        )

                return OrderResponse(
                    order_id="",
                    symbol=order.symbol,
                    direction=order.direction,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=order.price,
                    status=OrderStatus.REJECTED,
                    message=result.reason,
                )

            # 风控通过，提交委托
            return broker.submit_order(order)

        except Exception as e:
            logger.error("风控网关异常: %s", e, exc_info=True)
            return OrderResponse(
                order_id="",
                symbol=order.symbol,
                direction=order.direction,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price,
                status=OrderStatus.REJECTED,
                message=f"风控网关异常: {e}",
            )


# ---------------------------------------------------------------------------
# 止损预警消息构建 & 交易时段判断（需求 2）
# ---------------------------------------------------------------------------

import json
from datetime import datetime, time


def build_stop_loss_alert_message(
    symbol: str,
    alert_type: str,
    current_price: float,
    trigger_threshold: float,
    alert_level: str,
    trigger_time: datetime,
) -> str:
    """构建止损预警 JSON 消息字符串。

    Args:
        symbol: 股票代码
        alert_type: 预警类型（如 "固定止损触发"、"移动止损触发"）
        current_price: 当前价格
        trigger_threshold: 触发阈值
        alert_level: 预警级别（"danger" 或 "warning"）
        trigger_time: 触发时间

    Returns:
        JSON 格式的预警消息字符串
    """
    msg = {
        "type": "risk:alert",
        "symbol": symbol,
        "alert_type": alert_type,
        "current_price": current_price,
        "trigger_threshold": trigger_threshold,
        "alert_level": alert_level,
        "trigger_time": trigger_time.isoformat(),
    }
    return json.dumps(msg, ensure_ascii=False)


# ---------------------------------------------------------------------------
# StrategyHealthMonitor — 策略实盘健康监控（需求 8）
# ---------------------------------------------------------------------------

_LIVE_WIN_RATE_THRESHOLD = 0.4          # 实盘胜率预警阈值
_LIVE_MAX_DRAWDOWN_THRESHOLD = 0.2      # 实盘最大回撤预警阈值


# ---------------------------------------------------------------------------
# 预警建议操作映射（需求 12）
# ---------------------------------------------------------------------------

# 预警类型 → 建议操作的固定映射
_SUGGESTED_ACTION_MAP: dict[str, str] = {
    "固定止损触发": "建议止损卖出",
    "移动止损触发": "建议减仓",
    "急跌破位预警": "建议关注，考虑减仓",
    "阴跌破位预警": "建议关注，考虑减仓",
    "趋势止损触发": "建议关注，考虑减仓",
}


def get_suggested_action(warning_type: str) -> str:
    """根据预警类型返回建议操作文本。

    映射规则（需求 12.2）：
    - 固定止损触发 → 「建议止损卖出」
    - 移动止损触发 → 「建议减仓」
    - 急跌破位预警 / 阴跌破位预警 / 趋势止损触发 → 「建议关注，考虑减仓」
    - 包含「仓位超限」的预警 → 「建议不再加仓」
    - 其他未知类型 → 「建议关注」

    Args:
        warning_type: 预警类型字符串

    Returns:
        建议操作文本
    """
    # 仓位超限类预警（包括「单股仓位超限」和「XX行业仓位超限」）
    if "仓位超限" in warning_type:
        return "建议不再加仓"
    return _SUGGESTED_ACTION_MAP.get(warning_type, "建议关注")


class StrategyHealthMonitor:
    """策略实盘健康监控器。

    基于最近 N 笔实盘交易记录计算胜率和最大回撤，
    判定策略实盘表现是否健康。

    对应需求：
    - 需求 8.1：基于最近 N 笔实盘交易记录计算实盘胜率和最大回撤
    - 需求 8.2：胜率 < 40% 或最大回撤 > 20% 判定为不健康
    - 需求 8.5：交易记录不足 N 笔时标注 data_sufficient=False
    - 需求 8.6：纯函数版本便于属性测试
    """

    @staticmethod
    def compute_live_health_pure(
        trade_records: list[dict], n: int = 20,
    ) -> dict:
        """纯函数版本：基于实盘交易记录计算健康指标。

        取最近 N 笔交易计算胜率（盈利笔数/总笔数）和最大回撤，
        胜率 < 40% 或回撤 > 20% 判定为不健康。
        记录不足 N 笔时标注 data_sufficient=False。

        最大回撤计算方式：
        按交易顺序累加 PnL 得到累计收益曲线，
        max_drawdown = max((peak - trough) / peak) 其中 peak > 0。
        当累计收益始终 <= 0 时，使用绝对值回撤。

        Args:
            trade_records: 交易记录列表，每条记录包含 "pnl" 字段（盈亏金额）
                           如 [{"pnl": 500.0}, {"pnl": -200.0}, ...]
            n: 最近交易笔数，默认 20

        Returns:
            字典包含：
            - win_rate: 胜率（盈利交易数 / 总交易数），无交易时为 0.0
            - max_drawdown: 最大回撤比例（0~1），无交易时为 0.0
            - is_healthy: 是否健康
            - data_sufficient: 交易记录是否充足（>= n 笔）
            - trade_count: 实际使用的交易笔数
        """
        if not trade_records:
            return {
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "is_healthy": True,
                "data_sufficient": False,
                "trade_count": 0,
            }

        # 取最近 N 笔交易
        recent = trade_records[-n:]
        trade_count = len(recent)
        data_sufficient = len(trade_records) >= n

        # 计算胜率：盈利笔数 / 总笔数（pnl > 0 视为盈利）
        profitable = sum(1 for r in recent if r.get("pnl", 0) > 0)
        win_rate = profitable / trade_count if trade_count > 0 else 0.0

        # 计算最大回撤：基于累计 PnL 曲线
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0

        for r in recent:
            pnl = r.get("pnl", 0)
            cumulative += pnl

            if cumulative > peak:
                peak = cumulative

            # 当 peak > 0 时计算相对回撤
            if peak > 0:
                drawdown = (peak - cumulative) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # 判定健康状态
        is_healthy = win_rate >= _LIVE_WIN_RATE_THRESHOLD and max_drawdown <= _LIVE_MAX_DRAWDOWN_THRESHOLD

        return {
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "is_healthy": is_healthy,
            "data_sufficient": data_sufficient,
            "trade_count": trade_count,
        }


def is_risk_alert_active(now: datetime) -> bool:
    """判断当前时间是否处于交易时段，用于决定是否推送止损预警。

    交易时段：9:25 – 15:00
    非交易时段（15:00 至次日 9:25）返回 False，抑制无效推送。

    Args:
        now: 当前时间（datetime 对象，使用其 time 部分判断）

    Returns:
        True 表示处于交易时段，应正常推送预警；
        False 表示处于非交易时段，应抑制推送。
    """
    current_time = now.time()
    trading_start = time(9, 25)
    trading_end = time(15, 0)
    return trading_start <= current_time <= trading_end


# ---------------------------------------------------------------------------
# RiskEventLogger — 风控事件日志记录器（需求 10）
# ---------------------------------------------------------------------------


class RiskEventLogger:
    """风控事件日志记录器。

    提供构建事件记录字典和异步写入数据库的方法。
    日志写入失败时仅记录 logger.error，不阻塞风控校验主流程。

    对应需求：
    - 需求 10.1：风控事件记录持久化到 PostgreSQL
    - 需求 10.2：事件记录包含完整字段
    """

    @staticmethod
    def build_event_record(
        event_type: str,
        symbol: str | None,
        rule_name: str,
        trigger_value: float,
        threshold: float,
        result: str,
        triggered_at: datetime,
    ) -> dict:
        """构建风控事件记录字典。

        Args:
            event_type: 事件类型（ORDER_REJECTED / STOP_LOSS / POSITION_LIMIT / BREAKDOWN）
            symbol: 股票代码（可为 None）
            rule_name: 触发规则名称
            trigger_value: 触发值
            threshold: 阈值
            result: 处理结果（REJECTED / WARNING）
            triggered_at: 触发时间

        Returns:
            包含所有必需字段的事件记录字典
        """
        return {
            "event_type": event_type,
            "symbol": symbol,
            "rule_name": rule_name,
            "trigger_value": trigger_value,
            "threshold": threshold,
            "result": result,
            "triggered_at": triggered_at,
        }

    @staticmethod
    async def log_event(
        session: "AsyncSession",
        user_id: str,
        event_type: str,
        symbol: str | None,
        rule_name: str,
        trigger_value: float,
        threshold: float,
        result: str,
        triggered_at: datetime,
    ) -> None:
        """将风控事件写入数据库。

        写入失败时仅记录 logger.error，不抛出异常，不阻塞主流程。

        Args:
            session: SQLAlchemy 异步 Session
            user_id: 用户 ID
            event_type: 事件类型
            symbol: 股票代码
            rule_name: 触发规则名称
            trigger_value: 触发值
            threshold: 阈值
            result: 处理结果（REJECTED / WARNING）
            triggered_at: 触发时间
        """
        try:
            from app.models.risk_event import RiskEventLog

            event = RiskEventLog(
                user_id=user_id,
                event_type=event_type,
                symbol=symbol,
                rule_name=rule_name,
                trigger_value=trigger_value,
                threshold=threshold,
                result=result,
                triggered_at=triggered_at,
            )
            session.add(event)
            await session.flush()
        except Exception:
            logger.error(
                "风控事件日志写入失败: type=%s symbol=%s rule=%s",
                event_type, symbol, rule_name,
                exc_info=True,
            )
