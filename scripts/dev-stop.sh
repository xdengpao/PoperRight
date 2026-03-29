#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 本地开发一键停止脚本
# 用法: bash scripts/dev-stop.sh [--all]
#   默认只停止应用进程，Docker 基础设施保留
#   --all  同时停止 Docker 基础设施
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/.dev-pids"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}停止应用服务...${NC}"

# 停止 PID 文件中记录的进程
if [ -f "$PID_FILE" ]; then
  for pid in $(cat "$PID_FILE"); do
    if kill -0 "$pid" 2>/dev/null; then
      echo "  停止 PID=$pid"
      kill "$pid" 2>/dev/null || true
    fi
  done
  rm -f "$PID_FILE"
fi

# 兜底清理残留进程
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "celery -A app.core.celery_app worker" 2>/dev/null || true
pkill -f "celery -A app.core.celery_app beat" 2>/dev/null || true
pkill -f "vite.*--host" 2>/dev/null || true

echo -e "${GREEN}  ✓ 应用服务已停止${NC}"

# --all 参数时同时停止 Docker
if [[ "${1:-}" == "--all" ]]; then
  echo -e "${YELLOW}停止 Docker 基础设施...${NC}"
  docker compose -f "$ROOT_DIR/docker-compose.yml" stop timescaledb postgres redis 2>/dev/null || true
  echo -e "${GREEN}  ✓ Docker 容器已停止${NC}"
else
  echo -e "${YELLOW}提示: Docker 基础设施仍在运行（数据库/Redis），如需停止: bash scripts/dev-stop.sh --all${NC}"
fi
