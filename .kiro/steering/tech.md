# Tech Stack & Build

## Backend (Python 3.11+)

- Framework: FastAPI (async, uvicorn), app factory in `app/main.py` via `create_app()`
- ORM: SQLAlchemy 2.0 async API with two separate engines:
  - `PGBase` → PostgreSQL 16 (business data: users, strategies, trades, stocks)
  - `TSBase` → TimescaleDB (time-series: K-line hypertables)
- Models use `Mapped[]` + `mapped_column()` (SQLAlchemy 2.0 declarative style)
- Migrations: Alembic (script dir: `alembic/`, versions in `alembic/versions/`)
- Task queue: Celery + Redis broker, 4 queues: `data_sync`, `screening`, `backtest`, `review`
- Task base classes in `app/tasks/base.py`: `DataSyncTask`, `ScreeningTask`, `BacktestTask`, `ReviewTask`
- Scheduling: Celery Beat (crontab-based, weekday-only jobs)
- Caching / Pub-Sub: Redis 7 (async via `redis.asyncio`)
- Config: pydantic-settings (`BaseSettings` singleton in `app/core/config.py`), loaded from `.env`
- Auth: custom JWT (HMAC-SHA256), TOTP 2FA stub, bcrypt-style password hashing
- Build system: Hatchling (`pyproject.toml`)
- Python package layout: `app/` is the sole top-level package
- Business data types: plain `dataclasses` + `enum.Enum` in `app/core/schemas.py` (not Pydantic)
- Async test mode: `pytest-asyncio` with `asyncio_mode = "auto"`

## Frontend (TypeScript)

- Framework: Vue 3 (Composition API, `<script setup>`)
- State: Pinia stores (defineStore with setup syntax)
- Routing: vue-router 4 with JWT auth guards and role-based access (`meta.roles`)
- HTTP: Axios with interceptors for token injection and error handling
- Charts: ECharts 5 via vue-echarts
- Build: Vite 5 with `@` path alias → `src/`
- Testing: Vitest + @vue/test-utils + fast-check (property-based)

## Infrastructure

- Docker Compose orchestration: app, celery-worker, celery-beat, timescaledb, postgres, redis, nginx
- Nginx reverse proxy serves frontend static files and proxies `/api` to FastAPI
- Python image: `python:3.11-slim`
- Vite dev server proxies `/api` and `/ws` to localhost:8000

## Common Commands

### Backend
```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run dev server
uvicorn app.main:app --reload

# Run all backend tests
pytest

# Run property-based tests only
pytest tests/properties/

# Run a specific test file
pytest tests/services/test_risk_controller.py

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Celery worker
celery -A app.core.celery_app worker --loglevel=info -Q data_sync,screening,backtest,review

# Celery beat
celery -A app.core.celery_app beat --loglevel=info
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Dev server
npm run dev

# Build for production
npm run build

# Run tests (single run)
npm test

# Run tests in watch mode
npm run test:watch

# Type checking
npm run type-check
```

### Docker
```bash
docker compose up -d          # Start all services
docker compose down            # Stop all services
docker compose logs -f app     # Tail app logs
```
