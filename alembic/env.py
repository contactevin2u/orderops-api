from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # using imperative migrations

def get_url():
    url = os.getenv("DATABASE_URL")
    if url and url.strip():
        return url.strip()
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and ini_url.strip():
        return ini_url.strip()
    raise SystemExit(
        "DATABASE_URL is not set. On Render (Docker) it comes from env; "
        "for local dev set it or put sqlalchemy.url in alembic.ini."
    )

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