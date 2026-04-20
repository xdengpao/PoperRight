"""
选股执行器（Screen Executor）

提供：
- ScreenExecutor: 选股执行核心，封装盘后选股与盘中实时选股逻辑
- export_screen_result_to_excel: 选股结果导出为 Excel（CSV）

对应需求：
- 需求 7.4：每个交易日 15:30 自动执行盘后选股
- 需求 7.5：交易时段 9:30-15:00 每 10 秒刷新实时选股
- 需求 7.6：选股结果含买入参考价、趋势强度、风险等级，支持 Excel 导出
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.schemas import (
    ChangeType,
    DEFAULT_MODULE_WEIGHTS,
    MarketRiskLevel,
    RiskLevel,
    ScreenChange,
    ScreenItem,
    ScreenResult,
    ScreenType,
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
    StrategyConfig,
)
from app.services.risk_controller import (
    BlackWhiteListManager,
    MarketRiskChecker,
    StockRiskFilter,
)
from app.services.screener.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


def _classify_risk(score: float) -> RiskLevel:
    """根据趋势强度评分划分风险等级。"""
    if score >= 80:
        return RiskLevel.LOW
    if score >= 50:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def _estimate_ref_buy_price(stock_data: dict[str, Any]) -> Decimal:
    """
    估算买入参考价。

    优先使用 stock_data 中的 close 字段；
    若不存在则回退到 ma_trend 值（仅作占位）。
    """
    close = stock_data.get("close")
    if close is not None:
        return Decimal(str(close))
    return Decimal("0")


class ScreenExecutor:
    """
    选股执行器。

    接收 StrategyConfig 和全市场股票数据，
    通过 StrategyEngine 评估后生成 ScreenResult。
    """

    def __init__(
        self,
        strategy_config: StrategyConfig,
        strategy_id: str | None = None,
        enabled_modules: list[str] | None = None,
        raw_config: dict | None = None,
        market_risk_checker: MarketRiskChecker | None = None,
        stock_risk_filter: StockRiskFilter | None = None,
        blacklist_manager: BlackWhiteListManager | None = None,
    ):
        self._config = strategy_config
        self._strategy_id = strategy_id or str(uuid.uuid4())
        self._raw_config = raw_config or {}
        # None → all modules enabled (backward compat); [] → empty set (skip all)
        self._enabled_modules: set[str] | None = (
            set(enabled_modules) if enabled_modules is not None else None
        )
        # 风控组件（需求 4）
        self._market_risk_checker = market_risk_checker or MarketRiskChecker()
        self._stock_risk_filter = stock_risk_filter or StockRiskFilter()
        self._blacklist_manager = blacklist_manager or BlackWhiteListManager()

    def run_eod_screen(
        self,
        stocks_data: dict[str, dict[str, Any]],
        index_closes: list[float] | None = None,
        previous_items: list[ScreenItem] | None = None,
    ) -> ScreenResult:
        """
        盘后全市场选股（需求 7.4）。

        Args:
            stocks_data: {symbol: stock_data} 全市场股票因子数据
            index_closes: 指数收盘价序列（按时间升序），用于大盘风控
            previous_items: 上一轮选股结果的 ScreenItem 列表，用于信号新鲜度标记（需求 8）

        Returns:
            ScreenResult（screen_type=EOD）
        """
        return self._execute(stocks_data, ScreenType.EOD, index_closes=index_closes, previous_items=previous_items)

    def run_realtime_screen(
        self,
        stocks_data: dict[str, dict[str, Any]],
        index_closes: list[float] | None = None,
        previous_items: list[ScreenItem] | None = None,
    ) -> ScreenResult:
        """
        盘中实时选股（需求 7.5）。

        Args:
            stocks_data: {symbol: stock_data} 实时因子数据
            index_closes: 指数收盘价序列（按时间升序），用于大盘风控
            previous_items: 上一轮选股结果的 ScreenItem 列表，用于信号新鲜度标记（需求 8）

        Returns:
            ScreenResult（screen_type=REALTIME）
        """
        return self._execute(stocks_data, ScreenType.REALTIME, index_closes=index_closes, previous_items=previous_items)

    # 因子名称 → 所属模块标识符的映射
    # 注意：仅映射非 factor_editor 路径需要模块启用检查的因子。
    # 板块面因子（sector_rank, sector_trend）不在此映射中，
    # 因为它们通过 factor_editor 路径评估时不应受 volume_price 模块启用状态限制。
    _FACTOR_MODULE: dict[str, str] = {
        "ma_trend": "ma_trend",
        "ma_support": "ma_trend",
        "macd": "indicator_params",
        "boll": "indicator_params",
        "rsi": "indicator_params",
        "dma": "indicator_params",
        "breakout": "breakout",
        "money_flow": "volume_price",
        "large_order": "volume_price",
        "volume_price": "volume_price",
    }

    def _is_module_enabled(self, module_key: str) -> bool:
        """检查模块是否启用。None 表示全部启用（向后兼容）。"""
        if self._enabled_modules is None:
            return True
        return module_key in self._enabled_modules

    # ------------------------------------------------------------------
    # 技术指标差异化权重与共振加分（需求 5）
    # ------------------------------------------------------------------

    # 差异化权重：按指标可靠性分配
    _INDICATOR_WEIGHTS: dict[str, float] = {
        "macd": 35.0,
        "rsi": 25.0,
        "boll": 20.0,
        "dma": 20.0,
    }

    @staticmethod
    def _compute_indicator_score(triggered: dict[str, bool]) -> float:
        """
        计算 indicator_params 模块评分（纯函数，用于属性测试）。

        差异化权重：MACD=35, RSI=25, BOLL=20, DMA=20。
        共振加分：触发数 < 2 → 0, == 2 → +10, >= 3 → +20。
        最终评分 = min(base_score + resonance_bonus, 100.0)。

        Args:
            triggered: {指标名: 是否触发}，键为 "macd"/"rsi"/"boll"/"dma"

        Returns:
            indicator_params 模块评分，范围 [0, 100]
        """
        weights = ScreenExecutor._INDICATOR_WEIGHTS

        # 基础评分：触发指标的权重之和
        base_score = sum(
            weights.get(ind, 0.0)
            for ind, is_on in triggered.items()
            if is_on
        )

        # 触发指标数量
        count = sum(1 for v in triggered.values() if v)

        # 共振加分
        if count >= 3:
            resonance_bonus = 20.0
        elif count == 2:
            resonance_bonus = 10.0
        else:
            resonance_bonus = 0.0

        return min(base_score + resonance_bonus, 100.0)

    # ------------------------------------------------------------------
    # 加权求和评分（需求 5）
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_weighted_score(
        module_scores: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> float:
        """
        加权求和计算 Trend_Score（纯函数，用于属性测试）。

        公式: Trend_Score = Σ(score × weight) / Σ(weight)
        未启用或评分为 0 的模块不计入分母。
        结果保证在 [0, 100] 闭区间内。

        Args:
            module_scores: {模块名: 评分}，评分应在 [0, 100]
            weights: {模块名: 权重}，权重 > 0；None 时使用默认权重

        Returns:
            加权求和后的趋势评分，范围 [0, 100]
        """
        if weights is None:
            weights = DEFAULT_MODULE_WEIGHTS

        numerator = 0.0
        denominator = 0.0

        for module, score in module_scores.items():
            if score <= 0.0:
                continue
            w = weights.get(module, 0.0)
            if w <= 0.0:
                continue
            numerator += score * w
            denominator += w

        if denominator <= 0.0:
            return 0.0

        result = numerator / denominator
        return max(0.0, min(100.0, result))

    # ------------------------------------------------------------------
    # 趋势加速信号检测（需求 10）
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_trend_acceleration(
        current_score: float,
        previous_score: float | None,
        acceleration_high: float = 70.0,
        acceleration_low: float = 60.0,
    ) -> bool:
        """
        检测趋势加速信号（纯函数，用于属性测试）。

        当趋势评分从低位（< acceleration_low）快速上升至高位（>= acceleration_high）时，
        判定为趋势加速。前一轮评分不可用时不触发。

        Args:
            current_score: 当前趋势评分
            previous_score: 前一轮趋势评分，None 表示无历史数据
            acceleration_high: 当前评分触发阈值，默认 70.0
            acceleration_low: 前一轮评分上限阈值，默认 60.0

        Returns:
            True 表示趋势加速信号触发，False 表示未触发
        """
        if previous_score is None:
            return False
        return current_score >= acceleration_high and previous_score < acceleration_low

    # ------------------------------------------------------------------
    # 多重突破信号构建（需求 6）
    # ------------------------------------------------------------------

    @staticmethod
    def _build_breakout_signals(
        stock_data: dict[str, Any],
    ) -> list[SignalDetail]:
        """
        从 stock_data 中的突破数据构建 SignalDetail 列表（纯函数，用于属性测试）。

        支持两种数据格式：
        1. 新格式：breakout_list: list[dict]，为每个有效突破生成独立 SignalDetail
        2. 旧格式（向后兼容）：breakout: dict，单个突破信号

        Args:
            stock_data: 股票因子字典，包含 breakout 和/或 breakout_list 字段

        Returns:
            list[SignalDetail]，每个有效突破类型对应一个 BREAKOUT 信号
        """
        signals: list[SignalDetail] = []

        # 优先使用新格式 breakout_list
        breakout_list = stock_data.get("breakout_list")
        if isinstance(breakout_list, list) and breakout_list:
            for bo in breakout_list:
                if not isinstance(bo, dict):
                    continue
                if bo.get("is_valid"):
                    is_fake = bool(bo.get("is_false_breakout", False))
                    bo_type = bo.get("type")
                    signals.append(SignalDetail(
                        category=SignalCategory.BREAKOUT,
                        label="breakout",
                        is_fake_breakout=is_fake,
                        breakout_type=bo_type,
                    ))
            return signals

        # 向后兼容：breakout 为单个字典（旧格式）
        breakout_data = stock_data.get("breakout")
        if isinstance(breakout_data, dict) and breakout_data.get("is_valid"):
            is_fake = bool(breakout_data.get("is_false_breakout", False))
            bo_type = breakout_data.get("type")
            signals.append(SignalDetail(
                category=SignalCategory.BREAKOUT,
                label="breakout",
                is_fake_breakout=is_fake,
                breakout_type=bo_type,
            ))

        return signals

    # ------------------------------------------------------------------
    # 信号强度分级（需求 7）
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_signal_strength(
        signal: SignalDetail,
        stock_data: dict[str, Any],
    ) -> SignalStrength:
        """
        根据信号类别和上下文数据计算信号强度等级（纯函数，用于属性测试）。

        规则：
        - MA_TREND：ma_trend >= 90 → STRONG，>= 70 → MEDIUM，其余 → WEAK
        - BREAKOUT：volume_ratio >= 2.0 → STRONG，>= 1.5 → MEDIUM，其余 → WEAK
        - 技术指标（MACD/BOLL/RSI/DMA）：同时触发 >= 3 个 → STRONG，2 个 → MEDIUM，1 个 → WEAK

        Args:
            signal: 待计算强度的信号详情
            stock_data: 股票因子字典，包含 ma_trend、volume_ratio 等上下文数据

        Returns:
            SignalStrength 枚举值
        """
        category = signal.category

        # 均线趋势信号强度
        if category == SignalCategory.MA_TREND:
            ma_trend_val = float(stock_data.get("ma_trend", 0.0))
            if ma_trend_val >= 90:
                return SignalStrength.STRONG
            if ma_trend_val >= 70:
                return SignalStrength.MEDIUM
            return SignalStrength.WEAK

        # 突破信号强度：根据量比
        if category == SignalCategory.BREAKOUT:
            # 优先从 breakout_list 中查找匹配的突破信号获取量比
            volume_ratio = 0.0
            breakout_list = stock_data.get("breakout_list")
            if isinstance(breakout_list, list):
                for bo in breakout_list:
                    if isinstance(bo, dict) and bo.get("type") == signal.breakout_type:
                        volume_ratio = float(bo.get("volume_ratio", 0.0))
                        break
            # 向后兼容：从单个 breakout 字典获取量比
            if volume_ratio == 0.0:
                breakout_data = stock_data.get("breakout")
                if isinstance(breakout_data, dict):
                    volume_ratio = float(breakout_data.get("volume_ratio", 0.0))

            if volume_ratio >= 2.0:
                return SignalStrength.STRONG
            if volume_ratio >= 1.5:
                return SignalStrength.MEDIUM
            return SignalStrength.WEAK

        # 技术指标信号强度（MACD/BOLL/RSI/DMA）：根据同时触发的指标数量
        _INDICATOR_CATEGORIES = {
            SignalCategory.MACD,
            SignalCategory.BOLL,
            SignalCategory.RSI,
            SignalCategory.DMA,
        }
        if category in _INDICATOR_CATEGORIES:
            triggered_count = 0
            if stock_data.get("macd"):
                triggered_count += 1
            if stock_data.get("boll"):
                triggered_count += 1
            if stock_data.get("rsi"):
                triggered_count += 1
            # DMA 需要特殊判断
            dma_data = stock_data.get("dma")
            if isinstance(dma_data, dict):
                dma_val = dma_data.get("dma", 0)
                ama_val = dma_data.get("ama", 0)
                if dma_val and ama_val and dma_val > ama_val:
                    triggered_count += 1
            elif dma_data:
                triggered_count += 1

            if triggered_count >= 3:
                return SignalStrength.STRONG
            if triggered_count >= 2:
                return SignalStrength.MEDIUM
            return SignalStrength.WEAK

        # 其他类别默认 MEDIUM
        return SignalStrength.MEDIUM

    # ------------------------------------------------------------------
    # 信号描述文本生成（需求 2）
    # ------------------------------------------------------------------

    # 突破类型中文映射
    _BREAKOUT_TYPE_CN: dict[str, str] = {
        "BOX": "箱体",
        "PREVIOUS_HIGH": "前高",
        "TRENDLINE": "趋势线",
    }

    @staticmethod
    def _generate_signal_description(
        signal: SignalDetail,
        stock_data: dict[str, Any],
    ) -> str:
        """
        根据信号类别和上下文数据生成人类可读的因子条件描述文本（纯函数，用于属性测试）。

        按信号分类从 stock_data 中提取相关因子数值，生成包含量化信息的描述文本。
        当 stock_data 缺少预期字段时返回通用描述文本，不抛异常。
        未知的 SignalCategory 返回空字符串。

        Args:
            signal: 信号详情
            stock_data: 股票因子字典

        Returns:
            描述文本字符串
        """
        category = signal.category

        # 均线趋势信号
        if category == SignalCategory.MA_TREND:
            try:
                score = stock_data.get("ma_trend")
                if score is not None:
                    return f"均线多头排列, 趋势评分 {score}"
            except (TypeError, ValueError):
                pass
            return "均线趋势信号"

        # MACD 信号（需求 1.4：使用 signal_type 和 strength 生成描述）
        if category == SignalCategory.MACD:
            signal_type = getattr(signal, "signal_type", None) or stock_data.get("macd_signal_type")
            if signal_type == "above_zero":
                return "MACD 零轴上方金叉, DIF 上穿 DEA"
            if signal_type == "below_zero_second":
                return "MACD 零轴下方二次金叉"
            return "MACD 金叉, DIF 上穿 DEA"

        # 布林带信号（需求 2.2, 2.4：near_upper_band 时附加风险提示）
        if category == SignalCategory.BOLL:
            near_upper = stock_data.get("boll_near_upper_band", False)
            hold_days = stock_data.get("boll_hold_days", 0)
            base_desc = f"价格站稳布林带中轨 {hold_days} 日" if hold_days > 0 else "价格突破布林带中轨"
            if near_upper:
                return f"{base_desc}, ⚠️ 接近上轨注意风险"
            return base_desc

        # RSI 信号（需求 3.4：使用 current_rsi 生成描述）
        if category == SignalCategory.RSI:
            try:
                rsi_val = stock_data.get("rsi_current")
                if rsi_val is not None and rsi_val > 0:
                    return f"RSI(14) = {rsi_val:.1f}, 处于强势区间"
            except (TypeError, ValueError):
                pass
            return "RSI 强势信号"

        # DMA 信号
        if category == SignalCategory.DMA:
            try:
                dma_data = stock_data.get("dma")
                if isinstance(dma_data, dict):
                    dma_val = dma_data.get("dma")
                    if dma_val is not None:
                        return f"DMA 上穿 AMA, DMA={dma_val}"
            except (TypeError, ValueError):
                pass
            return "DMA 趋势信号"

        # 形态突破信号
        if category == SignalCategory.BREAKOUT:
            try:
                # 获取突破类型的中文名
                bo_type = signal.breakout_type
                type_cn = ScreenExecutor._BREAKOUT_TYPE_CN.get(bo_type or "", bo_type or "")

                # 从 breakout_list 或 breakout 中获取量比
                volume_ratio = 0.0
                breakout_list = stock_data.get("breakout_list")
                if isinstance(breakout_list, list):
                    for bo in breakout_list:
                        if isinstance(bo, dict) and bo.get("type") == bo_type:
                            volume_ratio = float(bo.get("volume_ratio", 0.0))
                            break
                if volume_ratio == 0.0:
                    breakout_data = stock_data.get("breakout")
                    if isinstance(breakout_data, dict):
                        volume_ratio = float(breakout_data.get("volume_ratio", 0.0))

                if type_cn and volume_ratio > 0:
                    return f"{type_cn}突破, 量比 {volume_ratio:.1f} 倍"
                if type_cn:
                    return f"{type_cn}突破"
            except (TypeError, ValueError):
                pass
            return "形态突破信号"

        # 资金流入信号（固定文本）
        if category == SignalCategory.CAPITAL_INFLOW:
            return "主力资金净流入"

        # 大单活跃信号（固定文本）
        if category == SignalCategory.LARGE_ORDER:
            return "大单成交活跃"

        # 均线支撑信号（固定文本）
        if category == SignalCategory.MA_SUPPORT:
            return "回调至均线获支撑"

        # 板块强势信号（需求 10.7：包含具体板块名称）
        if category == SignalCategory.SECTOR_STRONG:
            sector_name = stock_data.get("sector_name")
            if sector_name:
                return f"所属板块【{sector_name}】涨幅排名前列"
            return "所属板块涨幅排名前列"

        # 未知信号类别
        return ""

    # ------------------------------------------------------------------
    # 信号新鲜度标记（需求 8）
    # ------------------------------------------------------------------

    @staticmethod
    def _mark_signal_freshness(
        current_signals: list[SignalDetail],
        previous_signals: list[SignalDetail] | None,
    ) -> list[SignalDetail]:
        """
        标记信号新鲜度（纯函数，用于属性测试）。

        比较当前信号列表与上一轮信号列表，按 (category, label) 元组判断信号是否相同：
        - 存在于上一轮的信号 → CONTINUING
        - 不存在于上一轮的信号 → NEW
        - 上一轮为空（None 或空列表）时，所有信号标记为 NEW

        Args:
            current_signals: 当前轮次的信号列表
            previous_signals: 上一轮的信号列表，None 表示无上一轮数据

        Returns:
            标记了新鲜度的信号列表（原列表的浅拷贝，freshness 字段已更新）
        """
        # 上一轮为空时，所有信号标记为 NEW
        if not previous_signals:
            for sig in current_signals:
                sig.freshness = SignalFreshness.NEW
            return current_signals

        # 构建上一轮信号的 (category, label) 集合
        prev_signal_keys: set[tuple[str, str]] = {
            (s.category, s.label) for s in previous_signals
        }

        for sig in current_signals:
            key = (sig.category, sig.label)
            if key in prev_signal_keys:
                sig.freshness = SignalFreshness.CONTINUING
            else:
                sig.freshness = SignalFreshness.NEW

        return current_signals

    # ------------------------------------------------------------------
    # 选股结果变化检测（需求 10）
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_result_diff(
        current_items: list[ScreenItem],
        previous_items: list[ScreenItem] | None,
    ) -> list[ScreenChange]:
        """
        计算当前选股结果与上一轮结果的差异（纯函数，用于属性测试）。

        比较规则（按 symbol 索引）：
        - 本轮有、上轮无 → change_type=NEW
        - 两轮都有但信号列表不同（按 (category, label) 集合比较）→ change_type=UPDATED
        - 上轮有、本轮无 → change_type=REMOVED
        - 两轮都有且信号列表相同 → 不出现在 changes 中

        Args:
            current_items: 当前轮次的选股结果列表
            previous_items: 上一轮的选股结果列表，None 表示无上一轮数据

        Returns:
            变化列表，仅包含发生变化的股票
        """
        changes: list[ScreenChange] = []

        # 构建当前结果的 symbol → ScreenItem 映射
        current_by_symbol: dict[str, ScreenItem] = {
            item.symbol: item for item in current_items
        }

        # 构建上一轮结果的 symbol → ScreenItem 映射
        prev_by_symbol: dict[str, ScreenItem] = {}
        if previous_items:
            for item in previous_items:
                prev_by_symbol[item.symbol] = item

        # 检测 NEW 和 UPDATED
        for symbol, cur_item in current_by_symbol.items():
            prev_item = prev_by_symbol.get(symbol)
            if prev_item is None:
                # 本轮有、上轮无 → NEW
                changes.append(ScreenChange(
                    symbol=symbol,
                    change_type=ChangeType.NEW,
                    item=cur_item,
                ))
            else:
                # 两轮都有，比较信号列表（按 (category, label) 集合）
                cur_signal_keys = {
                    (s.category, s.label) for s in cur_item.signals
                }
                prev_signal_keys = {
                    (s.category, s.label) for s in prev_item.signals
                }
                if cur_signal_keys != prev_signal_keys:
                    changes.append(ScreenChange(
                        symbol=symbol,
                        change_type=ChangeType.UPDATED,
                        item=cur_item,
                    ))

        # 检测 REMOVED：上轮有、本轮无
        for symbol in prev_by_symbol:
            if symbol not in current_by_symbol:
                changes.append(ScreenChange(
                    symbol=symbol,
                    change_type=ChangeType.REMOVED,
                    item=None,
                ))

        return changes

    # ------------------------------------------------------------------
    # 风控过滤（需求 4）
    # ------------------------------------------------------------------

    _CAUTION_THRESHOLD = 90.0  # CAUTION 状态下的趋势打分阈值
    _DANGER_STRONG_THRESHOLD = 95.0  # DANGER 模式下强势股趋势评分阈值（需求 8.3）

    def _apply_risk_filters(
        self,
        items: list[ScreenItem],
        stocks_data: dict[str, dict[str, Any]],
        index_closes: list[float] | None = None,
    ) -> tuple[list[ScreenItem], MarketRiskLevel]:
        """
        对候选股票列表应用风控过滤（需求 4）。

        处理流程：
        1. 检查大盘风险等级
        2. DANGER → 仅允许 trend_score >= 95 的强势股通过
        3. CAUTION → 仅保留 trend_score >= 90 的股票
        4. 剔除单日涨幅 > 9% 的股票
        5. 剔除黑名单中的股票

        Args:
            items: 候选股票列表
            stocks_data: {symbol: stock_data} 全市场股票因子数据
            index_closes: 指数收盘价序列（按时间升序），None 时跳过大盘风控

        Returns:
            (过滤后的股票列表, 大盘风险等级)
        """
        return self._apply_risk_filters_pure(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
            market_risk_checker=self._market_risk_checker,
            stock_risk_filter=self._stock_risk_filter,
            blacklist_manager=self._blacklist_manager,
        )

    @staticmethod
    def _apply_risk_filters_pure(
        items: list[ScreenItem],
        stocks_data: dict[str, dict[str, Any]],
        index_closes: list[float] | None,
        market_risk_checker: MarketRiskChecker,
        stock_risk_filter: StockRiskFilter,
        blacklist_manager: BlackWhiteListManager,
        danger_strong_threshold: float = 95.0,
    ) -> tuple[list[ScreenItem], MarketRiskLevel]:
        """
        纯函数版本的风控过滤，用于属性测试（无实例依赖）。

        Args:
            items: 候选股票列表
            stocks_data: {symbol: stock_data} 全市场股票因子数据
            index_closes: 指数收盘价序列
            market_risk_checker: 大盘风控检测器
            stock_risk_filter: 个股风控过滤器
            blacklist_manager: 黑白名单管理器
            danger_strong_threshold: DANGER 模式下强势股趋势评分阈值，默认 95.0

        Returns:
            (过滤后的股票列表, 大盘风险等级)
        """
        # 1. 检查大盘风险等级
        risk_level = MarketRiskLevel.NORMAL
        if index_closes is not None:
            risk_level = market_risk_checker.check_market_risk(index_closes)

        # 2. DANGER → 仅允许 trend_score >= danger_strong_threshold 的强势股通过
        if risk_level == MarketRiskLevel.DANGER:
            logger.info(
                "大盘风险等级 DANGER，仅允许趋势评分 >= %.0f 的强势股通过",
                danger_strong_threshold,
            )
            items = [
                item for item in items
                if item.trend_score >= danger_strong_threshold
            ]

        # 3. CAUTION → 仅保留 trend_score >= 90
        if risk_level == MarketRiskLevel.CAUTION:
            caution_threshold = 90.0
            items = [
                item for item in items
                if item.trend_score >= caution_threshold
            ]
            logger.info(
                "大盘风险等级 CAUTION，阈值提升至 %.0f，剩余 %d 只股票",
                caution_threshold,
                len(items),
            )

        # 4. 剔除单日涨幅 > 9% 的股票
        filtered: list[ScreenItem] = []
        for item in items:
            stock_data = stocks_data.get(item.symbol, {})
            daily_change = float(stock_data.get("daily_change_pct", 0.0))

            if stock_risk_filter.check_daily_gain(daily_change):
                logger.debug(
                    "股票 %s 单日涨幅 %.2f%% > 9%%，剔除",
                    item.symbol,
                    daily_change,
                )
                continue

            # 5. 剔除黑名单股票
            if blacklist_manager.is_blacklisted(item.symbol):
                logger.debug("股票 %s 在黑名单中，剔除", item.symbol)
                continue

            filtered.append(item)

        return filtered, risk_level

    def _execute(
        self,
        stocks_data: dict[str, dict[str, Any]],
        screen_type: ScreenType,
        index_closes: list[float] | None = None,
        previous_items: list[ScreenItem] | None = None,
    ) -> ScreenResult:
        """核心选股执行逻辑。"""
        strategy_id = (
            uuid.UUID(self._strategy_id)
            if isinstance(self._strategy_id, str)
            else self._strategy_id
        )

        # enabled_modules 为空集（非 None）→ 跳过所有筛选，返回空结果（需求 27.8）
        if self._enabled_modules is not None and not self._enabled_modules:
            return ScreenResult(
                strategy_id=strategy_id,
                screen_time=datetime.now(),
                screen_type=screen_type,
                items=[],
                is_complete=True,
            )

        # 仅当 factor_editor 启用时执行多因子评估（需求 27.7）
        if self._is_module_enabled("factor_editor"):
            passed = StrategyEngine.screen_stocks(self._config, stocks_data)
        else:
            # 不使用因子筛选时，所有股票初始通过
            passed = [
                (sym, StrategyEngine.evaluate(self._config, data))
                for sym, data in stocks_data.items()
            ]

        # 因子名称到信号分类的映射
        _FACTOR_TO_CATEGORY: dict[str, SignalCategory] = {
            "ma_trend": SignalCategory.MA_TREND,
            "macd": SignalCategory.MACD,
            "boll": SignalCategory.BOLL,
            "rsi": SignalCategory.RSI,
            "dma": SignalCategory.DMA,
            "breakout": SignalCategory.BREAKOUT,
            "money_flow": SignalCategory.CAPITAL_INFLOW,
            "large_order": SignalCategory.LARGE_ORDER,
            "ma_support": SignalCategory.MA_SUPPORT,
            "sector_rank": SignalCategory.SECTOR_STRONG,
            "sector_trend": SignalCategory.SECTOR_STRONG,
            "volume_price": SignalCategory.CAPITAL_INFLOW,
        }

        # 判断是否仅启用非 factor_editor 模块（需要从 stock_data 直接构建信号）
        use_factor_editor = self._is_module_enabled("factor_editor")

        items: list[ScreenItem] = []
        for symbol, eval_result in passed:
            stock_data = stocks_data.get(symbol, {})

            # 收集各模块评分到字典，用于加权求和（需求 5）
            module_scores: dict[str, float] = {}

            # factor_editor 模块评分
            if self._is_module_enabled("factor_editor"):
                fe_score = eval_result.weighted_score
                if fe_score > 0:
                    module_scores["factor_editor"] = fe_score

            # ma_trend 模块评分
            if self._is_module_enabled("ma_trend"):
                ma_trend_score = float(stock_data.get("ma_trend", 0.0))
                if ma_trend_score > 0:
                    module_scores["ma_trend"] = ma_trend_score

            # breakout 模块评分（需求 6：多重突破信号并发）
            # 使用 breakout_list 或向后兼容 breakout 单字典
            if self._is_module_enabled("breakout"):
                bp_score = 0.0
                breakout_list = stock_data.get("breakout_list")
                if isinstance(breakout_list, list) and breakout_list:
                    # 新格式：取所有有效突破中的最高评分
                    for bo in breakout_list:
                        if isinstance(bo, dict) and bo.get("is_valid"):
                            s = 60.0
                            if not bo.get("is_false_breakout", False):
                                s += 20.0
                            vol_ratio = bo.get("volume_ratio", 0)
                            if vol_ratio and vol_ratio > 1.5:
                                s += 20.0
                            bp_score = max(bp_score, s)
                else:
                    # 向后兼容：单字典旧格式
                    breakout_data = stock_data.get("breakout")
                    if isinstance(breakout_data, dict) and breakout_data.get("is_valid"):
                        bp_score = 60.0
                        if not breakout_data.get("is_false_breakout", False):
                            bp_score += 20.0
                        vol_ratio = breakout_data.get("volume_ratio", 0)
                        if vol_ratio and vol_ratio > 1.5:
                            bp_score += 20.0
                if bp_score > 0:
                    module_scores["breakout"] = bp_score

            # indicator_params 模块评分：差异化权重 + 共振加分（需求 5）
            if self._is_module_enabled("indicator_params"):
                # 判断各指标是否触发
                dma_triggered = False
                if stock_data.get("dma") and isinstance(stock_data["dma"], dict):
                    dma_val = stock_data["dma"].get("dma", 0)
                    ama_val = stock_data["dma"].get("ama", 0)
                    if dma_val and ama_val and dma_val > ama_val:
                        dma_triggered = True

                triggered = {
                    "macd": bool(stock_data.get("macd")),
                    "boll": bool(stock_data.get("boll")),
                    "rsi": bool(stock_data.get("rsi")),
                    "dma": dma_triggered,
                }

                ind_score = self._compute_indicator_score(triggered)
                if ind_score > 0:
                    module_scores["indicator_params"] = ind_score

            # volume_price 模块评分：资金流入 +50，大单活跃 +50
            if self._is_module_enabled("volume_price"):
                vp_score = 0.0
                if stock_data.get("money_flow"):
                    vp_score += 50.0
                if stock_data.get("large_order"):
                    vp_score += 50.0
                if vp_score > 0:
                    module_scores["volume_price"] = vp_score

            # 加权求和计算趋势评分（需求 5），替代原有 max() 竞争
            trend_score = self._compute_weighted_score(module_scores)

            # 构建 SignalDetail 列表，仅包含已启用模块的信号
            signals: list[SignalDetail] = []

            if use_factor_editor:
                # factor_editor 路径：从 eval_result.factor_results 构建信号（原有逻辑）
                for fr in eval_result.factor_results:
                    if fr.passed:
                        factor_module = self._FACTOR_MODULE.get(fr.factor_name)
                        if factor_module and not self._is_module_enabled(factor_module):
                            continue
                        category = _FACTOR_TO_CATEGORY.get(
                            fr.factor_name, SignalCategory.MA_TREND
                        )
                        signals.append(SignalDetail(
                            category=category,
                            label=fr.factor_name,
                            is_fake_breakout=False,
                        ))

            # 非 factor_editor 模块：从 stock_data 派生因子值直接构建信号
            # ma_trend 模块（需求 10：阈值降低 + 趋势加速信号）
            if self._is_module_enabled("ma_trend"):
                ma_trend_score = float(stock_data.get("ma_trend", 0))
                # 使用 MaTrendConfig 的 trend_score_threshold（默认 68）
                threshold = self._config.ma_trend.trend_score_threshold
                if ma_trend_score >= threshold:
                    signals.append(SignalDetail(
                        category=SignalCategory.MA_TREND,
                        label="ma_trend",
                    ))

                # 趋势加速信号检测（需求 10.2, 10.4, 10.5）
                previous_ma_trend_score = stock_data.get("previous_ma_trend_score")
                if previous_ma_trend_score is not None:
                    previous_ma_trend_score = float(previous_ma_trend_score)
                if self._detect_trend_acceleration(ma_trend_score, previous_ma_trend_score):
                    signals.append(SignalDetail(
                        category=SignalCategory.MA_TREND,
                        label="ma_trend_acceleration",
                        strength=SignalStrength.STRONG,
                    ))

            # indicator_params 模块
            # 适配结构化信号结果（需求 1.4, 2.2, 2.4, 3.4）：
            # 使用 stock_data 中的新字段构建更丰富的 SignalDetail。
            if self._is_module_enabled("indicator_params"):
                if stock_data.get("macd"):
                    # MACD 信号：使用结构化的 strength 和 signal_type（需求 1.4）
                    macd_strength = stock_data.get("macd_strength")
                    macd_signal_type = stock_data.get("macd_signal_type", "none")
                    signals.append(SignalDetail(
                        category=SignalCategory.MACD,
                        label="macd",
                        strength=macd_strength if macd_strength is not None else SignalStrength.MEDIUM,
                        signal_type=macd_signal_type,
                    ))
                if stock_data.get("boll"):
                    signals.append(SignalDetail(
                        category=SignalCategory.BOLL,
                        label="boll",
                    ))
                if stock_data.get("rsi"):
                    signals.append(SignalDetail(
                        category=SignalCategory.RSI,
                        label="rsi",
                    ))

            # breakout 模块（需求 6：多重突破信号并发）
            breakout_signals = self._build_breakout_signals(stock_data)
            if self._is_module_enabled("breakout"):
                signals.extend(breakout_signals)

            # volume_price 模块
            if self._is_module_enabled("volume_price"):
                if stock_data.get("money_flow"):
                    signals.append(SignalDetail(
                        category=SignalCategory.CAPITAL_INFLOW,
                        label="money_flow",
                    ))
                if stock_data.get("large_order"):
                    signals.append(SignalDetail(
                        category=SignalCategory.LARGE_ORDER,
                        label="large_order",
                    ))

            # 当仅启用非 factor_editor 模块时，过滤无信号的股票
            if not use_factor_editor and not signals:
                continue

            # 信号强度分级（需求 7）：为每个信号计算强度等级
            # 趋势加速信号的强度已在生成时显式设为 STRONG（需求 10.4），跳过重新计算
            # MACD 信号的强度已从结构化结果中获取（需求 1.4），跳过重新计算
            for sig in signals:
                if sig.label == "ma_trend_acceleration":
                    continue
                if sig.category == SignalCategory.MACD and sig.strength is not None:
                    continue
                sig.strength = self._compute_signal_strength(sig, stock_data)

            # 信号描述文本生成（需求 2.11）：为每个信号生成人类可读的因子条件描述
            for sig in signals:
                sig.description = self._generate_signal_description(sig, stock_data)

            has_fake_breakout = any(s.is_fake_breakout for s in signals)

            items.append(
                ScreenItem(
                    symbol=symbol,
                    ref_buy_price=_estimate_ref_buy_price(stock_data),
                    trend_score=trend_score,
                    risk_level=_classify_risk(trend_score),
                    signals=signals,
                    has_fake_breakout=has_fake_breakout,
                )
            )

        # 风控过滤（需求 4）：作为选股后处理步骤
        filtered_items, market_risk_level = self._apply_risk_filters(
            items=items,
            stocks_data=stocks_data,
            index_closes=index_closes,
        )

        # 为每个 ScreenItem 设置风控信息
        risk_filter_info = {"market_risk_level": market_risk_level.value}
        for item in filtered_items:
            item.market_risk_level = market_risk_level
            item.risk_filter_info = risk_filter_info

        # 信号新鲜度标记（需求 8）：比较上一轮信号列表，标记 NEW/CONTINUING
        prev_signals_by_symbol: dict[str, list[SignalDetail]] = {}
        if previous_items:
            for prev_item in previous_items:
                prev_signals_by_symbol[prev_item.symbol] = prev_item.signals

        for item in filtered_items:
            prev_signals = prev_signals_by_symbol.get(item.symbol)
            self._mark_signal_freshness(item.signals, prev_signals)
            item.has_new_signal = any(
                s.freshness == SignalFreshness.NEW for s in item.signals
            )

        # 选股结果变化检测（需求 10）：比较上一轮结果，生成变化列表
        changes = self._compute_result_diff(filtered_items, previous_items)

        return ScreenResult(
            strategy_id=strategy_id,
            screen_time=datetime.now(),
            screen_type=screen_type,
            items=filtered_items,
            is_complete=True,
            market_risk_level=market_risk_level,
            changes=changes,
        )


# ---------------------------------------------------------------------------
# Excel / CSV 导出
# ---------------------------------------------------------------------------

_CSV_HEADERS = ["股票代码", "买入参考价", "趋势强度", "风险等级", "信号详情"]


def export_screen_result_to_csv(result: ScreenResult) -> bytes:
    """
    将选股结果导出为 CSV 字节流（需求 7.6）。

    Args:
        result: ScreenResult 选股结果

    Returns:
        UTF-8 BOM 编码的 CSV 字节流（兼容 Excel 打开中文）
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_HEADERS)

    for item in result.items:
        writer.writerow([
            item.symbol,
            str(item.ref_buy_price),
            f"{item.trend_score:.1f}",
            item.risk_level.value,
            "; ".join(f"{s.category.value}:{s.label}" for s in item.signals),
        ])

    # UTF-8 BOM 让 Excel 正确识别中文
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
