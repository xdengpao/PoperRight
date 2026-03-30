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
    RiskLevel,
    ScreenItem,
    ScreenResult,
    ScreenType,
    SignalCategory,
    SignalDetail,
    StrategyConfig,
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
    ):
        self._config = strategy_config
        self._strategy_id = strategy_id or str(uuid.uuid4())
        self._raw_config = raw_config or {}
        # None → all modules enabled (backward compat); [] → empty set (skip all)
        self._enabled_modules: set[str] | None = (
            set(enabled_modules) if enabled_modules is not None else None
        )

    def run_eod_screen(
        self,
        stocks_data: dict[str, dict[str, Any]],
    ) -> ScreenResult:
        """
        盘后全市场选股（需求 7.4）。

        Args:
            stocks_data: {symbol: stock_data} 全市场股票因子数据

        Returns:
            ScreenResult（screen_type=EOD）
        """
        return self._execute(stocks_data, ScreenType.EOD)

    def run_realtime_screen(
        self,
        stocks_data: dict[str, dict[str, Any]],
    ) -> ScreenResult:
        """
        盘中实时选股（需求 7.5）。

        Args:
            stocks_data: {symbol: stock_data} 实时因子数据

        Returns:
            ScreenResult（screen_type=REALTIME）
        """
        return self._execute(stocks_data, ScreenType.REALTIME)

    # 因子名称 → 所属模块标识符的映射
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
        "sector_rank": "volume_price",
        "sector_trend": "volume_price",
    }

    def _is_module_enabled(self, module_key: str) -> bool:
        """检查模块是否启用。None 表示全部启用（向后兼容）。"""
        if self._enabled_modules is None:
            return True
        return module_key in self._enabled_modules

    def _execute(
        self,
        stocks_data: dict[str, dict[str, Any]],
        screen_type: ScreenType,
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
            trend_score = eval_result.weighted_score
            if self._is_module_enabled("ma_trend"):
                ma_trend_score = float(stock_data.get("ma_trend", 0.0))
                trend_score = max(trend_score, ma_trend_score)

            # breakout 模块贡献趋势强度：有效突破 +60，非假突破再 +20，量比>1.5 再 +20
            breakout_data = stock_data.get("breakout")
            if self._is_module_enabled("breakout") and isinstance(breakout_data, dict):
                if breakout_data.get("is_valid"):
                    bp_score = 60.0
                    if not breakout_data.get("is_false_breakout", False):
                        bp_score += 20.0
                    vol_ratio = breakout_data.get("volume_ratio", 0)
                    if vol_ratio and vol_ratio > 1.5:
                        bp_score += 20.0
                    trend_score = max(trend_score, bp_score)

            # indicator_params 模块贡献趋势强度：每个有效信号 +25
            if self._is_module_enabled("indicator_params"):
                ind_score = 0.0
                if stock_data.get("macd"):
                    ind_score += 25.0
                if stock_data.get("boll"):
                    ind_score += 25.0
                if stock_data.get("rsi"):
                    ind_score += 25.0
                if stock_data.get("dma") and isinstance(stock_data["dma"], dict):
                    dma_val = stock_data["dma"].get("dma", 0)
                    ama_val = stock_data["dma"].get("ama", 0)
                    if dma_val and ama_val and dma_val > ama_val:
                        ind_score += 25.0
                if ind_score > 0:
                    trend_score = max(trend_score, ind_score)

            # 确保 trend_score 在 [0, 100]
            trend_score = max(0.0, min(100.0, trend_score))

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
            # ma_trend 模块
            if self._is_module_enabled("ma_trend"):
                ma_cfg = self._raw_config.get("ma_trend", {}) if isinstance(self._raw_config.get("ma_trend"), dict) else {}
                threshold = ma_cfg.get("trend_score_threshold", 80)
                if stock_data.get("ma_trend", 0) >= threshold:
                    signals.append(SignalDetail(
                        category=SignalCategory.MA_TREND,
                        label="ma_trend",
                    ))

            # indicator_params 模块
            if self._is_module_enabled("indicator_params"):
                if stock_data.get("macd"):
                    signals.append(SignalDetail(
                        category=SignalCategory.MACD,
                        label="macd",
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

            # breakout 模块
            breakout_data = stock_data.get("breakout")
            is_fake_breakout = False
            if self._is_module_enabled("breakout") and isinstance(breakout_data, dict):
                if breakout_data.get("is_valid"):
                    is_fake_breakout = bool(breakout_data.get("is_false_breakout", False))
                    signals.append(SignalDetail(
                        category=SignalCategory.BREAKOUT,
                        label="breakout",
                        is_fake_breakout=is_fake_breakout,
                    ))

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

        return ScreenResult(
            strategy_id=strategy_id,
            screen_time=datetime.now(),
            screen_type=screen_type,
            items=items,
            is_complete=True,
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
