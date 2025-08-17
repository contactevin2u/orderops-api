import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config
config = context.config

# logging config (optional)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# prefer DATABASE_URL from env
section = config.get_section(config.config_ini_section) or {}
env_url = os.getenv("DATABASE_URL")
if env_url:
    section["sqlalchemy.url"] = env_url

# explicit migrations only (no autogenerate metadata wired here)
target_metadata = None

def run_migrations_offline() -> None:
    url = section.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        section or config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()