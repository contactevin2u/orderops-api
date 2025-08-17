from alembic import op
import sqlalchemy as sa

revision = "4b2c4b3b8f9a"
down_revision = "3e5ced67facf"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "order_items" in tables:
        return

    if "items" in tables:
        op.rename_table("items", "order_items")
        op.execute("ALTER INDEX IF EXISTS ix_items_order_id RENAME TO ix_order_items_order_id")
    else:
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sku", sa.String(length=64)),
            sa.Column("name", sa.String(length=255)),
            sa.Column("qty", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("unit_price", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("item_type", sa.String(length=20), nullable=False),
        )
        op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "order_items" in tables and "items" not in tables:
        op.rename_table("order_items", "items")
        op.execute("ALTER INDEX IF EXISTS ix_order_items_order_id RENAME TO ix_items_order_id")