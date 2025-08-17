import os
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic import command

def main():
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    url = os.getenv("DATABASE_URL") or cfg.get_main_option("sqlalchemy.url")

    engine = create_engine(url)
    # Prune any stale/unknown versions that cause "Can't locate revision ..." errors
    try:
        with engine.begin() as conn:
            try:
                rows = list(conn.execute(text("SELECT version_num FROM alembic_version")))
                for (ver,) in rows:
                    if not script.get_revision(ver):
                        conn.execute(text("DELETE FROM alembic_version WHERE version_num = :v"), {"v": ver})
                        print(f"Removed unknown alembic version '{ver}'")
            except Exception:
                # Table may not exist (first run). That's fine.
                pass
    finally:
        engine.dispose()

    # Perform upgrade to the single merged head
    command.upgrade(cfg, "head")

if __name__ == "__main__":
    main()