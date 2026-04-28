#!/usr/bin/env python3
"""智能选股功能评估脚本

用法:
    python scripts/evaluate_screener.py
    python scripts/evaluate_screener.py --start-date 2025-01-01 --end-date 2025-03-31
    python scripts/evaluate_screener.py --strategies strategy1_id,strategy2_id
    python scripts/evaluate_screener.py --format markdown --output reports/eval.md

评估内容:
    1. 选股结果收益评价（命中率、超额收益、参考价偏离度）
    2. 信号有效性评价（10 种信号的独立和共振效果）
    3. 因子预测力评价（IC/IR、有效/无效因子识别）
    4. 趋势评分与风控有效性评价
    5. 22 个策略模板横向对比
    6. 可执行改进方案生成（因子权重/风控/信号/策略/参考价）
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("evaluate_screener")

# PLACEHOLDER_MAIN_SCRIPT_CONTINUE


def _check_index_data_completeness(
    trading_dates: list, index_data: dict,
) -> dict:
    """检查指数数据完整性。"""
    total = len(trading_dates)
    covered = sum(1 for d in trading_dates if d in index_data) if total > 0 else 0
    coverage = covered / total * 100 if total > 0 else 0

    if coverage < 80:
        logger.error(
            "基准指数数据不足（覆盖率 %.0f%%），超额收益和市场环境分类将不准确。"
            "请先通过 Tushare 导入页面导入 index_basic 和 index_daily 数据",
            coverage,
        )
    elif coverage < 100:
        logger.warning("基准指数数据覆盖率 %.0f%%，部分交易日缺失", coverage)

    return {
        "index_kline_coverage": round(coverage, 1),
        "trading_days_total": total,
        "trading_days_covered": covered,
    }


async def run_evaluation(args: argparse.Namespace) -> None:
    """执行完整评估流程。"""
    from app.core.database import AsyncSessionPG, AsyncSessionTS, init_db
    from app.services.data_engine.kline_repository import KlineRepository
    from app.services.screener.evaluation.historical_data_preparer import HistoricalDataPreparer
    from app.services.screener.evaluation.screening_simulator import ScreeningSimulator
    from app.services.screener.evaluation.forward_return_calculator import ForwardReturnCalculator
    from app.services.screener.evaluation.return_metrics import ReturnMetricsCalculator
    from app.services.screener.evaluation.signal_metrics import SignalMetricsCalculator
    from app.services.screener.evaluation.factor_metrics import FactorMetricsCalculator
    from app.services.screener.evaluation.score_metrics import ScoreMetricsCalculator
    from app.services.screener.evaluation.strategy_metrics import StrategyMetricsCalculator
    from app.services.screener.evaluation.factor_weight_optimizer import FactorWeightOptimizer
    from app.services.screener.evaluation.risk_rule_optimizer import RiskRuleOptimizer
    from app.services.screener.evaluation.signal_optimizer import SignalSystemOptimizer
    from app.services.screener.evaluation.strategy_optimizer import StrategyTemplateOptimizer
    from app.services.screener.evaluation.ref_price_optimizer import RefPriceOptimizer
    from app.services.screener.evaluation.improvement_prioritizer import ImprovementPrioritizer
    from app.services.screener.evaluation.report_generator import ReportGenerator
    from app.services.screener.strategy_examples import STRATEGY_EXAMPLES
    from app.core.schemas import StrategyConfig

    total_start = time.time()

    # 1. 初始化数据库
    logger.info("阶段 1/6: 初始化数据库连接...")
    await init_db()

    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else end_date - timedelta(days=90)

    async with AsyncSessionPG() as pg_session, AsyncSessionTS() as ts_session:
        preparer = HistoricalDataPreparer(pg_session=pg_session, ts_session=ts_session)
        kline_repo = KlineRepository(ts_session)

        # 2. 数据准备
        logger.info("阶段 2/6: 加载历史数据 (%s ~ %s)...", start_date, end_date)
        trading_dates = await preparer.get_trading_dates(start_date, end_date)
        if not trading_dates:
            logger.error("评估期内无交易日数据")
            return

        index_data = await preparer.load_index_data(start_date, end_date)
        stock_info = await preparer.load_stock_info()

        # 指数数据完整性检查
        index_data_status = _check_index_data_completeness(
            trading_dates, index_data,
        )

        # 3. 选股模拟
        logger.info("阶段 3/6: 模拟选股 (%d 个交易日)...", len(trading_dates))
        simulator = ScreeningSimulator()
        all_strategy_results: dict[str, list] = {}
        all_forward_returns: list = []
        forward_returns_map: dict[tuple, any] = {}
        daily_factor_data: dict[date, dict] = {}

        strategies = STRATEGY_EXAMPLES
        if args.strategies:
            strategy_names = [s.strip() for s in args.strategies.split(",")]
            strategies = [s for s in strategies if s.name in strategy_names]

        if not strategies:
            logger.error("无可用策略模板")
            return

        logger.info("评估 %d 个策略模板", len(strategies))

        for strategy_ex in strategies:
            config_dict = {
                "factors": strategy_ex.factors,
                "logic": strategy_ex.logic,
                "weights": strategy_ex.weights,
            }
            if strategy_ex.sector_config:
                config_dict["sector_config"] = strategy_ex.sector_config
            config = StrategyConfig.from_dict(config_dict)
            strategy_uuid = str(uuid.uuid4())
            daily_results = await simulator.simulate_period(
                strategy_config=config,
                strategy_id=strategy_uuid,
                strategy_name=strategy_ex.name,
                data_preparer=preparer,
                trading_dates=trading_dates,
                index_data=index_data,
                enabled_modules=strategy_ex.enabled_modules,
            )
            all_strategy_results[strategy_ex.name] = daily_results

            # 收集因子数据快照
            for td in trading_dates:
                if td not in daily_factor_data:
                    daily_factor_data[td] = await preparer.load_daily_snapshot(td)

        # 4. 计算未来收益
        logger.info("阶段 4/6: 计算未来收益...")
        fwd_calc = ForwardReturnCalculator(kline_repo)
        extended_dates = await preparer.get_trading_dates(
            start_date, end_date + timedelta(days=30),
        )

        for strategy_name, daily_results in all_strategy_results.items():
            for daily in daily_results:
                fwd_returns = await fwd_calc.calculate(
                    screen_items=daily.items,
                    screen_date=daily.trade_date,
                    index_data=index_data,
                    trading_dates=extended_dates,
                )
                all_forward_returns.extend(fwd_returns)
                for fr in fwd_returns:
                    forward_returns_map[(daily.trade_date, fr.symbol)] = fr

        # 5. 指标计算
        logger.info("阶段 5/6: 计算评价指标...")
        first_strategy_results = list(all_strategy_results.values())[0] if all_strategy_results else []

        return_metrics = ReturnMetricsCalculator.calculate(all_forward_returns)
        signal_metrics = SignalMetricsCalculator().calculate(first_strategy_results, forward_returns_map)
        factor_metrics = FactorMetricsCalculator().calculate(daily_factor_data, forward_returns_map)
        score_metrics = ScoreMetricsCalculator().calculate(first_strategy_results, forward_returns_map, daily_factor_data)
        strategy_metrics = StrategyMetricsCalculator().calculate(all_strategy_results, forward_returns_map, index_data)

        # 6. 生成改进方案
        logger.info("阶段 6/6: 生成改进方案...")
        factor_recs = FactorWeightOptimizer().generate(factor_metrics, score_metrics)
        risk_recs = RiskRuleOptimizer().generate(score_metrics)
        signal_recs = SignalSystemOptimizer().generate(signal_metrics)
        strategy_recs = StrategyTemplateOptimizer().generate(strategy_metrics, signal_metrics, factor_metrics)
        ref_price_rec = RefPriceOptimizer().generate(all_forward_returns, stock_info)
        improvements = ImprovementPrioritizer().prioritize(
            factor_recs, risk_recs, signal_recs, strategy_recs, ref_price_rec,
        )

        # 汇总
        hit_rate_5 = return_metrics.get(5)
        effective_count = len(factor_metrics.get("effective_factors", []))
        improvement_count = len(improvements.get("items", []))

        evaluation_data = {
            "summary": {
                "评估期": f"{start_date} ~ {end_date}",
                "交易日数": len(trading_dates),
                "策略数": len(all_strategy_results),
                "T+5命中率": f"{hit_rate_5.hit_rate:.1f}%" if hit_rate_5 else "N/A",
                "T+5平均超额收益": f"{hit_rate_5.excess_return:.2f}%" if hit_rate_5 else "N/A",
                "有效因子数": f"{effective_count}/52",
                "改进建议数": improvement_count,
                "index_data_status": index_data_status,
            },
            "return_metrics": return_metrics,
            "signal_metrics": signal_metrics,
            "factor_metrics": factor_metrics,
            "score_metrics": score_metrics,
            "strategy_metrics": strategy_metrics,
            "improvements": improvements,
        }

        # 输出报告
        reporter = ReportGenerator()
        output_dir = str(Path(args.output).parent)

        if args.format in ("json", "both"):
            json_path = args.output if args.output.endswith(".json") else args.output + ".json"
            reporter.generate_json(evaluation_data, json_path)
            logger.info("JSON 报告: %s", json_path)

        if args.format in ("markdown", "both"):
            md_path = args.output.replace(".json", ".md") if args.output.endswith(".json") else args.output + ".md"
            reporter.generate_markdown(evaluation_data, md_path)
            logger.info("Markdown 报告: %s", md_path)

        reporter.generate_improvement_reports(
            {
                "factor_weights": factor_recs,
                "risk_rules": risk_recs,
                "signals": signal_recs,
                "strategies": strategy_recs,
                "ref_price": ref_price_rec,
                "summary": improvements,
            },
            output_dir,
        )

        elapsed = time.time() - total_start
        hr = hit_rate_5.hit_rate if hit_rate_5 else 0
        er = hit_rate_5.excess_return if hit_rate_5 else 0
        print(
            f"评估完成：命中率 {hr:.1f}%，平均超额收益 {er:.2f}%，"
            f"有效因子 {effective_count}/52，改进建议 {improvement_count} 条 "
            f"(耗时 {elapsed:.0f}s)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="智能选股功能评估")
    parser.add_argument("--start-date", type=str, default=None, help="评估起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="评估结束日期 (YYYY-MM-DD)")
    parser.add_argument("--strategies", type=str, default=None, help="策略名称列表，逗号分隔")
    parser.add_argument("--output", type=str, default="reports/screener_evaluation.json", help="报告输出路径")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="both", help="输出格式")
    args = parser.parse_args()

    asyncio.run(run_evaluation(args))


if __name__ == "__main__":
    main()
