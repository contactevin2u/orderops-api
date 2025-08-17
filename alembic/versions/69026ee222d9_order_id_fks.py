"""add order_id FKs for deliveries + audit_logs (robust backfill)

Revision ID: 69026ee222d9
Revises: None
Create Date: 2025-08-17 12:53:14
"""
from alembic import op
import sqlalchemy as sa

revision = "69026ee222d9"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # deliveries.order_id
    op.add_column('deliveries', sa.Column('order_id', sa.Integer(), nullable=True))
    op.create_index('ix_deliveries_order_id', 'deliveries', ['order_id'], unique=False)
    op.create_foreign_key('fk_deliveries_order_id_orders', 'deliveries', 'orders', ['order_id'], ['id'])

    op.execute("""
        DO $$
        DECLARE orders_col text;
        BEGIN
          IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='code') THEN
            orders_col := 'code';
          ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='order_code') THEN
            orders_col := 'order_code';
          ELSE
            orders_col := NULL;
          END IF;

          IF orders_col IS NOT NULL
             AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='deliveries' AND column_name='order_code') THEN
            EXECUTE format($f$
              UPDATE deliveries d
                 SET order_id = o.id
                FROM orders o
               WHERE d.order_id IS NULL
                 AND d.order_code = o.%I
            $f$, orders_col);
          END IF;
        END $$;
    """)

    op.alter_column('deliveries', 'order_id', existing_type=sa.Integer(), nullable=False)

    # audit_logs.order_id
    op.add_column('audit_logs', sa.Column('order_id', sa.Integer(), nullable=True))
    op.create_index('ix_audit_logs_order_id', 'audit_logs', ['order_id'], unique=False)
    op.create_foreign_key('fk_audit_logs_order_id_orders', 'audit_logs', 'orders', ['order_id'], ['id'])

    op.execute("""
        DO $$
        DECLARE orders_col text;
        BEGIN
          IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='code') THEN
            orders_col := 'code';
          ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='order_code') THEN
            orders_col := 'order_code';
          ELSE
            orders_col := NULL;
          END IF;

          IF orders_col IS NOT NULL
             AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='audit_logs' AND column_name='order_code') THEN
            EXECUTE format($f$
              UPDATE audit_logs a
                 SET order_id = o.id
                FROM orders o
               WHERE a.order_id IS NULL
                 AND a.order_code = o.%I
            $f$, orders_col);
          END IF;
        END $$;
    """)

def downgrade():
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.drop_constraint('fk_audit_logs_order_id_orders', type_='foreignkey')
        batch_op.drop_index('ix_audit_logs_order_id')
        batch_op.drop_column('order_id')

    with op.batch_alter_table('deliveries') as batch_op:
        batch_op.drop_constraint('fk_deliveries_order_id_orders', type_='foreignkey')
        batch_op.drop_index('ix_deliveries_order_id')
        batch_op.drop_column('order_id')