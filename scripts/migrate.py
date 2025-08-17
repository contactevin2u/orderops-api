# scripts/migrate.py
import os, re, sys
from typing import Dict, Set, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

# Expected schema columns (adjust if your models differ)
EXPECTED: Dict[str, Set[str]] = {
    "orders": {
        "id","code","parent_order_id","created_at","updated_at","order_type","event_type","status",
        "customer_name","phone","address","location_url","subtotal","discount","delivery_fee",
        "return_delivery_fee","penalty_amount","buyback_amount","total","paid_initial","to_collect_initial",
        "rental_monthly_total","rental_start_date","instalment_months_total","instalment_monthly_amount",
        "instalment_start_date","notes",
    },
    "order_items": {
        "id","order_id","item_type","name","sku","text","qty","months","monthly_amount","unit_price","total",
    },
    "payments": {"id","order_id","amount","method","is_void","note","created_at"},
}

def db_url_from_env_or_cfg(cfg: Config) -> str:
    url = os.getenv("DATABASE_URL") or cfg.get_main_option("sqlalchemy.url")
    if not url:
        print("ERROR: missing DATABASE_URL / sqlalchemy.url", file=sys.stderr); sys.exit(2)
    return re.sub(r"^postgres://", "postgresql+psycopg2://", url)

def repo_head(cfg: Config) -> str:
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        print(f"ERROR: multiple heads in repo: {heads}", file=sys.stderr); sys.exit(3)
    return heads[0]

def table_exists_any_schema(conn, name: str) -> bool:
    q = text("""
        select 1
        from information_schema.tables
        where table_name = :t
        limit 1
    """)
    return conn.execute(q, {"t": name}).first() is not None

def column_names_any_schema(conn, name: str) -> Set[str]:
    q = text("""
        select column_name
        from information_schema.columns
        where table_name = :t
    """)
    return {r[0] for r in conn.execute(q, {"t": name}).fetchall()}

def schema_matches(conn) -> Tuple[bool, str]:
    for t, exp_cols in EXPECTED.items():
        if not table_exists_any_schema(conn, t):
            return False, f"missing table {t}"
        actual = column_names_any_schema(conn, t)
        missing = exp_cols - actual
        if missing:
            return False, f"table {t} missing columns: {sorted(missing)}"
    return True, "schema matches expected"

def current_db_version(conn) -> str | None:
    if not table_exists_any_schema(conn, "alembic_version"):
        return None
    try:
        r = conn.execute(text("select version_num from alembic_version")).first()
    except ProgrammingError:
        return None
    return r[0] if r else None

def ensure_version(conn, version: str) -> None:
    conn.execute(text("create table if not exists alembic_version (version_num varchar(32) not null)"))
    conn.execute(text("delete from alembic_version"))
    conn.execute(text("insert into alembic_version(version_num) values (:v)"), {"v": version})

def main():
    cfg = Config("alembic.ini")
    url = db_url_from_env_or_cfg(cfg)
    cfg.set_main_option("sqlalchemy.url", url)
    head = repo_head(cfg)
    print(f"Repo head: {head}")

    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        has_orders   = table_exists_any_schema(conn, "orders")
        has_items    = table_exists_any_schema(conn, "order_items")
        has_payments = table_exists_any_schema(conn, "payments")
        curr = current_db_version(conn)
        print(f"DB state: alembic_version={curr!r}; tables orders={has_orders}, items={has_items}, payments={has_payments}")

        if curr is None:
            if has_orders or has_items or has_payments:
                ok, msg = schema_matches(conn); print(f"Schema check: {msg}")
                if ok:
                    print("Existing schema detected without alembic_version → stamping to head (no DDL).")
                    ensure_version(conn, head); return
                print("ERROR: schema mismatch; refusing to stamp blindly.", file=sys.stderr); sys.exit(4)
            else:
                print("Fresh DB detected → upgrade to head.")
                command.upgrade(cfg, "head"); return

        if curr == head:
            print("DB already at head → nothing to do."); return

        print(f"DB at {curr}, upgrading → {head}")
        try:
            command.upgrade(cfg, "head"); print("Upgrade successful."); return
        except Exception as e:
            print(f"Upgrade failed: {e!r}")
            ok, msg = schema_matches(conn); print(f"Schema after failure: {msg}")
            if ok:
                print("Schema matches head; repairing alembic_version by stamping.")
                ensure_version(conn, head); return
            print("ERROR: schema mismatch and upgrade failed; manual action required.", file=sys.stderr)
            sys.exit(5)

if __name__ == "__main__":
    main()
