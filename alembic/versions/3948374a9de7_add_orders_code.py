"""Auto migration: add orders.code with backfill and index"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None  # set this to the actual previous revision id if you have one (e.g. "0001_init")
branch_labels = None
depends_on = None


def upgrade():
    # 1) add column nullable first
    op.add_column('orders', sa.Column('code', sa.String(length=50), nullable=True))

    # 2) backfill: ORD-<id> for any existing rows without code
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE orders SET code = CONCAT('ORD-', id) WHERE code IS NULL OR code = ''"))

    # 3) create index (non-unique for safety during transition)
    op.create_index('ix_orders_code', 'orders', ['code'], unique=False)

    # 4) make column NOT NULL (application always supplies code on create)
    op.alter_column('orders', 'code', existing_type=sa.String(length=50), nullable=False)


def downgrade():
    # reverse steps
    op.drop_index('ix_orders_code', table_name='orders')
    op.drop_column('orders', 'code')
