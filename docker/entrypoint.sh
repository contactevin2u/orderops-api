#!/usr/bin/env sh
set -e

echo "[entrypoint] DATABASE_URL=${DATABASE_URL:+present}"
echo "[entrypoint] Running Alembic migrations..."
alembic heads || true; alembic history -n -20 || true; alembic upgrade head

echo "[entrypoint] Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
