#!/bin/sh
set -e

echo "[entrypoint] DATABASE_URL=${DATABASE_URL:+present}"
echo "[entrypoint] Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 10000
