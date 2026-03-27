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

    def __init__(self, strategy_config: StrategyConfig, strategy_id: str | None = None):
        self._config = strategy_config
        self._strategy_id = strategy_id or str(uuid.uuid4())

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

    def _execute(
        self,
        stocks_data: dict[str, dict[str, Any]],
        screen_type: ScreenType,
    ) -> ScreenResult:
        """核心选股执行逻辑。"""
        passed = StrategyEngine.screen_stocks(self._config, stocks_data)

        items: list[ScreenItem] = []
        for symbol, eval_result in passed:
            stock_data = stocks_data.get(symbol, {})
            trend_score = eval_result.weighted_score
            # 确保 trend_score 在 [0, 100]
            trend_score = max(0.0, min(100.0, trend_score))

            signals = {
                fr.factor_name: {"passed": fr.passed, "value": fr.value}
                for fr in eval_result.factor_results
            }

            items.append(
                ScreenItem(
                    symbol=symbol,
                    ref_buy_price=_estimate_ref_buy_price(stock_data),
                    trend_score=trend_score,
                    risk_level=_classify_risk(trend_score),
                    signals=signals,
                )
            )

        return ScreenResult(
            strategy_id=uuid.UUID(self._strategy_id) if isinstance(self._strategy_id, str) else self._strategy_id,
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
            str(item.signals),
        ])

    # UTF-8 BOM 让 Excel 正确识别中文
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
