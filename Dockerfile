# A股右侧量化选股系统 - FastAPI 应用镜像
FROM docker.m.daocloud.io/library/python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 安装 Python 依赖（asyncpg 为纯 Python，无需 gcc/libpq-dev）
COPY pyproject.toml ./
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple . && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple gunicorn

# 复制应用代码
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

EXPOSE 8000

# 默认启动 FastAPI（可被 docker-compose command 覆盖）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
