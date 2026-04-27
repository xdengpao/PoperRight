"""回测任务模块"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from decimal import Decimal

import redis
from sqlalchemy import create_engine, select, and_, text
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.schemas import ExitConditionConfig, StrategyConfig
from app.models.adjustment_factor import AdjustmentFactor
# 前复权函数与选股引擎（ScreenDataProvider）共享同一纯函数实现
# (Requirement 13.3, 13.5)
from app.services.data_engine.forward_adjustment import adjust_kline_bars
from app.tasks.base import BaseTask, BacktestTask

logger = logging.getLogger(__name__)


def calculate_warmup_start_date(
    start_date: date,
    strategy_config: StrategyConfig,
    buffer_days: int = 250,
) -> date:
    """根据策略配置中的指标参数，计算所需的预热起始日期。

    取 max(ma_periods) 和各指标预热需求中的最大值，
    再乘以 1.5 倍安全系数（考虑非交易日），至少 buffer_days 个自然日。
    """
    # Step 1: 收集所有指标的最大回看窗口
    max_lookback = max(strategy_config.ma_periods) if strategy_config.ma_periods else 0

    ind = strategy_config.indicator_params
    if hasattr(ind, "macd_slow"):
        # MACD: EMA(slow) 需要 slow_period 天, 再加 signal_period
        macd_warmup = ind.macd_slow + ind.macd_signal
        max_lookback = max(max_lookback, macd_warmup)

        # BOLL: 需要 boll_period 天
        max_lookback = max(max_lookback, ind.boll_period)

        # RSI: 需要 rsi_period + 1 天
        max_lookback = max(max_lookback, ind.rsi_period + 1)

        # DMA: 需要 max(dma_short, dma_long) 天
        max_lookback = max(max_lookback, ind.dma_long)

    # Step 2: 取 buffer_days 和 max_lookback 的较大值
    required_days = max(buffer_days, max_lookback)

    # Step 3: 乘以 1.5 安全系数（覆盖节假日、停牌）
    calendar_days = int(required_days * 1.5)

    # Step 4: 计算预热起始日期
    warmup_date = start_date - timedelta(days=calendar_days)

    return warmup_date


def _get_sync_pg_url() -> str:
    """将 asyncpg URL 转为同步 psycopg2 URL。"""
    return settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


def _get_sync_ts_url() -> str:
    """将 asyncpg URL 转为同步 psycopg2 URL。"""
    return settings.timescale_url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


def _redis_set(key: str, value: str, ex: int = 86400) -> None:
    """同步写入 Redis。"""
    try:
        r = redis.from_url(settings.redis_url)
        r.set(key, value, ex=ex)
        r.close()
    except Exception as exc:
        logger.warning("Redis 写入失败: %s", exc)


@celery_app.task(base=BacktestTask, bind=True, queue="backtest", name="backtest.run")
def run_backtest_task(
    self,
    run_id: str,
    strategy_id: str | None = None,
    start_date: str = "",
    end_date: str = "",
    initial_capital: float = 1_000_000.0,
    commission_buy: float = 0.0003,
    commission_sell: float = 0.0013,
    slippage: float = 0.001,
    max_holdings: int = 10,
    stop_loss_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    max_holding_days: int = 20,
    allocation_mode: str = "equal",
    enable_market_risk: bool = True,
    trend_stop_ma: int = 20,
    exit_conditions: dict | None = None,
    enable_fundamental_data: bool = False,
    enable_money_flow_data: bool = False,
    enable_tushare_factors: bool = False,
) -> dict:
    """执行回测 Celery 任务（同步数据库访问）。"""
    logger.info("回测任务启动 run_id=%s strategy_id=%s", run_id, strategy_id)

    # 写入初始进度
    _redis_set(f"backtest:result:{run_id}", json.dumps({"status": "RUNNING", "run_id": run_id}))

    try:
        from app.core.schemas import BacktestConfig, KlineBar, StrategyConfig
        from app.services.backtest_engine import BacktestEngine

        # ── 1. 加载策略配置 ──
        strategy_config = StrategyConfig(
            factors=[], logic="AND", weights={}, ma_periods=[5, 10, 20, 60, 120],
        )
        enabled_modules: list[str] | None = None
        raw_config_dict: dict = {}

        if strategy_id:
            try:
                pg_engine = create_engine(_get_sync_pg_url())
                with Session(pg_engine) as session:
                    row = session.execute(
                        text("SELECT config, enabled_modules FROM strategy_template WHERE id = :sid"),
                        {"sid": strategy_id},
                    ).first()
                    if row and row[0]:
                        raw_config_dict = row[0]
                        strategy_config = StrategyConfig.from_dict(raw_config_dict)
                        enabled_modules = row[1] if row[1] else None
                        logger.info("已加载策略配置 strategy_id=%s, enabled_modules=%s", strategy_id, enabled_modules)
                pg_engine.dispose()
            except Exception as exc:
                logger.warning("加载策略配置失败: %s", exc)

        sd = date.fromisoformat(start_date) if start_date else date(2024, 1, 1)
        ed = date.fromisoformat(end_date) if end_date else date(2024, 12, 31)

        # 反序列化自定义平仓条件
        exit_config = (
            ExitConditionConfig.from_dict(exit_conditions)
            if exit_conditions is not None
            else None
        )

        config = BacktestConfig(
            strategy_config=strategy_config,
            start_date=sd,
            end_date=ed,
            initial_capital=Decimal(str(initial_capital)),
            commission_buy=Decimal(str(commission_buy)),
            commission_sell=Decimal(str(commission_sell)),
            slippage=Decimal(str(slippage)),
            max_holdings=max_holdings,
            stop_loss_pct=stop_loss_pct,
            trailing_stop_pct=trailing_stop_pct,
            max_holding_days=max_holding_days,
            allocation_mode=allocation_mode,
            enable_market_risk=enable_market_risk,
            trend_stop_ma=trend_stop_ma,
            enabled_modules=enabled_modules,
            raw_config=raw_config_dict,
            exit_conditions=exit_config,
        )

        # ── 2. 从 TimescaleDB 加载 K 线数据（同步） ──
        kline_data: dict[str, list[KlineBar]] = {}
        index_data: dict[str, list[KlineBar]] = {}

        warmup_date = calculate_warmup_start_date(sd, strategy_config)
        logger.info("预热起始日期: %s (回测起始: %s)", warmup_date.isoformat(), sd.isoformat())

        try:
            ts_engine = create_engine(_get_sync_ts_url())
            with Session(ts_engine) as session:
                rows = session.execute(
                    text("""
                        SELECT symbol, time, open, high, low, close, volume, amount, turnover, vol_ratio
                        FROM kline
                        WHERE freq = '1d' AND time >= :warmup_start AND time <= :end
                        ORDER BY symbol, time
                    """),
                    {"warmup_start": warmup_date.isoformat(), "end": ed.isoformat()},
                ).fetchall()

                for row in rows:
                    sym = row[0]
                    bar = KlineBar(
                        time=row[1],
                        symbol=sym,
                        freq="1d",
                        open=Decimal(str(row[2] or 0)),
                        high=Decimal(str(row[3] or 0)),
                        low=Decimal(str(row[4] or 0)),
                        close=Decimal(str(row[5] or 0)),
                        volume=int(row[6] or 0),
                        amount=Decimal(str(row[7] or 0)),
                        turnover=Decimal(str(row[8] or 0)),
                        vol_ratio=Decimal(str(row[9] or 0)),
                    )
                    if sym in ("000001.SH", "399006.SZ"):
                        index_data.setdefault(sym, []).append(bar)
                    else:
                        kline_data.setdefault(sym, []).append(bar)

            ts_engine.dispose()
            logger.info("K 线数据加载完成: %d 只股票, %d 条指数",
                        len(kline_data), sum(len(v) for v in index_data.values()))
        except Exception as exc:
            logger.warning("K 线数据加载失败: %s", exc)

        # ── 2.5 加载前复权因子并应用 ──
        adj_factors: dict[str, list[AdjustmentFactor]] = {}
        latest_factors: dict[str, Decimal] = {}
        try:

            ts_adj_engine = create_engine(_get_sync_ts_url())
            with Session(ts_adj_engine) as session:
                # 批量查询所有股票在回测日期范围内的前复权因子
                adj_rows = session.execute(
                    text("""
                        SELECT symbol, trade_date, adj_factor
                        FROM adjustment_factor
                        WHERE adj_type = 1
                          AND trade_date >= :start AND trade_date <= :end
                        ORDER BY symbol, trade_date
                    """),
                    {"start": warmup_date.isoformat(), "end": ed.isoformat()},
                ).fetchall()

                for row in adj_rows:
                    sym = row[0]
                    adj_factors.setdefault(sym, []).append(
                        AdjustmentFactor(
                            symbol=sym,
                            trade_date=row[1],
                            adj_type=1,
                            adj_factor=Decimal(str(row[2])),
                        )
                    )

                # 查询每只股票的最新复权因子（全局最新，不限日期范围）
                latest_rows = session.execute(
                    text("""
                        SELECT DISTINCT ON (symbol) symbol, adj_factor
                        FROM adjustment_factor
                        WHERE adj_type = 1
                        ORDER BY symbol, trade_date DESC
                    """),
                ).fetchall()
                for row in latest_rows:
                    latest_factors[row[0]] = Decimal(str(row[1]))

            ts_adj_engine.dispose()

            # 对每只股票的K线应用前复权
            adjusted_count = 0
            for sym, bars in kline_data.items():
                factors = adj_factors.get(sym, [])
                latest = latest_factors.get(sym)
                if factors and latest:
                    kline_data[sym] = adjust_kline_bars(bars, factors, latest)
                    adjusted_count += 1
                else:
                    logger.warning("股票 %s 无前复权因子数据，使用原始K线", sym)

            logger.info("前复权处理完成: %d/%d 只股票已调整", adjusted_count, len(kline_data))

        except Exception as exc:
            logger.warning("前复权因子加载失败，使用原始K线继续回测: %s", exc)

        # ── 2.6 加载分钟K线数据并应用前复权（Requirement 13.1, 13.4）──
        minute_kline_data: dict[str, dict[str, list[KlineBar]]] = {}
        _MINUTE_FREQS = ("1min", "5min", "15min", "30min", "60min")
        _FREQ_TO_DB = {"1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m", "60min": "60m"}

        # 仅在配置了分钟频率的平仓条件时才加载分钟K线
        needed_minute_freqs: set[str] = set()
        if exit_config and exit_config.conditions:
            for cond in exit_config.conditions:
                freq = cond.freq
                if freq == "minute":
                    freq = "1min"
                if freq in _MINUTE_FREQS:
                    needed_minute_freqs.add(freq)

        if needed_minute_freqs:
            try:
                ts_min_engine = create_engine(_get_sync_ts_url())
                with Session(ts_min_engine) as session:
                    for mfreq in needed_minute_freqs:
                        db_freq = _FREQ_TO_DB[mfreq]
                        min_rows = session.execute(
                            text("""
                                SELECT symbol, time, open, high, low, close, volume, amount, turnover, vol_ratio
                                FROM kline
                                WHERE freq = :freq AND time >= :warmup_start AND time <= :end
                                ORDER BY symbol, time
                            """),
                            {"freq": db_freq, "warmup_start": warmup_date.isoformat(), "end": ed.isoformat()},
                        ).fetchall()

                        freq_data: dict[str, list[KlineBar]] = {}
                        for row in min_rows:
                            sym = row[0]
                            bar = KlineBar(
                                time=row[1],
                                symbol=sym,
                                freq=db_freq,
                                open=Decimal(str(row[2] or 0)),
                                high=Decimal(str(row[3] or 0)),
                                low=Decimal(str(row[4] or 0)),
                                close=Decimal(str(row[5] or 0)),
                                volume=int(row[6] or 0),
                                amount=Decimal(str(row[7] or 0)),
                                turnover=Decimal(str(row[8] or 0)),
                                vol_ratio=Decimal(str(row[9] or 0)),
                            )
                            freq_data.setdefault(sym, []).append(bar)

                        # 对分钟K线应用前复权（复用日K线阶段已加载的复权因子）
                        min_adjusted = 0
                        for sym, bars in freq_data.items():
                            factors = adj_factors.get(sym, [])
                            latest = latest_factors.get(sym)
                            if factors and latest:
                                freq_data[sym] = adjust_kline_bars(bars, factors, latest)
                                min_adjusted += 1
                            # 无复权因子时保持原始数据（日K线处理阶段已记录过警告日志）

                        if freq_data:
                            minute_kline_data[mfreq] = freq_data
                            logger.info(
                                "分钟K线 %s 加载完成: %d 只股票, %d 只已前复权",
                                mfreq, len(freq_data), min_adjusted,
                            )

                ts_min_engine.dispose()
            except Exception as exc:
                logger.warning("分钟K线数据加载失败: %s", exc)

        # ── 3. 加载新增因子数据源 ──
        fundamental_data = None
        money_flow_data = None
        tushare_factor_data = None
        sector_kline_data_list = None
        stock_sector_map = None
        industry_map = None
        sector_info_map = None

        if enable_fundamental_data or enable_money_flow_data or enable_tushare_factors:
            try:
                from app.services.backtest_factor_data_loader import load_factor_data
                factor_data = load_factor_data(
                    enable_fundamental=enable_fundamental_data,
                    enable_money_flow=enable_money_flow_data,
                    enable_tushare=enable_tushare_factors,
                    symbols=list(kline_data.keys()),
                    start_date=warmup_date if 'warmup_date' in dir() else sd,
                    end_date=ed,
                    strategy_config=config.strategy_config,
                )
                fundamental_data = factor_data.get("fundamental")
                money_flow_data = factor_data.get("money_flow")
                tushare_factor_data = factor_data.get("tushare_factors")
                sector_kline_data_list = factor_data.get("sector_kline")
                stock_sector_map = factor_data.get("stock_sector_map")
                industry_map = factor_data.get("industry_map")
                sector_info_map = factor_data.get("sector_info_map")
            except Exception as exc:
                logger.warning("因子数据加载失败，使用默认值继续: %s", exc)

        # ── 4. 执行回测 ──
        engine = BacktestEngine()
        result = engine.run_backtest(
            config=config,
            kline_data=kline_data,
            index_data=index_data if enable_market_risk else None,
            minute_kline_data=minute_kline_data if minute_kline_data else None,
            fundamental_data=fundamental_data,
            money_flow_data=money_flow_data,
            tushare_factor_data=tushare_factor_data,
            sector_kline_data=sector_kline_data_list,
            stock_sector_map=stock_sector_map,
            industry_map=industry_map,
            sector_info_map=sector_info_map,
        )

        logger.info("回测完成 run_id=%s trades=%d return=%.4f",
                     run_id, result.total_trades, result.total_return)

        # ── 4. 构建结果并写入 Redis ──
        result_data = {
            "run_id": run_id,
            "status": "DONE",
            "result": {
                "annual_return": result.annual_return,
                "total_return": result.total_return,
                "win_rate": result.win_rate,
                "profit_loss_ratio": result.profit_loss_ratio,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "calmar_ratio": result.calmar_ratio,
                "total_trades": result.total_trades,
                "avg_holding_days": result.avg_holding_days,
                "equity_curve": [
                    [d.isoformat() if hasattr(d, "isoformat") else str(d), float(v)]
                    for d, v in (result.equity_curve or [])
                ],
                "trade_records": [
                    {
                        "date": t.get("date", "") if isinstance(t, dict) else str(getattr(t, "date", "")),
                        "created_at": t.get("date", "") if isinstance(t, dict) else str(getattr(t, "date", "")),
                        "symbol": t.get("symbol", "") if isinstance(t, dict) else getattr(t, "symbol", ""),
                        "action": t.get("action", "") if isinstance(t, dict) else getattr(t, "action", ""),
                        "direction": t.get("action", "") if isinstance(t, dict) else getattr(t, "action", ""),
                        "price": float(t.get("price", 0) if isinstance(t, dict) else getattr(t, "price", 0)),
                        "quantity": t.get("quantity", 0) if isinstance(t, dict) else getattr(t, "quantity", 0),
                        "cost": float(t.get("cost", 0) if isinstance(t, dict) else getattr(t, "cost", 0)),
                        "commission": float(t.get("cost", 0) if isinstance(t, dict) else getattr(t, "cost", 0)),
                        "amount": float(t.get("amount", 0) if isinstance(t, dict) else getattr(t, "amount", 0)),
                        "status": "FILLED",
                    }
                    for t in (result.trade_records or [])
                ],
            },
        }

        _redis_set(f"backtest:result:{run_id}", json.dumps(result_data, default=str))
        return result_data

    except Exception as exc:
        logger.error("回测任务失败 run_id=%s: %s", run_id, exc, exc_info=True)
        fail_data = {"run_id": run_id, "status": "FAILED", "error": str(exc)}
        _redis_set(f"backtest:result:{run_id}", json.dumps(fail_data))
        return fail_data
