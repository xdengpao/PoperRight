# Project Structure

```
├── app/                          # Backend Python package (FastAPI)
│   ├── main.py                   # App factory, middleware, lifespan
│   ├── core/                     # Cross-cutting infrastructure
│   │   ├── config.py             # pydantic-settings (Settings singleton)
│   │   ├── database.py           # SQLAlchemy engines, session factories, ORM bases
│   │   ├── redis_client.py       # Async Redis client, pub/sub, cache helpers
│   │   ├── celery_app.py         # Celery instance, queue routing, beat schedule
│   │   ├── schemas.py            # Pure dataclasses & enums (no ORM/Pydantic)
│   │   ├── security.py           # JWT, password hashing, TOTP, rate limiter
│   │   ├── pubsub_relay.py       # Redis → WebSocket relay
│   │   └── websocket_manager.py  # WS connection manager
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── kline.py              # TimescaleDB K-line hypertable
│   │   ├── stock.py              # StockInfo, StockList, PermanentExclusion
│   │   ├── strategy.py           # StrategyTemplate, ScreenResult
│   │   ├── backtest.py           # BacktestRun
│   │   ├── trade.py              # TradeOrder, Position
│   │   └── user.py               # AppUser, AuditLog
│   ├── services/                 # Business logic layer
│   │   ├── data_engine/          # Market data adapters & repository
│   │   ├── screener/             # Stock screening strategies & executor
│   │   ├── risk_controller.py    # Risk checks (position, sector, stop-loss)
│   │   ├── backtest_engine.py    # Historical backtesting
│   │   ├── trade_executor.py     # Order submission (live/paper)
│   │   ├── review_analyzer.py    # Daily review report generation
│   │   ├── alert_service.py      # Alert evaluation & dispatch
│   │   ├── alert_channel.py      # Notification channels
│   │   ├── admin_module.py       # User/role management, audit
│   │   └── param_optimizer.py    # Strategy parameter optimization
│   ├── api/v1/                   # REST + WebSocket endpoints (versioned)
│   │   ├── auth.py, data.py, screen.py, risk.py, backtest.py
│   │   ├── trade.py, review.py, admin.py, ws.py
│   │   └── __init__.py           # Aggregates all sub-routers
│   └── tasks/                    # Celery async tasks
│       ├── data_sync.py          # Market/fundamental/money-flow sync
│       ├── screening.py          # EOD & realtime screening
│       ├── backtest.py           # Backtest execution
│       └── review.py             # Daily review generation
│
├── tests/                        # Backend tests (pytest)
│   ├── properties/               # Property-based tests (Hypothesis)
│   ├── services/                 # Unit tests per service
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
├── alembic/                      # DB migration scripts
├── docker-compose.yml            # Full stack orchestration
├── Dockerfile                    # Backend image
├── pyproject.toml                # Python project config (Hatchling)
└── .env / .env.example           # Environment variables
```

## Conventions

- Backend layers: `api/` → `services/` → `models/` (top-down dependency)
- Two ORM base classes: `PGBase` (business) and `TSBase` (time-series) — never mix
- Business data types live in `app/core/schemas.py` as plain dataclasses, not Pydantic models
- API versioning via URL prefix: `/api/v1/`
- Celery tasks are thin wrappers that call into `services/`
- Frontend tests use `__tests__/` directories co-located with source files
- Property-based tests: backend uses Hypothesis (`tests/properties/`), frontend uses fast-check (`*.property.test.ts`)
- Backend test files follow `test_*.py` naming; frontend uses `*.test.ts` / `*.property.test.ts`
