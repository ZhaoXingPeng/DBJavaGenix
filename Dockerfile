# DBJavaGenix MCP Server
# Multi-stage Dockerfile for a small runtime image.

# ---- Stage 1: builder ----------------------------------------------------
# 用 uv 解析依赖并安装到 /app/.venv,后续阶段直接复制此目录,避免在
# 运行镜像里装 build toolchain。
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# 编译某些原生扩展(如 psycopg2-binary 的依赖)需要的工具,
# 在 builder 阶段一次性装上,运行镜像不带。
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# 先只复制依赖描述文件,利用 docker layer cache: 源码变更不会重装依赖。
COPY pyproject.toml ./
COPY requirements.txt ./

RUN uv venv /app/.venv \
    && . /app/.venv/bin/activate \
    && uv pip install --no-cache-dir -r requirements.txt

# 复制源码并以 editable 方式安装包(产生 entry points)
COPY src/ ./src/
COPY config/ ./config/
RUN . /app/.venv/bin/activate \
    && uv pip install --no-cache-dir -e .

# ---- Stage 2: runtime ----------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

# 创建非 root 用户运行 (MCP server 不需要 root 权限)
RUN groupadd --system --gid 1001 dbjg \
    && useradd --system --uid 1001 --gid 1001 --create-home --shell /sbin/nologin dbjg

WORKDIR /app

COPY --from=builder --chown=dbjg:dbjg /app /app

USER dbjg

# stdio 模式 MCP server 默认入口
ENTRYPOINT ["python", "-m", "dbjavagenix.cli", "server"]
