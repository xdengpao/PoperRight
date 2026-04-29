#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 本地开发一键停止脚本
# 用法: bash scripts/dev-stop.sh [--all]
#   默认只停止应用进程，Docker 基础设施保留
#   --all  同时停止 Docker 基础设施并清理状态
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/.dev-pids"
STATE_DIR="$LOG_DIR/.dev-state"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

case "${1:-}" in
  ""|--all)
    ;;
  -h|--help)
    echo "用法: bash scripts/dev-stop.sh [--all]"
    echo "  --all  同时停止 Docker 基础设施并清理状态"
    exit 0
    ;;
  *)
    echo -e "${RED}未知参数: $1${NC}"
    exit 1
    ;;
esac

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
    legacy)        [[ "$cmd" == *"uvicorn app.main:app"* || "$cmd" == *"celery -A app.core.celery_app"* || "$cmd" == *"vite"* ]] ;;
    *)             return 1 ;;
  esac
}

stop_pid() {
  local name="$1"
  local pid="$2"
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  if ! service_command_matches "$name" "$pid"; then
    echo -e "  ${DIM}跳过 ${name} (PID=$pid，命令不匹配，可能已被复用)${NC}"
    return 0
  fi

  echo "  停止 ${name} (PID=$pid)"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.5
  done
  kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
}

echo -e "${YELLOW}停止应用服务...${NC}"

for name in api celery-worker celery-beat vite; do
  pid_file="$STATE_DIR/${name}.pid"
  if [ -f "$pid_file" ]; then
    stop_pid "$name" "$(cat "$pid_file")"
    rm -f "$pid_file"
  fi
done

if [ -f "$PID_FILE" ]; then
  for pid in $(cat "$PID_FILE"); do
    [ -n "$pid" ] || continue
    stop_pid "legacy" "$pid"
  done
  rm -f "$PID_FILE"
fi

rm -f "$STATE_DIR/.last-start"

echo -e "${GREEN}  ✓ 应用服务已停止${NC}"

if [[ "${1:-}" == "--all" ]]; then
  echo -e "${YELLOW}停止 Docker 基础设施...${NC}"
  if docker compose -f "$COMPOSE_FILE" stop timescaledb postgres redis >/dev/null; then
    echo -e "${GREEN}  ✓ Docker 容器已停止${NC}"
  else
    echo -e "${RED}  ✗ Docker 容器停止失败，请检查 Docker Desktop 状态${NC}"
    exit 1
  fi
  rm -rf "$STATE_DIR"
else
  echo -e "${YELLOW}提示: Docker 基础设施仍在运行（数据库/Redis），如需停止: bash scripts/dev-stop.sh --all${NC}"
fi
