#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 本地开发一键启动脚本（混合模式）
#
# Docker 仅运行基础设施：TimescaleDB / PostgreSQL / Redis
# 应用服务在本地直接运行：FastAPI / Celery / Vite
#
# 特性:
#   - 首次启动：完整初始化所有服务
#   - 再次运行：检测代码变更，仅重启有更新的服务
#   - FastAPI 自带 --reload，Python 代码变更自动生效
#   - Celery worker/beat 无热重载，脚本检测 app/ 变更后自动重启
#   - Vite 自带 HMR，前端代码变更自动生效
#   - package.json 变更时自动重新安装依赖并重启 Vite
#
# 用法:  bash scripts/dev-start.sh          # 智能启动（增量）
#        bash scripts/dev-start.sh --force   # 强制全部重启
# 停止:  bash scripts/dev-stop.sh  或  Ctrl-C
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
STATE_DIR="$LOG_DIR/.dev-state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

PIDS=()

# ── 工具函数 ──────────────────────────────────────────────────────────────────

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

# 计算目录的内容指纹（基于文件修改时间）
dir_fingerprint() {
  local dir="$1"
  local pattern="${2:-*}"
  find "$dir" -name "$pattern" -type f -newer "$STATE_DIR/.last-start" 2>/dev/null | head -1
}

# 计算单个文件的 md5 指纹
file_fingerprint() {
  md5 -q "$1" 2>/dev/null || echo "none"
}

# 检查进程是否存活
is_alive() {
  kill -0 "$1" 2>/dev/null
}

# 停止指定名称的旧进程
stop_old_process() {
  local name="$1"
  local pid_file="$STATE_DIR/${name}.pid"
  if [ -f "$pid_file" ]; then
    local old_pid
    old_pid=$(cat "$pid_file")
    if is_alive "$old_pid"; then
      echo -e "  ${DIM}停止旧 ${name} (PID=$old_pid)${NC}"
      kill "$old_pid" 2>/dev/null || true
      # 等待进程退出（最多 5 秒）
      for _ in $(seq 1 10); do
        is_alive "$old_pid" || break
        sleep 0.5
      done
      # 强制杀死
      is_alive "$old_pid" && kill -9 "$old_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

# 保存进程 PID
save_pid() {
  local name="$1"
  local pid="$2"
  echo "$pid" > "$STATE_DIR/${name}.pid"
  PIDS+=("$pid")
}

# ── 变更检测 ──────────────────────────────────────────────────────────────────

detect_changes() {
  NEED_MIGRATION=false
  NEED_CELERY_RESTART=false
  NEED_FRONTEND_DEPS=false
  NEED_VITE_RESTART=false
  NEED_API_RESTART=false

  # 首次启动（无状态文件）→ 全部需要
  if [ ! -f "$STATE_DIR/.last-start" ] || $FORCE; then
    NEED_MIGRATION=true
    NEED_CELERY_RESTART=true
    NEED_FRONTEND_DEPS=true
    NEED_VITE_RESTART=true
    NEED_API_RESTART=true
    return
  fi

  # 检查 alembic 迁移脚本是否有变更
  if [ -n "$(dir_fingerprint "$ROOT_DIR/alembic" "*.py")" ]; then
    NEED_MIGRATION=true
    echo -e "  ${YELLOW}检测到 alembic/ 变更 → 需要执行迁移${NC}"
  fi

  # 检查 Python 后端代码是否有变更
  if [ -n "$(dir_fingerprint "$ROOT_DIR/app" "*.py")" ]; then
    NEED_CELERY_RESTART=true
    echo -e "  ${YELLOW}检测到 app/ 变更 → 需要重启 Celery${NC}"
    # FastAPI 有 --reload，不需要手动重启，但如果进程不在了需要启动
  fi

  # 检查 package.json 是否有变更
  local pkg_fp
  pkg_fp=$(file_fingerprint "$ROOT_DIR/frontend/package.json")
  local old_pkg_fp="none"
  [ -f "$STATE_DIR/package.json.md5" ] && old_pkg_fp=$(cat "$STATE_DIR/package.json.md5")
  if [ "$pkg_fp" != "$old_pkg_fp" ]; then
    NEED_FRONTEND_DEPS=true
    NEED_VITE_RESTART=true
    echo -e "  ${YELLOW}检测到 package.json 变更 → 需要重新安装依赖并重启 Vite${NC}"
  fi

  # 检查前端源码变更（Vite 有 HMR，通常不需要重启，但如果进程不在了需要启动）
  # 这里不主动重启 Vite，只在进程死亡时重启
}

# 检查某个服务进程是否还活着
check_service_alive() {
  local name="$1"
  local pid_file="$STATE_DIR/${name}.pid"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    if is_alive "$pid"; then
      return 0  # 活着
    fi
  fi
  return 1  # 不在了
}

# ── 主流程 ────────────────────────────────────────────────────────────────────

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  A股量化选股系统 — 开发环境启动${NC}"
echo -e "${GREEN}========================================${NC}"

# 变更检测
echo -e "\n${CYAN}[0] 检测代码变更...${NC}"
detect_changes

# ── 1. 启动基础设施 ──
echo -e "\n${CYAN}[1/5] Docker 基础设施 (TimescaleDB, PostgreSQL, Redis)...${NC}"

# 检查容器是否已在运行
INFRA_RUNNING=true
for svc in timescaledb postgres redis; do
  if ! docker compose -f "$ROOT_DIR/docker-compose.yml" ps --status running "$svc" 2>/dev/null | grep -q "$svc"; then
    INFRA_RUNNING=false
    break
  fi
done

if $INFRA_RUNNING; then
  echo -e "${GREEN}  ✓ 基础设施已在运行，跳过${NC}"
else
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
fi

# ── 2. 数据库迁移 ──
echo -e "\n${CYAN}[2/6] 数据库迁移...${NC}"
if $NEED_MIGRATION; then
  cd "$ROOT_DIR"
  if alembic upgrade head 2>&1 | tail -3; then
    echo -e "${GREEN}  ✓ 数据库迁移完成${NC}"
  else
    echo -e "${YELLOW}  ⚠ 迁移可能有警告，继续启动${NC}"
  fi
else
  echo -e "${GREEN}  ✓ 无迁移变更，跳过${NC}"
fi

# ── 3. 重建 Docker 应用镜像 ──
echo -e "\n${CYAN}[3/6] 重建 Docker 应用镜像 (app + celery-worker)...${NC}"
if $NEED_CELERY_RESTART || $NEED_API_RESTART; then
  docker compose -f "$ROOT_DIR/docker-compose.yml" up -d --build app celery-worker 2>&1 | grep -v "obsolete" || true
  echo -e "${GREEN}  ✓ Docker app + celery-worker 镜像已重建并启动${NC}"
else
  echo -e "${GREEN}  ✓ 无代码变更，跳过镜像重建${NC}"
fi

# ── 4. 启动 FastAPI 后端 ──
echo -e "\n${CYAN}[4/6] FastAPI 后端 (http://localhost:8000)...${NC}"
cd "$ROOT_DIR"

if ! $NEED_API_RESTART && check_service_alive "api"; then
  api_pid=$(cat "$STATE_DIR/api.pid")
  PIDS+=("$api_pid")
  echo -e "${GREEN}  ✓ FastAPI 已在运行 (PID=$api_pid)，--reload 自动加载代码变更${NC}"
else
  stop_old_process "api"
  uvicorn app.main:app \
    --reload \
    --log-level debug \
    --host 0.0.0.0 \
    --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 &
  save_pid "api" $!
  echo -e "${GREEN}  ✓ FastAPI  PID=$!  日志: logs/api.log${NC}"
fi

# ── 5. 启动 Celery Worker + Beat ──
echo -e "\n${CYAN}[5/6] Celery Worker + Beat...${NC}"
cd "$ROOT_DIR"

# Worker
if ! $NEED_CELERY_RESTART && check_service_alive "celery-worker"; then
  worker_pid=$(cat "$STATE_DIR/celery-worker.pid")
  PIDS+=("$worker_pid")
  echo -e "${GREEN}  ✓ Worker 已在运行 (PID=$worker_pid)，无代码变更${NC}"
else
  stop_old_process "celery-worker"
  celery -A app.core.celery_app worker \
    --loglevel=info \
    -Q data_sync,screening,backtest,review \
    --concurrency=2 \
    > "$LOG_DIR/celery-worker.log" 2>&1 &
  save_pid "celery-worker" $!
  echo -e "${GREEN}  ✓ Worker   PID=$!  日志: logs/celery-worker.log${NC}"
fi

# Beat
if ! $NEED_CELERY_RESTART && check_service_alive "celery-beat"; then
  beat_pid=$(cat "$STATE_DIR/celery-beat.pid")
  PIDS+=("$beat_pid")
  echo -e "${GREEN}  ✓ Beat 已在运行 (PID=$beat_pid)，无代码变更${NC}"
else
  stop_old_process "celery-beat"
  celery -A app.core.celery_app beat \
    --loglevel=info \
    > "$LOG_DIR/celery-beat.log" 2>&1 &
  save_pid "celery-beat" $!
  echo -e "${GREEN}  ✓ Beat     PID=$!  日志: logs/celery-beat.log${NC}"
fi

# ── 6. 启动前端 Vite 开发服务器 ──
echo -e "\n${CYAN}[6/6] Vue 前端 (http://localhost:5173)...${NC}"
cd "$ROOT_DIR/frontend"

# 检查是否需要安装依赖
if $NEED_FRONTEND_DEPS || [ ! -d "node_modules" ]; then
  echo -e "${YELLOW}  安装前端依赖...${NC}"
  npm install --silent 2>&1 | tail -1
  # 保存 package.json 指纹
  file_fingerprint "$ROOT_DIR/frontend/package.json" > "$STATE_DIR/package.json.md5"
fi

if ! $NEED_VITE_RESTART && check_service_alive "vite"; then
  vite_pid=$(cat "$STATE_DIR/vite.pid")
  PIDS+=("$vite_pid")
  echo -e "${GREEN}  ✓ Vite 已在运行 (PID=$vite_pid)，HMR 自动加载变更${NC}"
else
  stop_old_process "vite"
  npx vite --host 0.0.0.0 \
    > "$LOG_DIR/frontend.log" 2>&1 &
  save_pid "vite" $!
  echo -e "${GREEN}  ✓ Vite     PID=$!  日志: logs/frontend.log${NC}"
fi

# ── 保存状态 ──
echo "${PIDS[*]}" > "$LOG_DIR/.dev-pids"
touch "$STATE_DIR/.last-start"

# 首次启动时保存 package.json 指纹
if [ ! -f "$STATE_DIR/package.json.md5" ]; then
  file_fingerprint "$ROOT_DIR/frontend/package.json" > "$STATE_DIR/package.json.md5"
fi

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
echo -e "  再次运行脚本:  ${YELLOW}仅重启有代码变更的服务${NC}"
echo -e "  强制全部重启:  ${YELLOW}bash scripts/dev-start.sh --force${NC}"
echo -e "${GREEN}========================================${NC}"

# 前台等待
wait
