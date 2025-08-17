import os
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

def get_db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return url

def clear_unknown_revision(url: str, cfg: Config):
    eng = create_engine(url, future=True)
    insp = inspect(eng)
    if not insp.has_table("alembic_version"):
        return  # fresh DB
    with eng.begin() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        current = row[0] if row else None
        if not current:
            return
        # If current isn't in our script directory, delete the row(s) so upgrade can proceed from base
        script = ScriptDirectory.from_config(cfg)
        try:
            script.get_revision(current)
        except Exception:
            conn.execute(text("DELETE FROM alembic_version"))
            print(f"Removed unknown alembic version '{current}'")

def optional_reset(url: str):
    if os.getenv("RESET_DB") != "1":
        return
    eng = create_engine(url, future=True)
    with eng.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
            print("Schema public dropped & recreated.")
        elif conn.dialect.name == "sqlite" and url.startswith("sqlite:///"):
            import os as _os
            path = url.replace("sqlite:///", "", 1)
            try:
                _os.remove(path); print(f"Removed {path}")
            except FileNotFoundError:
                pass

def main():
    url = get_db_url()
    cfg = Config("alembic.ini")
    optional_reset(url)
    clear_unknown_revision(url, cfg)
    command.upgrade(cfg, "head")
    print("Alembic upgrade head complete.")

if __name__ == "__main__":
    main()