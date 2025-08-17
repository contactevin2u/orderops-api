"""add order_id FKs for deliveries + audit_logs (idempotent; robust backfill)

Revision ID: 69026ee222d9
Revises: None
Create Date: 2025-08-17 12:57:53
"""
from alembic import op
import sqlalchemy as sa  # noqa

revision = "69026ee222d9"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # deliveries: ensure column, index, FK
    op.execute("ALTER TABLE IF EXISTS deliveries ADD COLUMN IF NOT EXISTS order_id INTEGER;")
    op.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_indexes
          WHERE indexname = 'ix_deliveries_order_id'
        ) THEN
          CREATE INDEX ix_deliveries_order_id ON deliveries (order_id);
        END IF;
      END $$;
    """)
    op.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_constraint WHERE conname = 'fk_deliveries_order_id_orders'
        ) THEN
          ALTER TABLE deliveries
            ADD CONSTRAINT fk_deliveries_order_id_orders
            FOREIGN KEY (order_id) REFERENCES orders(id);
        END IF;
      END $$;
    """)

    # deliveries: robust backfill via orders.code OR orders.order_code, only if deliveries.order_code exists
    op.execute("""
      DO $$
      DECLARE col text;
      BEGIN
        SELECT CASE
          WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='code') THEN 'code'
          WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='order_code') THEN 'order_code'
          ELSE NULL
        END INTO col;

        IF col IS NOT NULL
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='deliveries' AND column_name='order_code') THEN
          EXECUTE format('UPDATE deliveries d SET order_id=o.id FROM orders o WHERE d.order_id IS NULL AND d.order_code = o.%I', col);
        END IF;
      END $$;
    """)

    # deliveries: set NOT NULL only if backfill completed
    op.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (SELECT 1 FROM deliveries WHERE order_id IS NULL) THEN
          ALTER TABLE deliveries ALTER COLUMN order_id SET NOT NULL;
        END IF;
      END $$;
    """)

    # audit_logs: ensure column, index, FK
    op.execute("ALTER TABLE IF EXISTS audit_logs ADD COLUMN IF NOT EXISTS order_id INTEGER;")
    op.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_indexes
          WHERE indexname = 'ix_audit_logs_order_id'
        ) THEN
          CREATE INDEX ix_audit_logs_order_id ON audit_logs (order_id);
        END IF;
      END $$;
    """)
    op.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_constraint WHERE conname = 'fk_audit_logs_order_id_orders'
        ) THEN
          ALTER TABLE audit_logs
            ADD CONSTRAINT fk_audit_logs_order_id_orders
            FOREIGN KEY (order_id) REFERENCES orders(id);
        END IF;
      END $$;
    """)

    # audit_logs: robust backfill if audit_logs.order_code exists
    op.execute("""
      DO $$
      DECLARE col text;
      BEGIN
        SELECT CASE
          WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='code') THEN 'code'
          WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='order_code') THEN 'order_code'
          ELSE NULL
        END INTO col;

        IF col IS NOT NULL
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='audit_logs' AND column_name='order_code') THEN
          EXECUTE format('UPDATE audit_logs a SET order_id=o.id FROM orders o WHERE a.order_id IS NULL AND a.order_code = o.%I', col);
        END IF;
      END $$;
    """)

def downgrade():
    -- No-op safe downgrade; drop guardedly
    op.execute("""
      DO $$
      BEGIN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_audit_logs_order_id_orders') THEN
          ALTER TABLE audit_logs DROP CONSTRAINT fk_audit_logs_order_id_orders;
        END IF;
        IF EXISTS (
          SELECT 1 FROM pg_indexes WHERE indexname = 'ix_audit_logs_order_id'
        ) THEN
          DROP INDEX ix_audit_logs_order_id;
        END IF;
        IF EXISTS (
          SELECT 1 FROM information_schema.columns WHERE table_name='audit_logs' AND column_name='order_id'
        ) THEN
          ALTER TABLE audit_logs DROP COLUMN order_id;
        END IF;
      END $$;
    """)
    op.execute("""
      DO $$
      BEGIN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_deliveries_order_id_orders') THEN
          ALTER TABLE deliveries DROP CONSTRAINT fk_deliveries_order_id_orders;
        END IF;
        IF EXISTS (
          SELECT 1 FROM pg_indexes WHERE indexname = 'ix_deliveries_order_id'
        ) THEN
          DROP INDEX ix_deliveries_order_id;
        END IF;
        IF EXISTS (
          SELECT 1 FROM information_schema.columns WHERE table_name='deliveries' AND column_name='order_id'
        ) THEN
          ALTER TABLE deliveries DROP COLUMN order_id;
        END IF;
      END $$;
    """)