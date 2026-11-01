FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY main.py alembic_identity.ini alembic_mentoring.ini alembic_guidelines.ini entrypoint.sh ./
COPY alembic_identity/ ./alembic_identity/
COPY alembic_mentoring/ ./alembic_mentoring/
COPY alembic_guidelines/ ./alembic_guidelines/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.15-slim-bookworm AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/main.py /app/main.py
COPY --from=builder /app/alembic_identity.ini /app/alembic_identity.ini
COPY --from=builder /app/alembic_identity /app/alembic_identity
COPY --from=builder /app/alembic_mentoring.ini /app/alembic_mentoring.ini
COPY --from=builder /app/alembic_mentoring /app/alembic_mentoring
COPY --from=builder /app/alembic_guidelines.ini /app/alembic_guidelines.ini
COPY --from=builder /app/alembic_guidelines /app/alembic_guidelines
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --no-create-home --no-log-init --uid 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod +x /app/entrypoint.sh
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["/app/entrypoint.sh"]
