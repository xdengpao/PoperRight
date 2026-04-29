#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 本地开发一键启动脚本（混合模式）
#
# Docker 仅运行基础设施：TimescaleDB / PostgreSQL / Redis
# 应用服务在本地直接运行：FastAPI / Celery / Vite
#
# 用法:  bash scripts/dev-start.sh          # 智能启动（增量）
#        bash scripts/dev-start.sh --force   # 强制全部重启
#        bash scripts/dev-start.sh --help    # 查看帮助
# 停止:  bash scripts/dev-stop.sh  或  Ctrl-C
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
LOG_DIR="$ROOT_DIR/logs"
STATE_DIR="$LOG_DIR/.dev-state"
PID_FILE="$LOG_DIR/.dev-pids"
mkdir -p "$LOG_DIR" "$STATE_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

FORCE=false
case "${1:-}" in
  "")
    ;;
  --force)
    FORCE=true
    ;;
  -h|--help)
    echo "用法: bash scripts/dev-start.sh [--force]"
    echo "  --force  强制重启本地应用服务，并重新执行必要初始化"
    exit 0
    ;;
  *)
    echo -e "${RED}未知参数: $1${NC}"
    exit 1
    ;;
esac

PIDS=()
LAST_PID=""

# ── 工具函数 ──────────────────────────────────────────────────────────────────

cleanup() {
  echo -e "\n${YELLOW}正在停止本次脚本启动的应用服务...${NC}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  rm -f "$PID_FILE"
  echo -e "${GREEN}应用进程已停止${NC}"
  echo -e "${YELLOW}提示: Docker 基础设施仍在运行，如需停止请执行: bash scripts/dev-stop.sh --all${NC}"
  exit 0
}

trap cleanup SIGINT SIGTERM

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

compose_filtered() {
  local status
  set +e
  docker compose -f "$COMPOSE_FILE" "$@" 2>&1 | grep -v "obsolete"
  status=${PIPESTATUS[0]}
  set -e
  return "$status"
}

file_fingerprint() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "missing"
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v md5 >/dev/null 2>&1; then
    md5 -q "$file"
  else
    cksum "$file"
  fi
}

files_fingerprint() {
  local file
  for file in "$@"; do
    printf '%s:%s\n' "$file" "$(file_fingerprint "$file")"
  done | cksum
}

changed_since_last_start() {
  local dir="$1"
  local pattern="${2:-*}"
  [ -f "$STATE_DIR/.last-start" ] || return 0
  find "$dir" -name "$pattern" -type f -newer "$STATE_DIR/.last-start" -print -quit 2>/dev/null | grep -q .
}

read_state() {
  local name="$1"
  local default="${2:-none}"
  if [ -f "$STATE_DIR/$name" ]; then
    cat "$STATE_DIR/$name"
  else
    echo "$default"
  fi
}

write_state() {
  local name="$1"
  local value="$2"
  printf '%s\n' "$value" > "$STATE_DIR/$name"
}

process_command() {
  ps -p "$1" -o command= 2>/dev/null || true
}

service_command_matches() {
  local name="$1"
  local pid="$2"
  local cmd
  cmd="$(process_command "$pid")"
  case "$name" in
    api)           [[ "$cmd" == *"uvicorn app.main:app"* ]] ;;
    celery-worker) [[ "$cmd" == *"celery -A app.core.celery_app worker"* ]] ;;
    celery-beat)   [[ "$cmd" == *"celery -A app.core.celery_app beat"* ]] ;;
    vite)          [[ "$cmd" == *"vite"* && "$cmd" == *"--host"* ]] ;;
    *)             return 1 ;;
  esac
}

is_service_alive() {
  local name="$1"
  local pid_file="$STATE_DIR/${name}.pid"
  local pid
  [ -f "$pid_file" ] || return 1
  pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null && service_command_matches "$name" "$pid"
}

stop_old_process() {
  local name="$1"
  local pid_file="$STATE_DIR/${name}.pid"
  local old_pid
  [ -f "$pid_file" ] || return 0

  old_pid="$(cat "$pid_file")"
  if kill -0 "$old_pid" 2>/dev/null && service_command_matches "$name" "$old_pid"; then
    echo -e "  ${DIM}停止旧 ${name} (PID=$old_pid)${NC}"
    kill "$old_pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$old_pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -0 "$old_pid" 2>/dev/null && kill -9 "$old_pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

save_pid() {
  local name="$1"
  local pid="$2"
  echo "$pid" > "$STATE_DIR/${name}.pid"
  PIDS+=("$pid")
  LAST_PID="$pid"
}

start_service() {
  local name="$1"
  local log_file="$2"
  shift 2

  stop_old_process "$name"
  "$@" > "$log_file" 2>&1 &
  save_pid "$name" $!
  sleep 1

  if ! is_service_alive "$name"; then
    echo -e "${RED}  ✗ ${name} 启动失败，日志: ${log_file#$ROOT_DIR/}${NC}"
    tail -20 "$log_file" 2>/dev/null || true
    exit 1
  fi
}

run_migration() {
  local log_file="$LOG_DIR/alembic.log"
  cd "$ROOT_DIR"
  if alembic upgrade head > "$log_file" 2>&1; then
    tail -3 "$log_file" 2>/dev/null || true
    echo -e "${GREEN}  ✓ 数据库迁移完成${NC}"
  else
    echo -e "${RED}  ✗ 数据库迁移失败，日志: logs/alembic.log${NC}"
    tail -20 "$log_file" 2>/dev/null || true
    exit 1
  fi
}

# ── 变更检测 ──────────────────────────────────────────────────────────────────

detect_changes() {
  NEED_MIGRATION=false
  NEED_CELERY_RESTART=false
  NEED_FRONTEND_DEPS=false
  NEED_VITE_RESTART=false
  NEED_API_RESTART=false

  local backend_fp env_fp frontend_deps_fp
  backend_fp="$(files_fingerprint "$ROOT_DIR/pyproject.toml")"
  env_fp="$(files_fingerprint "$ROOT_DIR/.env" "$ROOT_DIR/docker-compose.yml")"
  frontend_deps_fp="$(files_fingerprint "$ROOT_DIR/frontend/package.json" "$ROOT_DIR/frontend/package-lock.json")"

  if [ ! -f "$STATE_DIR/.last-start" ] || $FORCE; then
    NEED_MIGRATION=true
    NEED_CELERY_RESTART=true
    NEED_FRONTEND_DEPS=true
    NEED_VITE_RESTART=true
    NEED_API_RESTART=true
    write_state "backend-deps.fp" "$backend_fp"
    write_state "env.fp" "$env_fp"
    write_state "frontend-deps.fp" "$frontend_deps_fp"
    return
  fi

  if changed_since_last_start "$ROOT_DIR/alembic" "*.py"; then
    NEED_MIGRATION=true
    echo -e "  ${YELLOW}检测到 alembic/ 变更 → 需要执行迁移${NC}"
  fi

  if changed_since_last_start "$ROOT_DIR/app" "*.py"; then
    NEED_CELERY_RESTART=true
    echo -e "  ${YELLOW}检测到 app/ 变更 → 需要重启 Celery${NC}"
  fi

  if [ "$backend_fp" != "$(read_state "backend-deps.fp")" ]; then
    NEED_API_RESTART=true
    NEED_CELERY_RESTART=true
    echo -e "  ${YELLOW}检测到 pyproject.toml 变更 → 需要重启后端进程${NC}"
  fi

  if [ "$env_fp" != "$(read_state "env.fp")" ]; then
    NEED_API_RESTART=true
    NEED_CELERY_RESTART=true
    NEED_MIGRATION=true
    echo -e "  ${YELLOW}检测到 .env/docker-compose.yml 变更 → 需要刷新基础设施和后端进程${NC}"
  fi

  if [ "$frontend_deps_fp" != "$(read_state "frontend-deps.fp")" ]; then
    NEED_FRONTEND_DEPS=true
    NEED_VITE_RESTART=true
    echo -e "  ${YELLOW}检测到 package.json/package-lock.json 变更 → 需要重新安装依赖并重启 Vite${NC}"
  fi
}

save_fingerprints() {
  write_state "backend-deps.fp" "$(files_fingerprint "$ROOT_DIR/pyproject.toml")"
  write_state "env.fp" "$(files_fingerprint "$ROOT_DIR/.env" "$ROOT_DIR/docker-compose.yml")"
  write_state "frontend-deps.fp" "$(files_fingerprint "$ROOT_DIR/frontend/package.json" "$ROOT_DIR/frontend/package-lock.json")"
}

# ── 主流程 ────────────────────────────────────────────────────────────────────

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  A股量化选股系统 — 开发环境启动${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${CYAN}[0] 检测代码变更...${NC}"
detect_changes

echo -e "\n${CYAN}[1/5] Docker 基础设施 (TimescaleDB, PostgreSQL, Redis)...${NC}"

INFRA_RUNNING=true
for svc in timescaledb postgres redis; do
  if ! compose ps --status running "$svc" 2>/dev/null | grep -q "$svc"; then
    INFRA_RUNNING=false
    break
  fi
done

if $INFRA_RUNNING; then
  echo -e "${GREEN}  ✓ 基础设施已在运行，跳过${NC}"
else
  if ! compose_filtered up -d timescaledb postgres redis; then
    echo -e "${RED}  ✗ 基础设施容器启动失败，请检查 Docker Desktop 和 docker-compose.yml${NC}"
    exit 1
  fi
  echo -e "${GREEN}  ✓ 基础设施容器已启动${NC}"

  echo -ne "${YELLOW}  等待 PostgreSQL 就绪"
  for i in $(seq 1 30); do
    if compose exec -T postgres pg_isready -q 2>/dev/null; then
      echo -e " ${GREEN}✓${NC}"
      break
    fi
    if [ "$i" -eq 30 ]; then
      echo -e " ${RED}✗ 超时${NC}"
      exit 1
    fi
    echo -n "."
    sleep 1
  done

  echo -ne "${YELLOW}  等待 Redis 就绪"
  for i in $(seq 1 15); do
    if compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
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

echo -e "\n${CYAN}[2/5] 数据库迁移...${NC}"
if $NEED_MIGRATION; then
  run_migration
else
  echo -e "${GREEN}  ✓ 无迁移变更，跳过${NC}"
fi

echo -e "\n${CYAN}[3/5] FastAPI 后端 (http://localhost:8000)...${NC}"
cd "$ROOT_DIR"

if ! $NEED_API_RESTART && is_service_alive "api"; then
  api_pid="$(cat "$STATE_DIR/api.pid")"
  PIDS+=("$api_pid")
  echo -e "${GREEN}  ✓ FastAPI 已在运行 (PID=$api_pid)，--reload 自动加载代码变更${NC}"
else
  start_service "api" "$LOG_DIR/api.log" \
    uvicorn app.main:app --reload --log-level debug --host 0.0.0.0 --port 8000
  echo -e "${GREEN}  ✓ FastAPI  PID=$LAST_PID  日志: logs/api.log${NC}"
fi

echo -e "\n${CYAN}[4/5] Celery Worker + Beat...${NC}"
cd "$ROOT_DIR"

if ! $NEED_CELERY_RESTART && is_service_alive "celery-worker"; then
  worker_pid="$(cat "$STATE_DIR/celery-worker.pid")"
  PIDS+=("$worker_pid")
  echo -e "${GREEN}  ✓ Worker 已在运行 (PID=$worker_pid)，无代码变更${NC}"
else
  start_service "celery-worker" "$LOG_DIR/celery-worker.log" \
    celery -A app.core.celery_app worker --loglevel=info -Q data_sync,screening,backtest,review --concurrency=2
  echo -e "${GREEN}  ✓ Worker   PID=$LAST_PID  日志: logs/celery-worker.log${NC}"
fi

if ! $NEED_CELERY_RESTART && is_service_alive "celery-beat"; then
  beat_pid="$(cat "$STATE_DIR/celery-beat.pid")"
  PIDS+=("$beat_pid")
  echo -e "${GREEN}  ✓ Beat 已在运行 (PID=$beat_pid)，无代码变更${NC}"
else
  start_service "celery-beat" "$LOG_DIR/celery-beat.log" \
    celery -A app.core.celery_app beat --loglevel=info
  echo -e "${GREEN}  ✓ Beat     PID=$LAST_PID  日志: logs/celery-beat.log${NC}"
fi

echo -e "\n${CYAN}[5/5] Vue 前端 (http://localhost:5173)...${NC}"
cd "$ROOT_DIR/frontend"

if $NEED_FRONTEND_DEPS || [ ! -d "node_modules" ]; then
  echo -e "${YELLOW}  安装前端依赖...${NC}"
  npm install --silent 2>&1 | tail -1
fi

if ! $NEED_VITE_RESTART && is_service_alive "vite"; then
  vite_pid="$(cat "$STATE_DIR/vite.pid")"
  PIDS+=("$vite_pid")
  echo -e "${GREEN}  ✓ Vite 已在运行 (PID=$vite_pid)，HMR 自动加载变更${NC}"
else
  start_service "vite" "$LOG_DIR/frontend.log" \
    npx vite --host 0.0.0.0
  echo -e "${GREEN}  ✓ Vite     PID=$LAST_PID  日志: logs/frontend.log${NC}"
fi

echo "${PIDS[*]}" > "$PID_FILE"
touch "$STATE_DIR/.last-start"
save_fingerprints

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
echo -e "  强制全部重启:  ${YELLOW}bash scripts/dev-start.sh --force${NC}"
echo -e "${GREEN}========================================${NC}"

wait
