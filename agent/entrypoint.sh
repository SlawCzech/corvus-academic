#!/bin/sh
set -e

echo "[agent] Running database migrations..."
alembic upgrade head

# DEBUG=true comes from infra/docker-compose.override.yml (used by `make dev`).
# Without --reload the source mounted by that override would have no effect —
# you would still have to restart the container after every edit.
RELOAD=""
if [ "$DEBUG" = "true" ]; then
    RELOAD="--reload"
    echo "[agent] DEBUG=true — auto-reload enabled"
fi

echo "[agent] Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8002 $RELOAD
