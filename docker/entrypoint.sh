#!/usr/bin/env sh
set -e

echo "[entrypoint] DATABASE_URL=${DATABASE_URL:+present}"

if [ -f ./alembic.ini ]; then
  echo "[entrypoint] Running Alembic migrations..."
  # show heads; NEVER pass '-n -20'
  alembic heads || true
  # short history for context (optional)
  alembic history -n 20 || true
  # single-head path, else merge-heads path
  alembic upgrade head || alembic upgrade heads
fi

# Start the app on Render's assigned $PORT
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"