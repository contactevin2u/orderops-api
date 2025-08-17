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
        sa.Column("parent_order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),   # RENTAL | INSTALMENT | OUTRIGHT | BUYBACK
        sa.Column("event_type", sa.String(20), nullable=True),    # DELIVERY | RETURN | CANCEL | BUYBACK
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("location_url", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("delivery_fee", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("return_delivery_fee", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("penalty_amount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("buyback_amount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("paid_initial", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("to_collect_initial", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("rental_monthly_total", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("rental_start_date", sa.Date(), nullable=True),
        sa.Column("instalment_months_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("instalment_monthly_amount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("instalment_start_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_orders_code", "orders", ["code"], unique=True)
    op.create_index("ix_orders_status", "orders", ["status"])

    # order_items
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),  # RENTAL | INSTALMENT | OUTRIGHT | FEE | DELIVERY | RETURN_DELIVERY | PENALTY | BUYBACK
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("qty", sa.Numeric(10,2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12,2), nullable=True),
        sa.Column("line_total", sa.Numeric(12,2), nullable=True),
        sa.Column("months", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # payments (cash basis; can be voided)
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("method", sa.String(50), nullable=True),  # CASH | TRANSFER | TNG | CHEQUE
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("voided", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])

    # products (optional SKU mapping)
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_price", sa.Numeric(12,2), nullable=True),
        sa.Column("item_type", sa.String(20), nullable=True),  # OUTRIGHT | RENTAL | ACCESSORY | FEE
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ux_products_sku", "products", ["sku"], unique=True)

    # messages (raw + parsed whatsapp)
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("parsed_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ux_messages_sha256", "messages", ["sha256"], unique=True)

def downgrade():
    op.drop_index("ux_messages_sha256", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ux_products_sku", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_code", table_name="orders")
    op.drop_table("orders")
