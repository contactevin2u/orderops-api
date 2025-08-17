import os
import sys
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set.", file=sys.stderr)
        sys.exit(2)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)

    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    print(f"Repo head: {head}")

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    has_version_tbl = "alembic_version" in tables
    print(f"DB state: alembic_version={has_version_tbl}; tables orders={'orders' in tables}, items={'items' in tables}, payments={'payments' in tables}")

    if not tables:
        # clean DB: run full upgrade
        command.upgrade(cfg, "head")
        return

    if has_version_tbl:
        # already tracked by alembic; just upgrade
        command.upgrade(cfg, "head")
        return

    # tables exist but no alembic_version -> refuse to guess
    print("ERROR: schema mismatch; refusing to stamp blindly.", file=sys.stderr)
    # optional: deeper diff to help debugging
    missing = []
    expected = {"orders","items","payments"}
    for t in sorted(expected):
        if t not in tables:
            missing.append(t)
    if missing:
        print(f"Missing tables: {missing}", file=sys.stderr)
    sys.exit(4)

if __name__ == "__main__":
    main()