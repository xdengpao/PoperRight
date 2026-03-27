# 部署文档

## 1. 环境要求

- Docker >= 24.0
- Docker Compose >= 2.20
- 最低配置：4 核 CPU / 8GB 内存 / 50GB 磁盘

## 2. 快速部署

### 2.1 克隆项目并配置环境变量

```bash
git clone <repo-url> && cd a-share-quant-trading-system
cp .env.example .env
```

编辑 `.env`，修改以下关键配置：

```dotenv
# 必须修改 —— 生产密钥
APP_SECRET_KEY=<随机生成的强密钥>
JWT_SECRET_KEY=<随机生成的强密钥>
APP_ENV=production
APP_DEBUG=false

# 数据库密码（与 docker-compose 中 POSTGRES_PASSWORD 一致）
POSTGRES_PASSWORD=<强密码>
DATABASE_URL=postgresql+asyncpg://postgres:<密码>@postgres:5432/quant_db
TIMESCALE_URL=postgresql+asyncpg://postgres:<密码>@timescaledb:5432/quant_ts

# 行情数据 API
MARKET_DATA_API_KEY=<你的API密钥>
MARKET_DATA_API_URL=<行情数据接口地址>

# 券商 API
BROKER_API_KEY=<你的券商API密钥>
BROKER_API_SECRET=<你的券商API密钥>
BROKER_API_URL=<券商接口地址>
```

### 2.2 启动服务

```bash
docker compose up -d --build
```

### 2.3 初始化数据库

```bash
# 执行 Alembic 迁移（创建表结构）
docker compose exec app alembic upgrade head
```

### 2.4 验证部署

```bash
# 检查所有服务状态
docker compose ps

# 检查应用健康
curl http://localhost/health
# 预期返回: {"status":"ok","env":"production"}
```

## 3. 环境变量说明

| 变量 | 说明 | 默认值 |
|---|---|---|
| `APP_ENV` | 运行环境 (development/staging/production) | development |
| `APP_DEBUG` | 调试模式 | true |
| `APP_SECRET_KEY` | 应用密钥 | change-me-in-production |
| `APP_ALLOWED_HOSTS` | 允许的主机名 (JSON 数组) | ["localhost","127.0.0.1"] |
| `DATABASE_URL` | PostgreSQL 连接串 | postgresql+asyncpg://postgres:password@localhost:5432/quant_db |
| `TIMESCALE_URL` | TimescaleDB 连接串 | postgresql+asyncpg://postgres:password@localhost:5433/quant_ts |
| `REDIS_URL` | Redis 连接串 | redis://localhost:6379/0 |
| `CELERY_BROKER_URL` | Celery Broker | redis://localhost:6379/1 |
| `CELERY_RESULT_BACKEND` | Celery 结果后端 | redis://localhost:6379/2 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | change-me-in-production |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 过期时间(分钟) | 60 |
| `MARKET_DATA_API_KEY` | 行情数据 API 密钥 | - |
| `BROKER_API_KEY` | 券商 API 密钥 | - |
| `BROKER_API_SECRET` | 券商 API 密钥 | - |
| `MAX_SINGLE_STOCK_POSITION` | 单只个股仓位上限 | 0.15 |
| `MAX_SECTOR_POSITION` | 单一板块仓位上限 | 0.30 |
| `DEFAULT_STOP_LOSS_RATIO` | 默认止损比例 | 0.08 |

## 4. 数据库初始化

### 4.1 自动迁移

Alembic 迁移脚本位于 `alembic/versions/`，包含：
- `001_create_kline_hypertable.py` — TimescaleDB K线超表
- `002_create_business_tables.py` — PostgreSQL 业务表

```bash
# 执行全部迁移
docker compose exec app alembic upgrade head

# 查看当前迁移版本
docker compose exec app alembic current

# 回滚一个版本
docker compose exec app alembic downgrade -1
```

### 4.2 手动验证

```bash
# 连接 PostgreSQL
docker compose exec postgres psql -U postgres -d quant_db -c "\dt"

# 连接 TimescaleDB
docker compose exec timescaledb psql -U postgres -d quant_ts -c "\dt"
```

## 5. 系统监控

### 5.1 健康检查端点

- 应用健康: `GET /health` — 返回 `{"status": "ok"}`
- 所有 Docker 服务均配置了 healthcheck，可通过 `docker compose ps` 查看状态

### 5.2 Celery 监控

```bash
# 查看 Worker 状态
docker compose exec celery-worker celery -A app.core.celery_app inspect active

# 查看任务队列长度
docker compose exec celery-worker celery -A app.core.celery_app inspect reserved

# 查看定时任务调度
docker compose exec celery-beat celery -A app.core.celery_app inspect scheduled
```

### 5.3 数据库连接监控

```bash
# PostgreSQL 活跃连接数
docker compose exec postgres psql -U postgres -d quant_db \
  -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# TimescaleDB 活跃连接数
docker compose exec timescaledb psql -U postgres -d quant_ts \
  -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Redis 连接信息
docker compose exec redis redis-cli info clients
```

### 5.4 日志查看

```bash
# 查看所有服务日志
docker compose logs -f

# 查看单个服务日志
docker compose logs -f app
docker compose logs -f celery-worker
```

## 6. Windows 部署补充

Windows 环境需安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，启用 WSL 2 后端。其余步骤与 Linux 一致：

```powershell
# PowerShell
cp .env.example .env
# 编辑 .env 配置
docker compose up -d --build
docker compose exec app alembic upgrade head
```

## 7. 常用运维命令

```bash
# 重启单个服务
docker compose restart app

# 重新构建并启动
docker compose up -d --build app

# 停止所有服务
docker compose down

# 停止并清除数据卷（慎用）
docker compose down -v

# 查看资源占用
docker stats
```
