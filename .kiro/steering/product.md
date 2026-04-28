# Product Overview

A-Share Quantitative Trading System (A股右侧量化选股系统) — a full-stack platform for quantitative right-side stock screening and trading in the Chinese A-share market.

## Core Capabilities

- Market data ingestion: real-time and historical K-line data via TimescaleDB, plus fundamental and money-flow data
- Intelligent stock screening: configurable multi-factor strategies (MA trend, MACD, BOLL, RSI, DMA, volume-price, breakout) with AND/OR logic and weighted scoring
- Risk management: pre-trade (market risk, stock filters, blacklist), in-trade (position limits, sector concentration, breakdown detection), post-trade (fixed/trailing/trend stop-loss, strategy health)
- Backtesting engine: historical strategy replay with 9 performance metrics (Sharpe, Calmar, max drawdown, win rate, etc.), T+1 rule enforcement, configurable exit conditions
- Trade execution: live and paper trading modes, limit/market/condition orders, broker API integration
- Post-market review: automated daily review reports and strategy performance analysis
- Real-time alerts: WebSocket push for screening results, stop-loss triggers, price thresholds, and market risk changes
- Admin & audit: user/role management (ADMIN, TRADER, READONLY), audit logging, data retention policies

## Domain Context

- Trading hours: 09:25–15:00 CST (Asia/Shanghai)
- Scheduled jobs run on weekdays only (Mon–Fri)
- All monetary values use `Decimal`; percentages are floats
- Stock symbols use standard format with exchange suffix (e.g., "600000.SH", "000001.SZ", "830799.BJ")
- Market risk levels: NORMAL (threshold 80) → CAUTION (threshold 90, below MA20) → DANGER (buy suspended, below MA60)
- Comments, docstrings, and UI labels are in Chinese (中文)
- Data sources: Tushare, AkShare, local CSV files for K-line data
