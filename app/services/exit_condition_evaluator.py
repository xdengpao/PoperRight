"""
自定义平仓条件评估器

需求 2：平仓条件评估引擎
- 2.1: 每个交易日对持仓标的逐一评估自定义平仓条件
- 2.2: AND 逻辑 — 所有条件均满足时触发
- 2.3: OR 逻辑 — 任一条件满足时触发
- 2.4: 数值比较运算符 (>, <, >=, <=)
- 2.5: cross_up 交叉检测
- 2.6: cross_down 交叉检测
- 2.7: 日K线数据评估
- 2.8: 分钟K线数据评估（不可用时回退日K线）
- 2.9: 数据不足时跳过条件并记录警告
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from app.services.threshold_resolver import resolve_threshold

if TYPE_CHECKING:
    from app.core.schemas import ExitCondition, ExitConditionConfig, HoldingContext
    from app.services.backtest_engine import IndicatorCache

logger = logging.getLogger(__name__)

# 默认 MA 周期 → IndicatorCache 中无直接字段，需从 exit_indicator_cache 获取
_DEFAULT_MA_PERIODS = {5, 10, 20, 60}

# 合法频率常量
VALID_FREQS = {"daily", "1min", "5min", "15min", "30min", "60min"}

# 旧版频率映射
_FREQ_MIGRATION: dict[str, str] = {"minute": "1min"}

# 数值比较运算符映射
_NUMERIC_OPS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


class ExitConditionEvaluator:
    """自定义平仓条件评估器"""

    # 分钟频率集合
    _MINUTE_FREQS = {"1min", "5min", "15min", "30min", "60min"}

    def evaluate(
        self,
        config: ExitConditionConfig,
        symbol: str,
        bar_index: int,
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, dict[str, list[float]]] | None = None,
        minute_day_ranges: dict[str, list[tuple[int, int]]] | None = None,
        holding_context: HoldingContext | None = None,
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
            minute_day_ranges: 分钟频率日内 bar 索引范围映射（可选）
                格式: {freq: [(start_idx, end_idx), ...]}
                每个元组对应一个交易日在分钟缓存中的起止索引（闭区间）。
                当提供此参数时，分钟频率条件将使用日内扫描逻辑。
                为 None 时回退到现有行为（向后兼容）。
            holding_context: 持仓上下文（可选），用于相对值阈值的动态解析

        Returns:
            (triggered, reason) - triggered 为 True 时 reason 包含触发条件描述
        """
        if not config.conditions:
            return False, None

        results: list[tuple[bool, str]] = []
        for cond in config.conditions:
            try:
                freq = self._resolve_freq(cond.freq)
                # 根据频率从 exit_indicator_cache 获取对应缓存
                freq_cache: dict[str, list[float]] | None = None
                if exit_indicator_cache is not None:
                    freq_cache = exit_indicator_cache.get(freq)
                    if freq_cache is None and freq != "daily":
                        # 分钟K线缓存不可用时回退到 daily
                        logger.info(
                            "分钟K线缓存不可用 (freq=%s, symbol=%s)，回退到 daily",
                            freq, symbol,
                        )
                        freq_cache = exit_indicator_cache.get("daily")

                # 分钟频率条件：当 minute_day_ranges 可用时，路由到日内扫描
                if (
                    freq in self._MINUTE_FREQS
                    and minute_day_ranges is not None
                    and freq in minute_day_ranges
                ):
                    freq_ranges = minute_day_ranges[freq]
                    # bar_index 越界检查
                    if bar_index < 0 or bar_index >= len(freq_ranges):
                        logger.warning(
                            "bar_index=%d out of range for minute_day_ranges[%s] "
                            "(length=%d, symbol=%s), skipping condition",
                            bar_index, freq, len(freq_ranges), symbol,
                        )
                        results.append((False, ""))
                        continue

                    day_range = freq_ranges[bar_index]

                    # 哨兵值 (-1, -1) 表示该交易日无分钟数据
                    if day_range == (-1, -1):
                        logger.warning(
                            "No minute data for trading day bar_index=%d "
                            "(freq=%s, symbol=%s), skipping condition",
                            bar_index, freq, symbol,
                        )
                        results.append((False, ""))
                        continue

                    triggered, reason = self._evaluate_single_minute_scanning(
                        cond, day_range, indicator_cache, freq_cache,
                        holding_context,
                    )
                    results.append((triggered, reason))
                    continue

                # 日频条件或 minute_day_ranges 不可用时：使用原有单 bar_index 评估
                triggered, reason = self._evaluate_single(
                    cond, bar_index, indicator_cache, freq_cache,
                    holding_context,
                )
                results.append((triggered, reason))
            except Exception:
                logger.exception(
                    "Error evaluating exit condition for %s: %s %s",
                    symbol, cond.indicator, cond.operator,
                )
                # 异常时视为未满足
                results.append((False, ""))

        if not results:
            return False, None

        triggered_flags = [r[0] for r in results]
        triggered_reasons = [r[1] for r in results if r[0]]

        if config.logic == "OR":
            final = any(triggered_flags)
        else:
            # AND (default)
            final = all(triggered_flags)

        if final:
            reason = "; ".join(triggered_reasons) if triggered_reasons else None
            return True, reason

        return False, None

    @staticmethod
    def _resolve_freq(freq: str) -> str:
        """将旧版频率值映射为新版，如 'minute' → '1min'。"""
        return _FREQ_MIGRATION.get(freq, freq)

    def _evaluate_single_minute_scanning(
        self,
        condition: ExitCondition,
        day_range: tuple[int, int],
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, list[float]] | None,
        holding_context: HoldingContext | None = None,
    ) -> tuple[bool, str]:
        """
        日内扫描评估分钟频率条件。

        遍历该交易日内每一根分钟 bar 的指标值，任意一根满足条件即触发。

        Args:
            condition: 平仓条件
            day_range: (start_idx, end_idx) 闭区间，该交易日在分钟缓存中的起止索引
            indicator_cache: 日K线预计算指标缓存
            exit_indicator_cache: 该频率的指标缓存 {cache_key: values}
            holding_context: 持仓上下文（可选），用于相对值阈值的动态解析

        Returns:
            (triggered, reason_description)
        """
        start_idx, end_idx = day_range
        operator = condition.operator

        if operator in ("cross_up", "cross_down"):
            # Cross scanning: check consecutive pairs within day range
            if not condition.cross_target:
                logger.warning(
                    "Skipping minute cross condition: cross_target not specified for %s",
                    condition.indicator,
                )
                return False, ""

            direction = "up" if operator == "cross_up" else "down"
            for bar_idx in range(start_idx + 1, end_idx + 1):
                triggered = self._check_cross(
                    condition.indicator,
                    condition.cross_target,
                    bar_idx,
                    indicator_cache,
                    exit_indicator_cache,
                    direction,
                    condition.params,
                )
                if triggered:
                    if direction == "up":
                        reason = f"{condition.indicator.upper()} cross_up {condition.cross_target.upper()}"
                    else:
                        reason = f"{condition.indicator.upper()} cross_down {condition.cross_target.upper()}"
                    return True, reason
            return False, ""

        # Numeric comparison: scan all bars in day range
        op_fn = _NUMERIC_OPS.get(operator)
        if op_fn is None:
            logger.error("Invalid operator: %s", operator)
            return False, ""

        # 通过 ThresholdResolver 解析阈值
        resolved = resolve_threshold(condition, holding_context, indicator_cache, start_idx)
        if resolved is None:
            logger.warning(
                "Threshold resolution failed for minute scanning %s, skipping",
                condition.indicator,
            )
            return False, ""

        for bar_idx in range(start_idx, end_idx + 1):
            value = self._get_indicator_value(
                condition.indicator, bar_idx, indicator_cache,
                exit_indicator_cache, condition.params,
            )
            if value is None or math.isnan(value):
                continue  # Skip NaN/None, continue scanning

            if op_fn(value, resolved):
                # 构建触发原因字符串
                if condition.threshold_mode == "relative":
                    reason = f"{condition.indicator.upper()} {operator} {resolved:.4f}（{condition.base_field}×{condition.factor}）"
                else:
                    reason = f"{condition.indicator.upper()} {operator} {resolved}"
                return True, reason

        return False, ""

    def _evaluate_single(
        self,
        condition: ExitCondition,
        bar_index: int,
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, list[float]] | None,
        holding_context: HoldingContext | None = None,
    ) -> tuple[bool, str]:
        """
        评估单条平仓条件。

        Returns:
            (triggered, reason_description)
        """
        operator = condition.operator

        if operator in ("cross_up", "cross_down"):
            return self._evaluate_cross(
                condition, bar_index, indicator_cache, exit_indicator_cache,
            )

        # 数值比较
        value = self._get_indicator_value(
            condition.indicator, bar_index, indicator_cache,
            exit_indicator_cache, condition.params,
        )
        if value is None or math.isnan(value):
            logger.warning(
                "Skipping exit condition: %s value is NaN/None at bar_index=%d",
                condition.indicator, bar_index,
            )
            return False, ""

        # 通过 ThresholdResolver 解析阈值
        resolved = resolve_threshold(condition, holding_context, indicator_cache, bar_index)
        if resolved is None:
            logger.warning(
                "Threshold resolution failed for %s, skipping",
                condition.indicator,
            )
            return False, ""

        op_fn = _NUMERIC_OPS.get(operator)
        if op_fn is None:
            logger.error("Invalid operator: %s", operator)
            return False, ""

        triggered = op_fn(value, resolved)
        # 构建触发原因字符串
        if condition.threshold_mode == "relative":
            reason = f"{condition.indicator.upper()} {operator} {resolved:.4f}（{condition.base_field}×{condition.factor}）"
        else:
            reason = f"{condition.indicator.upper()} {operator} {resolved}"
        return triggered, reason

    def _evaluate_cross(
        self,
        condition: ExitCondition,
        bar_index: int,
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, list[float]] | None,
    ) -> tuple[bool, str]:
        """评估交叉条件 (cross_up / cross_down)。"""
        if bar_index < 1:
            logger.warning(
                "Skipping cross condition: insufficient data at bar_index=%d",
                bar_index,
            )
            return False, ""

        if not condition.cross_target:
            logger.warning(
                "Skipping cross condition: cross_target not specified for %s",
                condition.indicator,
            )
            return False, ""

        direction = "up" if condition.operator == "cross_up" else "down"
        triggered = self._check_cross(
            condition.indicator,
            condition.cross_target,
            bar_index,
            indicator_cache,
            exit_indicator_cache,
            direction,
            condition.params,
        )

        if direction == "up":
            reason = f"{condition.indicator.upper()} cross_up {condition.cross_target.upper()}"
        else:
            reason = f"{condition.indicator.upper()} cross_down {condition.cross_target.upper()}"

        return triggered, reason

    def _get_indicator_value(
        self,
        indicator_name: str,
        bar_index: int,
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, list[float]] | None,
        params: dict | None = None,
    ) -> float | None:
        """
        从缓存获取指标值，支持自定义参数。

        优先从 exit_indicator_cache 查找自定义参数指标，
        回退到 indicator_cache 中的默认指标。
        """
        params = params or {}

        # 直接映射：close, volume, turnover
        if indicator_name == "close":
            return self._safe_index(indicator_cache.closes, bar_index)
        if indicator_name == "volume":
            v = self._safe_index(indicator_cache.volumes, bar_index)
            return float(v) if v is not None else None
        if indicator_name == "turnover":
            v = self._safe_index(indicator_cache.turnovers, bar_index)
            return float(v) if v is not None else None

        # MA — 需要周期参数
        if indicator_name == "ma":
            period = params.get("period")
            if period is None:
                logger.warning("MA indicator requires 'period' param")
                return None
            cache_key = f"ma_{period}"
            return self._get_from_exit_cache(
                cache_key, bar_index, exit_indicator_cache,
            )

        # MACD 系列
        if indicator_name in ("macd_dif", "macd_dea", "macd_histogram"):
            cache_key = self._build_macd_cache_key(indicator_name, params)
            if cache_key and exit_indicator_cache:
                val = self._get_from_exit_cache(
                    cache_key, bar_index, exit_indicator_cache,
                )
                if val is not None:
                    return val
            # 无自定义参数 — 不在 exit_indicator_cache 中，返回 None
            # （默认 MACD 参数的值也应在 exit_indicator_cache 中预计算）
            return self._get_from_exit_cache(
                indicator_name, bar_index, exit_indicator_cache,
            )

        # BOLL 系列
        if indicator_name in ("boll_upper", "boll_middle", "boll_lower"):
            cache_key = self._build_boll_cache_key(indicator_name, params)
            if cache_key and exit_indicator_cache:
                val = self._get_from_exit_cache(
                    cache_key, bar_index, exit_indicator_cache,
                )
                if val is not None:
                    return val
            return self._get_from_exit_cache(
                indicator_name, bar_index, exit_indicator_cache,
            )

        # RSI
        if indicator_name == "rsi":
            cache_key = self._build_rsi_cache_key(params)
            if cache_key and exit_indicator_cache:
                val = self._get_from_exit_cache(
                    cache_key, bar_index, exit_indicator_cache,
                )
                if val is not None:
                    return val
            return self._get_from_exit_cache(
                "rsi", bar_index, exit_indicator_cache,
            )

        # DMA / AMA
        if indicator_name in ("dma", "ama"):
            cache_key = self._build_dma_cache_key(indicator_name, params)
            if cache_key and exit_indicator_cache:
                val = self._get_from_exit_cache(
                    cache_key, bar_index, exit_indicator_cache,
                )
                if val is not None:
                    return val
            return self._get_from_exit_cache(
                indicator_name, bar_index, exit_indicator_cache,
            )

        logger.error("Unknown indicator: %s", indicator_name)
        return None

    def _check_cross(
        self,
        indicator_name: str,
        cross_target: str,
        bar_index: int,
        indicator_cache: IndicatorCache,
        exit_indicator_cache: dict[str, list[float]] | None,
        direction: str,
        params: dict | None = None,
    ) -> bool:
        """
        检测交叉信号。

        cross_up:   prev_indicator <= prev_target AND curr_indicator > curr_target
        cross_down: prev_indicator >= prev_target AND curr_indicator < curr_target
        """
        if bar_index < 1:
            return False

        curr_ind = self._get_indicator_value(
            indicator_name, bar_index, indicator_cache,
            exit_indicator_cache, params,
        )
        prev_ind = self._get_indicator_value(
            indicator_name, bar_index - 1, indicator_cache,
            exit_indicator_cache, params,
        )
        curr_tgt = self._get_indicator_value(
            cross_target, bar_index, indicator_cache,
            exit_indicator_cache, params,
        )
        prev_tgt = self._get_indicator_value(
            cross_target, bar_index - 1, indicator_cache,
            exit_indicator_cache, params,
        )

        # 任一值为 None 或 NaN 则跳过
        for val, label in [
            (curr_ind, "curr_indicator"),
            (prev_ind, "prev_indicator"),
            (curr_tgt, "curr_target"),
            (prev_tgt, "prev_target"),
        ]:
            if val is None or math.isnan(val):
                logger.warning(
                    "Skipping cross check: %s is NaN/None for %s vs %s at bar_index=%d",
                    label, indicator_name, cross_target, bar_index,
                )
                return False

        if direction == "up":
            return prev_ind <= prev_tgt and curr_ind > curr_tgt
        else:  # down
            return prev_ind >= prev_tgt and curr_ind < curr_tgt

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_index(lst: list | None, index: int) -> float | None:
        """安全索引访问，越界或 None 返回 None。"""
        if lst is None or index < 0 or index >= len(lst):
            return None
        val = lst[index]
        if isinstance(val, (int, float)):
            return float(val)
        # Decimal 等
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_from_exit_cache(
        cache_key: str,
        bar_index: int,
        exit_indicator_cache: dict[str, list[float]] | None,
    ) -> float | None:
        """从 exit_indicator_cache 获取值。"""
        if not exit_indicator_cache:
            return None
        values = exit_indicator_cache.get(cache_key)
        if values is None or bar_index < 0 or bar_index >= len(values):
            return None
        val = values[bar_index]
        if math.isnan(val):
            return None
        return val

    @staticmethod
    def _build_macd_cache_key(indicator_name: str, params: dict) -> str | None:
        """构建 MACD 系列的缓存键。"""
        fast = params.get("macd_fast")
        slow = params.get("macd_slow")
        signal = params.get("macd_signal")
        if fast is not None and slow is not None and signal is not None:
            return f"{indicator_name}_{fast}_{slow}_{signal}"
        return None

    @staticmethod
    def _build_boll_cache_key(indicator_name: str, params: dict) -> str | None:
        """构建 BOLL 系列的缓存键。"""
        period = params.get("boll_period")
        std_dev = params.get("boll_std_dev")
        if period is not None:
            if std_dev is not None:
                return f"{indicator_name}_{period}_{std_dev}"
            return f"{indicator_name}_{period}"
        return None

    @staticmethod
    def _build_rsi_cache_key(params: dict) -> str | None:
        """构建 RSI 的缓存键。"""
        period = params.get("rsi_period")
        if period is not None:
            return f"rsi_{period}"
        return None

    @staticmethod
    def _build_dma_cache_key(indicator_name: str, params: dict) -> str | None:
        """构建 DMA/AMA 的缓存键。"""
        short = params.get("dma_short")
        long_ = params.get("dma_long")
        if short is not None and long_ is not None:
            return f"{indicator_name}_{short}_{long_}"
        return None
