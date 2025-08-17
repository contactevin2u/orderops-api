"""initial schema for orderops"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "3e5ced67facf"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # orders
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("parent_order_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(20)),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("address", sa.Text()),
        sa.Column("location_url", sa.Text()),
        sa.Column("subtotal", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("delivery_fee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("return_delivery_fee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("penalty_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("buyback_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("paid_initial", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("to_collect_initial", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("rental_monthly_total", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("rental_start_date", sa.Date()),
        sa.Column("instalment_months_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("instalment_monthly_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("instalment_start_date", sa.Date()),
        sa.Column("notes", sa.Text()),
    )

    # self-referential FK + unique index on code
    op.create_foreign_key(
        "orders_parent_fk", "orders", "orders", ["parent_order_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_orders_code", "orders", ["code"], unique=True)

    # items
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(20)),
        sa.Column("sku", sa.String(64)),
        sa.Column("name", sa.String(255)),
        sa.Column("text", sa.Text()),
        sa.Column("qty", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("months", sa.Integer()),
        sa.Column("monthly_amount", sa.Numeric(12, 2)),
    )
    op.create_foreign_key("items_order_fk", "items", "orders", ["order_id"], ["id"], ondelete="CASCADE")

    # payments
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("method", sa.String(50)),
        sa.Column("note", sa.Text()),
    )
    op.create_foreign_key("payments_order_fk", "payments", "orders", ["order_id"], ["id"], ondelete="CASCADE")


def downgrade():
    # drop in child->parent order
    op.drop_constraint("payments_order_fk", "payments", type_="foreignkey")
    op.drop_table("payments")

    op.drop_constraint("items_order_fk", "items", type_="foreignkey")
    op.drop_table("items")

    op.drop_index("ix_orders_code", table_name="orders")
    op.drop_constraint("orders_parent_fk", "orders", type_="foreignkey")
    op.drop_table("orders")
