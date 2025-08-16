from __future__ import annotations
import sys, os, pathlib
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure /app (repo root in container) is importable as a parent of the package "app"
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]  # /app
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Now we can import our package
from app import models
from app.settings import settings

# this Alembic Config object provides access to values within the .ini file
config = context.config

# configure Python logging
if config.config_file_name:
    fileConfig(config.config_file_name)

# Inject SQLAlchemy URL from our Pydantic settings (.env or Render env)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Provide the metadata for autogenerate
target_metadata = models.Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
