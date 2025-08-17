import os, sys
import importlib
from typing import List, Dict
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase

# ---- Grab DATABASE_URL from env (Render sets it) ----
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL is not set in env.", file=sys.stderr)
    sys.exit(2)

# ---- Import Base and models ----
Base = None
tried = []
for candidate in ["app.db", "app.models", "app.app.db", "app.app.models"]:
    try:
        m = importlib.import_module(candidate)
        if hasattr(m, "Base"):
            Base = getattr(m, "Base")
            # import the module that declares models so they register with Base
            # try common places:
            for mm in ["app.models", "app.app.models"]:
                try: importlib.import_module(mm)
                except Exception: pass
            break
    except Exception as e:
        tried.append(f"{candidate}: {e}")

if Base is None:
    print("ERROR: Couldn't import Base. Tried:", tried, file=sys.stderr)
    sys.exit(3)

# ---- Connect & reflect DB ----
engine = create_engine(db_url)
insp = inspect(engine)

db_tables: List[str] = insp.get_table_names()
model_tables: List[str] = [t.name for t in Base.metadata.sorted_tables]

print("== MODELS ==")
for t in Base.metadata.sorted_tables:
    print(f"  {t.name:15} cols=", [c.name for c in t.columns])

print("\n== DATABASE ==")
print("tables =", db_tables)

def cols_of(name:str)->List[str]:
    try:
        return [c["name"] for c in insp.get_columns(name)]
    except Exception:
        return []

print("\n== DIFF (Model vs DB) ==")
all_names = sorted(set(model_tables) | set(db_tables))
problems = 0
for name in all_names:
    m_has = name in model_tables
    d_has = name in db_tables
    if not m_has and d_has:
        problems += 1
        print(f"- EXTRA in DB only: {name}")
        continue
    if m_has and not d_has:
        problems += 1
        print(f"- MISSING in DB:    {name}")
        continue
    # both exist -> compare columns
    mcols = [c.name for c in Base.metadata.tables[name].columns]
    dcols = cols_of(name)
    missing = [c for c in mcols if c not in dcols]
    extra   = [c for c in dcols if c not in mcols]
    if missing or extra:
        problems += 1
        print(f"- COLUMN mismatch in {name}:")
        if missing: print(f"    missing in DB: {missing}")
        if extra:   print(f"    extra in DB:   {extra}")

# quick look at alembic_version
if "alembic_version" in db_tables:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("select version_num from alembic_version")).all()
        print("\n== alembic_version ==")
        for r in rows:
            print("  version:", r[0])
    except Exception as e:
        print("\n(alembic_version read failed):", e)
else:
    print("\n(alembic_version table not found)")

print("\n== SUMMARY ==")
if problems == 0:
    print("OK: Models and DB look consistent.")
    sys.exit(0)
else:
    print(f"Found {problems} schema differences.")
    sys.exit(1)
