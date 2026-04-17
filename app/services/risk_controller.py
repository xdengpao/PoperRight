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

from app.core.schemas import MarketRiskLevel, Position, RiskCheckResult


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

    def check_market_risk(self, index_closes: list[float]) -> MarketRiskLevel:
        """
        根据指数收盘价序列判定大盘风险等级。

        规则（按严重程度从高到低判定）：
        1. 最新收盘价 < 60 日均线 → DANGER（暂停买入）
        2. 最新收盘价 < 20 日均线 → CAUTION（阈值提升至 90）
        3. 其他 → NORMAL

        数据不足以计算均线时，保守返回 NORMAL（不自动放宽风控）。

        Args:
            index_closes: 指数收盘价序列（按时间升序）

        Returns:
            MarketRiskLevel 枚举值
        """
        if not index_closes:
            return MarketRiskLevel.NORMAL

        current_price = index_closes[-1]

        # 先检查 60 日均线（更严格的条件优先）
        ma60 = self._simple_ma(index_closes, _MA60_PERIOD)
        if ma60 is not None and current_price < ma60:
            return MarketRiskLevel.DANGER

        # 再检查 20 日均线
        ma20 = self._simple_ma(index_closes, _MA20_PERIOD)
        if ma20 is not None and current_price < ma20:
            return MarketRiskLevel.CAUTION

        return MarketRiskLevel.NORMAL

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
    个股黑名单/白名单管理器（内存存储）。

    - 黑名单中的股票不出现在任何选股结果中
    - 白名单中的股票不受弱势板块过滤规则影响
    """

    def __init__(self) -> None:
        self._blacklist: dict[str, str] = {}   # symbol -> reason
        self._whitelist: set[str] = set()

    # --- 黑名单操作 ---

    def add_to_blacklist(self, symbol: str, reason: str = "") -> None:
        """
        将股票加入黑名单。

        Args:
            symbol: 股票代码
            reason: 加入原因
        """
        self._blacklist[symbol] = reason

    def remove_from_blacklist(self, symbol: str) -> None:
        """
        将股票从黑名单移除。

        Args:
            symbol: 股票代码
        """
        self._blacklist.pop(symbol, None)

    def is_blacklisted(self, symbol: str) -> bool:
        """
        检查股票是否在黑名单中。

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
        将股票加入白名单。

        Args:
            symbol: 股票代码
        """
        self._whitelist.add(symbol)

    def remove_from_whitelist(self, symbol: str) -> None:
        """
        将股票从白名单移除。

        Args:
            symbol: 股票代码
        """
        self._whitelist.discard(symbol)

    def is_whitelisted(self, symbol: str) -> bool:
        """
        检查股票是否在白名单中。

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
