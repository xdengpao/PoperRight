#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "  A股量化选股系统 - 部署脚本"
echo "========================================="

# 1. 检查 .env 文件
if [ ! -f .env ]; then
    echo "[WARN] .env 文件不存在，从 .env.example 复制..."
    cp .env.example .env
    echo "[INFO] 请编辑 .env 配置后重新运行此脚本"
    exit 1
fi

# 2. 拉取最新代码（如果是 git 仓库）
if [ -d .git ]; then
    echo "[1/6] 拉取最新代码..."
    git pull --rebase || echo "[WARN] git pull 失败，使用本地代码继续"
else
    echo "[1/6] 非 git 仓库，跳过代码拉取"
fi

# 3. 构建前端
echo "[2/6] 构建前端..."
if [ -d frontend ]; then
    (cd frontend && npm install && npm run build)
    echo "[INFO] 前端构建完成 -> frontend/dist/"
else
    echo "[WARN] frontend 目录不存在，跳过前端构建"
fi

# 4. 停止旧容器
echo "[3/6] 停止旧容器..."
docker compose down --remove-orphans

# 5. 重新构建并启动
echo "[4/6] 构建镜像并启动服务..."
docker compose up -d --build

# 6. 等待服务就绪
echo "[5/6] 等待服务启动..."
sleep 10

# 7. 执行数据库迁移
echo "[6/6] 执行数据库迁移..."
docker compose exec -T app alembic upgrade head

echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "  服务状态："
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "  访问地址: http://localhost"
echo "  API 文档: http://localhost/api/docs"
echo "  健康检查: http://localhost/health"
echo "========================================="
