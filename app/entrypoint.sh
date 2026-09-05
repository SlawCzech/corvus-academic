#!/bin/sh
set -e

echo "[app] Running identity migrations..."
alembic -c alembic_identity.ini upgrade head

echo "[app] Seeding admin user..."
python scripts/seed_admin.py

echo "[app] Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
