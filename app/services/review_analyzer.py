"""
复盘分析服务

提供每日复盘报告生成，包含选股胜率、盈亏统计、成功/失败交易案例分析。
提供策略绩效报表、市场复盘分析、报表导出功能。

对应需求：
- 需求 16.1：每个交易日收盘后自动生成当日复盘报告
- 需求 16.2：日/周/月策略收益报表 + 风险指标报表 + 多策略对比
- 需求 16.3：板块轮动分析、趋势行情分布图、资金流向分析
- 需求 16.4：报表导出（CSV/JSON）
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field
from datetime import date


@dataclass
class DailyReview:
    """每日复盘报告数据"""

    date: date
    win_rate: float              # 胜率 [0, 1]
    total_pnl: float             # 总盈亏
    avg_pnl: float               # 平均盈亏
    total_trades: int            # 总交易笔数
    winning_trades: int          # 盈利笔数
    losing_trades: int           # 亏损笔数
    best_trade: dict | None      # 最佳交易
    worst_trade: dict | None     # 最差交易
    successful_cases: list[dict] = field(default_factory=list)
    failed_cases: list[dict] = field(default_factory=list)


class ReviewAnalyzer:
    """复盘分析器"""

    @staticmethod
    def generate_daily_review(
        trade_records: list[dict],
        screen_results: list[dict],
        review_date: date | None = None,
    ) -> DailyReview:
        """
        生成每日复盘报告。

        Args:
            trade_records: 交易记录列表，每条需包含 ``profit`` 字段。
            screen_results: 选股结果列表（预留，当前未使用）。
            review_date: 复盘日期，默认今天。

        Returns:
            DailyReview 数据对象。
        """
        review_date = review_date or date.today()

        if not trade_records:
            return DailyReview(
                date=review_date,
                win_rate=0.0,
                total_pnl=0.0,
                avg_pnl=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                best_trade=None,
                worst_trade=None,
            )

        profits = [float(r.get("profit", 0)) for r in trade_records]
        total_pnl = sum(profits)
        total_trades = len(trade_records)
        avg_pnl = total_pnl / total_trades

        successful = [r for r in trade_records if float(r.get("profit", 0)) > 0]
        failed = [r for r in trade_records if float(r.get("profit", 0)) <= 0]

        winning_trades = len(successful)
        losing_trades = len(failed)
        win_rate = winning_trades / total_trades

        best_trade = max(trade_records, key=lambda r: float(r.get("profit", 0)))
        worst_trade = min(trade_records, key=lambda r: float(r.get("profit", 0)))

        return DailyReview(
            date=review_date,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            best_trade=best_trade,
            worst_trade=worst_trade,
            successful_cases=successful,
            failed_cases=failed,
        )


# ---------------------------------------------------------------------------
# 9.2 策略绩效报表（需求 16.2）
# ---------------------------------------------------------------------------


class StrategyReportGenerator:
    """策略绩效报表生成器。

    生成日/周/月策略收益报表、风险指标报表，以及多策略并排对比分析。
    """

    @staticmethod
    def generate_period_report(trades: list[dict], period: str) -> dict:
        """生成指定周期的策略收益与风险报表。

        Args:
            trades: 交易记录列表，每条需包含 ``profit`` 字段。
            period: 报表周期，``"daily"`` / ``"weekly"`` / ``"monthly"``。

        Returns:
            包含 period、total_return、win_rate、total_trades、risk_metrics 的字典。
        """
        if period not in ("daily", "weekly", "monthly"):
            raise ValueError(f"period must be 'daily', 'weekly', or 'monthly', got '{period}'")

        if not trades:
            return {
                "period": period,
                "total_return": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "risk_metrics": {
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                    "volatility": 0.0,
                },
            }

        profits = [float(t.get("profit", 0)) for t in trades]
        total_return = sum(profits)
        total_trades = len(profits)
        winning = sum(1 for p in profits if p > 0)
        win_rate = winning / total_trades

        # Risk metrics
        max_drawdown = StrategyReportGenerator._calc_max_drawdown(profits)
        volatility = StrategyReportGenerator._calc_volatility(profits)
        sharpe_ratio = StrategyReportGenerator._calc_sharpe_ratio(profits, volatility)

        return {
            "period": period,
            "total_return": total_return,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "risk_metrics": {
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe_ratio,
                "volatility": volatility,
            },
        }

    @staticmethod
    def compare_strategies(strategy_reports: dict[str, dict]) -> dict:
        """多策略并排对比分析。

        Args:
            strategy_reports: ``{strategy_name: period_report_dict}`` 映射。

        Returns:
            包含 strategies（各策略摘要列表）和 best_strategy 的字典。
        """
        if not strategy_reports:
            return {"strategies": [], "best_strategy": None}

        summaries: list[dict] = []
        for name, report in strategy_reports.items():
            summaries.append({
                "name": name,
                "total_return": report.get("total_return", 0.0),
                "win_rate": report.get("win_rate", 0.0),
                "total_trades": report.get("total_trades", 0),
                "max_drawdown": report.get("risk_metrics", {}).get("max_drawdown", 0.0),
                "sharpe_ratio": report.get("risk_metrics", {}).get("sharpe_ratio", 0.0),
            })

        best = max(summaries, key=lambda s: s["total_return"])

        return {
            "strategies": summaries,
            "best_strategy": best["name"],
        }

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def _calc_max_drawdown(profits: list[float]) -> float:
        """从收益序列计算最大回撤（基于累计收益曲线）。"""
        if not profits:
            return 0.0
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in profits:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _calc_volatility(profits: list[float]) -> float:
        """计算收益序列的标准差。"""
        n = len(profits)
        if n < 2:
            return 0.0
        mean = sum(profits) / n
        variance = sum((p - mean) ** 2 for p in profits) / (n - 1)
        return math.sqrt(variance)

    @staticmethod
    def _calc_sharpe_ratio(profits: list[float], volatility: float) -> float:
        """简化夏普比率 = mean(profits) / volatility。"""
        if not profits or volatility == 0.0:
            return 0.0
        mean = sum(profits) / len(profits)
        return mean / volatility


# ---------------------------------------------------------------------------
# 9.3 市场复盘分析（需求 16.3）
# ---------------------------------------------------------------------------


class MarketReviewAnalyzer:
    """市场复盘分析器。

    提供板块轮动分析、趋势行情分布图数据、资金流向分析。
    """

    @staticmethod
    def analyze_sector_rotation(sector_data: list[dict]) -> dict:
        """板块轮动分析。

        Args:
            sector_data: 板块数据列表，每条需包含 ``name`` 和 ``change_pct`` 字段。

        Returns:
            包含 top_sectors、bottom_sectors、rotation_summary 的字典。
        """
        if not sector_data:
            return {"top_sectors": [], "bottom_sectors": [], "rotation_summary": "无数据"}

        sorted_sectors = sorted(sector_data, key=lambda s: float(s.get("change_pct", 0)), reverse=True)

        top_n = min(5, len(sorted_sectors))
        bottom_n = min(5, len(sorted_sectors))

        top_sectors = [
            {"name": s["name"], "change_pct": float(s["change_pct"])}
            for s in sorted_sectors[:top_n]
        ]
        bottom_sectors = [
            {"name": s["name"], "change_pct": float(s["change_pct"])}
            for s in sorted_sectors[-bottom_n:]
        ]

        rising = sum(1 for s in sector_data if float(s.get("change_pct", 0)) > 0)
        falling = len(sector_data) - rising

        if rising > falling:
            summary = f"板块整体偏强，上涨 {rising} 个，下跌 {falling} 个"
        elif falling > rising:
            summary = f"板块整体偏弱，上涨 {rising} 个，下跌 {falling} 个"
        else:
            summary = f"板块涨跌各半，上涨 {rising} 个，下跌 {falling} 个"

        return {
            "top_sectors": top_sectors,
            "bottom_sectors": bottom_sectors,
            "rotation_summary": summary,
        }

    @staticmethod
    def generate_trend_distribution(stock_scores: list[float]) -> dict:
        """生成趋势行情分布图数据（直方图，供 ECharts 渲染）。

        将趋势评分按 [0,20), [20,40), [40,60), [60,80), [80,100] 分桶。

        Args:
            stock_scores: 个股趋势评分列表（0-100）。

        Returns:
            包含 bins（区间标签列表）和 counts（各区间计数列表）的字典。
        """
        bins = ["0-20", "20-40", "40-60", "60-80", "80-100"]
        counts = [0, 0, 0, 0, 0]

        for score in stock_scores:
            s = float(score)
            if s < 20:
                counts[0] += 1
            elif s < 40:
                counts[1] += 1
            elif s < 60:
                counts[2] += 1
            elif s < 80:
                counts[3] += 1
            else:
                counts[4] += 1

        return {"bins": bins, "counts": counts}

    @staticmethod
    def analyze_money_flow(flow_data: list[dict]) -> dict:
        """资金流向分析。

        Args:
            flow_data: 资金流向数据列表，每条需包含 ``sector``、``net_inflow`` 字段。

        Returns:
            包含 net_inflow_total、top_inflow_sectors、top_outflow_sectors 的字典。
        """
        if not flow_data:
            return {
                "net_inflow_total": 0.0,
                "top_inflow_sectors": [],
                "top_outflow_sectors": [],
            }

        net_inflow_total = sum(float(f.get("net_inflow", 0)) for f in flow_data)

        sorted_by_inflow = sorted(flow_data, key=lambda f: float(f.get("net_inflow", 0)), reverse=True)

        inflow_sectors = [
            {"sector": f["sector"], "net_inflow": float(f["net_inflow"])}
            for f in sorted_by_inflow
            if float(f.get("net_inflow", 0)) > 0
        ]
        outflow_sectors = [
            {"sector": f["sector"], "net_inflow": float(f["net_inflow"])}
            for f in reversed(sorted_by_inflow)
            if float(f.get("net_inflow", 0)) < 0
        ]

        return {
            "net_inflow_total": net_inflow_total,
            "top_inflow_sectors": inflow_sectors[:5],
            "top_outflow_sectors": outflow_sectors[:5],
        }


# ---------------------------------------------------------------------------
# 9.4 报表导出（需求 16.4）
# ---------------------------------------------------------------------------


class ReportExporter:
    """报表导出器。

    支持 CSV 导出（bytes）和 JSON 导出（str，供前端 ECharts 渲染）。
    """

    @staticmethod
    def export_to_csv(data: dict | list) -> bytes:
        """将报表数据导出为 CSV 格式的 bytes。

        - 如果 *data* 是 ``list[dict]``，以字典键为列头输出。
        - 如果 *data* 是 ``dict``，将其扁平化为单行输出。

        Returns:
            UTF-8 编码的 CSV bytes（含 BOM 以兼容 Excel）。
        """
        buf = io.StringIO()
        writer: csv.DictWriter | None = None

        rows = ReportExporter._normalize_rows(data)
        if not rows:
            return b""

        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

        # UTF-8 BOM for Excel compatibility
        return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")

    @staticmethod
    def export_to_json(data: dict | list) -> str:
        """将报表数据导出为 JSON 字符串（供前端 ECharts 渲染）。

        Returns:
            格式化的 JSON 字符串。
        """
        return json.dumps(data, ensure_ascii=False, default=str)

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def _normalize_rows(data: dict | list) -> list[dict]:
        """将输入统一为 list[dict] 以便 CSV 写入。"""
        if isinstance(data, list):
            if not data:
                return []
            if isinstance(data[0], dict):
                return data
            # list of scalars → single-column
            return [{"value": v} for v in data]
        if isinstance(data, dict):
            return [ReportExporter._flatten_dict(data)]
        return []

    @staticmethod
    def _flatten_dict(d: dict, prefix: str = "") -> dict:
        """递归扁平化嵌套字典。"""
        items: dict = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(ReportExporter._flatten_dict(v, key))
            elif isinstance(v, list):
                items[key] = json.dumps(v, ensure_ascii=False, default=str)
            else:
                items[key] = v
        return items
