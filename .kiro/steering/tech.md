# Tech Stack & Build

## Backend (Python 3.11+)

- Framework: FastAPI (async, uvicorn), app factory in `app/main.py` via `create_app()`
- ORM: SQLAlchemy 2.0 async API with two separate engines:
  - `PGBase` → PostgreSQL 16 (business data: users, strategies, trades, stocks, pools, risk events, 86 Tushare tables)
  - `TSBase` → TimescaleDB (time-series: K-line hypertables)
- Models use `Mapped[]` + `mapped_column()` (SQLAlchemy 2.0 declarative style)
- Migrations: Alembic (script dir: `alembic/`, versions in `alembic/versions/`, 24+ migrations)
- Task queue: Celery + Redis broker, 4 queues: `data_sync`, `screening`, `backtest`, `review`
- Task base classes in `app/tasks/base.py`: `DataSyncTask`, `ScreeningTask`, `BacktestTask`, `ReviewTask`
- Scheduling: Celery Beat (crontab-based, weekday-only jobs, 含 risk_cleanup 每日 2:00)
- Caching / Pub-Sub: Redis 7 (async via `redis.asyncio`)
- Config: pydantic-settings (`BaseSettings` singleton in `app/core/config.py`), loaded from `.env`
- Auth: custom JWT (HMAC-SHA256), TOTP 2FA stub, bcrypt-style password hashing
- Build system: Hatchling (`pyproject.toml`)
- Python package layout: `app/` is the sole top-level package
- Business data types: plain `dataclasses` + `enum.Enum` in `app/core/schemas.py` (not Pydantic)
- Async test mode: `pytest-asyncio` with `asyncio_mode = "auto"`

## Data Sources

- Tushare Pro: 80+ API 接口, 4 级 Token (BASIC/ADVANCED/PREMIUM/SPECIAL), 声明式注册表管理
  - 支持多种分批策略: by_code, by_date, by_sector, by_index, by_code_and_date, single
  - 支持截断检测与递归重试, 字段映射, 冲突处理 (upsert/ignore)
  - 存储引擎路由: PG (业务表) / TS (时序表) / kline (K线专用) / sector_kline / adjustment_factor
  - 速率限制分组: 10 个限流组 (TIER_80/60/20/10/2 等)
- AkShare: 备用数据源适配器
- 本地 CSV: K线数据、复权因子、板块数据 (DC/TI/TDX 三种格式)

## Screening Engine

- 因子注册表: 52 个因子, 7 大类 (TECHNICAL/MONEY_FLOW/FUNDAMENTAL/SECTOR/CHIP/MARGIN/BOARD_HIT)
- 阈值类型: ABSOLUTE, PERCENTILE, INDUSTRY_RELATIVE, Z_SCORE, BOOLEAN, RANGE
- 策略模板: 22 个内置示例 (趋势跟踪/MACD金叉/板块龙头/行业轮动/突破/多指标共振等)
- 突破检测: 箱体突破/前高突破/趋势线突破, 含假突破检测与量能持续性验证
- 均线系统: 多头排列检测/趋势打分(0-100)/均线支撑信号

## Backtest Engine

- 因子数据加载: 批量预加载基本面/资金流/Tushare因子/板块数据
- 因子填充: 运行时 enrich factor dicts (PSY/OBV/量价/板块强度/条件百分位/行业相对)
- T+1 规则强制, 可配置退出条件, 9 项绩效指标

## Frontend (TypeScript)

- Framework: Vue 3 (Composition API, `<script setup>`)
- State: Pinia stores (defineStore with setup syntax), 10 个 stores
- Routing: vue-router 4 with JWT auth guards and role-based access (`meta.roles`), 17 个路由
- HTTP: Axios with interceptors for token injection and error handling
- Charts: ECharts 5 via vue-echarts (K线图/分钟K线/通用预览图表)
- Build: Vite 5 with `@` path alias → `src/`
- Testing: Vitest + @vue/test-utils + fast-check (property-based)
- UI Components: 自定义组件为主 (DatePicker/PreviewTable/PreviewChart/MinuteKlineChart)

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
