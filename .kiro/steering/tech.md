# Tech Stack & Build

## Backend (Python 3.11+)

- Framework: FastAPI (async, uvicorn)
- ORM: SQLAlchemy 2.0 async API with two separate engines:
  - `PGBase` → PostgreSQL 16 (business data)
  - `TSBase` → TimescaleDB (time-series market data)
- Migrations: Alembic (script dir: `alembic/`, versions in `alembic/versions/`)
- Task queue: Celery + Redis broker, 4 queues: `data_sync`, `screening`, `backtest`, `review`
- Scheduling: Celery Beat (crontab-based, weekday-only jobs)
- Caching / Pub-Sub: Redis 7 (async via `redis.asyncio`)
- Config: pydantic-settings (`BaseSettings`), loaded from `.env`
- Auth: custom JWT (HMAC-SHA256), TOTP 2FA stub, bcrypt-style password hashing
- Build system: Hatchling (`pyproject.toml`)
- Python package layout: `app/` is the sole top-level package

## Frontend (TypeScript)

- Framework: Vue 3 (Composition API, `<script setup>`)
- State: Pinia stores
- Routing: vue-router 4 with JWT auth guards and role-based access
- HTTP: Axios with interceptors for token injection
- Charts: ECharts 5 via vue-echarts
- Build: Vite 5
- Testing: Vitest + @vue/test-utils + fast-check (property-based)

## Infrastructure

- Docker Compose orchestration: app, celery-worker, celery-beat, timescaledb, postgres, redis, nginx
- Nginx reverse proxy serves frontend static files and proxies `/api` to FastAPI
- Python image: `python:3.11-slim`

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
