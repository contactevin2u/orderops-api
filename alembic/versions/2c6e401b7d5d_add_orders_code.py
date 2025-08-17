"""add orders.code with backfill and index"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2c6e401b7d5d"
down_revision = '3948374a9de7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    try:
        cols = [c["name"] for c in insp.get_columns("orders")]
    except Exception:
        cols = []
    if "code" not in cols:
        op.add_column("orders", sa.Column("code", sa.String(length=50), nullable=True))
        conn.execute(sa.text("UPDATE orders SET code = 'ORD-' || CAST(id AS VARCHAR) WHERE code IS NULL OR code = ''"))
        op.create_index("ix_orders_code", "orders", ["code"], unique=False)
        op.alter_column("orders", "code", existing_type=sa.String(length=50), nullable=False)


def downgrade():
    try:
        op.drop_index("ix_orders_code", table_name="orders")
    except Exception:
        pass
    try:
        op.drop_column("orders", "code")
    except Exception:
        pass
