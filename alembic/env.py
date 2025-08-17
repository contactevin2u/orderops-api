from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # we use imperative migrations

def get_url():
    # Prefer DATABASE_URL from environment (Render)
    url = os.getenv("DATABASE_URL")
    if url and url.strip():
        return url.strip()
    # Fallback to alembic.ini sqlalchemy.url if set
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and ini_url.strip():
        return ini_url.strip()
    # Friendly message (instead of SQLAlchemy ArgumentError)
    raise SystemExit("DATABASE_URL is not set. On Render this is provided via environment; locally set it or put sqlalchemy.url in alembic.ini.")

def run_migrations_offline():
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()