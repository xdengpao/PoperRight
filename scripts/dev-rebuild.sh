#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 重新编译并重启 Docker 应用服务
#
# 用法:  bash scripts/dev-rebuild.sh             # 重建 app/celery 镜像并重启
#        bash scripts/dev-rebuild.sh --no-cache  # 不使用 Docker 构建缓存
#        bash scripts/dev-rebuild.sh --all       # 额外重启 nginx
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

NO_CACHE=""
INCLUDE_NGINX=false

for arg in "$@"; do
  case "$arg" in
    --no-cache) NO_CACHE="--no-cache" ;;
    --all)      INCLUDE_NGINX=true ;;
    -h|--help)
      echo "用法: bash scripts/dev-rebuild.sh [--no-cache] [--all]"
      echo "  --no-cache  不使用 Docker 构建缓存（完整重编译）"
      echo "  --all       同时重启 nginx 前端服务"
      exit 0
      ;;
    *)
      echo -e "${RED}未知参数: $arg${NC}"
      exit 1
      ;;
  esac
done

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

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  重新编译并重启 Docker 应用服务${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${CYAN}[1/4] 检测代码变更...${NC}"

CHANGED_FILES="$(cd "$ROOT_DIR" && git status --short 2>/dev/null || true)"
if [ -n "$CHANGED_FILES" ]; then
  echo -e "${YELLOW}  变更文件:${NC}"
  echo "$CHANGED_FILES" | head -20 | while read -r line; do
    echo -e "    ${DIM}$line${NC}"
  done
  remaining="$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')"
  if [ "$remaining" -gt 20 ]; then
    echo -e "    ${DIM}... 及其他 $((remaining - 20)) 个文件${NC}"
  fi
else
  echo -e "${GREEN}  无 git 变更，将重新构建镜像${NC}"
fi

BUILD_SERVICES="app celery-worker celery-beat"
RESTART_SERVICES="$BUILD_SERVICES"
if $INCLUDE_NGINX; then
  RESTART_SERVICES="$RESTART_SERVICES nginx"
fi

echo -e "\n${CYAN}[2/4] 重新构建 Docker 镜像...${NC}"
echo -e "  构建服务: ${YELLOW}$BUILD_SERVICES${NC}"
if [ -n "$NO_CACHE" ]; then
  echo -e "  模式: ${YELLOW}无缓存构建${NC}"
fi

if ! compose_filtered build $NO_CACHE $BUILD_SERVICES; then
  echo -e "${RED}  ✗ 镜像构建失败，请检查上方错误信息${NC}"
  exit 1
fi
echo -e "${GREEN}  ✓ 镜像构建完成${NC}"

echo -e "\n${CYAN}[3/4] 重启应用服务...${NC}"

for svc in $RESTART_SERVICES; do
  echo -ne "  重启 ${svc}..."
  set +e
  restart_output="$(compose_filtered up -d --no-deps "$svc")"
  restart_status=$?
  set -e
  if [ "$restart_status" -eq 0 ]; then
    echo -e " ${GREEN}✓${NC}"
  else
    echo -e " ${RED}✗${NC}"
    [ -n "$restart_output" ] && echo "$restart_output"
    echo -e "${RED}  ${svc} 重启失败，请检查 docker compose 输出${NC}"
    exit 1
  fi
done

echo -e "\n${CYAN}[4/4] 等待服务健康检查...${NC}"

wait_healthy() {
  local svc="$1"
  local timeout="${2:-60}"
  local container
  container="$(compose ps -q "$svc" 2>/dev/null)"
  if [ -z "$container" ]; then
    echo -e "  ${RED}✗ ${svc}: 容器未找到${NC}"
    return 1
  fi

  echo -ne "  等待 ${svc}"
  for i in $(seq 1 "$timeout"); do
    local status
    status="$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")"
    case "$status" in
      healthy)
        echo -e " ${GREEN}✓ 健康${NC}"
        return 0
        ;;
      unhealthy)
        echo -e " ${RED}✗ 不健康${NC}"
        compose logs --tail=80 "$svc" 2>/dev/null || true
        return 1
        ;;
      *)
        local running
        running="$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null || echo "false")"
        if [ "$running" = "true" ] && [ "$i" -ge 5 ]; then
          echo -e " ${GREEN}✓ 运行中${NC}"
          return 0
        fi
        ;;
    esac
    echo -n "."
    sleep 1
  done

  echo -e " ${RED}✗ 等待超时${NC}"
  compose logs --tail=80 "$svc" 2>/dev/null || true
  return 1
}

HEALTH_FAILED=false
wait_healthy "app" 60 || HEALTH_FAILED=true
wait_healthy "celery-worker" 30 || HEALTH_FAILED=true
wait_healthy "celery-beat" 15 || HEALTH_FAILED=true
if $INCLUDE_NGINX; then
  wait_healthy "nginx" 30 || HEALTH_FAILED=true
fi

if $HEALTH_FAILED; then
  echo -e "${RED}  ✗ 存在服务未通过健康检查${NC}"
  exit 1
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  重新编译并重启完成${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  后端 API:    ${CYAN}http://localhost:8000${NC}"
echo -e "  API 文档:    ${CYAN}http://localhost:8000/docs${NC}"
if $INCLUDE_NGINX; then
  echo -e "  前端页面:    ${CYAN}http://localhost:80${NC}"
fi
echo -e ""
echo -e "  查看日志:    ${YELLOW}docker compose -f docker-compose.yml logs -f app${NC}"
echo -e "  查看状态:    ${YELLOW}docker compose -f docker-compose.yml ps${NC}"
echo -e "${GREEN}========================================${NC}"
