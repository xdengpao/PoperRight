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
│   │   ├── sector.py             # Sector data models
│   │   ├── strategy.py           # StrategyTemplate, ScreenResult
│   │   ├── backtest.py           # BacktestRun
│   │   ├── trade.py              # TradeOrder, Position
│   │   ├── user.py               # AppUser, AuditLog
│   │   └── adjustment_factor.py  # Price adjustment factors
│   ├── services/                 # Business logic layer
│   │   ├── data_engine/          # Market data adapters & repository
│   │   ├── screener/             # Stock screening strategies & executor
│   │   ├── risk_controller.py    # Risk checks (market, position, sector, stop-loss)
│   │   ├── backtest_engine.py    # Historical backtesting
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
│   │   └── __init__.py           # Aggregates all sub-routers under /api/v1
│   └── tasks/                    # Celery async tasks (thin wrappers → services)
│       ├── base.py               # Task base classes with retry/backoff
│       ├── data_sync.py          # Market/fundamental/money-flow sync
│       ├── screening.py          # EOD & realtime screening
│       ├── backtest.py           # Backtest execution
│       ├── review.py             # Daily review generation
│       └── sector_sync.py        # Sector data synchronization
│
├── tests/                        # Backend tests (pytest)
│   ├── properties/               # Property-based tests (Hypothesis)
│   ├── services/                 # Unit tests per service
│   ├── api/                      # API endpoint tests
│   ├── core/                     # Core module tests
│   ├── tasks/                    # Task tests
│   ├── integration/              # End-to-end pipeline tests
│   ├── security/                 # Security-focused tests
│   └── performance/              # Load tests (Locust)
│
├── frontend/                     # Vue 3 SPA
│   ├── src/
│   │   ├── api/                  # Axios client & interceptors
│   │   ├── components/           # Shared UI components
│   │   ├── composables/          # Vue composables (usePageState, usePermission)
│   │   ├── layouts/              # Page layouts (MainLayout)
│   │   ├── router/               # vue-router config with auth guards
│   │   ├── services/             # WebSocket client
│   │   ├── stores/               # Pinia stores (auth, alert, market, positions, screener)
│   │   ├── views/                # Page-level components
│   │   └── test/                 # Test setup
│   └── package.json
│
├── alembic/                      # DB migration scripts (timezone: Asia/Shanghai)
├── docker-compose.yml            # Full stack orchestration
├── Dockerfile                    # Backend image
├── pyproject.toml                # Python project config (Hatchling)
└── .env / .env.example           # Environment variables
```

## Conventions

### Architecture
- Backend layers: `api/` → `services/` → `models/` (top-down dependency, never skip layers)
- Two ORM base classes: `PGBase` (business data) and `TSBase` (time-series) — never mix in the same model
- Business data types live in `app/core/schemas.py` as plain `dataclasses`, not Pydantic models
- Config classes use `to_dict()` / `from_dict()` classmethods for JSON serialization
- API versioning via URL prefix: `/api/v1/`
- Celery tasks are thin wrappers that call into `services/`; task base classes in `app/tasks/base.py`
- FastAPI dependency injection for DB sessions: `get_pg_session()`, `get_ts_session()`

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
