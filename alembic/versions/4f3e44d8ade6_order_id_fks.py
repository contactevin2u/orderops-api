"""add order_id FKs for deliveries + audit_logs

Revision ID: 4f3e44d8ade6
Revises: 69026ee222d9
Create Date: 2025-08-17 12:12:23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4f3e44d8ade6"
down_revision = "69026ee222d9"
branch_labels = None
depends_on = None

def upgrade():
    # --- deliveries.order_id ---
    op.add_column('deliveries', sa.Column('order_id', sa.Integer(), nullable=True))
    op.create_index('ix_deliveries_order_id', 'deliveries', ['order_id'], unique=False)
    op.create_foreign_key('fk_deliveries_order_id_orders', 'deliveries', 'orders', ['order_id'], ['id'])

    op.execute("""
        UPDATE deliveries d
        SET order_id = o.id
        FROM orders o
        WHERE d.order_id IS NULL AND d.order_code = o.code
    """)

    op.alter_column('deliveries', 'order_id', existing_type=sa.Integer(), nullable=False)

    # --- audit_logs.order_id ---
    op.add_column('audit_logs', sa.Column('order_id', sa.Integer(), nullable=True))
    op.create_index('ix_audit_logs_order_id', 'audit_logs', ['order_id'], unique=False)
    op.create_foreign_key('fk_audit_logs_order_id_orders', 'audit_logs', 'orders', ['order_id'], ['id'])

    # Backfill only if audit_logs.order_code exists
    op.execute("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='audit_logs' AND column_name='order_code'
          ) THEN
            UPDATE audit_logs a
            SET order_id = o.id
            FROM orders o
            WHERE a.order_id IS NULL AND a.order_code = o.code;
          END IF;
        END $$;
    """)

def downgrade():
    # audit_logs (drop order_id)
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.drop_constraint('fk_audit_logs_order_id_orders', type_='foreignkey')
        batch_op.drop_index('ix_audit_logs_order_id')
        batch_op.drop_column('order_id')

    # deliveries (drop order_id)
    with op.batch_alter_table('deliveries') as batch_op:
        batch_op.drop_constraint('fk_deliveries_order_id_orders', type_='foreignkey')
        batch_op.drop_index('ix_deliveries_order_id')
        batch_op.drop_column('order_id')