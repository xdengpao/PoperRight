# Project Structure

```
├── app/                          # Backend Python package (FastAPI)
│   ├── main.py                   # App factory (create_app), middleware, lifespan
│   ├── core/                     # Cross-cutting infrastructure
│   │   ├── config.py             # pydantic-settings (Settings singleton)
│   │   ├── database.py           # SQLAlchemy engines, session factories, PGBase/TSBase
│   │   ├── redis_client.py       # Async Redis client, pub/sub, cache helpers
│   │   ├── celery_app.py         # Celery instance, queue routing, beat schedule
│   │   ├── schemas.py            # Pure dataclasses & enums (no ORM/Pydantic)
│   │   ├── security.py           # JWT, password hashing, TOTP, rate limiter
│   │   ├── pubsub_relay.py       # Redis → WebSocket relay
│   │   └── websocket_manager.py  # WS connection manager
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── kline.py              # TimescaleDB K-line hypertable (TSBase)
│   │   ├── stock.py              # StockInfo, StockList, PermanentExclusion (PGBase)
│   │   ├── sector.py             # Sector info, constituents, kline (PGBase + TSBase)
│   │   ├── strategy.py           # StrategyTemplate, ScreenResult
│   │   ├── backtest.py           # BacktestRun
│   │   ├── trade.py              # TradeOrder, Position
│   │   ├── user.py               # AppUser, AuditLog
│   │   ├── adjustment_factor.py  # Price adjustment factors
│   │   ├── pool.py               # StockPool, StockPoolItem (选股池)
│   │   ├── money_flow.py         # MoneyFlow (资金流向)
│   │   ├── risk_event.py         # RiskEventLog (风控事件日志)
│   │   └── tushare_import.py     # TushareImportLog + 86 Tushare数据表模型
│   ├── services/                 # Business logic layer
│   │   ├── data_engine/          # Market data adapters & repository (see below)
│   │   ├── screener/             # Stock screening strategies & executor (see below)
│   │   ├── risk_controller.py    # Risk checks (market, position, sector, stop-loss)
│   │   ├── backtest_engine.py    # Historical backtesting
│   │   ├── backtest_factor_data_loader.py  # 回测因子数据批量加载
│   │   ├── backtest_factor_provider.py     # 回测因子数据填充与计算
│   │   ├── pool_manager.py       # 选股池 CRUD & enrichment
│   │   ├── csv_exporter.py       # 选股结果 CSV 导出
│   │   ├── trade_executor.py     # Order submission (live/paper)
│   │   ├── review_analyzer.py    # Daily review report generation
│   │   ├── alert_service.py      # Alert evaluation & dispatch
│   │   ├── alert_channel.py      # Notification channels
│   │   ├── admin_module.py       # User/role management, audit
│   │   ├── param_optimizer.py    # Strategy parameter optimization
│   │   ├── exit_condition_evaluator.py  # Custom exit condition evaluation
│   │   └── threshold_resolver.py # Dynamic threshold resolution
│   ├── api/v1/                   # REST + WebSocket endpoints (versioned)
│   │   ├── auth.py, data.py, screen.py, risk.py, backtest.py
│   │   ├── trade.py, review.py, admin.py, sector.py, ws.py
│   │   ├── pool.py              # 选股池 REST API (/pools)
│   │   ├── tushare.py           # Tushare 数据导入 API (/data/tushare)
│   │   ├── tushare_preview.py   # Tushare 数据预览 API (/data/tushare/preview)
│   │   └── __init__.py           # Aggregates all sub-routers under /api/v1
│   └── tasks/                    # Celery async tasks (thin wrappers → services)
│       ├── base.py               # Task base classes with retry/backoff
│       ├── data_sync.py          # Market/fundamental/money-flow sync
│       ├── screening.py          # EOD & realtime screening
│       ├── backtest.py           # Backtest execution
│       ├── review.py             # Daily review generation
│       ├── sector_sync.py        # Sector data synchronization
│       ├── tushare_import.py     # Tushare API 批量导入 (多策略分批)
│       └── risk_cleanup.py       # 风控事件日志定期清理 (90天)
│
├── app/services/data_engine/     # 数据引擎子模块
│   ├── base_adapter.py           # BaseDataSourceAdapter 抽象基类
│   ├── data_source_router.py     # 数据源路由 (DC/TI/TDX/Tushare)
│   ├── kline_repository.py       # K线数据读写 (TimescaleDB)
│   ├── adj_factor_repository.py  # 复权因子读写
│   ├── forward_adjustment.py     # 前复权计算
│   ├── sector_repository.py      # 板块数据读写
│   ├── sector_csv_parser.py      # 板块CSV解析 (DC/TI/TDX三引擎)
│   ├── sector_import.py          # 板块数据导入编排 (全量/增量)
│   ├── stock_filter.py           # 股票过滤 (ST/退市/新股)
│   ├── format_converter.py       # 数据格式转换
│   ├── local_kline_import.py     # 本地CSV K线导入
│   ├── backfill_service.py       # 历史数据回填编排
│   ├── date_batch_splitter.py    # 日期分批工具
│   ├── tushare_adapter.py        # Tushare HTTP 适配器
│   ├── tushare_registry.py       # Tushare API 注册表 (80+ API, 4级Token)
│   ├── tushare_import_service.py # Tushare 导入编排服务
│   ├── tushare_preview_service.py # Tushare 数据预览查询服务
│   ├── akshare_adapter.py        # AkShare 适配器
│   ├── market_adapter.py         # 大盘数据适配器
│   ├── fundamental_adapter.py    # 基本面数据适配器
│   └── money_flow_adapter.py     # 资金流向适配器
│
├── app/services/screener/        # 选股引擎子模块
│   ├── screen_executor.py        # 选股执行器 (调度因子计算 + 评分)
│   ├── screen_data_provider.py   # 选股数据供给 (K线/因子/板块)
│   ├── strategy_engine.py        # 策略引擎 (因子组合 + 权重评分)
│   ├── factor_registry.py        # 因子注册表 (52因子, 7大类)
│   ├── indicators.py             # 技术指标计算 (MA/MACD/RSI/BOLL/DMA)
│   ├── ma_trend.py               # 均线趋势因子 (多头排列/趋势打分/均线支撑)
│   ├── breakout.py               # 突破因子 (箱体/前高/趋势线突破 + 假突破检测)
│   ├── volume_price.py           # 量价因子 (换手率/量价背离/资金流/大单/板块共振)
│   ├── sector_strength.py        # 板块强度因子
│   └── strategy_examples.py      # 22个策略模板示例
│
├── tests/                        # Backend tests (pytest)
│   ├── properties/               # Property-based tests (Hypothesis, 100+ files)
│   ├── services/                 # Unit tests per service (含 data_engine/, screener/ 子目录)
│   ├── api/                      # API endpoint tests (26 files)
│   ├── core/                     # Core module tests
│   ├── tasks/                    # Task tests (13 files)
│   ├── integration/              # End-to-end pipeline tests (14 files)
│   ├── security/                 # Security-focused tests
│   └── performance/              # Load tests (Locust)
│
├── frontend/                     # Vue 3 SPA
│   ├── src/
│   │   ├── api/                  # Axios client & interceptors
│   │   ├── components/           # Shared UI components (see below)
│   │   ├── composables/          # Vue composables (usePageState, usePermission)
│   │   ├── layouts/              # Page layouts (MainLayout)
│   │   ├── router/               # vue-router config with auth guards
│   │   ├── services/             # WebSocket client
│   │   ├── stores/               # Pinia stores (see below)
│   │   ├── views/                # Page-level components (see below)
│   │   └── test/                 # Test setup
│   └── package.json
│
├── alembic/                      # DB migration scripts (timezone: Asia/Shanghai)
├── scripts/                      # 运维脚本 (dev-start/stop, cleanup)
├── docs/                         # 部署文档、板块数据使用说明
├── docker-compose.yml            # Full stack orchestration
├── Dockerfile                    # Backend image
├── pyproject.toml                # Python project config (Hatchling)
└── .env / .env.example           # Environment variables
```

## Frontend Stores

| Store | 文件 | 管理内容 |
|-------|------|---------|
| auth | `stores/auth.ts` | 登录状态、JWT、用户信息 |
| alert | `stores/alert.ts` | 预警消息、toast 通知 |
| market | `stores/market.ts` | 大盘概况数据 |
| positions | `stores/positions.ts` | 持仓列表 |
| screener | `stores/screener.ts` | 选股结果、策略模板 |
| backtest | `stores/backtest.ts` | 回测状态与结果 |
| sector | `stores/sector.ts` | 板块排行、K线展开、板块浏览 |
| stockPool | `stores/stockPool.ts` | 选股池 CRUD、enriched 股票列表 |
| localImport | `stores/localImport.ts` | 本地数据导入 (K线/复权/板块) |
| tusharePreview | `stores/tusharePreview.ts` | Tushare 数据预览、完整性检查 |

## Frontend Views & Routes

| 路径 | 视图 | 功能 |
|------|------|------|
| `/dashboard` | DashboardView | 大盘概况 |
| `/data/online` | DataManageView | 在线数据管理 |
| `/data/online/tushare` | TushareImportView | Tushare 数据导入 (80+ API) |
| `/data/online/tushare-preview` | TusharePreviewView | Tushare 数据预览/完整性检查 |
| `/data/local` | LocalImportView | 本地 CSV 导入 (K线/复权/板块) |
| `/screener` | ScreenerView | 智能选股配置 |
| `/screener/results` | ScreenerResultsView | 选股结果展示 |
| `/stock-pool` | StockPoolView | 选股池管理 (enriched 详情) |
| `/risk` | RiskView | 风险控制 |
| `/backtest` | BacktestView | 策略回测 |
| `/trade` | TradeView | 交易执行 (TRADER/ADMIN) |
| `/positions` | PositionsView | 持仓管理 (TRADER/ADMIN) |
| `/review` | ReviewView | 复盘分析 |
| `/admin` | AdminView | 系统管理 (ADMIN) |

## Frontend Components

| 组件 | 用途 |
|------|------|
| MinuteKlineChart | 分钟级K线图 (多频率/复权切换) |
| PreviewChart | 通用数据预览图表 (candlestick/line/bar) |
| PreviewTable | 通用数据预览表格 (动态列/智能精度) |
| DatePicker | 自定义日历日期选择器 |
| FactorUsagePanel | 因子使用说明面板 |
| SectorBrowserPanel | 板块数据浏览面板 (信息/成分/行情三Tab) |
| TushareTabNav | Tushare 导入/预览页面 Tab 导航 |
| AlertNotification | 预警通知组件 |
| ErrorBanner | 错误提示横幅 |
| LoadingSpinner | 加载状态指示器 |

## Conventions

### Architecture
- Backend layers: `api/` → `services/` → `models/` (top-down dependency, never skip layers)
- Two ORM base classes: `PGBase` (business data) and `TSBase` (time-series) — never mix in the same model
- Business data types live in `app/core/schemas.py` as plain `dataclasses`, not Pydantic models
- Config classes use `to_dict()` / `from_dict()` classmethods for JSON serialization
- API versioning via URL prefix: `/api/v1/`
- Celery tasks are thin wrappers that call into `services/`; task base classes in `app/tasks/base.py`
- FastAPI dependency injection for DB sessions: `get_pg_session()`, `get_ts_session()`
- 数据引擎采用 Adapter 模式: `BaseDataSourceAdapter` → 具体适配器 (Tushare/AkShare/本地CSV)
- Tushare API 通过注册表 (`tushare_registry.py`) 声明式管理, 支持 4 级 Token 路由和多种分批策略
- 选股因子通过 `factor_registry.py` 注册表管理 (52 因子, 7 大类), 支持多种阈值类型
- 板块数据解析采用多引擎模式: DC/TI/TDX 各有独立 ParsingEngine

### Testing
- Backend test files follow `test_*.py` naming
- Frontend tests use `__tests__/` directories co-located with source files
- Property-based tests: backend uses Hypothesis (`tests/properties/`), frontend uses fast-check (`*.property.test.ts`)
- Service classes often provide a `_pure` or `compute_*_pure` static method for property testing without DB dependencies

### Code Style
- Docstrings and inline comments are in Chinese (中文)
- Module-level docstrings describe purpose and list related requirement IDs (需求 X.Y)
- Constants are module-level with underscore prefix (e.g., `_DAILY_GAIN_LIMIT`)
- Enums inherit from `(str, Enum)` for JSON serialization
