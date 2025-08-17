#!/usr/bin/env sh
set -e

echo "[entrypoint] DATABASE_URL=${DATABASE_URL:+present}"

if [ -f ./alembic.ini ]; then
  echo "[entrypoint] Running Alembic migrations..."
  # Show current heads and recent history (no -n on 'heads')
  alembic heads || true
  alembic history -n -20 || true
  # Try single-head upgrade; if multiple heads, upgrade all
  alembic upgrade head || alembic upgrade heads
fi

# Hand off to the image CMD/args
exec "$@"