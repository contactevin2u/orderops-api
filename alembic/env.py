import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

load_dotenv()  # optional: lets you keep DATABASE_URL in a .env during local dev

config = context.config
section = config.get_section(config.config_ini_section) or {}

# prefer env DATABASE_URL if present
db_url = os.getenv("DATABASE_URL", section.get("sqlalchemy.url"))
if not db_url:
    raise RuntimeError("DATABASE_URL is not set and sqlalchemy.url not configured.")
section["sqlalchemy.url"] = db_url

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # we're using explicit migrations (no autogenerate here)

def run_migrations_offline():
    context.configure(
        url=section["sqlalchemy.url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
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