#!/bin/sh
set -e

echo "[app] Running identity migrations..."
alembic -c alembic_identity.ini upgrade head

# One Alembic lineage per Postgres schema — they share a database but not a
# version table, so each is upgraded on its own.
echo "[app] Running mentoring migrations..."
alembic -c alembic_mentoring.ini upgrade head

echo "[app] Running guidelines migrations..."
alembic -c alembic_guidelines.ini upgrade head

echo "[app] Seeding admin user..."
python scripts/seed_admin.py

# DEBUG=true comes from infra/docker-compose.override.yml (used by `make dev`).
# Without --reload the source mounted by that override would have no effect —
# you would still have to restart the container after every edit.
RELOAD=""
if [ "$DEBUG" = "true" ]; then
    RELOAD="--reload"
    echo "[app] DEBUG=true — auto-reload enabled"
fi

echo "[app] Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 $RELOAD
