#!/bin/sh
set -e

echo "[agent] Running database migrations..."
alembic upgrade head

echo "[agent] Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8002
