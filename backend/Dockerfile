# syntax=docker/dockerfile:1
# Build context is the repository root (so rules/ is available):
#   docker build -f backend/Dockerfile -t brain-agent-backend .

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --no-editable
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    RULES_DIR=/app/rules \
    FORWARDED_ALLOW_IPS=127.0.0.1
RUN useradd --system --uid 10001 --user-group --home-dir /app --no-create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app rules /app/rules
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
# sh -c so FORWARDED_ALLOW_IPS is expanded; exec keeps uvicorn as PID 1 for signal handling.
CMD ["sh", "-c", "exec uvicorn brain_agent.api.app:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
