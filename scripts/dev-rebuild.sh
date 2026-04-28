#!/usr/bin/env bash
# ============================================================
# A股量化选股系统 — 重新编译并重启应用服务
#
# 问题: docker compose up 不会自动重新构建已变更的镜像
# 解决: 强制重新构建 app/celery 镜像后重启容器
#
# 用法:  bash scripts/dev-rebuild.sh            # 仅重启 app/celery
#        bash scripts/dev-rebuild.sh --no-cache  # 不使用 Docker 构建缓存
#        bash scripts/dev-rebuild.sh --all        # 同时重启 nginx
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

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
      echo "  --all       同时重建并重启 nginx 前端服务"
      exit 0
      ;;
    *)
      echo -e "${RED}未知参数: $arg${NC}"
      exit 1
      ;;
  esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  重新编译并重启应用服务${NC}"
echo -e "${GREEN}========================================${NC}"

# ── 1. 检测代码变更 ──
echo -e "\n${CYAN}[1/4] 检测代码变更...${NC}"

CHANGED_FILES=$(cd "$ROOT_DIR" && git diff --name-only HEAD 2>/dev/null || true)
if [ -z "$CHANGED_FILES" ]; then
  CHANGED_FILES=$(cd "$ROOT_DIR" && git diff --name-only --cached 2>/dev/null || true)
fi

if [ -n "$CHANGED_FILES" ]; then
  echo -e "${YELLOW}  变更文件:${NC}"
  echo "$CHANGED_FILES" | head -20 | while read -r f; do
    echo -e "    ${DIM}$f${NC}"
  done
  remaining=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
  if [ "$remaining" -gt 20 ]; then
    echo -e "    ${DIM}... 及其他 $((remaining - 20)) 个文件${NC}"
  fi
else
  echo -e "${GREEN}  无 git 变更，将强制重新构建镜像${NC}"
fi

# ── 2. 构建镜像 ──
SERVICES="app celery-worker celery-beat"
if $INCLUDE_NGINX; then
  SERVICES="$SERVICES nginx"
fi

echo -e "\n${CYAN}[2/4] 重新构建 Docker 镜像...${NC}"
echo -e "  构建服务: ${YELLOW}$SERVICES${NC}"
if [ -n "$NO_CACHE" ]; then
  echo -e "  模式: ${YELLOW}无缓存构建${NC}"
fi

docker compose -f "$ROOT_DIR/docker-compose.yml" build $NO_CACHE $SERVICES 2>&1 | while IFS= read -r line; do
  # 压缩冗余输出，只显示关键信息
  case "$line" in
    *"ERROR"*|*"error"*|*"FAIL"*)  echo -e "  ${RED}$line${NC}" ;;
    *"Step"*|*"CACHED"*|*"DONE"*|*"=>"*)  echo -e "  $line" ;;
    # 跳过纯进度行
    *) ;;
  esac
done

# 检查构建是否成功
if [ "${PIPESTATUS[0]}" -ne 0 ]; then
  echo -e "${RED}  ✗ 镜像构建失败，请检查上方错误信息${NC}"
  exit 1
fi
echo -e "${GREEN}  ✓ 镜像构建完成${NC}"

# ── 3. 滚动重启服务 ──
echo -e "\n${CYAN}[3/4] 重启应用服务...${NC}"

for svc in $SERVICES; do
  echo -ne "  重启 ${svc}..."
  docker compose -f "$ROOT_DIR/docker-compose.yml" up -d --no-deps "$svc" 2>&1 | grep -v "obsolete" || true
  echo -e " ${GREEN}✓${NC}"
done

# ── 4. 等待健康检查 ──
echo -e "\n${CYAN}[4/4] 等待服务健康检查...${NC}"

wait_healthy() {
  local svc="$1"
  local timeout="${2:-60}"
  local container
  container=$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q "$svc" 2>/dev/null)
  if [ -z "$container" ]; then
    echo -e "  ${YELLOW}⚠ ${svc}: 容器未找到${NC}"
    return
  fi
  echo -ne "  等待 ${svc}"
  for i in $(seq 1 "$timeout"); do
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
    case "$status" in
      healthy)
        echo -e " ${GREEN}✓ 健康${NC}"
        return 0
        ;;
      unhealthy)
        echo -e " ${RED}✗ 不健康${NC}"
        return 1
        ;;
      *)
        # 无 healthcheck 的容器检查是否在运行
        local running
        running=$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null || echo "false")
        if [ "$running" = "true" ]; then
          if [ "$i" -ge 5 ]; then
            echo -e " ${GREEN}✓ 运行中${NC}"
            return 0
          fi
        fi
        ;;
    esac
    echo -n "."
    sleep 1
  done
  echo -e " ${YELLOW}⚠ 等待超时${NC}"
}

wait_healthy "app" 60
wait_healthy "celery-worker" 30
wait_healthy "celery-beat" 15
$INCLUDE_NGINX && wait_healthy "nginx" 30

# ── 完成 ──
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
