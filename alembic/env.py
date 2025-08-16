import os, sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# Ensure backend/app is importable
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

# Load .env next to backend folder
ENV_PATH = os.path.abspath(os.path.join(BASE_DIR, ".env"))
load_dotenv(ENV_PATH)

config = context.config
fileConfig(config.config_file_name)

from app import models
target_metadata = models.Base.metadata

def run_migrations_offline():
    url = os.getenv('DATABASE_URL') or config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = os.getenv('DATABASE_URL', configuration.get("sqlalchemy.url"))
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
