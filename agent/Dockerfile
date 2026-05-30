FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --no-create-home --no-log-init --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import subprocess, sys; r = subprocess.run(['celery', '-A', 'src.infrastructure.celery_app', 'inspect', 'ping', '--timeout', '5'], capture_output=True); sys.exit(0 if r.returncode == 0 else 1)" || exit 1

CMD ["celery", "-A", "src.infrastructure.celery_app", "worker", "--loglevel=info"]
