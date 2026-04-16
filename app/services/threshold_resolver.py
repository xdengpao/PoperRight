"""阈值解析器 — 将平仓条件的阈值配置解析为具体浮点数值。

本模块实现为纯函数，不依赖外部状态。
- absolute 模式：直接返回 condition.threshold
- relative 模式：根据 base_field 从 HoldingContext 或 IndicatorCache 获取基准值，乘以 factor

Requirements: 3.1 ~ 3.17
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from app.core.schemas import VALID_BASE_FIELDS, ExitCondition, HoldingContext

if TYPE_CHECKING:
    from app.services.backtest_engine import IndicatorCache

logger = logging.getLogger(__name__)

# base_field 值中需要 HoldingContext 的子集
_HOLDING_FIELDS = {"entry_price", "highest_price", "lowest_price"}

# base_field 值中需要 bar_index >= 1（前一根 bar）的子集
_PREV_BAR_FIELDS = {
    "prev_close",
    "prev_high",
    "prev_low",
    "prev_bar_open",
    "prev_bar_high",
    "prev_bar_low",
    "prev_bar_close",
}


def resolve_threshold(
    condition: ExitCondition,
    holding_context: HoldingContext | None,
    indicator_cache: IndicatorCache,
    bar_index: int,
) -> float | None:
    """解析平仓条件的阈值。

    Args:
        condition: 平仓条件对象
        holding_context: 持仓上下文（relative 模式下需要 HoldingContext 字段时必须提供）
        indicator_cache: 预计算指标缓存
        bar_index: 当前 K 线 bar 索引

    Returns:
        解析后的浮点数阈值，或 None（解析失败时）
    """
    # --- absolute 模式 ---
    if condition.threshold_mode == "absolute":
        return condition.threshold

    # --- relative 模式 ---
    base_field = condition.base_field
    factor = condition.factor

    # factor 校验
    if factor is None or factor <= 0:
        logger.warning(
            "resolve_threshold: factor is None or non-positive (%s) for %s, skipping",
            factor,
            condition.indicator,
        )
        return None

    # base_field 合法性校验
    if base_field not in VALID_BASE_FIELDS:
        logger.error(
            "resolve_threshold: invalid base_field '%s' for %s",
            base_field,
            condition.indicator,
        )
        return None

    # 获取基准值
    base_value = _get_base_value(base_field, holding_context, indicator_cache, bar_index, condition)
    if base_value is None:
        return None

    # NaN 校验
    if math.isnan(base_value):
        logger.warning(
            "resolve_threshold: base value is NaN for base_field='%s', skipping",
            base_field,
        )
        return None

    return base_value * factor


def _get_base_value(
    base_field: str,
    holding_context: HoldingContext | None,
    indicator_cache: IndicatorCache,
    bar_index: int,
    condition: ExitCondition,
) -> float | None:
    """根据 base_field 从 HoldingContext 或 IndicatorCache 获取基准值。"""

    # --- HoldingContext 字段 ---
    if base_field in _HOLDING_FIELDS:
        if holding_context is None:
            logger.warning(
                "resolve_threshold: holding_context is None but base_field='%s' requires it, skipping",
                base_field,
            )
            return None
        value = getattr(holding_context, base_field, None)
        if value is None:
            logger.warning(
                "resolve_threshold: holding_context.%s is None, skipping",
                base_field,
            )
            return None
        return float(value)

    # --- prev_* 字段需要 bar_index >= 1 ---
    if base_field in _PREV_BAR_FIELDS:
        if bar_index < 1:
            logger.warning(
                "resolve_threshold: bar_index=%d < 1, cannot resolve '%s', skipping",
                bar_index,
                base_field,
            )
            return None
        return _get_prev_bar_value(base_field, indicator_cache, bar_index)

    # --- today_open ---
    if base_field == "today_open":
        if bar_index < 0 or bar_index >= len(indicator_cache.opens):
            logger.warning(
                "resolve_threshold: bar_index=%d out of range for opens (len=%d), skipping",
                bar_index,
                len(indicator_cache.opens),
            )
            return None
        return float(indicator_cache.opens[bar_index])

    # --- ma_volume ---
    if base_field == "ma_volume":
        return _get_ma_volume(indicator_cache, bar_index, condition)

    # 不应到达此处（已在上层校验 base_field 合法性）
    logger.error("resolve_threshold: unhandled base_field '%s'", base_field)
    return None


def _get_prev_bar_value(
    base_field: str,
    indicator_cache: IndicatorCache,
    bar_index: int,
) -> float | None:
    """获取前一根 bar 的价格数据。"""
    prev_idx = bar_index - 1

    field_map: dict[str, list] = {
        "prev_close": indicator_cache.closes,
        "prev_high": indicator_cache.highs,
        "prev_low": indicator_cache.lows,
        "prev_bar_open": indicator_cache.opens,
        "prev_bar_high": indicator_cache.highs,
        "prev_bar_low": indicator_cache.lows,
        "prev_bar_close": indicator_cache.closes,
    }

    series = field_map.get(base_field)
    if series is None or prev_idx < 0 or prev_idx >= len(series):
        logger.warning(
            "resolve_threshold: cannot access index %d for base_field='%s', skipping",
            prev_idx,
            base_field,
        )
        return None

    value = series[prev_idx]
    if value is None:
        logger.warning(
            "resolve_threshold: value at index %d is None for base_field='%s', skipping",
            prev_idx,
            base_field,
        )
        return None

    return float(value)


def _get_ma_volume(
    indicator_cache: IndicatorCache,
    bar_index: int,
    condition: ExitCondition,
) -> float | None:
    """计算过去 N 日均量。"""
    period = condition.params.get("ma_volume_period", 5)
    if not isinstance(period, int) or period < 1:
        logger.warning(
            "resolve_threshold: invalid ma_volume_period=%s, skipping",
            period,
        )
        return None

    volumes = indicator_cache.volumes
    # 需要 volumes[bar_index - period + 1 : bar_index + 1]，共 period 个元素
    start = bar_index - period + 1
    if start < 0 or bar_index >= len(volumes):
        logger.warning(
            "resolve_threshold: insufficient volume data for ma_volume "
            "(bar_index=%d, period=%d, volumes_len=%d), skipping",
            bar_index,
            period,
            len(volumes),
        )
        return None

    window = volumes[start : bar_index + 1]
    if len(window) < period:
        logger.warning(
            "resolve_threshold: volume window too short (%d < %d), skipping",
            len(window),
            period,
        )
        return None

    return sum(window) / period
