import os, re, sys
from alembic import context
from sqlalchemy import create_engine, pool

config = context.config

db_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not db_url:
    raise RuntimeError("DATABASE_URL or sqlalchemy.url must be set")
db_url = re.sub(r"^postgres://", "postgresql+psycopg2://", db_url)
config.set_main_option("sqlalchemy.url", db_url)

# make models importable for autogenerate (if you use it)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db import Base  # noqa: E402

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=db_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    engine = create_engine(db_url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
