#!/bin/sh
set -e

echo "[identity] Running database migrations..."
alembic upgrade head

echo "[identity] Seeding admin user..."
python scripts/seed_admin.py

echo "[identity] Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8003
