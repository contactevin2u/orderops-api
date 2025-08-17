#!/usr/bin/env sh
set -eu

echo "[entrypoint] DATABASE_URL=${DATABASE_URL:+present}"

# Show current Alembic state for debugging
alembic heads || true
alembic history -n -20 || true

# Run migrations
alembic upgrade head

# Start API
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"