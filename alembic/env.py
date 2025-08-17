from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # using imperative migrations

def _normalize_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgres://"):
        u = "postgresql+psycopg2://" + u[len("postgres://"):]
    return u

def get_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url and env_url.strip():
        return _normalize_url(env_url)
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and ini_url.strip():
        return _normalize_url(ini_url)
    raise SystemExit(
        "DATABASE_URL is not set. On Render it comes from the service env; "
        "for local dev set it or put sqlalchemy.url in alembic.ini."
    )

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # IMPORTANT: when prefix='' the key must be 'url'
    connectable = engine_from_config(
        {"url": get_url()},
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