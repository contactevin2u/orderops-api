import os, sys
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text, inspect

def needs_stamp_base(url: str, cfg: Config) -> bool:
    eng = create_engine(url, future=True)
    insp = inspect(eng)
    if not insp.has_table("alembic_version"):
        return True
    with eng.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        current = row[0] if row else None
    if not current:
        return True
    script = ScriptDirectory.from_config(cfg)
    try:
        script.get_revision(current)
        return False
    except Exception:
        return True

def reset_db_if_requested(url: str):
    if os.getenv("RESET_DB") != "1":
        return
    eng = create_engine(url, future=True)
    with eng.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
            print("Schema public dropped & recreated.")
        elif conn.dialect.name == "sqlite" and url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
            try:
                os.remove(path)
                print(f"Removed {path}")
            except FileNotFoundError:
                pass
        else:
            print(f"RESET_DB not implemented for {conn.dialect.name}", file=sys.stderr)

def main():
    cfg = Config("alembic.ini")
    url = os.environ["DATABASE_URL"]
    reset_db_if_requested(url)
    if needs_stamp_base(url, cfg):
        command.stamp(cfg, "base")
        print("Stamped base (version table was missing/unknown).")
    command.upgrade(cfg, "head")
    print("Upgraded to head.")

if __name__ == "__main__":
    main()