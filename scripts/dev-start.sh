#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 本地开发一键启动脚本（混合模式）
#
# Docker 仅运行基础设施：TimescaleDB / PostgreSQL / Redis
# 应用服务在本地直接运行：FastAPI / Celery / Vite
#
# 用法:  bash scripts/dev-start.sh
# 停止:  bash scripts/dev-stop.sh  或  Ctrl-C
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PIDS=()

cleanup() {
  echo -e "\n${YELLOW}正在停止所有服务...${NC}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  echo -e "${GREEN}应用进程已停止${NC}"
  echo -e "${YELLOW}提示: Docker 基础设施仍在运行，如需停止请执行: bash scripts/dev-stop.sh${NC}"
  rm -f "$LOG_DIR/.dev-pids"
  exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  A股量化选股系统 — 开发环境启动${NC}"
echo -e "${GREEN}========================================${NC}"

# ── 1. 启动基础设施 ──
echo -e "\n${CYAN}[1/5] 启动 Docker 基础设施 (TimescaleDB, PostgreSQL, Redis)...${NC}"
docker compose -f "$ROOT_DIR/docker-compose.yml" up -d timescaledb postgres redis 2>&1 | grep -v "obsolete" || true
echo -e "${GREEN}  ✓ 基础设施容器已启动${NC}"

# 等待 PostgreSQL 就绪
echo -ne "${YELLOW}  等待 PostgreSQL 就绪"
for i in $(seq 1 30); do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres pg_isready -q 2>/dev/null; then
    echo -e " ${GREEN}✓${NC}"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo -e " ${RED}✗ 超时${NC}"
    echo -e "${RED}  PostgreSQL 未能在 30 秒内就绪，请检查 Docker Desktop 是否正常运行${NC}"
    exit 1
  fi
  echo -n "."
  sleep 1
done

# 等待 Redis 就绪
echo -ne "${YELLOW}  等待 Redis 就绪"
for i in $(seq 1 15); do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo -e " ${GREEN}✓${NC}"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo -e " ${RED}✗ 超时${NC}"
    exit 1
  fi
  echo -n "."
  sleep 1
done

# ── 2. 数据库迁移 ──
echo -e "\n${CYAN}[2/5] 执行数据库迁移...${NC}"
cd "$ROOT_DIR"
if alembic upgrade head 2>&1 | tail -3; then
  echo -e "${GREEN}  ✓ 数据库迁移完成${NC}"
else
  echo -e "${YELLOW}  ⚠ 迁移可能有警告，继续启动${NC}"
fi

# ── 3. 启动 FastAPI 后端 ──
echo -e "\n${CYAN}[3/5] 启动 FastAPI 后端 (http://localhost:8000)...${NC}"
cd "$ROOT_DIR"
uvicorn app.main:app \
  --reload \
  --log-level debug \
  --host 0.0.0.0 \
  --port 8000 \
  > "$LOG_DIR/api.log" 2>&1 &
PIDS+=($!)
echo -e "${GREEN}  ✓ FastAPI  PID=$!  日志: logs/api.log${NC}"

# ── 4. 启动 Celery Worker + Beat ──
echo -e "\n${CYAN}[4/5] 启动 Celery Worker + Beat...${NC}"
cd "$ROOT_DIR"

celery -A app.core.celery_app worker \
  --loglevel=debug \
  -Q data_sync,screening,backtest,review \
  --concurrency=2 \
  > "$LOG_DIR/celery-worker.log" 2>&1 &
PIDS+=($!)
echo -e "${GREEN}  ✓ Worker   PID=$!  日志: logs/celery-worker.log${NC}"

celery -A app.core.celery_app beat \
  --loglevel=debug \
  > "$LOG_DIR/celery-beat.log" 2>&1 &
PIDS+=($!)
echo -e "${GREEN}  ✓ Beat     PID=$!  日志: logs/celery-beat.log${NC}"

# ── 5. 启动前端 Vite 开发服务器 ──
echo -e "\n${CYAN}[5/5] 启动 Vue 前端 (http://localhost:5173)...${NC}"
cd "$ROOT_DIR/frontend"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
  echo -e "${YELLOW}  安装前端依赖...${NC}"
  npm install --silent 2>&1 | tail -1
fi

npx vite --host 0.0.0.0 \
  > "$LOG_DIR/frontend.log" 2>&1 &
PIDS+=($!)
echo -e "${GREEN}  ✓ Vite     PID=$!  日志: logs/frontend.log${NC}"

# ── 保存 PID ──
echo "${PIDS[*]}" > "$LOG_DIR/.dev-pids"

# ── 等待服务就绪 ──
sleep 2

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  所有服务已启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  后端 API:  ${CYAN}http://localhost:8000${NC}"
echo -e "  API 文档:  ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  前端页面:  ${CYAN}http://localhost:5173${NC}"
echo -e "  日志目录:  ${CYAN}logs/${NC}"
echo -e ""
echo -e "  实时查看日志:  ${YELLOW}tail -f logs/api.log${NC}"
echo -e "  按 ${RED}Ctrl+C${NC} 停止应用服务"
echo -e "${GREEN}========================================${NC}"

# 前台等待
wait
